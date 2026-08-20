<template>
  <div class="section-header">
    <span class="step-badge">{{ step }}</span>
    <div>
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  step: { type: [String, Number], required: true },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<style scoped>
.section-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 16px;
}

.step-badge {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: white;
  font-size: 14px;
  font-weight: 700;
  border-radius: 8px;
}

.section-header h2 {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 2px;
}

.section-header p {
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
