# Vector-Lake 智能知识搜索引擎层 — PRD

> **版本**：v0.2 修订版
> **状态**：待评审
> **目标读者**：产品 / 架构 / 工程 / 算法
> **核心定位**：把 OSS 数据湖升级为可被智能引擎直接调用的"知识搜索引擎层"。
> **修订说明**：基于 v0.1 review + 架构讨论 + 开源项目对标，核心变更：(1) 1 OSS Object = 1 Entity；(2) Representation 是"认知视角"而非中间产物；(3) Pipeline 是一等公民，同一 Entity 可走多条并行流水线；(4) Chunk 是索引方法，不是存储概念；(5) 1 张 Lance 表 = representations.lance（内嵌 vector），PK = `(entity_id, rep_type, chunk_index)`；(6) 零持久化元数据，全部从两套 OSS Tag（Entity Tag 10个 + Representation Tag 7个）+ VFS 扫描实时获取；(7) 血缘不存于任何字段或 Tag，从**目录层级 + Pipeline 注册表**实时推导（目录层级即血缘深度：source/ → extract/ → recognize/ → compile/，_index/ 为系统目录）；(8) 表格型 Entity（entity_type=table）通过 DuckDB + compile/table.parquet 提供 SQL 统一查询，DuckDB 进程内嵌入、OSS 原生读取；(9) 三类一等检索能力（semantic / structural / textual）通过 §9 智能引擎统一路由与证据融合，DuckDB 作为 structural 的对等能力，与 Lance 协同工作；(10) Pipeline 间强依赖（拓扑排序）+ 混合型 Entity 启发式发现 + entity_type 6 级判定链；(11) **新增 Projector 层（§11）**：把 Lake 内部数据单向投影到多种外部消费者（RAG API / Wiki / Dashboard / Web），Lake 主体地位不动摇；(12) **新增 Wiki Projector 详设（§12）**：把 Karpathy LLM Wiki 视为 Lake 内部 Projector 的一种目标格式，Lake 主动把 Entity/Representation/Edge/Event 投影为 `~/wiki/` 目录的 .md + wikilink + index.md + log.md，wiki 独立可运行。

---

## 0. 一句话定义

> **Entity 是知识对象，Representation 是它的不同认知视角，Chunk 是某个视角下的检索粒度，Embedding 是 Chunk 的向量索引。同一问题可以从多个视角命中同一 Entity，融合后给出最完整的证据。**

---

## 1. 产品概述

### 1.1 背景

当前仓库已具备以下能力：

- **OSS Data Lake**：原始对象（pdf、docx、pptx、image、audio…）通过 `vector-lake/{workspace}/{collection}/{entity_id}/source/original` 落地，文件不可变。
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
| **Representation** | Entity 的"认知视角"（canonical_md / ocr_text / vlm_md / mind_map / graph_json / page_image / ...） | **派生产物**，血缘关系从目录层级推导 |
| **Pipeline** | 从 raw 或已有 representation 生成新 representation 的过程 | — | 一等公民，同一 Entity 可走多条并行流水线 |
| **Chunk** | 某个 Representation 下的检索最小单元 | **可重建** | 索引方法，检索命中的原子粒度 |
| **Embedding** | 某个 Chunk 的向量索引 | **可重建** | 内嵌于 `representations.lance` 的 vector 列 |
| **Index** | 某类检索能力（semantic/lexical/grep/visual/...） | 可演进 | 检索入口 |
| **Lineage** | Representation 之间的血缘关系（谁从谁派生） | **可追溯** | 一等公民，从**目录层级 + Pipeline 注册表**实时推导，支持级联失效 / 影响分析 |
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

**Lineage 元数据存储方式**：血缘关系**不存于任何字段或 OSS Tag**，完全从**目录层级**和**Pipeline 注册表**实时推导。目录层级天然编码血缘深度：`source/` → `extract/` → `recognize/` → `compile/`（见 §4.6）。

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

1. **上游变了 → 下游立即 stale**：沿 Pipeline 边向下遍历（从 Pipeline 注册表推导），所有下游 representation 文件的 OSS Tag `status` 更新为 `stale`，对应 chunks 标记 `stale`，检索不再命中。
2. **stale → 自动触发重建**：pipeline orchestrator 检测到 stale 状态，自动重跑对应 pipeline 生成新 representation + chunks。
3. **重建完成 → publish 切换**：新版本 ready 后，原子切换，检索恢复。
4. **重建期间 → 旧版本仍可查**：stale 的 chunks 在新版本 publish 前仍保留，但标记为 stale（可选：检索是否包含 stale 结果）。

> 追溯、可视化、影响分析都是 Lineage 的**辅助能力**，核心是"级联失效 + 自动重建"。

### 2.6 Pipeline 是一等公民

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
│      representations.lance (vector + FTS + scalar filter)     │
│      Hybrid Search (RRF / CrossEncoder rerank)               │
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
│      oss://vector-lake/{ws}/{col}/{entity_id}/source/original│
└──────────────────────────────────────────────────────────────┘
```

### 3.2 模块划分

| 模块 | 职责 | 关键产出 |
| --- | --- | --- |
| **Ingest Service** | 监听 OSS 新对象、登记 entity | OSS Tag + Entity 目录 |
| **Detect Worker** | mime / language / content_hash / size | detect 结果 |
| **Pipeline Orchestrator** | 根据 entity_type 选择 1..N 条 pipeline 并行调度 | pipeline_run 记录 |
| **Pipeline Worker** | 执行单条 pipeline，产出 representation + chunks | representation + chunks |
| **Embedder** | 调用 Embedding V5 多模态服务 | chunks 表的 vector 列 |
| **Lance Watcher** | 监听 staging Parquet 变动，实时增量同步到 Lance；支持全量 rebuild | 同步后的 Lance 数据集 |
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
         增量更新 VFS 树        从路径+Pipeline注册表推导血缘 DAG
                │                       │
                ▼                       ▼
         VFS 目录树            沿 Pipeline input_rep 边级联标 stale
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
| `ObjectCreated` | 新文件上传 | 增量添加节点 | 从路径推导血缘（无新增） | 触发对应 pipeline |
| `ObjectModified` | 文件覆盖（raw 更新） | 更新节点属性 | 沿 Pipeline 边级联下游 OSS Tag status→stale → 重建 | 触发重建 |
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

**Entity 属性视图（从 OSS Tag + 路径实时组装，非持久化文件）**：

```json
{
  "entity_id": "abc123",              // ← 从 OSS 目录名解析
  "entity_type": "document",          // ← OSS Tag: entity_type
  "workspace_id": "ws_001",           // ← 从 OSS 路径前缀解析
  "collection_id": "kb_001",          // ← 从 OSS 路径前缀解析
  "name": "pricing.pdf",              // ← OSS Tag: name
  "source_uri": "oss://bucket/.../abc123/source/original",  // ← 从 OSS 路径组装
  "content_hash": "sha256_xxx",       // ← OSS Tag: content_hash
  "version": 1,                       // ← OSS Tag: version
  "status": "enabled",                // ← OSS Tag: rag_status
  "labels": ["pricing", "finance"],   // ← OSS Tag: labels（逗号分隔解析）
  "created_at": "...",                // ← OSS 对象的 LastModified
  "updated_at": "..."                 // ← OSS Tag 变更时间
}
```

> **注意**：不存在 entity.json 文件。所有属性从 OSS Tag + 路径实时读取。

**entity_type 取值（v0.1）**：

```text
document · image · audio · video
```

> `document` 包含 pdf/docx/pptx/html/md 等；`image` 包含 png/jpg/svg 等；`audio` 包含 wav/mp3 等；`video` 包含 mp4 等。具体 subtype 由 detect 阶段的 mime_type 决定。

**entity_id 生成规则**：

- `entity_id = UUIDv7`（时间排序，可读性好，避免 hash 碰撞）。
- 目录名即 entity_id，VFS 扫描时直接从目录名解析。
- 同一 raw object 重复上传时，content_hash 检测到相同则复用已有 entity_id。

#### Entity 作为类：方法抽象

**Entity 是一个对象**，所有操作以 Entity 为入口组织。方法和属性在 OSS 上实时反映（无持久化元数据）。

```python
class Entity:
    """一个知识对象 = 一个 OSS 目录 + 一个 OSS Tag。"""

    # ===== 标识属性（从 OSS Tag 实时读取）=====
    entity_id: str                # 目录名 = entity_id
    workspace_id: str             # 从路径前缀解析
    collection_id: str            # 从路径前缀解析
    entity_type: str              # document / image / audio / video / table（OSS Tag）
    name: str                     # pricing.pdf（OSS Tag）
    content_hash: str             # raw SHA-256（OSS Tag）
    version: int                  # 单调递增（OSS Tag）
    status: str                   # enabled / hidden / deleted（OSS Tag）
    labels: list[str]             # 业务标签（OSS Tag，合并 category/project）
    oss_path: str                 # oss://bucket/vector-lake/{ws}/{col}/{entity_id}/source/original
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

    def rebuild_lance(self) -> None:
        """全量重建 Lance 数据集（从 OSS representation 文件 + staging Parquet）。
        适用场景：schema 变更 / Lance 损坏 / 碎片率过高 / 索引失效。
        支持 MVCC 回滚：重建失败自动回退到旧 version。"""

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
        """更新任意 OSS Tag（labels / ...）。"""

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

    # ===== 表格查询（基于 DuckDB + Parquet）=====
    def to_parquet(self) -> str:
        """将表格型 Entity 转为 Parquet 格式。
        触发 Pipeline G（表格获取），产出 compile/table.parquet。
        返回 OSS 路径。"""

    def query_table(self, sql: str) -> list[dict]:
        """通过 DuckDB 对该 Entity 的 table.parquet 执行 SQL 查询。
        支持 SELECT / WHERE / GROUP BY / JOIN / 窗口函数。
        返回 list of dicts。"""

    def get_table_schema(self) -> dict:
        """获取 table.parquet 的 schema（列名 + 类型 + 行数统计）。
        通过 DuckDB 的 DESCRIBE + COUNT(*) 实现。"""

    def get_table_stats(self) -> dict:
        """获取 table.parquet 的统计信息（行数、列数、文件大小、空值率等）。
        通过 DuckDB 的 SUMMARIZE 实现。"""

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
| **生成索引** | `build_index*` / `rebuild_index*` / `rebuild_lance` | Lance 索引 / Lance 数据集 |
| **查询清单** | `list_*` / `get_*` | 表现 / 流水线 / 索引 / chunk |
| **血缘** | `get_lineage*` / `cascade_invalidate` | 血缘 DAG |
| **状态** | `hide` / `show` / `delete` / `restore` / `update_tags` | OSS Tag |
| **检索** | `search` / `grep` | representations.lance + OSS |
| **表格查询** | `to_parquet` / `query_table` / `get_table_schema` / `get_table_stats` | DuckDB + compile/table.parquet |
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

**核心洞察**：**OSS 路径就是 Representation 的唯一身份标识（Primary Key）**。不需要 `representation_id`、`derived_from`、`derived_chain` 等字段——这些信息都可以从路径 + OSS Tag 实时推导出来。

```json
{
  "oss_path": "oss://bucket/vector-lake/{ws}/{col}/{entity_id}/recognize/vlm_extracted.md",
  "entity_id": "abc123",                           // ← 从路径前缀解析
  "entity_version": 1,                             // ← OSS Tag: entity_version
  "rep_type": "vlm_extracted_md",                  // ← OSS Tag: rep_type（从路径后缀也可推导）
  "mime_type": "text/markdown",                    // ← 从文件后缀推导
  "pipeline_id": "pipeline_c",                     // ← OSS Tag: pipeline_id
  "transform": "vlm",                              // ← OSS Tag: transform
  "modality": "text",                              // ← OSS Tag: modality
  "status": "ready",                               // ← OSS Tag: status
  "model_version": "qwen2vl_v3",                   // ← OSS Tag: model_version
  "created_at": "...",                             // ← OSS 对象的 LastModified
  "updated_at": "..."                              // ← OSS Tag 变更时间
}
```

**关键设计**：
- **路径即身份**：`oss_path` 是 Representation 的全局唯一 PK。两个不同路径 = 两个不同 Representation。
- **`rep_type` 是路径后缀的语义化**：从 `canonical.md` / `ocr.md` / `vlm_extracted.md` 等路径即可识别类型，OSS Tag 冗余存储加速过滤。
- **没有 `derived_from` 字段**：血缘关系不存于任何字段，从**路径前缀**和**命名约定**实时推导（见 §4.6 Lineage 实时推导）。
- **没有 `derived_chain` 字段**：完整溯源链通过路径前缀树 + 命名约定的递归查询实时组装。

**路径结构（Representation 身份的根基）**：

```text
vector-lake/{ws}/{col}/{entity_id}/{stage}/{rep_basename}

# 四层目录 = 四级血缘深度
{entity_id}/
├── source/                          ← L0: 原始文件（不可变，血缘根节点）
│   └── original                     ← rep_type: raw
│
├── extract/                         ← L1: 直接提取（source → extract）
│   ├── canonical.md                 ← rep_type: canonical_md
│   ├── plain_text.txt               ← rep_type: plain_text
│   ├── layout.json                  ← rep_type: layout_json
│   └── page_image/                  ← rep_type: page_image（多文件型）
│       ├── page_001.png
│       ├── page_002.png
│       └── ...
│
├── recognize/                       ← L2: 识别/转写（extract → recognize）
│   ├── ocr.md                       ← rep_type: ocr_text
│   ├── vlm_extracted.md             ← rep_type: vlm_extracted_md
│   ├── caption.md                   ← rep_type: caption
│   ├── transcript.md                ← rep_type: transcript
│   └── audio_segment/               ← rep_type: audio_segment（多文件型）
│       ├── seg_001.wav
│       └── seg_002.wav
│
├── compile/                         ← L3: 知识编译（extract/recognize → compile）
│   ├── mind_map.json                ← rep_type: mind_map
│   ├── graph.json                   ← rep_type: graph_json
│   ├── summary.md                   ← rep_type: summary
│   ├── wiki.md                      ← rep_type: wiki_md
│   ├── table.md                     ← rep_type: table_md
│   └── table.json                   ← rep_type: table_json
│
└── _index/                          ← 系统目录（索引 + 暂存，下划线前缀）
    ├── staging/                     ← L1 写入层（Pipeline 产出）
    │   └── representations_v{N}.parquet
    └── representations.lance/       ← L3 查询层（汇聚后）
        ├── data/
        └── _indices/
```

**目录层级即血缘深度**：

| 目录层级 | 血缘深度 | 含义 | Pipeline 示例 |
| --- | --- | --- | --- |
| `source/` | L0 | 原始文件，血缘根节点 | — |
| `extract/` | L1 | 从 source 直接提取 | Pipeline A: raw → canonical_md / page_image |
| `recognize/` | L2 | 从 extract 识别/转写 | Pipeline B/C: page_image → ocr_text / vlm_md |
| `compile/` | L3 | 从 extract/recognize 编译 | Pipeline D: canonical_md → mind_map / summary |
| `_index/` | 系统 | 索引 + 暂存，非内容 | Lance Watcher 管理 |

**核心优势**：
- **路径即血缘**：`recognize/ocr.md` 的上游一定是 `extract/` 或 `source/` 下的文件，无需查 Pipeline 注册表即可推断。
- **层级隔离**：`_index/` 下划线前缀 = 系统目录，VFS 内容扫描自动跳过。
- **可扩展**：未来新增 `translate/`（L4 翻译）、`reasoning/`（L5 推理）等层级，不破坏已有结构。
- **可扫描**：按层级 prefix 扫描，比全目录扫描更高效。

**多文件 Representation**（如 `page_image/`, `audio_segment/`）的特殊处理：

- 整个 `extract/page_image/` 目录视为**一个逻辑 Representation**（rep_type=page_image）。
- 目录内每个文件是该 rep 的一个分片。
- OSS Tag 打在目录内的**每个文件**上（同一 rep 的所有文件共享相同 Tag）。

**Representation 元数据存储方式**：

每个 representation 文件通过 **OSS Object Tagging** 携带业务元数据，**不再存血缘元数据**（血缘从目录层级推导）：

| Tag Key | 示例值 | 说明 |
| --- | --- | --- |
| `rep_type` | `vlm_extracted_md` | 认知视角类型（与路径后缀冗余，用于过滤） |
| `pipeline_id` | `pipeline_c` | 产出该 rep 的流水线 |
| `transform` | `vlm` | 具体变换方法 |
| `modality` | `text` | 模态 |
| `status` | `ready` | representation 状态 |
| `model_version` | `qwen2vl_v3` | 产出该 rep 的模型版本 |
| `entity_version` | `3` | 所属 Entity 版本 |

> 共 7 个 Tag，在 OSS 10 个 Tag 限制内，预留 3 个空位用于 evolution。
> 与之前 8 个 Tag 方案相比，去掉了 `derived_from`（从目录层级推导）。
> 若未来需要复杂元数据（超过 10 个 Tag 或嵌套 JSON），可在同目录放 `.meta.json` sidecar，并用 Tag `status=meta_extended` 标记"查看 sidecar 获取完整元数据"。此为 v0.2+ 演进路径。

**Representation 身份三元组（用于跨系统引用）**：

```python
# 三元组 = (entity_id, rep_type, chunk_index) 唯一确定一个 Chunk
# rep_type 由 (stage, rep_basename) 唯一确定
# 完整路径 = f"{entity_id}/{stage}/{rep_basename}"
representation_id = f"{entity_id}/{rep_type}"  # 不需要额外 ID 字段

# 多文件 rep（如 page_image/）的内部文件用 chunk_index 区分
chunk_id = f"{entity_id}/{rep_type}/#{chunk_index}"  # 用于 Lance 表 PK
```

**标准 rep_type 与路径约定（v0.1 落地集合）**：

```text
rep_type              路径约定
──────────────────   ──────────────────────────────────────
raw                   source/original
canonical_md          extract/canonical.md
plain_text            extract/plain_text.txt
layout_json           extract/layout.json
page_image            extract/page_image/page_{NNN}.png
ocr_text              recognize/ocr.md
vlm_extracted_md      recognize/vlm_extracted.md
caption               recognize/caption.md
transcript            recognize/transcript.md
audio_segment         recognize/audio_segment/seg_{NNN}.wav
table_md              compile/table.md
table_json            compile/table.json
table_parquet         compile/table.parquet
mind_map              compile/mind_map.json
wiki_md               compile/wiki.md
graph_json            compile/graph.json
summary               compile/summary.md
```

> 新增 rep_type 只需：(1) 写文件到约定路径的对应层级目录；(2) 写 OSS Tag；(3) 命名约定注册到 VFS 路径解析器。**无需修改任何血缘字段或代码。**

### 4.3 Chunk（检索粒度，索引方法）

**核心设计**：Chunk 是"在某个 Representation 内部的某个切分段"，其身份由 `(entity_id, rep_type, chunk_index)` 三元组唯一确定。**没有独立的 `representation_id` 字段**——这是从 §4.2 的路径即身份原则延伸。

```json
{
  "entity_id": "abc123",
  "rep_type": "canonical_md",
  "chunk_index": 3,
  "text": "## Q3 Pricing\nEnterprise: $4.2B, Consumer: $1.8B...",
  "embedding_text": "Heading Levels：Q3 Pricing。Content：Enterprise: $4.2B...",
  "start_pos": 1200,
  "end_pos": 2224,
  "token_count": 256,
  "chunk_chars": 1024,
  "page_number": 7,
  "section_header": "Q3 Pricing",
  "section_level": 2,
  "anchor": "q3-pricing",
  "doc_title": "pricing.pdf",
  "modality": "text",
  "status": "active",
  "pipeline_id": "pipeline_a",
  "transform": "parse",
  "model_version": "parser_v3",
  "content_hash": "sha256_xxx",
  "entity_version": 1,
  "vector": [...],
  "created_at": "2026-06-05T10:00:00Z",
  "updated_at": "2026-06-05T10:00:00Z"
}
```

**Chunk 身份（PK）**：

```python
# PK = (entity_id, rep_type, chunk_index)
# 等价于 §4.2 的路径拼接：f"{entity_id}/{rep_type}/#{chunk_index}"
chunk_id = f"{entity_id}/{rep_type}/#{chunk_index}"
# 例子："abc123/canonical_md/#3"

# 引用一个 Chunk 时，给出三元组 + 路径即可
# 上层 RAG/Agent 调用：
#   "Get chunk abc123/canonical_md/#3"  → 通过路径直接定位到 OSS 文件
#   "Get chunks of vlm_extracted_md in abc123"  → chunk_index 是变量
```

**没有 `representation_id` 字段的原因**：

- `representation_id` 是个中间概念，从 `entity_id + rep_type` 即可推导。
- 直接用 `(entity_id, rep_type, chunk_index)` 三元组做 PK 更直观，与 OSS 路径对齐。
- 减少字段 = 减少数据冗余 + 减少同步问题。

**Chunk 字段与 OSS Tag 的关系**：

| Chunk 字段 | 来源 | 说明 |
| --- | --- | --- |
| `entity_id` | Lance manifest metadata + VFS 路径 | Entity 标识 |
| `rep_type` | **OSS Tag**（从文件也可用路径后缀推导） | 来源视角 |
| `chunk_index` | Pipeline chunk 阶段产出 | 切分序号 |
| `text` / `embedding_text` / `start_pos` 等 | Pipeline chunk 阶段产出 | 切分内容 |
| `pipeline_id` / `transform` / `model_version` | **OSS Tag** | 产出流水线信息（可冗余存于 chunk 用于过滤） |
| `modality` | **OSS Tag** | 模态（可冗余存于 chunk 用于过滤） |
| `status` | Pipeline 阶段写入 | active / stale / hidden / deleted |
| `entity_version` | **OSS Tag** | 所属 Entity 版本 |
| `vector` | Pipeline embed 阶段产出 | 向量 |
| `content_hash` | Pipeline chunk 阶段计算 | chunk 内容哈希 |

> 注：`pipeline_id` / `transform` / `model_version` / `modality` / `entity_version` 等字段在 chunk 行中**冗余**自 OSS Tag，存储目的是**让 chunk 行能独立做过滤**（避免每次都 join OSS Tag）。可通过 v0.2+ 的列裁剪或物化视图优化。

**modality 取值**：`text | image | audio | table`

**不同 Representation 的 Chunk 策略**：

| rep_type | Chunk 策略 | modality |
| --- | --- | --- |
| canonical_md / ocr_text / vlm_extracted_md | 按标题+段落切 text chunk（ChunkingWithSlidingWindowUseCase） | text |
| page_image | 每页一个 chunk，走 image embedding | image |
| transcript / transcript_segment | 按时间戳切 segment | text |
| audio_segment | 每个 segment 一个 chunk，走 audio embedding | audio |
| table_md / table_json | 每个表格一个 chunk | table |
| table_parquet | 不切 chunk（由 DuckDB 直接查询） | table |
| mind_map | 按节点切 chunk | text |
| graph_json | 按 (subject, predicate, object) 三元组切 chunk | text |

### 4.4 跨 Entity 关系（作为 graph_json representation）

跨 Entity 关系不独立建表，而是作为 `graph_json` representation 存储在 representations.lance 中。

```json
{
  "entity_id": "abc123",
  "rep_type": "graph_json",
  "edges": [
    { "dst_entity_id": "def456", "edge_type": "cites", "confidence": 0.95, "source": "llm_compiler" },
    { "dst_entity_id": "ghi789", "edge_type": "mentions", "confidence": 0.88, "source": "llm_compiler" }
  ]
}
```

**edge_type**：`cites · mentions · same_as · contradicts · supports · related_to`

> 注意：不再有 `contains` edge。因为 1 OSS Object = 1 Entity，不存在父子实体关系。
> 跨 Entity 关系由 Pipeline D（知识编译）产出，存储为 graph_json representation。

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

**Pipeline 定义的存储位置**：

- v0.1：代码内注册（Python dataclass / YAML config），随服务部署。
- v0.2：支持动态注册（Pipeline 定义存 OSS，运行时加载）。

### 4.6 存储模型：Entity 目录自包含 + Parquet 写入 → Lance 索引

**核心决策**：

1. **每个 Entity 一个目录**，所有 representation 文件 + Lance 数据都在这个目录下，自包含。
2. **写入用 Parquet**（快写、隔离），**查询用 Lance**（索引、hybrid search），中间通过迭代式汇聚衔接。
3. **1 张 Lance 表**：`representations.lance`（Entity 目录内）。血缘从**目录层级 + Pipeline 注册表**实时推导，元数据用两套 OSS Tag（Entity Tag + Representation Tag）。

```text
┌─────────────────────────────────────────────────────────────┐
│  L1  写入层（Parquet）                                       │
│      每 Entity 目录下写入 Parquet，小文件快写，天然隔离         │
│      pipeline 产出直接落盘，无需全局协调                       │
├─────────────────────────────────────────────────────────────┤
│  L2  汇聚层（Lance Watcher）                                   │
│      事件驱动 + 增量同步 + 全量 Rebuild                       │
│      每 Entity 目录内独立同步，无需跨 Entity 协调              │
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
3. **两套 OSS Object Tagging** — Entity Tag（10个，打在 original 上）+ Representation Tag（7个，打在每个 rep 文件上），作为唯一的业务元数据存储层。
4. **VFS 实时扫描 prefix** 重建目录树 + 从**目录层级 + Pipeline 注册表**推导血缘 DAG，所有元数据从 OSS 实时获取。
5. **1 张 Lance 表**：`representations.lance`（Entity 目录内）。每行 = 一个可检索单元（chunk），PK = `(entity_id, rep_type, chunk_index)`。

```text
vector-lake/{workspace_id}/{collection_id}/
│
├── {entity_id}/                                 ← Entity 目录（自包含）
│   ├── source/                                  ← L0: 原始文件
│   │   └── original                             ← raw 文件（带 Entity OSS Tag，10个）
│   ├── extract/                                 ← L1: 直接提取
│   │   ├── canonical.md                         ← rep 文件（带 Rep OSS Tag，7个）
│   │   └── page_image/
│   │       ├── page_001.png                     ← rep 文件（带 Rep OSS Tag）
│   │       └── page_007.png                     ← rep 文件（带 Rep OSS Tag）
│   ├── recognize/                               ← L2: 识别/转写
│   │   ├── ocr.md                               ← rep 文件（带 Rep OSS Tag）
│   │   └── vlm_extracted.md                     ← rep 文件（带 Rep OSS Tag）
│   ├── compile/                                 ← L3: 知识编译
│   │   ├── mind_map.json                        ← rep 文件（带 Rep OSS Tag）
│   │   ├── graph.json                           ← rep 文件（带 Rep OSS Tag）
│   │   ├── summary.md                           ← rep 文件（带 Rep OSS Tag）
│   │   ├── wiki.md                              ← rep 文件（带 Rep OSS Tag）
│   │   └── table.parquet                        ← table 型 Entity 的 Parquet（DuckDB 访问）
│   └── _index/                                  ← 系统目录
│       ├── staging/                             ← L1 写入层（Pipeline 产出）
│       │   └── representations_v{N}.parquet     ← 可检索单元 + vectors
│       └── representations.lance/               ← L3 查询层（汇聚后）
│           ├── data/
│           └── _indices/
│               ├── vector.idx
│               └── fts.idx
│
├── {entity_id_2}/                               ← 另一个 Entity
│   ├── source/
│   ├── extract/
│   ├── ...
│   └── _index/
```

**关键设计**：
- Entity 目录 = 该 Entity 的完整知识单元，包含所有 representation 文件 + Lance 索引。
- 迁移/复制/删除 = 操作整个 Entity 目录。
- 不同 Entity 之间完全隔离，无并发写入冲突。
- **零持久化元数据**：catalog / lineage / entity 元数据全部从 OSS 实时获取（VFS 扫描 + OSS Tag API）。
- **每个 representation 文件自带 OSS Tag**：业务元数据直接附着在文件上，删除文件时 Tag 自动消失，不存在"孤儿元数据"问题。血缘从目录层级推导，不存于 Tag。

#### 1 张 Lance 表 + OSS Object Tagging

| # | 文件 | 位置 | 用途 |
| --- | --- | --- | --- |
| 1 | `representations.lance` | Entity 目录内 | 该 Entity 的所有可检索单元（含 vector + text） |
| — | OSS Object Tagging | raw 对象 | Entity 的状态/标签（rag_status / labels / sync_state） |

**为什么只用 1 张 Lance 表**：
- `catalog.lance` 不需要 — VFS 扫描 prefix 即可获取所有 Entity 目录。
- `lineage.json` 不需要 — 血缘从**目录层级 + Pipeline 注册表**实时推导（目录层级即血缘深度）。
- `entity.json` 不需要 — Entity 元数据从 OSS Tag 实时读取。
- 所有元数据都可以从 OSS 实时重建，零持久化 → 没有同步问题。

#### OSS Object Tagging（两套 Tag Schema：Entity + Representation）

**所有元数据存在 OSS 对象的 Tag 上**，通过 `PutObjectTagging` / `GetObjectTagging` API 读写。

**两套 Tag Schema**：

- **Entity Tag**（打在 `{entity_id}/original` 对象上）：Entity 级元数据 + 同步状态
- **Representation Tag**（打在每个 representation 文件上）：血缘 + 变换 + 状态

##### Entity Tag Schema（10 个 Tag，打在 original 对象上）

| Key | 取值 | 说明 |
| --- | --- | --- |
| `rag_status` | `enabled` / `hidden` / `deleted` | 用户意图，VFS 过滤 |
| `entity_type` | `document` / `image` / `audio` / `video` / `table` | Entity 类型 |
| `name` | `pricing.pdf` | 原始文件名 |
| `content_hash` | `sha256_xxx` | raw 内容的 SHA-256 |
| `version` | `1` | Entity 版本号 |
| `labels` | `pricing,finance,Q3,strategy,Q3-review` | 业务标签（合并 category/project，逗号分隔） |
| `model_version` | `embedding-v5-retrieval` | 最新 embedding 模型版本 |
| `sync_state` | `idle` / `syncing` / `rebuilding` / `ready` / `failed` / `stale` | 同步状态（覆盖增量/全量/重试/级联/失败） |
| `sync_version` | `42` | Lance MVCC version 号 |
| `sync_error` | `oom` | 失败原因（failed 时才有） |

**示例**：

```text
oss://bucket/vector-lake/ws_001/kb_001/abc123/source/original
  x-oss-tagging:
    rag_status=enabled
    entity_type=document
    name=pricing.pdf
    content_hash=sha256_abc...
    version=1
    labels=pricing,finance,Q3,strategy,Q3-review
    model_version=embedding-v5-retrieval
    sync_state=ready
    sync_version=42
    sync_error=
```

##### Representation Tag Schema（7 个 Tag，打在 representation 文件上）

| Key | 取值 | 说明 |
| --- | --- | --- |
| `rep_type` | `canonical_md` / `ocr_text` / `page_image` / ... | 认知视角类型 |
| `pipeline_id` | `pipeline_a` / `pipeline_b` / ... | 产出该 rep 的流水线 |
| `transform` | `parse` / `ocr` / `vlm` / `llm_compile` / `render` | 具体变换方法 |
| `modality` | `text` / `image` / `audio` / `table` | 模态 |
| `status` | `ready` / `stale` / `failed` / `deleted` | representation 状态 |
| `model_version` | `paddleocr_v3` / `qwen2vl_v3` / ... | 产出该 rep 的模型版本 |
| `entity_version` | `3` | 所属 Entity 版本 |

**示例**：

```text
oss://bucket/vector-lake/ws_001/kb_001/abc123/recognize/ocr.md
  x-oss-tagging:
    rep_type=ocr_text
    pipeline_id=pipeline_b
    transform=ocr
    modality=text
    status=ready
    model_version=paddleocr_v3
    entity_version=3

oss://bucket/vector-lake/ws_001/kb_001/abc123/extract/page_image/page_001.png
  x-oss-tagging:
    rep_type=page_image
    pipeline_id=pipeline_b
    transform=render
    modality=image
    status=ready
    model_version=pymupdf_v4
    entity_version=3
```

**为什么 Representation 用 OSS Tag 而非 sidecar 文件**：

| 维度 | OSS Tag (7个/rep文件) | Sidecar .meta.json |
| --- | --- | --- |
| **文件数量** | 0 额外文件 | +N 个/Entity（80% 膨胀） |
| **写入成本** | PutObjectTagging（不重写对象） | PutObject 小文件 |
| **孤儿检测** | Tag 始终与对象绑定，删除对象 Tag 自动消失 | 需额外检测逻辑 |
| **工具可见性** | OSS 控制台直接看 Tag | 需自定义工具 |
| **Schema 灵活性** | 固定 7 字段，128B/value | 任意 JSON |
| **Evolution** | 预留 3 个 Tag 空位 | JSON 加字段无限制 |

> **Sidecar 演进路径**：若未来需要超过 10 个 Tag 或复杂嵌套 JSON，可在 representation 文件同目录放 `{rep_basename}.meta.json`，并用 Tag `status=meta_extended` 标记"查看 sidecar 获取完整元数据"。此设计参考 FAR (File-Augmented Retrieval) 和 Unity Engine 的 .meta sidecar 模式。

**VFS + OSS Tag 协作**：

```text
VFS 扫描 vector-lake/{ws}/{col}/ prefix
  ├─ ListObjectsV2（带 Tagging 过滤）
  │   └─ 只返回 rag_status=enabled 的 original 对象
  ├─ 对每个 enabled original 对象 GetObjectTagging
  │   └─ 获取 entity_type / labels / sync_state / ...
  ├─ 对每个 representation 文件 GetObjectTagging
  │   └─ 获取 rep_type / pipeline_id / status / ...
  └─ 内存中构建完整目录树 + 实体视图 + 血缘 DAG（从目录层级推导）
```

**OSS Tag 的优势**：
- 零存储成本（metadata 存在 OSS 服务端）
- 支持按标签过滤列表（`ListObjectsV2` + `Tagging` 参数）
- 修改不需要重写对象（原子操作）
- **Tag 与对象生命周期绑定**：删除对象时 Tag 自动消失，不存在"孤儿元数据"
- 隐藏/删除/恢复都是单一 API 调用：

```bash
# 隐藏 Entity
ossutil put-object-tagging --bucket ... --key .../original --tagging '{"Tags":[{"Key":"rag_status","Value":"hidden"}]}'

# 恢复 Entity
ossutil put-object-tagging --bucket ... --key .../original --tagging '{"Tags":[{"Key":"rag_status","Value":"enabled"}]}'

# 删除（软删除，文件保留）
ossutil put-object-tagging --bucket ... --key .../original --tagging '{"Tags":[{"Key":"rag_status","Value":"deleted"}]}'

# 标记 representation 为 stale（血缘级联）
ossutil put-object-tagging --bucket ... --key .../ocr.md --tagging '{"Tags":[{"Key":"status","Value":"stale"}]}'
```

**OSS Tag 的限制**：
- 最多 10 个 tag → Entity Tag 用 10 个（满），Representation Tag 用 7 个（预留 3 个）
- 每个 tag value 最大 128 字节 → 当前所有字段值远小于此限制
- 只能打在具体对象上 → Entity Tag 打在 `original` 上，Representation Tag 打在各自文件上
- 列表过滤只能精确匹配 → 业务标签过滤在 VFS 内存中做
- PutObjectTagging 不支持原子 CAS → 用 `CopyObject` + `x-oss-copy-source-if-match` 实现（见 §4.6 同步协议 Stage 2）

#### `representations.lance`（Entity 目录内，核心检索表）

每行 = 一个可检索单元。一个 `canonical_md` representation 切成 50 行，每行有自己的 text + vector。`chunk_index` 区分同一 representation 的不同切分段。

##### PyArrow Schema 定义

```python
import pyarrow as pa

REPRESENTATIONS_SCHEMA = pa.schema([
    # ── 主键 ──────────────────────────────────────────────
    pa.field("entity_id", pa.utf8(), nullable=False),           # 所属 Entity
    pa.field("rep_type", pa.utf8(), nullable=False),            # 认知视角类型
    pa.field("chunk_index", pa.int32(), nullable=False),        # 同一 rep 的切分序号

    # ── Entity 关联 ───────────────────────────────────────
    pa.field("entity_version", pa.int32(), nullable=False),     # 冗余加速（权威值在 OSS Tag）

    # ── Representation 元数据 ─────────────────────────────
    pa.field("rep_type", pa.utf8(), nullable=False),            # canonical_md / ocr_text / ...
    pa.field("pipeline_id", pa.utf8(), nullable=False),         # 产出流水线
    pa.field("transform", pa.utf8(), nullable=False),           # parse / ocr / vlm / llm_compile
    pa.field("modality", pa.utf8(), nullable=False),            # text / image / audio / table
    pa.field("model_version", pa.utf8(), nullable=True),        # 产出该 rep 的模型版本

    # ── 文本内容 ──────────────────────────────────────────
    pa.field("text", pa.utf8(), nullable=False),                # 原文（建 FTS 索引）
    pa.field("embedding_text", pa.utf8(), nullable=True),       # 向量化文本（可能与 text 不同）

    # ── 定位信息 ──────────────────────────────────────────
    pa.field("start_pos", pa.int32(), nullable=False),          # 在 rep 中的字符偏移
    pa.field("end_pos", pa.int32(), nullable=False),            # 在 rep 中的字符结束偏移
    pa.field("token_count", pa.int32(), nullable=False),        # token 数
    pa.field("chunk_chars", pa.int32(), nullable=False),        # 字符数

    # ── 文档结构（nullable，仅结构化文档有值）──────────────
    pa.field("page_number", pa.int32(), nullable=True),         # 页码
    pa.field("section_header", pa.utf8(), nullable=True),       # 章节标题
    pa.field("section_level", pa.int32(), nullable=True),       # 章节层级
    pa.field("anchor", pa.utf8(), nullable=True),               # 锚点（HTML/PDF）
    pa.field("doc_title", pa.utf8(), nullable=True),            # 文档标题

    # ── 多模态扩展（nullable，非文本模态有值）──────────────
    pa.field("image_uri", pa.utf8(), nullable=True),            # 图片 OSS URI（modality=image）
    pa.field("audio_uri", pa.utf8(), nullable=True),            # 音频 OSS URI（modality=audio）
    pa.field("table_data", pa.utf8(), nullable=True),           # 表格 JSON（modality=table）

    # ── 向量 ──────────────────────────────────────────────
    pa.field("vector", pa.fixed_size_list(pa.float32(), 1024),  # Jina V5 维度
             nullable=False),

    # ── 状态 + 校验 ──────────────────────────────────────
    pa.field("status", pa.utf8(), nullable=False),              # active / stale / hidden / deleted
    pa.field("content_hash", pa.utf8(), nullable=True),         # chunk 内容的 SHA-256

    # ── 时间戳 ────────────────────────────────────────────
    pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("updated_at", pa.timestamp("us", tz="UTC"), nullable=False),
])

# 主键约束（Lance 不强制，应用层保证）
# PRIMARY KEY = (entity_id, rep_type, chunk_index)
```

##### Pydantic Model 定义

```python
from lancedb.pydantic import LanceModel, Vector
from datetime import datetime

class RepresentationChunk(LanceModel):
    # 主键
    entity_id: str
    rep_type: str
    chunk_index: int

    # Entity 关联
    entity_version: int

    # Representation 元数据
    pipeline_id: str
    transform: str
    modality: str
    model_version: str | None = None

    # 文本内容
    text: str
    embedding_text: str | None = None

    # 定位信息
    start_pos: int
    end_pos: int
    token_count: int
    chunk_chars: int

    # 文档结构
    page_number: int | None = None
    section_header: str | None = None
    section_level: int | None = None
    anchor: str | None = None
    doc_title: str | None = None

    # 多模态扩展
    image_uri: str | None = None
    audio_uri: str | None = None
    table_data: str | None = None

    # 向量
    vector: Vector(1024)  # Jina V5 维度

    # 状态 + 校验
    status: str = "active"
    content_hash: str | None = None

    # 时间戳
    created_at: datetime
    updated_at: datetime
```

##### 字段分组与用途

```text
┌─────────────────────────────────────────────────────────────┐
│  representations.lance 字段分组                               │
├──────────────┬──────────────────────────────────────────────┤
│  主键         │ entity_id + rep_type + chunk_index           │
│              │ (应用层保证唯一，Lance 不强制)                 │
├──────────────┼──────────────────────────────────────────────┤
│  Entity 关联  │ entity_id + entity_version                   │
│              │ (跨 Entity 检索时用于 fan-out 路由)            │
├──────────────┼──────────────────────────────────────────────┤
│  Rep 元数据   │ pipeline_id + transform + modality +         │
│              │ model_version                                 │
│              │ (冗余自 OSS Tag，用于过滤)                     │
├──────────────┼──────────────────────────────────────────────┤
│  文本内容     │ text + embedding_text                        │
│              │ (text 建 FTS，embedding_text 记录向量化原文)    │
├──────────────┼──────────────────────────────────────────────┤
│  定位信息     │ start_pos + end_pos + token_count +          │
│              │ chunk_chars                                  │
│              │ (用于高亮 + 预览定位)                          │
├──────────────┼──────────────────────────────────────────────┤
│  文档结构     │ page_number + section_header +               │
│  (nullable)  │ section_level + anchor + doc_title            │
│              │ (结构化文档才有值)                             │
├──────────────┼──────────────────────────────────────────────┤
│  多模态扩展   │ image_uri + audio_uri + table_data            │
│  (nullable)  │ (非文本模态才有值)                             │
├──────────────┼──────────────────────────────────────────────┤
│  向量         │ vector (fixed_size_list<float, 1024>)         │
│              │ (Jina V5 Omni，文本/图像/音频同一空间)         │
├──────────────┼──────────────────────────────────────────────┤
│  状态 + 校验  │ status + content_hash                        │
│              │ (status 驱动过滤，content_hash 驱动去重)       │
├──────────────┼──────────────────────────────────────────────┤
│  时间戳       │ created_at + updated_at                      │
│              │ (Lance timestamp，UTC 微秒精度)               │
└──────────────┴──────────────────────────────────────────────┘
```

##### 索引设计

```python
def create_all_indexes(table: lancedb.table.Table):
    """为 representations.lance 创建所有索引。"""

    # ── 1. 向量索引 ──────────────────────────────────────
    # IVF_HNSW_SQ：IVF 分区 + HNSW 图 + 标量量化
    # 适合：中等规模（1K-1M 行），低延迟，高召回
    table.create_index(
        column="vector",
        index_type="IVF_HNSW_SQ",
        metric="cosine",             # Jina V5 推荐 cosine
        num_partitions=256,          # IVF 分区数（行数 / 1000 为参考）
        replace=True,
    )

    # ── 2. 全文检索索引 ──────────────────────────────────
    # BM25 + 分词，支持中英文
    table.create_fts_index(
        column="text",
        replace=True,
    )

    # ── 3. 标量索引（过滤加速）───────────────────────────
    for col in ["status", "rep_type", "modality", "entity_version"]:
        table.create_scalar_index(
            column=col,
            replace=True,
        )
```

**索引选择策略**：

| 行数 | 向量索引 | num_partitions | 说明 |
| --- | --- | --- | --- |
| < 10K | 不建索引（暴力搜索） | - | Lance 自动全量扫描，延迟 < 50ms |
| 10K - 100K | `IVF_HNSW_SQ` | 32 | 小规模，SQ 量化足够 |
| 100K - 1M | `IVF_HNSW_SQ` | 256 | 中等规模，推荐默认配置 |
| > 1M | `IVF_HNSW_PQ` | 1024 | 大规模，PQ 压缩节省内存 |

> v0.1 每个 Entity 的 Lance 表通常 < 10K 行（1个文档 × 5个rep × 50个chunk = 250行），不需要建向量索引，暴力搜索即可。索引在跨 Entity 汇聚查询时才需要。

##### 查询模式

```python
# ── 模式 1：语义检索（向量搜索）─────────────────────────
results = table.search(query_vector) \
    .where("status = 'active'") \
    .where("modality = 'text'") \
    .limit(20) \
    .to_pandas()

# ── 模式 2：全文检索（BM25）────────────────────────────
results = table.search("定价策略", query_type="fts") \
    .where("status = 'active'") \
    .limit(20) \
    .to_pandas()

# ── 模式 3：混合检索（语义 + BM25 + RRF）───────────────
from lancedb.rerankers import RRFReranker

vector_results = table.search(query_vector).limit(50).to_list()
fts_results = table.search(query_text, query_type="fts").limit(50).to_list()

reranker = RRFReranker()
results = reranker.rerank(vector_results, fts_results)

# ── 模式 4：按 representation 过滤 ─────────────────────
results = table.search(query_vector) \
    .where("rep_type = 'ocr_text'") \
    .where("status = 'active'") \
    .limit(10) \
    .to_pandas()

# ── 模式 5：按变换方法过滤（只查直接提取的，不含 OCR/VLM）──
results = table.search(query_vector) \
    .where("transform = 'parse'") \
    .where("status = 'active'") \
    .limit(10) \
    .to_pandas()

# ── 模式 6：按页码定位 ─────────────────────────────────
results = table.search(query_vector) \
    .where("page_number = 3") \
    .where("status = 'active'") \
    .limit(5) \
    .to_pandas()

# ── 模式 7：多模态检索（文本 + 图片同一空间）────────────
results = table.search(query_vector) \
    .where("status = 'active'") \
    .where("modality IN ('text', 'image')") \
    .limit(20) \
    .to_pandas()
```

##### 数据生命周期

```text
┌─────────────────────────────────────────────────────────────┐
│  representations.lance 数据生命周期                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Pipeline 产出                                               │
│     │                                                       │
│     ▼                                                       │
│  staging/representations_v{N}.parquet                        │
│     │                                                       │
│     ▼  Lance Watcher 增量同步                                │
│  representations.lance (status=active)                       │
│     │                                                       │
│     ├── 上游变动 → status=stale（检索不命中）                  │
│     │       │                                               │
│     │       ▼  Pipeline 重建                                 │
│     │   新 chunk 写入 → status=active                        │
│     │   旧 chunk 标记 → status=stale（deletion vector）       │
│     │       │                                               │
│     │       ▼  Compact / Rebuild                             │
│     │   物理删除 stale 行                                     │
│     │                                                       │
│     ├── 用户隐藏 → status=hidden（检索不命中）                 │
│     │       │                                               │
│     │       ▼  用户恢复 → status=active                       │
│     │                                                       │
│     └── 用户删除 → status=deleted（检索不命中）                │
│             │                                               │
│             ▼  Compact / Rebuild                             │
│         物理删除 deleted 行                                   │
│                                                             │
│  MVCC 版本保留策略：                                          │
│  ├─ 保留最近 5 个 Lance version                              │
│  ├─ 超过 5 个 → Compact 时物理删除旧 version 数据文件         │
│  └─ 回滚窗口 = 5 个 version 内                               │
└─────────────────────────────────────────────────────────────┘
```

##### 跨 Entity 检索（fan-out + merge）

```text
每个 Entity 一个 representations.lance，跨 Entity 检索流程：

1. VFS 扫描 → 获取所有 enabled Entity 列表
2. 按 OSS Tag 路由 → 过滤 entity_type / labels / sync_state
3. fan-out → 并行查询 N 个 Entity 的 Lance 表
4. merge → 按 distance/score 排序，取 top_k
5. 补充 Entity 元数据 → 从 OSS Tag 读取 name / labels 等
```

```python
async def cross_entity_search(
    query_vector: list[float],
    workspace_id: str,
    collection_id: str,
    entity_types: list[str] | None = None,
    labels: list[str] | None = None,
    rep_types: list[str] | None = None,
    top_k: int = 20,
) -> list[dict]:
    """跨 Entity 混合检索。"""

    # 1. VFS 扫描 → 获取 enabled Entity 列表
    entities = await vfs.list_entities(
        workspace_id, collection_id,
        filters={"rag_status": "enabled", "sync_state": "ready",
                 "entity_type": entity_types, "labels": labels}
    )

    # 2. fan-out → 并行查询
    import asyncio
    tasks = []
    for entity in entities:
        lance_path = f"oss://.../{entity.entity_id}/representations.lance/"
        table = lancedb.open_table(lance_path)
        task = table.search(query_vector) \
            .where(f"status = 'active'") \
            .where(f"rep_type IN {rep_types}" if rep_types else "true") \
            .limit(top_k) \
            .to_list_async()
        tasks.append(task)

    all_results = await asyncio.gather(*tasks)

    # 3. merge → 按 _distance 排序
    merged = []
    for entity, results in zip(entities, all_results):
        for r in results:
            r["entity_id"] = entity.entity_id
            r["entity_name"] = entity.name
            r["entity_labels"] = entity.labels
            merged.append(r)

    merged.sort(key=lambda x: x["_distance"])
    return merged[:top_k]
```

##### Schema 演进策略

Lance 原生支持 schema evolution（加列不改列），演进规则：

| 操作 | 支持 | 说明 |
| --- | --- | --- |
| **新增 nullable 列** | 原生支持 | `table.add_columns({"new_col": "null"})`，旧行读出 null |
| **新增非 null 列** | 原生支持 | 需提供默认值 |
| **删除列** | 原生支持 | `table.drop_columns(["old_col"])`，元数据级删除 |
| **修改列类型** | 不支持 | 需 Full Rebuild（重建 Lance 数据集） |
| **修改向量维度** | 不支持 | 需 Full Rebuild + 重新 embedding |
| **重命名列** | 原生支持 | `table.rename_columns({"old": "new"})` |

> **v0.2 预留演进空间**：所有 nullable 列（page_number / section_header / image_uri 等）都是未来可扩展的方向。新增列不需要 Rebuild，Lance 原生支持。

#### Lineage 实时推导（从目录层级 + Pipeline 注册表）

**核心洞察**：血缘关系**不存于任何字段或 OSS Tag**，完全从**目录层级**和**Pipeline 注册表**实时推导。目录层级天然编码了血缘深度：`source/` → `extract/` → `recognize/` → `compile/`。

```text
推导方法：

1. 扫描 Entity 目录下的四个层级目录
   ├─ source/ → 血缘深度 L0（根节点）
   ├─ extract/ → 血缘深度 L1（直接提取）
   ├─ recognize/ → 血缘深度 L2（识别/转写）
   └─ compile/ → 血缘深度 L3（知识编译）

2. 从目录层级推断粗粒度血缘（无需查 Pipeline 注册表）
   ├─ extract/* 的上游一定是 source/original
   ├─ recognize/* 的上游一定是 extract/* 下的某个 rep
   └─ compile/* 的上游是 extract/* 或 recognize/* 下的某个 rep

3. 从 Pipeline 注册表获取细粒度血缘（精确到具体 rep_type）
   ├─ Pipeline A: input=raw, output=[canonical_md, plain_text]
   ├─ Pipeline B: input=raw, output=[page_image]
   ├─ Pipeline C: input=page_image, output=[ocr_text, vlm_extracted_md]
   ├─ Pipeline D: input=canonical_md, output=[mind_map, summary, graph_json, wiki_md]
   └─ Pipeline E: input=audio_segment, output=[transcript, transcript_segment]

4. 内存中构建血缘 DAG
   ├─ 节点 = 每个 rep_type（在当前 Entity 存在的）
   ├─ 边 = Pipeline.input_rep → Pipeline.output_rep
   ├─ 遍历上游/下游 → O(边数 × 存在检查)
   └─ 影响分析 → O(下游子树)
```

**示例 DAG**（从目录层级 + Pipeline 注册表推导）：

```text
source/original (L0, raw)
  ├─► extract/canonical_md      (L1, Pipeline A: parse)
  │     ├─► compile/mind_map    (L3, Pipeline D: llm_compile)
  │     ├─► compile/summary     (L3, Pipeline D: llm_compile)
  │     ├─► compile/graph_json  (L3, Pipeline D: llm_compile)
  │     └─► compile/wiki_md     (L3, Pipeline D: llm_compile)
  │
  ├─► extract/plain_text        (L1, Pipeline A: parse)
  │
  └─► extract/page_image        (L1, Pipeline B: render)
        ├─► recognize/ocr_text         (L2, Pipeline C: ocr)
        └─► recognize/vlm_extracted_md (L2, Pipeline C: vlm)
```

**目录层级带来的推导加速**：

| 推导需求 | 仅用目录层级 | + Pipeline 注册表 |
| --- | --- | --- |
| "ocr_text 的上游在哪？" | 一定是 `extract/` 下 → 缩小搜索范围 | `page_image`（Pipeline C 声明） |
| "raw 变了，影响谁？" | `extract/` + `recognize/` + `compile/` 全部 | 精确到具体 rep_type |
| "新增 recognize/xxx.md" | 上游一定是 `extract/` 下 | 查 Pipeline 注册表确定具体哪个 |

**推导的 Python 实现**：

```python
# 目录层级 → 血缘深度映射
STAGE_DEPTH = {
    "source": 0,    # 根节点
    "extract": 1,   # 直接提取
    "recognize": 2, # 识别/转写
    "compile": 3,   # 知识编译
}

# Pipeline 注册表（代码内注册，v0.1 静态）
PIPELINE_REGISTRY = {
    "pipeline_a": {
        "name": "直接提取",
        "input_rep": "raw",
        "output_reps": ["canonical_md", "plain_text"],
        "output_stage": "extract",
    },
    "pipeline_b": {
        "name": "OCR 流水线",
        "input_rep": "raw",
        "output_reps": ["page_image"],
        "output_stage": "extract",
    },
    "pipeline_c": {
        "name": "VLM 视觉",
        "input_rep": "page_image",
        "output_reps": ["ocr_text", "vlm_extracted_md"],
        "output_stage": "recognize",
    },
    "pipeline_d": {
        "name": "知识编译",
        "input_rep": "canonical_md",
        "output_reps": ["mind_map", "summary", "graph_json", "wiki_md"],
        "output_stage": "compile",
    },
    "pipeline_e": {
        "name": "音频转写",
        "input_rep": "audio_segment",
        "output_reps": ["transcript", "transcript_segment"],
        "output_stage": "recognize",
    },
}

def build_lineage_dag(entity_id: str) -> dict:
    """从目录层级 + Pipeline 注册表推导 Entity 的血缘 DAG。"""

    # 1. 按层级扫描 Entity 目录
    existing_reps = {}  # stage → set of rep_types
    for stage in ["source", "extract", "recognize", "compile"]:
        prefix = f"{entity_id}/{stage}/"
        files = vfs.list_files(prefix)
        rep_types = {infer_rep_type(f.path, stage) for f in files}
        if rep_types:
            existing_reps[stage] = rep_types

    # 2. 遍历 Pipeline 注册表，找出存在的 rep 之间的派生关系
    all_existing = set()
    for reps in existing_reps.values():
        all_existing.update(reps)

    edges = []
    for pid, pipeline in PIPELINE_REGISTRY.items():
        input_rep = pipeline["input_rep"]
        for output_rep in pipeline["output_reps"]:
            if input_rep in all_existing and output_rep in all_existing:
                edges.append((input_rep, output_rep, pid))

    return {
        "nodes": list(all_existing),
        "edges": edges,
        "stages": existing_reps,
    }

def infer_rep_type(oss_path: str, stage: str) -> str:
    """从路径 + 目录层级推导 rep_type。"""
    basename = os.path.basename(oss_path)
    # 1. 优先匹配 §4.2 路径约定表
    for rep_type, path_pattern in REP_TYPE_PATH_PATTERNS.items():
        if re.match(path_pattern, basename):
            return rep_type
    # 2. fallback 到 OSS Tag rep_type
    return get_object_tagging(oss_path).rep_type
```

**为什么从目录层级推导而非 OSS Tag**：

| 维度 | 目录层级推导 | OSS Tag 存储 derived_from |
| --- | --- | --- |
| **存储成本** | 零存储（目录即血缘） | 每个 rep 文件多 1 个 Tag（10个里占 1 个） |
| **准确性** | 目录层级 + Pipeline 注册表双重保证 | 需保证每个 rep 都正确打 Tag，可能漏打/错打 |
| **可扩展性** | 新增 rep_type 只需注册到 Pipeline + 放到对应层级目录 | 需每个产出 Pipeline 都正确写 Tag |
| **级联失效** | 沿 Pipeline 边遍历，目录层级加速定位 | 需读 derived_from Tag 遍历 |
| **多源衍生** | Pipeline 可声明多个 input_rep（merge） | derived_from 需用分隔符拼装 |
| **扫描成本** | 按层级 prefix 扫描（4 次 ListObjects） | 全目录扫描 + 批量 GetObjTagging |
| **可读性** | `recognize/ocr.md` 一眼看出是 L2 识别产物 | 需查看 Tag 才知血缘 |

**OSS Tag 减负的连锁效果**：

- Tag 从 8 个减为 7 个（去 `derived_from`），3 个空位可做 evolution。
- 血缘推导逻辑与 Pipeline 注册表 + 目录层级耦合，新增 Pipeline 只需修改注册表 + 放到对应目录。
- OSS Tag 仅承载**业务元数据**（状态、版本、流水线、模态），**不承担关系建模**。

**为什么实时推导而非持久化**：
- 一个 Entity 的血缘边通常 5-10 条，内存推导比读 JSON 快。
- 推导逻辑是确定性的（基于目录层级 + Pipeline 注册表），不需要快照。
- 任何文件变动都立即反映在血缘图上，无同步问题。
- Pipeline 升级时只需修改注册表，无需数据迁移。

**血缘推导性能估算**：

| 规模 | 文件数 | 目录层级扫描 | Pipeline 注册表查询 | 推导耗时 |
| --- | --- | --- | --- | --- |
| 1 Entity | ~10 | 4 次 ListObjects | 5 个 pipeline × 输出数 | < 50ms |
| 1K Entity | ~10K | 4K 次 ListObjects | 同上（独立推导） | ~10s |
| 1M Entity | ~10M | 4M 次 ListObjects | 同上 | ~3min（并行） |

> v0.1 规模（< 10K Entity）下推导耗时可忽略。v0.2 可引入缓存 + 增量更新（仅重建变更的 Entity）。

**Edge cases 与解决方案**：

| Edge case | 解决方案 |
| --- | --- |
| **同一 rep_type 由多条 Pipeline 产出** | Pipeline 注册表中同 rep_type 多条记录 → 推导时取并集边 |
| **跨 rep_type merge** | Pipeline 声明 `input_reps: [canonical_md, ocr_text]`（多上游） |
| **派生链分叉** | 推导时递归遍历，所有上游都在才标 stale（AND 语义） |
| **手写 representation**（非 pipeline 产出） | 在 Pipeline 注册表加 `manual: true` 标记，input=raw |
| **临时 rep（调试）** | 放在 `_tmp/` 目录，VFS 列表时跳过（下划线前缀 = 系统/临时） |
| **跨层级引用** | compile/ 的输入可以是 extract/ 或 recognize/，Pipeline 注册表精确声明 |

**演进路径（v0.2+）**：

- 如果未来出现"跨 Entity 血缘"（A 的 rep 是 B 的 rep 的输入），可在 Pipeline 注册表加 `cross_entity: true` 字段，推导时跨 Entity 查询。
- 如果未来需要"非确定性血缘"（动态选择上游），可回退到 OSS Tag 存 derived_from 方案。
- 如果未来需要更多层级（如 `translate/`、`reasoning/`），只需在 STAGE_DEPTH 注册新层级。

#### L1. 写入层：Pipeline 产出 Parquet

Pipeline 产出直接写入 Entity 目录下的 `staging/`：

`{entity_id}/staging/representations_v{N}.parquet`：

```text
entity_id · rep_type · chunk_index
pipeline_id · transform · modality · model_version
text · embedding_text · start_pos · end_pos · token_count · chunk_chars
page_number · section_header · section_level · anchor · doc_title
image_uri · audio_uri · table_data
content_hash · model_version
vector (list<float>) · status · entity_version
created_at · updated_at
```

> Parquet 与 `representations.lance` 共享同一逻辑 schema（L1 写入后由 L2 汇聚层负责类型对齐到 `fixed_size_list<float, 1024>`）。

**写入层特点**：
- **追加写**：pipeline 产出直接 append，无需建索引。
- **天然隔离**：不同 Entity 写不同目录，无并发冲突。
- **立即可查**：staging 中的 Parquet 可被直接扫描（用于调试 / 预览），但无索引优化。
- **版本化**：每次 pipeline 重跑产出新的 `representations_v{N}.parquet`。

#### L2. 汇聚层：Lance Watcher（事件驱动 + 增量同步 + Rebuild）

**核心设计**：Lance Watcher 是一个常驻服务，监听 staging Parquet 变动并实时同步到 Lance。同时支持全量 rebuild（从 OSS representation 文件重建整个 Lance 数据集）。

##### Lance Watcher 架构

```text
┌─────────────────────────────────────────────────────────────┐
│  Lance Watcher（常驻服务）                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐     ┌──────────────┐                     │
│  │ Event Listener│────►│ Sync Queue   │                     │
│  │ (OSS 事件)    │     │ (per Entity) │                     │
│  └──────────────┘     └──────┬───────┘                     │
│                              │                              │
│                    ┌─────────┴─────────┐                    │
│                    ▼                   ▼                    │
│            ┌──────────────┐    ┌──────────────┐            │
│            │ Incremental  │    │ Full Rebuild │            │
│            │ Sync Worker  │    │ Worker       │            │
│            └──────┬───────┘    └──────┬───────┘            │
│                   │                   │                     │
│                   ▼                   ▼                     │
│            ┌─────────────────────────────────┐             │
│            │  representations.lance           │             │
│            │  (MVCC, 原子切换)                │             │
│            └─────────────────────────────────┘             │
│                                                             │
│  ┌──────────────┐     ┌──────────────┐                     │
│  │ Reconciler   │────►│ 补漏 + 碎片  │                     │
│  │ (周期兜底)    │     │ 整理         │                     │
│  └──────────────┘     └──────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

##### 两种同步模式

| 模式 | 触发条件 | 数据来源 | 耗时 | 适用场景 |
| --- | --- | --- | --- | --- |
| **Incremental Sync** | staging Parquet 新增/修改 | staging/*.parquet | 秒级 | Pipeline 产出后实时同步 |
| **Full Rebuild** | 手动触发 / schema 变更 / Lance 损坏 / 碎片率过高 | 所有 representation 文件 + staging | 分钟级 | 修复 / 重建 / 优化 |

##### Incremental Sync：Parquet 变动即触发

**触发源**：

```text
触发路径（优先级从高到低）：

1. OSS 事件驱动（实时，主路径）
   ├─ ObjectCreated: {entity_id}/staging/*.parquet  → 立即触发增量同步
   ├─ ObjectModified: {entity_id}/staging/*.parquet  → 触发增量同步
   └─ ObjectRemoved: {entity_id}/staging/*.parquet  → 触发增量同步（删除对应行）

2. OSS Tag 变更驱动
   ├─ representation 文件 status→stale  → 删除 Lance 中对应行
   └─ representation 文件 status→ready  → 触发增量同步（如果 staging 有新 Parquet）

3. 周期 reconcile（兜底，每 15 min）
   ├─ 全量扫描 vector-lake/{ws}/{col}/ 下的所有 Entity
   ├─ 比对 sync_state Tag
   └─ 触发漏掉的事件处理

4. 手动触发
   └─ POST /entities/{id}/sync  → 强制增量同步
```

**增量同步流程**：

```text
OSS 事件: staging/representations_v3.parquet Created
   │
   ▼
[1] 入队：将 {entity_id} 放入 Sync Queue
   │
   ▼
[2] 获取同步锁（OSS Tag sync_state=idle→syncing）
   │  失败 → 跳过（已有同步在进行）
   │
   ▼
[3] Detect：扫描 staging/ 目录，找出未同步的 Parquet 文件
   ├─ 对比 Lance manifest 中记录的已同步文件列表
   └─ 计算变更集（新增 / 删除 / 替换）
   │
   ▼
[4] Transform：Parquet → Lance
   ├─ 读取新增 Parquet
   ├─ Schema 对齐 + 类型转换
   ├─ 去重（entity_id + rep_type + chunk_index）
   └─ 追加写入 Lance（append 模式）
   │
   ▼
[5] Delete：处理被删除的 Parquet
   ├─ 找出 Lance 中属于已删除 Parquet 的行
   └─ 标记为 deleted（Lance deletion vector）
   │
   ▼
[6] Index：增量更新索引
   ├─ vector 索引：新增向量加入索引
   ├─ FTS 索引：新增文本加入索引
   └─ Scalar 索引：自动更新
   │
   ▼
[7] Publish：原子切换
   ├─ Lance commit 新 version
   ├─ 更新 OSS Tag sync_state=ready, sync_version=N
   └─ 记录已同步的 Parquet 文件列表到 Lance manifest metadata
   │
   ▼
[8] Cleanup：清理已同步的 staging Parquet
   └─ 保留最近 1 个版本（debug 用），删除更早版本
```

**增量同步的幂等性**：

```python
# Lance manifest metadata 记录已同步的 Parquet 文件
synced_files = lance.get_manifest_metadata("synced_parquet_files")
# e.g. ["representations_v1.parquet", "representations_v2.parquet"]

# 新 Parquet 文件列表
new_files = [f for f in staging_files if f not in synced_files]

# 只同步新文件，重复触发不会重复写入
if not new_files:
    return  # 幂等：无新变更，跳过
```

**增量同步的延迟保证**：

| 场景 | 触发方式 | 延迟 |
| --- | --- | --- |
| Pipeline 产出 Parquet | OSS 事件 | < 5s |
| Representation stale | OSS Tag 变更 | < 10s |
| 事件丢失 | Reconciler 兜底 | < 15min |
| 手动触发 | API 调用 | 立即 |

##### Full Rebuild：从 OSS 重建整个 Lance

**触发条件**：

| 触发条件 | 说明 |
| --- | --- |
| **手动触发** | `POST /entities/{id}/rebuild` 或 `Entity.rebuild_lance()` |
| **Schema 变更** | Lance 表 schema 升级（新增/修改列），需要全量重写 |
| **Lance 损坏** | Lance 数据文件损坏，无法正常读取 |
| **碎片率过高** | fragment 数量 > 阈值，compact 无法有效优化 |
| **索引失效** | vector/FTS 索引损坏或严重退化 |
| **模型升级** | embedding 模型版本变更，需要全量重算向量 |
| **版本回滚** | 需要回退到某个历史版本 |

**Rebuild 流程**：

```text
POST /entities/{id}/rebuild
   │
   ▼
[1] 获取重建锁（OSS Tag sync_state=idle→rebuilding）
   │  失败 → 返回 409 Conflict
   │
   ▼
[2] Snapshot：记录当前 Lance version（用于回滚）
   └─ snapshot_version = current_lance_version
   │
   ▼
[3] Scan：扫描 Entity 目录下所有 representation 文件
   ├─ 读取每个 representation 文件的 OSS Tag
   ├─ 获取 rep_type / status / entity_version / ...
   └─ 过滤掉 status=deleted 的 representation
   │
   ▼
[4] Read：读取所有可用的数据源
   ├─ staging/*.parquet（最新 Parquet）
   ├─ representation 文件本身（如果 Parquet 不可用，需要重新 chunk + embed）
   └─ 旧 Lance 数据（如果只需 schema 变更，可直接迁移）
   │
   ▼
[5] Rebuild：全量重写 Lance
   ├─ 创建新的 Lance 数据集（新 version）
   ├─ Schema 对齐 + 类型转换
   ├─ 去重（entity_id + rep_type + chunk_index）
   ├─ 写入所有行
   └─ 保留旧 version 的 Lance 数据（MVCC）
   │
   ▼
[6] Index：重建所有索引
   ├─ vector 索引（IVF_PQ / HNSW）
   ├─ FTS 索引
   └─ Scalar 索引（status / rep_type / modality）
   │
   ▼
[7] Atomic Switch：原子切换到新 Lance version
   ├─ Lance commit 新 version
   ├─ 更新 OSS Tag sync_state=ready, sync_version=N
   └─ 旧 version 保留 5 个（回滚窗口）
   │
   ▼
[8] Verify：验证新 Lance 数据正确性
   ├─ 行数对比（新 vs 旧）
   ├─ 索引完整性检查
   └─ 抽样查询验证
   │
   ▼
[9] Cleanup：清理旧数据
   ├─ 删除超过保留窗口的旧 Lance version
   └─ 清理 staging 中已同步的 Parquet
```

**Rebuild 的回滚机制**：

```python
def rebuild_with_rollback(entity_id: str):
    """全量重建，支持回滚。"""

    # 1. 记录快照
    snapshot_version = get_lance_version(entity_id)

    try:
        # 2-7. 执行 rebuild 流程
        new_version = do_rebuild(entity_id)

        # 8. 验证
        if not verify_rebuild(entity_id, new_version):
            raise RebuildVerificationError("Row count mismatch")

        # 9. 成功，更新 Tag
        put_object_tagging(entity_id, {
            "sync_state": "ready",
            "sync_version": new_version,
        })

    except Exception as e:
        # 回滚：切回旧 version
        log.error(f"Rebuild failed: {e}, rolling back to v{snapshot_version}")
        lance.rollback(entity_id, snapshot_version)
        put_object_tagging(entity_id, {
            "sync_state": "failed",
            "sync_error": f"rebuild_failed: {str(e)[:100]}",
        })
```

**Rebuild vs Incremental Sync 选择策略**：

```python
def choose_sync_mode(entity_id: str) -> str:
    """自动选择同步模式。"""

    lance_stats = lance.get_stats(entity_id)

    # 1. 碎片率检查
    if lance_stats.num_fragments > 0:
        avg_rows_per_fragment = lance_stats.num_rows / lance_stats.num_fragments
        if avg_rows_per_fragment < 500:
            return "rebuild"  # 碎片率过高

    # 2. 累计增量次数检查
    incremental_count = lance_stats.get_metadata("incremental_count", 0)
    if incremental_count > 20:
        return "rebuild"  # 增量次数过多，需要全量整理

    # 3. 索引健康度检查
    if not lance_stats.index_healthy:
        return "rebuild"  # 索引退化

    # 4. 默认增量
    return "incremental"
```

##### 同步状态机（扩展版）

每个 Entity 维护一个 `sync_state`（存在 OSS Tag 上）：

```text
sync_state = idle | syncing | rebuilding | ready | failed | stale
```

```text
                    ┌──────┐
                    │ idle │  ← 初始状态 / 同步完成
                    └──┬───┘
                       │
            ┌──────────┼──────────┐
            │ 增量触发  │ rebuild  │
            ▼          ▼          │
        ┌────────┐ ┌────────────┐│
        │syncing │ │rebuilding  ││
        └──┬─────┘ └──┬─────────┘│
      ┌────┼─────┐  ┌──┼─────────┤
      ▼    ▼     ▼  ▼  ▼         │
  ┌─────┐┌─────┐┌───────┐       │
  │ready││stale││failed │       │
  └──┬──┘└──┬──┘└───┬───┘       │
     │      │        │           │
     └──────┘        │ retry     │
          │          │           │
          ▼          ▼           │
       ┌────────┐               │
       │syncing │◄──────────────┘
       └────────┘  (stale/failed 可选 rebuild)
```

**状态转换规则**：

| 当前状态 | 事件 | 目标状态 | 说明 |
| --- | --- | --- | --- |
| `idle` | Parquet 新增 | `syncing` | 增量同步 |
| `idle` | rebuild 请求 | `rebuilding` | 全量重建 |
| `syncing` | 同步完成 | `ready` | 成功 |
| `syncing` | 同步失败 | `failed` | 记录失败原因 |
| `syncing` | 上游 stale | `stale` | 血缘级联 |
| `rebuilding` | 重建完成 | `ready` | 成功 |
| `rebuilding` | 重建失败 | `failed` | 回滚到旧 version |
| `ready` | Parquet 新增 | `syncing` | 新增量 |
| `ready` | 上游 stale | `stale` | 血缘级联 |
| `stale` | 自动/手动触发 | `syncing` | 增量修复 |
| `stale` | rebuild 请求 | `rebuilding` | 全量修复 |
| `failed` | 自动/手动重试 | `syncing` | 从断点恢复 |
| `failed` | rebuild 请求 | `rebuilding` | 全量重建 |

##### Lance Watcher 的并发控制

```text
并发规则：

1. 每个 Entity 同一时刻只有一个同步操作（syncing 或 rebuilding）
   ├─ 通过 OSS Tag sync_state 做分布式锁
   └─ CAS 语义通过 CopyObject + x-oss-copy-source-if-match 实现

2. 不同 Entity 的同步操作可并行
   ├─ Sync Queue 按 entity_id 分片
   └─ 每个 Worker 独立处理一个 Entity

3. Incremental Sync 优先级高于 Rebuild
   ├─ 如果 syncing 进行中，rebuild 请求排队等待
   └─ syncing 完成后再执行 rebuild

4. Rebuild 期间新的增量变更缓存到队列
   ├─ rebuild 完成后检查队列
   └─ 如果有新变更，再执行一次 incremental sync
```

##### 汇聚策略

| 策略 | 触发条件 | 说明 |
| --- | --- | --- |
| **增量同步** | staging Parquet 新增/修改/删除 | 实时触发，秒级完成 |
| **全量 Rebuild** | 手动 / schema 变更 / 碎片率过高 / Lance 损坏 | 从 OSS 重建，分钟级完成 |
| **自动 Compact** | fragment 数 > 阈值 或 累计增量 > 20 次 | 合并 fragment，优化存储布局 |
| **版本切换** | Entity 有新 version | 替换旧 version 的行，保留 lineage |

#### OSS → Lance 同步协议

**核心挑战**：OSS 是 append-only 不可变存储，Lance 是支持 MVCC 的可更新存储。需要在两者之间建立确定性的同步协议，保证：

1. **幂等性**：重复同步不产生重复数据
2. **原子性**：sync 中断不留下半成品
3. **可恢复性**：sync 失败后能从断点继续
4. **实时性**：OSS 变更后 Lance 尽快更新
5. **可重建**：任意时刻可从 OSS 全量重建 Lance

##### 同步触发源

```text
┌─────────────────────────────────────────────────────────────┐
│  触发源                                                      │
├─────────────────────────────────────────────────────────────┤
│  1. OSS 事件驱动（主路径，实时）                               │
│     ├─ ObjectCreated（staging Parquet 新增）→ 增量同步        │
│     ├─ ObjectModified（staging Parquet 修改）→ 增量同步       │
│     ├─ ObjectRemoved（staging Parquet 删除）→ 增量同步        │
│     ├─ ObjectCreated（原文件上传）→ 创建 Entity + 触发 pipeline│
│     ├─ ObjectRemoved（原文件删除）→ cascade_invalidate        │
│     └─ OSS Tag 变更（rep status 变化）→ Lance 行状态更新      │
├─────────────────────────────────────────────────────────────┤
│  2. 周期 reconcile（兜底，每 15 min）                         │
│     ├─ 全量扫描 prefix                                        │
│     ├─ 比对 sync_state Tag                                    │
│     └─ 触发漏掉的事件处理                                     │
├─────────────────────────────────────────────────────────────┤
│  3. 手动触发（运维）                                          │
│     ├─ POST /entities/{id}/sync  → 强制增量同步              │
│     └─ POST /entities/{id}/rebuild → 强制全量重建            │
└─────────────────────────────────────────────────────────────┘
```

##### Incremental Sync 协议细节

**Stage 1：Detect（变更检测）**

```python
def detect_changes(entity_id: str) -> ChangeSet:
    """检测 Entity 目录的变更，决定是否需要同步。"""

    oss_files = list_oss_files(entity_id)          # 实时扫
    lance_meta = lance.get_manifest_metadata(entity_id)
    tag = get_object_tagging(entity_id)            # 读 Entity OSS Tag

    # 1. 找出未同步的 staging Parquet
    synced_files = lance_meta.get("synced_parquet_files", [])
    new_parquet = [f for f in oss_files.staging_parquet if f not in synced_files]

    # 2. 找出被删除的 staging Parquet（已同步但 OSS 上不存在）
    deleted_parquet = [f for f in synced_files if f not in oss_files.staging_parquet]

    # 3. 找出 content_hash 变化的 raw（导致级联失效）
    if oss_files.raw_hash != tag.content_hash:
        return ChangeSet(action="full_rebuild", reason="content_hash_changed")

    # 4. 找出需要更新状态的 representation（OSS Tag status 变化）
    rep_status_changes = detect_rep_status_changes(entity_id)

    return ChangeSet(
        upsert=new_parquet,
        delete=deleted_parquet,
        status_updates=rep_status_changes,
        action="incremental" if new_parquet or deleted_parquet or rep_status_changes else "noop"
    )
```

**Stage 2：Lock（防止并发同步）**

```python
def acquire_sync_lock(entity_id: str, mode: str = "syncing") -> bool:
    """原子获取同步锁，防止同一 Entity 并发同步。"""

    tag = get_object_tagging(entity_id)
    if tag.sync_state in ("syncing", "rebuilding"):
        if is_sync_timeout(tag.sync_started_at, timeout=300):
            log.warning("Sync timeout, force unlock")
        else:
            return False  # 拒绝

    # CAS 更新 sync_state（通过 CopyObject + x-oss-copy-source-if-match）
    cas_put_object_tagging(entity_id, {
        "sync_state": mode,  # "syncing" 或 "rebuilding"
    })
    return True
```

**Stage 3：Transform（Parquet → Lance）**

```python
def transform_to_lance(entity_id: str, parquet_files: list[str]):
    """把 staging Parquet 增量转为 Lance 格式。"""

    # 1. 读取新增 Parquet
    dfs = [read_parquet(f) for f in parquet_files]

    # 2. Schema 对齐 + 类型转换（list<float> → fixed_size_list<float>）
    combined = align_schema(concat(dfs))

    # 3. 去重（按 representation_id + chunk_index）
    combined = dedupe(combined, keys=["entity_id", "rep_type", "chunk_index"])

    # 4. 追加写入 Lance
    lance_path = f"oss://.../{entity_id}/representations.lance/"
    lance.append(lance_path, combined, mode="append")
```

**Stage 4：Delete（处理删除）**

```python
def delete_from_lance(entity_id: str, deleted_parquet: list[str]):
    """删除 Lance 中属于已删除 Parquet 的行。

    实现思路：
    Lance schema 中不存 source_parquet 字段（避免冗余），
    而是用 Lance manifest metadata 记录"每个 Parquet 文件 → 行 ID 范围"的映射。
    删除某个 Parquet 时，从 manifest metadata 查行范围，再做 deletion。
    """

    lance_path = f"oss://.../{entity_id}/representations.lance/"

    # 1. 从 manifest metadata 读取 Parquet → 行范围映射
    manifest_meta = lance.get_manifest_metadata(lance_path)
    parquet_to_rows = manifest_meta.get("parquet_to_row_ranges", {})
    # e.g. {
    #   "representations_v1.parquet": {"fragment_id": 1, "row_offset": 0, "row_count": 250},
    #   "representations_v2.parquet": {"fragment_id": 2, "row_offset": 0, "row_count": 50},
    # }

    # 2. 对每个被删除的 Parquet，按行范围做 Lance deletion
    for parquet_file in deleted_parquet:
        if parquet_file in parquet_to_rows:
            range_info = parquet_to_rows[parquet_file]
            # Lance 支持按 fragment_id + offset 范围删除
            lance.delete_rows(
                lance_path,
                fragment_id=range_info["fragment_id"],
                row_offset=range_info["row_offset"],
                row_count=range_info["row_count"],
            )

    # 3. 更新 manifest metadata（移除已删除 Parquet 的记录）
    for parquet_file in deleted_parquet:
        parquet_to_rows.pop(parquet_file, None)
    lance.update_manifest_metadata(lance_path, {
        "parquet_to_row_ranges": parquet_to_rows,
    })
```

> **为什么不用 `source_parquet` 字段做查询**：
> 1. Lance schema 不存 source_parquet 字段，避免冗余。
> 2. 用 manifest metadata 记录行范围，删除时按范围操作更高效。
> 3. Manifest metadata 在 Stage 3 写入时由 L1 → L2 同步流程更新。

**Stage 5：Index（建/更新索引）**

```python
def update_indexes(entity_id: str):
    """Lance 写入后建/更新索引。"""

    lance_path = f"oss://.../{entity_id}/representations.lance/"
    existing = lance.list_indices(lance_path)

    # vector 索引（与 §4.6 索引设计保持一致：IVF_HNSW_SQ）
    if "vector" not in existing:
        lance.create_index(lance_path, column="vector",
                          index_type="IVF_HNSW_SQ",
                          num_partitions=256,
                          metric="cosine")
    else:
        lance.optimize_index(lance_path, column="vector")  # 增量优化

    # FTS 索引
    if "text_fts" not in existing:
        lance.create_fts_index(lance_path, column="text")

    # Scalar 索引
    for col in ["status", "rep_type", "modality"]:
        if col not in existing:
            lance.create_scalar_index(lance_path, column=col)
```

**Stage 6：Compact（碎片整理，自动触发）**

```python
def maybe_compact(entity_id: str):
    """碎片率过高时自动触发 compact 或 rebuild。"""

    lance_path = f"oss://.../{entity_id}/representations.lance/"
    stats = lance.get_stats(lance_path)

    fragment_count = stats.num_fragments
    row_count = stats.num_rows

    # 阈值：平均每个 fragment 少于 500 行就整理
    if row_count / fragment_count < 500:
        log.info(f"Compacting {entity_id}: {fragment_count} fragments, {row_count} rows")
        lance.compact(lance_path)  # 合并 fragment，物理重写
```

**Stage 7：Atomic Switch（原子切换）**

```python
def atomic_publish(entity_id: str, synced_parquet_files: list[str]):
    """Lance 原生 MVCC，原子切换版本。"""

    lance_path = f"oss://.../{entity_id}/representations.lance/"

    # 1. commit 新 version
    new_lance_version = lance.commit(lance_path)

    # 2. 更新 Lance manifest metadata（记录已同步的 Parquet 文件）
    lance.update_manifest_metadata(lance_path, {
        "synced_parquet_files": synced_parquet_files,
        "last_sync_at": now().isoformat(),
    })

    # 3. 更新 OSS Tag（指向新 version）
    put_object_tagging(entity_id, {
        "sync_state": "ready",
        "sync_version": new_lance_version,
    })

    # 4. 旧 Lance version 保留 5 个（回滚窗口）
    schedule_cleanup(lance_path, keep_versions=5)
```

**Stage 8：Cleanup（清理 staging）**

```python
def cleanup_staging(entity_id: str, synced_files: list[str]):
    """已同步的 staging Parquet 清理。"""

    for f in synced_files:
        # 保留最近 1 个版本（debug 用），删除更早版本
        if not is_latest_version(f):
            delete_object(f.oss_path)
```

##### 失败处理

| 失败点 | 检测 | 恢复策略 |
| --- | --- | --- |
| **网络中断（Stage 3-5）** | sync timeout | OSS Tag 标 `failed`；下次 reconcile 重新检测 |
| **Lance 写入失败** | Lance 抛异常 | 回滚 OSS Tag 到 `failed`；不更新 `sync_version` |
| **OSS Tag 写入失败（Stage 7）** | API 抛异常 | Lance 已更新但 tag 未更新 → 标记 `sync_state=stale`；reconcile 时对比 Lance version 和 OSS Tag version 修复 |
| **实体被删除（中间态）** | 扫不到 original | 触发 Entity 软删除流程；清理 Lance |
| **Rebuild 失败** | 验证不通过 | 回滚到 snapshot_version；OSS Tag 标 `failed` |

**幂等性保证**：

```python
# 同一变更多次同步，结果一致
sync(entity_id, change_set)  # 第 1 次
sync(entity_id, change_set)  # 第 2 次，幂等

# 实现：
# 1. Lance manifest metadata 记录已同步的 Parquet 文件列表
# 2. 重复 append 会触发 dedupe（entity_id + rep_type + chunk_index 主键）
# 3. 重复 delete 是幂等的（Lance deletion vector 重复标记无副作用）
```

**断点续传**：

```python
def resume_sync(entity_id: str):
    tag = get_object_tagging(entity_id)
    if tag.sync_state == "failed":
        failed_stage = tag.sync_error  # e.g. "stage_4_index"
        sync_from_stage(entity_id, failed_stage)
```

##### 监控指标

| 指标 | 说明 |
| --- | --- |
| `sync_duration_seconds{stage, mode}` | 每个 stage 的耗时（mode=incremental/rebuild） |
| `sync_total_duration_seconds{mode}` | 完整 sync 耗时 |
| `sync_failures_total{stage, reason, mode}` | 同步失败次数 |
| `sync_state_count{state}` | 各状态的 Entity 数 |
| `lance_fragment_count{entity_id}` | Lance fragment 数（碎片率监控） |
| `lance_lag_seconds{entity_id}` | OSS 变更到 Lance 同步的延迟 |
| `rebuild_total` | Rebuild 执行次数 |
| `rebuild_rollback_total` | Rebuild 回滚次数 |

##### 一致性保证总结

| 场景 | 一致性级别 | 保证方式 |
| --- | --- | --- |
| **强一致** | 同一 Entity 内的 representation ↔ Lance | sync 协议 + 锁 + 原子切换 |
| **近实时** | OSS 事件 → Lance 增量同步 | 事件驱动，< 5s 延迟 |
| **最终一致** | 事件丢失 → Lance 滞后 | Reconciler 兜底（最大延迟 15 min） |
| **可恢复** | 任意 sync 中断 | OSS Tag 持久化进度 + 断点续传 |
| **可回滚** | Lance 索引异常 / Rebuild 失败 | 保留最近 5 个 Lance version（MVCC） |
| **可重建** | Lance 损坏 / Schema 变更 | Full Rebuild 从 OSS 全量重建 |

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
      └─ 可选：按 entity_type / labels 预筛选
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
   └─ 更新 OSS Tag (sync_state = ready)
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
| raw object `content_hash` 变化 | entity.version++；沿 Pipeline 注册表的 input_rep 边向下级联：所有下游 rep 文件 OSS Tag `status`→`stale`，对应 chunks 标 `stale`（检索不再命中）；自动触发 pipeline 重跑；新版本 ready 后 publish 切换 |
| representation OSS Tag `status`→`ready` | 触发对应 chunks 的 embed + index |
| representation OSS Tag `status`→`stale` | 沿 Pipeline input_rep 边向下级联：所有下游 rep 文件 OSS Tag `status`→`stale`，chunks 标 `stale`；自动触发下游 pipeline 重建 |
| representation OSS Tag `status`→`failed` | pipeline `partial_success`；已有 representation 的 chunks 仍可用 |
| OSS Tag `rag_status`→`hidden` | entity.status=hidden；所有 chunks 标 `hidden`（不进入默认检索） |
| OSS Tag `rag_status`→`deleted` | entity.status=deleted；chunks 软删除；OSS 原文件保留 |
| embedding 模型升级 | 检测 `model_version` 过期；触发对应 chunks 重跑 embed |
| pipeline 新增 | 对已有 entity 按需重跑新 pipeline；不影响已有 representation |
| 上游 representation 变化 | 沿 Pipeline 边向下级联：下游 representation OSS Tag `status`→`stale` → chunks stale → 自动重建 |

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
| **G. 表格获取** | raw (CSV / Excel / SQL) | table_parquet, table_md, table_json | table chunks | `retrieval.passage` on table_md/table_json text；table_parquet 供 DuckDB 查询 |

### 6.2 Pipeline 编排原则

- **idempotent**：所有 pipeline 可重跑，重跑结果应一致或单调升级。
- **append-only on raw**：raw object 永不修改；重建只写新 representation。
- **parallel**：多条 pipeline 可并行执行，互不阻塞。
- **partial success 优先**：单条 pipeline 失败不阻塞其他 pipeline 的产出可用。
- **可追加**：新 pipeline 可随时注册，对已有 entity 按需重跑。

### 6.3 Pipeline 与 Entity Type 的映射

| entity_type | 默认 Pipeline | 可选 Pipeline | 备注 |
| --- | --- | --- | --- |
| document | A (直接提取) | B (OCR), C (VLM), D (知识编译), E (图片向量) | 文档默认走文本提取 |
| image | E (图片向量) | B (OCR), C (VLM), D (知识编译) | 单图走 E，多图可走 A→B |
| audio | F (音频转写) | D (知识编译) | 录音默认转文字 |
| video | F (音频转写) | E (图片向量), D (知识编译) | 视频拆音轨 + 关键帧 |
| **table** | **G (表格获取)** | D (知识编译) | **结构化数据→Parquet→DuckDB 查询** |

### 6.4 边界与混合型 Entity

#### 6.4.1 entity_type 判定

`entity_type` 由**原始文件 MIME 类型 + 探测结果**判定：

| 判定优先级 | 探测方式 | 适用文件 |
| --- | --- | --- |
| 1 | MIME 类型白名单 | .csv / .tsv / .xlsx / .parquet / .json (array) / .sql → `table` |
| 2 | 内容探测（magic bytes） | .sqlite / .duckdb → `table` |
| 3 | 文件大小 + 内容采样 | < 1MB + 强结构化 → `table` |
| 4 | 文件大小 + 文本提取 | > 1MB + 多段文本 → `document` |
| 5 | 文件名 + 扩展名 | .pdf / .docx / .pptx → `document` |
| 6 | 媒体类型 | .png / .jpg / .mp3 / .wav / .mp4 → image/audio/video |

> v0.1 仅实现 1、2、5、6 三类（4 类启发式判定留 v0.2）。`entity_type` 写入 OSS Tag `entity_type`，用户可通过 `Entity.update_tags()` 手动修正。

#### 6.4.2 混合型 Entity（同一文件含多种内容）

常见场景：
- **PDF 内嵌表格**：`entity_type=document`，Pipeline A 产出 `canonical_md`（含表格 Markdown），可选 G **二次**产出 `table.parquet`（用 camelot/tabula 抽取）
- **Excel 含图片 / 图表**：`entity_type=table`，G 产出 `table.parquet`，可选 E 二次产出 `page_image/`
- **PPT 文本框 + 图表**：默认 `document`，A 产出 `canonical_md`；可同时 D 产出 `summary`/`graph_json`
- **HTML 页面（HTML + JS + CSS）**：解析为 `document`（保留结构）+ `summary`（LLM 摘要）

**多 Pipeline 并行执行策略**：

```python
def generate_all_representations(entity: Entity):
    """根据 entity 内容自动决定跑哪些 Pipeline。"""
    pipelines = []

    # 1. 默认 Pipeline（基于 entity_type）
    pipelines.extend(DEFAULT_PIPELINES[entity.entity_type])

    # 2. 启发式发现（基于内容）
    if entity.entity_type == "document":
        if has_embedded_tables(entity.source):
            pipelines.append("G")  # PDF 内嵌表格 → 走 G
        if entity.has_images:
            pipelines.append("E")  # 文档含图片 → 走 E

    elif entity.entity_type == "table":
        if has_chart_or_image(entity.source):
            pipelines.append("E")  # 表格含图表 → 走 E
        if is_multi_sheet(entity.source):
            # Excel 多 sheet → 每个 sheet 一个 rep_type
            pipelines.extend(["G_sheet_1", "G_sheet_2", ...])

    # 3. 并行执行
    results = await asyncio.gather(*[
        run_pipeline(entity, pid) for pid in pipelines
    ])
```

#### 6.4.3 Pipeline 间依赖

**部分 Pipeline 强依赖其他 Pipeline 的产出**：

| Pipeline | 强依赖上游 | 说明 |
| --- | --- | --- |
| B (OCR) | 依赖 E (page_image) 或自己生成 page_image | 需先有图片才能 OCR |
| C (VLM) | 依赖 E (page_image) | 需先有图片才能 VLM |
| D (知识编译) | 依赖 A (canonical_md) | 编译对象是 canonical_md |
| G (表格) | 通常无依赖 | raw 直接解析，但 PDF 表格需先 A→表格抽取 |

**依赖图可视化**：

```text
                raw
                 │
    ┌────────┬───┴────┬────────┬────────┐
    ▼        ▼        ▼        ▼        ▼
    A        B        C        E        G
    │                 │       │
    │ (canonical_md)  │       │ (page_image)
    ▼                 ▼       ▼
   D (知识编译)    (B/C 都依赖 E 的 page_image)
```

**Pipeline 调度规则**：

1. **拓扑排序**：D 必须等 A 完成；B/C 必须等 E（或自己生成 page_image）
2. **失败隔离**：B 失败不影响 A/D 的产出可用
3. **重试策略**：A 重试时不应触发 D 重试（除非 A 的产出变化）

### 6.5 Pipeline 之间的级联与避免重复

| 场景 | 处理 |
| --- | --- |
| A 产出 canonical_md 后触发 D | D 的 `derived_from=canonical_md`（从目录层级推导：compile/ 的 input 在 extract/） |
| B 与 C 同时产出（基于 page_image） | 两者并存，分别打 Rep OSS Tag；D 可选地基于任一产出 summary |
| 表格中的图片 | G + E 并行：G 产 `table.parquet`，E 产 `page_image/`（图片向量） |
| 公式 / 嵌入对象 | 暂不支持（v0.2+ 引入 Mathpix API / 公式抽取） |

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
{entity_id}/source/original                      →  /{name}                    # 原始文件
{entity_id}/extract/canonical.md                 →  /{name}/canonical.md       # 视角文件
{entity_id}/extract/page_image/                  →  /{name}/pages/             # 页面图片
{entity_id}/recognize/ocr.md                     →  /{name}/ocr.md             # OCR 结果
{entity_id}/recognize/vlm_extracted.md           →  /{name}/vlm_extracted.md   # VLM 结果
{entity_id}/compile/mind_map.json                →  /{name}/mind_map.json      # 脑图
{entity_id}/compile/graph.json                   →  /{name}/graph.json         # 关系图
{entity_id}/compile/summary.md                   →  /{name}/summary.md         # 摘要
{entity_id}/compile/wiki.md                      →  /{name}/wiki.md            # Wiki 页面
{entity_id}/compile/table.parquet                →  /{name}/table.parquet      # Parquet 表格
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
│   ├── wiki.md                     ← Wiki 页面
│   └── table.parquet                ← Parquet 表格
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
   └─ 从 representations 补充 representation 元数据（pipeline_id / transform / quality）
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
        "pipeline_id": "pipeline_a",
        "page_number": 7,
        "section_header": "Q3 Pricing",
        "mime_type": "text/markdown",
        "status": "active",
        "source_uri": "oss://bucket/vector-lake/ws_001/kb_001/abc123/source/original",
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
| `entity_type` / `name` / `rag_status` / `labels` | Entity OSS Tag（source/original 对象） | entity 元数据 |
| `rep_type` / `pipeline_id` / `transform` / `modality` / `status` | Representation OSS Tag | representation 业务元数据 |
| `page_number` / `section_header` | 行号 → chunk 定位 | 从 start_pos 反查最近的 chunk |
| `content_hash` | Entity OSS Tag | 原始文件信息 |
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
| `semantic` | Lance | representations.lance vector 列 | 自然语言 | top-k chunk + score |
| `lexical` | Lance | representations.lance text (FTS) | 关键词 | top-k chunk + BM25 |
| `hybrid` | Lance | representations.lance vector + text | 自然语言 | top-k chunk + 融合 score |
| `visual` | Lance | representations.lance (modality=image) | image / text | top-k chunk |
| `audio` | Lance | representations.lance (modality=audio) | audio / text | top-k chunk |
| `table` | Lance | representations.lance (modality=table) | SQL-like / 关键词 | 表行 + 来源 |
| `duckdb` | DuckDB | compile/table.parquet | SQL | 结构化查询结果 |
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
    reps_table.search(query_type="hybrid")
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
| `table_md` / `table_json` / `table_parquet` | 表格渲染 | table_parquet：DuckDB 抽样 100 行转 HTML 表格；JSON 转 HTML 表格；Markdown 表格直接渲染 |
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
      "chunk_id": "rep_xxx_chunk_3",
      "chunk_index": 3,
      "entity_id": "abc123",
      "entity_version": 1,
      "rep_type": "canonical_md",
      "pipeline_id": "pipeline_a",
      "modality": "text",
      "score": 0.83,
      "snippet": "## Q3 Pricing\nEnterprise: $4.2B...",
      "page_number": 7,
      "section_header": "Q3 Pricing",
      "provenance": {
        "source_uri": "oss://bucket/vector-lake/ws_001/kb_001/abc123/source/original",
        "source_version": "etag_xxx",
        "content_hash": "sha256_xxx",
        "model_version": "embedding-v5-retrieval"
      }
    }
  ]
}
```

### 8.7 DuckDB 统一访问 — 表格型 Entity 的 SQL 查询

**适用场景**：`entity_type=table` 的 Entity（CSV / Excel / 数据库表），需要 SQL 灵活查询。

#### 架构

```text
┌─────────────────────────────────────────────────────────────┐
│  DuckDB (进程内嵌入，无服务端)                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Entity A     │  │  Entity B     │  │  Entity N     │       │
│  │ compile/      │  │ compile/      │  │ compile/      │       │
│  │ table.parquet │  │ table.parquet │  │ table.parquet │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │                │
│         ▼                 ▼                 ▼                │
│  ┌─────────────────────────────────────────────────┐       │
│  │  DuckDB 注册多个 Parquet (httpfs + OSS)           │       │
│  │  → 联邦查询 : SELECT ... FROM entities WHERE ...  │       │
│  └─────────────────────────────────────────────────┘       │
│                                                             │
│  查询方式：                                                  │
│  1. 单 Entity 查询 : Entity.query_table(sql)                │
│  2. 跨 Entity 联邦 : DuckDB 注册多表，SQL JOIN/UNION         │
│  3. 与 Lance 协同 : DuckDB 过滤 ID 集合 → Lance 语义检索     │
└─────────────────────────────────────────────────────────────┘
```

#### 设计原则

- **进程内嵌入**：DuckDB 以 Python binding 形式嵌入智能引擎进程，零运维。
- **OSS 原生读取**：DuckDB `httpfs` 插件直接读 OSS Parquet，无需下载到本地。
- **Schema 推断**：Pipeline G 写入 `compile/table.parquet` 时自动记录 schema（列名 / 类型）。
- **列裁剪 + 谓词下推**：DuckDB 在 OSS 侧完成，只传输查询需要的列和行，节省带宽。

#### 核心 API

```python
# ── 1. 单 Entity SQL 查询 ──────────────────────────────
class Entity:
    def query_table(self, sql: str) -> list[dict]:
        """对该 Entity 的 table.parquet 执行 SQL。"""

import duckdb

conn = duckdb.connect()

# 注册 OSS Parquet（通过 DuckDB httpfs）
conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute(f"""
    CREATE VIEW entity_{entity.entity_id} AS
    SELECT * FROM read_parquet('s3://bucket/.../{entity.entity_id}/compile/table.parquet')
""")

# 执行用户 SQL（只读，安全沙箱）
result = conn.execute(sql).fetchall()
columns = [desc[0] for desc in conn.description]
return [dict(zip(columns, row)) for row in result]


# ── 2. 跨 Entity 联邦查询 ──────────────────────────────
class Collection:
    def query_tables(self, sql: str, entity_ids: list[str] = None) -> list[dict]:
        """跨多个 table 型 Entity 执行 SQL 联邦查询。

        SELECT a.quarter, a.revenue, b.cost
        FROM entity_abc a JOIN entity_def b ON a.quarter = b.quarter
        WHERE a.revenue > 1000000
        """

conn = duckdb.connect()

# 批量注册多个 Entity 的 table.parquet
for eid in entity_ids:
    conn.execute(f"""
        CREATE VIEW entity_{eid} AS
        SELECT *, '{eid}' AS _entity_id
        FROM read_parquet(
            's3://bucket/vector-lake/{ws}/{col}/{eid}/compile/table.parquet'
        )
    """)

return conn.execute(sql).fetchall()


# ── 3. SQL 过滤 + Lance 语义检索协同 ───────────────────
# DuckDB 先做结构化过滤（WHERE revenue > 1M），拿到 entity_id 集合
# 再用 Lance 在这些 Entity 中做语义检索
filtered_ids = duckdb.sql("""
    SELECT DISTINCT _entity_id
    FROM entities
    WHERE revenue > 1000000
""").fetchall()

# 在过滤结果上做语义检索
results = await cross_entity_semantic_search(query, entity_ids=filtered_ids)
```

#### 安全沙箱

| 安全措施 | 实现 |
| --- | --- |
| **只读** | DuckDB 连接只注册 `read_parquet()`，不开放写入 |
| **SQL 白名单** | 只允许 SELECT / WITH，禁止 INSERT / UPDATE / DELETE / DROP |
| **资源限制** | Statement timeout（30s），memory limit（512MB） |
| **OSS 鉴权** | DuckDB httpfs 用 STS 临时凭证，随 session 过期 |
| **Schema 可见性** | 每个 Entity 只暴露自己的 `entity_{id}` 视图 |

#### Pipeline G：表格获取（raw → table_parquet）

```text
Pipeline G 输入：raw (CSV / Excel / SQL dump / JSON array)
Pipeline G 输出：compile/table.parquet + compile/table.md + compile/table.json

Stage 1: Parse
  ├─ 根据 raw 文件格式选择解析器
  │   ├─ CSV → DuckDB read_csv_auto() → 自动推断 header + 类型
  │   ├─ Excel → openpyxl / calamine → 第一个 sheet → DataFrame
  │   ├─ SQL dump → sqlparse → 提取 CREATE TABLE + INSERT → DuckDB 重建
  │   └─ JSON array → Pandas read_json → DataFrame
  └─ 输出：内存 DataFrame

Stage 2: Normalize
  ├─ 列名标准化（去空格 / 小写 / 下划线）
  ├─ 类型推断优化（日期列 → DATE；货币列 → DECIMAL）
  └─ 空值规范化（空字符串 → NULL）

Stage 3: Parquet Write
  ├─ DataFrame → DuckDB COPY TO 'compile/table.parquet' (FORMAT PARQUET)
  ├─ 使用 Snappy 压缩 + 列统计（min/max/null_count）供谓词下推
  └─ 输出：compile/table.parquet（写入 OSS）

Stage 4: Schema 记录
  ├─ DuckDB DESCRIBE → 生成 table.json（schema 元数据，存到 compile/）
  └─ 输出：compile/table.json

Stage 5: Chunk + Index
  ├─ table.md（rep_type=table_md）：Markdown 表格格式，进入 Lance chunk + embed
  └─ table.json（rep_type=table_json）：供 tool 使用

Stage 6: 写 Rep OSS Tag（与 §4.6 同步协议对齐）
  ├─ 为 compile/table.parquet 写 Rep OSS Tag：
  │   rep_type=table_parquet
  │   pipeline_id=pipeline_g
  │   transform=parse_csv|parse_xlsx|parse_sql
  │   modality=table
  │   status=ready
  │   model_version=duckdb_v1
  │   entity_version={entity.version}
  ├─ 为 compile/table.md 写 Rep OSS Tag
  ├─ 为 compile/table.json 写 Rep OSS Tag
  └─ 触发 Lance Watcher 增量同步
```

#### Pipeline G 的写并发控制

**问题**：表格型 Entity 可能在以下场景出现并发写：
- 同一 Entity 被多个 Pipeline G Worker 同时重跑（如调度器 bug）
- Pipeline G 和 Pipeline A 同时产出（混合型 Entity）

**解决方案**：

```text
1. Entity 目录互斥锁（基于 OSS Tag）
   ├─ Pipeline G 开始前 CAS 设置 Entity Tag sync_state=syncing
   ├─ 写 table.parquet 完成后 CAS 设置回 ready
   └─ 失败时回滚到 failed

2. table.parquet 文件级锁
   ├─ 使用 CopyObject + x-oss-copy-source-if-match 实现 CAS
   └─ 写新版本前 read etag，写入时 if-match

3. MVCC 写入策略
   ├─ 写入新 table.parquet.v2，Lance 同时记录新旧两个版本
   ├─ 校验通过后原子切换（删除 v1）
   └─ 失败保留 v1 为权威源
```

**多 Worker 并行处理的实体级隔离**：
- 同一 Entity 的所有 Pipeline 串行执行（避免冲突）
- 不同 Entity 的 Pipeline 完全不同（OSS 目录隔离）
- Worker Pool 按 Entity ID 分片（一致性哈希）

#### 表格预览细化

`table_parquet` 预览策略：

| 表格大小 | 抽样方式 | 渲染 | 延迟 |
| --- | --- | --- | --- |
| < 1K rows | 全部返回 | HTML 表格（100% 完整） | < 50ms |
| 1K - 100K rows | 头 50 + 尾 50 + 随机 0 | HTML 表格（100 行） | < 200ms |
| > 100K rows | 头 30 + 随机 70 | HTML 表格 + 分页控件（默认第 1 页） | < 500ms |
| 任意大小 | 用户指定 OFFSET/LIMIT | 用户控制分页 | < 200ms |

**SQL 抽样**：
```sql
-- 头 50 行
SELECT * FROM read_parquet('...') ORDER BY _row_id LIMIT 50;
-- 尾 50 行
SELECT * FROM read_parquet('...') ORDER BY _row_id DESC LIMIT 50;
-- 头 30 + 随机 70
(SELECT * FROM read_parquet('...') ORDER BY _row_id LIMIT 30)
UNION ALL
(SELECT * FROM read_parquet('...') USING SAMPLE 70);
```

**预览元数据**：
- 总行数、列数、文件大小
- 数值列的 min/max/mean/std
- 字符串列的 distinct count + top 5
- 缺失值分布（每列 null_count / total）

#### table_parquet 的 schema 约定

```python
# compile/table.parquet 的隐含约束
# 1. 每行 = 一条业务记录
# 2. 列名标准化为 snake_case
# 3. 自动添加 _row_id 列（全局唯一行号，用于 tool evidence 引用）
# 4. Parquet 文件元数据中存储：
#    - source_format: "csv" | "xlsx" | "sql"
#    - source_hash: sha256 of raw
#    - row_count: 行数
#    - column_count: 列数
#    - created_at: 生成时间
```

#### 与 Lance 检索的协作

```text
┌─────────────────────────────────────────────────────────┐
│  Hybrid Query：SQL 过滤 + 语义检索                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  用户查询："revenue > 10M 的合同中，哪些提到定价策略？"    │
│                                                         │
│  Step 1: DuckDB 结构化过滤                                │
│    SELECT _row_id, contract_name                         │
│    FROM entity_finance                                  │
│    WHERE revenue > 10000000                              │
│    → 返回 15 行 (entity_id=_row_id)                      │
│                                                         │
│  Step 2: Lance 语义检索（在 DuckDB 过滤结果中）             │
│    search("定价策略", entity_ids=filtered_entity_ids)     │
│    → 返回 top 5 chunks                                  │
│                                                         │
│  Step 3: 融合返回                                        │
│    evidence = [{table_row, chunk_snippet, score}, ...]  │
└─────────────────────────────────────────────────────────┘
```

#### 性能参考

| 场景 | 数据量 | DuckDB 耗时 | 说明 |
| --- | --- | --- | --- |
| 单表全表扫描 | 10M rows, 500MB Parquet | ~2s | 列裁剪 + 谓词下推后 < 0.5s |
| GROUP BY 聚合 | 10M rows | ~1s | 列式存储列裁剪优化 |
| 两表 JOIN（等值） | 1M × 100K | ~3s | 内存 hash join |
| 联邦 10 Entity | 100K each | ~5s | httpfs 并行读取 |
| SQL + Lance 协同 | 100K → 过滤 1K → 语义检索 | ~1s | 先缩范围再语义 |

---

## 9. 智能引擎（Intelligent Engine）

### 9.1 目标

> **对上层应用屏蔽"该用哪个检索能力"的复杂度**。

### 9.1.1 三类一等检索能力

| 能力类别 | 引擎 | 适用 Query | 证据单元 |
| --- | --- | --- | --- |
| **语义检索 (semantic)** | Lance + Embedding V5 | 概念 / 解释 / 模糊匹配 | `Chunk` (含 vector) |
| **结构化检索 (structural)** | **DuckDB + Parquet** | 数值 / 范围 / 聚合 / JOIN / 统计 | `TableRow` (含完整字段) |
| **全文检索 (textual)** | VFS grep / Lance FTS | 精确字段 / 编号 / 模式匹配 | `GrepHit` (含 line_number) |

> **核心原则**：三种能力**对等、可组合、可融合**。智能引擎根据 Query 类型**路由 1..N 个能力**并融合结果。

### 9.2 流程

```text
User Query
   │
   ▼
[1] Query Understanding
    ├─ intent (lookup / aggregate / compare / reason / multimodal)
    ├─ entities mentioned
    ├─ modality hint (text / image / audio)
    ├─ query_type (semantic / numeric / structural / textual / multimodal)
    └─ aggregation hint (group_by / top_n / range / sum / count)
   │
   ▼
[2] Capability Routing（按 query_type 选择）
    ├─ semantic → Lance semantic search
    ├─ textual → VFS grep / Lance FTS
    ├─ structural → DuckDB SQL (单表 / 联邦 / 聚合)
    ├─ visual → Lance image↔text
    ├─ audio → Lance audio↔text
    ├─ graph → graph_json traversal
    └─ hybrid → 多个能力并行（structural + semantic / textual + semantic）
   │
   ▼
[3] Parallel Execution
    └─ 调 semantic / textual / structural / visual / audio / graph
   │
   ▼
[4] Result Fusion & Rerank
    ├─ 跨能力去重（按 entity_id + 证据单元 ID）
    ├─ 同一 Entity 多视角证据合并（Chunk + TableRow + GrepHit）
    ├─ 数值证据 vs 语义证据 vs 文本证据的归一化打分
    └─ Rerank (RRF / CrossEncoder)
   │
   ▼
[5] Pack & Return
    └─ evidence pack → 上层 RAG / Agent
```

#### 9.2.1 Structural Query 路由示例

```text
User Query: "2024 Q3 revenue 超过 1M 的合同中，哪些提到定价策略？"

[1] Query Understanding
    ├─ intent: filter + reason
    ├─ query_type: structural + semantic（混合）
    ├─ aggregation: range (revenue > 1M) + top_n
    └─ modality: text

[2] Capability Routing
    ├─ 触发条件: query_type ∈ {structural, numeric, aggregate}
    └─ 路由选择:
        ├─ Primary: DuckDB SQL 过滤 revenue > 1M
        │   SELECT _entity_id, _row_id, contract_name
        │   FROM entities WHERE revenue > 1000000
        └─ Secondary: Lance 语义检索"定价策略"
            search("定价策略", entity_ids=filtered_entity_ids)

[3] Parallel Execution
    ├─ DuckDB: 拿到 15 个 entity_id 集合
    └─ Lance: 在这 15 个 Entity 中检索语义 chunks

[4] Result Fusion
    └─ evidence = [
        {type: "table_row", entity_id, _row_id, contract_name, revenue},
        {type: "chunk", entity_id, chunk_id, text, score}
       ]

[5] Pack & Return
    └─ 上层 Agent 看到: 数值证据（revenue）+ 文本证据（定价策略）
```

#### 9.2.2 证据单元统一抽象

```python
from typing import Literal, Union
from pydantic import BaseModel

class ChunkEvidence(BaseModel):
    """Lance 语义检索的证据。"""
    type: Literal["chunk"] = "chunk"
    entity_id: str
    rep_type: str
    chunk_index: int
    text: str
    score: float
    page_number: int | None = None
    section_header: str | None = None
    provenance: dict  # source_uri, content_hash, model_version

class TableRowEvidence(BaseModel):
    """DuckDB 结构化查询的证据。"""
    type: Literal["table_row"] = "table_row"
    entity_id: str
    _row_id: int
    row: dict  # 所有列值
    sql: str    # 触发的 SQL（可重放）
    score: float = 1.0  # 结构化结果默认 1.0
    provenance: dict  # table.parquet uri, sha256

class GrepHitEvidence(BaseModel):
    """VFS 文本匹配的证据。"""
    type: Literal["grep_hit"] = "grep_hit"
    entity_id: str
    rep_type: str
    file_path: str
    line_number: int
    line_text: str
    context_before: list[str]
    context_after: list[str]
    score: float
    provenance: dict

# 统一证据类型
Evidence = Union[ChunkEvidence, TableRowEvidence, GrepHitEvidence]

class EvidencePack(BaseModel):
    """上层 RAG / Agent 接收的统一证据包。"""
    query: str
    query_type: list[str]  # ["structural", "semantic"]
    capabilities_used: list[str]  # ["duckdb", "lance_semantic"]
    evidences: list[Evidence]
    fusion_method: str  # "rrf" / "cross_encoder" / "manual"
    sql_executed: str | None = None  # 触发的 SQL（可重放）
```

### 9.3 路由策略（v0.1 规则版）

| Query 类型 | 识别特征 | 优先能力 | 次选 | 证据类型 |
| --- | --- | --- | --- | --- |
| **概念 / 解释** | "什么是 / 介绍 / 解释" | hybrid (semantic + lexical) | grep | Chunk + GrepHit |
| **精确字段 / 编号** | "编号 / ID / 邮箱 / 电话" | lexical + grep | semantic | GrepHit |
| **找一张图** | "图 / 截图 / 海报" | visual (image↔text) | caption semantic | Chunk(image) |
| **找一段录音** | "录音 / 音频" | audio (text↔audio) | transcript lexical | Chunk(audio) |
| **跨实体关系** | "关系 / 引用 / 提及" | graph | hybrid | Chunk + Edge |
| **数值范围** | "> 1M / < 10% / between X and Y" | **DuckDB SQL** | hybrid | **TableRow** |
| **聚合统计** | "总数 / 平均 / Top N / GROUP BY" | **DuckDB SQL** | hybrid | **TableRow** |
| **跨表 JOIN** | "A 和 B 的关联 / JOIN" | **DuckDB 联邦** | graph | **TableRow** |
| **表格行 / 列** | "行 / 列 / 单元格" | **DuckDB SQL** | lexical | **TableRow** |
| **混合** | "revenue > 1M 中提到定价的" | **DuckDB + Lance semantic** | graph | **TableRow + Chunk** |

> v0.2+ 替换为学习型 router（基于 query embedding + LLM 分类）。

### 9.4 智能引擎与 §8 检索能力的映射

| §8 能力 | 智能引擎调用 | 路由触发条件 | 输出证据类型 |
| --- | --- | --- | --- |
| §8.1 VFS (ls/stat/read/glob) | 上下文感知（先 ls 找 Entity） | 隐式 | — |
| §8.1 VFS grep | `capability_textual` | 精确字段 / 编号 | GrepHit |
| §8.3 Hybrid Search (Lance) | `capability_semantic` | 概念 / 解释 | Chunk |
| §8.3 Hybrid Search + FTS | `capability_semantic_textual` | 模糊 + 精确 | Chunk |
| §8.4 预览 | 嵌入到 evidence pack | 命中后预览 | PreviewContent |
| §8.5 工具协议 | 上层 RAG / Agent 调用 | tool_use | Evidence |
| §8.6 Lineage 可视化 | `capability_lineage` | 追溯 / 影响分析 | LineageDAG |
| **§8.7 DuckDB SQL** | **`capability_structural`** | **数值 / 聚合 / JOIN** | **TableRow** |
| **§8.7 DuckDB 联邦** | **`capability_structural_federated`** | **跨表 JOIN** | **TableRow（多 Entity）** |
| **§8.7 DuckDB + Lance** | **`capability_hybrid_structural_semantic`** | **结构化 + 语义** | **TableRow + Chunk** |

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

## 11. Projector 层（多目标投影）

> **核心定位**：Vector-Lake 是**主体**，Projector 层是它面向不同外部消费者（RAG API / Wiki / Dashboard / Web 前端）暴露数据形态的**适配器集合**。Projector 订阅 Lake 内部事件（entity 创建、representation 完工、edge 写入、lint 完成），把内部数据**单向投影**为各消费者约定的格式。
>
> **与检索层的关系**：§8 检索能力 / §9 智能引擎 是 Lake **被问** 时主动提供答案的 HTTP API；Projector 是 Lake **主动告知** 第三方（按事件驱动）的出站通道。两者正交。

### 11.1 设计目标

1. **Lake 内聚**：所有领域概念（Entity / Representation / Chunk / Edge / Event）只活在自己的边界内，不为外部消费者变形。
2. **消费解耦**：新增消费者 = 新增一个 Projector，不改 Lake 核心代码。
3. **最终一致**：投影允许秒级延迟；Lake 写入快，投影异步、可重放。
4. **可回放**：每个 Projector 的输出是 Lake 事件的纯函数，支持全量重建（rebuild）。
5. **不破坏消费者独立性**：消费者（如 Wiki）即使脱离 Lake 也能继续运行——因为拿到的是落地的 `.md` 文件，不是绑定到 Lake 的句柄。
6. **幂等**：同一事件重复投影不产生副作用；artifact 命名带 idempotency key。

### 11.2 Projector 抽象

```python
from typing import Protocol, Optional
from datetime import datetime

class Projector(Protocol):
    """Lake 内部数据 → 外部消费者格式"""

    name: str                                    # 唯一标识（注册表 key）
    consumer_type: str                           # 'wiki' | 'rag_api' | 'dashboard' | 'web'

    # ── 单事件投影（事件驱动调用）──
    def project_entity(self, entity: Entity) -> list[Artifact]: ...
    def project_representation(self, rep: Representation) -> list[Artifact]: ...
    def project_edge(self, edge: Edge) -> list[Artifact]: ...
    def project_event(self, event: Event) -> list[Artifact]: ...
    def project_lint(self, result: LintResult) -> list[Artifact]: ...

    # ── 全量重建接口（rebuild / schema 演进）──
    def rebuild(self, since: Optional[datetime] = None) -> int:
        """返回产出的 artifact 数量"""
        ...
```

`Artifact` 是 Projector 输出的"落地物"（OSS 写文件 / HTTP 推送 / WebSocket 消息 / DB 行）。

### 11.3 内置 Projector 清单

| Projector | 消费者 | 输出形态 | 落地方式 | 状态 |
|---|---|---|---|---|
| `RagApiProjector` | 上层 RAG / Agent | JSON Evidence | HTTP `/tools/*` 路由（§8） | v0.1 |
| `WikiProjector` | Karpathy LLM Wiki / Obsidian | `.md` 文件 + wikilink + log.md | OSS / 本地 vault | v0.1（详设见 §12） |
| `DashboardProjector` | 运维面板 | 指标 / 状态卡片 | TSDB / WebSocket | v0.2 |
| `WebProjector` | 前端 SPA | 视图模型 | HTTP `/v1/views/*` | v0.2 |

> WikiProjector 是本次设计重点，详设见 §12。

### 11.4 投影生命周期（事件驱动）

```text
Lake 内部事件源                        Projector 运行时
─────────────────                      ─────────────────
Entity.published       ───┐
Representation.ready   ───┤
Edge.created           ───┼──→  Event Bus（pub/sub）  ──→  [WikiProjector]
Event.appended         ───┤                                  │
Lint.completed         ───┤                                  ├─→ 1. 收事件
Supersede.occurred     ───┘                                  │   2. 调 project_xxx()
                                                            │   3. 落 Artifact（带 idempotency）
                                                            │   4. 失败 → DLQ + 告警
                                                            ↓
                                                     Artifact 落地
                                                     (OSS / HTTP / WS)
```

**幂等保证**：每个 Artifact 用 `sha256(input_event_id + projector_name + target_path)` 命名；重复投影覆盖同一目标，不产生重复条目。

### 11.5 投影一致性等级

| 等级 | 适用 | 实现 |
|---|---|---|
| **最终一致**（默认） | 绝大多数 Projector | 事件驱动 + 异步执行，秒级延迟 |
| **强一致** | RAG API 的"写后即查" | 不走 Projector，直接调 Lake 内部 API（§8） |
| **离线全量重建** | 投影损坏 / schema 演进 / 新接 Projector | `rebuild()` 接口，基于 `content_hash` 重放所有事件 |

### 11.6 投影失败的恢复

| 失败类型 | 检测 | 恢复 |
|---|---|---|
| 单事件投影失败 | DLQ 入队 + 告警 | 人工 replay 或自动重试 3 次后入 cold-DLQ |
| 投影器进程崩溃 | 健康检查 | 启动时从 last_committed_offset 续接 |
| 目标存储不可用 | 网络/权限错误 | 指数退避重试；最终进 DLQ |
| 数据漂移（artifact 与 Lake 不一致） | 周期性 hash 比对 | 触发 `rebuild()` |

---

## 12. Wiki Projector 详设

> **重新定位**：Vector-Lake 是**主体**，Wiki Projector 是其内部 Projector 层的成员。**Wiki 不是 Lake 的宿主，Wiki 也不是 Lake 的客户——Wiki 是 Lake 内部数据的一种"渲染格式"**。Lake 决定 wiki 长成什么样，wiki 用户可以选择消费或忽略这种格式。
>
> 这是对前两版（"Wiki 宿主 + Lake 后端" / "SBI 双边契约"）的最终修正：Lake 主体地位不动摇，Wiki Provider 是 Lake 内部 Projector 层的一个适配器。

### 12.1 设计目标

1. **Lake 主体地位不动摇**：所有 wiki 内容**派生自** Lake 内部事件。
2. **Wiki 独立可运行**：投影产出的 `~/wiki/` 是 Karpathy 原始约定的目录，可被 Obsidian 独立打开。
3. **两种投影模式**：
   - **Push**：Lake 主动写 `~/wiki/`（适合 wiki 完全是 Lake 镜像）
   - **Pull**：Lake 提供 `GET /v1/wiki/project/*` 拉取端点（适合 wiki 客户端灵活消费）
4. **用户手改可吸收**：用户编辑过的 `.md` 被识别为 `rep_type=user_edited_md` 的新 Representation，不会被覆盖（默认）。
5. **SCHEMA / index / log 由 Lake 维护**：减少用户手工负担；用户可基于 Lake 草稿修订。
6. **幂等 + 顺序保证**：相同事件多次投影结果一致；log.md 严格按事件时间追加。

### 12.2 投影范围

| Lake 内部对象 | 投影到 Wiki 哪里 | 触发事件 | v0.1 |
|---|---|---|---|
| `entity` (active) | `entities/{slug}.md`（按 entity_type 路由文件夹） | `entity.published` | ✅ |
| `representation(canonical_md)` | 文件正文 | `representation.ready` | ✅ |
| `representation(graph_json)` | `[[wikilink]]` 渲染 | `representation.ready` | ✅ |
| `edge` | `[[wikilink]]` + provenance 标记 | `edge.created` | ✅ |
| `entity.version 切换` | `log.md` 追加 + `index.md` 更新 | `entity.superseded` | ✅ |
| `lint_result` | `_lint/{page_id}.md` 报告 | `lint.completed` | v0.2 |
| `pipeline_run` | `_meta/runs/{date}.md` 运维日志 | `pipeline.completed` | v0.2 |

### 12.3 字段映射表（Lake 内部 → Wiki 格式）

| Lake 内部 | Wiki 投影 | 备注 |
|---|---|---|
| `entity.entity_type` | 文件夹（`entities/` / `concepts/` / `comparisons/` / `queries/`） | 映射规则见 §12.3.1 |
| `entity.title` | frontmatter `title:` | |
| `entity.aliases` | frontmatter `aliases: [...]` | 用于 wikilink 容错 |
| `entity.tags` | frontmatter `tags: [...]` | 来自 SCHEMA.md 词表 |
| `representation(canonical_md).content` | `.md` 正文 | 去 frontmatter 后的纯 markdown |
| `representation.sources[].raw_uri` | 行内 `^[raw/...]` 标记 | 出现在每个有出处的段落 |
| `entity.entity_version` | frontmatter `version: N` | |
| `entity.is_active=true` | 出现在 `entities/{slug}.md` | |
| `entity.is_active=false` | 移到 `_superseded/{slug}@v{N}.md` | 不删，可回看 |
| `entity.status='hidden'` | **不投影** | Lake 内仍可见、检索 |
| `entity.status='deleted'` | **不投影** | Lake 内仍可见、检索 |

#### 12.3.1 entity_type → 文件夹映射

```python
WIKI_FOLDER_BY_ENTITY_TYPE = {
    # 显式 wiki 概念（v0.1 新增）
    "wiki_entity":     "entities",
    "wiki_concept":    "concepts",
    "wiki_comparison": "comparisons",
    "wiki_query":      "queries",
    # 原始文档类型（v0.1 透传：每个 document 是一篇 wiki entity）
    "document":        "entities",
    # 不单独投影（嵌入到所属概念页）
    "image":           None,
    "audio":           None,
    "table":           None,
}
```

### 12.4 关系边（edge）到 Wikilink 渲染

| `edges.relation` | 投影形式 | 说明 |
|---|---|---|
| `mentions` | `[[target]]` | 普通引用 |
| `cites` | `[[target]]^[chunk_id]` | 带 chunk 引用，可点击定位原文 |
| `contradicts` | `[[target]] ⚡` | 冲突标记，触发 Lint R004 |
| `supports` | `[[target]] ✓` | 支持标记 |
| `synthesizes` | `[[target]] ⊕` | 综合关系（src ≥ 3） |
| `supersedes` | **不投影到正文** | 仅用于文件路径版本管理 |
| `derived_from` | frontmatter `sources: [raw/...]` | 来源清单 |

### 12.5 推送策略

| 策略 | 行为 | 适用 | v0.1 |
|---|---|---|---|
| `atomic_per_page` | 单页写入：先 `.md.tmp` → 校验 → `rename` 覆盖 | 默认，单 Entity 写 | ✅ |
| `whole_vault` | 重建整个 `~/wiki/`（基于 content_hash） | schema 演进、首次投影、灾难恢复 | v0.2 |
| `incremental` | 仅写变化页 + 增量 `log.md` | 日常 ingest | v0.1（v0.1 简化为"每条事件触发单页写"） |

**写入原子性**（critical，OSS 与本地 vault 同理）：

```python
import os, uuid

def atomic_write_artifact(target_path: str, content: bytes):
    tmp = f"{target_path}.tmp.{uuid.uuid4().hex[:8]}"
    with open(tmp, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())      # 强制落盘
    os.replace(tmp, target_path)   # POSIX 原子 rename
```

OSS 场景下等价为：`PutObject` 到 `.tmp` → `CopyObject` + `x-oss-copy-source-if-match` 原子替换。

### 12.6 反向回写（用户手改识别）

```text
用户在 Obsidian 编辑 ~/wiki/entities/foo.md
        ↓
WikiProjector 检测器（每 5 min 扫一次 vault；v0.1 简化为手动触发）
        ↓
mtime 变化 OR content_hash 变化
        ↓
调用 Lake: POST /v1/wiki/import
  {
    entity_id: "wiki_concept:transformer-arch",
    rep_type: "user_edited_md",
    content: <读取 .md 内容>,
    source: "user_edit",
    supersedes: "canonical_md@v3"
  }
        ↓
Lake 内部：
  v3 canonical → status=superseded
  v4 user_edited → status=active, is_active=true
  Edge: v3 → v4, relation=supersedes
        ↓
下次 Push 投影：
  默认 wiki.protect_user_edits=true → 不覆盖 vault（保护手改）
  配置 wiki.protect_user_edits=false → 用 v4 覆盖
```

**关键不变量**：
- Lake 内部数据是 Source of Truth
- User edit 作为 `user_edited_md` 类型的 Representation 留在 Lake，可被检索、可被血缘追溯
- Push 模式默认**不**用 v4 user_edited 覆盖 vault（避免循环覆盖）

### 12.7 SCHEMA.md / index.md / log.md 维护责任

| 文件 | 维护方 | 写入策略 | v0.1 |
|---|---|---|---|
| `SCHEMA.md` | 人 + Lake 草稿 | Lake 投影出**初稿**（基于 Pipeline 注册表 + Representation 矩阵），用户可手工修订 | ✅ 初稿生成 |
| `index.md` | Lake 全权 | 每次 `entity.published` 事件触发增量更新 | ✅ |
| `log.md` | Lake 全权 | append-only，事件映射见 §12.7.1 | ✅ |
| `entities/*.md` | Lake 全权（默认） | Push 模式覆盖；user_edit 保护模式不覆盖 | ✅ |
| `concepts/*.md` | Lake 全权 | 同上 | ✅ |
| `comparisons/*.md` | Lake 全权 | 同上 | ✅ |
| `queries/*.md` | 人 + LLM（Lake 投影为初稿） | 混合所有 | v0.2 |
| `raw/` | **人** | Lake **绝不写**（不可变性硬约束） | — |
| `_superseded/` | Lake 全权 | 写但不主动清理 | ✅ |
| `_lint/*.md` | Lake 全权 | 每次 lint_run 写一份 | v0.2 |

#### 12.7.1 event → log.md 行映射

```python
LOG_TEMPLATE = {
    "ingest":       "📥 [{ts}] ingest: {page_id} v{ver}",
    "publish":      "✅ [{ts}] publish: {page_id} v{ver} (supersedes v{prev})",
    "supersede":    "🔄 [{ts}] supersede: {page_id} v{old} ← v{new}",
    "delete":       "🗑️ [{ts}] delete: {page_id} (reason={reason})",
    "lint_run":     "🔍 [{ts}] lint: {rules_count} rules, {err} error, {warn} warn",
    "lint_error":   "❌ [{ts}] lint_error: {page_id} rule={rule} ({msg})",
    "project_fail": "💥 [{ts}] project_fail: {page_id} ({err})",
}
```

### 12.8 数据流（一次 ingest 到 wiki 落地）

```text
[用户/Agent]
   │  POST /v1/entities (raw 文档)
   ↓
[Vector-Lake Ingest Gateway]                  ← 主体
   │  1. detect(content_hash)
   │  2. 入 Ingest Queue
   │  3. Pipeline Orchestrator 调度
   ↓
[Pipeline: represent → chunk → embed]
   │  产出 Entity + Representations
   │  写入 Lance + Parquet 镜像
   ↓
[Event Bus: entity.created, rep.ready, edge.created]
   ↓
┌──┴──────────────────────────────────────────┐
│  Projector 层（订阅事件）                     │
│  ┌────────────┐  ┌────────────┐  ┌───────┐  │
│  │ RAG API    │  │ Wiki       │  │ Dash  │  │
│  │ 重建索引    │  │ 写 .md    │  │ 刷新  │  │
│  └────────────┘  └────────────┘  └───────┘  │
└──────────────────────────────────────────────┘
                     │
                     │ 写 ~/wiki/entities/foo.md
                     │  追加 ~/wiki/log.md
                     │  更新 ~/wiki/index.md
                     ↓
              [Karpathy LLM Wiki]
                     │
                     │  Obsidian 浏览
                     │  Agent 提问（走 /tools/hybrid，不走 wiki）
                     │  用户编辑 → 触发反向回写
```

### 12.9 反向验证（不变量）

| 验证项 | 期望 |
|---|---|
| 复制 `~/wiki/` 到无 Lake 机器 | Obsidian 仍能正常打开、跳转、搜索 |
| Lake 离线、Wiki 在线 | Wiki 仍能正常工作（`.md` 已落地） |
| Wiki 改了一行 `.md` | Lake 重启后识别为 `user_edited_md` Representation |
| Wiki 完全不用 Lake | `~/wiki/` 仍是 Karpathy 原始约定，可独立工作 |
| `rebuild()` 全量重投影 | 与增量投影结果一致（基于 `content_hash`） |

### 12.10 Wiki Projector v0.1 范围

- [x] §12.3 字段映射表
- [x] §12.4 edge → wikilink 渲染
- [x] §12.5 推送策略 `atomic_per_page`（默认）
- [x] §12.7 SCHEMA.md 草稿生成
- [x] §12.7 index.md / log.md 自动维护
- [x] §12.8 Push 模式端到端数据流
- [ ] §12.5 `whole_vault` 全量重建（v0.2）
- [ ] §12.5 `incremental` 优化（v0.1 简化为单事件单页写）
- [ ] §12.6 反向回写 + user_edit 保护（v0.2）
- [ ] §12 Pull 模式 `GET /v1/wiki/project/*`（v0.2）
- [ ] `_lint/*.md` 报告文件（v0.2）
- [ ] 反向回写检测器（v0.1 手动触发；v0.2 定时扫）

### 12.11 与 Karpathy LLM Wiki 的对位

| Karpathy 原始约定 | Vector-Lake Wiki Projector 投影 | 备注 |
|---|---|---|
| `raw/`（不可变原文） | **不投影**（用户自管） | Lake 只读访问 raw/ |
| `entities/*.md` | Lake 投影（基于 `entity_type=document` 或 `wiki_entity`） | v0.1 |
| `concepts/*.md` | Lake 投影（基于 `entity_type=wiki_concept`） | v0.2 引入 wiki_concept |
| `comparisons/*.md` | Lake 投影（基于 `entity_type=wiki_comparison`） | v0.2 |
| `queries/*.md` | Lake 投影 + 人/LLM 共同所有 | v0.2 |
| `[[wikilink]]` | 从 `edges` 表渲染（§12.4） | v0.1 |
| `^[raw/...]` provenance | 从 `representation.sources[]` 渲染 | v0.1 |
| `SCHEMA.md` | Lake 投影初稿（基于 Pipeline 注册表） | v0.1 |
| `index.md` | Lake 自动维护 | v0.1 |
| `log.md` | Lake 自动追加 | v0.1 |
| Lint（手工健康检查） | 升级为 Pipeline：`/v1/wiki/lint`（v0.2） | v0.2 |

---

## 13. v0.1 范围

### 13.1 文件类型

```text
pdf · docx · pptx · image · audio
```

### 13.2 Pipeline

```text
A. 直接提取（document 默认）
B. OCR 流水线（document 可选）
E. 图片向量（image 默认 / document 可选）
F. 音频转写（audio 默认）
```

> Pipeline C (VLM) 和 D (知识编译) 为 v0.2，但 schema 预留。

### 13.3 Representation

```text
raw · canonical_md · plain_text · page_image · ocr_text
transcript · transcript_segment · caption
```

> `vlm_extracted_md · mind_map · graph_json · wiki_md · summary` 为 v0.2，但 schema 预留。

### 13.4 Index

```text
semantic · lexical · hybrid · grep · visual
```

> `audio · table · graph` 为 v0.2，但 schema 预留。

### 13.5 状态

```text
enabled · hidden · deleted · active · stale
```

### 13.6 能力

```text
ls · read · stat · grep · glob
semantic · lexical · hybrid · visual
```

> `audio · table · graph` 为 v0.2。

### 13.7 明确不在 v0.1 范围

- VLM 视觉流水线（v0.2）
- 知识编译流水线 / mind_map / graph_json（v0.2）
- 视频 keyframe / 场景切分（v0.2）
- 表格列式检索（v0.2）
- 学习型 router（v0.2）
- 多租户 / 计费（后续）
- 端到端 RAG 答案生成（上层）

---

## 14. API 设计（v0.1 形态）

### 14.1 内部管线 API（异步）

| API | 说明 |
| --- | --- |
| `POST /ingest` | 登记 raw object，创建 entity，触发 pipeline |
| `GET /entities/{entity_id}` | 取 entity |
| `GET /representations?entity_id=...&rep_type=...` | 列表 representation |
| `GET /pipelines` | 列表已注册 pipeline |
| `POST /pipelines/{pipeline_id}/run` | 对指定 entity 手动触发某条 pipeline |
| `GET /pipeline_runs/{run_id}` | 查询运行状态 |
| `POST /reconcile` | 触发 reconcile 任务 |

### 14.2 检索 API（同步，对上层应用）

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

### 14.3 Entity 操作 API（对应 Entity 类方法）

| API | 对应 Entity 方法 | 说明 |
| --- | --- | --- |
| `POST /entities/{id}/representations` | `generate_representation` | 生成单个 representation |
| `POST /entities/{id}/representations/regenerate` | `regenerate` | 重新生成（血缘级联） |
| `POST /entities/{id}/indexes` | `build_index` | 建索引 |
| `POST /entities/{id}/rebuild` | `rebuild_lance` | 全量重建 Lance 数据集 |
| `POST /entities/{id}/cascade` | `cascade_invalidate` | 级联失效 + 重建 |
| `PATCH /entities/{id}/tags` | `update_tags` | 更新 OSS Tag |
| `DELETE /entities/{id}` | `delete` | 软删除 |
| `POST /entities/{id}/restore` | `restore` | 恢复 |
| `POST /entities/{id}/sync` | 手动触发 | 强制同步 OSS → Lance |
| `GET /entities/{id}/lineage` | `get_lineage` | 血缘 DAG |
| `GET /entities/{id}/perspectives` | `perspectives` | 视角面板 |
| `GET /entities/{id}/preview` | `preview` | 预览 |

### 14.4 统一响应

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

## 15. 非功能需求（NFR）

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
| | **fan-out 上限** | 单次跨 Entity 检索 ≤ 100 个 Entity（v0.1 简单 fan-out） |

---

## 16. 关键场景（v0.1 验收用例）

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

## 17. 里程碑

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
| **M9. Projector 层 + Wiki Projector v0.1** | W10 | Projector 抽象 + Registry；WikiProjector 投影 `~/wiki/` 端到端跑通（Push 模式 + atomic_per_page + index/log 自动维护） |
| **M10. v0.1 GA** | W11 | S1–S10 全通过；NFR 达标 |

---

## 18. 风险与开放问题

| # | 风险 / 问题 | 缓解 / 待定 |
| --- | --- | --- |
| R1 | 文档版面解析准确率影响 canonical_md 质量 | quality 字段记录 confidence；fallback 到 ocr_text / vlm_md |
| R2 | 多模态 embedding 调用成本 | V5 API 单批 ≤ 64；batching + 缓存；按需 embed |
| R3 | 大文件 PDF 多 pipeline 并行慢 | pipeline 间并行；分页并行；中间产物缓存 |
| R4 | Lance 表 schema 演进 | 所有表带 `schema_version`；变更走 migration |
| R5 | OSS 一致性 vs 索引一致性 | content_hash 检测 + publish 原子切换 + reconcile 兜底 |
| R6 | 大文档增量更新成本 | v0.1 全量重建；v0.2 评估 page-level 增量 |
| R7 | Embedding 模型升级 | model_version 字段 + reconcile 检测过期 + 按需重跑 |
| R8 | Projector 事件消费积压（Lake 写快、Projector 慢） | Projector 自带 DLQ + 告警 + last_committed_offset 续接；监控 lag 指标 |
| R9 | Wiki 投影 idempotency 漏洞（重复事件产生重复 wikilink） | artifact 命名带 `sha256(event_id + projector + target_path)`；重复事件覆盖同目标 |
| R10 | 用户手改 `.md` 与 Lake 投影冲突 | Push 模式默认 `wiki.protect_user_edits=true` 不覆盖；编辑以 `user_edited_md` Representation 形式回流到 Lake |
| R11 | Wiki vault 写入非原子（断电导致半截文件） | `os.replace` POSIX 原子 rename；OSS 端用 `PutObject → CopyObject + if-match` 替换 |
| R12 | `rebuild()` 全量重投影与增量结果不一致 | 投影函数必须是事件的纯函数；以 `content_hash` 为基准做等价性比对 |
| Q1 | entity 是否需要"跨 collection 合并"？ | v0.1 不做；v0.2 讨论 `same_as` edge |
| Q2 | wiki_md / mind_map 的 LLM 编译成本 | v0.2 实现；异步、按需、按版本 |
| Q3 | graph index 用什么存储 | v0.1 用 graph_json representation + 内存遍历；v0.2 评估 Neo4j |
| Q4 | 检索结果"高亮 / 片段截取" | v0.1 给 snippet；v0.2 接 highlighter |
| Q5 | multimodal embedding 与文本是否真的同空间 | V5 明确支持，但需回归测试 |
| Q6 | VLM pipeline 的模型选型 | v0.2 评估 Qwen2-VL / GPT-4o / Gemini |
| Q7 | Wiki Projector 是否要支持 Pull 模式（`GET /v1/wiki/project/*`） | v0.2 评估；v0.1 仅 Push 模式 |

---

## 19. 附录

### 19.1 与现有组件的对接

| 现有组件 | 对接方式 |
| --- | --- |
| **OSS Data Lake** | 直接读写；raw 路径即 source of truth |
| **Embedding V5** | 调 `/v1/embeddings`；按 §7.1 task 映射表选 task |
| **Chunking UseCase** | Pipeline A/B 的 chunk 阶段调用 `ChunkingWithSlidingWindowUseCase`；字段映射见下表 |
| **LanceDB** | representations.lance（vector + FTS + scalar filter）；hybrid search 原生支持 |

### 19.2 Chunking UseCase 字段映射

| Chunk 字段 | Lance representations.lance 字段 | 用途 |
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

### 19.3 名词表

- **Entity**：知识对象，1 个 OSS Object = 1 个 Entity。
- **Representation**：Entity 的一种"认知视角"，血缘关系从目录层级推导。
- **Pipeline**：从 raw 或已有 representation 生成新 representation 的过程，是一等公民。
- **Chunk**：某个 Representation 下的检索最小单元，是索引方法（不是存储概念）。
- **Embedding**：Chunk 的向量索引，内嵌于 representations.lance。
- **Index**：某类检索能力。
- **Manifest**：某次处理产物的注册清单。
- **Provenance**：结果可追溯到来源 + 版本 + pipeline。
- **Reconcile**：定期对账，修复状态漂移。
- **Projector**：Lake 内部事件驱动的出站适配器（§11），把 Entity/Representation/Edge/Event 投影为外部消费者（RAG API / Wiki / Dashboard / Web）约定的格式。
- **WikiProjector**：Projector 的一种（§12），目标消费者是 Karpathy LLM Wiki / Obsidian；投影产物是 `~/wiki/` 目录的 `.md` + wikilink + index.md + log.md，可独立运行。
- **Artifact**：Projector 输出的"落地物"（OSS 文件 / HTTP 推送 / WebSocket 消息 / DB 行）。

### 19.5 开源项目 Review：血缘方案对比

本方案（OSS Tag per representation 文件）参考了以下开源项目/标准的设计，并做出适配取舍：

| 项目/标准 | 血缘/元数据方案 | 对本方案的启示 |
| --- | --- | --- |
| **Apache Iceberg V3** | 三层 metadata（metadata.json → manifest list → manifest file），V3 新增 row lineage | 分层 metadata 思想启发 VFS 目录树 + OSS Tag 分层；但 Iceberg 面向 PB 级分析表，我们的 Entity 级血缘更轻量，不需要 manifest 分层索引 |
| **OpenLineage** | 事件驱动血缘采集标准（Job/Run/Dataset + Facets 扩展机制） | 事件驱动思想与我们的 OSS Event Listener 一致；但 OpenLineage 依赖外部事件总线，我们的需求是"从 OSS 扫描即可重建"，不能依赖外部系统 |
| **S3 Metadata Tables** | AWS 托管的 Iceberg 表，自动捕获对象元数据 + Tag，提供 SQL 查询 | 验证了"对象 Tag → 结构化查询"的可行性；但 S3 Metadata Tables 是 AWS 专属，我们需在 OSS 上自建 VFS 实现 |
| **FAR (File-Augmented Retrieval)** | 每个文件旁放 `.meta` sidecar，内含 YAML frontmatter + Markdown 提取内容 | Sidecar 模式成熟（Unity Engine 20 年验证），但我们评估后认为 OSS Tag 更优：0 额外文件、无孤儿问题、Tag 与对象生命周期绑定。Sidecar 作为 v0.2+ 演进路径保留 |
| **Delta Lake** | `_delta_log/` 事务日志 + Checkpoint（JSON → Parquet 聚合） | 事务日志思想启发 OSS→Lance 同步协议的 7 Stage 设计；但 Delta Lake 面向多 writer 并发场景，我们每个 Entity 目录天然隔离，不需要乐观并发控制 |
| **Apache Hudi** | `.hoodie/` timeline + Metadata Table + LSM Timeline | Timeline 的状态机（REQUESTED → INFLIGHT → COMPLETED）启发我们的 sync_state 状态机；Metadata Table 的"分层冗余"思想与我们的 OSS Tag + Lance 双层一致 |

**核心决策总结**：

1. **OSS Tag > Sidecar**：7 个 Tag 够用，0 额外文件，无孤儿问题。Sidecar 作为 evolution 路径保留。
2. **OSS Tag > x-oss-meta-**：PutObjectTagging 不需要重写对象，x-oss-meta- 需要 CopyObject 重写。
3. **目录层级 + Pipeline 注册表 > 持久化**：血缘不存于任何字段或 Tag，从目录层级（source/extract/recognize/compile）+ Pipeline 注册表实时推导，零存储、零同步问题。
4. **事件驱动 + reconcile 兜底**：与 OpenLineage/Hudi 一致，但血缘存储在对象自身（路径）而非外部系统。

### 19.6 评审清单（Review Checklist）

- [ ] 1 OSS Object = 1 Entity 是否覆盖所有 v0.1 场景？
- [ ] Representation 的血缘 DAG 是否满足可重建？
- [ ] Chunk 作为检索粒度是否能定位到页/段/时间戳？
- [ ] Pipeline 并行调度是否满足 partial success？
- [ ] Lance representations.lance（vector + FTS + scalar filter）是否满足 hybrid search？
- [ ] 状态模型 + version 是否能区分"用户意图"与"处理状态"？
- [ ] content_hash 变更检测是否比 etag 更可靠？
- [ ] v0.1 范围是否足够小、足够完整？
- [ ] 与现有 OSS / V5 / Chunking 的对接路径是否清晰？

---

> **本 PRD 是设计基线（baseline）**。任何对核心抽象的修改（entity / representation / pipeline / chunk / 状态机）都应先回到本文件评审，再写代码。
