# System Architecture

## Overview
Microservice architecture with 3 core services.

## Services
| Service   | Port | Language | Status      |
|-----------|------|----------|-------------|
| web-app   | 8080 | Python   | production  |
| api       | 3000 | Python   | production  |
| worker    | 9001 | Go       | beta        |

## Dependencies
- PostgreSQL 14
- Redis 7
- Kafka 3.5
- Nginx (reverse proxy)

## Known Issues
1. Memory leak in worker service under high load
2. API timeout when database connection pool exhausted
3. Web-app returns 500 on large file uploads > 100MB
