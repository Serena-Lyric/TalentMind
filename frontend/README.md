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

## Career Nebula 开发期对照（Issue #22）

默认仍为原版 legacy。需要审查关系布局时，完整刷新 `http://127.0.0.1:18080/?nebula=experimental#/graph`（独立 worktree 服务可改用 18081）；参数放在 hash 前。删除 `nebula=experimental` 后刷新即可回退，无新增永久工具栏。

实验版复用已有 d3-force 固定迭代，按真实关联安排岗位/技能/场景；共享节点考虑全部关联岗位。初次/重置按实际面板与完整节点范围fit，远景降低节点尺寸、标签和阴影，放大恢复。搜索旁前后按钮及序号切换多结果；Enter下一项、Shift+Enter上一项，首项精确优先，关键词/筛选/刷新重置游标。

普通连线按远/中/普通120/300/900预算优先较近真实边；技能实线、场景点线、岗位相关虚线使用原色板。选中展示全部可见直连并突出，scale >= 1.8 补全当前视口内关系。顶部仍为真实总关系；`nebulaDebug=1` 可读根节点 `data-nebula` 中候选/最终绘制/直连及fit结果，无新增可见统计项。详见[第二轮报告](../docs/review/M3-M5-issue-22-round2.md)。

`pnpm test` 使用 Node 内置 TypeScript stripping（本轮验证 Node 24.15.0），无需新增测试框架；`pnpm run build` 执行类型检查与构建。只读固定 API 快照可运行 `node --experimental-strip-types scripts/check-nebula.ts <graph-api.json>`；检查器不连接服务或写文件。测试与检查均不写数据库。首次布局计算仍在主线程，完整图全景较密集，最终视觉效果待用户验收。
