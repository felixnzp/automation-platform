<template>
  <LayoutShell>
    <el-card class="switch-card">
      <el-radio-group v-model="activeTab" @change="onTabChange">
        <el-radio-button label="instant">即时任务</el-radio-button>
        <el-radio-button label="planned">计划任务</el-radio-button>
      </el-radio-group>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <div class="header-row">
          <div class="section-title">计划任务</div>
          <el-button type="primary" @click="openCreateDialog">新增计划任务</el-button>
        </div>
      </template>

      <el-table :data="scheduledTasks" border>
        <el-table-column prop="name" label="任务名称" min-width="180" />
        <el-table-column label="任务类型" width="140">
          <template #default="scope">{{ taskTypeLabel(scope.row.task_type) }}</template>
        </el-table-column>
        <el-table-column label="目标对象" min-width="220">
          <template #default="scope">{{ targetText(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="执行周期" width="180">
          <template #default="scope">{{ cycleText(scope.row) }}</template>
        </el-table-column>
        <el-table-column prop="run_time" label="执行时间" width="110" />
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.enabled ? 'success' : 'info'">{{ scope.row.enabled ? "启用" : "禁用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" label="最近执行" width="180" />
        <el-table-column label="操作" width="260">
          <template #default="scope">
            <el-space>
              <el-button link type="primary" @click="openEditDialog(scope.row)">编辑</el-button>
              <el-button link type="success" @click="runOnce(scope.row)">执行一次</el-button>
              <el-button link type="danger" @click="removeTask(scope.row)">删除</el-button>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑计划任务' : '新增计划任务'" width="720px">
      <el-form label-width="110px">
        <el-form-item label="任务名称">
          <el-input v-model="form.name" placeholder="例如：每日服务器巡检" />
        </el-form-item>

        <el-form-item label="任务类型">
          <el-select v-model="form.task_type" style="width: 220px" @change="onFormTaskTypeChange">
            <el-option label="网络巡检" value="audit" />
            <el-option v-if="form.task_type === 'ntp'" label="NTP批量配置（已废弃）" value="ntp" disabled />
            <el-option label="服务器巡检" value="server_inspection" />
            <el-option label="服务器所属交换机检测" value="server_switch_detect" />
            <el-option label="SNMP配置（预留）" value="snmp" disabled />
          </el-select>
        </el-form-item>
        <el-alert
          v-if="form.task_type === 'ntp'"
          title="该任务类型已废弃，请在「配置中心 → NTP配置」中完成 NTP 配置"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />

        <el-form-item :label="isServerTask ? '目标服务器' : '目标设备'">
          <el-radio-group v-model="form.target_mode">
            <el-radio label="all">{{ isServerTask ? "全部服务器" : "全部设备" }}</el-radio>
            <el-radio label="group">按分组</el-radio>
            <el-radio label="custom">自定义选择</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.target_mode === 'group'" label="目标分组">
          <el-select v-model="form.target_group" style="width: 240px" placeholder="请选择分组">
            <el-option v-for="group in groups" :key="group" :label="group" :value="group" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.target_mode === 'custom'" :label="isServerTask ? '自定义服务器' : '自定义设备'">
          <el-select v-model="form.target_device_ids" multiple filterable style="width: 100%">
            <el-option v-for="item in selectableAssets" :key="item.id" :label="`${item.name}(${item.ip})`" :value="item.id" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">任务参数</el-divider>

        <template v-if="form.task_type === 'audit'">
          <el-form-item label="连接超时(秒)"><el-input-number v-model="params.audit.timeout" :min="5" :max="120" /></el-form-item>
          <el-form-item label="巡检模式">
            <el-select v-model="params.audit.mode" style="width: 220px">
              <el-option label="exec" value="exec" />
              <el-option label="shell" value="shell" />
            </el-select>
          </el-form-item>
        </template>

        <template v-else-if="form.task_type === 'server_inspection'">
          <el-form-item label="巡检项">
            <el-checkbox v-model="params.server_inspection.inspect_items.cpu">CPU</el-checkbox>
            <el-checkbox v-model="params.server_inspection.inspect_items.memory">内存</el-checkbox>
            <el-checkbox v-model="params.server_inspection.inspect_items.disk">磁盘</el-checkbox>
          </el-form-item>

          <el-form-item label="CPU 阈值">
            <el-input-number v-model="params.server_inspection.threshold_config.cpu_warning" :min="1" :max="100" />
            <span style="margin: 0 10px">告警</span>
            <el-input-number v-model="params.server_inspection.threshold_config.cpu_critical" :min="1" :max="100" />
            <span style="margin-left: 10px">严重</span>
          </el-form-item>

          <el-form-item label="内存 阈值">
            <el-input-number v-model="params.server_inspection.threshold_config.memory_warning" :min="1" :max="100" />
            <span style="margin: 0 10px">告警</span>
            <el-input-number v-model="params.server_inspection.threshold_config.memory_critical" :min="1" :max="100" />
            <span style="margin-left: 10px">严重</span>
          </el-form-item>

          <el-form-item label="磁盘 阈值">
            <el-input-number v-model="params.server_inspection.threshold_config.disk_warning" :min="1" :max="100" />
            <span style="margin: 0 10px">告警</span>
            <el-input-number v-model="params.server_inspection.threshold_config.disk_critical" :min="1" :max="100" />
            <span style="margin-left: 10px">严重</span>
          </el-form-item>
        </template>

        <template v-else-if="form.task_type === 'server_switch_detect'">
          <el-form-item label="检测选项">
            <el-checkbox v-model="params.server_switch_detect.force">强制重新检测</el-checkbox>
          </el-form-item>
        </template>

        <el-divider content-position="left">调度配置</el-divider>

        <el-form-item label="执行周期">
          <el-radio-group v-model="form.cycle_type">
            <el-radio label="daily">每天</el-radio>
            <el-radio label="weekly">每周</el-radio>
            <el-radio label="monthly">每月</el-radio>
            <el-radio label="cron">自定义 Cron（高级）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.cycle_type === 'cron'" label="Cron表达式">
          <el-input v-model="form.cron_expr" placeholder="例如：0 8 * * *" />
        </el-form-item>

        <el-form-item label="执行时间">
          <el-input v-model="form.run_time" style="width: 180px" placeholder="08:00" />
        </el-form-item>

        <el-form-item label="状态">
          <el-switch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-space>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :disabled="form.task_type === 'ntp'" @click="saveTask">保存</el-button>
        </el-space>
      </template>
    </el-dialog>
  </LayoutShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const router = useRouter();
const activeTab = ref("planned");
const scheduledTasks = ref([]);

const devices = ref([]);
const servers = ref([]);

const groups = ref([]);
const dialogVisible = ref(false);
const editingId = ref(null);

const form = reactive({
  name: "",
  task_type: "audit",
  target_mode: "all",
  target_group: "",
  target_device_ids: [],
  params: {},
  cycle_type: "daily",
  run_time: "08:00",
  cron_expr: "",
  enabled: true,
});

const params = reactive({
  audit: { timeout: 20, mode: "exec" },
  server_inspection: {
    inspect_items: { cpu: true, memory: true, disk: true },
    threshold_config: {
      cpu_warning: 80,
      cpu_critical: 90,
      memory_warning: 80,
      memory_critical: 90,
      disk_warning: 80,
      disk_critical: 90,
    },
  },
  server_switch_detect: {
    force: true,
    trigger: "schedule",
  },
});

const isServerTask = computed(() => ["server_inspection", "server_switch_detect"].includes(String(form.task_type || "")));
const isServerInspection = computed(() => form.task_type === "server_inspection");
const selectableAssets = computed(() => (isServerTask.value ? servers.value : devices.value) || []);

const refreshGroups = () => {
  const list = selectableAssets.value || [];
  groups.value = [...new Set(list.map((d) => d.group_name).filter(Boolean))].sort();
  if (form.target_mode === "group" && form.target_group && !groups.value.includes(form.target_group)) {
    form.target_group = "";
  }
};

const loadDevices = async () => {
  const { data } = await http.get("/devices", { params: { with_status: false } });
  devices.value = data || [];
  if (!isServerTask.value) refreshGroups();
};

const loadServers = async () => {
  const { data } = await http.get("/servers", { params: { with_status: false } });
  servers.value = data || [];
  if (isServerTask.value) refreshGroups();
};

const loadScheduledTasks = async () => {
  const { data } = await http.get("/tasks/schedules/list");
  scheduledTasks.value = data || [];
};

const onTabChange = (tab) => {
  if (tab === "instant") router.push("/tasks/execute");
};

const resetForm = () => {
  editingId.value = null;
  form.name = "";
  form.task_type = "audit";
  form.target_mode = "all";
  form.target_group = "";
  form.target_device_ids = [];
  form.cycle_type = "daily";
  form.run_time = "08:00";
  form.cron_expr = "";
  form.enabled = true;
  form.params = {};
};

const openCreateDialog = async () => {
  resetForm();
  dialogVisible.value = true;
  await onFormTaskTypeChange();
};

const openEditDialog = async (row) => {
  editingId.value = row.id;
  form.name = row.name || "";
  form.task_type = row.task_type || "audit";
  form.target_mode = row.target_mode || "all";
  form.target_group = row.target_group || "";
  form.target_device_ids = Array.isArray(row.target_device_ids) ? [...row.target_device_ids] : [];
  form.cycle_type = row.cycle_type || "daily";
  form.run_time = row.run_time || "08:00";
  form.cron_expr = row.cron_expr || "";
  form.enabled = Boolean(row.enabled);

  // Load related assets first, then apply params.
  await onFormTaskTypeChange();

  const savedParams = row.params || {};
  if (form.task_type === "audit") params.audit = { ...params.audit, ...(savedParams || {}) };
  if (form.task_type === "server_inspection") {
    params.server_inspection = {
      inspect_items: { ...params.server_inspection.inspect_items, ...(savedParams.inspect_items || {}) },
      threshold_config: { ...params.server_inspection.threshold_config, ...(savedParams.threshold_config || {}) },
    };
  }
  if (form.task_type === "server_switch_detect") {
    params.server_switch_detect = { ...params.server_switch_detect, ...(savedParams || {}) };
  }

  dialogVisible.value = true;
};

const onFormTaskTypeChange = async () => {
  // reload selectable list
  if (isServerTask.value) {
    await loadServers();
  } else {
    await loadDevices();
  }
  refreshGroups();

  // reset selection to avoid mixing ids
  form.target_mode = "all";
  form.target_group = "";
  form.target_device_ids = [];
};

const currentParams = computed(() => {
  if (form.task_type === "server_inspection") return params.server_inspection;
  if (form.task_type === "server_switch_detect") return params.server_switch_detect;
  return params.audit;
});

const buildPayload = () => ({
  name: String(form.name || "").trim(),
  task_type: form.task_type,
  target_mode: form.target_mode,
  target_group: form.target_group,
  target_device_ids: form.target_device_ids,
  params: currentParams.value,
  cycle_type: form.cycle_type,
  run_time: form.run_time,
  cron_expr: form.cron_expr,
  enabled: form.enabled,
});

const saveTask = async () => {
  if (!String(form.name || "").trim()) {
    ElMessage.warning("请输入任务名称");
    return;
  }

  try {
    if (editingId.value) {
      await http.put(`/tasks/schedules/${editingId.value}`, buildPayload());
      ElMessage.success("计划任务已更新");
    } else {
      await http.post("/tasks/schedules", buildPayload());
      ElMessage.success("计划任务已创建");
    }
    dialogVisible.value = false;
    await loadScheduledTasks();
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "保存失败");
  }
};

const runOnce = async (row) => {
  try {
    const { data } = await http.post(`/tasks/schedules/${row.id}/run-once`);
    ElMessage.success(`任务已触发，任务ID: ${data.task_id}`);
    await loadScheduledTasks();
    router.push("/tasks/execute");
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "执行失败");
  }
};

const removeTask = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除计划任务【${row.name}】吗？`, "提示", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch (_cancel) {
    return;
  }

  try {
    await http.delete(`/tasks/schedules/${row.id}`);
    ElMessage.success("计划任务已删除");
    await loadScheduledTasks();
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "删除失败");
  }
};

const taskTypeLabel = (value) => {
  if (value === "audit") return "网络巡检";
  if (value === "ntp") return "NTP批量配置（已废弃）";
  if (value === "server_inspection") return "服务器巡检";
  if (value === "server_switch_detect") return "服务器所属交换机检测";
  return value || "-";
};

const targetText = (row) => {
  const isServer = ["server_inspection", "server_switch_detect"].includes(String(row.task_type || ""));
  if (row.target_mode === "all") return isServer ? "全部服务器" : "全部设备";
  if (row.target_mode === "group") return `按分组：${row.target_group || "-"}`;
  const count = Array.isArray(row.target_device_ids) ? row.target_device_ids.length : 0;
  return `自定义选择（${count}台）`;
};

const cycleText = (row) => {
  const map = { daily: "每天", weekly: "每周", monthly: "每月", cron: "自定义 Cron" };
  if (row.cycle_type === "cron" && row.cron_expr) return `Cron: ${row.cron_expr}`;
  return map[row.cycle_type] || row.cycle_type;
};

onMounted(async () => {
  await Promise.all([loadDevices(), loadServers(), loadScheduledTasks()]);
  refreshGroups();
});
</script>

<style scoped>
.section-title {
  font-weight: 700;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.switch-card {
  margin-bottom: 10px;
}
</style>
