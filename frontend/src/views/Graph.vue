<template>
  <div class="page graph-page"><LegacyGraph v-if="route.query.graphRenderer === 'legacy'" /><GraphPanorama v-else :panels-hidden="panelsHidden" :immersive="immersive" /></div>
</template>
<script setup lang="ts">
import GraphPanorama from '../components/GraphPanorama.vue'
import LegacyGraph from '../components/LegacyGraph.vue'
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { graphShortcut } from '../graph/graphShortcut'

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
@media (max-width: 800px) { .graph-page { min-height: 560px; } }
</style>
