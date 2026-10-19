# P2.5 证据索引

正式Vue图谱真实浏览器捕获，2026-10-19，Asia/Singapore。工程状态与限制见[报告](../M3-M5-P2-5.md)。

- [五组同条件对照](comparison.html)：`p24/p25-{overview,middle,near,side,tail-orbit}.png`；每张对应同名JSON包含完整相机、分辨率、DPR、过滤、计数、源摘要及采样。P2.4为b7e6f65所含未改产品代码（与df1ca24相同），18154原构建；P2.5为4db4c10最终构建，18151。
- [程序核对](browser-checks.json)：5组camera/viewport/hash/freeze相同、非零滚转往返、非邻居和222个唯一索引。
- [实际PNG尺寸](capture-dimensions.json)：五组已用fullPage统一重拍为1600×900。初轮部分面板截图会裁成1437宽，不能只看DOM逻辑视口；非配对图保留实际边界。初轮侧视性能元数据另存[原采样](performance-steady-initial.json)，不冒充补拍后的时间样本。
- 主体特写：`job-closeup.png`、`skill-closeup.png`、`historical-scene-closeup.png`；渐变高亮：`gradient-job-scene.png`；Python：`python-222.png`、`python-final-page.png`。
- `python-keys-page-1.json`至`8.json`：最终222/222原生键盘激活核验。`python-pointer-transients.json`仅为初轮60次鼠标操作的瞬态记录，4次hover落点不同，不代表全部222条；报告另说明移开指针前键盘瞬态。
- 类型/可见/相机：`python-type-hidden`、`non-neighbor-before/selected`、`selection-cleared`、`p25-rolled-panned`、`job-selected/all-connections/returned`的PNG/JSON。
- 回退：`fallback-p24/p23/p22/p21/legacy.png`；legacy采用独立组件，没有新版`.nebula-page`诊断属性，所以对应JSON.state为null，截图显示7845/11412。
- [环绕采样GIF](orbit-sampled.gif)及`orbit-frame-00..12.png/json`、[采样说明](orbit-recording.json)：真实操作关键帧回放，非实时连续录屏，不用于FPS测量；原始图未改。
- 资源：`lifecycle-loaded-1..3`、`lifecycle-console.json`、`final-telemetry.json`。错误：`console-errors*.json`，捕获数组为空。
- [数据与原证据保全](data-integrity.json)、[测试日志](frontend-tests.log)、[构建日志](frontend-build.log)、[后端定向](backend-graph-tests.log)、[独立代码审查](code-review.md)。

普通截图默认所有类型开启；`python-type-hidden`显式隐藏岗位（222条边按类型隐藏）。三类星体、历史边和装饰粒子分账；历史Industry不是正式行业分类。源码/硬件/时间采样与最终美术验收分别解释。
