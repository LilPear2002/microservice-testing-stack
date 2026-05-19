"""Utility functions for web-app"""
import sqlite3
import hashlib
import json
from datetime import datetime

DB_PATH = "/var/data/app.db"

def init_db():
    """Initialize database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
    return conn

def handle_request(method, path, body=None):
    """Handle incoming HTTP request"""
    if method == "GET":
        return {"status": 200, "data": {"message": "OK", "path": path}}
    elif method == "POST":
        return {"status": 201, "data": {"id": 42, "body": body}}
    return {"status": 405, "error": "Method Not Allowed"}

def hash_password(password):
    """Hash a password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()
