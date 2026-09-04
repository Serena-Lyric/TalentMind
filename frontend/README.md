# frontend — TalentMind 前端（M5）

TalentMind 的唯一正式前端，采用 Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia。

## 页面

- 数据概览：真实岗位、简历、技能和 signal 趋势
- JD 岗位管理：岗位列表、详情、导入、新增、编辑、删除
- 采集图谱：真实 Neo4j 图谱的 Career Nebula 星云视图，支持搜索、筛选、缩放、拖拽和节点高亮
- 数据分析：真实趋势和技能统计；无可信数据时展示空态
- 采集模块管理：M1 BOSS 采集任务、CDP、数据库质量和历史任务
- 能力动态更新：读取 `job_change_log`，无记录时展示空态
- 简历分析 / 预览：上传解析、目标岗位匹配和最近一次结果预览
- 技能学习路径：基于岗位技能目录、JD 原文证据与当前简历命中生成确定性缺口与「基础→核心→专项→加分」分层分步路径，阶段内逐技能有序展示，并给出针对性改进建议（含类别/别名/同类别简历衔接），不虚构课程、时长或资源链接

## 启动

```powershell
pnpm install
pnpm run dev
```

开发端口为 `18080`，默认将 `/api` 代理到 `http://127.0.0.1:18000`，可通过 `VITE_PROXY_TARGET` 覆盖；可通过 `VITE_API_BASE_URL` 覆盖请求基址。

## 约束

- 所有业务请求使用统一 `/api` 和 `{code: 0, message, data}` 响应；`request.ts` 负责解包。
- 正式前端不读取 `input/`、`public/data/` 或本地 Mock 数据。
- 图谱和采集控制台分别使用真实后端 API；没有可信数据源的指标不显示演示数字。采集模块管理页的采集任务需**手动启动**（2026-09-03 起停用进入页面自动采集：不再自动准备 Edge/自动尝试单轮），系统不自动登录或绕过验证。
- `pnpm run build` 同时执行 `vue-tsc --noEmit` 和 Vite 构建。