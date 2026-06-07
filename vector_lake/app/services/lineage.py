"""Lineage cascade: mark downstream reps stale when upstream changes.

Implements PRD §2.5 two-phase consistency model:
- Phase 1 (Rep↔Raw): when a rep changes, all downstream reps that
  depend on it (via ``required_input_reps``) are marked stale.
- Phase 2 (Index↔Rep): when a rep goes stale, its corresponding
  index entries are also marked stale.

The cascade logic uses the RepStep registry to determine which steps
consume a given rep_type (via ``required_input_reps``), and therefore
which output_reps become stale.
"""

from __future__ import annotations

import logging

from app.services.registry import TemplateRegistry
from app.services.registry import registry as default_registry
from app.storage.protocol import StorageProtocol

logger = logging.getLogger(__name__)


def cascade_stale(
    workspace_id: str,
    collection_id: str,
    entity_id: str,
    changed_rep_type: str,
    storage: StorageProtocol,
    template_registry: TemplateRegistry | None = None,
) -> list[str]:
    """Mark downstream reps as stale when an upstream rep changes.

    Given a rep_type that has changed (e.g. "source_original"),
    find all RepSteps that consume it (via ``required_input_reps``),
    then mark their ``output_reps`` as stale by updating the rep's
    OSS Tag ``status`` to ``"stale"``.

    Returns a list of rep_types that were marked stale.
    """
    reg = template_registry or default_registry
    stale_reps: list[str] = []

    # Find all steps that consume the changed rep
    for step in reg._steps.values():
        if changed_rep_type in getattr(step, "required_input_reps", []):
            for output_rep in getattr(step, "output_reps", []):
                # Mark the output rep as stale
                _mark_rep_stale(
                    workspace_id, collection_id, entity_id,
                    output_rep, storage,
                )
                stale_reps.append(output_rep)
                # Recursively cascade: if this output is input to another step
                deeper = cascade_stale(
                    workspace_id, collection_id, entity_id,
                    output_rep, storage, reg,
                )
                stale_reps.extend(deeper)

    if stale_reps:
        logger.info(
            "Lineage cascade: %s changed → stale reps: %s",
            changed_rep_type, stale_reps,
        )

    return stale_reps


def _mark_rep_stale(
    workspace_id: str,
    collection_id: str,
    entity_id: str,
    rep_type: str,
    storage: StorageProtocol,
) -> None:
    """Mark a single rep as stale by updating its OSS Tag status."""
    # Read current tags
    tags = storage.get_rep_tags(
        workspace_id, collection_id, entity_id, rep_type,
    )
    if not tags:
        # Rep doesn't exist yet, nothing to mark
        return
    # Update status to stale
    tags["status"] = "stale"
    storage.set_rep_tags(
        workspace_id, collection_id, entity_id, rep_type, tags,
    )


def get_stale_reps(
    workspace_id: str,
    collection_id: str,
    entity_id: str,
    storage: StorageProtocol,
) -> list[str]:
    """Get all rep_types that are marked as stale for an entity."""
    from app.storage.lineage import REP_TYPE_TO_PATH

    stale: list[str] = []
    # Check all known rep types
    for rep_type in REP_TYPE_TO_PATH:
        if rep_type == "source_original":
            continue  # source is never stale (it's immutable)
        tags = storage.get_rep_tags(
            workspace_id, collection_id, entity_id, rep_type,
        )
        if tags.get("status") == "stale":
            stale.append(rep_type)
    return stale
