# API Endpoint Creation Guide

This document provides a step-by-step guide for creating new CRUD API endpoints in a generic business application. There are two main approaches:

1. **Using the Generator Script** - For standard CRUD operations using the automated generator
2. **Manual Creation** - For custom endpoints that require specialized logic

This guide focuses on both approaches, explaining how to leverage the automated generator for rapid development while maintaining the flexibility to add custom functionality.

## Overview of Components

Each API endpoint consists of:

1. **Schema Definition** - Pydantic models that define data structure and validation
2. **Service Layer** - Business logic for database operations
3. **API Routes** - FastAPI endpoint definitions
4. **Tests** - Pytest files for endpoint testing

## Approach 1: Using the Generator Script

The quickest and most consistent way to create standard CRUD endpoints is to use the `generate_basic_crud_api_endpoints.py` script. This ensures all endpoints follow the same patterns and best practices.

### Step 1: Create a JSON Schema

Create a JSON schema file in the `/schemas` directory named `your_entity.schema.json`. Follow this format:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "Your Entity",
  "description": "Schema for Your Entity",
  "properties": {
    "_id": { "type": "string", "description": "ArangoDB document ID" },
    "_key": { "type": "string", "description": "ArangoDB document key" },
    "name": { 
      "type": "string", 
      "description": "Name of the entity" 
    },
    "description": { 
      "type": "string", 
      "description": "Description of the entity" 
    },
    "entity_date": { 
      "type": "string", 
      "format": "date",
      "description": "Important date for this entity" 
    },
    "active": {
      "type": "boolean",
      "default": true,
      "description": "Is the entity active"
    },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" }
  },
  "required": ["name"],
  
  "x-unique-combinations": [["name"]],
  "x-search-fields": ["name", "description", "entity_date", "active"]
}
```

Important notes:
- Use `snake_case` for all field names
- If using a field named "date", rename it to something more specific (like "entity_date") to avoid conflicts with Python's `date` type
- Use descriptive field names and include descriptions
- Add extensions like `x-unique-combinations` and `x-search-fields` for enhanced functionality

### Step 2: Run the Generator Script

Execute the generator script with your schema:

```bash
cd /home/jason/github/vb-stat-logger
poetry run python scripts/generate_basic_crud_api_endpoints.py schemas/your_entity.schema.json
```

This will create:
- `/backend/schemas/your_entity.py` - Pydantic models
- `/backend/services/your_entity_service.py` - Database operations
- `/backend/routes/your_entity_routes.py` - API endpoints
- Updates to entity registry and imports

### Step 3: Review Generated Schema Models

The generator creates multiple schema models in `/backend/schemas/your_entity.py`:

```python
class YourEntityBase(BaseModel):
    """Base schema for YourEntity."""
    # Properties from the schema, excluding ArangoDB internal fields
    name: str = Field(description="Name of the entity") 
    description: str = Field(default=None, description="Description of the entity")
    entity_date: date = Field(default=None, description="Important date for this entity")
    active: bool = Field(default=None, description="Is the entity active")

class YourEntityCreate(BaseModel):
    """Schema for creating a new YourEntity."""
    # Contains required fields from the schema
    name: str = Field(description="Name of the entity")
    # Other fields are optional

class YourEntityUpdate(BaseModel):
    """Schema for updating an existing YourEntity."""
    # All fields are optional for updates
    name: Optional[str] = Field(default=None, description="Name of the entity")
    description: Optional[str] = Field(default=None, description="Description of the entity")
    entity_date: Optional[date] = Field(default=None, description="Important date for this entity") 
    active: Optional[bool] = Field(default=None, description="Is the entity active")

class YourEntityInDB(BaseModel):
    """Complete YourEntity with DB fields."""
    # All fields from the schema, including transformed ArangoDB fields
    id: str = Field(alias="_id", description="ArangoDB document ID")
    key: str = Field(alias="_key", description="ArangoDB document key")
    name: str = Field(description="Name of the entity") 
    description: Optional[str] = Field(default=None, description="Description of the entity")
    entity_date: Optional[date] = Field(default=None, description="Important date for this entity") 
    active: Optional[bool] = Field(default=None, description="Is the entity active")
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    
    # Configuration for aliases
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": { "example": { ... } }
    }

class YourEntityResponse(YourEntityInDB):
    """API response model for YourEntity."""
    pass

class YourEntityDeleteResponse(BaseModel):
    """Response model for successful delete operations."""
    success: bool
```

For edge collections (like `player_team`), special handling is included for the `_from` and `_to` fields, transforming them to `from_id` and `to_id` for the API.

### Step 4: Review Generated Service Class

The generator creates a service class in `/backend/services/your_entity_service.py` with standardized methods:

```python
class YourEntityService:
    def __init__(self, db: Database):
        self.db = db
        self.collection_name = "your_entity"
        
        # Auto-creates collection and unique indexes if they don't exist
        if not self.db.has_collection(self.collection_name):
            self.db.create_collection(self.collection_name)
            
        # Create unique indexes from x-unique-combinations
        if "name_unique_idx" not in [idx["name"] for idx in self.db.collection(self.collection_name).indexes()]:
            self.db.collection(self.collection_name).add_persistent_index(
                fields=["name"], 
                unique=True,
                name="name_unique_idx"
            )
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new yourEntity with validation and default values."""
        # Check for unique combinations (from x-unique-combinations)
        existing_combination = self.db.aql.execute(
            f"""FOR doc IN {self.collection_name} 
                FILTER doc.name == @name 
                LIMIT 1 RETURN 1""",
            bind_vars={"name": data.get("name")}
        )
        
        if list(existing_combination):
            raise HTTPException(
                status_code=409, 
                detail=f"A yourEntity with this name already exists"
            )
            
        # Apply default values from schema
        defaults = {
            "active": True,
        }
        
        # Apply defaults for missing fields
        for field, value in defaults.items():
            if field not in data:
                data[field] = value
                
        # Add timestamps
        data["created_at"] = datetime.utcnow().isoformat()
        data["updated_at"] = data["created_at"]
        
        # Insert the document
        result = self.db.collection(self.collection_name).insert(data, return_new=True)
        return result["new"]
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all yourEntities with pagination."""
        query = f"FOR doc IN {self.collection_name} LIMIT {skip}, {limit} RETURN doc"
        result = self.db.aql.execute(query)
        return [doc for doc in result]
    
    async def get_filtered(self, filters: Dict[str, Any], skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get filtered yourEntities with smart text search and pagination."""
        # Build filter conditions
        conditions = []
        bind_vars = {}
        
        for field, value in filters.items():
            if value is not None:  # Skip None values
                # Determine field type based on schema
                field_type = "string"  # Default to string
                
                if field == "name":
                    field_type = "string"
                if field == "description":
                    field_type = "string"
                if field == "entity_date":
                    field_type = "string"
                if field == "active":
                    field_type = "boolean"
                
                # Use LIKE for string fields (case-insensitive wildcard search)
                if field_type == "string" and not field.endswith("_id"):
                    conditions.append(f"LOWER(doc.{field}) LIKE LOWER(@{field})")
                    bind_vars[field] = f"%{value}%"  # Add wildcards for partial matching
                else:
                    # Exact match for non-string fields and ID fields
                    conditions.append(f"doc.{field} == @{field}")
                    bind_vars[field] = value
        
        # Construct query
        filter_clause = " AND ".join(conditions) if conditions else "true"
        query = f"""
            FOR doc IN {self.collection_name}
            FILTER {filter_clause}
            LIMIT {skip}, {limit}
            RETURN doc
        """
        
        result = self.db.aql.execute(query, bind_vars=bind_vars)
        return [doc for doc in result]
    
    async def get_by_key(self, key: str) -> Dict[str, Any]:
        """Get a yourEntity by its key."""
        result = self.db.collection(self.collection_name).get({'_key': key})
        if not result:
            raise HTTPException(status_code=404, detail=f"YourEntity with key {key} not found")
        return result
    
    async def update(self, key: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a yourEntity by its key."""
        # Check if document exists
        existing_doc = self.db.collection(self.collection_name).get({'_key': key})
        if not existing_doc:
            raise HTTPException(status_code=404, detail=f"YourEntity with key {key} not found")
        
        # Create merged document with updated data
        updated_doc = existing_doc.copy()
        updated_doc.update(data)
        
        # Add updated timestamp
        updated_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Remove any fields that shouldn't be modified
        for field in ["_id", "_rev"]:
            if field in updated_doc:
                del updated_doc[field]
        
        # Make sure key stays consistent
        updated_doc["_key"] = key
        
        # Replace the document
        self.db.collection(self.collection_name).replace(updated_doc)
        return self.db.collection(self.collection_name).get(key)
    
    async def delete(self, key: str) -> bool:
        """Delete a yourEntity by its key."""
        # Check if document exists
        if not self.db.collection(self.collection_name).get({'_key': key}):
            raise HTTPException(status_code=404, detail=f"YourEntity with key {key} not found")
        
        # Delete the document
        self.db.collection(self.collection_name).delete(key)
        return True
```

For edge collections, additional methods are generated for retrieving edges by source and target entities.

### Step 5: Review Generated API Routes

The generator creates route handlers in `/backend/routes/your_entity_routes.py`:

```python
"""
API routes for YourEntity management.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from arango.database import Database

from ..schemas.your_entity import YourEntityInDB, YourEntityCreate, YourEntityUpdate, YourEntityResponse, YourEntityDeleteResponse
from ..services.your_entity_service import YourEntityService
from ..db import get_db

router = APIRouter(prefix="/your_entity", tags=["YourEntity"])

@router.post("/", response_model=YourEntityResponse, status_code=201)
async def create_your_entity(
    data: YourEntityCreate,
    db: Database = Depends(get_db)
):
    """Create a new yourEntity"""
    service = YourEntityService(db)
    result = await service.create(data.model_dump(exclude_unset=True))
    return result

@router.get("/", response_model=List[YourEntityResponse])
async def get_all_your_entitys(
    name: Optional[str] = Query(None, description="Filter by name (supports partial matching)"),
    description: Optional[str] = Query(None, description="Filter by description (supports partial matching)"),
    entity_date: Optional[str] = Query(None, description="Filter by entity_date"),
    active: Optional[bool] = Query(None, description="Filter by active"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Database = Depends(get_db)
):
    """Get all yourEntities with optional filtering and text search"""
    service = YourEntityService(db)
    
    # Check if any filters are applied
    filters = {
        "name": name,
        "description": description,
        "entity_date": entity_date,
        "active": active,
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    if filters:
        result = await service.get_filtered(filters, skip, limit)
    else:
        result = await service.get_all(skip, limit)
        
    return result

@router.get("/{key}", response_model=YourEntityResponse)
async def get_your_entity_by_key(
    key: str = Path(..., title="YourEntity key"),
    db: Database = Depends(get_db)
):
    """Get a yourEntity by its key"""
    service = YourEntityService(db)
    result = await service.get_by_key(key)
    return result

@router.patch("/{key}", response_model=YourEntityResponse)
async def update_your_entity(
    data: YourEntityUpdate,
    key: str = Path(..., title="YourEntity key"),
    db: Database = Depends(get_db)
):
    """Update a yourEntity by its key"""
    service = YourEntityService(db)
    result = await service.update(key, data.model_dump(exclude_unset=True))
    return result

@router.delete("/{key}", response_model=YourEntityDeleteResponse)
async def delete_your_entity(
    key: str = Path(..., title="YourEntity key"),
    db: Database = Depends(get_db)
):
    """Delete a yourEntity by its key"""
    service = YourEntityService(db)
    result = await service.delete(key)
    return {"success": result}
```

For edge collections, additional routes are generated for retrieving edges by the from and to entities.

### Step 6: Verify the API is Working

After running the generator, your new API endpoints will be automatically registered. Restart the FastAPI server to see them in the Swagger UI:

```bash
cd /home/jason/github/vb-stat-logger
poetry run uvicorn backend.main:app --reload
```

Visit `http://localhost:8000/docs` to see and test your new API endpoints.

## Approach 2: Manual Creation

While the generator handles most standard CRUD operations, you may need to create custom endpoints with specialized business logic. Here's how to create them manually:

### Step 1: Create Schema Definitions Manually

Create a new file in `/backend/schemas/{custom_entity}.py` for your custom schema:

```python
from datetime import date, datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field

class CustomEntityBase(BaseModel):
    """Base schema for CustomEntity data."""
    name: str = Field(..., description="Name of the custom entity")
    description: Optional[str] = Field(None, description="Description of the custom entity")
    
class CustomEntityCreate(CustomEntityBase):
    """Schema for creating a new CustomEntity."""
    # Add creation-specific fields
    
class CustomEntityUpdate(BaseModel):
    """Schema for updating an existing CustomEntity."""
    # All fields are optional for updates
    name: Optional[str] = Field(None, description="Name of the custom entity")
    description: Optional[str] = Field(None, description="Description of the custom entity")

class CustomEntityInDB(CustomEntityBase):
    """Schema for CustomEntity as stored in the database."""
    id: str = Field(alias="_id", description="ArangoDB document ID")
    key: str = Field(alias="_key", description="ArangoDB document key")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = {
        "populate_by_name": True
    }

class CustomEntityResponse(CustomEntityInDB):
    """Schema for CustomEntity response."""
    pass

class CustomEntityDeleteResponse(BaseModel):
    """Schema for CustomEntity deletion response."""
    success: bool
```
    ### Step 2: Create Custom Service Class

Create a service file in `/backend/services/{custom_entity}_service.py`:

```python
"""
Service for CustomEntity operations.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import uuid4
from fastapi import HTTPException
from loguru import logger
from arango.database import Database

class CustomEntityService:
    """Service for handling CustomEntity operations."""
    
    def __init__(self, db: Database):
        """Initialize with database connection."""
        self.db = db
        self.collection_name = "custom_entity"
        
        # Ensure collection exists
        if not self.db.has_collection(self.collection_name):
            self.db.create_collection(self.collection_name)
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new custom entity."""
        # Add timestamps
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        data["updated_at"] = data["created_at"]
        
        # Generate key if not provided
        if "_key" not in data:
            data["_key"] = str(uuid4())
        
        try:
            result = self.db.collection(self.collection_name).insert(data, return_new=True)
            return result["new"]
        except Exception as e:
            logger.error(f"Error creating custom entity: {e}")
            raise HTTPException(status_code=500, detail=f"Error creating custom entity: {str(e)}")
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all custom entities with pagination."""
        try:
            query = f"""
                FOR doc IN {self.collection_name}
                LIMIT {skip}, {limit}
                RETURN doc
            """
            result = self.db.aql.execute(query)
            return [doc for doc in result]
        except Exception as e:
            logger.error(f"Error fetching custom entities: {e}")
            raise HTTPException(status_code=500, detail=f"Error fetching custom entities: {str(e)}")
    
    async def get_by_key(self, key: str) -> Dict[str, Any]:
        """Get a custom entity by its key."""
        try:
            result = self.db.collection(self.collection_name).get({"_key": key})
            if not result:
                raise HTTPException(status_code=404, detail=f"Custom entity with key {key} not found")
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching custom entity: {e}")
            raise HTTPException(status_code=500, detail=f"Error fetching custom entity: {str(e)}")
    
    async def update(self, key: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a custom entity by its key."""
        try:
            # First get the existing document
            existing_doc = self.db.collection(self.collection_name).get({"_key": key})
            if not existing_doc:
                raise HTTPException(status_code=404, detail=f"Custom entity with key {key} not found")
            
            # Create a new document with updates
            updated_doc = existing_doc.copy()
            updated_doc.update(data)
            
            # Add updated timestamp
            updated_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Remove any fields that shouldn't be modified
            for field in ["_id", "_rev"]:
                if field in updated_doc:
                    del updated_doc[field]
            
            # Make sure key stays consistent
            updated_doc["_key"] = key
            
            # Replace the document
            self.db.collection(self.collection_name).replace(updated_doc)
            
            # Return the updated document
            return self.db.collection(self.collection_name).get(key)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating custom entity: {e}")
            raise HTTPException(status_code=500, detail=f"Error updating custom entity: {str(e)}")
    
    async def delete(self, key: str) -> bool:
        """Delete a custom entity by its key."""
        try:
            # Check if document exists
            if not self.db.collection(self.collection_name).get({"_key": key}):
                raise HTTPException(status_code=404, detail=f"Custom entity with key {key} not found")
            
            # Delete the document
            self.db.collection(self.collection_name).delete(key)
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting custom entity: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting custom entity: {str(e)}")
    
    # Custom business logic methods
    async def custom_operation(self, key: str, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Example of a custom business logic method."""
        try:
            # Get the entity
            entity = await self.get_by_key(key)
            
            # Perform custom operation
            # ... custom logic here ...
            
            # Update the entity with the result
            result = await self.update(key, {"custom_field": "custom value"})
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error performing custom operation: {e}")
            raise HTTPException(status_code=500, detail=f"Error performing custom operation: {str(e)}")
```

### Step 3: Create Custom API Routes

Create a new routes file in `/backend/routes/{custom_entity}_routes.py`:

```python
"""
API routes for CustomEntity operations.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path

from ..schemas.custom_entity import (
    CustomEntityCreate,
    CustomEntityUpdate,
    CustomEntityResponse,
    CustomEntityDeleteResponse
)
from ..services.custom_entity_service import CustomEntityService
from ..db import get_db

router = APIRouter(prefix="/custom-entity", tags=["CustomEntity"])

@router.post("/", response_model=CustomEntityResponse, status_code=201)
async def create_custom_entity(
    data: CustomEntityCreate,
    service: CustomEntityService = Depends(lambda: CustomEntityService(get_db()))
):
    """Create a new custom entity."""
    result = await service.create(data.model_dump(exclude_unset=True))
    return result

@router.get("/", response_model=List[CustomEntityResponse])
async def get_all_custom_entities(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    service: CustomEntityService = Depends(lambda: CustomEntityService(get_db()))
):
    """Get all custom entities with pagination."""
    return await service.get_all(skip, limit)

@router.get("/{key}", response_model=CustomEntityResponse)
async def get_custom_entity_by_key(
    key: str = Path(..., description="The custom entity's unique key"),
    service: CustomEntityService = Depends(lambda: CustomEntityService(get_db()))
):
    """Get a specific custom entity by key."""
    return await service.get_by_key(key)

@router.patch("/{key}", response_model=CustomEntityResponse)
async def update_custom_entity(
    key: str = Path(..., description="The custom entity's unique key"),
    data: CustomEntityUpdate = None,
    service: CustomEntityService = Depends(lambda: CustomEntityService(get_db()))
):
    """Update a custom entity."""
    if data is None:
        data = CustomEntityUpdate()
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    return await service.update(key, update_data)

@router.delete("/{key}", response_model=CustomEntityDeleteResponse)
async def delete_custom_entity(
    key: str = Path(..., description="The custom entity's unique key"),
    service: CustomEntityService = Depends(lambda: CustomEntityService(get_db()))
):
    """Delete a custom entity."""
    result = await service.delete(key)
    return {"success": result}

# Custom endpoint for specialized business logic
@router.post("/{key}/custom-operation", response_model=CustomEntityResponse)
async def perform_custom_operation(
    key: str = Path(..., description="The custom entity's unique key"),
    operation_data: Dict[str, Any] = None,
    service: CustomEntityService = Depends(lambda: CustomEntityService(get_db()))
):
    """Perform a custom operation on the entity."""
    if operation_data is None:
        operation_data = {}
    return await service.custom_operation(key, operation_data)
```

### Step 4: Update API Router

Update `/backend/routes/api_router.py` to include your new router:

```python
from fastapi import APIRouter
from .custom_entity_routes import router as custom_entity_router
# Import other routers...

api_router = APIRouter()

# Include your new router
api_router.include_router(custom_entity_router)
# Include other routers...
```

## Extending Generated Endpoints

Sometimes you want to keep the standard CRUD endpoints but add custom functionality. Here are some approaches for extending the generated endpoints without losing your custom code when regenerating:

### 1. Create Custom Route Files

Create a separate routes file for your custom endpoints that uses the same service:

```python
# backend/routes/your_entity_custom_routes.py
from fastapi import APIRouter, Depends, HTTPException, Path
from ..services.your_entity_service import YourEntityService
from ..db import get_db

custom_router = APIRouter(prefix="/your-entity-custom", tags=["YourEntity Custom"])

@custom_router.get("/active-count")
async def get_active_count(db = Depends(get_db)):
    """Get count of active entities (custom endpoint)."""
    service = YourEntityService(db)
    # Custom logic here
    return {"count": 42}
```

Then register this router in `api_router.py`.

### 2. Create Custom Service with Extended Functionality

Create a custom service that inherits from the generated service:

```python
# backend/services/your_entity_custom_service.py
from typing import Dict, List, Any
from .your_entity_service import YourEntityService

class YourEntityCustomService(YourEntityService):
    """Extended service with custom business logic."""
    
    async def get_active_count(self) -> int:
        """Get count of active entities."""
        query = f"""
            FOR doc IN {self.collection_name}
            FILTER doc.active == true
            COLLECT WITH COUNT INTO count
            RETURN count
        """
        result = self.db.aql.execute(query)
        return next(result)
```

Use this custom service in your route handlers.

### 3. Use the Main API Router for Custom Logic

Add custom endpoints directly in `api_router.py`, which isn't touched by the generator:

```python
# backend/routes/api_router.py
@api_router.get("/your-entity-stats", tags=["YourEntity"])
async def get_your_entity_stats(db = Depends(get_db)):
    """Get statistics about your entities."""
    service = YourEntityService(db)
    # Custom statistics logic
    return {"total": 100, "active": 75}
```

## Schema Extensions

The generator script supports several special schema extensions that provide enhanced functionality.

### 1. Unique Combinations (`x-unique-combinations`)

Specify combinations of fields that must be unique across all documents:

```json
"x-unique-combinations": [
  ["name"],                  // Single field uniqueness
  ["field1", "field2"]       // Multi-field uniqueness
]
```

The generator will:
- Create database indexes for each combination
- Add validation to prevent duplicates in the service
- Return appropriate HTTP 409 Conflict errors

### 2. Search Fields (`x-search-fields`)

Enable filtering capabilities for specific fields:

```json
"x-search-fields": [
  "name",
  "description",
  "category",
  "active"
]
```

This will:
- Add query parameters to the GET collection endpoint
- Implement smart text search (partial matching for strings, exact matching for other types)
- Add database query optimizations

### 3. Default Values

Use standard JSON Schema default values:

```json
"active": { 
  "type": "boolean", 
  "default": true,
  "description": "Is the entity active" 
}
```

These defaults are applied when creating records if the field isn't explicitly provided.

## Testing API Endpoints

### 1. Create Automated Tests

For generated endpoints, create test files to verify functionality:

```python
# backend/tests/test_your_entity.py
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from ..main import app

client = TestClient(app)

class TestYourEntityAPI:
    """Tests for YourEntity API endpoints."""
    
    entity_key = None  # Track created entity for later tests
    
    def test_create_entity(self):
        """Test creating a new entity."""
        test_data = {
            "name": "Test Entity",
            "description": "A test entity"
        }
        response = client.post("/your_entity/", json=test_data)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == test_data["name"]
        # Save key for later tests
        TestYourEntityAPI.entity_key = data["key"]
    
    def test_get_entity(self):
        """Test retrieving an entity."""
        assert TestYourEntityAPI.entity_key, "Entity key not found from creation test"
        response = client.get(f"/your_entity/{TestYourEntityAPI.entity_key}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Test Entity"
    
    def test_update_entity(self):
        """Test updating an entity."""
        assert TestYourEntityAPI.entity_key, "Entity key not found from creation test"
        update_data = {"name": "Updated Entity Name"}
        response = client.patch(f"/your_entity/{TestYourEntityAPI.entity_key}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == update_data["name"]
    
    def test_get_filtered_entities(self):
        """Test filtering entities."""
        response = client.get("/your_entity/?name=Updated")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "Updated" in data[0]["name"]
    
    def test_delete_entity(self):
        """Test deleting an entity."""
        assert TestYourEntityAPI.entity_key, "Entity key not found from creation test"
        response = client.delete(f"/your_entity/{TestYourEntityAPI.entity_key}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
```

### 2. Manual Testing with Swagger UI

FastAPI automatically generates Swagger UI documentation that you can use to test your endpoints:

1. Start the server: `poetry run uvicorn backend.main:app --reload`
2. Open `http://localhost:8000/docs` in your browser
3. Expand the endpoint you want to test
4. Click "Try it out"
5. Enter test data and click "Execute"

## Troubleshooting and Best Practices

### Common Issues

1. **Field name conflicts with Python keywords**: Avoid using Python reserved words (like `id`, `type`, `class`, `date`) as field names. If needed, use a more specific name (e.g., `entity_date`, `entity_type`).

2. **Date/time field handling**: Always use `datetime` with timezone awareness for timestamps:
   ```python
   from datetime import datetime, timezone
   timestamp = datetime.now(timezone.utc).isoformat()
   ```

3. **Key vs ID confusion**: Keep in mind the distinction between:
   - **_key**: The document key in ArangoDB (maps to `key` in API responses)
   - **_id**: The full document ID with collection prefix (maps to `id` in API responses)

### Best Practices

1. **Always regenerate all related files**: When changing a schema, regenerate all related files (schemas, services, routes) to ensure consistency.

2. **Apply uniqueness constraints in schema**: Define uniqueness through `x-unique-combinations` rather than enforcing it in code.

3. **Use descriptive field names**: Clear, descriptive field names make APIs more intuitive.

4. **Add search fields for common filtering needs**: The `x-search-fields` extension makes your API more powerful with minimal effort.

5. **Keep custom endpoints in separate files**: When extending with custom functionality, put it in separate files to avoid losing changes on regeneration.

## Conclusion

This project uses a combination of automated generation and custom development to create efficient, consistent APIs. The generator script handles the boilerplate CRUD operations, while custom endpoints provide specialized business logic.

For most simple entities, the generator script is the fastest way to create a fully functional API. For complex business logic, manual development or extensions provide the needed flexibility.

Remember to always test your API endpoints thoroughly and document any special behavior for other developers.
