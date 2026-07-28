<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <div class="logo">WR</div>
        <div>
          <div class="brand-title">Work Report</div>
          <div class="brand-sub">周报管理</div>
        </div>
      </div>
      <el-menu
        :default-active="active"
        router
        background-color="#1f2a44"
        text-color="#c0c4cc"
        active-text-color="#ffffff"
        class="menu"
      >
        <el-menu-item index="/">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/runs">
          <el-icon><List /></el-icon>
          <span>运行记录</span>
        </el-menu-item>
        <el-menu-item index="/config">
          <el-icon><Setting /></el-icon>
          <span>系统配置</span>
        </el-menu-item>
        <el-menu-item index="/project-names">
          <el-icon><Collection /></el-icon>
          <span>项目名称</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-title">{{ title }}</div>
        <div class="muted">GitLab → LLM → 钉钉</div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const active = computed(() => {
  if (route.path.startsWith("/runs")) return route.path === "/runs" ? "/runs" : "/runs";
  return route.path;
});
const title = computed(() => {
  const map: Record<string, string> = {
    dashboard: "仪表盘",
    runs: "运行记录",
    "run-detail": "运行详情",
    config: "系统配置",
    "project-names": "项目名称",
  };
  return map[String(route.name)] || "Work Report";
});
</script>

<style scoped>
.layout {
  height: 100%;
}
.aside {
  background: #1f2a44;
  color: #fff;
  display: flex;
  flex-direction: column;
}
.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 18px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.logo {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.brand-title {
  font-weight: 700;
}
.brand-sub {
  font-size: 12px;
  opacity: 0.7;
}
.menu {
  border-right: none;
  flex: 1;
}
.header {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
}
.main {
  padding: 20px;
}
</style>
