# M1 → M2 数据库完整导出交接说明（2026-08-23）

> 面向：M2 岗位分析开发者
> 版本：`talentmind-db-full-20260823`
> 生成时间：2026-08-23 09:48:15 +08:00
> 重要：SQL 文件位于 `data/local/`，该目录被 Git 忽略，不会随 GitHub 提交。请通过项目约定的安全渠道单独传递 SQL 文件，并用下方 SHA-256 校验。

## 1. 交付物

| 文件 | 位置 | 大小 | SHA-256 |
|---|---|---:|---|
| 完整 MySQL 导出（schema + data） | `data/local/m2-data-pack/talentmind-db-full-20260823.sql` | 534,151,037 bytes（约 509.5 MiB） | `35FF215B1C3F7720701B5F553593357F8962AE436378D8EEBAD913BC29C4B4BD` |
| 数据库契约 | `backend/app/contracts/ddl.sql` | 以仓库当前版本为准 | — |
| 采集与导入状态 | `exchange/m1/collection-status-20260823.md` | 本次快照 | — |
| 采集模块说明 | `backend/app/collect/README.md` | 运行与字段说明 | — |

导出由 MySQL Docker 容器中的 `mysqldump 8.0.46` 生成，包含 8 张表的结构、数据、触发器/事件/例程声明（当前没有业务例程），使用 `--single-transaction` 获取一致性快照，导出本身不停止 BOSS 采集。

## 2. 导出时数据库内容

| 表 | 行数 | 用途 |
|---|---:|---|
| `jd_pool` | 126,330 | M1 清洗后的岗位池 |
| `job_change_log` | 0 | 岗位定义变更审计 |
| `job_definition` | 22 | 已有岗位定义 |
| `job_skill` | 22 | 岗位技能证据链 |
| `resume` | 0 | 简历解析结果 |
| `signal` | 680 | GitHub/博客趋势信号 |
| `skill_dict` | 285 | canonical 技能词典 |
| `talent_raw` | 0 | 人才原始线索 |

### `jd_pool` 来源与状态

- `linkedin`：123,849 条；`hn`：1,796 条；`boss`：685 条。
- 所有 126,330 条当前均为 `status='cleaned'`。
- `source` 只表示来源平台；不要把它当作岗位状态。细分数据集/页面标识在 `source_detail`。
- `cross_source=1` 表示岗位通过当前多源规则被标为 LinkedIn + HN 交叉命中；实时数据库为 888 行。报告文件可能是 887 行，因为保留了 1 条历史残留标记。

### BOSS 质量摘要

- 685 条全部 `cleaned`。
- `source_detail` 空值：0；`source_detail` 重复值：0。
- `duties` 非空：288 条。
- BOSS 使用用户人工登录的独立 Edge + CDP 读取页面可见内容；不接收或导出密码、验证码、Cookie，不实现安全措施绕过。

### `signal` 时间范围

- 共 680 条：GitHub 174 条，博客 506 条。
- 覆盖 2026-08-17 至 2026-08-22 共 6 个日期。
- `captured_at` 以数据库记录为准；M2 趋势分析应按时间点聚合，不要把不同日期压平为单一快照。

## 3. M2 恢复方式

### 推荐：恢复到新的数据库名

该 dump 对表使用 `DROP TABLE IF EXISTS`，不要未经确认直接导入当前生产库。推荐先恢复到隔离库：

```powershell
# 1) 将 SQL 复制到 MySQL 容器（路径按实际位置调整）
docker cp D:\Application\ClaudeCode\repository\TalentMind\data\local\m2-data-pack\talentmind-db-full-20260823.sql talentmind-mysql-1:/tmp/talentmind-db-full-20260823.sql

# 2) 创建隔离数据库；<MYSQL_ROOT_PASSWORD> 使用本机 backend/.env 中的值，不要写入 Git 或文档
docker exec talentmind-mysql-1 mysql -uroot -p<MYSQL_ROOT_PASSWORD> -e "CREATE DATABASE IF NOT EXISTS talentmind_m2_20260823 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"

# 3) 导入隔离库
docker exec talentmind-mysql-1 mysql -uroot -p<MYSQL_ROOT_PASSWORD> talentmind_m2_20260823 < /tmp/talentmind-db-full-20260823.sql
```

如果在 PowerShell 中执行第 3 步遇到重定向差异，使用容器内 shell：

```powershell
docker exec talentmind-mysql-1 sh -lc "mysql -uroot -p<MYSQL_ROOT_PASSWORD> talentmind_m2_20260823 < /tmp/talentmind-db-full-20260823.sql"
```

恢复后请执行：

```sql
SELECT source, status, COUNT(*) AS n
FROM jd_pool
GROUP BY source, status
ORDER BY source, status;

SELECT source, COUNT(*) AS n
FROM `signal`
GROUP BY source
ORDER BY source;
```

预期结果为：`linkedin/cleaned=123849`、`hn/cleaned=1796`、`boss/cleaned=685`；`signal` 为 `blog=506`、`github=174`。若恢复到项目默认库，需将数据库名切换为 `talentmind` 并先确认已有数据已备份。

## 4. M2 推荐读取方式

1. 岗位分析主输入优先读取 `jd_pool` 的 `job_title`、`raw_text`、`duties`、`experience`、`quality`、`source`、`source_detail`、`cross_source`、`crawled_at`。
2. 技能标准化使用 `skill_dict.canonical` 与 `skill_dict.aliases`；当前 canonical 词典 285 条。
3. 已有分析结果读取 `job_definition` 与 `job_skill`。`job_definition` 没有 `status` 字段；`source` 在该表中是 JSON 平台列表，不等价于 `jd_pool.source`。
4. `job_change_log`、`resume`、`talent_raw` 当前为空，M2 不应据此推断功能失败，它们分别是变更审计、简历结果和人才线索的预留/后续数据。
5. 数据契约的字段类型和语义以 `backend/app/contracts/ddl.sql` 为准；修改或删除字段前须通知全队。

## 5. 时间点与持续采集说明

这是 `2026-08-23 09:48:15 +08:00` 的一致性快照。导出后 BOSS 采集仍在后台低速运行，后续新增记录不会自动出现在该 SQL 文件中；如 M2 需要最新数据，应重新生成导出并更新文件名、时间和 SHA-256。

BOSS 最新运行状态见 `exchange/m1/collection-status-20260823.md`；重启后的首轮已完成 `new=2`，数据库 BOSS 总量为 685。持续采集使用人工登录 Edge + CDP，若页面进入登录/验证状态，程序会安全停止并记录到 `data/local/logs/`。

## 6. 安全与 Git 边界

- 不提交 `data/local/`、`backend/.env`、登录态、Cookie、真实简历或其他敏感数据。
- 本说明文档只记录路径、统计和校验值，不记录数据库密码。
- 发送给 M2 前，建议同时发送本文件、SQL 文件和 `backend/app/contracts/ddl.sql`；M2 收到后先校验 SHA-256，再导入隔离库。