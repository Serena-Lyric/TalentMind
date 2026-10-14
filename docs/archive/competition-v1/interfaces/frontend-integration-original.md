# 岗位能力图谱 — 前后端对接说明文档

> 本文档供前端与后端开发人员协同使用，明确接口规范、请求/响应格式、数据结构。
> 前端使用 Vue3 + Element Plus + ECharts，后端接口基础路径统一为 `/api`。

---

## 一、基础约定

### 1.1 通用响应格式

所有接口统一返回以下 JSON 格式：

```json
{
  "code": 200,
  "data": { ... },
  "message": "success"
}
```

- `code`：业务状态码，`200` 表示成功
- `data`：业务数据（具体结构见各接口说明）
- `message`：状态描述

### 1.2 错误码约定

| code | 含义 |
|------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 / token 过期 |
| 403 | 无访问权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 1.3 认证方式

请求头统一携带：
```
Authorization: Bearer <token>
```

### 1.4 前端 Mock 切换

前端代码中 `src/utils/request.ts` 有 `USE_MOCK` 开关：
- `true`：使用本地 mock 数据（开发调试）
- `false`：走真实后端接口（联调/上线）

---

## 二、接口清单

### 2.1 统计看板模块

#### GET /api/dashboard/overview

**用途**：获取统计看板概览数据

**请求参数**：无

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "totalJobs": 2468,
    "totalResumes": 8932,
    "matchSuccess": 1847,
    "skillGaps": 376,
    "coralBlocks": [
      { "label": "新增岗位", "value": 28 },
      { "label": "待面试", "value": 24 },
      { "label": "紧急招聘", "value": 4 }
    ]
  }
}
```

---

#### GET /api/dashboard/trend

**用途**：岗位能力趋势折线图数据

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| range | string | 否 | `month`/`quarter`/`year`，默认 `month` |

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "months": ["2月","3月","4月","5月","6月","7月"],
    "series": [
      { "name": "AI算法", "color": "#E07B6D", "data": [82,88,91,95,98,105] },
      { "name": "前端开发", "color": "#A8C5B8", "data": [75,78,82,86,90,94] }
    ]
  }
}
```

---

#### GET /api/dashboard/skill-distribution

**用途**：岗位技能分布柱状图

**请求参数**：无

**响应示例**：
```json
{
  "code": 200,
  "data": [
    { "name": "JavaScript", "count": 320, "percentage": 85 },
    { "name": "Python", "count": 280, "percentage": 74 }
  ]
}
```

---

#### GET /api/dashboard/skill-radar

**用途**：技能雷达图（8维度）

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skillName | string | 是 | 技能名称 |

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "dimensions": ["市场需求","技术热度","岗位覆盖","增长趋势","学习难度","生态成熟","薪资水平","就业广度"],
    "values": [88,92,85,90,65,82,88,80]
  }
}
```

---

#### GET /api/dashboard/industry-tracks

**用途**：行业赛道列表

**请求参数**：无

**响应示例**：
```json
{
  "code": 200,
  "data": [
    { "id": "ai", "name": "人工智能", "color": "#7c5cff", "description": "大模型、算法与智能体应用" }
  ]
}
```

---

### 2.2 岗位管理模块

#### GET /api/jobs

**用途**：岗位列表查询（带筛选 + 分页）

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 搜索关键词（岗位名/公司） |
| city | string | 否 | 城市筛选 |
| track | string | 否 | 赛道筛选 |
| skillStatus | string | 否 | 技能演进状态：新增/淘汰/变更 |
| salaryRange | string | 否 | 薪资区间 |
| startTime | string | 否 | 更新时间起始 |
| endTime | string | 否 | 更新时间截止 |
| page | number | 否 | 页码，默认 1 |
| pageSize | number | 否 | 每页条数，默认 10 |

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "list": [
      {
        "id": "JD-AI-001",
        "title": "Python算法工程师",
        "company": "智云科技",
        "city": "北京",
        "type": "人工智能",
        "salary": "25-40K",
        "status": "进行中",
        "skills": ["Python", "PyTorch", "机器学习", "深度学习"],
        "updated": "2026-07-15",
        "evolution": {
          "added": ["大模型应用"],
          "removed": ["TensorFlow 1.x"],
          "changed": ["Python → Python 工程化"]
        }
      }
    ],
    "total": 2468,
    "page": 1,
    "pageSize": 10
  }
}
```

---

#### GET /api/jobs/:id

**用途**：岗位详情

**响应**：单个 Job 对象（同上）

---

#### POST /api/jobs

**用途**：新增岗位

**请求体**：
```json
{
  "title": "AI提示词工程师",
  "company": "智云科技",
  "city": "深圳",
  "salary": "20-35K",
  "skills": ["Prompt Engineering", "Python", "LLM"]
}
```

**响应**：
```json
{ "code": 200, "data": { "id": "JD-AI-004" } }
```

---

#### PUT /api/jobs/:id

**用途**：编辑岗位

**请求体**：同 POST，字段可选

**响应**：
```json
{ "code": 200, "data": { "success": true } }
```

---

#### DELETE /api/jobs/:id

**用途**：删除岗位

**响应**：
```json
{ "code": 200, "data": { "success": true } }
```

---

#### POST /api/jobs/batch-delete

**用途**：批量删除岗位

**请求体**：
```json
{ "ids": ["JD-AI-001", "JD-AI-002"] }
```

**响应**：
```json
{ "code": 200, "data": { "deleted": 2 } }
```

---

#### POST /api/jobs/import

**用途**：批量导入 JD

**请求类型**：`multipart/form-data`

**字段**：`file` - JD 文件（txt/md/csv）

**响应**：
```json
{ "code": 200, "data": { "imported": 3 } }
```

---

#### GET /api/jobs/export

**用途**：导出岗位 Excel

**请求参数**：`ids`（可选，逗号分隔的岗位 ID）

**响应**：Excel 文件流（Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet）

---

### 2.3 简历匹配模块

#### POST /api/resume/upload

**用途**：上传简历文件解析

**请求类型**：`multipart/form-data`

**字段**：`file` - 简历文件（PDF/DOC/DOCX）

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "profile": {
      "name": "示例求职者（合成）",
      "role": "前端开发工程师",
      "experience": "2026届应届生",
      "education": "本科 · 软件工程",
      "company": "广州应用科技学院",
      "skills": ["HTML", "CSS", "JavaScript", "Vue3", "TypeScript"],
      "summary": "Vue3 项目开发、数据可视化、组件化设计..."
    },
    "matchResult": {
      "score": 82,
      "matched": ["Vue3", "TypeScript", "ECharts", "Vite", "Git"],
      "missing": [
        { "name": "微前端架构", "level": "high", "tip": "大型项目常见的应用拆分与集成方案" }
      ],
      "strengths": ["具备完整的 Vue3 项目经验"]
    }
  }
}
```

---

#### GET /api/resume/skill-dimensions

**用途**：技能维度雷达图

**请求参数**：`targetJob`（目标岗位标识）

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "dimensions": ["基础技能","前端开发框架","组件与工具","跨端开发","全栈开发","技术扩展","AI应用开发能力","综合素养"],
    "jobStandard": [80,85,82,65,70,75,60,80],
    "personalAbility": [85,90,88,60,55,70,65,82]
  }
}
```

---

#### GET /api/resume/target-jobs

**用途**：可选目标岗位列表

**响应示例**：
```json
{
  "code": 200,
  "data": [
    { "value": "frontend", "label": "高级前端工程师", "score": 87 }
  ]
}
```

---

### 2.4 全景图谱模块

#### GET /api/graph/data

**用途**：图谱节点与边数据

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| year | string | 否 | 年份快照，默认当前年 |
| focusJob | string | 否 | 聚焦岗位，`all` 表示全部 |

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "nodes": [
      { "id": "ind-ai", "label": "人工智能", "kind": "industry", "size": 42, "color": "#7c5cff" },
      { "id": "job-ai1", "label": "Python算法工程师", "kind": "job", "size": 28, "color": "#E07B6D", "parent": "ind-ai" },
      { "id": "sk-python", "label": "Python", "kind": "skill", "status": "stable", "size": 26, "color": "#8CA0B8", "jobs": 620, "growth": "+18%" }
    ],
    "edges": [
      { "source": "ind-ai", "target": "job-ai1", "kind": "industry-job" },
      { "source": "job-ai1", "target": "sk-python", "kind": "job-skill" }
    ],
    "stats": { "totalNodes": 33, "totalEdges": 36, "added": 10, "removed": 3, "changed": 2 }
  }
}
```

---

#### GET /api/graph/jobs

**用途**：图谱可选岗位列表

**响应示例**：
```json
{ "code": 200, "data": [{ "value": "all", "label": "全部岗位" }, { "value": "frontend", "label": "前端开发工程师" }] }
```

---

#### GET /api/graph/years

**用途**：可用年份列表

**响应示例**：
```json
{ "code": 200, "data": ["2024","2025","2026"] }
```

---

#### GET /api/graph/skill-radar

**用途**：图谱节点技能雷达图

**请求参数**：`nodeName`（节点名称）

**响应示例**：
```json
{
  "code": 200,
  "data": {
    "dimensions": ["市场需求","技术热度","岗位覆盖","增长趋势","学习难度","生态成熟","薪资水平","就业广度"],
    "values": [88,92,85,90,65,82,88,80]
  }
}
```

---

## 三、前端代码结构说明

```
src/
├── utils/
│   └── request.ts          # axios 封装（拦截器、错误处理）
├── api/
│   ├── index.ts            # 统一出口
│   ├── dashboard.ts        # 统计看板接口
│   ├── jobs.ts             # 岗位管理接口
│   ├── resume.ts           # 简历匹配接口
│   └── graph.ts            # 全景图谱接口
├── views/
│   ├── Dashboard.vue       # 数据概览页
│   ├── Jobs.vue            # 岗位管理页
│   ├── Graph.vue           # 全景图谱页
│   ├── Resume.vue          # 简历匹配页
│   └── Learning.vue        # 学习路径页
├── data/
│   └── mock.js             # 本地 mock 数据
├── store/
│   └── index.ts            # Pinia 状态管理
└── router/
    └── index.ts            # 路由配置
```

### 切换真实后端步骤

1. 打开 `src/utils/request.ts`
2. 将 `export const USE_MOCK = true` 改为 `export const USE_MOCK = false`
3. 将 `BASE_URL` 改为后端实际地址，如 `http://your-server:8080/api`
4. 取消响应拦截器中 `data.code !== 200` 校验的注释
5. 取消请求拦截器中 token 附加的注释

---

## 四、后端开发注意事项

1. 所有接口统一 `/api` 前缀
2. 文件上传接口使用 `multipart/form-data`
3. Excel 导出返回 `Blob` 流
4. 分页接口统一返回 `{ list, total, page, pageSize }` 结构
5. 图谱数据 `nodes` 中 `kind` 字段必须为 `industry`/`job`/`skill` 三选一
6. 日期格式统一使用 `YYYY-MM-DD`