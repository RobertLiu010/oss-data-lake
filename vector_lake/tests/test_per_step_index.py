"""Tests for per-step indexing feature.

Key concepts:
- RepStep protocol has an `index_mode` field: str | None
- StepResult dataclass has an `indexable_text: str | None` field
- PipelineService._index_step_output() indexes a step's output independently
- PipelineService._execute_step_pipeline() checks each step's index_mode
  and calls _index_step_output() for non-final steps with index_mode set
- The final step's output is always indexed by the main pipeline (not per-step)
"""

from __future__ import annotations

import os

os.environ["EMBEDDING_MOCK"] = "1"

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.services.pipeline import PipelineService
from app.services.registry import (
    StepContext,
    StepResult,
    TemplateRegistry,
)

# ---------------------------------------------------------------------------
# Mock step implementations
# ---------------------------------------------------------------------------


@dataclass
class TextStep:
    """Step with index_mode='text': raw → text, adds a prefix."""

    name: str = "text_step"
    input_format: str = "raw"
    output_format: str = "text"
    index_mode: str | None = "text"
    required_input_reps: list[str] = field(default_factory=lambda: ["source_original"])
    output_reps: list[str] = field(default_factory=lambda: ["rep_text"])

    async def transform(self, ctx: StepContext) -> StepResult:
        original = ctx.input_content.decode("utf-8", errors="replace")
        result_text = f"[TEXT] {original}"
        return StepResult(
            content=result_text.encode("utf-8"),
            output_format=self.output_format,
            indexable_text=result_text,
        )


@dataclass
class LexicalStep:
    """Step with index_mode='lexical': text → md, transforms text."""

    name: str = "lexical_step"
    input_format: str = "text"
    output_format: str = "md"
    index_mode: str | None = "lexical"
    required_input_reps: list[str] = field(default_factory=lambda: ["rep_text"])
    output_reps: list[str] = field(default_factory=lambda: ["canonical_md"])

    async def transform(self, ctx: StepContext) -> StepResult:
        original = ctx.input_content.decode("utf-8", errors="replace")
        result_text = f"# Lexical\n{original}"
        return StepResult(
            content=result_text.encode("utf-8"),
            output_format=self.output_format,
            indexable_text=result_text,
        )


@dataclass
class NoIndexStep:
    """Step with index_mode=None: raw → mid, transforms text."""

    name: str = "no_index_step"
    input_format: str = "raw"
    output_format: str = "mid"
    index_mode: str | None = None
    required_input_reps: list[str] = field(default_factory=lambda: ["source_original"])
    output_reps: list[str] = field(default_factory=lambda: ["rep_mid"])

    async def transform(self, ctx: StepContext) -> StepResult:
        original = ctx.input_content.decode("utf-8", errors="replace")
        result_text = f"[NOINDEX] {original}"
        return StepResult(
            content=result_text.encode("utf-8"),
            output_format=self.output_format,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_registry() -> TemplateRegistry:
    """Provide a fresh TemplateRegistry for each test."""
    return TemplateRegistry()


@pytest_asyncio.fixture
async def pipeline_with_registry(
    storage,
    chunking_service,
    embedding_service,
    index_service,
    settings,
    event_bus,
    fresh_registry,
):
    """PipelineService wired to a fresh TemplateRegistry."""
    return PipelineService(
        storage=storage,
        chunking=chunking_service,
        embedding=embedding_service,
        index=index_service,
        settings=settings,
        event_bus=event_bus,
        template_registry=fresh_registry,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStepResultIndexableText:
    """1. StepResult with indexable_text field."""

    def test_indexable_text_default_none(self):
        result = StepResult(content=b"hello", output_format="text")
        assert result.indexable_text is None

    def test_indexable_text_set(self):
        result = StepResult(
            content=b"hello",
            output_format="text",
            indexable_text="hello world",
        )
        assert result.indexable_text == "hello world"

    def test_indexable_text_empty_string(self):
        result = StepResult(
            content=b"hello",
            output_format="text",
            indexable_text="",
        )
        assert result.indexable_text == ""


class TestStepIndexModeInListSteps:
    """2. list_steps includes index_mode."""

    def test_list_steps_includes_index_mode(self, fresh_registry):
        fresh_registry.register_step(TextStep())
        fresh_registry.register_step(LexicalStep())
        fresh_registry.register_step(NoIndexStep())

        steps = fresh_registry.list_steps()
        assert len(steps) == 3

        by_name = {s["name"]: s for s in steps}

        assert by_name["text_step"]["index_mode"] == "text"
        assert by_name["lexical_step"]["index_mode"] == "lexical"
        assert by_name["no_index_step"]["index_mode"] is None

    def test_list_steps_includes_all_fields(self, fresh_registry):
        fresh_registry.register_step(TextStep())
        steps = fresh_registry.list_steps()
        assert len(steps) == 1
        step = steps[0]
        assert "name" in step
        assert "input_format" in step
        assert "output_format" in step
        assert "index_mode" in step


class TestPerStepIndexTextMode:
    """3. A step with index_mode='text' gets its output indexed during pipeline execution."""

    @pytest.mark.asyncio
    async def test_text_step_gets_indexed(self, pipeline_with_registry, fresh_registry):
        fresh_registry.register_step(TextStep())
        fresh_registry.register_extension_format(".raw", "raw")

        # We need a 2-step pipeline so TextStep is NOT the final step.
        # TextStep: raw → text, then we need a step: text → md
        @dataclass
        class FinalMdStep:
            name: str = "final_md"
            input_format: str = "text"
            output_format: str = "md"
            index_mode: str | None = None
            required_input_reps: list[str] = field(default_factory=lambda: ["rep_text"])
            output_reps: list[str] = field(default_factory=lambda: ["canonical_md"])

            async def transform(self, ctx: StepContext) -> StepResult:
                original = ctx.input_content.decode("utf-8", errors="replace")
                return StepResult(
                    content=original.encode("utf-8"),
                    output_format=self.output_format,
                )

        fresh_registry.register_step(FinalMdStep())

        # Register a vector_index template so the main pipeline can index
        from app.services.registry import IndexContext

        class FakeIndexTemplate:
            name = "vector_index"
            index_type = "vector"

            async def build(self, ctx: IndexContext) -> None:
                pass

            async def search(self, ctx):
                return []

        fresh_registry.register_index(FakeIndexTemplate())

        # Spy on _index_step_output
        with patch.object(
            pipeline_with_registry,
            "_index_step_output",
            new=AsyncMock(return_value=True),
        ) as mock_index:
            _result = await pipeline_with_registry.process_entity(
                workspace_id="ws",
                collection_id="col",
                entity_id="ent1",
                filename="test.raw",
                source_content=b"hello world",
            )

            # _index_step_output should have been called for the TextStep (step 0)
            mock_index.assert_called_once()
            call_args = mock_index.call_args
            step_result_arg = call_args[0][3]  # 4th positional arg
            assert isinstance(step_result_arg, StepResult)
            assert step_result_arg.indexable_text is not None
            assert "[TEXT]" in step_result_arg.indexable_text


class TestPerStepIndexLexicalMode:
    """4. A step with index_mode='lexical' gets FTS-only indexing."""

    @pytest.mark.asyncio
    async def test_lexical_step_fts_only(self, pipeline_with_registry, fresh_registry):
        # Build a 3-step pipeline: raw → text → mid → md
        # so LexicalStep (text → mid) is NOT the final step.
        @dataclass
        class RawToTextStep:
            name: str = "raw_to_text"
            input_format: str = "raw"
            output_format: str = "text"
            index_mode: str | None = None
            required_input_reps: list[str] = field(default_factory=lambda: ["source_original"])
            output_reps: list[str] = field(default_factory=lambda: ["rep_text"])

            async def transform(self, ctx: StepContext) -> StepResult:
                return StepResult(
                    content=ctx.input_content,
                    output_format=self.output_format,
                )

        @dataclass
        class LexicalMidStep:
            name: str = "lexical_mid"
            input_format: str = "text"
            output_format: str = "mid"
            index_mode: str | None = "lexical"
            required_input_reps: list[str] = field(default_factory=lambda: ["rep_text"])
            output_reps: list[str] = field(default_factory=lambda: ["rep_mid"])

            async def transform(self, ctx: StepContext) -> StepResult:
                original = ctx.input_content.decode("utf-8", errors="replace")
                result_text = f"# Lexical\n{original}"
                return StepResult(
                    content=result_text.encode("utf-8"),
                    output_format=self.output_format,
                    indexable_text=result_text,
                )

        @dataclass
        class MidToMdStep:
            name: str = "mid_to_md"
            input_format: str = "mid"
            output_format: str = "md"
            index_mode: str | None = None
            required_input_reps: list[str] = field(default_factory=lambda: ["rep_mid"])
            output_reps: list[str] = field(default_factory=lambda: ["canonical_md"])

            async def transform(self, ctx: StepContext) -> StepResult:
                return StepResult(
                    content=ctx.input_content,
                    output_format=self.output_format,
                )

        fresh_registry.register_step(RawToTextStep())
        fresh_registry.register_step(LexicalMidStep())
        fresh_registry.register_step(MidToMdStep())
        fresh_registry.register_extension_format(".raw", "raw")

        # Register index template
        from app.services.registry import IndexContext

        class FakeIndexTemplate:
            name = "vector_index"
            index_type = "vector"

            async def build(self, ctx: IndexContext) -> None:
                pass

            async def search(self, ctx):
                return []

        fresh_registry.register_index(FakeIndexTemplate())

        # Spy on _index_step_output
        with patch.object(
            pipeline_with_registry,
            "_index_step_output",
            new=AsyncMock(return_value=True),
        ) as mock_index:
            _result = await pipeline_with_registry.process_entity(
                workspace_id="ws",
                collection_id="col",
                entity_id="ent2",
                filename="test.raw",
                source_content=b"lexical content",
            )

            # _index_step_output should have been called for LexicalMidStep (step 1, not final)
            mock_index.assert_called_once()
            call_args = mock_index.call_args
            # Positional: (workspace_id, collection_id, entity_id, step_result, rep_name, index_mode)
            assert call_args[0][5] == "lexical"


class TestPerStepIndexNoneMode:
    """5. A step with index_mode=None does NOT get per-step indexed."""

    @pytest.mark.asyncio
    async def test_none_mode_not_indexed(self, pipeline_with_registry, fresh_registry):
        fresh_registry.register_step(NoIndexStep())
        fresh_registry.register_extension_format(".raw", "raw")

        # Need a step: mid → md for the pipeline to resolve
        @dataclass
        class MidToMdStep:
            name: str = "mid_to_md"
            input_format: str = "mid"
            output_format: str = "md"
            index_mode: str | None = None
            required_input_reps: list[str] = field(default_factory=lambda: ["rep_mid"])
            output_reps: list[str] = field(default_factory=lambda: ["canonical_md"])

            async def transform(self, ctx: StepContext) -> StepResult:
                return StepResult(
                    content=ctx.input_content,
                    output_format=self.output_format,
                )

        fresh_registry.register_step(MidToMdStep())

        # Register index template
        from app.services.registry import IndexContext

        class FakeIndexTemplate:
            name = "vector_index"
            index_type = "vector"

            async def build(self, ctx: IndexContext) -> None:
                pass

            async def search(self, ctx):
                return []

        fresh_registry.register_index(FakeIndexTemplate())

        with patch.object(
            pipeline_with_registry,
            "_index_step_output",
            new=AsyncMock(return_value=True),
        ) as mock_index:
            _result = await pipeline_with_registry.process_entity(
                workspace_id="ws",
                collection_id="col",
                entity_id="ent3",
                filename="test.raw",
                source_content=b"no index content",
            )

            # _index_step_output should NOT have been called
            # because NoIndexStep has index_mode=None and MidToMdStep is final
            mock_index.assert_not_called()


class TestPerStepIndexNoIndexableText:
    """6. Step with index_mode='text' but no indexable_text falls back to content.decode()."""

    @pytest.mark.asyncio
    async def test_fallback_to_content_decode(self, pipeline_with_registry, fresh_registry):
        @dataclass
        class TextNoIndexableStep:
            """Step with index_mode='text' but no indexable_text in StepResult."""

            name: str = "text_no_idx"
            input_format: str = "raw"
            output_format: str = "text"
            index_mode: str | None = "text"
            required_input_reps: list[str] = field(default_factory=lambda: ["source_original"])
            output_reps: list[str] = field(default_factory=lambda: ["rep_text"])

            async def transform(self, ctx: StepContext) -> StepResult:
                # Return StepResult WITHOUT indexable_text
                return StepResult(
                    content=b"fallback content from bytes",
                    output_format=self.output_format,
                    # indexable_text is None (default)
                )

        @dataclass
        class FinalMdStep:
            name: str = "final_md"
            input_format: str = "text"
            output_format: str = "md"
            index_mode: str | None = None
            required_input_reps: list[str] = field(default_factory=lambda: ["rep_text"])
            output_reps: list[str] = field(default_factory=lambda: ["canonical_md"])

            async def transform(self, ctx: StepContext) -> StepResult:
                return StepResult(
                    content=ctx.input_content,
                    output_format=self.output_format,
                )

        fresh_registry.register_step(TextNoIndexableStep())
        fresh_registry.register_step(FinalMdStep())
        fresh_registry.register_extension_format(".raw", "raw")

        # Register index template
        from app.services.registry import IndexContext

        class FakeIndexTemplate:
            name = "vector_index"
            index_type = "vector"

            async def build(self, ctx: IndexContext) -> None:
                pass

            async def search(self, ctx):
                return []

        fresh_registry.register_index(FakeIndexTemplate())

        # Call _index_step_output directly to verify fallback behavior
        step_result = StepResult(
            content=b"fallback content from bytes",
            output_format="text",
            # indexable_text is None
        )

        indexed = await pipeline_with_registry._index_step_output(
            workspace_id="ws",
            collection_id="col",
            entity_id="ent4",
            step_result=step_result,
            rep_name="rep_text",
            index_mode="text",
        )

        # Should succeed — falls back to content.decode()
        assert indexed is True


class TestPerStepIndexEmptyText:
    """7. Step with empty indexable_text is skipped."""

    @pytest.mark.asyncio
    async def test_empty_indexable_text_skipped(self, pipeline_with_registry, fresh_registry):
        step_result = StepResult(
            content=b"",
            output_format="text",
            indexable_text="   ",  # whitespace only
        )

        indexed = await pipeline_with_registry._index_step_output(
            workspace_id="ws",
            collection_id="col",
            entity_id="ent5",
            step_result=step_result,
            rep_name="rep_text",
            index_mode="text",
        )

        # Should be skipped because text is empty after strip()
        assert indexed is False

    @pytest.mark.asyncio
    async def test_empty_string_indexable_text_skipped(self, pipeline_with_registry, fresh_registry):
        step_result = StepResult(
            content=b"some content",
            output_format="text",
            indexable_text="",
        )

        indexed = await pipeline_with_registry._index_step_output(
            workspace_id="ws",
            collection_id="col",
            entity_id="ent6",
            step_result=step_result,
            rep_name="rep_text",
            index_mode="text",
        )

        # Empty string should be skipped
        assert indexed is False


class TestPerStepIndexEmbeddingFailure:
    """8. Per-step indexing gracefully handles embedding failure."""

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_false(self, pipeline_with_registry, fresh_registry):
        step_result = StepResult(
            content=b"some text content",
            output_format="text",
            indexable_text="some text content for embedding",
        )

        # Mock the embedding service to raise an exception
        pipeline_with_registry.embedding = AsyncMock()
        pipeline_with_registry.embedding.embed_passages.side_effect = RuntimeError("Embedding service down")

        indexed = await pipeline_with_registry._index_step_output(
            workspace_id="ws",
            collection_id="col",
            entity_id="ent7",
            step_result=step_result,
            rep_name="rep_text",
            index_mode="text",
        )

        # Should return False gracefully, not raise
        assert indexed is False

    @pytest.mark.asyncio
    async def test_lexical_index_failure_returns_false(self, pipeline_with_registry, fresh_registry):
        step_result = StepResult(
            content=b"some text content",
            output_format="text",
            indexable_text="some text content for lexical",
        )

        # Mock the index service to raise an exception
        pipeline_with_registry.index = AsyncMock()
        pipeline_with_registry.index.upsert_chunks.side_effect = RuntimeError("Index service down")

        indexed = await pipeline_with_registry._index_step_output(
            workspace_id="ws",
            collection_id="col",
            entity_id="ent8",
            step_result=step_result,
            rep_name="rep_text",
            index_mode="lexical",
        )

        # Should return False gracefully, not raise
        assert indexed is False


class TestPerStepIndexMetadata:
    """9. intermediate_reps metadata includes index_mode and indexed fields."""

    @pytest.mark.asyncio
    async def test_metadata_includes_index_mode_and_indexed(self, pipeline_with_registry, fresh_registry):
        fresh_registry.register_step(TextStep())
        fresh_registry.register_extension_format(".raw", "raw")

        @dataclass
        class FinalMdStep:
            name: str = "final_md"
            input_format: str = "text"
            output_format: str = "md"
            index_mode: str | None = None
            required_input_reps: list[str] = field(default_factory=lambda: ["rep_text"])
            output_reps: list[str] = field(default_factory=lambda: ["canonical_md"])

            async def transform(self, ctx: StepContext) -> StepResult:
                return StepResult(
                    content=ctx.input_content,
                    output_format=self.output_format,
                )

        fresh_registry.register_step(FinalMdStep())

        # Register index template
        from app.services.registry import IndexContext

        class FakeIndexTemplate:
            name = "vector_index"
            index_type = "vector"

            async def build(self, ctx: IndexContext) -> None:
                pass

            async def search(self, ctx):
                return []

        fresh_registry.register_index(FakeIndexTemplate())

        # Patch _index_step_output to return True
        with patch.object(
            pipeline_with_registry,
            "_index_step_output",
            new=AsyncMock(return_value=True),
        ):
            canonical_text, metadata = await pipeline_with_registry._execute_step_pipeline(
                workspace_id="ws",
                collection_id="col",
                entity_id="ent9",
                source_content=b"metadata test",
                pipeline=fresh_registry.resolve_pipeline("raw"),
            )

        # Check intermediate_reps metadata
        reps = metadata["intermediate_reps"]
        assert len(reps) == 2

        # Step 0: TextStep with index_mode="text"
        step0_meta = reps[0]
        assert step0_meta["step"] == "text_step"
        assert step0_meta["index_mode"] == "text"
        assert step0_meta["indexed"] is True
        assert step0_meta["rep_name"] == "rep_text"
        assert step0_meta["step_index"] == 0

        # Step 1: FinalMdStep with index_mode=None (final step, not per-step indexed)
        step1_meta = reps[1]
        assert step1_meta["step"] == "final_md"
        assert step1_meta["index_mode"] is None
        assert step1_meta["indexed"] is False
        assert step1_meta["rep_name"] == "canonical_md"
        assert step1_meta["step_index"] == 1


class TestFullPipelineWithPerStepIndex:
    """10. End-to-end: 2-step pipeline where step 0 has index_mode='text'
    and step 1 (final) has index_mode='text', verify both get indexed."""

    @pytest.mark.asyncio
    async def test_both_steps_indexed(self, pipeline_with_registry, fresh_registry):
        @dataclass
        class Step0Text:
            name: str = "step0_text"
            input_format: str = "raw"
            output_format: str = "text"
            index_mode: str | None = "text"
            required_input_reps: list[str] = field(default_factory=lambda: ["source_original"])
            output_reps: list[str] = field(default_factory=lambda: ["rep_text"])

            async def transform(self, ctx: StepContext) -> StepResult:
                original = ctx.input_content.decode("utf-8", errors="replace")
                result_text = f"[STEP0] {original}"
                return StepResult(
                    content=result_text.encode("utf-8"),
                    output_format=self.output_format,
                    indexable_text=result_text,
                )

        @dataclass
        class Step1FinalText:
            name: str = "step1_final"
            input_format: str = "text"
            output_format: str = "md"
            index_mode: str | None = "text"
            required_input_reps: list[str] = field(default_factory=lambda: ["rep_text"])
            output_reps: list[str] = field(default_factory=lambda: ["canonical_md"])

            async def transform(self, ctx: StepContext) -> StepResult:
                original = ctx.input_content.decode("utf-8", errors="replace")
                result_text = f"[STEP1] {original}"
                return StepResult(
                    content=result_text.encode("utf-8"),
                    output_format=self.output_format,
                    indexable_text=result_text,
                )

        fresh_registry.register_step(Step0Text())
        fresh_registry.register_step(Step1FinalText())
        fresh_registry.register_extension_format(".raw", "raw")

        # Register index template — track build() calls for the final step
        from app.services.registry import IndexContext

        index_build_calls = []

        class FakeIndexTemplate:
            name = "vector_index"
            index_type = "vector"

            async def build(self, ctx: IndexContext) -> None:
                index_build_calls.append(ctx)

            async def search(self, ctx):
                return []

        fresh_registry.register_index(FakeIndexTemplate())

        # Track calls to _index_step_output
        per_step_index_calls = []

        original_index_step_output = pipeline_with_registry._index_step_output

        async def tracking_index_step_output(*args, **kwargs):
            per_step_index_calls.append((args, kwargs))
            return await original_index_step_output(*args, **kwargs)

        with patch.object(
            pipeline_with_registry,
            "_index_step_output",
            side_effect=tracking_index_step_output,
        ):
            result = await pipeline_with_registry.process_entity(
                workspace_id="ws",
                collection_id="col",
                entity_id="ent10",
                filename="test.raw",
                source_content=b"full pipeline test",
            )

        # Step 0 should have been per-step indexed (it's not the final step)
        assert len(per_step_index_calls) == 1
        step_result_arg = per_step_index_calls[0][0][3]
        assert isinstance(step_result_arg, StepResult)
        assert "[STEP0]" in step_result_arg.indexable_text
        # index_mode for step 0
        assert per_step_index_calls[0][0][5] == "text"

        # The final step (step 1) is indexed by the main pipeline via IndexTemplate.build(),
        # NOT via _index_step_output. Verify IndexTemplate.build() was called.
        assert len(index_build_calls) == 1
        idx_ctx = index_build_calls[0]
        assert isinstance(idx_ctx, IndexContext)
        assert len(idx_ctx.chunks) > 0
        # Each chunk from the main pipeline should have an embedding
        for chunk_item in idx_ctx.chunks:
            assert "embedding" in chunk_item
            assert "text" in chunk_item

        # Verify we got chunks back from the pipeline
        assert len(result) > 0
