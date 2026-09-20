---
feature: ops-platform
status: delivered
updated: 2026-09-20
branch: ops/platform
commits: 8edf67d..bec1dec # reviewed implementation; finalize/doc+residual in cce737d
---

# 轻量级 Agent 管理平台（PostgreSQL 版）

## Report

**What was built** — 在 worktree `ops/platform` 交付了完整 P1–P4：FastAPI + PostgreSQL 16 后端（六表、JWT 强制改密、Agent 心跳/快照/指令队列、白名单双侧校验、metrics 7d / logs 3d 清理、WS 日志 `?token=` 鉴权）；`platform_reporter.py` daemon 上报与受限指令执行（禁 `shell=True`，Windows 服务降级，`project_deploy` 默认关）；Vue3 + Element Plus + ECharts 前端（Dashboard、节点详情四 Tab、登录/改密、深色模式、5s 轮询与离线防抖）；Compose 六件套与中文 README。安全评审 critical（注册劫持、WS 无鉴权、deploy 空 snapshot/穿越、强制改密未在服务端生效）已修复并回归通过。

**Verification** —
- `ruff check platform agent tests` — PASS
- `pytest -q` — PASS（24 tests，含安全回归）
- `npx vue-tsc --noEmit` — PASS exit 0
- `npm run build` — PASS exit 0
- 实时 API 链路 `register→heartbeat→snapshot→commands→result` — PASS；负例：非法 action / Windows service / project_deploy 默认关 / 注册劫持 / WS 无 token — PASS
- `docker compose config`（WSL + 本地 `.env`）— services `db/platform/nginx` 解析正常；db 无宿主机端口；healthcheck/`depends_on` 存在
- Windows 无 docker CLI；`compose up` 全镜像构建未在本机执行（引擎在 WSL，留给 P5/生产）

**Journey log** —
1. 包名用 `app` 而非 `platform`，避免与 Python 标准库冲突；Dockerfile 路径仍按计划 `platform/Dockerfile`。
2. 评审 REQUEST_CHANGES 后集中修 C1–C4：已有节点注册必须出示**当前** token；WS `?token=` JWT；deploy 路径用 Unix 字符串规范化拒绝 `..`（勿用 `Path.resolve`，Windows 会改盘符）；管理 API `require_password_changed`。
3. 心跳下发时 `pending→running`，避免结果回传失败导致每 10s 重复执行危险指令。
4. Agent 双侧校验在空 snapshot 时应 fail-closed（`if not known or name not in known`），与服务端一致。
5. 计划文件 `PLAN.md` / `运维平台-执行计划.md` 含 §11 密码，已 gitignore，真实密钥不入仓。

## [S1] Problem

小主机/国内机/海外机分散，缺少统一的节点在线状态、资源指标、容器与项目运维入口。需要 **Agent 主动上报、平台绝不反连** 的轻量平台：心跳与资源快照、指令队列拉取、日志与指标可视化；Windows 小主机无 systemd 时服务运维降级；生产部署到国内机并复用现有 nginx。

本地冻结任务书：`PLAN.md` / `运维平台-执行计划.md`（含网络与密码，**不入仓**）。

## [S2] Design

### [S2.1] Tech stack（冻结）

- 后端：Python 3.11 + FastAPI + SQLAlchemy 2.x + Pydantic v2 + `psycopg`（v3）
- DB：PostgreSQL 16；连接池 `pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600`
- 时间：`DateTime(timezone=True)`；JSON：SQLAlchemy `JSON`
- 实时：WebSocket 日志（`?token=` JWT，2s 节流）；前端：Vue 3 + Vite + TS + Element Plus + ECharts 5
- 部署：Compose `db` / `platform` / `nginx`（生产 nginx 由国内机现有实例接管）
- Agent：`platform_reporter.py`，daemon 线程，异常不杀主程序
- 禁止：K8s / RabbitMQ / Redis / 微服务 / Flask / SQLite / `shell=True` / Vue2 Options API

### [S2.2] Data model（6 表）

`nodes` / `metrics`（联合索引 `(node_id, timestamp)`）/ `commands`（`pending|running|done|failed`）/ `logs` / `resource_snapshots` / `users`（bcrypt + `must_change_password`）。

初始化：`create_all` + 默认 admin（`ADMIN_PASSWORD`），首次登录强制改密（服务端 403 直至改密）。在线判定：`now - last_seen_at < 30s` + 前端连续 2 次超时才标离线。

### [S2.3] API contracts

Agent（节点 Bearer）：`POST /nodes/register`、`heartbeat`（响应 `pending_commands`，下发后标 `running`）、`resource-snapshot`、`commands/{id}/result`。

管理端（JWT，且必须已改密）：nodes 列表/详情/资源/metrics/logs/commands；`POST /auth/login`、`/auth/change-password`；`WS /nodes/{id}/logs?token=<jwt>`。

### [S2.4] Command whitelist（服务端 + Agent 双侧，fail-closed）

参数必须存在于最近 snapshot，否则拒绝（空 snapshot 亦拒）。`service_*` 在 Windows 节点直接拒。`project_deploy`：配置默认关；路径前缀 `/opt/projects/`、`/data/apps/`；拒绝 `..`；目录下须有 `deploy.sh`。执行 `subprocess` 参数列表，禁止 `shell=True`。

### [S2.5] Data retention

metrics 7 天、logs 3 天；平台内小时级清理循环。Agent 心跳周期 10s、快照 60s、HTTP `timeout=25`。

### [S2.6] Agent reporter

`collect_metrics` / `collect_resources` / `execute_command` / `start_reporting`；Windows `load_avg=None`；无 docker/systemd → 空数组不报错；`agent_integration.py` 中文示例。

### [S2.7] Frontend

Dashboard（4 统计卡 + 趋势 + 节点表 + 5s 轮询开关）；节点详情四 Tab（概览/资源运维/实时日志/指令历史；Windows 服务「不支持」；危险操作二次确认）；全局侧边栏+顶栏+暗色模式；登录与强制改密流；`project_deploy` 按钮默认不露出。

### [S2.8] Deploy

`docker-compose.yml`（healthcheck、命名卷 `pgdata`、db 无宿主机端口）；`platform/Dockerfile` 多阶段；`nginx` 多阶段构建前端并反代 `/api/` + WS Upgrade；`.env.example` 无真实密码；中文 README（架构图/启动/集成/备份/生产 server 块说明）。

### [S2.9] Engineering conventions

Commit：`ops: <phase>-<内容>`。合入 master 需 Hermes 明确同意。密码/计划文件不入仓。命令状态含 `running`（防重复下发）。

## [S3] Out of Scope

K8s / Redis / RabbitMQ / 微服务；任意 shell 字符串接口；`shell=True`；PG 公网暴露；真实密码入仓；恒生首期接入；`project_deploy` 默认开启；生产上机与 28 号部署链路；自行 merge main；`ops-v0.*` 正式 tag（待 Hermes 验收后打）。

## Tasks

- [x] T1: 后端工程骨架与配置 — acceptance: `app` 包可导入；settings 读取 DB/JWT/ADMIN 环境变量；requirements 齐全（covers: S2.1 S2.2）
- [x] T2: 六表模型与初始化 — acceptance: 字段与 [S2.2] 一致；`create_all` + 默认 admin + `must_change_password`（covers: S2.2）
- [x] T3: 认证 API — acceptance: login JWT；改密生效；错误凭据 401；默认密码会话在改密前管理 API 403（covers: S2.3）
- [x] T4: Agent 上报 API — acceptance: register/heartbeat/snapshot/result；`pending_commands`；节点 Bearer；online <30s；已有节点不可被陌生 token 劫持（covers: S2.3 S2.5）
- [x] T5: 管理查询 + 指令 + WS — acceptance: 列表/详情/资源/metrics/logs/commands；WS JWT 鉴权 + 2s 节流（covers: S2.3）
- [x] T6: 白名单、能力降级与数据保留 — acceptance: 非法 action/name、Windows service、空 snapshot、deploy 默认关/穿越 均拒；retention 可触发（covers: S2.4 S2.5）
- [x] T7: 后端测试与 ruff — acceptance: pytest 全绿（主链路+负例+安全回归）；ruff 通过（covers: S2.3 S2.4 S2.5；depends: T2–T6）
- [x] T8: `platform_reporter.py` 采集与循环 — acceptance: 10s/60s/timeout 25；Windows 降级；异常不杀主程序（covers: S2.1 S2.6）
- [x] T9: Agent 指令执行 — acceptance: 双侧白名单 fail-closed；无 `shell=True`；deploy 路径校验；Windows 拒 service_*（covers: S2.4 S2.6）
- [x] T10: `agent_integration.py` 示例 — acceptance: 中文注释；`start_reporting()` 一次接入（covers: S2.6；depends: T8 T9）
- [x] T11: 前端工程与布局 — acceptance: Vue3+Vite+TS+Element Plus；JWT 拦截；暗色模式；侧边栏+顶栏（covers: S2.1 S2.7）
- [x] T12: Dashboard — acceptance: 4 卡、ECharts、5s 轮询、离线防抖（covers: S2.7；depends: T11）
- [x] T13: 节点详情四 Tab — acceptance: 四 Tab；Windows 服务不支持；二次确认；project_deploy 默认不露出（covers: S2.7；depends: T11）
- [x] T14: 登录页与构建验收 — acceptance: 登录+强制改密；`tsc` 0 error + `vite build` 通过（covers: S2.7；depends: T11–T13）
- [x] T15: 部署六件套 — acceptance: compose 三服务+healthcheck+命名卷；Dockerfile 多阶段；nginx WS；db 无宿主机端口（covers: S2.8）
- [x] T16: 中文 README — acceptance: 架构图、快速启动、Agent 集成、备份命令、生产 nginx 说明（covers: S2.8；depends: T15）
