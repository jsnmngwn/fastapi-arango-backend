#!/usr/bin/env python3
# filepath: /home/jason/github/vb-stat-logger/scripts/generate_basic_crud_api_endpoints.py
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

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger


def snake_to_pascal(snake_str: str) -> str:
    """Convert snake_case to PascalCase"""
    return "".join(x.capitalize() for x in snake_str.split("_"))


def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    components = snake_str.split("_")
    return components[0] + "".join(x.capitalize() for x in components[1:])


def update_collection_config(
    entity_info, is_edge=None, from_collection=None, to_collection=None
):
    """Update the collections.json configuration file with the new collection.
    
    Uses singular form for collection names to ensure consistency with service classes.
    """
    # Extract values from entity_info if a dict is provided
    if isinstance(entity_info, dict):
        collection_name = entity_info.get("entity_name", "")
        is_edge = entity_info.get("is_edge", False) if is_edge is None else is_edge
        
        # For edge collections, get connected entities
        if is_edge and not from_collection and not to_collection:
            connected_entities = entity_info.get("connected_entities", [])
            if len(connected_entities) == 2:
                from_collection, to_collection = connected_entities
    else:
        # If entity_info is just the collection name as a string
        collection_name = entity_info
        is_edge = is_edge if is_edge is not None else False
        
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
            # Use singular form for collections consistently
            # No pluralization needed as service classes use singular form
            
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
                        "from_collections": [from_collection],
                        "to_collections": [to_collection],
                    }
                )
    else:
        # Use singular form consistently (no pluralization)
        if collection_name not in config["document_collections"]:
            config["document_collections"].append(collection_name)

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
            
    # Extract deletion constraints
    deletion_constraints = schema.get("x-deletion-constraints", [])
    
    # Extract custom endpoints (new format)
    custom_endpoints = schema.get("x-custom-endpoints", [])
    
    # For backward compatibility, also handle the old format
    custom_functions = schema.get("x-custom-functions", [])
    custom_routes = schema.get("x-custom-routes", [])
    
    # Convert old format to new format if needed
    if custom_functions and not custom_endpoints:
        for func_name in custom_functions:
            endpoint = {
                "name": func_name,
                "expose_route": func_name in custom_routes
            }
            custom_endpoints.append(endpoint)

    # Extract just the function names for template rendering
    custom_functions = [endpoint["name"] for endpoint in custom_endpoints]
    # Extract route-enabled function names
    custom_routes = [endpoint["name"] for endpoint in custom_endpoints if endpoint.get("expose_route", True)]

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
        "deletion_constraints": deletion_constraints,
        "custom_functions": custom_functions,
        "custom_routes": custom_routes,
        "custom_endpoints": custom_endpoints,
        "x-default-values": schema.get("x-default-values", {}),
    }


def get_jinja_env():
    """Create and return a Jinja2 environment"""
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=None,  # Disable auto-escaping for JSON generation
        trim_blocks=True,  # Remove first newline after a block
        lstrip_blocks=True,  # Strip tabs and spaces from the beginning of a line to the start of a block
        keep_trailing_newline=True  # Keep the newline when rendering templates
    )
    
    # Register custom filters
    env.filters["pascal"] = snake_to_pascal
    env.filters["camel"] = snake_to_camel
    
    # Special Python-specific filter for bool values
    env.filters["py_bool"] = lambda x: "True" if x else "False"
    
    return env


def generate_schema_file(entity_info: Dict[str, Any], output_dir: str) -> None:
    """Generate Pydantic schema file using Jinja2 template"""
    env = get_jinja_env()
    
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
    
    template = env.get_template("base/schema.py.jinja")
    rendered = template.render(
        entity=entity_info,
        type_mapping=type_mapping,
        format_mapping=format_mapping
    )
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{entity_info['entity_name']}.py")
    
    # Fix indentation to ensure class fields are properly indented
    lines = rendered.split('\n')
    properly_indented = []
    class_def_found = False
    
    for line in lines:
        if line.strip().startswith('class '):
            class_def_found = True
            properly_indented.append(line)
        elif class_def_found and line.strip() and not line.startswith('    ') and not line.startswith('"""'):
            # Add indentation to class fields that aren't already indented
            properly_indented.append('    ' + line)
        else:
            properly_indented.append(line)
    
    with open(output_path, "w") as f:
        f.write('\n'.join(properly_indented))
        
    print(f"Generated schema file: {output_path}")


def generate_service_file(entity_info: Dict[str, Any], output_dir: str) -> None:
    """Generate service class file using Jinja2 template"""
    env = get_jinja_env()
    template = env.get_template("base/service.py.jinja")
    
    rendered = template.render(
        entity=entity_info
    )
    
    # Fix method definitions not properly indented under class
    lines = rendered.split('\n')
    properly_indented = []
    in_class = False
    
    for line in lines:
        if line.strip().startswith('class '):
            in_class = True
            properly_indented.append(line)
        elif in_class and line.strip() and (line.startswith('async def ') or line.startswith('def ')):
            # Add indentation to method definitions
            properly_indented.append('    ' + line)
        else:
            properly_indented.append(line)
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{entity_info['entity_name']}_service.py")
    with open(output_path, "w") as f:
        f.write('\n'.join(properly_indented))
        
    print(f"Generated service file: {output_path}")


def generate_routes_file(entity_info: Dict[str, Any], output_dir: str) -> None:
    """Generate routes file using Jinja2 template"""
    env = get_jinja_env()
    
    # Map JSON schema types to Python types for query params
    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "List[Any]",
        "object": "Dict[str, Any]",
    }
    
    template = env.get_template("base/routes.py.jinja")
    rendered = template.render(
        entity=entity_info,
        type_mapping=type_mapping
    )
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{entity_info['entity_name']}_routes.py")
    
    # Ensure route function definitions are properly indented
    lines = rendered.split('\n')
    properly_indented = []
    in_decorator = False
    
    for line in lines:
        if line.strip().startswith('@router.'):
            in_decorator = True
            properly_indented.append(line)
        elif in_decorator and line.strip().startswith('async def '):
            # Keep the decorator's function correctly indented
            properly_indented.append(line)
            in_decorator = False
        elif line.strip().startswith('async def '):
            # Add indentation to any async def that isn't after a decorator
            properly_indented.append('    ' + line)
        else:
            properly_indented.append(line)
    
    with open(output_path, "w") as f:
        f.write('\n'.join(properly_indented))
        
    print(f"Generated routes file: {output_path}")


def generate_custom_files(entity_info: Dict[str, Any], output_dir: str) -> None:
    """Generate custom function and route files using Jinja2 templates"""
    env = get_jinja_env()
    
    # Get the custom endpoints configuration
    custom_endpoints = entity_info.get("custom_endpoints", [])
    
    for endpoint in custom_endpoints:
        function_name = endpoint.get("name")
        if not function_name:
            continue
            
        # Check if there are custom templates for this function
        function_template_path = f"custom/{function_name}.py.jinja"
        route_template_path = f"custom/{function_name}.route.jinja"
        
        # Try to get the function template
        try:
            function_template = env.get_template(function_template_path)
            
            # Get HTTP method and route path from endpoint or use defaults
            http_method = endpoint.get("http_method", "get").lower()
            route_path = endpoint.get("route_path", f"/{function_name}")
            
            # Render the function template with additional context
            rendered_function = function_template.render(
                entity=entity_info,
                http_method=http_method,
                route_path=route_path,
                endpoint=endpoint
            )
            
            # Add the function to the service file
            service_file_path = os.path.join(output_dir, f"{entity_info['entity_name']}_service.py")
            
            if os.path.exists(service_file_path):
                with open(service_file_path, "r") as f:
                    service_content = f.read()
                
                # Check if the function is already defined
                function_def_pattern = re.compile(f"async def {function_name}\\(.*?\\):")
                if not function_def_pattern.search(service_content):
                    # Find where to insert the function - before the last line
                    last_line_index = service_content.rstrip().rfind("\n")
                    
                    # Insert the function at the appropriate place
                    service_content = (
                        service_content[:last_line_index] +
                        "\n\n" + rendered_function +
                        service_content[last_line_index:]
                    )
                    
                    with open(service_file_path, "w") as f:
                        f.write(service_content)
                        
                    print(f"Added custom function '{function_name}' to service file")
                else:
                    print(f"Custom function '{function_name}' already exists in service file")
            else:
                print(f"Warning: Service file not found at {service_file_path}")
                
        except Exception as e:
            print(f"Error generating custom function {function_name}: {e}")
        
        # If this endpoint should have a route, generate it
        if endpoint.get("expose_route", True):
            try:
                route_template = env.get_template(route_template_path)
                
                # Get HTTP method and route path from endpoint or use defaults
                http_method = endpoint.get("http_method", "get").lower()
                route_path = endpoint.get("route_path", f"/{function_name}")
                
                # Render the route template with additional context
                rendered_route = route_template.render(
                    entity=entity_info,
                    http_method=http_method,
                    route_path=route_path,
                    endpoint=endpoint
                )
                
                # Add the route to the routes file
                routes_file_path = os.path.join(output_dir, f"{entity_info['entity_name']}_routes.py")
                
                if os.path.exists(routes_file_path):
                    with open(routes_file_path, "r") as f:
                        routes_content = f.read()
                    
                    # Check if the route is already defined
                    route_def_pattern = re.compile(f"async def {entity_info['entity_name']}_{function_name}\\(.*?\\):")
                    if not route_def_pattern.search(routes_content):
                        # Find where to insert the route - before the last line
                        last_line_index = routes_content.rstrip().rfind("\n")
                        
                        # Insert the route at the appropriate place
                        routes_content = (
                            routes_content[:last_line_index] +
                            "\n\n" + rendered_route +
                            routes_content[last_line_index:]
                        )
                        
                        with open(routes_file_path, "w") as f:
                            f.write(routes_content)
                            
                        print(f"Added custom route for '{function_name}' to routes file")
                    else:
                        print(f"Custom route for '{function_name}' already exists in routes file")
                else:
                    print(f"Warning: Routes file not found at {routes_file_path}")
                    
            except Exception as e:
                print(f"Error generating custom route for {function_name}: {e}")


def update_entity_registry(entity_name: str) -> None:
    """Update the entity registry file and schema imports with the new entity"""
    pascal_name = snake_to_pascal(entity_name)

    # Build paths with absolute references
    project_root = Path(__file__).parent.parent
    entity_registry_path = project_root / "backend" / "routes" / "entities.py"
    router_json_path = project_root / "backend" / "routes" / "entity_router.json"
    schemas_init_path = project_root / "backend" / "schemas" / "__init__.py"

    # Get Jinja2 environment
    env = get_jinja_env()

    print(f"Updating entity registry at: {entity_registry_path}")
    print(f"Updating schemas __init__ at: {schemas_init_path}")
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

    # Render the router import and router entry
    router_import = env.get_template("helpers/router_import.py.jinja").render(
        entity_name=entity_name
    )
    router_block = env.get_template("helpers/router_block.py.jinja").render(
        entity_name=entity_name
    )

    if router_import not in content:  # Avoid duplicates
        content = content.replace(
            "# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
            f"{router_import}\n# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
        )

    # Check if this router is already listed by looking for its name specifically
    router_pattern = rf"\b{entity_name}_router\b"
    router_already_exists = False
    if "entity_routers = [" in content:
        router_already_exists = re.search(
            router_pattern, content.split("entity_routers = [")[1].split("]")[0]
        )

    if not router_already_exists:  # Only add if not already in the list
        content = content.replace(
            "    # AUTO-GENERATED ROUTERS - DO NOT REMOVE THIS LINE",
            f"{router_block}\n    # AUTO-GENERATED ROUTERS - DO NOT REMOVE THIS LINE",
        )
        
    # Write the updated content
    with open(entity_registry_path, "w") as f:
        f.write(content)

    print(f"Updated entity registry with {entity_name}_router")

    # Get schema info to check if it's an edge collection
    entity_is_edge = False
    connected_entities = []
    search_fields = []
    
    # Look for the entity info in the original schema path
    schema_files = glob.glob(str(Path(sys.argv[1]).parent / f"{entity_name}.schema.json"))
    if schema_files:
        try:
            schema_info = parse_schema(schema_files[0])
            entity_is_edge = schema_info.get("is_edge", False)
            connected_entities = schema_info.get("connected_entities", [])
            search_fields = schema_info.get("search_fields", [])
        except Exception as e:
            logger.warning(f"Error parsing schema for {entity_name}: {e}")
    
    # Create simplified entity info for the router config
    pascal_name = snake_to_pascal(entity_name)
    simple_entity_info = {
        "entity_name": entity_name,
        "pascal_name": pascal_name,
        "camel_name": snake_to_camel(entity_name),
        "description": f"API for managing {pascal_name} resources",
        "is_edge": entity_is_edge,
        "connected_entities": connected_entities,
        "search_fields": search_fields
    }
    
    # Update entity router JSON config
    env.filters["tojson"] = json.dumps
    router_config_template = env.get_template("helpers/entity_router_config.json.jinja")
    router_config_rendered = router_config_template.render(entity=simple_entity_info)
    
    # Parse the rendered JSON
    router_config = json.loads(router_config_rendered)
    
    # Load existing router config if it exists
    router_config_full = {}
    if router_json_path.exists():
        try:
            with open(router_json_path, "r") as f:
                router_config_full = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Error parsing {router_json_path}, starting with empty config")
    
    # Update with new entity configuration
    router_config_full.update(router_config)
    
    # Write the updated config
    with open(router_json_path, "w") as f:
        json.dump(router_config_full, f, indent=2)
        
    print(f"Updated entity router JSON config for {entity_name}")

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

    # Render the import and models blocks using Jinja2 templates
    import_block = env.get_template("helpers/import_block.py.jinja").render(
        entity_name=entity_name, pascal_name=pascal_name
    )
    models_block = env.get_template("helpers/models_block.py.jinja").render(
        pascal_name=pascal_name
    )

    if f"from .{entity_name} import" not in init_content:  # Avoid duplicates
        init_content = init_content.replace(
            "# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
            f"{import_block}\n\n# AUTO-GENERATED IMPORTS - DO NOT REMOVE THIS LINE",
        )

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

                # Update collection configuration - FIX HERE
                update_collection_config(
                    entity_info["entity_name"],
                    is_edge=entity_info["is_edge"],
                    from_collection=(
                        entity_info["connected_entities"][0]
                        if entity_info["is_edge"] and entity_info["connected_entities"]
                        else None
                    ),
                    to_collection=(
                        entity_info["connected_entities"][1]
                        if entity_info["is_edge"]
                        and len(entity_info["connected_entities"]) > 1
                        else None
                    ),
                )

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
