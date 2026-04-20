import { createRouter, createWebHistory } from 'vue-router'

const HomeView = () => import('../views/HomeView.vue')
const OutlineView = () => import('../views/OutlineView.vue')
const KnowledgeView = () => import('../views/KnowledgeView.vue')
const ChatView = () => import('../views/ChatView.vue')
const PlanView = () => import('../views/PlanView.vue')
const AgentChatView = () => import('../views/AgentChatView.vue')

export default createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/outline', name: 'outline', component: OutlineView },
    { path: '/knowledge', name: 'knowledge', component: KnowledgeView },
    { path: '/chat', name: 'chat', component: ChatView },
    { path: '/agent', name: 'agent', component: AgentChatView },
    { path: '/plan', name: 'plan', component: PlanView },
  ],
})
