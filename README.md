# FastAPI ArangoDB Backend

A modular, reusable backend built with FastAPI and ArangoDB, designed to serve as a foundation for web applications.

## Key Features

- **FastAPI Framework**: High-performance, easy-to-use web framework with automatic interactive documentation
- **ArangoDB Integration**: Multi-model NoSQL database with document, graph, and search capabilities
- **Docker Deployment**: Easy setup with Docker and Docker Compose
- **Schema-Driven Development**: JSON Schema definitions for data models with validation
- **Code Generation**: Automated CRUD API generation based on schemas
- **Edge Collections**: Built-in support for modeling relationships between entities
- **Generic Data Model**: Example entities (users, products, orders, categories) ready for customization

## Project Structure

```
.
├── backend/             # FastAPI application code
│   ├── routes/          # API endpoints
│   ├── services/        # Business logic and database operations
│   ├── schemas/         # Pydantic models for data validation
│   ├── db.py            # Database connection and configuration
│   └── main.py          # Application entry point
├── docs/                # Documentation
│   ├── api_endpoint_creation_guide.md
│   └── basic_crud_api_generator_guide.md
├── schemas/             # JSON Schema definitions
├── scripts/             # Utility scripts
│   ├── drop_all_collections.py
│   └── init_arangodb.py
├── docker-compose.yml   # Docker Compose configuration
├── Dockerfile           # Docker image definition
└── pyproject.toml       # Python package configuration
```

## Prerequisites

- Docker and Docker Compose installed on your system
  - Follow the [official Docker installation guide](https://docs.docker.com/get-docker/) to install Docker.
  - Install Docker Compose, which is included with Docker Desktop or can be installed separately for Linux.

## Getting Started

### Using Docker Compose (Recommended)

The easiest way to set up the entire application with ArangoDB and the FastAPI backend is using Docker Compose:

```bash
docker compose up -d
```

This command will:
- Start ArangoDB with persistent storage on `localhost:8529`
- Build and start the FastAPI backend container

The API will be available at [http://localhost:8000](http://localhost:8000) with interactive documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

### Development Environment

#### Steps:

1. **Start ArangoDB**:
   ```bash
   docker compose up -d arangodb
   ```
   This will start ArangoDB on `localhost:8529` with root password `rootpassword` and persist data in a Docker volume.

2. **Run the Backend Development Container**:
   Build and start a container for the backend:
   ```bash
   docker build -t fastapi-arango-backend .
   docker run -it --rm -v $(pwd):/app -p 8000:8000 --name fastapi-arango-backend fastapi-arango-backend bash
   ```
   Inside the container, you can:
   ```bash
   # Install dependencies
   poetry install
   
   # Initialize the database
   poetry run python scripts/init_arangodb.py
   
   # Start the application in development mode
   poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Testing

Run the tests:
```bash
poetry run pytest backend/tests/
```

## Customizing for Your Project

1. Modify or create JSON schema files in the `/schemas` directory for your data model
2. Run the API generator script to create endpoints:
   ```bash
   poetry run python scripts/generate_basic_crud_api_endpoints.py --schema-file schemas/your_entity.schema.json
   ```
3. Add custom business logic in the service layer
4. Define additional routes for specialized endpoints

## Documentation

For more detailed information, refer to:

- [API Endpoint Creation Guide](docs/api_endpoint_creation_guide.md)
- [Basic CRUD API Generator Guide](docs/basic_crud_api_generator_guide.md)
