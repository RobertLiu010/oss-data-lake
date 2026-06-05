# Vector-Lake PRD 深度 Review

> **评审依据**：项目内部代码（base_chunking.py / base_embedding.md / OSS 目录结构）+ 外部行业资料（NVIDIA Enterprise RAG Blueprint、Databricks AI Search、LiveVectorLake 论文、LanceDB 官方文档、多模态 RAG 最佳实践）

---

## 一、总体评价

PRD 的核心抽象（Entity → Representation → Embedding → Index）**方向正确**，与 2025–2026 行业主流高度对齐：

- **NVIDIA Enterprise RAG Blueprint** 的管线同样是 `Ingest → Extract → Embed → Index → Retrieve`，且强调"文档理解必须多模态"。
- **LiveVectorLake 论文**（arXiv 2601.05270）提出"内容寻址 chunk 同步 + 双层存储 + 时间点查询"，与 PRD 的 `etag 变更检测 + reconcile + versioned publish` 思路一致。
- **Databricks AI Search** 的核心决策是"存储计算分离 + 摄入与查询解耦"，PRD 的 `Ingest Queue → Pipeline Orchestrator` 模式与之吻合。
- **LanceDB 官方** 2026 年发布 Lance × DuckDB 扩展，定位"多模态 Lakehouse 格式"，直接支持 `lance_vector_search` + `lance_fts` + `lance_hybrid_search`，与 PRD 的 hybrid search 需求天然匹配。

**结论：架构方向没问题，但存在 7 个需要修正/补充的关键问题。**

---

## 二、关键问题（Must Fix）

### P1. Embedding 表缺少 Chunk 粒度 — 最大架构缺陷

**问题**：PRD 定义 Embedding 关联到 `entity_id + representation_id`，但实际 embedding 是对 **chunk/segment** 做的，不是对整个 entity 或 representation 做的。一个 `canonical_md` representation 可能被切成 50 个 chunk，每个 chunk 各有一个 embedding。

当前 `ChunkingWithSlidingWindowUseCase` 产出的是 `Chunk` 对象（含 text / embedding_text / start_pos / token_count / metadata），这些 chunk 是 embedding 的真正粒度。

**行业对照**：
- NVIDIA Nemotron RAG 的管线是 `Document → Structured Chunks → Embed → Index`，chunk 是一等公民。
- LiveVectorLake 的核心贡献之一就是"content-addressable chunk-level synchronization using SHA-256 hashing"。
- LanceDB 官方文档的所有示例都是"每行一个 chunk + vector"。

**风险**：如果 embedding 只挂在 representation 下，检索时无法定位到具体段落/时间戳，只能返回整个 entity，**丧失了 RAG 的核心价值**。

**建议**：

1. 增加 `chunks` 表作为 v0.1 一等公民（不是 v0.2 可选项）：

```text
chunks
  chunk_id
  entity_id
  representation_id
  chunk_index          # 在 representation 中的序号
  text                 # 中心块原文
  embedding_text       # 向量化文本（可能含窗口上下文）
  start_pos            # 在 representation 中的字符偏移
  token_count
  chunk_chars
  metadata             # header / level / chunk_type / page / anchor
  status
  created_at
```

2. `embeddings` 表改为关联 `chunk_id` 而非直接关联 `representation_id`：

```text
embeddings
  embedding_id
  chunk_id             # ← 改为关联 chunk
  entity_id            # 冗余，加速过滤
  embedding_type
  model
  task
  dimension
  vector               # Lance 原生 vector 列
  status
  created_at
```

3. 检索返回的 evidence 应包含 `chunk_id` + `start_pos` + `snippet`，而非只返回 entity_id。

---

### P2. Lance 表设计未利用 LanceDB 原生能力 — 实现会走弯路

**问题**：PRD 把 LanceDB 当"关系型元数据存储 + 向量存储"来用，但 LanceDB 的核心优势是 **单表内 hybrid search**（vector + FTS + scalar filter），以及 **multivector search**（ColPali/ColBERT 风格）。

**行业对照**：
- LanceDB 2026 年的 `lance_vector_search` + `lance_fts` + `lance_hybrid_search` 全部是 **单表操作**。
- LanceDB multivector search 支持每行存多个向量（`list<list<float32>>`），天然适配 ColPali 页面级检索。
- Lance × DuckDB 扩展让 SQL 查询和向量检索在同一数据集上无缝 join。

**建议**：

1. **核心检索表应该是 `chunks`（或叫 `documents`），不是 `embeddings`**：

```text
chunks (Lance 主表)
  chunk_id             # PK
  entity_id            # 用于 join entities 表
  entity_type          # 冗余，加速过滤
  workspace_id         # 必须有，安全隔离
  collection_id
  text                 # 原文（同时建 FTS 索引）
  embedding_text       # 向量化文本
  vector               # Lance 原生 vector 列，直接建 IVF_PQ / HNSW
  page_number          # 可 null
  section_header       # 可 null
  source_uri           # raw object URI
  source_version       # etag
  rep_type             # canonical_md / ocr / transcript / caption
  modality             # text / image / audio / table
  status               # active / hidden / deleted / stale
  created_at
```

2. `entities` 和 `edges` 可以保留为独立 Lance 表，用于元数据查询和图遍历，但 **不存 vector**。
3. `representations` 可以是 OSS manifest 的 Lance 镜像，用于 stat / ls / read，但 **不参与向量检索**。
4. `embeddings` 表降级为可选的"向量血缘追踪表"，不作为检索入口。

---

### P3. 缺少内容寻址（Content-Addressable）变更检测 — Reconcile 会漏判

**问题**：PRD 依赖 OSS `etag` 变更来触发重建，但 LiveVectorLake 论文证明 **chunk 级 SHA-256 哈希** 才是可靠的变更检测方式。原因：

1. OSS etag 在 multipart upload 时是分片 MD5 拼接，不等于文件内容哈希。
2. 同一 raw object 的 representation 可能因 parser 升级而变化，但 etag 不变。
3. Reconcile 无法区分"内容真变了"和"重新上传了同一文件"。

**建议**：

1. `detect` 阶段增加 `content_hash` 字段（SHA-256 of raw bytes）。
2. `chunks` 表增加 `content_hash` 字段（chunk 文本的 SHA-256）。
3. Reconcile 时比较 `content_hash` 而非 `etag`。
4. Parser 升级时，强制对受影响的 entity_type 重跑 `represent → chunk → embed` 管线，即使 etag 未变。

---

### P4. 状态模型缺少"版本"维度 — Publish 语义不完整

**问题**：PRD 提到 `versioned publish`，但状态模型中没有 `version` 字段。当 raw object 更新时：

- 旧 representation 标 `stale`，但新 representation 还没 `ready`，中间态怎么办？
- 检索应该看到旧版本还是新版本？
- 如果新版本处理失败，如何回滚？

**行业对照**：
- LiveVectorLake 的核心贡献就是"temporal query routing enabling point-in-time knowledge retrieval via delta-versioning"。
- Databricks AI Search 使用 Delta Lake 的 MVCC 机制，天然支持时间旅行查询。
- Lance 格式本身支持版本（每次写入产生新 version）。

**建议**：

1. Entity 增加 `version` 字段（整数，单调递增）。
2. Representation 增加 `entity_version` 字段。
3. Chunk / Embedding 增加 `entity_version` 字段。
4. Publish 操作 = "将某个 entity_version 标记为 active"。
5. 检索默认查 `active` 版本；支持 `?version=N` 查历史版本。
6. 新版本处理期间，旧版本保持 active（不标 stale），直到新版本 publish 成功才切换。

---

### P5. 多模态 Embedding 策略不够具体 — 实现时会产生歧义

**问题**：PRD 说"文本/图像/音频/视频在同一向量空间可互检"，但没说清楚：

1. 一个 PDF 页面同时有文本和图片，是生成 1 个 text embedding + 1 个 image embedding，还是 1 个 multimodal embedding？
2. 音频 segment 是用 `task="audio"` 还是 `task="retrieval.passage"` 对 transcript 做？
3. ColPali 风格的页面级多向量检索是否考虑？

**行业对照**：
- NVIDIA RAG Blueprint 明确区分三种策略：`Embed-Then-Chunk`（先向量再切）、`Caption-Then-Embed`（先描述再向量）、`ColPali`（页面级多向量）。
- Dify 2026 架构引入"跨模态对齐桥接层（CMAL）"，统一不同编码器的输出空间。
- LanceDB multivector search 原生支持 ColPali 的多向量存储和 MaxSim 检索。

**建议**：

1. 在 §7 Representation 矩阵中，为每种模态明确 **embedding 策略**：

```text
文档文本 chunk:
  → task="retrieval.passage", input=embedding_text
  → 1 chunk = 1 vector

文档页面图片:
  → task="image", input=page_image URL/base64
  → 1 page = 1 image vector (与 text 同空间)

音频 segment:
  → task="audio", input=segment WAV base64  (音频向量)
  → task="retrieval.passage", input=transcript_text  (文本向量)
  → 双向量，检索时合并

图片 caption:
  → task="retrieval.passage", input=caption_text
  → 1 caption = 1 text vector
```

2. v0.1 不做 ColPali，但在 schema 中预留 `multivector` 列（`list<list<float32>>`）。
3. 在 §4 Embedding 模型中增加 `task` 字段映射表：

| embedding_type | V5 task | 输入来源 |
| --- | --- | --- |
| text | `retrieval.passage` | chunk.embedding_text |
| image | `image` | page_image / image URL |
| audio | `audio` | audio_segment WAV |
| transcript | `retrieval.passage` | transcript_segment text |
| caption | `retrieval.passage` | caption text |

---

### P6. 检索 API 设计缺少 Hybrid Search — 最常用的模式缺失

**问题**：PRD 定义了 11 个独立 tool API，但行业实践表明 **hybrid search（semantic + lexical 融合）** 是生产环境最常用的模式，单独调 semantic 或 lexical 都不如融合效果好。

**行业对照**：
- LanceDB 官方文档的 Hybrid Search 页面是搜索功能中阅读量最高的。
- NVIDIA RAG Blueprint 的 baseline 配置就是"semantic retrieval + reranking"。
- Databricks AI Search 的查询引擎同时跑 vector search 和 keyword search，用 RRF 融合。

**建议**：

1. 增加 `POST /tools/hybrid` API：

```json
{
  "tool": "hybrid",
  "args": {
    "query": "Q3 定价策略",
    "modalities": ["text", "image"],
    "semantic_weight": 0.7,
    "lexical_weight": 0.3,
    "reranker": "rrf",
    "filters": { "entity_type": ["document", "page"] },
    "top_k": 10
  }
}
```

2. `POST /engine/ask` 内部默认走 hybrid，而非只走 semantic。
3. 各 tool API 保留为"原子能力"，供高级用户和 Agent 直接调用。

---

### P7. 与现有 Chunking UseCase 的对接路径不够具体

**问题**：PRD 说"在 chunk_or_segment 阶段调用 ChunkingWithSlidingWindowUseCase"，但没说清楚：

1. Chunk 的 `metadata`（header / level / chunk_type / window_size / anchors）如何映射到 Lance `chunks` 表的字段？
2. `embedding_text`（含滑动窗口上下文）和 `text`（中心块原文）的分工？
3. Library 角色的特殊切分逻辑如何适配？

**建议**：

1. 明确映射关系：

| Chunk 字段 | Lance chunks 表字段 | 用途 |
| --- | --- | --- |
| `text` | `text` | 中心块原文，用于 snippet / 高亮 |
| `embedding_text` | `embedding_text` | 向量化输入文本 |
| `start_pos` | `start_pos` | 定位 |
| `token_count` | `token_count` | 统计 |
| `metadata.header` | `section_header` | FTS + 过滤 |
| `metadata.level` | `section_level` | 过滤 |
| `metadata.chunk_type` | `chunk_type` | 过滤 |
| `metadata.window_size` | 不入 Lance | 仅 pipeline 内部使用 |
| `metadata.anchors` | `anchor` | 定位 |
| `metadata.title` | `doc_title` | FTS + 展示 |

2. `embedding_text` 用于调 V5 `retrieval.passage`；`text` 用于 FTS 索引和 snippet 返回。
3. Library 角色走 `_build_library_chunks` 分支，产出结构一致，只是 chunk_type 不同。

---

## 三、重要建议（Should Fix）

### S1. 增加 Reranker 阶段

PRD 的 Intelligent Engine 有"Result Fusion & Rerank"步骤，但管线中没有 Reranker 模块。行业实践（NVIDIA、LanceDB、Dify）都表明 **cross-encoder reranker 是提升检索精度的关键**。

**建议**：在 §6 Pipeline 中，Index 之后、Compile 之前增加可选的 `rerank` 阶段，或在 Retrieval Gateway 中内置 reranker（如 Cohere Rerank、Cross-Encoder、RRF）。

### S2. OSS 目录结构缺少版本维度

当前 `representations/{entity_type}/{entity_id}/canonical.md` 没有版本路径。如果 raw 更新，新旧 representation 会互相覆盖。

**建议**：

```text
representations/{entity_type}/{entity_id}/v{version}/canonical.md
```

### S3. Entity ID 设计需要规范

`doc:abc123` 这种 `type:uuid` 格式在 Lance 中做过滤时需要字符串解析，性能差。

**建议**：
- `entity_id` 用纯 UUID，`entity_type` 作为独立列。
- 或用 `entity_type` + `entity_uuid` 复合主键。

### S4. 缺少"增量更新"策略

PRD 只描述了"全量重建"（raw 变了 → 全部 representation stale → 重建），没有增量策略。对于 500 页 PDF 只改了 1 页的场景，全量重建代价太高。

**建议**：
- v0.1 可以全量重建（简单可靠）。
- v0.2 引入 page-level 增量：只重建 etag 变化的 page entity 及其下游。
- 在 §16 风险中增加 R6：大文档增量更新成本。

### S5. 缺少 Embedding 模型版本管理

当 V5 升级到 V6 时，所有 embedding 需要重建。PRD 没有描述如何管理 embedding 模型版本。

**建议**：
- `embeddings` 表（或 `chunks` 表）增加 `model_version` 字段。
- Reconcile 检测 `model_version` 是否过期，触发重跑。
- Publish 时可以同时维护两个 model_version 的索引，做 A/B 对比。

### S6. NFR 缺少存储成本指标

PRD 有延迟/吞吐/可用性指标，但缺少存储成本估算。100 万页 PDF × 1024 维向量 × 每页平均 5 个 chunk 的存储量是多少？

**建议**：增加存储估算表：

| 规模 | 向量数 | 向量存储 (1024d float32) | FTS 索引 | OSS 原文 | 总计 |
| --- | --- | --- | --- | --- | --- |
| 1K 文档 | ~500K | ~2 GB | ~200 MB | ~5 GB | ~7 GB |
| 100K 文档 | ~50M | ~200 GB | ~20 GB | ~500 GB | ~720 GB |

---

## 四、优化建议（Nice to Have）

### N1. 考虑 ColPali 页面级检索

LanceDB multivector search 原生支持 ColPali（每页 ~1030 个 128 维向量，MaxSim 检索）。对于 PDF 这种版面密集的文档，ColPali 比 chunk-then-embed 精度更高。

**建议**：v0.2 评估 ColPali 作为 `page_image` 的替代 embedding 策略。

### N2. 考虑 Lance × DuckDB 作为分析层

Lance × DuckDB 扩展支持 SQL 查询 Lance 表，可以做"检索 → 分析 → 物化"的迭代循环，对调试和评估非常有用。

**建议**：v0.2 考虑引入 DuckDB 作为离线分析层。

### N3. 考虑 Query Decomposition

NVIDIA RAG Blueprint 的第 3 个关键配置就是 Query Decomposition（把复杂查询拆成子查询）。PRD 的 Intelligent Engine 只做了"路由"，没做"拆解"。

**建议**：v0.2 在 Query Understanding 阶段增加 query decomposition 能力。

### N4. 考虑 Temporal Query

LiveVectorLake 的核心卖点就是"point-in-time retrieval"。对于合规/审计场景，"这个文档上个月是怎么说的"是刚需。

**建议**：v0.2 利用 Lance 原生版本能力，支持 `?as_of=2026-05-01` 查询。

---

## 五、PRD 亮点（保持不变）

1. **Entity → Representation → Index 三层解耦**：比传统"文件 → chunk → vector"模型更灵活，支持多模态扩展。
2. **状态分层**（用户意图 vs 处理状态 vs 表现状态 vs 索引状态）：比单一 status 字段更清晰。
3. **隐藏不删除向量**：生产环境刚需，很多系统做不到。
4. **idempotent & append-only 原则**：管线可重跑是工程可靠性的基础。
5. **Provenance 必带**：可解释性是知识搜索引擎的生命线。
6. **v0.1 范围克制**：5 种文件类型、9 种 representation、5 种 index，足够验证架构，不过度承诺。

---

## 六、修改优先级汇总

| 优先级 | 编号 | 问题 | 建议动作 |
| --- | --- | --- | --- |
| **Must Fix** | P1 | 缺少 Chunk 粒度 | 增加 `chunks` 表为 v0.1 一等公民 |
| **Must Fix** | P2 | Lance 表设计未用原生能力 | 重构为 `chunks` 主表 + vector 内嵌 |
| **Must Fix** | P3 | 缺少内容寻址变更检测 | 增加 content_hash |
| **Must Fix** | P4 | 状态模型缺版本维度 | 增加 entity_version + publish 语义 |
| **Must Fix** | P5 | 多模态 embedding 策略不具体 | 增加 task 映射表 |
| **Must Fix** | P6 | 缺少 Hybrid Search API | 增加 /tools/hybrid |
| **Must Fix** | P7 | Chunking 对接路径不具体 | 增加字段映射表 |
| **Should Fix** | S1 | 缺少 Reranker | 增加可选 rerank 阶段 |
| **Should Fix** | S2 | OSS 目录缺版本 | 增加 v{version} 路径 |
| **Should Fix** | S3 | Entity ID 设计不规范 | 改为纯 UUID + entity_type 列 |
| **Should Fix** | S4 | 缺少增量更新策略 | v0.1 全量；v0.2 page-level 增量 |
| **Should Fix** | S5 | 缺少 embedding 模型版本管理 | 增加 model_version 字段 |
| **Should Fix** | S6 | NFR 缺存储成本 | 增加存储估算表 |
| **Nice to Have** | N1 | ColPali 页面级检索 | v0.2 评估 |
| **Nice to Have** | N2 | Lance × DuckDB 分析层 | v0.2 评估 |
| **Nice to Have** | N3 | Query Decomposition | v0.2 评估 |
| **Nice to Have** | N4 | Temporal Query | v0.2 评估 |

---

## 七、参考资料

| 来源 | 关键洞察 |
| --- | --- |
| [NVIDIA Enterprise RAG Blueprint](https://developer.nvidia.com/blog/build-ai-ready-knowledge-systems-using-5-essential-multimodal-rag-capabilities/) | 5 种关键配置：Baseline + Reasoning + Query Decomposition + Metadata Filtering + Visual Reasoning |
| [NVIDIA Nemotron RAG Pipeline](https://developer.nvidia.com/blog/how-to-build-a-document-processing-pipeline-for-rag-with-nemotron/) | Document → Structured Chunks → Embed → Rerank → Index，chunk 是一等公民 |
| [LiveVectorLake (arXiv 2601.05270)](https://arxiv.org/html/2601.05270) | Content-addressable chunk + Dual-tier storage + Temporal query routing |
| [Databricks AI Search](https://www.databricks.com/blog/decoupled-design-billion-scale-vector-search) | 存储计算分离 + 摄入与查询解耦 + Rust 查询引擎 |
| [Lance × DuckDB](https://www.lancedb.com/blog/lance-x-duckdb-sql-retrieval-on-the-multimodal-lakehouse-format) | 单表 hybrid search (vector + FTS) + SQL 接口 |
| [LanceDB Hybrid Search](https://docs.lancedb.com/search/hybrid-search) | RRF / CrossEncoder reranker + vector + FTS 融合 |
| [LanceDB Multivector Search](https://docs.lancedb.com/search/multivector-search) | ColPali / ColBERT 多向量存储 + MaxSim 检索 |
| [Multi-modal RAG (codesota)](https://www.codesota.com/learn/lessons/4-1-multimodal-rag) | Embed-Then-Chunk / Caption-Then-Embed / ColPali 三种策略对比 |
| [大模型知识库存储](https://docs.pingcode.com/insights/lwkja0a4yn1tebp2ooo1sop8) | 分层设计、类型分离、索引前置、治理贯穿 |
