# Career Nebula · P1-A 视觉实验

独立 Three.js / WebGL 2 原型，**不是正式图谱页面**。八职业星区、116 个节点和 40 条曲线全部为确定性合成视觉演示；不请求后端，不读取 JD、M3 快照或数据库，不表示审核后的知识关系。

## 运行

在本目录执行（Node >=22.12，当前验证 Node 24.15）：

```powershell
npm ci --ignore-scripts
npm run dev
```

打开 <http://127.0.0.1:18126/>。端口严格绑定 18126；被占用会失败，不能停止其他服务或自动换端口。依赖、锁文件、构建目录均在本目录，**不要把这里的 node_modules 链接到正式前端的共享 junction**。

```powershell
npm test
npm run build
# 确认 18126 未被本轮 dev 服务占用后，才使用 npm run preview
```

`dist/` 是独立静态输出，不修改正式 Vue 应用。构建有约 530 kB 单包警告，gzip 约 135 kB；本轮没有为视觉实验增加拆包架构。

## 操作

- W/S/A/D：相对屏幕持续平移；Q/E：持续放大/缩小。
- 无选择时滚轮调整装饰流速，范围 0–2，可暂停；有选择时滚轮调整相机距离，范围 24–520。
- 单击星体原位选择，单击空白清除；拖动旋转观察纵深。选择不触发镜头定位。
- 输入框、组合输入、Ctrl/Alt/Meta 快捷键受到保护，失焦或切出页面清除持续按键。

默认没有操作提示或调试 HUD。仅 `npm run dev` 的 `?diagnostics=1` 显示诊断面板，可运行真实 DOM 事件检查、记录前台帧时间和录制真实 canvas.captureStream 录像。录像由页面脚本驱动 DOM 键盘/滚轮与演示选择，**不是人工操作录像，也不是静态图视频**。生产构建不包含本实验的诊断模块、GPU/UA 采集或帧历史。开发录像保存到本机 TEMP 随机文件，生产预览没有保存入口。

可复现截图入口：`?view=mid`、`?view=near`、`?view=selected`；`?evidence=1` 固定场景容器为 1600×900，浏览器视口须相应设置。正常体验不使用 evidence 参数，自动跟随窗口。

## 文件与视觉参数

| 文件 | 用途 |
|---|---|
| `src/config.js` | 粒子数量、画质、旋臂、运动、相机、八示例色场及临时实体样式 |
| `src/generate.js` | 确定性空间、密度噪声与合成节点/边 |
| `src/particles.js` | 尘埃/薄雾/星核/亮星/背景的 GPU Points Shader |
| `src/knowledge.js` | 固定的可选星体、屏幕命中、选中星核与持续光晕、端点准确的曲线 |
| `src/camera.js`、`control-state.js` | OrbitControls、持续键盘、滚轮分流、输入保护与边界 |
| `src/main.js` | 组合场景、适度 Bloom、标签与 ResizeObserver |
| `src/diagnostics.js` | 仅开发时按需加载的检查和真实视频采集 |

不旋转知识网络。装饰只做小幅有界的局部漂移/呼吸，调速累积时钟，改变速度没有相位跳变。中心没有大面积光斑、贴图、CSS/SVG 银河或底光精灵；星云结构全部来自真实三维粒子叠加。

## 参考与许可

主要参考 [《诗云》原作](https://shiyun.cohenjikan.com/) 和 [源码](https://github.com/Cohenjikan/shiyun)，研究固定到 `2c7ff2fe5c41b1a833e29d47075e6030636d9a10`：Galaxy、PoetStars、GiftLines、positions、galaxyParams、App、DEVLOG。参考其分层、高斯柔边、加法叠加、空间密度与曲线处理方法；全部独立编写。原作 PolyForm Noncommercial 1.0.0 的源码/纹理/诗歌/图片/视频均未复制进仓库。

直接依赖 Three.js 0.180.0（MIT）、开发依赖 Vite 7.3.7（MIT）；许可证随 npm 包保留。锁文件固定安装结果；本轮 `npm audit` 为零漏洞。未引入 React、后端或新的正式前端依赖。

真实运行证据、限制及原作对照见 [阶段报告](../../docs/review/Career-Nebula-P1-A.md)。视觉仍待用户验收，不能以构建或自动检查通过宣称美术完成。
