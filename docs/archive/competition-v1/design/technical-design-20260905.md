> 竞赛 V1 历史正文导出。Word 作者/自定义属性/缩略图未公开，原件保留于私有备份。表格已转为段落，版式不复刻；文中的设计承诺与旧测试指标不是本轮重新验证的结果。

TalentMind 技术设计文档

目录

[系统架构](一系统架构)

[数据采集模块（M1）]

[新岗位发现模块（M2）]

[能力 "幻觉" 防控机制]

[全景图谱模块（M3）]

[人岗匹配模块（M4）]

[前端模块（M5）]

[附录 A-数据库设计]

[附录 B-API 接口清单]

一、系统架构

1.1 整体架构

分层层级

内容说明

用户界面层

技术：Vue3 + TypeScript + Element Plus + ECharts页面：Dashboard、Jobs、Graph、Collection、Evolution、Resume、Learning、ResumeDemo

应用服务层

后端框架：FastAPI 后端（统一 API）业务模块：M1 采集、M2 岗位分析、M3 图谱构建、M4 简历匹配

存储层

MySQL（结构化）、Neo4j（图谱）、Redis（缓存）

数据源层

BOSS 直聘 (1133 条)、智联招聘 (1088 条)、猎聘 (763 条)合计：2984 条有效数据

调用关系：用户界面层 → 应用服务层 → 存储层 → 数据源层

1.2 模块划分

系统采用模块化设计，共 5 个核心模块：

M1 数据采集：从三大招聘平台采集原始 JD 数据，支持 BOSS 直聘 CDP 采集、智联 / 猎聘 DOM 采集

M2 岗位分析：7 步管道处理，岗位定义 717 个（新一代 342 / 现有 375）

M3 图谱构建：构建岗位‑技能知识图谱，7845 节点 / 11412 关系

M4 简历匹配：简历解析、技能提取、匹配度计算

M5 前端展示：8 个业务页面，对接真实后端 API

二、数据采集模块（M1）

2.1 采集方式

数据源

采集技术

数据量

合规策略

BOSS 直聘

CDP 协议 + DOM 采集

1,133 条

9333 端口、低速循环、人工登录态、遇验证码即停止

智联招聘

页面可见 DOM 采集

1,088 条

遵守 robots.txt、人工登录态、遇验证码即停止

猎聘

页面可见 DOM 采集

763 条

人工登录态、遇验证码即停止

合计

-

2,984 条

三大国内主流平台

2.2 数据清洗流程

原始数据采集后，经过 7 步清洗流程后入库：

HTML 剥离：去除 HTML 标签，保留纯文本内容。

字段归一：统一不同招聘平台的字段命名，映射为系统标准字段。

经验截断修复：修复平台字段截断问题，补全文本内容。

去重：基于文本相似度算法，对重复 JD 进行去重。

交叉验证：双向包含 + 长度比算法，跨平台校验岗位真实性，标记可信数据。

质量评分：综合来源、完整性计算 0‑1 范围的数据质量分数。

入库：清洗完成数据存入 MySQL jd_pool原始岗位数据表。

2.3 采集状态

采集任务状态：已暂停（通过 PAUSE_COLLECT 开关控制）

暂停原因：避免每日计划任务误写入 HN 原始 JD 数据

数据清理：已清理 228 条误写入的 HN 原始 JD 数据

当前数据：中文三平台数据（BOSS 1133 + 智联 1088 + 猎聘 763 = 2984）

三、新岗位发现模块（M2）

3.1 处理管道（7 步）

Step1 SQL 解析：读取jd_pool原始 JD，转为结构化数据。

Step2 规则预筛：过滤非技术、信息残缺的无效 JD。

Step3 LLM 模型分析：调用 3 个独立大模型，提取岗位五要素：岗位名称、核心职责、必备技能、加分技能、应用场景；多模型降低 AI 幻觉风险。

Step4 合并：多数投票 + 置信度加权，合并多模型输出结果。

Step5 diff 对比：和历史岗位定义比对，识别新增、修改、删除变更。

Step6 导出：输出 JSON 岗位定义文件，保存至exchange/m2目录。

Step7 中英翻译：完成岗位定义中文翻译，用于前端展示。

3.2 产出数据

岗位定义：717 条（新一代 342 条 + 现有岗位 375 条）

岗位技能明细：717 条

能力变更日志：275 条

四、能力 "幻觉" 防控机制

4.1 AI 幻觉说明

大语言模型存在幻觉现象，会生成看起来专业、实际不存在的技能名词；如果直接采信，会造成岗位定义、知识图谱失真，误导求职者。项目设计三道防线层层过滤，保障输出数据可信。

第一道防线：技能词典约束

维护 285 个条目标准技能词典skill_dict。

大模型仅允许从词典中选取技能，禁止自由编造。

未收录的新技能进入人工候选队列，不直接入库。

技能词典与行业知识库保持同步，确保技能命名规范性。

第二道防线：证据链溯源

每一条识别得到的技能必须附带三项信息：

evidence：JD 原文证据片段；

confidence：0-1 置信度分值；

is_required：标记必备 / 加分技能。

json{  "skill_name": "Python",  "evidence": "熟练掌握Python编程语言，有3年以上开发经验",  "confidence": 0.95,  "is_required": true}

通过多源文档交叉验证，增强证据链的可靠性。

第三道防线：双模型交叉验证

使用 qwen3.7‑plus、mimo‑v2.5‑pro 两个模型独立解析同一份 JD：

双模型同时识别出 → verified已验证，保留原始置信度；

仅单个模型识别出 → suspicious可疑，降低置信度；

两个模型均未识别 → 直接删除。

结合外部知识检索结果，对模型输出进行二次验证，提高识别准确性。

4.2 RAG 框架扩展能力

系统架构支持检索增强生成（RAG）框架，具备以下扩展特性：

外部知识库接入：可接入行业技能标准库、岗位能力模型等外部知识源

文档检索增强：支持从海量 JD 文档中检索相关技能描述，增强技能识别准确性

上下文感知：基于岗位上下文和行业背景，动态调整技能识别策略

五、全景图谱模块（M3）

5.1 图谱模型

节点

节点类型

标签

数量

ID 格式

关键属性

岗位

Job

717

job:<m2_job_id>

job_name、name_zh、category、is_emerging、evolution

技能

Skill

4671

skill:<canonical>

canonical、category

行业

Industry

2457

industry:<slug>

name、slug

关系

关系类型

方向

属性

REQUIRES

Job → Skill

weight、is_required、evidence、confidence

RELATED_TO

Job → Job

similarity、common_skills

5.2 图谱构建流程

读取 M2 输出的job_definition、job_skill数据；

2.builder.py脚本提取节点、关系；

3.导出graph.json中间文件；

4.import_graph.py脚本执行 Cypher，批量导入 Neo4j 图数据库。

5.3 可视化展示

实现 Career Nebula 星云视图，同时支持力导向、桑基等多种布局，支持搜索、筛选、缩放、节点高亮交互。

5.4 图谱数据统计

Neo4j 总节点：7845 个

Job 节点：717 个

Skill 节点：4671 个

Industry 节点：2457 个

Neo4j 总关系：11412 个

REQUIRES 关系：8866 个

APPLIES_TO 关系：2539 个

RELATED_TO 关系：7 个

六、人岗匹配模块（M4）

6.1 简历解析

支持 PDF、DOC、DOCX、TXT 简历文件。处理流程：识别文件格式 → 调用对应库提取文本 → 结构化解析教育、工作经历 → NER + 词典归一提取标准化技能列表。

6.2 加权匹配算法

编程语言权重：1.5x

后端框架权重：1.3x

数据库权重：1.2x

其余类别权重（与代码 SKILL_WEIGHTS 一致）：前端技术 1.0x、DevOps/运维 1.0x、大数据/云 1.1x、AI/机器学习 1.2x、软件工程 0.8x、专业领域 0.8x、其他 0.5x

匹配度计算公式：匹配度 =（已匹配技能权重总和 ÷ 岗位全部技能权重总和）× 100

6.3 岗位自动推荐

根据简历技能与岗位技能匹配分数，自动输出不少于 3 个推荐岗位。

6.4 学习路径生成

6.4.1 分层路径设计

缺口技能按 "学习性质" 归入 4 个有序阶段：

编程语言、数据库，及 linux/shell/bash/git/powershell/sql/vim 等通用工具

核心框架与平台（core）：后端框架、前端技术、大数据 / 云、DevOps / 运维、软件工程

岗位专项（advanced）：AI / 机器学习、专业领域，以及未被归类 / 岗位特有写法

加分拓展（bonus）：加分技能缺口（放在最后，达标后再补）

6.4.2 针对性改进建议

每条缺口技能给出 "针对性改进建议"，字段全部来自真实数据：

category：技能类别（来自 skill_dict seed）

aliases/display_name：技能别名 / 显示名称

evidence：JD 原文证据片段（岗位为何要求该技能）

bridge_skills：简历已命中且与缺口同类别技能（个性化衔接点）

suggestion：以上字段确定性拼装的整句建议

6.4.3 设计约束

不引入 LLM 生成文案

不虚构课程、时长、链接

无缺口时返回 at_standard 达标态

七、前端模块（M5）

7.1 技术栈

Vue3.5 + TypeScript5.3.3 + Vite4.5；Element Plus；ECharts+G6 可视化；Pinia 状态管理；Axios 网络请求。

7.2 8 个业务页面清单

页面

路由

功能说明

Dashboard

/

系统数据概览

Jobs

/jobs

岗位管理，增删改查、导入

Graph

/graph

岗位星云图谱可视化

Collection

/collection

采集任务管理

Evolution

/evolution

岗位能力演化查看

Resume

/resume

简历上传、解析、匹配

Learning

/learning

技能学习路径展示

ResumeDemo

/resume‑demo

简历解析结果预览

7.3 前端开发约束

全部接口统一使用/api前缀，统一返回格式{code:0,message,data}；

禁止读取本地 Mock 数据，全部请求后端真实接口；

无可信数据源的数据不展示虚假演示指标。

7.4 学习路径页面升级

分层路径展示：按 "基础→核心→专项→加分" 四阶段展示

针对性建议面板：每条缺口技能展示 JD 证据、同类别衔接、建议文案

有序步骤列表：每个阶段卡片内改为有序步骤列表

达标状态展示：无缺口时显示达标卡

附录 A：数据库设计

A.1 MySQL 数据表总览

表名

说明

关键字段

数据量

jd_pool

原始岗位数据

source, job_title, raw_text, quality, cross_source

2,984 条

job_definition

岗位定义主表

job_name, job_name_zh, m2_job_id, core_duties, required_skills, bonus_skills, scenarios, is_emerging, evolution, category

717 个

job_skill

岗位技能明细

m2_job_id, skills (JSON 含证据链)

717 条

job_change_log

能力变更日志

change_type, object_type, skill_name, detail, source, reason, m2_job_id

275 条

skill_dict

技能词典

canonical (唯一), aliases (JSON), category

285 个

signal

技术信号

skill_or_job, signal_type, metric, value, source

1540 条

talent_raw

人才原始数据

source, raw_text, skills_hint, quality

‑

resume

简历解析结果

raw_format, skills(JSON), experience(JSON)

‑

job_change_log 7 种变更类型

变更类型

代码

说明

新增能力项

added

新增技能要求

删除能力项

removed

移除技能要求

修改能力项

modified

修改技能属性

职责变化

duties_changed

核心职责变化

场景新增

scenarios_added

新增应用场景

场景删除

scenarios_removed

移除应用场景

演化阶段变化

evolution_changed

岗位演化阶段升级 / 降级

A.2 Neo4j 图模型

核心数据汇总

指标

数值

jd_pool

2,984 条

job_definition

717 个

job_change_log

275 条

skill_dict

285 个

Neo4j Job 节点

717

Neo4j Skill 节点

4671

Neo4j Industry 节点

2457

Neo4j 总节点

7845

Neo4j 总关系

11412

后端单元测试

246 个，100% 通过

附录 B‑API 接口清单

模块

请求方式

接口路径

功能说明

岗位

GET

/api/jobs

获取岗位列表

岗位

GET

/api/jobs/{id}

获取岗位详情

岗位

POST

/api/jobs

新增岗位

岗位

PUT

/api/jobs/{id}

编辑岗位

岗位

DELETE

/api/jobs/{id}

删除岗位

岗位

POST

/api/jobs/import

批量导入岗位

图谱

GET

/api/graph/data

获取图谱节点关系数据

匹配

POST

/api/resume/upload

上传简历文件

匹配

GET

/api/resume/target-jobs

获取推荐岗位列表与真实匹配分

演化

GET

/api/evolution/timeline/{job_id}

获取岗位能力演化日志

采集

‑

/api/collection/*

采集任务相关接口（status/progress/stats/database-stats/history/config/start/stop 等）

学习

GET/POST

/api/learning/jobs、/api/learning/job-skills/{job_id}、/api/learning/generate-path

学习路径相关接口（分层路径 + 针对性建议）

系统

GET

/health

健康检查（统一响应结构 {code, message, data}）

看板

GET

/api/dashboard/overview

数据概览统计（岗位/技能/趋势）

学习路径接口详情

接口

功能说明

POST /api/learning/generate-path

生成简历×目标岗位的分层学习路径（基础→核心→专项→加分）与针对性建议

GET /api/learning/job-skills/{job_id}

获取岗位技能明细（学习路径数据源，含类别与 JD 证据）