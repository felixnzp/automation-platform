<template>
  <el-container class="layout">
    <el-aside width="260px" class="sidebar">
      <div class="brand">
        <img class="brand-logo" src="/images/logo-white.png" alt="安室智能 Logo" />
        <div class="brand-text">安室智能 自动化运维平台</div>
      </div>

      <el-menu :default-active="active" router class="nav-menu">
        <el-menu-item index="/dashboard"><span class="menu-text">主页</span></el-menu-item>
        <el-menu-item index="/devices"><span class="menu-text">设备中心</span></el-menu-item>
        <el-menu-item index="/tasks/execute"><span class="menu-text">任务中心</span></el-menu-item>
        <el-menu-item index="/config-center"><span class="menu-text">配置中心</span></el-menu-item>
        <el-menu-item index="/tasks/history"><span class="menu-text">日志中心</span></el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">安室智能 自动化运维平台</div>
        <div class="header-right">
          <el-dropdown @command="onThemeChange">
            <el-button>主题：{{ themeLabel }}</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="system">跟随系统</el-dropdown-item>
                <el-dropdown-item command="light">浅色</el-dropdown-item>
                <el-dropdown-item command="dark">深色</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="danger" plain @click="logout">退出登录</el-button>
        </div>
      </el-header>
      <el-main>
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { applyTheme, getStoredTheme } from "../utils/theme";

const route = useRoute();
const router = useRouter();
const active = computed(() => {
  if (route.path.startsWith("/tasks/scheduled")) return "/tasks/execute";
  return route.path;
});

const modeText = {
  system: "跟随系统",
  light: "浅色",
  dark: "深色",
};

const themeMode = ref(getStoredTheme());
const themeLabel = computed(() => modeText[themeMode.value] || "跟随系统");

const onThemeChange = (mode) => {
  themeMode.value = mode;
  applyTheme(mode);
};

const logout = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("username");
  router.push("/login");
};
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.sidebar {
  background: var(--app-sidebar);
  border-right: 1px solid var(--app-border);
  padding: 18px 14px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden auto;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.sidebar::after {
  content: "";
  position: absolute;
  right: 0;
  top: 24px;
  bottom: 24px;
  width: 1px;
  background: linear-gradient(to bottom, transparent, rgba(72, 224, 255, 0.7), transparent);
}

.brand {
  margin-bottom: 18px;
  text-align: center;
}

.brand-logo {
  width: 148px;
  max-width: 100%;
  display: block;
  filter: drop-shadow(0 0 12px rgba(72, 224, 255, 0.45));
}

.brand-text {
  color: var(--app-sidebar-text);
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.35;
}

.nav-menu {
  background: transparent;
  border-right: none;
  width: 100%;
}

:deep(.nav-menu .el-menu-item) {
  display: flex;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 0 !important;
  color: var(--app-sidebar-text) !important;
  background: transparent !important;
}

.menu-text {
  position: relative;
  display: inline-block;
  padding-bottom: 2px;
}

.menu-text::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -3px;
  height: 2px;
  background: #2fdcff;
  transform: scaleX(0);
  transform-origin: center;
  transition: transform 0.28s ease;
}

:deep(.nav-menu .el-menu-item:hover .menu-text::after),
:deep(.nav-menu .el-menu-item.is-active .menu-text::after) {
  transform: scaleX(1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--app-border);
  background: rgba(6, 19, 38, 0.7);
  backdrop-filter: blur(6px);
}

.header-left {
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #e8f3ff;
}

.header-right {
  display: flex;
  gap: 10px;
}
</style>
