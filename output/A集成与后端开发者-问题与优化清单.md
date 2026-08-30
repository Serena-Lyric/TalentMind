> **2026-08-30 整合状态**：M2 新回包已导入 MySQL（job_definition/job_skill 各 470）；M3 图谱已重建并导入 Neo4j（588 节点/3998 关系）；Dashboard/Graph/Jobs API 已重新实测。趋势、雷达、目标岗位匹配和 DTO 统一等问题仍需 A/后端处理。

# A 集成与后端开发者问题与优化清单

- 审计日期：2026-08-30
- 对象：`backend/app/routers/`、`backend/app/integration/`、MySQL/Neo4j 数据闭环、前后端 DTO

## P0 必须处理

### A-P0-01 冻结真实 API DTO，清理演示数据来源

当前 `/api/dashboard/overview` 实测返回 22 个岗位、0 份简历、0 次匹配、0 个技能缺口；前端却显示另一套演示数字。A 需要明确每个字段的真实性：

- 真实统计：直接来自数据库；
- 暂无数据：返回 `null`/空数组并要求前端显示空态；
- 演示数据：只能放在单独 demo 环境，不能混入正式 API。

验收：API 文档样例、前端显示和数据库查询结果一致。

### A-P0-02 补全 Dashboard 数据接口或明确降级

当前：

- `/api/dashboard/trend` 返回空 `months/series`；
- `/api/dashboard/skill-radar` 返回全 50 的占位值；
- `/api/dashboard/industry-tracks` 是静态常量；
- `/api/dashboard/skill-distribution` 有真实技能频次，但前端没有接入。

要求：

1. 趋势按 `signal.captured_at` 或岗位历史快照实现真实时间序列；
2. radar 没有数据时返回空结构并附可解释状态，不返回全 50；
3. 技能分布 DTO 与前端确认是数组还是 `{items,total}`；
4. 行业赛道如果只是静态映射，文档中标为展示映射，不称为数据分析结果。

### A-P0-03 Jobs 写接口与前端行为闭环

后端已经有新增、编辑、删除、批量删除、导入、导出路由，但前端没有真正调用。请提供统一的成功/失败语义：

- 新增/编辑后返回完整岗位或明确的 `id`；
- 删除应考虑 `job_skill`、`job_change_log` 的关联处理；
- 导入返回成功数、失败数、错误行；
- 导出声明真实格式（CSV 或 XLSX），不要 API 名称写 Excel、实际返回不一致格式；
- 写操作应有幂等或重复提交保护。

### A-P0-04 Resume 匹配接口必须接收目标岗位

当前 `POST /api/resume/upload` 会遍历岗位并选择最高分岗位，前端的目标岗位选择没有进入后端。需要将协议改为：

```text
file/content + target_job_id -> profile + match_result(target_job_id, score, matched, missing, path)
```

如果暂时无法改上传接口，至少新增一个按岗位匹配的接口，并让前端明确使用它。

### A-P0-05 修复 Resume/Graph 的空能力接口语义

当前：

- `/api/resume/skill-dimensions` 返回空数组；
- `/api/graph/skill-radar` 返回空数组；
- Dashboard radar 返回全 50。

要求所有空实现统一：

- 返回 `data: null` 或空数组；
- 附带 `message`/状态说明；
- 不允许前端把空数组当作 0 分或正常图表；
- API 文档必须删除虚构示例。

## P1 重要优化

### A-P1-01 `/api/graph/data` 实现查询参数

前端和文档已有 `year`、`focusJob` 概念，但后端当前只读取 Neo4j 全量节点和边，没有使用过滤参数。请明确：

- `focus_job` 是按 ID、英文 key 还是数据库岗位 ID；
- `year` 对当前无历史图谱时是否只接受 2026；
- 聚焦时是否返回一跳技能、相关岗位和统计；
- 参数无效时返回 400 还是空结果。

### A-P1-02 统一 Job 中文名来源

当前 API 使用 `exchange/m2/job_definition_zh.json` 与英文文件按顺序 zip 的过渡映射；M3 import 已支持 `name_zh`，但 `/api/graph/data` 仍使用 A 自己的映射。M2 新回包后应：

1. `job_definition` 主数据包含 `job_name_zh`；
2. graph.json Job 节点包含 `name_zh`；
3. Neo4j 保存 `name_zh`；
4. API 优先返回 Neo4j/DB 的 `name_zh`，只在缺失时回退英文；
5. 删除按数组顺序 zip 的过渡逻辑。

### A-P1-03 统一错误响应和 HTTP 语义

当前项目约定业务响应 `{code,message,data}`，但所有业务错误仍可能以 HTTP 200 返回，且前端请求封装按 `code` 解包。请明确：

- 参数错误、资源不存在是否使用 HTTP 4xx；
- `code` 枚举和前端错误展示；
- Blob 下载是否绕过统一解包；
- 上传解析错误是否能给出用户可理解的错误类型。

### A-P1-04 增加只读集成验收脚本

建议提供一个不写库的 API smoke 脚本，检查：

- 所有 20 个接口可访问；
- code=0；
- 核心字段类型正确；
- Graph 节点/边引用闭合；
- Job 列表中的 `id` 可以访问详情；
- 空数据接口不会返回假数字。

### A-P1-05 维护真实数据快照版本

当前数据库岗位 ID 会因重导变化，前端和测试如果写死 ID 容易失效。建议 API 返回 `contract_version`/`snapshot_version`，测试先取列表中的真实 ID，再访问详情。

## P2 可选优化

- 采用 OpenAPI 生成前端 TypeScript 类型，减少字段漂移；
- 为 `/api/jobs` 增加后端分页、排序、城市/赛道/技能筛选；
- 将 Dashboard 的 `matchSuccess/skillGaps` 明确为统计表或事件表计算，不要长期固定为 0；
- 为 resume 上传增加大小、扩展名、MIME 和内容解析失败保护；
- 为 Graph 导出提供 JSON/PNG 两种明确格式；
- 对 Neo4j 导入增加“旧图清理/新图导入/节点边计数/孤儿边检查”一体化命令。

## A 回执验收标准

- [ ] API 文档与实测 JSON 一致；
- [ ] Dashboard 不再需要前端硬编码数字；
- [ ] Jobs 所有写接口至少有一条真实集成测试；
- [ ] Resume 目标岗位能进入匹配逻辑；
- [ ] Graph focus/year 参数有明确行为；
- [ ] 空 radar/trend 不返回假数据；
- [ ] M2 新回包后可一键重建中文图谱；
- [ ] 每个写库测试必须在 finally/fixture teardown 中按 job_title、identity_hint 或唯一标记精确删除自己的夹具行；禁止按 source 等宽泛条件删除；测试结束必须查询夹具计数为 0，并核对生产表总量未异常下降。

## 2026-08-30 验收证据

- MySQL：`job_definition=470`、`job_skill=470`、`job_change_log=0`、`skill_dict=285`；
- Neo4j：`588` 节点、`3998` 条关系；
- `/api/jobs` 返回 `total=470`；`/api/graph/data` 返回 `588/3998`；`/api/dashboard/overview` 返回 `totalJobs=470`；
- M1 `jd_pool` 未被 M2 导入流程清空，当前全量测试结束后夹具行数为 0。
