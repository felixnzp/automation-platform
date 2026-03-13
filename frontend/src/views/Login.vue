<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>Automation Platform</h2>
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" show-password type="password" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="onLogin">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import http from "../api/http";

const router = useRouter();
const loading = ref(false);
const form = reactive({ username: "admin", password: "admin123" });

const onLogin = async () => {
  loading.value = true;
  try {
    const { data } = await http.post("/login", form);
    localStorage.setItem("token", data.token);
    ElMessage.success("登录成功");
    router.push("/dashboard");
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "登录失败");
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #d7e7f8, #f8fbff);
}

.login-card {
  width: 420px;
}
</style>
