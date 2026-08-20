import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue')
  },
  {
    path: '/disasters',
    name: 'Disasters',
    component: () => import('../views/DisasterView.vue')
  },
  {
    path: '/rescue',
    name: 'Rescue',
    component: () => import('../views/RescueView.vue')
  },
  {
    path: '/materials',
    name: 'Materials',
    component: () => import('../views/MaterialView.vue')
  },
  {
    path: '/evacuation',
    name: 'Evacuation',
    component: () => import('../views/EvacuationView.vue')
  },
  {
    path: '/ai-decision',
    name: 'AIDecision',
    component: () => import('../views/AIDecisionView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
