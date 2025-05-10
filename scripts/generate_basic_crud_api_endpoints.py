#!/usr/bin/env python3
# filepath: /home/jason/github/vb-stat-logger/scripts/generate_crud_api.py
"""
CRUD API Generator
Generates route, service, and schema files from JSON schema definitions
"""
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


def snake_to_pascal(snake_str: str) -> str:
    """Convert snake_case to PascalCase"""
    return "".join(x.capitalize() for x in snake_str.split("_"))


def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    components = snake_str.split("_")
    return components[0] + "".join(x.capitalize() for x in components[1:])


def update_collection_config(
    collection_name, is_edge=False, from_collection=None, to_collection=None
):
    """Update the collections.json configuration file with the new collection."""
    config_path = (
        Path(__file__).parent.parent / "backend" / "config" / "collections.json"
    )
    config_dir = config_path.parent

    # Create config directory if it doesn't exist
    config_dir.mkdir(exist_ok=True)

    # Initialize default config
    config = {"document_collections": [], "edge_collections": [], "graph_edges": []}

    # Load existing config if it exists
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Error parsing {config_path}, using defaults")

    # Update config with the new collection
    if is_edge:
        if collection_name not in config["edge_collections"]:
            config["edge_collections"].append(collection_name)

        # Handle graph edge definition
        if from_collection and to_collection:
            # Handle pluralization for collections ending in 'y'
            from_coll = (
                from_collection[:-1] + "ies"
                if from_collection.endswith("y")
                else from_collection + "s"
            )
            to_coll = (
                to_collection[:-1] + "ies"
                if to_collection.endswith("y")
                else to_collection + "s"
            )

            # Check if this edge definition already exists
            edge_exists = False
            for edge in config["graph_edges"]:
                if edge["edge_collection"] == collection_name:
                    edge_exists = True
                    break

            if not edge_exists:
                config["graph_edges"].append(
                    {
                        "edge_collection": collection_name,
                        "from_collections": [from_coll],
                        "to_collections": [to_coll],
                    }
                )
    else:
        # Handle pluralization for collections ending in 'y'
        coll_plural = (
            collection_name[:-1] + "ies"
            if collection_name.endswith("y")
            else collection_name + "s"
        )
        if coll_plural not in config["document_collections"]:
            config["document_collections"].append(coll_plural)

    # Write the updated config back to the file
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    logger.info(f"Updated collection configuration in {config_path}")


def parse_schema(schema_path: str) -> Dict[str, Any]:
    """Parse JSON schema file and extract relevant information"""
    with open(schema_path, "r") as f:
        schema = json.load(f)

    # Extract entity name from filename
    filename = os.path.basename(schema_path)
    entity_name = filename.replace(".schema.json", "")

    # Determine if this is an edge collection
    is_edge = "_from" in schema.get("properties", {}) and "_to" in schema.get(
        "properties", {}
    )

    # If it's an edge, extract the entities it connects
    connected_entities = []
    if is_edge and "_" in entity_name:
        parts = entity_name.split("_")
        connected_entities = [parts[0], parts[1]]

    # Extract unique combinations
    unique_combinations = schema.get("x-unique-combinations", [])

    # Extract search fields with their types for smart filtering
    search_fields = schema.get("x-search-fields", [])
    search_field_types = {}

    for field in search_fields:
        if field in schema.get("properties", {}):
            field_type = schema["properties"][field].get("type", "string")
            search_field_types[field] = field_type

    return {
        "entity_name": entity_name,
        "pascal_name": snake_to_pascal(entity_name),
        "camel_name": snake_to_camel(entity_name),
        "is_edge": is_edge,
        "connected_entities": connected_entities,
        "required_fields": schema.get("required", []),
        "properties": schema.get("properties", {}),
        "title": schema.get("title", ""),
        "description": schema.get("description", ""),
        "unique_combinations": unique_combinations,
        "search_fields": search_fields,
        "search_field_types": search_field_types,
    }


def generate_schema_file(entity_info: Dict[str, Any], output_dir: str) -> None:
    """Generate Pydantic schema file"""
    entity_name = entity_info["entity_name"]
    pascal_name = entity_info["pascal_name"]
    properties = entity_info["properties"]
    required = entity_info["required_fields"]
    is_edge = entity_info["is_edge"]

    # Map JSON schema types to Python types
    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "List[Any]",
        "object": "Dict[str, Any]",
    }

    # Special formats
    format_mapping = {"date-time": "datetime", "date": "date"}

    template = f"""\"\"\"
Pydantic schemas for {pascal_name} entity.
\"\"\"
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class {pascal_name}Base(BaseModel):
    \"\"\"Base schema for {pascal_name}\"\"\"
"""

    # Add fields from properties
    for prop_name, prop_info in properties.items():
        # Skip internal fields for the base model
        if prop_name.startswith("_"):
            continue

        prop_type = type_mapping.get(prop_info.get("type", "string"), "Any")

        # Handle formats like date-time
        if "format" in prop_info:
            prop_type = format_mapping.get(prop_info["format"], prop_type)

        # Make optional if not required
        is_optional = prop_name not in required
        type_str = f"Optional[{prop_type}]" if is_optional else prop_type

        # Add field description if available
        desc = prop_info.get("description", "")

        # FIX: Handle optional fields with Field() attributes properly
        if is_optional:
            if desc:
                template += f'    {prop_name}: {prop_type} = Field(default=None, description="{desc}")\n'
            else:
                template += f"    {prop_name}: {prop_type} = None\n"
        else:
            if desc:
                template += (
                    f'    {prop_name}: {prop_type} = Field(description="{desc}")\n'
                )
            else:
                template += f"    {prop_name}: {prop_type}\n"

    # Create schema
    template += f"""

class {pascal_name}Create(BaseModel):
    \"\"\"Schema for creating a new {pascal_name}\"\"\"
"""

    # For edge collections, we need _from and _to as special fields
    if is_edge:
        # Add the edge fields with aliases
        from_desc = properties.get("_from", {}).get(
            "description", "Source document handle"
        )
        to_desc = properties.get("_to", {}).get("description", "Target document handle")

        template += f"""    from_id: str = Field(..., alias="_from", description="{from_desc}")
    to_id: str = Field(..., alias="_to", description="{to_desc}")
"""

    # Add required fields for creation
    for prop_name in required:
        # Skip _id, _key and already handled edge fields
        if prop_name.startswith("_") and prop_name not in ["_from", "_to"]:
            continue

        # Skip _from and _to if we already added them for edge collections
        if is_edge and prop_name in ["_from", "_to"]:
            continue

        prop_info = properties.get(prop_name, {})
        prop_type = type_mapping.get(prop_info.get("type", "string"), "Any")

        # Handle formats like date-time
        if "format" in prop_info:
            prop_type = format_mapping.get(prop_info["format"], prop_type)

        # Add field description if available
        desc = prop_info.get("description", "")
        if desc:
            template += f'    {prop_name}: {prop_type} = Field(description="{desc}")\n'
        else:
            template += f"    {prop_name}: {prop_type}\n"

    # Add model_config for aliases
    if is_edge:
        template += """
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "from_id": "collection/123",
                "to_id": "collection/456"
            }
        }
    }
"""

    # Update schema with all fields optional
    template += f"""

class {pascal_name}Update(BaseModel):
    \"\"\"Schema for updating an existing {pascal_name}\"\"\"
"""

    for prop_name, prop_info in properties.items():
        # Skip internal fields for updates
        if prop_name.startswith("_"):
            continue

        prop_type = type_mapping.get(prop_info.get("type", "string"), "Any")

        # Handle formats like date-time
        if "format" in prop_info:
            prop_type = format_mapping.get(prop_info["format"], prop_type)

        # All fields are optional for updates
        type_str = f"Optional[{prop_type}]"

        # Add field description if available
        desc = prop_info.get("description", "")
        if desc:
            template += f'    {prop_name}: {type_str} = Field(default=None, description="{desc}")\n'
        else:
            template += f"    {prop_name}: {type_str} = None\n"

    # Full response model
    template += f"""

class {pascal_name}InDB(BaseModel):
    \"\"\"Complete {pascal_name} with DB fields\"\"\"
"""

    # Add all fields to the response model, with aliases for underscore fields
    for prop_name, prop_info in properties.items():
        prop_type = type_mapping.get(prop_info.get("type", "string"), "Any")

        # Handle formats like date-time
        if "format" in prop_info:
            prop_type = format_mapping.get(prop_info["format"], prop_type)

        # Make optional if not required
        is_optional = prop_name not in required
        type_str = f"Optional[{prop_type}]" if is_optional else prop_type

        # Handle underscore fields
        if prop_name.startswith("_"):
            # Convert _id to id, _key to key, _from to from_id, _to to to_id
            field_name = prop_name[1:]
            if prop_name in ["_from", "_to"]:
                field_name = f"{field_name}_id"

            desc = prop_info.get("description", "")

            if is_optional:
                template += f'    {field_name}: {type_str} = Field(default=None, alias="{prop_name}"'
            else:
                template += f'    {field_name}: {type_str} = Field(alias="{prop_name}"'

            if desc:
                template += f', description="{desc}"'
            template += ")\n"
        else:
            # Regular fields
            desc = prop_info.get("description", "")

            # FIX: Handle optional fields with Field() attributes properly
            if is_optional:
                if desc:
                    template += f'    {prop_name}: {prop_type} = Field(default=None, description="{desc}")\n'
                else:
                    template += f"    {prop_name}: {prop_type} = None\n"
            else:
                if desc:
                    template += (
                        f'    {prop_name}: {prop_type} = Field(description="{desc}")\n'
                    )
                else:
                    template += f"    {prop_name}: {prop_type}\n"

    # Add model_config for using aliases in response model
    template += """
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
"""

    # Add a simple example for visualization in Swagger
    example = {}
    if "id" in template:
        example["id"] = f"{entity_name}/123456"
    if "key" in template:
        example["key"] = "123456"
    if is_edge:
        example["from_id"] = "collection/123"
        example["to_id"] = "collection/456"

    # Add some example values for regular fields
    for prop_name, prop_info in properties.items():
        if not prop_name.startswith("_"):
            if prop_info.get("type") == "string":
                example[prop_name] = "Example value"
            elif prop_info.get("type") == "integer":
                example[prop_name] = 42
            elif prop_info.get("type") == "number":
                example[prop_name] = 3.14
            elif prop_info.get("type") == "boolean":
                example[prop_name] = True

    # Add the example to the template
    for key, value in example.items():
        if isinstance(value, str):
            template += f'                "{key}": "{value}",\n'
        else:
            template += f'                "{key}": {value},\n'

    # Close the example configuration
    template = template.rstrip(",\n") + "\n"
    template += """            }
        }
    }
"""

    # Add response models needed by routes
    template += f"""

class {pascal_name}Response({pascal_name}InDB):
    \"\"\"API response model for {pascal_name}\"\"\"
    pass

class {pascal_name}DeleteResponse(BaseModel):
    \"\"\"Response model for successful delete operations\"\"\"
    success: bool
"""

    # Write to file
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{entity_name}.py")
    with open(output_path, "w") as f:
        f.write(template)

    print(f"Generated schema file: {output_path}")


def generate_service_file(entity_info: Dict[str, Any], output_dir: str) -> None:
    """Generate service class file with uniqueness constraints"""
    entity_name = entity_info["entity_name"]
    pascal_name = entity_info["pascal_name"]
    camel_name = entity_info["camel_name"]
    is_edge = entity_info["is_edge"]

    # Get unique combinations for composite indexes
    unique_combinations = entity_info.get("unique_combinations", [])

    # For edge collection, determine the connected entities
    edge_methods = ""
    if is_edge and len(entity_info["connected_entities"]) == 2:
        from_entity, to_entity = entity_info["connected_entities"]
        from_pascal = snake_to_pascal(from_entity)
        to_pascal = snake_to_pascal(to_entity)

        edge_methods = f"""
    async def get_by_from_to(self, from_key: str, to_key: str) -> List[Dict[str, Any]]:
        \"\"\"Get edges between specific {from_entity} and {to_entity}\"\"\"
        try:
            from_id = f"{from_entity}/{{from_key}}"
            to_id = f"{to_entity}/{{to_key}}"
            
            query = f\"\"\"
                FOR edge IN {{self.collection_name}}
                FILTER edge._from == @from_id AND edge._to == @to_id
                RETURN edge
            \"\"\"
            
            result = self.db.aql.execute(
                query, 
                bind_vars={{"from_id": from_id, "to_id": to_id}}
            )
            
            return [doc for doc in result]
        except Exception as e:
            logger.error(f"Error fetching {camel_name} by from/to: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error fetching {camel_name}: {{str(e)}}")
    
    async def get_by_from(self, from_key: str) -> List[Dict[str, Any]]:
        \"\"\"Get all edges from a specific {from_entity}\"\"\"
        try:
            from_id = f"{from_entity}/{{from_key}}"
            
            query = f\"\"\"
                FOR edge IN {{self.collection_name}}
                FILTER edge._from == @from_id
                RETURN edge
            \"\"\"
            
            result = self.db.aql.execute(
                query, 
                bind_vars={{"from_id": from_id}}
            )
            
            return [doc for doc in result]
        except Exception as e:
            logger.error(f"Error fetching {camel_name} by from: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error fetching {camel_name}: {{str(e)}}")
    
    async def get_by_to(self, to_key: str) -> List[Dict[str, Any]]:
        \"\"\"Get all edges to a specific {to_entity}\"\"\"
        try:
            to_id = f"{to_entity}/{{to_key}}"
            
            query = f\"\"\"
                FOR edge IN {{self.collection_name}}
                FILTER edge._to == @to_id
                RETURN edge
            \"\"\"
            
            result = self.db.aql.execute(
                query, 
                bind_vars={{"to_id": to_id}}
            )
            
            return [doc for doc in result]
        except Exception as e:
            logger.error(f"Error fetching {camel_name} by to: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error fetching {camel_name}: {{str(e)}}")
"""

    # Prepare index creation code for unique combinations
    index_code = ""
    if unique_combinations:
        index_code = "\n        # Create unique composite indexes\n"
        for fields in unique_combinations:
            index_name = f"{'_'.join(fields)}_unique_idx"
            fields_str = ", ".join([f'"{field}"' for field in fields])

            index_code += f"""        if "{index_name}" not in [idx["name"] for idx in self.db.collection(self.collection_name).indexes()]:
            self.db.collection(self.collection_name).add_persistent_index(
                fields=[{fields_str}], 
                unique=True,
                name="{index_name}"
            )\n"""

    # Prepare validation code for unique combinations
    validation_code = ""
    if unique_combinations:
        validation_code = "\n        # Check for unique combinations\n"
        for fields in unique_combinations:
            # Build AQL filter conditions for each field in the combination
            filter_conditions = []
            bind_vars = []
            field_names = []

            for field in fields:
                filter_conditions.append(f"doc.{field} == @{field}")
                bind_vars.append(f'"{field}": data.get("{field}")')
                field_names.append(field)

            # Join the field conditions with AND
            field_conditions = " AND ".join(filter_conditions)
            bind_vars_str = ", ".join(bind_vars)
            field_names_str = ", ".join(field_names)

            validation_code += f"""        # Check for existing {field_names_str} combination
        existing_combination = self.db.aql.execute(
            f\"\"\"FOR doc IN {{self.collection_name}} 
                FILTER {field_conditions} 
                LIMIT 1 RETURN 1\"\"\",
            bind_vars={{{bind_vars_str}}}
        )
        
        if list(existing_combination):
            raise HTTPException(
                status_code=409, 
                detail=f"A {camel_name} with this {field_names_str} combination already exists"
            )
            
"""

    # Add this code to the create method in the service template
    validation_code += """
        # Apply default values
        defaults = {
"""

    # Add default values from schema
    for field, prop in entity_info.get("properties", {}).items():
        if "default" in prop:
            # Convert JSON booleans to Python booleans
            if prop["default"] is True:
                default_value = "True"
            elif prop["default"] is False:
                default_value = "False"
            else:
                default_value = json.dumps(
                    prop["default"]
                )  # Properly format other values
            validation_code += f'            "{field}": {default_value},\n'

    # Add defaults from custom extension if it exists
    for field, value in entity_info.get("x-default-values", {}).items():
        # Convert JSON booleans to Python booleans
        if value is True:
            default_value = "True"
        elif value is False:
            default_value = "False"
        else:
            default_value = json.dumps(value)  # Properly format other values
        validation_code += f'            "{field}": {default_value},\n'

    validation_code += """
        }
        
        # Apply defaults for missing fields
        for field, value in defaults.items():
            if field not in data:
                data[field] = value
"""

    # Get search fields with their types
    search_fields = entity_info.get("search_fields", [])
    search_field_types = entity_info.get("search_field_types", {})

    # Prepare filtered query method if search fields exist
    filtered_query_method = ""
    if search_fields:
        # Build field type checks for each search field
        field_type_checks = ""
        for field in search_fields:
            field_type = search_field_types.get(field, "string")
            field_type_checks += f'                    if field == "{field}":\n'
            field_type_checks += (
                f'                        field_type = "{field_type}"\n'
            )

        filtered_query_method = f"""
    async def get_filtered(self, filters: Dict[str, Any], skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        \"\"\"Get filtered {camel_name}s with smart text search and pagination\"\"\"
        try:
            # Build filter conditions
            conditions = []
            bind_vars = {{}}
            
            for field, value in filters.items():
                if value is not None:  # Skip None values
                    # Determine field type based on schema
                    field_type = "string"  # Default to string
{field_type_checks}
                    
                    # Use LIKE for string fields (case-insensitive wildcard search)
                    if field_type == "string" and not field.endswith("_id"):
                        conditions.append(f"LOWER(doc.{{field}}) LIKE LOWER(@{{field}})")
                        bind_vars[field] = f"%{{value}}%"  # Add wildcards for partial matching
                    else:
                        # Exact match for non-string fields and ID fields
                        conditions.append(f"doc.{{field}} == @{{field}}")
                        bind_vars[field] = value
            
            # Construct query
            filter_clause = " AND ".join(conditions) if conditions else "true"
            query = f\"\"\"
                FOR doc IN {{self.collection_name}}
                FILTER {{filter_clause}}
                LIMIT {{skip}}, {{limit}}
                RETURN doc
            \"\"\"
            
            result = self.db.aql.execute(query, bind_vars=bind_vars)
            return [doc for doc in result]
        except Exception as e:
            logger.error(f"Error fetching filtered {camel_name}s: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error fetching {camel_name}s: {{str(e)}}")
"""

    # Basic service template
    template = f"""\"\"\"
Service for {pascal_name} operations.
\"\"\"
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from arango.database import Database
from fastapi import HTTPException
from loguru import logger

class {pascal_name}Service:
    def __init__(self, db: Database):
        self.db = db
        self.collection_name = "{entity_name}"
        
        # Ensure collection exists
        if not self.db.has_collection(self.collection_name):
            self.db.create_collection(
                self.collection_name, 
                edge={"True" if is_edge else "False"}
            ){index_code}
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Create a new {camel_name}\"\"\"
{validation_code}
        # Add timestamps
        data["created_at"] = datetime.utcnow().isoformat()
        data["updated_at"] = data["created_at"]
        
        try:
            result = self.db.collection(self.collection_name).insert(data, return_new=True)
            return result["new"]
        except Exception as e:
            logger.error(f"Error creating {camel_name}: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error creating {camel_name}: {{str(e)}}")
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        \"\"\"Get all {camel_name}s with pagination\"\"\"
        try:
            query = f"FOR doc IN {{self.collection_name}} LIMIT {{skip}}, {{limit}} RETURN doc"
            result = self.db.aql.execute(query)
            return [doc for doc in result]
        except Exception as e:
            logger.error(f"Error fetching {camel_name}s: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error fetching {camel_name}s: {{str(e)}}")
    
    async def get_by_key(self, key: str) -> Dict[str, Any]:
        \"\"\"Get a {camel_name} by its key\"\"\"
        try:
            result = self.db.collection(self.collection_name).get({{'_key': key}})
            if not result:
                raise HTTPException(status_code=404, detail=f"{pascal_name} with key {{key}} not found")
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching {camel_name} by key: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error fetching {camel_name}: {{str(e)}}")
    
    async def update(self, key: str, data: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Update a {camel_name} by its key\"\"\"
        try:
            # Check if document exists
            existing_doc = self.db.collection(self.collection_name).get({{'_key': key}})
            if not existing_doc:
                raise HTTPException(status_code=404, detail=f"{pascal_name} with key {{key}} not found")
            
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
            
            # Replace the document with the updated version
            result = self.db.collection(self.collection_name).replace(updated_doc, return_new=True)
            return result["new"]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating {camel_name}: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error updating {camel_name}: {{str(e)}}")
    
    async def delete(self, key: str) -> bool:
        \"\"\"Delete a {camel_name} by its key\"\"\"
        try:
            # Check if document exists
            existing = self.db.collection(self.collection_name).get({{'_key': key}})
            if not existing:
                raise HTTPException(status_code=404, detail=f"{pascal_name} with key {{key}} not found")
            
            # Delete the document
            self.db.collection(self.collection_name).delete({{'_key': key}})
            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting {camel_name}: {{e}}")
            raise HTTPException(status_code=500, detail=f"Error deleting {camel_name}: {{str(e)}}")
{edge_methods}{filtered_query_method}"""

    # Write to file
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{entity_name}_service.py")
    with open(output_path, "w") as f:
        f.write(template)

    print(f"Generated service file: {output_path}")


def generate_routes_file(entity_info: Dict[str, Any], output_dir: str) -> None:
    """Generate routes file with API endpoints"""
    entity_name = entity_info["entity_name"]
    pascal_name = entity_info["pascal_name"]
    camel_name = entity_info["camel_name"]
    is_edge = entity_info["is_edge"]

    # Get search fields with types
    search_fields = entity_info.get("search_fields", [])
    search_field_types = entity_info.get("search_field_types", {})
    properties = entity_info.get("properties", {})

    # Build query parameters for search fields
    query_params = ""
    filter_params_dict = ""

    if search_fields:
        # Create query parameters for each search field
        for field in search_fields:
            if field in properties:
                prop_info = properties[field]
                field_type = prop_info.get("type", "string")

                # Map JSON types to Python types
                type_map = {
                    "string": "str",
                    "integer": "int",
                    "number": "float",
                    "boolean": "bool",
                }
                py_type = type_map.get(field_type, "str")

                # Get description if available
                desc = prop_info.get("description", f"Filter by {field}")
                if field_type == "string" and not field.endswith("_id"):
                    desc += " (supports partial matching)"

                # Add the query parameter
                query_params += f"""    {field}: Optional[{py_type}] = Query(None, description="{desc}"),\n"""

                # Add to filter params dictionary
                filter_params_dict += f'        "{field}": {field},\n'

    # Edge-specific routes
    edge_routes = ""
    if is_edge and len(entity_info["connected_entities"]) == 2:
        from_entity, to_entity = entity_info["connected_entities"]
        from_pascal = snake_to_pascal(from_entity)
        to_pascal = snake_to_pascal(to_entity)

        edge_routes = f"""
@router.get("/{from_entity}/{{from_key}}/{to_entity}/{{to_key}}", response_model=List[{pascal_name}Response])
async def get_{entity_name}_by_from_to(
    from_key: str = Path(..., title="{from_pascal} key"),
    to_key: str = Path(..., title="{to_pascal} key"),
    db: Database = Depends(get_db)
):
    \"\"\"Get {camel_name} edges between a specific {from_entity} and {to_entity}\"\"\"
    service = {pascal_name}Service(db)
    result = await service.get_by_from_to(from_key, to_key)
    return result

@router.get("/{from_entity}/{{from_key}}", response_model=List[{pascal_name}Response])
async def get_{entity_name}_by_from(
    from_key: str = Path(..., title="{from_pascal} key"),
    db: Database = Depends(get_db)
):
    \"\"\"Get all {camel_name} edges from a specific {from_entity}\"\"\"
    service = {pascal_name}Service(db)
    result = await service.get_by_from(from_key)
    return result

@router.get("/{to_entity}/{{to_key}}", response_model=List[{pascal_name}Response])
async def get_{entity_name}_by_to(
    to_key: str = Path(..., title="{to_pascal} key"),
    db: Database = Depends(get_db)
):
    \"\"\"Get all {camel_name} edges to a specific {to_entity}\"\"\"
    service = {pascal_name}Service(db)
    result = await service.get_by_to(to_key)
    return result
"""

    # Build the complete template by parts to avoid syntax errors
    template_parts = []

    # Header section
    template_parts.append(
        f"""\"\"\"
API routes for {camel_name} management.
\"\"\"
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from arango.database import Database

from ..schemas.{entity_name} import {pascal_name}InDB, {pascal_name}Create, {pascal_name}Update, {pascal_name}Response, {pascal_name}DeleteResponse
from ..services.{entity_name}_service import {pascal_name}Service
from ..db import get_db

router = APIRouter(prefix="/{entity_name}", tags=["{pascal_name}"])

@router.post("/", response_model={pascal_name}Response, status_code=201)
async def create_{entity_name}(
    data: {pascal_name}Create,
    db: Database = Depends(get_db)
):
    \"\"\"Create a new {camel_name}\"\"\"
    service = {pascal_name}Service(db)
    result = await service.create(data.model_dump(exclude_unset=True))
    return result
"""
    )

    # Get all endpoint with or without search
    if search_fields:
        template_parts.append(
            f"""
@router.get("/", response_model=List[{pascal_name}Response])
async def get_all_{entity_name}s(
{query_params}    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Database = Depends(get_db)
):
    \"\"\"Get all {camel_name}s with optional filtering and text search\"\"\"
    service = {pascal_name}Service(db)
    
    # Check if any filters are applied
    filters = {{
{filter_params_dict}    }}
    
    # Remove None values
    filters = {{k: v for k, v in filters.items() if v is not None}}
    
    if filters:
        result = await service.get_filtered(filters, skip, limit)
    else:
        result = await service.get_all(skip, limit)
        
    return result
"""
        )
    else:
        template_parts.append(
            f"""
@router.get("/", response_model=List[{pascal_name}Response])
async def get_all_{entity_name}s(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Database = Depends(get_db)
):
    \"\"\"Get all {camel_name}s with pagination\"\"\"
    service = {pascal_name}Service(db)
    result = await service.get_all(skip, limit)
    return result
"""
        )

    # CRUD endpoints
    template_parts.append(
        f"""
@router.get("/{{key}}", response_model={pascal_name}Response)
async def get_{entity_name}_by_key(
    key: str = Path(..., title="{pascal_name} key"),
    db: Database = Depends(get_db)
):
    \"\"\"Get a {camel_name} by its key\"\"\"
    service = {pascal_name}Service(db)
    result = await service.get_by_key(key)
    return result

@router.patch("/{{key}}", response_model={pascal_name}Response)
async def update_{entity_name}(
    data: {pascal_name}Update,
    key: str = Path(..., title="{pascal_name} key"),
    db: Database = Depends(get_db)
):
    \"\"\"Update a {camel_name} by its key\"\"\"
    service = {pascal_name}Service(db)
    result = await service.update(key, data.model_dump(exclude_unset=True))
    return result

@router.delete("/{{key}}", response_model={pascal_name}DeleteResponse)
async def delete_{entity_name}(
    key: str = Path(..., title="{pascal_name} key"),
    db: Database = Depends(get_db)
):
    \"\"\"Delete a {camel_name} by its key\"\"\"
    service = {pascal_name}Service(db)
    result = await service.delete(key)
    return {{"success": result}}
"""
    )

    # Edge-specific routes
    if edge_routes:
        template_parts.append(edge_routes)

    # Combine all parts into final template
    template = "".join(template_parts)

    # Write to file
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{entity_name}_routes.py")
    with open(output_path, "w") as f:
        f.write(template)

    print(f"Generated routes file: {output_path}")


def update_entity_registry(entity_name: str) -> None:
    """Update the entity registry file and schema imports with the new entity"""
    pascal_name = snake_to_pascal(entity_name)

    # Build paths with absolute references
    project_root = Path(__file__).parent.parent
    entity_registry_path = project_root / "backend" / "routes" / "entities.py"
    schemas_init_path = project_root / "backend" / "schemas" / "__init__.py"

    print(f"Updating entity registry at: {entity_registry_path}")
    print(f"Updating schemas __init__ at: {schemas_init_path}")

    # 1. Update Router Registry
    if not entity_registry_path.exists():
        with open(entity_registry_path, "w") as f:
            f.write(
                '''"""
Entity router registry - automatically updated by the generator script.
"""
from fastapi import APIRouter

# Import all entity routers
# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE

# Create a list of all routers to be included
entity_routers = [
    # AUTO-GENERATED ROUTERS - DO NOT REMOVE THIS LINE
]
'''
            )

    # Read the current content
    with open(entity_registry_path, "r") as f:
        content = f.read()

    # Add import statement
    import_line = f"from .{entity_name}_routes import router as {entity_name}_router"
    if import_line not in content:  # Avoid duplicates
        content = content.replace(
            "# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
            f"{import_line}\n# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
        )

    # Add router to list
    router_line = f"    {entity_name}_router,"
    router_pattern = rf"\b{entity_name}_router\b"

    # Check if this router is already listed by looking for its name specifically
    router_already_exists = False
    if "entity_routers = [" in content:
        router_already_exists = re.search(
            router_pattern, content.split("entity_routers = [")[1].split("]")[0]
        )

    if not router_already_exists:  # Only add if not already in the list
        content = content.replace(
            "    # AUTO-GENERATED ROUTERS - DO NOT REMOVE THIS LINE",
            f"{router_line}\n    # AUTO-GENERATED ROUTERS - DO NOT REMOVE THIS LINE",
        )

    # Write the updated content
    with open(entity_registry_path, "w") as f:
        f.write(content)

    print(f"Updated entity registry with {entity_name}_router")

    # 2. Update Schema Imports
    if not schemas_init_path.exists():
        with open(schemas_init_path, "w") as f:
            f.write(
                '''"""Schemas package for VB Stat Logger API."""

# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE

__all__ = [
    # AUTO-GENERATED MODELS - DO NOT REMOVE THIS LINE
]
'''
            )

    # Read the current content
    with open(schemas_init_path, "r") as f:
        init_content = f.read()

    # Check for marker comments
    if "# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE" not in init_content:
        print("Adding marker comments to schemas/__init__.py")
        init_content = (
            '''"""Schemas package for VB Stat Logger API."""

# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE
'''
            + init_content
        )

    if "__all__ = [" not in init_content:
        print("Adding __all__ list to schemas/__init__.py")
        init_content += """

__all__ = [
    # AUTO-GENERATED MODELS - DO NOT REMOVE THIS LINE
]
"""

    # Add import statement
    import_block = f"""from .{entity_name} import (
    {pascal_name}Base,
    {pascal_name}Create,
    {pascal_name}Update,
    {pascal_name}InDB,
    {pascal_name}Response,
    {pascal_name}DeleteResponse,
)"""

    if f"from .{entity_name} import" not in init_content:  # Avoid duplicates
        init_content = init_content.replace(
            "# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
            f"{import_block}\n\n# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
        )

    # Add to __all__
    models_block = f"""    "{pascal_name}Base",
    "{pascal_name}Create",
    "{pascal_name}Update",
    "{pascal_name}InDB",
    "{pascal_name}Response",
    "{pascal_name}DeleteResponse","""

    if f'"{pascal_name}Base"' not in init_content:  # Avoid duplicates
        init_content = init_content.replace(
            "    # AUTO-GENERATED MODELS - DO NOT REMOVE THIS LINE",
            f"{models_block}\n    # AUTO-GENERATED MODELS - DO NOT REMOVE THIS LINE",
        )

    # Write the updated content
    with open(schemas_init_path, "w") as f:
        f.write(init_content)

    print(f"Updated schema imports with {pascal_name} models")


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_crud_api.py path/to/schema.json")
        print("   OR: python generate_crud_api.py --all path/to/schemas/dir")
        sys.exit(1)

    # Define output directories
    backend_dir = Path("./backend")
    schemas_dir = backend_dir / "schemas"
    services_dir = backend_dir / "services"
    routes_dir = backend_dir / "routes"

    # Check if we're processing all schemas
    if sys.argv[1] == "--all":
        if len(sys.argv) < 3:
            schemas_dir_path = "./schemas"  # Default schemas directory
            print(f"No directory specified, using default: {schemas_dir_path}")
        else:
            schemas_dir_path = sys.argv[2]

        # Find all schema files
        schema_files = glob.glob(f"{schemas_dir_path}/*.schema.json")

        if not schema_files:
            print(f"No schema files found in {schemas_dir_path}")
            sys.exit(1)

        print(f"Found {len(schema_files)} schema files to process")

        # Process each schema file
        for schema_path in schema_files:
            print(f"\n=== Processing {schema_path} ===")
            try:
                # Parse the schema
                entity_info = parse_schema(schema_path)

                # Update collection configuration
                update_collection_config(entity_info)

                # Generate files
                generate_schema_file(entity_info, str(schemas_dir))
                generate_service_file(entity_info, str(services_dir))
                generate_routes_file(entity_info, str(routes_dir))

                # Update the entity registry
                update_entity_registry(entity_info["entity_name"])

                print(f"✅ CRUD API generated for {entity_info['entity_name']}")
            except Exception as e:
                print(f"❌ Error processing {schema_path}: {str(e)}")
                import traceback

                print(traceback.format_exc())

        print("\n✅ All schema files processed!")
        print("\nNext steps:")
        print(
            "All files have been generated and the API router has been automatically updated."
        )

    else:
        # Process a single schema file (original behavior)
        schema_path = sys.argv[1]

        # Parse the schema
        entity_info = parse_schema(schema_path)

        # Update collection configuration
        update_collection_config(entity_info)

        # Generate files
        generate_schema_file(entity_info, str(schemas_dir))
        generate_service_file(entity_info, str(services_dir))
        generate_routes_file(entity_info, str(routes_dir))

        # Update the entity registry
        update_entity_registry(entity_info["entity_name"])

        print(f"\nCRUD API generated for {entity_info['entity_name']}!")
        print(f"\nNext steps:")
        print(
            f"All files have been generated and the API router has been automatically updated."
        )


if __name__ == "__main__":
    main()
