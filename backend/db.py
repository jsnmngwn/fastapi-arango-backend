"""Generic Database module for FastAPI ArangoDB backend application."""

import os
import json
from pathlib import Path
from arango import ArangoClient
from loguru import logger

# Generic database connection parameters
DB_HOST = os.environ.get("ARANGO_HOST", "http://localhost:8529")
DB_USER = os.environ.get("ARANGO_USER", "root")
DB_PASS = os.environ.get("ARANGO_PASSWORD", "rootpassword")
DB_NAME = os.environ.get("ARANGO_DB", "app_db")

# Optionally load collection names from config, else use empty/generic defaults
CONFIG_PATH = Path(__file__).parent / "config" / "collections.json"
DOCUMENT_COLLECTIONS = []
EDGE_COLLECTIONS = []
try:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            DOCUMENT_COLLECTIONS = config.get("document_collections", DOCUMENT_COLLECTIONS)
            EDGE_COLLECTIONS = config.get("edge_collections", EDGE_COLLECTIONS)
        logger.info(f"Loaded collections from {CONFIG_PATH}")
    else:
        logger.info(f"No collection config found at {CONFIG_PATH}, using empty defaults.")
except Exception as e:
    logger.error(f"Error loading collection config: {e}")

# Singleton database connection
_db_instance = None


def get_db_connection(
    host=DB_HOST, username=DB_USER, password=DB_PASS, database_name=DB_NAME
):
    """
    Establish a connection to the ArangoDB database, creating the database if needed.
    """
    global _db_instance
    if _db_instance is not None:
        return _db_instance
    try:
        client = ArangoClient(hosts=host)
        sys_db = client.db("_system", username=username, password=password)
        if not sys_db.has_database(database_name):
            logger.info(f"Creating database: {database_name}")
            sys_db.create_database(database_name)
        _db_instance = client.db(database_name, username=username, password=password)
        logger.info(f"Connected to database: {database_name}")
        return _db_instance
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise


def get_db():
    """Get a shared database connection."""
    global _db_instance
    if _db_instance is None:
        _db_instance = get_db_connection()
    return _db_instance


def get_collection(collection_name):
    """
    Get a collection by name, creating it if it does not exist.
    """
    db = get_db()
    if not db.has_collection(collection_name):
        logger.info(f"Creating collection: {collection_name}")
        if collection_name in EDGE_COLLECTIONS:
            db.create_collection(collection_name, edge=True)
        else:
            db.create_collection(collection_name)
    return db.collection(collection_name)


def init_db():
    """
    Initialize the database with configured collections.
    Call this at application startup if you want to ensure collections exist.
    """
    try:
        db = get_db()
        for collection_name in DOCUMENT_COLLECTIONS:
            if not db.has_collection(collection_name):
                logger.info(f"Creating document collection: {collection_name}")
                db.create_collection(collection_name)
        for collection_name in EDGE_COLLECTIONS:
            if not db.has_collection(collection_name):
                logger.info(f"Creating edge collection: {collection_name}")
                db.create_collection(collection_name, edge=True)
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
