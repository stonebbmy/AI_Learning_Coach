<script setup lang="ts">
interface Task {
  task_id?: number
  db_id?: number
  description: string
  estimated_time?: string
  status: string
}

interface PlanPayload {
  tasks: Task[]
}

const props = defineProps<{
  payload: PlanPayload
}>()

const emit = defineEmits<{
  taskDone: [taskId: number, status: string]
}>()

const done = (t: Task) => ['已完成', 'done', 'DONE', 'completed'].includes(t.status)
</script>

<template>
  <div class="plan-card">
    <div class="plan-card__header">
      <span class="plan-card__badge">📅 今日计划</span>
      <span class="plan-card__progress">
        {{ payload.tasks.filter(done).length }} / {{ payload.tasks.length }} 已完成
      </span>
    </div>

    <ul class="plan-card__tasks">
      <li
        v-for="task in payload.tasks"
        :key="task.task_id ?? task.description"
        class="plan-card__task"
        :class="{ 'is-done': done(task) }"
      >
        <button
          class="plan-card__check"
          :class="{ 'is-done': done(task) }"
          @click.stop="
            emit('taskDone', task.db_id ?? task.task_id ?? 0, done(task) ? '待开始' : '已完成')
          "
        >
          {{ done(task) ? '✓' : '' }}
        </button>
        <span class="plan-card__task-desc">{{ task.description }}</span>
        <span v-if="task.estimated_time" class="plan-card__task-time">
          {{ task.estimated_time }}
        </span>
      </li>
    </ul>

    <div class="plan-card__progress-bar">
      <div
        class="plan-card__progress-fill"
        :style="{
          width:
            payload.tasks.length > 0
              ? (payload.tasks.filter(done).length / payload.tasks.length) * 100 + '%'
              : '0%',
        }"
      />
    </div>
  </div>
</template>

<style scoped>
.plan-card {
  background: var(--card-bg, #1e2233);
  border: 1px solid var(--border, #2e3450);
  border-radius: 12px;
  padding: 1.25rem;
  margin: 0.5rem 0;
  width: 100%;
}
.plan-card__header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.plan-card__badge {
  background: #6b3b10;
  color: #fbbf24;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 600;
}
.plan-card__progress {
  font-size: 0.82rem;
  color: var(--muted, #8899cc);
  margin-left: auto;
}
.plan-card__tasks {
  list-style: none;
  padding: 0;
  margin: 0 0 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.plan-card__task {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.6rem;
  background: var(--input-bg, #161924);
  border-radius: 6px;
  transition: opacity 0.2s;
}
.plan-card__task.is-done {
  opacity: 0.55;
}
.plan-card__check {
  width: 20px;
  height: 20px;
  border: 2px solid #5b72e8;
  border-radius: 4px;
  background: transparent;
  color: #6ee7b7;
  font-size: 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}
.plan-card__check.is-done {
  background: #22c55e;
  border-color: #22c55e;
}
.plan-card__task-desc {
  flex: 1;
  font-size: 0.86rem;
  color: var(--text, #e0e6f7);
}
.plan-card__task-time {
  font-size: 0.75rem;
  color: var(--muted, #8899cc);
  flex-shrink: 0;
}
.plan-card__progress-bar {
  height: 4px;
  background: var(--border, #2e3450);
  border-radius: 2px;
  overflow: hidden;
}
.plan-card__progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b4db8, #22c55e);
  border-radius: 2px;
  transition: width 0.4s ease;
}
</style>
