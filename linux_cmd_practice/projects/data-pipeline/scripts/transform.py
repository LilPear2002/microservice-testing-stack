"""Transform extracted data"""
import json
import logging

logger = logging.getLogger("pipeline.transform")

def clean_phone(phone):
    """Normalize phone number format"""
    return ''.join(c for c in phone if c.isdigit())

def validate_email(email):
    """Simple email validation"""
    return '@' in email and '.' in email.split('@')[1]

def transform_records(records, schema):
    """Apply schema mapping to records"""
    transformed = []
    for rec in records:
        new_rec = {}
        for target_field, source_field in schema.items():
            new_rec[target_field] = rec.get(source_field)
        transformed.append(new_rec)
    logger.info(f"Transformed {len(transformed)} records")
    return transformed

def deduplicate(records, key_field):
    """Remove duplicate records by key"""
    seen = set()
    result = []
    for rec in records:
        key = rec.get(key_field)
        if key not in seen:
            seen.add(key)
            result.append(rec)
    logger.info(f"Dedup: {len(records)} -> {len(result)} records")
    return result
