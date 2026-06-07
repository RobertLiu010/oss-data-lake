"""Template registry management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.registry import registry

router = APIRouter(
    prefix="/api/v1/templates",
    tags=["templates"],
)


@router.get("/rep")
async def list_rep_templates():
    """List all registered representation templates."""
    return registry.list_rep_templates()


@router.get("/index")
async def list_index_templates():
    """List all registered index templates."""
    return registry.list_index_templates()


@router.get("/rep/{name}")
async def get_rep_template(name: str):
    """Get details of a specific RepTemplate."""
    tmpl = registry.get_rep_template(name)
    if tmpl is None:
        raise HTTPException(status_code=404, detail=f"RepTemplate '{name}' not found")
    return {
        "name": tmpl.name,
        "rep_type": tmpl.rep_type,
        "source_extensions": tmpl.source_extensions,
        "entity_types": getattr(tmpl, "entity_types", []),
    }


@router.get("/index/{name}")
async def get_index_template(name: str):
    """Get details of a specific IndexTemplate."""
    tmpl = registry.get_index_template(name)
    if tmpl is None:
        raise HTTPException(status_code=404, detail=f"IndexTemplate '{name}' not found")
    return {
        "name": tmpl.name,
        "index_type": tmpl.index_type,
    }


@router.get("/resolve")
async def resolve_template(extension: str = ""):
    """Resolve which RepTemplate handles a given file extension."""
    if not extension:
        raise HTTPException(status_code=400, detail="extension parameter is required")
    templates = registry.find_rep_templates_for_extension(extension)
    if not templates:
        return {"extension": extension, "templates": []}
    return {
        "extension": extension,
        "templates": [
            {
                "name": t.name,
                "rep_type": t.rep_type,
                "source_extensions": t.source_extensions,
            }
            for t in templates
        ],
    }
