"""Load transformed data into destination"""
import logging

logger = logging.getLogger("pipeline.load")

def load_to_postgres(records, table, connection_string):
    """Bulk load records into PostgreSQL"""
    logger.info(f"Loading {len(records)} records into {table}")
    # Simulated load
    return {"inserted": len(records), "errors": 0, "table": table}

def load_to_redis(data, key_prefix, ttl=3600):
    """Cache data in Redis with TTL"""
    logger.info(f"Caching {len(data)} items with prefix '{key_prefix}', TTL={ttl}s")
    return {"cached": len(data), "ttl": ttl}

def load_to_elasticsearch(documents, index):
    """Index documents into Elasticsearch"""
    logger.info(f"Indexing {len(documents)} docs into '{index}'")
    return {"indexed": len(documents), "index": index}
