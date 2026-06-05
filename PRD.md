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

同一个 Entity 可以有多种认知视角，它们之间可以互为 derived_from：

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

derived_from 链：

```text
raw_html → canonical_md
raw_html → page_screenshot
page_screenshot → vlm_extracted_md    ← 图片→文字
canonical_md → mind_map               ← 文字→结构
canonical_md → summary
canonical_md → graph_json
```

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
│  L3  Indexing Layer (LanceDB)                                │
│      chunks 主表 (vector + FTS + scalar filter)              │
│      Hybrid Search (RRF / CrossEncoder rerank)               │
│      Graph index (edges 表) · Grep (ripgrep on OSS)          │
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
| **Retrieval Gateway** | 暴露统一检索 API | tool 调用结果 |
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
- `derived_from` 指向另一个 `representation_id`（而非 OSS URI），形成 representation DAG。
- `derived_chain` 记录完整溯源链，方便调试和重建。
- `pipeline_id` 标识由哪条流水线产出。

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

### 4.6 OSS 目录结构

```text
vector-lake/{workspace_id}/{collection_id}/

├── raw/
│   └── {entity_id}/original
│
├── representations/
│   └── {entity_id}/v{version}/
│       ├── canonical.md
│       ├── plain.txt
│       ├── layout.json
│       ├── page_image/
│       │   ├── page_001.png
│       │   └── page_002.png
│       ├── ocr.md
│       ├── vlm_extracted.md
│       ├── caption.md
│       ├── table.json
│       ├── mind_map.json
│       ├── graph.json
│       └── preview.png
│
├── wiki/
│   └── {entity_id}.md
│
└── manifests/
    └── {entity_id}.json
```

**关键变化**：增加 `v{version}/` 路径，支持多版本共存。

### 4.7 Lance 表设计

**核心检索表 = chunks（内嵌 vector）**，辅助表 = entities / representations / edges / pipelines。

#### `chunks`（Lance 主表，检索入口）

```text
chunk_id             string
entity_id            string
entity_version       int
representation_id    string
rep_type             string
pipeline_id          string
chunk_index          int
text                 string              # 中心块原文（同时建 FTS 索引）
embedding_text       string              # 向量化文本
start_pos            int
token_count          int
chunk_chars          int
page_number          int?                # 可 null
section_header       string?             # 可 null
section_level        int?                # 可 null
anchor               string?             # 可 null
doc_title            string?             # 可 null
modality             string              # text / image / audio / table
content_hash         string              # chunk 文本的 SHA-256
workspace_id         string              # 安全隔离
collection_id        string
source_uri           string              # raw object URI
source_version       string              # etag
model_version        string              # embedding 模型版本
vector               fixed_size_list<float>  # Lance 原生 vector 列
status               string              # active / hidden / deleted / stale
created_at           timestamp
```

> **Lance 索引**：`vector` 列建 IVF_PQ 或 HNSW；`text` 列建 FTS 索引；`workspace_id` / `collection_id` / `entity_type` / `modality` / `status` 建 scalar 索引。

#### `entities`（辅助表，元数据查询）

```text
entity_id · entity_type · workspace_id · collection_id · name
source_uri · source_version · content_hash · version
status · created_at · updated_at
```

#### `representations`（辅助表，表现注册）

```text
representation_id · entity_id · entity_version · rep_type · uri
mime_type · derived_from · derived_chain · pipeline_id
status · quality_score · created_at · updated_at
```

#### `edges`（辅助表，图遍历）

```text
src_entity_id · dst_entity_id · edge_type · confidence · source · created_at
```

#### `pipeline_runs`（辅助表，运行历史）

```text
run_id · entity_id · entity_version · pipeline_id · status
started_at · finished_at · error_message
```

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
| raw object `content_hash` 变化 | entity.version++；触发所有 pipeline 重跑；旧 chunks 保持 active 直到新版本 publish |
| representation `ready` | 触发对应 chunks 的 embed + index |
| representation `failed` | pipeline `partial_success`；已有 representation 的 chunks 仍可用 |
| OSS tag → `hidden` | entity.status=hidden；所有 chunks 标 `hidden`（不进入默认检索） |
| OSS tag → `deleted` | entity.status=deleted；chunks 软删除；OSS 原文件保留 |
| embedding 模型升级 | 检测 `model_version` 过期；触发对应 chunks 重跑 embed |
| pipeline 新增 | 对已有 entity 按需重跑新 pipeline；不影响已有 representation |

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

### 8.1 能力清单

| 能力 | 面对的数据 | 典型输入 | 典型输出 |
| --- | --- | --- | --- |
| `ls` | entity | dir / collection | entity 列表 |
| `stat` | entity | entity_id | 元数据 + 状态 |
| `read` | representation | entity_id + rep_type | 内容 |
| `grep` | OSS 上的 text / md / ocr / transcript | pattern | 行级命中 |
| `glob` | entity name | pattern | 匹配 entity |
| `semantic` | chunks.vector | 自然语言 | top-k chunk + score |
| `lexical` | chunks.text (FTS) | 关键词 | top-k chunk + BM25 |
| `hybrid` | chunks.vector + chunks.text | 自然语言 | top-k chunk + 融合 score |
| `visual` | chunks.vector (modality=image) | image / text | top-k chunk |
| `audio` | chunks.vector (modality=audio) | audio / text | top-k chunk |
| `table` | chunks (modality=table) | SQL-like / 关键词 | 表行 + 来源 |
| `graph` | edges | 实体 / 关系查询 | 邻居子图 |

### 8.2 Hybrid Search（v0.1 核心检索模式）

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

### 8.3 预览能力（Preview）

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

### 8.4 工具协议

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
