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
| **Must Fix（v0.2 增补）** | P8 | 缺少 Wiki / 第三方消费者的统一抽象 | 新增 §11 Projector 层，把 Lake → Wiki 的集成从"宿主-后端"修正为"主体-渲染格式" |
| **Must Fix（v0.2 增补）** | P9 | Lake 写后到 wiki 可见无一致性保证 | §11.5 投影一致性等级：默认最终一致；可 `rebuild()` 全量重放 |
| **Should Fix（v0.2 增补）** | S7 | 缺少反向回写（用户手改 → Lake） | §12.6 `user_edited_md` Representation 机制；Push 默认 `protect_user_edits=true` 不覆盖 |
| **Should Fix（v0.2 增补）** | S8 | SCHEMA/index/log 全靠用户维护负担重 | §12.7 由 Lake 投影出初稿 + 维护 index/log |
| **Should Fix（v0.2 增补）** | S9 | 缺少 wiki 写入原子性 | §12.5 `atomic_per_page`（POSIX `os.replace` / OSS `CopyObject+if-match`） |
| **Nice to Have** | N1 | ColPali 页面级检索 | v0.2 评估 |
| **Nice to Have** | N2 | Lance × DuckDB 分析层 | v0.2 评估 |
| **Nice to Have** | N3 | Query Decomposition | v0.2 评估 |
| **Nice to Have** | N4 | Temporal Query | v0.2 评估 |
| **Nice to Have（v0.2 增补）** | N5 | Wiki Projector Pull 模式（`GET /v1/wiki/project/*`） | v0.2 评估；v0.1 仅 Push 模式 |

---

## 七、可靠平台视角：元数据不可靠时的重建策略

> **评审视角**：从一个生产级可靠平台的角度，审视当前 PRD 的元数据架构在"元数据丢失/损坏/不一致"时的恢复能力。核心问题：**当 OSS Tag 丢失、VFS 漂移、Lance 元数据损坏时，系统能否自愈？恢复路径是否完整？**

### 7.1 当前元数据架构的依赖链

当前 PRD 的元数据架构遵循"零持久化"原则，所有元数据从以下 3 个来源实时组装：

```text
来源1: OSS 路径结构（目录名 + 文件名）
  → entity_id, workspace_id, collection_id, stage, rep_type

来源2: OSS Object Tagging
  → Entity Tag（10个，打在 source/original 上）: entity_type, name, content_hash, version, rag_status, labels, ...
  → Rep Tag（7个，打在每个 rep 文件上）: rep_type, pipeline_id, transform, modality, status, model_version, entity_version

来源3: Lance dataset custom metadata
  → index_status, index_built_from_hash, index_built_at, index_model_version, index_pipeline_id, index_failed_reason
```

**关键假设**：这 3 个来源始终可用、始终一致。

### 7.2 故障场景分析

#### F1. OSS Tag 全部丢失（最严重）

**触发原因**：
- OSS 跨区域复制（Cross-Region Replication）默认**不复制 Tag**（需显式开启 `ReplicateTags`）
- OSS 生命周期规则误配：`Expiration` 策略只清理对象，但某些云厂商的 `NoncurrentVersionExpiration` 会清理历史版本的 Tag
- 运维误操作：`ossutil rm --tagging` 批量清除 Tag
- OSS 控制面故障：Tag 服务短暂不可用（阿里云 OSS 2024 年发生过 Tag API 499 事件）
- Bucket Policy 变更导致 Tag API 权限丢失

**影响范围**：
- Entity 属性全部丢失：`entity_type`、`content_hash`、`version`、`rag_status`、`labels` 无法读取
- Rep 属性全部丢失：`status`、`pipeline_id`、`transform`、`model_version`、`entity_version` 无法读取
- 状态联动全部失效：无法判断哪些 Rep 是 stale/failed/ready
- Index 状态丢失：Lance metadata 仍在，但 `index_built_from_hash` 无法与 Rep Tag 的 `content_hash` 对账
- **系统完全瘫痪**：VFS 能看到文件，但不知道任何文件的语义

**当前 PRD 的恢复能力**：❌ **无**。PRD 没有描述任何 Tag 重建机制。

**可恢复性分析**：

| 字段 | 能否从其他来源重建 | 重建方式 | 代价 |
|---|---|---|---|
| `entity_type` | ✅ 可重建 | 从文件 MIME 推断（但不如原始 detect 准确） | 需重新 detect |
| `name` | ✅ 可重建 | 从 source/original 的文件名提取 | 低 |
| `content_hash` | ✅ 可重建 | 重新计算 raw bytes SHA-256 | 高（需读全部 raw） |
| `version` | ⚠️ 不可靠重建 | Lance manifest 可能保留 entity_version 线索，但不可靠 | 可能丢失版本历史 |
| `rag_status` | ❌ 不可重建 | enabled/hidden/deleted 是用户意图，无法从文件推断 | **用户意图永久丢失** |
| `labels` | ❌ 不可重建 | 业务标签是人工标注，无法从文件推断 | **业务元数据永久丢失** |
| `rep_type` | ✅ 可重建 | 从路径后缀 + 命名约定表推导 | 低 |
| `pipeline_id` | ⚠️ 部分重建 | 从 rep_type 反查 RepStepRegistry 的 output_reps | 可能多对一 |
| `transform` | ⚠️ 部分重建 | 从 pipeline_id + step_id 推导 | 同上 |
| `modality` | ✅ 可重建 | 从 rep_type → 命名约定表推导 | 低 |
| `status` | ⚠️ 需重新计算 | 重新执行一致性校验（文件存在=ready? 不一定） | 需全量 reconcile |
| `model_version` | ❌ 不可重建 | 产出该 Rep 的模型版本信息无法从文件内容推断 | **需重跑 Pipeline 才能确认** |
| `entity_version` | ⚠️ 部分重建 | 从 Lance chunk 的 entity_version 列获取 | 仅限已索引的 Rep |

**结论**：OSS Tag 丢失后，**用户意图（rag_status/labels）和版本信息（version/model_version）不可恢复**，这是"零持久化"架构的根本风险。

#### F2. OSS Tag 部分损坏（Tag 与实际状态不一致）

**触发原因**：
- Tag 写入非原子：`PutObjectTagging` API 调用成功但只写了部分 Tag（网络超时后重试，但 OSS 端已部分写入）
- Pipeline 执行中断：RepStep 写了文件但未打 Tag（进程 OOM / 被杀）
- 并发写入冲突：两个 RepStep 同时写同一 Rep 的 Tag（虽然 PRD 说 Entity 内串行，但 Tag 更新可能跨 Entity）

**影响范围**：
- Rep 文件存在但 Tag `status=stale`（文件实际是新的，Tag 是旧的）
- Rep 文件不存在但 Tag `status=ready`（文件被删，Tag 未更新）
- `content_hash` Tag 与文件实际内容不匹配（文件被覆盖但 Tag 未更新）

**当前 PRD 的恢复能力**：⚠️ **部分**。Reconciler 每 15 分钟做一次全量扫描，但：
- Reconciler 依赖 Tag 中的 `source_content_hash` 来判断 Rep 是否 stale——如果 Tag 本身就是错的，Reconciler 的判断也会错
- PRD 没有描述 Reconciler 如何检测"Tag 与文件内容不一致"（§5.9.1 提到了 `body_hash` vs Tag `content_hash`，但没有详细描述检测频率和修复策略）

#### F3. VFS 漂移（内存视图与 OSS 实际状态不一致）

**触发原因**：
- OSS 事件丢失：Event Listener 宕机期间的所有事件丢失
- OSS 事件乱序：`ObjectCreated` 事件比 `ObjectModified` 先到达（OSS 事件不保证严格有序）
- VFS 内存淘汰：长时间未访问的节点被 LRU 淘汰，后续访问读到的可能是过期数据

**当前 PRD 的恢复能力**：✅ **有**。Reconciler 每 15 分钟全量扫描 + VFS 对账。但：
- 15 分钟窗口内的漂移可能导致检索返回过期结果
- PRD 没有描述 VFS 漂移的检测指标（如 `vfs_drift_count`）
- 全量扫描在大规模数据下（100K+ Entity）的延迟未量化

#### F4. Lance 元数据损坏

**触发原因**：
- Lance 数据文件损坏（磁盘 bit rot / OSS 静默数据损坏）
- Lance schema 演进失败（migration 中断）
- Lance 写入中断（进程 crash 导致 manifest 不一致）

**当前 PRD 的恢复能力**：✅ **有**。`Entity.rebuild_lance()` 支持从 OSS Rep 文件 + staging Parquet 全量重建。但：
- PRD 没有描述 `rebuild_lance()` 的触发条件（自动检测损坏？手动触发？）
- 全量重建的代价未量化（100K chunks 的重建需要多久？）
- Lance metadata 中的 `index_status` / `index_built_from_hash` 丢失后，Index 状态需要从 Rep Tag 重新推导

#### F5. OSS 对象静默损坏

**触发原因**：
- OSS 内部数据校验失败（极低概率但非零）
- 网络传输 bit flip
- 客户端写入时数据已损坏（但 OSS 端 etag 校验通过——因为 etag 是上传时计算的）

**当前 PRD 的恢复能力**：⚠️ **部分**。`content_hash`（SHA-256）可以检测损坏，但：
- PRD 没有描述定期校验 `content_hash` 的机制（Reconciler 检查的是 Tag 中的 hash vs Tag 中的 hash，不是 Tag hash vs 实际文件 hash）
- §5.9.1 提到"检查 Rep 文件的 body_hash vs Tag 中的 content_hash（防篡改/损坏）"，但没有描述 body_hash 的计算频率和代价

#### F6. OSS Tag 数量限制导致的元数据截断

**触发原因**：
- 阿里云 OSS 限制每个对象最多 **10 个 Tag**，每个 Tag Key ≤ 128 字节，Value ≤ 256 字节
- 当前 Entity Tag 已用 10 个（满额），Rep Tag 已用 7 个（预留 3 个）
- 如果未来需要新增 Tag（如 `sync_state`、`quality_score`、`source_url`），会超出限制

**当前 PRD 的恢复能力**：⚠️ **部分**。PRD 提到了 `.meta.json` sidecar 作为 v0.2+ 演进路径，但：
- sidecar 文件本身没有原子性保证（写 sidecar 和写 Tag 不是原子操作）
- sidecar 文件的损坏/丢失场景未描述
- sidecar 与 Tag 的优先级未定义（Tag 优先？sidecar 优先？合并？）

### 7.3 核心问题汇总

| # | 问题 | 严重度 | 当前状态 |
|---|---|---|---|
| **M1** | OSS Tag 全部丢失后用户意图（rag_status/labels）不可恢复 | **Must Fix** | PRD 无任何恢复机制 |
| **M2** | OSS Tag 写入非原子，可能导致 Tag 与文件状态不一致 | **Must Fix** | PRD 未描述 Tag 写入的原子性保证 |
| **M3** | `version` 字段在 Tag 丢失后不可靠重建 | **Must Fix** | 版本历史可能永久丢失 |
| **S1** | Reconciler 依赖 Tag 判断一致性，但 Tag 本身可能不可靠 | **Should Fix** | §5.9.1 有 body_hash 检查但不够具体 |
| **S2** | VFS 漂移检测无指标、无告警 | **Should Fix** | 无 `vfs_drift_count` 等指标 |
| **S3** | Lance 损坏自动检测未描述 | **Should Fix** | `rebuild_lance()` 存在但触发条件不明 |
| **S4** | OSS 对象静默损坏的定期校验未描述 | **Should Fix** | content_hash 可检测但无定期校验机制 |
| **S5** | `.meta.json` sidecar 与 Tag 的一致性未定义 | **Should Fix** | v0.2+ 演进路径但无一致性模型 |
| **S6** | Reconciler 全量扫描在大规模数据下的延迟未量化 | **Should Fix** | 15 min 周期但 100K+ Entity 场景未评估 |
| **N1** | Tag 10 个限制的扩展策略过于模糊 | **Nice to Have** | sidecar 方案仅一句话提及 |

### 7.4 重建策略建议

#### 7.4.1 核心原则：**文件是 Truth，Tag 是 Cache**

当前 PRD 的隐含假设是"Tag 是 Truth"——所有元数据从 Tag 读取，路径只是定位。但从一个可靠平台的角度，应该反过来：

> **文件内容 + 路径结构 = Ground Truth（可重建）**
> **OSS Tag = 加速缓存（可从 Ground Truth 重建）**

这意味着：
1. 所有 Tag 中的信息，要么能从文件/路径**确定性地推导**，要么能从**确定性算法重建**
2. 不能从文件/路径推导的信息（用户意图），必须有**独立的持久化存储**
3. Tag 重建 = 从 Ground Truth 重新计算 + 写回 Tag

#### 7.4.2 具体修复方案

**M1 修复：用户意图持久化**

`rag_status` 和 `labels` 是用户意图，无法从文件推断。需要独立持久化：

```text
方案A（推荐）: Entity Manifest Sidecar
  在 source/ 目录下增加 source/.entity_manifest.json
  内容：{ "rag_status": "enabled", "labels": ["pricing", "finance"], "version": 3, "content_hash": "sha256:xxx" }
  写入时机：与 Tag 写入原子绑定（先写文件再写 Tag，读时以文件为准）
  优势：与 raw 文件同目录，迁移/复制时自动跟随

方案B: 外部元数据存储（PostgreSQL / Redis）
  优势：事务性、查询能力强
  劣势：引入新依赖，与"零持久化"原则冲突
```

**M2 修复：Tag 写入原子性**

```text
当前问题：PutObjectTagging 是单次 API 调用（原子），但"写文件 + 打 Tag"是两步操作。

修复：两阶段写入协议
  Phase 1: 写 Rep 文件（内容就绪）
  Phase 2: 写 Tag（标记就绪）
  读 Tag 时：如果文件存在但 Tag 缺失/不完整 → 视为"写入中断" → 标记 status=stale → 触发重建

具体实现：
  1. RepStep.execute() 产出文件后，先写文件
  2. 文件写入成功后，调用 PutObjectTagging 打全量 Tag（原子操作）
  3. 如果步骤 2 失败，Reconciler 检测到"文件存在但 Tag 缺失" → 标 stale → 重跑
```

**M3 修复：版本历史持久化**

```text
当前问题：version 存在 Tag 中，Tag 丢失后版本历史不可恢复。

修复：版本日志文件
  在 source/ 目录下增加 source/.version_log.jsonl
  每行：{ "version": 3, "content_hash": "sha256:xxx", "timestamp": "...", "trigger": "raw_update" }
  追加写入（append-only），不修改历史行
  Tag 丢失时从 .version_log.jsonl 重建 version 字段
```

**S1 修复：Reconciler 增加 body_hash 校验**

```text
当前 §5.9.1 提到 body_hash 检查但不够具体。

增强：
  Reconciler Phase 0（在 Phase 1 之前）:
    ├─ 扫描所有 Rep 文件
    ├─ 计算文件内容的 SHA-256（body_hash）
    ├─ 对比 body_hash vs Tag 中的 content_hash
    ├─ 不匹配 → Tag 不可靠 → 以 body_hash 为准，重写 Tag
    └─ Tag 缺失 → 从路径 + 命名约定 + body_hash 重建 Tag

  频率：每天一次（非每次 Reconciler 都做，因为计算 body_hash 代价高）
  触发条件：也可由 `POST /v1/entities/{entity_id}/verify` 手动触发
```

**S2 修复：VFS 漂移指标**

```text
新增指标：
  vfs_drift_count          — Reconciler 每次扫描发现的漂移数量
  vfs_drift_type           — 漂移类型（missing_file / extra_file / tag_mismatch / hash_mismatch）
  vfs_reconcile_duration   — Reconciler 扫描耗时
  vfs_event_lag            — Event Listener 事件积压数量

告警规则：
  vfs_drift_count > 10 in 15 min → 告警
  vfs_reconcile_duration > 5 min → 告警（大规模数据下可能需要分片扫描）
```

**S3 修复：Lance 损坏自动检测**

```text
触发条件：
  1. Lance 查询抛异常（CorruptedError / SchemaError）
  2. Reconciler Phase 0 校验 Lance manifest 完整性
  3. 手动触发 `POST /v1/entities/{entity_id}/rebuild_lance`

自动恢复：
  Lance 损坏 → 标 index_status=failed → 触发 rebuild_lance()
  rebuild_lance() 从 OSS Rep 文件重跑 IndexPipeline → 重建 staging Parquet → 重建 Lance
```

**S4 修复：定期 content_hash 校验**

```text
新增 Reconciler Phase 0（每天一次）:
  ├─ 随机采样 1% 的 Rep 文件
  ├─ 计算文件内容 SHA-256
  ├─ 对比 Tag content_hash
  └─ 不匹配 → 告警 + 标 stale + 触发重建

全量校验：
  `POST /v1/admin/verify_all?mode=full` — 全量计算所有文件的 body_hash
  代价高，仅用于灾难恢复场景
```

**S5 修复：sidecar 一致性模型**

```text
优先级规则：
  1. 如果 .meta.json 存在 → 以 .meta.json 为准（它是最新写入的）
  2. 如果 .meta.json 不存在 → 以 Tag 为准
  3. 如果两者都存在但冲突 → 以 .meta.json 为准，Tag 视为过期缓存

写入协议：
  写入时：先写 .meta.json → 再写 Tag（Tag 是 .meta.json 的子集缓存）
  读取时：先读 Tag（快），如果 Tag 缺失/不完整 → 读 .meta.json（慢但可靠）

一致性保证：
  .meta.json 写入用 OSS Conditional Write（if-match etag）保证原子性
  Tag 写入失败不影响 .meta.json（下次 Reconciler 从 .meta.json 重建 Tag）
```

**S6 修复：Reconciler 分片扫描**

```text
当前：全量扫描 vector-lake/{ws}/{col}/ prefix

改进：分片扫描
  ├─ 按 entity_id 前缀分片（如 0-9, a-f, g-m, n-s, t-z）
  ├─ 每个分片独立扫描、独立对账
  ├─ 15 min 内轮完所有分片（每个分片约 1-2 min）
  └─ 大规模场景（100K+ Entity）下可配置并行扫描

指标：
  reconcile_shard_count       — 分片数量
  reconcile_shard_duration    — 单分片扫描耗时
  reconcile_entities_scanned  — 本次扫描的 Entity 数量
```

### 7.5 元数据重建的完整流程

```text
灾难恢复：OSS Tag 全部丢失
  │
  ├─ Step 1: VFS 全量扫描（从 OSS 路径重建目录树）
  │   ├─ 扫描 vector-lake/{ws}/{col}/ prefix
  │   ├─ 从路径解析：entity_id, workspace_id, collection_id, stage, rep_type
  │   └─ 产出：Entity 目录列表 + Rep 文件列表
  │
  ├─ Step 2: 重建 Entity Tag（从文件 + .entity_manifest.json）
  │   ├─ 读取 source/.entity_manifest.json → 恢复 rag_status, labels, version
  │   ├─ 重新计算 raw bytes SHA-256 → 恢复 content_hash
  │   ├─ 从文件 MIME 推断 entity_type → 恢复 entity_type
  │   ├─ 从文件名提取 name → 恢复 name
  │   └─ 写回 Entity Tag（PutObjectTagging）
  │
  ├─ Step 3: 重建 Rep Tag（从路径 + 命名约定 + 文件内容）
  │   ├─ 从路径后缀 + 命名约定表 → 恢复 rep_type
  │   ├─ 从 RepStepRegistry 反查 → 恢复 pipeline_id, transform, modality
  │   ├─ 计算文件内容 SHA-256 → 恢复 content_hash
  │   ├─ 从 .entity_manifest.json → 恢复 entity_version
  │   ├─ status 暂设 "stale"（保守策略，需重新校验）
  │   └─ 写回 Rep Tag
  │
  ├─ Step 4: 重建 Index Status（从 Rep Tag + Lance metadata）
  │   ├─ 重新计算 build_from_hash_set
  │   ├─ 对比 Lance metadata 中的 index_built_from_hash
  │   ├─ 不匹配 → 标 index_status=stale
  │   └─ 写回 Lance metadata
  │
  ├─ Step 5: 全量 Reconcile（Phase 0 + Phase 1 + Phase 2）
  │   ├─ Phase 0: body_hash 校验（确认 Step 2/3 重建的 Tag 正确）
  │   ├─ Phase 1: Rep↔Raw 一致性校验（确认所有 Rep 与 Raw 一致）
  │   └─ Phase 2: Index↔Rep 一致性校验（确认所有 Index 与 Rep 一致）
  │
  └─ Step 6: 触发必要重建
      ├─ stale Rep → 重跑 RepPipeline
      ├─ stale Index → 重跑 IndexPipeline
      └─ 产出 `recovery_report.json`（记录重建了哪些 Tag、哪些 Pipeline 被重跑）
```

### 7.6 关键设计变更建议

| # | 变更 | 原则 | 影响 |
|---|---|---|---|
| **D1** | 新增 `source/.entity_manifest.json` | 用户意图（rag_status/labels/version）必须有独立于 Tag 的持久化 | 打破"零持久化"原则，但换来可恢复性 |
| **D2** | 新增 `source/.version_log.jsonl` | 版本历史 append-only 记录 | 极小文件，不影响性能 |
| **D3** | Tag 写入协议：先文件后 Tag，Tag 视为缓存 | 文件是 Truth，Tag 是 Cache | 需修改 RepStep 写入逻辑 |
| **D4** | Reconciler 增加 Phase 0（body_hash 校验） | 不信任 Tag，信任文件内容 | 每天一次，代价可控 |
| **D5** | 新增 `POST /v1/admin/rebuild_tags` API | 一键重建所有 Tag | 灾难恢复专用 |
| **D6** | 新增 `POST /v1/admin/verify` API | 手动触发 body_hash 校验 | 运维工具 |
| **D7** | `.meta.json` sidecar 与 Tag 的一致性模型 | sidecar 优先，Tag 是缓存 | v0.2+ 实现 |

### 7.7 对"零持久化"原则的重新审视

当前 PRD 的"零持久化"原则（§4.6 核心决策第 2 条）是一个**理想化设计**——它消除了元数据同步问题，但引入了**元数据不可恢复**的根本风险。

从可靠平台的角度，建议将原则调整为：

> **准零持久化**：系统运行时从 OSS Tag + 路径实时组装元数据（零持久化运行）；但关键不可推导信息（用户意图、版本历史）以 sidecar 文件持久化，作为灾难恢复的 Ground Truth。

**不可推导信息清单**（必须持久化）：

| 信息 | 存储位置 | 可否从文件/路径推导 |
|---|---|---|
| `rag_status` | `.entity_manifest.json` | ❌ 用户意图 |
| `labels` | `.entity_manifest.json` | ❌ 业务标注 |
| `version` | `.version_log.jsonl` | ⚠️ 可从 Lance 推断但不可靠 |
| `model_version` | Rep Tag（可从重跑 Pipeline 重建） | ⚠️ 代价高但可重建 |

**可推导信息**（不需要持久化，可从 Ground Truth 重建）：

| 信息 | 推导方式 |
|---|---|
| `entity_id` | 目录名 |
| `entity_type` | 文件 MIME 推断 |
| `name` | 文件名 |
| `content_hash` | 重新计算 SHA-256 |
| `rep_type` | 路径后缀 + 命名约定表 |
| `pipeline_id` | RepStepRegistry 反查 |
| `transform` | RepStepRegistry 反查 |
| `modality` | 命名约定表 |
| `status` | 重新执行一致性校验 |
| `index_status` | 重新执行 Index↔Rep 校验 |

---

## 八、成熟项目参照设计与对比

> **评审视角**：借鉴 Delta Lake、Apache Iceberg、lakeFS、Lance 4 个成熟数据湖/表格式项目的元数据管理设计，评估当前 PRD 元数据架构的优化空间。
>
> 这 4 个项目都已通过生产级验证，其元数据设计原则是行业的"标准答案"。

### 8.1 4 个项目的元数据架构对比

| 项目 | 元数据存储 | 原子性保证 | 版本管理 | 适用场景 | 关键创新 |
|---|---|---|---|---|---|
| **Delta Lake** | `_delta_log/00000000000000000000.json` 序列 + Parquet checkpoint | 乐观并发控制 + Conditional Put（`PUT-if-absent`） | 单调递增 version + Time Travel | 高吞吐批处理 + Spark/Databricks 生态 | JSON 事务日志 + Checkpoint 加速 |
| **Apache Iceberg** | `metadata.json` + Manifest List (Avro) + Manifest (Avro) + Data File | 原子指针交换（compare-and-swap on catalog） | Snapshot + Time Travel | 跨引擎互操作（Spark/Trino/Flink）+ 湖仓 | 三层元数据 + 列级统计 + 隐藏分区 |
| **lakeFS** | Graveler Ranges + Meta-Range（Merkle 树）+ Object Store pointer | 零拷贝分支 + 原子提交 | Git-like commit/branch/merge/tag | 数据湖版本控制 + CI/CD for data | 2 层 Merkle 树 + 不可变 SSTable |
| **Lance** | Manifest (Protobuf) + Data Fragments + Index Sections | MVCC + 原子 Manifest 替换 | 单调递增 version + Time Travel | ML/AI 场景 + 多模态 RAG | 两维存储 + 一等 Index + External Manifest Store |

### 8.2 核心设计模式提取

#### 模式 1：事务日志（Transaction Log）

**Delta Lake 的实现**：
```
_delta_log/
  00000000000000000000.json    ← 初始表结构
  00000000000000000001.json    ← 第一次 commit（add file）
  00000000000000000002.json    ← 第二次 commit（remove + add）
  ...
  00000000000000000010.checkpoint.parquet  ← 10 次 commit 后聚合
```

**关键特征**：
- 每个 commit = 一个原子 JSON 文件
- 写入流程：先写数据文件 → 再写 JSON commit（Conditional PUT）
- 读取流程：从最近 checkpoint 重放 JSON commits → 重建当前状态
- CRC 文件校验日志完整性（Delta 3.x 已弃用）
- 优化：日志压缩（compacted.json）、Checkpoint Parquet

**借鉴价值**：
- 当前 PRD 的"零持久化"完全依赖 OSS Tag + 路径，没有事务日志概念
- 一旦 OSS Tag 丢失，**没有任何线索重建变更历史**
- 应该引入 append-only 事务日志，**记录所有 Entity/Rep/Index 状态变更**

#### 模式 2：原子指针交换（Atomic Pointer Swap）

**Iceberg 的实现**：
```text
Step 1: Write Data Files (Parquet)
Step 2: Create Manifest Entries
Step 3: Create/Update Manifest Files (Avro)
Step 4: Create Manifest List (Avro)
Step 5: Create New metadata.json (new snapshot)
Step 6: Atomic Commit (compare-and-swap on metadata location pointer)
        ↑ 这一步是 ACID 的核心
        ↑ Before: readers see old snapshot
        ↑ After: readers see new snapshot
        ↑ No in-between state
```

**关键特征**：
- Catalog 保存一个指针（"当前 metadata.json 在哪里"）
- 写入新 metadata.json 后，原子交换指针
- 依赖 Catalog 的 compare-and-swap 语义（`if-match`）
- OSS/S3 的实现：`CopyObject` + `if-match etag` 或 `PUT-if-absent`

**借鉴价值**：
- 当前 PRD 的"先写文件再打 Tag"是两步操作，**没有原子指针交换**
- 改进方案：在每个 Entity 目录加 `_current` 指针文件，写入协议改为"写新 manifest → 原子交换 _current"

#### 模式 3：三层元数据（Three-tier Metadata）

**Iceberg 的实现**：
```text
Catalog pointer → metadata.json (v1, v2, v3, ...)
                    ↓
                    Manifest List (per snapshot)
                    ↓
                    Manifest Files (per partition, with column stats)
                    ↓
                    Data Files (Parquet)
```

**关键特征**：
- 三层递进：Catalog → metadata.json → Manifest List → Manifest → Data File
- 每层有不同作用：版本管理 / snapshot 索引 / 文件清单 + 统计 / 实际数据
- Manifest 包含列级统计（min/max/null_count），支持分区裁剪和文件裁剪
- 大规模数据集下也能 O(1) 找到目标文件

**借鉴价值**：
- 当前 PRD 是单层：Entity 目录 → Rep 文件 → Lance 表，**没有中间索引层**
- 100K+ Entity 规模下，全量扫描 prefix 会很慢
- 应该引入"Entity Manifest"中间层（参考 Iceberg 的 Manifest List），包含 Entity 级别的统计信息

#### 模式 4：Merkle 树 + Ranges（lakeFS Graveler）

**lakeFS 的实现**：
```text
Commit
  └─ Meta-Range（内容寻址，SSTable 格式）
       └─ Ranges（按 key 范围分片）
            └─ ValueRecord（key, identity=sha256, value=metadata）
```

**关键特征**：
- 2 层 Merkle 树：Meta-Range → Ranges
- 内容寻址：ValueRecord 的 identity = sha256(value)
- Commit 之间复用未修改的 Ranges（零拷贝分支）
- Diff 算法 O(diff_size) 而非 O(total_size)
- 不可变 SSTable 格式：一旦写入，永不修改

**借鉴价值**：
- 当前 PRD 的"血缘"是从目录层级推导的，**每次扫描都要重新计算**
- 应该把血缘关系**显式持久化**为内容寻址的 Merkle 树结构
- 大规模场景下（100K+ Entity），血缘计算效率可提升 10-100x

#### 模式 5：MVCC + 不可变 Manifest（Delta + Iceberg + Lance 共有）

**Lance 的实现**：
```protobuf
message Manifest {
  repeated Field fields = 1;        // 完整 schema（包括嵌套字段）
  map<string, bytes> schema_metadata = 5;
  repeated DataFragment fragments = 2;  // 数据片段
  uint64 version = 3;               // 单调递增
  uint64 version_aux_data = 4;      // 可选辅助数据
  WriterVersion writer_version = ...;
}
```

**关键特征**：
- 每次写入产生**新**的 Manifest，旧 Manifest 保留
- 原子协议：先写 Manifest → 再 atomic swap pointer
- 读者看到 consistent snapshot（基于 version）
- Time Travel：通过指定旧 version 读取历史
- 冲突检测：基于 version 号的 optimistic concurrency

**借鉴价值**：
- 当前 PRD 的 Lance 数据集没有显式的 Manifest 概念（依赖 Lance 内部）
- 应该让 Entity-level Manifest 显式化，作为 Entity 的"Truth of State"
- Rep + Index 的状态变更统一记录到 Entity Manifest

#### 模式 6：Schema Evolution（Delta + Iceberg + Lance 共有）

**三个项目的共同设计**：
- Schema 是 metadata 的一部分，记录在事务日志 / metadata.json / Manifest
- 字段有唯一 field ID（Iceberg 独有）
- 支持：加列、删列、改列类型、改列顺序
- 兼容性规则：向后兼容（读旧 schema 读新数据）、向前兼容（读新 schema 读旧数据）
- Schema 检查点：定期冻结 schema snapshot 加速查询

**借鉴价值**：
- 当前 PRD 的"§15 NFR R4 Lance schema 演进"提到"所有表带 schema_version，变更走 migration"
- 但 Entity-level schema（entity_type、rep_type 集合）的演进规则未定义
- 应该引入 Entity-level schema versioning，明确 Entity 字段的可演进规则

### 8.3 当前 PRD 元数据架构的问题

基于上述 6 个成熟模式，对比当前 PRD：

| 设计模式 | 当前 PRD | 问题 | 严重度 |
|---|---|---|---|
| **事务日志** | ❌ 无 | 状态变更历史不可追溯；Tag 丢失后无法重建变更序列 | Must Fix |
| **原子指针交换** | ❌ 无 | "先写文件再打 Tag"是两步操作；中间态导致不一致 | Must Fix |
| **三层元数据** | ⚠️ 单层 | Entity → Rep → Lance，缺中间索引层；大规模扫描慢 | Should Fix |
| **Merkle 树** | ❌ 无 | 血缘每次重新计算；无法复用历史 | Should Fix |
| **MVCC + 不可变 Manifest** | ⚠️ 部分 | Lance 内部有 MVCC，但 Entity 状态没有 Manifest 显式化 | Should Fix |
| **Schema Evolution** | ⚠️ 部分 | Lance 表 schema 有，但 Entity/Rep schema 演进未定义 | Should Fix |
| **Checkpoint / Compaction** | ❌ 无 | 没有事务日志压缩机制；metadata 增长无界 | Should Fix |
| **Catalog 抽象** | ❌ 无 | 没有 Catalog 概念；状态机分散在 OSS Tag | Should Fix |

### 8.4 优化设计建议（参照成熟项目）

#### 优化 1：引入事务日志（参考 Delta Lake）

```text
vector-lake/{ws}/{col}/{entity_id}/_log/
  000000000000.json    ← 初始 Rep 状态
  000000000001.json    ← "render_page" 产出 page_image
  000000000002.json    ← "ocr" 产出 ocr_text
  000000000003.json    ← raw update → 级联标 stale
  000000000004.json    ← "ocr" 重建
  ...
  000000000100.checkpoint.jsonl  ← 100 次 commit 后聚合（参考 Delta）
```

**事务日志格式**（每行一个 JSON action）：

```json
{"add": {"path": "extract/canonical.md", "rep_type": "canonical_md", "content_hash": "sha256:abc", "size": 12345, "tags": {...}}}
{"remove": {"path": "recognize/ocr_text.md"}}
{"stale": {"rep_type": "ocr_text", "reason": "raw_update", "upstream_hash": "sha256:def"}}
{"index_built": {"index_type": "semantic", "build_from_hash": "sha256:combined"}}
{"checkpoint": {"version": 100}}
```

**借鉴价值**：
- 完整的变更历史可回放
- 灾难恢复时，从 checkpoint + 日志重放 = 完整重建
- 时间旅行：读 `version=N` = 回到 Entity 的某个历史状态

#### 优化 2：原子指针交换（参考 Iceberg）

**当前问题**：
```python
# 旧协议（两步，非原子）
1. write Rep file to OSS      ← 文件存在
2. put_object_tagging(rep)    ← Tag 写入
   → 中间态：文件存在但 Tag 缺失
   → 此时崩溃 → Reconciler 需要检测 + 修复
```

**新协议**（基于 Iceberg）：
```python
# 新协议（基于 _current 指针的原子交换）
1. write new manifest to /_log/000000000101.json  (Conditional PUT, if-match)
2. write Rep file to /extract/canonical.md
3. atomic swap: write /_current with new pointer
   # 写入协议：PutObject with if-match on _current.etag
   # 成功 = 新版本生效；失败 = 旧版本继续生效，下次重试
```

**关键改造**：
- 每个 Entity 目录增加 `_current` 指针文件（指向当前 manifest 位置）
- 写入协议改为"先写 manifest → 写 Rep 文件 → 原子交换 _current"
- 读取时：先读 `_current` → 拿到当前 manifest → 知道有哪些 Rep

#### 优化 3：三层元数据（参考 Iceberg）

```text
Lake 目录
  ├─ _catalog/                         ← L0: 全局 Catalog（workspace 级）
  │   └─ {collection_id}.json          ← 指向 _current 指针位置
  │
  └─ {entity_id}/
      ├─ _current                      ← L1: Entity 当前状态指针
      │
      ├─ _log/                         ← L2: 事务日志
      │   ├─ 000000000000.json         ← append-only
      │   ├─ 000000000001.json
      │   └─ 000000000100.checkpoint.jsonl
      │
      ├─ _manifest/                    ← L3: 快速查找索引（参考 Iceberg Manifest）
      │   ├─ reps.jsonl                ← 所有 Rep 列表 + 列级统计
      │   ├─ indexes.jsonl             ← 所有 Index 列表
      │   └─ edges.jsonl               ← 所有 Edge 列表
      │
      ├─ source/                       ← 实际数据
      ├─ extract/
      ├─ recognize/
      └─ _index/
```

**L3 _manifest 作用**：
- 替代"每次扫描 prefix"，直接读 `_manifest/reps.jsonl` 拿到所有 Rep 列表
- 包含列级统计：rep_type / status / content_hash / size / mtime
- 写入协议：每次 Rep 变更追加一行到 `reps.jsonl`（append-only）
- 定期 compaction（小文件合并）

**优势**：
- O(1) 拿到 Entity 状态（不需要 LIST prefix）
- 大规模场景下（100K+ Entity）扫描时间从分钟级降到秒级
- 灾难恢复：`_manifest` + `_log` 即可重建整个 Entity 状态

#### 优化 4：Merkle 树血缘（参考 lakeFS Graveler）

```text
Lineage Merkle Tree
  └─ Root (sha256)
       ├─ rep:raw (sha256 of Rep's content_hash)
       ├─ rep:canonical_md (sha256)
       │    └─ upstream: raw (sha256)
       └─ rep:ocr_text (sha256)
            └─ upstream: page_image (sha256)
```

**优势**：
- 血缘关系**显式持久化**为内容寻址
- Diff 算法 O(diff_size) 而非 O(total_size)
- 跨 Entity 血缘追踪更高效
- 支持"零拷贝" Entity 快照（复用未修改的 Rep）

#### 优化 5：Lance Manifest 显式化（参考 Lance spec）

**当前**：PRD 把 `index_status` / `index_built_from_hash` 存在 Lance dataset custom metadata（§5.10.2）

**改进**：
- Entity 级 Manifest（`_manifest/reps.jsonl`）作为 Entity 的 Truth of State
- Lance dataset custom metadata 仅作为快速缓存
- Manifest 写入协议：先写 Lance → 再写 `_manifest`（如果失败可重建）

#### 优化 6：Schema Evolution 规则（参考 Delta + Iceberg）

**Entity Schema 演进规则**：
```text
v0.1 初始 Entity Schema
  ↓ 加 entity_type: video
v0.2 Schema Evolution
  → 旧 Entity 不受影响（向后兼容）
  → 新 Entity 可用新 entity_type
  → Manifest 记录 schema_version
```

**Rep Schema 演进规则**：
```text
v0.1 Rep Tag: 7 个字段
  ↓ 加 sync_state 字段（v0.2 引入 Projector 需要）
v0.2 Rep Schema Evolution
  → 旧 Rep Tag 自动补全默认 sync_state=ready
  → Manifest 记录 schema_version
  → 旧读卡器忽略未知字段
```

### 8.5 完整优化后的元数据架构

```text
Lake 目录
│
├─ _catalog/                                  ← 全局 Catalog（workspace 级）
│   └─ {collection_id}.json → 指向 _current 指针
│
└─ {entity_id}/
    │
    ├─ _current                               ← Entity 当前状态指针（原子交换）
    │
    ├─ _log/                                  ← 事务日志（参考 Delta _delta_log）
    │   ├─ 000000000000.json
    │   ├─ 000000000001.json
    │   └─ 000000000100.checkpoint.jsonl     ← 周期 Checkpoint（参考 Delta）
    │
    ├─ _manifest/                             ← 快速查找索引（参考 Iceberg Manifest）
    │   ├─ entity.json                        ← Entity 元数据（rag_status, labels, version）
    │   ├─ reps.jsonl                         ← 所有 Rep 列表 + 统计
    │   ├─ indexes.jsonl                      ← 所有 Index 列表
    │   ├─ edges.jsonl                        ← 所有 Edge 列表
    │   └─ schema_version                     ← 当前 schema 版本
    │
    ├─ source/                                ← 实际数据
    │   └── original
    ├─ extract/
    │   └── canonical.md
    ├─ recognize/
    │   └── ocr_text.md
    └─ _index/
        └─ representations.lance/
```

**写入协议**（新）：
```text
1. write Rep file to /extract/canonical.md
2. write action to /_log/000000000101.json (append)
   {"add": {"path": "extract/canonical.md", ...}}
3. update /_manifest/reps.jsonl (append row)
4. atomic swap /_current → 指向 /_log/000000000101.json
   PutObject with if-match on _current.etag
   - 成功：新版本生效
   - 失败：旧版本继续生效，下次重试
```

**读取协议**（新）：
```text
1. 读 /_current → 拿到当前 manifest 位置
2. 读 manifest 位置 → 拿到 Entity 完整状态
3. 读具体 Rep 文件
```

**Checkpoint 协议**（参考 Delta）：
```text
每 100 次 commit 触发一次 Checkpoint：
1. 重放最近 100 次 commit
2. 合并为单一 checkpoint.jsonl（包含所有 active Rep + Index + Edge）
3. 写 /_log/000000000100.checkpoint.jsonl
4. atomic swap /_current → 指向 checkpoint
   - 后续读从 checkpoint 开始
   - 历史 commit 保留（用于 time travel / 灾难恢复）
```

### 8.6 优化前后对比

| 维度 | 优化前 | 优化后 | 借鉴项目 |
|---|---|---|---|
| **变更历史** | 无（只有当前 Tag） | 完整 append-only 事务日志 | Delta Lake |
| **原子性** | 2 步操作（写文件 + 打 Tag） | 4 步操作（含 manifest + 原子指针） | Iceberg |
| **大规模扫描** | 全量 LIST prefix | 读 `_manifest/reps.jsonl` O(1) | Iceberg |
| **灾难恢复** | 仅依赖 `.entity_manifest.json` + Tag | 完整事务日志 + Checkpoint | Delta + Iceberg |
| **Time Travel** | 不支持 | 通过 manifest version 回放 | Delta + Iceberg + Lance |
| **血缘** | 每次重新计算 | Merkle 树内容寻址 | lakeFS |
| **Schema 演进** | 未定义 | 显式 schema_version + 兼容性规则 | Delta + Iceberg + Lance |
| **零拷贝快照** | 不支持 | Merkle 树复用未修改 Rep | lakeFS |
| **实现复杂度** | 低 | 中（需管理 _log / _manifest / _current） | — |

### 8.7 实施路径建议

| 阶段 | 内容 | 优先级 |
|---|---|---|
| **v0.1（当前）** | `.entity_manifest.json` + `.version_log.jsonl`（已实现） | ✅ |
| **v0.2 阶段 1** | 引入 `_current` 指针 + 原子指针交换协议 | 高 |
| **v0.2 阶段 2** | 引入 `_log/` 事务日志（add/remove/stale actions） | 高 |
| **v0.2 阶段 3** | 引入 `_manifest/` 快速查找索引（reps.jsonl / indexes.jsonl） | 中 |
| **v0.2 阶段 4** | Checkpoint 机制（每 N 次 commit 合并） | 中 |
| **v0.2 阶段 5** | Merkle 树血缘（Content-addressable Ranges） | 低 |
| **v0.3** | Schema Evolution 规则 | 中 |
| **v0.3** | Time Travel API | 低 |

---

## 九、产品级 Review：架构一致性 + 实现可行性 + 边界场景

> **评审视角**：从"能落地"的角度，审查 PRD 的架构一致性、实现可行性和边界场景覆盖。重点关注"写了很多设计但实际跑不起来"的问题。

### 9.1 架构一致性问题

#### C1. 元数据存储三重冗余，一致性模型不完整

**现状**：同一个 `rag_status` 存在三个地方：
1. OSS Entity Tag（`rag_status=enabled`）
2. `.entity_manifest.json`（`{"rag_status": "enabled"}`）
3. v0.2 `_manifest/entity.json`（§5.12.11）

**问题**：PRD 定义了"manifest 优先"原则（§5.12.2），但没有定义**写入失败时的降级策略**：
- 写 manifest 成功 + 写 Tag 失败 → OK（下次 Reconciler 修）
- 写 manifest 失败 + 写 Tag 成功 → **Tag 和 manifest 不一致**
- 两者都失败 → Entity 处于"未知状态"

**建议**：增加写入状态机，明确每种失败组合的处理策略。

#### C2. Entity class 方法与 Pipeline 解耦不彻底

**现状**：§4.1 Entity class 有 `generate_representation()` 和 `build_index()` 方法，但 §6 说 Pipeline 由 RepStep/IndexStep 调度。

**问题**：Entity 是"触发器"还是"执行者"？
- 如果是触发器：`generate_representation()` 只投递消息到 Redis Streams，不执行
- 如果是执行者：`generate_representation()` 直接调用 RepStep.execute()

PRD 没有明确这一点。当前 §4.1 的 Entity class 像执行者（有 `search()` / `grep()` 等实现），但 §6.9 的 Worker 伪代码又暗示 Entity 只是消息源。

**建议**：明确 Entity 是"领域模型 + 触发器"，不是"执行者"。执行由 Worker 进程完成。Entity class 的 `generate_*` / `build_*` 方法只做 `XADD` 到 Redis Streams。

#### C3. RepStep 的 `required_input_reps` 与 Redis Streams 消息格式不匹配

**现状**：§6.6 RepStep 定义了 `required_input_reps: list[str]`（如 `["page_image"]`），但 §6.9.2 Redis Streams 消息格式只有 `step_id`，没有 `input_reps` 信息。

**问题**：Worker 拿到消息后，如何知道要读哪些 input Rep？需要从 RepStepRegistry 查 `step.required_input_reps`，然后从 OSS 读取。但消息里没有 `rep_types` 的具体路径。

**建议**：消息格式增加 `input_reps` 字段（运行时由 Orchestrator 填充具体路径），或者 Worker 从 Registry + Entity 目录动态解析。

#### C4. v0.1 Entity Tag 10 个字段已满，v0.2 无法扩展

**现状**：§4.6 Entity Tag 10 个字段（entity_type, name, content_hash, version, rag_status, labels, workspace_id, collection_id, entity_id, source_format），阿里云 OSS 限制每个对象最多 10 个 Tag。

**问题**：v0.2 Projector 需要 `sync_state` 字段，但 10 个 Tag 已满。PRD 提到了 `.meta.json` sidecar（§5.12.8）但只定义了优先级规则，没有定义具体迁移策略。

**建议**：v0.1 就预留 1-2 个 Tag 位置（如 `_reserved1`, `_reserved2`），或者将 `workspace_id` / `collection_id` / `entity_id` 从 Tag 移到路径推导（这三个本来就能从路径解析，不需要存 Tag）。

#### C5. MCP Tools 与 REST API 功能重叠

**现状**：§14 定义了 REST API（`GET /v1/entities/{id}` 等），§9.5 定义了 MCP Tools（`vfs_get_entity` 等），两者功能完全重叠。

**问题**：维护两套 API 的成本高。MCP Tools 底层是调 REST API 还是直接访问 OSS？

**建议**：MCP Server 底层复用 REST API 的 Service 层（不是 HTTP 调用，而是共享 Python 函数）。REST API 和 MCP Tools 是同一套业务逻辑的两种暴露方式。

### 9.2 实现可行性问题

#### F1. OSS Conditional Write (if-match etag) 支持有限

**现状**：§5.12.2 和 §5.12.9 大量使用 OSS Conditional Write（`if-match etag`）保证原子性。

**问题**：
- 阿里云 OSS 的 `PutObject` **不支持** `if-match`（只有 `CopyObject` 和 `HeadObject` 支持）
- AWS S3 的 `PutObject` 也不支持 `if-match`（只有 `CopyObject` 支持）
- MinIO 的 `PutObject` 同样不支持

**这意味着**：`.entity_manifest.json` 的 Conditional Write 在 OSS 上**不可行**。

**替代方案**：
1. 用 `CopyObject` + `if-match` 模拟（先写临时文件，再 CopyObject 到目标路径）
2. 用 ETag-based 乐观锁（读 etag → 写入时带 etag 校验 → 失败则重试）
3. v0.1 放弃 Conditional Write，依赖 Reconciler 修复不一致

**建议**：§5.12.2 明确标注"OSS PutObject 不支持 if-match"，改用方案 1 或 3。

#### F2. Reconciler Phase 0 body_hash 计算代价过高

**现状**：§5.12.3 Phase 0 每天采样 1% 的 Rep 文件计算 SHA-256。

**问题**：
- 1% 的 Rep 文件 = 假设 10K Entity × 平均 5 Rep = 50K 文件 × 1% = 500 文件/天
- 每个 Rep 平均 100KB → 50MB/天的 OSS 下载量（可接受）
- 但如果 Entity 包含大文件（如 100MB PDF 的 page_image），1% 可能命中大文件 → 带宽暴增
- SHA-256 计算本身不是瓶颈，**OSS 下载带宽**才是

**建议**：Phase 0 改为"只校验 ETag（OSS 自带的 MD5）vs Tag content_hash"，不重新计算 SHA-256。ETag 校验零下载（HeadObject 即可）。只有 ETag 不匹配时才下载文件计算 SHA-256。

#### F3. OSS LIST API 每次最多返回 1000 个对象

**现状**：§4.6 VFS 通过 `LIST prefix` 扫描目录树。

**问题**：
- OSS LIST API 每次最多返回 1000 个对象（`max-keys=1000`）
- 10K Entity × 平均 10 个文件 = 100K 对象 → 需要 100 次 LIST 调用
- 100 次 LIST × 平均 100ms = 10s（可接受）
- 但 100K Entity × 10 = 1M 对象 → 1000 次 LIST → 100s（不可接受）

**建议**：
1. VFS 维护 Redis 缓存（已有），LIST 只在冷启动时做
2. v0.2 引入 `_manifest/reps.jsonl`（§5.12.11）替代 LIST
3. 冷启动时用 OSS Event Notification 增量更新，不做全量 LIST

#### F4. Redis Streams 无 per-entity 有序保证

**现状**：§6.8 说"Entity 内串行"，§6.9 用 Redis Streams Consumer Group。

**问题**：Redis Streams 的 Consumer Group **不保证同一 entity_id 的消息被同一 consumer 按序消费**。两个 `render_page` 消息（同一 entity_id）可能被不同 worker 同时消费。

**当前方案**：§6.9.3 用 `redis_lock(f"rep:{entity_id}")` 解决。但：
- 分布式锁有超时风险（worker 处理慢 → 锁超时 → 另一 worker 拿到锁 → 重复执行）
- 锁超时设置太长 → worker crash 后锁长时间不释放

**建议**：
1. 锁超时 = step 预估耗时 × 3（如 `render_page` 预估 30s → 锁超时 90s）
2. 加锁时写入 worker_id + timestamp，超时后其他 worker 可以安全抢占
3. 或者改用 Redis Stream 的 `XADD` + `MAXLEN ~` 按 entity_id 分 stream（但 stream 数量会暴增）

#### F5. Lance dataset custom metadata 有大小限制

**现状**：§5.10.2 把 `index_built_from_hash` 等信息存在 Lance dataset custom metadata。

**问题**：Lance 的 `manifest.metadata` 是 Protobuf `map<string, bytes>`，理论上无大小限制，但：
- 每次 `update_metadata()` 会重写整个 Manifest
- 如果 metadata 过大（如存储了 100 个 index 的 `built_from_hash`），写入延迟增加
- Lance 的 `update_metadata()` 不是原子操作（先读旧 Manifest → 修改 → 写新 Manifest）

**建议**：v0.1 限制每个 Entity 最多 5 个 Index（语义/全文/结构/图/多模态），metadata 大小可控。v0.2 迁移到 `_manifest/indexes.jsonl`。

#### F6. `.entity_manifest.json` 的 append-only 写入在 OSS 上不可行

**现状**：§5.12.1 `.entity_manifest.json` 用 Conditional Write（`if-match etag`）保证原子性。

**问题**：
- OSS `PutObject` 不支持 `if-match`（见 F1）
- 每次更新 manifest 需要先读旧值 → 合并 → 写新值 → 如果中间有人写了 → 冲突
- 这是一个 **read-modify-write** 竞态条件

**建议**：
1. v0.1 放弃 Conditional Write，接受"最后一个写入者赢"（last-writer-wins）
2. Reconciler 定期校验 manifest vs Tag 一致性
3. v0.2 用 `_current` 指针原子交换（`CopyObject` + `if-match` 是支持的）

### 9.3 边界场景缺失

#### E1. Entity 目录下有大量 page_image 文件时的性能

**现状**：一个 100 页 PDF 会产出 100 个 `page_image/page_001.png` ... `page_image/page_100.png`。

**问题**：
- 每个 page_image 都有 7 个 Rep Tag → 100 × 7 = 700 次 `PutObjectTagging` API 调用
- LIST prefix 扫描 `extract/page_image/` 返回 100 个对象
- Lance 表中 100 个 page_image 各自的 chunk 数量

**缺失**：PRD 没有定义"多文件 Rep"的批量 Tag 写入策略和 LIST 优化。

**建议**：`page_image` 类 Rep 用"目录级 Tag"（打在目录的 `.meta` 文件上）而非逐文件打 Tag。

#### E2. 并发写入同一 Entity 的不同 RepPipeline

**现状**：§6.8 说"Entity 内串行"，但 §6.9 的 Redis Streams 拓扑中，`rep_pipeline` stream 的消息可能同时触发同一 Entity 的 `parse` 和 `render_page`。

**问题**：`parse` 和 `render_page` 都读 `raw` 文件，不冲突。但它们都写 `extract/` 目录，且都需要更新 `.entity_manifest.json`。

**缺失**：PRD 没有定义"同一 Entity 的不同 RepPipeline 是否可以并行"的粒度。

**建议**：明确"Entity 内 RepPipeline 间可并行，RepStep 间串行"。锁粒度从 Entity 级改为 RepPipeline 级。

#### E3. Entity 删除后的 Lance 数据清理

**现状**：§5.10.3 说 `entity status=deleted → index_status=deleted + 实际删除 Lance 数据集`。

**问题**：Lance 数据集删除是**不可逆**的。如果误删 Entity，Lance 数据无法恢复（即使 OSS 文件还在）。

**缺失**：没有定义"软删除期间 Lance 数据保留策略"。

**建议**：`rag_status=deleted` 时只标记 Tag，不删 Lance 数据。Lance 数据在"硬删除"（`destroy()`）时才物理删除。Reconciler 定期清理 `deleted > 30 days` 的 Entity。

#### E4. Embedding 模型升级时的全量重建策略

**现状**：§5.10.3 说"embedding 模型升级 → index_status=stale → 触发重跑"。

**问题**：全量重建 10K Entity 的 Index 需要：
- 10K × 平均 5 chunks = 50K 次 Embedding API 调用
- 如果用 OpenAI API → $0.13/1K tokens × 50K × 500 tokens ≈ $3,250
- 如果用本地模型 → 需要 GPU 资源

**缺失**：没有定义"渐进式模型升级"策略（如按 Entity 优先级分批重建）。

**建议**：增加"Index 重建优先级"概念（high/medium/low），模型升级时按优先级分批重建。

#### E5. MCP Server 的权限模型

**现状**：§9.5.2 提到"Bearer Token / mTLS"但没定义权限模型。

**问题**：
- `vfs_get_status` 暴露系统内部状态（Reconciler / 队列积压），不应给普通用户
- `vfs_search` 可能返回 `rag_status=hidden` 的 Entity（如果没做权限过滤）
- `vfs_get_rep_content` 可能返回敏感内容

**缺失**：MCP Tools 没有权限分级。

**建议**：MCP Tools 增加 `required_role` 标注（admin / user / readonly），SSE 模式下按 Token role 过滤。

#### E6. Redis Streams 消息积压时的背压策略

**现状**：§6.9 定义了 Consumer Group 但没有背压策略。

**问题**：如果 OSS Event 突然涌入大量消息（如批量上传 1000 个文件），Redis Streams 积压 → Worker 处理不过来 → 内存增长 → Redis OOM。

**缺失**：没有定义 `MAXLEN` 策略和背压机制。

**建议**：
1. `XADD` 时设置 `MAXLEN ~ 100000`（近似裁剪，保留最近 10 万条）
2. Worker 消费延迟 > 5 min → 告警
3. 积压 > 50K → 触发背压（拒绝新的 OSS Event Webhook，返回 429）

### 9.4 问题汇总与优先级

| # | 问题 | 严重度 | 类型 | 建议修复 |
|---|---|---|---|---|
| **C1** | 元数据三重冗余一致性模型不完整 | **Must Fix** | 一致性 | 增加写入状态机 |
| **C2** | Entity class 是触发器还是执行者不明确 | **Must Fix** | 架构 | 明确 Entity = 触发器，Worker = 执行者 |
| **C3** | RepStep required_input_reps 与消息格式不匹配 | **Should Fix** | 一致性 | 消息增加 input_reps 或 Worker 动态解析 |
| **C4** | Entity Tag 10 个已满，v0.2 无法扩展 | **Must Fix** | 可扩展性 | 移除可推导字段（workspace_id/collection_id/entity_id） |
| **C5** | MCP Tools 与 REST API 功能重叠 | **Should Fix** | 架构 | 共享 Service 层 |
| **F1** | OSS PutObject 不支持 if-match | **Must Fix** | 可行性 | 改用 CopyObject+if-match 或 last-writer-wins |
| **F2** | Phase 0 body_hash 计算代价过高 | **Should Fix** | 可行性 | 改为 ETag 校验（HeadObject），不下载文件 |
| **F3** | OSS LIST API 1000 对象限制 | **Should Fix** | 可行性 | VFS Redis 缓存 + v0.2 manifest |
| **F4** | Redis Streams 无 per-entity 有序保证 | **Should Fix** | 可行性 | 锁超时 = 预估耗时 × 3 + worker_id |
| **F5** | Lance metadata 大小限制 | **Nice to Have** | 可行性 | v0.1 限制 5 个 Index |
| **F6** | .entity_manifest.json read-modify-write 竞态 | **Must Fix** | 可行性 | v0.1 last-writer-wins + Reconciler 修复 |
| **E1** | 多文件 Rep 批量 Tag 写入 | **Should Fix** | 边界 | 目录级 .meta 文件 |
| **E2** | 同 Entity 不同 RepPipeline 并行粒度 | **Should Fix** | 边界 | 锁粒度改为 RepPipeline 级 |
| **E3** | 软删除后 Lance 数据保留策略 | **Should Fix** | 边界 | deleted 只标 Tag，destroy 才物理删 |
| **E4** | Embedding 模型升级全量重建策略 | **Should Fix** | 边界 | 按优先级分批重建 |
| **E5** | MCP Server 权限模型 | **Should Fix** | 边界 | Tools 增加 required_role |
| **E6** | Redis Streams 背压策略 | **Should Fix** | 边界 | MAXLEN + 告警 + 429 |

### 9.5 关键优化建议（Top 5）

1. **Entity Tag 从 10 个减到 7 个**：移除 `workspace_id` / `collection_id` / `entity_id`（可从路径推导），为 v0.2 预留 3 个位置（`sync_state` / `quality_score` / `custom_1`）

2. **OSS Conditional Write 降级**：v0.1 用 last-writer-wins + Reconciler 修复，不依赖 `if-match`（OSS PutObject 不支持）；v0.2 用 `CopyObject` + `if-match` 实现原子交换

3. **Phase 0 改为 ETag 校验**：不下载文件计算 SHA-256，而是 `HeadObject` 获取 ETag → 对比 Tag `content_hash` → 不匹配才下载计算 SHA-256。代价从 O(file_size) 降到 O(1)

4. **Entity = 触发器，Worker = 执行者**：Entity class 的 `generate_*` / `build_*` 方法只做 `XADD` 到 Redis Streams，不直接执行 RepStep。所有执行由 Worker 进程完成

5. **软删除不删 Lance**：`rag_status=deleted` 只标记 Tag，Lance 数据保留 30 天。`destroy()` 才物理删除

---

## 十、参考资料

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
