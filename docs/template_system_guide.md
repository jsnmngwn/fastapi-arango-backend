# Template System Guide for API Generator

## Overview

This guide explains the Jinja2 template-based system used to generate CRUD API endpoints for the FastAPI backend. The template system replaces the previous string concatenation approach with a more structured and maintainable solution.

## Template Directory Structure

The templates are organized into the following directories:

```
scripts/templates/
├── base/              # Core file templates
│   ├── schema.py.jinja
│   ├── service.py.jinja
│   └── routes.py.jinja
├── crud/              # CRUD operation templates
│   ├── create.py.jinja
│   ├── delete.py.jinja
│   ├── get_all.py.jinja
│   ├── get_by_key.py.jinja
│   ├── get_filtered.py.jinja
│   └── update.py.jinja
├── edge/              # Edge collection templates
├── custom/            # Custom function templates
└── helpers/           # Helper templates
    ├── import_block.py.jinja
    ├── models_block.py.jinja
    ├── router_block.py.jinja
    ├── router_import.py.jinja
    └── entity_router_config.json.jinja
```

## Template Categories

### 1. Base File Templates

These templates provide the core structure for schema, service, and routes files:

- `base/schema.py.jinja`: Defines Pydantic schemas for entities
- `base/service.py.jinja`: Contains service classes for database operations
- `base/routes.py.jinja`: Implements API endpoints

### 2. CRUD Function Templates

These templates implement standard CRUD operations that are included in the service file:

- `crud/create.py.jinja`: Create operation
- `crud/get_all.py.jinja`: Get all documents operation
- `crud/get_by_key.py.jinja`: Get document by key operation
- `crud/get_filtered.py.jinja`: Get filtered documents operation
- `crud/update.py.jinja`: Update operation
- `crud/delete.py.jinja`: Delete operation

### 3. Custom Function Templates

These templates provide specialized functionality for specific entity needs.

### 4. Helper Templates

These templates assist with integrating the generated code into the application:

- `helpers/import_block.py.jinja`: Import statements
- `helpers/models_block.py.jinja`: Model registration
- `helpers/router_block.py.jinja`: Router registration
- `helpers/router_import.py.jinja`: Router import statements
- `helpers/entity_router_config.json.jinja`: Entity router configuration

## Schema Configuration

The schema files use special properties to control the generation process:

### Standard Properties

- `properties`: Defines the fields and their types
- `required`: Lists the required fields
- `title`: Title for the entity
- `description`: Description for the entity

### Extended Properties

- `x-unique-combinations`: Defines field combinations that should have unique constraints
- `x-search-fields`: Specifies fields that should be searchable
- `x-custom-endpoints`: Defines custom functions with optional API routes that expose them
- `x-deletion-constraints`: Specifies collections to check for related documents before deletion
- `x-default-values`: Defines default values for fields

Example schema configuration with extended properties:

```json
{
  "properties": {
    "first_name": { "type": "string" },
    "last_name": { "type": "string" },
    "is_active": { "type": "boolean", "default": true }
  },
  "required": [
    "first_name", "last_name"
  ],
  "x-unique-combinations": [
    ["first_name", "last_name"]
  ],
  "x-search-fields": [
    "first_name",
    "last_name",
    "is_active"
  ],
  "x-custom-endpoints": [
    {
      "name": "get_order_products",
      "expose_route": true,
      "route_path": "/{key}/products",
      "http_method": "get"
    }
  ],
  "x-deletion-constraints": [
    "related_collection1",
    "related_collection2"
  ]
}
```

## Custom Jinja Filters

The template system uses custom Jinja filters to transform data:

- `pascal`: Converts snake_case to PascalCase (e.g., `user_profile` → `UserProfile`)
- `camel`: Converts snake_case to camelCase (e.g., `user_profile` → `userProfile`)
- `py_bool`: Ensures boolean values are properly formatted as Python booleans (`True`/`False`)
- `tojson`: Converts Python objects to JSON strings for inclusion in templates

## Creating Custom Functions

To create a custom function for an entity:

1. Define the custom endpoint in the schema's `x-custom-endpoints` array with the following properties:
   - `name`: The name of the custom function (required)
   - `expose_route`: Whether to expose the function via an API endpoint (default: true)
   - `route_path`: The URL path to expose the function at (default: based on the function name)
   - `http_method`: The HTTP method to use (default: "get")

2. Create a template file in `scripts/templates/custom/<function_name>.py.jinja`

3. If `expose_route` is true, create a route template in `scripts/templates/custom/<function_name>.route.jinja`

### Example: Organization Players Function

The following example shows a custom function that traverses a graph database to find all players in an organization:

```json
"x-custom-endpoints": [
  {
    "name": "get_organization_players",
    "expose_route": true,
    "route_path": "/{key}/players",
    "http_method": "get"
  }
]
```

The function template (`get_organization_players.py.jinja`):

```python
async def get_organization_players(self, key: str) -> Dict[str, Any]:
    """
    Get all players that belong to any team in this organization using graph traversal.
    
    This function traverses the graph from the organization to its teams and then to the 
    players associated with those teams.
    """
    try:
        # First check if the organization exists
        org = await self.get_by_key(key)
        
        # Define the AQL query for traversing the graph
        query = """
            LET org = DOCUMENT('organization/{0}')
            
            // Step 1: Find all teams belonging to this organization
            LET teams = (
                FOR team, edge IN INBOUND org team_organization
                RETURN team
            )
            
            // Step 2: Find all players belonging to any of these teams
            LET players = (
                FOR team IN teams
                    FOR player, edge IN INBOUND team player_team
                    RETURN MERGE(player, {{
                        "team": KEEP(team, '_key', 'name'),
                        "role": edge.role,
                        "position": edge.position1
                    }})
            )
            
            RETURN {{
                "organization": KEEP(org, '_key', 'name'),
                "players": players
            }}
        """.format(key)
        
        cursor = self.db.aql.execute(query)
        result = next(cursor, {{"organization": {{}}, "players": []}})
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting players in organization: {{e}}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving players for organization: {{str(e)}}"
        )
```

The route template (`get_organization_players.route.jinja`):

```python
@router.{{ http_method }}("{{ route_path }}", response_model=Dict[str, Any])
async def get_{{ entity.entity_name }}_players(
    key: str = Path(..., title="{{ entity.pascal_name }} key"),
    db: Database = Depends(get_db)
):
    """
    Get all players that belong to any team in the organization.
    
    This endpoint traverses the graph from the organization to teams to players,
    returning all players that are part of any team in the organization.
    """
    service = {{ entity.pascal_name }}Service(db)
    result = await service.get_organization_players(key)
    return result
```

## Important Notes

- JSON generation: The system uses `autoescape=None` to prevent automatic escaping in the Jinja environment, which is important for JSON generation.
- Python booleans: The `py_bool` filter ensures that Python's `True` and `False` are used in Python code contexts, while JSON booleans (`true`/`false`) are used in JSON contexts.
- Unique constraints: The system automatically creates unique indexes based on the `x-unique-combinations` property.
- Deletion constraints: The system generates code to check referenced collections before deletion based on the `x-deletion-constraints` property.
- Jinja2 and AQL syntax conflicts: When writing templates for AQL queries, be careful with double curly braces. Use `{{` and `}}` to output literal `{` and `}` characters in the generated code. This is especially important when defining JavaScript objects within AQL queries.

## Best Practices

1. Use the appropriate template category for your use case
2. Follow Python naming conventions in the generated code
3. Ensure all schema properties have appropriate types and descriptions
4. Add proper validation rules to Pydantic schemas
5. Document custom functions with clear docstrings
6. Implement proper error handling in custom functions
7. Use consistent naming for related templates (e.g., `get_stats.py.jinja` and `get_stats.route.jinja`)
8. When working with AQL in templates, use string formatting with `.format()` instead of f-strings when mixing with Jinja2
9. When defining complex custom functions with AQL queries, consider editing service files directly if template generation is challenging

## Troubleshooting

### Common Template Issues

1. **Template Syntax Error**: If you see errors like `jinja2.exceptions.TemplateSyntaxError`, check for:
   - Unmatched opening/closing tags (`{%`, `%}`, `{{`, `}}`)
   - Invalid Jinja2 expressions or statements
   - Python syntax errors inside Jinja2 code blocks

2. **Template Not Found**: If you get a `jinja2.exceptions.TemplateNotFound` error:
   - Verify the template filename matches what's referenced in the code
   - Check that the template is in the expected directory
   - Ensure template directories are correctly registered in the Jinja2 environment

3. **Undefined Variables**: For `jinja2.exceptions.UndefinedError`:
   - Check for typos in variable names
   - Ensure all required variables are passed to the template
   - Use `{{ variable | default('default_value') }}` for optional variables

### AQL in Templates

1. **Mismatched Braces**: The most common issue when working with AQL in templates is mismatched braces:
   
   **Problem**:
   ```python
   # This won't work - Jinja2 thinks {{ is part of a template variable
   query = """
       RETURN { "data": { "nested": true } }
   """
   ```
   
   **Solution**:
   ```python
   # Double the braces for literal braces in the output
   query = """
       RETURN {{ "data": {{ "nested": true }} }}
   """
   ```

2. **String Interpolation**: When including variables in AQL:
   
   **Problem**:
   ```python
   # This can cause confusion between Jinja2 variables and string interpolation
   query = f"""
       FOR doc IN collection
           FILTER doc._key == '{key}'
           RETURN doc
   """
   ```
   
   **Solution**:
   ```python
   # Use string formatting with position placeholders
   query = """
       FOR doc IN collection
           FILTER doc._key == '{0}'
           RETURN doc
   """.format(key)
   ```

3. **Undefined AQL Variables**: When AQL variables have the same names as Jinja2 variables:
   
   **Problem**:
   ```python
   # If 'name' is also a Jinja2 variable, this causes confusion
   query = """
       LET name = 'test'
       RETURN name
   """
   ```
   
   **Solution**:
   ```python
   # Use distinctive names for AQL variables
   query = """
       LET aql_name = 'test'
       RETURN aql_name
   """
   ```

### Graph Traversal Issues

1. **Wrong Direction**: Graph traversals can be INBOUND, OUTBOUND, or ANY:
   
   ```
   // Use INBOUND when traversing from the target to the source
   FOR team, edge IN INBOUND org team_organization
   
   // Use OUTBOUND when traversing from the source to the target
   FOR team, edge IN OUTBOUND org organization_team
   ```

2. **Edge Collection Names**: Make sure the edge collection names match your database:
   
   ```
   // If your edge collection is named team_organization (from team to organization)
   FOR team, edge IN INBOUND org team_organization
   
   // NOT this (unless you have an edge collection with this name)
   FOR team, edge IN INBOUND org organization_team
   ```

3. **Missing or Incorrect Merge Parameters**: When merging documents with attributes:
   
   **Problem**:
   ```
   // This will cause an error if edge.role doesn't exist
   RETURN MERGE(player, { "role": edge.role })
   ```
   
   **Solution**:
   ```
   // Check if the attribute exists or provide a default
   RETURN MERGE(player, { "role": HAS(edge, "role") ? edge.role : null })
   ```

### Debugging Templates

1. **Preview Generated Code**: You can preview the generated code without writing to files:
   
   ```bash
   python3 scripts/generate_basic_crud_api_endpoints.py --preview organization
   ```

2. **Add Debug Comments**: Add debug comments in your templates to mark sections:
   
   ```python
   # DEBUG: Start of custom function
   async def get_organization_players(self, key: str) -> Dict[str, Any]:
       # ...
   # DEBUG: End of custom function
   ```

3. **Use Jinja2 Debug Extension**: Enable the Jinja2 debug extension for more verbose error messages:
   
   ```python
   env = Environment(
       loader=FileSystemLoader("templates"),
       extensions=['jinja2.ext.debug']
   )
   ```

### Testing AQL Queries

To test AQL queries separately from your templates:

1. Extract the query from your template
2. Replace template variables with actual values
3. Test the query directly in the ArangoDB web interface or arangosh

Example workflow:

1. In your template:
   ```python
   query = """
       FOR team, edge IN INBOUND DOCUMENT('organization/{0}') team_organization
       RETURN team
   """.format(key)
   ```

2. For testing (replace variables with test values):
   ```
   FOR team, edge IN INBOUND DOCUMENT('organization/12345') team_organization
   RETURN team
   ```

3. Run this in the ArangoDB web interface to verify it works
4. Once verified, incorporate it back into your template
