"""Chunking service – simplified from base_chunking.py.

No dependency on config.settings.Settings, src.application.exceptions, or
text_truncation.  Accepts configuration as simple kwargs and uses a
len(text)//4 token estimator.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import Settings
from app.models.chunk import Chunk, ChunkAnchor

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert heading text to a Markdown slug (lowercase, hyphens)."""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    return slug or "section"


def _make_anchor(header: str | None, level: int, start_pos: int) -> ChunkAnchor | None:
    """Create a ChunkAnchor from header metadata.

    Returns None if no header info is available.
    """
    if not header and start_pos == 0:
        return None
    slug = _slugify(header) if header else ""
    return ChunkAnchor(
        slug=slug,
        char_offset=start_pos,
    )


# =========================================================================
# Markdown splitter
# =========================================================================

class MarkdownSplitter:
    """Split Markdown text by headers."""

    @staticmethod
    def split_by_headers(text: str) -> list[dict[str, Any]]:
        if not text:
            return []

        header_pattern = r'^(#{1,6})\s+(.+?)\s*$'
        chunks: list[dict[str, Any]] = []
        lines = text.split('\n')
        current_chunk: list[str] = []
        current_header: str | None = None
        current_level = 0
        start_pos = 0

        for i, line in enumerate(lines):
            match = re.match(header_pattern, line)
            if match:
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'header': current_header,
                        'level': current_level,
                        'start_pos': start_pos,
                        'is_header': False,
                    })
                current_chunk = [line]
                current_header = match.group(2).strip()
                current_level = len(match.group(1))
                start_pos = sum(len(line_) + 1 for line_ in lines[:i])
            else:
                current_chunk.append(line)

        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'header': current_header,
                'level': current_level,
                'start_pos': start_pos,
                'is_header': False,
            })

        return chunks


# =========================================================================
# Table detector
# =========================================================================

class TableDetector:
    """Detect Markdown tables."""

    @staticmethod
    def find_tables(text: str) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        lines = text.split('\n')
        in_table = False
        table_start = -1
        table_lines: list[str] = []

        for i, line in enumerate(lines):
            is_table_line = '|' in line
            if is_table_line and not in_table:
                in_table = True
                table_start = i
                table_lines = [line]
            elif is_table_line and in_table:
                table_lines.append(line)
            elif not is_table_line and in_table:
                tables.append({
                    'start': table_start,
                    'end': i - 1,
                    'content': '\n'.join(table_lines),
                })
                in_table = False
                table_lines = []

        if in_table and table_lines:
            tables.append({
                'start': table_start,
                'end': len(lines) - 1,
                'content': '\n'.join(table_lines),
            })

        return tables

    @staticmethod
    def is_inside_table(pos: int, tables: list[dict[str, Any]]) -> bool:
        for table in tables:
            if table['start'] <= pos <= table['end']:
                return True
        return False


# =========================================================================
# Center-priority truncation (replaces truncate_text_from_sides)
# =========================================================================

def _truncate_center(text: str, max_length: int) -> str:
    """Truncate text from both sides, keeping the center portion."""
    if len(text) <= max_length:
        return text
    # Keep the center portion
    start = (len(text) - max_length) // 2
    return text[start:start + max_length]


# =========================================================================
# Chunking service
# =========================================================================

class ChunkingService:
    """Simplified chunking with sliding-window, no external tokenizer."""

    def __init__(self, settings: Settings):
        self.chunk_tokens = settings.chunking.chunk_tokens
        self.window_size = settings.chunking.window_size
        self.max_window_length = settings.chunking.max_window_length
        self.target_max_length = settings.chunking.target_max_length
        self.max_table_length = settings.chunking.max_table_length

        # Ensure window size is odd
        if self.window_size % 2 == 0:
            self.window_size += 1
            logger.info("Window size adjusted to odd: %d", self.window_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        markdown_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Execute chunking pipeline: split → token-chunk → sliding-window."""
        if metadata is None:
            metadata = {}

        logger.info(
            "Starting text chunking: content_length=%d",
            len(markdown_content),
        )

        # Step 1: split by headers
        header_chunks = self._split_by_headers(markdown_content)
        logger.info("Header splitting complete: %d chunks", len(header_chunks))

        # Step 2: detect tables (for boundary awareness)
        tables = TableDetector.find_tables(markdown_content)
        logger.info("Detected %d tables", len(tables))

        # Step 3: split by token threshold
        token_chunks = self._split_by_tokens(header_chunks, tables)
        logger.info("Token splitting complete: %d chunks", len(token_chunks))

        # Step 4: sliding window
        window_chunks = self._apply_sliding_window(token_chunks, metadata)
        logger.info("Sliding window complete: %d windows", len(window_chunks))

        return window_chunks

    # ------------------------------------------------------------------
    # Token counting (simple estimation)
    # ------------------------------------------------------------------

    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(text) // 4

    # ------------------------------------------------------------------
    # Splitting helpers
    # ------------------------------------------------------------------

    def _split_by_headers(self, text: str) -> list[dict[str, Any]]:
        return MarkdownSplitter.split_by_headers(text)

    def _split_by_tokens(
        self,
        header_chunks: list[dict[str, Any]],
        _tables: list[dict[str, Any]],
    ) -> list[Chunk]:
        chunks: list[Chunk] = []

        for chunk_data in header_chunks:
            text = chunk_data['text']
            start_pos = chunk_data['start_pos']
            header = chunk_data.get('header', '')
            level = chunk_data.get('level', 0)

            token_count = self._count_tokens(text)
            if token_count <= self.chunk_tokens:
                chunks.append(Chunk(
                    text=text,
                    start_pos=start_pos,
                    end_pos=start_pos + len(text),
                    token_count=token_count,
                    chunk_chars=len(text),
                    anchor=_make_anchor(header, level, start_pos),
                    metadata={
                        'header': header,
                        'level': level,
                        'chunk_type': 'header_chunk',
                    },
                ))
                continue

            # Need further splitting
            paragraphs = self._split_by_paragraphs(text)
            current_chunk: list[dict[str, Any]] = []
            current_tokens = 0

            for para in paragraphs:
                para_text = para['text']
                para_tokens = self._count_tokens(para_text)

                if para_tokens > self.chunk_tokens:
                    # Flush current
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk, start_pos, header, level,
                            chunk_type='paragraph_split',
                        ))
                        current_chunk = []
                        current_tokens = 0
                    # Force-split long paragraph
                    split_chunks = self._split_long_paragraph(
                        para_text,
                        start_pos + para['start_pos'],
                        header,
                        level,
                    )
                    chunks.extend(split_chunks)

                elif current_tokens + para_tokens <= self.chunk_tokens:
                    current_chunk.append({
                        'text': para_text,
                        'start_pos': start_pos + para['start_pos'],
                    })
                    current_tokens += para_tokens

                else:
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk, start_pos, header, level,
                            chunk_type='paragraph_group',
                        ))
                    current_chunk = [{
                        'text': para_text,
                        'start_pos': start_pos + para['start_pos'],
                    }]
                    current_tokens = para_tokens

            if current_chunk:
                chunks.append(self._create_chunk(
                    current_chunk, start_pos, header, level,
                    chunk_type='paragraph_group',
                ))

        return chunks

    def _split_by_paragraphs(self, text: str) -> list[dict[str, Any]]:
        paragraphs: list[dict[str, Any]] = []
        lines = text.split('\n')
        current_paragraph: list[str] = []
        current_start = 0

        for i, line in enumerate(lines):
            if line.strip():
                if not current_paragraph:
                    current_start = i
                current_paragraph.append(line)
            else:
                if current_paragraph:
                    paragraphs.append({
                        'text': '\n'.join(current_paragraph),
                        'start_pos': current_start,
                    })
                    current_paragraph = []

        if current_paragraph:
            paragraphs.append({
                'text': '\n'.join(current_paragraph),
                'start_pos': current_start,
            })

        return paragraphs

    def _split_long_paragraph(
        self,
        text: str,
        start_pos: int,
        header: str,
        level: int,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        sentences = re.split(r'([。！？.!?]+)', text)

        current_parts: list[str] = []
        current_tokens = 0

        for i in range(0, len(sentences), 2):
            sentence = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else '')
            sentence_tokens = self._count_tokens(sentence)

            if current_tokens + sentence_tokens <= self.chunk_tokens:
                current_parts.append(sentence)
                current_tokens += sentence_tokens
            else:
                if current_parts:
                    chunk_text = ''.join(current_parts)
                    chunks.append(Chunk(
                        text=chunk_text,
                        start_pos=start_pos,
                        end_pos=start_pos + len(chunk_text),
                        token_count=current_tokens,
                        chunk_chars=len(chunk_text),
                        anchor=_make_anchor(header, level, start_pos),
                        metadata={
                            'header': header,
                            'level': level,
                            'chunk_type': 'forced_split',
                            'is_truncated': True,
                        },
                    ))
                    start_pos += len(chunk_text)
                # Single sentence too long – hard cut
                if sentence_tokens > self.chunk_tokens:
                    chunk_size = self.chunk_tokens * 4
                    chunk_text = sentence[:chunk_size]
                    chunks.append(Chunk(
                        text=chunk_text,
                        start_pos=start_pos,
                        end_pos=start_pos + len(chunk_text),
                        token_count=self._count_tokens(chunk_text),
                        chunk_chars=len(chunk_text),
                        anchor=_make_anchor(header, level, start_pos),
                        metadata={
                            'header': header,
                            'level': level,
                            'chunk_type': 'forced_split',
                            'is_truncated': True,
                        },
                    ))
                    remaining = sentence[chunk_size:]
                    if remaining:
                        chunks.append(Chunk(
                            text=remaining,
                            start_pos=start_pos + len(chunk_text),
                            end_pos=start_pos + len(chunk_text) + len(remaining),
                            token_count=self._count_tokens(remaining),
                            chunk_chars=len(remaining),
                            anchor=_make_anchor(header, level, start_pos + len(chunk_text)),
                            metadata={
                                'header': header,
                                'level': level,
                                'chunk_type': 'forced_split',
                                'is_truncated': True,
                            },
                        ))
                    current_parts = []
                    current_tokens = 0
                else:
                    current_parts = [sentence]
                    current_tokens = sentence_tokens

        if current_parts:
            chunk_text = ''.join(current_parts)
            chunks.append(Chunk(
                text=chunk_text,
                start_pos=start_pos,
                end_pos=start_pos + len(chunk_text),
                token_count=current_tokens,
                chunk_chars=len(chunk_text),
                anchor=_make_anchor(header, level, start_pos),
                metadata={
                    'header': header,
                    'level': level,
                    'chunk_type': 'forced_split',
                },
            ))

        return chunks

    def _create_chunk(
        self,
        text_parts: list[dict[str, Any]],
        _base_start_pos: int,
        header: str,
        level: int,
        chunk_type: str,
    ) -> Chunk:
        text = '\n\n'.join(p['text'] for p in text_parts)
        start_pos = text_parts[0]['start_pos']
        token_count = sum(self._count_tokens(p['text']) for p in text_parts)
        chunk_chars = sum(len(p['text']) for p in text_parts)
        return Chunk(
            text=text,
            start_pos=start_pos,
            end_pos=start_pos + len(text),
            token_count=token_count,
            chunk_chars=chunk_chars,
            anchor=_make_anchor(header, level, start_pos),
            metadata={
                'header': header,
                'level': level,
                'chunk_type': chunk_type,
            },
        )

    # ------------------------------------------------------------------
    # Sliding window
    # ------------------------------------------------------------------

    def _get_chunk_window_text(self, chunk: Chunk) -> str:
        return chunk.embedding_text or chunk.text

    def _apply_sliding_window(
        self,
        chunks: list[Chunk],
        metadata: dict[str, Any],
    ) -> list[Chunk]:
        if not chunks:
            return []

        half_window = self.window_size // 2
        windowed_chunks: list[Chunk] = []

        for i, chunk in enumerate(chunks):
            start_idx = max(0, i - half_window)
            end_idx = min(len(chunks), i + half_window + 1)
            window_chunks = chunks[start_idx:end_idx]

            # Compute window length
            window_length = sum(len(self._get_chunk_window_text(c)) for c in window_chunks)
            window_length += 2 * (len(window_chunks) - 1)  # \n\n separators

            if window_length > self.max_window_length:
                window_chunks = self._truncate_window_chunks(window_chunks, i - start_idx)

            window_text = '\n\n'.join(self._get_chunk_window_text(c) for c in window_chunks)

            windowed_chunk = chunk.model_copy(update={
                'embedding_text': window_text,
                'metadata': {
                    **chunk.metadata,
                    'window_size': len(window_chunks),
                    'window_index': i,
                    'target_chunk_index': i,
                    'chunk_index': i,
                    'embedding_text_chars': len(window_text),
                    **metadata,
                },
            })
            windowed_chunks.append(windowed_chunk)

        return windowed_chunks

    def _truncate_window_chunks(
        self,
        window_chunks: list[Chunk],
        target_chunk_index: int,
    ) -> list[Chunk]:
        """Center-priority window truncation."""
        if not window_chunks:
            return []

        separator_length = len('\n\n')
        target_chunk = window_chunks[target_chunk_index]
        target_text = self._get_chunk_window_text(target_chunk)

        # If the target itself exceeds the limit, truncate it
        if len(target_text) >= self.max_window_length:
            truncated = _truncate_center(target_text, self.max_window_length)
            update_fields: dict[str, Any] = {
                'token_count': self._count_tokens(truncated),
            }
            if target_chunk.embedding_text:
                update_fields['embedding_text'] = truncated
            else:
                update_fields['text'] = truncated
                update_fields['chunk_chars'] = len(truncated)
            return [target_chunk.model_copy(update=update_fields)]

        # Expand outward from the center
        left_bound = target_chunk_index
        right_bound = target_chunk_index
        current_length = len(target_text)
        left_blocked = False
        right_blocked = False
        max_distance = max(target_chunk_index, len(window_chunks) - target_chunk_index - 1)

        for distance in range(1, max_distance + 1):
            candidates: list[tuple[str, int]] = []
            left_index = target_chunk_index - distance
            right_index = target_chunk_index + distance

            if left_index >= 0 and not left_blocked:
                candidates.append(('left', left_index))
            if right_index < len(window_chunks) and not right_blocked:
                candidates.append(('right', right_index))

            candidates.sort(key=lambda item: len(window_chunks[item[1]].text))

            for side, candidate_index in candidates:
                candidate = window_chunks[candidate_index]
                candidate_length = len(self._get_chunk_window_text(candidate)) + separator_length

                if current_length + candidate_length <= self.max_window_length:
                    current_length += candidate_length
                    if side == 'left':
                        left_bound = candidate_index
                    else:
                        right_bound = candidate_index
                elif side == 'left':
                    left_blocked = True
                else:
                    right_blocked = True

            if left_blocked and right_blocked:
                break

        return window_chunks[left_bound:right_bound + 1]
