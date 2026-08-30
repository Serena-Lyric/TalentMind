# 岗位示例（赛题提交材料）

## 示例 1：新岗位发现与定义

### 输入（原始 JD 片段）

```
Data Architect - linkedin
Design and develop the enterprise data platform architecture,
covering streaming and batch data integration. Requirements:
AWS, ETL, data warehousing, SQL, Python, Databricks, Snowflake...
```

### 输出（管道生成的新岗位定义）

```json
{
  "job_name": "Data Architect",
  "core_duties": "Design and develop the enterprise data platform architecture, covering streaming and batch data integration.",
  "required_skills": ["aws", "etl", "data warehousing", "sql", "python", "databricks", "snowflake", "big data technologies"],
  "bonus_skills": ["..."],
  "scenarios": ["Streaming and batch data integration", "Business intelligence analytics", "AWS-based ETL and data warehouse implementations"],
  "is_emerging": true,
  "evolution": {"stage": "growth", "stage_confidence": 0.8}
}
```

**特征**：is_emerging=true（新岗位标记）+ 完整技能 + 应用场景。

---

## 示例 2：既有岗位能力动态更新

### 岗位：Senior PHP Developer（成熟岗位）

聚合了 **3 条 JD** 的能力要求：

```json
{
  "job_name": "Senior PHP Developer",
  "required_skills": ["php", "laravel", "object-oriented programming", "mysql", "mvc design patterns", "html/css/javascript", "restful apis"],
  "source_jd_count": 3,
  "evolution": {"stage": "mature", "stage_confidence": 0.6}
}
```

**动态更新机制**（differ 变更日志）：
- 新数据到达 → 指纹对比 → 只处理变化的 JD
- 新技能出现 → 变更日志标注 `added` + 原文证据
- 旧技能消失 → 标注 `removed`
- 技能权重变化 → 标注 `modified`（旧置信度 → 新置信度）
- 全部标注**数据源**（evidence 原文引用）

---

## 数据源示例

每个技能都带原文证据：

```json
{
  "name": "aws",
  "confidence": 0.9,
  "evidence": "JD #112345: Knowledge of AWS services is required",
  "verification": "verified"
}
```

`verification` 由双模型交叉验证：qwen3.7-plus ∥ mimo-v2.5-pro 独立核查，双证通过才标 verified。
