<template>
  <div class="run-console" :class="{ active: visible }">
    <div class="console-header">
      <div class="console-title">
        <span class="dot" :class="statusClass"></span>
        <span>{{ statusText }}</span>
      </div>
      <div class="console-actions">
        <button v-if="logs.length" class="btn-sm" @click="emit('clear')">清空</button>
        <button class="btn-sm" @click="emit('close')">收起</button>
      </div>
    </div>
    <pre ref="logEl" class="console-body">{{ logs.join('') || placeholder }}</pre>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  logs: { type: Array, default: () => [] },
  running: { type: Boolean, default: false },
  error: { type: String, default: null },
})

const emit = defineEmits(['close', 'clear'])

const logEl = ref(null)

const statusText = computed(() => {
  if (props.running) return '算法运行中...'
  if (props.error) return '运行失败'
  if (props.logs.length) return '运行完成'
  return '等待运行'
})

const statusClass = computed(() => {
  if (props.running) return 'running'
  if (props.error) return 'error'
  if (props.logs.length) return 'done'
  return 'idle'
})

const placeholder = computed(() =>
  props.visible ? '运行日志将在此显示...\n' : ''
)

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
)
</script>

<style scoped>
.run-console {
  margin-bottom: 20px;
  background: #0a0e14;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  display: none;
}

.run-console.active {
  display: block;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

.console-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary);
}

.dot.running {
  background: var(--warning);
  animation: pulse 1s infinite;
}

.dot.done {
  background: var(--success);
}

.dot.error {
  background: var(--danger);
}

@keyframes pulse {
  50% { opacity: 0.4; }
}

.console-actions {
  display: flex;
  gap: 8px;
}

.btn-sm {
  padding: 4px 10px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.btn-sm:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}

.console-body {
  margin: 0;
  padding: 14px 16px;
  max-height: 320px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.55;
  color: #a8b8cc;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
