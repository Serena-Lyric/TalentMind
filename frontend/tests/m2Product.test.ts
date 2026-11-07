import test from 'node:test'
import assert from 'node:assert/strict'
import { m2Component } from './helpers/m2Component.ts'
const draft = { run_id: 'a'.repeat(32), status: 'prepared', request_sha256:'f'.repeat(64), items: [], counts: {} }
test('翻页失败清空旧页，保持选择并从页面按钮重试失败页', async () => {
  let fail = true
  const page=m2Component({getDeliveryInputs:(offset:number)=>{
    if(offset===20 && fail) throw new Error('offline')
    return {items:[{jd_id:offset+1}],total:42}
  }})
  try {
    await page.state.changeInputPage(1);page.state.toggleInput(1)
    await page.state.changeInputPage(2)
    assert.deepEqual(page.state.inputs.value, [])
    assert.equal(page.state.inputPage.value,2)
    assert.ok(page.state.inputError.value)
    assert.deepEqual(page.state.selectedJdIds.value,[1])
    fail=false
    const retry=page.elements('el-button').find(node=>JSON.stringify(node.children?.default?.()).includes('重试第'))
    assert.ok(retry)
    await retry.props.onClick()
    assert.equal(page.state.inputs.value[0].jd_id,21)
    assert.equal(page.state.inputError.value,'')
    assert.deepEqual(page.state.selectedJdIds.value,[1])
  } finally {page.stop()}
})
test('分页迟到成功或失败不覆盖新页，也不提前结束新页加载', async () => {
  const pending:Record<number,{resolve:(value:any)=>void;reject:(reason:any)=>void}>={}
  const page=m2Component({getDeliveryInputs:(offset:number)=>new Promise((resolve,reject)=>{pending[offset]={resolve,reject}})})
  try {
    const first=page.state.changeInputPage(1),second=page.state.changeInputPage(2)
    pending[0].resolve({items:[{jd_id:1}],total:42});await first
    assert.deepEqual(page.state.inputs.value,[]);assert.equal(page.state.inputsLoading.value,true)
    pending[20].resolve({items:[{jd_id:21}],total:42});await second
    const third=page.state.changeInputPage(3),retry=page.state.changeInputPage(2)
    pending[20].resolve({items:[{jd_id:22}],total:43});await retry
    pending[40].reject(new Error('old failure'));await third
    assert.equal(page.state.inputs.value[0].jd_id,22)
    assert.equal(page.state.inputPage.value,2);assert.equal(page.state.inputTotal.value,43)
    assert.equal(page.state.inputError.value,'');assert.equal(page.state.inputsLoading.value,false)
  } finally {page.stop()}
})
test('新版进入和轮询不执行，显式选择后仅冻结，开始/停止/恢复独立调用', async () => {
  const page=m2Component({createDeliveryRun:draft,startDeliveryRun:{...draft,status:'running'},stopDeliveryRun:{...draft,status:'stopped'},resumeDeliveryRun:{...draft,status:'running'}})
  try {
    await page.mounted(); for(const poll of page.intervals) await poll()
    assert.equal(page.calls.some(c=>/create|start|resume/i.test(c.method)),false)
    await page.state.createRun(); assert.equal(page.calls.some(c=>c.method==='createDeliveryRun'),false)
    page.state.selectedJdIds.value=[12,15]; await page.state.createRun()
    assert.deepEqual(page.calls.find(c=>c.method==='createDeliveryRun').args,[{jd_ids:[12,15]}])
    assert.equal(page.calls.some(c=>c.method==='startDeliveryRun'),false)
    await page.state.startRun(); await page.state.stopRun(); await page.state.resumeRun()
    assert.ok(page.calls.some(c=>c.method==='resumeDeliveryRun'))
  } finally {page.stop()}
})
test('历史改选和卸载后，迟到结果不能覆盖当前运行', async()=>{
  let finish!:(value:any)=>void
  const page=m2Component({getDeliveryRun:(id:string)=>id==='old'?new Promise(r=>{finish=r}):{...draft,run_id:id}})
  try {
    const old=page.state.selectRun('old'); await page.state.selectRun('new'); finish({...draft,run_id:'old'}); await old
    assert.equal(page.state.selected.value.run_id,'new')
    const pending=page.state.selectRun('old');page.stop();finish({...draft,run_id:'old'});await pending
    assert.notEqual(page.state.selected.value?.run_id,'old')
  } finally {page.stop()}
})
test('候选图失败不切换历史图，改选后旧导航失效',async()=>{
  let finish!:(value:any)=>void
  const page=m2Component({getDeliveryGraph:()=>new Promise(r=>{finish=r}),getDeliveryRun:{...draft,run_id:'new'}})
  try {
    page.state.selected.value={...draft,status:'completed'};page.state.selectedId.value=draft.run_id
    const pending=page.state.openGraph();await page.state.selectRun('new');finish({run_id:draft.run_id,url:'/old'});await pending
    assert.deepEqual(page.navigations,[])
  } finally {page.stop()}
})


test('执行中prepared响应仍会轮询，历史只读运行不会执行或放弃',async()=>{
 const page=m2Component({startDeliveryRun:{...draft,execution_active:true},getDeliveryRun:{...draft,status:'running',execution_active:true}})
 try {
  await page.mounted();page.state.selected.value=draft;page.state.selectedId.value=draft.run_id
  await page.state.startRun();for(const poll of page.intervals)await poll()
  assert.ok(page.calls.some(c=>c.method==='getDeliveryRun'))
  page.state.selected.value={...draft,status:'stopped',execution_available:false};const before=page.calls.length
  await page.state.resumeRun();await page.state.abandonRun();assert.equal(page.calls.length,before)
 } finally {page.stop()}
})

test('用户显式放弃保留结果；迟到开始响应不能覆盖改选运行',async()=>{
 let finish!:(value:any)=>void
 const page=m2Component({startDeliveryRun:()=>new Promise(r=>{finish=r}),getDeliveryRun:{...draft,run_id:'new'},abandonDeliveryRun:{...draft,run_id:'new',status:'abandoned',execution_available:false}})
 try {
  page.state.selected.value=draft;page.state.selectedId.value=draft.run_id
  const pending=page.state.startRun();await page.state.selectRun('new');finish({...draft,status:'running'});await pending
  assert.equal(page.state.selected.value.run_id,'new')
  await page.state.abandonRun();assert.deepEqual(page.calls.find(c=>c.method==='abandonDeliveryRun').args,['new'])
  assert.equal(page.state.selected.value.status,'abandoned')
 } finally {page.stop()}
})
