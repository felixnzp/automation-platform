# 安室智能 自动化运维平台（automation-platform）

**当前版本：`v1.1.1`**

本项目为 Windows 环境下的自动化运维 Web 平台，提供网络设备与服务器的资产管理、巡检任务（即时/定时）、配置中心能力，以及主页（原“总览大屏”）等可视化页面。

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite
- 前端：Vue 3 + Element Plus + Vite + Axios + Vue Router

## 目录结构

```text
D:\automation-platform
  backend\           # FastAPI 后端（含 SQLite 数据库 automation.db）
  frontend\          # Vue3 前端
  devices\           # 设备拓扑/映射等数据文件（例如 NetDevices.xlsx）
  start-lan-dev.ps1  # 一键启动（局域网可访问）
```

## 环境要求

- Windows PowerShell 5.1+（或 PowerShell 7+）
- Python 3.12+
- Node.js 18+

## 一键启动（推荐）

脚本会分别打开两个 PowerShell 窗口启动后端和前端，并将服务绑定到 `0.0.0.0`，便于局域网访问。

```powershell
cd D:\automation-platform
.\start-lan-dev.ps1
```

访问地址：

- 前端：`http://<你的电脑IP>:80`
- 后端：`http://<你的电脑IP>:8000`
- API 文档：`http://<你的电脑IP>:8000/docs`

说明：

- 若端口 `80` 被占用，可在 `start-lan-dev.ps1` 中调整前端端口（或改用 Vite 默认端口）。
- 若其他电脑访问不了，请检查 Windows 防火墙是否放行 `80/8000` 端口。

## 手动启动（首次安装/排障）

### 1）启动后端

```powershell
cd D:\automation-platform\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2）启动前端

```powershell
cd D:\automation-platform\frontend
npm install
npm run dev -- --host 0.0.0.0 --port 80
```

## 默认登录

- 用户名：`admin`
- 密码：`admin123`

## 核心功能概览（当前版本）

- 主页：网络/服务器视图切换、拓扑展示、设备详情联动、最近任务
- 设备中心：
  - 网络设备管理：增删改查、状态检测
  - 服务器管理：增删改查、连接测试（WinRM/SSH）
- 任务中心：
  - 即时任务：网络巡检、服务器巡检等
  - 计划任务：支持按周期/cron 执行
- 配置中心：
  - 端口查询（按 IP / 按 MAC）
  - VLAN 修改（含 trunk 放通检查、端口 flap、配置保存）
- 日志中心：任务/配置操作日志查询
- 告警中心：告警聚合、筛选（若已启用）

## 主要接口（后端路由前缀）

- 认证：`/api/*`（登录等）
- 设备：`/api/devices/*`
- 服务器：`/api/servers/*`
- 任务：`/api/tasks/*`
- 配置中心：`/api/config/*`
- 端口查询（重构接口）：`/api/port-query/*`
- 主页数据：`/api/dashboard/*`
- 告警：`/api/alerts/*`

以 `http://<IP>:8000/docs` 为准查看当前实际接口与入参。

## 数据库

- SQLite 文件：`backend/automation.db`

## 开发定位

- 前端路由入口：`frontend/src/router/index.js`
- 主布局（左侧菜单/顶部栏）：`frontend/src/components/LayoutShell.vue`
- 主页页面：`frontend/src/views/Dashboard.vue`
- 配置中心页面（含端口查询）：`frontend/src/views/ConfigCenter.vue`
