# Issue #73 七页面接通阶段报告

本轮仍是本地开发产品，不对外发布，不合并。基线`33d5df43c89371684d53bfa7a3465fddd13ca558`，分支`codex/issue-73-seven-pages`；实现提交`749a6aa1c3f633b3b44baea17aa49097f2fc71a1`；其后的文档提交不改变已验证代码，最终head及独立复审入口随PR记录。需求依据：[Issue #73](https://github.com/Serena-Lyric/TalentMind/issues/73)。产品规则已回写主文档，阶段状态与资产位置见[资产与状态](../superpowers/资产与状态.md)。

## 页面 → API → 实际结果

| 页面 | 实际路径与已验证结果 |
|---|---|
| 采集 `/collection` | 保留原控制器、频率门禁及准备/开始/停止边界；原文弹窗显式携带JD到`/m2`。浏览器隔离QA仅验证503原因、未知计数与禁用启动；未执行实站采集。 |
| M2 `/m2` | `/m2/delivery/inputs,runs`→`DeliveryService`→`delivery.runner`→P1/P2/P3/P4，冻结与开始分开。隔离HTTP实际完成两次合成处理；浏览器读到同run事实、OR组合、原文偏移、未执行归属、技能候选/投影。 |
| 画像 `/jobs` | `/jobs`列表/详情/PUT读取`job_definition`；保留必备/加分编辑身份，同事务审计写`job_change_log`。SQLite往返及浏览器详情已核验，无虚构open/薪资/发布时间，维护共享作用域可见。 |
| 演化 `/evolution` | `/evolution/timeline/{id}`显示档案前后值/版本/原因；`/m2/delivery/compare`只读两个确切run，按来源及研究registry比较。浏览器从M2链接带入选中run、选基线比较成功，缺少共同来源明确不可比。 |
| 图谱 `/graph` | `/m2/delivery/runs/{id}/graph`→内容摘要快照→`deliverySnapshot`校验→现行Three.js/Worker视图；已验证同run往返。移动run的旧snapshot、缺失snapshot及源证据篡改由回归覆盖。历史P2.5/旧M2身份保留，无静默回落。 |
| 简历 `/resume` | `/resume/upload`→正式parser/matcher；浏览器上传合成TXT，显示80%字段覆盖率与3项实际规则分70/60/30，不解释为准确率。未用真实简历或外部模型。 |
| 学习 `/learning` | `/learning/jobs`全部合格画像、`/learning/generate-path`校验要求摘要并重算规则分/路径。浏览器先验证未选状态，再选择前三名之外Java画像，显示同目标摘要、实际0分与3项学习建议。SQLite覆盖编辑后409及显式重算；退出/切换/迟到响应由组件/会话回归覆盖。 |

## 接入、删除与保留

- **接入：** 新统一HTTP任务；技能候选`CandidateRegistry.observe→CandidateRegistry.project→align_analysis`；来源独立职责研究假设；原输入/分析/知识/候选版本；新图快照；档案审计与目标要求摘要。
- **删除：** Dashboard/Analytics页面、直接路由、dashboard API/router、专属样式/测试；LegacyGraph/AbilityRadar、旧图`/graph/{data,jobs,years,skill-radar}`、未使用`/resume/{target-jobs,skill-dimensions}`和`/learning/job-skills`；无消费者的G6/ECharts依赖；旧Workflow执行/重放/新审核写入、旧图生成入口；顶层M2旧CLI/LLM管道25模块及专属6测试/SQL夹具。
- **迁移支撑：** 旧SQL原件值解析移入`integration/sql_values.py`，`real_jd_export`继续使用，原解析回归保留。
- **必要保留：** 原始采集与身份门禁、现行简历预览/PDF导出；输入/安全路径/原子导出/OS租约；新契约复用Evidence/角色结构；历史图离线再现依赖的foundation/screening/semantics/governance；历史目录及审核约束。不以“未来可能用”保留第二套网页业务链。

具体删除路径以PR diff为准；私有源目录、数据库、卷和原始交接文件没有删除或迁移。

## 旧任务与数据身份

旧`workflow.sqlite3`以mode=ro核实45项：37 completed_with_issues、7 queued、1 stopped，没有running/stopping/publishing。7排队与1停止保留原状态/原文；页面声明只读退役，若继续必须显式选择新输入建立delivery运行，不能静默恢复旧引擎或冒称完成。`History`不会创建缺失旧库，保留输入/报告/人工记录完整性校验。

既有新版10个run来自P5/P6的7个合成连续序列及3个受控DEV运行，只读挂载原目录；10个结果的Python新图投影→前端验证器联调通过。此项不包含模型重算，也不是独立真实语义验收。已删除两份被替代的旧产品/真实规则改进设计和一份旧Gate3报告，长期边界保留在正式说明/陷阱，旧证据用固定Git提交追溯，当前报告总数5份。

历史演示日志按固定275条基线中32条的完整业务内容摘要匹配，未按数据库ID、模糊关键词改写历史。

## 验证与运行边界

- 最终前端完整回归：**250 passed**；`pnpm run build`包含类型检查并通过，保留既有大chunk告警。此结果包含最终审查修复和展示修订。
- 最终后端`python -m pytest -m "not integration" -q --disable-warnings`：**2423 passed / 2 skipped / 21 deselected**，241.96秒。跳过/排除不当作通过；已删除接口的专属测试退役，共享Neo4j生命周期测试保留。
- 新M2、知识治理、停止/恢复、候选提交后崩溃、租约冲突、放弃不可复活、历史读取、演化身份、目标摘要与迟到响应有针对性回归。三名实现代理交叉审查修复并列任务基线、移动图快照、学习重算迟到、历史导出缺import；独立整体审查另发现既有技能双重成员丢失和审计类型差异造成版本断链，均补RED→GREEN回归修复。自检不代替ChatGPT PR复审。
- 浏览器使用Edge、前端18080→后端18100；后端是真实FastAPI路由+隔离SQLite+合成Fixture处理器，未连接正式MySQL/Neo4j或发模型网络请求。六页主要阅读/推荐/目标流程实机通过，采集页只验隔离不可用状态。未覆盖PDF/DOCX实机上传、真实站点、fresh模型、真实数据库部署和全部设备尺寸。
- QA使用独立runtime，正常关闭后`job_definition/job_change_log/job_skill`夹具计数均0，runtime目录删除。原18000/18080进程与QA18100/18080最终均无监听。取证脚本、HTTP结果、日志及七张截图仅在忽略的`data/local/issue73-qa/`，不上传原文/数据。

## 限制与待审

没有新增产品含义裁决。#63真实中文同组、完整职业归属与市场准确率仍未验收；单来源职责种子只是研究假设。真实模型配置和收费运行仍需相应许可。旧未完成任务不自动迁移；旧历史图仅能读取已保存产物。首次推送后的CI及ChatGPT独立复审仍须核对最终head，项目保持开发中。
