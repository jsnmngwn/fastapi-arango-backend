"""
Initialize ArangoDB for FastAPI ArangoDB Backend
Usage:
    poetry run python scripts/init_arangodb.py
"""

import json
import os
from pathlib import Path
from arango import ArangoClient
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Database connection parameters
ARANGO_HOST = os.environ.get("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.environ.get("ARANGO_USER", "root")
ARANGO_PASS = os.environ.get("ARANGO_PASSWORD", "rootpassword")
DB_NAME = os.environ.get("ARANGO_DB", "app_db")

# Path to config file
CONFIG_PATH = Path(__file__).parent.parent / "backend" / "config" / "collections.json"


# Default collections in case config file is not found (generic example)
DOCUMENT_COLLECTIONS = [
    "users",
    "products",
    "categories",
    "orders",
    "resources",
]

EDGE_COLLECTIONS = [
    "user_order",
    "product_category",
    "order_product",
]

# Graph support is optional; kept generic for demo purposes
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

# Try to load from config file if it exists
try:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            collection_config = json.load(f)

        # Override with config values
        DOCUMENT_COLLECTIONS = collection_config.get(
            "document_collections", DOCUMENT_COLLECTIONS
        )
        EDGE_COLLECTIONS = collection_config.get("edge_collections", EDGE_COLLECTIONS)
        GRAPH_EDGES = collection_config.get("graph_edges", GRAPH_EDGES)
        print(f"Loaded collection configuration from {CONFIG_PATH}")
    else:
        print(f"Collection config file not found at {CONFIG_PATH}, using defaults")
except Exception as e:
    print(f"Error loading collection config: {str(e)}")
    print("Using default collection configuration")


def main():
    client = ArangoClient(hosts=ARANGO_HOST)
    sys_db = client.db("_system", username=ARANGO_USER, password=ARANGO_PASS)

    # Create database if it doesn't exist
    if not sys_db.has_database(DB_NAME):
        sys_db.create_database(DB_NAME)
        print(f"Database '{DB_NAME}' created.")
    else:
        print(f"Database '{DB_NAME}' already exists.")

    db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASS)

    # Create document collections
    for col in DOCUMENT_COLLECTIONS:
        if not db.has_collection(col):
            db.create_collection(col)
            print(f"Collection '{col}' created.")
        else:
            print(f"Collection '{col}' already exists.")

    # Create edge collections
    for col in EDGE_COLLECTIONS:
        if not db.has_collection(col):
            db.create_collection(col, edge=True)
            print(f"Edge collection '{col}' created.")
        else:
            print(f"Edge collection '{col}' already exists.")

    # Create graph
    if not db.has_graph(GRAPH_NAME):
        print(f"Creating graph: {GRAPH_NAME}")
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
                        existing_edge_definitions.append(edge_def["edge_collection"])
                    elif "name" in edge_def:
                        existing_edge_definitions.append(edge_def["name"])
                elif isinstance(edge_def, str):
                    existing_edge_definitions.append(edge_def)
        except Exception as e:
            print(f"Error getting edge definitions: {str(e)}")
            # If we can't get edge definitions, we'll try to recreate them
            existing_edge_definitions = []

        # Add missing edge definitions
        for edge_def in GRAPH_EDGES:
            edge_name = edge_def["edge_collection"]

            if edge_name not in existing_edge_definitions:
                print(f"Adding edge definition to graph: {edge_name}")
                graph.create_edge_definition(
                    edge_collection=edge_name,
                    from_vertex_collections=edge_def["from_collections"],
                    to_vertex_collections=edge_def["to_collections"],
                )

    print("ArangoDB initialized with database and collections.")


if __name__ == "__main__":
    main()
