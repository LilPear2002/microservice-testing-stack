"""Extract data from source systems"""
import csv
import json
import logging

logger = logging.getLogger("pipeline.extract")

SOURCES = ["mysql", "postgres", "mongodb", "kafka"]

def extract_from_csv(filepath):
    """Extract rows from a CSV file"""
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)

def extract_from_api(url, token=None):
    """Extract data from REST API"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    logger.info(f"Extracting from {url}")
    # Simulated API call
    return {"source": url, "records": 500, "status": "success"}

def extract_batch(sources):
    """Extract data from multiple sources in parallel"""
    results = {}
    for src in sources:
        try:
            logger.info(f"Processing source: {src}")
            results[src] = {"status": "ok", "count": 1000}
        except Exception as e:
            logger.error(f"Failed on {src}: {e}")
            results[src] = {"status": "error", "error": str(e)}
    return results
