# Deployment Guide

## Prerequisites
- Docker 24+
- Docker Compose v2
- 4GB RAM minimum

## Quick Start
```bash
docker compose up -d
```

## Environment Variables
Required:
- DB_PASSWORD
- REDIS_PASSWORD
- JWT_SECRET

Optional:
- LOG_LEVEL (default: INFO)
- MAX_WORKERS (default: 4)
- ENABLE_METRICS (default: false)

## Health Checks
- Web: http://localhost:8080/health
- API: http://localhost:3000/health
