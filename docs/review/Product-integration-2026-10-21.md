# TalentMind 统一产品集成验收（2026-10-20～21）

本报告区分已完成工程验证与真实站点限制。控制台准备/启动/停止及历史可操作；尚无本轮可准入完整JD，不宣称Gate1通过。

## 统一版本

- 工作区：`C:\Users\Serena Lyric\.codex\worktrees\m1-m2-quality-replay\TalentMind`，集成分支 `codex/product-integration-20261020`，基于最新 `origin/master@1e5f4da`；主仓10项修改未动。
- 合并提交：`f7816b8` 纳入 #40 `9f829bd`，包含 #38 `e2e07ec`、#39 `e20e6ff`；`a184d60` 纳入 #42 `fd2325f`；`4e28faf` 纳入 #37 `72b673a`，包含 #35 `df1ca24`、#36 `b7e6f65`。
- 保留原始提交/PR，无squash、无master推送/合并。文档并列保留带日期的证据；GraphPanorama冲突逐段整合真实加载/来源、node-field、legacy、相机/交互与失败清空。修复空间回退丢失真实数据集参数。
- 统一产品及准备/重新检查实现提交：`d93941d`。后续文档提交仅补交付索引，不改变实测业务代码。
- 远端最新检查未取得前端成员新增业务分支/提交，仅有接入说明#34；未覆盖她未提交或不可取得的独立工作。

## 启动与操作

在上述工作区双击 `start_system.bat`，或运行 `pwsh -File scripts/start-local.ps1`（PowerShell 7）。访问 `http://127.0.0.1:18080/#/collection`；后端健康为 `http://127.0.0.1:18000/health`。页面沿用明确标示的前端演示登录，未把它升级为后端账号认证；完整原文另由本地进程授权保护。

停止：双击 `stop_system.bat` 或 `pwsh -File scripts/stop-local.ps1`。先确认任务整树退出与历史归档，再停止本入口进程；数据库、数据卷、Edge保留，不关闭其他工作区。启动检查既有容器、本树依赖、端口进程归属、后端健康及前端代理真实数据库读取；失败日志在忽略的 `data/local/local-runtime/`。

当前配置、采前原像和原依赖junction保留在本地证据目录 `data/local/product-integration-20261020/`。`.env`与独立venv/node_modules仅本机，不依赖另一个工作树的应用源码或依赖目录。

真实样本图为显式私有预览：启动时可传 `-RealGraphDirectory ./data/local/quality-round2-v3`，再打开 `/?graphDataset=real&graphSpace=node-field-v1#/graph`。省略目录参数复用已保存选择；要关闭，先停止，再以 `-RealGraphDirectory ''` 启动。普通构建不打包私有原文。

## 联通根因与修复

1. 指定工作树原本缺 `.env` 和venv，前端依赖junction指向其他工作树。现保留原链接副本并独立安装依赖，私有配置复制到本树。
2. 旧模板/启动脚本仍采用3306，现有MySQL实际23306；端口占用曾被当成健康。新入口检查配置/代理，核对进程实例和监听子进程。
3. Docker Desktop停止后仅启动Web服务会形成“页面能开、数据库不可达”。新入口自动等待Desktop并只启原容器，缺失时明确报错，不创建新卷。
4. Windows venv包装器与真实Python不同PID。worker使用私有Job Object管理整树，停止等待完成/归档；入口停止亦核对保存实例，避免误杀。
5. 旧页面混用平台城市、详情尝试/成功及硬编码数值。重构为分步骤操作、真实分账、未知null和本轮run_id隔离。
6. 后续真实排查发现准备只传平台、复用同域首页，启动前门禁又要求已有职位；旧后台响应可能覆盖刚准备的新状态。修复为当前关键词/城市准确目标、prepare/start同目标、请求世代及最近显式检查结果保留。重新检查复用原标签，不通过新开/刷新规避门禁，目标跳回首页也不重复创建。见[准备目标陷阱](../superpowers/traps/2026-10-21-collection-prepare-target.md)。

## 可核验接口与数据边界

- `GET /api/collection/platforms`：BOSS北京101010100，智联北京530等各自城市；不支持来源无假启动入口。
- `prepare`不采集；`start`只启动显式单轮，访问阻塞/异常也归档真实run_id；本轮限定一关键词/城市/页、5列表/5详情，持续能力保留但禁用。
- `status/history`：列表、详情尝试、取得、完整、新增、更新、跳过、拒绝、失败、stop_reason；未知为null，`details`仅旧尝试兼容。归档waiting_for_browser不锁死页面；进程退出后的日志归档不冒充控制器重启。
- `results?run_id=…`：该轮真实事件/拒绝/失败、来源身份、观察时间、结果与jd_pool_id；不补旧JD。`raw/{id}`：当前数据库原文与职责、明确要求标题分段，无明确标题不推断。事件原文与当前库记录分别展示。
- 完整正文端点要求 `TALENTMIND_LOCAL_RAW=1`（统一入口仅在子进程设置）+回环+本地Host/Origin，跨站请求拒绝；真实经Vite代理的跨站results请求已得到403。事件JSONL/普通日志私有，status/history过滤TM_EVENT正文。
- 复用原fetch/pipeline/jd_pool；无数据库迁移、新业务表、M2正式表或Neo4j自动更新。拒绝/失败结果不以旧库原文补成成果。

## 已有验证与限制

- 真实浏览器完成演示登录、采集页真实数据库统计读取。后端health正常，Vite `/api`代理读到jd_pool2988，BOSS1137/智联1088/猎聘763；全库职责非空1622。
- 图谱：历史7845节点/11412关系，Python搜索与222直接关系；node-field显式加载、legacy空间回退；真实52节点/263陈述与原文证据回溯均已在浏览器检查。真实样本原文截图仅私有，不入仓。
- 最终准备修复定向167通过；此前更广M1相关303通过（含Windows纯sleep包装父/子停止、真实合成子进程到SQLite与历史）。最终全量离线为1373 passed / 2 failed / 2 skipped / 23 deselected；失败仍仅 `test_repository_draft_covers_eight_families_and_empty_release`、`test_shipped_source_hash_matches_a_fresh_LF_checkout` 的既有B3来源hash/quote不匹配，没有重签或跳过修绿。guard92个Python进程、网络尝试0、临时目录移除true。
- 最终前端128项通过，采集SFC26项；类型检查/构建通过，保留已有大chunk与相机混合导入警告。最终准备修复经独立只读复审，无新增P1/P2阻塞；此复审不替代负责人集中验收。
- 未运行生产库集成测试；纯测试只用临时SQLite/服务替身。正式数据只有授权有界试采可写，采后按全字段原像核查。

## 前端成员后续协调

采集页正式文件为 `frontend/src/views/Collection.vue`、`src/api/collection.ts`，图谱共享文件为 `GraphPanorama.vue` / `views/Graph.vue`。保留既有路由、壳层和演示鉴权。前端成员接入时须按本轮接口的null、finished_at、平台城市、run_id及本地原文门禁合并；不可回退演示平台数或将details改称成功。其余页面未因本次控制台重构覆盖。

## 回退与后续master建议

需要切回原#40时，先停止本入口，再切回原 `codex/m1-m2-quality-replay@9f829bd`；本轮唯一集成分支及合并历史保留。源码回退不自动删除/回滚数据；真实UPDATE必须依据私有原像逐行审查，不能仅删新增ID或按source批量清理。图谱数据集与空间分别回退，不导入或重建正式图。

建议负责人集中审查集成分支与本报告，网站人工验证完成后补齐未通过的真实门禁，再确认是否合入master；Agent不自动合并。

## BOSS／智联真实页面与采后核验

2026-10-21实际通过18080控制台操作，同一受控独立Edge，不调用临时Python采集函数、不变换身份或代理。表内“未执行”不填业务零值。

| 平台/配置 | 实际操作与结果 | 任务/数据库 |
|---|---|---|
| BOSS / Java / 深圳101280600 | 点击准备后已打开准确搜索目标；真实返回verification_required，页面显示“需人工完成安全验证”和完整目标URL，立即停止该平台，不反复重查/搜索 | 未点启动，无run_id；详情/完整JD未执行；INSERT/UPDATE=0/0 |
| 智联 / Java / 北京530 | 准备公开可访问，按钮可用；明确点击启动单轮后列表5、详情尝试1/取得1、完整0、拒绝1、失败0、跳过0；原因unverified_dom_identity。为避免重复无身份保证的访问，点击停止，归档user_stopped | run_id=`zhaopin-98c0d0f1f91c4dac9c675f06338d426d`；开始07:48:55，结束07:49:45（Asia/Singapore）；INSERT/UPDATE=0/0，PID清空，无采集worker残留 |

智联取得的是候选面板原文（466字符），由于当前DOM-only适配器不能可靠绑定到目标职位身份，被明确拒绝。**这是适配器身份绑定限制，不冒充网站验证/游客截断，也不冒充完整JD或入库成功。** 页面“查看原文”已实际打开本轮事件正文；其无jd_pool_id，界面明确不能读取本轮数据库原文映射，不用旧库原文补齐。完整合格JD→INSERT/UPDATE尚未在本轮通过。

页面“日志与结果”已实际打开归档状态、日志摘要和5个候选事件。停止API等待整个worker子树退出及历史归档；本轮停止后无后台采集，持续入口保持锁定。准备不自动start。

私有新原像 `before-recheck-20261021/` 与采后 `after-recheck-20261021/`、逐行verification、任务与事件保存在本地证据目录。精确对账：jd_pool INSERT/UPDATE/DELETE **0/0/0**，2988行全字段相同；其他七表全内容摘要相同；Neo4j7845/11412全内容摘要相同；正式graph.json SHA不变；主仓10项文件摘要相同。未在生产库运行集成测试，无测试数据写入/残留；没有清理或回滚真实数据。

公开截图仅控制台/历史图，不含完整JD、Cookie、凭据或私有原像：

- [BOSS明确人工验证与准确目标](product-integration/boss-prepare.jpg)
- [智联已准备、启动可用](product-integration/zhaopin-ready.jpg)
- [智联真实计数、停止与历史](product-integration/zhaopin-stopped.jpg)
- [归档日志与结果](product-integration/zhaopin-history.jpg)
- [历史图](product-integration/historical-graph.jpg)、[node-field](product-integration/node-field.jpg)、[legacy空间](product-integration/legacy-space.jpg)

后续需用户正常完成BOSS人工验证；智联需单独修复/证明DOM身份绑定后，再按新授权试采。不要为凑完整JD放松质量判定或重复采集。本轮统一版本可启动和观察真实链路，但Gate1未通过，不建议直接合并master。
