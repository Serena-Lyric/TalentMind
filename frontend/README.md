# frontend — TalentMind 前端（M5）

岗位能力图谱前端（原 `岗位能力图谱-前端源码/`，2026-08-13 迁入，D26）。

- 技术栈：Vue 3.5 + TypeScript + Vite 4.5 + Element Plus + ECharts + @antv/g6 + Pinia + Axios
- 页面：Dashboard（数据概览）/ Jobs（JD岗位管理）/ Graph（全景知识图谱）/ Resume（简历匹配）/ Learning（学习路径）/ ResumeDemo（简历预览），共 6 页（D26 保留）
- 接口：20 个，见 `前后端接口对接文档.md`；统一响应 `{code:0, message, data}`（D29）；当前正式前端不使用本地 mock。
- 启动：`pnpm install && pnpm run dev`（Node >= 18）；默认通过 `/api` 代理到 `127.0.0.1:8000`，也可用 `VITE_API_BASE_URL` 指向其他后端地址。
- 图谱：`GraphPanorama.vue` 提供力导向、树状、环形、桑基和星云视图，数据来自正式 `/api/graph/data`，不直接读取 `input/` 图谱快照。
- 详细说明：`readme.txt`（安装/启动/接口配置）