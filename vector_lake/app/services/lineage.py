"""Lineage cascade: mark downstream reps stale when upstream changes.

Implements PRD §2.5 two-phase consistency model:
- Phase 1 (Rep↔Raw): when a rep changes, all downstream reps that
  depend on it (via ``required_input_reps``) are marked stale.
- Phase 2 (Index↔Rep): when a rep goes stale, its corresponding
  index entries are also marked stale and rebuilt.

The cascade logic uses the RepStep registry to determine which steps
consume a given rep_type (via ``required_input_reps``), and therefore
which output_reps become stale.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.registry import TemplateRegistry
from app.services.registry import registry as default_registry
from app.storage.protocol import StorageProtocol

if TYPE_CHECKING:
    from app.services.pipeline import PipelineService

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
    """Mark a single rep as stale by updating its OSS Tag status + manifest."""
    # Read current tags (may be empty if xattr unavailable)
    tags = storage.get_rep_tags(
        workspace_id, collection_id, entity_id, rep_type,
    )

    # Check if rep exists (file or manifest entry)
    file_exists = storage.file_exists(workspace_id, collection_id, entity_id, rep_type)
    manifest = storage.read_entity_manifest(workspace_id, collection_id, entity_id)
    rep_in_manifest = (
        manifest is not None
        and "rep_info" in manifest
        and rep_type in manifest.get("rep_info", {})
    )

    if not tags and not file_exists and not rep_in_manifest:
        # Rep doesn't exist, nothing to mark
        return

    # Update tags (best-effort, may fail if xattr unavailable)
    if tags:
        tags["status"] = "stale"
        storage.set_rep_tags(
            workspace_id, collection_id, entity_id, rep_type, tags,
        )

    # Also update manifest (source of truth, survives xattr loss)
    if manifest is not None:
        rep_info = manifest.setdefault("rep_info", {})
        rep_info[rep_type] = rep_info.get(rep_type, {
            "rep_type": rep_type,
            "status": "active",
            "modality": "text",
        })
        rep_info[rep_type]["status"] = "stale"
        storage.save_entity_manifest(workspace_id, collection_id, entity_id, manifest)


def get_stale_reps(
    workspace_id: str,
    collection_id: str,
    entity_id: str,
    storage: StorageProtocol,
) -> list[str]:
    """Get all rep_types that are marked as stale for an entity.

    Checks manifest first (source of truth), falls back to xattr tags.
    """
    from app.storage.lineage import REP_TYPE_TO_PATH

    stale: list[str] = []

    # Try manifest first (source of truth)
    manifest = storage.read_entity_manifest(workspace_id, collection_id, entity_id)
    if manifest and "rep_info" in manifest:
        for rep_type, info in manifest["rep_info"].items():
            if rep_type == "source_original":
                continue
            if info.get("status") == "stale":
                stale.append(rep_type)
        if stale:
            return stale

    # Fallback: check xattr tags
    for rep_type in REP_TYPE_TO_PATH:
        if rep_type == "source_original":
            continue
        tags = storage.get_rep_tags(
            workspace_id, collection_id, entity_id, rep_type,
        )
        if tags.get("status") == "stale":
            stale.append(rep_type)
    return stale


async def cascade_rebuild(
    workspace_id: str,
    collection_id: str,
    entity_id: str,
    changed_rep_type: str,
    storage: StorageProtocol,
    pipeline: PipelineService,
    template_registry: TemplateRegistry | None = None,
) -> list[str]:
    """Full cascade: mark stale → re-execute pipeline → re-sync index.

    This implements the complete PRD §2.5 two-phase consistency:
    1. Mark all downstream reps as stale (cascade_stale)
    2. Re-execute the pipeline to regenerate stale reps
    3. Re-sync index (parquet → LanceDB)

    Returns a list of rep_types that were rebuilt.
    """
    # Phase 1: Mark downstream reps as stale
    stale_reps = cascade_stale(
        workspace_id, collection_id, entity_id,
        changed_rep_type, storage, template_registry,
    )

    if not stale_reps:
        logger.info("No downstream reps to rebuild for %s", changed_rep_type)
        return []

    logger.info(
        "Cascade rebuild: %s changed → stale reps: %s → re-executing pipeline",
        changed_rep_type, stale_reps,
    )

    # Phase 2: Re-execute pipeline for stale reps
    rebuilt: list[str] = []
    for rep_type in stale_reps:
        try:
            # Read source content
            source_content = storage.read_file(
                workspace_id, collection_id, entity_id, "source_original",
            )
            if source_content is None:
                logger.warning("Cannot rebuild %s: source_original not found", rep_type)
                continue

            # Re-execute pipeline
            md_content = source_content.decode("utf-8", errors="replace")
            await pipeline.process_md_entity(
                workspace_id, collection_id, entity_id, md_content,
            )

            # Mark rep as active again in manifest
            manifest = storage.read_entity_manifest(workspace_id, collection_id, entity_id)
            if manifest and "rep_info" in manifest:
                if rep_type in manifest["rep_info"]:
                    manifest["rep_info"][rep_type]["status"] = "active"
                    storage.save_entity_manifest(
                        workspace_id, collection_id, entity_id, manifest,
                    )

            rebuilt.append(rep_type)
            logger.info("Rebuilt rep %s for entity %s", rep_type, entity_id)

        except Exception as e:
            logger.error(
                "Failed to rebuild rep %s for entity %s: %s",
                rep_type, entity_id, e,
            )

    # Phase 3: Re-sync index
    if rebuilt:
        try:
            count = await pipeline.index.sync_to_lance(
                workspace_id, collection_id, entity_id, "canonical_md",
            )
            logger.info(
                "Cascade rebuild: re-synced %d rows to LanceDB for entity %s",
                count, entity_id,
            )
        except Exception as e:
            logger.error(
                "Cascade rebuild: index re-sync failed for entity %s: %s",
                entity_id, e,
            )

    return rebuilt
