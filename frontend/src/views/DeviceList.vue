<template>
  <LayoutShell>
    <el-card class="switch-card">
      <div class="module-switch">
        <button
          type="button"
          class="module-switch-btn"
          :class="{ active: activeModule === 'network' }"
          @click="activeModule = 'network'"
        >
          网络设备管理
        </button>
        <button
          type="button"
          class="module-switch-btn"
          :class="{ active: activeModule === 'server' }"
          @click="activeModule = 'server'"
        >
          服务器管理
        </button>
      </div>
    </el-card>

    <el-card v-if="activeModule === 'network'">
      <template #header>
        <div class="card-title">网络设备管理</div>
      </template>

      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索名称/IP/分组/位置" clearable style="width: 260px" />
        <el-select v-model="selectedGroup" placeholder="设备分组" clearable style="width: 180px">
          <el-option label="全部分组" value="" />
          <el-option v-for="group in deviceGroups" :key="group" :label="group" :value="group" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="全部状态" style="width: 160px">
          <el-option label="全部状态" value="all" />
          <el-option label="在线" value="online" />
          <el-option label="离线" value="offline" />
          <el-option label="异常" value="alarm" />
        </el-select>
        <el-button type="primary" @click="loadDevices">搜索</el-button>
        <el-button @click="resetDeviceFilter">重置</el-button>
        <el-button type="success" @click="openAddDevice">新增设备</el-button>
        <el-button @click="openImportDialog('device')">批量导入</el-button>
        <span class="toolbar-meta">状态每 30 秒自动刷新</span>
      </div>

      <el-table :data="tableDevices" border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="名称" min-width="160">
          <template #default="{ row }">
            <el-button class="name-link" type="primary" link @click="openDeviceDetail(row)">
              {{ row.name }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="管理IP" min-width="140" />
        <el-table-column prop="device_type" label="设备类型" min-width="120" />
        <el-table-column prop="group_name" label="分组" min-width="120" />
        <el-table-column prop="location" label="位置" min-width="120" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="networkStatusTagType(row.status)">{{ networkStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEditDevice(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="onDeleteDevice(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-else>
      <template #header>
        <div class="card-title">服务器管理</div>
      </template>

      <div class="toolbar">
        <el-input v-model="serverKeyword" placeholder="搜索名称/IP" clearable style="width: 260px" />
        <el-select v-model="serverSelectedGroup" placeholder="所属分组" clearable style="width: 180px">
          <el-option label="全部分组" value="" />
          <el-option v-for="group in serverGroups" :key="group" :label="group" :value="group" />
        </el-select>
        <el-select v-model="serverStatusFilter" placeholder="全部状态" style="width: 160px">
          <el-option label="全部状态" value="all" />
          <el-option label="在线" value="online" />
          <el-option label="在线异常" value="online_abnormal" />
          <el-option label="离线" value="offline" />
        </el-select>
        <el-button type="primary" @click="loadServers">搜索</el-button>
        <el-button @click="resetServerFilter">重置</el-button>
        <el-button type="success" @click="openAddServer">新增服务器</el-button>
        <el-button @click="openImportDialog('server')">批量导入</el-button>
        <span class="toolbar-meta">状态每 30 秒自动刷新</span>
      </div>

      <el-table :data="tableServers" border>
        <el-table-column label="名称" min-width="170">
          <template #default="{ row }">
            <el-button class="name-link" type="primary" link @click="openServerDetail(row)">
              {{ row.name }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP地址" min-width="140" />
        <el-table-column prop="hostname" label="主机名" min-width="150" />
        <el-table-column label="服务器类型" min-width="110">
          <template #default="{ row }">
            {{ row.server_type === "windows" ? "Windows" : "Linux" }}
          </template>
        </el-table-column>
        <el-table-column label="接入方式" min-width="110">
          <template #default="{ row }">
            {{ formatAccessMethod(row.access_method) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="serverStatusTagType(row.status)">{{ serverStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="group_name" label="所属分组" min-width="120" />
        <el-table-column prop="server_switch_name" label="所属服务器交换机" min-width="150" />
        <el-table-column label="最近检测时间" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.last_checked_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEditServer(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="onDeleteServer(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="设备详情" width="620px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="名称">{{ detailDevice.name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="管理IP">{{ detailDevice.ip || "-" }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ detailDevice.username || "-" }}</el-descriptions-item>
        <el-descriptions-item label="端口">{{ detailDevice.port || "-" }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">{{ detailDevice.device_type || "-" }}</el-descriptions-item>
        <el-descriptions-item label="分组">{{ detailDevice.group_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="位置">{{ detailDevice.location || "-" }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="serverDetailVisible" title="服务器详情" width="620px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="名称">{{ serverDetail.name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ serverDetail.ip || "-" }}</el-descriptions-item>
        <el-descriptions-item label="主机名">{{ serverDetail.hostname || "-" }}</el-descriptions-item>
        <el-descriptions-item label="服务器类型">
          {{ serverDetail.server_type === "windows" ? "Windows" : "Linux" }}
        </el-descriptions-item>
        <el-descriptions-item label="接入方式">
          {{ formatAccessMethod(serverDetail.access_method) }}
        </el-descriptions-item>
        <el-descriptions-item label="端口">{{ serverDetail.port || "-" }}</el-descriptions-item>
        <el-descriptions-item label="所属分组">{{ serverDetail.group_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="最近检测时间">{{ formatDateTime(serverDetail.last_checked_at) }}</el-descriptions-item>
        <el-descriptions-item label="所属服务器交换机">{{ serverDetail.server_switch_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="核心交换机端口">{{ serverDetail.uplink_core_switch_port || "-" }}</el-descriptions-item>
        <el-descriptions-item label="定位方式">{{ serverLocateMethodLabel(serverDetail.topology_locate_method || serverDetail.topology_locate_status) }}</el-descriptions-item>
        <el-descriptions-item label="最近定位时间">{{ formatDateTime(serverDetail.topology_located_at) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="serverStatusTagType(serverDetail.status)">{{ serverStatusLabel(serverDetail.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="serverDetail.last_error" label="错误原因">
          {{ translateServerError(serverDetail.last_error) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :show-close="false" :title="editingId ? '编辑设备' : '新增设备'" width="520px">
      <template #header="{ close, titleId, titleClass }">
        <div class="dialog-header">
          <span :id="titleId" :class="titleClass">{{ editingId ? "编辑设备" : "新增设备" }}</span>
          <button type="button" class="dialog-header__close" @click="handleDeviceDialogClose(close)">×</button>
        </div>
      </template>
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="IP"><el-input v-model="form.ip" /></el-form-item>
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" show-password /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="form.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item label="设备类型"><el-input v-model="form.device_type" /></el-form-item>
        <el-form-item label="分组"><el-input v-model="form.group_name" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="form.location" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDevice">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="serverDialogVisible" :show-close="false" :title="serverEditingId ? '编辑服务器' : '新增服务器'" width="560px">
      <template #header="{ close, titleId, titleClass }">
        <div class="dialog-header">
          <span :id="titleId" :class="titleClass">{{ serverEditingId ? "编辑服务器" : "新增服务器" }}</span>
          <button type="button" class="dialog-header__close" @click="handleServerDialogClose(close)">×</button>
        </div>
      </template>
      <el-form :model="serverForm" label-width="110px">
        <el-form-item label="名称"><el-input v-model="serverForm.name" /></el-form-item>
        <el-form-item label="IP地址"><el-input v-model="serverForm.ip" /></el-form-item>
        <el-form-item label="主机名"><el-input v-model="serverForm.hostname" placeholder="可留空，检测成功后自动回填" /></el-form-item>
        <el-form-item label="服务器类型">
          <el-select v-model="serverForm.server_type" style="width: 100%">
            <el-option label="Windows" value="windows" />
            <el-option label="Linux" value="linux" />
          </el-select>
        </el-form-item>
        <el-form-item label="接入方式">
          <el-input :model-value="formatAccessMethod(serverForm.access_method)" disabled />
        </el-form-item>
        <el-form-item label="用户名"><el-input v-model="serverForm.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="serverForm.password" show-password /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="serverForm.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item label="所属分组">
          <el-select v-model="serverForm.group_name" style="width: 100%">
            <el-option label="Windows" value="Windows" />
            <el-option label="Linux" value="Linux" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="serverEnabled" /></el-form-item>
        <el-form-item label="连接测试">
          <div class="server-test-box">
            <div class="server-test-actions">
              <el-button
                type="primary"
                plain
                :loading="serverTestLoading"
                :disabled="!canTestServerForm"
                @click="runServerConnectionTest"
              >
                测试连接
              </el-button>
                <span v-if="serverTestHint" class="server-test-hint">{{ serverTestHint }}</span>
                <el-button
                  v-if="serverEditingId"
                  plain
                  :loading="serverRelocateLoading"
                  @click="runServerTopologyRelocate"
                >
                  重新定位
                </el-button>
              </div>
            <div
              v-if="serverTestResult"
              class="server-test-result"
              :class="serverTestResult.success ? 'is-success' : 'is-error'"
            >
              <div>
                {{ serverTestResult.success ? "连接成功" : "连接失败" }}
                <template v-if="serverTestResult.status">（{{ serverStatusLabel(serverTestResult.status) }}）</template>
              </div>
              <div>响应时间：{{ formatResponseTime(serverTestResult.response_time_ms) }}</div>
              <div v-if="serverTestResult.error_reason">
                错误原因：{{ translateServerError(serverTestResult.error_reason) }}
              </div>
            </div>
            <div v-if="serverLocateResult" class="server-locate-result">
              <div>所属服务器交换机：{{ serverLocateResult.server_switch_name || "未定位" }}</div>
              <div>核心交换机端口：{{ serverLocateResult.uplink_core_switch_port || "-" }}</div>
              <div>交换机端口：{{ serverLocateResult.server_switch_port || "-" }}</div>
              <div>定位状态：{{ serverLocateMethodLabel(serverLocateResult.topology_locate_status || serverLocateResult.topology_locate_method) }}</div>
              <div>说明：{{ serverLocateResult.topology_locate_reason || "-" }}</div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="serverDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveServer">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importDialogVisible" :title="importTarget === 'server' ? '批量导入服务器' : '批量导入网络设备'" width="980px">
      <div class="import-box">
        <el-alert type="info" :closable="false" style="margin-bottom: 12px">
          <template #title>
            支持上传 CSV 或 Excel(.xlsx)。系统会先预检查，再确认导入；已存在的 IP 会自动跳过。
          </template>
        </el-alert>

        <el-upload
          :auto-upload="false"
          :show-file-list="false"
          accept=".csv,.xlsx"
          @change="handleImportFileChange"
        >
          <el-button type="primary" plain :loading="importPreviewLoading">选择文件并预检查</el-button>
        </el-upload>

        <div v-if="importPreview.preview_id" class="import-summary">
          <el-descriptions :column="5" border>
            <el-descriptions-item label="总行数">{{ importPreview.summary?.total ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="可导入">{{ importPreview.summary?.importable ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="已存在">{{ importPreview.summary?.exists ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="文件重复">{{ importPreview.summary?.duplicate ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="错误">{{ importPreview.summary?.error ?? 0 }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <el-table v-if="importPreview.rows.length" :data="importPreview.rows" border style="margin-top: 12px" height="420">
          <el-table-column prop="row_no" label="行号" width="70" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="importRowTagType(row.status)">{{ importRowStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="说明" min-width="220" />
          <el-table-column label="名称" min-width="160">
            <template #default="{ row }">{{ importEntity(row).name || "-" }}</template>
          </el-table-column>
          <el-table-column label="IP" min-width="140">
            <template #default="{ row }">{{ importEntity(row).ip || "-" }}</template>
          </el-table-column>
          <el-table-column v-if="importTarget === 'device'" label="设备类型" min-width="120">
            <template #default="{ row }">{{ importEntity(row).device_type || "-" }}</template>
          </el-table-column>
          <el-table-column v-if="importTarget === 'server'" label="服务器类型" min-width="120">
            <template #default="{ row }">{{ importEntity(row).server_type || "-" }}</template>
          </el-table-column>
          <el-table-column label="分组" min-width="120">
            <template #default="{ row }">{{ importEntity(row).group_name || "-" }}</template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button
          type="success"
          :disabled="!importPreview.preview_id || !(importPreview.summary?.importable > 0)"
          :loading="importConfirmLoading"
          @click="confirmImport"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>
  </LayoutShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRoute } from "vue-router";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const route = useRoute();

const activeModule = ref("network");
const devices = ref([]);
const servers = ref([]);
const allGroups = ref([]);
const allServerGroups = ref([]);
const keyword = ref("");
const selectedGroup = ref("");
const statusFilter = ref("all");
const serverKeyword = ref("");
const serverSelectedGroup = ref("");
const serverStatusFilter = ref("all");
const selectedRows = ref([]);

const detailVisible = ref(false);
const serverDetailVisible = ref(false);
const dialogVisible = ref(false);
const serverDialogVisible = ref(false);
const editingId = ref(null);
const serverEditingId = ref(null);
const enabled = ref(true);
const serverEnabled = ref(true);
const serverTestLoading = ref(false);
const serverTestResult = ref(null);
const serverRelocateLoading = ref(false);
const serverLocateResult = ref(null);

const importDialogVisible = ref(false);
const importTarget = ref("device"); // device | server
const importPreviewLoading = ref(false);
const importConfirmLoading = ref(false);
const importPreview = reactive({
  preview_id: "",
  summary: null,
  rows: [],
});

const detailDevice = reactive({});
const serverDetail = reactive({});

const emptyForm = () => ({
  name: "",
  ip: "",
  username: "",
  password: "",
  port: 22,
  device_type: "huawei",
  group_name: "default",
  location: "unknown",
  enable: 1,
});

const emptyServerForm = () => ({
  name: "",
  ip: "",
  hostname: "",
  server_type: "windows",
  access_method: "winrm",
  username: "administrator",
  password: "",
  port: 5985,
  group_name: "Windows",
  enable: 1,
});

const form = reactive(emptyForm());
const serverForm = reactive(emptyServerForm());
// Keep add-dialog drafts when user clicks the mask/presses ESC; only clear on explicit close (X) or after save.
const deviceAddDraftActive = ref(false);
const serverAddDraftActive = ref(false);

const deviceGroups = computed(() => allGroups.value);
const serverGroups = computed(() => allServerGroups.value);

const tableDevices = computed(() =>
  devices.value.filter((item) => {
    const statusMatched = statusFilter.value === "all" || item.status === statusFilter.value;
    const groupMatched = !selectedGroup.value || item.group_name === selectedGroup.value;
    const text = `${item.name} ${item.ip} ${item.group_name} ${item.location}`.toLowerCase();
    const keywordMatched = !keyword.value || text.includes(keyword.value.toLowerCase());
    return statusMatched && groupMatched && keywordMatched;
  })
);

const tableServers = computed(() =>
  servers.value.filter((item) => {
    const statusMatched =
      serverStatusFilter.value === "all" ||
      item.status === serverStatusFilter.value ||
      // “在线”包含可通信状态：online / online_abnormal / alarm
      (serverStatusFilter.value === "online" && ["online", "online_abnormal", "alarm"].includes(String(item.status || "").toLowerCase()));
    const groupMatched = !serverSelectedGroup.value || item.group_name === serverSelectedGroup.value;
    const text = `${item.name} ${item.ip} ${item.hostname || ""}`.toLowerCase();
    const keywordMatched = !serverKeyword.value || text.includes(serverKeyword.value.toLowerCase());
    return statusMatched && groupMatched && keywordMatched;
  })
);

const canTestServerForm = computed(() => Boolean(serverForm.ip && serverForm.username && serverForm.password && serverForm.port));
const serverTestHint = computed(() => (canTestServerForm.value ? "" : "请先填写 IP、用户名、密码和端口"));

let refreshTimer = null;

const networkStatusLabel = (status) =>
  ({
    online: "在线",
    offline: "离线",
    alarm: "异常",
    unknown: "未知",
  }[status] || "未知");

const networkStatusTagType = (status) =>
  ({
    online: "success",
    offline: "danger",
    alarm: "warning",
    unknown: "info",
  }[status] || "info");

const serverStatusLabel = (status) =>
  ({
    online: "在线",
    online_abnormal: "在线异常",
    alarm: "在线异常",
    offline: "离线",
    unknown: "未知",
  }[status] || "未知");

const serverStatusTagType = (status) =>
  ({
    online: "success",
    online_abnormal: "warning",
    alarm: "warning",
    offline: "danger",
    unknown: "info",
  }[status] || "info");

const formatAccessMethod = (value) => (String(value).toLowerCase() === "winrm" ? "WinRM" : "SSH");
const formatDateTime = (value) => (!value ? "-" : String(value).replace("T", " ").slice(0, 19));
const formatResponseTime = (value) => (value === null || value === undefined ? "-" : `${value}ms`);
const serverLocateMethodLabel = (value) =>
  ({
    auto: "自动",
    manual: "手动",
    success: "自动",
    failed: "失败",
  }[String(value || "").toLowerCase()] || "-");

const translateServerError = (message) => {
  const text = String(message || "").trim();
  if (!text) return "";
  const lower = text.toLowerCase();
  if (lower.includes("credentials were rejected")) return "用户名或密码错误，服务器拒绝了当前凭据";
  if (lower.includes("label empty or too long")) return "目标地址格式不正确，请检查 IP 地址是否填写有误";
  if (lower.includes("timed out") || lower.includes("timeout")) return "连接超时，请检查网络连通性或端口是否开放";
  if (lower.includes("refused")) return "目标端口拒绝连接，请检查服务是否开启";
  if (lower.includes("name or service not known") || lower.includes("host unreachable")) return "主机不可达，请检查 IP 地址或网络";
  if (lower.includes("authentication")) return "认证失败，请检查用户名或密码";
  return text;
};

const syncServerDefaults = () => {
  if (serverForm.server_type === "windows") {
    serverForm.access_method = "winrm";
    serverForm.port = 5985;
    serverForm.group_name = "Windows";
    if (!serverEditingId.value || !serverForm.username || serverForm.username === "root") {
      serverForm.username = "administrator";
    }
    return;
  }
  serverForm.access_method = "ssh";
  serverForm.port = 22;
  serverForm.group_name = "Linux";
  if (!serverEditingId.value || !serverForm.username || serverForm.username === "administrator") {
    serverForm.username = "root";
  }
};

const applyRouteQuery = () => {
  if (route.query.module === "server" || route.query.module === "network") {
    activeModule.value = route.query.module;
  }
  const status = typeof route.query.status === "string" ? route.query.status : "all";
  if (activeModule.value === "server") {
    serverStatusFilter.value = status;
    return;
  }
  statusFilter.value = status;
};

const loadDevices = async () => {
  const { data } = await http.get("/devices", { params: { with_status: true } });
  devices.value = Array.isArray(data) ? data : [];
  const groupSet = new Set(devices.value.map((item) => item.group_name).filter(Boolean));
  allGroups.value = Array.from(groupSet);
};

const loadServers = async () => {
  const { data } = await http.get("/servers", { params: { with_status: false } });
  servers.value = Array.isArray(data) ? data : [];
};

const loadServerGroups = async () => {
  const { data } = await http.get("/servers/groups");
  allServerGroups.value = Array.isArray(data) ? data : [];
};

const resetImportState = () => {
  importPreview.preview_id = "";
  importPreview.summary = null;
  importPreview.rows = [];
};

const openImportDialog = (target) => {
  importTarget.value = target === "server" ? "server" : "device";
  resetImportState();
  importDialogVisible.value = true;
};

const importEntity = (row) => {
  if (!row) return {};
  if (importTarget.value === "server") return row.server || {};
  return row.device || {};
};

const importRowTagType = (status) =>
  ({
    importable: "success",
    exists: "info",
    duplicate: "warning",
    error: "danger",
  }[String(status || "").toLowerCase()] || "info");

const importRowStatusLabel = (status) =>
  ({
    importable: "可导入",
    exists: "已存在",
    duplicate: "文件重复",
    error: "错误",
  }[String(status || "").toLowerCase()] || "未知");

const handleImportFileChange = async (file) => {
  const raw = file?.raw || file;
  if (!raw) return;
  resetImportState();
  importPreviewLoading.value = true;
  try {
    const form = new FormData();
    form.append("file", raw);
    const endpoint = importTarget.value === "server" ? "/servers/import/preview" : "/devices/import/preview";
    const { data } = await http.post(endpoint, form, { headers: { "Content-Type": "multipart/form-data" } });
    importPreview.preview_id = data?.preview_id || "";
    importPreview.summary = data?.summary || null;
    importPreview.rows = Array.isArray(data?.rows) ? data.rows : [];
    ElMessage.success("预检查完成");
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "预检查失败");
  } finally {
    importPreviewLoading.value = false;
  }
};

const confirmImport = async () => {
  if (!importPreview.preview_id) return;
  importConfirmLoading.value = true;
  try {
    const endpoint = importTarget.value === "server" ? "/servers/import/confirm" : "/devices/import/confirm";
    const { data } = await http.post(endpoint, { preview_id: importPreview.preview_id });
    ElMessage.success(`导入完成：成功 ${data?.imported ?? 0} 条，跳过 ${data?.skipped ?? 0} 条`);
    importDialogVisible.value = false;
    resetImportState();
    if (importTarget.value === "server") {
      await Promise.all([loadServers(), loadServerGroups()]);
    } else {
      await loadDevices();
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "导入失败");
  } finally {
    importConfirmLoading.value = false;
  }
};

const resetDeviceFilter = async () => {
  keyword.value = "";
  selectedGroup.value = "";
  statusFilter.value = "all";
  await loadDevices();
};

const resetServerFilter = async () => {
  serverKeyword.value = "";
  serverSelectedGroup.value = "";
  serverStatusFilter.value = "all";
  await Promise.all([loadServers(), loadServerGroups()]);
};

const openDeviceDetail = (row) => {
  Object.keys(detailDevice).forEach((key) => delete detailDevice[key]);
  Object.assign(detailDevice, row || {});
  detailVisible.value = true;
};

const openServerDetail = (row) => {
  Object.keys(serverDetail).forEach((key) => delete serverDetail[key]);
  Object.assign(serverDetail, row || {});
  serverDetailVisible.value = true;
};

const openAddDevice = () => {
  editingId.value = null;
  // If the user previously hid the dialog (clicking the mask), keep the draft.
  if (!deviceAddDraftActive.value) {
    Object.assign(form, emptyForm());
    enabled.value = true;
    deviceAddDraftActive.value = true;
  }
  dialogVisible.value = true;
};

const openEditDevice = (row) => {
  editingId.value = row.id;
  Object.assign(form, { ...row });
  enabled.value = row.enable === 1;
  deviceAddDraftActive.value = false;
  dialogVisible.value = true;
};

const saveDevice = async () => {
  const payload = { ...form, enable: enabled.value ? 1 : 0 };
  if (editingId.value) {
    await http.put(`/devices/${editingId.value}`, payload);
    ElMessage.success("设备更新成功");
  } else {
    await http.post("/devices", payload);
    ElMessage.success("设备创建成功");
  }
  dialogVisible.value = false;
  if (!editingId.value) {
    Object.assign(form, emptyForm());
    enabled.value = true;
    deviceAddDraftActive.value = false;
  }
  await loadDevices();
};

const onDeleteDevice = async (id) => {
  await ElMessageBox.confirm("确认删除该设备？", "提示", {
    type: "warning",
    confirmButtonText: "确定",
    cancelButtonText: "取消",
  });
  await http.delete(`/devices/${id}`);
  ElMessage.success("设备删除成功");
  await loadDevices();
};

const openAddServer = () => {
  serverEditingId.value = null;
  // If the user previously hid the dialog (clicking the mask), keep the draft.
  if (!serverAddDraftActive.value) {
    Object.assign(serverForm, emptyServerForm());
    serverEnabled.value = true;
    serverTestResult.value = null;
    serverLocateResult.value = null;
    syncServerDefaults();
    serverAddDraftActive.value = true;
  }
  serverDialogVisible.value = true;
};

const openEditServer = (row) => {
  serverEditingId.value = row.id;
  Object.assign(serverForm, {
    name: row.name,
    ip: row.ip,
    hostname: row.hostname || "",
    server_type: row.server_type || "windows",
    access_method: row.access_method || "winrm",
    username: row.username,
    password: row.password,
    port: row.port,
    group_name: row.group_name || (row.server_type === "windows" ? "Windows" : "Linux"),
    enable: row.enable,
  });
  serverEnabled.value = row.enable === 1;
  serverTestResult.value = null;
  serverLocateResult.value = null;
  syncServerDefaults();
  serverAddDraftActive.value = false;
  serverDialogVisible.value = true;
};

const saveServer = async () => {
  const payload = { ...serverForm, enable: serverEnabled.value ? 1 : 0 };
  if (serverEditingId.value) {
    await http.put(`/servers/${serverEditingId.value}`, payload);
    ElMessage.success("服务器更新成功");
  } else {
    await http.post("/servers", payload);
    ElMessage.success("服务器创建成功");
  }
  serverDialogVisible.value = false;
  if (!serverEditingId.value) {
    Object.assign(serverForm, emptyServerForm());
    serverEnabled.value = true;
    serverTestResult.value = null;
    serverLocateResult.value = null;
    syncServerDefaults();
    serverAddDraftActive.value = false;
  }
  await Promise.all([loadServers(), loadServerGroups()]);
};

const onDeleteServer = async (id) => {
  await ElMessageBox.confirm("确认删除该服务器？", "提示", {
    type: "warning",
    confirmButtonText: "确定",
    cancelButtonText: "取消",
  });
  await http.delete(`/servers/${id}`);
  ElMessage.success("服务器删除成功");
  await Promise.all([loadServers(), loadServerGroups()]);
};

const runServerConnectionTest = async () => {
  if (!canTestServerForm.value) {
    ElMessage.warning(serverTestHint.value);
    return;
  }
  try {
    serverTestLoading.value = true;
    const { data } = await http.post("/servers/test-connection", {
      ...serverForm,
      enable: serverEnabled.value ? 1 : 0,
    });
    serverTestResult.value = data;
    if (data?.hostname) {
      serverForm.hostname = data.hostname;
    }
    if (data.success) {
      ElMessage.success(`连接成功，响应 ${formatResponseTime(data.response_time_ms)}`);
    } else {
      ElMessage.warning(translateServerError(data.error_reason) || "连接失败");
    }
  } catch (error) {
    const detail = error?.response?.data?.detail || "测试连接失败";
    serverTestResult.value = {
      success: false,
      status: "offline",
      response_time_ms: 0,
      error_reason: detail,
    };
    ElMessage.error(translateServerError(detail));
  } finally {
    serverTestLoading.value = false;
  }
};

const runServerTopologyRelocate = async () => {
  if (!serverEditingId.value) return;
  try {
    serverRelocateLoading.value = true;
    const { data } = await http.post(`/servers/${serverEditingId.value}/relocate-topology`);
    serverLocateResult.value = data || null;
    if (data?.task_id) {
      ElMessage.success(`已提交所属交换机检测任务，任务ID: ${data.task_id}`);
      return;
    }
    ElMessage.success(data?.server_switch_name ? `已定位到 ${data.server_switch_name}` : "定位完成");
    await Promise.all([loadServers(), loadServerGroups()]);
  } catch (error) {
    const detail = error?.response?.data?.detail || "重新定位失败";
    ElMessage.error(detail);
  } finally {
    serverRelocateLoading.value = false;
  }
};

const handleDeviceDialogClose = (close) => {
  // Explicit close (X): clear draft only for "add" mode.
  if (!editingId.value) {
    Object.assign(form, emptyForm());
    enabled.value = true;
    deviceAddDraftActive.value = false;
  }
  close();
};

const handleServerDialogClose = (close) => {
  // Explicit close (X): clear draft only for "add" mode.
  if (!serverEditingId.value) {
    Object.assign(serverForm, emptyServerForm());
    serverEnabled.value = true;
    serverTestResult.value = null;
    serverLocateResult.value = null;
    syncServerDefaults();
    serverAddDraftActive.value = false;
  }
  close();
};

watch(
  () => serverForm.server_type,
  () => {
    syncServerDefaults();
  }
);

watch(
  () => route.query,
  async () => {
    applyRouteQuery();
    await Promise.all([loadDevices(), loadServers(), loadServerGroups()]);
  }
);

onMounted(async () => {
  applyRouteQuery();
  await Promise.all([loadDevices(), loadServers(), loadServerGroups()]);
  refreshTimer = setInterval(() => {
    if (activeModule.value === "server") {
      loadServers();
      return;
    }
    loadDevices();
  }, 30000);
});

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
});
</script>

<style scoped>
.switch-card {
  margin-bottom: 16px;
}

.module-switch {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.module-switch-btn {
  border: 1px solid rgba(47, 220, 255, 0.28);
  background: rgba(10, 26, 51, 0.62);
  color: #cfe9ff;
  padding: 10px 18px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.22s ease;
  font-weight: 600;
}

.module-switch-btn.active {
  color: #ffffff;
  border-color: rgba(47, 220, 255, 0.7);
  box-shadow: 0 0 0 1px rgba(47, 220, 255, 0.2), 0 0 20px rgba(47, 220, 255, 0.18);
  background: linear-gradient(135deg, rgba(25, 74, 136, 0.95), rgba(24, 129, 214, 0.95));
}

.card-title {
  font-weight: 600;
  letter-spacing: 0.3px;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.toolbar-meta {
  color: var(--app-subtext);
  font-size: 12px;
}

.name-link {
  font-weight: 600;
}

.server-test-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.server-test-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.server-test-hint {
  color: #64748b;
  font-size: 12px;
}

.server-test-result {
  border-radius: 10px;
  padding: 12px 14px;
  line-height: 1.8;
}

.server-test-result.is-success {
  background: rgba(34, 197, 94, 0.08);
  color: #166534;
}

.server-test-result.is-error {
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
}

.import-box {
  text-align: left;
}

.import-summary {
  margin-top: 12px;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-right: 4px;
}

.dialog-header__close {
  width: 28px;
  height: 28px;
  line-height: 26px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.08);
  color: rgba(15, 23, 42, 0.72);
  cursor: pointer;
  font-size: 18px;
  font-weight: 700;
  transition: all 0.16s ease;
}

.dialog-header__close:hover {
  border-color: rgba(47, 220, 255, 0.65);
  background: rgba(47, 220, 255, 0.12);
  color: rgba(15, 23, 42, 0.9);
}
</style>
