<script setup lang="ts">
import { userStore } from '../lib/userStore'
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** plain：无框，用于左侧流程卡内 */
    variant?: 'card' | 'plain'
  }>(),
  { variant: 'card' },
)

const hint = computed(() => {
  const o = userStore.state.currentOutlineId
  const n = userStore.state.planTasks.length
  if (!o) return '尚未选定已保存的大纲，可先在「大纲」页确认或去私教生成。'
  if (n === 0) return '已有大纲，可在「计划」拉取今日任务。'
  return '今日侧栏会显示任务，完成率会同步到进度。'
})
</script>

<template>
  <p class="flow-hint" :class="{ 'flow-hint--plain': props.variant === 'plain' }" role="note">
    {{ hint }}
  </p>
</template>

<style scoped>
.flow-hint {
  margin: 0 0 1rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  color: var(--muted, #8b9cb3);
  line-height: 1.45;
  border-radius: 8px;
  background: var(--bg, #0f1419);
  border: 1px solid var(--border, #2d3a4d);
}
.flow-hint--plain {
  margin: 0 0 0.65rem;
  padding: 0;
  background: none;
  border: none;
  font-size: 0.8rem;
}
</style>
