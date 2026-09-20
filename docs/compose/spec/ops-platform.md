---
feature: ops-platform
status: in-progress
updated: 2026-09-20
branch: ops/platform
commits: 8edf67d..<head> # filled at delivery
---

# 轻量级 Agent 管理平台（PostgreSQL 版）

## Report

## [S1] Problem

小主机/国内机/海外机分散，缺少统一的节点在线状态、资源指标、容器与项目运维入口。现有方式无法安全地下发有限运维指令，也不能在 Windows 小主机（无 systemd）上做降级运维。需要一套 **Agent 主动上报、平台绝不反连** 的轻量平台：心跳与资源快照上报、指令队列拉取、日志与指标可视化，并按冻结计划部署到国内机（复用现有 nginx）。

本地冻结任务书：`PLAN.md` / `运维平台-执行计划.md`（含网络与密码，**不入仓**）。本文是可入仓的实现契约与任务清单。

## [S2] Design

### [S2.1] Tech stack（冻结，勿换）

- 后端：Python 3.11 + FastAPI + SQLAlchemy 2.x + Pydantic v2 + `psycopg`（v3），连接串 `postgresql+psycopg://`
- DB：PostgreSQL 16；连接池 `pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600`
- 时间：一律 `DateTime(timezone=True)`；JSON：SQLAlchemy `JSON`（PG→JSONB）
- 实时：WebSocket 日志流；前端：Vue 3 + Vite + TS + Element Plus（深色模式）+ ECharts 5
- 部署：Compose 三服务 `db` / `platform` / `nginx`（生产 nginx 由国内机现有实例接管）
- Agent：独立模块 `platform_reporter.py`，`threading.Thread(daemon=True)`，异常不杀主程序
- 禁止：K8s / RabbitMQ / Redis / 微服务 / Flask / SQLite / `shell=True` / Vue2 Options API

### [S2.2] Data model（6 表）

1. `nodes`：id；`node_id` Varchar(100) unique；hostname；ip；os；agent_version；`token` unique；status；`last_seen_at` timestamptz；`created_at` timestamptz
2. `metrics`：id；`node_id`；cpu/mem/disk percent；load_avg Float nullable；`timestamp` timestamptz；索引 `(node_id, timestamp)`
3. `commands`：id；`node_id`；action Varchar(50)；params JSONB `{}`；status pending/done/failed；result Text；`created_at`；`finished_at` nullable
4. `logs`：id；`node_id`；level info/warn/error；content Text；`timestamp`
5. `resource_snapshots`：id；`node_id`；snapshot JSONB；`timestamp`；snapshot 含 containers/images/services/projects 四段
6. `users`：id；username unique；password_hash（bcrypt）；`created_at`；`must_change_password` bool

初始化：`Base.metadata.create_all()` + 首次启动建默认 admin（`ADMIN_PASSWORD`），首次登录强制改密。

环境变量：`DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME` + `SECRET_KEY` + `ADMIN_PASSWORD`。Compose `db` 用命名卷 `pgdata`；生产 PG 不暴露宿主机端口；`.env.example` 齐全；真实密码禁入仓。

在线判定：`now - last_seen_at < 30s`；前端连续 2 次超时才标离线。

### [S2.3] API contracts（按计划 §4 实现，勿增）

Agent（Bearer = 节点 token）：

- `POST /api/v1/nodes/register`
- `POST /api/v1/nodes/{node_id}/heartbeat`（body 含 metrics；响应 `pending_commands`）
- `POST /api/v1/nodes/{node_id}/resource-snapshot`
- 指令结果经 result 通道在后续心跳回传（`POST .../commands/{command_id}/result` 或等价 result 接口，与 heartbeat 响应队列配合）

管理端（JWT）：

- `GET /api/v1/nodes`（含实时 online/offline）
- `GET /api/v1/nodes/{node_id}`
- `GET /api/v1/nodes/{node_id}/resources`（最新快照）
- `GET /api/v1/nodes/{node_id}/metrics?range=1h|6h|24h`
- `GET /api/v1/nodes/{node_id}/logs?limit=200`
- `WS /api/v1/nodes/{node_id}/logs`（平台从 DB 推送，2s 节流）
- `POST /api/v1/nodes/{node_id}/commands` `{"action","params"}`
- `GET /api/v1/nodes/{node_id}/commands`
- `POST /api/v1/auth/login`（JWT）

### [S2.4] Command whitelist（服务端 + Agent 双侧）

参数必须存在于最近 resource snapshot，否则拒绝：

| action | params | 备注 |
|---|---|---|
| `restart_agent` | 无 | |
| `agent_status` | 无 | |
| `container_restart` / `container_stop` / `container_start` | `{name}` | name ∈ 最近 snapshot containers |
| `container_logs` | `{name, lines≤1000}` | |
| `service_restart` / `service_stop` / `service_status` | `{name}` | Windows 节点直接拒 |
| `image_prune` | 无 | 清 `<none>` |
| `project_deploy` | `{path}` | 前缀 `/opt/projects/` 或 `/data/apps/` + 目录下 `deploy.sh`；**首版按钮默认关闭**（配置项打开） |

执行：`subprocess.run` 参数列表，禁止 `shell=True`。平台侧校验白名单 + snapshot 存在性 + Windows 能力降级；非法 action/name 必拒。

### [S2.5] Data retention

- `metrics` 保留 7 天，`logs` 保留 3 天；平台内定时清理任务。
- 在线阈值 30s；Agent 心跳 HTTP `timeout=25`；心跳周期 10s；资源快照周期 60s。

### [S2.6] Agent reporter

- `collect_metrics()`：psutil CPU/内存/磁盘/负载；Windows 无 load_avg → `None`
- `collect_resources()`：`docker ps -a --format json`、`docker images --format json`、`systemctl list-units --type=service`、扫描 `/opt/projects` 与 `/data/apps`；无 Docker/systemd → 空数组且不报错
- `get_logs(limit=100)`；`execute_command(action, params)` 白名单外直接拒
- `start_reporting()`：主程序调用一次；daemon 线程；失败静默重试不杀主程序
- 交付 `agent_integration.py`（中文注释示例）

### [S2.7] Frontend pages

1. **Dashboard**：4 统计卡（总数/在线/离线/异常）+ ECharts 集群 CPU/内存趋势（按节点筛）+ 节点表（状态灯/主机名/IP/版本/CPU/内存/最后心跳/操作按钮）；5s 轮询 + 开关；离线防抖
2. **节点详情** `/nodes/:node_id`：Tab1 概览（信息 + 圆形仪表盘 + 日志预览）；Tab2 资源运维（容器|镜像|服务|项目，表格 + 二次确认，危险红色；Windows 服务 Tab 置灰「该节点不支持」）；Tab3 实时日志（黑底等宽、自动滚动、级别过滤、暂停）；Tab4 指令历史
3. **全局**：可折叠侧边栏（总览/节点管理/日志检索/系统设置）+ 顶栏（标题/hostname·ip 搜索/深浅切换/头像）；Element Plus 暗黑；卡片圆角微阴影；响应式
4. **登录**：居中卡片，左品牌右表单；检测到默认密码即提示修改

axios：JWT 拦截 + 统一错误；`project_deploy` 按钮默认隐藏/禁用。

### [S2.8] Deploy deliverables

- `docker-compose.yml`：`db`/`platform`/`nginx`，卷 `pgdata`+`appdata`，`depends_on` + healthcheck；PG 无宿主机端口；platform 对外建议 8081
- `platform/Dockerfile`：多阶段，`python:3.11-slim` + `gcc` + `libpq-dev`
- `nginx/nginx.conf`：静态 + `/api/` 反代 + WS Upgrade + Gzip；生产改为现有 nginx server 块，不另起 80/443
- `.env.example` / `requirements.txt` / `package.json` / 中文 `README.md`（ASCII 架构图、快速启动、Agent 集成、资源运维、备份命令、现有 nginx 接入说明）

### [S2.9] Engineering conventions

- Commit：`ops: <phase>-<内容>`；Phase 标签规划 `ops-v0.1`…`ops-v0.4`（P5 归 Hermes）
- 合入主分支需 Hermes 明确同意；本分支不自行 merge
- 密码/真实 `.env`/含 §11 的计划文件不入仓
- 测试：pytest 覆盖主链路与负例；前端 `tsc` 0 error + `vite build`

## [S3] Out of Scope

- K8s / RabbitMQ / Redis / 微服务拆分
- 直接执行任意 shell 字符串的接口；Agent `shell=True`
- PG 公网暴露；真实密码入仓
- 恒生官网机首期接入（只预留 `node_id` 注册）
- `project_deploy` 首版默认开启
- 生产环境上机/域名切换/28 号部署链路操作（P5 Hermes 协调）
- 自行 merge 进 master/main

## Tasks

- [ ] T1: 后端工程骨架与配置 — acceptance: `platform` 包可导入；settings 读取 DB/JWT/ADMIN 环境变量；`requirements.txt` 含 FastAPI/SQLAlchemy2/psycopg/pydantic v2/python-jose/passlib[bcrypt]/psutil（covers: S2.1 S2.2）
- [ ] T2: 六表模型与初始化 — acceptance: 模型字段与 [S2.2] 一致（含 `metrics(node_id,timestamp)` 联合索引）；`create_all` + 默认 admin + `must_change_password`（covers: S2.2）
- [ ] T3: 认证 API — acceptance: `POST /api/v1/auth/login` 返回 JWT；改密生效；错误凭据 401；默认密码登录后强制改密逻辑存在（covers: S2.3）
- [ ] T4: Agent 上报 API — acceptance: register/heartbeat/resource-snapshot/结果回传走通；心跳响应含 `pending_commands`；节点 Bearer 校验；online 判定 <30s（covers: S2.3 S2.5）
- [ ] T5: 管理查询 + 指令 + WS — acceptance: nodes 列表/详情/资源/metrics range/logs/commands 下发与历史；WS 日志从 DB 推送且 2s 节流（covers: S2.3）
- [ ] T6: 白名单、能力降级与数据保留 — acceptance: 非法 action、非法 name、Windows service、无 snapshot、`project_deploy` 默认关闭 均拒绝；metrics 7d / logs 3d 清理可触发（covers: S2.4 S2.5）
- [ ] T7: 后端测试与 ruff — acceptance: pytest 全绿覆盖 `register→heartbeat→snapshot→commands→result` 与负例；ruff 通过（covers: S2.3 S2.4 S2.5；depends: T2 T3 T4 T5 T6）
- [ ] T8: `platform_reporter.py` 采集与循环 — acceptance: 心跳周期 10s、快照 60s、HTTP timeout 25s；Windows load_avg=None；无 docker/systemd 空数组不抛错；异常不杀主程序（covers: S2.1 S2.6）
- [ ] T9: Agent 指令执行 — acceptance: 双侧白名单；`subprocess` 参数列表且无 `shell=True`；`project_deploy` 校验路径前缀与 `deploy.sh`；Windows 拒绝 service_*（covers: S2.4 S2.6）
- [ ] T10: `agent_integration.py` 示例 — acceptance: 中文注释；主程序仅调用 `start_reporting()` 一次即可接入（covers: S2.6；depends: T8 T9）
- [ ] T11: 前端工程与布局 — acceptance: Vite+Vue3+TS+Element Plus；路由；axios JWT 拦截与统一错误；暗色模式；侧边栏+顶栏（covers: S2.1 S2.7）
- [ ] T12: Dashboard — acceptance: 4 统计卡、ECharts 趋势可按节点筛、节点表与 5s 轮询开关、前端离线防抖（covers: S2.7；depends: T11）
- [ ] T13: 节点详情四 Tab — acceptance: 概览仪表盘；资源运维四子标签+二次确认+危险红；Windows 服务「不支持」；实时日志终端；指令历史；`project_deploy` 默认不露出（covers: S2.7；depends: T11）
- [ ] T14: 登录页与构建验收 — acceptance: 居中登录卡片与默认密码提示；响应式可用；`tsc` 0 error 且 `vite build` 成功（covers: S2.7；depends: T11 T12 T13）
- [ ] T15: 部署六件套 — acceptance: compose 三服务+healthcheck+命名卷；Dockerfile 多阶段；nginx 含 `/api/` 与 WS Upgrade；`.env.example` 无真实密码；PG 不映射宿主机端口（covers: S2.8）
- [ ] T16: 中文 README — acceptance: ASCII 架构图、快速启动、Agent 集成、资源运维说明、备份命令、生产复用现有 nginx 的 server 块说明（covers: S2.8；depends: T15）
