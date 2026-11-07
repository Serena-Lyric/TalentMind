import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse, compileScript } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

function component(name: string, api: Record<string, any>) {
  const store = vue.reactive<any>({ revision: 0, learningTarget: null, profile: { skills: [] }, matchResult: { target_job_id: '1' }, recommendedJobs: [{ id: '1', requirements_version: 'v1' }, { id: '2', requirements_version: 'v2' }], parseQuality: 0, fileName: 'old.txt',
    setParsed(profile: any, matchResult: any, recommendedJobs: any[], parseQuality: number, fileName: string) { Object.assign(this, { profile, matchResult, recommendedJobs, parseQuality, fileName }) },
    selectTarget(id: string, requirements_version: string) { this.learningTarget = { id, requirements_version } },
    clear() { this.revision++; this.learningTarget = null; this.profile = null; this.matchResult = null; this.recommendedJobs = []; this.fileName = '' },
  })
  const route = vue.reactive({ query: { job_id: '1' } })
  const mounted: Function[] = [], unmounted: Function[] = []
  const messages: string[] = []
  const source = readFileSync(resolve(import.meta.dirname, `../src/${name === 'ResumeDemo' ? 'views' : 'components'}/${name}.vue`), 'utf8')
  const compiled = compileScript(parse(source).descriptor, { id: 'resume-learning-test' }).content
  const code = ts.transpileModule(compiled, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as any }
  const require = (id: string) => {
    if (id === 'vue') return { ...vue, onMounted: (fn: Function) => mounted.push(fn), onUnmounted: (fn: Function) => unmounted.push(fn) }
    if (id === 'vue-router') return { useRoute: () => route, useRouter: () => ({ push() {}, replace(value: any) { Object.assign(route.query, value.query) } }) }
    if (id === '../store/resume') return { useResumeStore: () => store }
    if (id.startsWith('../api/')) return { getLearningJobs: async () => [], ...api }
    if (id === 'element-plus') return { ElMessage: { success: (s: string) => messages.push(s), error: (s: string) => messages.push(s) } }
    if (id === '@element-plus/icons-vue') return {}
    throw new Error(id)
  }
  new Function('require', 'module', 'exports', code)(require, module, module.exports)
  const scope = vue.effectScope()
  const state = scope.run(() => module.exports.default.setup({}, { expose() {} }))
  return { state, route, store, messages, mounted: () => Promise.all(mounted.map(fn => fn())), stop() { unmounted.forEach(fn => fn()); scope.stop() } }
}

const tick = async () => { await vue.nextTick(); await Promise.resolve(); await Promise.resolve() }

test('已解析但技能为空的简历仍能生成路径', async () => {
  let calls = 0
  const page = component('LearningRoadmap', { generateLearningPath: async () => { calls++; return { job_id: '1' } } })
  try { await page.mounted(); await tick(); assert.equal(calls, 1); assert.equal(page.state.hasResume.value, true) } finally { page.stop() }
})

test('切换岗位只接受最新路径，清空简历立即清空结果', async () => {
  const pending: { job: string; resolve: Function }[] = []
  const page = component('LearningRoadmap', { generateLearningPath: ({ job_id }: any) => new Promise(resolve => pending.push({ job: job_id, resolve })) })
  try {
    page.store.profile = { skills: ['python'] }
    void page.mounted(); await tick()
    page.route.query.job_id = '2'; await tick()
    const newer = pending.find(p => p.job === '2')
    assert.ok(newer)
    newer.resolve({ job_id: '2' }); await tick()
    for (const old of pending.filter(p => p.job === '1')) old.resolve({ job_id: '1' })
    await tick(); assert.equal(page.state.path.value.job_id, '2')
    page.store.clear(); await tick(); assert.equal(page.state.path.value, null)
  } finally { page.stop() }
})

test('生成失败显示可重试错误，不永久显示正在生成', async () => {
  const page = component('LearningRoadmap', { generateLearningPath: async () => { throw new Error('请求失败') } })
  try { page.store.profile = { skills: ['python'] }; await page.mounted(); await tick(); assert.ok(page.state.error.value); assert.equal(page.state.generating.value, false) } finally { page.stop() }
})

test('路由中的非推荐岗位不能复用简历生成路径', async () => {
  let calls = 0
  const page = component('LearningRoadmap', { generateLearningPath: async () => { calls++; return {} } })
  try { await page.mounted(); await tick(); calls = 0; page.route.query.job_id = '999'; await tick(); assert.equal(calls, 0); assert.equal(page.state.path.value, null); assert.ok(page.state.error.value) } finally { page.stop() }
})

test('较早上传迟到不覆盖新文件，失败保持原文件名', async () => {
  const pending: { resolve: Function; reject: Function }[] = []
  const page = component('ResumeDiagnosis', { uploadResume: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) })
  try {
    await page.mounted()
    const first = page.state.handleFile(new File(['one'], 'one.txt'))
    const second = page.state.handleFile(new File(['two'], 'two.txt'))
    pending[1].resolve({ profile: { name: 'two', skills: [] }, parseQuality: 0 }); await second
    pending[0].resolve({ profile: { name: 'one', skills: [] } }); await first
    assert.equal(page.store.profile.name, 'two'); assert.equal(page.store.fileName, 'two.txt'); assert.equal(page.store.parseQuality, 0)
    const failed = page.state.handleFile(new File(['bad'], 'bad.txt')); pending[2].reject(new Error('bad')); await failed
    assert.equal(page.state.fileName.value, 'two.txt')
  } finally { page.stop() }
})

test('重置后迟到上传不能恢复已清除的简历', async () => {
  let finish!: Function
  const page = component('ResumeDiagnosis', { uploadResume: () => new Promise(resolve => { finish = resolve }) })
  try {
    const upload = page.state.handleFile(new File(['one'], 'one.txt'))
    page.state.resetDiagnosis(); finish({ profile: { skills: ['python'] } }); await upload
    assert.equal(page.store.profile, null); assert.equal(page.state.parsed.value, false)
  } finally { page.stop() }
})

test('预览保留多段教育和工作经历，不捏造技能分', () => {
  const page = component('ResumeDemo', {})
  try {
    page.store.profile = { skills: ['python'], education_history: [{ school: '学校甲', degree: '本科' }, { school: '学校乙', degree: '硕士' }], work_experience: [{ company: '演示公司', description: ['负责测试'] }] }
    assert.equal(page.state.resume.value.education.length, 2)
    assert.equal(page.state.resume.value.works[0].company, '演示公司')
    assert.equal(page.state.resume.value.skills.details['已识别技能'].level, undefined)
  } finally { page.stop() }
})

for (const reject of [false, true]) {
  test(`上传组件卸载后迟到${reject ? '失败' : '成功'}不写回状态、存储或消息`, async () => {
    let settle!: Function
    const page = component('ResumeDiagnosis', { uploadResume: () => new Promise((resolve, fail) => { settle = reject ? fail : resolve }) })
    await page.mounted()
    const upload = page.state.handleFile(new File(['one'], 'one.txt'))
    page.stop()
    const before = JSON.stringify({ store: page.store, parsed: page.state.parsed.value, uploading: page.state.uploading.value, file: page.state.fileName.value, messages: page.messages })
    settle(reject ? new Error('late') : { profile: { name: 'late', skills: ['python'] } })
    await upload
    assert.equal(JSON.stringify({ store: page.store, parsed: page.state.parsed.value, uploading: page.state.uploading.value, file: page.state.fileName.value, messages: page.messages }), before)
  })

  test(`学习路径卸载后迟到${reject ? '失败' : '成功'}不写回状态或消息`, async () => {
    let settle!: Function
    const page = component('LearningRoadmap', { generateLearningPath: () => new Promise((resolve, fail) => { settle = reject ? fail : resolve }) })
    await tick()
    page.stop()
    const before = JSON.stringify({ path: page.state.path.value, error: page.state.error.value, generating: page.state.generating.value, messages: page.messages })
    settle(reject ? new Error('late') : { job_id: '1' })
    await tick()
    assert.equal(JSON.stringify({ path: page.state.path.value, error: page.state.error.value, generating: page.state.generating.value, messages: page.messages }), before)
  })
}

test('未点选目标不会从匹配第一名自动生成路径', async () => {
  let calls = 0
  const page = component('LearningRoadmap', { generateLearningPath: async () => { calls++; return {} } })
  try { await tick(); calls = 0; delete (page.route.query as any).job_id; await tick(); assert.equal(calls, 0); assert.equal(page.state.selectedJobId.value, '') } finally { page.stop() }
})

test('全目录显式选择推荐外画像后携带版本生成', async () => {
  const requests: any[] = []
  const page = component('LearningRoadmap', {
    getLearningJobs: async () => [{ value: '9', label: 'Other', requirements_version: 'v9', source: [] }],
    generateLearningPath: async (request: any) => { requests.push(request); return { job_id: request.job_id, score: 20, requirements_version: request.requirements_version } },
  })
  try { await page.mounted(); await tick(); await page.state.chooseTarget('9'); await tick(); assert.equal(requests.at(-1).requirements_version, 'v9'); assert.equal(page.state.path.value.job_id, '9') } finally { page.stop() }
})

test('会话清除时组件仍挂载也不能接收旧上传', async () => {
  let finish!: Function
  const page = component('ResumeDiagnosis', { uploadResume: () => new Promise(resolve => { finish = resolve }) })
  try { const upload = page.state.handleFile(new File(['one'], 'one.txt')); page.store.clear(); finish({ profile: { name: 'late', skills: [] } }); await upload; assert.equal(page.store.profile, null); assert.equal(page.state.parsed.value, false) } finally { page.stop() }
})

for (const transition of ['unmount', 'new-session']) {
  test(`重算等待目录时${transition}使旧目标和导航失效`, async () => {
    let finish!: Function
    const page = component('LearningRoadmap', {
      getLearningJobs: () => new Promise(resolve => { finish = resolve }),
      generateLearningPath: async () => ({ job_id: '1' }),
    })
    try {
      page.state.eligibleJobs.value = [{ value: '1', label: 'Old', requirements_version: 'old', source: [] }]
      await tick()
      const recomputing = page.state.recomputeCurrent()
      if (transition === 'unmount') page.stop()
      else { page.store.clear(); page.store.profile = { skills: ['Java'] }; page.store.recommendedJobs = [{ id: '1', requirements_version: 'new-session' }] }
      finish([{ value: '1', label: 'Late', requirements_version: 'late', source: [] }]); await recomputing
      assert.equal(page.store.learningTarget, null)
    } finally { page.stop() }
  })
}
