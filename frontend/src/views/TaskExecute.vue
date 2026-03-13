<template>
  <LayoutShell>
    <el-card>
      <el-form label-width="120px">
        <el-form-item label="选择设备">
          <el-select v-model="selected" multiple filterable style="width: 500px">
            <el-option v-for="item in devices" :key="item.id" :value="item.id" :label="`${item.name}(${item.ip})`" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">NTP 参数</el-divider>
        <el-form-item label="时区">
          <el-input v-model="ntp.timezone" style="width: 180px" />
        </el-form-item>
        <el-form-item label="偏移">
          <el-input v-model="ntp.offset" style="width: 180px" />
        </el-form-item>
        <el-form-item label="NTP 服务器">
          <el-input v-model="ntp.ntp_server" style="width: 240px" />
        </el-form-item>

        <el-divider content-position="left">SNMP 参数</el-divider>
        <el-form-item label="Community">
          <el-input v-model="snmp.community" style="width: 240px" />
        </el-form-item>

        <el-space>
          <el-button type="primary" @click="runAudit">执行巡检</el-button>
          <el-button type="success" @click="runNtp">配置 NTP</el-button>
          <el-button type="warning" @click="runSnmp">配置 SNMP</el-button>
        </el-space>
      </el-form>
    </el-card>
  </LayoutShell>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const devices = ref([]);
const selected = ref([]);
const ntp = reactive({ timezone: "BJ", offset: "08:00:00", ntp_server: "10.18.101.2" });
const snmp = reactive({ community: "public" });

const loadDevices = async () => {
  const { data } = await http.get("/devices");
  devices.value = data;
};

const ensureSelection = () => {
  if (!selected.value.length) {
    ElMessage.warning("请先选择设备");
    return false;
  }
  return true;
};

const runAudit = async () => {
  if (!ensureSelection()) return;
  const { data } = await http.post("/tasks/audit", { devices: selected.value });
  ElMessage.success(`巡检任务已完成，任务ID: ${data.id}`);
};

const runNtp = async () => {
  if (!ensureSelection()) return;
  const { data } = await http.post("/tasks/ntp", {
    devices: selected.value,
    ...ntp,
  });
  ElMessage.success(`NTP任务已完成，任务ID: ${data.id}`);
};

const runSnmp = async () => {
  if (!ensureSelection()) return;
  const { data } = await http.post("/tasks/snmp", {
    devices: selected.value,
    ...snmp,
  });
  ElMessage.success(`SNMP任务已完成，任务ID: ${data.id}`);
};

onMounted(loadDevices);
</script>
