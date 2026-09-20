# 轻量级 Agent 管理平台（ops-platform）

## 项目简介

面向分散主机（国内机 / 小主机 Windows / 海外机等）的轻量运维平台：统一节点在线状态、资源指标、容器与项目运维入口，支持有限指令下发与日志可视化。

核心原则：**Agent 主动上报，平台绝不反连**。Agent 不开端口、不改防火墙；平台只接收心跳/快照/指令结果，并在心跳响应中返回 `pending_commands` 队列。

生产部署目标：国内机，**复用现有 nginx**（加 server 块 / 子域名反代到独立端口），PostgreSQL 使用独立实例与命名卷，不占用 80/443。

---

## ASCII 架构图（Agent 主动上报）

```
                    +---------------------------+
                    |   管理端浏览器 / 运维人员  |
                    +-------------+-------------+
                                  | HTTPS
                                  v
                    +---------------------------+
                    |  现有 nginx（国内机）      |
                    |  server 块: ops.sida.win  |
                    |  /api/ -> :8081           |
                    +-------------+-------------+
                                  | proxy
                                  v
   +------------------------------------------------------------------+
   |  docker compose (国内机)                                         |
   |                                                                  |
   |   nginx (local/dev only) -----> platform (FastAPI :8081)         |
   |                                      |                           |
   |                                      v                           |
   |                                  db (PostgreSQL 16)              |
   |                                  volume: pgdata                  |
   |                                  (no host port in production)    |
   +------------------------------------------------------------------+
                    ^                 ^                 ^
                    | heartbeat 10s   | heartbeat 10s   | heartbeat 10s
                    | snapshot  60s   | snapshot  60s   | snapshot  60s
                    | pending cmds    | pending cmds    | pending cmds
                    | result 回传     | result 回传     | result 回传
             +------+------+    +------+------+    +------+------+
             | 国内机 Agent  |    | 小主机 Agent  |    | hermes Agent |
             | (Linux)       |    | (Windows)     |    | (Linux)      |
             +---------------+    +---------------+    +--------------+
                  主动上报               主动上报              主动上报
                  (无入站端口)           (无 systemd 降级)     (无入站端口)
```

---

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11 · FastAPI · SQLAlchemy 2.x · Pydantic v2 · psycopg (v3) |
| 数据库 | PostgreSQL 16（`postgres:16-alpine`） |
| 实时 | WebSocket（日志流，2s 节流） |
| 前端 | Vue 3 · Vite · TypeScript · Element Plus（深色模式）· ECharts 5 |
| Agent | Python `platform_reporter.py`（daemon 线程，`timeout=25`） |
| 部署 | Docker Compose：`db` / `platform` / `nginx` |

禁止项（冻结计划）：K8s / Redis / RabbitMQ / 微服务拆分 / Flask / SQLite / `shell=True` / 真实密码入仓。

---

## 目录结构

```
ops-platform/
├── docker-compose.yml          # 三服务编排（db / platform / nginx）
├── .env.example                # 环境变量模板（无真实密钥）
├── requirements.txt            # Python 依赖（镜像构建从仓库根复制）
├── pyproject.toml              # pytest / ruff 配置
├── platform/
│   ├── Dockerfile              # 多阶段 API 镜像
│   └── app/
│       ├── main.py             # FastAPI 入口 + retention 循环
│       ├── config.py           # Settings（DB_*/SECRET_KEY/ADMIN_*）
│       ├── database.py         # engine / session
│       ├── models.py           # 6 表
│       ├── routers/            # auth / nodes / ws
│       └── ...
├── agent/
│   ├── platform_reporter.py    # 上报模块（心跳/快照/指令执行）
│   └── agent_integration.py    # 接入示例
├── nginx/
│   ├── Dockerfile              # 反代镜像（可选拷贝 frontend/dist）
│   └── nginx.conf              # /api/ 反代 + WS Upgrade + gzip
├── frontend/                   # Vue3 前端（npm run build 后产生 dist/）
├── tests/
└── docs/compose/spec/ops-platform.md
```

---

## 快速启动

### 1. 准备环境变量

```bash
cp .env.example .env
# 编辑 .env：DB_PASSWORD / SECRET_KEY / ADMIN_PASSWORD 必须改为强随机值
# 生成示例：
#   openssl rand -hex 32   # SECRET_KEY
```

`project_deploy` 默认关闭：`PROJECT_DEPLOY_ENABLED=false`。

### 2. 启动三服务

```bash
docker compose up -d --build
```

| 服务 | 本地端口 | 说明 |
|---|---|---|
| platform | `8081` | FastAPI，健康检查 `GET /api/v1/health` |
| nginx | `8080` | 本地反代入口（生产不用这个口对外） |
| db | 不映射 | 仅 Docker 内网可达（生产与本地默认一致） |

### 3. 验证

```bash
curl -s http://127.0.0.1:8081/api/v1/health
# {"ok":true,"project_deploy_enabled":false}

curl -s http://127.0.0.1:8080/api/v1/health
# 经 nginx 反代同样应返回 ok
```

默认管理员：用户名 `admin`，密码为 `.env` 中的 `ADMIN_PASSWORD`；**首次登录强制改密**。

### 4. 前端（可选）

```bash
cd frontend
npm install
npm run build   # 产出 frontend/dist
```

构建完成后：取消 `nginx/Dockerfile` 中 `COPY frontend/dist ...` 的注释再重建 nginx 镜像。  
**API-only 模式**无需前端也能完成 Agent 上报与指令联调。

### Windows 本地说明

- Docker 引擎在 WSL（如 `Ubuntu-22.04`）时，请在 WSL 内执行 `docker compose up`。
- Windows 主机上的 `.env` 换行需为 LF，避免解析异常。

---

## Agent 集成

现有 Agent 主程序只需在启动时调用一次 `start_reporting()`：

```python
from platform_reporter import start_reporting

reporter = start_reporting(
    base_url="http://127.0.0.1:8081",   # 生产：https://ops.sida.win 或 http://国内机:8081
    node_id="mini-host-win",             # 每节点唯一
    token="replace-with-node-token",     # 每节点独立 Bearer，勿入仓
    agent_version="0.2.0",
    project_deploy_enabled=False,
)
```

要点：

- 心跳周期 **10s**，HTTP `timeout=25`；资源快照 **60s**
- 线程 `daemon=True`，采集/上报异常被吞掉，**不会拖垮主程序**
- 指令白名单双侧校验；`subprocess` 参数列表，禁止 `shell=True`
- 完整示例见 `agent/agent_integration.py`

节点 token 在部署国内机时为每台预生成，写入节点侧配置，**不进 git**。

---

## 资源运维说明 + Windows 降级

资源运维通过指令队列下发，参数必须来自最近一次 resource snapshot（否则拒绝）：

| action | params | 说明 |
|---|---|---|
| `restart_agent` | 无 | 重启上报线程/进程 |
| `agent_status` | 无 | 查询 Agent 状态 |
| `container_restart/stop/start` | `{name}` | 容器运维 |
| `container_logs` | `{name, lines≤1000}` | 容器日志 |
| `service_restart/stop/status` | `{name}` | systemd 服务（Linux） |
| `image_prune` | 无 | 清理 `<none>` 镜像 |
| `project_deploy` | `{path}` | 仅白名单路径 + `deploy.sh` |

**Windows 降级（小主机）：**

- 无 systemd → `service_*` 指令由 Agent 与平台双侧直接拒绝
- 前端服务 Tab 显示「该节点不支持」，仅提供容器/镜像/项目操作
- `load_avg` 在 Windows 上报 `None`，不伪造数据

**安全默认：**

- `project_deploy` 按钮/接口首版**默认关闭**（`PROJECT_DEPLOY_ENABLED=false`）
- 即使打开，路径也必须在 `/opt/projects/` 或 `/data/apps/` 前缀内，且目录下存在预定义 `deploy.sh`

---

## API 摘要

Agent（Bearer = 节点 token）：

| 方法 | 路径 |
|---|---|
| POST | `/api/v1/nodes/register` |
| POST | `/api/v1/nodes/{node_id}/heartbeat`（响应含 `pending_commands`） |
| POST | `/api/v1/nodes/{node_id}/resource-snapshot` |
| POST | `/api/v1/nodes/{node_id}/commands/{command_id}/result` |

管理端（JWT）：

| 方法 | 路径 |
|---|---|
| POST | `/api/v1/auth/login` |
| GET | `/api/v1/nodes` |
| GET | `/api/v1/nodes/{node_id}` |
| GET | `/api/v1/nodes/{node_id}/resources` |
| GET | `/api/v1/nodes/{node_id}/metrics?range=1h\|6h\|24h` |
| GET | `/api/v1/nodes/{node_id}/logs?limit=200` |
| WS | `/api/v1/nodes/{node_id}/logs` |
| POST | `/api/v1/nodes/{node_id}/commands` |
| GET | `/api/v1/nodes/{node_id}/commands` |
| GET | `/api/v1/health` |

在线判定：`now - last_seen_at < 30s`；前端连续 2 次超时才标离线。  
数据保留：metrics 7 天，logs 3 天（平台内定时清理）。

---

## 数据库备份命令

PostgreSQL 在 Compose 网络内，**无宿主机端口**。备份使用 `docker exec`：

```bash
# 逻辑备份（在 docker-compose.yml 所在目录执行；密码来自 .env）
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > ops_platform_$(date +%Y%m%d_%H%M%S).sql

# 或指定容器名
docker exec -t ops-db pg_dump -U ops -d ops_platform > ops_platform_backup.sql

# 恢复示例
cat ops_platform_backup.sql | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

命名卷：`ops-platform-pgdata`（`docker volume inspect ops-platform-pgdata`）。  
生产备份建议配合宿主机 cron + 异地拷贝；恢复前先停 platform 服务。

---

## 生产接入现有 nginx（国内机）

生产**不要**用本仓库的 nginx 容器对外开 80/443。应在国内机**现有 nginx** 上新增 server 块，反代到平台独立端口 `8081`。

域名占位：`ops.sida.win`（解析与证书按现行 sida.win 链路办理；上线前先验证可达性，防 SNI 问题）。

```nginx
# 示例：加入现有 nginx 的 conf.d / sites-available
# 域名 ops.sida.win 为占位，按实际申请结果替换
# 上游为国内机本机 platform 端口 8081（compose 已发布该端口）
#
# 注意：若现有 nginx 已定义 map $http_upgrade $connection_upgrade，
# 请勿重复添加该 map（会报 duplicate map），只复制下面的 server 块。

map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 443 ssl http2;
    server_name ops.sida.win;

    # ssl_certificate     /path/to/ops.sida.win.pem;   # 按现有证书路径填写
    # ssl_certificate_key /path/to/ops.sida.win.key;

    location /api/ {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }

    # 若已构建前端，可将 dist 放到该 server 的 root 下
    location / {
        root /var/www/ops-platform;   # 路径按实际放置位置调整
        try_files $uri $uri/ /index.html;
    }
}

# 如需 HTTP 跳转，按现有站点惯例添加 80 -> 380 重定向
```

生产检查清单：

1. `.env` 放在部署目录，权限收紧，**不入仓**
2. `db` 不映射宿主机端口（保持 compose 默认）
3. `platform` 仅监听内网或经现有 nginx 暴露
4. 新子域名先 `curl` 验证再切换流量
5. 生产变更走协调流程，不在本仓库自动上机

---

## 安全注意

1. **真实密码 / token 不入仓**：`.env`、节点 Bearer、生产 PG 密码一律只留在部署主机；仓库只保留 `.env.example` 占位。
2. **`project_deploy` 默认关**：`PROJECT_DEPLOY_ENABLED=false`；前端按钮默认隐藏/禁用；即使开启也仅允许白名单路径下预定义 `deploy.sh`。
3. **PG 不暴露公网**：生产与本地 compose 均默认不映射 db 宿主机端口。
4. **JWT / admin**：`SECRET_KEY` 与 `ADMIN_PASSWORD` 在部署时现生成；首次登录强制改密。
5. **指令面最小化**：白名单外 action、snapshot 中不存在的 name、Windows 节点 service_* 一律拒绝。
6. **禁止 `shell=True`**：Agent 执行命令使用参数列表。
7. **网络暴露最小化**：生产复用现有 nginx 与 HTTPS 链路，不新开 80/443 直连容器。

---

## 开发与测试

```bash
# 后端测试（仓库根）
python -m pytest
ruff check platform agent tests

# 前端
cd frontend && npm run typecheck && npm run build
```

本地不经过 Docker 时，可将 `DB_HOST` 指向可达的 PostgreSQL，并保证库已创建。

---

## License / 归属

内部运维平台，按冻结执行计划分阶段交付（Phase 1–4）。合入主分支需验收方确认。
