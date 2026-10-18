# frontend — TalentMind 前端（M5）

TalentMind 的唯一正式前端，采用 Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia。

## 页面

- 数据概览：真实岗位、简历、技能和 signal 趋势
- JD 岗位管理：岗位列表、详情、导入、新增、编辑、删除
- 采集图谱：真实 Neo4j 图谱的 Career Nebula 星云视图，支持搜索、筛选、缩放、拖拽和节点高亮
- 数据分析：真实趋势和技能统计；无可信数据时展示空态
- 采集模块管理：M1 BOSS/智联/猎聘采集任务、CDP、数据库质量和历史任务；LinkedIn/Hacker News 为展示项，未接启动任务
- 能力动态更新：读取 `job_change_log`，无记录时展示空态
- 简历分析 / 预览：上传解析、自动多岗位推荐和最近一次内存态结果预览，学习路径绑定所点击的推荐岗位
- 技能学习路径：基于岗位技能目录、JD 原文证据与当前简历命中生成确定性缺口与「基础→核心→专项→加分」分层分步路径，阶段内逐技能有序展示，并给出针对性改进建议（含类别/别名/同类别简历衔接），不虚构课程、时长或资源链接

## 启动

### M3/M5-P2.1 集成候选（2026-10-19，待独立审核）

正式 Vue `/graph` 默认使用银河候选；现有 Hash Router 的地址为 `/#/graph`，旧 Canvas 回退为 `/#/graph?graphRenderer=legacy`。导航和原演示登录保持；后者仅前端演示校验。候选从唯一 `exchange/m3/graph.json` 读取已核验历史交接快照（7845/11412），不访问实时数据库、不混入未发布标准岗位。Vite只在构建输出复制该文件；源码不重复存放快照。

预计算候选、版本绑定、共享技能/孤点层级、完整邻接分页、测试及截图/录屏见 [集成报告](../docs/review/M3-M5-P2-1.md)。Jaccard0.10/Leiden及固定投影视觉尚未定稿。运行需localhost或HTTPS，普通局域网HTTP不跳过摘要校验。`pnpm test` 运行前端定向与#28交互回归，`pnpm run build` 包含类型检查。

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
