import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import ts from 'typescript'
import * as pinia from 'pinia'

function loadModule(file: string, cache = new Map<string, any>()): any {
  if (cache.has(file)) return cache.get(file)
  const compiled = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} }; cache.set(file, module.exports)
  new Function('require', 'module', 'exports', compiled)((id: string) => id === 'pinia' ? pinia : loadModule(resolve(dirname(file), id + '.ts'), cache), module, module.exports)
  return module.exports
}

test('真实演示账户切换和退出清空简历、推荐、目标并推进会话代数', () => {
  const values = new Map<string, string>()
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage')
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: { getItem: (key: string) => values.get(key), setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) } })
  const active = pinia.createPinia(); pinia.setActivePinia(active)
  const cache = new Map<string, any>()
  const auth = loadModule(resolve(import.meta.dirname, '../src/utils/auth.ts'), cache)
  const store = loadModule(resolve(import.meta.dirname, '../src/store/resume.ts'), cache).useResumeStore()
  try {
    for (const change of [() => auth.setCurrentUser({ username: 'user', label: '演示用户' }), () => auth.clearCurrentUser()]) {
      store.setParsed({ skills: ['Python'] }, { score: 70 }, [{ id: '1' }], 40, 'private.txt')
      store.selectTarget('1', 'version')
      const revision = store.revision
      change()
      assert.equal(store.profile, null); assert.equal(store.matchResult, null); assert.deepEqual(store.recommendedJobs, []); assert.equal(store.learningTarget, null); assert.equal(store.fileName, ''); assert.equal(store.parseQuality, 0)
      assert.ok(store.revision > revision)
    }
  } finally { pinia.setActivePinia(undefined); if (previous) Object.defineProperty(globalThis, 'sessionStorage', previous); else delete (globalThis as any).sessionStorage }
})
