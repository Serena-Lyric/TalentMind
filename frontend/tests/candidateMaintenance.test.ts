import test from 'node:test'
import assert from 'node:assert/strict'
import {candidateComponent} from './helpers/candidateComponent.ts'
const binding={registry_id:'local',revision:1,sha256:'a'.repeat(64)}
const analysis={namespace:'synthetic',jd_id:'1',input_row:{raw_text:'负责处理数据。'},claims:[{id:'d1',kind:'duty',text:'处理数据',evidence:[{quote:'处理数据'}]}]}
const source={analysis_sha256:'b'.repeat(64),analysis}
const work=(revision=1)=>({state:{binding:{...binding,revision},candidates:{c1:{id:'c1',version:revision,description:'原说明',research_question:'原问题',unresolved:['尚未复核']}},relations:{r1:{id:'r1',candidate_id:'c1',namespace:'synthetic',jd_id:'1',analysis_sha256:source.analysis_sha256,work_ids:['d1'],state:'pending_review'}}},versions:[1,2],relation_sha256s:{r1:'c'.repeat(64)},sources:[source]})
const skill=(id='s1',version=1)=>({candidate:{candidate_id:id,version,surface:id,description:'原解释',reason:'原原因',status:'observing',competing_hypotheses:[],referenced_observations:[]},versions:[1,2],projection:{sha256:'d'.repeat(64)},projection_scope:'current_head',eligible_new_evidence:[source]})
function deferred(){let resolve!:(v:any)=>void;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
const nodeText=(node:any):string=>typeof node==='string'?node:Array.isArray(node)?node.map(nodeText).join(''):nodeText(typeof node?.children?.default==='function'?node.children.default():node?.children||'')
const closeLabel='结束旧版未完成维护（保留已保存成果）'
const legacyPending={id:'maintenance-skill-legacy',kind:'skill',candidate_id:'s1',request_sha256:'f'.repeat(64),can_close:true}

test('重新进入页面持久读取已结束但未完整完成的记录，旧服务无closed仍可读取',async()=>{
  let reads=0
  const closure={...legacyPending,status:'closed_incomplete',reason:'旧流程投影身份缺失',candidate_version_saved:true,projection_binding:'not_recorded'}
  const page=candidateComponent({getPendingMaintenance:()=>++reads===1?{items:[],closed:[closure]}:{items:[]}})
  try{await page.state.loadPending();const warning=page.elements().find(n=>n.type?.name==='el-alert'&&n.props?.type==='warning');assert.ok(warning);assert.match(warning.props.title,/closed_incomplete/);assert.match(warning.props.title,/旧流程投影身份缺失/);assert.match(warning.props.title,/s1/);assert.equal(page.state.pendingSaved.value,'');assert.equal(page.calls.length,1)
    await page.state.loadPending();assert.equal(page.elements().filter(n=>n.type?.name==='el-alert'&&n.props?.type==='warning').length,0)
  }finally{page.stop()}
})

test('只有可结束的旧维护显示结束入口，原因必填且读取不自动写入',async()=>{
  const page=candidateComponent({getPendingMaintenance:{items:[legacyPending,{...legacyPending,id:'modern',can_close:false},{...legacyPending,id:'missing',can_close:undefined}]}})
  try{await page.state.loadPending();const nodes=page.elements();const buttons=nodes.filter(n=>n.type?.name==='el-button'&&nodeText(n)===closeLabel);assert.equal(buttons.length,1);assert.equal(page.calls.length,1);assert.ok(nodes.some(n=>n.type==='p'&&/不删除历史、不回滚候选，也不会记作完整成功/.test(nodeText(n))))
    await buttons[0].props.onClick();assert.equal(page.calls.length,1);assert.match(page.state.pendingError.value,/原因/)
    await page.state.closePending({...legacyPending,id:'modern'});assert.equal(page.calls.length,1)
  }finally{page.stop()}
})

for(const saved of [true,false])test(`旧维护显式结束绑定原因，防止重复写入，展示实际未完成状态及候选已保存=${saved}`,async()=>{
  const closing=deferred();let closed=false
  const result={status:'closed_incomplete',reason:'无法确认旧投影绑定',candidate_version_saved:saved,projection_binding:'not_recorded'}
  const page=candidateComponent({getPendingMaintenance:()=>({items:closed?[]:[legacyPending],closed:closed?[{...legacyPending,...result}]:[]}),closeMaintenance:()=>closing.promise})
  try{await page.state.loadPending();const input=page.elements().find(n=>n.props?.['aria-label']==='结束旧版维护原因');assert.ok(input);input.props['onUpdate:modelValue']('  无法确认旧投影绑定  ')
    const button=page.elements().find(n=>n.type?.name==='el-button'&&nodeText(n)===closeLabel);const save=button.props.onClick();await button.props.onClick();await page.state.resumePending(legacyPending);await page.state.loadPending()
    assert.deepEqual(page.calls.filter(c=>c.method==='closeMaintenance').map(c=>c.args),[[legacyPending.id,'无法确认旧投影绑定']]);assert.equal(page.calls.filter(c=>c.method==='resumeMaintenance').length,0);assert.equal(page.calls.filter(c=>c.method==='getPendingMaintenance').length,1)
    assert.ok(page.elements().find(n=>n.type?.name==='el-button'&&nodeText(n)===closeLabel).props.disabled)
    closed=true;closing.resolve(result);await save
    const alert=page.elements().find(n=>n.type?.name==='el-alert'&&n.props?.type==='warning');assert.ok(alert);assert.match(alert.props.title,/closed_incomplete/);assert.match(alert.props.title,/无法确认旧投影绑定/);assert.match(alert.props.title,saved?/候选版本已保存/:/候选版本未保存/);assert.match(alert.props.title,/not_recorded/);assert.equal(page.state.pendingSaved.value,'');assert.equal(page.state.pending.value.length,0)
  }finally{page.stop()}
})

test('结束请求失败保留原因供显式重试，卸载后的迟到结束响应不写回',async()=>{
  const closing=deferred();let attempt=0
  const page=candidateComponent({getPendingMaintenance:{items:[legacyPending]},closeMaintenance:()=>{if(!attempt++)throw Error('网络结果未知');return closing.promise}})
  await page.state.loadPending();page.state.pendingCloseReasons.value[legacyPending.id]='保留原候选，结束旧流程';await page.state.closePending(legacyPending)
  assert.match(page.state.pendingError.value,/网络结果未知/);assert.equal(page.state.pending.value.length,1);assert.equal(page.state.pendingCloseReasons.value[legacyPending.id],'保留原候选，结束旧流程');assert.equal(page.state.pendingSaving.value,'')
  const save=page.state.closePending(legacyPending);page.stop();closing.resolve({status:'closed_incomplete',reason:'保留原候选，结束旧流程',candidate_version_saved:true,projection_binding:'not_recorded'});await save
  assert.deepEqual(page.state.closedMaintenance.value,[]);assert.equal(page.state.pending.value.length,1);assert.equal(page.calls.filter(c=>c.method==='getPendingMaintenance').length,1)
})

test('未完成列表刷新中阻止结束，旧读取迟到不能恢复已撤销的结束资格',async()=>{
  const stale=deferred();let reads=0
  const page=candidateComponent({getPendingMaintenance:()=>++reads===2?stale.promise:{items:[{...legacyPending,can_close:reads===1}]}})
  try{await page.state.loadPending();page.state.pendingCloseReasons.value[legacyPending.id]='结束原因';const refresh=page.state.loadPending();await page.state.closePending(legacyPending);assert.equal(page.calls.filter(c=>c.method==='closeMaintenance').length,0)
    await page.state.loadPending();stale.resolve({items:[legacyPending]});await refresh;assert.equal(page.state.pending.value[0].can_close,false);assert.equal(page.elements().filter(n=>n.type?.name==='el-button'&&nodeText(n)===closeLabel).length,0);await page.state.closePending(legacyPending);assert.equal(page.calls.filter(c=>c.method==='closeMaintenance').length,0)
  }finally{page.stop()}
})

test('工作说明提交绑定读到的版本，响应显示实际保存版本，历史只读',async()=>{
  const page=candidateComponent({getWorkCandidates:work(),saveWorkCandidates:work(2)})
  try{await page.state.loadWork();page.state.selectWork('c1');page.state.workForm.value.description='人工说明';page.state.workForm.value.reason='补充研究目的';await page.state.saveWork()
    const payload=page.calls.find(c=>c.method==='saveWorkCandidates')!.args[0]
    assert.deepEqual(payload.baseline,binding);assert.equal(payload.operations[0].expected_version,1);assert.equal(payload.operations[0].description,'人工说明')
    assert.match(payload.batch_id,/^[a-z][a-z0-9._-]{0,95}$/)
    assert.equal(page.state.work.value.state.binding.revision,2)
    await page.state.loadWork(1);await page.state.saveWork()
    assert.equal(page.calls.filter(c=>c.method==='saveWorkCandidates').length,1)
  }finally{page.stop()}
})
test('关系纠正携带旧SHA、原因、同JD替代来源和明确反证，浏览器不生成审核确认',async()=>{
  const page=candidateComponent({getWorkCandidates:work(),saveWorkCandidates:work(2)})
  try{await page.state.loadWork();page.state.selectWork('c1');Object.assign(page.state.workForm.value,{action:'correct',relationId:'r1',decision:'weakens',reason:'职责范围存在反证',sourceSha:source.analysis_sha256,workIds:['d1'],replace:true,counterSourceSha:source.analysis_sha256,counterIds:['d1']});await page.state.saveWork()
    const op=page.calls.find(c=>c.method==='saveWorkCandidates')!.args[0].operations[0]
    assert.equal(op.expected_sha256,'c'.repeat(64));assert.equal(op.verification,null);assert.deepEqual(op.replacement,{analysis_sha256:source.analysis_sha256,work_ids:['d1']});assert.deepEqual(op.counterevidence,[{analysis_sha256:source.analysis_sha256,claim_id:'d1'}])
  }finally{page.stop()}
})
test('工作版本冲突保留用户输入并阻止重复写，刷新当前版本后才可重做',async()=>{
  const conflict=Object.assign(new Error('stale'),{response:{status:409,data:{detail:'stale baseline'}}})
  const page=candidateComponent({getWorkCandidates:work(),saveWorkCandidates:conflict})
  try{await page.state.loadWork();page.state.selectWork('c1');page.state.workForm.value.reason='研究修订';await page.state.saveWork();await page.state.saveWork()
    assert.equal(page.calls.filter(c=>c.method==='saveWorkCandidates').length,1);assert.match(page.state.workError.value,/版本冲突/);assert.equal(page.state.workForm.value.reason,'研究修订')
  }finally{page.stop()}
})
test('技能未知网络结果重试使用同一请求ID，成功后读回真实版本',async()=>{
  let attempt=0
  const page=candidateComponent({getSkillCandidate:skill(),saveSkillCandidate:()=>{if(!attempt++)throw Error('network');return skill('s1',2)}})
  try{await page.state.loadSkill('s1');Object.assign(page.state.skillForm.value,{action:'mark_disputed',reason:'解释有歧义',hypotheses:'另一种解释'});await page.state.saveSkill();await page.state.saveSkill()
    const requests=page.calls.filter(c=>c.method==='saveSkillCandidate').map(c=>c.args[1]);assert.equal(requests[0].request_id,requests[1].request_id);assert.match(requests[0].request_id,/^[a-z][a-z0-9._-]{0,95}$/);assert.equal(requests[0].expected_version,1);assert.deepEqual(requests[0].competing_hypotheses,['另一种解释']);assert.equal(page.state.skill.value.candidate.version,2)
  }finally{page.stop()}
})
test('技能证据修订仅允许服务器提供的新证据，无证据不发送请求',async()=>{
  const page=candidateComponent({getSkillCandidate:{...skill(),eligible_new_evidence:[]},saveSkillCandidate:skill('s1',2)})
  try{await page.state.loadSkill('s1');Object.assign(page.state.skillForm.value,{action:'revise',reason:'更新解释',description:'有依据的解释',sourceSha:source.analysis_sha256});await page.state.saveSkill();assert.equal(page.calls.filter(c=>c.method==='saveSkillCandidate').length,0);assert.match(page.state.skillError.value,/新证据/)
  }finally{page.stop()}
})
test('候选与版本切换后迟到读取及保存不会覆盖新选择',async()=>{
  const pending=deferred(),saving=deferred()
  const page=candidateComponent({getSkillCandidate:(id:string)=>id==='slow'?pending.promise:skill(id),saveSkillCandidate:()=>saving.promise})
  try{const old=page.state.loadSkill('slow');await page.state.loadSkill('s1');pending.resolve(skill('slow'));await old;assert.equal(page.state.skill.value.candidate.candidate_id,'s1')
    Object.assign(page.state.skillForm.value,{action:'withdraw',reason:'整体撤回'});const save=page.state.saveSkill();await page.state.loadSkill('s2');saving.resolve(skill('s1',2));await save;assert.equal(page.state.skill.value.candidate.candidate_id,'s2')
  }finally{page.stop()}
})
test('新来源关联必须有具体职责且已有JD关系不能被重复关联覆盖',async()=>{
  const different={analysis_sha256:'e'.repeat(64),analysis:{...analysis,jd_id:'2'}}
  const page=candidateComponent({getWorkCandidates:{...work(),sources:[source,different]},saveWorkCandidates:work(2)})
  try{await page.state.loadWork();page.state.selectWork('c1');Object.assign(page.state.workForm.value,{action:'link',sourceSha:source.analysis_sha256,workIds:['d1'],reason:'关联职责'});await page.state.saveWork();assert.equal(page.calls.filter(c=>c.method==='saveWorkCandidates').length,0)
    page.state.workForm.value.sourceSha=different.analysis_sha256;await page.state.saveWork();const payload=page.calls.find(c=>c.method==='saveWorkCandidates')!.args[0];assert.deepEqual(payload.analysis_sha256s,[different.analysis_sha256]);assert.equal(payload.operations[0].op,'link');assert.deepEqual(payload.operations[0].work_ids,['d1'])
  }finally{page.stop()}
})
test('技能修订提交实际新证据与原版本，整体撤回不伪造单条观察删除',async()=>{
  const page=candidateComponent({getSkillCandidate:skill(),saveSkillCandidate:skill('s1',2)})
  try{await page.state.loadSkill('s1');Object.assign(page.state.skillForm.value,{action:'revise',reason:'新来源支持',description:'基于新证据的解释',sourceSha:source.analysis_sha256});await page.state.saveSkill();const revised=page.calls.find(c=>c.method==='saveSkillCandidate')!.args[1];assert.equal(revised.source_analysis_sha256,source.analysis_sha256);assert.equal(revised.expected_version,1)
    Object.assign(page.state.skillForm.value,{action:'withdraw',reason:'整体不再使用'});await page.state.saveSkill();const withdrawn=page.calls.filter(c=>c.method==='saveSkillCandidate')[1].args[1];assert.equal(withdrawn.expected_version,2);assert.equal(withdrawn.action,'withdraw');assert.equal('observation_key' in withdrawn,false)
  }finally{page.stop()}
})
test('技能历史只读，旧版本迟到结果不写回',async()=>{
  const pending=deferred();const page=candidateComponent({getSkillCandidate:(_:string,version?:number)=>version===1?pending.promise:skill('s1',2),saveSkillCandidate:skill('s1',3)})
  try{const old=page.state.loadSkill('s1',1);await page.state.loadSkill('s1',2);pending.resolve(skill('s1',1));await old;assert.equal(page.state.skill.value.candidate.version,2);Object.assign(page.state.skillForm.value,{action:'withdraw',reason:'撤回'});await page.state.saveSkill();assert.equal(page.calls.filter(c=>c.method==='saveSkillCandidate').length,0)
  }finally{page.stop()}
})
test('卸载后工作及技能响应都不恢复已离开的维护页面',async()=>{
  const workPending=deferred(),skillPending=deferred();const page=candidateComponent({getWorkCandidates:()=>workPending.promise,getSkillCandidate:()=>skillPending.promise})
  const loadingWork=page.state.loadWork(),loadingSkill=page.state.loadSkill('s1');page.stop();workPending.resolve(work());skillPending.resolve(skill());await Promise.all([loadingWork,loadingSkill]);assert.equal(page.state.work.value,null);assert.equal(page.state.skill.value,null)
})
test('重新进入页面可查询并显式恢复未完成维护，读取不会自动恢复',async()=>{
  const item={id:'maintenance-skill-test',kind:'skill',candidate_id:'s1'}
  let resumed=false
  const page=candidateComponent({getPendingMaintenance:()=>({items:resumed?[]:[item]}),resumeMaintenance:()=>{resumed=true;return skill('s1',2)}})
  try{await page.state.loadPending();assert.equal(resumed,false);assert.equal(page.state.pending.value.length,1);await page.state.resumePending(item);assert.equal(page.calls.find(c=>c.method==='resumeMaintenance')!.args[0],item.id);assert.match(page.state.pendingSaved.value,/v2/);assert.equal(page.state.pending.value.length,0);assert.equal(page.state.skill.value,null)}finally{page.stop()}
})
test('工作读取倒序时旧请求不覆盖新版本也不提前结束新加载',async()=>{
  const old=deferred(),current=deferred();let calls=0
  const page=candidateComponent({getWorkCandidates:()=>++calls===1?old.promise:current.promise})
  try{const first=page.state.loadWork(1),second=page.state.loadWork();old.resolve(work(1));await first;assert.equal(page.state.work.value,null);assert.equal(page.state.workLoading.value,true);current.resolve(work(2));await second;assert.equal(page.state.work.value.state.binding.revision,2);assert.equal(page.state.workLoading.value,false)}finally{page.stop()}
})
test('历史读取拒绝与所选版本不一致的响应，不能借当前版本冒充历史',async()=>{
  const page=candidateComponent({getWorkCandidates:work(2),getSkillCandidate:skill('s1',2)})
  try{await page.state.loadWork(1);assert.equal(page.state.work.value,null);assert.match(page.state.workError.value,/版本/);await page.state.loadSkill('s1',1);assert.equal(page.state.skill.value,null);assert.match(page.state.skillError.value,/版本/)}finally{page.stop()}
})
