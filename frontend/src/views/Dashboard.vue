<template>
  <LayoutShell>
    <el-row :gutter="16">
      <el-col :span="6"><el-card>设备数量: {{ stats.devices }}</el-card></el-col>
      <el-col :span="6"><el-card>今日任务: {{ stats.todayTasks }}</el-card></el-col>
      <el-col :span="6"><el-card>成功任务: {{ stats.successTasks }}</el-card></el-col>
      <el-col :span="6"><el-card>失败任务: {{ stats.failedTasks }}</el-card></el-col>
    </el-row>
  </LayoutShell>
</template>

<script setup>
import { onMounted, reactive } from "vue";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const stats = reactive({
  devices: 0,
  todayTasks: 0,
  successTasks: 0,
  failedTasks: 0,
});

const load = async () => {
  const [deviceRes, taskRes] = await Promise.all([http.get("/devices"), http.get("/tasks")]);
  stats.devices = deviceRes.data.length;

  const today = new Date().toISOString().slice(0, 10);
  const tasks = taskRes.data || [];
  stats.todayTasks = tasks.filter((t) => String(t.start_time || "").startsWith(today)).length;
  stats.successTasks = tasks.filter((t) => t.failed === 0).length;
  stats.failedTasks = tasks.filter((t) => t.failed > 0).length;
};

onMounted(load);
</script>
