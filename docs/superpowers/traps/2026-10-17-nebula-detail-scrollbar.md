# 节点详情可见滚动条与 headless 截图（2026-10-17）

## 症状

右侧节点详情长内容显示竖向滚动条，与用户确认的界面要求不符。

## 根因

`.nebula-detail` 明确设置 `scrollbar-width: thin`。另外，headless 浏览器可能通过默认 `--hide-scrollbars` 隐藏滚动条，仅看默认自动化截图会误判产品已隐藏。

## 修复

只将右侧 `scrollbar-width` 改为 `none`（Firefox/现代 Chromium），并增加 `.nebula-detail::-webkit-scrollbar { display: none; }`（Chromium 兼容）。保留 `overflow-y: auto`，不修改尺寸、位置、内容、左侧菜单或交互。

## 教训与验证

对照截图排除 `--hide-scrollbars`，先在原样式下记录隐藏断言失败，再用同一真实岗位、分辨率和浏览器验证修复。除样式值和截图，还需实际测试滚轮、小增量 wheel、键盘 Home/End 及末尾内容完整可见；核对外框、文字哈希、左侧菜单和相机状态。测试浏览器 finally 关闭，GET API 只读，结果与前后截图见 [P0.5 报告](../../review/Career-Nebula-issue-26-P05.md)。
