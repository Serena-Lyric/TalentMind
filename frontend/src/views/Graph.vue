<template>
  <div class="page graph-page"><GraphPanorama /></div>
</template>
<script setup lang="ts">
import GraphPanorama from '../components/GraphPanorama.vue'
</script>
<style scoped>
.graph-page { max-width: 1600px; height: calc(100vh - 36px); height: calc(100dvh - 36px); min-height: 620px; margin: 0 auto; }
.graph-page :deep(.nebula-page) { height: 100%; min-height: inherit; }
@media (max-width: 800px) { .graph-page { min-height: 560px; } }
</style>
