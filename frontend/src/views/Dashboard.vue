<template>
  <LayoutShell>
    <div class="dashboard-page">
      <div class="screen-switch">
        <div>
          <div class="switch-title">视图切换</div>
          <div class="switch-subtitle">
            当前为{{ activeView === "network" ? "网络设备" : "服务器" }}视图，画面每 60 秒自动切换一次，
            鼠标移动、点击或滚轮操作时会暂停自动切换。
          </div>
        </div>
        <div class="switch-pills">
          <button class="switch-pill" :class="{ active: activeView === 'network' }" @click="handleManualViewSwitch('network')">
            网络设备
          </button>
          <button class="switch-pill" :class="{ active: activeView === 'server' }" @click="handleManualViewSwitch('server')">
            服务器
          </button>
        </div>
      </div>

      <div class="stats-grid" :style="statsGridStyle">
        <el-card
          v-for="card in statCards"
          :key="card.key"
          class="glass stat-card"
          :class="{ clickable: card.clickable }"
          @click="card.clickable && handleStatCardClick(card.key)"
        >
          <div class="stat-title">{{ card.label }}</div>
          <div class="stat-num" :class="card.valueClass">{{ card.value }}</div>
        </el-card>
      </div>

      <div v-if="activeView === 'network'" class="content-grid">
        <el-card class="glass topology-card server-topology-card">
          <template #header>
            <div class="panel-title">网络拓扑</div>
          </template>
          <div
            class="topology-canvas network-topology-canvas"
            :class="`topology-canvas--${networkTopologyMode}`"
            :style="networkTopologyVars"
          >
            <div
              class="network-topology-tree"
              :class="`network-topology-tree--${networkTopologyMode}`"
              :style="networkTopologyTreeStyle"
            >
              <div class="tree-level tree-level--single">
                <button
                  type="button"
                  class="topology-node topology-node--internet is-static"
                  :class="`topology-node--${networkTopologyMode}`"
                >
                  <span class="topology-node__icon topology-node__icon--image">
                    <img :src="networkNodeImage('internet', 'online')" alt="Internet" />
                  </span>
                  <span class="topology-node__label">Internet</span>
                </button>
              </div>

              <div class="tree-connector"></div>

              <div class="tree-level tree-level--single">
                <button
                  type="button"
                  class="topology-node topology-node--router"
                  :class="[`topology-node--${networkTopologyMode}`, topologyStatusClass(networkViewModel.router.status), { 'topology-node--selected': selectedNetworkDevice.id === networkViewModel.router.id }]"
                  @click="handleNetworkNodeClick(networkViewModel.router)"
                >
                  <span class="topology-node__icon topology-node__icon--image">
                    <img :src="networkNodeImage('router', networkViewModel.router.status)" :alt="networkViewModel.router.name" />
                  </span>
                  <span class="topology-node__label">{{ networkViewModel.router.name }}</span>
                  <span class="topology-node__meta">{{ networkViewModel.router.ip || '-' }}</span>
                </button>
              </div>

              <div class="tree-connector"></div>

              <div class="tree-level tree-level--single">
                <button
                  type="button"
                  class="topology-node topology-node--core-switch"
                  :class="[`topology-node--${networkTopologyMode}`, topologyStatusClass(networkViewModel.core.status), { 'topology-node--selected': selectedNetworkDevice.id === networkViewModel.core.id }]"
                  @click="handleNetworkNodeClick(networkViewModel.core)"
                >
                  <span class="topology-node__icon topology-node__icon--image">
                    <img :src="networkNodeImage('core-switch', networkViewModel.core.status)" :alt="networkViewModel.core.name" />
                  </span>
                  <span class="topology-node__label">{{ networkViewModel.core.name }}</span>
                  <span class="topology-node__meta">{{ networkViewModel.core.ip || '-' }}</span>
                </button>
              </div>

              <div class="tree-connector"></div>

              <div class="tree-level tree-level--groups">
                <div
                  v-for="group in networkViewModel.groups"
                  :key="group.groupKey"
                  class="topology-group"
                  :class="[`topology-group--${networkTopologyMode}`, { 'topology-group--server': group.groupKey === 'SERVER' }]"
                >
                  <div class="topology-group__header">
                    <span class="topology-group__title">{{ group.groupName }}</span>
                    <span class="topology-group__count">{{ group.devices.length }} 台</span>
                  </div>
                  <div class="topology-group__body">
                    <button
                      v-for="device in group.devices"
                      :key="device.id"
                      type="button"
                      class="topology-node topology-node--access-switch"
                      :class="[`topology-node--${networkTopologyMode}`, topologyStatusClass(device.status), { 'topology-node--selected': selectedNetworkDevice.id === device.id }]"
                      @click="handleNetworkNodeClick(device)"
                    >
                      <span class="topology-node__icon topology-node__icon--image">
                        <img :src="networkNodeImage('access-switch', device.status)" :alt="device.name" />
                      </span>
                      <span class="topology-node__label">{{ device.name }}</span>
                      <span class="topology-node__meta">{{ device.ip || '-' }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="legend server-legend">
            <span><i class="dot normal"></i> 在线</span>
            <span><i class="dot alarm"></i> 异常</span>
            <span><i class="dot offline"></i> 离线</span>
            <span><i class="dot unknown"></i> 未知</span>
            <span class="legend-device"><img :src="networkNodeImage('router', 'online')" alt="router" /> 路由器</span>
            <span class="legend-device"><img :src="networkNodeImage('core-switch', 'online')" alt="core-switch" /> 核心交换机</span>
            <span class="legend-device"><img :src="networkNodeImage('access-switch', 'online')" alt="access-switch" /> 接入交换机</span>
          </div>
        </el-card>

        <div class="right-stack">
          <el-card class="glass side-card">
            <template #header>
              <div class="panel-title">设备详情</div>
            </template>
            <div v-if="selectedNetworkDevice.id" class="detail-box">
              <div class="detail-item"><span>名称</span><b>{{ selectedNetworkDevice.name }}</b></div>
              <div class="detail-item"><span>IP</span><b>{{ selectedNetworkDevice.ip }}</b></div>
              <div class="detail-item"><span>类型</span><b>{{ networkRoleLabel(selectedNetworkDevice.role) }}</b></div>
              <div class="detail-item"><span>楼层</span><b>{{ selectedNetworkDevice.floor || "-" }}</b></div>
              <div class="detail-item"><span>状态</span><b>{{ statusLabel(selectedNetworkDevice.status) }}</b></div>
              <div class="detail-item"><span>SSH</span><b>{{ selectedNetworkDevice.ssh_status || "unknown" }}</b></div>
              <div class="detail-item"><span>Ping</span><b>{{ selectedNetworkDevice.ping_status || "unknown" }}</b></div>
              <div class="detail-item"><span>最近检测</span><b>{{ selectedNetworkDevice.last_check_time || "-" }}</b></div>
              <div class="detail-item detail-span-2"><span>说明</span><b>{{ selectedNetworkDevice.status_reason || "-" }}</b></div>
            </div>
            <el-empty v-else description="点击拓扑节点查看设备详情" :image-size="56" />
          </el-card>

          <el-card class="glass side-card">
            <template #header>
              <div class="panel-title">最近任务</div>
            </template>
            <el-table :data="recentTasks" border size="small" height="190">
              <el-table-column prop="id" label="ID" width="66" />
              <el-table-column prop="task_type" label="任务" width="90">
                <template #default="{ row }">{{ taskTypeLabel(row.task_type) }}</template>
              </el-table-column>
              <el-table-column prop="status_label" label="状态" width="96" />
              <el-table-column prop="start_time_label" label="开始时间" min-width="130" />
            </el-table>
          </el-card>
        </div>
      </div>

      <div v-else class="content-grid">
        <el-card class="glass topology-card">
          <template #header>
            <div class="panel-title">服务器拓扑</div>
          </template>
          <div class="topology-canvas server-topology-canvas">
            <div class="server-topology-tree">
              <div class="tree-level tree-level--single">
                <button
                  type="button"
                  class="topology-node topology-node--core-switch topology-node--detail"
                  :class="[topologyStatusClass(serverViewModel.core.status), { 'topology-node--selected': selectedServerNode.node_kind === 'core' }]"
                  @click="handleServerNodeClick({ node_kind: 'core', ...serverViewModel.core, switch_count: serverViewModel.switches.length, server_count: serverTopology.servers.length })"
                >
                  <span class="topology-node__icon topology-node__icon--image">
                    <img :src="networkNodeImage('core-switch', serverViewModel.core.status)" :alt="serverViewModel.core.name" />
                  </span>
                  <span class="topology-node__label">{{ serverViewModel.core.name }}</span>
                  <span class="topology-node__meta">{{ serverViewModel.core.ip || '-' }}</span>
                </button>
              </div>

              <div class="tree-connector"></div>

              <div class="tree-level tree-level--groups">
                <div
                  v-for="switchNode in serverViewModel.switches"
                  :key="switchNode.name"
                  class="topology-group topology-group--detail"
                >
                  <div class="topology-group__header">
                    <button
                      type="button"
                      class="topology-node topology-node--access-switch topology-node--detail topology-node--group-header"
                      :class="[topologyStatusClass(switchNode.status), { 'topology-node--selected': selectedServerNode.node_kind === 'server_switch' && selectedServerNode.name === switchNode.name }]"
                      @click="handleServerNodeClick({ node_kind: 'server_switch', ...switchNode })"
                    >
                      <span class="topology-node__icon topology-node__icon--image">
                        <img :src="networkNodeImage('access-switch', switchNode.status)" :alt="switchNode.name" />
                      </span>
                      <span class="topology-node__label">{{ switchNode.name }}</span>
                      <span class="topology-node__meta">{{ switchNode.server_count || 0 }} 台服务器</span>
                    </button>
                  </div>
                  <div class="topology-group__body server-topology-group__body">
                    <button
                      v-for="server in switchNode.servers"
                      :key="server.id"
                      type="button"
                      class="topology-node topology-node--server-leaf topology-node--detail"
                      :class="[topologyStatusClass(server.topology_status), { 'topology-node--selected': selectedServerNode.node_kind === 'server' && selectedServerNode.id === server.id }]"
                      @click="handleServerNodeClick({ node_kind: 'server', ...server })"
                    >
                      <span class="topology-node__icon topology-node__icon--image">
                        <img :src="serverNodeImage(server.topology_status)" :alt="server.name" />
                      </span>
                      <span class="topology-node__label">{{ server.name }}</span>
                      <span class="topology-node__meta">{{ server.ip || '-' }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="legend">
            <span><i class="dot normal"></i> 正常</span>
            <span><i class="dot alarm"></i> 告警</span>
            <span><i class="dot offline"></i> 离线</span>
            <span><i class="dot unknown"></i> 未检测</span>
          </div>
        </el-card>

        <div class="right-stack">
          <el-card class="glass side-card">
            <template #header>
              <div class="panel-title">设备详情</div>
            </template>
            <div v-if="selectedServerNode.node_kind === 'server'" class="detail-box">
              <div class="detail-item"><span>设备名称</span><b>{{ selectedServerNode.name || "-" }}</b></div>
              <div class="detail-item"><span>设备类型</span><b>{{ selectedServerNode.device_type || "服务器" }}</b></div>
              <div class="detail-item"><span>IP</span><b>{{ selectedServerNode.ip || "-" }}</b></div>
              <div class="detail-item"><span>主机名</span><b>{{ selectedServerNode.hostname || "-" }}</b></div>
              <div class="detail-item"><span>状态</span><b>{{ statusLabel(selectedServerNode.topology_status) }}</b></div>
              <div class="detail-item"><span>所属分组</span><b>{{ selectedServerNode.group_name || "-" }}</b></div>
              <div class="detail-item"><span>操作系统</span><b>{{ serverOsLabel(selectedServerNode) }}</b></div>
              <div class="detail-item"><span>MAC</span><b>{{ selectedServerNode.server_mac || "-" }}</b></div>
              <div class="detail-item"><span>所属服务器交换机</span><b>{{ selectedServerNode.server_switch_name || selectedServerNode.assigned_switch || "-" }}</b></div>
              <div class="detail-item"><span>核心上联口</span><b>{{ selectedServerNode.core_uplink_interface || "-" }}</b></div>
              <div class="detail-item"><span>交换机端口</span><b>{{ selectedServerNode.server_switch_port || "-" }}</b></div>
              <div class="detail-item" :class="{ 'detail-item--alert': serverFieldAlert('core', selectedServerNode) }"><span>核心交换机连通</span><b>{{ pingStatusLabel(selectedServerNode.core_ping_status) }}</b></div>
              <div class="detail-item"><span>最近巡检</span><b>{{ parseTime(selectedServerNode.last_checked_at) }}</b></div>
              <div class="detail-item"><span>最后在线时间</span><b>{{ parseTime(selectedServerNode.last_online_time || selectedServerNode.last_seen_at) }}</b></div>
              <div class="detail-item" :class="{ 'detail-item--alert': serverFieldAlert('cpu', selectedServerNode) }"><span>CPU</span><b>{{ metricValue(selectedServerNode.cpu_usage) }}</b></div>
              <div class="detail-item" :class="{ 'detail-item--alert': serverFieldAlert('memory', selectedServerNode) }"><span>内存</span><b>{{ metricValue(selectedServerNode.memory_usage) }}</b></div>
              <div class="detail-item" :class="{ 'detail-item--alert': serverFieldAlert('disk', selectedServerNode) }"><span>磁盘</span><b>{{ metricValue(selectedServerNode.disk_usage) }}</b></div>
              <div class="detail-item detail-span-2" :class="{ 'detail-item--alert': serverFieldAlert('reason', selectedServerNode) }"><span>说明</span><b>{{ serverDescription(selectedServerNode) }}</b></div>
            </div>
            <div v-else-if="selectedServerNode.node_kind === 'server_switch'" class="detail-box">
              <div class="detail-item"><span>交换机名称</span><b>{{ selectedServerNode.name || "-" }}</b></div>
              <div class="detail-item"><span>IP</span><b>{{ selectedServerNode.ip || "-" }}</b></div>
              <div class="detail-item"><span>状态</span><b>{{ statusLabel(selectedServerNode.status) }}</b></div>
              <div class="detail-item"><span>挂载服务器</span><b>{{ selectedServerNode.server_count || 0 }}</b></div>
              <div class="detail-item detail-span-2"><span>说明</span><b>{{ selectedServerNode.status_reason || "-" }}</b></div>
            </div>
            <div v-else-if="selectedServerNode.node_kind === 'core'" class="detail-box">
              <div class="detail-item"><span>设备名称</span><b>{{ selectedServerNode.name || "-" }}</b></div>
              <div class="detail-item"><span>IP</span><b>{{ selectedServerNode.ip || "-" }}</b></div>
              <div class="detail-item"><span>状态</span><b>{{ statusLabel(selectedServerNode.status) }}</b></div>
              <div class="detail-item"><span>下挂交换机</span><b>{{ selectedServerNode.switch_count || 0 }}</b></div>
              <div class="detail-item"><span>下挂服务器</span><b>{{ selectedServerNode.server_count || 0 }}</b></div>
              <div class="detail-item detail-span-2"><span>说明</span><b>{{ selectedServerNode.status_reason || "-" }}</b></div>
            </div>
            <div v-else-if="selectedServerNode.node_kind === 'router'" class="detail-box">
              <div class="detail-item"><span>设备名称</span><b>{{ selectedServerNode.name || "-" }}</b></div>
              <div class="detail-item"><span>IP</span><b>{{ selectedServerNode.ip || "-" }}</b></div>
              <div class="detail-item"><span>状态</span><b>{{ statusLabel(selectedServerNode.status) }}</b></div>
              <div class="detail-item detail-span-2"><span>说明</span><b>{{ selectedServerNode.status_reason || "-" }}</b></div>
            </div>
            <el-empty v-else :description="serverDetailEmptyText" :image-size="56" />
          </el-card>

          <el-card class="glass side-card">
            <template #header>
              <div class="panel-title">最近任务</div>
            </template>
            <el-table :data="recentTasks" border size="small" height="190">
              <el-table-column prop="id" label="ID" width="66" />
              <el-table-column prop="task_type" label="任务" width="90">
                <template #default="{ row }">{{ taskTypeLabel(row.task_type) }}</template>
              </el-table-column>
              <el-table-column prop="status_label" label="状态" width="96" />
              <el-table-column prop="start_time_label" label="开始时间" min-width="130" />
            </el-table>
          </el-card>
        </div>
      </div>
    </div>
  </LayoutShell>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { DataSet } from "vis-data";
import { Network } from "vis-network";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const router = useRouter();
const networkTopologyRef = ref(null);
const serverTopologyRef = ref(null);
const activeView = ref("network");

const networkStats = reactive({
  totalDevices: 0,
  onlineDevices: 0,
  offlineDevices: 0,
  alarmDevices: 0,
  todayTasks: 0,
});

const serverStats = reactive({
  totalDevices: 0,
  onlineDevices: 0,
  offlineDevices: 0,
  warningDevices: 0,
  criticalDevices: 0,
  todayTasks: 0,
});

const networkDevices = ref([]);
const recentTasksNetwork = ref([]);
const recentTasksServer = ref([]);
const recentTasks = computed(() => (activeView.value === "network" ? recentTasksNetwork.value : recentTasksServer.value));
const selectedNetworkDevice = reactive({});
const selectedServerNode = reactive({});
const serverTopology = reactive({
  _refreshing: false,
  generated_at: "",
  stats: {
    total_servers: 0,
    normal_servers: 0,
    alarm_servers: 0,
    offline_servers: 0,
    unknown_servers: 0,
  },
  nodes: {
    internet: {},
    router: {},
    core: {},
    server_switches: [],
  },
  servers: [],
});

let networkInstance = null;
let serverInstance = null;
let refreshTimer = null;
let rotateTimer = null;
let nextSwitchAt = Date.now();
const SCREEN_SWITCH_INTERVAL_MS = 60 * 1000;
let loadRunning = false;

const statusLabel = (status) =>
  ({
    normal: "正常",
    online: "在线",
    alarm: "告警",
    offline: "离线",
    unknown: "未检测",
  }[status] || "未知");

const pingStatusLabel = (status) =>
  ({
    reachable: "可达",
    unreachable: "不可达",
    unknown: "未检测",
  }[status] || "未检测");

const taskTypeLabel = (type) =>
  ({
    audit: "网络巡检",
    ntp: "NTP批量配置（已废弃）",
    snmp: "SNMP",
    server_inspection: "服务器巡检",
  }[type] || type);

const networkRoleLabel = (role) =>
  ({
    router: "路由器",
    core_switch: "核心交换机",
    access_switch: "接入交换机",
    unknown: "未知设备",
  }[role] || role);

const parseTime = (value) => {
  if (!value) return "-";
  return String(value).replace("T", " ").slice(0, 19);
};

const metricValue = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(0)}%`;
};

const serverOsLabel = (server = {}) => {
  const explicit = [server.os_name, server.os, server.platform, server.platform_name].find((item) => String(item || "").trim());
  if (explicit) return explicit;
  const serverType = String(server.server_type || "").trim().toLowerCase();
  if (serverType === "windows") return "Windows";
  if (serverType === "linux") return "Linux";
  return "-";
};

const serverDescription = (server = {}) =>
  server.description || server.topology_reason || server.assignment_reason || server.last_error || "-";

const serverFieldAlert = (field, server = {}) => {
  const topologyStatus = String(server.topology_status || "").toLowerCase();
  const corePingStatus = String(server.core_ping_status || "").toLowerCase();
  const cpu = Number(server.cpu_usage || 0);
  const memory = Number(server.memory_usage || 0);
  const disk = Number(server.disk_usage || 0);
  const reason = String(serverDescription(server) || "").toLowerCase();

  if (field === "status") return topologyStatus === "alarm" || topologyStatus === "offline";
  if (field === "core") return corePingStatus && corePingStatus !== "reachable" && corePingStatus !== "unknown";
  if (field === "cpu") return cpu >= 85;
  if (field === "memory") return memory >= 85;
  if (field === "disk") return disk >= 85;
  if (field === "reason") {
    return (
      topologyStatus === "alarm" ||
      topologyStatus === "offline" ||
      reason.includes("异常") ||
      reason.includes("超") ||
      reason.includes("失败") ||
      reason.includes("不可达")
    );
  }
  return false;
};

const currentStats = computed(() => (activeView.value === "network" ? networkStats : serverStats));
const networkTopologyMode = computed(() => "overview");

const NETWORK_TOPOLOGY_LAYOUT_CONFIG = {
  overview: {
    treeMinWidth: 760,
    canvasPadding: "14px 12px 16px",
    connectorHeight: "24px",
    connectorMargin: "4px 0",
    groupWidth: "224px",
    groupMinHeight: "150px",
    groupPadding: "10px 10px 12px",
    groupBodyGap: "8px",
    groupTitleFontSize: "13px",
    groupCountFontSize: "11px",
    groupHeaderMargin: "10px",
    routerWidth: "126px",
    routerMinHeight: "102px",
    coreWidth: "152px",
    coreMinHeight: "112px",
    accessMinHeight: "104px",
    internetWidth: "110px",
    internetMinHeight: "92px",
    nodePadding: "9px 8px 8px",
    nodeGap: "4px",
    nodeRadius: "14px",
    iconWidth: "52px",
    iconHeight: "60px",
    coreIconWidth: "60px",
    coreIconHeight: "70px",
    labelFontSize: "12px",
    metaFontSize: "10px",
  },
  detail: {
    treeMinWidth: 820,
    canvasPadding: "22px 18px 26px",
    connectorHeight: "42px",
    connectorMargin: "8px 0",
    groupWidth: "260px",
    groupMinHeight: "180px",
    groupPadding: "14px 14px 16px",
    groupBodyGap: "12px",
    groupTitleFontSize: "14px",
    groupCountFontSize: "12px",
    groupHeaderMargin: "14px",
    routerWidth: "152px",
    routerMinHeight: "122px",
    coreWidth: "178px",
    coreMinHeight: "134px",
    accessMinHeight: "126px",
    internetWidth: "136px",
    internetMinHeight: "118px",
    nodePadding: "12px 12px 10px",
    nodeGap: "6px",
    nodeRadius: "16px",
    iconWidth: "62px",
    iconHeight: "72px",
    coreIconWidth: "72px",
    coreIconHeight: "84px",
    labelFontSize: "13px",
    metaFontSize: "11px",
  },
};

const networkTopologyLayout = computed(() => NETWORK_TOPOLOGY_LAYOUT_CONFIG[networkTopologyMode.value]);

const getOverviewScale = (contentHeight, containerHeight) => {
  const ratio = containerHeight / Math.max(contentHeight, 1);
  if (ratio >= 1) return 1;
  if (ratio >= 0.92) return 0.92;
  if (ratio >= 0.88) return 0.88;
  return 0.85;
};

const networkTopologyVars = computed(() => {
  const layout = networkTopologyLayout.value;
  return {
    "--network-tree-min-width": `${layout.treeMinWidth}px`,
    "--network-canvas-padding": layout.canvasPadding,
    "--network-connector-height": layout.connectorHeight,
    "--network-connector-margin": layout.connectorMargin,
    "--network-group-width": layout.groupWidth,
    "--network-group-min-height": layout.groupMinHeight,
    "--network-group-padding": layout.groupPadding,
    "--network-group-body-gap": layout.groupBodyGap,
    "--network-group-title-font-size": layout.groupTitleFontSize,
    "--network-group-count-font-size": layout.groupCountFontSize,
    "--network-group-header-margin": layout.groupHeaderMargin,
    "--network-router-width": layout.routerWidth,
    "--network-router-min-height": layout.routerMinHeight,
    "--network-core-width": layout.coreWidth,
    "--network-core-min-height": layout.coreMinHeight,
    "--network-access-min-height": layout.accessMinHeight,
    "--network-internet-width": layout.internetWidth,
    "--network-internet-min-height": layout.internetMinHeight,
    "--network-node-padding": layout.nodePadding,
    "--network-node-gap": layout.nodeGap,
    "--network-node-radius": layout.nodeRadius,
    "--network-icon-width": layout.iconWidth,
    "--network-icon-height": layout.iconHeight,
    "--network-core-icon-width": layout.coreIconWidth,
    "--network-core-icon-height": layout.coreIconHeight,
    "--network-node-label-font-size": layout.labelFontSize,
    "--network-node-meta-font-size": layout.metaFontSize,
  };
});

const networkTopologyScale = computed(() => {
  if (networkTopologyMode.value !== "overview") return 1;
  const groupCount = Math.max(networkViewModel.value.groups.length, 1);
  const maxGroupDevices = Math.max(...networkViewModel.value.groups.map((group) => group.devices.length), 1);
  const estimatedHeight = 300 + Math.ceil(maxGroupDevices / 2) * 120;
  const estimatedWidth = groupCount * 240 + Math.max(groupCount - 1, 0) * 18;
  const heightScale = getOverviewScale(estimatedHeight, 830);
  const widthScale = getOverviewScale(estimatedWidth, 900);
  return Math.min(1, heightScale, widthScale);
});

const networkTopologyTreeStyle = computed(() => {
  if (networkTopologyMode.value !== "overview" || networkTopologyScale.value >= 1) {
    return {};
  }
  return {
    transform: `scale(${networkTopologyScale.value})`,
    transformOrigin: "top center",
  };
});

const legacyStatCards = computed(() => [
  { key: "total", label: "总设备数", value: currentStats.value.totalDevices, valueClass: "", clickable: false },
  { key: "online", label: "在线", value: currentStats.value.onlineDevices, valueClass: "status-normal", clickable: true },
  { key: "offline", label: "离线", value: currentStats.value.offlineDevices, valueClass: "status-offline", clickable: true },
  { key: "alarm", label: "异常", value: currentStats.value.alarmDevices, valueClass: "status-alarm", clickable: true },
  { key: "today_tasks", label: "今日任务", value: currentStats.value.todayTasks, valueClass: "", clickable: false },
]);

const statCards = computed(() => {
  if (activeView.value === "server") {
    return [
      { key: "total", label: "设备总数", value: serverStats.totalDevices, valueClass: "", clickable: false },
      { key: "online", label: "在线", value: serverStats.onlineDevices, valueClass: "status-normal", clickable: true },
      { key: "offline", label: "离线", value: serverStats.offlineDevices, valueClass: "status-offline", clickable: true },
      { key: "warning", label: "告警", value: serverStats.warningDevices, valueClass: "status-alarm", clickable: false },
      { key: "critical", label: "严重", value: serverStats.criticalDevices, valueClass: "status-offline", clickable: false },
      { key: "today_tasks", label: "今日任务", value: serverStats.todayTasks, valueClass: "", clickable: false },
    ];
  }
  return legacyStatCards.value;
});

const statsGridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${statCards.value.length}, minmax(0, 1fr))`,
}));

const serverDetailEmptyText = computed(() =>
  serverTopology.servers.length ? "点击拓扑节点查看设备详情" : "暂无服务器数据",
);

const setStats = (target, source = {}) => {
  target.totalDevices = source.total_devices || 0;
  target.onlineDevices = source.online_devices || 0;
  target.offlineDevices = source.offline_devices || 0;
  if ("alarmDevices" in target) target.alarmDevices = source.alarm_devices || 0;
  if ("warningDevices" in target) target.warningDevices = source.warning_devices || 0;
  if ("criticalDevices" in target) target.criticalDevices = source.critical_devices || 0;
  target.todayTasks = source.today_tasks || 0;
};

const statusColor = (status) => {
  if (status === "normal" || status === "online") {
    return { background: "#16a34a", border: "#22c55e" };
  }
  if (status === "alarm") {
    return { background: "#ea580c", border: "#fb923c" };
  }
  if (status === "offline") {
    return { background: "#dc2626", border: "#ef4444" };
  }
  return { background: "#64748b", border: "#94a3b8" };
};

const topologyStatusClass = (status) => {
  if (status === "normal" || status === "online") return "topology-node--online";
  if (status === "alarm") return "topology-node--abnormal";
  if (status === "offline") return "topology-node--offline";
  return "topology-node--unknown";
};

const buildNodeSvg = (kind, status) => {
  const palette =
    status === "normal" || status === "online"
      ? { stroke: "#22c55e", glow: "#16a34a", accent: "#86efac", base: "#08192d" }
      : status === "alarm"
        ? { stroke: "#fb923c", glow: "#ea580c", accent: "#fdba74", base: "#1c1917" }
        : status === "offline"
          ? { stroke: "#ef4444", glow: "#dc2626", accent: "#fca5a5", base: "#200d12" }
          : { stroke: "#94a3b8", glow: "#64748b", accent: "#cbd5e1", base: "#0f172a" };

  const body =
    kind === "router"
      ? `
        <ellipse cx="52" cy="104" rx="30" ry="9" fill="rgba(15,23,42,0.35)"/>
        <g filter="url(#g)">
          <circle cx="52" cy="48" r="25" fill="${palette.base}" stroke="${palette.stroke}" stroke-width="4"/>
          <path d="M34 48h36M52 30v36" stroke="${palette.accent}" stroke-width="4" stroke-linecap="round"/>
          <path d="M40 36l-8-8M64 36l8-8M40 60l-8 8M64 60l8 8" stroke="${palette.accent}" stroke-width="3.4" stroke-linecap="round"/>
        </g>
      `
      : kind === "core-switch"
        ? `
          <ellipse cx="52" cy="108" rx="28" ry="8" fill="rgba(15,23,42,0.35)"/>
          <g filter="url(#g)">
            <rect x="18" y="18" width="68" height="56" rx="10" fill="${palette.base}" stroke="${palette.stroke}" stroke-width="4"/>
            <rect x="24" y="27" width="56" height="10" rx="4" fill="${palette.accent}" opacity="0.95"/>
            <rect x="24" y="44" width="56" height="8" rx="4" fill="${palette.accent}" opacity="0.72"/>
            <rect x="24" y="58" width="22" height="6" rx="3" fill="${palette.accent}" opacity="0.65"/>
            <rect x="36" y="80" width="32" height="12" rx="4" fill="${palette.stroke}" opacity="0.95"/>
          </g>
        `
        : kind === "access-switch"
          ? `
            <ellipse cx="52" cy="105" rx="26" ry="8" fill="rgba(15,23,42,0.3)"/>
            <g filter="url(#g)">
              <rect x="20" y="28" width="64" height="36" rx="9" fill="${palette.base}" stroke="${palette.stroke}" stroke-width="4"/>
              <rect x="27" y="37" width="50" height="8" rx="4" fill="${palette.accent}" opacity="0.9"/>
              <rect x="27" y="50" width="30" height="6" rx="3" fill="${palette.accent}" opacity="0.7"/>
              <circle cx="69" cy="53" r="3" fill="${palette.stroke}"/>
            </g>
          `
          : `
            <ellipse cx="52" cy="105" rx="26" ry="8" fill="rgba(15,23,42,0.3)"/>
            <g filter="url(#g)">
              <circle cx="52" cy="46" r="24" fill="${palette.base}" stroke="${palette.stroke}" stroke-width="4"/>
              <path d="M36 47c6-8 26-8 32 0M35 56c8 7 26 7 34 0M52 30v32" stroke="${palette.accent}" stroke-width="3.6" stroke-linecap="round"/>
            </g>
          `;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="104" height="120" viewBox="0 0 104 120">
      <defs>
        <filter id="g" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="${palette.glow}" flood-opacity="0.35"/>
        </filter>
      </defs>
      ${body}
    </svg>
  `;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
};

const networkNodeImage = (kind, status) => buildNodeSvg(kind, status);

const serverNodeImage = (status) => {
  const palette =
    status === "normal" || status === "online"
      ? { stroke: "#22c55e", glow: "#16a34a", accent: "#86efac" }
      : status === "alarm"
        ? { stroke: "#fb923c", glow: "#ea580c", accent: "#fdba74" }
        : status === "offline"
          ? { stroke: "#ef4444", glow: "#dc2626", accent: "#fca5a5" }
          : { stroke: "#94a3b8", glow: "#64748b", accent: "#cbd5e1" };

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="96" height="120" viewBox="0 0 96 120">
      <defs>
        <filter id="g" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="${palette.glow}" flood-opacity="0.35"/>
        </filter>
      </defs>
      <ellipse cx="48" cy="108" rx="26" ry="8" fill="rgba(15,23,42,0.35)"/>
      <g filter="url(#g)">
        <rect x="21" y="20" width="54" height="56" rx="7" fill="#0f172a" stroke="${palette.stroke}" stroke-width="4"/>
        <rect x="27" y="28" width="42" height="9" rx="3" fill="${palette.accent}" opacity="0.9"/>
        <rect x="27" y="43" width="42" height="9" rx="3" fill="${palette.accent}" opacity="0.75"/>
        <rect x="27" y="58" width="26" height="8" rx="3" fill="${palette.accent}" opacity="0.6"/>
        <rect x="35" y="79" width="26" height="10" rx="4" fill="${palette.stroke}" opacity="0.95"/>
        <rect x="31" y="89" width="34" height="7" rx="3" fill="${palette.accent}" opacity="0.75"/>
      </g>
    </svg>
  `;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
};

const isPreferredAdServer = (server) => {
  const bag = [
    server?.name,
    server?.hostname,
    server?.group_name,
    server?.description,
    server?.topology_reason,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return /(^|\b)(ad|domain|dc|域控|域控制器)(\b|$)/.test(bag);
};

const getPreferredServer = (servers = []) => {
  return (
    servers.find((item) => isPreferredAdServer(item)) ||
    servers.find((item) => item.topology_status === "normal" || item.status === "online") ||
    servers[0] ||
    null
  );
};

const getServerNodeId = (serverId) => `server-node-${serverId}`;

const extractFloorKey = (name = "", floor = "") => {
  const byFloor = String(floor || "").trim().toUpperCase();
  if (/^\d+F$/.test(byFloor)) return byFloor;
  const match = String(name || "").match(/(\d+F)/i);
  return match ? match[1].toUpperCase() : null;
};

const NETWORK_GROUP_RENDER_ORDER = ["17F", "18F", "SERVER", "UNGROUPED"];

const resolveNetworkGroupKey = (device) => {
  const name = String(device?.name || "").toUpperCase();
  if (name.includes("SERVER-SW")) return "SERVER";
  const floorKey = extractFloorKey(device?.name, device?.floor);
  if (floorKey === "17F") return "17F";
  if (floorKey === "18F") return "18F";
  if (floorKey) return floorKey;
  return "UNGROUPED";
};

const networkGroupLabel = (groupKey) => {
  if (groupKey === "SERVER") return "服务器交换机组";
  if (groupKey === "UNGROUPED") return "未分组交换机";
  return `${groupKey}交换机组`;
};

const inferNetworkRole = (device = {}) => {
  const bag = `${device.name || ""} ${device.device_type || ""} ${device.group_name || ""} ${device.location || ""}`.toLowerCase();
  if (["sz-router", "router", "路由", "ar"].some((key) => bag.includes(key))) return "router";
  if (["core", "核心"].some((key) => bag.includes(key))) return "core_switch";
  if (["switch", "sw", "交换"].some((key) => bag.includes(key))) return "access_switch";
  return "access_switch";
};

const normalizeNetworkDevicesFallback = (rows = []) => {
  const now = new Date();
  const ts = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(
    now.getHours(),
  ).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;

  return (rows || []).map((row) => {
    const role = inferNetworkRole(row);
    const status = row.status === "online" ? "normal" : row.status === "offline" ? "offline" : "unknown";
    return {
      ...row,
      role,
      floor: row.floor || resolveNetworkGroupKey(row),
      status,
      ping_status: row.status || "unknown",
      ssh_status: "skipped",
      last_check_time: ts,
      status_reason: row.status === "online" ? "Ping可达（快速检测）" : row.status === "offline" ? "Ping不可达（快速检测）" : "未检测",
    };
  });
};

const networkViewModel = computed(() => {
  const fallbackRouter = { id: "virtual-router", name: "路由器", ip: "-", role: "router", status: "unknown" };
  const fallbackCore = { id: "virtual-core", name: "核心交换机", ip: "-", role: "core_switch", status: "unknown" };
  const routerNode = networkDevices.value.find((item) => item.role === "router") || fallbackRouter;
  const coreNode = networkDevices.value.find((item) => item.role === "core_switch") || fallbackCore;
  const accessNodes = networkDevices.value
    .filter((item) => item.role === "access_switch")
    .sort((a, b) => {
      const floorSort = String(a.floor || "").localeCompare(String(b.floor || ""), "zh-CN");
      if (floorSort !== 0) return floorSort;
      return String(a.name || "").localeCompare(String(b.name || ""), "zh-CN");
    });

  const groupMap = new Map();
  accessNodes.forEach((device) => {
    const key = resolveNetworkGroupKey(device);
    if (!groupMap.has(key)) {
      groupMap.set(key, {
        groupKey: key,
        groupName: networkGroupLabel(key),
        devices: [],
      });
    }
    groupMap.get(key).devices.push(device);
  });

  const groups = Array.from(groupMap.values()).sort((a, b) => {
    const indexA = NETWORK_GROUP_RENDER_ORDER.indexOf(a.groupKey);
    const indexB = NETWORK_GROUP_RENDER_ORDER.indexOf(b.groupKey);
    if (indexA >= 0 && indexB >= 0) return indexA - indexB;
    if (indexA >= 0) return -1;
    if (indexB >= 0) return 1;
    return a.groupKey.localeCompare(b.groupKey, "zh-CN", { numeric: true });
  });

  return {
    router: routerNode,
    core: coreNode,
    groups,
  };
});

const serverViewModel = computed(() => ({
  core: serverTopology.nodes.core || { name: "核心交换机", ip: "-", status: "unknown" },
  switches: (serverTopology.nodes.server_switches || []).map((item) => ({
    ...item,
    servers: item.servers || [],
  })),
}));

const destroyNetworkTopology = () => {
  if (networkInstance) {
    networkInstance.destroy();
    networkInstance = null;
  }
};

const destroyServerTopology = () => {
  if (serverInstance) {
    serverInstance.destroy();
    serverInstance = null;
  }
};

const buildNetworkTopology = () => {
  destroyNetworkTopology();
  const allClickableNodes = [
    networkViewModel.value.router,
    networkViewModel.value.core,
    ...networkViewModel.value.groups.flatMap((group) => group.devices),
  ].filter(Boolean);

  const stillSelected =
    selectedNetworkDevice.id &&
    allClickableNodes.find((item) => String(item.id) === String(selectedNetworkDevice.id));

  const fallbackSelected =
    stillSelected ||
    networkViewModel.value.router ||
    networkViewModel.value.core ||
    allClickableNodes[0] ||
    null;

  if (!fallbackSelected) return;

  Object.keys(selectedNetworkDevice).forEach((key) => delete selectedNetworkDevice[key]);
  Object.assign(selectedNetworkDevice, fallbackSelected);
};

const buildServerTopology = () => {
  destroyServerTopology();
  const currentSwitch = serverViewModel.value.switches.find(
    (item) => selectedServerNode.node_kind === "server_switch" && item.name === selectedServerNode.name,
  );
  const currentServer =
    selectedServerNode.id &&
    serverTopology.servers.find((item) => String(item.id) === String(selectedServerNode.id));
  const preferredServer = currentServer || getPreferredServer(serverTopology.servers);

  if (preferredServer) {
    Object.keys(selectedServerNode).forEach((key) => delete selectedServerNode[key]);
    Object.assign(selectedServerNode, { node_kind: "server", ...preferredServer });
    return;
  }

  if (currentSwitch) {
    Object.keys(selectedServerNode).forEach((key) => delete selectedServerNode[key]);
    Object.assign(selectedServerNode, { node_kind: "server_switch", ...currentSwitch });
    return;
  }

  if (serverViewModel.value.core?.name) {
    Object.keys(selectedServerNode).forEach((key) => delete selectedServerNode[key]);
    Object.assign(selectedServerNode, {
      node_kind: "core",
      ...serverViewModel.value.core,
      switch_count: serverViewModel.value.switches.length,
      server_count: serverTopology.servers.length,
    });
  }
};

const loadOverview = async () => {
  let data = null;
  try {
    const resp = await http.get("/dashboard/overview", { timeout: 12000 });
    data = resp?.data || null;
  } catch (error) {
    // Fallback: still render topology using /devices (ping-based) so the page isn't empty.
    data = null;
  }

  if (data) {
    setStats(networkStats, data.network_stats || data.stats || {});
    setStats(serverStats, data.server_stats || {});
    networkDevices.value = data.topology?.devices || [];
  }

  const normalizeTaskRows = (rows = []) =>
    (rows || []).slice(0, 10).map((item) => ({
      ...item,
      status_label:
        ({
          success: "成功",
          failed: "失败",
          running: "执行中",
          partial_failed: "部分失败",
          completed: "已完成",
        }[item.status] || item.status),
      start_time_label: parseTime(item.start_time),
    }));

  recentTasksNetwork.value = normalizeTaskRows((data && (data.recent_tasks_network || data.recent_tasks)) || []);
  recentTasksServer.value = normalizeTaskRows((data && data.recent_tasks_server) || []);

  // If dashboard overview returns empty, use /devices as a best-effort fallback so topology shows up.
  if (!networkDevices.value.length) {
    try {
      const { data: deviceRows } = await http.get("/devices", { params: { with_status: true }, timeout: 12000 });
      const rows = Array.isArray(deviceRows) ? deviceRows : [];
      networkDevices.value = normalizeNetworkDevicesFallback(rows);
      const total = networkDevices.value.length;
      const offline = networkDevices.value.filter((d) => d.ping_status === "offline").length;
      const online = total - offline;
      setStats(networkStats, {
        total_devices: total,
        online_devices: online,
        offline_devices: offline,
        alarm_devices: 0,
        today_tasks: networkStats.todayTasks,
      });
    } catch (error) {
      // ignore
    }
  }

  if (!selectedNetworkDevice.id && networkDevices.value.length) {
    Object.assign(selectedNetworkDevice, networkDevices.value[0]);
  }
};

const loadServerTopology = async (options = {}) => {
  const { with_status = false, auto_locate = false, skeleton = false, timeout = 12000, silent = false } = options || {};
  const { data } = await http.get("/servers/topology", { params: { with_status, auto_locate, skeleton }, timeout });
  serverTopology.generated_at = data.generated_at || "";
  serverTopology.stats = data.stats || serverTopology.stats;
  serverTopology.nodes = data.nodes || serverTopology.nodes;
  // Skeleton response intentionally omits server list; avoid clearing existing data.
  if (!data.skeleton) {
    serverTopology.servers = data.servers || [];
  }

  // Keep server stat cards meaningful even if /dashboard/overview is slow or unavailable.
  try {
    const servers = Array.isArray(serverTopology.servers) ? serverTopology.servers : [];
    const total = servers.length;
    const offline = servers.filter((s) => String(s.status || "").toLowerCase() === "offline").length;
    const online = Math.max(0, total - offline);

    const warning = servers.filter((s) => {
      const level = String(s.inspection_level || "").toLowerCase();
      const st = String(s.status || "").toLowerCase();
      const topo = String(s.topology_status || "").toLowerCase();
      return level === "warning" || st === "online_abnormal" || topo === "alarm";
    }).length;
    const critical = servers.filter((s) => {
      const level = String(s.inspection_level || "").toLowerCase();
      return level === "critical" || level === "failed";
    }).length;

    // Preserve todayTasks from overview if it was loaded.
    if (total > 0) {
      serverStats.totalDevices = total;
      serverStats.onlineDevices = online;
      serverStats.offlineDevices = offline;
      serverStats.warningDevices = warning;
      serverStats.criticalDevices = critical;
    }
  } catch (error) {
    // ignore
  }

  const latestSelected =
    selectedServerNode.id &&
    serverTopology.servers.find((item) => String(item.id) === String(selectedServerNode.id));
  const preferred = latestSelected || getPreferredServer(serverTopology.servers);

  if (preferred) {
    Object.keys(selectedServerNode).forEach((key) => delete selectedServerNode[key]);
    Object.assign(selectedServerNode, { node_kind: "server", ...preferred });
    return;
  }

  if (!selectedServerNode.node_kind && data.nodes?.core) {
    Object.assign(selectedServerNode, { node_kind: "core", ...data.nodes.core });
  }

  if (!silent) {
    // no-op placeholder for future toast
  }
};

// Background refresh: keep topology data fresh without running heavy server probes (WinRM/SSH).
const refreshServerTopologyAsync = () => {
  // Do not stack multiple background refreshes.
  if (serverTopology._refreshing) return;
  serverTopology._refreshing = true;
  setTimeout(async () => {
    try {
      // Keep it lightweight for overview screen: do NOT trigger real-time probes here.
      await loadServerTopology({ with_status: false, auto_locate: false, timeout: 12000, silent: true });
      if (activeView.value === "server") {
        await nextTick();
        buildServerTopology();
      }
    } catch (_err) {
      // ignore; keep fast-first UI
    } finally {
      serverTopology._refreshing = false;
    }
  }, 50);
};

const handleNetworkNodeClick = (node) => {
  if (!node?.id) return;
  Object.keys(selectedNetworkDevice).forEach((key) => delete selectedNetworkDevice[key]);
  Object.assign(selectedNetworkDevice, node);
};

const handleServerNodeClick = (node) => {
  if (!node) return;
  Object.keys(selectedServerNode).forEach((key) => delete selectedServerNode[key]);
  Object.assign(selectedServerNode, node);
};

const loadNetworkFastFirst = async () => {
  // Quick path: render topology from /devices as soon as possible.
  try {
    const { data: deviceRows } = await http.get("/devices", { params: { with_status: true }, timeout: 4000 });
    const rows = Array.isArray(deviceRows) ? deviceRows : [];
    if (rows.length) {
      networkDevices.value = normalizeNetworkDevicesFallback(rows);
      const total = networkDevices.value.length;
      const offline = networkDevices.value.filter((d) => d.ping_status === "offline").length;
      const online = total - offline;
      setStats(networkStats, {
        total_devices: total,
        online_devices: online,
        offline_devices: offline,
        alarm_devices: 0,
        today_tasks: networkStats.todayTasks,
      });
      if (!selectedNetworkDevice.id && networkDevices.value.length) {
        Object.assign(selectedNetworkDevice, networkDevices.value[0]);
      }
      await nextTick();
      buildNetworkTopology();
    }
  } catch (error) {
    // ignore quick path failure
  }

  // Full overview (tasks/stats/details) arrives later; when it does, rebuild topology once.
  try {
    await loadOverview();
    await nextTick();
    buildNetworkTopology();
  } catch (error) {
    // ignore
  }

  // Background warm-up for faster view switching.
  loadServerTopology({ with_status: false, auto_locate: false, timeout: 12000, silent: true }).catch(() => {});
};

const load = async () => {
  if (loadRunning) return;
  loadRunning = true;
  try {
    if (activeView.value === "network") {
      await loadNetworkFastFirst();
      return;
    }

    // Server view: fast-first skeleton for 1st paint (core + server switches),
    // then load full server list in background. Network overview remains untouched.
    loadOverview().catch(() => {});

    try {
      await loadServerTopology({ with_status: false, auto_locate: false, skeleton: true, timeout: 3000, silent: true });
      await nextTick();
      buildServerTopology();
    } catch (_err) {
      // ignore skeleton failure
    }

    // Full data (servers list) comes next; this may be slower under DB lock contention.
    try {
      await loadServerTopology({ with_status: false, auto_locate: false, skeleton: false, timeout: 12000, silent: true });
      await nextTick();
      buildServerTopology();
    } catch (_err) {
      // ignore; keep skeleton UI
    }

    refreshServerTopologyAsync();
  } finally {
    loadRunning = false;
  }
};

const postponeAutoSwitch = () => {
  nextSwitchAt = Date.now() + SCREEN_SWITCH_INTERVAL_MS;
};

const handleManualViewSwitch = async (view) => {
  postponeAutoSwitch();
  activeView.value = view;
  await nextTick();
  if (view === "network") {
    buildNetworkTopology();
    return;
  }
  buildServerTopology();
};

const handleMouseActivity = () => {
  postponeAutoSwitch();
};

const startRotation = () => {
  postponeAutoSwitch();
  rotateTimer = setInterval(async () => {
    if (Date.now() < nextSwitchAt) return;
    activeView.value = activeView.value === "network" ? "server" : "network";
    await nextTick();
    if (activeView.value === "network") {
      buildNetworkTopology();
    } else {
      buildServerTopology();
    }
    postponeAutoSwitch();
  }, 1000);
};

const handleStatCardClick = (key) => {
  const statusMap = {
    online: "online",
    offline: "offline",
    alarm: "alarm",
  };
  const status = statusMap[key];
  if (!status) return;
  router.push({
    path: "/devices",
    query: {
      module: activeView.value,
      status,
    },
  });
};

onMounted(async () => {
  await load();
  refreshTimer = setInterval(load, 30000);
  startRotation();
  window.addEventListener("mousemove", handleMouseActivity, { passive: true });
  window.addEventListener("mousedown", handleMouseActivity, { passive: true });
  window.addEventListener("wheel", handleMouseActivity, { passive: true });
});

onUnmounted(() => {
  destroyNetworkTopology();
  destroyServerTopology();
  if (refreshTimer) clearInterval(refreshTimer);
  if (rotateTimer) clearInterval(rotateTimer);
  window.removeEventListener("mousemove", handleMouseActivity);
  window.removeEventListener("mousedown", handleMouseActivity);
  window.removeEventListener("wheel", handleMouseActivity);
});
</script>

<style scoped>
.dashboard-page {
  background:
    radial-gradient(circle at 16% 18%, rgba(56, 189, 248, 0.16), transparent 38%),
    radial-gradient(circle at 88% 12%, rgba(34, 211, 238, 0.18), transparent 32%),
    linear-gradient(145deg, #020817 0%, #04162f 50%, #071d3b 100%);
  border-radius: 14px;
  padding: 14px;
  color: #e2e8f0;
}

.glass {
  background: rgba(7, 24, 48, 0.58) !important;
  border: 1px solid rgba(56, 189, 248, 0.32);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.1) inset, 0 0 20px rgba(56, 189, 248, 0.15);
  backdrop-filter: blur(8px);
}

:deep(.glass .el-card__body),
:deep(.glass .el-card__header) {
  color: #e2e8f0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.stat-card {
  min-height: 94px;
}

.stat-card.clickable {
  cursor: pointer;
}

.stat-title {
  color: #93c5fd;
  font-size: 13px;
  margin-bottom: 10px;
}

.stat-num {
  font-size: 28px;
  line-height: 1;
  font-weight: 700;
  color: #f8fafc;
}

.status-normal {
  color: #22c55e;
}

.status-alarm {
  color: #fb923c;
}

.status-offline {
  color: #ef4444;
}

.screen-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
  padding: 10px 14px;
  border: 1px solid rgba(56, 189, 248, 0.22);
  border-radius: 12px;
  background: rgba(8, 25, 45, 0.52);
}

.switch-title {
  color: #dbeafe;
  font-size: 15px;
  font-weight: 700;
}

.switch-subtitle {
  color: #93c5fd;
  font-size: 13px;
  margin-top: 4px;
}

.switch-pills {
  display: inline-flex;
  gap: 8px;
}

.switch-pill {
  border: 1px solid rgba(125, 211, 252, 0.28);
  background: rgba(15, 23, 42, 0.58);
  color: #e0f2fe;
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
}

.switch-pill.active {
  border-color: rgba(34, 211, 238, 0.7);
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.2) inset, 0 0 12px rgba(34, 211, 238, 0.14);
}

.content-grid {
  display: grid;
  grid-template-columns: 1.8fr 1fr;
  gap: 12px;
}

.topology-card {
  min-height: 900px;
}

.topology-canvas {
  height: 830px;
  border-radius: 12px;
  background:
    radial-gradient(circle at 20% 10%, rgba(59, 130, 246, 0.18), transparent 32%),
    linear-gradient(160deg, rgba(2, 6, 23, 0.88), rgba(7, 24, 48, 0.92));
}

.network-topology-canvas {
  padding: var(--network-canvas-padding);
  overflow: auto;
}

.topology-canvas--overview {
  overflow: hidden auto;
}

.topology-canvas--detail {
  overflow: auto;
}

.network-topology-tree {
  min-width: var(--network-tree-min-width);
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.24s ease;
}

.network-topology-tree--overview {
  justify-content: flex-start;
}

.network-topology-tree--detail {
  justify-content: center;
}

.tree-level {
  width: 100%;
  display: flex;
  justify-content: center;
}

.tree-level--groups {
  align-items: flex-start;
  justify-content: center;
  gap: 18px;
  padding-top: 8px;
  flex-wrap: wrap;
}

.tree-connector {
  width: 2px;
  height: var(--network-connector-height);
  margin: var(--network-connector-margin);
  background: linear-gradient(180deg, rgba(56, 189, 248, 0.78), rgba(103, 232, 249, 0.18));
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.22);
}

.topology-group {
  width: var(--network-group-width);
  min-height: var(--network-group-min-height);
  padding: var(--network-group-padding);
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(7, 24, 48, 0.8), rgba(5, 18, 35, 0.7));
  box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.08);
  position: relative;
}

.topology-group--overview {
  box-shadow:
    inset 0 0 0 1px rgba(34, 211, 238, 0.06),
    0 8px 20px rgba(8, 25, 45, 0.16);
}

.topology-group--detail {
  box-shadow:
    inset 0 0 0 1px rgba(34, 211, 238, 0.08),
    0 14px 28px rgba(8, 25, 45, 0.2);
}

.topology-group--server {
  border-color: rgba(56, 189, 248, 0.34);
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.1), transparent 34%),
    linear-gradient(180deg, rgba(7, 24, 48, 0.82), rgba(5, 18, 35, 0.72));
}

.topology-group::before {
  content: "";
  position: absolute;
  top: -24px;
  left: 50%;
  width: 2px;
  height: 24px;
  transform: translateX(-50%);
  background: linear-gradient(180deg, rgba(56, 189, 248, 0.78), rgba(103, 232, 249, 0.18));
}

.topology-group__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: var(--network-group-header-margin);
}

.topology-group__title {
  color: #e0f2fe;
  font-size: var(--network-group-title-font-size);
  font-weight: 700;
}

.topology-group__count {
  color: #7dd3fc;
  font-size: var(--network-group-count-font-size);
}

.topology-group__body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--network-group-body-gap);
}

.topology-node {
  border: 1px solid rgba(96, 165, 250, 0.2);
  background: rgba(7, 24, 48, 0.6);
  border-radius: var(--network-node-radius);
  color: #f8fafc;
  padding: var(--network-node-padding);
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--network-node-gap);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.topology-node--overview {
  box-shadow: 0 8px 20px rgba(8, 25, 45, 0.14);
}

.topology-node--detail {
  box-shadow: 0 14px 26px rgba(8, 25, 45, 0.18);
}

.topology-node:hover {
  transform: translateY(-2px);
}

.topology-node.is-static {
  cursor: default;
}

.topology-node.is-static:hover {
  transform: none;
}

.topology-node--router {
  width: var(--network-router-width);
  min-height: var(--network-router-min-height);
}

.topology-node--core-switch {
  width: var(--network-core-width);
  min-height: var(--network-core-min-height);
}

.topology-node--access-switch {
  width: 100%;
  min-height: var(--network-access-min-height);
}

.topology-node--internet {
  width: var(--network-internet-width);
  min-height: var(--network-internet-min-height);
}

.topology-node--selected {
  border-color: rgba(34, 211, 238, 0.88);
  box-shadow:
    0 0 0 1px rgba(34, 211, 238, 0.2) inset,
    0 0 18px rgba(34, 211, 238, 0.22);
}

.topology-node--online {
  border-color: rgba(34, 197, 94, 0.5);
}

.topology-node--abnormal {
  border-color: rgba(251, 146, 60, 0.55);
}

.topology-node--offline {
  border-color: rgba(239, 68, 68, 0.55);
}

.topology-node--unknown {
  border-color: rgba(148, 163, 184, 0.42);
}

.topology-node__icon--image img {
  display: block;
  width: var(--network-icon-width);
  height: var(--network-icon-height);
  object-fit: contain;
}

.topology-node--core-switch .topology-node__icon--image img {
  width: var(--network-core-icon-width);
  height: var(--network-core-icon-height);
}

.topology-node__label {
  color: #f8fafc;
  font-size: var(--network-node-label-font-size);
  font-weight: 700;
  text-align: center;
  line-height: 1.25;
}

.topology-node__meta {
  color: #93c5fd;
  font-size: var(--network-node-meta-font-size);
  text-align: center;
  line-height: 1.2;
  word-break: break-all;
}

.server-topology-canvas {
  height: auto;
  min-height: 460px;
  padding-bottom: 8px;
}

.server-topology-card {
  min-height: auto;
}

.server-legend {
  margin-top: 4px;
}

.legend {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  color: #cbd5e1;
  font-size: 13px;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
}

.dot.normal {
  background: #22c55e;
}

.dot.alarm {
  background: #fb923c;
}

.dot.offline {
  background: #ef4444;
}

.dot.unknown {
  background: #94a3b8;
}

.legend-device {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-device img {
  width: 24px;
  height: 28px;
  object-fit: contain;
}

.right-stack {
  display: grid;
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.side-card {
  min-height: 260px;
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: #f8fafc;
}

.detail-box {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.detail-item {
  padding: 10px 12px;
  border: 1px solid rgba(96, 165, 250, 0.22);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.38);
}

.detail-item--alert {
  border-color: rgba(251, 146, 60, 0.7);
  background: linear-gradient(180deg, rgba(120, 53, 15, 0.34), rgba(15, 23, 42, 0.45));
  box-shadow: inset 0 0 0 1px rgba(251, 146, 60, 0.16), 0 0 16px rgba(251, 146, 60, 0.08);
}

.detail-span-2 {
  grid-column: span 2;
}

.detail-item span {
  display: block;
  color: #93c5fd;
  font-size: 12px;
  margin-bottom: 6px;
}

.detail-item--alert span {
  color: #fdba74;
}

.detail-item b {
  color: #f8fafc;
  font-size: 13px;
  word-break: break-all;
}

.detail-item--alert b {
  color: #fff7ed;
}

:deep(.el-table) {
  --el-table-border-color: rgba(96, 165, 250, 0.16);
  --el-table-header-bg-color: rgba(8, 25, 45, 0.68);
  --el-table-tr-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(56, 189, 248, 0.08);
  --el-table-bg-color: transparent;
  --el-table-text-color: #f8fafc;
  --el-table-header-text-color: #bfdbfe;
}

:deep(.el-table th),
:deep(.el-table td),
:deep(.el-table .cell) {
  color: #f8fafc !important;
}

:deep(.el-empty__description p) {
  color: #94a3b8 !important;
}

:deep(.el-table__empty-block),
:deep(.el-table__empty-text) {
  color: #94a3b8 !important;
  font-size: 13px;
}

@media (max-width: 1200px) {
  .stats-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .screen-switch {
    flex-direction: column;
    align-items: flex-start;
  }

  .network-topology-tree {
    min-width: 100%;
  }

  .topology-group {
    width: 100%;
  }

  .topology-group__body {
    grid-template-columns: 1fr;
  }

  .right-stack,
  .detail-box {
    grid-template-columns: 1fr;
  }

  .detail-span-2 {
    grid-column: span 1;
  }
}
</style>
