import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { graphComponent } from './helpers/graphComponent.ts'

const node = (id: string, x: number, y: number, kind = 'skill') => ({ id, label: id, kind, size: 12, color: '', point: { x, y } })
const click = (x: number, y: number) => ({ clientX: x, clientY: y })

test('单击节点、空白与关闭详情保持相机；resize 不因已选中而 fit', async t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  app.setGraph([node('python', 0, 0), node('far', 3000, 0, 'job')], [{source:'python',target:'far',kind:'requires'}])
  Object.assign(s.transform, { x: 10, y: 20, scale: .8 })
  const before = { ...s.transform }
  await s.onCanvasClick(click(608, 416))
  assert.equal(s.selectedNode.value.id, 'python')
  assert.deepEqual({ ...s.transform }, before)
  s.resizeCanvas()
  assert.deepEqual({ ...s.transform }, before)
  s.clearSelection()
  assert.equal(s.selectedNode.value, null)
  assert.deepEqual({ ...s.transform }, before)
  await s.onCanvasClick(click(608, 416))
  await s.onCanvasClick(click(10, 10))
  assert.equal(s.selectedNode.value, null)
  assert.deepEqual({ ...s.transform }, before)
})

test('主动完整邻域 fit 和返回精确往返，重复查看不覆盖原相机，重置清除返回', async t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  app.setGraph([node('python', 0, 0), node('far', 3000, 0, 'job')], [{source:'python',target:'far',kind:'requires'}])
  await s.onCanvasClick(click(600, 400))
  const before = { ...s.transform }
  assert.equal(typeof s.viewAllConnections, 'function')
  await s.viewAllConnections()
  assert.notDeepEqual({ ...s.transform }, before)
  assert.equal(app.debug().lastFit.points, 2)
  assert.equal(app.debug().lastFit.outside, 0)
  await s.viewAllConnections()
  s.returnToView()
  assert.deepEqual({ ...s.transform }, before)
  assert.equal(s.savedView.value, null)
  await s.viewAllConnections()
  await s.resetView()
  assert.equal(s.savedView.value, null)
})

test('搜索仅平移离开有效区域的目标，保留比例；连续切换不 fit 邻居', async t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  app.setGraph([node('python', 0, 0), node('python-other', 2000, 0), node('neighbor', 1e6, 0, 'job')], [{source:'python',target:'neighbor',kind:'requires'}])
  s.searchKeyword.value = 'python'; await nextTick()
  const before = { ...s.transform }
  await s.stepSearch(1)
  assert.deepEqual({ ...s.transform }, before)
  assert.equal(s.searchIndex.value, 0)
  await s.stepSearch(1)
  assert.equal(s.transform.scale, 1)
  assert.equal(s.searchIndex.value, 1)
  assert.equal(s.transform.x, -2000)
})
