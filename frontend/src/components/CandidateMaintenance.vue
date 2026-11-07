<template>
  <section class="candidate-maintenance surface">
    <h2>候选维护</h2>
    <p>这里读取本机候选当前版本；上方运行、历史比较和图谱继续保留当时快照。维护只影响后续研究与知识对齐，不修改原 JD 或正式岗位。</p>
    <div class="actions"><el-button :loading="workLoading" @click="loadWork()">读取工作候选</el-button><el-button :loading="skillListLoading" @click="loadSkills()">读取技能候选</el-button><el-button :loading="pendingLoading" :disabled="!!pendingSaving" @click="loadPending()">检查未完成维护</el-button></div>
    <el-alert v-if="pendingError" :title="pendingError" type="error" :closable="false" />
    <el-alert v-if="pendingSaved" :title="pendingSaved" type="success" :closable="false" />
    <el-alert v-for="item in closedMaintenance" :key="item.id" :title="closedMaintenanceMessage(item)" type="warning" :closable="false" />
    <template v-if="pending!==null"><p v-if="!pending.length">没有需要恢复的未完成维护。</p><article v-for="item in pending" :key="item.id" class="source"><p>{{item.kind==='work'?'工作候选':'技能候选'}}维护中断 · {{item.candidate_id || item.id}}</p><p>恢复将继续服务端已冻结的原请求，不使用当前表单内容。</p><p class="binding">请求摘要 {{item.request_sha256}}</p><details v-if="item.request"><summary>核对待恢复操作、原因和版本</summary><pre>{{pretty(item.request)}}</pre></details><el-button :loading="pendingSaving===item.id" :disabled="!!pendingSaving" @click="resumePending(item)">恢复未完成维护</el-button>
      <template v-if="item.can_close===true">
        <p>旧版维护没有记录完整投影绑定，无法安全认领为完整成功。结束将保留已保存成果，不删除历史、不回滚候选，也不会记作完整成功。</p>
        <el-input v-model="pendingCloseReasons[item.id]" aria-label="结束旧版维护原因" placeholder="填写结束原因（必填）" type="textarea" :disabled="!!pendingSaving || pendingLoading" />
        <el-button :loading="pendingSaving===item.id" :disabled="!!pendingSaving || pendingLoading" @click="closePending(item)">结束旧版未完成维护（保留已保存成果）</el-button>
      </template>
    </article></template>
    <el-alert v-if="workError" :title="workError" type="error" :closable="false" />
    <el-alert v-if="workSaved" :title="workSaved" type="success" :closable="false" />
    <article v-if="work" class="candidate-block">
      <h3>工作候选</h3>
      <div class="actions">
        <el-select aria-label="工作候选" :model-value="workId" placeholder="选择工作候选" @change="selectWork"><el-option v-for="(candidate,id) in work.state.candidates" :key="id" :value="String(id)" :label="candidate.description || String(id)" /></el-select>
        <el-select aria-label="工作研究版本" :model-value="workRevision ?? 'current'" @change="changeWorkRevision"><el-option value="current" label="当前版本（可维护）" /><el-option v-for="version in work.versions" :key="version" :value="version" :label="`历史研究版本 ${version}（只读）`" /></el-select>
      </div>
      <p class="binding">研究版本 {{work.state.binding.revision}} · {{work.state.binding.sha256}}</p>
      <p v-if="!Object.keys(work.state.candidates).length">本机尚无工作候选，请先显式执行分析。</p>
      <template v-if="workCandidate">
        <p>候选 {{workId}} · v{{workCandidate.version}} · {{stateLabel(workCandidate.status)}}；普通支持仍待复核。</p>
        <h4>人工研究说明与系统解释</h4><p>当前说明：{{workCandidate.description}}</p><p>研究问题：{{workCandidate.research_question}}</p><p>未决：{{(workCandidate.unresolved || []).join('；')}}</p>
        <details><summary>系统研究解释与核心工作（维护说明不覆盖它们）</summary><pre>{{pretty({research:workCandidate.research,core_work:workCandidate.core_work})}}</pre></details>
        <h4>候选与 JD 的关系、职责及原文</h4>
        <article v-for="relation in workRelations" :key="relation.id" class="source">
          <p>{{relation.namespace}} / JD {{relation.jd_id}} · {{stateLabel(relation.state)}} · {{relation.reason}}</p>
          <p class="binding">分析 {{relation.analysis_sha256}}</p>
          <template v-for="claim in sourceClaims(relation.analysis_sha256,relation.work_ids)" :key="claim.id"><p>{{claim.text}}</p><blockquote v-for="(e,index) in claim.evidence" :key="index">{{e.quote}}<small>{{e.field}} [{{e.start}}, {{e.end}})</small></blockquote></template>
          <details><summary>冻结原文、替换原因与旧版本引用</summary><pre>{{pretty({source:sourceBySha(relation.analysis_sha256)?.analysis.input_row,relation})}}</pre></details>
        </article>
        <p v-if="workRevision!==undefined">正在阅读历史版本。选择“当前版本（可维护）”后才能修改。</p>
        <el-form v-else label-position="top" :disabled="workSaving || workLoading || workConflict" @submit.prevent="saveWork">
          <el-form-item label="维护操作"><el-select v-model="workForm.action"><el-option value="describe" label="修订人工研究说明" /><el-option value="link" label="关联有职责依据的新来源" /><el-option value="correct" label="纠正已有候选—JD 关系" /></el-select></el-form-item>
          <template v-if="workForm.action==='describe'">
            <el-form-item label="人工研究说明"><el-input v-model="workForm.description" type="textarea" /></el-form-item>
            <el-form-item label="研究问题"><el-input v-model="workForm.question" type="textarea" /></el-form-item>
            <el-form-item label="未决备注（每行一项，至少一项）"><el-input v-model="workForm.unresolved" type="textarea" /></el-form-item>
          </template>
          <template v-if="workForm.action==='correct'">
            <el-form-item label="已有关系"><el-select v-model="workForm.relationId" @change="resetWorkEvidence"><el-option v-for="relation in workRelations" :key="relation.id" :value="relation.id" :label="`${relation.namespace} / JD ${relation.jd_id} · ${stateLabel(relation.state)}`" /></el-select></el-form-item>
            <el-form-item label="纠正含义"><el-select v-model="workForm.decision"><el-option value="corroborates" label="普通支持补充（仍待复核）" /><el-option value="weakens" label="反证 / 存在争议" /><el-option value="rejects" label="拒绝该关系" /><el-option value="withdraw" label="撤回该关系" /></el-select></el-form-item>
            <el-checkbox v-model="workForm.replace" @change="resetWorkEvidence">更换同一 JD 的分析版本及职责依据</el-checkbox>
          </template>
          <template v-if="workForm.action==='link' || (workForm.action==='correct' && workForm.replace)">
            <el-form-item label="来源分析（必须包含具体职责）"><el-select v-model="workForm.sourceSha" @change="workForm.workIds=[]"><el-option v-for="source in selectableWorkSources" :key="source.analysis_sha256" :value="source.analysis_sha256" :label="sourceLabel(source)" /></el-select></el-form-item>
            <p v-if="!selectableWorkSources.length">没有适用来源。已有关联请使用纠正；替换仅允许同一 JD 身份。</p>
            <el-checkbox-group v-model="workForm.workIds"><el-checkbox v-for="claim in workClaims(workForm.sourceSha)" :key="claim.id" :value="claim.id" :label="claim.id">{{claim.kind}} · {{claim.text}}</el-checkbox></el-checkbox-group>
            <details v-if="workForm.sourceSha"><summary>所选来源原文与证据</summary><pre>{{pretty(sourceBySha(workForm.sourceSha)?.analysis)}}</pre></details>
          </template>
          <template v-if="workForm.action==='correct'">
            <el-form-item label="反证来源（可选；仅陈述理由时留空）"><el-select v-model="workForm.counterSourceSha" clearable @change="workForm.counterIds=[]"><el-option v-for="source in work.sources" :key="source.analysis_sha256" :value="source.analysis_sha256" :label="sourceLabel(source)" /></el-select></el-form-item>
            <el-checkbox-group v-model="workForm.counterIds"><el-checkbox v-for="claim in workClaims(workForm.counterSourceSha)" :key="claim.id" :value="claim.id" :label="claim.id">{{claim.kind}} · {{claim.text}}</el-checkbox></el-checkbox-group>
            <details v-if="workForm.counterSourceSha"><summary>反证原文</summary><pre>{{pretty(sourceBySha(workForm.counterSourceSha)?.analysis)}}</pre></details>
          </template>
          <el-form-item label="本次维护原因（必填）"><el-input v-model="workForm.reason" type="textarea" /></el-form-item>
          <el-button type="primary" native-type="submit" :loading="workSaving">保存工作候选新版本</el-button>
        </el-form>
        <el-button v-if="workConflict" @click="loadWork()">重新读取当前版本后修改</el-button>
      </template>
    </article>
    <el-alert v-if="skillError" :title="skillError" type="error" :closable="false" />
    <el-alert v-if="skillSaved" :title="skillSaved" type="success" :closable="false" />
    <article v-if="skills!==null" class="candidate-block">
      <h3>技能候选</h3><p>争议保留不同解释；整体撤回作用于候选，不删除单条观察。正式准入未开放。</p>
      <el-select aria-label="技能候选" :model-value="skillId" placeholder="选择技能候选" @change="selectSkill"><el-option v-for="candidate in skills" :key="candidate.candidate_id" :value="candidate.candidate_id" :label="`${candidate.surface} · ${stateLabel(candidate.status)} · v${candidate.version}`" /></el-select>
      <p v-if="!skills.length">本机尚无技能候选。</p>
    </article>
    <article v-if="skill" v-loading="skillLoading" class="candidate-block">
      <h4>{{skill.candidate.surface}} · {{stateLabel(skill.candidate.status)}} · 实际保存 v{{skill.candidate.version}}</h4>
      <el-select aria-label="技能候选版本" :model-value="skillVersion ?? 'current'" @change="changeSkillVersion"><el-option value="current" label="当前版本（可维护）" /><el-option v-for="version in skill.versions" :key="version" :value="version" :label="`历史 v${version}（只读）`" /></el-select>
      <p>{{skill.candidate.description}}</p><p>原因：{{skill.candidate.reason}}</p><p>不同解释：{{(skill.candidate.competing_hypotheses || []).join('；') || '未记录'}}</p>
      <article v-for="observation in skill.candidate.referenced_observations || []" :key="observation.observation_key" class="source"><p>{{observation.namespace}} / JD {{observation.jd_id}} · {{observation.member}}</p><blockquote v-for="(e,index) in observation.evidence" :key="index">{{e.quote}}<small>{{e.field}} [{{e.start}}, {{e.end}})</small></blockquote><details><summary>完整绑定观察</summary><pre>{{pretty(observation)}}</pre></details></article>
      <details v-if="skill.projection_scope==='current_head'"><summary>当前知识投影（后续分析使用）</summary><pre>{{pretty(skill.projection)}}</pre></details>
      <p v-else>此处只读该历史候选及绑定证据；历史运行的知识投影请在对应运行中查看。</p>
      <p v-if="skillVersion!==undefined">正在阅读历史版本，不能在旧版本上写入。</p>
      <el-form v-else label-position="top" :disabled="skillSaving || skillLoading || skillConflict" @submit.prevent="saveSkill">
        <el-form-item label="维护操作"><el-select v-model="skillForm.action"><el-option value="mark_disputed" label="记录争议及不同解释" /><el-option value="withdraw" label="整体撤回候选" /><el-option value="revise" label="使用新来源证据修订解释" /></el-select></el-form-item>
        <template v-if="skillForm.action==='revise'">
          <el-alert v-if="!skill.eligible_new_evidence.length" title="当前没有同一解释下尚未绑定的新证据；已 observe 的证据不能用于修订。" type="info" :closable="false" />
          <el-form-item label="尚未绑定的新来源证据"><el-select v-model="skillForm.sourceSha"><el-option v-for="source in skill.eligible_new_evidence" :key="source.analysis_sha256" :value="source.analysis_sha256" :label="sourceLabel(source)" /></el-select></el-form-item>
          <details v-if="skillForm.sourceSha"><summary>所选新证据与原文</summary><pre>{{pretty(skill.eligible_new_evidence.find(source=>source.analysis_sha256===skillForm.sourceSha)?.analysis)}}</pre></details>
          <el-form-item label="基于新证据的解释"><el-input v-model="skillForm.description" type="textarea" /></el-form-item>
        </template>
        <el-form-item v-if="skillForm.action!=='withdraw'" :label="skillForm.action==='mark_disputed'?'不同解释（每行一项，至少一项）':'不同解释（可选，每行一项）'"><el-input v-model="skillForm.hypotheses" type="textarea" /></el-form-item>
        <el-form-item label="本次维护原因（必填）"><el-input v-model="skillForm.reason" type="textarea" /></el-form-item>
        <el-button type="primary" native-type="submit" :loading="skillSaving" :disabled="skillForm.action==='revise' && !skill.eligible_new_evidence.length">保存技能候选新版本</el-button>
      </el-form>
      <el-button v-if="skillConflict" @click="loadSkill(skillId)">重新读取当前版本后修改</el-button>
    </article>
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import {getWorkCandidates,saveWorkCandidates,getSkillCandidates,getSkillCandidate,saveSkillCandidate,getPendingMaintenance,resumeMaintenance,closeMaintenance,type WorkCandidates,type SkillCandidateDetail,type CandidateSource,type PendingMaintenance,type ClosedMaintenanceRecord} from '../api/candidates'

const work=ref<WorkCandidates|null>(null),workId=ref(''),workRevision=ref<number>(),workLoading=ref(false),workSaving=ref(false),workError=ref(''),workSaved=ref(''),workConflict=ref(false)
const skills=ref<Record<string,any>[]|null>(null),skill=ref<SkillCandidateDetail|null>(null),skillId=ref(''),skillVersion=ref<number>(),skillLoading=ref(false),skillListLoading=ref(false),skillSaving=ref(false),skillError=ref(''),skillSaved=ref(''),skillConflict=ref(false)
const pending=ref<PendingMaintenance[]|null>(null),pendingLoading=ref(false),pendingSaving=ref(''),pendingError=ref(''),pendingSaved=ref('')
const pendingCloseReasons=ref<Record<string,string>>({}),closedMaintenance=ref<ClosedMaintenanceRecord[]>([])
const emptyWork=()=>({action:'describe',description:'',question:'',unresolved:'',reason:'',relationId:'',decision:'corroborates',sourceSha:'',workIds:[] as string[],replace:false,counterSourceSha:'',counterIds:[] as string[]})
const workForm=ref(emptyWork())
const skillForm=ref({action:'mark_disputed',reason:'',description:'',hypotheses:'',sourceSha:''})
let disposed=false,workEpoch=0,skillEpoch=0,listEpoch=0,pendingEpoch=0
let workRetry:{signature:string;id:string}|null=null,skillRetry:{signature:string;id:string}|null=null
const workCandidate=computed(()=>work.value?.state.candidates[workId.value])
const workRelations=computed(()=>Object.values(work.value?.state.relations || {}).filter(r=>r.candidate_id===workId.value))
const selectableWorkSources=computed(()=>{
  const relation=work.value?.state.relations[workForm.value.relationId]
  return (work.value?.sources || []).filter(source=>{
    if(!source.analysis.claims.some(c=>c.kind==='duty'))return false
    if(workForm.value.action==='correct')return relation && source.analysis.namespace===relation.namespace && source.analysis.jd_id===relation.jd_id
    return !workRelations.value.some(r=>r.namespace===source.analysis.namespace&&r.jd_id===source.analysis.jd_id)
  })
})
function pretty(value:any){return JSON.stringify(value??null,null,2)}
function lines(value:string){return value.split('\n').map(s=>s.trim()).filter(Boolean)}
function message(e:any){const detail=e?.response?.data?.detail;return typeof detail==='string'?detail:e?.message || String(e)}
function stateLabel(value:string){return ({observing:'持续观察',pending_review:'待复核',controlled_support:'合成控制支持',disputed:'存在争议',rejected_proposal:'关系已拒绝',withdrawn:'已撤回',corroborated:'已有支持证据'} as Record<string,string>)[value] || value || '未提供'}
function sourceLabel(source:CandidateSource){return `${source.analysis.namespace} / JD ${source.analysis.jd_id} · ${source.analysis.input_row.job_title || '来源分析'} · ${source.analysis_sha256.slice(0,12)}`}
function sourceBySha(sha:string){return work.value?.sources.find(source=>source.analysis_sha256===sha)}
function sourceClaims(sha:string,ids:string[]){return sourceBySha(sha)?.analysis.claims.filter(c=>ids.includes(c.id)) || []}
function workClaims(sha:string){return sourceBySha(sha)?.analysis.claims.filter(c=>['duty','goal','object'].includes(c.kind)) || []}
function changeWorkRevision(value:string|number){return loadWork(value==='current'?undefined:Number(value))}
function selectSkill(id:string){return loadSkill(id)}
function changeSkillVersion(value:string|number){return loadSkill(skillId.value,value==='current'?undefined:Number(value))}
function resetWorkEvidence(){workForm.value.sourceSha='';workForm.value.workIds=[]}
function resetWorkForm(id:string){workId.value=id;workSaved.value='';workRetry=null;const candidate=work.value?.state.candidates[id];workForm.value={...emptyWork(),description:candidate?.description||'',question:candidate?.research_question||'',unresolved:(candidate?.unresolved||[]).join('\n')}}
function selectWork(id:string){workEpoch++;workSaving.value=false;resetWorkForm(id)}
async function loadWork(revision?:number){const token=++workEpoch;workLoading.value=true;workSaving.value=false;workError.value='';workSaved.value='';work.value=null;workRevision.value=revision;workRetry=null
  try{const result=await getWorkCandidates(revision);if(disposed||token!==workEpoch)return;if(revision!==undefined&&result.state.binding.revision!==revision)throw Error('工作研究版本与所选历史不一致');work.value=result;workConflict.value=false;resetWorkForm(result.state.candidates[workId.value]?workId.value:'')}
  catch(e){if(!disposed&&token===workEpoch)workError.value=message(e)}finally{if(!disposed&&token===workEpoch)workLoading.value=false}
}
function requireDuty(sha:string,ids:string[]){const source=selectableWorkSources.value.find(s=>s.analysis_sha256===sha);if(!source||!ids.length||ids.some(id=>!source.analysis.claims.some(c=>c.id===id&&['duty','goal','object'].includes(c.kind)))||!source.analysis.claims.some(c=>ids.includes(c.id)&&c.kind==='duty'))throw Error('请选择适用来源及至少一项具体职责证据')}
async function saveWork(){if(!work.value||!workCandidate.value||workRevision.value!==undefined||workSaving.value||workLoading.value||workConflict.value)return
  const token=workEpoch;workError.value='';workSaved.value=''
  try{const f=workForm.value;if(!f.reason.trim())throw Error('请填写维护原因');let operation:Record<string,any>;const analyses=new Set<string>()
    if(f.action==='describe'){if(!f.description.trim()||!f.question.trim()||!lines(f.unresolved).length)throw Error('请填写研究说明、研究问题和未决备注');operation={op:'describe',candidate_id:workId.value,expected_version:workCandidate.value.version,description:f.description.trim(),research_question:f.question.trim(),unresolved:lines(f.unresolved),reason:f.reason.trim()}}
    else if(f.action==='link'){requireDuty(f.sourceSha,f.workIds);analyses.add(f.sourceSha);operation={op:'link',candidate_id:workId.value,analysis_sha256:f.sourceSha,work_ids:[...f.workIds],reason:f.reason.trim()}}
    else{const relation=workRelations.value.find(r=>r.id===f.relationId);if(!relation)throw Error('请选择需要纠正的关系');operation={op:'correct',relation_id:relation.id,expected_sha256:work.value.relation_sha256s[relation.id],decision:f.decision,reason:f.reason.trim(),verification:null,replacement:null,counterevidence:[]}
      if(f.replace){requireDuty(f.sourceSha,f.workIds);analyses.add(f.sourceSha);operation.replacement={analysis_sha256:f.sourceSha,work_ids:[...f.workIds]}}
      if(f.counterSourceSha){if(!f.counterIds.length||f.counterIds.some(id=>!workClaims(f.counterSourceSha).some(c=>c.id===id)))throw Error('请选择反证的具体职责、目标或对象');analyses.add(f.counterSourceSha);operation.counterevidence=f.counterIds.map(id=>({analysis_sha256:f.counterSourceSha,claim_id:id}))}
    }
    const request={baseline:work.value.state.binding,operations:[operation],analysis_sha256s:[...analyses].sort()};const signature=JSON.stringify(request)
    if(workRetry?.signature!==signature)workRetry={signature,id:'work-'+crypto.randomUUID()}
    workSaving.value=true;const saved=await saveWorkCandidates({...request,batch_id:workRetry.id})
    if(disposed||token!==workEpoch)return;work.value=saved;resetWorkForm(workId.value);workSaved.value=`已保存研究版本 ${saved.state.binding.revision}；原运行快照保留。`
  }catch(e:any){if(!disposed&&token===workEpoch){workConflict.value=e?.response?.status===409;workError.value=workConflict.value?`版本冲突：${message(e)}。请重新读取当前版本后修改。`:message(e)}}finally{if(!disposed&&token===workEpoch)workSaving.value=false}
}
async function loadSkills(){const token=++listEpoch;skillListLoading.value=true;skillError.value='';try{const result=await getSkillCandidates();if(!disposed&&token===listEpoch)skills.value=result.items}catch(e){if(!disposed&&token===listEpoch)skillError.value=message(e)}finally{if(!disposed&&token===listEpoch)skillListLoading.value=false}}
async function loadSkill(id:string,version?:number){const token=++skillEpoch;skillId.value=id;skillVersion.value=version;skill.value=null;skillLoading.value=true;skillSaving.value=false;skillError.value='';skillSaved.value='';skillRetry=null
  try{const result=await getSkillCandidate(id,version);if(disposed||token!==skillEpoch)return;if(result.candidate.candidate_id!==id)throw Error('候选身份不一致');if(version!==undefined&&result.candidate.version!==version)throw Error('技能候选版本与所选历史不一致');skill.value=result;skillConflict.value=false;skillForm.value={action:'mark_disputed',reason:'',description:result.candidate.description||'',hypotheses:(result.candidate.competing_hypotheses||[]).join('\n'),sourceSha:''}}
  catch(e){if(!disposed&&token===skillEpoch)skillError.value=message(e)}finally{if(!disposed&&token===skillEpoch)skillLoading.value=false}
}
async function saveSkill(){if(!skill.value||skillVersion.value!==undefined||skillSaving.value||skillLoading.value||skillConflict.value)return;const token=skillEpoch,id=skillId.value;skillError.value='';skillSaved.value=''
  try{const f=skillForm.value;if(!f.reason.trim())throw Error('请填写维护原因');const request:Record<string,any>={expected_version:skill.value.candidate.version,action:f.action,reason:f.reason.trim()}
    if(f.action==='mark_disputed'){if(!lines(f.hypotheses).length)throw Error('争议至少需要一项不同解释');request.competing_hypotheses=lines(f.hypotheses)}
    if(f.action==='revise'){if(!skill.value.eligible_new_evidence.some(s=>s.analysis_sha256===f.sourceSha))throw Error('需要同一解释下尚未绑定的新证据');if(!f.description.trim())throw Error('请填写基于新证据的解释');Object.assign(request,{description:f.description.trim(),competing_hypotheses:lines(f.hypotheses),source_analysis_sha256:f.sourceSha})}
    const signature=JSON.stringify([id,request]);if(skillRetry?.signature!==signature)skillRetry={signature,id:'skill-'+crypto.randomUUID()}
    skillSaving.value=true;const result=await saveSkillCandidate(id,{...request,request_id:skillRetry.id});if(disposed||token!==skillEpoch)return;if(result.candidate.candidate_id!==id)throw Error('保存结果候选身份不一致');skill.value=result;skillRetry=null;skillSaved.value=`已保存技能候选 v${result.candidate.version}；后续分析使用维护后的投影。`;skillForm.value.reason='';skillForm.value.sourceSha='';if(skills.value)skills.value=skills.value.map(c=>c.candidate_id===id?result.candidate:c)
  }catch(e:any){if(!disposed&&token===skillEpoch){skillConflict.value=e?.response?.status===409;skillError.value=skillConflict.value?`版本冲突：${message(e)}。请重新读取当前版本后修改。`:message(e)}}finally{if(!disposed&&token===skillEpoch)skillSaving.value=false}
}
async function loadPending(){if(pendingSaving.value)return;const token=++pendingEpoch;pendingLoading.value=true;pendingError.value='';try{const result=await getPendingMaintenance();if(!disposed&&token===pendingEpoch){pending.value=result.items;closedMaintenance.value=result.closed||[]}}catch(e){if(!disposed&&token===pendingEpoch)pendingError.value=message(e)}finally{if(!disposed&&token===pendingEpoch)pendingLoading.value=false}}
function closedMaintenanceMessage(item:ClosedMaintenanceRecord){return `${item.kind==='work'?'工作候选':'技能候选'} ${item.candidate_id||item.id}：维护已结束但未完整完成（${item.status}）；${item.candidate_version_saved?'候选版本已保存':'候选版本未保存'}；投影绑定未记录（${item.projection_binding}）。原因：${item.reason}。历史与已保存候选保留。`}
async function closePending(item:PendingMaintenance){
  if(disposed||pendingSaving.value||pendingLoading.value||!pending.value?.some(p=>p.id===item.id&&p.can_close===true))return
  const reason=(pendingCloseReasons.value[item.id]||'').trim()
  pendingError.value='';pendingSaved.value=''
  if(!reason){pendingError.value='请填写结束旧版维护的原因';return}
  const token=++pendingEpoch;pendingSaving.value=item.id
  try{
    const result=await closeMaintenance(item.id,reason)
    if(disposed||token!==pendingEpoch)return
    closedMaintenance.value=[...closedMaintenance.value.filter(p=>p.id!==item.id),{...result,id:item.id,kind:item.kind,candidate_id:item.candidate_id}]
    pending.value=pending.value?.filter(p=>p.id!==item.id)||[];delete pendingCloseReasons.value[item.id]
    pendingSaving.value='';await loadPending()
  }catch(e){if(!disposed&&token===pendingEpoch)pendingError.value=message(e)}
  finally{if(!disposed&&(token===pendingEpoch||!pendingSaving.value))pendingSaving.value=''}
}
async function resumePending(item:PendingMaintenance){if(pendingSaving.value||!pending.value?.some(p=>p.id===item.id))return;const token=++pendingEpoch;pendingSaving.value=item.id;pendingError.value='';pendingSaved.value='';try{const result=await resumeMaintenance(item.id);if(disposed||token!==pendingEpoch)return;const version=item.kind==='work'?`研究版本 ${(result as WorkCandidates).state.binding.revision}`:`技能候选 v${(result as SkillCandidateDetail).candidate.version}`;pendingSaved.value=`已恢复并保存${version}。请重新读取当前候选查看结果。`;pending.value=pending.value?.filter(p=>p.id!==item.id)||[];pendingSaving.value='';await loadPending()}catch(e){if(!disposed&&token===pendingEpoch)pendingError.value=message(e)}finally{if(!disposed&&(token===pendingEpoch||!pendingSaving.value))pendingSaving.value=''}}
onUnmounted(()=>{disposed=true;workEpoch++;skillEpoch++;listEpoch++;pendingEpoch++})
</script>
<style scoped>
.surface{padding:22px;margin:18px 0;border:1px solid var(--line,#d9e2e7);border-radius:16px;background:var(--card,#fff)}.actions{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}.candidate-block{border-top:1px solid var(--line,#d9e2e7);margin-top:20px;padding-top:14px}.el-select{min-width:270px;max-width:100%}.el-form{max-width:820px;margin-top:20px}.source{border-left:3px solid #618ed2;padding:8px 16px;margin:14px 0}p{line-height:1.7}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:480px;overflow:auto;font-size:13px;background:var(--card-soft,#f8fafb);padding:12px}summary{cursor:pointer;color:var(--primary,#247ca2)}details{margin:12px 0}.binding,small{overflow-wrap:anywhere;color:var(--muted-strong,#69808e)}small{display:block}blockquote{white-space:pre-wrap;margin:8px 0}.el-checkbox-group{display:flex;flex-direction:column;align-items:flex-start}.el-checkbox{height:auto;white-space:normal;margin:8px 0}h2{font-size:19px}.el-alert{margin:12px 0}
</style>
