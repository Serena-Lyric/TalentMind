#!/usr/bin/env python3
"""JD Filter (M2) —— 3-LLM 管道：解析原始JD → 去重 → 提取 → 合并 → 中英文双语输出。

用法:
  # 设置 API Key
  set LLM_API_KEY=sk-xxxx
  # 运行完整管道
  python main.py
  # 指定输入文件
  python main.py data/my_jd_pool.sql
  # 强制重新运行（忽略断点）
  python main.py --force
  # 与存量结果对比
  python main.py --existing exchange/m2/job_definition.json

输出: exchange/m2/
  job_definition.json      岗位定义
  job_skill.json           技能详情（含evidence）
  job_change_log.json      与存量对比的变更日志
  pipeline_report.json     管道统计报告
  rejected.json            被拒记录
  manual_review.json       需人工复核的记录
"""
import sys
import os
from .config import LLM_API_KEY


def _show_help():
    print(__doc__)
    print("参数:")
    print("  --force              清除断点，从头运行")
    print("  --existing PATH      与存量 job_definition.json 对比")
    print("  --output DIR         输出目录（默认 exchange/m2）")
    print("  --help               显示此帮助")
    print()
    print("模型配置（环境变量）:")
    print("  LLM_API_KEY              API Key（必填）")
    print("  LLM_BASE_URL             基础URL（默认 DeepSeek）")
    print("  JD_MODEL_STAGE1          模型1-相关性（默认 deepseek-v4-flash）")
    print("  JD_MODEL_STAGE2          模型2-质量（默认 deepseek-v4-pro）")
    print("  JD_MODEL_STAGE3          模型3-提取（默认 deepseek-v4-pro）")
    print("  JD_MODEL_DUTIES_DIFF     模型4-变更对比（默认 deepseek-v4-flash）")


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        _show_help()
        return

    if not LLM_API_KEY:
        print("[错误] 请设置环境变量 LLM_API_KEY")
        sys.exit(1)

    if "--reset" in sys.argv:
        from db_state import StateDB
        db = StateDB()
        db._conn.execute("DELETE FROM records")
        db._conn.execute("DELETE FROM stats")
        db._commit()
        print("[reset] state.db 已清空")

    from pipeline import run_pipeline

    force = "--force" in sys.argv
    existing = next((sys.argv[i + 1] for i, a in enumerate(sys.argv)
                     if a == "--existing" and i + 1 < len(sys.argv)), None)
    output = next((sys.argv[i + 1] for i, a in enumerate(sys.argv)
                    if a == "--output" and i + 1 < len(sys.argv)), None)
    cross_src = next((sys.argv[i + 1] for i, a in enumerate(sys.argv)
                      if a == "--cross-source" and i + 1 < len(sys.argv)),
                     None)
    # 默认自动找数据包里的交叉验证报告
    if not cross_src:
        from pathlib import Path as _P
        _default_cross = _P(r"c:/Users/admin/Desktop/m2-data-pack/岗位数据"
                            r"/cross_validate_report.md")
        if _default_cross.exists():
            cross_src = str(_default_cross)
    input_path = next((a for a in sys.argv[1:]
                       if not a.startswith("--")
                       and a not in (existing or "", output or "",
                                     cross_src or "")), None)

    if input_path and input_path.lower().endswith(".json"):
        # JSON 输入：转成临时 SQL 文件，由 pipeline 统一 ingest
        import json as _json
        import tempfile
        with open(input_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        rows = []
        for d in data:
            rows.append(
                "INSERT INTO `jd_pool` VALUES (%d,'%s','%s','%s','%s','%s',"
                "%s,'%s','%s','%s');" % (
                    int(d["id"]), d.get("source", "linkedin"),
                    str(d.get("job_title", "")).replace("'", "\\'"),
                    str(d.get("raw_text", "")).replace("'", "\\'")
                    .replace("\n", "\\n"),
                    str(d.get("duties", "")).replace("'", "\\'"),
                    str(d.get("experience", "")).replace("'", "\\'"),
                    float(d.get("quality", 0.8)),
                    d.get("dup_group", ""),
                    d.get("crawled_at", ""),
                    d.get("status", "cleaned"),
                ))
        tmpf = tempfile.NamedTemporaryFile(
            "w", suffix=".sql", delete=False, encoding="utf-8")
        tmpf.write("\n".join(rows))
        tmpf.close()
        input_path = tmpf.name
        print(f"[json输入] {len(rows)} 条 -> 临时 SQL")

    run_pipeline(
        input_path=input_path,
        output_dir=output,
        force=force,
        existing_job_defs_path=existing,
        cross_source_path=cross_src,
    )


if __name__ == "__main__":
    main()
