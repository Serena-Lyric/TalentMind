import { test } from 'node:test'
import assert from 'node:assert/strict'
import { graphComponent } from './helpers/graphComponent.ts'

test('派生相似独立计数与说明，不混入历史关系及直连数',t=>{
  const app=graphComponent();t.after(app.stop)
  const nodes=['a','b'].map((id,i)=>({id,label:id,kind:'job',point:{x:i*20,y:0}}))
  app.setGraph(nodes,[{source:'a',target:'b',kind:'RELATED_TO'}])
  app.state.artifact.value={nodes:[],derived_edges:[{source:'a',target:'b',score:.2,shared:[]}]}
  app.state.showDerived.value=true;app.state.draw()
  assert.equal(app.debug().totalEdges,1);assert.equal(app.debug().derivedSubmitted,1)
  assert.match(app.state.derivedSummary.value,/1.*1/)
})

test('可访问的缩放按钮复用滚轮状态，保持画布中心世界坐标',t=>{
  const app=graphComponent();t.after(app.stop)
  const s=app.state
  Object.assign(s.transform,{x:10,y:20,scale:.2})
  s.zoomView(-1)
  assert.ok(s.transform.scale>.2)
  assert.equal(s.transform.x,10);assert.equal(s.transform.y,20)
})

test('密集知识节点按最近屏幕中心命中，不由原数组的最后一项夺取身份',t=>{
  const app=graphComponent();t.after(app.stop)
  const nodes=[{id:'python',label:'Python',kind:'skill',point:{x:0,y:0}}, {id:'near',label:'Near',kind:'skill',point:{x:4,y:0}}]
  app.setGraph(nodes,[])
  assert.equal(app.state.nodeAt(600,400).id,'python')
})

test('正式状态保留全部直连与原边索引，分页末页不漏边', t=>{
  const app=graphComponent();t.after(app.stop)
  const nodes=[{id:'python',label:'Python',kind:'skill',point:{x:0,y:0}},...Array.from({length:222},(_,i)=>({id:`j${i}`,label:`Job ${i}`,kind:'job',point:{x:i*2,y:0}}))]
  const edges=nodes.slice(1).map((n,i)=>({source:n.id,target:'python',kind:'REQUIRES',sourceIndex:i,raw:{type:'REQUIRES'}}))
  app.setGraph(nodes,edges)
  app.state.highlightNode(nodes[0]);app.state.draw()
  assert.equal(app.state.directEdges.value.length,222)
  assert.equal(app.state.connectionRows.value.length,30)
  app.state.connectionPage.value=7
  assert.equal(app.state.connectionRows.value.length,12)
  assert.equal(app.state.connectionRows.value.at(-1).sourceIndex,221)
  assert.equal(app.debug().direct.submitted,222)
})
