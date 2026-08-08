# 计划 B — 前端(Vue3 + TS 可视化) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现产品展示前端——首页、AI人才能力大脑、岗位地图、能力图谱(G6)、人岗匹配上传页、演化时间轴,对接冻结的后端 API。

**Architecture:** Vite + Vue3 + TS 单页应用;Axios 封装统一 `{code,message,data}` 解析;API 层用 TS 类型镜像后端契约;图谱用 AntV G6,趋势/时间轴用 ECharts;无数据阶段用 Mock 响应先行开发。

**Tech Stack:** Vue3, TypeScript, Vite, Vue Router, Pinia, Axios, @antv/g6, echarts, Element Plus, vitest

**依赖:** 计划 0 冻结的 API 契约(可用 Mock 先行,不阻塞后端)。

## Global Constraints

- API 响应统一 `{code:number, message:string, data:T}`;`code===0` 成功,否则走错误提示
- 业务错误经 body.code 表达(后端一律 HTTP 200);axios 只处理传输层错误
- API base URL 走环境变量 `VITE_API_BASE`(默认 `http://localhost:8000`)
- TS 类型镜像后端 schemas(GraphView/MatchResult 等),契约变更同步更新
- 无后端数据时用 Mock adapter 开发;组件用 vitest 单测
- 每任务 commit

---

## 文件结构(本计划创建)

```
frontend/
  package.json  vite.config.ts  tsconfig.json  .env.example
  src/
    main.ts  App.vue  router.ts
    api/
      http.ts          # axios 封装 + {code,message,data} 解析
      types.ts         # 镜像后端契约的 TS 类型
      jobs.ts graph.ts resume.ts   # 各域 API 调用
    views/
      HomeView.vue
      BrainView.vue        # AI人才能力大脑
      JobMapView.vue       # 岗位地图
      GraphView.vue        # 能力图谱(G6)
      MatchView.vue        # 人岗匹配上传
      EvolutionView.vue    # 演化时间轴
    components/
      GraphCanvas.vue      # G6 封装
      MatchResultCard.vue  # 匹配结果+差距+路径
  tests/
    http.spec.ts
    matchResultCard.spec.ts
```

---

## Task 1: 脚手架 + API 层(http 封装 + 类型)

**Files:**
- Create: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `.env.example`
- Create: `frontend/src/api/http.ts`, `frontend/src/api/types.ts`
- Test: `frontend/tests/http.spec.ts`

**Interfaces:**
- Produces:
  - `request<T>(config): Promise<T>`——解析 `{code,message,data}`,`code!==0` 抛错,成功返回 `data`
  - TS 类型:`SkillItem, MatchResult, GraphView, GraphNode, GraphEdge, EmergingJob`

- [ ] **Step 1: 初始化项目**

Run: `npm create vite@latest frontend -- --template vue-ts && cd frontend && npm install && npm install axios @antv/g6 echarts element-plus pinia vue-router && npm install -D vitest`
Expected: 依赖安装成功,`frontend/` 生成 Vite+Vue-TS 骨架

- [ ] **Step 2: 写 types.ts(镜像后端契约)**

```typescript
// frontend/src/api/types.ts  【镜像后端 schemas.py,契约变更同步】
export interface SkillItem {
  skill_id: number; name: string; weight: number;
  confidence?: number | null; evidence?: string | null;
}
export interface MatchResult {
  target_job: string; score: number;
  matched: string[]; missing: string[];
  path: Array<{ from: string | null; to: string; gap: string[] }>;
}
export interface GraphNode { id: string; label: string; type: string; }
export interface GraphEdge { source: string; target: string; rel: string; weight?: number | null; }
export interface GraphView { nodes: GraphNode[]; edges: GraphEdge[]; }
export interface EmergingJob {
  job_name: string; definition: string; core_skills: string[];
  evolution: { stage: string; growth_rate?: number };
}
export interface ApiEnvelope<T> { code: number; message: string; data: T; }
```

- [ ] **Step 3: 写失败测试**

```typescript
// frontend/tests/http.spec.ts
import { describe, it, expect, vi } from 'vitest';
import { parseEnvelope } from '../src/api/http';

describe('parseEnvelope', () => {
  it('returns data when code=0', () => {
    expect(parseEnvelope({ code: 0, message: 'ok', data: { x: 1 } })).toEqual({ x: 1 });
  });
  it('throws when code!=0', () => {
    expect(() => parseEnvelope({ code: 4100, message: '不支持格式', data: null }))
      .toThrowError('不支持格式');
  });
});
```

- [ ] **Step 4: 运行验证失败**

Run: `cd frontend && npx vitest run tests/http.spec.ts`
Expected: FAIL,无法从 `../src/api/http` 导入 `parseEnvelope`

- [ ] **Step 5: 实现 http.ts**

```typescript
// frontend/src/api/http.ts
import axios from 'axios';
import type { ApiEnvelope } from './types';

const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000',
  timeout: 30000,
});

export function parseEnvelope<T>(env: ApiEnvelope<T>): T {
  if (env.code !== 0) {
    throw new Error(env.message || `请求失败(code=${env.code})`);
  }
  return env.data;
}

export async function request<T>(config: Parameters<typeof instance.request>[0]): Promise<T> {
  const resp = await instance.request<ApiEnvelope<T>>(config);
  return parseEnvelope(resp.data);
}
```

创建 `.env.example`:`VITE_API_BASE=http://localhost:8000`

- [ ] **Step 6: 运行验证通过**

Run: `cd frontend && npx vitest run tests/http.spec.ts`
Expected: PASS(2 passed)

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/.env.example frontend/src/api/ frontend/tests/http.spec.ts
git commit -m "feat(B): scaffold frontend with typed api layer"
```

---

## Task 2: 域 API 调用 + 路由

**Files:**
- Create: `frontend/src/api/jobs.ts`, `graph.ts`, `resume.ts`
- Create: `frontend/src/router.ts`
- Modify: `frontend/src/main.ts`, `frontend/src/App.vue`

**Interfaces:**
- Consumes: `request`, types
- Produces:
  - `getOverview(domain?), getJobTree(name), getSkillPath(from,to)` → GraphView
  - `getEmerging(limit), getEvolution(range)` → EmergingJob[]
  - `analyzeResume(file) → {resume_id,...}`, `matchJob(resumeId, jobId?) → MatchResult`

- [ ] **Step 1: 实现 graph.ts / jobs.ts / resume.ts**

```typescript
// frontend/src/api/graph.ts
import { request } from './http';
import type { GraphView } from './types';
export const getOverview = (domain?: string) =>
  request<GraphView>({ url: '/graph/overview', params: { domain } });
export const getJobTree = (name: string) =>
  request<GraphView>({ url: `/graph/job/${encodeURIComponent(name)}` });
export const getSkillPath = (from: string, to: string) =>
  request<GraphView>({ url: '/graph/skill-path', params: { from, to } });
```

```typescript
// frontend/src/api/jobs.ts
import { request } from './http';
import type { EmergingJob } from './types';
export const getEmerging = (limit = 20) =>
  request<EmergingJob[]>({ url: '/jobs/emerging', params: { limit } });
export const getEvolution = (range = 'all') =>
  request<any[]>({ url: '/jobs/evolution', params: { range } });
```

```typescript
// frontend/src/api/resume.ts
import { request } from './http';
import type { MatchResult, SkillItem } from './types';
export const analyzeResume = (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return request<{ resume_id: number; raw_format: string; skills: SkillItem[] }>(
    { url: '/resume/analyze', method: 'post', data: fd });
};
export const matchJob = (resumeId: number, jobId?: number) =>
  request<MatchResult>({ url: '/match', method: 'post', params: { resume_id: resumeId, job_id: jobId } });
```

- [ ] **Step 2: 配置路由(6 视图)**

```typescript
// frontend/src/router.ts
import { createRouter, createWebHistory } from 'vue-router';
const routes = [
  { path: '/', component: () => import('./views/HomeView.vue') },
  { path: '/brain', component: () => import('./views/BrainView.vue') },
  { path: '/job-map', component: () => import('./views/JobMapView.vue') },
  { path: '/graph', component: () => import('./views/GraphView.vue') },
  { path: '/match', component: () => import('./views/MatchView.vue') },
  { path: '/evolution', component: () => import('./views/EvolutionView.vue') },
];
export default createRouter({ history: createWebHistory(), routes });
```

在 `main.ts` 注册 router/pinia/ElementPlus;`App.vue` 放 `<router-view>` + 导航。为 6 个 view 各建一个最小占位组件(`<template><div>标题</div></template>`),保证路由可跑。

- [ ] **Step 3: 类型检查通过**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/ frontend/src/router.ts frontend/src/main.ts frontend/src/App.vue frontend/src/views/
git commit -m "feat(B): domain api calls and routing with view stubs"
```

---

## Task 3: 能力图谱可视化(G6 封装)

**Files:**
- Create: `frontend/src/components/GraphCanvas.vue`
- Modify: `frontend/src/views/GraphView.vue`

**Interfaces:**
- Consumes: `GraphView` 类型, `getJobTree`/`getOverview`, @antv/g6
- Produces: `GraphCanvas` 组件,props `{ data: GraphView }`,渲染节点/边;按 type 着色

- [ ] **Step 1: 实现 GraphCanvas.vue**

```vue
<!-- frontend/src/components/GraphCanvas.vue -->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { Graph } from '@antv/g6';
import type { GraphView } from '../api/types';

const props = defineProps<{ data: GraphView }>();
const container = ref<HTMLDivElement>();
let graph: Graph | null = null;

const COLOR: Record<string, string> = {
  Domain: '#5B8FF9', JobFamily: '#5AD8A6', Job: '#F6BD16', Skill: '#E86452',
};

function render() {
  if (!container.value) return;
  const nodes = props.data.nodes.map(n => ({ id: n.id, data: { label: n.label },
    style: { fill: COLOR[n.type] || '#999' } }));
  const edges = props.data.edges.map(e => ({ source: e.source, target: e.target }));
  if (graph) graph.destroy();
  graph = new Graph({ container: container.value, data: { nodes, edges },
    layout: { type: 'force' }, behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'] });
  graph.render();
}

onMounted(render);
watch(() => props.data, render, { deep: true });
</script>
<template><div ref="container" style="width:100%;height:600px"></div></template>
```

- [ ] **Step 2: GraphView.vue 加载岗位技能树**

```vue
<!-- frontend/src/views/GraphView.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import GraphCanvas from '../components/GraphCanvas.vue';
import { getJobTree } from '../api/graph';
import type { GraphView as GV } from '../api/types';

const data = ref<GV>({ nodes: [], edges: [] });
const job = ref('AI应用工程师');
async function load() { data.value = await getJobTree(job.value); }
onMounted(load);
</script>
<template>
  <div>
    <input v-model="job" @keyup.enter="load" placeholder="输入岗位名" />
    <GraphCanvas :data="data" />
  </div>
</template>
```

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npx vue-tsc --noEmit && npm run build`
Expected: 类型检查 + 构建通过

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/GraphCanvas.vue frontend/src/views/GraphView.vue
git commit -m "feat(B): G6 graph canvas and job skill tree view"
```

---

## Task 4: 人岗匹配页 + 结果卡片

**Files:**
- Create: `frontend/src/components/MatchResultCard.vue`
- Modify: `frontend/src/views/MatchView.vue`
- Test: `frontend/tests/matchResultCard.spec.ts`

**Interfaces:**
- Consumes: `MatchResult` 类型, `analyzeResume`/`matchJob`
- Produces: `MatchResultCard` props `{ result: MatchResult }`——展示匹配度、已有、缺失、路径

- [ ] **Step 1: 写失败测试(组件渲染)**

```typescript
// frontend/tests/matchResultCard.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MatchResultCard from '../src/components/MatchResultCard.vue';

describe('MatchResultCard', () => {
  it('renders score and missing skills', () => {
    const result = { target_job: 'AI应用工程师', score: 82, matched: ['Python'],
      missing: ['RAG', 'LangChain'], path: [{ from: null, to: 'AI应用工程师', gap: ['RAG'] }] };
    const wrapper = mount(MatchResultCard, { props: { result } });
    expect(wrapper.text()).toContain('82');
    expect(wrapper.text()).toContain('RAG');
    expect(wrapper.text()).toContain('AI应用工程师');
  });
});
```

安装测试依赖:`cd frontend && npm install -D @vue/test-utils happy-dom`,并在 `vite.config.ts` 的 test 配置加 `environment: 'happy-dom'`。

- [ ] **Step 2: 运行验证失败**

Run: `cd frontend && npx vitest run tests/matchResultCard.spec.ts`
Expected: FAIL,无法导入 MatchResultCard

- [ ] **Step 3: 实现 MatchResultCard.vue**

```vue
<!-- frontend/src/components/MatchResultCard.vue -->
<script setup lang="ts">
import type { MatchResult } from '../api/types';
defineProps<{ result: MatchResult }>();
</script>
<template>
  <div class="match-card">
    <h3>目标岗位:{{ result.target_job }}</h3>
    <p class="score">匹配度:{{ result.score }}%</p>
    <div>已有技能:<span v-for="s in result.matched" :key="s">{{ s }} </span></div>
    <div>缺失技能:<span v-for="s in result.missing" :key="s" class="missing">{{ s }} </span></div>
    <div v-for="(step, i) in result.path" :key="i">
      学习路径:{{ step.from ?? '当前' }} → {{ step.to }}(补齐:{{ step.gap.join('、') }})
    </div>
  </div>
</template>
```

- [ ] **Step 4: MatchView.vue 串联上传→匹配**

```vue
<!-- frontend/src/views/MatchView.vue -->
<script setup lang="ts">
import { ref } from 'vue';
import { analyzeResume, matchJob } from '../api/resume';
import MatchResultCard from '../components/MatchResultCard.vue';
import type { MatchResult } from '../api/types';

const result = ref<MatchResult | null>(null);
const error = ref('');
async function onFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  error.value = '';
  try {
    const { resume_id } = await analyzeResume(file);
    result.value = await matchJob(resume_id);
  } catch (err: any) {
    error.value = err.message;   // 后端 code!=0(如不支持格式)在此展示
  }
}
</script>
<template>
  <div>
    <input type="file" accept=".pdf,.docx" @change="onFile" />
    <p v-if="error" class="error">{{ error }}</p>
    <MatchResultCard v-if="result" :result="result" />
  </div>
</template>
```

- [ ] **Step 5: 运行验证通过**

Run: `cd frontend && npx vitest run tests/matchResultCard.spec.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/MatchResultCard.vue frontend/src/views/MatchView.vue frontend/tests/matchResultCard.spec.ts frontend/vite.config.ts frontend/package.json
git commit -m "feat(B): match view with upload and result card"
```

---

## Task 5: 演化时间轴 + 新岗位展示(ECharts)

**Files:**
- Modify: `frontend/src/views/EvolutionView.vue`, `frontend/src/views/BrainView.vue`

**Interfaces:**
- Consumes: `getEvolution`, `getEmerging`, echarts
- Produces: 演化时间轴视图(技能/岗位随时间迁移);新岗位卡片列表

- [ ] **Step 1: 实现 EvolutionView.vue(时间轴)**

```vue
<!-- frontend/src/views/EvolutionView.vue -->
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import * as echarts from 'echarts';
import { getEvolution } from '../api/jobs';

const chart = ref<HTMLDivElement>();
onMounted(async () => {
  const data = await getEvolution('all');
  const inst = echarts.init(chart.value!);
  inst.setOption({
    xAxis: { type: 'category', data: data.map((d: any) => d.first_seen) },
    yAxis: { type: 'category', data: data.map((d: any) => d.job_name) },
    series: [{ type: 'scatter', symbolSize: 20,
      data: data.map((d: any, i: number) => [i, i, d.evolution.stage]) }],
    tooltip: { formatter: (p: any) => `${p.data[2]}` },
  });
});
</script>
<template><div ref="chart" style="width:100%;height:500px"></div></template>
```

> 时间轴只展示后端返回的 stage 与 first_seen,不渲染任何前端编造的数字(DR-2)。growth_rate 仅当后端提供时显示。

- [ ] **Step 2: BrainView.vue 新岗位卡片**

```vue
<!-- frontend/src/views/BrainView.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { getEmerging } from '../api/jobs';
import type { EmergingJob } from '../api/types';
const jobs = ref<EmergingJob[]>([]);
onMounted(async () => { jobs.value = await getEmerging(20); });
</script>
<template>
  <div class="brain">
    <div v-for="j in jobs" :key="j.job_name" class="job-card">
      <h4>{{ j.job_name }} <small>[{{ j.evolution.stage }}]</small></h4>
      <p>{{ j.definition }}</p>
      <span v-for="s in j.core_skills" :key="s">{{ s }} </span>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npx vue-tsc --noEmit && npm run build`
Expected: 通过

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/EvolutionView.vue frontend/src/views/BrainView.vue
git commit -m "feat(B): evolution timeline and emerging jobs view"
```

---

## Task 6: 首页 + 岗位地图 + 全局构建

**Files:**
- Modify: `frontend/src/views/HomeView.vue`, `frontend/src/views/JobMapView.vue`

**Interfaces:**
- Consumes: `getOverview`, GraphCanvas
- Produces: 首页导航;岗位地图(全景图谱 overview)

- [ ] **Step 1: JobMapView.vue 用 overview**

```vue
<!-- frontend/src/views/JobMapView.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import GraphCanvas from '../components/GraphCanvas.vue';
import { getOverview } from '../api/graph';
import type { GraphView as GV } from '../api/types';
const data = ref<GV>({ nodes: [], edges: [] });
onMounted(async () => { data.value = await getOverview(); });
</script>
<template><GraphCanvas :data="data" /></template>
```

- [ ] **Step 2: HomeView.vue 导航首页**

```vue
<!-- frontend/src/views/HomeView.vue -->
<script setup lang="ts">
import { RouterLink } from 'vue-router';
</script>
<template>
  <div class="home">
    <h1>TalentMind 新一代信息技术岗位能力图谱</h1>
    <nav>
      <RouterLink to="/brain">AI人才能力大脑</RouterLink>
      <RouterLink to="/job-map">岗位地图</RouterLink>
      <RouterLink to="/graph">能力图谱</RouterLink>
      <RouterLink to="/match">人岗匹配</RouterLink>
      <RouterLink to="/evolution">动态演化</RouterLink>
    </nav>
  </div>
</template>
```

- [ ] **Step 3: 全局类型检查 + 构建 + 测试**

Run: `cd frontend && npx vue-tsc --noEmit && npm run build && npx vitest run`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/HomeView.vue frontend/src/views/JobMapView.vue
git commit -m "feat(B): home and job map views, full build green"
```

---

## 自审说明
- 覆盖 spec:6 页面(首页/能力大脑/岗位地图/能力图谱/匹配/演化时间轴)✓ G6图谱✓ 差距+路径展示✓ 演化可视化✓
- 类型一致:`types.ts` 镜像计划0 schemas;`MatchResult.path`/`EmergingJob.evolution` 结构与后端一致
- 契约解耦:全部经 `request<T>` 消费统一信封;后端未就绪可用 Mock,不阻塞
- 合规:前端不渲染编造数字,growth_rate 仅后端提供时显示(DR-2)
