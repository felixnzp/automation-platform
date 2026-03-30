<template>
  <div class="login-wrap">
    <div class="tech-glow"></div>
    <el-card class="login-card">
      <div class="login-brand">
        <img class="logo" src="/images/logo-black.png" alt="安室智能 Logo" />
        <h2>安室智能 自动化运维平台</h2>
        <p>智能感知 · 自动执行 · 全局可视</p>
      </div>
      <el-form :model="form" label-width="72px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" show-password type="password" placeholder="请输入密码" />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="login-btn" @click="onLogin">登录平台</el-button>
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
    localStorage.setItem("username", data.username || form.username);
    ElMessage.success("登录成功");
    router.push("/dashboard");
  } catch (err) {
    if (err?.code === "ERR_NETWORK") {
      ElMessage.error("后端服务未启动，请先启动 backend（8000端口）");
    } else {
      ElMessage.error(err?.response?.data?.detail || "登录失败");
    }
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
  position: relative;
  overflow: hidden;
}

.tech-glow {
  position: absolute;
  width: 760px;
  height: 760px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(72, 224, 255, 0.25), rgba(79, 125, 255, 0.12), transparent 68%);
  filter: blur(10px);
}

.login-card {
  width: 470px;
  position: relative;
  z-index: 1;
}

.login-brand {
  margin-bottom: 14px;
}

.logo {
  width: 170px;
  max-width: 100%;
  display: block;
  margin-bottom: 10px;
}

h2 {
  margin: 0;
  font-size: 23px;
}

p {
  margin: 6px 0 0;
  color: var(--app-subtext);
}

.login-btn {
  width: 100%;
  margin-top: 4px;
}
</style>
