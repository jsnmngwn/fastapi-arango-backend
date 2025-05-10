# Backend (FastAPI with ArangoDB)

This folder contains the FastAPI-based backend for the application.

## Structure

- `routes/`: API endpoints
- `services/`: Business logic and database operations
- `schemas/`: Pydantic models for data validation
- `db.py`: Database connection and configuration
- `main.py`: Application entry point

## Getting Started

To generate CRUD API endpoints for a new entity:

```bash
poetry run python scripts/generate_basic_crud_api_endpoints.py --schema-file schemas/your_entity.schema.json
```

This will create all necessary components for the entity (schemas, services, routes).
