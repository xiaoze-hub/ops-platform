# ops-platform 国内机部署验证（勿碰 panwatch / 80 / 443）

目标机：国内机 Tailscale `100.73.2.76`（公网 101.35.244.238）
端口：platform **8081**，PG 仅 Docker 内网
前置：已有 SSH 密钥可登录 `xiaoze-hub@100.73.2.76`，机上已装 docker compose

## 1. 上传代码

```bash
# 从小主机打包（不含 .env / PLAN.md）
cd "C:/Users/tianxiang/运维平台"
git archive --format=tar.gz -o /tmp/ops-platform.tar.gz master

scp /tmp/ops-platform.tar.gz xiaoze-hub@100.73.2.76:/tmp/
ssh xiaoze-hub@100.73.2.76 'mkdir -p ~/apps/ops-platform && tar -xzf /tmp/ops-platform.tar.gz -C ~/apps/ops-platform'
```

若远端已有 `ops-platform` git 仓库：

```bash
ssh xiaoze-hub@100.73.2.76 'git clone <REPO_URL> ~/apps/ops-platform && cd ~/apps/ops-platform && git checkout master'
```

## 2. 生成本地 .env（真实密码不入仓）

```bash
ssh xiaoze-hub@100.73.2.76 'cd ~/apps/ops-platform && cat > .env <<EOF
DB_HOST=db
DB_PORT=5432
DB_USER=ops
DB_PASSWORD=$(openssl rand -base64 24)
DB_NAME=ops_platform
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -base64 18)
PROJECT_DEPLOY_ENABLED=false
METRICS_RETENTION_DAYS=7
LOGS_RETENTION_DAYS=3
EOF'
```

## 3. 启动（仅 db + platform，验证阶段可不暴露 nginx）

```bash
ssh xiaoze-hub@100.73.2.76 'cd ~/apps/ops-platform && docker compose up -d db platform'
ssh xiaoze-hub@100.73.2.76 'cd ~/apps/ops-platform && docker compose ps && docker compose logs --tail=50 platform'
```

## 4. 验收清单

```bash
# 健康
curl -sS http://127.0.0.1:8081/api/v1/health

# 登录并强制改密（用 .env 里的 ADMIN_PASSWORD）
# 登录 → change-password → 再 login

# 节点注册 + 心跳（token 自拟，首次 register bearer=body.token）
TOKEN=verify-node-$(date +%s)
curl -sS -X POST http://127.0.0.1:8081/api/v1/nodes/register \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"node_id\":\"verify-cn\",\"hostname\":\"domestic\",\"ip\":\"100.73.2.76\",\"os\":\"Linux\",\"agent_version\":\"0.2.0\",\"token\":\"$TOKEN\"}"
curl -sS -X POST http://127.0.0.1:8081/api/v1/nodes/verify-cn/heartbeat \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"metrics":{"cpu_percent":1,"mem_percent":1,"disk_percent":1,"load_avg":0.1}}'

# 负例：非法 action 必拒（需 admin JWT 且已改密）
```

## 5. 生产接入（P5 / 28 号）

- 不要动 panwatch-postgres、80/443
- 现有 nginx 加 server 块反代 `ops.sida.win` → 国内机 `:8081`（先 curl --resolve 验证 SNI）
- 新子域名 DNS 由 Hermes 操作 Cloudflare

## 6. 小主机 Agent 接入（验证）

```python
# agent/agent_integration.py
start_reporting(base_url="http://100.73.2.76:8081", node_id="mini-host-win", token="<节点token>")
```
