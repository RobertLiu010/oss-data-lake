"""Built-in pipeline step implementations.

RepSteps (§6.6.3): parse, render_page, ocr, transcribe, table_parse, ...
IndexSteps (§6.7.3): chunk_and_embed_text, build_vector_index, build_fts_index, ...
ProjectorSteps (§11.3): project_rag_api, project_wiki, ...
"""

from vector_lake.pipeline.steps.index_steps import register_builtin_index_steps
from vector_lake.pipeline.steps.projector_steps import register_builtin_projector_steps
from vector_lake.pipeline.steps.rep_steps import register_builtin_rep_steps


def register_all_builtin_steps() -> None:
    """Register all built-in pipeline steps (Rep + Index + Projector)."""
    register_builtin_rep_steps()
    register_builtin_index_steps()
    register_builtin_projector_steps()
