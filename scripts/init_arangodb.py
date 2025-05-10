"""
Initialize ArangoDB for FastAPI ArangoDB Backend
Usage:
    poetry run python scripts/init_arangodb.py
"""

from arango import ArangoClient

ARANGO_HOST = "http://localhost:8529"
ARANGO_USER = "root"
ARANGO_PASS = "rootpassword"
DB_NAME = "fastapi_arango_db"
# Document collections
DOCUMENT_COLLECTIONS = [
    "users",
    "products",
    "categories",
    "orders",
    "resources",
]
# Edge collections
EDGE_COLLECTIONS = [
    "user_order",
    "product_category",
    "order_product",
]


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
    print("ArangoDB initialized with database and collections.")


if __name__ == "__main__":
    main()
