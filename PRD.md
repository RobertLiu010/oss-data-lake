# Vector-Lake 智能知识搜索引擎层 — PRD

> **版本**：v0.1 草案
> **状态**：待评审
> **目标读者**：产品 / 架构 / 工程 / 算法
> **核心定位**：把 OSS 数据湖升级为可被智能引擎直接调用的"知识搜索引擎层"。

---

## 0. 一句话定义

> **每个 raw object 会被编译成多个 entity；每个 entity 会生成多个 representation；每个 representation 可以进入不同 index；智能引擎根据问题动态选择 semantic、lexical、grep、visual、audio、table、graph 等检索能力。**

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
3. 为上层 Agent / RAG / 搜索 UI 提供统一的检索能力接口（`ls / read / grep / semantic / lexical / visual / audio / table / graph`）。
4. 解决状态一致性问题（raw / entity / representation / index 之间的可见性与重建）。

### 1.2 产品愿景

构建一个 **实体驱动、表现多模、检索可组合、状态可调和** 的知识搜索引擎层，作为上层 AI 应用（问答、Agent、研究助手、企业搜索）唯一可信的知识访问入口。

### 1.3 目标（Goals）

| 目标 | 描述 |
| --- | --- |
| **G1. 知识编译** | 把任意 raw object 编译成一组可被多种检索能力消费的 entity + representation。 |
| **G2. 多模态同构** | 文本、图像、音频、视频在同一向量空间可互检。 |
| **G3. 检索能力可组合** | 智能引擎根据问题动态选择并组合 `semantic / lexical / grep / visual / audio / table / graph / ls` 等能力。 |
| **G4. 不可变与可重建** | raw object 不可变；representation 可重建；entity 是稳定知识单元。 |
| **G5. 状态可调和** | OSS / manifest / Lance / index 状态不一致时，可被 reconcile 任务发现并修复。 |
| **G6. 可演进** | v0.1 仅支持 PDF/DOCX/PPTX/Image/Audio；后续可平滑扩展到 video、code、table、graph，**不破坏架构**。 |

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
| **Entity** | 知识实体（doc/page/table/image/audio/...） | 标识稳定，属性可演进 | 稳定知识单元 |
| **Representation** | 实体的一种"可计算视图"（markdown/text/layout/image/caption/...） | **可重建** | 派生产物 |
| **Embedding** | 某个 Representation 的向量索引 | **可重建** | 派生产物 |
| **Index** | 某类检索能力（semantic/lexical/grep/visual/...） | 可演进 | 检索入口 |
| **Edge** | 实体之间的关系（contains/mentions/cites/derived_from/...） | 可演进 | 图检索基础 |
| **Pipeline** | 从 raw object 生成 representations + embeddings + indexes 的过程 | — | 编排单元 |

### 2.2 主链路

```text
Raw Object (OSS, immutable)
    │
    ▼
[1] Ingest
    ▼
[2] Detect  (mime / size / hash / language)
    ▼
[3] Entity Extract  (doc / page / table / image / audio_segment / concept / claim …)
    ▼
[4] Represent  (raw / canonical_md / plain_text / layout / image / audio / transcript …)
    ▼
[5] Chunk / Segment  (text chunk / audio segment / video frame)
    ▼
[6] Embed  (text / image / audio / table / multimodal)
    ▼
[7] Index  (semantic / lexical / grep / graph / visual / audio)
    ▼
[8] Compile  (wiki_md / summary / claims / concept pages / backlinks)
    ▼
[9] Publish  (mark active, visible to retrieval)
    ▼
[10] Reconcile  (continuous; fix drift)
```

### 2.3 一句话架构

> **Raw Object → Entity → Representations → Embeddings / Indexes → Intelligent Engine**

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
│      semantic · lexical · visual · audio · table · graph     │
├──────────────────────────────────────────────────────────────┤
│  L3  Indexing Layer                                          │
│      Semantic (Lance vector) · Lexical (BM25)                │
│      Grep (ripgrep) · Graph (property graph)                 │
│      Visual / Audio / Table (specialized index)              │
├──────────────────────────────────────────────────────────────┤
│  L2  Representation Layer                                    │
│      raw · canonical_md · plain_text · layout_json           │
│      image · ocr_text · caption · audio · transcript         │
│      table_md / table_json · graph_json · wiki_md            │
├──────────────────────────────────────────────────────────────┤
│  L1  Entity Layer                                            │
│      Entity registry · Edge registry · Manifest              │
├──────────────────────────────────────────────────────────────┤
│  L0  Raw Object Store (OSS Data Lake)                        │
│      oss://vector-lake/{ws}/{col}/raw/{doc_id}/original      │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 模块划分

| 模块 | 职责 | 关键产出 |
| --- | --- | --- |
| **Ingest Service** | 监听 OSS 新对象、登记 manifest | manifest、pipeline run |
| **Detect Worker** | mime / language / hash / size | `detect.json` |
| **Entity Extractor** | 拆 raw 为 entity | entity.json × N |
| **Representer** | 为 entity 生成多种 representation | representation.json + OSS 文件 |
| **Chunker / Segmenter** | 文本切 chunk / 音频切 segment / 视频抽 frame | chunk / segment 元数据 |
| **Embedder** | 调用 Embedding V5 多模态服务 | embeddings 行 |
| **Indexer** | 写入 semantic / lexical / grep / graph / visual / audio index | index 状态 |
| **Compiler** | LLM 编译 wiki / summary / claims / concepts | wiki_md、claim entity |
| **Publisher** | 状态标记 active、版本切换 | active 版本 |
| **Reconciler** | 周期扫描 OSS / manifest / Lance / index | drift report、修复任务 |
| **Retrieval Gateway** | 暴露 `ls/read/stat/grep/glob/semantic/lexical/visual/audio/table/graph` | 统一检索 API |
| **Intelligent Engine** | 理解 query、路由能力、融合、重排 | answer / context pack |

### 3.3 数据流

```text
OSS Event
   │
   ▼
Ingest Queue  ────►  Pipeline Orchestrator
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
     Detect             Extract              Represent
                            │                   │
                            ▼                   ▼
                         Entity           Representation
                            │                   │
                            ▼                   ▼
                        Edge Build       Chunk / Segment
                                                │
                                                ▼
                                            Embed (V5)
                                                │
                                                ▼
                                              Index
                                                │
                                                ▼
                                            Compile
                                                │
                                                ▼
                                            Publish
                                                │
                                                ▼
                                          Active (queryable)
```

---

## 4. 数据模型

### 4.1 Entity（统一字段）

```json
{
  "entity_id": "doc:abc123",
  "entity_type": "document",
  "workspace_id": "ws_001",
  "collection_id": "kb_001",
  "name": "pricing.pdf",
  "source_uri": "oss://bucket/raw/pricing.pdf",
  "source_version": "etag_xxx",
  "status": "enabled",
  "created_at": "2026-06-05T10:00:00Z",
  "updated_at": "2026-06-05T10:00:00Z"
}
```

**entity_type 取值（v0.1 支持）**：

```text
document · page · section · paragraph · table · image · chart
audio · audio_segment · video · video_frame
person · company · concept · event · claim · decision · task
```

### 4.2 Representation

```json
{
  "representation_id": "rep:xxx",
  "entity_id": "doc:abc123",
  "rep_type": "canonical_md",
  "uri": "oss://bucket/representations/document/abc123/canonical.md",
  "content": null,
  "mime_type": "text/markdown",
  "derived_from": "oss://bucket/raw/pricing.pdf",
  "status": "ready",
  "quality": {
    "confidence": 0.96,
    "source": "parser"
  },
  "created_at": "2026-06-05T10:00:00Z",
  "updated_at": "2026-06-05T10:00:00Z"
}
```

**标准 rep_type（v0.1 落地集合）**：

```text
raw · canonical_md · plain_text · layout_json · page_image
image · chart · ocr_text · caption
table_md · table_json
audio · audio_segment · transcript · transcript_segment
video_frame · wiki_md · graph_json
```

### 4.3 Embedding

```json
{
  "embedding_id": "emb:xxx",
  "entity_id": "doc:abc123",
  "representation_id": "rep:xxx",
  "embedding_type": "text",
  "model": "embedding-v5-retrieval",
  "task": "retrieval.passage",
  "dimension": 1024,
  "vector_ref": "oss://bucket/embeddings/emb_xxx.bin",
  "status": "ready",
  "created_at": "2026-06-05T10:00:00Z"
}
```

**embedding_type**：`text | image | audio | table | code | multimodal`

### 4.4 Edge

```json
{
  "src_entity_id": "page:p_007",
  "dst_entity_id": "image:i_023",
  "edge_type": "contains",
  "confidence": 1.0,
  "source": "layout_parser",
  "created_at": "2026-06-05T10:00:00Z"
}
```

**edge_type**：`contains · mentions · cites · derived_from · same_as · contradicts · supports`

### 4.5 OSS 目录结构

```text
vector-lake/{workspace_id}/{collection_id}/

├── raw/
│   └── {doc_id}/original
│
├── entities/
│   └── {entity_type}/{entity_id}/entity.json
│
├── representations/
│   └── {entity_type}/{entity_id}/
│       ├── canonical.md
│       ├── plain.txt
│       ├── layout.json
│       ├── ocr.md
│       ├── caption.md
│       ├── table.json
│       └── preview.png
│
├── wiki/
│   └── {entity_id}.md
│
├── manifests/
│   └── {doc_id}.json
│
└── indexes/
    └── optional metadata
```

### 4.6 Lance 表设计

**不只一张 chunks 表**，建议至少四张：

| 表 | 关键字段 | 用途 |
| --- | --- | --- |
| `entities` | `entity_id, entity_type, workspace_id, collection_id, name, source_uri, source_version, status, created_at, updated_at` | 实体注册表 |
| `representations` | `representation_id, entity_id, rep_type, uri, content, mime_type, derived_from, status, quality_score, created_at, updated_at` | 表现注册表 |
| `embeddings` | `embedding_id, entity_id, representation_id, embedding_type, model, dimension, vector, status, created_at` | 向量元数据（`vector` 可选；可指向 OSS 实际向量文件） |
| `edges` | `src_entity_id, dst_entity_id, edge_type, confidence, source, created_at` | 图边 |

> **可选项**（v0.2+）：`chunks`（embedding 粒度的 chunk 元数据）、`pipeline_runs`（运行历史）。

---

## 5. 状态模型（分层）

### 5.1 OSS Object Tag — 用户意图

```text
rag_status = enabled | hidden | deleted
```

### 5.2 Pipeline Status — 处理状态

```text
pending → running → partial_success | success | failed
                                        → stale（raw 变了）
```

### 5.3 Representation Status — 单个表现是否可用

```text
ready · skipped · failed · stale · deleted
```

### 5.4 Index Status — 是否进入检索

```text
indexed · not_indexed · index_failed · stale
```

### 5.5 状态联动规则

| 触发事件 | 联动动作 |
| --- | --- |
| raw object `etag` 变化 | 旧 representation 标 `stale`；触发重建；新版本进入 `ready`；index 切换 |
| representation `ready` | 自动触发对应 index 的 `indexed` |
| representation `failed` | pipeline `partial_success`；上层查询时 fallback |
| OSS tag → `hidden` | representation 仍保留；index 标 `hidden`（不进入默认检索） |
| OSS tag → `deleted` | 保留 vector / representation 软删除；index 不再 query |

---

## 6. 管道（Pipeline）阶段定义

| 阶段 | 输入 | 输出 | 失败行为 |
| --- | --- | --- | --- |
| **1. ingest** | OSS 事件 | `manifest.json` | 重试 / DLQ |
| **2. detect** | raw path | `detect.json` (mime/hash/size/lang) | 标记 `failed` |
| **3. entity_extract** | raw + detect | entity × N | 至少 document entity 必成；子实体允许失败 |
| **4. represent** | entity | representation × M (按 entity_type 决定) | 标 `skipped/failed` |
| **5. chunk_or_segment** | text/audio/video representation | chunk/segment 元数据 | 标 `failed` 但保留原文 |
| **6. embed** | representation → chunk | embedding 行 | 标 `failed`；可重试 |
| **7. index** | embedding / text / image | semantic/lexical/grep/graph/visual/audio index | 标 `index_failed` |
| **8. compile** | entity + representation + edge | `wiki_md`、claim、concept | 异步可重试 |
| **9. publish** | version manifest | 切到 active 版本 | 原子切换 |
| **10. reconcile** | 周期扫描 | drift 报告 + 修复任务 | 持续运行 |

### 6.1 编排原则

- **idempotent**：所有阶段可重跑，重跑结果应一致或单调升级。
- **append-only on raw**：raw object 永不修改；重建只写新 representation。
- **versioned publish**：每次 publish 切到一个新 manifest 版本，检索时按版本号定位。
- **partial success 优先**：子任务失败不阻塞主实体可用。

---

## 7. 不同文件类型的表现（Representation 矩阵）

### 7.1 文档（pdf/docx/pptx/html）

```text
raw → canonical_md → plain_text → layout_json → page_image
     → table_md / table_json → image / chart → ocr_text
     → text_embedding → image_embedding → wiki_md
```

### 7.2 图片

```text
raw image → ocr_text → caption → detected_objects
         → image_embedding → caption_text_embedding → graph_json
```

### 7.3 音频

```text
raw audio → audio_segment → transcript → transcript_segment
         → speaker diarization
         → audio_embedding → transcript_text_embedding → wiki_md
```

### 7.4 视频

```text
raw video → audio track → transcript → keyframes → scene segments
         → frame caption → frame image_embedding
         → transcript_text_embedding → wiki_md
```

### 7.5 表格（v0.2）

```text
table → table_md → table_json → schema_json → summary → cell_text
     → table_embedding → graph_json
```

---

## 8. 检索能力（Retrieval Capabilities）

### 8.1 能力清单

| 能力 | 面对的 Representation | 典型输入 | 典型输出 |
| --- | --- | --- | --- |
| `ls` | manifest / entity | dir / collection | entity 列表 |
| `stat` | manifest / entity | entity_id | 元数据 + 状态 |
| `read` | representation | entity_id + rep_type | 内容 |
| `grep` | raw text / md / ocr / transcript | pattern | 行级命中 |
| `glob` | entity name | pattern | 匹配 entity |
| `semantic` | text/transcript/caption embedding | 自然语言 | top-k entity + score |
| `lexical` | plain_text / canonical_md / ocr_text | 关键词 | top-k entity + BM25 |
| `visual` | image / page_image / video_frame embedding | image / text | top-k entity |
| `audio` | audio / audio_segment embedding | audio / text | top-k entity |
| `table` | table_json / table_md / table_embedding | SQL-like / 关键词 | 表行 + 来源 |
| `graph` | edges / graph_json / wiki backlinks | 实体 / 关系查询 | 邻居子图 |

### 8.2 能力与 Representation 的关系

```text
semantic search
  → text_embedding / transcript_embedding / caption_embedding

lexical search
  → plain_text / canonical_md / transcript / ocr_text

grep
  → raw text / md / ocr / transcript

visual search
  → image_embedding / page_image_embedding / video_frame_embedding

audio search
  → audio_embedding / audio_segment_embedding

table search
  → table_json / table_md / table_embedding

graph search
  → edges / graph_json / wiki backlinks

ls / read / stat
  → OSS + manifest + entity metadata
```

### 8.3 工具协议（v0.1 形态）

```json
{
  "tool": "semantic",
  "args": {
    "query": "Q3 定价策略",
    "filters": { "entity_type": ["document", "page"], "workspace_id": "ws_001" },
    "top_k": 10
  }
}
```

所有工具返回统一的 **evidence 包装**：

```json
{
  "tool": "semantic",
  "results": [
    {
      "entity_id": "page:p_007",
      "representation_id": "rep:xxx",
      "score": 0.83,
      "snippet": "...",
      "highlights": [...],
      "provenance": { "source_uri": "...", "raw_version": "etag_xxx" }
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
    └─ 决定 filter / top_k
   │
   ▼
[3] Parallel Execution
    └─ 调 ls/semantic/lexical/grep/visual/audio/table/graph
   │
   ▼
[4] Result Fusion & Rerank
    ├─ 跨工具去重（按 entity_id + 句段）
    ├─ 证据合并
    └─ LLM 重排 / 解释
   │
   ▼
[5] Pack & Return
    └─ evidence pack → 上层 RAG / Agent
```

### 9.3 路由策略（v0.1 规则版）

| Query 类型 | 优先能力 | 次选 |
| --- | --- | --- |
| 概念 / 解释 | semantic + lexical | grep |
| 精确字段 / 编号 | lexical + grep | semantic |
| "找一张图" | visual (image↔text) | caption semantic |
| "找一段录音" | audio (text↔audio) | transcript lexical |
| 跨实体关系 | graph | semantic |
| 表格行 / 列 | table | lexical |

> 后续可替换为学习型 router（v0.2+）。

---

## 10. 设计原则（不可妥协）

1. **原始文件不可变**：`raw object = source of truth`。
2. **Representation 可重建**：`canonical_md / OCR / caption / embedding` 都是派生物，丢失不致命。
3. **Entity 是稳定知识单元**：文件版本变化，entity 仍可定位（通过 `derived_from` + `source_version`）。
4. **检索不直接面对文件**：检索面对的是 representation 和 entity。
5. **隐藏不删除向量**：`enabled/hidden/deleted` 与 `active/stale` 分离，软删除保留可恢复能力。
6. **idempotent & append-only**：管线可重跑，结果一致或单调升级。
7. **可解释性优先**：所有结果必须带 `provenance`（来源 URI、版本、representation）。

---

## 11. v0.1 范围

### 11.1 文件类型

```text
pdf · docx · pptx · image · audio
```

### 11.2 Representation

```text
raw · canonical_md · plain_text · ocr_text · image
transcript · transcript_segment · caption · wiki_md
```

### 11.3 Index

```text
semantic · lexical · grep · visual · graph
```

### 11.4 状态

```text
enabled · hidden · deleted · active · stale
```

### 11.5 能力

```text
ls · read · stat · grep · glob
semantic · lexical · visual · audio · table · graph
```

### 11.6 明确不在 v0.1 范围

- 视频 keyframe / 场景切分（仅预留 schema）
- 表格列式检索（v0.2）
- 学习型 router（v0.2）
- 多租户 / 计费（后续）
- 端到端 RAG 答案生成（上层）

---

## 12. API 设计（v0.1 形态）

### 12.1 内部管线 API（异步）

| API | 说明 |
| --- | --- |
| `POST /ingest` | 登记 raw object，触发 pipeline |
| `GET /pipeline_runs/{run_id}` | 查询运行状态 |
| `GET /entities/{entity_id}` | 取 entity |
| `GET /representations?entity_id=...&rep_type=...` | 列表 representation |
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
| `POST /tools/visual` | 图像 / 帧检索 |
| `POST /tools/audio` | 音频检索 |
| `POST /tools/table` | 表格检索 |
| `POST /tools/graph` | 图检索 |
| `POST /engine/ask` | 智能引擎（综合） |

### 12.3 统一响应

```json
{
  "request_id": "req_xxx",
  "tool": "semantic",
  "took_ms": 134,
  "results": [ /* evidence pack */ ],
  "provenance": { "manifest_version": "v_42", "indexed_at": "..." }
}
```

---

## 13. 非功能需求（NFR）

| 维度 | 指标 | v0.1 目标 |
| --- | --- | --- |
| **检索延迟** | `semantic` P95 | ≤ 500 ms（含 embedding） |
| | `lexical / grep` P95 | ≤ 200 ms |
| | `read` P95 | ≤ 300 ms（OSS 读） |
| **吞吐** | `semantic` QPS（单 workspace） | ≥ 50 |
| **可恢复** | raw → searchable 时间 | ≤ 5 min（PDF 100 页级别） |
| **一致性** | reconcile 周期 | ≤ 15 min |
| **可用性** | retrieval gateway 月度可用性 | ≥ 99.5% |
| **可观测** | 必埋点 | `ingest/detect/extract/represent/embed/index/publish/reconcile` 阶段耗时与失败率；检索 QPS / 延迟 / top1 命中率 |
| **可扩展** | 横向扩展 | Ingest/Detect/Embed/Index 各 worker 独立扩缩容 |
| **安全** | workspace 隔离 | 所有查询强制带 `workspace_id`；跨 ws 默认拒绝 |

---

## 14. 关键场景（v0.1 验收用例）

| 场景 | 触发 | 期望 |
| --- | --- | --- |
| **S1. PDF 全文检索** | 录入 pricing.pdf | semantic + lexical + grep 都能命中；带页码 snippet |
| **S2. 图片反查** | 录入 chart.png | 用文本"柱状图" → visual 命中 |
| **S3. 录音转写检索** | 录入 meeting.wav | 用文本"Q3 定价" → 命中 transcript_segment + audio 时间戳 |
| **S4. 隐藏不删** | 把 doc 标 hidden | 检索默认不可见；`include_hidden=true` 仍可取 |
| **S5. 软删除** | 标 deleted | OSS 原文件保留；vector 软删除；UI 不可见 |
| **S6. 重建** | 改 parser | 对应 entity 的 representation 重新生成，wiki 重建 |
| **S7. Reconcile** | 手动删除 OSS 某个 chunk 文件 | reconcile 跑完后该 representation 标 `stale` 并补回 |

---

## 15. 里程碑

| 里程碑 | 周期 | 交付 |
| --- | --- | --- |
| **M0. Schema 冻结** | W1 | 实体/表/目录/状态模型 review 通过 |
| **M1. Ingest + Detect** | W2 | raw → detect 跑通；manifest 落盘 |
| **M2. Entity Extract** | W3 | pdf/docx/pptx/image/audio 出 entity 列表 |
| **M3. Represent** | W4 | canonical_md / plain_text / ocr / image / transcript / caption |
| **M4. Embed + Index** | W6 | semantic / lexical / grep / visual / graph 全部接通 |
| **M5. Retrieval Gateway** | W7 | 11 个 tool API 上线 |
| **M6. Intelligent Engine** | W8 | 规则版 router + 融合 + evidence pack |
| **M7. Reconcile + Publish** | W9 | 软删除 / 隐藏 / 版本切换 / 周期调和 |
| **M8. v0.1 GA** | W10 | S1–S7 全通过；NFR 达标 |

---

## 16. 风险与开放问题

| # | 风险 / 问题 | 缓解 / 待定 |
| --- | --- | --- |
| R1 | 文档版面解析准确率影响 canonical_md 质量 | 引入 layout parser benchmark；quality 字段记录 confidence；fallback 到 plain_text |
| R2 | 多模态 embedding 调用成本 | V5 API 单批 ≤ 64；batching + 缓存；按需 embed |
| R3 | 大文件 PDF 切分慢 | 分页并行；中间产物缓存；MRL 截断降维 |
| R4 | Lance 表 schema 演进 | 所有表带 `schema_version`；变更走 migration |
| R5 | OSS 一致性 vs 索引一致性 | 强 publish 流程 + reconcile 兜底 |
| Q1 | entity 是否需要"跨 collection 合并"？ | v0.1 不做；v0.2 讨论 `same_as` edge |
| Q2 | wiki_md 的 LLM 编译成本与频率 | 异步、按需、按版本 |
| Q3 | graph index 用什么存储 | v0.1 用 Lance `edges` 表 + 内存 join；v0.2 评估 Neo4j / 内存图 |
| Q4 | 检索结果"高亮 / 片段截取" | v0.1 给 snippet；v0.2 接 highlighter |
| Q5 | multimodal embedding 与文本是否真的同空间 | 已在 V5 中明确支持，但仍需回归测试 |

---

## 17. 附录

### 17.1 与现有组件的对接

| 现有组件 | 对接方式 |
| --- | --- |
| **OSS Data Lake** | 直接读写；raw 路径即 source of truth |
| **Embedding V5** | 调 `/v1/embeddings`；按 `embedding_type` 选 `task` |
| **Chunking UseCase** | 在 L2 `Representation Layer` 的 `chunk_or_segment` 阶段调用 `ChunkingWithSlidingWindowUseCase` |
| **LanceDB** | L3 Indexing Layer 的 vector / 表格存储 |

### 17.2 名词表

- **Entity**：知识实体，最小可被引用的知识单元。
- **Representation**：实体的"可计算视图"。
- **Embedding**：representation 的向量索引。
- **Index**：某类检索能力。
- **Pipeline**：从 raw 到 queryable 的过程。
- **Manifest**：某次处理产物的注册清单。
- **Provenance**：结果可追溯到来源 + 版本。
- **Reconcile**：定期对账，修复状态漂移。

### 17.3 评审清单（Review Checklist）

- [ ] Entity / Representation / Embedding / Edge schema 是否覆盖所有 v0.1 场景？
- [ ] OSS 目录与 Lance 表是否满足不可变 + 可重建？
- [ ] 状态模型是否能区分"用户意图"与"处理状态"？
- [ ] 11 个 tool API 是否覆盖上层 80% 检索需求？
- [ ] Intelligent Engine 规则版 router 是否合理？
- [ ] NFR 指标是否可观测、可验收？
- [ ] v0.1 范围是否足够小、足够完整？
- [ ] 与现有 OSS / V5 / Chunking 的对接路径是否清晰？

---

> **本 PRD 是设计基线（baseline）**。任何对核心抽象的修改（entity / representation / index / 状态机）都应先回到本文件评审，再写代码。
