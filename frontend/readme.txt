================================================================================
                    岗位能力图谱 - 前端项目说明
================================================================================

一、技术栈
────────────────────────────────────────────────────────────────
  框架：Vue 3.5 + TypeScript
  构建工具：Vite 4.5
  UI 组件库：Element Plus 2.9
  图表库：ECharts 5.6
  图谱库：@antv/g6 5.0
  状态管理：Pinia 2.1
  HTTP 客户端：Axios 1.6
  PDF 导出：jsPDF 2.5 + html2canvas 1.4

二、本地安装与启动
────────────────────────────────────────────────────────────────
  1. 安装依赖（需要 Node.js >= 18）
     npm install

  2. 启动开发服务器（默认 http://localhost:5173）
     npm run dev

  3. 构建生产版本
     npm run build

  4. 预览构建结果
     npm run preview

三、接口配置文件位置
────────────────────────────────────────────────────────────────
  统一封装：src/utils/request.ts
    - axios 实例配置、请求/响应拦截器、统一错误处理
    - 基础地址通过环境变量 VITE_API_BASE_URL 配置，默认 /api

  API 接口层：
    src/api/dashboard.ts   - 数据看板相关接口
    src/api/jobs.ts        - 岗位管理相关接口
    src/api/resume.ts      - 简历上传相关接口
    src/api/graph.ts       - 全景图谱相关接口
    src/api/index.ts       - 统一导出

四、Mock 模拟数据切换说明
────────────────────────────────────────────────────────────────
  配置位置：src/utils/request.ts

  本地开发（使用 Mock 数据）：
    export const USE_MOCK = true

  对接真实后端：
    1. 将 USE_MOCK 改为 false
    2. 将 BASE_URL 改为后端实际地址，如 http://your-server:8080/api
    3. 取消响应拦截器中 code 校验的注释
    4. 取消请求拦截器中 token 附加的注释

  Mock 数据文件位置：
    src/data/mock.js        - 主要业务模拟数据
    src/mock/learning-data.js - 学习路径模拟数据
    src/mock/resume-data.js   - 简历相关模拟数据

五、项目结构
────────────────────────────────────────────────────────────────
  src/
  ├── api/              # API 接口层（按模块拆分）
  ├── components/       # 公共组件
  ├── data/             # Mock 模拟数据
  ├── mock/             # 补充模拟数据
  ├── router/           # 路由配置
  ├── store/            # Pinia 状态管理
  ├── styles.css        # 全局样式
  ├── utils/            # 工具函数（axios 封装等）
  └── views/            # 页面视图
      ├── Dashboard.vue # 数据概览
      ├── Jobs.vue      # 岗位管理
      ├── Graph.vue     # 全景图谱
      ├── Resume.vue    # 简历匹配
      ├── Learning.vue  # 学习路径
      └── ResumeDemo.vue# 简历预览

================================================================================