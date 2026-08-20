<template>
  <el-container class="app-container">
    <el-aside width="214px" class="sidebar">
      <div class="logo">
        <div class="logo-mark">
          <el-icon :size="21"><Monitor /></el-icon>
        </div>
        <div>
          <span>应急指挥舱</span>
          <small>AI COMMAND</small>
        </div>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#0a1929"
        text-color="#a0cfff"
        active-text-color="#00d4ff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>指挥大屏</span>
        </el-menu-item>
        <el-menu-item index="/disasters">
          <el-icon><Warning /></el-icon>
          <span>灾情态势</span>
        </el-menu-item>
        <el-menu-item index="/rescue">
          <el-icon><UserFilled /></el-icon>
          <span>救援部署</span>
        </el-menu-item>
        <el-menu-item index="/materials">
          <el-icon><Box /></el-icon>
          <span>物资调度</span>
        </el-menu-item>
        <el-menu-item index="/evacuation">
          <el-icon><Van /></el-icon>
          <span>群众转移</span>
        </el-menu-item>
        <el-menu-item index="/ai-decision">
          <el-icon><Cpu /></el-icon>
          <span>AI决策</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style scoped>
.app-container {
  height: 100vh;
  background:
    radial-gradient(circle at 48% 18%, rgba(28, 126, 214, 0.18), transparent 30%),
    linear-gradient(135deg, #07111f 0%, #0a1729 45%, #08121f 100%);
}
.sidebar {
  background: linear-gradient(180deg, rgba(6, 18, 32, 0.98), rgba(8, 27, 47, 0.96));
  border-right: 1px solid rgba(62, 180, 255, 0.2);
  box-shadow: 10px 0 30px rgba(0, 0, 0, 0.28);
}
.logo {
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 0 18px;
  color: #d8f4ff;
  font-size: 17px;
  font-weight: bold;
  border-bottom: 1px solid rgba(62, 180, 255, 0.2);
}
.logo small {
  display: block;
  margin-top: 2px;
  color: #5fbef7;
  font-size: 10px;
  letter-spacing: 1.6px;
}
.logo-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(0, 212, 255, 0.55);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.18), rgba(35, 94, 180, 0.18));
  color: #65e4ff;
  box-shadow: inset 0 0 16px rgba(0, 212, 255, 0.12);
}
.main-content {
  padding: 0;
  background: transparent;
}
</style>
