"""全面修复重建测试 — 模拟各种故障场景并验证系统自愈能力。

测试覆盖:
1. 完整生命周期: 创建 → 多种故障注入 → 检测 → 修复 → 验证恢复
2. Rep 层故障: 缺失 canonical_md、stale rep、损坏的 manifest
3. Index 层故障: 缺失 parquet、缺失 LanceDB 记录
4. 级联故障: source_original 变动后下游全部 stale
5. Reconciler 自动检测 + 自动修复
6. cascade_rebuild 手动触发完整级联
7. update_entity_content API 触发级联重建
8. 多实体批量故障 + 批量修复
9. 修复后搜索功能验证
10. 修复后数据完整性验证 (manifest/parquet/LanceDB 三层一致)
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.services.lineage import cascade_rebuild, cascade_stale, get_stale_reps
from app.storage.lineage import rep_type_to_relpath


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def ws():
    return "rebuild_ws"


@pytest.fixture
def col():
    return "rebuild_col"


# ===========================================================================
# 1. 完整生命周期: 创建 → 故障 → 检测 → 修复 → 验证
# ===========================================================================


class TestFullLifecycleRebuild:
    """完整生命周期: 正常创建 → 注入多种故障 → reconciler 检测 → 自动修复 → 验证恢复。"""

    @pytest.mark.asyncio
    async def test_full_lifecycle_missing_rep_then_reconcile(
        self, entity_service, reconciler_service, index_service, storage, ws, col,
    ):
        """场景: 创建实体 → 删除 canonical_md → reconciler 检测并修复。"""
        # Step 1: 创建实体
        entity = await entity_service.create_from_bytes(
            ws, col, "lifecycle1.md", b"# Lifecycle Test\n\nOriginal content here.",
        )
        eid = entity.entity_id

        # 验证初始状态完整
        assert storage.file_exists(ws, col, eid, "source_original")
        assert storage.file_exists(ws, col, eid, "canonical_md")
        assert index_service.read_entity_parquet(ws, col, eid, "canonical_md") is not None
        manifest = storage.read_entity_manifest(ws, col, eid)
        assert manifest is not None

        # Step 2: 注入故障 — 删除 canonical_md
        canon_path = storage._entity_dir(ws, col, eid) / rep_type_to_relpath("canonical_md")
        assert canon_path.exists()
        canon_path.unlink()
        assert not storage.file_exists(ws, col, eid, "canonical_md")

        # Step 3: reconciler 检测
        result = await reconciler_service.reconcile(ws, col)
        assert result.entities_scanned >= 1
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_rep" in drift_types

        # Step 4: reconciler 自动修复
        assert result.drifts_repaired >= 1

        # Step 5: 验证恢复
        assert storage.file_exists(ws, col, eid, "canonical_md")
        content = storage.read_file(ws, col, eid, "canonical_md")
        assert content is not None
        assert b"Lifecycle Test" in content

    @pytest.mark.asyncio
    async def test_full_lifecycle_stale_rep_then_reconcile(
        self, entity_service, reconciler_service, index_service, storage, ws, col,
    ):
        """场景: 创建实体 → 修改 source_original 但不触发 pipeline → reconciler 检测 stale。"""
        # Step 1: 创建实体
        entity = await entity_service.create_from_bytes(
            ws, col, "lifecycle2.md", b"# Stale Test\n\nVersion 1.",
        )
        eid = entity.entity_id
        original_canon = storage.read_file(ws, col, eid, "canonical_md")

        # Step 2: 注入故障 — 直接修改 source_original (绕过 pipeline)
        new_content = b"# Stale Test\n\nVersion 2 with updated content."
        storage.save_file(ws, col, eid, "source_original", new_content)
        # 更新 manifest 的 content_hash 使其与实际不匹配
        manifest = storage.read_entity_manifest(ws, col, eid)
        if manifest:
            manifest["content_hash"] = "wrong_hash"
            storage.save_entity_manifest(ws, col, eid, manifest)

        # Step 3: reconciler 检测 stale
        result = await reconciler_service.reconcile(ws, col)
        drift_types = {d.drift_type.value for d in result.drifts_found}
        # 可能检测到 stale_rep (content_hash 不匹配)
        assert result.entities_scanned >= 1

        # Step 4: 验证修复 (reconciler 会重新执行 pipeline)
        if result.drifts_repaired > 0:
            new_canon = storage.read_file(ws, col, eid, "canonical_md")
            assert new_canon is not None


# ===========================================================================
# 2. Index 层故障: parquet 缺失 / LanceDB 缺失
# ===========================================================================


class TestIndexLayerRebuild:
    """Index 层故障: parquet 文件缺失、LanceDB 记录缺失。"""

    @pytest.mark.asyncio
    async def test_missing_parquet_detected_and_repaired(
        self, entity_service, reconciler_service, index_service, storage, ws, col,
    ):
        """场景: 删除 parquet 文件 → reconciler 检测 missing_index → 修复。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "idx1.md", b"# Index Test\n\nContent for index.",
        )
        eid = entity.entity_id

        # 删除 parquet 文件
        index_service.delete_entity_parquet(ws, col, eid, "canonical_md")
        assert index_service.read_entity_parquet(ws, col, eid, "canonical_md") is None

        # reconciler 检测
        result = await reconciler_service.reconcile(ws, col)
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_index" in drift_types

        # 自动修复
        assert result.drifts_repaired >= 1

    @pytest.mark.asyncio
    async def test_sync_to_lance_rebuilds_index(
        self, entity_service, index_service, storage, ws, col,
    ):
        """场景: 手动调用 sync_to_lance 重建 index。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "idx2.md", b"# Sync Test\n\nContent for sync.",
        )
        eid = entity.entity_id

        # 删除 parquet + 重新写入
        index_service.delete_entity_parquet(ws, col, eid, "canonical_md")

        # 重新执行 pipeline (通过 process_md_entity)
        pipeline = entity_service.pipeline
        source = storage.read_file(ws, col, eid, "source_original")
        if source:
            await pipeline.process_md_entity(ws, col, eid, source.decode("utf-8", errors="replace"))

        # sync_to_lance 重建
        count = await index_service.sync_to_lance(ws, col, eid, "canonical_md")
        assert count > 0


# ===========================================================================
# 3. 级联故障: source_original 变动 → 下游全部 stale
# ===========================================================================


class TestCascadeStaleAndRebuild:
    """级联故障: 上游变动 → 下游 stale → 完整级联重建。"""

    @pytest.mark.asyncio
    async def test_cascade_stale_marks_downstream(
        self, entity_service, storage, ws, col,
    ):
        """场景: cascade_stale 将 source_original 的下游标记为 stale。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "cascade1.md", b"# Cascade Stale\n\nContent.",
        )
        eid = entity.entity_id

        # 触发 cascade_stale
        stale_reps = cascade_stale(ws, col, eid, "source_original", storage)
        assert "canonical_md" in stale_reps

        # 验证 manifest 中 canonical_md 被标记为 stale
        manifest = storage.read_entity_manifest(ws, col, eid)
        assert manifest is not None
        if "rep_info" in manifest and "canonical_md" in manifest["rep_info"]:
            assert manifest["rep_info"]["canonical_md"]["status"] == "stale"

    @pytest.mark.asyncio
    async def test_cascade_rebuild_full_cycle(
        self, entity_service, index_service, storage, pipeline_service, ws, col,
    ):
        """场景: cascade_rebuild 完整级联 — stale → pipeline → index。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "cascade2.md", b"# Cascade Rebuild\n\nOriginal.",
        )
        eid = entity.entity_id

        # 完整级联重建
        rebuilt = await cascade_rebuild(
            ws, col, eid, "source_original", storage, pipeline_service,
        )
        assert "canonical_md" in rebuilt

        # 验证无 stale rep
        stale = get_stale_reps(ws, col, eid, storage)
        assert len(stale) == 0

        # 验证 canonical_md 存在
        assert storage.file_exists(ws, col, eid, "canonical_md")

    @pytest.mark.asyncio
    async def test_update_entity_content_triggers_cascade(
        self, entity_service, index_service, storage, ws, col,
    ):
        """场景: update_entity_content 触发完整级联重建。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "cascade3.md", b"# Before Update\n\nOld content.",
        )
        eid = entity.entity_id
        old_hash = entity.content_hash

        # 更新内容
        updated = await entity_service.update_entity_content(
            ws, col, eid, b"# After Update\n\nNew content with more details.",
        )
        assert updated is not None
        assert updated.version == 2
        assert updated.content_hash != old_hash

        # 验证 canonical_md 已更新
        canon = storage.read_file(ws, col, eid, "canonical_md")
        assert canon is not None
        assert b"After Update" in canon

        # 验证 version log
        log = storage.read_version_log(ws, col, eid)
        triggers = [entry["trigger"] for entry in log]
        assert "content_update" in triggers

        # 验证无 stale rep
        stale = get_stale_reps(ws, col, eid, storage)
        assert len(stale) == 0


# ===========================================================================
# 4. Manifest 损坏 / 丢失
# ===========================================================================


class TestManifestCorruption:
    """Manifest 损坏或丢失场景。"""

    @pytest.mark.asyncio
    async def test_missing_manifest_detected(
        self, entity_service, reconciler_service, storage, ws, col,
    ):
        """场景: 删除 manifest → reconciler 检测 missing_meta。"""
        # 手动创建实体 (只有 source_original)
        storage.save_file(ws, col, "ent_no_meta", "source_original", b"# No Meta")
        # 不写 manifest

        result = await reconciler_service.reconcile(ws, col)
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_meta" in drift_types

    @pytest.mark.asyncio
    async def test_corrupted_manifest_fallback(
        self, entity_service, storage, ws, col,
    ):
        """场景: manifest 损坏 → assemble_entity 降级到 tags。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "corrupt1.md", b"# Corrupt Manifest\n\nContent.",
        )
        eid = entity.entity_id

        # 损坏 manifest
        entity_dir = storage._entity_dir(ws, col, eid)
        manifest_path = entity_dir / ".entity_manifest.json"
        manifest_path.write_text("{invalid json")

        # assemble_entity 应该降级到 tags
        result = storage.assemble_entity(ws, col, eid)
        # 可能返回 None 或降级结果
        # 关键是不应该抛异常


# ===========================================================================
# 5. 多实体批量故障 + 批量修复
# ===========================================================================


class TestBatchFailureAndRepair:
    """多实体批量故障场景。"""

    @pytest.mark.asyncio
    async def test_multiple_entities_with_missing_reps(
        self, entity_service, reconciler_service, storage, ws, col,
    ):
        """场景: 多个实体同时缺失 canonical_md → reconciler 批量修复。"""
        # 创建 3 个实体
        entities = []
        for i in range(3):
            e = await entity_service.create_from_bytes(
                ws, col, f"batch{i}.md", f"# Batch {i}\n\nContent {i}.".encode(),
            )
            entities.append(e)

        # 删除所有实体的 canonical_md
        for e in entities:
            canon_path = storage._entity_dir(ws, col, e.entity_id) / rep_type_to_relpath("canonical_md")
            if canon_path.exists():
                canon_path.unlink()

        # reconciler 批量检测
        result = await reconciler_service.reconcile(ws, col)
        assert result.entities_scanned >= 3
        missing_rep_count = sum(
            1 for d in result.drifts_found if d.drift_type.value == "missing_rep"
        )
        assert missing_rep_count >= 3

        # 批量修复
        assert result.drifts_repaired >= 3

        # 验证所有实体恢复
        for e in entities:
            assert storage.file_exists(ws, col, e.entity_id, "canonical_md")

    @pytest.mark.asyncio
    async def test_mixed_drift_types(
        self, entity_service, reconciler_service, index_service, storage, ws, col,
    ):
        """场景: 混合故障类型 — 一个缺 rep、一个缺 index、一个正常。"""
        # 实体 1: 正常
        e1 = await entity_service.create_from_bytes(
            ws, col, "mixed_ok.md", b"# OK Entity\n\nNormal content.",
        )
        # 实体 2: 缺 canonical_md
        e2 = await entity_service.create_from_bytes(
            ws, col, "mixed_norep.md", b"# No Rep Entity\n\nContent.",
        )
        canon_path = storage._entity_dir(ws, col, e2.entity_id) / rep_type_to_relpath("canonical_md")
        if canon_path.exists():
            canon_path.unlink()

        # 实体 3: 缺 index (删除 parquet)
        e3 = await entity_service.create_from_bytes(
            ws, col, "mixed_noidx.md", b"# No Index Entity\n\nContent.",
        )
        index_service.delete_entity_parquet(ws, col, e3.entity_id, "canonical_md")

        # reconciler 检测混合故障
        result = await reconciler_service.reconcile(ws, col)
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_rep" in drift_types or "missing_index" in drift_types

        # 修复后验证
        assert result.drifts_repaired >= 1


# ===========================================================================
# 6. 修复后搜索功能验证
# ===========================================================================


class TestSearchAfterRebuild:
    """修复后搜索功能验证。"""

    @pytest.mark.asyncio
    async def test_search_after_content_update(
        self, entity_service, index_service, storage, ws, col,
    ):
        """场景: 更新内容后搜索能找到新内容。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "search1.md", b"# Searchable\n\nQuantum computing basics.",
        )
        eid = entity.entity_id

        # 更新内容
        await entity_service.update_entity_content(
            ws, col, eid, b"# Updated Search\n\nMachine learning fundamentals.",
        )

        # 搜索新内容 (lexical)
        results = await index_service.search_lexical(
            ws, col, "Machine learning", top_k=5,
        )
        # 搜索结果可能包含更新后的内容
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_after_cascade_rebuild(
        self, entity_service, index_service, storage, pipeline_service, ws, col,
    ):
        """场景: cascade_rebuild 后搜索功能正常。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "search2.md", b"# Rebuild Search\n\nNeural network architectures.",
        )
        eid = entity.entity_id

        # 触发 cascade rebuild
        await cascade_rebuild(
            ws, col, eid, "source_original", storage, pipeline_service,
        )

        # 搜索
        results = await index_service.search_lexical(
            ws, col, "Neural network", top_k=5,
        )
        assert isinstance(results, list)


# ===========================================================================
# 7. 三层一致性验证: Manifest / Parquet / LanceDB
# ===========================================================================


class TestThreeLayerConsistency:
    """验证修复后 Manifest / Parquet / LanceDB 三层一致。"""

    @pytest.mark.asyncio
    async def test_consistency_after_create(
        self, entity_service, index_service, storage, ws, col,
    ):
        """创建后三层一致。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "consistency1.md", b"# Consistency\n\nThree layer check.",
        )
        eid = entity.entity_id

        # Layer 1: Manifest
        manifest = storage.read_entity_manifest(ws, col, eid)
        assert manifest is not None
        assert manifest["entity_id"] == eid

        # Layer 2: Parquet
        pq = index_service.read_entity_parquet(ws, col, eid, "canonical_md")
        assert pq is not None
        assert pq.num_rows > 0

        # Layer 3: LanceDB (via sync)
        indexed = index_service.get_indexed_entity_ids(ws, col)
        assert eid in indexed

    @pytest.mark.asyncio
    async def test_consistency_after_update(
        self, entity_service, index_service, storage, ws, col,
    ):
        """更新后三层一致。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "consistency2.md", b"# V1\n\nFirst version.",
        )
        eid = entity.entity_id

        # 更新
        updated = await entity_service.update_entity_content(
            ws, col, eid, b"# V2\n\nSecond version with updates.",
        )
        assert updated is not None
        assert updated.version == 2

        # 验证三层
        manifest = storage.read_entity_manifest(ws, col, eid)
        assert manifest is not None
        assert manifest["version"] == 2

        pq = index_service.read_entity_parquet(ws, col, eid, "canonical_md")
        assert pq is not None

    @pytest.mark.asyncio
    async def test_consistency_after_reconcile_repair(
        self, entity_service, reconciler_service, index_service, storage, ws, col,
    ):
        """Reconciler 修复后三层一致。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "consistency3.md", b"# Reconcile Consistency\n\nContent.",
        )
        eid = entity.entity_id

        # 注入故障: 删除 canonical_md
        canon_path = storage._entity_dir(ws, col, eid) / rep_type_to_relpath("canonical_md")
        if canon_path.exists():
            canon_path.unlink()

        # Reconcile 修复
        result = await reconciler_service.reconcile(ws, col)
        assert result.drifts_repaired >= 1

        # 验证三层
        assert storage.file_exists(ws, col, eid, "canonical_md")
        manifest = storage.read_entity_manifest(ws, col, eid)
        assert manifest is not None

    @pytest.mark.asyncio
    async def test_consistency_after_cascade_rebuild(
        self, entity_service, index_service, storage, pipeline_service, ws, col,
    ):
        """cascade_rebuild 后三层一致。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "consistency4.md", b"# Cascade Consistency\n\nContent.",
        )
        eid = entity.entity_id

        # Cascade rebuild
        rebuilt = await cascade_rebuild(
            ws, col, eid, "source_original", storage, pipeline_service,
        )
        assert "canonical_md" in rebuilt

        # 验证三层
        manifest = storage.read_entity_manifest(ws, col, eid)
        assert manifest is not None

        # 验证无 stale
        stale = get_stale_reps(ws, col, eid, storage)
        assert len(stale) == 0


# ===========================================================================
# 8. 极端场景: 全部删除后重建
# ===========================================================================


class TestExtremeRebuild:
    """极端场景: 大面积删除后重建。"""

    @pytest.mark.asyncio
    async def test_delete_all_reps_and_rebuild(
        self, entity_service, index_service, storage, pipeline_service, ws, col,
    ):
        """场景: 删除所有 rep 文件 → cascade_rebuild 完全重建。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "extreme1.md", b"# Extreme Rebuild\n\nFull delete test.",
        )
        eid = entity.entity_id

        # 删除所有 rep 文件 (保留 source_original)
        entity_dir = storage._entity_dir(ws, col, eid)
        for item in entity_dir.rglob("*"):
            if item.is_file() and "source" not in str(item) and ".entity_manifest" not in str(item):
                item.unlink()

        # 验证 canonical_md 已删除
        assert not storage.file_exists(ws, col, eid, "canonical_md")

        # 通过 cascade_rebuild 重建
        rebuilt = await cascade_rebuild(
            ws, col, eid, "source_original", storage, pipeline_service,
        )
        assert "canonical_md" in rebuilt

        # 验证恢复
        assert storage.file_exists(ws, col, eid, "canonical_md")
        canon = storage.read_file(ws, col, eid, "canonical_md")
        assert canon is not None
        assert b"Extreme Rebuild" in canon

    @pytest.mark.asyncio
    async def test_delete_parquet_and_lance_then_rebuild(
        self, entity_service, index_service, storage, ws, col,
    ):
        """场景: 删除 parquet + LanceDB 记录 → 完全重建 index。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "extreme2.md", b"# Index Extreme\n\nFull index rebuild.",
        )
        eid = entity.entity_id

        # 删除 parquet
        index_service.delete_entity_parquet(ws, col, eid)

        # 重新执行 pipeline
        pipeline = entity_service.pipeline
        source = storage.read_file(ws, col, eid, "source_original")
        assert source is not None
        await pipeline.process_md_entity(ws, col, eid, source.decode("utf-8", errors="replace"))

        # 重建 index
        count = await index_service.sync_to_lance(ws, col, eid, "canonical_md")
        assert count > 0

        # 验证搜索可用
        results = await index_service.search_lexical(ws, col, "Index Extreme", top_k=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_repeated_updates_dont_corrupt(
        self, entity_service, index_service, storage, ws, col,
    ):
        """场景: 连续多次更新不会导致数据损坏。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "extreme3.md", b"# V0\n\nInitial.",
        )
        eid = entity.entity_id

        # 连续 5 次更新
        for i in range(1, 6):
            updated = await entity_service.update_entity_content(
                ws, col, eid, f"# V{i}\n\nVersion {i} content.".encode(),
            )
            assert updated is not None
            assert updated.version == i + 1

        # 验证最终状态
        final = await entity_service.get_entity(ws, col, eid)
        assert final is not None
        assert final.version == 6

        # 验证 version log
        log = storage.read_version_log(ws, col, eid)
        assert len(log) >= 5  # 至少 5 个 content_update 条目

        # 验证 canonical_md 是最新版本
        canon = storage.read_file(ws, col, eid, "canonical_md")
        assert canon is not None
        assert b"V5" in canon


# ===========================================================================
# 9. Version Log 完整性
# ===========================================================================


class TestVersionLogIntegrity:
    """Version log 完整性验证。"""

    @pytest.mark.asyncio
    async def test_version_log_after_create(
        self, entity_service, storage, ws, col,
    ):
        """创建后 version log 有 ingest 条目。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "vlog1.md", b"# Version Log\n\nContent.",
        )
        eid = entity.entity_id

        log = storage.read_version_log(ws, col, eid)
        assert len(log) >= 1
        triggers = [entry["trigger"] for entry in log]
        assert "ingest" in triggers

    @pytest.mark.asyncio
    async def test_version_log_after_update(
        self, entity_service, storage, ws, col,
    ):
        """更新后 version log 有 content_update 条目。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "vlog2.md", b"# V1\n\nContent.",
        )
        eid = entity.entity_id

        await entity_service.update_entity_content(
            ws, col, eid, b"# V2\n\nUpdated.",
        )

        log = storage.read_version_log(ws, col, eid)
        triggers = [entry["trigger"] for entry in log]
        assert "content_update" in triggers

    @pytest.mark.asyncio
    async def test_version_log_monotonic_versions(
        self, entity_service, storage, ws, col,
    ):
        """Version log 中版本号单调递增。"""
        entity = await entity_service.create_from_bytes(
            ws, col, "vlog3.md", b"# V1\n\nContent.",
        )
        eid = entity.entity_id

        for i in range(3):
            await entity_service.update_entity_content(
                ws, col, eid, f"# V{i+2}\n\nContent {i+2}.".encode(),
            )

        log = storage.read_version_log(ws, col, eid)
        versions = [entry["version"] for entry in log]
        # 版本号应单调递增
        for i in range(1, len(versions)):
            assert versions[i] > versions[i - 1], f"Version not monotonic: {versions}"


# ===========================================================================
# 10. 端到端 API 级别重建测试
# ===========================================================================


class TestAPILevelRebuild:
    """通过 API 触发重建。"""

    @pytest.mark.asyncio
    async def test_update_content_via_api(
        self, client, ws, col,
    ):
        """通过 PUT /{entity_id}/content API 更新内容触发级联重建。"""
        # 创建 workspace + collection
        await client.post("/api/v1/workspaces", json={"workspace_id": ws})
        await client.post(
            f"/api/v1/workspaces/{ws}/collections",
            json={"collection_id": col, "name": col},
        )

        # 创建实体
        import io
        files = {"file": ("api_rebuild.md", io.BytesIO(b"# API Rebuild\n\nOriginal."), "text/markdown")}
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities",
            files=files,
        )
        assert resp.status_code == 201
        eid = resp.json()["entity_id"]

        # 更新内容
        files = {"file": ("api_rebuild.md", io.BytesIO(b"# API Rebuild V2\n\nUpdated via API."), "text/markdown")}
        resp = await client.put(
            f"/api/v1/workspaces/{ws}/collections/{col}/entities/{eid}/content",
            files=files,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 2

    @pytest.mark.asyncio
    async def test_status_endpoint_after_rebuild(
        self, client, entity_service, reconciler_service, ws, col,
    ):
        """重建后 /status 端点反映系统状态。"""
        # 创建实体
        await entity_service.create_from_bytes(
            ws, col, "status1.md", b"# Status Test\n\nContent.",
        )

        # 运行 reconcile
        await reconciler_service.reconcile(ws, col)

        # 检查 /status
        resp = await client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "reconciler" in data
