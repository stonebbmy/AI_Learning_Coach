import { createRouter, createWebHistory } from 'vue-router'

const TutorView = () => import('../views/TutorView.vue')
const HomeView = () => import('../views/HomeView.vue')
const OutlineView = () => import('../views/OutlineView.vue')
const KnowledgeView = () => import('../views/KnowledgeView.vue')
const ChatView = () => import('../views/ChatView.vue')
const PlanView = () => import('../views/PlanView.vue')
const AgentChatView = () => import('../views/AgentChatView.vue')
const MetricsView = () => import('../views/MetricsView.vue')
const EvalView = () => import('../views/EvalView.vue')
const ProgressView = () => import('../views/ProgressView.vue')

export default createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'tutor', component: TutorView },          // 私教页设为默认首页
    { path: '/home', name: 'home', component: HomeView },
    { path: '/outline', name: 'outline', component: OutlineView },
    { path: '/knowledge', name: 'knowledge', component: KnowledgeView },
    { path: '/chat', name: 'chat', component: ChatView },
    { path: '/agent', name: 'agent', component: AgentChatView },
    { path: '/plan', name: 'plan', component: PlanView },
    { path: '/progress', name: 'progress', component: ProgressView },
    { path: '/metrics', name: 'metrics', component: MetricsView },
    { path: '/eval', name: 'eval', component: EvalView },
  ],
})
