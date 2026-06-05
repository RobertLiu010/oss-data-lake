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
| **Embedding** | 某个 Chunk 的向量索引 | **可重建** | 内嵌于 `representations.lance` 的 vector 列 |
| **Index** | 某类检索能力（semantic/lexical/grep/visual/...） | 可演进 | 检索入口 |
| **Lineage** | Representation 之间的血缘关系（谁从谁派生） | **可追溯** | 一等公民，从文件命名 + staging Parquet 实时推算，支持级联失效 / 影响分析 |
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
│      事件驱动 + 迭代式 OSS prefix 扫描 → 目录树                │
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
| **Event Listener** | 订阅 OSS 事件，实时更新 VFS 目录树 + 触发血缘重算 | 增量 VFS 视图 + 事件队列 |
| **Reconciler** | 周期全量扫描 OSS prefix，对账 VFS 视图与 OSS 实际状态 | drift 报告 + 修复 |
| **VFS Builder** | 迭代式扫描 OSS prefix，构建虚拟文件系统目录树 | 目录树 + 路径映射 |
| **Retrieval Gateway** | 暴露统一检索 API（含 VFS 工具） | tool 调用结果 |
| **Intelligent Engine** | 理解 query、路由能力、融合、重排 | evidence pack |

### 3.3 数据流：事件驱动 + 实时 VFS

**核心：OSS 事件是所有变更的唯一入口，VFS 是实时数据源。**

```text
┌──────────────────────────────────────────────────────────────┐
│  OSS Bucket                                                  │
│      ObjectCreated / ObjectRemoved / ObjectModified          │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────────┐
                  │   Event Listener     │  ← 订阅 OSS 事件流
                  │   (实时)             │
                  └─────────┬───────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
         增量更新 VFS 树        触发血缘重算
                │                       │
                ▼                       ▼
         VFS 目录树            受影响下游标 stale
         (内存视图)                   │
                                      ▼
                              触发 pipeline 重跑
                                      │
                                      ▼
                              写 staging Parquet
                                      │
                                      ▼
                              汇聚 → representations.lance
                                      │
                                      ▼
                              Active (queryable)
```

**事件类型与处理**：

| 事件 | 触发条件 | VFS 更新 | 血缘动作 | 检索动作 |
| --- | --- | --- | --- | --- |
| `ObjectCreated` | 新文件上传 | 增量添加节点 | 推算新增边 | 触发对应 pipeline |
| `ObjectModified` | 文件覆盖（raw 更新） | 更新节点属性 | 下游标 stale → 级联重建 | 触发重建 |
| `ObjectRemoved` | 文件删除 | 移除节点 | 下游标 stale | 受影响 rep 从检索移除 |

**VFS 与检索的协作**：

```text
VFS 目录树（内存，实时）
  ├─ ls / stat / glob → 读目录树
  ├─ grep → 迭代式读 OSS 文本文件
  ├─ read → 读 OSS 文件内容
  └─ 提供路径 ↔ Entity/Representation 映射，给 Lance 检索用
```

**Reconciler（兜底）**：

事件可能丢失（网络抖动、Listener 宕机），所以 Reconciler 周期全量扫描 OSS prefix，与 VFS 视图对账：

```text
Reconciler 周期任务（每 15 min）
  ├─ 全量扫描 vector-lake/{ws}/{col}/ prefix
  ├─ 与 VFS 内存视图对比
  ├─ 修复漂移（增删改）
  └─ 触发漏掉的事件处理
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

#### Entity 作为类：方法抽象

**Entity 是一个对象**，所有操作以 Entity 为入口组织。方法和属性在 OSS 上实时反映（无持久化元数据）。

```python
class Entity:
    """一个知识对象 = 一个 OSS 目录 + 一个 OSS Tag。"""

    # ===== 标识属性（从 OSS Tag 实时读取）=====
    entity_id: str                # 目录名 = entity_id
    workspace_id: str             # 从路径前缀解析
    collection_id: str            # 从路径前缀解析
    entity_type: str              # document / image / audio / video（OSS Tag）
    name: str                     # pricing.pdf（OSS Tag）
    content_hash: str             # raw SHA-256（OSS Tag）
    version: int                  # 单调递增（OSS Tag）
    status: str                   # enabled / hidden / deleted（OSS Tag）
    labels: list[str]             # 业务标签（OSS Tag）
    category: str                 # 分类（OSS Tag）
    project: str                  # 项目归属（OSS Tag）
    oss_path: str                 # oss://bucket/vector-lake/{ws}/{col}/{entity_id}/
    created_at: datetime
    updated_at: datetime

    # ===== 表现管理（生成表现）=====
    def generate_representation(self, rep_type: str) -> Representation:
        """生成单个 representation。触发对应 pipeline，写入 staging。"""

    def generate_all_representations(self) -> list[Representation]:
        """生成所有该 entity_type 适用的 representations。"""

    def regenerate(self, rep_type: str) -> Representation:
        """重新生成单个 representation。血缘级联：标 stale → 重建 → publish。"""

    def regenerate_all(self) -> list[Representation]:
        """重新生成所有 representations。"""

    # ===== 索引管理（生成索引）=====
    def build_index(self, index_type: str) -> None:
        """对 representations.lance 建指定索引（vector / fts / scalar）。"""

    def build_all_indexes(self) -> None:
        """建所有适用索引。"""

    def rebuild_index(self, index_type: str) -> None:
        """删除旧索引并重建。"""

    def refresh_indexes(self) -> None:
        """representation 变动后增量更新索引。"""

    # ===== 查询表现清单 =====
    def list_representations(self) -> list[Representation]:
        """列出所有 representation（含 status / quality / mtime）。"""

    def get_representation(self, rep_type: str) -> Representation:
        """获取指定 rep_type 的 representation（含 content / metadata）。"""

    def list_pipelines(self) -> list[Pipeline]:
        """列出已执行过的 pipeline（含运行历史）。"""

    def list_indexes(self) -> list[Index]:
        """列出已构建的索引（含索引状态、文件大小）。"""

    def list_chunks(self, rep_type: str = None) -> list[Chunk]:
        """列出可检索单元（来自 representations.lance）。"""

    # ===== 血缘（Lineage）=====
    def get_lineage(self, rep_type: str = None) -> LineageDAG:
        """获取血缘 DAG（实时从文件结构推算）。"""

    def get_upstream(self, rep_type: str) -> list[Representation]:
        """获取指定 rep 的所有上游。"""

    def get_downstream(self, rep_type: str) -> list[Representation]:
        """获取指定 rep 的所有下游。"""

    def cascade_invalidate(self, rep_type: str) -> None:
        """级联失效：从指定 rep 开始，所有下游标 stale → 触发重建。"""

    # ===== 状态管理 =====
    def hide(self) -> None:
        """隐藏：OSS Tag rag_status=hidden。检索默认不可见。"""

    def show(self) -> None:
        """显示：OSS Tag rag_status=enabled。"""

    def delete(self) -> None:
        """软删除：OSS Tag rag_status=deleted。文件保留，永不返回。"""

    def restore(self) -> None:
        """恢复：OSS Tag rag_status=enabled。"""

    def update_tags(self, **tags) -> None:
        """更新任意 OSS Tag（labels / category / project / ...）。"""

    # ===== 检索（基于 representations.lance）=====
    def search(
        self,
        query: str = None,
        query_vector: list[float] = None,
        rep_types: list[str] = None,
        modalities: list[str] = None,
        top_k: int = 10,
        reranker: str = "rrf"
    ) -> list[Chunk]:
        """在该 Entity 内执行 hybrid search。"""

    def grep(self, pattern: str, rep_types: list[str] = None) -> list[GrepHit]:
        """在该 Entity 内执行文本匹配（带 metadata）。"""

    # ===== 预览（基于 VFS）=====
    def preview(self, rep_type: str, page: int = None) -> PreviewContent:
        """预览指定 representation 的内容。"""

    def perspectives(self) -> PerspectivesView:
        """返回视角面板（所有可用 rep + 状态 + preview_url）。"""

    # ===== 生命周期 =====
    def export(self) -> EntityBundle:
        """导出整个 Entity 目录为可迁移包。"""

    def destroy(self) -> None:
        """物理删除：删除整个 OSS 目录。"""

    def exists(self) -> bool:
        """检查 Entity 是否存在（OSS 目录存在）。"""
```

**方法分组**：

| 类别 | 方法 | 操作对象 |
| --- | --- | --- |
| **生成表现** | `generate_*` / `regenerate_*` | 触发 pipeline |
| **生成索引** | `build_index*` / `rebuild_index*` | Lance 索引 |
| **查询清单** | `list_*` / `get_*` | 表现 / 流水线 / 索引 / chunk |
| **血缘** | `get_lineage*` / `cascade_invalidate` | 血缘 DAG |
| **状态** | `hide` / `show` / `delete` / `restore` / `update_tags` | OSS Tag |
| **检索** | `search` / `grep` | representations.lance + OSS |
| **预览** | `preview` / `perspectives` | VFS |
| **生命周期** | `export` / `destroy` / `exists` | OSS 目录 |

**Entity vs LanceDB 行**：

Entity 不是数据库行，而是**一个聚合根**，把以下资源聚合在一起：
- 一个 OSS 目录（含 raw + 所有 representations + staging + Lance）
- 一个 OSS Tag（含状态 / 标签 / 元数据）
- 一个血缘 DAG（实时推算）
- 一组可检索单元（representations.lance 行）

所有方法都通过这个聚合根访问，调用方不需要直接操作 OSS 或 Lance。

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

### 4.6 存储模型：Entity 目录自包含 + Parquet 写入 → Lance 索引

**核心决策**：

1. **每个 Entity 一个目录**，所有 representation 文件 + Lance 数据都在这个目录下，自包含。
2. **写入用 Parquet**（快写、隔离），**查询用 Lance**（索引、hybrid search），中间通过迭代式汇聚衔接。
3. **1 张 Lance 表**：`representations.lance`（Entity 目录内）。血缘实时推算，元数据用 OSS Tag。

```text
┌─────────────────────────────────────────────────────────────┐
│  L1  写入层（Parquet）                                       │
│      每 Entity 目录下写入 Parquet，小文件快写，天然隔离         │
│      pipeline 产出直接落盘，无需全局协调                       │
├─────────────────────────────────────────────────────────────┤
│  L2  汇聚层（Prefix Merge）                                  │
│      迭代式扫描 Entity 目录，将 Parquet 转为 Lance             │
│      每 Entity 目录内独立转换，无需跨 Entity 协调              │
├─────────────────────────────────────────────────────────────┤
│  L3  查询层（Lance）                                         │
│      每 Entity 目录内的 representations.lance 支持检索         │
│      跨 Entity 检索通过 VFS 扫描 + OSS Tag 路由 + fan-out        │
│      Lance 原生索引（IVF_PQ / HNSW / FTS）                   │
└─────────────────────────────────────────────────────────────┘
```

#### OSS 目录结构 + OSS Object Tagging

**核心决策**：
1. **每个 Entity 一个目录**，所有 representation 文件 + Lance 数据都在这个目录下，自包含。
2. **零持久化元数据** — 不需要 `catalog.lance`、不需要 `lineage.json`、不需要 `entity.json`。
3. **OSS Object Tagging** 作为唯一的状态/标签存储层（`rag_status` / `labels` / `category` / `project`）。
4. **VFS 实时扫描 prefix** 重建目录树 + 血缘图，所有元数据从 OSS 实时获取。
5. **1 张 Lance 表**：`representations.lance`（Entity 目录内）。

```text
vector-lake/{workspace_id}/{collection_id}/
│
├── {entity_id}/                                 ← Entity 目录（自包含）
│   ├── original                                 ← raw 文件（带 OSS Tag）
│   ├── canonical.md                             ← representation 文件
│   ├── ocr.md
│   ├── vlm_extracted.md
│   ├── page_image/
│   │   ├── page_001.png
│   │   └── page_007.png
│   ├── mind_map.json
│   ├── graph.json
│   ├── summary.md
│   ├── wiki.md
│   ├── ...
│   ├── staging/                                 ← L1 写入层（Pipeline 产出）
│   │   └── representations_v{N}.parquet         ← 可检索单元 + vectors
│   └── representations.lance/                   ← L3 查询层（汇聚后）
│       ├── data/
│       └── _indices/
│           ├── vector.idx
│           └── fts.idx
│
├── {entity_id_2}/                               ← 另一个 Entity
│   ├── original
│   ├── ...
│   ├── staging/
│   └── representations.lance/
```

**关键设计**：
- Entity 目录 = 该 Entity 的完整知识单元，包含所有 representation 文件 + Lance 索引。
- 迁移/复制/删除 = 操作整个 Entity 目录。
- 不同 Entity 之间完全隔离，无并发写入冲突。
- **零持久化元数据**：catalog / lineage / entity 元数据全部从 OSS 实时获取（VFS 扫描 + OSS Tag API）。

#### 1 张 Lance 表 + OSS Object Tagging

| # | 文件 | 位置 | 用途 |
| --- | --- | --- | --- |
| 1 | `representations.lance` | Entity 目录内 | 该 Entity 的所有可检索单元（含 vector + text） |
| — | OSS Object Tagging | raw 对象 | Entity 的状态/标签（rag_status / labels / category / project） |

**为什么只用 1 张 Lance 表**：
- `catalog.lance` 不需要 — VFS 扫描 prefix 即可获取所有 Entity 目录。
- `lineage.json` 不需要 — 从文件命名规则 + staging Parquet 实时推算血缘。
- `entity.json` 不需要 — Entity 元数据从 OSS Tag 实时读取。
- 所有元数据都可以从 OSS 实时重建，零持久化 → 没有同步问题。

#### OSS Object Tagging（唯一的状态/标签层）

**所有 Entity 元数据存在 OSS 对象的 Tag 上**，通过 `PutObjectTagging` / `GetObjectTagging` API 读写。

**Tag schema**（打在 `{entity_id}/original` 对象上）：

| Key | 取值 | 说明 |
| --- | --- | --- |
| `rag_status` | `enabled` / `hidden` / `deleted` | 用户意图，VFS 过滤 |
| `entity_type` | `document` / `image` / `audio` / `video` | Entity 类型 |
| `name` | `pricing.pdf` | 原始文件名 |
| `content_hash` | `sha256_xxx` | raw 内容的 SHA-256 |
| `version` | `1` | Entity 版本号 |
| `labels` | `pricing,finance,Q3` | 业务标签（逗号分隔） |
| `category` | `strategy` | 分类 |
| `project` | `Q3-review` | 项目归属 |
| `model_version` | `embedding-v5-retrieval` | 最新 embedding 模型版本 |
| `staging_status` | `pending` / `merged` / `stale` | staging 汇聚状态 |

**示例**：

```text
oss://bucket/vector-lake/ws_001/kb_001/abc123/original
  x-oss-tagging:
    rag_status=enabled
    entity_type=document
    name=pricing.pdf
    content_hash=sha256_abc...
    version=1
    labels=pricing,finance,Q3
    category=strategy
    project=Q3-review
    model_version=embedding-v5-retrieval
    staging_status=merged
```

**VFS + OSS Tag 协作**：

```text
VFS 扫描 vector-lake/{ws}/{col}/ prefix
  ├─ ListObjectsV2（带 Tagging 过滤）
  │   └─ 只返回 rag_status=enabled 的对象
  ├─ 对每个 enabled 对象 GetObjectTagging
  │   └─ 获取 entity_type / labels / category / ...
  └─ 内存中构建完整目录树 + 实体视图
```

**OSS Tag 的优势**：
- 零存储成本（metadata 存在 OSS 服务端）
- 支持按标签过滤列表（`ListObjectsV2` + `Tagging` 参数）
- 修改不需要重写对象（原子操作）
- 隐藏/删除/恢复都是单一 API 调用：

```bash
# 隐藏
ossutil put-object-tagging --bucket ... --key ... --tagging '{"Tags":[{"Key":"rag_status","Value":"hidden"}]}'

# 恢复
ossutil put-object-tagging --bucket ... --key ... --tagging '{"Tags":[{"Key":"rag_status","Value":"enabled"}]}'

# 删除（软删除，文件保留）
ossutil put-object-tagging --bucket ... --key ... --tagging '{"Tags":[{"Key":"rag_status","Value":"deleted"}]}'
```

**OSS Tag 的限制**：
- 最多 10 个 tag → 我们用 10 个，刚好
- 只能打在具体对象上 → 打在 `original` 上代表整个 Entity
- 列表过滤只能精确匹配 → 业务标签过滤在 VFS 内存中做

#### `representations.lance`（Entity 目录内，核心检索表）

每行 = 一个可检索单元。一个 `canonical_md` representation 切成 50 行，每行有自己的 text + vector。`chunk_index` 区分同一 representation 的不同切分段。

```text
representation_id    string              # 全局唯一
rep_type             string              # canonical_md / ocr_text / page_image / ...
pipeline_id          string
chunk_index          int                 # 同一 representation 的切分序号（0, 1, 2, ...）
text                 string              # 原文（建 FTS 索引）
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
vector               fixed_size_list<float>  # Lance 原生 vector 列
status               string              # active / hidden / deleted / stale
entity_version       int
created_at           timestamp
```

> **Lance 索引**：`vector` 列建 IVF_PQ 或 HNSW；`text` 列建 FTS 索引；`modality` / `rep_type` / `status` 建 scalar 索引。

#### Lineage 实时推算

血缘不持久化，**每次从 OSS 实时推算**：

```text
推算方法：

1. 扫描 Entity 目录内的 representation 文件
   ├─ canonical.md, ocr.md, page_image/, vlm_extracted.md, mind_map.json, ...
   └─ 推断每个文件的 rep_type

2. 扫描 staging/representations_v{N}.parquet
   ├─ 读取每行的 source_rep_type 字段（标记来自哪个上游 rep）
   └─ 推算派生关系

3. 应用命名规则 + 已知 pipeline 拓扑
   ├─ page_image → ocr_text（OCR pipeline）
   ├─ page_image → vlm_extracted_md（VLM pipeline）
   ├─ canonical_md → mind_map / summary / graph_json（LLM 编译 pipeline）
   └─ raw → canonical_md / page_image（解析 pipeline）

4. 内存中构建血缘 DAG
   ├─ 遍历上游/下游 → O(边数)
   ├─ 影响分析 → O(下游子树)
   └─ 级联失效 → 沿边标 stale
```

**示例 DAG**（从文件扫描推算）：

```text
raw (original)
  ├─► canonical_md           (pipeline_a: parse)
  ├─► page_image             (pipeline_b: render)
  │     ├─► ocr_text         (pipeline_b: ocr)
  │     └─► vlm_extracted_md (pipeline_c: vlm)
  └─► canonical_md → mind_map (pipeline_d: llm_compile)
                  → summary
                  → graph_json
```

**为什么实时推算而非持久化**：
- 一个 Entity 的血缘边通常 5-10 条，内存推算比读 JSON 快。
- 推算逻辑是确定性的（基于文件命名 + pipeline 拓扑），不需要快照。
- 任何文件变动都立即反映在血缘图上，无同步问题。
- Pipeline 升级时改"已知 pipeline 拓扑"即可，无需数据迁移。

#### L1. 写入层：Pipeline 产出 Parquet

Pipeline 产出直接写入 Entity 目录下的 `staging/`：

`{entity_id}/staging/representations_v{N}.parquet`：

```text
representation_id · rep_type · pipeline_id · chunk_index
text · embedding_text · start_pos · token_count · chunk_chars
page_number · section_header · section_level · anchor · doc_title
modality · content_hash · model_version
vector (list<float>) · status · entity_version · created_at
```

**写入层特点**：
- **追加写**：pipeline 产出直接 append，无需建索引。
- **天然隔离**：不同 Entity 写不同目录，无并发冲突。
- **立即可查**：staging 中的 Parquet 可被直接扫描（用于调试 / 预览），但无索引优化。
- **版本化**：每次 pipeline 重跑产出新的 `representations_v{N}.parquet`。

#### L2. 汇聚层：迭代式 Prefix Merge

汇聚层定期扫描每个 Entity 目录下的 `staging/`，将 Parquet 转为 Lance：

```text
汇聚流程：

1. 扫描所有 Entity 目录（VFS prefix 扫描）
   ├─ 列出 vector-lake/{ws}/{col}/ 下的所有 {entity_id}/
   └─ GetObjectTagging 读取 staging_status
      └─ 找出 staging_status=pending 的 Entity
   │
   ▼
2. 对每个 pending Entity，扫描其 staging/ 目录
   ├─ 发现新 Parquet 文件
   └─ 转换为 Lance 格式
   │
   ▼
3. 写入 Entity 目录下的 representations.lance
   ├─ 建索引（vector / FTS / scalar）
   └─ 原子切换（Lance MVCC）
   │
   ▼
4. 更新 OSS Tag（staging_status=merged）
   │
   ▼
5. 清理 staging（已汇聚的 Parquet 可归档/删除）
```

**汇聚策略**：

| 策略 | 触发条件 | 说明 |
| --- | --- | --- |
| **增量汇聚** | 新 Parquet 文件出现 | 只合并新增文件，不重写已有 Lance |
| **全量重写** | Parquet 文件数 > 阈值 或 碎片率过高 | 重写整个 Lance 数据集，优化存储布局 |
| **版本切换** | Entity 有新 version | 替换旧 version 的行，保留 lineage |

#### OSS → Lance 同步协议

**核心挑战**：OSS 是 append-only 不可变存储，Lance 是支持 MVCC 的可更新存储。需要在两者之间建立确定性的同步协议，保证：

1. **幂等性**：重复同步不产生重复数据
2. **原子性**：sync 中断不留下半成品
3. **可恢复性**：sync 失败后能从断点继续
4. **实时性**：OSS 变更后 Lance 尽快更新

##### 同步触发源

```text
┌─────────────────────────────────────────────────────────────┐
│  触发源                                                      │
├─────────────────────────────────────────────────────────────┤
│  1. OSS 事件驱动（主路径）                                    │
│     ├─ ObjectCreated（原文件上传）→ 创建 Entity + 触发 pipeline │
│     ├─ ObjectModified（staging Parquet 新增）→ 触发汇聚        │
│     ├─ ObjectRemoved（原文件删除）→ cascade_invalidate        │
│     └─ OSS Tag 变更（rag_status 切换）→ VFS 重扫 + 索引过滤   │
├─────────────────────────────────────────────────────────────┤
│  2. 周期 reconcile（兜底）                                    │
│     ├─ 每 15 min 全量扫描 prefix                              │
│     ├─ 比对 staging_status tag                               │
│     └─ 触发漏掉的事件处理                                     │
├─────────────────────────────────────────────────────────────┤
│  3. 手动触发（运维）                                          │
│     └─ POST /entities/{id}/sync 强制同步                    │
└─────────────────────────────────────────────────────────────┘
```

##### 同步状态机

每个 Entity 维护一个 `sync_state`（存在 OSS Tag 上）：

```text
sync_state = idle | syncing | ready | failed | stale
```

```text
                 ┌──────┐
                 │ idle │  ← 初始状态
                 └──┬───┘
                    │ OSS 事件触发
                    ▼
                 ┌────────┐
                 │syncing │  ← 正在同步
                 └──┬─────┘
              ┌─────┼─────┐
              ▼     ▼     ▼
         ┌─────┐ ┌─────┐ ┌───────┐
         │ready│ │stale│ │failed │
         └─────┘ └─────┘ └───┬───┘
              │        │     │
              └────────┘     │ retry
                   │         │
                   ▼         ▼
                ┌────────┐
                │syncing │
                └────────┘
```

**OSS Tag 扩展**（新增 sync_state）：

| Key | 取值 | 说明 |
| --- | --- | --- |
| `sync_state` | `idle` / `syncing` / `ready` / `failed` / `stale` | 同步状态 |
| `sync_started_at` | `2026-06-05T10:00:00Z` | 同步开始时间 |
| `sync_version` | `42` | Lance MVCC version 号 |
| `sync_error` | `oom` | 失败原因（failed 时） |

##### 同步协议细节

**Stage 1：Detect（变更检测）**

```python
def detect_changes(entity_id: str) -> ChangeSet:
    """检测 Entity 目录的变更，决定是否需要同步。"""

    oss_files = list_oss_files(entity_id)          # 实时扫
    lance_files = list_lance_files(entity_id)      # 扫 Lance 目录
    tag = get_object_tagging(entity_id)            # 读 OSS Tag

    # 1. 找出新增的 staging Parquet
    new_parquet = oss_files.staging_parquet - lance_files.source_parquet

    # 2. 找出被删除的 staging Parquet
    deleted_parquet = lance_files.source_parquet - oss_files.staging_parquet

    # 3. 找出 content_hash 变化的 raw（导致级联失效）
    if oss_files.raw_hash != tag.content_hash:
        # content_hash 变了 → 整个 Entity 需要重新跑
        return ChangeSet(action="full_rebuild", reason="content_hash_changed")

    # 4. 找出需要删除的 representation（被软删或物理删）
    deleted_reps = lance_files.reps - oss_files.reps - oss_files.staging_reps

    return ChangeSet(
        upsert=new_parquet,
        delete=deleted_parquet | deleted_reps,
        action="incremental" if new_parquet or deleted_parquet else "noop"
    )
```

**Stage 2：Lock（防止并发同步）**

```python
def acquire_sync_lock(entity_id: str) -> bool:
    """原子获取同步锁，防止同一 Entity 并发同步。"""

    # 用 OSS Tag 上的 sync_state 做分布式锁
    tag = get_object_tagging(entity_id)
    if tag.sync_state == "syncing":
        # 已有同步在进行，检查是否超时
        if is_sync_timeout(tag.sync_started_at, timeout=300):
            log.warning("Sync timeout, force unlock")
        else:
            return False  # 拒绝

    # CAS 更新 sync_state
    put_object_tagging(entity_id, {
        "sync_state": "syncing",
        "sync_started_at": now()
    })
    return True
```

**Stage 3：Transform（Parquet → Lance）**

```python
def transform_to_lance(entity_id: str, parquet_files: list[str]):
    """把 staging Parquet 转为 Lance 格式。"""

    # 1. 读取所有待汇聚的 Parquet
    dfs = [read_parquet(f) for f in parquet_files]

    # 2. Schema 对齐 + 类型转换（list<float> → fixed_size_list<float>）
    combined = align_schema(concat(dfs))

    # 3. 去重（按 representation_id + chunk_index）
    combined = dedupe(combined, keys=["representation_id", "chunk_index"])

    # 4. 写入 Lance（追加，不覆盖）
    lance_path = f"oss://.../{entity_id}/representations.lance/"
    lance.append(lance_path, combined, mode="append")
```

**Stage 4：Index（建索引）**

```python
def build_indexes(entity_id: str):
    """Lance 写入后建/更新索引。"""

    lance_path = f"oss://.../{entity_id}/representations.lance/"

    # 1. 检查现有索引
    existing = lance.list_indices(lance_path)

    # 2. vector 索引（IVF_PQ 或 HNSW）
    if "vector" not in existing:
        lance.create_index(
            lance_path, column="vector",
            index_type="IVF_PQ", num_partitions=256, num_sub_vectors=64
        )

    # 3. FTS 索引（text 列）
    if "text_fts" not in existing:
        lance.create_fts_index(lance_path, column="text")

    # 4. Scalar 索引（status / rep_type / modality 过滤列）
    for col in ["status", "rep_type", "modality"]:
        if col not in existing:
            lance.create_scalar_index(lance_path, column=col)
```

**Stage 5：Compact（碎片整理）**

```python
def maybe_compact(entity_id: str):
    """碎片率过高时全量重写。"""

    lance_path = f"oss://.../{entity_id}/representations.lance/"
    stats = lance.get_stats(lance_path)

    fragment_count = stats.num_fragments
    row_count = stats.num_rows

    # 阈值：平均每个 fragment 少于 1000 行就重写
    if row_count / fragment_count < 1000:
        log.info(f"Compacting {entity_id}: {fragment_count} fragments")
        lance.compact(lance_path)  # 合并 fragment，物理重写
```

**Stage 6：Atomic Switch（原子切换）**

```python
def atomic_publish(entity_id: str, new_version: int):
    """Lance 原生 MVCC，原子切换版本。"""

    # Lance 的 version 机制：每次 commit 产生新 version，旧 version 仍可读
    lance_path = f"oss://.../{entity_id}/representations.lance/"

    # 1. commit 新 version（自动）
    new_lance_version = lance.commit(lance_path)

    # 2. 更新 OSS Tag（指向新 version）
    put_object_tagging(entity_id, {
        "sync_state": "ready",
        "sync_version": new_lance_version,
        "staging_status": "merged",
        "last_sync_at": now()
    })

    # 3. 旧 Lance version 保留 N 小时后清理（保留回滚窗口）
    schedule_cleanup(lance_path, keep_versions=5)
```

**Stage 7：Cleanup（清理）**

```python
def cleanup_staging(entity_id: str):
    """已汇聚的 staging Parquet 可归档或删除。"""

    # 选项 A：归档到 cold storage（OSS 生命周期规则）
    # 选项 B：直接删除（如果 Lance 是唯一真相源）
    # 选项 C：保留最近 1 个版本（debug 用）

    staging_files = list_oss_files(entity_id).staging
    for f in staging_files:
        if f.version < current_version - 1:
            delete_object(f.oss_path)  # 删除旧版本
```

##### 失败处理

| 失败点 | 检测 | 恢复策略 |
| --- | --- | --- |
| **网络中断（Stage 3-4）** | sync timeout | OSS Tag 标 `failed`；下次 reconcile 重新检测 |
| **Lance 写入失败** | Lance 抛异常 | 回滚 OSS Tag 到 `failed`；不更新 `sync_version` |
| **OSS Tag 写入失败（Stage 6）** | API 抛异常 | Lance 已更新但 tag 未更新 → 标记 `sync_state=stale`；reconcile 时对比 Lance version 和 OSS Tag version 修复 |
| **实体被删除（中间态）** | 扫不到 original | 触发 Entity 软删除流程；清理 Lance |

**幂等性保证**：

```python
# 同一变更多次同步，结果一致
sync(entity_id, change_set)  # 第 1 次
sync(entity_id, change_set)  # 第 2 次，幂等

# 实现：每个 Lance row 用 (representation_id, chunk_index) 做主键
# 重复 append 会触发 dedupe
```

**断点续传**：

```python
# sync 失败后，下次 sync 从断点继续
def resume_sync(entity_id: str):
    tag = get_object_tagging(entity_id)
    if tag.sync_state == "failed":
        # 找出失败的 stage
        failed_stage = tag.sync_error  # e.g. "stage_4_index"
        # 从 failed_stage 重新开始
        sync_from_stage(entity_id, failed_stage)
```

##### 监控指标

| 指标 | 说明 |
| --- | --- |
| `sync_duration_seconds{stage}` | 每个 stage 的耗时 |
| `sync_total_duration_seconds` | 完整 sync 耗时 |
| `sync_failures_total{stage, reason}` | 同步失败次数（按 stage + reason 分组） |
| `sync_state_count{state}` | 各状态的 Entity 数（idle/syncing/ready/failed/stale） |
| `lance_fragment_count{entity_id}` | Lance fragment 数（碎片率监控） |
| `lance_lag_seconds{entity_id}` | OSS 变更到 Lance 同步的延迟 |

##### 一致性保证总结

| 场景 | 一致性级别 | 保证方式 |
| --- | --- | --- |
| **强一致** | 同一 Entity 内的 representation ↔ Lance | sync 协议 + 锁 + 原子切换 |
| **最终一致** | OSS 事件 → Lance | 事件驱动 + reconcile 兜底（最大延迟 15 min） |
| **可恢复** | 任意 sync 中断 | OSS Tag 持久化进度 + 断点续传 |
| **可回滚** | Lance 索引异常 | 保留最近 5 个 Lance version（MVCC） |

#### L3. 查询层

**单 Entity 查询**：直接打开 `{entity_id}/representations.lance`，hybrid search。

**跨 Entity 查询**：

```text
用户查询 "Q3 定价策略"
   │
   ▼
[1] VFS 扫描 + OSS Tag 过滤
   ├─ ListObjectsV2（prefix=vector-lake/{ws}/{col}/, tag rag_status=enabled）
   └─ 对每个 enabled 对象 GetObjectTagging
      └─ 可选：按 entity_type / labels / category 预筛选
   │
   ▼
[2] Fan-out 检索
   ├─ 对每个候选 Entity 的 representations.lance 并行执行 hybrid search
   └─ 每个文件返回 top-k
   │
   ▼
[3] 全局 Merge
   ├─ 合并所有文件的 top-k 结果
   ├─ RRF / CrossEncoder 重排
   └─ 返回全局 top-k
```

> **优化**：v0.1 简单 fan-out；v0.2 可引入全局 ANN 索引做粗排，减少 fan-out 数量。

#### 数据流全链路

```text
Pipeline 产出
   │
   ▼
[L1] 写入 {entity_id}/staging/representations_v{N}.parquet
   │
   ▼
[L2] 汇聚层扫描 Entity 目录的 staging/
   ├─ 转换为 Lance 格式
   ├─ 写入 {entity_id}/representations.lance
   ├─ 建索引 (vector / FTS / scalar)
   └─ 更新 OSS Tag (staging_status = merged)
   │
   ▼
[L3] 查询层
   ├─ 单 Entity → 直接读 representations.lance
   └─ 跨 Entity → VFS 扫描 + OSS Tag 路由 + fan-out + merge
```

#### Lineage 级联在三层中的体现

```text
raw 更新 (content_hash 变化)
   │
   ▼
[L1] Pipeline 重跑 → 新 representations_v{N+1}.parquet 写入 staging
     旧 representation 行标 stale（在 Parquet 内标记）
   │
   ▼
[L2] 汇聚层检测到新 Parquet
     → 增量合并到 representations.lance
     → 旧 version 行标 stale（检索不再命中）
     → 新 version 行标 active
   │
   ▼
[L3] 查询层读新 representations.lance
     → stale 行不参与检索
     → active 行可被检索
```

#### Lineage 查询能力

| 查询 | 说明 |
| --- | --- |
| `GET /lineage/{entity_id}?direction=upstream&rep_type=ocr_text` | 从 ocr_text 向上追溯到 raw（辅助能力） |
| `GET /lineage/{entity_id}?direction=downstream&rep_type=page_image` | 从 page_image 向下找出所有下游（级联失效目标） |
| `GET /lineage/{entity_id}/impact?rep_type=page_image` | 影响分析：如果 page_image 变了，哪些下游需要 stale + 重建 |
| `POST /lineage/{entity_id}/cascade` | 手动触发级联：将指定 rep 的所有下游标 stale 并触发重建 |

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
   └─ 每个节点记录：path / type(file|dir) / size / last_modified / entity_id / rep_type / rag_status
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
| `stat` | 读目录树缓存 + OSS Tag | 返回文件/目录元数据（size / last_modified / entity_id / status） |
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
[4] 附加 metadata
   ├─ 从 VFS 路径反查 entity_id / rep_type / entity_version
   ├─ 从 OSS Tag 补充 entity 元数据（name / entity_type / rag_status / labels）
   └─ 从 representations 补充 representation 元数据（pipeline_id / derived_from / quality）
   │
   ▼
[5] 返回结果（带 metadata 的 evidence）
```

**grep 返回格式**（与其他 tool 的 evidence 包装对齐）：

```json
{
  "tool": "grep",
  "results": [
    {
      "file_path": "/pricing.pdf/canonical.md",
      "line_number": 42,
      "line_text": "Q3 定价策略：Enterprise $4.2B, Consumer $1.8B",
      "context_before": ["line 40...", "line 41..."],
      "context_after": ["line 43...", "line 44..."],
      "metadata": {
        "entity_id": "abc123",
        "entity_type": "document",
        "entity_version": 1,
        "name": "pricing.pdf",
        "rep_type": "canonical_md",
        "representation_id": "rep_xxx",
        "pipeline_id": "pipeline_a",
        "derived_from": "raw",
        "derived_chain": ["raw", "canonical_md"],
        "page_number": 7,
        "section_header": "Q3 Pricing",
        "mime_type": "text/markdown",
        "status": "active",
        "source_uri": "oss://bucket/raw/pricing.pdf",
        "content_hash": "sha256_xxx",
        "quality": { "confidence": 0.96, "source": "parser" }
      }
    }
  ]
}
```

**metadata 来源映射**：

| metadata 字段 | 来源 | 说明 |
| --- | --- | --- |
| `entity_id` | VFS 路径反查 | 从虚拟路径 → entity_id |
| `entity_type` / `name` / `rag_status` / `labels` | OSS Tag | entity 元数据 |
| `rep_type` / `representation_id` | VFS 路径反查 | 从虚拟路径 → representation |
| `pipeline_id` / `derived_from` / `derived_chain` / `quality` | representations.parquet | representation 元数据 |
| `page_number` / `section_header` | 行号 → chunk 定位 | 从 start_pos 反查最近的 chunk |
| `content_hash` | OSS Tag | 原始文件信息 |
| `mime_type` | VFS 目录树缓存 | 文件类型 |

**优化**：
- 先用 `glob` 缩小范围，避免扫描所有文件。
- 对已缓存在本地的 representation（如 staging 中的 Parquet），直接本地 grep。
- 大文件分块流式读取，不全部加载到内存。
- metadata 附加在命中后批量查询 OSS Tag API。

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
| `stat` | VFS | 目录树缓存 + OSS Tag | entity_id / path | 元数据 + 状态 |
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
