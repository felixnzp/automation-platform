<template>
  <el-container class="layout">
    <el-aside width="220px" class="sidebar">
      <h3>AutoOps</h3>
      <el-menu :default-active="active" router>
        <el-menu-item index="/dashboard">Dashboard</el-menu-item>
        <el-menu-item index="/devices">Device List</el-menu-item>
        <el-menu-item index="/tasks/execute">Task Execute</el-menu-item>
        <el-menu-item index="/tasks/history">Task History</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <el-button type="danger" plain @click="logout">Logout</el-button>
      </el-header>
      <el-main>
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const active = computed(() => route.path);

const logout = () => {
  localStorage.removeItem("token");
  router.push("/login");
};
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.sidebar {
  background: #0d2a4a;
  color: #fff;
  padding: 16px;
}

.sidebar h3 {
  color: #fff;
  margin-bottom: 20px;
}

.header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  border-bottom: 1px solid #eee;
}
</style>
