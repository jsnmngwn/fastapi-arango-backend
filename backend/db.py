"""Database module for FastAPI ArangoDB backend application."""

import os
import json
from pathlib import Path

from arango import ArangoClient
from loguru import logger

# Database connection parameters
DB_HOST = os.environ.get("ARANGO_HOST", "http://localhost:8529")
DB_USER = os.environ.get("ARANGO_USER", "root")
DB_PASS = os.environ.get("ARANGO_PASSWORD", "rootpassword")
DB_NAME = os.environ.get("ARANGO_DB", "fastapi_arango_db")

# Load collections from config
CONFIG_PATH = Path(__file__).parent / "config" / "collections.json"

# Default collections in case config file is not found
DOCUMENT_COLLECTIONS = ["users", "products", "categories", "orders", "resources"]

EDGE_COLLECTIONS = ["user_order", "product_category", "order_product"]

GRAPH_NAME = "example_graph"
GRAPH_EDGES = [
    {
        "edge_collection": "user_order",
        "from_collections": ["users"],
        "to_collections": ["orders"],
    },
    {
        "edge_collection": "product_category",
        "from_collections": ["products"],
        "to_collections": ["categories"],
    },
    {
        "edge_collection": "order_product",
        "from_collections": ["orders"],
        "to_collections": ["products"],
    },
]

# Try to load from the config file if it exists
try:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            DOCUMENT_COLLECTIONS = config.get(
                "document_collections", DOCUMENT_COLLECTIONS
            )
            EDGE_COLLECTIONS = config.get("edge_collections", EDGE_COLLECTIONS)
            GRAPH_EDGES = config.get("graph_edges", GRAPH_EDGES)
            logger.info(f"Loaded collections from {CONFIG_PATH}")
    else:
        logger.warning(f"Configuration file {CONFIG_PATH} not found, using defaults")
except Exception as e:
    logger.error(f"Error loading configuration from {CONFIG_PATH}: {e}")
    logger.warning("Using default collections")

# Singleton database connection
_db_connection = None


def get_db_connection(
    host=DB_HOST, username=DB_USER, password=DB_PASS, database_name=DB_NAME
):
    """
    Establish a connection to the ArangoDB database.

    Args:
        host: ArangoDB host URL
        username: Database username
        password: Database password
        database_name: Name of the database to connect to

    Returns:
        Database connection object
    """
    global _db_connection

    if _db_connection is not None:
        return _db_connection

    try:
        # Initialize the client
        client = ArangoClient(hosts=host)

        # Connect to the system database to check if our database exists
        sys_db = client.db("_system", username=username, password=password)

        # Create database if it doesn't exist
        if not sys_db.has_database(database_name):
            logger.info(f"Creating database: {database_name}")
            sys_db.create_database(database_name)

        # Connect to the application database
        _db_connection = client.db(database_name, username=username, password=password)
        logger.info(f"Connected to database: {database_name}")
        return _db_connection

    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise


def get_db():
    """
    Get the database connection.

    Returns:
        Database connection object
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = get_db_connection()
    return _db_connection


def get_collection(collection_name):
    """
    Get a collection from the database.

    Args:
        collection_name: Name of the collection to retrieve

    Returns:
        Collection object
    """
    db = get_db()
    if not db.has_collection(collection_name):
        logger.warning(f"Collection {collection_name} does not exist. Creating it.")
        if collection_name in EDGE_COLLECTIONS:
            db.create_collection(collection_name, edge=True)
        else:
            db.create_collection(collection_name)

    return db.collection(collection_name)


def init_db():
    """
    Initialize the database with collections and graph structure.

    This function should be called when the application starts.
    """
    try:
        db = get_db()

        # Create document collections
        for collection_name in DOCUMENT_COLLECTIONS:
            if not db.has_collection(collection_name):
                logger.info(f"Creating document collection: {collection_name}")
                db.create_collection(collection_name)

        # Create edge collections
        for collection_name in EDGE_COLLECTIONS:
            if not db.has_collection(collection_name):
                logger.info(f"Creating edge collection: {collection_name}")
                db.create_collection(collection_name, edge=True)

        # Create graph
        if not db.has_graph(GRAPH_NAME):
            logger.info(f"Creating graph: {GRAPH_NAME}")
            graph = db.create_graph(GRAPH_NAME)

            # Add edge definitions to graph
            for edge_def in GRAPH_EDGES:
                graph.create_edge_definition(
                    edge_collection=edge_def["edge_collection"],
                    from_vertex_collections=edge_def["from_collections"],
                    to_vertex_collections=edge_def["to_collections"],
                )
        else:
            # Get existing graph
            graph = db.graph(GRAPH_NAME)

            # Get existing edge definitions
            existing_edge_definitions = []
            try:
                for edge_def in graph.edge_definitions():
                    if hasattr(edge_def, "name"):
                        existing_edge_definitions.append(edge_def.name)
                    elif isinstance(edge_def, dict):
                        if "edge_collection" in edge_def:
                            existing_edge_definitions.append(
                                edge_def["edge_collection"]
                            )
                        elif "name" in edge_def:
                            existing_edge_definitions.append(edge_def["name"])
                    elif isinstance(edge_def, str):
                        existing_edge_definitions.append(edge_def)
            except Exception as e:
                logger.warning(f"Error getting edge definitions: {str(e)}")
                # If we can't get edge definitions, we'll try to recreate them
                existing_edge_definitions = []

            # Add missing edge definitions
            for edge_def in GRAPH_EDGES:
                edge_name = edge_def["edge_collection"]

                if edge_name not in existing_edge_definitions:
                    logger.info(f"Adding edge definition to graph: {edge_name}")
                    graph.create_edge_definition(
                        edge_collection=edge_name,
                        from_vertex_collections=edge_def["from_collections"],
                        to_vertex_collections=edge_def["to_collections"],
                    )

        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        # Don't re-raise the exception to allow the application to start
        # Log the full error for debugging


# Create a global database connection for reuse
_db_instance = None


def get_db():
    """Get a shared database connection."""
    global _db_instance
    if _db_instance is None:
        _db_instance = get_db_connection()
    return _db_instance


def get_collection(collection_name):
    """
    Get a collection by name.

    Args:
        collection_name: Name of the collection

    Returns:
        Collection object
    """
    db = get_db()
    if not db.has_collection(collection_name):
        if collection_name in EDGE_COLLECTIONS:
            db.create_collection(collection_name, edge=True)
        else:
            db.create_collection(collection_name)
    return db.collection(collection_name)
