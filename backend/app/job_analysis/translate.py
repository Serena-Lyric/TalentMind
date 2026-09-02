"""翻译层 —— 将 job_definition.json 译为中文版本。"""
import json
import asyncio
from pathlib import Path
from app.job_analysis.llm import call_llm_batch
from app.job_analysis.config import MODEL_STAGE1, SLOT_POOLS  # 翻译用便宜模型

TRANSLATE_SYSTEM = """You are a professional technical translator. Translate job descriptions from English to Chinese.

Rules:
- Keep technical proper nouns in English (e.g., "Python", "Kubernetes", "AWS", "RAG", "LLM", "Figma", "Docker", "PostgreSQL", "Redis", "TypeScript", "Node.js", "React", "Vue")
- Job titles should be returned in a separate `job_name_zh` display field (e.g., "Senior Backend Engineer" → "高级后端工程师")
- Keep JSON structure unchanged, only translate display text values
- core_duties, scenarios: translate fully to natural Chinese
- job_name_zh: translate to a natural Chinese display title; keep `job_name` as the stable English key
- required_skills and bonus_skills are canonical keys and MUST remain unchanged; never translate skill names
- General/soft skills SHOULD be translated only in display text, never in skill arrays:
  "communication skills" → "沟通能力"
  "people management" → "人员管理"
  "problem-solving" → "问题解决能力"
  "project management" → "项目管理"
  "analytical skills" → "分析能力"
  "user support" → "用户支持"
  "vendor management" → "供应商管理"
  "change management" → "变更管理"
  "teamwork" → "团队协作"
  "presentation skills" → "演讲能力"
  etc.
- Source and field names should remain in English"""


def _build_translate_prompt(job_def: dict, index: int) -> str:
    """Build a translation prompt for a single job definition."""
    translatable = {
        "job_name": job_def.get("job_name", ""),
        "core_duties": job_def.get("core_duties", ""),
        "scenarios": job_def.get("scenarios", []),
    }
    return f"""Translate this job definition to Chinese.
- Technical proper nouns (Python, AWS, Docker, Kubernetes, Redis, etc.) keep in English.
- Keep canonical skill arrays unchanged; they are identifiers, not display text.

{json.dumps(translatable, ensure_ascii=False, indent=2)}

Output ONLY a JSON object with these display keys:
{{"job_name_zh": "...", "core_duties": "...", "scenarios": ["..."]}}"""


def _items(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return value["items"]
    return []


async def translate_job_definitions(
    input_path: str,
    output_path: str,
    model: str = "",
) -> list[dict]:
    """翻译 job_definition.json 为中文版。"""
    model = model or SLOT_POOLS["translate"][0]

    with open(input_path, "r", encoding="utf-8") as f:
        job_defs = _items(json.load(f))

    if not job_defs:
        return []

    prompts = [_build_translate_prompt(d, i) for i, d in enumerate(job_defs)]
    responses = await call_llm_batch(
        prompts, model, system=TRANSLATE_SYSTEM, max_concurrent=5,
    )

    zh_defs = []
    for i, (original, resp) in enumerate(zip(job_defs, responses)):
        zh = dict(original)  # copy all fields
        if "_error" not in resp:
            zh["job_name_zh"] = resp.get("job_name_zh", resp.get("job_name", original.get("job_name", "")))
            zh["job_name"] = original.get("job_name", "")
            zh["core_duties"] = resp.get("core_duties", original.get("core_duties", ""))
            zh["scenarios"] = resp.get("scenarios", original.get("scenarios", []))
            zh["required_skills"] = list(original.get("required_skills", []))
            zh["bonus_skills"] = list(original.get("bonus_skills", []))
        # else keep original English
        zh_defs.append(zh)

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(zh_defs, f, ensure_ascii=False, indent=2)

    print(f"      中文版: {len(zh_defs)} 条 -> {output_path}")
    return zh_defs


def translate_sync(input_path: str, output_path: str, model: str = "") -> list[dict]:
    """同步包装器。"""
    return asyncio.run(translate_job_definitions(input_path, output_path, model))


async def translate_job_skills(
    input_path: str,
    output_path: str,
    model: str = "",
) -> list[dict]:
    """复制 job_skill.json，保留英文关联 key 和 canonical 技能名不变。"""
    del model
    with open(input_path, "r", encoding="utf-8") as f:
        skill_data = _items(json.load(f))
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(skill_data, f, ensure_ascii=False, indent=2)
    return skill_data

async def translate_change_logs(
    input_path: str,
    output_path: str,
    model: str = "",
) -> list[dict]:
    """翻译 job_change_log.json 中的文本字段为中文。"""
    model = model or SLOT_POOLS["translate"][0]

    with open(input_path, "r", encoding="utf-8") as f:
        logs = _items(json.load(f))

    if not logs:
        # 空的 changelog，直接复制
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        return logs

    # 收集需要翻译的文本
    texts_to_translate: list[dict] = []
    for i, log in enumerate(logs):
        if log.get("reason"):
            texts_to_translate.append({"idx": i, "field": "reason", "text": log["reason"]})
        # detail 中可能有 duties_changed、summary 等
        if log.get("detail"):
            for k, v in log["detail"].items():
                if isinstance(v, str) and len(v) > 20:
                    texts_to_translate.append({"idx": i, "field": f"detail.{k}", "text": v})

    if not texts_to_translate:
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        return logs

    prompts = [
        f'Translate this technical description to Chinese. Keep technical terms in English.\n\n{t["text"]}\n\nOutput ONLY a JSON object: {{"zh": "..."}}'
        for t in texts_to_translate
    ]
    responses = await call_llm_batch(
        prompts, model, system=TRANSLATE_SYSTEM, max_concurrent=5,
    )

    for t, resp in zip(texts_to_translate, responses):
        if "_error" not in resp and resp.get("zh"):
            if t["field"] == "reason":
                logs[t["idx"]]["reason"] = resp["zh"]
            elif t["field"].startswith("detail."):
                key = t["field"].split(".", 1)[1]
                logs[t["idx"]]["detail"][key] = resp["zh"]

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

    print(f"      变更日志中文版: {len(logs)} 条 -> {output_path}")
    return logs
