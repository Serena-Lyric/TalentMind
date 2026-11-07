<template>
  <section class="role-research">
    <h3>岗位归属研究</h3>
    <template v-if="research?.schema_version==='m2-role-research-1'">
      <p>{{label(research.status)}} · {{label(research.evidence_kind)}}。局部职责支持不等于整岗等价；研究候选不成为正式职业或学习目标。</p>
      <p class="binding">方法 {{research.method_version}} · 研究摘要 {{research.result_sha256}}<br />来源分析 {{research.source_analysis_sha256}} · 知识 {{research.knowledge_sha256}}</p>
      <div class="axes"><article v-for="(name,key) in axisNames" :key="key"><h4>{{name}} · {{label(research.axes?.[key]?.status || 'unknown')}}</h4><p>选定：{{(research.axes?.[key]?.selected_values || []).join('、') || '未选定'}}</p><ul v-if="research.axes?.[key]?.candidates?.length"><li v-for="(candidate,index) in research.axes[key].candidates" :key="index">{{candidate.value || candidate.name || candidate.role_id}} <small>{{label(candidate.maturity || 'candidate')}} · 依据事实 {{(candidate.claim_ids || []).join('、') || '见原研究记录'}}</small></li></ul><p v-else>没有已保存候选。</p><p>{{label(research.axes?.[key]?.reason || 'unknown')}}</p></article></div>
      <h4>检查覆盖与未执行项</h4><dl class="coverage"><div v-for="(name,key) in coverageNames" :key="key"><dt>{{name}}</dt><dd>{{research.coverage?.[key] ?? '未知'}}</dd></div></dl>
      <h4>局部职责支持</h4><p v-if="!research.local_supports?.length">本次没有已保存的局部支持；不能据此推断原文没有相关职责。</p>
      <article v-for="(support,index) in research.local_supports || []" :key="index" class="support"><p><strong>{{claimText(support.claim_id)}}</strong> → {{support.role_id}} / {{support.reference_id}}</p><p>{{label(support.state || 'research_candidates')}} · {{label(support.importance || 'unknown')}}</p><p v-if="support.matched_aspects?.length">相符方面：{{support.matched_aspects.map((aspect:any)=>`${aspect.action} / ${aspect.object}`).join('；')}}</p><blockquote v-for="(e,i) in support.source_evidence || []" :key="i">{{e.quote}}<small>来源原文 {{e.field}} [{{e.start}}, {{e.end}})</small></blockquote><details v-if="support.reference_evidence?.length"><summary>参照依据</summary><blockquote v-for="(e,i) in support.reference_evidence" :key="i">{{e.quote}}<small>{{e.source_id || e.field}}</small></blockquote></details></article>
      <h4>来源职责与未覆盖工作</h4><ul><li v-for="(source,index) in research.source_work || []" :key="index">{{claimText(source.claim_id)}} · {{source.core===true?'核心职责':source.core===false?'辅助职责':'核心性未确定'}}</li></ul><ul v-if="research.uncovered_work?.length"><li v-for="(item,index) in research.uncovered_work" :key="index">{{claimText(item.claim_id)}}：{{label(item.reason)}}</li></ul><p v-else>本次未列出未覆盖职责；完整边界仍见限制。</p>
      <h4>知识缺口与限制</h4><ul><li v-for="(item,index) in [...(research.knowledge_gaps || []),...(research.limitations || [])]" :key="index">{{item}}</li></ul>
    </template>
    <p v-else>本版本未保存新版岗位研究明细。原状态：{{label(research?.status || 'unknown')}}；{{research?.reason || '未提供原因'}}。没有按当前知识重算历史。</p>
    <details><summary>完整岗位研究记录</summary><pre>{{JSON.stringify(research ?? null,null,2)}}</pre></details>
  </section>
</template>
<script setup lang="ts">
import type {Claim} from '../api/m2'
const props=defineProps<{research?:Record<string,any>|null;claims:Claim[]}>()
const axisNames={family:'职业大类',canonical_job:'标准岗位',technology_tracks:'技术方向',seniority:'岗位级别'}
const coverageNames={pool_pairs:'参照候选对',selected_pairs:'已选择',checked_pairs:'已检查',unchecked_pairs:'未检查',pending_pairs:'等待检查',failed_pairs:'检查失败'}
function claimText(id:string){return props.claims.find(c=>c.id===id)?.text || id}
function label(value:string){return ({bounded_research_completed:'有限职责研究已执行',bounded_offline_rules:'离线有界规则',model_research_recorded:'已保存模型研究',saved_model_results:'已保存模型结果',research_candidates:'研究候选',unresolved:'未决',not_evaluated:'未评价',unknown:'未知',unavailable:'不可用',candidate:'候选',formal:'正式参照知识',test:'测试参照知识',core:'核心职责',auxiliary:'辅助职责',bounded_source_supported:'有限来源方面支持',no_supported_task_aspect:'没有得到有限职责方面支持',not_checked:'尚未检查',no_versioned_reference:'缺少版本化参照'} as Record<string,string>)[value] || value}
</script>
<style scoped>
.axes{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.axes article,.support{border:1px solid var(--line,#d9e2e7);padding:12px;border-radius:8px}.support{margin:12px 0}.coverage{display:flex;gap:20px;flex-wrap:wrap}.coverage dd{margin:5px 0;font-weight:600}p,li{line-height:1.7}.binding,small{overflow-wrap:anywhere;color:var(--muted-strong,#69808e)}small{display:block}h4{margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:480px;overflow:auto;font-size:13px}blockquote{margin:10px 0;border-left:3px solid #618ed2;padding:8px 12px;white-space:pre-wrap}summary{cursor:pointer;color:var(--primary,#247ca2)}
</style>
