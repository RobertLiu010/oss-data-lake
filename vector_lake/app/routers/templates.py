"""Template registry management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.registry import registry

router = APIRouter(
    prefix="/api/v1/templates",
    tags=["templates"],
)


# ---------------------------------------------------------------------------
# Rep Steps (multi-step pipeline)
# ---------------------------------------------------------------------------


@router.get("/steps")
async def list_steps():
    """List all registered RepSteps."""
    return registry.list_steps()


@router.get("/steps/{name}")
async def get_step(name: str):
    """Get details of a specific RepStep."""
    step = registry.get_step(name)
    if step is None:
        raise HTTPException(status_code=404, detail=f"RepStep '{name}' not found")
    return {
        "name": step.name,
        "input_format": step.input_format,
        "output_format": step.output_format,
    }


@router.get("/pipeline/resolve")
async def resolve_pipeline(
    source_format: str = "",
    filename: str = "",
    target_format: str = "md",
):
    """Resolve the pipeline path from a source format or filename.

    Provide either ``source_format`` or ``filename``.
    """
    if not source_format and not filename:
        raise HTTPException(
            status_code=400,
            detail="Provide either source_format or filename parameter",
        )

    try:
        if source_format:
            pipeline = registry.resolve_pipeline(source_format, target_format)
        else:
            pipeline = registry.resolve_pipeline_for_file(filename, target_format)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "source_format": pipeline.source_format,
        "target_format": pipeline.target_format,
        "steps": [
            {
                "name": s.name,
                "input_format": s.input_format,
                "output_format": s.output_format,
            }
            for s in pipeline.steps
        ],
        "description": pipeline.describe(),
    }


@router.get("/pipeline/formats")
async def list_formats():
    """List all registered extension → format mappings."""
    return {
        "mappings": registry._extension_format_map,
        "dag": {
            src: [{"format": fmt, "step": name} for fmt, name in edges]
            for src, edges in registry._dag.items()
        },
    }


# ---------------------------------------------------------------------------
# Rep Templates (legacy)
# ---------------------------------------------------------------------------


@router.get("/rep")
async def list_rep_templates():
    """List all registered representation templates."""
    return registry.list_rep_templates()


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


# ---------------------------------------------------------------------------
# Index Templates
# ---------------------------------------------------------------------------


@router.get("/index")
async def list_index_templates():
    """List all registered index templates."""
    return registry.list_index_templates()


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


# ---------------------------------------------------------------------------
# Extension resolution
# ---------------------------------------------------------------------------


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
