"""管道编排 —— ingest → L0 → L1 → 分块流水线（记录级断点）→ 合并/diff/翻译/导出。"""
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import (PipelineStats, MergedJobDefinition, MergedJobSkillDetail,
                    RejectedItem, JdRecord, JobChangeLog)
from .db import parse_jd_pool
from .db_state import StateDB
from .rules import apply_rules, segment_text
from .stage1_relevance import run_stage1
from .stage2_quality import run_stage2
from .stage3_extract import run_stage3
from .merge import merge_jobs
from .differ import diff_jobs
from .export import export_all, _load_json
from .llm import LLMClient, reset_cost_counters, get_cost_summary
from .config import (SKILL_DICT_PATH, DATA_DIR, EXCHANGE_DIR,
                    POST_VERIFY_AFTER_AGGREGATE)

CHUNK_SIZE = 200


def _row_to_record(row: dict, use_seg: bool = True) -> JdRecord:
    return JdRecord(
        id=row["id"], source=row["source"], job_title=row["job_title"],
        raw_text=(row["seg_text"] or row["raw_text"]) if use_seg
        else row["raw_text"],
        duties=row["duties"], experience=row["experience"],
        quality=row["quality"], dup_group=row["dup_group"],
        crawled_at=row["crawled_at"], status="cleaned")


def _load_cross_source_ids(path: str | None) -> set[int]:
    if not path:
        return set()
    # cross_validate_report.md 解析：行格式 "| hn id | linkedin id | ..."
    ids = set()
    for line in open(path, encoding="utf-8").read().splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|", line)
        if m:
            ids.update(int(x) for x in m.groups())
    return ids


async def _run_pipeline_async(
    input_path: str,
    output_dir: Path,
    force: bool = False,
    existing_job_defs_path: str | None = None,
    accuracy: float | None = None,
    cross_source_path: str | None = None,
) -> PipelineStats:
    reset_cost_counters()
    db = StateDB()
    rejected: list[RejectedItem] = []
    manual: list[dict] = []
    change_logs: list[JobChangeLog] = []

    # ═══ ingest ═══
    records = parse_jd_pool(input_path)
    print(f"[ingest] 加载 {len(records)} 条")
    cross_ids = _load_cross_source_ids(cross_source_path)
    stats = db.ingest(records, cross_source_ids=cross_ids, force=force)
    print(f"         新增 {stats.new}, 重复跳过 {stats.dup_skipped}")

    # ═══ 增量：消失 JD 检测（新快照里没有的已处理 id → 记下架）═══
    if not force:
        snapshot_ids = {r.id for r in records}
        gone_ids = [
            r["id"] for r in db.rows_where("done") + db.rows_where("s3_pass")
            + db.rows_where("s2_pass") + db.rows_where("s1_pass")
            if r["id"] not in snapshot_ids
        ]
        if gone_ids:
            now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            for gid in gone_ids:
                db._conn.execute(
                    "UPDATE records SET status='removed', "
                    "reject_reason='job delisted from new snapshot' "
                    "WHERE id=?", (gid,))
                rec = db.get_record(gid)
                if rec:
                    change_logs.append(JobChangeLog(
                        job_id=str(gid),
                        change_type="removed", object_type="job",
                        skill_name=rec.get("job_title", ""),
                        detail={"old_value": rec.get("job_title", ""),
                                "new_value": None},
                        source=[rec.get("source", "")],
                        reason="岗位从新快照下架",
                        created_at=now_ts,
                    ))
            db._commit()
            print(f"         下架 {len(gone_ids)} 条 -> 变更日志")

    # ═══ L0 硬规则（含分层切割缓存）═══
    print("[L0] 硬规则预筛")
    # ingest 已处理 force 重置（记录回到 pending），这里直接取 pending
    pending_rows = db.pending("s1")
    fresh = [_row_to_record(r, use_seg=False) for r in pending_rows]
    passed_rules, rejected_rules = apply_rules(fresh)
    rejected.extend(rejected_rules)
    for r in passed_rules:
        seg = segment_text(r)
        db._conn.execute(
            "UPDATE records SET seg_text=?, status='s1_pass' WHERE id=?",
            (seg["a_text"], r.id))
    for rj in rejected_rules:
        db._conn.execute(
            "UPDATE records SET status='rejected', reject_reason=? "
            "WHERE id=? AND status='pending'",
            (f"rules_{rj.rule_id}", rj.jd_id))
    db._commit()
    print(f"         L0 通过: {len(passed_rules)}, 拒绝: {len(rejected_rules)}")

    # go 端点 client（L5 验证/联网查证用）；L2/L4 在 stage 内部
    # 自动创建官方 DeepSeek 端点 client（实测 11s/批 vs go 107s/批）
    client = LLMClient()
    term_lookup = None
    try:
        # ═══ L1 BM25 预筛（hn 直通，linkedin 过筛）+ 客观技术信号层 ═══
        from prefilter import build_prefilter
        from tech_signal import build_scorer
        from new_term_lookup import TermLookup
        s1_rows = db.rows_where("s1_pass")
        hn_rows = [r for r in s1_rows if r["source"] == "hn"]
        # 客观技术信号 scorer（全管道复用；信号文件可选；自学习词回灌）
        from config import SIGNAL_SNAPSHOT_PATH
        from tech_signal import load_learned_terms
        tech_scorer = build_scorer(
            SKILL_DICT_PATH,
            SIGNAL_SNAPSHOT_PATH if SIGNAL_SNAPSHOT_PATH.exists() else None,
            learned_terms=load_learned_terms())
        # 联网新词查证器（仅不确定区触发；网络失败自动降级）
        term_lookup = TermLookup()
        if hn_rows:
            pf = build_prefilter(SKILL_DICT_PATH,
                                 [r["raw_text"][:2000] for r in hn_rows])
            candidates = []
            for r in s1_rows:
                if r["source"] == "hn" or pf.should_pass(
                        r["seg_text"] or r["raw_text"]):
                    candidates.append(r)
                else:
                    db.mark_done(r["id"], "s1", "reject")
                    rejected.append(RejectedItem(
                        jd_id=r["id"], rule_id="prefilter_reject",
                        stage="L1", detail="bm25 score below threshold"))
            print(f"[L1] BM25 预筛: {len(candidates)}/{len(s1_rows)} 进 LLM")
        else:
            candidates = s1_rows
            print(f"[L1] 预筛占位: {len(candidates)} 条进 LLM 漏斗")

        # ═══ 分块流水线 ═══
        # L2_L4_SERIAL=True 时：先全部 L2（含标题+正文），再全部 L4
        # （官方 flash 单 key 限流，重叠导致 missing 风暴）
        from config import L2_L4_SERIAL
        print(f"[L2-L5] 分块流水线 (串行模式={L2_L4_SERIAL})")
        final_s3: list = []
        stage_counts = {"stage1_passed": 0, "stage1_rejected": 0,
                        "stage1_manual": 0, "stage2_passed": 0,
                        "stage2_rejected": 0, "stage2_manual": 0,
                        "stage3_passed": 0, "stage3_manual": 0}
        verify_totals = {"skills_extracted": 0,
                         "verified_by_two_models": 0,
                         "removed_hallucinated": 0,
                         "downgraded_suspicious": 0}
        for i in range(0, len(candidates), CHUNK_SIZE):
            chunk = candidates[i:i + CHUNK_SIZE]
            print(f"  块 {i // CHUNK_SIZE + 1}: {len(chunk)} 条")
            recs = [_row_to_record(r) for r in chunk]
            # L2a 标题快筛（只看名字，flash 批量，极快）
            from title_filter import run_title_filter
            title_verdicts = await run_title_filter(recs, None)
            title_rejected = [r for r in recs
                              if title_verdicts.get(r.id, {}).get("verdict")
                              == "nontech"]
            title_passed = [r for r in recs
                            if title_verdicts.get(r.id, {}).get("verdict")
                            == "tech"]
            unclear_recs = [r for r in recs
                            if r not in title_rejected
                            and r not in title_passed]
            for r in title_rejected:
                stage_counts["stage1_rejected"] += 1
                rejected.append(RejectedItem(
                    jd_id=r.id, rule_id="title_nontech",
                    stage="model1",
                    detail=f"title rule: {r.job_title}"))
                db.mark_done(r.id, "s1", "reject")
            for r in title_passed:
                stage_counts["stage1_passed"] += 1
                db.mark_done(r.id, "s1", "pass")
            print(f"        L2a 标题: 拒 {len(title_rejected)}, "
                  f"过 {len(title_passed)}, 模糊 {len(unclear_recs)} 进正文判定")
            # L2b 正文判定（只处理模糊标题，传 None → 官方端点 client）
            passed_s1, results_s1 = await run_stage1(
                unclear_recs, None, tech_scorer=tech_scorer,
                term_lookup=term_lookup)
            for rec, res in zip(unclear_recs, results_s1):
                if res.verdict == "retry":
                    # API 错误：不改状态，下次续跑自动重试
                    continue
                if res.verdict == "reject":
                    stage_counts["stage1_rejected"] += 1
                    rejected.append(RejectedItem(
                        jd_id=rec.id, rule_id="relevance_reject",
                        stage="model1", detail=res.reasoning))
                    db.mark_done(rec.id, "s1", "reject", res.model_dump())
                elif res.verdict == "manual":
                    # 全自动模式：manual 一律按 reject 收口（保留原因）
                    stage_counts["stage1_rejected"] += 1
                    rejected.append(RejectedItem(
                        jd_id=rec.id, rule_id="relevance_auto_reject",
                        stage="model1", detail=res.reasoning))
                    db.mark_done(rec.id, "s1", "reject", res.model_dump())
                else:
                    stage_counts["stage1_passed"] += 1
                    db.mark_done(rec.id, "s1", "pass", res.model_dump())
            # 标题直接通过的 + 正文判定通过的 = 最终通过集
            passed_s1 = title_passed + passed_s1
            print(f"        L2 通过: {len(passed_s1)}/{len(recs)}")
            # L3
            passed_s2, results_s2 = await run_stage2(
                passed_s1, client, cross_source_ids=cross_ids)
            for rec, res in zip(passed_s1, results_s2):
                if res.verdict == "reject":
                    stage_counts["stage2_rejected"] += 1
                    rejected.append(RejectedItem(
                        jd_id=rec.id, rule_id="quality_reject",
                        stage="model2", detail=res.weak_points))
                    db.mark_done(rec.id, "s2", "reject", res.model_dump())
                elif res.verdict == "manual":
                    # 全自动模式：质量中间带按 reject 收口
                    stage_counts["stage2_rejected"] += 1
                    rejected.append(RejectedItem(
                        jd_id=rec.id, rule_id="quality_auto_reject",
                        stage="model2", detail=res.weak_points))
                    db.mark_done(rec.id, "s2", "reject", res.model_dump())
                else:
                    stage_counts["stage2_passed"] += 1
                    db.mark_done(rec.id, "s2", "pass", res.model_dump())
            print(f"        L3 通过: {len(passed_s2)}/{len(passed_s1)}")
            # L4（传 None → stage 内部创建官方 DeepSeek 端点 client）
            # 串行模式：L2 全部完成才跑 L4（防 flash 竞争）
            # 逐条落库：每批完成立即写 s3_json（断点续跑/进度可见）
            def _l4_chunk_done(chunk_recs, chunk_results):
                for rec, resp in zip(chunk_recs, chunk_results):
                    if isinstance(resp, dict) and "_error" not in resp:
                        db._conn.execute(
                            "UPDATE records SET s3_json=? WHERE id=?",
                            (json.dumps(resp, ensure_ascii=False), rec.id))
                db._commit()

            # ═══ L4→L5 流水线：L4 每解析完一条立即送 L5 worker 消费 ═══
            # asyncio 单线程，无需锁（await 之间不会被打断）
            from merge import normalize_job_type
            pending_results: list = []      # L4 完成待 L5 的结果
            acc_groups: dict = {}           # key -> 累积组（跨批次合并）
            verified_counts: dict = {}      # key -> 上次验证时的 JD 数
            final_verdicts: dict = {}       # key -> verdict

            def _l4_result_cb(result):
                """L4 单条完成：入流水线队列。"""
                if result.verdict != "pass":
                    return
                pending_results.append(result)

            async def _l5_worker():
                """L5 消费：攒批验证，结果缓存（不应用）。"""
                from verify import run_verify_aggregated
                while True:
                    if not pending_results:
                        if l4_finished.is_set():
                            break
                        await asyncio.sleep(1.0)
                        continue
                    batch = pending_results[:]
                    pending_results.clear()
                    # 累积合并到 acc_groups（同 key 跨批次不丢）
                    batch_groups: dict[str, dict] = {}
                    for res in batch:
                        key = normalize_job_type(res.job_name)
                        g = batch_groups.setdefault(key, {
                            "full_texts": [], "skills": [], "results": []})
                        g["full_texts"].append(
                            full_text_map.get(res.jd_id, res.core_duties))
                        g["skills"].extend(
                            res.required_skills + res.bonus_skills)
                        g["results"].append(res)
                        # 同步累积
                        acc = acc_groups.setdefault(key, {
                            "full_texts": [], "skills": [], "results": []})
                        acc["full_texts"].append(
                            full_text_map.get(res.jd_id, res.core_duties))
                        acc["skills"].extend(
                            res.required_skills + res.bonus_skills)
                        acc["results"].append(res)
                    if not batch_groups:
                        continue
                    verdicts = await run_verify_aggregated(
                        client, batch_groups)
                    for key in batch_groups:
                        final_verdicts[key] = verdicts.get(key)
                        verified_counts[key] = len(acc_groups[key]["results"])

            full_text_map = {r["id"]: r["raw_text"] for r in chunk}
            # L3 清洗：L5 验证文本必须与 L4 提取输入一致
            # （L4 用清洗后文本，evidence 引用清洗后文字）
            from l3_clean import clean_jd_text
            full_text_map = {k: clean_jd_text(v)
                             for k, v in full_text_map.items()}
            l4_finished = asyncio.Event()
            l5_task = asyncio.create_task(_l5_worker())

            results_s3, manual_s3 = await run_stage3(
                passed_s2, None, on_chunk_done=_l4_chunk_done,
                on_result=_l4_result_cb)
            l4_finished.set()     # L4 完成，通知 worker 处理剩余
            await l5_task         # 等 L5 消化完

            # L4 完成后：对验证时组不完整的 key 补一次完整验证
            from verify import run_verify_aggregated
            incomplete = {k: g for k, g in acc_groups.items()
                          if verified_counts.get(k, 0)
                          < len(g["results"])}
            if incomplete:
                v2 = await run_verify_aggregated(client, incomplete)
                for k in incomplete:
                    final_verdicts[k] = v2.get(k)

            # ═══ L5 统一应用（L4 全部完成后，按 key 完整应用）═══
            for key, g in acc_groups.items():
                v = final_verdicts.get(key)
                verify_totals["skills_extracted"] += sum(
                    len(s["skills"]) for s in [g])
                if v is None or v.get("null"):
                    for res in g["results"]:
                        for sk in res.required_skills + res.bonus_skills:
                            sk.verification = "verified"
                        db.mark_done(res.jd_id, "s3", "pass",
                                     res.model_dump())
                    continue
                removed_names = set(v["removed"])
                down_names = set(v["downgraded"])
                for res in g["results"]:
                    for sk in res.required_skills + res.bonus_skills:
                        if sk.name.lower() in removed_names:
                            verify_totals["removed_hallucinated"] += 1
                            sk.verification = "removed"
                        elif sk.name.lower() in down_names:
                            verify_totals["downgraded_suspicious"] += 1
                            sk.verification = "suspicious"
                            sk.confidence = max(0.0, sk.confidence - 0.15)
                        else:
                            sk.verification = "verified"
                            verify_totals["verified_by_two_models"] += 1
                    res.required_skills = [
                        s for s in res.required_skills
                        if s.verification != "removed"]
                    res.bonus_skills = [
                        s for s in res.bonus_skills
                        if s.verification != "removed"]
                    db.mark_done(res.jd_id, "s3", "pass",
                                 res.model_dump())
            # 提取失败重试耗尽 → reject（记录原因）
            failed_ids = set()
            for res in results_s3:
                if res.verdict == "manual":
                    failed_ids.add(res.jd_id)
                    rejected.append(RejectedItem(
                        jd_id=res.jd_id, rule_id="extract_failed",
                        stage="model3",
                        detail="extraction validation failed after retries"))
                    db.mark_done(res.jd_id, "s3", "reject", res.model_dump())
            results_s3 = [r for r in results_s3 if r.verdict != "manual"]
            for res in results_s3:
                stage_counts["stage3_passed"] += 1
            # ── 技能不足过滤（用户决策：未达标的去掉）──
            # 只滤"成功提取但技能 <3"的真残缺；
            # 0 技能的 = 提取失败（hn 脏标题等），不滤（另行兜底）
            MIN_SKILLS = 3
            for res in results_s3:
                total_skills = len(res.required_skills) + len(
                    res.bonus_skills)
                if 0 < total_skills < MIN_SKILLS:
                    rejected.append(RejectedItem(
                        jd_id=res.jd_id, rule_id="insufficient_skills",
                        stage="model3",
                        detail=f"only {total_skills} skills after "
                               f"verification (min {MIN_SKILLS})"))
                    db.mark_done(res.jd_id, "s3", "reject", res.model_dump())
                    res.verdict = "reject"
                elif total_skills == 0 and res.model and \
                        "API error" not in res.model:
                    # 0 技能且提取"成功"（无错误记录）= 模型真没提出技能
                    # → 也滤掉（垃圾 JD 残留），不因提取失败误删
                    rejected.append(RejectedItem(
                        jd_id=res.jd_id, rule_id="no_skills_extracted",
                        stage="model3",
                        detail="extraction succeeded but 0 skills"))
                    db.mark_done(res.jd_id, "s3", "reject", res.model_dump())
                    res.verdict = "reject"
            results_s3 = [r for r in results_s3 if r.verdict == "pass"]
            # L5 已由流水线 worker 在 L4 进行中增量完成（见上方 _l5_worker）
            for res in results_s3:
                if not (res.required_skills or res.bonus_skills):
                    db.mark_done(res.jd_id, "s3", "pass", res.model_dump())
            print(f"        L4 提取: {len(results_s3)} 条, "
                  f"幻觉删除: {verify_totals['removed_hallucinated']}")
            final_s3.extend(results_s3)

        passed_s3 = [r for r in final_s3 if r.verdict == "pass"]

        # ═══ 合并 / diff / 导出 ═══
        print("[合并] 合并层")
        job_defs, job_skills = merge_jobs(passed_s3)
        print(f"       合并后岗位: {len(job_defs)} (原始 {len(passed_s3)})")

        # ── 合并后过滤 ──
        # 1. >50 技能的复合岗位（hn 多岗位聚合帖）→ 剔除
        # 2. 岗位名含 multiple/multi- 的复合帖 → 剔除
        #    （赛题要求"一个类型一条定义"，混多岗位不符）
        MAX_MERGED_SKILLS = 50
        keep_defs = []
        removed_big = 0
        removed_multi = 0
        for jd in job_defs:
            n = len(jd.required_skills) + len(jd.bonus_skills)
            name_low = jd.job_name.lower()
            if n > MAX_MERGED_SKILLS:
                removed_big += 1
                continue
            if "multiple" in name_low or "multi-" in name_low:
                removed_multi += 1
                continue
            keep_defs.append(jd)
        if removed_big:
            print(f"       剔除复合岗位(>50技能): {removed_big} 个")
        if removed_multi:
            print(f"       剔除多岗位聚合帖: {removed_multi} 个")
        job_defs = keep_defs
        kept_names = {jd.job_name for jd in job_defs}
        job_skills = [s for s in job_skills if s.job_name in kept_names]

        print("[对比] 对比层")
        existing_defs: dict[str, MergedJobDefinition] = {}
        existing_skills: dict[str, MergedJobSkillDetail] = {}
        if existing_job_defs_path:
            ed_path = Path(existing_job_defs_path)
            if ed_path.exists():
                for item in (_load_json(ed_path) or []):
                    jd = MergedJobDefinition(**item)
                    existing_defs[jd.job_name.strip().lower()] = jd
                esk_path = ed_path.parent / "job_skill.json"
                if esk_path.exists():
                    for item in (_load_json(esk_path) or []):
                        js = MergedJobSkillDetail(**item)
                        existing_skills[js.job_name.strip().lower()] = js
        job_defs, job_skills, change_logs = await diff_jobs(
            job_defs, job_skills, existing_defs, existing_skills)
        print(f"       变更日志: {len(change_logs)} 条")

        print("[导出] 导出")
        # M2 回包的中文展示名由专用翻译层负责；中文标题本身可直接作为展示名。
        for definition in job_defs:
            if not definition.job_name_zh and any("\u4e00" <= char <= "\u9fff" for char in definition.job_name):
                definition.job_name_zh = definition.job_name
        cost = get_cost_summary()
        # 成本估算：按各模型 token 计费（MODEL_COST 表，未列模型兜底）
        from config import MODEL_COST
        est_usd = 0.0
        for model, tok in cost.get("model_tokens", {}).items():
            p_cost, c_cost = MODEL_COST.get(model, (0.80, 2.00))
            est_usd += (tok["prompt"] / 1_000_000 * p_cost
                        + tok["completion"] / 1_000_000 * c_cost)
        cost["estimated_cost_usd"] = round(est_usd, 4)
        hc = dict(verify_totals)
        hc["hallucination_rate"] = (
            f"{hc['removed_hallucinated'] / max(hc['skills_extracted'], 1) * 100:.1f}%")
        stats = export_all(job_defs, job_skills, change_logs, rejected,
                           manual, output_dir, accuracy, cost,
                           hallucination_control=hc,
                           stage_counts=stage_counts)

        print(f"\n完成! {stats.model_dump_json(indent=2)}")
        return stats
    finally:
        await client.close()
        if term_lookup is not None:
            await term_lookup.close()


def run_pipeline(
    input_path: str | None = None,
    output_dir: str | None = None,
    force: bool = False,
    existing_job_defs_path: str | None = None,
    accuracy: float | None = None,
    cross_source_path: str | None = None,
) -> PipelineStats:
    """主入口：运行完整漏斗管道。"""
    inp = input_path or str(DATA_DIR / "seed_jd_pool.sql")
    # 如果 data/ 下没有，尝试从桌面加载
    if not Path(inp).exists():
        inp = str(Path(__file__).parent.parent.parent / "seed_jd_pool.sql")
    od = Path(output_dir) if output_dir else EXCHANGE_DIR
    return asyncio.run(_run_pipeline_async(
        inp, od, force, existing_job_defs_path, accuracy, cross_source_path))


async def stage1_only(input_path: str, output_path: str):
    """单独运行模型1（调试用）。"""
    from db import parse_jd_pool
    from rules import apply_rules
    records = parse_jd_pool(input_path)
    passed_rules, _ = apply_rules(records)
    client = LLMClient()
    try:
        passed_s1, results_s1 = await run_stage1(passed_rules, client)
    finally:
        await client.close()
    from export import _write_json
    _write_json(Path(output_path).parent, Path(output_path).name,
                [r.model_dump() for r in results_s1])
    print(f"模型1完成: {len(passed_s1)}/{len(passed_rules)} 通过 "
          f"-> {output_path}")


async def stage2_only(input_path: str, output_path: str):
    """单独运行模型2（调试用）。"""
    from models import JdRecord
    parent = Path(input_path).parent
    s1_path = parent / "s1_passed.json"
    if not s1_path.exists():
        raise FileNotFoundError(f"需要 s1_passed.json: {s1_path}")
    with open(s1_path, "r", encoding="utf-8") as f:
        records = [JdRecord(**item) for item in json.load(f)]
    with open(input_path, "r", encoding="utf-8") as f:
        s2_data = json.load(f)
    passed_s1_ids = {d["jd_id"] for d in s2_data if d.get("verdict") == "pass"}
    passed_records = [r for r in records if r.id in passed_s1_ids]
    client = LLMClient()
    try:
        passed_s2, results_s2 = await run_stage2(passed_records, client)
    finally:
        await client.close()
    from export import _write_json
    _write_json(parent, Path(output_path).name,
                [r.model_dump() for r in results_s2])
    print(f"模型2完成: {len(passed_s2)}/{len(passed_records)} 通过 "
          f"-> {output_path}")


def merge_manual_review(review_path: str, job_defs_path: str) -> None:
    """合并人工复核结果到 job_definition.json。"""
    with open(review_path, "r", encoding="utf-8") as f:
        reviews = json.load(f)
    with open(job_defs_path, "r", encoding="utf-8") as f:
        defs = json.load(f)

    approved = [r for r in reviews
                if r.get("review_status") in ("approved", "modified")]
    for r in approved:
        if r.get("modified_fields"):
            defs.append(r["modified_fields"])

    with open(job_defs_path, "w", encoding="utf-8") as f:
        json.dump(defs, f, ensure_ascii=False, indent=2)
    print(f"合并 {len(approved)} 条人工复核记录 -> {job_defs_path}")
