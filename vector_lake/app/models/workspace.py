"""Workspace and Collection models."""

from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    workspace_id: str
    name: str = ""
    description: str = ""


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: str
    collections_count: int = 0


class CollectionCreate(BaseModel):
    collection_id: str
    name: str = ""
    description: str = ""


class CollectionResponse(BaseModel):
    collection_id: str
    name: str
    description: str
    entity_count: int = 0
