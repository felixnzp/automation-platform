import { createRouter, createWebHistory } from "vue-router";
import Login from "../views/Login.vue";
import Dashboard from "../views/Dashboard.vue";
import DeviceList from "../views/DeviceList.vue";
import TaskExecute from "../views/TaskExecute.vue";
import TaskHistory from "../views/TaskHistory.vue";

const routes = [
  { path: "/", redirect: "/login" },
  { path: "/login", component: Login },
  { path: "/dashboard", component: Dashboard },
  { path: "/devices", component: DeviceList },
  { path: "/tasks/execute", component: TaskExecute },
  { path: "/tasks/history", component: TaskHistory },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  if (to.path === "/login") {
    next();
    return;
  }

  const token = localStorage.getItem("token");
  if (!token) {
    next("/login");
    return;
  }
  next();
});

export default router;
