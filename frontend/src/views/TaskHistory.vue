<template>
  <LayoutShell>
    <el-card>
      <el-table :data="tasks" border>
        <el-table-column prop="id" label="任务ID" width="80" />
        <el-table-column prop="task_type" label="任务类型" width="120" />
        <el-table-column prop="start_time" label="开始时间" />
        <el-table-column prop="end_time" label="结束时间" />
        <el-table-column prop="status" label="状态" width="140" />
        <el-table-column prop="success" label="成功" width="80" />
        <el-table-column prop="failed" label="失败" width="80" />
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button size="small" @click="showDetail(scope.row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="任务详情" width="860px">
      <el-table :data="detailRows" border>
        <el-table-column prop="device_name" label="设备名" />
        <el-table-column prop="device_ip" label="IP" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="message" label="结果" />
        <el-table-column prop="start_time" label="开始" />
        <el-table-column prop="end_time" label="结束" />
      </el-table>
    </el-dialog>
  </LayoutShell>
</template>

<script setup>
import { ref } from "vue";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const tasks = ref([]);
const detailVisible = ref(false);
const detailRows = ref([]);

const load = async () => {
  const { data } = await http.get("/tasks");
  tasks.value = data;
};

const showDetail = async (taskId) => {
  const { data } = await http.get(`/tasks/${taskId}`);
  detailRows.value = data.results || [];
  detailVisible.value = true;
};

load();
</script>
