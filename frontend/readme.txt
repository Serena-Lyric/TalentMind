TalentMind 正式前端说明

安装与启动：
1. cd frontend
2. pnpm install
3. pnpm run dev

正式前端默认通过 /api 代理到本机后端，当前不使用本地 Mock 数据。页面数据来源和字段以正式后端 API、backend/app/contracts/ddl.sql 及项目决策记录为准。

页面：数据概览、JD岗位管理、全景能力图谱、简历解析匹配、技能学习路径、简历预览。

当前空态：学习路径需要 M4 pathfinder；简历预览需要先完成一次简历解析。空态不使用伪造数据。

构建：pnpm run build（包含 vue-tsc 类型检查）。
