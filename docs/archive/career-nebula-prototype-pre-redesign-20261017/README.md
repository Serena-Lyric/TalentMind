# Career Nebula 旧原型归档（2026-10-17）

**旧 Issue #24 已终止；本分支只保全历史，不是新一轮技术或产品基线。** 历史报告中“待用户选路/待集成”属于终止前草稿，不是当前指令。下一轮按 Issue #26 和另行确认的规范推进，本次不执行其开发、不复制《诗云》代码/素材、不修改产品设计。

## 分支与来源

- 分支：`archive/career-nebula-prototype-pre-redesign-20261017`。
- [GitHub 分支](https://github.com/Serena-Lyric/TalentMind/tree/archive/career-nebula-prototype-pre-redesign-20261017)。
- 来源：`issue-24-r0/TalentMind`，原分支 `codex/issue-24-r0`。
- 基线：`abb73eb9c2b35819ba0ac870ed4cbd8dd5d91e7f`，PR #23 的已提交历史。此前图谱布局/交互、测试和记录由基线完整保留，不重新算作 R0 新开发。
- 35 文件原样保全提交：[`473236db3e664b87894c35947ad1ae0c50acdf0b`](https://github.com/Serena-Lyric/TalentMind/commit/473236db3e664b87894c35947ad1ae0c50acdf0b)。
- 本说明、manifest 和归档状态随后另作提交；最终 SHA 以本分支 GitHub HEAD / `git rev-parse HEAD` 为准。本分支不创建改造 PR、不合并 master。

已逐一检查16个既有 worktree 的 HEAD、分支、状态、索引及文件摘要。只有原主工作区的 M1/MySQL 修复和 R0 原型树有未提交内容；其余14个工作树干净。各 HEAD 均可从核查时的远端分支 HEAD 集合追溯；R0 没有新增未推送提交，遗留为33个未跟踪文件和2个原型文档修改。

归档分支核查时本地/远端均不存在，故从实际基线新建独立归档 worktree；不切换、暂存或修改原树。另只读核对 PR #25 文档分支 `6f3a8873a2e7e5948bd93d8b51adc09dcbec5676` 的产品 §7：旧方案终止、新视觉规范另立；该分支修改未复制进本归档。

## 实际文件清单

共 **35 个历史成果文件，11,122,131 字节（约11.12 MB）**。逐项原始字节数、SHA-256、用途和来源见 [manifest.json](manifest.json)。原样提交与源工作树逐文件一致；后续仅新增归档元数据，并在归档分支资产文档补终止状态。

| 文件 | 用途 |
|---|---|
| `frontend/prototypes/nebula-r0/main.js` | Vue 页面、搜索、相机、详情、录屏 |
| `frontend/prototypes/nebula-r0/model.js` | 空间协议、LOD、半径、标签、装饰生成 |
| `frontend/prototypes/nebula-r0/renderers.js` | Canvas / Three Points 与内嵌 GLSL 着色器 |
| `frontend/prototypes/nebula-r0/style.css` | 独立实验页面样式 |
| `frontend/prototypes/nebula-r0/index.html` | 独立入口 |
| `frontend/prototypes/nebula-r0/package.json` | JavaScript 依赖与命令 |
| `frontend/prototypes/nebula-r0/pnpm-lock.yaml` | 精确依赖锁 |
| `frontend/prototypes/nebula-r0/pnpm-workspace.yaml` | 原型安装边界 |
| `frontend/prototypes/nebula-r0/requirements-research.txt` | Python 固定研究依赖 |
| `frontend/prototypes/nebula-r0/vite.config.js` | 独立构建配置 |
| `frontend/prototypes/nebula-r0/.gitignore` | 依赖、缓存、生成数据排除 |
| `frontend/prototypes/nebula-r0/README.md` | 历史运行命令、协议、限制 |
| `frontend/prototypes/nebula-r0/tests/model.test.js` | 实体保全、LOD、像素、搜索、标签测试 |
| `scripts/nebula_r0.py` | 只读投影、群落比较、布局、协议导出 |
| `scripts/tests/test_nebula_r0.py` | 研究算法、完整图跨进程确定性回归 |
| `docs/review/M3-M5-issue-24-R0.md` | 未完成交付的原研究报告，按历史草稿保存 |
| `docs/review/issue-24-r0-analysis.json` | 拓扑、群落、参数、依赖版本摘要 |
| `docs/review/issue-24-r0/observations.json` | 原浏览器观察记录，早于最后部分截帧 |
| `docs/review/issue-24-r0/a-audit.json` | A 节点、原关系、相机与耗时审计 |
| `docs/review/issue-24-r0/b-audit.json` | B 节点、原关系、相机与耗时审计 |
| `docs/review/issue-24-r0/a-overview.png` | A 实际全览 |
| `docs/review/issue-24-r0/a-community.png` | A 群落局部 |
| `docs/review/issue-24-r0/a-near.png` | A 近景 |
| `docs/review/issue-24-r0/a-python-all.png` | 原命名为 A 全关联的历史截帧，最后重拍未收口 |
| `docs/review/issue-24-r0/b-overview.png` | B 实际全览 |
| `docs/review/issue-24-r0/b-community.png` | B 群落局部 |
| `docs/review/issue-24-r0/b-near.png` | B 近景 |
| `docs/review/issue-24-r0/b-python-all.png` | B 全关联历史截帧 |
| `docs/review/issue-24-r0/b-rotated.png` | B 显式旋转历史截帧 |
| `docs/review/issue-24-r0/b-type-5px-no-dust.png` | 类型色、5px 上限、无装饰层对照 |
| `docs/review/issue-24-r0/a-interaction.webm` | A 真实画布交互录屏 |
| `docs/review/issue-24-r0/b-interaction.webm` | B 真实画布交互录屏 |
| `docs/superpowers/traps/2026-10-17-r0-prototype-viewport-and-selection.md` | 视口、响应依赖、确定性问题教训 |
| `docs/superpowers/资产与状态.md` | 历史 R0 资产/验证增量，后补本归档状态 |
| `frontend/README.md` | 原型入口的历史文档增量 |

没有另发现独立着色器文件或 R0 Vue SFC。原目录位置保留，便于按旧说明研究。已有正式组件、`frontend/src/graph/`、PR #23 的测试/计划/记录来自基线历史，不是本轮新增或修改。

## 可参考与不宜沿用的实验

可参考：

- 实体/原属性保全、来源指纹、中立空间协议，以及事实、推断群落、装饰层隔离。
- 岗位—技能投影、Jaccard/IDF 对照，种子/分辨率/高频桥梁敏感性记录。
- 原位选中、主动全关联/返回、多结果搜索、像素上限、标签碰撞及历史测试。
- Points/BufferGeometry、点形状/渐变着色器、Canvas 对照、依赖锁和原始录屏。
- Python 子图集合枚举影响跨进程确定性的失败回归与排序重建教训。

已经观察到不足、不能直接沿用为新方案的部分：

- 五个分离团块没有达到大型连续知识银河目标；装饰粒子未解决整体形态。
- 群落受高频技能、软技能影响，语义混杂；IDF 结果不是职业分类准确率证明。
- 222 条完整直连仍呈扇形线束；近景拥挤，避让会省略普通标签。
- 首次/切换近景出现顿挫，旧表 B 样本为112.8ms；这是 CPU 提交观察，不是持续 FPS、GPU 或跨设备验收。逐帧 CPU 投影/重建 BufferAttribute 未优化。
- 未验证 GPU context loss、移动端/多浏览器矩阵，无 Bloom、美术定稿或正式业务集成。这些不足不证明 Three.js / Canvas 本身不适用。
- **最后截帧重拍未完成收口**：部分 PNG 已更新，observations/报告未全部同步。保留原文件，不重拍或改写为“已验收”；对照标签、视角与性能数字须回到原始材料逐项核实。

## 未上传、保留本地的内容

| 文件/位置 | 原因 |
|---|---|
| 原型 `public/data.json` | 约6.42MB可重建协议，Git忽略；原 `exchange/m3/graph.json` 已在基线中，脚本/依赖/指纹已归档。 |
| 原型 `node_modules/`、`.vite/`、`dist/` | 可重新安装/构建，不上传依赖和缓存。 |
| `data/local/issue-24-r0-env/` | Git忽略的Python环境，可由固定requirements重建。 |
| `data/local/r0-vite.out.log`、`r0-vite.err.log` | 私有运行位置，两文件核查时均0字节，不是测试结果证据。 |
| 桌面 `ChatGPT 图像 2026年10月17日 20_21_50.jpg`、`20_21_52.jpg` | 私有审美参考，原型运行不依赖；不复制或公开。 |
| Downloads `r0-a.webm`、`r0-b.webm` | 更早不同版本录屏；工作树已选存的较新两段已归档。额外私有版本保留原地，如需补充上传须另行确认。 |
| Downloads `r0-a-audit.json`、`r0-b-audit.json`、`r0-b-audit (1).json` | 更早视角/布局记录，非恢复当前源码必需；保留私有原地。下载目录另四项与已归档录屏/审计哈希相同，不重复上传。 |
| 原主工作区10项 M1/MySQL 未提交文件 | 无关任务，不复制、不暂存、不提交。 |
| `.env`、密钥/Cookie、数据库/卷、input/output/data/local等 | 项目私有边界，未强制添加。 |

没有发现必须取自私有/忽略目录才能恢复的独有源码；已确认 R0 源码均归档。没有删除上表文件、下载物、旧分支/worktree、依赖或进程，也未停止已有原型服务。

## 本轮核验与恢复范围

- 35文件源工作树、Git索引、保全提交原始blob逐项SHA-256相等；二进制不转换。文本保留源换行，普通diff因CRLF可能较大；忽略行尾后两份已有文档只有8行/2行原型增量。按 `core.whitespace=cr-at-eol` 检查通过。
- 私钥/常见Token/明文凭据模式扫描无命中，并核查来源/内容、JSON可解析、图片/WebM文件头，人工查看A/B全览。模式扫描不能证明所有类型秘密绝对不存在。
- JS五个文件用 `node --check`、Python两个文件用标准库AST解析，通过。**未重新运行原型、布局、模型、测试或构建**；历史5+7、39项和构建数字仅来自旧记录，不冒称本轮结果。
- 不访问MySQL/Neo4j、不采集/迁移/清理、不修改主README、已确认产品决策、正式图谱或生产API。
- 前后核对16个原worktree的HEAD/分支、索引SHA、Git状态、全部已跟踪/非忽略未跟踪文件摘要，以及.env/PAUSE_COLLECT存在时的私有哨兵摘要。私有核查明细只留本机临时审计目录，不公开实际配置。
- 恢复研究可在新目录检出本归档分支，再按[历史原型README](../../../frontend/prototypes/nebula-r0/README.md)安装固定依赖并显式生成忽略的数据。归档不依赖localhost仍运行；不要在现有库上执行历史导入命令。

**完成边界：只归档推送；不建PR、不合并、不更新#23/#25/#24，不续做#26，不清理旧环境。**
