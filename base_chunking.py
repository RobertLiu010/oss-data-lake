#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chunking With Sliding Window Use Case

使用滑动窗口技术对文本进行分块处理，保留原文本结构（标题、表格等），
并应用窗口截断以满足 token 限制。

主要功能：
1. 按标题分割 Markdown 文本
2. 检测并保护表格边界（不切断表格）
3. 按 token 阈值切分文本块
4. 应用滑动窗口（支持奇数窗口大小）
5. 窗口截断（满足 max_window_length 限制）
6. 保留元数据（页码、锚点、标题、chunk_index）
"""

import logging
import os
import re
from urllib.parse import unquote
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from config.settings import Settings
from src.application.exceptions import ChunkingFailedError
from ..text_truncation import joined_text_length, truncate_text_from_sides

logger = logging.getLogger(__name__)


# =============================================================================
# Chunk 模型定义
# =============================================================================

class Chunk(BaseModel):
    """分块数据模型
    
    Attributes:
        text: 中心块原始文本内容
        embedding_text: 向量化时使用的文本，默认为中心块文本
        start_pos: 在原文本中的起始位置（字符索引）
        token_count: token数量
        chunk_chars: 字符数
        metadata: 元数据字典
    """
    text: str = Field(description="分块文本内容")
    embedding_text: Optional[str] = Field(
        default=None,
        description="向量化使用的文本，未提供时回退到 text"
    )
    start_pos: int = Field(default=0, description="在原文本中的起始位置（字符索引）")
    token_count: int = Field(default=0, description="token数量")
    chunk_chars: int = Field(default=0, description="字符数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据字典")


# =============================================================================
# 辅助工具类
# =============================================================================

class MarkdownSplitter:
    """Markdown 分割工具"""
    
    @staticmethod
    def split_by_headers(text: str) -> List[Dict[str, Any]]:
        """
        按标题分割 Markdown 文本
        
        Args:
            text: Markdown 文本
            
        Returns:
            分割后的块列表，每个块包含 'text', 'header', 'level' 等元数据
        """
        if not text:
            return []
        
        # 匹配 Markdown 标题（# to ######）
        header_pattern = r'^(#{1,6})\s+(.+?)\s*$'
        
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_header = None
        current_level = 0
        start_pos = 0
        
        for i, line in enumerate(lines):
            match = re.match(header_pattern, line)
            if match:
                # 保存之前的 chunk
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'header': current_header,
                        'level': current_level,
                        'start_pos': start_pos,
                        'is_header': False
                    })
                
                # 开始新 chunk（包含标题）
                current_chunk = [line]
                current_header = match.group(2).strip()
                current_level = len(match.group(1))
                start_pos = sum(len(l) + 1 for l in lines[:i])  # +1 for newline
            else:
                current_chunk.append(line)
        
        # 保存最后一个 chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'header': current_header,
                'level': current_level,
                'start_pos': start_pos,
                'is_header': False
            })
        
        return chunks

    @staticmethod
    def split_library_sections(text: str) -> List[Dict[str, Any]]:
        """按标题切分 library Markdown，并保留完整标题层级信息。"""
        if not text:
            return []

        header_pattern = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.MULTILINE)
        lines = text.split('\n')
        sections: List[Dict[str, Any]] = []
        current_headers: Dict[str, str] = {}
        current_lines: List[str] = []
        current_start = 0
        char_pos = 0

        for line in lines:
            match = header_pattern.match(line)
            if match:
                if current_lines:
                    sections.append({
                        "metadata": current_headers.copy(),
                        "content": "\n".join(current_lines).strip("\n"),
                        "start_pos": current_start,
                    })
                    current_lines = []

                level = len(match.group(1))
                current_headers = {
                    key: value
                    for key, value in current_headers.items()
                    if int(key.split()[-1]) < level
                }
                current_headers[f"Header {level}"] = match.group(2).strip()
                current_start = char_pos + len(line) + 1
            else:
                if not current_lines:
                    current_start = char_pos
                current_lines.append(line)

            char_pos += len(line) + 1

        if current_lines:
            sections.append({
                "metadata": current_headers.copy(),
                "content": "\n".join(current_lines).strip("\n"),
                "start_pos": current_start,
            })

        return sections


class TableDetector:
    """表格检测工具"""
    
    @staticmethod
    def find_tables(text: str) -> List[Dict[str, Any]]:
        """
        查找 Markdown 表格位置
        
        Args:
            text: Markdown 文本
            
        Returns:
            表格位置列表，每个包含 'start', 'end', 'content'
        """
        tables = []
        lines = text.split('\n')
        
        in_table = False
        table_start = -1
        table_lines = []
        
        for i, line in enumerate(lines):
            # 检测表格行（包含 |）
            is_table_line = '|' in line
            
            if is_table_line and not in_table:
                # 表格开始
                in_table = True
                table_start = i
                table_lines = [line]
            elif is_table_line and in_table:
                # 表格继续
                table_lines.append(line)
            elif not is_table_line and in_table:
                # 表格结束
                tables.append({
                    'start': table_start,
                    'end': i - 1,
                    'content': '\n'.join(table_lines)
                })
                in_table = False
                table_lines = []
        
        # 处理结尾的表格
        if in_table and table_lines:
            tables.append({
                'start': table_start,
                'end': len(lines) - 1,
                'content': '\n'.join(table_lines)
            })
        
        return tables
    
    @staticmethod
    def is_inside_table(pos: int, tables: List[Dict[str, Any]]) -> bool:
        """检查位置是否在表格内"""
        for table in tables:
            if table['start'] <= pos <= table['end']:
                return True
        return False


# =============================================================================
# 主 Use Case
# =============================================================================

class ChunkingWithSlidingWindowUseCase:
    """文本分块与滑动窗口处理用例"""
    
    def __init__(
        self,
        settings: Settings,
        tokenizer_repo  # 用于 count_tokens 的分词器
    ):
        """
        初始化分块处理器
        
        Args:
            settings: 配置对象，包含分块相关配置
            tokenizer_repo: 分词器实例，需要有 count_tokens 方法
        """
        self.settings = settings
        self.tokenizer_repo = tokenizer_repo
        self.logger = logging.getLogger(__name__)
        
        # 从配置获取参数
        self.chunk_tokens = settings.file_processing.chunk_tokens  # 默认 256
        self.window_size = settings.file_processing.window_size    # 默认 9
        self.max_window_length = settings.file_processing.max_window_length  # 默认 12000
        self.target_max_length = settings.file_processing.target_max_length  # 默认 10000
        
        # 确保窗口大小为奇数
        if self.window_size % 2 == 0:
            self.window_size += 1
            self.logger.info(f"窗口大小调整为奇数: {self.window_size}")
        
        self.logger.info(
            f"ChunkingWithSlidingWindowUseCase 初始化: "
            f"chunk_tokens={self.chunk_tokens}, "
            f"window_size={self.window_size}, "
            f"max_window_length={self.max_window_length}"
        )

    def _get_library_chunk_token_limit(self) -> int:
        """获取 library 角色的切分阈值，对齐旧项目默认 512。"""
        return max(self.chunk_tokens, 512)

    def _get_max_table_length(self) -> int:
        """获取表格最大保护长度，缺失时回退到旧项目默认值。"""
        value = getattr(self.settings.file_processing, "max_table_length", 3000)
        return value if isinstance(value, int) and value > 0 else 3000
    
    async def execute(
        self,
        markdown_content: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """
        执行文本分块和滑动窗口处理
        
        Args:
            markdown_content: Markdown 内容
            metadata: 元数据（页码、锚点、标题等）
            
        Returns:
            Chunk 列表
            
        Raises:
            ChunkingFailedError: 分块处理失败
        """
        self.logger.info(
            f"开始文本分块处理: "
            f"content_length={len(markdown_content)}, "
            f"metadata={list(metadata.keys())}"
        )
        
        try:
            if metadata.get("user_role", "").lower() == "library":
                library_chunks = self._build_library_chunks(markdown_content, metadata)
                window_chunks = self._apply_sliding_window(library_chunks, metadata)
                self.logger.info(f"library 文本分块处理完成: chunks={len(window_chunks)}")
                return window_chunks

            # 步骤 1: 按标题分割
            header_chunks = self._split_by_headers(markdown_content)
            self.logger.info(f"按标题分割完成: {len(header_chunks)} 个块")
            
            # 步骤 2: 检测表格边界
            tables = TableDetector.find_tables(markdown_content)
            self.logger.info(f"检测到 {len(tables)} 个表格")
            
            # 步骤 3: 按 token 阈值切分
            token_chunks = self._split_by_tokens(header_chunks, tables)
            self.logger.info(f"按 token 切分完成: {len(token_chunks)} 个块")
            
            # 步骤 4: 应用滑动窗口
            window_chunks = self._apply_sliding_window(token_chunks, metadata)
            self.logger.info(f"滑动窗口处理完成: {len(window_chunks)} 个窗口")
            
            # 统计信息
            total_tokens = sum(c.token_count for c in window_chunks)
            avg_tokens = total_tokens / len(window_chunks) if window_chunks else 0
            
            self.logger.info(
                f"文本分块处理完成: "
                f"chunks={len(window_chunks)}, "
                f"total_tokens={total_tokens}, "
                f"avg_tokens={avg_tokens:.1f}"
            )
            
            return window_chunks
            
        except Exception as e:
            self.logger.error(f"文本分块处理失败: {e}")
            raise ChunkingFailedError(f"Chunking failed: {e}", original_error=e)
    
    # =========================================================================
    # 私有方法
    # =========================================================================
    
    def _count_tokens(self, text: str) -> int:
        """计算文本的 token 数量"""
        if not text:
            return 0
        
        try:
            # 调用 tokenizer_repo 的 count_tokens 方法
            if hasattr(self.tokenizer_repo, 'count_tokens'):
                return self.tokenizer_repo.count_tokens(text)
            elif hasattr(self.tokenizer_repo, 'tokenize_with_count'):
                result = self.tokenizer_repo.tokenize_with_count([text])
                if result and 'token_counts' in result:
                    token_counts = result['token_counts']
                    return token_counts.get(text, 0)
            else:
                # 降级方案：直接使用字符数
                return len(text)
        except Exception as e:
            self.logger.warning(f"token 计算失败: {e}，使用简单估算")
            return len(text)
    
    def _split_by_headers(self, text: str) -> List[Dict[str, Any]]:
        """
        按标题分割 Markdown 文本
        
        Args:
            text: Markdown 文本
            
        Returns:
            分割后的块列表
        """
        return MarkdownSplitter.split_by_headers(text)

    def _build_library_chunks(
        self,
        markdown_content: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """按旧项目 library 语义生成结构化 chunk。"""
        title = self._extract_library_title(markdown_content, metadata.get("doc_name", ""))
        sections = MarkdownSplitter.split_library_sections(markdown_content)
        chunks: List[Chunk] = []
        library_chunk_limit = self._get_library_chunk_token_limit()

        for section in sections:
            section_metadata = section["metadata"]
            content = section["content"].strip()
            if not content or self._is_library_table_of_contents(content, section_metadata):
                continue
            if self._is_library_separator_block(content):
                continue

            heading_levels = self._format_library_heading_levels(section_metadata)
            anchors = self._extract_library_anchor(section_metadata, heading_levels)
            level = max(
                (int(key.split()[-1]) for key in section_metadata.keys() if key.startswith("Header ")),
                default=0
            )
            header = section_metadata.get(f"Header {level}", "") if level else ""
            start_pos = section["start_pos"]
            full_text = self._build_library_embedding_text(heading_levels, content)
            full_tokens = self._count_tokens(full_text)
            chunk_metadata = {
                "header": header,
                "level": level,
                "chunk_type": "library_markdown",
                "anchors": anchors,
                "heading_levels": heading_levels,
                "title": title,
                "content": content,
            }

            if full_tokens <= library_chunk_limit:
                chunks.append(Chunk(
                    text=content,
                    embedding_text=full_text,
                    start_pos=start_pos,
                    token_count=full_tokens,
                    chunk_chars=len(content),
                    metadata=chunk_metadata
                ))
                continue

            prefix = self._build_library_prefix(heading_levels)
            prefix_tokens = self._count_tokens(prefix)
            content_max_tokens = library_chunk_limit - prefix_tokens
            if content_max_tokens <= 0:
                chunks.append(Chunk(
                    text=content,
                    embedding_text=full_text,
                    start_pos=start_pos,
                    token_count=full_tokens,
                    chunk_chars=len(content),
                    metadata={**chunk_metadata, "is_truncated": True}
                ))
                continue

            for split_chunk in self._split_library_content(content, start_pos, content_max_tokens):
                split_content = split_chunk["text"]
                split_start = split_chunk["start_pos"]
                split_full_text = self._build_library_embedding_text(heading_levels, split_content)
                chunks.append(Chunk(
                    text=split_content,
                    embedding_text=split_full_text,
                    start_pos=split_start,
                    token_count=self._count_tokens(split_full_text),
                    chunk_chars=len(split_content),
                    metadata={
                        **chunk_metadata,
                        "content": split_content,
                        "chunk_type": "library_markdown_split",
                    }
                ))

        return chunks

    def _normalize_library_title(self, raw_title: str) -> str:
        """清理 doc_name，尽量恢复旧项目中的书名表现。"""
        clean_title = raw_title.strip().strip("`").strip()
        if not clean_title:
            return ""

        clean_title = unquote(clean_title)
        clean_title = clean_title.split("?")[0].split("#")[0].strip()
        clean_title = os.path.basename(clean_title.rstrip("/"))
        if clean_title.lower().endswith(".md"):
            clean_title = clean_title[:-3]
        return clean_title

    def _extract_library_title(self, markdown_content: str, fallback_title: str) -> str:
        """优先从 Markdown 一级标题提取书名，失败时回退到文件名。"""
        header_pattern = re.compile(r'^#\s+(.+?)\s*$', re.MULTILINE)
        toc_keywords = ('目录', '目次', 'table of contents', 'contents', 'toc', '索引', 'index')

        for match in header_pattern.finditer(markdown_content):
            title = re.sub(r'<a id="[^"]+"></a>', '', match.group(1)).strip()
            lower_title = title.lower()
            if title and not any(keyword in lower_title for keyword in toc_keywords):
                return title

        return self._normalize_library_title(fallback_title)

    def _is_library_table_of_contents(self, content: str, headers: Dict[str, str]) -> bool:
        """复用旧项目目录识别规则，过滤目录块。"""
        toc_keywords = ['目录', '目次', 'table of contents', 'contents', 'toc', '索引', 'index']

        for header_value in headers.values():
            stripped_header = re.sub(r'<a id="[^"]+"></a>', '', header_value).strip().lower()
            if any(keyword in stripped_header for keyword in toc_keywords):
                return True

        lines = [line.strip() for line in content.strip().split('\n') if line.strip()]
        if not lines:
            return False

        link_lines = 0
        for line in lines:
            if re.search(r'\[.*?\]\(.*?\)', line):
                link_lines += 1
            elif re.search(r'<a\s+.*?href=.*?>', line, re.IGNORECASE):
                link_lines += 1
            elif re.match(r'^\s*(?:\d+\.\s+\S+|第[一二三四五六七八九十\d]+章\s+\S+|Chapter\s+\d+\s+\S+)', line, re.IGNORECASE):
                if not re.search(r'\s{3,}|\t{2,}', line):
                    link_lines += 1

        total_lines = len(lines)
        link_ratio = link_lines / total_lines
        avg_line_length = sum(len(line) for line in lines) / total_lines
        return link_ratio > 0.5 or (link_ratio > 0.3 and avg_line_length < 50)

    def _format_library_heading_levels(self, metadata: Dict[str, str]) -> str:
        """格式化 library 块的标题层级。"""
        headers = []
        for index in range(1, 7):
            header_key = f"Header {index}"
            if header_key in metadata:
                clean_header = re.sub(r'<a id="[^"]+"></a>', '', metadata[header_key]).strip()
                if clean_header:
                    headers.append(clean_header)
        return '-'.join(headers)

    def _is_library_separator_block(self, content: str) -> bool:
        """过滤纯 Markdown 分隔线，避免产生独立噪音块。"""
        normalized = (content or "").strip()
        return bool(normalized) and re.fullmatch(r"[-*_]{3,}", normalized) is not None

    def _extract_library_anchor(self, metadata: Dict[str, str], heading_levels: str) -> str:
        """优先从标题锚点提取 anchors，找不到时回退到 Page 锚点。"""
        for index in range(1, 7):
            header_key = f"Header {index}"
            header_text = metadata.get(header_key, "")
            match = re.search(r'<a id="([^"]+)"></a>', header_text)
            if match:
                return match.group(1)

        page_match = re.search(r'Page\s+(\d+)', heading_levels, re.IGNORECASE)
        if page_match:
            return f"Page {page_match.group(1)}"

        return ""

    def _build_library_prefix(self, heading_levels: str) -> str:
        """构建旧项目 library 的 embedding 前缀。"""
        return f"Heading Levels：{heading_levels}。Content："

    def _build_library_embedding_text(self, heading_levels: str, content: str) -> str:
        """构建旧项目 library 的 embedding 文本。"""
        return f"{self._build_library_prefix(heading_levels)}{content}"

    def _is_library_table_line(self, line: str) -> bool:
        """判断某行是否属于 Markdown 或网格表格。"""
        stripped = line.strip()
        if not stripped:
            return False
        return (
            ('|' in stripped and stripped.count('|') >= 2)
            or bool(re.match(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$', stripped))
            or bool(re.match(r'^\s*[+-][-=|\s\+]*[+-]\s*$', stripped))
        )

    def _find_library_table_boundaries(self, text: str) -> List[Dict[str, int]]:
        """查找 library 文本中的表格字符边界。"""
        lines = text.split('\n')
        boundaries: List[Dict[str, int]] = []
        table_start_line: Optional[int] = None
        char_positions: List[int] = []
        char_pos = 0

        for line in lines:
            char_positions.append(char_pos)
            char_pos += len(line) + 1

        for index, line in enumerate(lines):
            is_table_line = self._is_library_table_line(line)
            if is_table_line and table_start_line is None:
                table_start_line = index
            elif not is_table_line and table_start_line is not None:
                end_line = index - 1
                boundaries.append({
                    "start_char": char_positions[table_start_line],
                    "end_char": char_positions[end_line] + len(lines[end_line]),
                })
                table_start_line = None

        if table_start_line is not None and lines:
            end_line = len(lines) - 1
            boundaries.append({
                "start_char": char_positions[table_start_line],
                "end_char": char_positions[end_line] + len(lines[end_line]),
            })

        return boundaries

    def _find_library_code_block_boundaries(self, text: str) -> List[Dict[str, int]]:
        """查找 library 文本中的 fenced code block 字符边界。"""
        lines = text.split('\n')
        boundaries: List[Dict[str, int]] = []
        code_start_line: Optional[int] = None
        fence_marker: Optional[str] = None
        char_positions: List[int] = []
        char_pos = 0

        for line in lines:
            char_positions.append(char_pos)
            char_pos += len(line) + 1

        for index, line in enumerate(lines):
            match = re.match(r'^\s*(```+|~~~+)', line)
            if not match:
                continue

            marker = match.group(1)[0]
            if code_start_line is None:
                code_start_line = index
                fence_marker = marker
                continue

            if fence_marker == marker:
                boundaries.append({
                    "start_char": char_positions[code_start_line],
                    "end_char": char_positions[index] + len(lines[index]),
                    "type": "code_block",
                })
                code_start_line = None
                fence_marker = None

        if code_start_line is not None and lines:
            end_line = len(lines) - 1
            boundaries.append({
                "start_char": char_positions[code_start_line],
                "end_char": char_positions[end_line] + len(lines[end_line]),
                "type": "code_block",
            })

        return boundaries

    def _find_library_natural_break(self, text: str, target_pos: int) -> int:
        """在目标位置后寻找旧项目风格的自然断点。"""
        search_range = min(300, max(0, len(text) - target_pos))
        end_pos = min(len(text), target_pos + search_range)
        break_patterns = ['\n\n', '。', '.', '！', '!']

        for pos in range(target_pos, end_pos):
            for pattern in break_patterns:
                if text[pos:pos + len(pattern)] == pattern:
                    return pos + len(pattern)

        forward_slice = text[target_pos:end_pos]
        next_newline = forward_slice.find('\n')
        if next_newline != -1:
            return min(target_pos + next_newline + 1, len(text))

        return target_pos

    def _find_library_safe_split_position(
        self,
        text: str,
        start_pos: int,
        max_chars: int,
        protected_boundaries: List[Dict[str, Any]]
    ) -> int:
        """在保护表格和代码块边界的前提下找到安全切分位置。"""
        target_pos = min(start_pos + max_chars, len(text))

        for boundary in protected_boundaries:
            if boundary["start_char"] <= target_pos <= boundary["end_char"]:
                if boundary.get("type") == "table":
                    table_length = boundary["end_char"] - boundary["start_char"]
                    max_table_length = self._get_max_table_length()
                    if table_length > max_table_length:
                        return min(start_pos + max_table_length, boundary["end_char"])
                return min(boundary["end_char"] + 1, len(text))

        adjusted_target = target_pos
        for boundary in protected_boundaries:
            overlaps = not (boundary["end_char"] < start_pos or boundary["start_char"] > target_pos)
            if overlaps:
                adjusted_target = max(adjusted_target, min(boundary["end_char"] + 1, len(text)))

        return self._find_library_natural_break(text, adjusted_target)

    def _is_library_mergeable_fragment(self, content: str) -> bool:
        """判断切分后的小碎片是否应并回前一个 chunk。"""
        normalized = (content or "").strip()
        if not normalized:
            return False
        if self._is_library_separator_block(normalized):
            return True
        return normalized in {"```", "~~~"}

    def _merge_library_split_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并切分后残留的分隔线或代码围栏碎片，避免产生噪音块。"""
        merged_chunks: List[Dict[str, Any]] = []

        for chunk in chunks:
            text = chunk["text"]
            if merged_chunks and self._is_library_mergeable_fragment(text):
                merged_chunks[-1]["text"] = f"{merged_chunks[-1]['text'].rstrip()}\n{text.lstrip()}"
                continue
            merged_chunks.append(chunk)

        return merged_chunks

    def _split_library_content(
        self,
        content: str,
        content_start_pos: int,
        content_max_tokens: int
    ) -> List[Dict[str, Any]]:
        """按旧项目的字符切分策略拆分 library 正文。"""
        max_chars = max(content_max_tokens * 2, 1)
        if len(content) <= max_chars:
            return [{"text": content, "start_pos": content_start_pos}]

        table_boundaries = [
            {**boundary, "type": "table"}
            for boundary in self._find_library_table_boundaries(content)
        ]
        code_block_boundaries = self._find_library_code_block_boundaries(content)
        protected_boundaries = sorted(
            table_boundaries + code_block_boundaries,
            key=lambda item: (item["start_char"], item["end_char"])
        )
        chunks: List[Dict[str, Any]] = []
        current_pos = 0

        while current_pos < len(content):
            safe_pos = self._find_library_safe_split_position(
                content,
                current_pos,
                max_chars,
                protected_boundaries
            )
            if safe_pos <= current_pos:
                safe_pos = min(current_pos + 1, len(content))

            chunk_text = content[current_pos:safe_pos].strip()
            if chunk_text:
                raw_chunk = content[current_pos:safe_pos]
                leading_spaces = len(raw_chunk) - len(raw_chunk.lstrip())
                chunks.append({
                    "text": chunk_text,
                    "start_pos": content_start_pos + current_pos + leading_spaces
                })

            current_pos = safe_pos

        return self._merge_library_split_chunks(chunks)

    def _get_chunk_window_text(self, chunk: Chunk) -> str:
        """获取参与滑动窗口拼接的文本，优先使用 embedding_text。"""
        return chunk.embedding_text or chunk.text
    
    def _split_by_tokens(
        self,
        header_chunks: List[Dict[str, Any]],
        _tables: List[Dict[str, Any]]
    ) -> List[Chunk]:
        """
        按 token 阈值切分文本块
        
        Args:
            header_chunks: 按标题分割后的块
            tables: 表格位置列表
            
        Returns:
            切分后的 Chunk 列表
        """
        chunks = []
        
        for chunk_data in header_chunks:
            text = chunk_data['text']
            start_pos = chunk_data['start_pos']
            header = chunk_data.get('header', '')
            level = chunk_data.get('level', 0)
            
            # 如果文本本身不超阈值，直接返回
            token_count = self._count_tokens(text)
            if token_count <= self.chunk_tokens:
                chunks.append(Chunk(
                    text=text,
                    start_pos=start_pos,
                    token_count=token_count,
                    chunk_chars=len(text),
                    metadata={
                        'header': header,
                        'level': level,
                        'chunk_type': 'header_chunk'
                    }
                ))
                continue
            
            # 需要进一步切分
            self.logger.debug(f"需要切分大块: header={header}, tokens={token_count}")
            
            # 尝试按段落分割
            paragraphs = self._split_by_paragraphs(text)
            
            current_chunk = []
            current_tokens = 0
            current_chars = 0
            
            for para in paragraphs:
                para_text = para['text']
                para_tokens = self._count_tokens(para_text)
                para_chars = len(para_text)
                
                # 如果单个段落就超限，强制切分
                if para_tokens > self.chunk_tokens:
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk,
                            start_pos,
                            header,
                            level,
                            chunk_type='paragraph_split'
                        ))
                        current_chunk = []
                        current_tokens = 0
                        current_chars = 0
                    
                    # 强制切分超长段落
                    split_chunks = self._split_long_paragraph(
                        para_text,
                        start_pos + para['start_pos'],
                        header,
                        level
                    )
                    chunks.extend(split_chunks)
                    
                # 如果加入后不超限，加入当前 chunk
                elif current_tokens + para_tokens <= self.chunk_tokens:
                    current_chunk.append({
                        'text': para_text,
                        'start_pos': start_pos + para['start_pos']
                    })
                    current_tokens += para_tokens
                    current_chars += para_chars
                    
                # 否则保存当前 chunk，开始新 chunk
                else:
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk,
                            start_pos,
                            header,
                            level,
                            chunk_type='paragraph_group'
                        ))
                    current_chunk = [{
                        'text': para_text,
                        'start_pos': start_pos + para['start_pos']
                    }]
                    current_tokens = para_tokens
                    current_chars = para_chars
            
            # 保存最后一个 chunk
            if current_chunk:
                chunks.append(self._create_chunk(
                    current_chunk,
                    start_pos,
                    header,
                    level,
                    chunk_type='paragraph_group'
                ))
        
        return chunks
    
    def _split_by_paragraphs(self, text: str) -> List[Dict[str, Any]]:
        """
        按段落分割文本
        
        Args:
            text: 文本
            
        Returns:
            段落列表
        """
        paragraphs = []
        lines = text.split('\n')
        current_paragraph = []
        current_start = 0
        
        for i, line in enumerate(lines):
            if line.strip():  # 非空行
                if not current_paragraph:
                    current_start = i
                current_paragraph.append(line)
            else:  # 空行
                if current_paragraph:
                    paragraph_text = '\n'.join(current_paragraph)
                    paragraphs.append({
                        'text': paragraph_text,
                        'start_pos': current_start
                    })
                    current_paragraph = []
        
        # 保存最后一个段落
        if current_paragraph:
            paragraph_text = '\n'.join(current_paragraph)
            paragraphs.append({
                'text': paragraph_text,
                'start_pos': current_start
            })
        
        return paragraphs
    
    def _split_long_paragraph(
        self,
        text: str,
        start_pos: int,
        header: str,
        level: int
    ) -> List[Chunk]:
        """
        强制切分超长段落
        
        Args:
            text: 段落文本
            start_pos: 起始位置
            header: 标题
            level: 标题级别
            
        Returns:
            切分后的 Chunk 列表
        """
        chunks = []
        
        # 按句子分割
        sentences = re.split(r'([。！？.!?]+)', text)
        
        current_chunk = []
        current_tokens = 0
        current_chars = 0
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else '')
            sentence_tokens = self._count_tokens(sentence)
            sentence_chars = len(sentence)
            
            if current_tokens + sentence_tokens <= self.chunk_tokens:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
                current_chars += sentence_chars
            else:
                if current_chunk:
                    chunk_text = ''.join(current_chunk)
                    chunks.append(Chunk(
                        text=chunk_text,
                        start_pos=start_pos,
                        token_count=current_tokens,
                        chunk_chars=current_chars,
                        metadata={
                            'header': header,
                            'level': level,
                            'chunk_type': 'forced_split',
                            'is_truncated': True
                        }
                    ))
                    start_pos += current_chars
                    current_chunk = [sentence]
                    current_tokens = sentence_tokens
                    current_chars = sentence_chars
                else:
                    # 单个句子超限，强制截断
                    # 按字符分割
                    chunk_size = self.chunk_tokens * 4  # 估算
                    chunk_text = sentence[:chunk_size]
                    chunks.append(Chunk(
                        text=chunk_text,
                        start_pos=start_pos,
                        token_count=self._count_tokens(chunk_text),
                        chunk_chars=len(chunk_text),
                        metadata={
                            'header': header,
                            'level': level,
                            'chunk_type': 'forced_split',
                            'is_truncated': True
                        }
                    ))
                    # 继续处理剩余部分
                    remaining = sentence[chunk_size:]
                    if remaining:
                        remaining_chunk = Chunk(
                            text=remaining,
                            start_pos=start_pos + len(chunk_text),
                            token_count=self._count_tokens(remaining),
                            chunk_chars=len(remaining),
                            metadata={
                                'header': header,
                                'level': level,
                                'chunk_type': 'forced_split',
                                'is_truncated': True
                            }
                        )
                        chunks.append(remaining_chunk)
        
        # 保存最后一个 chunk
        if current_chunk:
            chunk_text = ''.join(current_chunk)
            chunks.append(Chunk(
                text=chunk_text,
                start_pos=start_pos,
                token_count=current_tokens,
                chunk_chars=current_chars,
                metadata={
                    'header': header,
                    'level': level,
                    'chunk_type': 'forced_split'
                }
            ))
        
        return chunks
    
    def _create_chunk(
        self,
        text_parts: List[Dict[str, Any]],
        _base_start_pos: int,
        header: str,
        level: int,
        chunk_type: str
    ) -> Chunk:
        """
        从文本部分创建 Chunk
        
        Args:
            text_parts: 文本部分列表
            base_start_pos: 基础起始位置
            header: 标题
            level: 标题级别
            chunk_type: chunk 类型
            
        Returns:
            Chunk 对象
        """
        text = '\n\n'.join(p['text'] for p in text_parts)
        start_pos = text_parts[0]['start_pos']
        token_count = sum(self._count_tokens(p['text']) for p in text_parts)
        chunk_chars = sum(len(p['text']) for p in text_parts)
        
        return Chunk(
            text=text,
            start_pos=start_pos,
            token_count=token_count,
            chunk_chars=chunk_chars,
            metadata={
                'header': header,
                'level': level,
                'chunk_type': chunk_type
            }
        )
    
    def _apply_sliding_window(
        self,
        chunks: List[Chunk],
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """
        应用滑动窗口
        
        Args:
            chunks: Chunk 列表
            metadata: 元数据
            
        Returns:
            应用滑动窗口后的 Chunk 列表
        """
        if not chunks:
            return []
        
        half_window = self.window_size // 2
        windowed_chunks = []
        
        self.logger.info(
            f"应用滑动窗口: "
            f"chunks={len(chunks)}, "
            f"window_size={self.window_size}, "
            f"half_window={half_window}"
        )
        
        for i, chunk in enumerate(chunks):
            # 确定窗口范围
            start_idx = max(0, i - half_window)
            end_idx = min(len(chunks), i + half_window + 1)
            
            # 获取窗口内的 chunks
            window_chunks = chunks[start_idx:end_idx]
            target_chunk_index = i - start_idx
            
            # 计算窗口总长度
            window_length = joined_text_length([self._get_chunk_window_text(c) for c in window_chunks])
            
            # 如果窗口超长，进行截断
            if window_length > self.max_window_length:
                self.logger.debug(
                    f"窗口超长: index={i}, "
                    f"window_length={window_length}, "
                    f"max={self.max_window_length}"
                )
                
                window_chunks = self._truncate_window_chunks(
                    window_chunks=window_chunks,
                    target_chunk_index=target_chunk_index
                )
            
            window_text = '\n\n'.join(self._get_chunk_window_text(c) for c in window_chunks)

            # 保留中心块原文用于入库，仅将窗口文本暴露给 embedding。
            windowed_chunk = chunk.model_copy(
                update={
                    'embedding_text': window_text,
                    'metadata': {
                        **chunk.metadata,
                        'window_size': len(window_chunks),
                        'window_index': i,
                        'target_chunk_index': i,
                        'chunk_index': i,
                        'embedding_text_chars': len(window_text),
                        **metadata
                    }
                }
            )
            
            windowed_chunks.append(windowed_chunk)
        
        return windowed_chunks

    def _truncate_window_chunks(
        self,
        window_chunks: List[Chunk],
        target_chunk_index: int
    ) -> List[Chunk]:
        """按中心优先策略裁剪窗口，尽量保留最中心 chunk 及其邻近上下文。"""
        if not window_chunks:
            return []

        separator_length = len('\n\n')
        target_chunk = window_chunks[target_chunk_index]
        target_text = self._get_chunk_window_text(target_chunk)

        if len(target_text) >= self.max_window_length:
            truncated_target = truncate_text_from_sides(
                target_text,
                self.max_window_length
            )
            update_fields: Dict[str, Any] = {
                'token_count': self._count_tokens(truncated_target)
            }
            if target_chunk.embedding_text is not None:
                update_fields['embedding_text'] = truncated_target
            else:
                update_fields['text'] = truncated_target
                update_fields['chunk_chars'] = len(truncated_target)
            return [
                target_chunk.model_copy(
                    update=update_fields
                )
            ]

        left_bound = target_chunk_index
        right_bound = target_chunk_index
        current_length = len(target_text)
        left_blocked = False
        right_blocked = False
        max_distance = max(target_chunk_index, len(window_chunks) - target_chunk_index - 1)

        for distance in range(1, max_distance + 1):
            candidates = []
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
