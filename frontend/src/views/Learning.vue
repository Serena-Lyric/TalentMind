<template>
  <section class="learning-page">
    <div class="empty-state">
      <div class="empty-icon">✦</div>
      <h1>学习路径暂未生成</h1>
      <p>请先完成简历解析；待 M4 提供 pathfinder 后，系统将在这里展示真实技能差距和学习路径。</p>
      <el-button type="primary" @click="router.push('/resume')">前往简历解析</el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.learning-page {
  max-width: 1440px;
  margin: auto;
}

.empty-state {
  min-height: 520px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #F0EBE3;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  text-align: center;
}

.empty-icon {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #FDE8E4;
  color: #D98B6E;
  font-size: 30px;
}

.empty-state h1 {
  margin: 8px 0 0;
  color: #3D3D3D;
  font-size: 22px;
}

.empty-state p {
  max-width: 520px;
  margin: 0 0 8px;
  color: #8C8C8C;
  font-size: 13px;
  line-height: 1.8;
}
</style>
