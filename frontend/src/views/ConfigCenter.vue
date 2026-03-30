<template>
  <LayoutShell>
    <el-card class="switch-card">
      <el-radio-group v-model="activeTab">
        <el-radio-button label="config">批量配置</el-radio-button>
        <el-radio-button label="ip-vlan">端口查询</el-radio-button>
      </el-radio-group>
    </el-card>

    <template v-if="activeTab === 'config'">
      <el-card>
        <template #header>
          <div class="section-title">配置中心</div>
        </template>

        <el-form label-width="120px">
          <el-form-item label="配置功能">
            <el-select v-model="intent" style="width: 280px" @change="onIntentChange">
              <el-option v-for="item in intents" :key="item.intent" :label="item.label" :value="item.intent" />
            </el-select>
          </el-form-item>

          <el-form-item label="目标设备">
            <el-radio-group v-model="targetMode" @change="onTargetModeChange">
              <el-radio label="all">全部设备</el-radio>
              <el-radio label="group">按分组</el-radio>
              <el-radio label="custom">自定义选择</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="targetMode === 'group'" label="目标分组">
            <el-select v-model="groupName" style="width: 220px" @change="applyGroupSelection">
              <el-option v-for="g in groups" :key="g" :label="g" :value="g" />
            </el-select>
          </el-form-item>

          <el-form-item v-if="targetMode === 'custom'" label="设备选择">
            <el-select v-model="selectedDevices" multiple filterable style="width: 620px">
              <el-option v-for="item in devices" :key="item.id" :label="`${item.name} (${item.ip})`" :value="item.id" />
            </el-select>
          </el-form-item>

          <el-divider content-position="left">配置参数</el-divider>

          <template v-if="intent === 'ntp'">
            <el-form-item label="时区名称">
              <el-input v-model="params.ntp.timezone" style="width: 220px" />
            </el-form-item>
            <el-form-item label="时区偏移">
              <el-input v-model="params.ntp.offset" style="width: 220px" />
            </el-form-item>
            <el-form-item label="NTP服务器">
              <el-input v-model="params.ntp.ntp_server" style="width: 280px" />
            </el-form-item>
          </template>

          <template v-if="intent === 'snmp'">
            <el-form-item label="SNMP团体字">
              <el-input v-model="params.snmp.community" style="width: 280px" />
            </el-form-item>
          </template>

          <el-form-item label="连接超时(秒)">
            <el-input-number v-model="timeout" :min="5" :max="120" />
          </el-form-item>

          <el-form-item>
            <el-space>
              <el-button type="primary" :loading="precheckLoading" @click="runPrecheck">执行前检查</el-button>
              <el-button type="success" :loading="executeLoading" :disabled="!canExecute" @click="confirmExecute">
                确认执行
              </el-button>
            </el-space>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card style="margin-top: 16px">
        <template #header>
          <div class="section-title">预检查结果与命令预览</div>
        </template>

        <el-row :gutter="12" class="summary-row">
          <el-col :span="6"><el-statistic title="总设备数" :value="precheckSummary.total" /></el-col>
          <el-col :span="6"><el-statistic title="可执行" :value="precheckSummary.executable" /></el-col>
          <el-col :span="6"><el-statistic title="跳过" :value="precheckSummary.skipped" /></el-col>
          <el-col :span="6"><el-statistic title="失败" :value="precheckSummary.failed" /></el-col>
        </el-row>

        <el-table :data="precheckDetails" border>
          <el-table-column prop="device_name" label="设备" width="150" />
          <el-table-column prop="device_ip" label="管理IP" width="150" />
          <el-table-column prop="role" label="设备类型" width="130" />
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column prop="audit_hint" label="巡检联动提示" min-width="220" />
          <el-table-column prop="message" label="检查说明" min-width="220" />
          <el-table-column label="命令预览" min-width="260">
            <template #default="scope">
              <el-input type="textarea" :rows="3" :model-value="(scope.row.commands || []).join('\n')" readonly />
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="jobId > 0" style="margin-top: 16px">
        <template #header>
          <div class="section-title">执行状态</div>
        </template>
        <el-descriptions :column="5" border>
          <el-descriptions-item label="状态">{{ runtime.state }}</el-descriptions-item>
          <el-descriptions-item label="总数">{{ runtime.total }}</el-descriptions-item>
          <el-descriptions-item label="成功">{{ runtime.success }}</el-descriptions-item>
          <el-descriptions-item label="失败">{{ runtime.failed }}</el-descriptions-item>
          <el-descriptions-item label="跳过">{{ runtime.skipped }}</el-descriptions-item>
        </el-descriptions>
        <el-progress :percentage="runtime.progress" style="margin-top: 12px" />
        <el-input type="textarea" :rows="10" :model-value="runtime.logs.join('\n')" readonly style="margin-top: 12px" />
      </el-card>

      <el-card v-if="resultRows.length" style="margin-top: 16px; margin-bottom: 16px">
        <template #header>
          <div class="section-title">执行结果</div>
        </template>
        <el-table :data="resultRows" border>
          <el-table-column prop="device_name" label="设备" width="150" />
          <el-table-column prop="device_ip" label="管理IP" width="150" />
          <el-table-column prop="role" label="设备类型" width="120" />
          <el-table-column prop="status" label="执行状态" width="100" />
          <el-table-column prop="rollback_status" label="回滚状态" width="140" />
          <el-table-column prop="backup_file" label="备份文件" min-width="220" />
          <el-table-column prop="message" label="结果说明" min-width="220" />
        </el-table>
      </el-card>
    </template>

    <template v-else>
      <el-card>
        <template #header>
          <div class="section-title">端口查询</div>
        </template>

        <el-form label-width="130px" @submit.prevent>
          <el-form-item label="查询方式">
            <el-radio-group v-model="ipVlanForm.query_type">
              <el-radio-button label="ip">按 IP 查询</el-radio-button>
              <el-radio-button label="mac">按 MAC 查询</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item :label="ipVlanForm.query_type === 'ip' ? '终端IP' : 'MAC关键字'">
            <el-input
              v-if="ipVlanForm.query_type === 'ip'"
              v-model="ipVlanForm.target_ip"
              placeholder="例如：10.18.100.25"
              style="width: 320px"
              @keydown.enter.stop.prevent="startLocate"
            />
            <el-input
              v-else
              v-model="ipVlanForm.mac_keyword"
              placeholder="例如：60cf / 8457 / 60cf-8457"
              style="width: 320px"
              @keydown.enter.stop.prevent="startLocate"
            />
            <el-button
              type="primary"
              style="margin-left: 12px"
              :loading="locateLoading"
              :disabled="!canStartLocate"
              @click="startLocate"
            >
              查询
            </el-button>
          </el-form-item>

          <div v-if="ipVlanForm.query_type === 'ip' && ipVlanForm.target_ip.trim() && !isValidTargetIp" class="inline-error">
            请输入合法的 IPv4 地址
          </div>
          <div v-if="ipVlanForm.query_type === 'mac' && macKeywordValidationMessage" class="inline-error">
            {{ macKeywordValidationMessage }}
          </div>

          <el-form-item>
            <el-button :disabled="!locateLogs.length && !locateErrorMessage" @click="showCurrentLocateLogs = !showCurrentLocateLogs">
              {{ showCurrentLocateLogs ? "收起日志" : "查看日志" }}
            </el-button>
            <el-button style="margin-left: 12px" @click="showLogDrawer = true">历史日志</el-button>
          </el-form-item>

          <div v-if="queryStageMessage" class="inline-hint">{{ queryStageMessage }}</div>

          <el-card v-if="queryProgress.visible" class="query-progress-card">
            <div class="query-progress-text">{{ queryProgress.step }}</div>
            <el-progress :percentage="queryProgress.percent" :stroke-width="16" />
          </el-card>
        </el-form>

        <el-card v-if="showCurrentLocateLogs && (locateLogs.length || locateErrorMessage)" style="margin-top: 12px">
          <template #header>
            <div class="sub-title">当前查询日志</div>
          </template>
          <el-alert v-if="locateErrorMessage" :title="locateErrorMessage" type="error" :closable="false" style="margin-bottom: 12px" />
          <el-table :data="locateLogs" border>
            <el-table-column prop="device" label="设备" width="180" />
            <el-table-column prop="command" label="命令" min-width="260" />
            <el-table-column label="返回结果" min-width="320">
              <template #default="scope">
                <el-input type="textarea" :rows="4" :model-value="scope.row.output || ''" readonly />
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card v-if="pendingMacSelection && macMatchOptions.length" style="margin-top: 12px">
          <template #header>
            <div class="sub-title">MAC 匹配结果</div>
          </template>
          <el-alert title="匹配到多个 MAC，请先选择具体 MAC 再继续定位。" type="warning" :closable="false" style="margin-bottom: 12px" />
          <el-table :data="macMatchOptions" border>
            <el-table-column label="选择" width="90">
              <template #default="scope">
                <el-radio v-model="selectedMacOption" :label="scope.row.mac">{{ "" }}</el-radio>
              </template>
            </el-table-column>
            <el-table-column prop="mac" label="MAC" min-width="180" />
            <el-table-column prop="core_uplink_interface" label="核心上联口" min-width="160" />
            <el-table-column prop="display_text" label="匹配内容" min-width="220" />
          </el-table>
          <el-button type="primary" style="margin-top: 12px" :disabled="!selectedMacOption" @click="continueLocateBySelectedMac">
            继续定位
          </el-button>
        </el-card>
      </el-card>

      <el-card style="margin-top: 16px">
        <template #header>
          <div class="section-title">查询结果</div>
        </template>

        <template v-if="!hasLocateOutcome">
          <el-empty description="输入终端 IP 或 MAC 关键字后点击查询" />
        </template>

        <template v-else>
          <el-alert v-if="locateErrorMessage" :title="locateErrorMessage" type="error" :closable="false" style="margin-bottom: 16px" />

          <el-descriptions :column="2" border>
            <el-descriptions-item :label="queryIdentityLabel">{{ queryIdentityValue }}</el-descriptions-item>
            <el-descriptions-item label="终端MAC">{{ locateResult.mac || "-" }}</el-descriptions-item>
            <el-descriptions-item label="接入交换机">{{ locateResult.access_switch?.name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="当前接口">{{ locateResult.interface_name || "-" }}</el-descriptions-item>
            <el-descriptions-item label="当前VLAN">{{ locateResult.current_vlan || "-" }}</el-descriptions-item>
            <el-descriptions-item label="核心上联口">{{ locateResult.core_uplink_interface || "-" }}</el-descriptions-item>
            <el-descriptions-item label="接入上联口">{{ locateResult.access_uplink_interface || "-" }}</el-descriptions-item>
            <el-descriptions-item label="链路说明">{{ locateChainSummary }}</el-descriptions-item>
          </el-descriptions>

          <el-alert
            v-for="warning in ipVlanWarnings"
            :key="warning"
            :title="warning"
            type="warning"
            :closable="false"
            style="margin-top: 12px"
          />
        </template>
      </el-card>

      <el-card v-if="locateResult.interface_name" style="margin-top: 16px">
        <template #header>
          <div class="section-title">VLAN变更区</div>
        </template>

        <el-form label-width="130px">
          <el-form-item label="新VLAN">
            <el-input v-model="ipVlanForm.new_vlan" placeholder="请输入 1-4094" style="width: 180px" />
            <el-button
              type="success"
              style="margin-left: 12px"
              :disabled="!canModifyVlan"
              :loading="ipVlanExecuteLoading"
              @click="confirmIpVlanChange"
            >
              {{ modifyButtonText2 }}
            </el-button>
            <el-button
              style="margin-left: 12px"
              :disabled="!canModifyVlan || trunkCheckLoading"
              :loading="trunkCheckLoading"
              @click="checkTrunkAllow"
            >
              检查放通
            </el-button>
          </el-form-item>
        </el-form>

        <div v-if="!isNewVlanFilled" class="inline-hint inline-hint-inline">如需修改VLAN，请先填写新VLAN</div>
        <div v-else-if="newVlanValidationMessage" class="inline-error inline-error-inline">{{ newVlanValidationMessage }}</div>
        <div v-else :class="['inline-status', trunkCheckState2.can_modify ? 'status-success' : 'status-warning']">
          {{ trunkCheckState2.reason }}
        </div>

        <el-card v-if="showTrunkCheckSection2" style="margin-top: 16px">
          <template #header>
            <div class="sub-title">上下联VLAN放通检查</div>
          </template>
          <el-table :data="displayUplinkRows2" border>
            <el-table-column prop="interface_name" label="接口名称" min-width="180" />
            <el-table-column prop="allowed_vlans" label="当前允许 VLAN 列表" min-width="260" />
            <el-table-column prop="has_vlan_text" label="是否包含目标 VLAN" width="170" />
            <el-table-column prop="status" label="状态" width="160" />
          </el-table>
        </el-card>
      </el-card>

      <el-card v-if="ipVlanExecuteResult.id" style="margin-top: 16px; margin-bottom: 16px">
        <template #header>
          <div class="section-title">修改结果</div>
        </template>
        <el-result
          :icon="ipVlanExecuteResult.status === 'success' ? 'success' : 'error'"
          :title="ipVlanExecuteResult.status === 'success' ? '修改成功' : '修改失败'"
          :sub-title="ipVlanExecuteResult.message || '-'"
        >
          <template #extra>
            <div class="result-extra">
              <div>目标：{{ ipVlanExecuteResult.target_ip || ipVlanExecuteResult.target_mac || "-" }}</div>
              <div>接入交换机：{{ ipVlanExecuteResult.access_switch?.name || "-" }}</div>
              <div>终端接入口：{{ ipVlanExecuteResult.interface_name || "-" }}</div>
              <div>VLAN：{{ ipVlanExecuteResult.old_vlan || "-" }} -> {{ ipVlanExecuteResult.new_vlan || "-" }}</div>
              <div>核心上联 trunk：{{ ipVlanExecuteResult.core_uplink_added ? "已补放通" : "无需补放通" }}</div>
              <div>接入上联 trunk：{{ ipVlanExecuteResult.access_uplink_added ? "已补放通" : "无需补放通" }}</div>
              <div>接入口 VLAN 修改：{{ ipVlanExecuteResult.vlan_change_success ? "成功" : "失败" }}</div>
              <div>接口 flap：{{ flapResultText }}</div>
              <div>操作人：{{ ipVlanExecuteResult.operator || "-" }}</div>
              <div>执行时间：{{ ipVlanExecuteResult.execute_time || "-" }}</div>
            </div>
          </template>
        </el-result>
      </el-card>
    </template>

    <el-drawer v-model="showLogDrawer" title="端口查询日志" size="60%">
      <el-button type="primary" size="small" @click="loadIpVlanLogs">刷新日志</el-button>
      <el-table :data="ipVlanLogs" border style="margin-top: 12px">
        <el-table-column prop="execute_time" label="时间" width="180" />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="target_ip" label="IP" width="140" />
        <el-table-column prop="target_mac" label="MAC" width="170" />
        <el-table-column prop="access_switch" label="接入交换机" min-width="140" />
        <el-table-column prop="interface_name" label="接口" width="150" />
        <el-table-column label="VLAN" width="120">
          <template #default="scope">{{ scope.row.old_vlan }} -> {{ scope.row.new_vlan }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="message" label="结果说明" min-width="220" />
      </el-table>
    </el-drawer>
  </LayoutShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const activeTab = ref("config");
const intents = ref([]);
const intent = ref("ntp");
const targetMode = ref("all");
const groupName = ref("");
const devices = ref([]);
const groups = ref([]);
const selectedDevices = ref([]);
const precheckId = ref("");
const precheckLoading = ref(false);
const executeLoading = ref(false);
const precheckDetails = ref([]);
const precheckSummary = reactive({ total: 0, executable: 0, skipped: 0, failed: 0 });
const jobId = ref(0);
const resultRows = ref([]);
let pollTimer = null;

const runtime = reactive({
  state: "idle",
  progress: 0,
  total: 0,
  success: 0,
  failed: 0,
  skipped: 0,
  logs: [],
});

const params = reactive({
  ntp: { timezone: "BJ", offset: "08:00:00", ntp_server: "10.18.101.2" },
  snmp: { community: "public" },
});
const timeout = ref(20);

const ipVlanForm = reactive({
  query_type: "ip",
  target_ip: "",
  mac_keyword: "",
  new_vlan: "",
});

const locateLoading = ref(false);
const ipVlanExecuteLoading = ref(false);
const locateErrorMessage = ref("");
const queryStageMessage = ref("");
const locateResult = reactive({
  target_ip: "",
  mac: "",
  core_switch: null,
  core_uplink_interface: "",
  access_uplink_interface: "",
  access_switch: null,
  interface_name: "",
  current_vlan: "",
  core_allowed_vlans: "",
  access_allowed_vlans: "",
});
const locateLogs = ref([]);
const ipVlanWarnings = ref([]);
const pendingMacSelection = ref(false);
const macMatchOptions = ref([]);
const selectedMacOption = ref("");
const showCurrentLocateLogs = ref(false);
const showLogDrawer = ref(false);
const ipVlanLogs = ref([]);

let queryProgressTimer = null;
const queryProgress = reactive({
  visible: false,
  percent: 0,
  step: "",
});

const ipVlanExecuteResult = reactive({
  id: 0,
  status: "",
  message: "",
  target_ip: "",
  target_mac: "",
  access_switch: null,
  interface_name: "",
  old_vlan: "",
  new_vlan: "",
  core_uplink_added: false,
  access_uplink_added: false,
  vlan_change_success: false,
  shutdown_success: false,
  undo_shutdown_success: false,
  refresh_attempted: false,
  operator: "",
  execute_time: "",
});

const currentParams = computed(() => {
  const payload = { ...(params[intent.value] || {}) };
  payload.timeout = timeout.value;
  return payload;
});

const finalDeviceIds = computed(() => {
  if (targetMode.value === "all") return devices.value.map((item) => item.id);
  return selectedDevices.value;
});

const canExecute = computed(() => precheckSummary.executable > 0 && precheckId.value !== "");

const isValidTargetIp = computed(() => {
  const text = String(ipVlanForm.target_ip || "").trim();
  if (!text) return false;
  const parts = text.split(".");
  if (parts.length !== 4) return false;
  return parts.every((part) => /^\d+$/.test(part) && Number(part) >= 0 && Number(part) <= 255);
});

const macKeywordValidationMessage = computed(() => {
  if (ipVlanForm.query_type !== "mac") return "";
  const text = String(ipVlanForm.mac_keyword || "").trim();
  if (!text) return "请输入 MAC 关键字";
  const normalized = text.replace(/[^0-9a-fA-F]/g, "");
  if (!normalized) return "MAC 关键字只能包含十六进制字符";
  if (normalized.length < 4) return "MAC 关键字至少输入 4 位";
  return "";
});

const canStartLocate = computed(() => {
  if (ipVlanForm.query_type === "mac") return !macKeywordValidationMessage.value;
  return isValidTargetIp.value;
});

const isNewVlanFilled = computed(() => String(ipVlanForm.new_vlan ?? "").trim() !== "");
const newVlanValidationMessage = computed(() => {
  const text = String(ipVlanForm.new_vlan ?? "").trim();
  if (!text) return "请填写新VLAN";
  if (!/^\d+$/.test(text)) return "新VLAN必须为数字";
  const value = Number(text);
  if (!Number.isInteger(value) || value < 1 || value > 4094) return "新VLAN范围需在1~4094之间";
  return "";
});
const isValidNewVlan = computed(() => newVlanValidationMessage.value === "");
const currentOperator = computed(() => localStorage.getItem("username") || "admin");

const queryIdentityLabel = computed(() => (ipVlanForm.query_type === "mac" && !locateResult.target_ip ? "查询MAC" : "终端IP"));
const queryIdentityValue = computed(() => {
  if (locateResult.target_ip) return locateResult.target_ip;
  if (locateResult.mac) return locateResult.mac;
  return ipVlanForm.query_type === "mac" ? ipVlanForm.mac_keyword.trim() || "-" : ipVlanForm.target_ip.trim() || "-";
});
const locateChainSummary = computed(() => {
  const parts = [];
  if (locateResult.core_switch?.name) parts.push(`核心：${locateResult.core_switch.name}`);
  if (locateResult.access_switch?.name) parts.push(`接入：${locateResult.access_switch.name}`);
  return parts.length ? parts.join(" / ") : "-";
});
const hasLocateOutcome = computed(() => {
  return Boolean(
    locateResult.target_ip ||
      locateResult.mac ||
      locateResult.interface_name ||
      locateErrorMessage.value ||
      locateLogs.value.length ||
      pendingMacSelection.value,
  );
});

const checkVlanInSpec = (specText, vlanId) => {
  const text = String(specText || "").trim().toLowerCase();
  if (!text) return false;
  if (text === "all") return true;

  const tokens = text.split(/\s+/);
  for (let i = 0; i < tokens.length; i += 1) {
    const token = tokens[i];
    if (!/^\d+$/.test(token)) continue;
    const start = Number(token);
    if (start === vlanId) return true;
    if (tokens[i + 1] === "to" && /^\d+$/.test(tokens[i + 2] || "")) {
      const end = Number(tokens[i + 2]);
      if (start <= vlanId && vlanId <= end) return true;
      i += 2;
    }
  }
  return false;
};

const trunkCheckState = computed(() => {
  if (!isNewVlanFilled.value) {
    return { core_has_vlan: false, access_has_vlan: false, can_modify: false, reason: "待输入新VLAN后校验" };
  }
  if (!isValidNewVlan.value) {
    return { core_has_vlan: false, access_has_vlan: false, can_modify: false, reason: newVlanValidationMessage.value };
  }

  const vlan = Number(ipVlanForm.new_vlan);
  const coreHas = checkVlanInSpec(locateResult.core_allowed_vlans, vlan);
  const accessHas = checkVlanInSpec(locateResult.access_allowed_vlans, vlan);
  const canModify = coreHas && accessHas;

  return {
    core_has_vlan: coreHas,
    access_has_vlan: accessHas,
    can_modify: canModify,
    reason: canModify
      ? "目标 VLAN 已放通，可直接修改"
      : `目标 VLAN 未完全放通，提交时将自动在上下联端口追加 port trunk allow-pass vlan ${vlan}`,
  };
});

const showTrunkCheckSection = computed(() => {
  return Boolean(
    locateResult.interface_name &&
      isNewVlanFilled.value &&
      isValidNewVlan.value &&
      (locateResult.core_uplink_interface || locateResult.access_uplink_interface),
  );
});

// New 2-phase trunk check (refactor): only shown after user clicks "检查放通" or after change.
const trunkCheckLoading = ref(false);
const trunkCheckPerformed = ref(false);
const trunkCheckResult = ref(null);

const trunkCheckState2 = computed(() => {
  if (!locateResult.interface_name) return { can_modify: false, reason: "" };
  if (!isNewVlanFilled.value) return { can_modify: false, reason: "请先填写新VLAN" };
  if (newVlanValidationMessage.value) return { can_modify: false, reason: newVlanValidationMessage.value };
  if (!trunkCheckPerformed.value || !trunkCheckResult.value) return { can_modify: false, reason: "待检查放通" };
  const passed = Boolean(trunkCheckResult.value?.summary?.passed);
  return { can_modify: passed, reason: passed ? "目标VLAN已放通，可直接修改" : "目标VLAN未在上下联trunk放通" };
});

const showTrunkCheckSection2 = computed(() => trunkCheckPerformed.value && Boolean(trunkCheckResult.value));

const displayUplinkRows2 = computed(() => {
  if (!showTrunkCheckSection2.value) return [];
  const core = trunkCheckResult.value?.corePortCheck || {};
  const access = trunkCheckResult.value?.accessPortCheck || {};
  return [
    {
      interface_name: core.portName || "-",
      allowed_vlans: core.allowedVlans || "-",
      has_vlan_text: core.allowed ? "是" : "否",
      status: core.allowed ? "已放通" : "未放通",
    },
    {
      interface_name: access.portName || "-",
      allowed_vlans: access.allowedVlans || "-",
      has_vlan_text: access.allowed ? "是" : "否",
      status: access.allowed ? "已放通" : "未放通",
    },
  ];
});

const modifyButtonText2 = computed(() => {
  if (!isNewVlanFilled.value || !isValidNewVlan.value) return "确认修改";
  if (!trunkCheckPerformed.value) return "修改 VLAN";
  return trunkCheckState2.value.can_modify ? "直接修改 VLAN" : "修改 VLAN";
});

const displayUplinkRows = computed(() => {
  if (!showTrunkCheckSection.value) return [];
  return [
    {
      interface_name: locateResult.core_uplink_interface || "-",
      allowed_vlans: locateResult.core_allowed_vlans || "-",
      has_vlan_text: trunkCheckState.value.core_has_vlan ? "是" : "否",
      status: trunkCheckState.value.core_has_vlan ? "已放通" : "未放通",
    },
    {
      interface_name: locateResult.access_uplink_interface || "-",
      allowed_vlans: locateResult.access_allowed_vlans || "-",
      has_vlan_text: trunkCheckState.value.access_has_vlan ? "是" : "否",
      status: trunkCheckState.value.access_has_vlan ? "已放通" : "未放通",
    },
  ];
});

const canModifyVlan = computed(() => Boolean(locateResult.interface_name && locateResult.access_switch?.id) && isValidNewVlan.value);
const modifyButtonText = computed(() => {
  if (!isNewVlanFilled.value || !isValidNewVlan.value) return "确认修改";
  return trunkCheckState.value.can_modify ? "直接修改 VLAN" : "放通并修改 VLAN";
});
const flapResultText = computed(() => {
  if (!ipVlanExecuteResult.refresh_attempted) return "未执行";
  return ipVlanExecuteResult.shutdown_success && ipVlanExecuteResult.undo_shutdown_success ? "成功" : "失败";
});

const clearQueryProgress = () => {
  if (queryProgressTimer) {
    clearInterval(queryProgressTimer);
    queryProgressTimer = null;
  }
  queryProgress.visible = false;
  queryProgress.percent = 0;
  queryProgress.step = "";
};

const startProgressSequence = (steps) => {
  clearQueryProgress();
  if (!steps.length) return;
  queryProgress.visible = true;
  let index = 0;
  const applyStep = () => {
    const current = steps[Math.min(index, steps.length - 1)];
    queryProgress.percent = current.percent;
    queryProgress.step = current.label;
    if (index < steps.length - 1) index += 1;
  };
  applyStep();
  queryProgressTimer = setInterval(applyStep, 1600);
};

const resetIpVlanResult = () => {
  Object.assign(locateResult, {
    target_ip: "",
    mac: "",
    core_switch: null,
    core_uplink_interface: "",
    access_uplink_interface: "",
    access_switch: null,
    interface_name: "",
    current_vlan: "",
    core_allowed_vlans: "",
    access_allowed_vlans: "",
  });
  locateLogs.value = [];
  ipVlanWarnings.value = [];
  pendingMacSelection.value = false;
  macMatchOptions.value = [];
  selectedMacOption.value = "";
  locateErrorMessage.value = "";
  queryStageMessage.value = "";
  showCurrentLocateLogs.value = false;
  trunkCheckLoading.value = false;
  trunkCheckPerformed.value = false;
  trunkCheckResult.value = null;
  Object.assign(ipVlanExecuteResult, {
    id: 0,
    status: "",
    message: "",
    target_ip: "",
    target_mac: "",
    access_switch: null,
    interface_name: "",
    old_vlan: "",
    new_vlan: "",
    core_uplink_added: false,
    access_uplink_added: false,
    vlan_change_success: false,
    shutdown_success: false,
    undo_shutdown_success: false,
    refresh_attempted: false,
    operator: "",
    execute_time: "",
  });
};

const loadIntents = async () => {
  const { data } = await http.get("/config/intents");
  intents.value = data || [];
};

const loadDevices = async () => {
  const { data } = await http.get("/devices", { params: { with_status: false } });
  devices.value = data || [];
  groups.value = [...new Set(devices.value.map((item) => item.group_name).filter(Boolean))].sort();
};

const onIntentChange = () => {
  precheckId.value = "";
};

const onTargetModeChange = () => {
  if (targetMode.value === "all") {
    selectedDevices.value = devices.value.map((item) => item.id);
    return;
  }
  if (targetMode.value === "group") {
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
  selectedDevices.value = devices.value.filter((item) => item.group_name === groupName.value).map((item) => item.id);
};

const runPrecheck = async () => {
  if (!finalDeviceIds.value.length) {
    ElMessage.warning("请先选择目标设备");
    return;
  }

  precheckLoading.value = true;
  try {
    const { data } = await http.post("/config/precheck", {
      intent: intent.value,
      device_ids: finalDeviceIds.value,
      params: currentParams.value,
    });
    precheckId.value = data.precheck_id;
    precheckDetails.value = data.details || [];
    Object.assign(precheckSummary, data.summary || {});
    ElMessage.success("预检查完成");
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "预检查失败");
  } finally {
    precheckLoading.value = false;
  }
};

const fetchJobDetail = async () => {
  const { data } = await http.get(`/config/jobs/${jobId.value}`);
  resultRows.value = data.results || [];
};

const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const { data } = await http.get(`/config/jobs/${jobId.value}/progress`);
      runtime.state = data.state || "running";
      runtime.progress = data.progress || 0;
      runtime.total = data.total || 0;
      runtime.success = data.success || 0;
      runtime.failed = data.failed || 0;
      runtime.skipped = data.skipped || 0;
      runtime.logs = data.logs || runtime.logs;
      if (data.state === "completed" || data.state === "failed") {
        clearInterval(pollTimer);
        pollTimer = null;
        await fetchJobDetail();
        ElMessage.success("配置任务执行完成");
      }
    } catch (_err) {
      clearInterval(pollTimer);
      pollTimer = null;
      ElMessage.error("获取执行进度失败");
    }
  }, 1200);
};

const confirmExecute = async () => {
  if (!canExecute.value) {
    ElMessage.warning("请先执行检查，并确保存在可执行设备");
    return;
  }

  try {
    await ElMessageBox.confirm("确认开始配置下发？系统将自动备份，并在失败时尝试回滚。", "确认执行", {
      type: "warning",
      confirmButtonText: "确认执行",
      cancelButtonText: "取消",
    });
  } catch (_cancel) {
    return;
  }

  executeLoading.value = true;
  try {
    runtime.state = "running";
    runtime.logs = [`[${new Date().toLocaleTimeString()}] 配置任务已启动`];
    const { data } = await http.post("/config/execute", {
      intent: intent.value,
      device_ids: finalDeviceIds.value,
      params: currentParams.value,
      precheck_id: precheckId.value,
      auto_rollback: true,
    });
    jobId.value = data.job_id;
    runtime.total = data.total || 0;
    startPolling();
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "执行失败");
  } finally {
    executeLoading.value = false;
  }
};

const getLocateProgressSteps = () => {
  if (ipVlanForm.query_type === "mac") {
    return [
      { percent: 15, label: "正在连接核心交换机..." },
      { percent: 32, label: "正在查询核心交换机 MAC 表..." },
      { percent: 56, label: "正在定位接入交换机端口..." },
      { percent: 76, label: "正在查询核心互联口 trunk 放通..." },
      { percent: 92, label: "正在查询接入交换机上联口 trunk 放通..." },
    ];
  }

  return [
    { percent: 15, label: "正在连接核心交换机..." },
    { percent: 32, label: "正在查询 ARP / 获取 MAC..." },
    { percent: 56, label: "正在定位接入交换机端口..." },
    { percent: 76, label: "正在查询核心互联口 trunk 放通..." },
    { percent: 92, label: "正在查询接入交换机上联口 trunk 放通..." },
  ];
};

const handleLocateError = (err) => {
  if (err?.code === "ECONNABORTED") {
    locateErrorMessage.value = "查询超时，请检查交换机响应或缩小查询范围";
    locateLogs.value = [{ device: "system", command: "query-timeout", output: "前端等待后端返回超过 120 秒，查询被中断" }];
    showCurrentLocateLogs.value = true;
    ElMessage.error(locateErrorMessage.value);
    return;
  }

  const detail = err?.response?.data?.detail;
  if (detail && typeof detail === "object") {
    locateErrorMessage.value = detail.message || "查询失败";
    locateLogs.value = detail.logs || [];
  } else {
    locateErrorMessage.value = detail || "查询失败";
    locateLogs.value = [];
  }
  if (!locateLogs.value.length && locateErrorMessage.value) {
    locateLogs.value = [{ device: "system", command: "query-error", output: locateErrorMessage.value }];
  }
  showCurrentLocateLogs.value = true;
  ElMessage.error(locateErrorMessage.value);
};

const startLocate = async () => {
  if (ipVlanForm.query_type === "ip") {
    if (!ipVlanForm.target_ip.trim()) {
      ElMessage.warning("请输入终端IP");
      return;
    }
    if (!isValidTargetIp.value) {
      ElMessage.warning("请输入合法的 IPv4 地址");
      return;
    }
  } else {
    if (!String(ipVlanForm.mac_keyword || "").trim()) {
      ElMessage.warning("请输入 MAC 关键字");
      return;
    }
    if (macKeywordValidationMessage.value) {
      ElMessage.warning(macKeywordValidationMessage.value);
      return;
    }
  }

  resetIpVlanResult();
  locateLoading.value = true;
  queryStageMessage.value = ipVlanForm.query_type === "mac" ? "正在根据 MAC 关键字定位端口..." : "正在根据 IP 定位端口...";
  startProgressSequence(getLocateProgressSteps());

  try {
    const { data } = await http.post(
      "/port-query/locate",
      {
        queryType: ipVlanForm.query_type,
        queryValue: ipVlanForm.query_type === "mac" ? ipVlanForm.mac_keyword.trim() : ipVlanForm.target_ip.trim(),
      },
      { timeout: 120000 },
    );

    const payloadData = data?.data || {};
    if (payloadData?.pending_selection) {
      pendingMacSelection.value = true;
      macMatchOptions.value = payloadData.match_options || [];
      selectedMacOption.value = "";
      locateLogs.value = payloadData.logs || [];
      locateErrorMessage.value = payloadData.reason || "";
      showCurrentLocateLogs.value = false;
      return;
    }

    const mapped = {
      target_ip: payloadData.ip || "",
      mac: payloadData.mac || "",
      core_switch: payloadData.coreDevice
        ? { id: payloadData.coreDevice.deviceId, name: payloadData.coreDevice.deviceName, ip: payloadData.coreDevice.managementIp }
        : null,
      access_switch: payloadData.accessSwitch
        ? { id: payloadData.accessSwitch.deviceId, name: payloadData.accessSwitch.deviceName, ip: payloadData.accessSwitch.managementIp }
        : null,
      core_uplink_interface: payloadData.coreUplinkPort || "",
      access_uplink_interface: payloadData.accessUplinkPort || "",
      interface_name: payloadData.accessPort || "",
      current_vlan: payloadData.currentVlan ? String(payloadData.currentVlan) : "",
      core_allowed_vlans: "",
      access_allowed_vlans: "",
    };
    Object.assign(locateResult, mapped);
    locateLogs.value = payloadData?.logs || [];
    locateErrorMessage.value = "";
    showCurrentLocateLogs.value = false;
    ElMessage.success("查询完成");
  } catch (err) {
    handleLocateError(err);
  } finally {
    locateLoading.value = false;
    queryStageMessage.value = "";
    clearQueryProgress();
  }
};

const continueLocateBySelectedMac = async () => {
  const selected = macMatchOptions.value.find((item) => item.mac === selectedMacOption.value);
  if (!selected) {
    ElMessage.warning("请先选择具体 MAC");
    return;
  }

  locateLoading.value = true;
  queryStageMessage.value = "正在根据所选 MAC 继续定位...";
  startProgressSequence(getLocateProgressSteps());

  try {
    const { data } = await http.post(
      "/port-query/locate",
      {
        queryType: "mac",
        queryValue: ipVlanForm.mac_keyword.trim(),
        selectedMac: selected.mac,
        selectedCoreUplink: selected.core_uplink_interface,
      },
      { timeout: 120000 },
    );

    pendingMacSelection.value = false;
    macMatchOptions.value = [];
    selectedMacOption.value = "";
    const payloadData = data?.data || {};
    const mapped = {
      target_ip: payloadData.ip || "",
      mac: payloadData.mac || "",
      core_switch: payloadData.coreDevice
        ? { id: payloadData.coreDevice.deviceId, name: payloadData.coreDevice.deviceName, ip: payloadData.coreDevice.managementIp }
        : null,
      access_switch: payloadData.accessSwitch
        ? { id: payloadData.accessSwitch.deviceId, name: payloadData.accessSwitch.deviceName, ip: payloadData.accessSwitch.managementIp }
        : null,
      core_uplink_interface: payloadData.coreUplinkPort || "",
      access_uplink_interface: payloadData.accessUplinkPort || "",
      interface_name: payloadData.accessPort || "",
      current_vlan: payloadData.currentVlan ? String(payloadData.currentVlan) : "",
      core_allowed_vlans: "",
      access_allowed_vlans: "",
    };
    Object.assign(locateResult, mapped);
    locateLogs.value = payloadData?.logs || [];
    locateErrorMessage.value = "";
    showCurrentLocateLogs.value = false;
    ElMessage.success("查询完成");
  } catch (err) {
    handleLocateError(err);
  } finally {
    locateLoading.value = false;
    queryStageMessage.value = "";
    clearQueryProgress();
  }
};

const loadIpVlanLogs = async () => {
  const { data } = await http.get("/config/ip-vlan/logs", { params: { limit: 50 } });
  ipVlanLogs.value = data || [];
};

const checkTrunkAllow = async () => {
  if (!locateResult.interface_name || !locateResult.access_switch?.id) {
    ElMessage.warning("请先完成端口定位");
    return;
  }
  if (!isNewVlanFilled.value) {
    ElMessage.warning("请先填写新VLAN");
    return;
  }
  if (!isValidNewVlan.value) {
    ElMessage.warning(newVlanValidationMessage.value);
    return;
  }
  trunkCheckLoading.value = true;
  try {
    const { data } = await http.post("/port-query/check-trunk", {
      taskId: "",
      targetVlan: Number(ipVlanForm.new_vlan),
      coreDeviceId: Number(locateResult.core_switch?.id || 0),
      coreUplinkPort: locateResult.core_uplink_interface,
      accessSwitchId: Number(locateResult.access_switch?.id || 0),
      accessUplinkPort: locateResult.access_uplink_interface,
    });
    trunkCheckPerformed.value = true;
    trunkCheckResult.value = data?.data || null;
    if (trunkCheckResult.value?.summary?.passed) ElMessage.success("放通检查通过");
    else ElMessage.warning("放通检查未通过");
  } catch (err) {
    trunkCheckPerformed.value = true;
    trunkCheckResult.value = null;
    ElMessage.error(err?.response?.data?.detail?.message || err?.response?.data?.detail || "放通检查失败");
  } finally {
    trunkCheckLoading.value = false;
  }
};

const confirmIpVlanChange = async () => {
  if (!isNewVlanFilled.value) {
    ElMessage.warning("如需修改VLAN，请先填写新VLAN");
    return;
  }
  if (!isValidNewVlan.value) {
    ElMessage.warning(newVlanValidationMessage.value);
    return;
  }
  if (!locateResult.interface_name || !locateResult.access_switch?.id) {
    ElMessage.warning("请先完成端口定位");
    return;
  }

  const actionText = trunkCheckState.value.can_modify ? "直接修改" : "放通并修改";
  try {
    await ElMessageBox.confirm(
      `确认在 ${locateResult.access_switch?.name || "-"} 的接口 ${locateResult.interface_name || "-"} 上${actionText} VLAN ${ipVlanForm.new_vlan} 吗？`,
      "确认修改",
      { type: "warning", confirmButtonText: actionText, cancelButtonText: "取消" },
    );
  } catch (_cancel) {
    return;
  }

  ipVlanExecuteLoading.value = true;
  try {
    const { data } = await http.post("/port-query/change-vlan", {
      taskId: "",
      ip: locateResult.target_ip || "",
      mac: locateResult.mac || "",
      accessSwitchId: Number(locateResult.access_switch?.id || 0),
      accessPort: locateResult.interface_name,
      currentVlan: locateResult.current_vlan || "",
      targetVlan: Number(ipVlanForm.new_vlan),
      coreDeviceId: Number(locateResult.core_switch?.id || 0),
      coreUplinkPort: locateResult.core_uplink_interface,
      accessUplinkPort: locateResult.access_uplink_interface,
      checkTrunkBeforeChange: true,
      autoFlapPort: true,
      operator: currentOperator.value,
    });
    const payload = data?.data || {};
    const exec = payload.execute || {};
    Object.assign(ipVlanExecuteResult, exec || {});
    ipVlanWarnings.value = exec?.warnings || [];
    if (payload.trunkCheck) {
      trunkCheckPerformed.value = true;
      trunkCheckResult.value = payload.trunkCheck;
    }
    await loadIpVlanLogs();
    showLogDrawer.value = true;
    ElMessage.success(data?.message || "VLAN 修改成功");
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "VLAN 修改失败");
    await loadIpVlanLogs();
  } finally {
    ipVlanExecuteLoading.value = false;
  }
};

watch(() => ipVlanForm.target_ip, () => {
  if (ipVlanForm.query_type === "ip") resetIpVlanResult();
});

watch(() => ipVlanForm.mac_keyword, () => {
  if (ipVlanForm.query_type === "mac") resetIpVlanResult();
});

watch(() => ipVlanForm.query_type, () => {
  resetIpVlanResult();
});

watch(showLogDrawer, async (value) => {
  if (value) await loadIpVlanLogs();
});

onMounted(async () => {
  await Promise.all([loadIntents(), loadDevices(), loadIpVlanLogs()]);
  selectedDevices.value = devices.value.map((item) => item.id);
});

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  clearQueryProgress();
});
</script>

<style scoped>
.section-title {
  font-weight: 700;
}

.sub-title {
  font-weight: 600;
}

.switch-card {
  margin-bottom: 12px;
}

.summary-row {
  margin-bottom: 12px;
}

.result-extra {
  line-height: 1.9;
  text-align: left;
}

.inline-error {
  color: #f56c6c;
  margin: -8px 0 12px 130px;
}

.inline-error-inline {
  margin-left: 130px;
}

.inline-hint {
  color: #409eff;
  margin: -8px 0 12px 130px;
}

.inline-hint-inline {
  margin-left: 130px;
}

.inline-status {
  margin: -8px 0 12px 130px;
  font-size: 13px;
}

.status-success {
  color: #67c23a;
}

.status-warning {
  color: #e6a23c;
}

.query-progress-card {
  margin: 8px 0 0 130px;
  max-width: 520px;
}

.query-progress-text {
  margin-bottom: 10px;
  color: #1f2937;
  font-size: 13px;
}
</style>
