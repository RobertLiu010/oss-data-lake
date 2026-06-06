# Vector Lake 技术文档

## 1. 系统概述

Vector Lake 是一个基于 OSS 的知识库管理系统，支持文档的自动解析、分块、向量化与检索。

### 1.1 核心概念

- **Entity**：知识库中的基本单元，一个文件或一个 URL 对应一个 Entity
- **Representation**：Entity 的不同表示形式，如 canonical_md、page_image 等
- **Chunk**：Representation 的分片，用于向量化检索

### 1.2 技术栈

- FastAPI + Uvicorn
- LanceDB 向量数据库
- Jina Embeddings V5
- Redis 任务队列

## 2. 数据模型

### 2.1 Entity 模型

每个 Entity 包含以下字段：
- entity_id：唯一标识
- entity_type：类型（document/image/audio/video/table）
- source_type：来源类型（oss/url）
- content_hash：内容哈希

### 2.2 存储结构

```
{workspace_id}/{collection_id}/{entity_id}/
  source/original      ← 原始文件
  canonical_md.md      ← 解析后的 Markdown
```

## 3. Pipeline 体系

### 3.1 RepPipeline

RepPipeline 负责将原始文件转换为各种 Representation：
1. parse：文档解析
2. render_page：页面渲染
3. visual_recognize：VLM 视觉识别

### 3.2 IndexPipeline

IndexPipeline 负责将 Representation 转换为可检索的索引：
1. chunk_and_embed_text：分块 + 向量化
2. build_vector_index：构建向量索引
3. build_fts_index：构建全文索引

## 4. 搜索与检索

系统支持三种检索模式：
- 语义检索：基于向量相似度
- 全文检索：基于关键词匹配
- 混合检索：语义 + 全文融合
