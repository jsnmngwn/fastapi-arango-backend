# Basic CRUD API Generator Guide

This guide explains how the `generate_basic_crud_api_endpoints.py` script works, its capabilities, and how to use custom schema extensions to generate powerful, customized API endpoints for the VB Stat Logger application.

## Introduction

The basic CRUD API generator (`generate_basic_crud_api_endpoints.py`) is a utility that automatically creates all the necessary components for a complete CRUD (Create, Read, Update, Delete) API based on JSON Schema definitions. It follows the architectural patterns and best practices established in the VB Stat Logger project and generates consistent, well-structured code with proper error handling and validation.

The script is only intended to create the basic APIs.  Custom API endpoints can be added to the existing files, or manually created in custom endpoint files.  If any custom API endpoints are added to an existing file and the generator is re-run, the custom endpoints will be removed.

## How the Generator Works

At a high level, the generator performs these steps:

1. **Parse Schema**: Reads a JSON Schema file to extract entity information, field types, validation rules, and relationships
2. **Generate Schema Models**: Creates Pydantic models that handle validation and serialization
3. **Create Service Layer**: Builds a service class with database operations
4. **Define API Routes**: Generates FastAPI route handlers with appropriate endpoints
5. **Update Registry**: Registers the new routes in the entity registry
6. **Update Imports**: Adds imports to `__init__.py` files for better code organization

## JSON Schema Structure and Extensions

Your schema files should follow this format:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "_id": { "type": "string", "description": "ArangoDB document ID (_id)" },
    "_key": { "type": "string", "description": "ArangoDB document key (_key)" },
    "field1": { 
      "type": "string", 
      "description": "Description of field1" 
    },
    "field2": { 
      "type": "integer", 
      "description": "Description of field2" 
    },
    "active": {
      "type": "boolean",
      "default": true,
      "description": "Is the entity active"
    }
  },
  "required": ["field1"],
  
  // Custom extensions
  "x-unique-combinations": [["field1"]],
  "x-search-fields": ["field1", "field2", "active"]
}
```

### Standard JSON Schema Features

The generator supports all standard JSON Schema features:

#### Data Types

| JSON Schema Type | Generated Python Type |
|-----------------|---------------------|
| `string` | `str` |
| `integer` | `int` |
| `number` | `float` |
| `boolean` | `bool` |
| `array` | `List[Any]` |
| `object` | `Dict[str, Any]` |

#### Formats

Special string formats are mapped to appropriate Python types:

| Format | Generated Python Type |
|--------|---------------------|
| `date-time` | `datetime` |
| `date` | `date` |
| `uri` | `str` (with URL validation) |

#### Required Fields

Fields listed in the `required` array become mandatory fields in the create schema and non-optional in the database schema.

```json
"required": ["name", "created_date"]
```

This will generate create models where these fields are required and proper validation will be applied.

### Custom Extensions

The generator supports several custom extensions that enhance the generated API:

#### 1. `x-unique-combinations`

This extension specifies field combinations that must be unique across all documents in the collection.

```json
"x-unique-combinations": [
  ["name"],                 // Single field uniqueness
  ["team_id", "player_id"]  // Multi-field uniqueness
]
```

For each combination:
- A database index is created to enforce uniqueness
- Validation logic is added to the service class
- Proper HTTP 409 Conflict errors are returned when uniqueness is violated

The generator creates optimized AQL queries for each uniqueness check, with the field names used in error messages.

#### 2. `x-search-fields`

This extension enables smart text search capabilities for specific fields, automatically generating appropriate query endpoints and service methods.

```json
"x-search-fields": [
  "name",
  "description",
  "active"  
]
```

For each search field:
- A query parameter is added to the GET collection endpoint
- String fields use case-insensitive wildcard search (contains)
- Non-string fields (numbers, booleans) use exact matching
- ID fields use exact matching regardless of type

This allows filtering collections by multiple criteria, with appropriate handling for each data type.

Example usage in API:
```
GET /organization?name=volley&active=true
```

#### 3. Default Values

The generator supports standard JSON Schema default values, which are applied when creating new documents if the field is not explicitly provided.

```json
"active": { 
  "type": "boolean", 
  "default": true, 
  "description": "Is the organization active?" 
}
```

The generator handles type conversion between JSON and Python, particularly for boolean values (converting JSON `true`/`false` to Python `True`/`False`).

#### 4. Edge Collections

Edge collections (relationships between entities) are automatically detected when `_from` and `_to` fields are present in the schema.

```json
"properties": {
  "_from": { "type": "string", "description": "Source document handle" },
  "_to": { "type": "string", "description": "Target document handle" }
}
```

For edge collections:
- The collection is created with `edge=True`
- Special field aliases are used (`from_id` and `to_id` in the API)
- Additional edge-specific routes are generated:
  - `GET /{from_entity}/{from_key}/{to_entity}/{to_key}` - Get edges between specific entities
  - `GET /{from_entity}/{from_key}` - Get all edges from a specific entity
  - `GET /{to_entity}/{to_key}` - Get all edges to a specific entity

Edge collection naming should follow the convention `entity1_entity2` (e.g., `player_team`).

## Running the Generator

### For a Single Schema

To generate API components for a single schema:

```bash
cd /home/jason/github/vb-stat-logger
poetry run python scripts/generate_basic_crud_api_endpoints.py schemas/your_entity.schema.json
```

### For All Schemas

To generate API components for all schemas in the schemas directory:

```bash
cd /home/jason/github/vb-stat-logger
poetry run python scripts/generate_basic_crud_api_endpoints.py --all
```

You can also specify a different schemas directory:

```bash
poetry run python scripts/generate_basic_crud_api_endpoints.py --all schemas/subdirectory
```

## Generated Components

For each schema (`entity_name.schema.json`), the generator creates:

### 1. Pydantic Models (`backend/schemas/entity_name.py`)

Six model classes are generated:

- `EntityNameBase` - Base fields used in all schemas
- `EntityNameCreate` - Fields required for entity creation
- `EntityNameUpdate` - Optional fields for partial updates
- `EntityNameInDB` - Complete model with database fields
- `EntityNameResponse` - API response model
- `EntityNameDeleteResponse` - Delete operation response

### 2. Service Class (`backend/services/entity_name_service.py`)

A service class with these methods:

- `create(data)` - Create new entity with validation
- `get_all(skip, limit)` - List entities with pagination
- `get_filtered(filters, skip, limit)` - Retrieve entities with smart filtering (when search fields are defined)
- `get_by_key(key)` - Retrieve single entity by key
- `update(key, data)` - Update entity (using API Guide approach with document merge and replace)
- `delete(key)` - Delete entity

For edge collections, additional methods:
- `get_by_from_to(from_key, to_key)`
- `get_by_from(from_key)`
- `get_by_to(to_key)`

### 3. API Routes (`backend/routes/entity_name_routes.py`)

FastAPI route handlers:

- `POST /entity_name` - Create entity (201 Created)
- `GET /entity_name` - List all entities (with pagination)
  - If search fields are defined, includes query parameters for each field
  - String fields support partial matching with wildcards
  - Non-string fields use exact matching
- `GET /entity_name/{key}` - Get entity by key
- `PATCH /entity_name/{key}` - Update entity
- `DELETE /entity_name/{key}` - Delete entity

For edge collections, additional routes as described earlier.

### 4. Registry Updates

The generator also:

- Updates `backend/routes/entities.py` to include the new router
- Updates `backend/schemas/__init__.py` with proper imports

## The Update Approach

The generator implements updates following the robust approach from the API Guide:

1. Retrieves the existing document
2. Creates a copy of the document and merges with the update data
3. Updates the timestamp with timezone-aware datetime
4. Removes system fields that shouldn't be modified
5. Ensures key consistency
6. Replaces the entire document atomically

This approach avoids issues with partial updates and null values, ensuring data integrity. By using the document's copy method and then updating, the code preserves data types and structure properly.

## Best Practices

1. **Schema Design**:
   - Use descriptive field names in snake_case
   - Always include field descriptions for documentation
   - Mark only truly required fields as `required`
   - Use appropriate data types and formats

2. **Uniqueness Constraints**:
   - Use `x-unique-combinations` for business-level uniqueness rules
   - Consider composite uniqueness for relationship data

3. **Search Fields**:
   - Add frequently queried fields to `x-search-fields`
   - Include a mix of text fields (for wildcard search) and boolean/numeric fields (for filtering)
   - Remember that string fields get wildcard search, while other types use exact matching

4. **Default Values**:
   - Use default values for fields that should have a consistent initial state
   - Boolean flags like `active` typically benefit from defaults
   - Timestamps can use functions like `datetime.now()` in the service layer

5. **Edge Collections**:
   - Name using connected entities (e.g., `player_team`)
   - Include descriptive information in edge documents

4. **Schema Updates**:
   - You can safely regenerate code - the script won't overwrite custom changes to routes/services
   - Consider versioning your schemas for API evolution

## Troubleshooting

### Common Issues

1. **Script errors about missing requirements**:
   - Ensure all `required` fields are defined in `properties`

2. **Uniqueness checks not working**:
   - Verify field names in `x-unique-combinations` match property names
   - Check database indexes were created (ArangoDB web UI)

3. **Edge collection traversal not working**:
   - Ensure the collection name follows the `entity1_entity2` convention
   - Verify the `_from` and `_to` fields point to valid documents

4. **Search filters not working as expected**:
   - Verify the field names in `x-search-fields` match the property names
   - Remember that string fields use wildcard search, other types use exact matching
   - Check if the generated query parameters are being passed correctly in API calls

5. **Default values not being applied**:
   - Make sure default values use the correct JSON format
   - For boolean values, use JSON `true`/`false` not strings
   - Check the schema property type matches the default value type

6. **Generated code not running**:
   - Check for import errors in the console
   - Verify Python 3.10+ compatibility (especially for type annotations)

### Extending the Generator

The generator is designed to be extendable. If you need custom logic:

1. Generate the basic API first
2. Add custom methods to the service classes
3. Add custom endpoints to the route files

## Extending the API with Custom Endpoints

Since re-running the generator will overwrite any custom changes to the generated files, here are recommended approaches for adding custom endpoints:

### 1. Create Separate Route Files

The safest approach is to create separate route files for your custom endpoints:

```python
# backend/routes/organization_custom_routes.py
from fastapi import APIRouter, Depends, HTTPException
from arango.database import Database

from ..schemas.organization import OrganizationResponse
from ..services.organization_service import OrganizationService
from ..db import get_db

custom_router = APIRouter(prefix="/organization-custom", tags=["Organization Custom"])

@custom_router.get("/active", response_model=list[OrganizationResponse])
async def get_active_organizations(
    db: Database = Depends(get_db)
):
    """Get only active organizations"""
    service = OrganizationService(db)
    # Custom logic here
    return result
```

Then register this router in `backend/routes/api_router.py`:

```python
from .organization_custom_routes import custom_router

# ...existing code...

api_router.include_router(custom_router)
```

### 2. Create Custom Service Classes

For custom business logic, extend the generated service class:

```python
# backend/services/organization_custom_service.py
from typing import List, Dict, Any
from .organization_service import OrganizationService

class OrganizationCustomService(OrganizationService):
    """Extended service with custom business logic"""
    
    async def get_active_organizations(self) -> List[Dict[str, Any]]:
        """Get only active organizations"""
        try:
            query = f"""
                FOR doc IN {self.collection_name}
                FILTER doc.active == true
                RETURN doc
            """
            result = self.db.aql.execute(query)
            return [doc for doc in result]
        except Exception as e:
            # Error handling
            pass
```

### 3. Add an Extension Module Pattern

For complex custom logic, use an extension module pattern:

```
backend/
  extensions/
    __init__.py
    organization/
      __init__.py
      routes.py      # Custom routes
      service.py     # Custom service methods
      schemas.py     # Custom schemas
```

This keeps all custom logic separate from generated code so it won't be affected by regeneration.

### 4. Use Extension Points in api_router.py

The main `api_router.py` file isn't generated by the script, so you can safely add custom endpoints there that use the generated services:

```python
from fastapi import APIRouter, Depends, Query
from .entities import entity_routers
from ..services.organization_service import OrganizationService
from ..db import get_db

api_router = APIRouter()

# Include all entity routers
for router in entity_routers:
    api_router.include_router(router)

# Custom endpoints that won't be overwritten
@api_router.get("/organizations/report", tags=["Reports"])
async def organization_report(
    db = Depends(get_db)
):
    """Custom report endpoint"""
    service = OrganizationService(db)
    # Custom reporting logic
    return {"result": "report data"}
```

By following these patterns, you can safely extend the generated API with custom endpoints without worrying about losing your work when you regenerate the basic CRUD endpoints.

## Conclusion

The basic CRUD API generator streamlines API development by generating consistent, well-structured code that follows best practices. By leveraging JSON Schema and custom extensions, you can rapidly build robust APIs for your VB Stat Logger application.
