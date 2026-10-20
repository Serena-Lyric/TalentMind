<template>
  <aside class="real-source-panel panel-glass" aria-label="原始 JD 证据" tabindex="0">
    <button type="button" class="close" aria-label="关闭原文" @click="$emit('close')">×</button>
    <h3>原始 JD · {{ record.payload.job_title }}</h3>
    <p>来源 {{ record.payload.source }} · JD ID {{ record.jd_id }}</p>
    <p>数据集 {{ record.namespace }}<br />内容指纹 {{ record.fingerprint }}</p>
    <p>采集观察时间 {{ record.observation || '未提供' }}（不是发布时间）</p>
    <p>原始来源 {{ record.payload.source_detail || '未提供' }}</p>
    <p>筛选 {{ record.screening.validity }} / {{ record.screening.scope_status || '未判断' }}<br />{{ record.screening.reason_codes?.join('、') }}</p>
    <p v-if="quote">本次关系证据：<mark>{{ quote }}</mark></p>
    <p>程序仅核对原文位置；未进行人工语义审核。岗位分类未发布。</p>
    <details><summary>M2 五态、冲突、组合及治理完整记录</summary><pre>{{ JSON.stringify(record.governance, null, 2) }}</pre></details>
    <h4>原始正文</h4><pre>{{ record.payload.raw_text || '原始正文为空，未补造内容' }}</pre>
    <details><summary>全部原始字段</summary><pre>{{ JSON.stringify(record.payload, null, 2) }}</pre></details>
  </aside>
</template>
<script setup lang="ts">
import type { SourceRecord } from '../graph/realSnapshot'
defineProps<{record:SourceRecord;quote?:string}>()
defineEmits<{(event:'close'):void}>()
</script>
<style scoped>
.real-source-panel{position:absolute;z-index:25;right:18px;top:65px;width:420px;max-width:calc(100% - 36px);max-height:calc(100% - 95px);overflow:auto;padding:20px;color:#dce8f5;background:rgba(9,18,35,.97);border:1px solid #52799c;border-radius:14px;box-sizing:border-box}.close{float:right}p{font-size:12px;line-height:1.7;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.6}h3{padding-right:22px}mark{color:#ecf4ff;background:#234c70}button{cursor:pointer}summary{cursor:pointer;font-size:12px}
</style>
