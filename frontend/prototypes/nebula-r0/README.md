# Career Nebula R0：可丢弃的对照原型

Issue #24 的独立 Vue 3 实验入口。A 使用 Canvas 2D；B 使用延迟加载的 Three.js / WebGL2。两者使用同一份真实交接快照衍生的中立空间协议，不接入正式路由、生产 API 或数据库。正式 M5 仍按原入口运行；本目录不是最终图谱集成方案。

## 复现

在仓库根目录（PowerShell，Python 3.14.5 / Node 24.15.0 / pnpm 11.5.1 为本轮实测环境）：

```powershell
python -m venv data/local/issue-24-r0-env
.\data\local\issue-24-r0-env\Scripts\python.exe -m pip install -r frontend/prototypes/nebula-r0/requirements-research.txt
.\data\local\issue-24-r0-env\Scripts\python.exe scripts/nebula_r0.py
.\data\local\issue-24-r0-env\Scripts\python.exe -m unittest discover -s scripts/tests -p test_nebula_r0.py
Set-Location frontend/prototypes/nebula-r0
pnpm install --frozen-lockfile
pnpm test
pnpm run build
pnpm dev
```

- A：<http://127.0.0.1:18082/?route=a>
- B：<http://127.0.0.1:18082/?route=b>
- 本目录有独立 `pnpm-workspace.yaml/package.json/pnpm-lock.yaml`，依赖不进入正式前端包。只绑定本机回环地址；端口占用直接失败。
- `public/data.json` 是可重建输出，Git 忽略；构建前必须生成。输入固定为仓库 `exchange/m3/graph.json`，不调用旧 builder、不导入数据库。分析报告另存 `docs/review/issue-24-r0-analysis.json`。
- 数据和布局指纹见生成结果与页面“导出审计”。重复输入、固定参数与固定依赖版本重现相同坐标；跨版本/平台不承诺浮点字节一致。

## 空间协议与交互

每个真实节点保留 `nodeId, type, communityId, communityMembership, xyz, importance, visibleLevel, label, properties`。`properties` 是原节点原样副本。边保留 source/target/type 与原 properties；原快照没有边 ID，`snapshot:序号` 由端点和类型稳定排序生成，结合 sourceSha256 与原关系三元组反查，不是 Neo4j 的 relationship ID。

群落是技能二部图投影的算法推断；C 编号不等于正式职业类别。共享实体保留全部群落邻接计数，颜色仅取最多邻接岗位的群落，平票按 C 编号。叶子角度、深度、星尘和雾光是视觉排布，没有新增知识关系。装饰粒子走独立渲染层，无 ID、无命中，不计入实体统计；可关闭。

默认颜色=推断群落，形状=类型（◇岗位、○技能、□场景）。可切换颜色=类型（蓝/绿/紫）；背景雾色仍表示群落，页面明确说明。超过八群后颜色循环，C 编号区分；没有随机配色。

全景显示岗位；相对全览 1.6× 展开共享技能/场景；3.5× 展开全部实体。选中和搜索结果例外保留；默认节点核心半径不超过 6 CSS px（可改 5/8 px），标签按优先级碰撞避让，详情保留完整名称。

单击、清空、关闭详情均原位。搜索 Enter/Shift+Enter 与前后按钮切换，精确命中优先，仅在目标离屏时平移。搜索列表点击只选中；“定位下一结果”执行定位。选中提交全部过滤后真实直连，视口外有计数；主动“查看全部关联”才 fit，“返回原视角”恢复。B 默认正面正交相机；显式打开旋转后拖拽才改变 yaw/pitch。

支持保存画布、导出当前原始属性/直连与耗时 JSON、MediaRecorder 画布短录屏。截图/录屏工具导出画布层，完整页面截图另见阶段报告。

## 限制与恢复

- 按桌面 1440×900 对照；窄屏不是本轮验收对象。WebGL2 初始化失败会提示，手动切 A 恢复；未做 GPU context loss 注入或其他浏览器矩阵测试。
- 开发期简单 CPU 投影与每次重建 BufferAttribute，近景可能顿挫；页面计时为 CPU 绘制/提交耗时，非 GPU 完成时间/连续帧率。没有极限规模承诺。
- 巨量完整直连仍可形成扇形线束；碰撞避让会省略部分普通标签，完整名称和边在详情/审计中可查。尚未做边束化、Bloom 后处理或审美定稿。
- 完整研究报告、真实全景/局部/近景截图、短视频和实测记录见 [R0 阶段报告](../../../docs/review/M3-M5-issue-24-R0.md)。
