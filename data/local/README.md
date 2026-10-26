# 本地私有数据

本目录默认不提交 Git，仅本说明文件入库。真实 JD、数据库、浏览器档案和会话信息不得上传 GitHub。

## 数据用途

| 路径 | 用途与保留边界 |
|---|---|
| `chinese-jd-archive.zip` | 中文原始 JD 的唯一独立历史存档；原始 SQL/JSON/压缩快照等重复备份已删除，产品运行必需的冻结输入继续保留 |
| `m2-product/analysis.sqlite3`、`m2-product/workflow.sqlite3` | 当前 M2 原生分析及产品编排状态；保留全部记录，已做 NTFS 透明压缩，未改数据库结构或内容 |
| `m2-product/runs/*/input.json` | 产品读取、完整性检查及重放直接依赖的冻结输入；属于运行状态，不能随历史备份删除 |
| `m2-product/native-reports/`、`m2-product/graphs/` | 当前产品引用的原生阶段报告及候选图；原生报告已做 NTFS 透明压缩 |
| `quality-round2-v3/input.json`、`quality-holdout-input/input.json` | `product/source.py` 的 main120、holdout60 成员索引，继续保留 |
| `m2-data-pack/岗位数据/skill_dict_seed.json`、`m2-data-pack/信号数据/signal_snapshot.json` | 旧管道配置仍引用的可选词典和信号快照，继续保留 |
| `collection/`、`local-runtime/services.json`、`PAUSE_COLLECT` | 采集控制、配对状态、启动归属及每日采集暂停标记；保留，不能当作无用缓存删除 |
| `edge-boss-cdp-profile/` | 当前采集使用的独立 Edge 档案；Cookie、登录状态、用户配置、扩展及站点存储保留 |

## 中文存档读取与口径

`chinese-jd-archive.zip` 使用标准 ZIP/UTF-8 JSONL，大小 8,078,835 字节。SHA-256：`068935e3fbafbeb4218510cfdfab586c45075761f836e679ff6bff1ce25c4a8d`。

- `records.jsonl`：按来源及完整原字段内容的 SHA-256 去重；只将 `crawled_at`、`captured_at` 拆到观察记录，不按岗位名称合并，也不覆盖不同版本。
- `observations.jsonl`：内容引用、原采集字段、原文件内位置及必要上下文；将记录的 `payload` 与观察的 `capture_fields` 合并可恢复对应原始行。
- `sources.jsonl`：原文件路径、大小、SHA-256，以及适用的原 SQL 表结构；用于追溯，不重复存整份原备份。
- `manifest.json`：范围、格式和计数。共 3,573 种原字段表示、125,788 次出现，涉及 6,685 个来源文件；其中包含 150 条历史 BOSS 列表卡。其余表示也含不同版本、缺少部分字段的派生输入及测试上下文，**不能解释为 3,573 个独立真实岗位或完整 JD**。

存档覆盖所识别的 BOSS、智联、猎聘历史内容，包括 2,988 条基线、其他 SQL/JSON/压缩快照及本地分析输入中的版本差异；不是正式 MySQL 的实时导出。两组 SQL 与对应 JSON 的 2,988 行逐字段核对一致，日期的字符串/类型包装保留原表示。ZIP CRC、全部内容哈希及来源文件哈希已核验。

```python
import json, zipfile
with zipfile.ZipFile("data/local/chinese-jd-archive.zip") as archive:
    records = {r["sha256"]: r for r in map(json.loads, archive.open("records.jsonl"))}
    observation = json.loads(next(archive.open("observations.jsonl")))
    original_row = {**records[observation["record_sha256"]]["payload"], **observation["capture_fields"]}
```

## 本地存储状态（2026-10-26）

负责人已按确认清单完成删除：共 5,411 个原文件、约 1.75 GiB，覆盖重复中文备份、恢复取证副本、英文历史存档与旧数据包、废弃实验/验收产物、临时脚本、37 份与 SQLite 一致的最终报告文件、2,305 份可重建单条输入，以及页面/代码/图形/组件下载缓存。英文历史由负责人确认已在仓库外保全，仓库内不再保留；不再按批次或恢复过程建立整份原始 JD 备份。

M2 两个 SQLite 文件及 8,653 份原生报告已做 NTFS 透明压缩，压缩后内容哈希不变、SQLite `integrity_check` 均为 `ok`，45 份冻结输入、37 份数据库内产品报告及 7 份候选图通过当前代码只读访问。收尾仅统计占用并确认保留路径，未重复原始内容比对，未启动业务服务或连接正式数据库。正式 MySQL/Neo4j/Redis 数据卷及本目录外私有资产未操作。

清理及压缩后，`data/` 实际分配量由约 **3.80 GiB 降至 1.40 GiB**，净减少约 **2.40 GiB（63%）**。主要保留目录为 Edge 档案（约 751 MiB）和 M2 产品状态（实际约 670 MiB）；前者包含用户配置、扩展、站点存储及浏览器组件，后者保留当前产品依赖的数据与历史读取能力。
