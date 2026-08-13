"""翻译层 —— 将 job_definition.json 译为中文版本。"""
import json
import asyncio
from pathlib import Path
from app.job_analysis.llm import call_llm_batch
from app.job_analysis.config import MODEL_STAGE1  # 翻译用便宜模型

TRANSLATE_SYSTEM = """You are a professional technical translator. Translate job descriptions from English to Chinese.

Rules:
- Keep technical proper nouns in English (e.g., "Python", "Kubernetes", "AWS", "RAG", "LLM", "Figma", "Docker", "PostgreSQL", "Redis", "TypeScript", "Node.js", "React", "Vue")
- Job titles should be natural Chinese (e.g., "Senior Backend Engineer" → "高级后端工程师")
- Keep JSON structure unchanged, only translate text values
- core_duties, scenarios: translate fully to natural Chinese
- job_name: translate to natural Chinese job title
- General/soft skills SHOULD be translated:
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
        "required_skills": job_def.get("required_skills", []),
        "bonus_skills": job_def.get("bonus_skills", []),
    }
    return f"""Translate this job definition to Chinese.
- Technical proper nouns (Python, AWS, Docker, Kubernetes, Redis, etc.) keep in English.
- General/soft skills (communication, management, analytical, etc.) translate to natural Chinese.

{json.dumps(translatable, ensure_ascii=False, indent=2)}

Output ONLY a JSON object with the same keys, values translated to Chinese:
{{"job_name": "...", "core_duties": "...", "scenarios": ["..."], "required_skills": ["..."], "bonus_skills": ["..."]}}"""


async def translate_job_definitions(
    input_path: str,
    output_path: str,
    model: str = "",
) -> list[dict]:
    """翻译 job_definition.json 为中文版。"""
    model = model or MODEL_STAGE1

    with open(input_path, "r", encoding="utf-8") as f:
        job_defs = json.load(f)

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
            zh["job_name"] = resp.get("job_name", original.get("job_name", ""))
            zh["core_duties"] = resp.get("core_duties", original.get("core_duties", ""))
            zh["scenarios"] = resp.get("scenarios", original.get("scenarios", []))
            zh["required_skills"] = resp.get("required_skills", original.get("required_skills", []))
            zh["bonus_skills"] = resp.get("bonus_skills", original.get("bonus_skills", []))
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
    """翻译 job_skill.json 中的 job_name 和技能名为中文。"""
    model = model or MODEL_STAGE1

    with open(input_path, "r", encoding="utf-8") as f:
        skill_data = json.load(f)

    if not skill_data:
        return []

    # 收集所有 job_name + skill names 去重
    job_names = list({item["job_name"] for item in skill_data})
    skill_names: list[str] = []
    seen_skills = set()
    for item in skill_data:
        for sk in item.get("skills", []):
            name = sk["name"]
            if name not in seen_skills:
                seen_skills.add(name)
                skill_names.append(name)

    # 翻译 job_name
    job_prompts = [
        f'Translate this job title to natural Chinese. Keep technical terms in English.\n\n"{name}"\n\nOutput ONLY a JSON object: {{"zh": "..."}}'
        for name in job_names
    ]
    job_responses = await call_llm_batch(
        job_prompts, model, system=TRANSLATE_SYSTEM, max_concurrent=5,
    )
    name_map: dict[str, str] = {}
    for original, resp in zip(job_names, job_responses):
        if "_error" not in resp:
            name_map[original] = resp.get("zh", original)
        else:
            name_map[original] = original

    # 翻译 skill names（技术名词保留英文，通用技能翻译）
    BATCH = 20
    skill_map: dict[str, str] = {}
    for i in range(0, len(skill_names), BATCH):
        batch = skill_names[i:i + BATCH]
        prompts = [
            f'Translate this skill name to Chinese. Technical proper nouns (Python, AWS, Docker, Figma, Kubernetes, etc.) MUST stay in English. General/soft skills (communication, management, analytical, etc.) translate to natural Chinese.\n\n"{name}"\n\nOutput ONLY a JSON object: {{"zh": "..."}}'
            for name in batch
        ]
        responses = await call_llm_batch(
            prompts, model, system=TRANSLATE_SYSTEM, max_concurrent=5,
        )
        for original, resp in zip(batch, responses):
            if "_error" not in resp:
                skill_map[original] = resp.get("zh", original)
            else:
                skill_map[original] = original

    zh_skills = []
    for item in skill_data:
        zh = dict(item)
        zh["job_name"] = name_map.get(item["job_name"], item["job_name"])
        zh["skills"] = []
        for sk in item.get("skills", []):
            sk_zh = dict(sk)
            sk_zh["name"] = skill_map.get(sk["name"], sk["name"])
            zh["skills"].append(sk_zh)
        zh_skills.append(zh)

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(zh_skills, f, ensure_ascii=False, indent=2)

    print(f"      技能中文版: {len(zh_skills)} 条 -> {output_path}")
    return zh_skills


async def translate_change_logs(
    input_path: str,
    output_path: str,
    model: str = "",
) -> list[dict]:
    """翻译 job_change_log.json 中的文本字段为中文。"""
    model = model or MODEL_STAGE1

    with open(input_path, "r", encoding="utf-8") as f:
        logs = json.load(f)

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
