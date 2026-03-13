# Automation Platform 自动化运维 Web 平台

基于 FastAPI + Vue3 的前后端分离自动化运维平台，用于统一管理网络设备并执行批量任务（巡检、NTP、SNMP）。

## 1. 功能说明

- 设备管理：新增、编辑、删除、搜索设备
- 批量任务：批量执行 `audit`、`ntp`、`snmp`
- 任务记录：查看任务历史、成功失败统计
- 任务详情：按设备查看执行结果
- 日志：`system.log`、`task.log`、`error.log`

## 2. 项目结构

```text
automation-platform
├── backend
│   ├── app
│   │   ├── main.py
│   │   ├── api
│   │   ├── models
│   │   ├── database
│   │   ├── services
│   │   ├── automation
│   │   └── utils
│   ├── logs
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── views
│   │   ├── router
│   │   ├── api
│   │   └── components
└── README.md
```

## 3. 环境要求

- Python 3.10+
- Node.js 18+
- npm 9+

## 4. 运行方法

### 4.1 启动后端

```powershell
cd D:\automation-platform\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端地址：`http://127.0.0.1:8000`

### 4.2 启动前端

```powershell
cd D:\automation-platform\frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 5. 使用方法

### 5.1 登录

1. 打开 `http://127.0.0.1:5173`
2. 使用默认账号登录：
   - 用户名：`admin`
   - 密码：`admin123`

### 5.2 设备管理

1. 进入 `Device List`
2. 点击“新增设备”录入设备信息
3. 可按名称/IP/分组/位置搜索
4. 支持编辑和删除

### 5.3 执行任务

1. 进入 `Task Execute`
2. 多选设备
3. 选择任务按钮：
   - 执行巡检
   - 配置 NTP（可填写 `timezone`、`offset`、`ntp_server`）
   - 配置 SNMP（可填写 `community`）
4. 执行后会返回任务 ID

### 5.4 查看历史

1. 进入 `Task History`
2. 查看任务类型、开始/结束时间、成功/失败数量
3. 点击“详情”查看每台设备执行结果

## 6. API 说明

接口统一前缀：`/api`

- `POST /api/login`
- `GET /api/devices`
- `POST /api/devices`
- `PUT /api/devices/{id}`
- `DELETE /api/devices/{id}`
- `POST /api/tasks/audit`
- `POST /api/tasks/ntp`
- `POST /api/tasks/snmp`
- `GET /api/tasks`
- `GET /api/tasks/{id}`

## 7. API 调用示例

### 7.1 登录

```bash
curl -X POST http://127.0.0.1:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 7.2 新增设备

```bash
curl -X POST http://127.0.0.1:8000/api/devices \
  -H "Content-Type: application/json" \
  -d '{
    "name":"core-sw1",
    "ip":"10.1.1.1",
    "username":"admin",
    "password":"admin",
    "port":22,
    "device_type":"huawei",
    "group_name":"core",
    "location":"datacenter",
    "enable":1
  }'
```

### 7.3 执行 NTP 任务

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/ntp \
  -H "Content-Type: application/json" \
  -d '{
    "devices":[1,2],
    "timezone":"BJ",
    "offset":"08:00:00",
    "ntp_server":"10.18.101.2"
  }'
```

## 8. 数据库与日志

- SQLite 文件：`backend/automation.db`
- 数据表：`devices`、`tasks`、`task_results`
- 日志目录：`backend/logs/`
  - `system.log`
  - `task.log`
  - `error.log`

## 9. 说明

- 当前自动化模块为模拟执行，未建立真实 SSH 会话。
- 后续可在 `backend/app/automation/*.py` 中替换为真实 Netmiko 逻辑。
