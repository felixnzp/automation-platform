# Automation Platform

Automation Platform is a full-stack AutoOps web console for network devices.

## Features

- Device management (CRUD + search)
- Batch audit task execution
- Batch NTP configuration task execution
- Batch SNMP configuration task execution
- Task history and result details
- Simulated automation modules with unified `run(devices, params)` interface

## Project Structure

```text
automation-platform
├── backend
│   ├── app
│   │   ├── main.py
│   │   ├── api
│   │   │   ├── device_api.py
│   │   │   ├── task_api.py
│   │   │   └── auth_api.py
│   │   ├── models
│   │   │   ├── device.py
│   │   │   └── task.py
│   │   ├── database
│   │   │   └── database.py
│   │   ├── services
│   │   │   ├── device_service.py
│   │   │   └── task_service.py
│   │   ├── automation
│   │   │   ├── audit_module.py
│   │   │   ├── ntp_module.py
│   │   │   └── snmp_module.py
│   │   └── utils
│   │       └── logger.py
│   ├── logs
│   │   ├── system.log
│   │   ├── task.log
│   │   └── error.log
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── views
│   │   │   ├── Login.vue
│   │   │   ├── Dashboard.vue
│   │   │   ├── DeviceList.vue
│   │   │   ├── TaskExecute.vue
│   │   │   └── TaskHistory.vue
│   │   ├── router
│   │   ├── api
│   │   └── components
└── README.md
```

## Backend Setup

### Requirements

- Python 3.10+

### Start backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

### Default login

- username: `admin`
- password: `admin123`

## Frontend Setup

### Requirements

- Node.js 18+

### Start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

## API Overview

Base prefix: `/api`

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

## Database

SQLite database file is created automatically at:

- `backend/automation.db`

Tables:

- `devices`
- `tasks`
- `task_results`

## Notes

- Automation modules currently simulate results and do not require real SSH sessions.
- The `netmiko` dependency is included for future integration with real devices.
- Logging files are located in `backend/logs/`.
