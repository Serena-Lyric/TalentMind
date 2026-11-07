<template>
  <div class="page graph-page"><GraphPanorama :panels-hidden="panelsHidden" :immersive="immersive" /></div>
</template>
<script setup lang="ts">
import { defineAsyncComponent, h, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { graphShortcut } from '../graph/graphShortcut'

const GraphPanorama = defineAsyncComponent({
  loader: () => import('../components/GraphPanorama.vue'),
  delay: 0,
  loadingComponent: { render: () => h('div', { class: 'graph-loading', role: 'status' }, '正在准备星云图谱…') },
  errorComponent: { render: () => h('div', { class: 'graph-loading', role: 'alert' }, [
    h('span', '图谱模块加载失败，请刷新页面重试。'),
  ]) },
})

const emit = defineEmits<{ (event: 'immersive-change', value: boolean): void }>()
const route = useRoute()
const panelsHidden = ref(false)
const immersive = ref(false)
let composing = false
function onCompositionStart() { composing = true }
function onCompositionEnd() { composing = false }
function onKeydown(event: KeyboardEvent) {
  if (route.name !== 'Graph') return
  const action = graphShortcut(event, composing)
  if (!action) return
  event.preventDefault()
  if (action === 'panels') panelsHidden.value = !panelsHidden.value
  else { immersive.value = !immersive.value; emit('immersive-change', immersive.value) }
}
onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('compositionstart', onCompositionStart)
  window.addEventListener('compositionend', onCompositionEnd)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('compositionstart', onCompositionStart)
  window.removeEventListener('compositionend', onCompositionEnd)
  emit('immersive-change', false)
})
</script>
<style scoped>
.graph-page { max-width: 1600px; height: calc(100vh - 36px); height: calc(100dvh - 36px); min-height: 620px; margin: 0 auto; }
.graph-page :deep(.nebula-page) { height: 100%; min-height: inherit; }
.graph-page :deep(.graph-loading) { min-height: inherit; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 18px; color: #c5d3ed; background: radial-gradient(ellipse at center, #152641, #080b17 65%); border-radius: 14px; }
.graph-page :deep(.graph-loading a) { color: #9cc5ff; }
@media (max-width: 800px) { .graph-page { min-height: 560px; } }
</style>
