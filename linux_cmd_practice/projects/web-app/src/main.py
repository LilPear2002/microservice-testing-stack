"""Web Application Main Module"""
import os
import logging
from utils import init_db, handle_request

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

APP_NAME = "MyWebApp v2.1.0"
PORT = int(os.environ.get("APP_PORT", 8080))

def main():
    logger.info(f"Starting {APP_NAME} on port {PORT}")
    init_db()
    logger.info("Application started successfully")

if __name__ == "__main__":
    main()
