<template>
  <LayoutShell>
    <el-card>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索名称/IP/分组/位置" style="width: 280px" />
        <el-button type="primary" @click="load">搜索</el-button>
        <el-button type="success" @click="openAdd">新增设备</el-button>
      </div>

      <el-table :data="devices" border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="ip" label="IP" />
        <el-table-column prop="device_type" label="类型" />
        <el-table-column prop="group_name" label="分组" />
        <el-table-column prop="location" label="位置" />
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button size="small" @click="openEdit(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="onDelete(scope.row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑设备' : '新增设备'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="IP"><el-input v-model="form.ip" /></el-form-item>
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="form.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item label="设备类型"><el-input v-model="form.device_type" /></el-form-item>
        <el-form-item label="分组"><el-input v-model="form.group_name" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="form.location" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </LayoutShell>
</template>

<script setup>
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import LayoutShell from "../components/LayoutShell.vue";
import http from "../api/http";

const devices = ref([]);
const keyword = ref("");
const dialogVisible = ref(false);
const editingId = ref(null);
const enabled = ref(true);

const emptyForm = () => ({
  name: "",
  ip: "",
  username: "admin",
  password: "admin",
  port: 22,
  device_type: "huawei",
  group_name: "default",
  location: "datacenter",
  enable: 1,
});

const form = reactive(emptyForm());

const load = async () => {
  const { data } = await http.get("/devices", { params: { keyword: keyword.value || undefined } });
  devices.value = data;
};

const openAdd = () => {
  editingId.value = null;
  Object.assign(form, emptyForm());
  enabled.value = true;
  dialogVisible.value = true;
};

const openEdit = (row) => {
  editingId.value = row.id;
  Object.assign(form, row);
  enabled.value = row.enable === 1;
  dialogVisible.value = true;
};

const save = async () => {
  form.enable = enabled.value ? 1 : 0;
  if (editingId.value) {
    await http.put(`/devices/${editingId.value}`, form);
    ElMessage.success("更新成功");
  } else {
    await http.post("/devices", form);
    ElMessage.success("创建成功");
  }
  dialogVisible.value = false;
  load();
};

const onDelete = async (id) => {
  await ElMessageBox.confirm("确认删除该设备?", "提示", { type: "warning" });
  await http.delete(`/devices/${id}`);
  ElMessage.success("删除成功");
  load();
};

load();
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
