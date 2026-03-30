<template>
  <LayoutShell>
    <el-card class="switch-card">
      <el-radio-group v-model="taskCenterTab" @change="onTaskTabChange">
        <el-radio-button label="instant">即时任务</el-radio-button>
        <el-radio-button label="planned">计划任务</el-radio-button>
      </el-radio-group>
    </el-card>

    <el-card>
      <template #header>
        <div class="section-title">任务定义区</div>
      </template>

      <el-form label-width="120px">
        <el-form-item label="任务类型">
          <el-select v-model="taskType" style="width: 280px" @change="onTaskTypeChange">
            <el-option v-for="item in taskTypes" :key="item.type" :label="item.label" :value="item.type" />
          </el-select>
        </el-form-item>

        <el-form-item :label="isServerTask ? '目标服务器' : '目标设备'">
          <el-radio-group v-model="selectMode" @change="onSelectModeChange">
            <el-radio label="all">{{ isServerTask ? "全部服务器" : "全部设备" }}</el-radio>
            <el-radio label="group">按分组</el-radio>
            <el-radio label="manual">自定义选择</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="selectMode === 'group'" label="目标分组">
          <el-select v-model="groupName" style="width: 280px" @change="applyGroupSelection">
            <el-option v-for="g in groups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="!isServerTask" label="设备筛选">
          <el-radio-group v-model="deviceFilterMode">
            <el-radio label="all">显示全部设备</el-radio>
            <el-radio label="ntp_unconfigured">仅显示未配置 NTP 设备</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item :label="isServerTask ? '目标服务器' : '目标设备'">
          <div class="device-select-wrap">
            <div class="device-select-toolbar">
              <el-checkbox v-model="checkAllOnFiltered" :indeterminate="checkAllIndeterminate">全选</el-checkbox>
              <span class="filter-hint">当前可选 {{ filteredDevices.length }} 台</span>
            </div>

            <el-select v-model="selectedDevices" multiple filterable style="width: 620px">
              <el-option
                v-for="item in filteredDevices"
                :key="item.id"
                :label="`${item.name}(${item.ip})`"
                :value="item.id"
              />
            </el-select>

            <div class="selected-counter">已选择设备：{{ selectedDevices.length }} 台</div>
          </div>
        </el-form-item>

        <el-divider content-position="left">任务参数</el-divider>

        <template v-if="taskType === 'server_inspection'">
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

        <template v-else-if="taskType === 'server_switch_detect'">
          <el-form-item label="检测选项">
            <el-checkbox v-model="params.server_switch_detect.force">强制重新检测</el-checkbox>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="巡检模式">
            <el-select v-model="params.audit.mode" style="width: 220px">
              <el-option label="标准模式（默认）" value="exec" />
              <el-option label="终端模式（兼容）" value="shell" />
            </el-select>
          </el-form-item>
          <el-form-item label="连接超时(秒)"><el-input-number v-model="params.audit.timeout" :min="5" :max="120" /></el-form-item>
        </template>

        <el-space>
          <el-button
            type="success"
            :loading="isActionRunning"
            :disabled="isActionRunning"
            @click="confirmAndExecute"
          >
            {{ actionButtonText }}
          </el-button>
        </el-space>
      </el-form>

      <div v-if="statusPanelVisible" ref="statusPanelRef" class="inline-status-panel">
        <el-divider content-position="left">任务执行状态区</el-divider>

        <el-row :gutter="12" class="summary-row">
          <el-col :span="4"><el-statistic title="当前任务状态" :value="runtimeStateLabel" /></el-col>
          <el-col :span="4"><el-statistic title="总设备数" :value="runtime.total" /></el-col>
          <el-col :span="4"><el-statistic title="已完成数" :value="completedCount" /></el-col>
          <template v-if="!isServerInspection">
            <el-col :span="4"><el-statistic title="成功数" :value="runtime.success" /></el-col>
            <el-col :span="4"><el-statistic title="失败数" :value="runtime.failed" /></el-col>
            <el-col :span="4"><el-statistic title="跳过数" :value="runtime.skipped" /></el-col>
          </template>
          <template v-else>
            <el-col :span="4"><el-statistic title="执行失败数" :value="runtime.failed" /></el-col>
            <el-col :span="4"><el-statistic title="跳过数" :value="runtime.skipped" /></el-col>
          </template>
        </el-row>

        <el-row v-if="isServerInspection" :gutter="12" class="summary-row" style="margin-top: 10px">
          <el-col :span="4"><el-statistic title="正常数" :value="inspectionSummary.normal" /></el-col>
          <el-col :span="4"><el-statistic title="告警数" :value="inspectionSummary.warning" /></el-col>
          <el-col :span="4"><el-statistic title="严重数" :value="inspectionSummary.critical" /></el-col>
        </el-row>

        <el-progress :percentage="overallProgress" :stroke-width="18" status="success" />

        <el-descriptions :column="2" border style="margin-top: 12px">
          <el-descriptions-item label="当前执行设备">{{ currentExecutingDeviceText }}</el-descriptions-item>
          <el-descriptions-item label="最新日志摘要">{{ latestLogSummary }}</el-descriptions-item>
        </el-descriptions>

        <div class="status-actions">
          <el-button size="small" @click="toggleDetailedLogs">
            {{ showDetailedLogs ? '收起详细日志' : '查看详细日志' }}
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <div class="section-title">执行前检查区</div>
      </template>

      <el-row :gutter="12" class="summary-row">
        <el-col :span="4"><el-statistic title="总设备数" :value="precheckSummary.total" /></el-col>
        <el-col :span="4"><el-statistic title="可执行数量" :value="precheckSummary.executable" /></el-col>
        <el-col :span="4"><el-statistic title="已符合配置" :value="precheckSummary.compliant" /></el-col>
        <el-col :span="4"><el-statistic title="跳过数量" :value="precheckSummary.skipped" /></el-col>
        <el-col :span="4"><el-statistic title="失败数量" :value="precheckSummary.failed" /></el-col>
      </el-row>

      <el-table :data="precheckDetails" border>
        <el-table-column prop="device_name" label="设备名称" width="150" />
        <el-table-column prop="device_ip" label="管理IP" width="150" />
        <el-table-column label="在线" width="90">
          <template #default="scope">{{ scope.row.online ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="连接方式" width="110">
          <template #default="scope">{{ precheckConnectionMethod(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="连接结果" width="110">
          <template #default="scope">{{ precheckConnectionResult(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="scope">{{ precheckStatusLabel(scope.row.status) }}</template>
        </el-table-column>
        <el-table-column prop="message" label="检查说明" min-width="260" />
      </el-table>
    </el-card>

    <el-card v-if="showDetailedLogs" style="margin-top: 16px">
      <template #header>
        <div class="section-title">执行过程详细日志</div>
      </template>

      <el-descriptions :column="4" border>
        <el-descriptions-item label="当前任务状态">{{ runtime.state }}</el-descriptions-item>
        <el-descriptions-item label="成功数量">{{ runtime.success }}</el-descriptions-item>
        <el-descriptions-item label="失败数量">{{ runtime.failed }}</el-descriptions-item>
        <el-descriptions-item label="跳过数量">{{ runtime.skipped }}</el-descriptions-item>
      </el-descriptions>

      <el-input
        type="textarea"
        :rows="10"
        :model-value="runtime.logs.join('\n')"
        readonly
        style="margin-top: 12px"
      />
    </el-card>

    <el-card style="margin-top: 16px; margin-bottom: 16px">
      <template #header>
        <div class="section-title">任务结果</div>
      </template>

      <el-row :gutter="12" class="summary-row">
        <template v-if="!isServerInspection">
          <el-col :span="6"><el-statistic title="总数" :value="resultSummary.total" /></el-col>
          <el-col :span="6"><el-statistic title="成功" :value="resultSummary.success" /></el-col>
          <el-col :span="6"><el-statistic title="失败" :value="resultSummary.failed" /></el-col>
          <el-col :span="6"><el-statistic title="跳过" :value="resultSummary.skipped" /></el-col>
        </template>
        <template v-else>
          <el-col :span="6"><el-statistic title="总设备数" :value="runtime.total" /></el-col>
          <el-col :span="6"><el-statistic title="已完成数" :value="completedCount" /></el-col>
          <el-col :span="6"><el-statistic title="执行失败数" :value="runtime.failed" /></el-col>
          <el-col :span="6"><el-statistic title="跳过数" :value="runtime.skipped" /></el-col>
        </template>
      </el-row>

      <el-space style="margin-bottom: 8px">
        <el-button @click="exportResult">导出结果</el-button>
        <el-button type="primary" @click="goHistory">查看日志中心</el-button>
      </el-space>

      <el-table v-if="!isServerInspection" :data="resultRows" border>
        <el-table-column prop="device_name" label="设备名称" width="150" />
        <el-table-column prop="device_ip" label="管理IP" width="150" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="message" label="结果说明" min-width="260" />
        <el-table-column prop="start_time" label="开始时间" width="170" />
        <el-table-column prop="end_time" label="结束时间" width="170" />
      </el-table>

      <el-table v-else :data="serverDetailRows" border>
        <el-table-column prop="server_name" label="服务器名称" width="160" />
        <el-table-column prop="server_ip" label="IP" width="150" />
        <el-table-column prop="cpu_usage" label="CPU(%)" width="110" />
        <el-table-column prop="memory_usage" label="内存(%)" width="110" />
        <el-table-column prop="disk_usage" label="磁盘(%)" width="110" />
        <el-table-column label="结果等级" width="110">
          <template #default="scope">
            <el-tag
              class="level-tag"
              :class="`level-tag--${String(scope.row.result_level || 'unknown').toLowerCase()}`"
              :type="inspectionLevelTagType(scope.row.result_level)"
            >
              {{ inspectionLevelLabel(scope.row.result_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="result_message" label="说明" min-width="240" />
        <el-table-column prop="executed_at" label="执行时间" width="180" />
      </el-table>
    </el-card>
  </LayoutShell>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const router = useRouter();
const taskCenterTab = ref("instant");
const fallbackTaskTypes = [
  { type: "audit", label: "网络巡检" },
  { type: "server_inspection", label: "服务器巡检" },
  { type: "server_switch_detect", label: "服务器所属交换机检测" },
];

const taskType = ref("audit");
const taskTypes = ref([]);
const selectMode = ref("all");
const deviceFilterMode = ref("all");
const groupName = ref("");
const groups = ref([]);
const devices = ref([]);
const selectedDevices = ref([]);

const precheckLoading = ref(false);
const executeLoading = ref(false);
const statusPanelVisible = ref(false);
const showDetailedLogs = ref(false);
const statusPanelRef = ref(null);

const precheckData = reactive({ precheck_id: "", summary: {}, details: [] });
const runtime = reactive({ state: "idle", progress: 0, total: 0, success: 0, failed: 0, skipped: 0, status: "", logs: [] });
const resultRows = ref([]);
const serverDetailRows = ref([]);
let pollTimer = null;

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
    trigger: "manual",
  },
});

const isServerInspection = computed(() => taskType.value === "server_inspection");
const isServerSwitchDetect = computed(() => taskType.value === "server_switch_detect");
const isServerTask = computed(() => isServerInspection.value || isServerSwitchDetect.value);

const currentParams = computed(() => {
  if (taskType.value === "server_inspection") return params.server_inspection;
  if (taskType.value === "server_switch_detect") return params.server_switch_detect;
  return params.audit;
});
const precheckSummary = computed(() => precheckData.summary || { total: 0, executable: 0, compliant: 0, skipped: 0, failed: 0 });
const precheckDetails = computed(() => precheckData.details || []);

const inspectionSummary = computed(() => {
  if (!isServerInspection.value) return { normal: 0, warning: 0, critical: 0, unknown: 0, failed: 0 };
  const rows = serverDetailRows.value || [];
  const summary = { normal: 0, warning: 0, critical: 0, unknown: 0, failed: 0 };
  rows.forEach((row) => {
    const key = String(row?.result_level || "unknown").toLowerCase();
    if (key in summary) summary[key] += 1;
    else summary.unknown += 1;
  });
  return summary;
});

const resultSummary = computed(() => {
  const rows = resultRows.value || [];
  return {
    total: rows.length,
    success: rows.filter((r) => r.status === "success").length,
    failed: rows.filter((r) => r.status === "failed").length,
    skipped: rows.filter((r) => r.status === "skipped").length,
  };
});

const completedCount = computed(() => Number(runtime.success || 0) + Number(runtime.failed || 0) + Number(runtime.skipped || 0));

const overallProgress = computed(() => {
  if (runtime.total > 0) {
    return Math.min(100, Math.round((completedCount.value / runtime.total) * 100));
  }
  return Math.min(100, Math.max(0, runtime.progress || 0));
});

const runtimeStateLabel = computed(() => {
  if (runtime.state === "idle") return "未开始";
  if (runtime.state === "checking") return "运行中";
  if (runtime.state === "running") return "运行中";
  if (runtime.state === "failed") return "执行失败";

  const finalStatus = runtime.status || "";
  if (finalStatus === "partial_failed") return "部分失败";
  if (finalStatus === "failed") return "执行失败";
  if (runtime.state === "completed") return isServerTask.value ? "执行完成" : "已完成";
  return "未开始";
});

const inspectionLevelLabel = (value) =>
  ({
    normal: "正常",
    warning: "告警",
    critical: "严重",
    unknown: "未知",
    failed: "失败",
  }[String(value || "").toLowerCase()] || "未知");

const inspectionLevelTagType = (value) =>
  ({
    normal: "success",
    warning: "warning",
    critical: "danger",
    unknown: "info",
    failed: "danger",
  }[String(value || "").toLowerCase()] || "info");

const precheckStatusLabel = (status) =>
  ({
    executable: "可执行",
    compliant: "已符合",
    skipped: "跳过",
    failed: "失败",
  }[String(status || "").toLowerCase()] || String(status || "-"));

const precheckConnectionMethod = (row) => {
  if (!isServerTask.value) return "SSH";
  const id = row?.device_id;
  const server = (devices.value || []).find((item) => String(item.id) === String(id));
  if (String(server?.server_type || "").toLowerCase() === "windows") return "WinRM";
  return "SSH";
};

const precheckConnectionResult = (row) => {
  const status = String(row?.status || "").toLowerCase();
  if (status === "skipped") return "-";
  if (row?.online === false) return "离线";
  return row?.ssh_ok ? "成功" : "失败";
};

const latestLogSummary = computed(() => {
  const logs = runtime.logs || [];
  if (!logs.length) return "等待执行";
  return logs[logs.length - 1];
});

const currentExecutingDeviceText = computed(() => {
  const logs = runtime.logs || [];
  for (let i = logs.length - 1; i >= 0; i -= 1) {
    const match = String(logs[i]).match(/([^\s\[]+)\((\d+\.\d+\.\d+\.\d+)\)/);
    if (match) {
      return `${match[1]} (${match[2]})`;
    }
  }
  return "-";
});

const isActionRunning = computed(() => precheckLoading.value || executeLoading.value || runtime.state === "running" || runtime.state === "checking");
const actionButtonText = computed(() => (isActionRunning.value ? "任务执行中..." : "确认执行"));

const isNtpConfigured = (device) => {
  const value = device?.ntp_configured ?? device?.ntpConfigured ?? device?.has_ntp;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value === 1;
  if (typeof value === "string") {
    const text = value.trim().toLowerCase();
    return ["1", "true", "yes", "configured", "ok", "已配置", "是"].includes(text);
  }
  return false;
};

const filteredDevices = computed(() => {
  const baseList = devices.value || [];
  if (isServerTask.value) {
    return baseList;
  }
  if (deviceFilterMode.value === "ntp_unconfigured") {
    return baseList.filter((d) => !isNtpConfigured(d));
  }
  return baseList;
});

const filteredDeviceIds = computed(() => filteredDevices.value.map((d) => d.id));

const checkAllOnFiltered = computed({
  get() {
    const ids = filteredDeviceIds.value;
    if (!ids.length) return false;
    return ids.every((id) => selectedDevices.value.includes(id));
  },
  set(checked) {
    const filteredSet = new Set(filteredDeviceIds.value);
    const selectedSet = new Set(selectedDevices.value);

    if (checked) {
      filteredSet.forEach((id) => selectedSet.add(id));
    } else {
      filteredSet.forEach((id) => selectedSet.delete(id));
    }

    selectedDevices.value = Array.from(selectedSet);
  },
});

const checkAllIndeterminate = computed(() => {
  const ids = filteredDeviceIds.value;
  if (!ids.length) return false;
  const selectedInFiltered = ids.filter((id) => selectedDevices.value.includes(id)).length;
  return selectedInFiltered > 0 && selectedInFiltered < ids.length;
});

const selectedDeviceIps = computed(() => {
  const map = new Map((devices.value || []).map((item) => [item.id, item.ip]));
  return (selectedDevices.value || []).map((id) => map.get(id)).filter(Boolean);
});

const buildTaskPayload = () => ({
  task_type: taskType.value,
  devices: selectedDevices.value,
  device_ids: selectedDevices.value,
  device_ips: selectedDeviceIps.value,
  params: currentParams.value,
});

const buildPrecheckPayload = () => {
  const payload = buildTaskPayload();
  const rawTimeout = Number(payload?.params?.timeout ?? 20);
  const safeTimeout = Number.isFinite(rawTimeout) ? Math.max(rawTimeout, 15) : 20;
  return {
    ...payload,
    params: {
      ...(payload.params || {}),
      timeout: safeTimeout,
    },
  };
};

const loadTaskTypes = async () => {
  try {
    const { data } = await http.get("/tasks/types");
    const resolved = Array.isArray(data) && data.length ? data : fallbackTaskTypes;
    taskTypes.value = resolved;
  } catch (_err) {
    taskTypes.value = fallbackTaskTypes;
    ElMessage.warning("任务类型加载失败，已切换到本地默认配置");
  }

  if (!taskTypes.value.some((item) => item.type === taskType.value)) {
    taskType.value = taskTypes.value[0]?.type || "audit";
  }
};

const loadDevices = async () => {
  if (isServerTask.value) {
    const { data } = await http.get("/servers", { params: { with_status: false } });
    devices.value = data || [];
    groups.value = [...new Set((devices.value || []).map((d) => d.group_name).filter(Boolean))].sort();
  } else {
    const { data } = await http.get("/devices", { params: { with_status: false } });
    devices.value = data || [];
    groups.value = [...new Set(devices.value.map((d) => d.group_name).filter(Boolean))].sort();
  }

  if (selectMode.value === "all") {
    selectedDevices.value = devices.value.map((d) => d.id);
  }
};

const onTaskTypeChange = () => {
  precheckData.precheck_id = "";
  precheckData.summary = {};
  precheckData.details = [];
  deviceFilterMode.value = "all";
  loadDevices();
};

const onTaskTabChange = (tab) => {
  if (tab === "planned") {
    router.push("/tasks/scheduled");
  }
};

const onSelectModeChange = () => {
  if (selectMode.value === "all") {
    selectedDevices.value = devices.value.map((d) => d.id);
    return;
  }
  if (selectMode.value === "group") {
    applyGroupSelection();
    return;
  }
  selectedDevices.value = [];
};

const applyGroupSelection = () => {
  if (!groupName.value) {
    selectedDevices.value = [];
    return;
  }
  selectedDevices.value = devices.value.filter((d) => d.group_name === groupName.value).map((d) => d.id);
};

const appendRuntimeLog = (text) => {
  runtime.logs = [...runtime.logs, `[${new Date().toLocaleTimeString()}] ${text}`].slice(-200);
};

const scrollToStatusPanel = async () => {
  await nextTick();
  if (statusPanelRef.value?.scrollIntoView) {
    statusPanelRef.value.scrollIntoView({ behavior: "smooth", block: "center" });
  }
};

const toggleDetailedLogs = () => {
  showDetailedLogs.value = !showDetailedLogs.value;
};

const startAutoPrecheck = async () => {
  runtime.state = "checking";
  runtime.status = "";
  runtime.progress = 8;
  runtime.total = selectedDevices.value.length;
  runtime.success = 0;
  runtime.failed = 0;
  runtime.skipped = 0;
  runtime.logs = [];
  appendRuntimeLog("开始执行任务前自动检查...");

  const { data } = await http.post("/tasks/precheck", buildPrecheckPayload(), { timeout: 300000 });
  precheckData.precheck_id = data.precheck_id;
  precheckData.summary = data.summary;
  precheckData.details = data.details;

  runtime.total = Number(data?.summary?.total || runtime.total || 0);
  runtime.progress = 24;
  appendRuntimeLog(`检查完成：总设备 ${data.summary.total}，可执行 ${data.summary.executable}。`);

  (data.details || []).slice(0, 20).forEach((item) => {
    const statusMap = {
      executable: "可执行",
      compliant: "已符合",
      skipped: "已跳过",
      failed: "失败",
    };
    appendRuntimeLog(`设备 ${item.device_name || item.device_ip}：${statusMap[item.status] || item.status}，${item.message || ""}`);
  });

  return data;
};

const buildIssueHtml = (details) => {
  const issueRows = (details || []).filter((item) => item.status !== "executable");
  if (!issueRows.length) return "";

  const top = issueRows.slice(0, 8);
  const items = top
    .map((x) => `<li><b>${x.device_name || x.device_ip}</b>：${x.message || x.status}</li>`)
    .join("");

  const more = issueRows.length > top.length ? `<p>还有 ${issueRows.length - top.length} 台设备未展示。</p>` : "";
  return `<p>检查发现部分问题设备：</p><ul>${items}</ul>${more}<p>是否跳过问题设备并继续执行？</p>`;
};

const executeWithPrecheck = async (precheckId) => {
  executeLoading.value = true;
  try {
    runtime.state = "running";
    runtime.progress = Math.max(runtime.progress, 30);

    const payload = {
      ...buildTaskPayload(),
      precheck_id: precheckId,
    };

    const { data } = await http.post("/tasks/execute", payload);
    runtime.total = Number(data?.total || runtime.total || 0);
    appendRuntimeLog(`任务开始执行，任务ID: ${data.task_id}`);
    startPolling(data.task_id);
    ElMessage.success(`任务已开始，任务ID: ${data.task_id}`);
  } finally {
    executeLoading.value = false;
  }
};

const confirmAndExecute = async () => {
  if (!selectedDevices.value.length) {
    ElMessage.warning("请先选择目标设备");
    return;
  }

  if (isActionRunning.value) return;

  statusPanelVisible.value = true;
  await scrollToStatusPanel();

  precheckLoading.value = true;
  try {
    const precheckResult = await startAutoPrecheck();
    const summary = precheckResult.summary || {};

    if ((summary.executable || 0) <= 0) {
      runtime.state = "idle";
      runtime.progress = 0;
      appendRuntimeLog("没有可执行设备，任务未启动。");
      ElMessage.warning("没有可执行设备，请根据检查结果调整后重试");
      return;
    }

    const issueHtml = buildIssueHtml(precheckResult.details || []);
    if (issueHtml) {
      try {
        await ElMessageBox.confirm(issueHtml, "检查发现问题设备", {
          type: "warning",
          confirmButtonText: "跳过问题设备并继续",
          cancelButtonText: "取消执行",
          dangerouslyUseHTMLString: true,
        });
        appendRuntimeLog("用户选择跳过问题设备，继续执行任务。");
      } catch (_cancel) {
        runtime.state = "idle";
        runtime.progress = 0;
        appendRuntimeLog("用户取消执行。可调整参数后重新确认执行。");
        ElMessage.info("已取消执行");
        return;
      }
    } else {
      appendRuntimeLog("检查通过，开始执行任务。");
    }

    await executeWithPrecheck(precheckResult.precheck_id);
  } catch (err) {
    runtime.state = "failed";
    runtime.status = "failed";
    runtime.progress = 0;
    appendRuntimeLog(`检查失败：${err?.response?.data?.detail || "未知错误"}`);
    ElMessage.error(err?.response?.data?.detail || "自动检查失败");
  } finally {
    precheckLoading.value = false;
  }
};

const fetchTaskDetail = async (taskId) => {
  const { data } = await http.get(`/tasks/${taskId}`);
  resultRows.value = data.results || [];
  serverDetailRows.value = data.server_details || [];
};

const startPolling = (taskId) => {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const { data } = await http.get(`/tasks/progress/${taskId}`);
      runtime.state = data.state || "running";
      runtime.status = data.status || runtime.status;
      runtime.progress = data.progress || 0;
      runtime.total = Number(data.total || runtime.total || 0);
      runtime.success = data.success || 0;
      runtime.failed = data.failed || 0;
      runtime.skipped = data.skipped || 0;
      runtime.logs = data.logs || runtime.logs;

      if (data.state === "completed" || data.state === "failed") {
        clearInterval(pollTimer);
        pollTimer = null;
        await fetchTaskDetail(taskId);
        ElMessage.success("任务执行完成，结果已保存到日志中心");
      }
    } catch (_err) {
      clearInterval(pollTimer);
      pollTimer = null;
      runtime.state = "failed";
      runtime.status = "failed";
      ElMessage.error("任务进度获取失败");
    }
  }, 1200);
};

const exportResult = () => {
  const isServer = isServerInspection.value;
  const baseRows = isServer ? serverDetailRows.value : resultRows.value;
  if (!baseRows.length) {
    ElMessage.warning("暂无可导出的任务结果");
    return;
  }

  let header = [];
  let rows = [];
  if (isServer) {
    header = ["服务器名称", "IP", "CPU(%)", "内存(%)", "磁盘(%)", "结果等级", "说明", "执行时间"];
    rows = (serverDetailRows.value || []).map((r) => [
      r.server_name,
      r.server_ip,
      r.cpu_usage,
      r.memory_usage,
      r.disk_usage,
      inspectionLevelLabel(r.result_level),
      r.result_message,
      r.executed_at,
    ]);
  } else {
    header = ["设备名称", "管理IP", "状态", "结果说明", "开始时间", "结束时间"];
    rows = (resultRows.value || []).map((r) => [r.device_name, r.device_ip, r.status, r.message, r.start_time, r.end_time]);
  }
  const csv = [header, ...rows]
    .map((line) => line.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");

  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `任务结果_${Date.now()}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const goHistory = () => router.push("/tasks/history");

const applyPrefillFromDeviceCenter = () => {
  const raw = localStorage.getItem("task_execute_prefill");
  if (!raw) return;

  try {
    const data = JSON.parse(raw);
    if (Array.isArray(data.device_ids) && data.device_ids.length) {
      selectedDevices.value = data.device_ids;
    }
    if (["audit"].includes(data.task_type)) {
      taskType.value = data.task_type;
    }
  } catch (_err) {
    // ignore broken prefill data
  } finally {
    localStorage.removeItem("task_execute_prefill");
  }
};

onMounted(async () => {
  await Promise.all([loadTaskTypes(), loadDevices()]);
  applyPrefillFromDeviceCenter();
});

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
});
</script>

<style scoped>
.section-title {
  font-weight: 700;
}

.switch-card {
  margin-bottom: 12px;
}

.summary-row {
  margin-bottom: 12px;
}

.device-select-wrap {
  width: 620px;
}

.device-select-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.filter-hint {
  color: var(--text-secondary, #9ca3af);
  font-size: 13px;
}

.selected-counter {
  margin-top: 8px;
  color: var(--text-primary, #111827);
  font-size: 13px;
}

.inline-status-panel {
  margin-top: 14px;
  border-top: 1px dashed var(--app-border);
  padding-top: 12px;
}

.status-actions {
  margin-top: 10px;
}

.level-tag {
  font-weight: 600;
}

.level-tag--failed {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.35);
  color: #7f1d1d;
}
</style>
