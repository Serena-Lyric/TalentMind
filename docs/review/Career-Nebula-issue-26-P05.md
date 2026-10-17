# Issue #26 · P0.5 交互补全交付（2026-10-17）

状态：已开发、本机验证；等待 ChatGPT 复审与用户实机验收。未合并 PR #27 或本轮 PR，P1《诗云》未启动。

## 基线、分支与运行

- 基线：PR #27 `codex/issue-26-p0@41f9184f2e47a86df4fc86d60b93556e8a19e0db`。用户已验收 P0 外壳；本分支仅叠加 P0.5，PR base 为 `codex/issue-26-p0`，不是把 P0 当作已发布 master。
- 代码及正式决策提交：`9f9b478f6afd0f7ea68496bc08ea1ce5ab3b2528`。报告/真实截图另作独立提交。回退该代码提交即可回到 P0 行为；截图文档提交不承载业务逻辑。
- 独立检出：`D:/Application/ClaudeCode/repository/TalentMind-p05`；分支 `codex/issue-26-p05`。原目录仍为 `codex/m1-stage-02@e8235c8`，既有未提交运维文件保持原状；原 17 个 worktree 保留。
- 验收地址：[P0.5 图谱](http://127.0.0.1:18087/#/graph)。只读诊断：[含诊断入口](http://127.0.0.1:18087/?nebulaDebug=1#/graph)，不需要 experimental 参数。未登录时使用页面已有的演示账号登录。
- 保留原后端 `18000` 与 P0 对照 `18086`；本轮前端 `18087`。PR #23 对照仅在本轮目录内导出 `abb73eb` 的 frontend，临时 `18088` 截图后已关闭；全部测试浏览器在 finally 中关闭。

## 实际源码变化

| 文件 | 本轮变化 |
|---|---|
| `frontend/src/components/GraphPanorama.vue` | 启用完整 fit/动态缩放/重置、原位选择、全部真实可见直连、显式全部关联/返回、搜索导航、悬停与三类标签；H 用 v-show 保留面板状态；模式 resize 保留相机，全览窗口 resize 重新 fit；窄屏面板错开滚动。 |
| `frontend/src/graph/nebulaLayout.ts` | 经用户确认，只提取 PR #23 的确定性关系坐标；无新语义布局或旧 R0。 |
| `nebulaViewport.ts`、`nebulaEdges.ts`、`nebulaPresentation.ts` | 选择性复用 PR #23 的真实面板可用矩形、坐标转换、命中、搜索/边筛选与标签避让；屏幕半径上限为岗位/行业/技能 12/10/8 CSS px。 |
| `frontend/src/graph/graphShortcut.ts`、`frontend/src/views/Graph.vue` | Y/H 单键保护、IME 生命周期、路由限定、事件注册/释放；两种模式状态由 Graph 路由持有。 |
| `frontend/src/App.vue`、`frontend/src/styles.css` | 仅图谱路由沉浸类隐藏应用导航/外壳间距，图谱铺满网页内容区域；无 Fullscreen API、无 F11；保留 P0 默认外壳与其他页顶栏。 |
| `frontend/package.json`、`pnpm-lock.yaml` | 恢复 PR #23 已用 d3-force 3.0.0（ISC）及对应类型，增加 Node 测试命令；复用已装依赖，未安装或重装共享依赖。 |
| `frontend/tests/`、`frontend/scripts/test-nebula-browser.mjs` | 42 项算法/真实 SFC 回归及可重跑的真实浏览器 UI 流程。浏览器脚本通过 PLAYWRIGHT_MODULE 使用本机既有运行时，未将 Playwright 增为产品依赖。 |

已同步 PRODUCT_DECISIONS §7.3.1、决策索引 D105–D108、视觉规范、第一批任务书、P0.5 计划和资产状态。H 及关系坐标均由本会话用户明确确认。P0 已验收与 P0.5 已开发/待验收分开记录；后续视觉参数、引擎、语义社区/路径、设置页及旧 PR/工作树处置仍未定，不在本轮实施。

## 布局与 PR #23 的关系

PR #27 旧版黄金角岗位和行业横排导致约 27 万坐标宽度，本轮不是继续保留该坐标后偷偷裁掉外围节点。用户明确允许仅复用 PR #23 关系坐标：岗位/共享节点形成确定性骨干，叶子围绕真实父节点，孤立节点有有限位置。与旧 P0 位置不同，与 PR #23 experimental 的全部 **7,845 个坐标逐项相等**，逆序输入仍相等；关系数据仍是 11,412 条，未增删节点/边。

坐标一致不代表相机比例相同：P0 主窗高度与 PR #23 原外壳不同，完整 fit 会根据实际矩形调整比例和平移。普通边有 LOD 预算；选中时保留该节点的全部类型可见真实直连，不混入邻居之间的关系。选择态只显示当前邻域，清除选择恢复完整筛选图；缩放不会改变真实数据数量。

对照证据：[坐标比对记录](assets/issue-26-p05/comparison-results.json)、[PR #23 1600×900](assets/issue-26-p05/pr23-experimental-1600x900.png)、[PR #23 1920×1080](assets/issue-26-p05/pr23-experimental-1920x1080.png)。这些是真实对照浏览器画面，不是新的视觉目标或《诗云》样品。

## 实际验证

环境：Windows、本机 Node **v24.15.0**、真实 Microsoft Edge **155.0.4283.45**，以 headless Chromium/Edge 的实际网页视口渲染截图，deviceScaleFactor=1。使用既有后端 GET API，未替换正式图谱响应为 Mock。浏览器中真实键盘、鼠标、滚轮与路由操作；evaluate 仅读诊断/尺寸、设置路由及模拟 IME/重复键边界，不调用组件事件函数。

| 检查 | 实测结果 |
|---|---|
| `pnpm test` | **42 passed / 0 failed**，覆盖真实 SFC、布局/视口/边/标签及热键保护。 |
| `pnpm run build` | vue-tsc + Vite 成功；保留现有 >500kB chunk 警告。 |
| 两种桌面尺寸 | 1600×900 图谱/导航均为 y=18..882；1920×1080 均为 y=18..1062，首屏无额外纵向溢出。完整 7845 节点 fit，outside=0。 |
| Y/H | 默认/沉浸交叉隐藏恢复，图谱矩形分别精确为 1600×900、1920×1080；fullscreenElement=null；相机 scale/x/y 精确往返。选择、搜索游标、非默认筛选、高亮保留；长按只切一次。 |
| 搜索及关系 | Python **87 项**，Enter/Shift+Enter/前后按钮循环；222 条原始直连全部提交，显式全关联 fit **223 节点**且 outside=0，重复查看不覆盖原相机，返回精确恢复。隐藏岗位后原始222、可绘制0，无虚构边。 |
| 鼠标及窗口 | 实际节点/空白点击和关闭详情均不改相机；真实滚轮、拖拽；探索 resize 保留相机，全览 resize 重新适配。 |
| 筛选/刷新/窄屏 | 三类开关、全关闭、刷新成功；1280×600、390×844；窄屏选中、全部关联、返回均可点击，两面板不重叠并各自滚动；窄屏沉浸视口高度844。 |
| 输入保护 | 搜索输入、textarea、select、contenteditable、Ctrl/Alt/Meta/Shift 组合、repeat、IME isComposing/compositionstart 与 keyCode229 均不误触发。 |
| 其他页面与登录 | Dashboard/Jobs/Analytics/Evolution/Resume/Learning/ResumeDemo/Collection 八页顶栏和热键隔离冒烟通过；错误密码、登录守卫、注销、重新登录及重入后无重复监听通过。不是八页全部业务功能验收。 |
| 浏览器错误与写入 | pageerror=[]；API 非 GET/HEAD 写请求=[]；临时输入元素 finally 删除，浏览器 finally 关闭。未启动采集/导入/迁移或数据库集成测试。 |

完整结果：[browser-results.json](assets/issue-26-p05/browser-results.json)。复跑（frontend 目录，前端18087和既有只读 API 可用）：

```powershell
$env:pnpm_config_verify_deps_before_run='false'
pnpm test
pnpm run build
$env:PLAYWRIGHT_MODULE='C:/Users/Serena Lyric/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
node --experimental-strip-types scripts/test-nebula-browser.mjs
```

共享 node_modules 为指向已装 PR #23 依赖的 junction；不应对它执行删除或重装。pnpm 进程关闭自动依赖重装检查；没有重新生成依赖树。独立检出使用本地对象共享以避免下载整仓，与原工作树的文件及分支状态隔离，后续仓库清理仍需单独审计。

## 独立审查与修复证据

独立只读审查无 Critical，发现窄屏详情遮挡（Important）和搜索标签避让读取旧面板高度（Minor），均已修复：

- 窄屏真实浏览器先复现面板相交 RED，再增加错位限高滚动；最终实际点击关联/返回通过。
- 搜索面板高度变化新增 SFC 回归先得到 drawn=1 的 RED，等待 nextTick 后绘制得到0；42项全绿。
- 初次网页沉浸测试发现高度864而非900，修正 scoped CSS 优先级后两分辨率通过；图谱外壳动画禁用，避免连续 resize 破坏相机。

长期陷阱记录：[全览基线与网页沉浸高度](../superpowers/traps/2026-10-17-nebula-fit-and-immersive.md)。独立作者审查和本机测试不能替代 ChatGPT 复审或用户视觉验收。

## 真机截图

以下全部是本轮真实页面渲染，数据为当前既有 API 的 7845节点/11412关系；无装饰节点注入、无 AI 合成画面。

| 场景 | 1600×900 | 1920×1080 |
|---|---|---|
| P0 默认外壳 + P0.5 全览 | [查看](assets/issue-26-p05/overview-1600x900.png) | [查看](assets/issue-26-p05/overview-1920x1080.png) |
| Y 网页沉浸 | [查看](assets/issue-26-p05/immersive-1600x900.png) | [查看](assets/issue-26-p05/immersive-1920x1080.png) |
| Y + H 隐藏内部面板 | [查看](assets/issue-26-p05/immersive-hidden-1600x900.png) | [查看](assets/issue-26-p05/immersive-hidden-1920x1080.png) |

[Python 搜索](assets/issue-26-p05/search-python-1600x900.png) · [全部关联](assets/issue-26-p05/connections-python-1600x900.png) · [真实滚轮近景](assets/issue-26-p05/zoom-1600x900.png) · [窄屏选中及面板](assets/issue-26-p05/narrow-selected-390x844.png) · [窄屏 Y/H](assets/issue-26-p05/narrow-immersive-hidden-390x844.png)

![1600×900 默认全览](assets/issue-26-p05/overview-1600x900.png)

![1920×1080 默认全览](assets/issue-26-p05/overview-1920x1080.png)

## 保护边界与限制

`backend/`、`exchange/` 相对基线无 diff；正式 graph.json 的 Git blob 仍为 `1416538fedc56d928815b8d6322d0d40c51dac1f`，新检出/原目录 SHA-256 同为 `6565D56DBC5A267EB90144F078C54F3D0C761C9A98CA29A18B4DC9C6CDDE38E2`。未直接连接或查询数据库，故不宣称本轮查询过库表计数/清理夹具；没有写库测试。原工作区的未提交文件清单与开工时一致。

现有 API 的关联岗位数元数据（如 Python 显示225）可能与真实直接边数222不同，未擅改后端或伪造前端数字；关联绘制及诊断以真实边为准。普通 LOD、近景绘制耗时不构成持续帧率保证；未做生产部署、网络失败/空图端到端模拟、付费模型或数据库集成测试，也没有远端 CI 成功声明。离开图谱会初始化下一次图谱会话，不承诺跨路由/刷新持久保存。

到此停下，等待 ChatGPT 复审和用户验收；不自动合并、不启动 P1、不清理旧分支或工作树。
