# TalentMind 全站语义检查、前端交接与材料口径

核查日期：2026-10-20（Asia/Singapore）。交付分支为既有 Draft [PR #42](https://github.com/Serena-Lyric/TalentMind/pull/42)，起点 `abd416536e27aa2373262b30105d51622c9adb22`。本轮仅修订文档，不运行采集、业务管道、数据库或应用，不改前端代码。以下是源码与既有运行证据审计，**不是重新打开全站后的浏览器验收**。

## 1. 依据、优先级与工作区保护

- [#39 任务规范](https://github.com/Serena-Lyric/TalentMind/pull/39) `e20e6ff`、[#42 分阶段门禁](https://github.com/Serena-Lyric/TalentMind/pull/42) `abd4165`；本轮用户要求覆盖旧任务书“新建工作树/分支/PR”的安排。
- [#43 当日最新授权](https://github.com/Serena-Lyric/TalentMind/issues/43#issuecomment-6282375204)覆盖其正文、[#41 较早门禁说明](https://github.com/Serena-Lyric/TalentMind/issues/41#issuecomment-6282258005)和 #42 初版的“必须隔离库/仅落文件”。允许有界 M1 真实试采写现有 `jd_pool`，不扩展为写 M2/Neo4j、持续采集、删除或合并许可；集成测试仍用隔离实例。
- [#41 跨行业边界与初审](https://github.com/Serena-Lyric/TalentMind/issues/41#issuecomment-6282073419)：按实际软件开发活动判断，不按航天/工业等行业名排除；助手对真实样本的初审不是用户逐条签审。多职位公告当前整条待审，未来按角色可溯源分段；成熟复合职业与多职位公告分开。
- [#38 首轮报告](M1-M5-real-jd-e2e.md)及 [#40 第二轮报告（固定提交）](https://github.com/Serena-Lyric/TalentMind/blob/284bb62d4b94ed56d69f132877e22ea1e59a0939/docs/review/M1-M2-real-quality-round2.md)。#42 没有合入 #40 后端改动，引用外部分支结果不代表本分支能够直接重现第二轮。
- 切换前 `codex/real-jd-e2e@e2e07ec` 干净，所属聊天已结束，未发现引用该工作树的运行进程或 Git 锁；原分支及私有产物保留。fetch 后建立同名本地跟踪引用并切换到远端**既有** #42 分支，没有另起开发分支或工作树。
- Codex B 的“改进节点引导的银河空间”聊天正在 #37 的 `m3-m5-p25` 工作树编辑空间算法/图谱组件。为避免后续集成重叠，本轮图谱也只交清单；非图谱页面、路由、App、通用样式及 frontend README 均保持原状。没有向其他聊天发送消息；下表供负责人直接交接。

## 2. 全站问题表（当前原词 → 建议；尚未修改页面）

源码链接均定位于本轮起点，行号不会随文档修订漂移。**F01–F24 共 24 项交前端成员，G01–G05 共 5 项交 Codex B/集成者；29 项均为待应用建议，页面已修数为 0。** “文案”可按已确认规则处理；“接口/产品”表示不能只替换字符串，需负责人协调字段或确认展示方案，不代表要重新确认已有产品边界。

| ID / 页面位置 | 当前措辞或显示 | 建议新措辞 / 行为 | 实现证据与限制 | 责任 / 类型 |
|---|---|---|---|---|
| F01 `/jobs` 标题、导航 | “JD 岗位管理”“完整岗位目录” | “历史结构化岗位目录”，附“来自 job_definition，非原始 JD 列表、非新版 B3 已发布目录” | [Jobs:4](../../frontend/src/views/Jobs.vue#L4)、[mvp:52](../../backend/app/routers/mvp.py#L52)：列表查 job_definition；不是 jd_pool | 前端 / 文案 |
| F02 `/jobs` 技能列、详情及编辑 | “当前技能”“技能要求”，新增技能默认归必备 | “历史技能条目”，展示原 required/bonus 字段及旧语义；不得写为新版已审需求。编辑新增时明确原字段归属 | [Jobs:21](../../frontend/src/views/Jobs.vue#L21)、[Jobs:76](../../frontend/src/views/Jobs.vue#L76)、[mvp:84](../../backend/app/routers/mvp.py#L84)：列表合并两类，saveSkills 新增项写 required | 前端+后端 / 接口与产品 |
| F03 `/jobs` 详情时间 | “采集时间”可回退到 updated | “采集观察时间”只用 collected_at；updated 单列“最近修改时间”，缺值写“未提供” | [Jobs:29](../../frontend/src/views/Jobs.vue#L29)：collected_at 或 updated 混用，修改时间不能证明采集/发布 | 前端 / 文案及绑定 |
| F04 `/jobs` 加载错误、导出文件名 | “中文平台岗位数据加载失败”“中文平台岗位.csv” | “岗位目录加载失败”“历史结构化岗位目录.csv” | [Jobs:68](../../frontend/src/views/Jobs.vue#L68)、[Jobs:77](../../frontend/src/views/Jobs.vue#L77)、[mvp:394](../../backend/app/routers/mvp.py#L394)：未按中文平台限制导出 | 前端 / 文案 |
| F05 `/dashboard` 趋势图与切换 | “近6个月各岗位需求指数变化”“薪资水平” | “技术信号观察趋势（按采集日）”；未实现的需求/薪资切换隐藏或标“未接入” | [Dashboard:80](../../frontend/src/views/Dashboard.vue#L80)、[dashboard:52](../../backend/app/routers/dashboard.py#L52)：实际按 signal 聚合，range 未筛选半年；[Dashboard:191](../../frontend/src/views/Dashboard.vue#L191)图序列未按薪资切换 | 前端+API维护者 / 接口 |
| F06 `/dashboard` 技能柱图 | “Top 8 核心技能覆盖率”、百分数 | “历史技能出现频次（相对最高项归一化）”；若改真实覆盖率，先约定分母/资格 | [Dashboard:87](../../frontend/src/views/Dashboard.vue#L87)、[dashboard:86](../../backend/app/routers/dashboard.py#L86)：percentage=count/max_count，不是 JD 覆盖率或需求率 | 前端 / 文案；改指标需产品确认 |
| F07 `/dashboard` 岗位列表 | “在招岗位”“招聘中”“需求人数” | “本次加载的岗位定义”；招聘状态/人数“未提供”，不推断在招 | [Dashboard:97](../../frontend/src/views/Dashboard.vue#L97)、[Dashboard:258](../../frontend/src/views/Dashboard.vue#L258)、[mvp:94](../../backend/app/routers/mvp.py#L94)：open 硬编码、count=0，最多请求100行，非全部在招人数 | 前端 / 文案及绑定 |
| F08 `/dashboard` 与 `/analytics` 统计卡 | “匹配成功数”“技能缺口数”“新增岗位/待面试/紧急招聘”显示0 | “尚无持久化统计”，不把缺统计当真实0 | [Dashboard:155](../../frontend/src/views/Dashboard.vue#L155)、[Analytics:12](../../frontend/src/views/Analytics.vue#L12)、[dashboard:41](../../backend/app/routers/dashboard.py#L41)：这些值固定0 | 前端+API维护者 / 缺测状态接口 |
| F09 `/analytics` 技能图及统计卡 | “热门技能需求”“技能种类” | “历史技能条目频次（Top30）”“当前返回技能项数” | [Analytics:11](../../frontend/src/views/Analytics.vue#L11)、[Analytics:34](../../frontend/src/views/Analytics.vue#L34)、[dashboard:110](../../backend/app/routers/dashboard.py#L110)：最多30项历史记录计数，无五态需求率 | 前端 / 文案 |
| F10 `/dashboard`、`/analytics` 简历数 | “解析简历数”“解析简历”易被理解为上传次数 | “已持久化简历数”；旁注本次上传结果仅内存预览 | [dashboard:35](../../backend/app/routers/dashboard.py#L35)、[mvp:235](../../backend/app/routers/mvp.py#L235)：查 resume 表，上传不写该表 | 前端 / 文案 |
| F11 `/collection` 平台统计 | “数据库累计数据”下可显示 LinkedIn1164/HN1253 | 缺接口项显示“未提供”；如保留旧数，独立标明历史演示来源与日期，不能并入实时统计 | [Collection:115](../../frontend/src/views/Collection.vue#L115)：PLATFORM_FALLBACK_COUNTS。有真实0时不回退，缺项才回退 | 前端 / 文案及绑定 |
| F12 `/collection` 数据统计单位 | “全库岗位”“平台岗位”“本次新增” | “原始JD记录总数”“该平台原始记录”“本任务新增记录（INSERT）”；不当作独立职位数/正式岗位数，未知与0分开 | [Collection:129](../../frontend/src/views/Collection.vue#L129)、[control:351](../../backend/app/collect/control.py#L351)：查询jd_pool记录，未做独立职位确认；数据库侧database_new_count固定0，不能作为独立新增测量 | 前端+API维护者 / 文案及缺测状态 |
| F13 `/collection` 进度、历史详情 | “详情补采”“列表 / 详情” | “详情尝试次数”，成功/失败/UPDATE 分列；没有结果观测时写“未统计” | [Collection:128](../../frontend/src/views/Collection.vue#L128)、[fetch_boss_jobs:202](../../backend/app/collect/fetch_boss_jobs.py#L202)、[repository:40](../../backend/app/collect/repository.py#L40)：details 先加尝试，返回值只累计 INSERT，UPDATE 不计入 new | 前端+M1 / 接口 |
| F14 `/collection` 历史任务说明 | “仅记录通过本控制台启动的采集任务” | “控制台记录及可识别的历史日志”，区分实际来源/解析状态 | [Collection:69](../../frontend/src/views/Collection.vue#L69)、[control:512](../../backend/app/collect/control.py#L512)：会补入扫描的历史日志 | 前端 / 文案 |
| F15 `/collection` 质量与最近时间 | “当前采集平台来源质量”“最近采集”可随所选平台理解 | 明确“BOSS历史原始层质量/最近观察时间”；若随平台切换，先补按平台查询接口。任务空闲的“可启动”另改“当前无运行任务”，不代表会话已可用 | [Collection:46](../../frontend/src/views/Collection.vue#L46)、[control:353](../../backend/app/collect/control.py#L353)：质量/最新时间查询固定source=boss；[Collection:118](../../frontend/src/views/Collection.vue#L118)可启动只看任务状态 | 前端+M1 / 接口及文案 |
| F16 `/evolution` 记录及“版本” | “只展示可追溯数据”“N次变更”，易全当真实市场变化 | “历史变更记录”，明确真实来源、演示、来源未核验；记录条数不等于真实版本/市场演化次数 | [JobEvolution:6](../../frontend/src/views/JobEvolution.vue#L6)、[evolution:50](../../backend/app/routers/evolution.py#L50)：version 为遍历编号；[资产历史快照](../superpowers/资产与状态.md)明确含32条演示日志，不能只凭 source 判断真伪 | 前端+集成 / 来源标识接口 |
| F17 `/resume` 推荐得分 | “展示匹配度”显示90–100% | “演示展示分”；如切实际规则分，明确标 raw_score、算法与未评估准确率 | [ResumeDiagnosis:86](../../frontend/src/components/ResumeDiagnosis.vue#L86)、[mvp:326](../../backend/app/routers/mvp.py#L326)：低于90时随机展示分；规则得分也不是正确概率 | 前端+M4 / 产品展示选择 |
| F18 `/resume` 徽章及 `/learning` | 百分比徽章、“解析完成度” | “解析结果已生成”；启发式字段不能称完成度/准确率，另列具体识别字段 | [ResumeDiagnosis:33](../../frontend/src/components/ResumeDiagnosis.vue#L33)、[LearningRoadmap:12](../../frontend/src/components/LearningRoadmap.vue#L12)、[mvp:345](../../backend/app/routers/mvp.py#L345)：parseQuality 按技能数生成92–98，前端还有92回退 | 前端 / 文案及绑定 |
| F19 `/resume`、`/learning` 推荐说明 | “固定展示至少3个”“会自动给出至少3个” | “有可用目录时展示最多3项规则候选”；不承诺真实适配或至少三项 | [ResumeDiagnosis:85](../../frontend/src/components/ResumeDiagnosis.vue#L85)、[LearningRoadmap:8](../../frontend/src/components/LearningRoadmap.vue#L8)、[mvp:325](../../backend/app/routers/mvp.py#L325)：切片最多3，目录不足无法保证3 | 前端 / 文案 |
| F20 `/learning` 技能命中及衔接 | “已掌握”“已掌握技能” | “简历已识别/已命中的技能”，不作熟练度认证 | [LearningRoadmap:22](../../frontend/src/components/LearningRoadmap.vue#L22)、[LearningRoadmap:46](../../frontend/src/components/LearningRoadmap.vue#L46)、[learning:181](../../backend/app/routers/learning.py#L181)：canonical 集合命中 | 前端 / 文案 |
| F21 `/learning` 全命中提示 | “当前已达标”“可直接投递” | “当前目录条目均在简历中命中；任职资格与实际能力仍需核实” | [LearningRoadmap:29](../../frontend/src/components/LearningRoadmap.vue#L29)、[learning:237](../../backend/app/routers/learning.py#L237)：at_standard 仅无缺项，未核验其他任职条件 | 前端 / 文案 |
| F22 `/learning` 缺口及阶段 | “岗位技能缺口”“待学习”“必备缺口” | “当前简历未命中的历史目录条目”“建议核实/补充证据”；软技能未提及不推断缺乏；阶段称“规则建议顺序” | [LearningRoadmap:23](../../frontend/src/components/LearningRoadmap.vue#L23)、[learning:185](../../backend/app/routers/learning.py#L185)、[learning:205](../../backend/app/routers/learning.py#L205)：集合差集及启发式分层，非已验证依赖路径；按产品 M2-06 处理软技能 | 前端+M4 / 分类接口 |
| F23 `/resume-demo` 专业技能 | 技能“80分”及进度条 | “简历已识别技能”；移除无测评依据的能力分 | [ResumeDemo:77](../../frontend/src/views/ResumeDemo.vue#L77)、[ResumeDemo:163](../../frontend/src/views/ResumeDemo.vue#L163)：内存结果映射固定 level80 | 前端 / 文案及展示 |
| F24 共享外壳、`/login` 品牌副标题 | “岗位演化预测系统” | “岗位与技能信息分析（演示环境）”；预测能力列规划 | [App:10](../../frontend/src/App.vue#L10)、[Login:10](../../frontend/src/views/Login.vue#L10)、[auth:1](../../frontend/src/utils/auth.ts#L1)：登录仅前端演示校验；不得在材料称后端安全鉴权 | 前端 / 品牌措辞需负责人确认 |
| G01 `/graph` real模式搜索、图例、筛选、详情 | “输入岗位或技能”“岗位节点”“蓝色恒星为岗位” | real 模式“原始 JD 记录/技能词项”；历史模式“历史岗位定义”，搜索与空输入提示同步 | [GraphPanorama:20](../../frontend/src/components/GraphPanorama.vue#L20)、[GraphPanorama:39](../../frontend/src/components/GraphPanorama.vue#L39)、[GraphPanorama:204](../../frontend/src/components/GraphPanorama.vue#L204)、[GraphPanorama:268](../../frontend/src/components/GraphPanorama.vue#L268)、[real_pipeline:32](../../backend/app/graph/real_pipeline.py#L32)：job 身份为原 JD | Codex B/集成 / 文案 |
| G02 `/graph` 关系五态、历史边 | “五态 uncertain”等原码；历史 REQUIRES 显示“岗位技能关联” | 保留原码并配中文五态；历史边加“旧字段投影，非新版已确认要求”，组合/冲突不压成必备 | [GraphPanorama:109](../../frontend/src/components/GraphPanorama.vue#L109)、[GraphPanorama:267](../../frontend/src/components/GraphPanorama.vue#L267)；HAS_SKILL_STATEMENT 已明确未人工审核，应保留 | Codex B/集成 / 文案 |
| G03 `/graph` 来源及账本 | 筛选原码和完整 JSON，未突出 B2 partial | 默认分开显示“有效性/范围/B2执行状态”；partial“部分分析”，completed“程序分析完成（不代表人工签审）” | [SourceEvidence:9](../../frontend/src/components/SourceEvidence.vue#L9)、[SourceEvidence:12](../../frontend/src/components/SourceEvidence.vue#L12)：治理详情折叠；两轮B2 completed均0 | Codex B+M2 / 显示字段核对 |
| G04 `/graph` 领域与旧类型 | “八大领域沿用B3职业大类”，config TYPES含“行业/技术方向” | “八类为产品分类设计；本图未按正式职业目录归类”，旧 Industry 只称“历史场景投影”；美术 TYPES 不作事实类型 | [GraphPanorama:67](../../frontend/src/components/GraphPanorama.vue#L67)、[config:19](../../frontend/src/graph/galaxy/config.js#L19)：美术分组与实际实体分开，禁止因词项存在新增图类别 | Codex B/集成 / 文案 |
| G05 `/graph` real统计及数据集选择 | “真实JD隔离预览”可加载任一包，摘要只显示版本前缀 | 同时说明“#38首轮 / #40第二轮候选”、固定输入/进入量/陈述数/审核状态；只按已核验 manifest绑定，不能按节点数猜版本 | [GraphPanorama:10](../../frontend/src/components/GraphPanorama.vue#L10)、[realSnapshot](../../frontend/src/graph/realSnapshot.ts)：真实包显式选择，不应默认为第二轮替代首轮 | Codex B+集成 / manifest展示接口 |

已正确区分、应保留的内容：[SourceEvidence:7](../../frontend/src/components/SourceEvidence.vue#L7)明确采集观察时间不是发布时间；图谱已标“非实时数据库/非新版标准目录”、陈述未审核、历史场景投影和布局非职业分类；`/analytics` 的 signal 来源说明及登录页“演示环境”提示。`/graph-collection` 只是重定向，不另计业务页面；旧 Canvas/LegacyGraph 回退尚需集成者按相同术语复查，本轮未作回退浏览器验收。

## 3. 五态、执行状态与正式准入的交接约定

| 原字段/状态 | 普通用户措辞 | 不得推断 |
|---|---|---|
| required | 原文明确要求（规则识别；列审核状态） | 人工已确认、所有同类岗位必备 |
| preferred | 原文加分优先（规则识别；列条件） | 必备、普遍要求 |
| mentioned | 仅提及 | 存在招聘需求 |
| not_required | 原文明示不要求（限原文作用域） | 未出现某技能就不需要 |
| uncertain | 待判断（有陈述但要求语义未定） | 无效JD、范围外、执行失败 |
| partial | 部分分析，仍有未覆盖内容 | 整条分析完成、正式统计合格 |
| completed | 程序分析完成 | 人工签审通过、语义准确率达标 |
| failed / input_failed | 执行失败 / 输入失败（按实际字段） | uncertain 或无效JD |
| B3 产品审核19/19 | 产品层逐项审核完成 | 已版本归档/正式发布；当前正式目录仍0 |

先交 F01–F06、F11–F13、F17–F23 与 G01–G03，优先消除把原始记录、演示分、未确认陈述当正式事实的风险。前端成员自行应用非图谱项；Codex B 处理图谱项或留集成阶段。API 缺少的统计缺测、详情成功/UPDATE、来源演示标记及软技能分类，由相应后端负责人补充版本化字段，**本轮没有改 API 或替用户选展示方案**。材料可先采用下一节的已核实口径。

## 4. 当前功能与证据矩阵（可用于竞赛材料）

| 版本/能力 | 已实现、已有验证 | 质量/发布边界 |
|---|---|---|
| #38 `e2e07ec`，数据版 `ba1717fc…` | 固定120条已有真实JD→22条入规则分析→71节点（22原JD+49技能）/417陈述；来源回溯、重放、失败关闭已有浏览器/离线证据 | 416 uncertain、1 mentioned；22条B2全部partial；required/preferred/not_required均0，正式确认需求0；非新采数据 |
| #40 `284bb62`（实现 `2c51aa5`），数据版 `31c3947f…` | 同字节120条→14条入分析→52节点/263陈述；正式Vue已加载、回源及回退；独立60条留出另得1条入分析/6节点/20陈述 | 262 uncertain、1 mentioned；14条B2全部partial；确认需求0。9条降级/1条升级含真实召回损失，未完成签审，precision/recall=null；32项仅本地待审草稿 |
| M1 当日 preflight，代码 `284bb62` | 私有REPORT/verification记录目标 localhost:23306/talentmind、2,988行可恢复备份、八表内容摘要前后一致 | CDP不可用，采集器未执行；listed/详情尝试/成功/INSERT/UPDATE/跳过均0，原因是未启动；没有新数据或正文质量验收，不能声称试采成功 |
| P2.5 #37 `fb68d3b` | 程序化主体、密度治理、端点渐变、相机/交互及回退已有[技术与浏览器报告](M3-M5-P2-5.md) | 技术实现与最终视觉验收分开；Codex B 正在做新空间候选，本轮不预测其交付或美术结论 |
| 历史图 | 文件7845节点/11412边，历史回退已有截图；本轮只核对文件摘要 | 非实时库、新版需求图或已治理行业；保留原字节 |
| B3/M4及后续能力 | B3治理工具、规则匹配与学习建议已有源码基础；19项产品审核完成 | 正式B3发布0；M4展示分/解析质量含演示逻辑，真实提取/匹配准确率未验收；多职位分段、可靠需求趋势与正式生产迁移均未完成 |

两轮选样为同一2026-10-14备份中各平台ID升序前40条，不随机；不能相加成240条独立样本，417/263是陈述边数，不是独立职位数或独立技能需求数。#40 B22八个候选未准入。两轮相似边、非平凡社区均0；这是允许的空派生结果，不能宣称已发现真实职业聚类。两轮报告的后端回归各有2项B3文档来源摘要/引文失配，不能声称全仓全绿；本轮修改产品文档不重签候选来源、不改审核事件来消除失败。

M1证据来源为本机另一工作树的 `data/local/m1-live-boss-20261020/REPORT.md` 与 `verification.json`，本轮只读摘录聚合结论，未复制快照、原文或凭据，也未重新查询数据库。原始行身份、完整哈希映射及备份继续私有；报告的PAUSE标记/任务状态有工作树与时点差异，不能把Issue早期现场值当当前机器状态。后续有新实采报告时逐版增补，不用计划命令预填成功数。

**可直接用于PPT/讲稿的口径：**

> TalentMind 已建立基于已有真实招聘原文的隔离分析与可追溯图谱候选链路。相同120条固定样本，首轮22条进入规则分析，形成71节点与417条未人工确认的技能陈述；第二轮14条进入，形成52节点与263条陈述，并暴露了真实召回损失。两轮均无正式确认的技能需求，语义质量和人工签审仍待完成。P2.5银河已有技术实现与浏览器证据，最终视觉待验收；本次M1试采因CDP前置阻塞尚未启动。后续按M1→M2新旧数据分别验证→M3小批→全量历史稳定性逐关验收。

## 5. 本轮实际修改与未改原因

| 文件 | 本轮变更 |
|---|---|
| `docs/PRODUCT_DECISIONS.md` §12 | 记录#43授权覆盖原因、有限M1入现库、原像/更新回退、下游边界 |
| `docs/superpowers/plans/2026-10-20-staged-m1-m3-real-validation.md` | 修正Gate0/1、首轮上限、T0、执行状态拼写和已发生的CDP阻塞；保留逐关顺序 |
| `docs/superpowers/plans/2026-10-20-post-e2e-execution.md` | 初版总计划前追加当日授权/工作区安排的替代说明，保留历史任务原文 |
| `docs/team/TALENTMIND_TERMINOLOGY_AND_CAPABILITY_2026-10-20.md` | 增补#40、最新M1报告和语义交接入口 |
| `docs/演示能力与证据索引-2026-10-21.md` | 补双版本/零确认需求/M1未启动；旧阶段表标历史并保留 |
| 根`README.md`、`docs/README.md` | 当前能力/导航与新版授权口径一致 |
| `backend/app/collect/README.md` | 历史采集命令前补最新有界授权入口，防误用旧范围 |
| `docs/superpowers/决策跟踪.md`、`资产与状态.md` | 追加当日替代关系、文档资产及真实运行状态来源 |
| 本报告 | 29项源码语义建议、成员交接、证据与最终材料口径 |

没有改前端源码/共享样式、B1/B2、正式B3目录/来源签名、DDL、M2正式数据、Neo4j、历史graph.json。#38/#40及P2.1–P2.5历史报告按原时点保留；模块README中的历史错词（例如frontend称实时Neo4j、M3旧API说明、M2旧“全部未审”）应以当日术语索引为当前说明，后续由模块负责人修订，未覆盖Codex B/成员文件。本轮是事实与材料同步，不新增业务功能；不为纯Markdown启动业务测试或浏览器，不以引用旧证据声称本轮重新实测。

交付前检查：11个Markdown文件、93个新增本地链接与72处源码行号范围通过；新增表格列数一致，29项交接ID唯一；`git diff --check`通过，历史graph.json字节摘要与原基线一致，正式目录条目数仍0。检查脚本只读文件，未运行业务测试。页面建议仍需成员应用后做真实页面和双图谱/回退验收；本轮不将清单交付标成UI修复完成。
