<template>
  <div class="graph-page">
    <GraphPanorama />
  </div>
</template>

<script setup lang="ts">
import GraphPanorama from '../components/GraphPanorama.vue'
</script>

<style scoped>
.graph-page {
  max-width: 1440px;
  height: calc(100vh - 116px);
  min-height: 600px;
  margin: auto;
}
</style>