import test from 'node:test'
import assert from 'node:assert/strict'
import {candidateComponent} from './helpers/candidateComponent.ts'
const binding={registry_id:'local',revision:1,sha256:'a'.repeat(64)}
const analysis={namespace:'synthetic',jd_id:'1',input_row:{raw_text:'负责处理数据。'},claims:[{id:'d1',kind:'duty',text:'处理数据',evidence:[{quote:'处理数据'}]}]}
const source={analysis_sha256:'b'.repeat(64),analysis}
const work=(revision=1)=>({state:{binding:{...binding,revision},candidates:{c1:{id:'c1',version:revision,description:'原说明',research_question:'原问题',unresolved:['尚未复核']}},relations:{r1:{id:'r1',candidate_id:'c1',namespace:'synthetic',jd_id:'1',analysis_sha256:source.analysis_sha256,work_ids:['d1'],state:'pending_review'}}},versions:[1,2],relation_sha256s:{r1:'c'.repeat(64)},sources:[source]})
const skill=(id='s1',version=1)=>({candidate:{candidate_id:id,version,surface:id,description:'原解释',reason:'原原因',status:'observing',competing_hypotheses:[],referenced_observations:[]},versions:[1,2],projection:{sha256:'d'.repeat(64)},projection_scope:'current_head',eligible_new_evidence:[source]})
function deferred(){let resolve!:(v:any)=>void;const promise=new Promise(r=>resolve=r);return {promise,resolve}}

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
