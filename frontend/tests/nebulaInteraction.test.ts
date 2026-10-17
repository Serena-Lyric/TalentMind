import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, watch } from 'vue'
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

test('真实绘制路径随缩放展示三类型标签，远景仅悬停目标显示并在离开时清除', t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  app.setGraph([node('job1', -200, 0, 'job'), node('skill1', 0, 0), node('industry1', 200, 0, 'industry')], [])
  s.transform.scale = 1.25; s.draw()
  assert.deepEqual([...app.labels].sort(), ['industry1', 'job1', 'skill1'])
  app.labels.length = 0
  s.transform.scale = .085; s.draw()
  assert.equal(app.labels.length, 0)
  s.onPointerMove(click(600, 400))
  assert.deepEqual(app.labels, ['skill1'])
  assert.equal(app.debug().hoveredId, 'skill1')
  app.labels.length = 0
  s.onPointerLeave()
  assert.equal(app.labels.length, 0)
})
test('真实 draw 诊断区分全部提交与画布相交，并保留原始及类型过滤度数', t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  app.setGraph([node('j',2000,0,'job'),node('on',0,0),node('off',2500,0),node('hidden',2000,0,'industry')], [
    {source:'j',target:'on',kind:'requires'}, {source:'j',target:'off',kind:'requires'}, {source:'j',target:'hidden',kind:'applies_to'},
  ])
  s.filters.find((filter:any)=>filter.kind==='industry').active = false
  s.highlightNode(s.drawNodes.value[0]); s.draw()
  assert.deepEqual(app.debug().direct, { dataDegree:3, typeFiltered:2, drawable:2, submitted:2, intersecting:1 })
})
test('宽泛搜索下悬停命中只线性读取节点身份，不逐节点扫描全部匹配项', async t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  let reads = 0
  const nodes = Array.from({length:500},(_,i) => ({ ...node('skill'+i,1e6,i), get id() { reads++; return 'skill'+i } }))
  app.setGraph(nodes, [])
  s.searchKeyword.value = 'skill'; await nextTick()
  assert.equal(s.searchMatches.value.length,500)
  reads = 0
  s.nodeAt(0,0)
  assert.ok(reads < 500 * 6, `identity reads: ${reads}`)
})
test('选中和关闭详情后按更新后的面板矩形避让标签，相机不变', async t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  app.setGraph([node('job1',200,0,'job')], [])
  s.transform.scale = 1.25
  let panelOpen = false
  const stop = watch(s.selectedNode, value => { panelOpen = Boolean(value) }, {flush:'post'})
  t.after(stop)
  s.rootRef.value.querySelectorAll = () => panelOpen ? [{getBoundingClientRect:()=>({left:800,right:1200,top:0,bottom:800})}] : []
  const before = {...s.transform}
  await s.onCanvasClick(click(850,400))
  assert.equal(app.debug().labels.drawn,0)
  await s.clearSelection()
  assert.equal(app.debug().labels.drawn,1)
  assert.deepEqual({...s.transform},before)
})

test('搜索导航改变面板高度后使用更新后的 DOM 矩形避让标签', async t => {
  const app = graphComponent(); t.after(app.stop)
  const s = app.state
  app.setGraph([node('job1', 0, -200, 'job')], [])
  s.transform.scale = 1.25
  let bottom = 140
  s.rootRef.value.querySelectorAll = () => [{ getBoundingClientRect: () => ({ left: 550, right: 650, top: 0, bottom }) }]
  const stop = watch(s.searchKeyword, () => { bottom = 200 }, { flush: 'post' }); t.after(stop)
  s.draw(); assert.equal(app.debug().labels.drawn, 1)
  s.searchKeyword.value = 'other'
  await nextTick(); await nextTick()
  assert.equal(app.debug().labels.drawn, 0)
})
