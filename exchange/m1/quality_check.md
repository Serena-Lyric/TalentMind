# M1 质量分抽样核对记录（2026-08-15）

- 数据源：`docs/originalfile/archive/postings.csv`（LinkedIn 数据集，共 72 万行；本次导入 5000 行）
- jd_pool cleaned 总数：5003；quality 范围 0.18–1.0，均值 0.756
- dup_group 非空分组数：4565（去重按同组保留最高 quality）

## 抽样 10 条（quality 降序）

| id | job_title | quality | dup_group | source | 核对结论 |
|---|---|---|---|---|---|
| 106779 | VP of Digital Enablement and Technology | 1.0 | af408a560184d5df | dataset | 待核对 |
| 106862 | Store Manager | 1.0 | f3f976181d3bc0ee | dataset | 待核对 |
| 106645 | Store Manager | 1.0 | f3f976181d3bc0ee | dataset | 待核对 |
| 106714 | Store Manager | 1.0 | f3f976181d3bc0ee | dataset | 待核对 |
| 106671 | Legal Assistant (Legal Access Officer) | 1.0 | 7ea8a987e33f3be8 | dataset | 待核对 |
| 106709 | Business Controlling, Full Value Chain A | 1.0 | b6160c2d8fe61f29 | dataset | 待核对 |
| 106624 | Seal Product Design Engineer | 1.0 | c971692199002026 | dataset | 待核对 |
| 106721 | Store Manager | 1.0 | f3f976181d3bc0ee | dataset | 待核对 |
| 106634 | Manufacturing Engineering Manager | 1.0 | b507ef4dcc2c1f70 | dataset | 待核对 |
| 106879 | Sales Development Representative | 1.0 | 80cbe64f4bfa44d2 | dataset | 待核对 |

## 说明
- quality 来自 dedup 交叉验证机制（同 dup_group 取最高质量；质量分由 cleaner/dedup 计算）。
- 抽样核对结论由 A 人工补填：确认质量分合理性、去重分组正确性后，将『待核对』改为『通过/异常说明』。
- 已知限制：`experience VARCHAR(32)` 截断（D33 后续扩容）；本批数据为英文 JD，岗位标题未中文化（M2 处理）。