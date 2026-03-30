<template>
  <LayoutShell>
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="card-title">日志中心</div>
          <el-space>
            <el-button @click="exportCurrent('csv')">导出 CSV</el-button>
            <el-button @click="exportCurrent('txt')">导出 TXT</el-button>
          </el-space>
        </div>
      </template>

      <el-radio-group v-model="activeTab" class="tab-switch">
        <el-radio-button label="tasks">任务日志</el-radio-button>
        <el-radio-button label="alerts">告警中心</el-radio-button>
      </el-radio-group>

      <template v-if="activeTab === 'tasks'">
        <div class="toolbar">
          <el-select v-model="taskFilters.taskType" placeholder="任务类型" clearable style="width: 150px">
            <el-option label="网络巡检" value="audit" />
            <el-option label="SNMP配置" value="snmp" />
          </el-select>

          <el-select v-model="taskFilters.status" placeholder="任务状态" clearable style="width: 150px">
            <el-option label="成功" value="success" />
            <el-option label="部分失败" value="partial_failed" />
            <el-option label="失败" value="failed" />
            <el-option label="执行中" value="running" />
            <el-option label="未检测" value="unknown" />
          </el-select>

          <el-date-picker
            v-model="taskFilters.timeRange"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            range-separator="至"
            style="width: 360px"
          />

          <el-input v-model="taskFilters.keyword" placeholder="搜索任务ID/任务名称/设备名" clearable style="width: 280px" />
          <el-button type="primary" @click="loadTasks">刷新</el-button>
          <el-button @click="resetTaskFilters">重置</el-button>
        </div>

        <el-table :data="filteredTasks" border row-class-name="log-row" class="log-table">
          <el-table-column prop="id" label="任务ID" width="90" />
          <el-table-column label="任务类型" width="130">
            <template #default="scope">{{ taskTypeText(scope.row.task_type) }}</template>
          </el-table-column>
          <el-table-column prop="start_time" label="开始时间" min-width="160" />
          <el-table-column prop="end_time" label="结束时间" min-width="160" />
          <el-table-column label="状态" width="150">
            <template #default="scope">
              <el-tag :type="taskStatusMeta(scope.row).type" effect="dark" class="status-tag">
                {{ taskStatusMeta(scope.row).icon }} {{ taskStatusMeta(scope.row).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="success" label="成功" width="80" />
          <el-table-column prop="failed" label="失败" width="80" />
          <el-table-column label="操作" width="200">
            <template #default="scope">
              <el-space>
                <el-button size="small" @click="showDetail(scope.row.id)">查看</el-button>
                <el-button v-if="isFailedTask(scope.row)" size="small" type="warning" @click="retryTask(scope.row)">重试任务</el-button>
              </el-space>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else>
        <div class="toolbar">
          <el-select v-model="alertFilters.sourceType" placeholder="告警来源" clearable style="width: 150px">
            <el-option label="服务器巡检" value="server" />
            <el-option label="网络巡检" value="network" />
          </el-select>

          <el-select v-model="alertFilters.severity" placeholder="告警等级" clearable style="width: 150px">
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="CRITICAL" value="CRITICAL" />
          </el-select>

          <el-select v-model="alertFilters.status" placeholder="告警状态" clearable style="width: 150px">
            <el-option label="NEW" value="NEW" />
            <el-option label="ACK" value="ACK" />
            <el-option label="RECOVERED" value="RECOVERED" />
            <el-option label="CLOSED" value="CLOSED" />
          </el-select>

          <el-input v-model="alertFilters.keyword" placeholder="搜索名称/IP/标题/内容" clearable style="width: 300px" />
          <el-button type="primary" @click="loadAlerts">刷新</el-button>
          <el-button @click="resetAlertFilters">重置</el-button>
        </div>

        <div class="toolbar toolbar-compact">
          <el-button type="warning" :disabled="!selectedAlertIds.length" @click="bulkUpdateAlerts('ACK')">批量 ACK</el-button>
          <el-button type="danger" :disabled="!selectedAlertIds.length" @click="bulkUpdateAlerts('CLOSED')">批量关闭</el-button>
          <div class="selection-hint">已选 {{ selectedAlertIds.length }} 条告警</div>
        </div>

        <el-table :data="filteredAlerts" border class="log-table" @selection-change="handleAlertSelectionChange">
          <el-table-column type="selection" width="52" />
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="等级" width="120">
            <template #default="scope">
              <el-tag :type="alertSeverityMeta(scope.row.severity).type" effect="dark" class="status-tag">
                {{ alertSeverityMeta(scope.row.severity).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="scope">
              <el-tag :type="alertStatusMeta(scope.row.status).type">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="120">
            <template #default="scope">{{ scope.row.source_type === "server" ? "服务器巡检" : "网络巡检" }}</template>
          </el-table-column>
          <el-table-column prop="source_name" label="对象名称" min-width="140" />
          <el-table-column prop="source_ip" label="IP地址" min-width="130" />
          <el-table-column prop="metric_type" label="指标" width="100" />
          <el-table-column prop="title" label="告警标题" min-width="220" />
          <el-table-column prop="message" label="告警内容" min-width="260" />
          <el-table-column prop="last_triggered_at" label="最近触发时间" min-width="170" />
          <el-table-column label="通知结果" min-width="220">
            <template #default="scope">{{ scope.row.notify_result || "-" }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-dialog v-model="detailVisible" title="详细日志" width="980px">
      <el-table :data="detailRows" border height="480">
        <el-table-column prop="device_name" label="设备名" min-width="140" />
        <el-table-column prop="device_ip" label="IP" width="140" />
        <el-table-column label="状态" width="120">
          <template #default="scope">{{ resultStatusText(scope.row.status) }}</template>
        </el-table-column>
        <el-table-column prop="message" label="日志信息" min-width="260" />
        <el-table-column prop="start_time" label="开始时间" width="160" />
        <el-table-column prop="end_time" label="结束时间" width="160" />
      </el-table>
    </el-dialog>
  </LayoutShell>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const router = useRouter();
const activeTab = ref("tasks");

const tasks = ref([]);
const alerts = ref([]);
const selectedAlertIds = ref([]);
const detailVisible = ref(false);
const detailRows = ref([]);
const taskDetailsCache = ref({});

const taskFilters = reactive({
  taskType: "",
  status: "",
  timeRange: [],
  keyword: "",
});

const alertFilters = reactive({
  sourceType: "",
  severity: "",
  status: "",
  keyword: "",
});

const taskTypeMap = {
  audit: "网络巡检",
  ntp: "NTP批量配置（已废弃）",
  snmp: "SNMP配置",
};

const taskStatusMap = {
  success: "成功",
  partial_failed: "部分失败",
  failed: "失败",
  running: "执行中",
  unknown: "未检测",
};

const resultStatusMap = {
  success: "成功",
  failed: "失败",
  skipped: "跳过",
};

const taskTypeText = (type) => taskTypeMap[type] || type;
const taskStatusText = (status) => taskStatusMap[status] || status;
const resultStatusText = (status) => resultStatusMap[status] || status;

const parseTime = (value) => {
  if (!value) return "";
  return String(value).replace("T", " ").slice(0, 19);
};

const taskStatusMeta = (task) => {
  const s = task.status || "unknown";
  if (s === "success") return { type: "success", label: "成功", icon: "√" };
  if (s === "partial_failed") return { type: "warning", label: "部分失败", icon: "!" };
  if (s === "failed") return { type: "danger", label: "失败", icon: "×" };
  if (s === "running") return { type: "warning", label: "执行中", icon: "…" };
  return { type: "info", label: "未检测", icon: "-" };
};

const alertSeverityMeta = (severity) => {
  if (severity === "CRITICAL") return { type: "danger", label: "CRITICAL" };
  if (severity === "WARNING") return { type: "warning", label: "WARNING" };
  return { type: "success", label: "INFO" };
};

const alertStatusMeta = (status) => {
  if (status === "NEW") return { type: "danger" };
  if (status === "ACK") return { type: "warning" };
  if (status === "RECOVERED") return { type: "success" };
  return { type: "info" };
};

const isFailedTask = (task) => ["failed", "partial_failed"].includes(task.status);

const filteredTasks = computed(() => {
  const keyword = (taskFilters.keyword || "").trim().toLowerCase();
  return (tasks.value || []).filter((item) => {
    if (taskFilters.taskType && item.task_type !== taskFilters.taskType) return false;
    if (taskFilters.status && item.status !== taskFilters.status) return false;
    if (taskFilters.timeRange?.length === 2) {
      const t = new Date(item.start_time || item.end_time || 0).getTime();
      const start = new Date(taskFilters.timeRange[0]).getTime();
      const end = new Date(taskFilters.timeRange[1]).getTime();
      if (Number.isFinite(t) && (t < start || t > end)) return false;
    }
    if (!keyword) return true;
    const cached = taskDetailsCache.value[item.id] || [];
    const deviceNames = cached.map((r) => `${r.device_name || ""} ${r.device_ip || ""}`).join(" ").toLowerCase();
    const haystack = [
      String(item.id),
      taskTypeText(item.task_type),
      taskStatusText(item.status),
      item.start_time || "",
      item.end_time || "",
      deviceNames,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(keyword);
  });
});

const filteredAlerts = computed(() => {
  const keyword = (alertFilters.keyword || "").trim().toLowerCase();
  return (alerts.value || []).filter((item) => {
    if (alertFilters.sourceType && item.source_type !== alertFilters.sourceType) return false;
    if (alertFilters.severity && item.severity !== alertFilters.severity) return false;
    if (alertFilters.status && item.status !== alertFilters.status) return false;
    if (!keyword) return true;
    const haystack = [
      item.source_name,
      item.source_ip,
      item.title,
      item.message,
      item.metric_type,
      item.status,
      item.severity,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(keyword);
  });
});

const loadTasks = async () => {
  const { data } = await http.get("/tasks");
  const rows = (data || []).map((item) => ({
    ...item,
    start_time: parseTime(item.start_time),
    end_time: parseTime(item.end_time),
    status: item.status || (item.failed > 0 ? "partial_failed" : "unknown"),
  }));
  tasks.value = rows;

  const topIds = rows.slice(0, 40).map((item) => item.id);
  await Promise.all(
    topIds.map(async (id) => {
      try {
        const res = await http.get(`/tasks/${id}`);
        taskDetailsCache.value[id] = res.data?.results || [];
      } catch (_err) {
        taskDetailsCache.value[id] = [];
      }
    }),
  );
};

const loadAlerts = async () => {
  const { data } = await http.get("/alerts");
  alerts.value = (data || []).map((item) => ({
    ...item,
    first_triggered_at: parseTime(item.first_triggered_at),
    last_triggered_at: parseTime(item.last_triggered_at),
    acknowledged_at: parseTime(item.acknowledged_at),
    recovered_at: parseTime(item.recovered_at),
    closed_at: parseTime(item.closed_at),
  }));
};

const showDetail = async (taskId) => {
  const { data } = await http.get(`/tasks/${taskId}`);
  detailRows.value = (data.results || []).map((item) => ({
    ...item,
    start_time: parseTime(item.start_time),
    end_time: parseTime(item.end_time),
  }));
  taskDetailsCache.value[taskId] = data.results || [];
  detailVisible.value = true;
};

const retryTask = async (task) => {
  const { data } = await http.get(`/tasks/${task.id}`);
  const failedRows = (data.results || []).filter((item) => item.status === "failed");
  const retryRows = failedRows.length ? failedRows : (data.results || []);
  if (!retryRows.length) {
    ElMessage.warning("该任务没有可重试设备");
    return;
  }

  const deviceRes = await http.get("/devices", { params: { with_status: false } });
  const deviceByIp = new Map((deviceRes.data || []).map((item) => [item.ip, item.id]));
  const deviceIds = retryRows.map((item) => deviceByIp.get(item.device_ip)).filter(Boolean);
  if (!deviceIds.length) {
    ElMessage.warning("未匹配到可重试设备ID");
    return;
  }

  localStorage.setItem(
    "task_execute_prefill",
    JSON.stringify({
      task_type: task.task_type,
      device_ids: Array.from(new Set(deviceIds)),
      from: "log_center_retry",
      timestamp: Date.now(),
    }),
  );

  ElMessage.success("已带入任务参数，请在任务中心确认执行");
  router.push("/tasks/execute");
};

const handleAlertSelectionChange = (rows) => {
  selectedAlertIds.value = (rows || []).map((item) => item.id);
};

const bulkUpdateAlerts = async (action) => {
  if (!selectedAlertIds.value.length) {
    ElMessage.warning("请先选择告警");
    return;
  }
  await http.post("/alerts/bulk", {
    alert_ids: selectedAlertIds.value,
    action,
    operator: localStorage.getItem("username") || "admin",
  });
  ElMessage.success(action === "ACK" ? "批量 ACK 完成" : "批量关闭完成");
  selectedAlertIds.value = [];
  await loadAlerts();
};

const exportCurrent = (format) => {
  const rows = activeTab.value === "tasks" ? filteredTasks.value : filteredAlerts.value;
  if (!rows.length) {
    ElMessage.warning("当前无可导出的内容");
    return;
  }

  let header = [];
  let body = [];
  if (activeTab.value === "tasks") {
    header = ["任务ID", "任务类型", "开始时间", "结束时间", "状态", "成功", "失败"];
    body = rows.map((item) => [
      item.id,
      taskTypeText(item.task_type),
      item.start_time,
      item.end_time,
      taskStatusText(item.status),
      item.success,
      item.failed,
    ]);
  } else {
    header = ["ID", "等级", "状态", "来源", "名称", "IP", "指标", "标题", "内容", "最近触发时间"];
    body = rows.map((item) => [
      item.id,
      item.severity,
      item.status,
      item.source_type === "server" ? "服务器巡检" : "网络巡检",
      item.source_name,
      item.source_ip,
      item.metric_type,
      item.title,
      item.message,
      item.last_triggered_at,
    ]);
  }

  let content = "";
  let mime = "text/plain;charset=utf-8;";
  let ext = "txt";
  if (format === "csv") {
    content = [header, ...body]
      .map((line) => line.map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`).join(","))
      .join("\n");
    content = `\uFEFF${content}`;
    mime = "text/csv;charset=utf-8;";
    ext = "csv";
  } else {
    content = [header.join("\t"), ...body.map((line) => line.join("\t"))].join("\n");
  }

  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${activeTab.value === "tasks" ? "日志中心" : "告警中心"}_${Date.now()}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const resetTaskFilters = () => {
  taskFilters.taskType = "";
  taskFilters.status = "";
  taskFilters.timeRange = [];
  taskFilters.keyword = "";
};

const resetAlertFilters = () => {
  alertFilters.sourceType = "";
  alertFilters.severity = "";
  alertFilters.status = "";
  alertFilters.keyword = "";
};

watch(
  activeTab,
  async (value) => {
    if (value === "alerts") {
      await loadAlerts();
    } else {
      await loadTasks();
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-weight: 700;
}

.tab-switch {
  margin-bottom: 14px;
}

.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 12px;
}

.toolbar-compact {
  margin-top: -4px;
}

.selection-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.status-tag {
  font-weight: 700;
}

:deep(.log-table .el-table__body tr:hover > td) {
  background: rgba(47, 220, 255, 0.12) !important;
}

:deep(.log-table .el-table__body tr) {
  transition: background-color 0.2s ease;
}
</style>
