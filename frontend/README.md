# frontend — TalentMind 前端（M5）

岗位能力图谱前端（原 `岗位能力图谱-前端源码/`，2026-08-13 迁入，D26）。

- 技术栈：Vue 3.5 + TypeScript + Vite 4.5 + Element Plus + ECharts + @antv/g6 + Pinia + Axios
- 页面：Dashboard（数据概览）/ Jobs（JD岗位管理）/ Graph（全景知识图谱）/ Resume（简历匹配）/ Learning（学习路径）/ ResumeDemo（简历预览），共 6 页（D26 保留）
- 接口：20 个，见 `前后端接口对接文档.md`；统一响应 `{code:0, message, data}`（D29）；开发期 `src/utils/request.ts` 中 `USE_MOCK=true`
- 启动：`npm install && npm run dev`（Node >= 18）；对接真实后端：改 `VITE_API_BASE_URL` 并置 `USE_MOCK=false`
- 详细说明：`readme.txt`（安装/启动/Mock 切换）