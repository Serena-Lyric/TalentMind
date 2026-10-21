# Career Nebula P2.3 Implementation Plan

> **For agentic workers:** 使用 executing-plans 在当前独立工作树逐项执行；完成后由 fresh-context reviewer 检查整项变更。

**Goal:** 在正式 Vue `/graph` 交付可环绕、平移、滚转、恢复的三维知识银河，并降低交互重绘成本。

**Architecture:** 保留同一页面和事实适配层，以相机模式选择三维渲染或 P2.2 固定投影。控制器基础相机与滚转后的显示相机分离，节点、关系、标签和拾取共享显示投影；WebGL 批处理知识几何，Canvas 绘制缓存标签。

**Tech Stack:** Vue 3 / Three.js 0.180 / camera-controls（优先验证）/ Node test runner / 现有 Element Plus。

**Spec:** `docs/superpowers/specs/2026-10-19-career-nebula-p23-design.md`，结合本轮用户完整执行要求。

## Global Constraints

- 基线 `a373427`，独立工作树及 `codex/m3-m5-p2-3-galaxy` 分支。
- 7845 节点 / 11412 原边保持；Python 222 原直连不受预算删除。
- 不操作生产库、正式重建、原始快照、历史岗位分类；不合并或清理其他工作树。
- 单击不移相机；完整返回姿态；派生关系/社区默认关闭；三条回退均可用。
- 左右面板隐藏滚动条但保留滚动与键盘操作。

## Review Focus

- 连续滚转后右拖/WASD 仍沿显示屏幕坐标，旋转/缩放不重置滚转。
- 输入法、输入框、修饰键快捷键和失焦不会留下持续移动。
- 相机目标不在原点或过渡中再次定位/恢复，仍完整且无姿态跳变。
- 背面/近裁剪和多角度重叠节点，拾取与标签/关系端点对应且不选隐藏点。
- 刷新、路由卸载、WebGL 丢失、窄屏面板重叠时资源与回退仍有效。

## Task 1：相机与深度

Files: `frontend/src/graph/galaxy/{camera,spatialLayout}.ts`，`frontend/tests/galaxyCamera.test.ts`。

Interfaces: 产出控制器 camera/displayCamera、完整 capture/restore、平移/滚转/update/focus/fit；确定性 `spatialPoint`。

- [x] 添加相机完整恢复、滚转后屏幕平移、投影/拾取、深度不改输入的失败测试并运行确认 RED。
- [x] 核验官方包版本、MIT 和 Three peer dependency；最小相机适配实现并 GREEN。
- [x] 对连续旋转/过渡/缩放和快捷键守卫补行为验证。

## Task 2：正式页面三维渲染

Files: `frontend/src/graph/galaxy/{background,knowledge}.ts`，`frontend/src/components/GraphPanorama.vue`，现有图谱测试。

Interfaces: 消费 Task1 显示相机，产出统一三维投影、批量星体/曲线、脏标记、诊断和 dispose。

- [x] 先扩展正式组件测试，覆盖原位选择、222 原边、筛选/搜索/返回。
- [x] 接入批量知识星体、真实曲线与标签投影，保留固定投影分支。
- [x] 加入输入、按钮提示、左侧滚动条处理和窄屏验证。
- [x] 运行前端完整测试及类型检查构建；预期通过，警告单列。

## Task 3：真实浏览器、配对性能与交付

Files: `docs/review/M3-M5-P2-3.md` 及同名证据目录、产品/资产/决策索引、陷阱记录。

Interfaces: 消费正式 `/graph` 和诊断输出，产出可审阅证据与 Draft PR。

- [x] 独立端口运行正式 Vue；真实浏览器覆盖全部验收操作并保存相机/来源/错误记录。
- [x] 同机配对 P2.1/P2.2/P2.3 绘制、响应、帧时间、内存与资源清理，不截屏计时。
- [x] 核对原快照/布局/旧证据摘要，复测三条回退；记录未达到项。
- [x] fresh-context reviewer 整体自检；必要修复先 RED 再 GREEN。
- [x] 同步报告与索引，显式暂存，提交并推送独立 Draft PR；不合并。

实机覆盖限制以P2.3报告为准：IAB原生右拖/系统IME/强制硬件上下文丢失未全覆盖，已明确区分离线回归与实机观察。

交付：Draft PR #35，面向master；核心实现/证据c400e4d。前置PR33仍未合并，本PR不会修改其分支；增量审查a373427..HEAD。
