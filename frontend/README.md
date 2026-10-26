# frontend — TalentMind 前端（M5）

真实 JD 隔离候选通过 `M3_REAL_PREVIEW_DIR=<私有bundle>` 启动 localhost Vite，并显式打开 `?graphDataset=real#/graph`。原始来源和五态保持可回溯，普通构建不携带私有数据；不带参数仍为历史 P2.5。完整运行命令、真实浏览器证据及限制见[链路交付](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/M1-M5-real-jd-e2e.md)。

TalentMind 的唯一正式前端，采用 Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia。

## 页面

- 岗位分析工作台：独立 `/#/m2`，历史 JD 有界选择、冻结与显式启动、四阶段进度、停止/恢复/版本重放、逐条证据及历史报告。后端严格本地门禁，演示登录不代表生产授权；仅写隔离 SQLite。四阶段完成不是准确率，B1 未决和 B3 未发布状态明确保留；见[交付报告](../docs/review/M2-product-2026-10-21.md)。

- 数据概览：真实岗位、简历、技能和 signal 趋势
- JD 岗位管理：岗位列表、详情、导入、新增、编辑、删除
- 采集图谱：真实 Neo4j 图谱的 Career Nebula 星云视图，支持搜索、筛选、缩放、拖拽和节点高亮
- 数据分析：真实趋势和技能统计；无可信数据时展示空态
- 采集模块管理：单轮及多关键词×多城市批次；先创建计划，再显式串行开始/统一停止，逐项状态/原因/精确日志与原文复用；平台城市独立、未知计数诚实、持续入口仍禁用。使用根目录统一启动入口，见[集成验收](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/Product-integration-2026-10-21.md)与[批次验证](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/Collection-batches-2026-10-21.md)。
- 能力动态更新：读取 `job_change_log`，无记录时展示空态
- BOSS普通浏览器人工采集：采集控制台“普通浏览器”创建单页有界任务，由用户在普通Edge手动打开本轮列表和详情，再点击扩展读取；无自动平台访问或CDP重试。先列表后详情，验证或数据库故障结束会话，字段迁移须单独许可。扩展及安装步骤见[说明](bridge-extension/README.md)，离线验证与实机待验收边界见[分平台修复报告](../docs/review/M1-platform-repair-2026-10-22.md)。
- 简历分析 / 预览：上传解析、自动多岗位推荐和最近一次内存态结果预览，学习路径绑定所点击的推荐岗位
- 技能学习路径：基于岗位技能目录、JD 原文证据与当前简历命中生成确定性缺口与「基础→核心→专项→加分」分层分步路径，阶段内逐技能有序展示，并给出针对性改进建议（含类别/别名/同类别简历衔接），不虚构课程、时长或资源链接

## 启动

### 节点引导空间（2026-10-22 默认启用；原 2026-10-20 #37 候选）

普通菜单 `/#/graph` 默认启用 `node-field-v1`：星尘分布响应知识节点总体密度，并保留基础旋臂；`/?graphSpace=node-field-v1#/graph` 显式指定同一版本，`/?graphSpace=legacy#/graph` 回退原 P2.5 空间。固定相机、受控对照和旧 Canvas 入口保持原行为；节点坐标与星体语义不变，窗口 resize/相机操作不重采样。原候选的版本、统计和截图见[空间场报告](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/M3-node-guided-galaxy-field.md)，其中“省略参数回退旧版”为当时状态，已由本次用户授权替代；该报告的历史验收范围不因默认切换扩大。

复现历史空间统计：在 `frontend` 执行 `node --experimental-strip-types scripts/measureGalaxyField.ts`。可追加显式只读layout路径；仅输出聚合空间指标/摘要，不输出节点身份或JD原文。

### P2.4 恒星与交互（2026-10-19，PR35追加候选）

正式 `/#/graph` 新增四类程序化星体与独立装饰过渡，默认无线；选中显示真实直连且保留非邻居。类型标识、恒星色温与业务统计各自独立。技术信息可切换外观预设；“定位全部关联”与“近距离观察”是主动镜头操作。测试/实际截图/222原边/开销见[P2.4报告](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/M3-M5-P2-4.md)。`/?graphStars=p23#/graph` 回退星点外观并保留新交互；精确P2.3见提交33b2142。以下历史段落保留各自版本语境。

### P2.3 三维知识银河（2026-10-19，独立Draft候选）

当前候选 `/#/graph` 默认中心环绕三维：左拖旋转、右拖/WASD屏幕平移、Q/E滚转、滚轮缩放、R恢复。控制器基础相机与滚转显示相机分离；知识星体、原边、标签和拾取共享投影，原历史快照和来源索引保持。展示深度不代表语义距离，历史岗位未自动分八类。完整运行、80项前端测试、配对性能和实机限制见 [P2.3报告](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/M3-M5-P2-3.md)。

回退 `/?graphCamera=fixed&graphVisual=p22#/graph`、`/?graphCamera=fixed&graphVisual=p21#/graph`、`/#/graph?graphRenderer=legacy`。下列P2.2/P2.1段落保留当时实现语境；最终产品验收仍待独立审核和用户确认。

### P2.2 星体与关系可读性修订（PR33追加，待视觉验收）

默认正式 `/#/graph` 已使用修订版星体、逐边关系对账、独立原边曲线/高亮和标签避让。历史Industry只称旧场景投影，社区说明折叠、派生相似默认关闭。原输入/布局不变；三方真实截图、性能成本与遗留见 [P2.2报告](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/M3-M5-P2-2.md)。

P2.1视觉回退为 `/?graphVisual=p21#/graph`，旧Canvas仍为 `/#/graph?graphRenderer=legacy`。受控比较使用 `/?graphVisual=p1a2|p21|p22&graphCompare=overview|middle|near#/graph`（分别选一个值），统一输入/布局/固定投影并冻结时钟；p1a2只回放原知识点shader，不冒充原独立站相机。全景重绘成本仍高于P2.1，不以帧间隔采样宣称全面性能提升。

### M3/M5-P2.1 集成候选（2026-10-19，待独立审核）

正式 Vue `/graph` 默认使用银河候选；现有 Hash Router 的地址为 `/#/graph`，旧 Canvas 回退为 `/#/graph?graphRenderer=legacy`。导航和原演示登录保持；后者仅前端演示校验。候选从唯一 `exchange/m3/graph.json` 读取已核验历史交接快照（7845/11412），不访问实时数据库、不混入未发布标准岗位。Vite只在构建输出复制该文件；源码不重复存放快照。

预计算候选、版本绑定、共享技能/孤点层级、完整邻接分页、测试及截图/录屏见 [集成报告](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/review/M3-M5-P2-1.md)。Jaccard0.10/Leiden及固定投影视觉尚未定稿。运行需localhost或HTTPS，普通局域网HTTP不跳过摘要校验。`pnpm test` 运行前端定向与#28交互回归，`pnpm run build` 包含类型检查。

```powershell
pnpm install --frozen-lockfile
pnpm run dev
```

开发端口为 `18080`，默认将 `/api` 代理到 `http://127.0.0.1:18000`，可通过 `VITE_PROXY_TARGET` 覆盖；可通过 `VITE_API_BASE_URL` 覆盖请求基址。

## 约束

- 所有业务请求使用统一 `/api` 和 `{code: 0, message, data}` 响应；`request.ts` 负责解包。
- 正式前端不读取 `input/`、`public/data/` 或本地 Mock 数据。
- 图谱和采集控制台使用后端 API；`Collection.vue` 的平台统计仍有历史回退值，接口缺项时不能据此认定为实时数据。采集模块管理页的采集任务需**手动启动**（2026-09-03 起停用进入页面自动采集：不再自动准备 Edge/自动尝试单轮），系统不自动登录或绕过验证。
- 简历推荐展示分仍包含演示口径：低于 90 的真实 `raw_score` 会映射为随机的 90–100 展示分；展示分及 `parseQuality` 不能作为实测准确率。相关源码本轮未改。
- `pnpm run build` 同时执行 `vue-tsc --noEmit` 和 Vite 构建。
