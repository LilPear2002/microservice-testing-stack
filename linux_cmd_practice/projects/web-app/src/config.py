"""Application Configuration"""
import os

# Database settings
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "myapp")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "secret123")

# Redis settings
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = 6379

# App settings
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

SERVERS = ["web01.example.com", "web02.example.com", "web03.example.com"]
REGIONS = {"us-east": "10.0.1.0/24", "us-west": "10.0.2.0/24", "eu-central": "10.0.3.0/24"}
