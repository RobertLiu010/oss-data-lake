# Vector-Lake 智能知识搜索引擎层 — PRD

> **版本**：v0.2 修订版
> **状态**：待评审
> **目标读者**：产品 / 架构 / 工程 / 算法
> **核心定位**：把 OSS 数据湖升级为可被智能引擎直接调用的"知识搜索引擎层"。
> **修订说明**：基于 v0.1 review + 架构讨论，核心变更：(1) 1 OSS Object = 1 Entity；(2) Representation 是"认知视角"而非中间产物；(3) Pipeline 是一等公民，同一 Entity 可走多条并行流水线；(4) Chunk 是检索最小单元，提升为一等公民；(5) Lance 主表 = chunks（内嵌 vector）。

---

## 0. 一句话定义

> **Entity 是知识对象，Representation 是它的不同认知视角，Chunk 是某个视角下的检索粒度，Embedding 是 Chunk 的向量索引。同一问题可以从多个视角命中同一 Entity，融合后给出最完整的证据。**

---

## 1. 产品概述

### 1.1 背景

当前仓库已具备以下能力：

- **OSS Data Lake**：原始对象（pdf、docx、pptx、image、audio…）通过 `vector-lake/{workspace}/{collection}/raw/...` 落地，文件不可变。
- **Embedding V5 服务**：基于 Jina V5 Omni 的多模态 embedding（文本/图像/音频/视频在同一向量空间），支持 `retrieval.query` / `retrieval.passage` / `text-matching` / `image` / `audio` / `video`，支持 MRL 维度截断。
- **Chunking Use Case**：基于 Markdown 标题 + 表格保护 + token 阈值 + 滑动窗口的成熟文本切分实现。

但是**这些能力是孤立的**，缺少一个统一的"知识搜索引擎层"来：

1. 描述"raw → 可检索知识"的完整语义模型。
2. 把多种模态、多种 representation、多种 index 编排为可调度管线。
3. 为上层 Agent / RAG / 搜索 UI 提供统一的检索能力接口。
4. 解决状态一致性问题（raw / entity / representation / index 之间的可见性与重建）。

### 1.2 产品愿景

构建一个 **实体驱动、表现多模、检索可组合、状态可调和** 的知识搜索引擎层，作为上层 AI 应用（问答、Agent、研究助手、企业搜索）唯一可信的知识访问入口。

### 1.3 目标（Goals）

| 目标 | 描述 |
| --- | --- |
| **G1. 知识编译** | 把任意 raw object 编译成多种 representation（认知视角），每种视角可独立检索。 |
| **G2. 多模态同构** | 文本、图像、音频、视频在同一向量空间可互检。 |
| **G3. 检索能力可组合** | 智能引擎根据问题动态选择并组合 semantic / lexical / grep / visual / audio / table / graph / hybrid 等能力。 |
| **G4. 不可变与可重建** | raw object 不可变；representation 可重建；entity 是稳定知识单元。 |
| **G5. 状态可调和** | OSS / manifest / Lance / index 状态不一致时，可被 reconcile 任务发现并修复。 |
| **G6. 可演进** | 新 Pipeline / 新 Representation / 新 Index 可随时追加，不破坏已有架构。 |

### 1.4 非目标（Non-Goals）

| 非目标 | 描述 |
| --- | --- |
| **N1.** | 不做用户态权限/RBAC 完整实现，v0.1 仅做 workspace/collection 隔离。 |
| **N2.** | 不做端到端多租户计费、审计、合规。 |
| **N3.** | 不做端到端 RAG 答案生成（属于上层应用）。 |
| **N4.** | 不替代 LanceDB / Elasticsearch / 向量数据库本身，只做编排与建模。 |
| **N5.** | v0.1 不做实时增量索引（先做近实时批式 reconcile + publish）。 |

---

## 2. 核心抽象（Core Abstractions）

### 2.1 一等公民定义

| 抽象 | 含义 | 是否可变 | 备注 |
| --- | --- | --- | --- |
| **Raw Object** | OSS 上的原始文件 | **不可变** | source of truth |
| **Entity** | 知识对象，1 个 OSS Object = 1 个 Entity | 标识稳定，属性可演进 | 文件级知识单元 |
| **Representation** | Entity 的一种"认知视角"（markdown / 截图 / OCR / 脑图 / 关系图 / ...） | **可重建** | 派生产物，可互为 derived_from |
| **Pipeline** | 从 raw 或已有 representation 生成新 representation 的过程 | — | 一等公民，同一 Entity 可走多条并行流水线 |
| **Chunk** | 某个 Representation 下的检索最小单元 | **可重建** | 一等公民，检索命中的原子粒度 |
| **Embedding** | 某个 Chunk 的向量索引 | **可重建** | 内嵌于 Lance chunks 表的 vector 列 |
| **Index** | 某类检索能力（semantic/lexical/grep/visual/...） | 可演进 | 检索入口 |
| **Lineage** | Representation 之间的血缘关系（谁从谁派生） | **可追溯** | 一等公民，支持追溯 / 可视化 / 影响分析 |
| **Edge** | 跨 Entity 关系（cites/mentions/same_as/...） | 可演进 | 图检索基础 |

### 2.2 核心链路

```text
Raw Object (OSS, immutable)
    │
    ▼
[1] Ingest  (登记 entity)
    ▼
[2] Detect  (mime / size / content_hash / language)
    ▼
[3] Pipeline Dispatch  (根据 entity_type 选择 1..N 条流水线)
    │
    ├── Pipeline A: "直接提取" ──► representation(canonical_md) ──► chunks ──► embed(text)
    ├── Pipeline B: "OCR 流水线" ──► representation(page_image) ──► representation(ocr_text) ──► chunks ──► embed(text)
    ├── Pipeline C: "VLM 视觉" ──► representation(page_image) ──► representation(vlm_md) ──► chunks ──► embed(text)
    ├── Pipeline D: "图片向量" ──► representation(page_image) ──► chunks ──► embed(image)
    ├── Pipeline E: "知识编译" ──► representation(canonical_md) ──► representation(mind_map / graph_json / wiki_md)
    └── Pipeline F: "音频转写" ──► representation(audio_segment) ──► representation(transcript) ──► chunks ──► embed(text + audio)
    │
    ▼
[4] Index  (semantic / lexical / grep / graph / visual / audio)
    ▼
[5] Publish  (mark active, visible to retrieval)
    ▼
[6] Reconcile  (continuous; fix drift)
```

### 2.3 一句话架构

> **Raw Object → Entity → (Pipeline → Representation → Chunk → Embedding)×N → Index → Intelligent Engine**

### 2.4 Representation 是"认知视角"

同一个 Entity 可以有多种认知视角，它们之间通过 **Lineage（血缘）** 互相关联：

```text
Entity: "https://example.com/pricing"
  │
  ├── rep: canonical_md        ← 网页抓取的 Markdown
  ├── rep: page_screenshot     ← 网页截图
  ├── rep: vlm_extracted_md    ← 截图经 VLM 识别出的 Markdown
  ├── rep: mind_map            ← LLM 编译的脑图
  ├── rep: summary             ← 摘要
  └── rep: graph_json          ← 实体关系图
```

Lineage 血缘链：

```text
raw ──► canonical_md ──► mind_map
                   ├──► summary
                   └──► graph_json
raw ──► page_screenshot ──► vlm_extracted_md
```

### 2.5 Lineage 是一等公民

Lineage 的核心目的是：**上游变动后，下游立即不可用并重新生成**。

```text
raw 更新
  → page_image 立即 stale → ocr_text 立即 stale → ocr chunks 立即 stale
                          → vlm_extracted_md 立即 stale → vlm chunks 立即 stale
                          → image_embedding 立即 stale
  → canonical_md 立即 stale → mind_map 立即 stale
                            → summary 立即 stale
                            → graph_json 立即 stale
```

**Lineage 驱动的级联规则**：

1. **上游变了 → 下游立即 stale**：沿 lineage 边向下遍历，所有下游 representation + chunk 标记 `stale`，检索不再命中。
2. **stale → 自动触发重建**：pipeline orchestrator 检测到 stale 状态，自动重跑对应 pipeline 生成新 representation + chunks。
3. **重建完成 → publish 切换**：新版本 ready 后，原子切换，检索恢复。
4. **重建期间 → 旧版本仍可查**：stale 的 chunks 在新版本 publish 前仍保留，但标记为 stale（可选：检索是否包含 stale 结果）。

> 追溯、可视化、影响分析都是 Lineage 的**辅助能力**，核心是"级联失效 + 自动重建"。

### 2.5 Pipeline 是一等公民

同一 Entity 可以走多条并行流水线，每条产出不同的 Representation：

```text
Entity: pricing.pdf
  │
  ├── Pipeline A: "直接提取"
  │     └── raw → canonical_md → text chunks → text embedding
  │
  ├── Pipeline B: "OCR 流水线"
  │     └── raw → page_image → ocr_text → ocr chunks → ocr embedding
  │
  ├── Pipeline C: "VLM 视觉流水线"
  │     └── raw → page_image → vlm_extracted_md → vlm chunks → vlm embedding
  │
  ├── Pipeline D: "知识编译流水线"
  │     └── canonical_md → mind_map / graph_json / summary / wiki_md
  │
  └── Pipeline E: "图片向量流水线"
        └── page_image → image embedding (直接走 visual 索引)
```

---

## 3. 架构设计

### 3.1 分层架构

```text
┌──────────────────────────────────────────────────────────────┐
│  L5  Intelligent Engine                                      │
│      Query Understanding · Capability Routing · Fusion · RAG │
├──────────────────────────────────────────────────────────────┤
│  L4  Retrieval Capabilities (Tools)                          │
│      ls · read · stat · grep · glob                          │
│      semantic · lexical · hybrid · visual · audio · table    │
│      graph                                                   │
├──────────────────────────────────────────────────────────────┤
│  L3.5  Virtual File System (VFS)                             │
│      迭代式 OSS prefix 扫描 → 目录树缓存                      │
│      路径 ↔ Entity/Representation 映射                       │
│      glob / grep / ls / stat / read 基于此层                  │
├──────────────────────────────────────────────────────────────┤
│  L3  Indexing Layer (LanceDB)                                │
│      chunks 主表 (vector + FTS + scalar filter)              │
│      Hybrid Search (RRF / CrossEncoder rerank)               │
│      Graph index (edges 表)                                  │
├──────────────────────────────────────────────────────────────┤
│  L2  Representation Layer                                    │
│      Pipeline A → canonical_md → chunks → embeddings         │
│      Pipeline B → page_image → ocr_text → chunks → embeds   │
│      Pipeline C → page_image → vlm_md → chunks → embeds     │
│      Pipeline D → mind_map / graph_json / wiki_md            │
│      Pipeline E → page_image → image embeddings              │
├──────────────────────────────────────────────────────────────┤
│  L1  Entity Layer                                            │
│      Entity registry (1 OSS Object = 1 Entity)               │
│      Edge registry (跨 Entity 关系) · Manifest               │
├──────────────────────────────────────────────────────────────┤
│  L0  Raw Object Store (OSS Data Lake)                        │
│      oss://vector-lake/{ws}/{col}/raw/{entity_id}/original   │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 模块划分

| 模块 | 职责 | 关键产出 |
| --- | --- | --- |
| **Ingest Service** | 监听 OSS 新对象、登记 entity | entity 行 + manifest |
| **Detect Worker** | mime / language / content_hash / size | detect 结果 |
| **Pipeline Orchestrator** | 根据 entity_type 选择 1..N 条 pipeline 并行调度 | pipeline_run 记录 |
| **Pipeline Worker** | 执行单条 pipeline，产出 representation + chunks | representation + chunks |
| **Embedder** | 调用 Embedding V5 多模态服务 | chunks 表的 vector 列 |
| **Indexer** | 构建 Lance 索引（IVF_PQ / HNSW / FTS） | 索引状态 |
| **Compiler** | LLM 编译 wiki / summary / mind_map / graph | 高阶 representation |
| **Publisher** | 版本标记 active、原子切换 | active 版本 |
| **Reconciler** | 周期扫描 OSS / manifest / Lance / index | drift 报告 + 修复 |
| **VFS Builder** | 迭代式扫描 OSS prefix，构建虚拟文件系统目录树 | 目录树缓存 + 路径映射 |
| **Retrieval Gateway** | 暴露统一检索 API（含 VFS 工具） | tool 调用结果 |
| **Intelligent Engine** | 理解 query、路由能力、融合、重排 | evidence pack |

### 3.3 数据流

```text
OSS Event
   │
   ▼
Ingest + Detect  ────►  Entity (1 OSS Object = 1 Entity)
                            │
                            ▼
                     Pipeline Dispatch
                            │
        ┌───────────┬───────┼───────┬───────────┐
        ▼           ▼       ▼       ▼           ▼
    Pipeline A  Pipeline B  ...  Pipeline D  Pipeline E
        │           │               │           │
        ▼           ▼               ▼           ▼
    Rep(canonical) Rep(page_img) Rep(mind_map) Rep(page_img)
        │           │               │           │
        ▼           ▼               ▼           ▼
    Chunks      Chunks          Chunks      Chunks
        │           │               │           │
        ▼           ▼               ▼           ▼
    Embed(text) Embed(ocr)    Embed(text)  Embed(image)
        │           │               │           │
        └───────────┴───────┬───────┴───────────┘
                            ▼
                    Lance chunks 主表
                            │
                            ▼
                    Index + Publish
                            │
                            ▼
                    Active (queryable)
```

---

## 4. 数据模型

### 4.1 Entity（1 OSS Object = 1 Entity）

```json
{
  "entity_id": "abc123",
  "entity_type": "document",
  "workspace_id": "ws_001",
  "collection_id": "kb_001",
  "name": "pricing.pdf",
  "source_uri": "oss://bucket/raw/pricing.pdf",
  "source_version": "etag_xxx",
  "content_hash": "sha256_xxx",
  "version": 1,
  "status": "enabled",
  "created_at": "2026-06-05T10:00:00Z",
  "updated_at": "2026-06-05T10:00:00Z"
}
```

**entity_type 取值（v0.1）**：

```text
document · image · audio · video
```

> `document` 包含 pdf/docx/pptx/html/md 等；`image` 包含 png/jpg/svg 等；`audio` 包含 wav/mp3 等；`video` 包含 mp4 等。具体 subtype 由 detect 阶段的 mime_type 决定。

### 4.2 Representation（认知视角）

```json
{
  "representation_id": "rep_xxx",
  "entity_id": "abc123",
  "entity_version": 1,
  "rep_type": "vlm_extracted_md",
  "uri": "oss://bucket/representations/abc123/v1/vlm_extracted.md",
  "mime_type": "text/markdown",
  "derived_from": "rep_yyy",
  "derived_chain": ["raw", "page_image", "vlm_extracted_md"],
  "pipeline_id": "pipeline_c",
  "status": "ready",
  "quality": {
    "confidence": 0.92,
    "source": "vlm_qwen2vl"
  },
  "created_at": "2026-06-05T10:00:00Z",
  "updated_at": "2026-06-05T10:00:00Z"
}
```

**关键设计**：
- `derived_from` 指向直接上游的 `representation_id`（而非 OSS URI），形成血缘链。
- `derived_chain` 记录完整溯源链（从 raw 到当前），方便追溯和调试。
- `pipeline_id` 标识由哪条流水线产出。
- 更完整的血缘关系由 `lineage` 表维护（见 §4.6），支持多父节点和影响分析。

**标准 rep_type（v0.1 落地集合）**：

```text
raw · canonical_md · plain_text · layout_json · page_image
ocr_text · vlm_extracted_md · caption
table_md · table_json
audio_segment · transcript · transcript_segment
mind_map · wiki_md · graph_json · summary
```

### 4.3 Chunk（检索最小单元，一等公民）

```json
{
  "chunk_id": "chk_xxx",
  "entity_id": "abc123",
  "entity_version": 1,
  "representation_id": "rep_xxx",
  "rep_type": "canonical_md",
  "pipeline_id": "pipeline_a",
  "chunk_index": 3,
  "text": "## Q3 Pricing\nEnterprise: $4.2B, Consumer: $1.8B...",
  "embedding_text": "Heading Levels：Q3 Pricing。Content：Enterprise: $4.2B...",
  "start_pos": 1200,
  "token_count": 256,
  "chunk_chars": 1024,
  "page_number": 7,
  "section_header": "Q3 Pricing",
  "section_level": 2,
  "anchor": "q3-pricing",
  "doc_title": "pricing.pdf",
  "modality": "text",
  "status": "active",
  "created_at": "2026-06-05T10:00:00Z"
}
```

**modality 取值**：`text | image | audio | table`

**不同 Representation 的 Chunk 策略**：

| rep_type | Chunk 策略 | modality |
| --- | --- | --- |
| canonical_md / ocr_text / vlm_extracted_md | 按标题+段落切 text chunk（ChunkingWithSlidingWindowUseCase） | text |
| page_image | 每页一个 chunk，走 image embedding | image |
| transcript / transcript_segment | 按时间戳切 segment | text |
| audio_segment | 每个 segment 一个 chunk，走 audio embedding | audio |
| table_md / table_json | 每个表格一个 chunk | table |
| mind_map | 按节点切 chunk | text |
| graph_json | 按 (subject, predicate, object) 三元组切 chunk | text |

### 4.4 Edge（跨 Entity 关系）

```json
{
  "src_entity_id": "abc123",
  "dst_entity_id": "def456",
  "edge_type": "cites",
  "confidence": 0.95,
  "source": "llm_compiler",
  "created_at": "2026-06-05T10:00:00Z"
}
```

**edge_type**：`cites · mentions · same_as · contradicts · supports · related_to`

> 注意：不再有 `contains` edge。因为 1 OSS Object = 1 Entity，不存在父子实体关系。

### 4.5 Pipeline（流水线定义）

```json
{
  "pipeline_id": "pipeline_b",
  "name": "OCR 流水线",
  "entity_types": ["document"],
  "steps": [
    { "action": "represent", "input_rep": "raw", "output_rep": "page_image" },
    { "action": "represent", "input_rep": "page_image", "output_rep": "ocr_text" },
    { "action": "chunk", "input_rep": "ocr_text", "strategy": "markdown_sliding_window" },
    { "action": "embed", "modality": "text", "task": "retrieval.passage" }
  ],
  "enabled": true,
  "priority": 2
}
```

### 4.6 存储模型：Parquet 写入 → Prefix 汇聚 → Lance 统一索引

**核心决策：三层存储架构，写入用 Parquet，查询用 Lance，中间通过迭代式汇聚衔接。**

```text
┌─────────────────────────────────────────────────────────────┐
│  L1  写入层（Parquet）                                       │
│      每 Entity 一个 Parquet 文件，小文件快写，天然隔离         │
│      pipeline 产出直接落盘，无需全局协调                       │
├─────────────────────────────────────────────────────────────┤
│  L2  汇聚层（Prefix Merge）                                  │
│      迭代式扫描 prefix，将多个 Entity 的 Parquet 合并          │
│      按 workspace / collection / entity_type 分组            │
│      产出 Lance 格式数据集                                    │
├─────────────────────────────────────────────────────────────┤
│  L3  查询层（Lance）                                         │
│      统一 hybrid search（vector + FTS + scalar filter）       │
│      Lance 原生索引（IVF_PQ / HNSW / FTS）                   │
│      全局 Catalog 路由                                       │
└─────────────────────────────────────────────────────────────┘
```

#### 为什么三层？

| 维度 | 纯 Parquet | 纯 Lance 大表 | 三层（Parquet → 汇聚 → Lance） |
| --- | --- | --- | --- |
| **写入延迟** | 最低（追加写） | 高（需建索引） | 低（先写 Parquet） |
| **写入隔离** | 天然隔离 | 需全局锁 | 天然隔离（Entity 级） |
| **查询性能** | 差（无索引） | 好 | 好（Lance 索引） |
| **跨 Entity 检索** | 需 fan-out N 个文件 | 单表查询 | Lance 统一查询 |
| **版本管理** | 文件级 | 行级 | Lance 原生 MVCC |
| **Lineage 级联** | 单文件内 | 跨行扫描 | 单 Entity Parquet 内 + Lance 内 |
| **小文件问题** | 严重 | 无 | 汇聚层解决 |

#### OSS 目录结构

```text
vector-lake/{workspace_id}/{collection_id}/
├── raw/
│   └── {entity_id}/original
│
├── representations/
│   └── {entity_id}/v{version}/
│       ├── canonical.md
│       ├── page_image/
│       ├── ocr.md
│       └── ...
│
├── staging/                                    ← L1 写入层
│   └── {entity_id}/
│       ├── chunks_v{version}.parquet           ← chunks + vectors
│       ├── representations.parquet             ← representation 注册
│       └── lineage.parquet                     ← 血缘边
│
├── indexes/                                    ← L3 查询层
│   ├── chunks.lance/                           ← 全局 chunks 索引（汇聚后）
│   │   ├── data/
│   │   │   ├── part-0.lance
│   │   │   └── part-1.lance
│   │   └── _indices/
│   │       ├── vector.idx                      ← IVF_PQ / HNSW
│   │       └── fts.idx                         ← FTS 索引
│   │
│   ├── {entity_id}.lance/                      ← Entity 级索引（单 Entity 精细查询）
│   │   ├── chunks.lance
│   │   ├── representations.lance
│   │   └── lineage.lance
│   │
│   ├── catalog.lance                           ← 全局 Entity 注册
│   ├── edges.lance                             ← 全局跨 Entity 关系
│   └── pipeline_runs.lance                     ← 全局运行历史
│
└── wiki/
    └── {entity_id}.md
```

#### L1. 写入层：每 Entity 一个 Parquet

Pipeline 产出的 chunks + vectors 直接写入 Entity 独立的 Parquet 文件：

`staging/{entity_id}/chunks_v{version}.parquet`：

```text
chunk_id             string
representation_id    string
rep_type             string              # canonical_md / ocr_text / page_image / ...
pipeline_id          string
chunk_index          int
text                 string              # 中心块原文
embedding_text       string              # 向量化文本
start_pos            int
token_count          int
chunk_chars          int
page_number          int?
section_header       string?
section_level        int?
anchor               string?
doc_title            string?
modality             string              # text / image / audio / table
content_hash         string
model_version        string
vector               list<float>         # Parquet 用 list<float>，汇聚时转 Lance fixed_size_list
status               string              # active / hidden / deleted / stale
created_at           timestamp
```

`staging/{entity_id}/representations.parquet`：

```text
representation_id · rep_type · uri · mime_type
derived_from · derived_chain · pipeline_id
status · quality_score · created_at · updated_at
```

`staging/{entity_id}/lineage.parquet`：

```text
src_representation_id · dst_representation_id
pipeline_id · transform · created_at
```

**写入层特点**：
- **追加写**：pipeline 产出直接 append，无需建索引。
- **天然隔离**：不同 Entity 写不同文件，无并发冲突。
- **立即可查**：staging 中的 Parquet 可被直接扫描（用于调试 / 预览），但无索引优化。
- **版本化**：每次 pipeline 重跑产出新的 `chunks_v{N}.parquet`，旧版本保留。

#### L2. 汇聚层：迭代式 Prefix Merge

汇聚层定期扫描 `staging/` prefix，将多个 Entity 的 Parquet 合并为 Lance 数据集：

```text
汇聚流程：

1. 扫描 staging/ prefix
   ├─ 发现新增/更新的 Parquet 文件
   └─ 按 workspace_id + collection_id 分组

2. 按 prefix 汇聚
   ├─ 将同 prefix 下的多个 Entity Parquet 合并
   ├─ 产出 Lance 格式数据集
   └─ 建索引（vector / FTS / scalar）

3. 原子切换
   ├─ 新 Lance 数据集 ready
   ├─ 切换查询层指向新数据集
   └─ 保留旧版本（Lance MVCC）

4. 清理 staging
   └─ 已汇聚的 Parquet 可归档/删除
```

**汇聚策略**：

| 策略 | 触发条件 | 说明 |
| --- | --- | --- |
| **增量汇聚** | 新 Parquet 文件出现 | 只合并新增文件，不重写已有 Lance |
| **全量重写** | Parquet 文件数 > 阈值 或 碎片率过高 | 重写整个 Lance 数据集，优化存储布局 |
| **版本切换** | Entity 有新 version | 替换旧 version 的 chunks，保留 lineage |

#### L3. 查询层：Lance 统一索引

**全局 `chunks.lance`**（核心检索入口，汇聚后）：

```text
chunk_id             string
entity_id            string              # 汇聚时从文件名/路径注入
entity_version       int
representation_id    string
rep_type             string
pipeline_id          string
chunk_index          int
text                 string              # FTS 索引
embedding_text       string
start_pos            int
token_count          int
chunk_chars          int
page_number          int?
section_header       string?
section_level        int?
anchor               string?
doc_title            string?
modality             string
content_hash         string
model_version        string
vector               fixed_size_list<float>  # Lance 原生 vector 列
status               string
workspace_id         string              # 汇聚时注入，安全隔离
collection_id        string              # 汇聚时注入
created_at           timestamp
```

> **Lance 索引**：`vector` 列建 IVF_PQ 或 HNSW；`text` 列建 FTS 索引；`workspace_id` / `collection_id` / `modality` / `rep_type` / `status` 建 scalar 索引。

**Entity 级 `{entity_id}.lance/`**（可选，用于单 Entity 精细查询）：

- `chunks.lance` — 该 Entity 的 chunks + vectors
- `representations.lance` — 该 Entity 的 representation 注册
- `lineage.lance` — 该 Entity 的血缘边

> 全局 `chunks.lance` 用于跨 Entity 检索；Entity 级 Lance 用于预览 / lineage / 单文件调试。

#### 全局 Catalog

```text
catalog.lance (全局)
  entity_id            string
  entity_type          string
  workspace_id         string
  collection_id        string
  name                 string
  source_uri           string
  source_version       string
  content_hash         string
  version              int
  status               string              # enabled / hidden / deleted
  staging_uri          string              # oss://.../staging/{entity_id}/
  lance_uri            string              # oss://.../indexes/{entity_id}.lance/
  chunk_count          int
  representation_types list<string>
  modalities           list<string>
  model_version        string
  staging_status       string              # pending / merged / stale
  created_at           timestamp
  updated_at           timestamp
```

> `staging_status`：`pending` = 有新 Parquet 未汇聚；`merged` = 已汇聚到 Lance；`stale` = staging 有更新但未重新汇聚。

#### 数据流全链路

```text
Pipeline 产出
   │
   ▼
[L1] 写入 staging/{entity_id}/chunks_v{N}.parquet
   │
   ▼
[L2] 汇聚层扫描 staging/ prefix
   ├─ 发现新 Parquet
   ├─ 按 workspace/collection 分组
   ├─ 合并 → Lance 格式
   ├─ 建索引 (vector / FTS / scalar)
   ├─ 原子切换查询层指向
   └─ 更新 catalog (staging_status = merged)
   │
   ▼
[L3] 查询层读 chunks.lance
   ├─ hybrid search (vector + FTS + scalar filter)
   ├─ RRF / CrossEncoder rerank
   └─ 返回 evidence pack
```

#### Lineage 级联在三层中的体现

```text
raw 更新 (content_hash 变化)
   │
   ▼
[L1] Pipeline 重跑 → 新 chunks_v{N+1}.parquet 写入 staging
     旧 representation/chunks 标 stale（在 Parquet 内标记）
   │
   ▼
[L2] 汇聚层检测到新 Parquet
     → 增量合并到 chunks.lance
     → 旧 version chunks 标 stale（检索不再命中）
     → 新 version chunks 标 active
   │
   ▼
[L3] 查询层读新 chunks.lance
     → stale chunks 不参与检索
     → active chunks 可被检索
```

#### Lineage 查询能力

| 查询 | 说明 |
| --- | --- |
| `GET /lineage/{entity_id}?direction=upstream&rep_type=ocr_text` | 从 ocr_text 向上追溯到 raw（辅助能力） |
| `GET /lineage/{entity_id}?direction=downstream&rep_type=page_image` | 从 page_image 向下找出所有下游（级联失效目标） |
| `GET /lineage/{entity_id}/impact?rep_type=page_image` | 影响分析：如果 page_image 变了，哪些下游需要 stale + 重建 |
| `POST /lineage/{entity_id}/cascade` | 手动触发级联：将指定 rep 的所有下游标 stale 并触发重建 |

#### 全局辅助表

| 表 | 存储位置 | 用途 |
| --- | --- | --- |
| `catalog.lance` | 全局 indexes/ | Entity 注册 + 检索路由 + staging 状态 |
| `edges.lance` | 全局 indexes/ | 跨 Entity 关系（cites/mentions/...） |
| `pipeline_runs.lance` | 全局 indexes/ | Pipeline 运行历史 |

---

## 5. 状态模型（分层）

### 5.1 OSS Object Tag — 用户意图

```text
rag_status = enabled | hidden | deleted
```

### 5.2 Entity Status — 知识对象状态

```text
enabled · hidden · deleted
```

### 5.3 Pipeline Run Status — 处理状态

```text
pending → running → partial_success | success | failed
```

### 5.4 Representation Status — 单个视角是否可用

```text
ready · skipped · failed · stale · deleted
```

### 5.5 Chunk Status — 检索可见性

```text
active · hidden · deleted · stale
```

### 5.6 版本与发布

- Entity 有 `version` 字段，单调递增。
- Representation 和 Chunk 都带 `entity_version`。
- **Publish 操作** = "将某个 entity_version 的所有 chunks 标记为 active"。
- 新版本处理期间，旧版本保持 active，直到新版本 publish 成功才切换。
- 检索默认查 `status=active` 的最新 `entity_version`。

### 5.7 状态联动规则

| 触发事件 | 联动动作 |
| --- | --- |
| raw object `content_hash` 变化 | entity.version++；沿 lineage 向下级联：所有下游 representation 标 `stale`，对应 chunks 标 `stale`（检索不再命中）；自动触发 pipeline 重跑；新版本 ready 后 publish 切换 |
| representation `ready` | 触发对应 chunks 的 embed + index |
| representation `stale` | 沿 lineage 向下级联：所有下游 representation 标 `stale`，chunks 标 `stale`；自动触发下游 pipeline 重建 |
| representation `failed` | pipeline `partial_success`；已有 representation 的 chunks 仍可用 |
| OSS tag → `hidden` | entity.status=hidden；所有 chunks 标 `hidden`（不进入默认检索） |
| OSS tag → `deleted` | entity.status=deleted；chunks 软删除；OSS 原文件保留 |
| embedding 模型升级 | 检测 `model_version` 过期；触发对应 chunks 重跑 embed |
| pipeline 新增 | 对已有 entity 按需重跑新 pipeline；不影响已有 representation |
| 上游 representation 变化 | 沿 lineage 向下级联：下游 representation 立即 stale → chunks stale → 自动重建 |

### 5.8 内容寻址变更检测

- `detect` 阶段计算 raw bytes 的 SHA-256 `content_hash`。
- 每个 chunk 计算文本内容的 SHA-256 `content_hash`。
- Reconcile 比较 `content_hash` 而非 `etag`（etag 在 multipart upload 时不可靠）。
- Parser 升级时，强制对受影响的 entity_type 重跑 pipeline，即使 content_hash 未变。

---

## 6. Pipeline 定义

### 6.1 Pipeline 是一等公民

同一 Entity 可以走多条并行流水线，每条产出不同的 Representation：

| Pipeline | 输入 | 产出 Representation | 产出 Chunk 类型 | Embedding 策略 |
| --- | --- | --- | --- | --- |
| **A. 直接提取** | raw | canonical_md, plain_text | text chunks | `retrieval.passage` on embedding_text |
| **B. OCR 流水线** | raw → page_image | page_image, ocr_text | image chunks + text chunks | `image` on page_image; `retrieval.passage` on ocr_text |
| **C. VLM 视觉** | raw → page_image | page_image, vlm_extracted_md | image chunks + text chunks | `image` on page_image; `retrieval.passage` on vlm_md |
| **D. 知识编译** | canonical_md | mind_map, graph_json, wiki_md, summary | text chunks | `retrieval.passage` on summary/caption |
| **E. 图片向量** | raw → page_image | page_image | image chunks | `image` on page_image |
| **F. 音频转写** | raw → audio_segment | audio_segment, transcript, transcript_segment | audio chunks + text chunks | `audio` on segment; `retrieval.passage` on transcript |

### 6.2 Pipeline 编排原则

- **idempotent**：所有 pipeline 可重跑，重跑结果应一致或单调升级。
- **append-only on raw**：raw object 永不修改；重建只写新 representation。
- **parallel**：多条 pipeline 可并行执行，互不阻塞。
- **partial success 优先**：单条 pipeline 失败不阻塞其他 pipeline 的产出可用。
- **可追加**：新 pipeline 可随时注册，对已有 entity 按需重跑。

### 6.3 Pipeline 与 Entity Type 的映射

| entity_type | 默认 Pipeline | 可选 Pipeline |
| --- | --- | --- |
| document | A (直接提取) | B (OCR), C (VLM), D (知识编译), E (图片向量) |
| image | E (图片向量) | B (OCR), C (VLM), D (知识编译) |
| audio | F (音频转写) | D (知识编译) |
| video | F (音频转写) | E (图片向量), D (知识编译) |

---

## 7. 多模态 Embedding 策略

### 7.1 Embedding V5 Task 映射表

| Chunk modality | V5 task | 输入来源 | 说明 |
| --- | --- | --- | --- |
| text | `retrieval.passage` | chunk.embedding_text | 文本语义向量 |
| image | `image` | page_image URL/base64 | 图片向量（与 text 同空间） |
| audio | `audio` | audio_segment WAV base64 | 音频向量（与 text 同空间） |
| transcript | `retrieval.passage` | transcript_segment text | 转写文本向量 |
| caption | `retrieval.passage` | caption text | 图片描述文本向量 |
| table | `retrieval.passage` | table_md / table_json text | 表格文本向量 |

### 7.2 查询端统一用 retrieval.query

```text
用户查询 → task="retrieval.query", input=query_text
→ 在同一向量空间匹配 text / image / audio / caption / table 向量
→ 跨模态检索天然支持
```

### 7.3 双向量策略（音频场景）

音频 segment 同时生成：
- `audio` 向量（task="audio"，输入 WAV）
- `text` 向量（task="retrieval.passage"，输入 transcript）

检索时两个向量独立召回，融合后去重。

---

## 8. 检索能力（Retrieval Capabilities）

### 8.1 Virtual File System（VFS）— 文件系统级能力

**VFS 是 OSS 数据湖的虚拟文件系统层**，通过迭代式 prefix 扫描构建目录树缓存，对外提供文件系统级操作。

#### VFS 构建方式

```text
迭代式 OSS Prefix 扫描：

1. 初始扫描
   ├─ 从 vector-lake/{workspace_id}/{collection_id}/ 开始
   ├─ 列出所有 prefix（raw/ / representations/ / staging/ / indexes/）
   └─ 递归扫描每个 prefix，构建完整目录树

2. 增量更新
   ├─ 监听 OSS 事件（新对象 / 删除 / 修改）
   ├─ 只更新受影响的子树
   └─ 定期全量对账（reconcile）

3. 目录树缓存
   ├─ 内存中维护完整的虚拟目录树
   ├─ 每个节点记录：path / type(file|dir) / size / last_modified / entity_id / rep_type
   └─ 定期持久化到 catalog.lance
```

#### VFS 路径映射

VFS 将 OSS 路径映射为语义化的虚拟路径：

```text
OSS 物理路径                                          VFS 虚拟路径
─────────────────────────────────────────────────────────────────────
raw/{entity_id}/original                         →  /{name}                    # 原始文件
representations/{entity_id}/v1/canonical.md      →  /{name}/canonical.md       # 视角文件
representations/{entity_id}/v1/page_image/       →  /{name}/pages/             # 页面图片
representations/{entity_id}/v1/ocr.md            →  /{name}/ocr.md             # OCR 结果
representations/{entity_id}/v1/mind_map.json     →  /{name}/mind_map.json      # 脑图
wiki/{entity_id}.md                              →  /{name}/wiki.md            # Wiki 页面
```

**用户看到的目录结构**：

```text
/
├── pricing.pdf/                    ← Entity（目录）
│   ├── original                    ← raw 文件
│   ├── canonical.md                ← 直接提取
│   ├── ocr.md                      ← OCR 提取
│   ├── vlm_extracted.md            ← VLM 提取
│   ├── pages/                      ← 页面图片
│   │   ├── page_001.png
│   │   └── page_007.png
│   ├── mind_map.json               ← 脑图
│   ├── graph.json                  ← 关系图
│   ├── summary.md                  ← 摘要
│   └── wiki.md                     ← Wiki 页面
│
├── meeting.wav/                    ← Entity（目录）
│   ├── original
│   ├── transcript.md               ← 转写全文
│   ├── segments/                   ← 音频片段
│   └── wiki.md
│
└── chart.png/                      ← Entity（目录）
    ├── original
    ├── ocr.md                      ← OCR 文字
    ├── caption.md                  ← 图片描述
    └── wiki.md
```

#### VFS 提供的工具

| 工具 | 实现 | 说明 |
| --- | --- | --- |
| `ls` | 读目录树缓存 | 列出虚拟路径下的子项；支持 `--sort` / `--filter` |
| `stat` | 读目录树缓存 + catalog | 返回文件/目录元数据（size / last_modified / entity_id / status） |
| `read` | 从 OSS 读取实际文件 | 返回文件内容；支持 range 读取 |
| `glob` | 在目录树缓存上匹配 | 支持 `**/*.pdf` / `**/canonical.md` 等模式 |
| `grep` | 迭代式扫描 OSS 文本文件 | 在匹配的文件中搜索 pattern；支持正则 |

#### grep 的迭代式实现

grep 不能依赖索引（它需要精确匹配原始文本），所以采用**迭代式 OSS 文件扫描**：

```text
grep "Q3 定价" /pricing.pdf/**
   │
   ▼
[1] glob 匹配 → 找到 /pricing.pdf/canonical.md, /pricing.pdf/ocr.md, ...
   │
   ▼
[2] 过滤文本文件（mime_type = text/* 或 .md/.txt/.json）
   │
   ▼
[3] 迭代式读取 + ripgrep
   ├─ 从 OSS 流式读取每个文件
   ├─ 用 ripgrep 在内存中匹配
   └─ 收集命中行 + 上下文
   │
   ▼
[4] 返回结果
   └─ 每个命中：file_path / line_number / line_text / context
```

**优化**：
- 先用 `glob` 缩小范围，避免扫描所有文件。
- 对已缓存在本地的 representation（如 staging 中的 Parquet），直接本地 grep。
- 大文件分块流式读取，不全部加载到内存。

#### VFS 与 Lance 检索的协作

```text
用户查询 "Q3 定价策略"
   │
   ├── 需要精确匹配 → VFS grep（迭代式 OSS 扫描）
   │                    返回：行级命中 + 文件路径
   │
   ├── 需要语义匹配 → Lance hybrid search
   │                    返回：chunk 级命中 + entity_id + page_number
   │
   ├── 需要浏览文件 → VFS ls / glob
   │                    返回：目录列表 / 文件匹配
   │
   └── 需要读文件内容 → VFS read
                        返回：文件内容
```

### 8.2 能力清单

| 能力 | 实现层 | 面对的数据 | 典型输入 | 典型输出 |
| --- | --- | --- | --- | --- |
| `ls` | VFS | 目录树缓存 | dir / collection | 子项列表 |
| `stat` | VFS | 目录树缓存 + catalog | entity_id / path | 元数据 + 状态 |
| `read` | VFS | OSS 文件 | entity_id + rep_type | 文件内容 |
| `grep` | VFS | OSS 文本文件（迭代式扫描） | pattern + path | 行级命中 |
| `glob` | VFS | 目录树缓存 | pattern | 匹配文件/目录 |
| `semantic` | Lance | chunks.vector | 自然语言 | top-k chunk + score |
| `lexical` | Lance | chunks.text (FTS) | 关键词 | top-k chunk + BM25 |
| `hybrid` | Lance | chunks.vector + chunks.text | 自然语言 | top-k chunk + 融合 score |
| `visual` | Lance | chunks.vector (modality=image) | image / text | top-k chunk |
| `audio` | Lance | chunks.vector (modality=audio) | audio / text | top-k chunk |
| `table` | Lance | chunks (modality=table) | SQL-like / 关键词 | 表行 + 来源 |
| `graph` | Lance | edges | 实体 / 关系查询 | 邻居子图 |

### 8.3 Hybrid Search（v0.1 核心检索模式）

```json
{
  "tool": "hybrid",
  "args": {
    "query": "Q3 定价策略",
    "modalities": ["text", "image"],
    "semantic_weight": 0.7,
    "lexical_weight": 0.3,
    "reranker": "rrf",
    "filters": { "entity_type": ["document"], "workspace_id": "ws_001" },
    "top_k": 10
  }
}
```

**LanceDB 实现**：

```python
results = (
    chunks_table.search(query_type="hybrid")
    .vector(query_vector)
    .text(query_text)
    .where(f"workspace_id = 'ws_001' AND status = 'active'")
    .rerank(RRFReranker())
    .limit(10)
    .to_pandas()
)
```

### 8.4 预览能力（Preview）

**每个 Entity 的每种 Representation 都必须可预览**。预览是检索到知识后的第一交互动作。

#### 预览 API

```text
GET /preview/{entity_id}?rep_type={rep_type}&page={page_number}
```

返回对应 representation 的可渲染内容。

#### 各 Representation 的预览方式

| rep_type | 预览渲染 | 说明 |
| --- | --- | --- |
| `raw` | 原文件下载 / 浏览器内嵌 | PDF 用 pdf.js；图片直接展示；音频用 `<audio>` |
| `canonical_md` | Markdown 渲染 | 支持 GFM（表格、代码块、数学公式） |
| `plain_text` | 纯文本 + 行号 | 等宽字体，支持高亮定位 |
| `page_image` | 图片列表 / 翻页 | 每页一张截图，支持页码跳转 |
| `ocr_text` | Markdown 渲染 | 同 canonical_md |
| `vlm_extracted_md` | Markdown 渲染 | 同 canonical_md |
| `caption` | 文本卡片 | 图片描述文本 |
| `table_md` / `table_json` | 表格渲染 | JSON 转 HTML 表格；Markdown 表格直接渲染 |
| `transcript` | 时间轴 + 文本 | 带时间戳的转写文本，可点击跳转 |
| `transcript_segment` | 时间轴 + 文本 | 同 transcript |
| `audio_segment` | 音频播放器 | `<audio>` + 时间范围高亮 |
| `mind_map` | 脑图渲染 | JSON → 交互式脑图（可展开/折叠） |
| `graph_json` | 关系图渲染 | JSON → 力导向图（可拖拽/缩放） |
| `wiki_md` | Wiki 页面渲染 | Markdown + backlinks + 面包屑 |
| `summary` | 文本卡片 | 摘要文本 |
| `layout_json` | JSON 树 / 版面叠加 | 可视化版面结构 |

#### 预览与检索结果的联动

```text
检索命中 chunk
  │
  ├─ 点击 → 预览该 chunk 所在的 representation
  │         自动定位到 page_number / start_pos
  │
  └─ 切换视角 → 预览同一 entity 的其他 representation
                保留定位（同一页码 / 同一时间戳）
```

#### Entity 视角面板

每个 Entity 提供一个**视角面板**，列出所有可用的 Representation：

```json
{
  "entity_id": "abc123",
  "name": "pricing.pdf",
  "representations": [
    { "rep_type": "raw", "status": "ready", "preview_url": "/preview/abc123?rep_type=raw" },
    { "rep_type": "canonical_md", "status": "ready", "preview_url": "/preview/abc123?rep_type=canonical_md" },
    { "rep_type": "page_image", "status": "ready", "preview_url": "/preview/abc123?rep_type=page_image" },
    { "rep_type": "ocr_text", "status": "ready", "preview_url": "/preview/abc123?rep_type=ocr_text" },
    { "rep_type": "mind_map", "status": "ready", "preview_url": "/preview/abc123?rep_type=mind_map" },
    { "rep_type": "graph_json", "status": "skipped", "preview_url": null }
  ]
}
```

用户可以在视角面板中**一键切换**不同 Representation 的预览，无需重新检索。

#### 血缘可视化

在预览界面中，展示当前 Entity 的血缘 DAG，用户可以：

1. **查看血缘图**：看到所有 representation 之间的派生关系。
2. **点击节点跳转**：点击 DAG 中的任意节点，切换到该 representation 的预览。
3. **高亮当前路径**：当前预览的 representation 在 DAG 中高亮，其上游链路加粗显示。
4. **影响分析**：右键某个节点 → "查看影响" → 高亮所有下游 representation。

```text
         ┌── raw ──┐
         │         │
         ▼         ▼
   canonical_md  page_image ──────────┐
      │    │       │    │             │
      │    │       ▼    ▼             ▼
      │    │    ocr_text vlm_md   image_emb
      ▼    ▼
  mind_map summary
      │
      ▼
   graph_json

   ← 点击 vlm_md → 预览 VLM 提取结果
   ← 高亮 raw → page_image → vlm_md 链路
   ← 右键 page_image → "查看影响" → 高亮 ocr_text, vlm_md, image_emb
```

### 8.5 工具协议

所有工具返回统一的 **evidence 包装**：

```json
{
  "tool": "hybrid",
  "results": [
    {
      "chunk_id": "chk_xxx",
      "entity_id": "abc123",
      "entity_version": 1,
      "representation_id": "rep_xxx",
      "rep_type": "canonical_md",
      "pipeline_id": "pipeline_a",
      "modality": "text",
      "score": 0.83,
      "snippet": "## Q3 Pricing\nEnterprise: $4.2B...",
      "page_number": 7,
      "section_header": "Q3 Pricing",
      "provenance": {
        "source_uri": "oss://bucket/raw/pricing.pdf",
        "source_version": "etag_xxx",
        "content_hash": "sha256_xxx",
        "model_version": "embedding-v5-retrieval"
      }
    }
  ]
}
```

---

## 9. 智能引擎（Intelligent Engine）

### 9.1 目标

> **对上层应用屏蔽"该用哪个检索能力"的复杂度**。

### 9.2 流程

```text
User Query
   │
   ▼
[1] Query Understanding
    ├─ intent (lookup / aggregate / compare / reason / multimodal)
    ├─ entities mentioned
    └─ modality hint (text / image / audio)
   │
   ▼
[2] Capability Routing
    ├─ 选择 1..N 个 tool
    └─ 决定 filter / top_k / reranker
   │
   ▼
[3] Parallel Execution
    └─ 调 hybrid / semantic / lexical / visual / audio / graph
   │
   ▼
[4] Result Fusion & Rerank
    ├─ 跨工具去重（按 entity_id + chunk_id）
    ├─ 同一 Entity 多视角证据合并
    └─ Rerank (RRF / CrossEncoder)
   │
   ▼
[5] Pack & Return
    └─ evidence pack → 上层 RAG / Agent
```

### 9.3 路由策略（v0.1 规则版）

| Query 类型 | 优先能力 | 次选 |
| --- | --- | --- |
| 概念 / 解释 | hybrid (semantic + lexical) | grep |
| 精确字段 / 编号 | lexical + grep | semantic |
| "找一张图" | visual (image↔text) | caption semantic |
| "找一段录音" | audio (text↔audio) | transcript lexical |
| 跨实体关系 | graph | hybrid |
| 表格行 / 列 | table | lexical |

> 后续可替换为学习型 router（v0.2+）。

---

## 10. 设计原则（不可妥协）

1. **原始文件不可变**：`raw object = source of truth`。
2. **Representation 可重建**：所有 representation 都是派生物，丢失不致命。
3. **Entity 是稳定知识对象**：1 OSS Object = 1 Entity；文件版本变化时 entity.version 递增。
4. **检索不直接面对文件**：检索面对的是 chunk（检索粒度）和 entity（知识对象）。
5. **隐藏不删除向量**：`enabled/hidden/deleted` 与 `active/stale` 分离，软删除保留可恢复能力。
6. **idempotent & append-only**：管线可重跑，结果一致或单调升级。
7. **可解释性优先**：所有结果必须带 `provenance`（来源 URI、版本、representation、pipeline）。
8. **Pipeline 可追加**：新 pipeline 不影响已有 representation 和 index。

---

## 11. v0.1 范围

### 11.1 文件类型

```text
pdf · docx · pptx · image · audio
```

### 11.2 Pipeline

```text
A. 直接提取（document 默认）
B. OCR 流水线（document 可选）
E. 图片向量（image 默认 / document 可选）
F. 音频转写（audio 默认）
```

> Pipeline C (VLM) 和 D (知识编译) 为 v0.2，但 schema 预留。

### 11.3 Representation

```text
raw · canonical_md · plain_text · page_image · ocr_text
transcript · transcript_segment · caption
```

> `vlm_extracted_md · mind_map · graph_json · wiki_md · summary` 为 v0.2，但 schema 预留。

### 11.4 Index

```text
semantic · lexical · hybrid · grep · visual
```

> `audio · table · graph` 为 v0.2，但 schema 预留。

### 11.5 状态

```text
enabled · hidden · deleted · active · stale
```

### 11.6 能力

```text
ls · read · stat · grep · glob
semantic · lexical · hybrid · visual
```

> `audio · table · graph` 为 v0.2。

### 11.7 明确不在 v0.1 范围

- VLM 视觉流水线（v0.2）
- 知识编译流水线 / mind_map / graph_json（v0.2）
- 视频 keyframe / 场景切分（v0.2）
- 表格列式检索（v0.2）
- 学习型 router（v0.2）
- 多租户 / 计费（后续）
- 端到端 RAG 答案生成（上层）

---

## 12. API 设计（v0.1 形态）

### 12.1 内部管线 API（异步）

| API | 说明 |
| --- | --- |
| `POST /ingest` | 登记 raw object，创建 entity，触发 pipeline |
| `GET /entities/{entity_id}` | 取 entity |
| `GET /representations?entity_id=...&rep_type=...` | 列表 representation |
| `GET /pipelines` | 列表已注册 pipeline |
| `POST /pipelines/{pipeline_id}/run` | 对指定 entity 手动触发某条 pipeline |
| `GET /pipeline_runs/{run_id}` | 查询运行状态 |
| `POST /reconcile` | 触发 reconcile 任务 |

### 12.2 检索 API（同步，对上层应用）

| API | 说明 |
| --- | --- |
| `POST /tools/ls` | 列举 entity |
| `POST /tools/stat` | 元数据 |
| `POST /tools/read` | 读 representation 内容 |
| `POST /tools/grep` | 文本精确匹配 |
| `POST /tools/glob` | 名称匹配 |
| `POST /tools/semantic` | 语义检索 |
| `POST /tools/lexical` | 关键词检索 |
| `POST /tools/hybrid` | 混合检索（semantic + lexical + rerank） |
| `POST /tools/visual` | 图像检索 |
| `GET /preview/{entity_id}` | 预览 representation（rep_type / page 参数） |
| `GET /perspectives/{entity_id}` | 获取 Entity 的视角面板（所有可用 representation 列表） |
| `GET /lineage/{entity_id}` | 查询血缘关系（direction=upstream/downstream/both） |
| `GET /lineage/{entity_id}/impact` | 影响分析（某个 rep 变了会影响哪些下游） |
| `POST /engine/ask` | 智能引擎（综合） |

### 12.3 统一响应

```json
{
  "request_id": "req_xxx",
  "tool": "hybrid",
  "took_ms": 134,
  "results": [ /* evidence pack */ ],
  "provenance": {
    "manifest_version": "v_42",
    "indexed_at": "...",
    "model_version": "embedding-v5-retrieval"
  }
}
```

---

## 13. 非功能需求（NFR）

| 维度 | 指标 | v0.1 目标 |
| --- | --- | --- |
| **检索延迟** | `hybrid` P95 | ≤ 500 ms（含 embedding） |
| | `semantic` P95 | ≤ 300 ms |
| | `lexical / grep` P95 | ≤ 200 ms |
| | `read` P95 | ≤ 300 ms（OSS 读） |
| | `preview` P95 | ≤ 500 ms（含 OSS 读 + 渲染数据准备） |
| **吞吐** | `hybrid` QPS（单 workspace） | ≥ 50 |
| **可恢复** | raw → searchable 时间 | ≤ 5 min（PDF 100 页级别） |
| **一致性** | reconcile 周期 | ≤ 15 min |
| **可用性** | retrieval gateway 月度可用性 | ≥ 99.5% |
| **可观测** | 必埋点 | pipeline 各阶段耗时与失败率；检索 QPS / 延迟 / top1 命中率 |
| **可扩展** | 横向扩展 | Pipeline Worker / Embedder / Indexer 各自独立扩缩容 |
| **安全** | workspace 隔离 | 所有查询强制带 `workspace_id`；跨 ws 默认拒绝 |
| **存储** | 1K 文档估算 | ~7 GB（向量 ~2 GB + FTS ~200 MB + OSS ~5 GB） |

---

## 14. 关键场景（v0.1 验收用例）

| 场景 | 触发 | 期望 |
| --- | --- | --- |
| **S1. PDF 全文检索** | 录入 pricing.pdf | hybrid (semantic + lexical) 命中；带页码 + section snippet |
| **S2. PDF 双流水线** | 同一 PDF 走 Pipeline A + B | canonical_md 和 ocr_text 的 chunks 都可被检索到 |
| **S3. 图片反查** | 录入 chart.png | 用文本"柱状图" → visual 命中 |
| **S4. 录音转写检索** | 录入 meeting.wav | 用文本"Q3 定价" → 命中 transcript_segment + audio 时间戳 |
| **S5. 隐藏不删** | 把 doc 标 hidden | 检索默认不可见；`include_hidden=true` 仍可取 |
| **S6. 软删除** | 标 deleted | OSS 原文件保留；chunks 软删除；UI 不可见 |
| **S7. 版本切换** | raw 更新 | 旧版本 active 直到新版本 publish 成功；检索无中断 |
| **S8. Reconcile** | content_hash 变化 | reconcile 检测到变化，触发 pipeline 重跑 |
| **S9. Pipeline 追加** | 注册新 pipeline | 对已有 entity 按需重跑；不影响已有 representation |
| **S10. 视角预览** | 检索命中 pricing.pdf 的 chunk | 点击 → 预览 canonical_md（定位到第7页）；切换 → 预览 page_image / ocr_text / mind_map |
| **S11. 视角面板** | 打开 entity 详情 | 列出所有可用 representation + 状态 + preview_url；skipped/failed 的灰显 |
| **S12. 血缘级联失效** | raw 更新（content_hash 变化） | 沿 lineage 级联：page_image/ocr_text/canonical_md 全部标 stale；对应 chunks 检索不再命中 |
| **S13. 血缘级联重建** | S12 之后 | pipeline 自动重跑；新 representation ready → chunks active → 检索恢复 |
| **S14. 中间节点失效** | page_image 重建失败 | 下游 ocr_text/vlm_md 保持 stale；上游 canonical_md 不受影响（不同 lineage 分支） |

---

## 15. 里程碑

| 里程碑 | 周期 | 交付 |
| --- | --- | --- |
| **M0. Schema 冻结** | W1 | Entity / Representation / Chunk / Edge / Pipeline schema review 通过 |
| **M1. Ingest + Detect** | W2 | raw → entity + detect 跑通；content_hash 落盘 |
| **M2. Pipeline A (直接提取)** | W3-4 | canonical_md → chunks → text embedding → semantic index |
| **M3. Pipeline B (OCR)** | W5 | page_image → ocr_text → chunks → ocr embedding |
| **M4. Pipeline E (图片向量)** | W5 | page_image → image embedding → visual index |
| **M5. Pipeline F (音频转写)** | W6 | audio_segment → transcript → chunks → dual embedding |
| **M6. Hybrid Search + Retrieval Gateway** | W7 | hybrid / semantic / lexical / visual / ls / read / grep / glob |
| **M7. Intelligent Engine** | W8 | 规则版 router + RRF fusion + evidence pack |
| **M8. Reconcile + Publish + 版本管理** | W9 | 软删除 / 隐藏 / 版本切换 / 周期调和 |
| **M9. v0.1 GA** | W10 | S1–S9 全通过；NFR 达标 |

---

## 16. 风险与开放问题

| # | 风险 / 问题 | 缓解 / 待定 |
| --- | --- | --- |
| R1 | 文档版面解析准确率影响 canonical_md 质量 | quality 字段记录 confidence；fallback 到 ocr_text / vlm_md |
| R2 | 多模态 embedding 调用成本 | V5 API 单批 ≤ 64；batching + 缓存；按需 embed |
| R3 | 大文件 PDF 多 pipeline 并行慢 | pipeline 间并行；分页并行；中间产物缓存 |
| R4 | Lance 表 schema 演进 | 所有表带 `schema_version`；变更走 migration |
| R5 | OSS 一致性 vs 索引一致性 | content_hash 检测 + publish 原子切换 + reconcile 兜底 |
| R6 | 大文档增量更新成本 | v0.1 全量重建；v0.2 评估 page-level 增量 |
| R7 | Embedding 模型升级 | model_version 字段 + reconcile 检测过期 + 按需重跑 |
| Q1 | entity 是否需要"跨 collection 合并"？ | v0.1 不做；v0.2 讨论 `same_as` edge |
| Q2 | wiki_md / mind_map 的 LLM 编译成本 | v0.2 实现；异步、按需、按版本 |
| Q3 | graph index 用什么存储 | v0.1 用 Lance `edges` 表 + 内存 join；v0.2 评估 Neo4j |
| Q4 | 检索结果"高亮 / 片段截取" | v0.1 给 snippet；v0.2 接 highlighter |
| Q5 | multimodal embedding 与文本是否真的同空间 | V5 明确支持，但需回归测试 |
| Q6 | VLM pipeline 的模型选型 | v0.2 评估 Qwen2-VL / GPT-4o / Gemini |

---

## 17. 附录

### 17.1 与现有组件的对接

| 现有组件 | 对接方式 |
| --- | --- |
| **OSS Data Lake** | 直接读写；raw 路径即 source of truth |
| **Embedding V5** | 调 `/v1/embeddings`；按 §7.1 task 映射表选 task |
| **Chunking UseCase** | Pipeline A/B 的 chunk 阶段调用 `ChunkingWithSlidingWindowUseCase`；字段映射见下表 |
| **LanceDB** | chunks 主表（vector + FTS + scalar filter）；hybrid search 原生支持 |

### 17.2 Chunking UseCase 字段映射

| Chunk 字段 | Lance chunks 表字段 | 用途 |
| --- | --- | --- |
| `text` | `text` | 中心块原文，用于 snippet / FTS 索引 |
| `embedding_text` | `embedding_text` | 向量化输入文本 |
| `start_pos` | `start_pos` | 定位 |
| `token_count` | `token_count` | 统计 |
| `chunk_chars` | `chunk_chars` | 统计 |
| `metadata.header` | `section_header` | FTS + 过滤 |
| `metadata.level` | `section_level` | 过滤 |
| `metadata.chunk_type` | 不入 Lance | 仅 pipeline 内部使用 |
| `metadata.anchors` | `anchor` | 定位 |
| `metadata.title` | `doc_title` | FTS + 展示 |
| `metadata.page_number` | `page_number` | 过滤 + 展示 |

### 17.3 名词表

- **Entity**：知识对象，1 个 OSS Object = 1 个 Entity。
- **Representation**：Entity 的一种"认知视角"，可互为 derived_from。
- **Pipeline**：从 raw 或已有 representation 生成新 representation 的过程，是一等公民。
- **Chunk**：某个 Representation 下的检索最小单元，是一等公民。
- **Embedding**：Chunk 的向量索引，内嵌于 Lance chunks 表。
- **Index**：某类检索能力。
- **Manifest**：某次处理产物的注册清单。
- **Provenance**：结果可追溯到来源 + 版本 + pipeline。
- **Reconcile**：定期对账，修复状态漂移。

### 17.4 评审清单（Review Checklist）

- [ ] 1 OSS Object = 1 Entity 是否覆盖所有 v0.1 场景？
- [ ] Representation 的 derived_from DAG 是否满足可重建？
- [ ] Chunk 作为检索粒度是否能定位到页/段/时间戳？
- [ ] Pipeline 并行调度是否满足 partial success？
- [ ] Lance chunks 主表（vector + FTS + scalar filter）是否满足 hybrid search？
- [ ] 状态模型 + version 是否能区分"用户意图"与"处理状态"？
- [ ] content_hash 变更检测是否比 etag 更可靠？
- [ ] v0.1 范围是否足够小、足够完整？
- [ ] 与现有 OSS / V5 / Chunking 的对接路径是否清晰？

---

> **本 PRD 是设计基线（baseline）**。任何对核心抽象的修改（entity / representation / pipeline / chunk / 状态机）都应先回到本文件评审，再写代码。
