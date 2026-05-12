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
app/cache.py       — in-memory TTL cache (1 hour) to avoid redundant API calls
app/reputation.py  — fetches and consolidates data from AbuseIPDB and IPInfo
app/main.py        — FastAPI app with /health and /reputation/{ip} endpoints
tests/test_main.py — automated tests using pytest and mocks (no real API calls)
Dockerfile         — multi-stage build: deps stage + lean runtime stage
```

**Key design decisions:**

- Input validation rejects anything that isn't a valid IPv4/IPv6 address (returns 400)
- `/health` endpoint is kept intentionally simple — no external calls — so the load balancer health check never fails due to a third-party outage
- Graceful degradation: if one external API fails, the response still includes data from the other
- Cache is per-process (in-memory); with multiple containers running, each has its own cache — a shared Redis cache would be the production solution
- Container runs as a non-root user (`appuser`) for security

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

## Roadmap

- **Phase 2** — Manual AWS deployment: push image to ECR, run on ECS Fargate behind an Application Load Balancer, store API keys in Secrets Manager, deploy across 2 availability zones
- **Phase 3** — CI/CD with GitHub Actions: automated test → build → push to ECR → rolling deploy to ECS on every push to `main`
- **Phase 4** — Infrastructure as Code with Terraform
- **Phase 5** — Observability: CloudWatch dashboard, custom metrics (cache hit rate, external API latency), alarms