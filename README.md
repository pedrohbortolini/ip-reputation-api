# IP Reputation API

A REST API that receives an IP address and returns reputation data by querying two external sources: **AbuseIPDB** and **IPInfo**. Built as a cloud portfolio project to demonstrate containerization, automated testing, and cloud deployment.

## What it does

Send a GET request with any IP and receive a consolidated report:

```bash
curl http://localhost:8000/reputation/8.8.8.8
```

```json
{
  "ip": "8.8.8.8",
  "abuseipdb": {
    "abuse_score": 0,
    "total_reports": 61,
    "country_code": "US",
    "isp": "Google LLC"
  },
  "ipinfo": {
    "country": "US",
    "city": "Mountain View",
    "org": "AS15169 Google LLC",
    "hostname": "dns.google"
  },
  "errors": [],
  "cached": false
}
```

## Architecture

```
User (curl / browser)
        │
        ▼
   ALB (port 80)  ─── health check every 30s ──▶ /health
        │
   ┌────┴────┐
   ▼         ▼
 ECS Task  ECS Task    (Fargate, 2 AZs, public subnets)
 :8000     :8000
   │         │
   ▼         ▼
 AbuseIPDB + IPInfo    (external APIs via httpx)
```

**Application code:**

```
app/cache.py       — in-memory TTL cache (1 hour) to avoid redundant API calls
app/reputation.py  — fetches and consolidates data from AbuseIPDB and IPInfo
app/main.py        — FastAPI app with /health and /reputation/{ip} endpoints
app/metrics.py     — Prometheus instrumentation (RED metrics + business metrics)
tests/test_main.py — automated tests using pytest and mocks (no real API calls)
Dockerfile         — multi-stage build: deps stage + lean runtime stage
```

**Key design decisions:**

- Input validation rejects anything that isn't a valid IPv4/IPv6 address (returns 400)
- `/health` endpoint is kept intentionally simple — no external calls — so the load balancer health check never fails due to a third-party outage
- Graceful degradation: if one external API fails, the response still includes data from the other
- Cache is per-process (in-memory); with multiple containers running, each has its own cache — a shared Redis cache would be the production solution
- Container runs as a non-root user (`appuser`) for security
- Async functions (`async/await`) with `httpx` allow the server to handle multiple requests concurrently without blocking while waiting for external API responses

## Running locally

**Without Docker:**

```bash
pip install -r requirements.txt
cp .env.example .env  # add your real API keys
export $(cat .env | xargs)
uvicorn app.main:app --reload --port 8000
```

**With Docker:**

```bash
docker build -t ip-reputation-api .
docker run -p 8000:8000 --env-file .env ip-reputation-api
```

**With full observability stack (Prometheus + Grafana + Alertmanager):**

```bash
docker compose up
```

Access: API at `localhost:8000`, Prometheus at `localhost:9090`, Grafana at `localhost:3000` (admin/admin), Alertmanager at `localhost:9093`.

**Tests:**

```bash
pytest -v
```

## Environment variables

| Variable | Description |
|---|---|
| `ABUSEIPDB_KEY` | API key from [abuseipdb.com](https://abuseipdb.com) (free tier: 1000 req/day) |
| `IPINFO_KEY` | API key from [ipinfo.io](https://ipinfo.io) (free tier: 50k req/month) |

Copy `.env.example` to `.env` and fill in your keys. Never commit `.env`.

## Phase 2 — AWS Deployment

The application was deployed to AWS using the following services:

- **ECR** — private container registry to store the Docker image
- **ECS Fargate** — runs 2 containers (tasks) across 2 availability zones without managing servers
- **ALB** — Application Load Balancer distributes traffic on port 80 and performs health checks on `/health`
- **Secrets Manager** — stores API keys securely; injected into containers at runtime via IAM role (never hardcoded or exposed in environment variables)
- **CloudWatch Logs** — captures container logs for debugging

**Security measures:**

- ECS security group only accepts traffic from the ALB security group on port 8000 — containers are not directly accessible from the internet
- Task execution role follows least privilege: only permissions to pull images from ECR and read secrets from Secrets Manager
- Container runs as non-root user inside the image

**What I would change in production:**

- Use private subnets with a NAT Gateway for defense in depth (skipped here to avoid the ~$32/month cost)
- Replace in-memory cache with Redis (ElastiCache) for shared caching across containers
- Add HTTPS with an ACM certificate on the ALB
- Configure ECS auto-scaling based on CPU/memory metrics

## Phase 3 — CI/CD with GitHub Actions

Every push to `main` triggers an automated pipeline:

```
git push → GitHub Actions
              │
              ├─ Job 1: Test
              │   └─ pytest -v (4 tests)
              │         │
              │      pass? ──▶ no ──▶ deploy blocked
              │         │
              │        yes
              │         ▼
              └─ Job 2: Build & Deploy
                  ├─ docker build (tagged with commit SHA)
                  ├─ docker push → ECR
                  ├─ update ECS task definition
                  └─ rolling deploy → ECS (zero downtime)
```

Pipeline configuration is in `.github/workflows/deploy.yml`. AWS credentials are stored as GitHub repository secrets — never in code.

## Phase 4 — Infrastructure as Code

The entire AWS infrastructure is provisioned with OpenTofu (Terraform-compatible) across 5 files in `infra/`:

| File | Resources |
|---|---|
| `main.tf` | Provider, variables, locals, data sources |
| `network.tf` | VPC, 2 public subnets across AZs, Internet Gateway, route tables, security groups |
| `ecs.tf` | ECR with lifecycle policy, CloudWatch logs, IAM roles, ECS cluster, task definition, service |
| `alb.tf` | Application Load Balancer, target group with health checks, HTTP listener |
| `outputs.tf` | ALB DNS, ECR URL, cluster and service names |

```bash
cd infra
tofu init
tofu plan
tofu apply
```

**Key IaC decisions:**

- `ignore_changes` on task definition and desired count — prevents Terraform from reverting CI/CD deployments
- ECR lifecycle policy keeps only the 5 most recent images, controlling storage costs
- IAM execution role follows least privilege: read access only to the specific Secrets Manager secret
- `cidrsubnet()` calculates subnet CIDRs dynamically — code works in any AWS region without hardcoded AZ names

## Phase 5 — Observability

Local observability stack running via Docker Compose: Prometheus collects metrics, Grafana displays dashboards, Alertmanager handles alert routing.

**Instrumented metrics:**

| Metric | Type | What it measures |
|---|---|---|
| `http_requests_total` | Counter | Request count by method, route, and status code |
| `http_request_duration_seconds` | Histogram | Request latency — enables p50/p95/p99 queries |
| `ip_reputation_cache_hits_total` | Counter | Cache hits |
| `ip_reputation_cache_misses_total` | Counter | Cache misses — derive hit rate via PromQL |
| `ip_reputation_cache_size` | Gauge | Current number of entries in cache |
| `external_api_requests_total` | Counter | Calls to AbuseIPDB and IPInfo by status |
| `external_api_duration_seconds` | Histogram | Upstream latency per API — p95 per provider |

**Alert rules (3 SLO-based alerts):**

- `HighErrorRate` — 5xx rate above 5% for 2 minutes (critical)
- `HighLatencyP99` — p99 latency above 500ms for 5 minutes (warning)
- `ExternalAPIFailureRate` — upstream error rate above 20% for 3 minutes (warning)

**Dashboard panels cover:**

- RED method: requests/s by status, error rate %, latency p50/p95/p99
- Cache: hit rate %, current size, hits vs misses over time
- Upstreams: p95 latency per external API, error rate per provider

**Design decisions:**

- `prometheus-client` used directly instead of third-party instrumentator — full control over label cardinality
- Route path template used as label (`/reputation/{ip}` not `/reputation/8.8.8.8`) — prevents cardinality explosion with unique IPs
- Dashboard JSON versioned in Git under `monitoring/grafana/dashboards/` — reproducible, reviewable, not manually created

## Roadmap

- ~~Phase 1~~ — ✅ Application + Docker + tests
- ~~Phase 2~~ — ✅ Manual AWS deployment (ECR, ECS, ALB, Secrets Manager)
- ~~Phase 3~~ — ✅ CI/CD with GitHub Actions
- ~~Phase 4~~ — ✅ Infrastructure as Code with OpenTofu
- ~~Phase 5~~ — ✅ Observability with Prometheus, Grafana and Alertmanager