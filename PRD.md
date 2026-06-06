# Vector-Lake 智能知识搜索引擎层 — PRD

> **版本**：v0.2 修订版
> **状态**：待评审
> **目标读者**：产品 / 架构 / 工程 / 算法
> **核心定位**：把 OSS 数据湖升级为可被智能引擎直接调用的"知识搜索引擎层"。
> **修订说明**：基于 v0.1 review + 架构讨论 + 开源项目对标，核心变更：(1) 1 OSS Object = 1 Entity；(2) Representation 是"认知视角"而非中间产物；(3) Pipeline 是一等公民，同一 Entity 可走多条并行流水线；(4) Chunk 是索引方法，不是存储概念；(5) 1 张 Lance 表 = representations.lance（内嵌 vector），PK = `(entity_id, rep_type, chunk_index)`；(6) 零持久化元数据，全部从两套 OSS Tag（Entity Tag 7个 + Representation Tag 7个）+ VFS 扫描实时获取；(7) 血缘不存于任何字段或 Tag，从**目录层级 + Pipeline 注册表**实时推导（目录层级即血缘深度：source/ → extract/ → recognize/ → compile/，_index/ 为系统目录）；(8) 表格型 Entity（entity_type=table）通过 DuckDB + compile/table.parquet 提供 SQL 统一查询，DuckDB 进程内嵌入、OSS 原生读取；(9) 三类一等检索能力（semantic / structural / textual）通过 §9 智能引擎统一路由与证据融合，DuckDB 作为 structural 的对等能力，与 Lance 协同工作；(10) Pipeline 间强依赖（拓扑排序）+ 混合型 Entity 启发式发现 + entity_type 6 级判定链；(11) **新增 Projector 层（§11）**：把 Lake 内部数据单向投影到多种外部消费者（RAG API / Wiki / Dashboard / Web），Lake 主体地位不动摇；(12) **新增 Wiki Projector 详设（§12）**：把 Karpathy LLM Wiki 视为 Lake 内部 Projector 的一种目标格式，Lake 主动把 Entity/Representation/Edge/Event 投影为 `~/wiki/` 目录的 .md + wikilink + index.md + log.md，wiki 独立可运行；(13) **RepPipeline 与 IndexPipeline 解耦（§2.2 / §3.1 / §4.5）**：Representation 生成（内容变换）和 Index 生成（搜索结构构建）是两件本质不同的事，拆为两套独立流水线，各自有独立的 Plugin 体系（RepStep / IndexStep）；(14) **RepStep Plugin 体系（§6.6）**：可插拔的内容变换步骤，新增 rep_type = 新增 RepStep + 注册，不改已有代码；(15) **IndexStep Plugin 体系（§6.7）**：可插拔的索引构建步骤，新增 index_type = 新增 IndexStep + 注册，与 RepStep 完全解耦；(16) **Projector 作为 RepStep 注册（§11）**：Projector 不再是独立事件驱动，而是 RepStep 的一种特殊形态，复用 RepPipeline 的编排能力；(17) **两阶段一致性模型（§2.5 / §5.7 / §5.9）**：一致性校验拆为 Rep↔Raw（内容一致性）和 Index↔Rep（索引一致性）两条独立链，Reconciler 也拆为两阶段执行，先修 Rep 再修 Index；(18) **专家 review 修复（v0.2 完善）**：P1 修复 §13 v0.1 范围对齐 Wiki Projector 是 v0.2；P2 拆 `input_reps` 为 `required_input_reps` + `optional_input_reps` 解决循环依赖；P3 §4.5 JSON schema 加 step_id 注释；S1-S11 + O1-O2 全面修复（§2.6/§3.2/§4.6 重写、§5.9.3 Projector 一致性、§5.10 Index Status、§5.11 Edge 生命周期、§5.9.4 rep_all_ready 精确定义、§6.8 并发模型、§14.5 Plugin 注册 API、§16 S15-S20 验收用例）；§2.4 术语统一 vlm_extracted_md → vlm_md；§11.3 表格对齐 WikiProjectorStep 状态为 v0.2；(19) **元数据可靠性与重建策略（§5.12）**：从可靠平台视角审视"零持久化"架构的元数据不可恢复风险，调整为"准零持久化"原则——运行时零持久化，但不可推导信息（rag_status/labels/version）以 `.entity_manifest.json` + `.version_log.jsonl` sidecar 持久化；新增 Reconciler Phase 0 body_hash 校验、Tag 写入原子性协议、Lance 损坏自愈、VFS 漂移监控、灾难恢复流程、管理员 API（§14.7）；§4.6 核心决策更新为"准零持久化"；§5.9 Reconciler 增加 Phase 0；§15 NFR 增加元数据可恢复指标；§16 增加 S21-S24 验收场景；§18 增加 R17-R20 风险；(20) **成熟项目参照优化（§5.12.9 - §5.12.14）**：参照 Delta Lake、Apache Iceberg、lakeFS、Lance 4 个成熟数据湖项目的元数据架构，识别当前 PRD 6 大设计缺口（事务日志、原子指针、三层元数据、Merkle 血缘、MVCC Manifest、Schema Evolution）；§4.6.x 新增 v0.2 三层元数据架构预览（事务日志 + 原子指针 + 快速索引）；§5.12.9 新增事务日志 + 原子指针交换（参考 Delta _delta_log + Iceberg compare-and-swap）；§5.12.10 新增 Merkle 树血缘（参考 lakeFS Graveler）；§5.12.11 新增三层元数据架构（参考 Iceberg Manifest List）；§5.12.12 新增 MVCC + 不可变 Manifest（参考 Lance spec）；§5.12.13 新增 Schema Evolution 规则；§5.12.14 明确 v0.1/v0.2 实施路径与设计哲学；§5.10.2 标注 v0.2 Manifest 显式化升级；§15 NFR 新增 v0.2 元数据架构指标（原子交换延迟 / 事务日志吞吐 / Time Travel / Checkpoint）；§18 风险新增 R21-R25；(21) **开源技术选型与复用（§20 + [OPEN_SOURCE_STACK.md](file:///workspace/OPEN_SOURCE_STACK.md)）**：从 OSS 数据管理 / 同步 / 向量检索 / Pipeline 编排 / 元数据治理 / 可观测性 / Lake Format 7 大类别盘点 50+ 开源项目；v0.1 选定最小可用集（OSS / MinIO + LanceDB + 自研调度 + OTel + Prometheus + Grafana + Sentry）；v0.2 引入候选（Dagster / Temporal / OpenMetadata / Kafka / JuiceFS / lakeFS）；新增 §20 包含 7 大类别速查、v0.1 最小可用集、v0.2 候选、OSS 事件通知集成模式、关键开源项目 GitHub 链接表、7 项关键决策记录（为何选 LanceDB / 为何自研调度 / 为何借鉴而非直接用 Iceberg）；(22) **Redis Streams 任务队列 + VFS MCP Server**：§6.9 新增 Redis Streams 任务队列设计（Stream 拓扑 / 消息格式 / 消费协议 / 可靠性保证 / 与 Celery 对比 / v0.2 演进路径），确认 v0.1 不使用 Celery（Celery 不可靠的根因是抽象层太多，直接用 Redis Streams 原语更可靠）；§9.5 新增 VFS MCP Server 设计（8 个 MCP Tools / stdio+SSE 双模式部署 / 与智能引擎映射 / v0.1 全量实现），向 LLM 暴露 Lake 的浏览/查询/检索能力；§20 v0.1 技术栈更新（Queue: Redis Streams / VFS→LLM: MCP Server）；§20.6 关键决策新增"任务队列"和"VFS→LLM"两条记录；(23) **产品级 Review 修复（17 项）**：C4 Entity Tag 从 10→7（移除 workspace_id/collection_id/entity_id，预留 3 个给 v0.2）；C2 Entity=触发器（generate_*/build_* 只投递消息到 Redis Streams，Worker 执行）；F1 OSS PutObject 不支持 if-match（v0.1 last-writer-wins + Reconciler 修复，v0.2 CopyObject+if-match）；C1 元数据写入状态机（CLEAN/FILE_WRITTEN/MANIFEST_WRITTEN/TAG_MISSING 四态 + Reconciler 自动修复）；F2 Phase 0 改为 ETag 校验（HeadObject 零下载，代价 O(file_size)→O(1)）；C3 消息格式增加 input_reps（Orchestrator 填充具体路径）；C5 MCP+REST 共享 Service 层；E3 软删除不删 Lance（deleted 保留 30 天，destroy 才物理删）；E2 锁粒度从 Entity 级改为 RepPipeline 级；E6 Redis Streams 背压策略（MAXLEN+告警+429+锁超时策略）；E5 MCP 权限模型（admin/user/readonly + required_role）；E4 Index 重建优先级（high/medium/low 分批重建）；E1 多文件 Rep 目录级 .meta.json；F3 OSS LIST 1000 限制 + VFS Redis 缓存；F5 Lance metadata 限制（v0.1 最多 5 个 Index）；(24) **完整 PRD 补充（§1.5/§1.6/§21-§25）**：新增用户角色（5 类 Personas）与竞争定位（与 Elasticsearch/Pinecone/LlamaIndex/lakeFS/OpenMetadata 6 维对比）；新增部署模型（Docker Compose 一键部署 + 拓扑图 + 8 条运维命令）；新增 SDK 策略（Python SDK + CLI + MCP 集成 + 多语言路线图）；新增错误模型（17 个错误码 + 4 个故障排查场景）；新增测试策略（测试金字塔 + 7 个 E2E 场景 + CI/CD 流程 + 6 项质量门禁）；新增版本策略（SemVer + 生命周期 + 5 层向后兼容承诺 + 数据格式演进 + CHANGELOG 规范）；(25) **支持输入格式清单（§6.5）**：新增完整格式支持清单，覆盖 5 大 entity_type 共 50+ 种文件格式——文档格式 14 种（md/doc/docx/pdf/ppt/pptx + WPS 系列 .wps/.wpt/.dps/.dpt + txt/rtf/odt/html）；表格格式 9 种（csv/xls/xlsx + WPS 系列 .et/.ett + tsv/parquet/json）；图片格式 9 种（Jina V5 Omni 全量：jpg/png/gif/webp/bmp/tiff/avif/heic/svg）；音频格式 6 种（Jina V5 Omni 全量：wav/mp3/flac/ogg/m4a/opus）；视频格式 7 种（Jina V5 Omni 全量：mp4/avi/mov/mkv/webm/flv/wmv）；新增格式→entity_type→Pipeline 路由总表（§6.5.6）、格式不支持时的处理策略（§6.5.7）、v0.2 格式扩展计划（§6.5.8）；§2.1 entity_type 取值新增 table；§6.4.1 判定表更新引用 §6.5；RepStep transcribe 扩展支持 video entity_type；(26) **排版保留与 Rep 对齐（§4.3.1）**：索引时保留排版信息，chunk 增加 `layout` 字段（含 blocks/bbox/page_number/page_size），与 Representation 对齐；新增 layout_json 完整 Schema（8 种 block 类型 + start_pos/end_pos 区间映射）；IndexStep chunk_and_embed_text/image/table 新增 `optional_reps: layout_json`；RepStep parse 产出新增 `layout_json`；排版一致性保证（layout↔canonical_md 覆盖率检测 + chunk↔layout 区间重叠校验 + layout↔page_image 引用完整性）；排版在多 Rep 间共享（同一 Entity 的 canonical_md/ocr_text/vlm_md 共享同一份 layout_json）；锚点跳转机制（5 种锚点类型：Markdown slug / 页码 / bbox 坐标 / 字符偏移 / 时间戳）；锚点跳转 REST API（anchor-jump + cross_rep_anchors 跨 Rep 一致性）；block_id 作为锚点唯一标识保证跨 Rep 定位一致。

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

### 1.5 用户角色（User Personas）

| 角色 | 职责 | 核心诉求 | 交互方式 |
| --- | --- | --- | --- |
| **数据工程师 / Pipeline 开发者** | 开发 RepStep / IndexStep / ProjectorStep Plugin；定义 RepPipeline 拓扑；调试 Pipeline 编排 | 清晰的 Plugin 接口（Protocol）；可复用的 Step 注册机制；丰富的日志与调试工具 | Python SDK (§22) + CLI + RepStepRegistry API |
| **AI 应用开发者** | 构建 RAG 应用、Agent、问答系统；调用检索 API 获取知识证据 | 统一的检索入口（semantic + structural + textual）；可解释的检索结果（provenance + snippet）；低延迟 | REST API + MCP Server (§9.5) + Python SDK |
| **知识管理者 / 数据管家** | 管理 Entity 生命周期（ingest / label / delete）；配置 Projector 输出目标；监控数据质量 | Entity 状态可视化；血缘追溯；批量操作（label / delete）；数据质量报告 | CLI + REST API + Dashboard（v0.2） |
| **DevOps / 平台工程师** | 部署与运维 Vector-Lake 服务；监控系统健康；配置 OSS / Redis / LanceDB 连接 | 一键部署（Docker Compose / K8s）；健康检查与告警；日志聚合；配置热更新 | 配置文件（YAML + ENV）+ Prometheus + Grafana |
| **终端用户（通过 MCP / API）** | 通过 LLM Agent 间接使用知识检索能力 | 准确、快速的知识检索结果；支持自然语言查询 | 间接（通过 MCP Server → LLM → 终端用户） |

### 1.6 竞争定位（Competitive Positioning）

Vector-Lake 不是另一个向量数据库、搜索引擎或数据治理平台。它是一个**知识搜索引擎层**——在 OSS 数据湖之上，提供 Entity 驱动的知识建模、多 Pipeline 内容变换、多模态索引构建、以及统一检索路由。

| 维度 | Vector-Lake | Elasticsearch | Pinecone / Weaviate | LlamaIndex / LangChain | lakeFS / Delta Lake | OpenMetadata |
| --- | --- | --- | --- | --- | --- | --- |
| **定位** | 知识搜索引擎层 | 全文搜索引擎 | 向量数据库 | LLM 数据框架 | 数据湖版本控制 | 元数据治理平台 |
| **数据源** | OSS 数据湖（原生） | 自建索引 | 自建索引 | 多种 Connector | OSS / S3 数据湖 | 多种 Connector |
| **知识建模** | Entity + Representation + Lineage | 文档（无 Entity 概念） | 无知识建模 | Document / Node（轻量） | 无 | Dataset / Table（面向分析） |
| **内容变换** | RepPipeline（可插拔 Plugin） | Ingest Pipeline（有限） | 无 | Transformation（代码级） | 无 | 无 |
| **索引策略** | IndexPipeline（可插拔 Plugin） | 倒排索引（固定） | 向量索引（固定） | 向量 + 关键词（有限） | 无 | 无 |
| **多模态** | 原生（文本 / 图片 / 音频 / 视频 / 表格） | 仅文本 | 仅向量 | 部分支持 | 无 | 无 |
| **血缘** | 目录层级 + Pipeline 注册表（零存储） | 无 | 无 | 无 | 版本历史 | 表级血缘 |
| **一致性模型** | 两阶段（Rep↔Raw + Index↔Rep） | 最终一致 | 最终一致 | 无保证 | 事务性 | 元数据同步 |
| **对外投影** | Projector 层（Wiki / RAG API / Dashboard） | Kibana | 无 | 无 | 无 | 无 |
| **LLM 集成** | MCP Server（原生） | 第三方 | 原生 SDK | 原生 | 无 | 无 |
| **部署复杂度** | 轻量（LanceDB 嵌入式 + Redis Streams） | 重（集群） | 中等（SaaS / 自托管） | 轻量（Python 库） | 中等 | 重 |
| **开源协议** | Apache 2.0（计划） | Elastic License | 源码可用 / 开源 | MIT | Apache 2.0 | Apache 2.0 |

**Vector-Lake 的独特价值**：

1. **Entity 驱动的知识建模** — 不是文档索引，而是以 Entity 为核心的知识对象管理，支持多 Representation 视角和完整血缘。
2. **解耦的双 Pipeline 架构** — RepPipeline（内容变换）和 IndexPipeline（索引构建）完全解耦，各自有独立的 Plugin 体系，可独立演进。
3. **准零持久化元数据** — 元数据从 OSS Tag + VFS 路径实时推导，不依赖外部元数据库，从 OSS 扫描即可完整重建。
4. **Projector 层** — 知识引擎层主动将内部数据投影到多种外部消费者（Wiki / RAG API / Dashboard），而非被动等待查询。
5. **两阶段一致性** — 首次在知识引擎中同时保证内容一致性（Rep↔Raw）和索引一致性（Index↔Rep），可调和、可重建。
6. **LLM 原生** — MCP Server 作为一等公民，让 LLM 可以直接探索和检索知识湖。

**与现有工具的互补关系**：

```text
Elasticsearch / Pinecone  ←→  Vector-Lake  ←→  LlamaIndex / LangChain
  (底层索引引擎)              (知识搜索引擎层)         (上层应用框架)
```

Vector-Lake 不替代 Elasticsearch 或 Pinecone，而是在它们之上（或 LanceDB 之上）提供知识建模、Pipeline 编排、一致性保证和统一检索路由。它也不替代 LlamaIndex / LangChain，而是为它们提供更高质量、可追溯、多模态的知识检索结果。

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

> **关键分离**：Representation 生成（内容变换）和 Index 生成（搜索结构构建）是两件本质不同的事，必须解耦。Rep 生成有血缘、有版本；Index 生成无血缘、可重建。两者通过独立的 Plugin 体系注入，互不依赖。

```text
Raw Object (OSS, immutable)
    │
    ▼
[1] Ingest  (登记 entity)
    ▼
[2] Detect  (mime / size / content_hash / language)
    ▼
[3] Rep Pipeline Dispatch  (根据 entity_type 选择 1..N 条 RepPipeline)
    │                                    ← 内容变换阶段
    ├── RepPipeline A: "直接提取" ──► rep(canonical_md) ──► rep(plain_text)
    ├── RepPipeline B: "页面渲染" ──► rep(page_image)
    ├── RepPipeline C: "OCR" ──► rep(ocr_text)
    ├── RepPipeline D: "VLM" ──► rep(vlm_md)
    ├── RepPipeline E: "知识编译" ──► rep(mind_map / graph_json / wiki_md / summary)
    ├── RepPipeline F: "音频转写" ──► rep(audio_segment) ──► rep(transcript)
    └── RepPipeline G: "表格获取" ──► rep(table_parquet / table_md)
    │
    ▼  Rep 全部 ready 后
    │
[4] Index Pipeline Dispatch  (根据 rep 模态 + 可用性选择 1..N 条 IndexPipeline)
    │                                    ← 搜索结构构建阶段
    ├── IndexPipeline "文本索引" ──► chunk(text) ──► embed(text) ──► vector + FTS index
    ├── IndexPipeline "图片索引" ──► chunk(image) ──► embed(image) ──► visual index
    ├── IndexPipeline "音频索引" ──► chunk(audio) ──► embed(audio+text) ──► audio index
    ├── IndexPipeline "表格索引" ──► chunk(table) ──► embed(table) ──► table index
    └── IndexPipeline "图索引"   ──► parse(graph_json) ──► graph index
    │
    ▼
[5] Projector Dispatch  (根据配置选择 0..N 个 Projector)
    │                                    ← 外部格式投影阶段
    ├── WikiProjector ──► ~/wiki/*.md + wikilinks
    ├── RAG API Projector ──► /tools/* HTTP 路由
    └── Dashboard Projector ──► TSDB / WebSocket
    │
    ▼
[6] Publish  (mark active, visible to retrieval)
    ▼
[7] Reconcile  (continuous; fix drift)
```

### 2.3 一句话架构

> **Raw Object → Entity → (RepPipeline → Representation)×N → (IndexPipeline → Chunk → Embedding → Index)×N → Projector×N → Intelligent Engine**

### 2.4 Representation 是"认知视角"

同一个 Entity 可以有多种认知视角，它们之间通过 **Lineage（血缘）** 互相关联：

```text
Entity: "https://example.com/pricing"
  │
  ├── rep: canonical_md        ← 网页抓取的 Markdown
  ├── rep: page_screenshot     ← 网页截图
  ├── rep: vlm_md                ← 截图经 VLM 识别出的 Markdown
  ├── rep: mind_map            ← LLM 编译的脑图
  ├── rep: summary             ← 摘要
  └── rep: graph_json          ← 实体关系图
```

Lineage 血缘链：

```text
raw ──► canonical_md ──► mind_map
                   ├──► summary
                   └──► graph_json
raw ──► page_screenshot ──► vlm_md
```

### 2.5 Lineage 是一等公民

Lineage 的核心目的是：**上游变动后，下游立即不可用并重新生成**。

**Lineage 元数据存储方式**：血缘关系**不存于任何字段或 OSS Tag**，完全从**目录层级**和**Pipeline 注册表**实时推导。目录层级天然编码血缘深度：`source/` → `extract/` → `recognize/` → `compile/`（见 §4.6）。

```text
raw 更新
  → [Rep 级联] canonical_md stale → mind_map stale → graph_json stale → summary stale → wiki_md stale
  → [Rep 级联] page_image stale → ocr_text stale → vlm_md stale
  → [Index 重建] 所有基于 stale rep 的 index 自动标记 stale
```

**两阶段一致性模型**：

> 解耦后，一致性校验变成两条清晰的链：**校验1：Rep↔Raw（内容一致性）**和**校验2：Index↔Rep（索引一致性）**。两者独立触发、独立修复。

**阶段 1：Rep ↔ Raw 一致性（内容一致性）**：

1. **上游变了 → 下游 Rep 立即 stale**：沿 RepPipeline 的 `input_reps` 边向下遍历，所有下游 Rep 文件的 OSS Tag `status` 更新为 `stale`。
2. **stale → 自动触发 RepPipeline 重建**：RepPipelineOrchestrator 检测到 stale 状态，自动重跑对应 RepPipeline 生成新 Representation 文件。
3. **重建完成 → publish 切换**：新版本 ready 后，原子切换。
4. **重建期间 → 旧版本仍可查**：stale 的 Rep 在新版本 publish 前仍保留。

**阶段 2：Index ↔ Rep 一致性（索引一致性）**：

1. **Rep 变了 → 对应 Index 立即 stale**：IndexPipeline 消费的 Rep 有任一 stale，则该 Index 标记 stale。
2. **stale → 自动触发 IndexPipeline 重建**：IndexPipelineOrchestrator 检测到 Index stale，自动重跑对应 IndexPipeline 重建索引。
3. **Index 重建失败不影响 Rep**：Rep 文件仍在，只是检索能力暂时缺失。
4. **Index 无血缘**：Index 之间不存在级联关系，每个 Index 独立重建。

**两阶段的关键区别**：

| 维度 | Rep ↔ Raw 一致性 | Index ↔ Rep 一致性 |
|---|---|---|
| 校验内容 | Rep 文件内容是否与 Raw 一致 | Index 是否与当前 active Rep 一致 |
| 检测方式 | `content_hash` 比对 | `rep_content_hash` vs `index_built_from_hash` |
| 级联 | 有（Rep 之间沿 RepPipeline 边级联） | 无（Index 之间独立） |
| 修复 | 重跑 RepPipeline | 重跑 IndexPipeline |
| 修复影响 | 知识内容变化 | 检索能力恢复 |
| 修复顺序 | 先修 Rep，再修 Index | 必须等 Rep 全部 active 后 |

### 2.6 Pipeline 是两套独立的一等公民

> **RepPipeline**（内容变换）和 **IndexPipeline**（索引构建）是两套独立的一等公民。RepPipeline 产出 Representation 文件；IndexPipeline 消费 Rep 产出索引。两者不混合在同一条流水线中。

**RepPipeline**（内容变换）：

```text
Entity: pricing.pdf
  │
  ├── rep_pipeline_a: "直接提取"
  │     └── parse: raw → canonical_md, plain_text
  │
  ├── rep_pipeline_b: "OCR 内容变换"
  │     └── render_page → ocr: raw → page_image → ocr_text
  │
  ├── rep_pipeline_c: "VLM 内容变换" (v0.2)
  │     └── render_page → vlm: raw → page_image → vlm_md
  │
  ├── rep_pipeline_d_wiki: "Wiki 编译" (v0.2)
  │     └── compile_wiki_md: canonical_md → wiki_md
  │
  └── rep_pipeline_e: "图片渲染"
        └── render_page: raw → page_image
```

**IndexPipeline**（索引构建）：

```text
基于上述 Rep 产出的 Rep 文件
  │
  ├── index_pipeline_text: "文本索引"
  │     └── chunk_and_embed_text → build_vector_index → build_fts_index
  │         消费: canonical_md / ocr_text / vlm_md
  │
  ├── index_pipeline_image: "图片索引"
  │     └── chunk_and_embed_image → build_vector_index
  │         消费: page_image
  │
  └── index_pipeline_graph: "图索引" (v0.2)
        └── build_graph_index
            消费: graph_json
```

---

## 3. 架构设计

### 3.1 分层架构

```text
┌──────────────────────────────────────────────────────────────┐
│  L6  Intelligent Engine                                      │
│      Query Understanding · Capability Routing · Fusion · RAG │
├──────────────────────────────────────────────────────────────┤
│  L5  Retrieval Capabilities (Tools)                          │
│      ls · read · stat · grep · glob                          │
│      semantic · lexical · hybrid · visual · audio · table    │
│      graph                                                   │
├──────────────────────────────────────────────────────────────┤
│  L4.5  Virtual File System (VFS)                             │
│      事件驱动 + 迭代式 OSS prefix 扫描 → 目录树                │
│      路径 ↔ Entity/Representation 映射                       │
│      glob / grep / ls / stat / read 基于此层                  │
├──────────────────────────────────────────────────────────────┤
│  L4  Projector Layer                                         │
│      WikiProjector → ~/wiki/*.md                             │
│      RAG API Projector → /tools/* HTTP                       │
│      Dashboard Projector → TSDB / WS                         │
│      (可插拔，注册为 RepStep)                                  │
├──────────────────────────────────────────────────────────────┤
│  L3  Index Layer (LanceDB)                                   │
│      IndexPipeline → chunk → embed → vector/FTS/graph index  │
│      IndexStep Plugin 体系（可插拔）                           │
│      Hybrid Search (RRF / CrossEncoder rerank)               │
├──────────────────────────────────────────────────────────────┤
│  L2  Representation Layer                                    │
│      RepPipeline → RepStep → Representation 文件             │
│      RepStep Plugin 体系（可插拔）                             │
│      parse → canonical_md · render → page_image              │
│      ocr → ocr_text · vlm → vlm_md                          │
│      compile → mind_map / graph_json / wiki_md / summary     │
├──────────────────────────────────────────────────────────────┤
│  L1  Entity Layer                                            │
│      Entity registry (1 OSS Object = 1 Entity)               │
│      Edge registry (跨 Entity 关系) · Manifest               │
├──────────────────────────────────────────────────────────────┤
│  L0  Raw Object Store (OSS Data Lake)                        │
│      oss://vector-lake/{ws}/{col}/{entity_id}/source/original│
└──────────────────────────────────────────────────────────────┘
```

> **L2 与 L3 的关键分离**：L2（Representation Layer）只做内容变换，产出文件；L3（Index Layer）只做搜索结构构建，消费 L2 产出的文件。两者通过独立的 Plugin 体系注入，互不依赖。L4（Projector Layer）消费 L2 产出的文件，投影为外部格式。

### 3.2 模块划分

> **关键**：Pipeline 拆为 RepPipeline + IndexPipeline 两套独立编排器；Projector 复用 RepPipeline 编排器。模块表已对齐新分层。

| 模块 | 职责 | 关键产出 | 对应层 |
| --- | --- | --- | --- |
| **Ingest Service** | 监听 OSS 新对象、登记 entity | OSS Tag + Entity 目录 | L1 |
| **Detect Worker** | mime / language / content_hash / size | detect 结果 | L1 |
| **RepStepRegistry** | 全局 RepStep 注册表（v0.1 代码内注册） | RepStep 索引 | L2 |
| **RepPipelineOrchestrator** | 选择 1..N 条 RepPipeline，按拓扑序调度 RepStep 执行 | rep_all_ready 事件 | L2 |
| **RepStep Executor Pool** | 执行 RepStep（含 LLM/VLM/OCR Worker） | Rep 文件 + OSS Tag | L2 |
| **IndexStepRegistry** | 全局 IndexStep 注册表 | IndexStep 索引 | L3 |
| **IndexPipelineOrchestrator** | 消费 `rep_all_ready` 事件，调度 IndexStep 重建 | index 重建任务 | L3 |
| **IndexStep Executor Pool** | 执行 IndexStep（chunk + embed + index build） | Lance 数据集 + 索引 | L3 |
| **Lance Watcher** | 监听 staging Parquet 变动，实时同步到 Lance；支持全量 rebuild | Lance 数据集 | L3 |
| **ProjectorStepRegistry** | Projector Step 注册表（v0.1 仅 `project_rag_api`） | ProjectorStep 索引 | L4 |
| **ProjectorStep Executor** | 执行 ProjectorStep（写入外部 vault / HTTP / WS） | 外部 artifact | L4 |
| **Retrieval Gateway** | 暴露统一检索 API（含 VFS 工具） | tool 调用结果 | L5 |
| **Intelligent Engine** | 理解 query、路由能力、融合、重排 | evidence pack | L6 |
| **Event Listener** | 订阅 OSS 事件，实时更新 VFS 目录树 | 增量 VFS 视图 | L4.5 |
| **Reconciler** | 周期全量扫描 OSS prefix，对账 VFS 与实际状态；两阶段一致性校验 | drift 报告 + 修复 | 跨层 |

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
document · table · image · audio · video
```

> `document` 包含 pdf/doc/docx/ppt/pptx/md/wps/wpt/dps/dpt/txt 等；`table` 包含 csv/xls/xlsx/et/ett/tsv/parquet/json 等；`image` 包含 jpg/png/gif/webp/bmp/tiff/avif/heic/svg 等（Jina V5 Omni 全量支持）；`audio` 包含 wav/mp3/flac/ogg/m4a/opus 等（Jina V5 Omni 全量支持）；`video` 包含 mp4/avi/mov/mkv/webm/flv/wmv 等（Jina V5 Omni 全量支持）。完整格式清单见 §6.5。

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

    # ===== 表现管理（Entity = 触发器，投递消息到 Redis Streams）=====
    # 注意：Entity 是领域模型 + 触发器，不是执行者。
    # generate_* / build_* 方法只做 XADD 到 Redis Streams，不直接执行 RepStep/IndexStep。
    # 执行由 Worker 进程完成（§6.9）。
    def generate_representation(self, rep_type: str) -> str:
        """投递 RepStep 任务到 Redis Streams。返回 entry_id。
        委托给 RepStepRegistry 找到能产出该 rep_type 的 step，
        由 RepPipelineOrchestrator 投递消息，Worker 执行。"""

    def generate_all_representations(self) -> list[str]:
        """投递所有该 entity_type 适用的 RepStep 任务。返回 entry_id 列表。"""

    def regenerate(self, rep_type: str) -> str:
        """投递重新生成任务。血缘级联：标 stale → 投递重建任务。"""

    def regenerate_all(self) -> list[str]:
        """投递重新生成所有 representations 的任务。"""

    # ===== 索引管理（Entity = 触发器，投递消息到 Redis Streams）=====
    # 注意：索引管理与表现管理完全解耦。索引消费表现产出的文件，但不属于表现层。
    def build_index(self, index_type: str) -> str:
        """投递 IndexStep 任务到 Redis Streams。返回 entry_id。
        委托给 IndexStepRegistry 找到对应 IndexStep，
        由 IndexPipelineOrchestrator 投递消息，Worker 执行。"""

    def build_all_indexes(self) -> list[str]:
        """投递所有适用索引构建任务。"""

    def rebuild_index(self, index_type: str) -> str:
        """投递删除旧索引并重建的任务。"""

    def rebuild_lance(self) -> str:
        """投递全量重建 Lance 数据集的任务（从 OSS representation 文件 + staging Parquet）。
        适用场景：schema 变更 / Lance 损坏 / 碎片率过高 / 索引失效。
        支持 MVCC 回滚：重建失败自动回退到旧 version。"""

    def refresh_indexes(self) -> str:
        """投递 representation 变动后的增量索引更新任务。"""

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
  "layout": {
    "blocks": [
      {"type": "heading", "level": 2, "text": "Q3 Pricing", "bbox": [72, 120, 540, 144]},
      {"type": "paragraph", "text": "Enterprise: $4.2B, Consumer: $1.8B...", "bbox": [72, 150, 540, 180]}
    ],
    "page_number": 7,
    "page_width": 612,
    "page_height": 792,
    "source_rep": "canonical_md",
    "layout_version": 1
  },
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
| `layout` | Pipeline chunk 阶段从 `layout_json` Rep 映射 | 排版信息（与 Rep 对齐，见 §4.3.1） |

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

#### 4.3.1 排版保留与 Rep 对齐（Layout Alignment）

**核心原则**：索引时保留排版信息，且排版与 Representation 对齐——**对齐 = 实现引用锚点跳转**：检索命中 Chunk 后，通过锚点（anchor）精确跳转到 Rep 中的原始排版位置（页码、bbox、段落），实现"检索→锚点→跳转→呈现"的完整链路。

**排版数据流**：

```text
RepStep parse
  │
  ├─ 产出 canonical_md（内容）
  └─ 产出 layout_json（排版）
        │
        ▼
IndexStep chunk_and_embed_text
  │
  ├─ 读取 canonical_md → 切 chunk（text + start_pos + end_pos）
  ├─ 读取 layout_json → 为每个 chunk 映射排版信息
  │     │
  │     ├─ text chunk 的 (start_pos, end_pos) ↔ layout_json 的 blocks 区间
  │     ├─ 每个 block 含 type / level / bbox / page_number
  │     └─ chunk.layout = 命中的 blocks 子集 + 页面尺寸
  │
  └─ 写入 Lance 表（chunk 行含 layout 字段）
```

**layout_json Representation Schema**：

```json
{
  "version": 1,
  "source_entity_id": "abc123",
  "source_rep": "canonical_md",
  "pages": [
    {
      "page_number": 1,
      "width": 612,
      "height": 792,
      "blocks": [
        {
          "block_id": "b1",
          "type": "heading",
          "level": 1,
          "text": "Annual Report 2025",
          "bbox": [72, 72, 540, 96],
          "start_pos": 0,
          "end_pos": 22,
          "children": ["b2", "b3"]
        },
        {
          "block_id": "b2",
          "type": "paragraph",
          "text": "This report covers...",
          "bbox": [72, 110, 540, 180],
          "start_pos": 23,
          "end_pos": 150,
          "children": []
        },
        {
          "block_id": "b3",
          "type": "table",
          "text": "| Metric | Value |",
          "bbox": [72, 190, 540, 320],
          "start_pos": 151,
          "end_pos": 280,
          "children": [],
          "table_meta": {"rows": 5, "cols": 3}
        },
        {
          "block_id": "b4",
          "type": "image",
          "bbox": [72, 330, 540, 480],
          "start_pos": null,
          "end_pos": null,
          "children": [],
          "image_ref": "page_image/page_001.png",
          "caption": "Figure 1: Revenue Trend"
        }
      ]
    }
  ]
}
```

**layout block 类型**：

| type | 含义 | 必含字段 | 可选字段 |
| --- | --- | --- | --- |
| `heading` | 标题 | `level`, `text`, `bbox` | — |
| `paragraph` | 段落 | `text`, `bbox` | — |
| `table` | 表格 | `text`, `bbox` | `table_meta`（rows/cols） |
| `image` | 图片 | `bbox` | `image_ref`, `caption` |
| `list` | 列表 | `text`, `bbox` | `list_type`（ordered/unordered） |
| `code` | 代码块 | `text`, `bbox` | `language` |
| `blockquote` | 引用 | `text`, `bbox` | — |
| `page_break` | 分页符 | — | — |

**Chunk layout 字段映射规则**：

```python
def map_layout_to_chunk(chunk_text: str, chunk_start: int, chunk_end: int,
                        layout: LayoutJSON) -> ChunkLayout:
    """将 layout_json 中与 chunk 区间 [start_pos, end_pos) 重叠的 blocks 映射到 chunk。"""
    matched_blocks = []
    for page in layout.pages:
        for block in page.blocks:
            # 区间重叠判定
            if block.start_pos is not None and block.end_pos is not None:
                if block.start_pos < chunk_end and block.end_pos > chunk_start:
                    matched_blocks.append({
                        "type": block.type,
                        "level": block.get("level"),
                        "text": block.text,
                        "bbox": block.bbox,
                    })
    return ChunkLayout(
        blocks=matched_blocks,
        page_number=matched_blocks[0].get("page_number") if matched_blocks else None,
        page_width=layout.pages[0].width if layout.pages else None,
        page_height=layout.pages[0].height if layout.pages else None,
        source_rep=layout.source_rep,
        layout_version=layout.version,
    )
```

**排版对齐一致性保证**：

| 一致性维度 | 保证方式 | 不一致时处理 |
| --- | --- | --- |
| layout_json ↔ canonical_md | `start_pos` / `end_pos` 区间必须覆盖 canonical_md 全文 | Reconciler Phase 1 检测：layout 覆盖率 < 100% → 标记 stale，触发 Rep 重建 |
| chunk.layout ↔ canonical_md | chunk 的 `(start_pos, end_pos)` 必须与 layout blocks 区间有重叠 | IndexStep 校验：无重叠 → 跳过 layout 字段，chunk 仍可检索但无排版定位 |
| chunk.layout ↔ page_image | layout 中 image block 的 `image_ref` 必须指向存在的 page_image 文件 | Reconciler Phase 2 检测：引用断裂 → 标记 layout stale |

**排版在不同 Rep 间的对齐**：

```text
同一 Entity 的多个 Rep 共享同一份 layout_json：

canonical_md ──┐
               ├─► layout_json（唯一，由 RepStep parse 产出）
ocr_text ──────┘
               │
               ├─ IndexStep chunk_and_embed_text(canonical_md + layout_json)
               └─ IndexStep chunk_and_embed_text(ocr_text + layout_json)

关键：layout_json 是 Entity 级别的共享 Rep，不随 Rep 类型变化。
所有文本类 Rep（canonical_md / ocr_text / vlm_md）的 chunk
都引用同一份 layout，保证"同一页码 / 同一 bbox"在不同视角间一致。
```

**检索结果中的锚点跳转（Anchor Jump）**：

锚点跳转是排版对齐的核心交互模式。每个 Chunk 携带锚点信息，检索命中后可跳转到任意 Rep 视图中的精确位置。

```text
用户检索 "Q3 定价策略"
  │
  ▼
命中 chunk: entity=abc123, rep_type=canonical_md, chunk_index=3
  │
  ├─ chunk.anchor = "q3-pricing"           ← Markdown 锚点（标题 slug）
  ├─ chunk.layout.page_number = 7          ← 页码锚点
  ├─ chunk.layout.blocks[0].bbox = [72,120,540,144]  ← 坐标锚点
  ├─ chunk.start_pos = 1200                ← 字符偏移锚点
  │
  ▼ 锚点跳转（3 种目标视图）
  │
  ├─① Markdown 视图：跳转到 #q3-pricing 锚点
  │   URL: /ws/kb/abc123/canonical_md#q3-pricing
  │   行为：滚动到 ## Q3 Pricing 标题，高亮 chunk 覆盖的段落
  │
  ├─② 版面视图：跳转到第 7 页 bbox 区域
  │   URL: /ws/kb/abc123/page_image?page=7&bbox=72,120,540,144
  │   行为：渲染 page_007.png，在 bbox 区域叠加半透明高亮矩形
  │
  └─③ 切换视角：同一锚点跳转到 ocr_text / vlm_md
      URL: /ws/kb/abc123/ocr_text#q3-pricing
      行为：定位到同一标题锚点（共享 layout_json 保证位置一致）
```

**锚点类型与跳转规则**：

| 锚点类型 | 字段 | 跳转目标 | 适用 Rep |
| --- | --- | --- | --- |
| **Markdown 锚点** | `anchor` (slug) | `canonical_md#q3-pricing` | canonical_md / ocr_text / vlm_md |
| **页码锚点** | `layout.page_number` | `page_image?page=7` | page_image |
| **坐标锚点** | `layout.blocks[].bbox` | `page_image?page=7&bbox=72,120,540,144` | page_image |
| **字符偏移锚点** | `start_pos` / `end_pos` | `canonical_md?pos=1200-2224` | canonical_md / plain_text |
| **时间戳锚点** | `time_start` / `time_end` | `audio_segment?t=120.5-180.3` | transcript / audio_segment |

**锚点跳转 API**：

```python
# REST API: 锚点跳转
GET /api/v1/entities/{entity_id}/anchor-jump
    ?chunk_id=abc123/canonical_md/#3
    &target_rep=page_image        # 跳转目标 Rep（可选，默认 chunk 所在 Rep）
    &view=layout                  # 视图模式：text | layout | structural

# 响应
{
  "jump_url": "/ws/kb/abc123/page_image?page=7&bbox=72,120,540,144",
  "anchor": {
    "type": "bbox",
    "page_number": 7,
    "bbox": [72, 120, 540, 144],
    "highlight_text": "## Q3 Pricing\nEnterprise: $4.2B, Consumer: $1.8B..."
  },
  "cross_rep_anchors": {
    "canonical_md": "#q3-pricing",
    "ocr_text": "#q3-pricing",
    "page_image": "?page=7&bbox=72,120,540,144",
    "vlm_md": "#q3-pricing"
  }
}
```

**跨 Rep 锚点一致性**：

```text
同一 Chunk 在不同 Rep 中的锚点必须指向同一语义位置：

canonical_md#q3-pricing  ←→  page_image?page=7&bbox=72,120,540,144
         ↑                              ↑
         └──── 共享 layout_json ────────┘
              block_id=b1, page=7, bbox=[72,120,540,144]

保证机制：
1. layout_json 的 block_id 是锚点的唯一标识
2. 每个 block 含 start_pos（→ Markdown 锚点）+ page_number + bbox（→ 版面锚点）
3. IndexStep 映射 layout 时，将 block_id 写入 chunk.layout.blocks[].block_id
4. 前端通过 block_id 在任意 Rep 视图中定位同一语义位置
```

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

### 4.5 Pipeline（两套独立流水线）

> **关键分离**：RepPipeline（内容变换）和 IndexPipeline（索引构建）是两套独立的流水线，各自有独立的 Plugin 体系。RepPipeline 产出 Representation 文件；IndexPipeline 消费 Representation 文件产出搜索索引。两者不混合在同一条流水线中。

#### 4.5.1 RepPipeline（内容变换流水线）

```json
{
  "pipeline_id": "rep_pipeline_b",
  "pipeline_type": "rep",
  "name": "OCR 内容变换",
  "entity_types": ["document"],
  "steps": [
    { "step_id": "render_page", "required_input_reps": ["raw"], "output_reps": ["page_image"] },
    { "step_id": "ocr",          "required_input_reps": ["page_image"], "output_reps": ["ocr_text"] }
  ],
  "enabled": true,
  "priority": 2
}
```

> `step_id` 对应 `RepStepRegistry`（§6.6）中的 key；运行期由 `RepPipelineOrchestrator` 通过 `RepStepRegistry.get(step_id)` 解析为具体 RepStep 实例。

**RepPipeline 特征**：
- 每个 step 是一个 `RepStep`（§6.6），实现 `PipelineStep` Protocol
- step 产出 Representation 文件（.md / .json / .png 等），写入 OSS
- step 之间有血缘关系（上游变 → 下游 stale）
- step 可由第三方 Plugin 注入（注册到 `RepStepRegistry`）

#### 4.5.2 IndexPipeline（索引构建流水线）

```json
{
  "pipeline_id": "index_pipeline_text",
  "pipeline_type": "index",
  "name": "文本索引构建",
  "required_reps": ["canonical_md", "ocr_text"],
  "steps": [
    { "step_id": "chunk_and_embed_text", "required_reps": ["canonical_md", "ocr_text"] },
    { "step_id": "build_vector_index",   "index_type": "semantic" },
    { "step_id": "build_fts_index",      "index_type": "lexical" }
  ],
  "enabled": true
}
```

> `step_id` 对应 `IndexStepRegistry`（§6.7）中的 key；运行期由 `IndexPipelineOrchestrator` 通过 `IndexStepRegistry.get(step_id)` 解析为具体 IndexStep 实例。

**IndexPipeline 特征**：
- 每个 step 是一个 `IndexStep`（§6.7），实现 `IndexStep` Protocol
- step 消费 Representation 文件，产出索引结构（Lance index / 内存图等）
- step 之间**无血缘**（索引是派生物，丢了可重建）
- step 可由第三方 Plugin 注入（注册到 `IndexStepRegistry`）
- **触发时机**：RepPipeline 全部完成后，由 IndexPipelineOrchestrator 自动调度

#### 4.5.3 两套流水线的对比

| 维度 | RepPipeline | IndexPipeline |
|---|---|---|
| 本质 | 内容变换 | 搜索结构构建 |
| 产出 | Representation 文件 | 索引（vector / FTS / graph） |
| 血缘 | 有（上游变 → 下游 stale） | 无（索引可重建） |
| 触发 | 内容变化 / 用户请求 | Rep ready / 索引过期 |
| 失败影响 | 知识缺失 | 检索能力缺失（内容仍在） |
| 版本 | 跟随 entity_version | 跟随 lance_version |
| Plugin 注册表 | `RepStepRegistry` | `IndexStepRegistry` |
| 编排器 | `RepPipelineOrchestrator` | `IndexPipelineOrchestrator` |

**Pipeline 定义的存储位置**：

- v0.1：代码内注册（Python dataclass / YAML config），随服务部署。
- v0.2：支持动态注册（Pipeline 定义存 OSS，运行时加载）。

### 4.6 存储模型：Entity 目录自包含 + Rep 写 OSS / Index 写 Parquet → Lance

> **关键决策**：RepPipeline 产出 Rep 文件（写 OSS），**不写** staging Parquet；IndexPipeline 消费 Rep 文件产出可检索单元（写 staging Parquet）+ Lance 索引。两者完全解耦，写入路径分开。

```text
┌─────────────────────────────────────────────────────────────┐
│  Rep 写入路径（RepPipeline → Rep 文件）                       │
│   RepStep.execute() → 写 OSS Rep 文件 + 打 Rep OSS Tag        │
│   （无 Parquet、无 Lance 写入）                               │
├─────────────────────────────────────────────────────────────┤
│  Index 写入路径（IndexPipeline → chunk/vector/index）         │
│   IndexStep.execute() → 写 staging Parquet → Lance Watcher    │
│   同步 → Lance 索引                                          │
└─────────────────────────────────────────────────────────────┘
```

#### OSS 目录结构 + OSS Object Tagging

**核心决策**：
1. **每个 Entity 一个目录**，所有 representation 文件 + Lance 数据都在这个目录下，自包含。
2. **准零持久化元数据** — 运行时从 OSS Tag + 路径实时组装（零持久化运行）；但关键不可推导信息（`rag_status` / `labels` / `version`）以 sidecar 文件持久化（`.entity_manifest.json` + `.version_log.jsonl`），作为灾难恢复的 Ground Truth（详见 §5.12）。
3. **两套 OSS Object Tagging** — Entity Tag（7个，打在 original 上）+ Representation Tag（7个，打在每个 rep 文件上），作为运行时加速缓存（Tag 可从 Ground Truth 重建）。
4. **VFS 实时扫描 prefix** 重建目录树 + 从**目录层级 + Pipeline 注册表**推导血缘 DAG，所有元数据从 OSS 实时获取。
5. **1 张 Lance 表**：`representations.lance`（Entity 目录内）。每行 = 一个可检索单元（chunk），PK = `(entity_id, rep_type, chunk_index)`。

```text
vector-lake/{workspace_id}/{collection_id}/
│
├── {entity_id}/                                 ← Entity 目录（自包含）
│   ├── source/                                  ← L0: 原始文件
│   │   ├── original                             ← raw 文件（带 Entity OSS Tag，10个）
│   │   ├── .entity_manifest.json                ← 不可推导信息持久化（§5.12）
│   │   └── .version_log.jsonl                   ← 版本历史 append-only（§5.12）
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
- **准零持久化元数据**：运行时从 OSS Tag + 路径实时组装（零持久化运行）；不可推导信息（rag_status/labels/version）以 sidecar 持久化（§5.12）。
- **每个 representation 文件自带 OSS Tag**：业务元数据直接附着在文件上，删除文件时 Tag 自动消失，不存在"孤儿元数据"问题。血缘从目录层级推导，不存于 Tag。Tag 可从 Ground Truth 重建。

#### 1 张 Lance 表 + OSS Object Tagging

| # | 文件 | 位置 | 用途 |
| --- | --- | --- | --- |
| 1 | `representations.lance` | Entity 目录内 | 该 Entity 的所有可检索单元（含 vector + text） |
| — | OSS Object Tagging | raw 对象 | Entity 的状态/标签（rag_status / labels / sync_state） |

**为什么只用 1 张 Lance 表**：
- `catalog.lance` 不需要 — VFS 扫描 prefix 即可获取所有 Entity 目录。
- `lineage.json` 不需要 — 血缘从**目录层级 + Pipeline 注册表**实时推导（目录层级即血缘深度）。
- `entity.json` 不需要 — Entity 元数据从 OSS Tag 实时读取（不可推导信息从 `.entity_manifest.json` 读取）。
- 所有元数据都可以从 Ground Truth（文件 + 路径 + sidecar）重建，准零持久化 → 运行时无同步问题，灾难时可恢复。

#### OSS Object Tagging（两套 Tag Schema：Entity + Representation）

**所有元数据存在 OSS 对象的 Tag 上**，通过 `PutObjectTagging` / `GetObjectTagging` API 读写。

**两套 Tag Schema**：

- **Entity Tag**（打在 `{entity_id}/original` 对象上）：Entity 级元数据 + 同步状态
- **Representation Tag**（打在每个 representation 文件上）：血缘 + 变换 + 状态

##### Entity Tag Schema（7 个 Tag，打在 original 对象上）

> **设计决策**：Entity Tag 从 10 个精简为 7 个，移除 `workspace_id` / `collection_id` / `entity_id`（可从 OSS 路径推导），为 v0.2 预留 3 个位置（`sync_state` / `quality_score` / `custom_1`）。

| Key | 取值 | 说明 |
| --- | --- | --- |
| `rag_status` | `enabled` / `hidden` / `deleted` | 用户意图，VFS 过滤 |
| `entity_type` | `document` / `image` / `audio` / `video` / `table` | Entity 类型 |
| `name` | `pricing.pdf` | 原始文件名 |
| `content_hash` | `sha256_xxx` | raw 内容的 SHA-256 |
| `version` | `1` | Entity 版本号 |
| `labels` | `pricing,finance,Q3,strategy,Q3-review` | 业务标签（合并 category/project，逗号分隔） |
| `model_version` | `embedding-v5-retrieval` | 最新 embedding 模型版本 |

> **v0.2 预留 Tag**（当前不写入，v0.2 启用）：
> - `sync_state`：`idle` / `syncing` / `ready` / `failed` / `stale` — Projector 同步状态
> - `quality_score`：`0.0` - `1.0` — Entity 质量评分
> - `custom_1`：自定义扩展字段

**从路径推导的字段**（不存 Tag，从 OSS 路径实时解析）：

| 字段 | 推导方式 |
|---|---|
| `workspace_id` | 路径第 2 段：`vector-lake/{workspace_id}/...` |
| `collection_id` | 路径第 3 段：`vector-lake/{ws}/{collection_id}/...` |
| `entity_id` | 路径第 4 段：`vector-lake/{ws}/{col}/{entity_id}/...` |

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
- 最多 10 个 tag → Entity Tag 用 7 个（预留 3 个给 v0.2），Representation Tag 用 7 个（预留 3 个）
- 每个 tag value 最大 128 字节 → 当前所有字段值远小于此限制
- 只能打在具体对象上 → Entity Tag 打在 `original` 上，Representation Tag 打在各自文件上
- 列表过滤只能精确匹配 → 业务标签过滤在 VFS 内存中做
- PutObjectTagging 不支持原子 CAS → 用 `CopyObject` + `x-oss-copy-source-if-match` 实现（见 §4.6 同步协议 Stage 2）

**OSS LIST API 限制**（F3）：
- 每次 LIST 最多返回 1000 个对象（`max-keys=1000`）
- 10K Entity × 10 文件 = 100K 对象 → 100 次 LIST → ~10s（可接受）
- 100K Entity × 10 = 1M 对象 → 1000 次 LIST → ~100s（不可接受）
- **v0.1 策略**：VFS 维护 Redis 缓存，冷启动时全量 LIST + 增量 Event 更新
- **v0.2 策略**：引入 `_manifest/reps.jsonl`（§5.12.11）替代全量 LIST

**多文件 Rep 的 Tag 策略**（E1）：
- 一个 100 页 PDF 产出 100 个 `page_image/page_001.png` ... `page_image/page_100.png`
- 逐文件打 Tag = 100 × 7 = 700 次 `PutObjectTagging` API 调用（代价高）
- **v0.1 策略**：多文件 Rep 只在目录的 `.meta.json` 打一次 Tag（包含 `rep_type` / `count` / `content_hash_set`），不在每个文件上打 Tag
- **v0.2 策略**：引入 `_manifest/reps.jsonl` 统一管理

**Lance metadata 大小限制**（F5）：
- Lance `manifest.metadata` 是 Protobuf `map<string, bytes>`，理论上无大小限制
- 但每次 `update_metadata()` 会重写整个 Manifest
- **v0.1 限制**：每个 Entity 最多 5 个 Index（semantic / textual / structural / graph / multimodal），metadata 大小可控
- **v0.2 迁移**：Index metadata 迁移到 `_manifest/indexes.jsonl`

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

#### 4.6.x v0.2 三层元数据架构预览（参照成熟项目）

> **设计目标**：v0.2 在 v0.1 "准零持久化"基础上，引入 Delta Lake / Iceberg / lakeFS / Lance 4 个成熟项目验证过的元数据架构：事务日志 + 原子指针 + 快速索引 + Merkle 血缘。详见 §5.12.9 - §5.12.13。
>
> **v0.1 策略** vs **v0.2 策略**：

| 维度 | v0.1 策略 | v0.2 策略 | 借鉴项目 |
|---|---|---|---|
| **变更历史** | `.version_log.jsonl`（仅 Entity 版本） | `_log/` 事务日志（所有 Rep/Index/Edge 变更） | Delta Lake |
| **原子性** | 先写文件再打 Tag（两步） | `_current` 指针原子交换（compare-and-swap） | Apache Iceberg |
| **状态查询** | LIST prefix + Tag 解析 | 读 `_manifest/reps.jsonl`（O(1)） | Apache Iceberg |
| **血缘** | 从目录层级推导（每次重算） | Merkle 树内容寻址（O(diff_size) diff） | lakeFS |
| **Schema 演进** | 未定义 | 显式 schema_version + 兼容性规则 | Delta + Iceberg + Lance |
| **Time Travel** | 不支持 | 通过 `_log/N.json` 回放 | Delta + Iceberg + Lance |
| **零拷贝快照** | 不支持 | Merkle 树复用未修改 Rep | lakeFS |
| **灾难恢复** | sidecar + Tag 重建 | checkpoint + 日志重放 | Delta + Iceberg |

**v0.1 → v0.2 演进路径**：

```text
v0.1（当前）
  ├─ OSS Object Tagging (Entity Tag + Rep Tag)
  ├─ .entity_manifest.json + .version_log.jsonl
  └─ Reconciler Phase 0/1/2/3
       ↓ v0.2 阶段 1
v0.2 阶段 1
  ├─ 新增 _current 指针
  ├─ 写入协议升级为"写文件 → 写日志 → 原子交换 _current"
  └─ 读取协议升级为"读 _current → 读 _manifest"
       ↓ v0.2 阶段 2
v0.2 阶段 2
  ├─ 完整 _log/ 事务日志（add/remove/stale/index_built actions）
  └─ Time Travel API（GET /v1/entities/{id}/at?version=N）
       ↓ v0.2 阶段 3
v0.2 阶段 3
  ├─ _manifest/ 快速索引（reps.jsonl / indexes.jsonl / edges.jsonl）
  └─ 替代"全量 LIST prefix" → 大规模场景秒级响应
       ↓ v0.2 阶段 4
v0.2 阶段 4
  └─ Checkpoint 机制（每 100 次 commit 合并，参考 Delta）
       ↓ v0.3
v0.3
  ├─ Merkle 树血缘（Content-addressable Ranges）
  ├─ Schema Evolution 规则
  └─ 零拷贝 Entity 快照
```

> **设计哲学**：v0.1 优先解决"能跑 + 基础可靠性"（sidecar + Reconciler），v0.2 引入"行业标准 ACID"（事务日志 + 原子指针），v0.3 引入"高级能力"（Merkle + Schema Evolution + Time Travel）。这与 Delta Lake / Iceberg / lakeFS 的演进路径一致。

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

### 5.7 状态联动规则（两阶段）

> 解耦后，状态联动分为 **Rep 联动**（内容层）和 **Index 联动**（索引层），两者独立触发、独立修复。

#### 5.7.1 Rep 联动（内容层）

| 触发事件 | 联动动作 |
| --- | --- |
| raw object `content_hash` 变化 | entity.version++；沿 RepPipeline 的 `input_reps` 边向下级联：所有下游 Rep 文件 OSS Tag `status`→`stale`；自动触发 RepPipeline 重建 |
| Rep OSS Tag `status`→`ready` | 触发 `rep_all_ready` 事件 → IndexPipelineOrchestrator 评估是否需要重建索引 |
| Rep OSS Tag `status`→`stale` | 沿 RepPipeline `input_reps` 边向下级联：下游 Rep `status`→`stale`；自动触发下游 RepPipeline 重建 |
| Rep OSS Tag `status`→`failed` | RepPipeline `partial_success`；已有 Rep 的 Index 仍可用 |
| OSS Tag `rag_status`→`hidden` | entity.status=hidden；所有 Rep + Index 标 `hidden` |
| OSS Tag `rag_status`→`deleted` | entity.status=deleted；Rep + Index 软删除；OSS 原文件保留 |
| RepPipeline 新增 | 对已有 entity 按需重跑新 RepPipeline；不影响已有 Rep |

#### 5.7.2 Index 联动（索引层）

| 触发事件 | 联动动作 |
| --- | --- |
| `rep_all_ready` 事件 | IndexPipelineOrchestrator 评估：若 `index_built_from_hash` ≠ 当前 active Rep 的 `content_hash` 并集 → 标 Index stale → 自动重建 |
| Index stale | 自动触发 IndexPipeline 重建；**不级联**（Index 之间独立） |
| Index 重建失败 | Rep 不受影响；检索能力暂时缺失；下次 reconcile 重试 |
| embedding 模型升级 | 检测 `model_version` 过期；标对应 Index stale → 触发 IndexPipeline 重跑 |
| IndexPipeline 新增 | 对已有 Rep 按需重跑新 IndexPipeline；不影响已有 Index |

#### 5.7.3 跨阶段联动

| 触发事件 | 联动动作 |
| --- | --- |
| Rep `status`→`stale` | 该 Rep 对应的 Index 标 stale（因为 `index_built_from_hash` 不再匹配） |
| Rep `status`→`ready`（全部 active） | 发出 `rep_all_ready` 事件 → IndexPipelineOrchestrator 评估重建 |
| Rep 重建中（部分 stale） | Index 等待，不触发重建（避免基于不完整 Rep 建索引） |

### 5.8 内容寻址变更检测

- `detect` 阶段计算 raw bytes 的 SHA-256 `content_hash`。
- 每个 Rep 文件计算内容的 SHA-256 `content_hash`（写入 Representation Tag）。
- 每个 chunk 计算文本内容的 SHA-256 `content_hash`。
- Reconcile 比较 `content_hash` 而非 `etag`（etag 在 multipart upload 时不可靠）。
- Parser 升级时，强制对受影响的 entity_type 重跑 RepPipeline，即使 content_hash 未变。

### 5.9 两阶段一致性校验

> 解耦后，Reconciler 的职责也拆为两阶段：**Rep↔Raw 校验**和**Index↔Rep 校验**。两者独立运行、独立修复。

#### 5.9.1 校验1：Rep ↔ Raw 一致性（内容一致性）

**校验内容**：每个 Rep 文件的内容是否与它声明的 `source_content_hash`（即 raw 的 `content_hash`）一致。

```text
Reconciler 周期任务（每 15 min）— Rep 阶段
  ├─ 扫描所有 Rep 文件的 Representation Tag
  ├─ 对比 Rep Tag 的 source_content_hash vs Raw 的 content_hash
  ├─ 不匹配 → 标 Rep stale → 触发 RepPipeline 重建
  ├─ 检查 Rep 文件是否存在（OSS 404 → 标 failed）
  └─ 检查 Rep 文件的 body_hash vs Tag 中的 content_hash（防篡改/损坏）
```

**校验场景**：

| 场景 | 检测方式 | 修复 |
|---|---|---|
| Raw 更新但 Rep 未重建 | `source_content_hash` 不匹配 | 标 stale → RepPipeline 重建 |
| Rep 文件损坏/丢失 | OSS 404 或 `body_hash` 不匹配 | 标 failed → RepPipeline 重建 |
| RepPipeline 升级后旧 Rep 过时 | `pipeline_version` Tag 不匹配 | 标 stale → RepPipeline 重建 |
| Rep 被意外删除 | OSS 404 | 标 deleted → RepPipeline 重建（如果 raw 仍在） |

#### 5.9.2 校验2：Index ↔ Rep 一致性（索引一致性）

**校验内容**：每个 Index 是否基于当前所有 active Rep 的最新 `content_hash` 构建。

```text
Reconciler 周期任务（每 15 min）— Index 阶段
  ├─ 扫描所有 Index 的元数据（index_built_from_hash）
  ├─ 对比 index_built_from_hash vs 当前 active Rep 的 content_hash 并集
  ├─ 不匹配 → 标 Index stale → 触发 IndexPipeline 重建
  ├─ 检查 Index 是否存在（Lance index 缺失 → 标 stale）
  └─ 检查 embedding model_version 是否过期 → 标 stale
```

**校验场景**：

| 场景 | 检测方式 | 修复 |
|---|---|---|
| Rep 重建后 Index 未重建 | `index_built_from_hash` 不匹配 | 标 stale → IndexPipeline 重建 |
| Index 损坏 | Lance index 校验失败 | 标 stale → IndexPipeline 重建 |
| Embedding 模型升级 | `model_version` 过期 | 标 stale → IndexPipeline 重建 |
| IndexPipeline 新增 | 无对应 Index 记录 | 首次构建 |
| Rep 部分 stale | `index_built_from_hash` 不完整 | 等待 Rep 全部 active 后再重建 |

#### 5.9.3 两阶段 Reconciler 的执行顺序

```text
Reconciler 周期（每 15 min）
  │
  ├─ Phase 0: Tag 可靠性校验（每天一次，详见 §5.12.3）
  │   ├─ 随机采样 1% 的 Rep 文件
  │   ├─ 计算 body_hash vs Tag content_hash
  │   ├─ 不匹配 → 以 body_hash 为准，重写 Tag + 告警
  │   └─ Tag 缺失 → 从 Ground Truth 重建（§5.12.4）
  │
  ├─ Phase 1: Rep ↔ Raw 校验
  │   ├─ 扫描所有 Rep
  │   ├─ 检测不一致
  │   ├─ 标 stale / failed
  │   └─ 触发 RepPipeline 重建
  │
  ├─ Phase 2: Index ↔ Rep 校验（等 Phase 1 完成后）
  │   ├─ 扫描所有 Index
  │   ├─ 检测不一致
  │   ├─ 标 stale
  │   └─ 触发 IndexPipeline 重建
  │
  └─ Phase 3: 跨阶段校验
      ├─ 检查是否有 Rep 全部 active 但 Index 仍 stale 的情况
      └─ 触发 IndexPipeline 重建
```

**关键不变量**：
- Phase 0 在 Phase 1 之前执行（确保 Tag 可靠后再做一致性校验）
- Phase 2 必须在 Phase 1 完成后执行（避免基于 stale Rep 建索引）
- Index 重建失败不影响 Rep（两阶段独立）
- 两个 Phase 可以并行运行在不同 Entity 上（Entity A 的 Rep 校验 和 Entity B 的 Index 校验不冲突）

#### 5.9.3 Phase 3：Projector 一致性校验

```text
Reconciler 周期（每 15 min）— Phase 3（在 Phase 1+2 完成后）
  ├─ 扫描 ProjectorStepRegistry 启用的所有 Projector
  ├─ 对每个 Projector：
  │   ├─ 扫描外部目标（如 ~/wiki/、/tools/* 路由缓存）
  │   ├─ 对比 artifact content_hash vs Lake 内 active Rep 的 content_hash
  │   └─ 不匹配 → 标 ProjectorStep 失败 → 触发对应 RepPipeline 重跑（包含 ProjectorStep）
  └─ Projector 失败不影响 Rep 和 Index（独立）
```

**Projector 校验场景**：

| 场景 | 检测方式 | 修复 |
|---|---|---|
| Rep 重建后 Projector 旧 artifact 未更新 | artifact `content_hash` vs active Rep `content_hash` | 触发 ProjectorStep 重跑 |
| 外部 vault 文件被用户删除 | OSS 404 | 触发 ProjectorStep 重跑 |
| Projector 配置变更（如 `protect_user_edits` 切换） | 配置 diff | 触发全量 `rebuild()` |
| 外部 artifact 数据漂移 | hash 比对 | 触发 `rebuild()` |

#### 5.9.4 `rep_all_ready` 事件精确定义

> **定义**：`rep_all_ready` 事件由 `RepPipelineOrchestrator` 发出，表示**该 Entity 的所有 enabled RepPipeline 的所有 RepStep 产出已收敛**。

**收敛条件**（全部满足才发）：
1. 该 Entity 的所有 enabled `RepPipeline` 已结束（`pipeline_run.status ∈ {success, partial_success, failed}`）
2. 该 Entity 的所有 enabled `RepPipeline` 的 `required_input_reps` 已被满足（Rep `status ∈ {ready, skipped}`）
3. 至少一条 RepPipeline 产出了新 Rep（防止空跑污染事件流）

**`partial_success` 语义**：
- 至少一条 RepStep 失败，但其他 RepStep 成功 → 标 `partial_success`
- 此时仍发 `rep_all_ready` 事件（因为有 Rep ready），但附带 `failed_steps` 列表
- IndexPipelineOrchestrator 收到事件后，**只基于 `ready` 的 Rep 评估是否重建索引**（跳过 failed Rep）

**`failed` 语义**：
- 所有 RepStep 都失败 → 标 `failed`
- **不发** `rep_all_ready` 事件
- IndexPipelineOrchestrator 等待下次重试

**事件负载**：

```json
{
  "event_type": "rep_all_ready",
  "entity_id": "...",
  "entity_version": 3,
  "ready_reps": ["canonical_md", "ocr_text"],
  "failed_reps": ["vlm_md"],
  "skipped_reps": [],
  "rep_content_hashes": {
    "canonical_md": "sha256:abc...",
    "ocr_text": "sha256:def..."
  },
  "build_from_hash_set": "sha256:combined_set_hash",
  "pipeline_runs": ["run_001", "run_002"]
}
```

> `build_from_hash_set` 是该 Entity 当前所有 `ready` Rep 的 `content_hash` 排序后拼接再 SHA-256，用于 IndexPipeline 的 `index_built_from_hash` 比对（§5.9.2）。

### 5.10 Index Status（独立状态模型）

> **关键分离**：Rep 有自己的状态（§5.4），Index 也有自己的状态。两者独立维护、独立更新。

#### 5.10.1 Index Status 定义

| 状态 | 含义 | 触发 |
|---|---|---|
| `built` | 索引构建完成，与当前 active Rep 一致 | IndexStep.execute() 成功；`index_built_from_hash` == `build_from_hash_set` |
| `stale` | 索引存在但与当前 active Rep 不一致 | Phase 2 检测：`index_built_from_hash` ≠ `build_from_hash_set`；或 Rep 状态变化 |
| `failed` | 索引构建失败 | IndexStep.execute() 抛异常 |
| `deleted` | 索引被删除（entity 删除或索引主动清理） | entity.status=deleted；或显式 `drop_index()` |

#### 5.10.2 Index Status 存储位置

> **决策**：Index 状态存储在 **Lance dataset 的 custom metadata**（不是 OSS Tag、不是单独的 metadata 文件）。

```python
# Lance dataset 的 custom metadata（写入 metadata key）
lance_dataset = LanceDataset.open(...)
lance_dataset.update_metadata({
    "index_status": "built",                    # built | stale | failed | deleted
    "index_built_from_hash": "sha256:abc...",   # 当前索引基于的 build_from_hash_set
    "index_built_at": "2026-06-06T10:00:00Z",
    "index_model_version": "v5-2026-05",        # embedding 模型版本
    "index_pipeline_id": "index_pipeline_text",
    "index_failed_reason": null,                # 失败原因（failed 状态时填）
})
```

**为什么用 Lance metadata 而非 OSS Tag**：
- 索引是 Lance 数据集的内部结构，metadata 是其原生位置
- Lance 自带 version 管理，metadata 跟随 version 自动备份
- 避免在 OSS 端为每个 Index 创建额外的元数据文件

> **v0.2 升级（参照 Lance Manifest + Delta + Iceberg）**：Entity 级 Manifest（`_manifest/indexes.jsonl`，见 §5.12.12）作为 Index Status 的 **Truth of State**，Lance dataset custom metadata 仅作为快速缓存。Manifest 写入协议：先写 Lance → 再写 `_manifest`（如果失败可重建，从 Lance 自检恢复）。

#### 5.10.3 Index Status 联动

| 触发事件 | 联动动作 |
| --- | --- |
| IndexStep.execute() 成功 | 写 `index_status=built` + 更新 `index_built_from_hash` |
| IndexStep.execute() 失败 | 写 `index_status=failed` + 填 `index_failed_reason` |
| Rep `status` 变化（`build_from_hash_set` 变化） | 标 `index_status=stale` |
| Phase 2 Reconciler 检测不一致 | 标 `index_status=stale` + 触发 IndexPipeline 重建 |
| embedding 模型升级（`index_model_version` 不匹配） | 标 `index_status=stale` + 触发重跑 |
| entity `status=deleted` | 标 `index_status=deleted` + **保留 Lance 数据 30 天**（软删除）；`destroy()` 才物理删除 Lance |
| embedding 模型升级（全量重建） | 按 **Index 重建优先级** 分批重建（见下方） |

**Index 重建优先级**（E4 修复，解决全量重建代价过高问题）：

| 优先级 | 条件 | 示例 |
|---|---|---|
| **high** | Entity 近 7 天被检索过 + `rag_status=enabled` | 热点数据，优先重建 |
| **medium** | Entity 近 30 天被检索过 | 温数据，第二批重建 |
| **low** | Entity 30 天内未被检索 | 冷数据，最后重建或跳过 |

> 模型升级时按优先级分批投递到 `index_pipeline`，每批 100 个 Entity，避免一次性打满 GPU/API 配额。

### 5.11 Edge 生命周期

> **v0.1 简化**：Edge v0.1 仅支持"由 RepPipeline 编译产物自动产出 + 手动 API 创建"，不支持独立 Edge Pipeline。

#### 5.11.1 Edge 状态

| 状态 | 含义 |
|---|---|
| `active` | 边生效，参与检索 |
| `stale` | 边关联的 src 或 dst Entity 处于 stale，Edge 暂不参与检索 |
| `deleted` | 边已删除（src 或 dst Entity 删除时级联） |

#### 5.11.2 Edge 生命周期事件

| 触发事件 | 联动动作 |
| --- | --- |
| `RepPipeline.d_graph` 产出 `graph_json`（v0.2） | 解析 `graph_json` 中的边，自动写入 Edge 存储 |
| 手动 `POST /edges`（v0.1） | 创建 Edge，`status=active` |
| src 或 dst Entity `status=deleted` | 级联 Edge `status=deleted` |
| src 或 dst Entity `status=stale` | 关联 Edge `status=stale`（不参与检索） |
| `RepPipeline.d_graph` 重跑且新 `graph_json` 缺某边 | 该边 `status=deleted`（v0.2） |

#### 5.11.3 v0.1 范围

- ✅ 手动创建/查询/删除 Edge 的 API
- ✅ Edge 与 Entity 状态联动（stale / deleted）
- ❌ 自动从 `graph_json` 解析（v0.2，因 `compile_graph_json` 是 v0.2）
- ❌ 反向回写（从 `~/wiki/` wikilink 解析回 Edge，v0.2）
- ❌ Edge 自己的 Lint 规则（v0.2）

### 5.12 元数据可靠性与重建策略

> **核心原则**：**文件内容 + 路径结构 = Ground Truth（可重建），OSS Tag = 加速缓存（可从 Ground Truth 重建）**。
>
> 当前 PRD 的"零持久化"原则在运行时不变（从 OSS Tag + 路径实时组装元数据），但关键不可推导信息（用户意图、版本历史）必须有独立于 Tag 的持久化，作为灾难恢复的 Ground Truth。此即**准零持久化**原则。

#### 5.12.1 不可推导信息持久化

以下信息无法从文件/路径确定性地推导，必须独立持久化：

| 信息 | 持久化方式 | 位置 | 说明 |
|---|---|---|---|
| `rag_status` | `.entity_manifest.json` | `source/.entity_manifest.json` | 用户意图（enabled/hidden/deleted） |
| `labels` | `.entity_manifest.json` | `source/.entity_manifest.json` | 业务标签 |
| `version` | `.version_log.jsonl` | `source/.version_log.jsonl` | 版本历史（append-only） |

**Entity Manifest 文件**（`source/.entity_manifest.json`）：

```json
{
  "rag_status": "enabled",
  "labels": ["pricing", "finance"],
  "version": 3,
  "content_hash": "sha256:abc...",
  "entity_type": "document",
  "name": "pricing.pdf",
  "updated_at": "2026-06-06T10:00:00Z"
}
```

> 写入时机：与 Tag 写入绑定——先写 `.entity_manifest.json`，再写 Tag。Tag 写入失败不影响 manifest。
>
> **关键约束**：OSS `PutObject` **不支持** `if-match`（阿里云 OSS / AWS S3 / MinIO 均不支持，只有 `CopyObject` 支持）。v0.1 采用 **last-writer-wins** 策略，v0.2 用 `CopyObject` + `if-match` 实现原子交换。

**版本日志文件**（`source/.version_log.jsonl`）：

```text
{"version": 1, "content_hash": "sha256:aaa...", "timestamp": "2026-06-01T10:00:00Z", "trigger": "ingest"}
{"version": 2, "content_hash": "sha256:bbb...", "timestamp": "2026-06-03T14:00:00Z", "trigger": "raw_update"}
{"version": 3, "content_hash": "sha256:ccc...", "timestamp": "2026-06-06T10:00:00Z", "trigger": "raw_update"}
```

> 追加写入（append-only），不修改历史行。Tag 丢失时从最后一行恢复 `version` 字段。

#### 5.12.2 Tag 写入原子性协议 + 元数据写入状态机

```text
RepStep 写入协议（v0.1: last-writer-wins + Reconciler 修复）：
  Phase 1: 写 Rep 文件到 OSS（内容就绪）
  Phase 2: 写 OSS Tag（PutObjectTagging，单次 API 原子操作）
  Phase 2b: 写 .entity_manifest.json（如果涉及 Entity 级 Tag 变更）
  Phase 2c: 写 .version_log.jsonl（append-only，如果 version 变更）

读取协议：
  正常路径：读 Tag（快）
  Tag 缺失/不完整：读 .entity_manifest.json（慢但可靠）+ 从路径推导

异常检测：
  文件存在 + Tag 缺失 → "写入中断" → 标 status=stale → 触发重建
  文件存在 + Tag 不完整 → 以 .entity_manifest.json 为准 → 重写 Tag
```

**元数据写入状态机**（解决 Tag / manifest / 文件 三重冗余一致性）：

```text
写入状态（per Entity，存储在 Redis）：
  CLEAN ──写文件──► FILE_WRITTEN ──写manifest──► MANIFEST_WRITTEN ──写Tag──► CLEAN
    │                    │                          │                       │
    │                    │ (crash)                  │ (crash)               │ (crash)
    │                    ▼                          ▼                       ▼
    │               STALE_FILE                 MANIFEST_ONLY            TAG_MISSING
    │               (Reconciler:               (Reconciler:            (Reconciler:
    │                标stale→重建)               从manifest重建Tag)       从manifest重建Tag)
    │
    └── Reconciler 每次扫描检测非 CLEAN 状态 → 自动修复 → 回到 CLEAN
```

| 状态 | 含义 | 检测方式 | 自动修复 |
|---|---|---|---|
| `CLEAN` | 文件 + manifest + Tag 三者一致 | — | — |
| `FILE_WRITTEN` | 文件存在但 manifest 未写 | 文件存在 + manifest 缺失/旧 | 标 stale → 触发重建 |
| `MANIFEST_WRITTEN` | manifest 已写但 Tag 未写 | manifest 比 Tag 新 | 从 manifest 重建 Tag |
| `TAG_MISSING` | Tag 缺失/不完整 | Tag 缺失关键字段 | 从 manifest 重建 Tag |

#### 5.12.3 Reconciler Phase 0：ETag 校验（零下载）

> 在现有 Phase 1（Rep↔Raw）和 Phase 2（Index↔Rep）之前，增加 Phase 0 校验 Tag 与文件内容的一致性。
>
> **关键优化**：Phase 0 使用 **ETag 校验**（`HeadObject` 获取 OSS ETag），不下载文件计算 SHA-256。代价从 O(file_size) 降到 O(1)。只有 ETag 不匹配时才下载文件计算完整 SHA-256。

```text
Reconciler Phase 0（每天一次，非每 15 min）:
  ├─ 随机采样 1% 的 Rep 文件
  ├─ HeadObject 获取 ETag（零下载，O(1)）
  ├─ 对比 ETag vs Tag content_hash
  │   ├─ ETag = MD5（小文件）→ 直接对比 Tag content_hash 前 32 字符
  │   └─ ETag = multipart hash（大文件）→ 需下载计算 SHA-256
  ├─ 不匹配 → 下载文件计算完整 SHA-256 → 以 body_hash 为准，重写 Tag + 告警
  └─ Tag 缺失 → 从路径 + 命名约定 + ETag 重建 Tag
  └─ .entity_manifest.json 缺失 → 从 Tag 重建 manifest

手动触发：
  POST /v1/admin/verify?entity_id=...&mode=sampling  — 采样校验
  POST /v1/admin/verify?entity_id=...&mode=full       — 全量校验（代价高）
```

#### 5.12.4 元数据灾难重建流程

```text
灾难场景：OSS Tag 全部丢失
  │
  ├─ Step 1: VFS 全量扫描（从 OSS 路径重建目录树）
  │   ├─ 扫描 vector-lake/{ws}/{col}/ prefix
  │   └─ 从路径解析：entity_id, workspace_id, collection_id, stage, rep_type
  │
  ├─ Step 2: 重建 Entity Tag（从 .entity_manifest.json + 文件）
  │   ├─ 读取 source/.entity_manifest.json → 恢复 rag_status, labels, version
  │   ├─ 重新计算 raw bytes SHA-256 → 恢复 content_hash
  │   ├─ 从文件 MIME 推断 entity_type → 恢复 entity_type
  │   └─ 写回 Entity Tag（PutObjectTagging）
  │
  ├─ Step 3: 重建 Rep Tag（从路径 + 命名约定 + 文件内容）
  │   ├─ 从路径后缀 + 命名约定表 → 恢复 rep_type
  │   ├─ 从 RepStepRegistry 反查 → 恢复 pipeline_id, transform, modality
  │   ├─ 计算文件内容 SHA-256 → 恢复 content_hash
  │   ├─ status 暂设 "stale"（保守策略）
  │   └─ 写回 Rep Tag
  │
  ├─ Step 4: 重建 Index Status（从 Rep Tag + Lance metadata）
  │   ├─ 重新计算 build_from_hash_set
  │   ├─ 对比 Lance metadata 中的 index_built_from_hash
  │   └─ 不匹配 → 标 index_status=stale
  │
  ├─ Step 5: 全量 Reconcile（Phase 0 + Phase 1 + Phase 2）
  │
  └─ Step 6: 触发必要重建 + 产出 recovery_report.json

一键触发：
  POST /v1/admin/rebuild_tags?scope=workspace&workspace_id=...
  POST /v1/admin/rebuild_tags?scope=entity&entity_id=...
```

#### 5.12.5 Lance 损坏自动检测与恢复

```text
触发条件：
  1. Lance 查询抛异常（CorruptedError / SchemaError / IOError）
  2. Reconciler Phase 0 校验 Lance manifest 完整性
  3. 手动触发 POST /v1/entities/{entity_id}/rebuild_lance

自动恢复：
  Lance 损坏 → 标 index_status=failed → 触发 rebuild_lance()
  rebuild_lance() 从 OSS Rep 文件重跑 IndexPipeline → 重建 Lance
  重建失败 → 保留 index_status=failed + 告警 + 下次 Reconcile 重试
```

#### 5.12.6 VFS 漂移监控

```text
新增指标：
  vfs_drift_count          — Reconciler 每次扫描发现的漂移数量
  vfs_drift_type           — 漂移类型（missing_file / extra_file / tag_mismatch / hash_mismatch）
  vfs_reconcile_duration   — Reconciler 扫描耗时
  vfs_event_lag            — Event Listener 事件积压数量

告警规则：
  vfs_drift_count > 10 in 15 min → P2 告警
  vfs_reconcile_duration > 5 min → P3 告警
```

#### 5.12.7 Reconciler 分片扫描

```text
当前：全量扫描 vector-lake/{ws}/{col}/ prefix

改进（v0.2）：分片扫描
  ├─ 按 entity_id 前缀分片（0-9, a-f, g-m, n-s, t-z）
  ├─ 每个分片独立扫描、独立对账
  ├─ 15 min 内轮完所有分片
  └─ 大规模场景（100K+ Entity）下可配置并行扫描

v0.1 策略：全量扫描（简单可靠），但增加 reconcile_entities_scanned 指标监控
```

#### 5.12.8 `.meta.json` sidecar 与 Tag 的一致性模型（v0.2）

```text
优先级规则：
  1. .meta.json 存在 → 以 .meta.json 为准
  2. .meta.json 不存在 → 以 Tag 为准
  3. 两者冲突 → 以 .meta.json 为准，Tag 视为过期缓存

写入协议：
  先写 .meta.json（Conditional Write if-match etag）→ 再写 Tag
  Tag 写入失败不影响 .meta.json（下次 Reconciler 从 .meta.json 重建 Tag）
```

#### 5.12.9 成熟项目参照：事务日志 + 原子指针交换（v0.2）

> **设计目标**：解决 v0.1 元数据架构在"原子性、变更历史、大规模扫描"上的不足。参照 **Delta Lake**、**Apache Iceberg**、**lakeFS**、**Lance** 4 个成熟数据湖项目的设计。

**核心改造**：引入 **`_current` 指针 + `_log/` 事务日志 + `_manifest/` 快速索引** 三个组件。

```text
{entity_id}/
  ├─ _current                                ← L1: 当前状态指针（原子交换）
  │                                            内容：{ "log_offset": "/_log/000000000101.json",
  │                                                   "manifest_version": 101,
  │                                                   "schema_version": 2 }
  │
  ├─ _log/                                   ← L2: 事务日志（参考 Delta _delta_log）
  │   ├─ 000000000000.json                   ← append-only 提交日志
  │   ├─ 000000000001.json
  │   ├─ ...
  │   └─ 000000000100.checkpoint.jsonl       ← 周期 Checkpoint（参考 Delta）
  │
  ├─ _manifest/                              ← L3: 快速查找索引（参考 Iceberg Manifest）
  │   ├─ entity.json                         ← Entity 元数据（rag_status, labels, version, schema_version）
  │   ├─ reps.jsonl                          ← 所有 Rep 列表 + 列级统计（替代"每次 LIST prefix"）
  │   ├─ indexes.jsonl                       ← 所有 Index 列表
  │   └─ edges.jsonl                         ← 所有 Edge 列表
  │
  ├─ source/                                 ← 实际数据
  └─ ...
```

**事务日志格式**（每行一个 JSON action，参考 Delta Lake）：

```json
{"txn_id": 101, "ts": "2026-06-06T10:00:00Z", "action": "add",      "rep": {"path": "extract/canonical.md", "rep_type": "canonical_md", "content_hash": "sha256:abc", "size": 12345}}
{"txn_id": 102, "ts": "2026-06-06T10:01:00Z", "action": "remove",   "rep": "recognize/ocr_text.md"}
{"txn_id": 103, "ts": "2026-06-06T10:02:00Z", "action": "stale",    "rep_type": "ocr_text", "reason": "raw_update", "upstream_hash": "sha256:def"}
{"txn_id": 104, "ts": "2026-06-06T10:03:00Z", "action": "index_built", "index_type": "semantic", "build_from_hash": "sha256:combined"}
{"txn_id": 105, "ts": "2026-06-06T10:04:00Z", "action": "checkpoint", "version": 100, "manifest": "/_log/000000000100.checkpoint.jsonl"}
```

**写入协议**（基于 Iceberg 原子指针交换）：

```text
RepStep 写入流程（新协议）：
  1. 写 Rep 文件 → /extract/canonical.md
  2. 写事务日志 → /_log/000000000101.json（append，Conditional PUT if-match）
  3. 更新 _manifest → /_manifest/reps.jsonl 追加一行
  4. 原子交换 _current → PutObject with if-match on _current.etag
     ├─ 成功：新版本生效
     └─ 失败：旧版本继续生效，下次重试（写入幂等）

读取流程（新协议）：
  1. 读 /_current → 拿到当前 manifest version
  2. 读 /_manifest/reps.jsonl（O(1) 拿到所有 Rep 列表）
  3. 读具体 Rep 文件
```

**Checkpoint 协议**（参考 Delta Lake）：

```text
每 100 次 commit 触发一次 Checkpoint：
  1. 重放最近 100 次 commit
  2. 合并为单一 checkpoint.jsonl（包含所有 active Rep + Index + Edge）
  3. 写 /_log/000000000100.checkpoint.jsonl
  4. 原子交换 _current → 指向 checkpoint
  5. 历史 commit 保留（用于 time travel / 灾难恢复）
```

**关键优势**：
- **完整变更历史**：事务日志记录所有 Entity/Rep/Index 状态变更
- **原子性**：`_current` 指针的 compare-and-swap 保证 readers 永远看到 consistent snapshot
- **O(1) 状态查询**：读 `_manifest/reps.jsonl` 替代"全量 LIST prefix"
- **Time Travel**：通过指定 `_log/N.json` 回放到 Entity 的某个历史状态
- **灾难恢复**：从最近 checkpoint + 后续 commit 重放 = 完整重建

#### 5.12.10 成熟项目参照：Merkle 树血缘（v0.3）

> **设计目标**：把血缘关系从"每次重新计算"改为"显式持久化 + 内容寻址"。参考 **lakeFS Graveler** 的 2 层 Merkle 树。

```text
Entity Lineage Merkle Tree
  └─ Root (sha256 of all children)
       ├─ rep:raw              → sha256(content_hash)
       ├─ rep:canonical_md     → sha256(content_hash)
       │    └─ upstream: raw   → sha256(content_hash)
       └─ rep:ocr_text         → sha256(content_hash)
            └─ upstream: page_image → sha256(content_hash)
```

**存储**：`{entity_id}/_lineage/ranges.jsonl`（Merkle 树序列化）

**优势**：
- 血缘关系**显式持久化**为内容寻址
- Diff 算法 O(diff_size) 而非 O(total_size)
- 跨 Entity 血缘追踪更高效
- 支持"零拷贝" Entity 快照（复用未修改的 Rep）

**借鉴项目**：
- **lakeFS Graveler**：2 层 Merkle 树（Meta-Range → Ranges），Commit 之间复用未修改的 Ranges
- **Git**：blob 树结构，commit 之间复用未修改的 blob

#### 5.12.11 成熟项目参照：三层元数据架构（v0.2）

> **设计目标**：避免"100K+ Entity 规模下全量扫描 prefix 慢"。参考 **Apache Iceberg** 的 Catalog → metadata.json → Manifest List → Manifest → Data File 三层架构。

```text
L0: Catalog (workspace 级)
    └─ {collection_id}.json → 指向 _current 指针

L1: _current (Entity 级)
    └─ { "log_offset": "...", "manifest_version": 101 }

L2: _log/ (Entity 级，append-only)
    └─ 000000000000.json ... 000000000100.checkpoint.jsonl

L3: _manifest/ (Entity 级，快速索引)
    └─ entity.json + reps.jsonl + indexes.jsonl + edges.jsonl
```

**每层作用**：
- **L0 Catalog**：跨 Entity 索引，workspace 级 metadata
- **L1 _current**：Entity 当前快照指针（原子交换）
- **L2 _log**：变更历史（time travel / 灾难恢复）
- **L3 _manifest**：当前活跃状态快速查询（替代 prefix 扫描）

**与 Iceberg 的对应**：
| Iceberg | Vector-Lake |
|---|---|
| Catalog pointer | L0 `{collection_id}.json` |
| metadata.json | L1 `_current` + L2 `_log` |
| Manifest List | L3 `_manifest/reps.jsonl` |
| Manifest File | L3 `_manifest/reps.jsonl` 单行 |
| Data File | `extract/canonical.md` 等实际数据 |

#### 5.12.12 成熟项目参照：MVCC + 不可变 Manifest（v0.2）

> **设计目标**：让 Entity-level Manifest 显式化，作为 Entity 的"Truth of State"。参考 **Lance Manifest + Delta + Iceberg** 共同模式。

**核心原则**：
- 每次写入产生**新**的 Manifest 项，旧 Manifest 项保留
- 原子协议：先写 Manifest → 再 atomic swap pointer
- 读者看到 consistent snapshot（基于 manifest version）
- Time Travel：通过指定旧 manifest version 读取历史

**与 PRD 现有 §5.10 Index Status 的关系**：
- §5.10 的 `index_status` / `index_built_from_hash` 存在 Lance dataset custom metadata
- v0.2 改进：Entity 级 Manifest（`_manifest/indexes.jsonl`）作为 Truth of State
- Lance dataset custom metadata 仅作为快速缓存
- Manifest 写入协议：先写 Lance → 再写 `_manifest`（如果失败可重建）

#### 5.12.13 成熟项目参照：Schema Evolution 规则（v0.3）

> **设计目标**：明确 Entity/Rep schema 的演进规则。参考 **Delta + Iceberg + Lance** 三家共同设计。

**Entity Schema 演进规则**：

```text
v0.1 初始 Entity Schema
  ├─ entity_type: document | table | image | audio | video
  ├─ name: string
  ├─ content_hash: string
  └─ version: int

v0.2 Schema Evolution（加 entity_type: webpage）
  → 旧 Entity 不受影响（向后兼容）
  → 新 Entity 可用新 entity_type
  → _manifest/entity.json 记录 schema_version
  → 旧读卡器忽略未知 entity_type（视为不可处理）
```

**Rep Schema 演进规则**：

```text
v0.1 Rep Tag: 7 个字段（rep_type, pipeline_id, transform, modality, status, model_version, entity_version）

v0.2 Rep Schema Evolution（加 sync_state 字段）
  → 旧 Rep Tag 自动补全默认 sync_state=ready（Conditional Update）
  → _manifest/reps.jsonl 记录 schema_version
  → 旧读卡器忽略未知字段
```

**Lance Schema 演进规则**（§15 R4 已存在）：
- 所有表带 schema_version
- 变更走 migration
- 兼容性规则：向后兼容（读旧 schema 读新数据）、向前兼容（读新 schema 读旧数据）

**Schema Checkpoint**（参考 Iceberg）：
- 定期冻结 schema snapshot
- 加速查询（不必每次解析 schema）
- 与 Log Checkpoint 一起触发

#### 5.12.14 实施路径与 v0.1/v0.2 边界

| 阶段 | 内容 | v0.1 状态 | v0.2 实施 |
|---|---|---|---|
| `.entity_manifest.json` | 不可推导信息持久化 | ✅ 已实现 | — |
| `.version_log.jsonl` | 版本历史 append-only | ✅ 已实现 | — |
| Phase 0 body_hash 校验 | Tag 可靠性兜底 | ✅ 已实现 | — |
| `_current` 指针 + 原子交换 | 原子性保证 | ❌ 推迟 | v0.2 阶段 1 |
| `_log/` 事务日志 | 变更历史 | ❌ 推迟 | v0.2 阶段 2 |
| `_manifest/` 快速索引 | O(1) 状态查询 | ❌ 推迟 | v0.2 阶段 3 |
| Checkpoint 机制 | 日志压缩 | ❌ 推迟 | v0.2 阶段 4 |
| Merkle 树血缘 | 内容寻址血缘 | ❌ 推迟 | v0.3 |
| Schema Evolution 规则 | Entity/Rep schema 演进 | ❌ 推迟 | v0.3 |
| Time Travel API | 历史快照查询 | ❌ 推迟 | v0.3 |

> **设计哲学**：v0.1 先解决"能跑起来 + 基础可靠性"（sidecar 持久化 + Reconciler 兜底），v0.2 引入"行业标准的 ACID + 大规模能力"（事务日志 + 原子指针 + 快速索引），v0.3 引入"高级能力"（Merkle 血缘 + Schema 演进 + Time Travel）。

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
| 1 | MIME 类型白名单 | .csv / .tsv / .xlsx / .xls / .et / .ett / .parquet / .json (array) / .sql → `table` |
| 2 | 内容探测（magic bytes） | .sqlite / .duckdb → `table` |
| 3 | 文件大小 + 内容采样 | < 1MB + 强结构化 → `table` |
| 4 | 文件大小 + 文本提取 | > 1MB + 多段文本 → `document` |
| 5 | 文件名 + 扩展名 | .pdf / .docx / .doc / .pptx / .ppt / .md / .wps / .dps → `document` |
| 6 | 媒体类型 | .jpg / .png / .mp3 / .wav / .mp4 等 → image/audio/video（完整清单见 §6.5） |

> v0.1 仅实现 1、2、5、6 四类（3、4 类启发式判定留 v0.2）。`entity_type` 写入 OSS Tag `entity_type`，用户可通过 `Entity.update_tags()` 手动修正。完整支持格式清单见 §6.5。

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

### 6.5 支持输入格式清单（Supported Input Formats）

Vector-Lake v0.1 支持以下输入格式，按 `entity_type` 分组。格式选择决定 Entity 的 `entity_type` 判定（§6.4.1）和默认 Pipeline 路由（§6.3）。

#### 6.5.1 文档格式（entity_type=document）

| 格式 | 扩展名 | MIME 类型 | 解析方式 | v0.1 |
| --- | --- | --- | --- | --- |
| **Markdown** | `.md` | `text/markdown` | 原生解析（marko/mistune） | ✅ |
| **PDF** | `.pdf` | `application/pdf` | PyMuPDF / pdfplumber | ✅ |
| **Word** | `.doc` | `application/msword` | python-docx（需先 LibreOffice 转 docx） | ✅ |
| **Word** | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx | ✅ |
| **PowerPoint** | `.ppt` | `application/vnd.ms-powerpoint` | python-pptx（需先 LibreOffice 转 pptx） | ✅ |
| **PowerPoint** | `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | python-pptx | ✅ |
| **WPS 文字** | `.wps` | `application/wps-office.wps` | LibreOffice 转 docx → python-docx | ✅ |
| **WPS 文字模板** | `.wpt` | `application/wps-office.wpt` | LibreOffice 转 docx → python-docx | ✅ |
| **WPS 演示** | `.dps` | `application/wps-office.dps` | LibreOffice 转 pptx → python-pptx | ✅ |
| **WPS 演示模板** | `.dpt` | `application/wps-office.dpt` | LibreOffice 转 pptx → python-pptx | ✅ |
| **RTF** | `.rtf` | `application/rtf` | LibreOffice 转 md | v0.2 |
| **ODT** | `.odt` | `application/vnd.oasis.opendocument.text` | python-docx / LibreOffice | v0.2 |
| **HTML** | `.html`, `.htm` | `text/html` | BeautifulSoup | v0.2 |
| **纯文本** | `.txt` | `text/plain` | 原生读取 | ✅ |

> **WPS 格式说明**：WPS 原生格式（.wps/.wpt/.dps/.dpt/.et/.ett）通过 LibreOffice 转换为对应 Microsoft 格式后解析。v0.1 依赖系统安装 LibreOffice（Docker 镜像内置），v0.2 评估 WPS SDK 直读。

#### 6.5.2 表格格式（entity_type=table）

| 格式 | 扩展名 | MIME 类型 | 解析方式 | v0.1 |
| --- | --- | --- | --- | --- |
| **CSV** | `.csv` | `text/csv` | DuckDB / pandas | ✅ |
| **Excel** | `.xls` | `application/vnd.ms-excel` | openpyxl（需先 LibreOffice 转 xlsx） | ✅ |
| **Excel** | `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | openpyxl | ✅ |
| **WPS 表格** | `.et` | `application/wps-office.et` | LibreOffice 转 xlsx → openpyxl | ✅ |
| **WPS 表格模板** | `.ett` | `application/wps-office.ett` | LibreOffice 转 xlsx → openpyxl | ✅ |
| **TSV** | `.tsv` | `text/tab-separated-values` | DuckDB / pandas | ✅ |
| **Parquet** | `.parquet` | `application/parquet` | DuckDB / PyArrow | ✅ |
| **ODS** | `.ods` | `application/vnd.oasis.opendocument.spreadsheet` | LibreOffice 转 xlsx | v0.2 |
| **JSON** | `.json` (array) | `application/json` | DuckDB JSON 扩展 | ✅ |

> **Excel 多 Sheet**：`.xls/.xlsx/.et/.ett` 多 Sheet 文件，每个 Sheet 生成独立 `table_parquet` Representation，通过 `.meta.json` 记录 Sheet 映射。

#### 6.5.3 图片格式（entity_type=image）

Jina Embedding V5 Omni 原生支持以下图片格式，Vector-Lake 直接对接：

| 格式 | 扩展名 | MIME 类型 | 说明 | v0.1 |
| --- | --- | --- | --- | --- |
| **JPEG** | `.jpg`, `.jpeg` | `image/jpeg` | 最常见图片格式 | ✅ |
| **PNG** | `.png` | `image/png` | 无损压缩 | ✅ |
| **GIF** | `.gif` | `image/gif` | 动图（取首帧） | ✅ |
| **WebP** | `.webp` | `image/webp` | 现代压缩格式 | ✅ |
| **BMP** | `.bmp` | `image/bmp` | 无压缩位图 | ✅ |
| **TIFF** | `.tif`, `.tiff` | `image/tiff` | 扫描文档常见 | ✅ |
| **AVIF** | `.avif` | `image/avif` | 新一代压缩格式 | ✅ |
| **HEIC** | `.heic` | `image/heic` | Apple 设备格式 | ✅ |
| **SVG** | `.svg` | `image/svg+xml` | 矢量图（rasterize 后 embed） | ✅ |

> **SVG 特殊处理**：SVG 是矢量格式，Jina V5 不直接支持。Vector-Lake 先通过 cairosvg 将 SVG rasterize 为 PNG，再送入 Jina V5 编码。

#### 6.5.4 音频格式（entity_type=audio）

Jina Embedding V5 Omni 原生支持以下音频格式：

| 格式 | 扩展名 | MIME 类型 | 说明 | v0.1 |
| --- | --- | --- | --- | --- |
| **WAV** | `.wav` | `audio/wav` | 无损音频 | ✅ |
| **MP3** | `.mp3` | `audio/mpeg` | 最常见音频格式 | ✅ |
| **FLAC** | `.flac` | `audio/flac` | 无损压缩 | ✅ |
| **OGG** | `.ogg` | `audio/ogg` | 开源音频格式 | ✅ |
| **M4A** | `.m4a` | `audio/mp4` | AAC 音频 | ✅ |
| **Opus** | `.opus` | `audio/opus` | 低延迟编码 | ✅ |

> 音频文件走 RepPipeline F（`transcribe`），产出 `transcript` + `audio_segment`，再走 IndexPipeline 语义索引。

#### 6.5.5 视频格式（entity_type=video）

Jina Embedding V5 Omni 原生支持以下视频格式：

| 格式 | 扩展名 | MIME 类型 | 说明 | v0.1 |
| --- | --- | --- | --- | --- |
| **MP4** | `.mp4` | `video/mp4` | 最常见视频格式 | ✅ |
| **AVI** | `.avi` | `video/x-msvideo` | 传统视频格式 | ✅ |
| **MOV** | `.mov` | `video/quicktime` | Apple 视频格式 | ✅ |
| **MKV** | `.mkv` | `video/x-matroska` | 开源容器格式 | ✅ |
| **WebM** | `.webm` | `video/webm` | Web 视频格式 | ✅ |
| **FLV** | `.flv` | `video/x-flv` | Flash 视频 | ✅ |
| **WMV** | `.wmv` | `video/x-ms-wmv` | Windows 视频 | ✅ |

> 视频文件走 RepPipeline F（提取音轨 `transcribe`）+ RepPipeline E（关键帧 `render_page` → `page_image`），双路并行处理。

#### 6.5.6 格式→entity_type→Pipeline 路由总表

```text
输入扩展名                    → entity_type → 默认 Pipeline
─────────────────────────────────────────────────────────────
.md .pdf .doc .docx          → document    → A (parse)
.ppt .pptx                   → document    → A (parse) + E (render_page)
.wps .wpt .dps .dpt          → document    → A (parse) + E (render_page)
.txt .rtf .odt .html         → document    → A (parse)
.csv .tsv .xls .xlsx         → table       → G (table_parse)
.et .ett .parquet .json      → table       → G (table_parse)
.jpg .jpeg .png .gif .webp   → image       → E (render_page)
.bmp .tif .tiff .avif .heic  → image       → E (render_page)
.svg                         → image       → E (rasterize→render_page)
.wav .mp3 .flac .ogg         → audio       → F (transcribe)
.m4a .opus                   → audio       → F (transcribe)
.mp4 .avi .mov .mkv          → video       → F+E (transcribe+render_page)
.webm .flv .wmv              → video       → F+E (transcribe+render_page)
```

#### 6.5.7 格式不支持时的处理

| 场景 | 处理方式 |
| --- | --- |
| 扩展名不在清单中 | 返回 `INVALID_ENTITY_ID` 错误，提示支持的格式列表 |
| 扩展名匹配但内容损坏 | RepStep `parse` 失败 → `PIPELINE_STEP_FAILED`，Worker 日志记录具体错误 |
| WPS 格式但 LibreOffice 不可用 | 降级为 `UNSUPPORTED_FORMAT` 错误，提示安装 LibreOffice |
| 新格式需求 | 注册自定义 RepStep（§6.6.5），在 Plugin 配置中声明 `supported_extensions` |

#### 6.5.8 v0.2 格式扩展计划

| 格式 | 扩展名 | entity_type | 说明 |
| --- | --- | --- | --- |
| **EPUB** | `.epub` | document | 电子书格式 |
| **ODT** | `.odt` | document | OpenDocument 文本 |
| **ODP** | `.odp` | document | OpenDocument 演示 |
| **ODS** | `.ods` | table | OpenDocument 表格 |
| **DOCX with macros** | `.docm` | document | 含宏的 Word 文档 |
| **XLSX with macros** | `.xlsm` | table | 含宏的 Excel |
| **网页快照** | `.mhtml` | document | MIME HTML 归档 |
| **数据库** | `.sqlite`, `.duckdb` | table | 本地数据库文件 |
| **网页** | URL | webpage | v0.2 新增 entity_type |

### 6.6 Pipeline 之间的级联与避免重复

| 场景 | 处理 |
| --- | --- |
| A 产出 canonical_md 后触发 D | D 的 `derived_from=canonical_md`（从目录层级推导：compile/ 的 input 在 extract/） |
| B 与 C 同时产出（基于 page_image） | 两者并存，分别打 Rep OSS Tag；D 可选地基于任一产出 summary |
| 表格中的图片 | G + E 并行：G 产 `table.parquet`，E 产 `page_image/`（图片向量） |
| 公式 / 嵌入对象 | 暂不支持（v0.2+ 引入 Mathpix API / 公式抽取） |

### 6.6 RepStep Plugin 体系（内容变换插件）

> **核心定位**：RepStep 是 RepPipeline 的可插拔步骤。每个 RepStep 做一件事：把上游 Representation 文件变换为下游 Representation 文件。新增 rep_type = 新增 RepStep + 注册，不改已有代码。

#### 6.6.1 RepStep Protocol

```python
from typing import Protocol, Optional
from dataclasses import dataclass

@dataclass
class RepStepContext:
    """RepStep 执行上下文，由 RepPipelineOrchestrator 注入。"""
    entity_id: str
    entity_type: str
    workspace_id: str
    collection_id: str
    content_hash: str
    entity_version: int
    # 可访问上游 step 的产出
    upstream_outputs: dict[str, "RepStepOutput"]

@dataclass
class RepStepOutput:
    """RepStep 产出声明。"""
    rep_type: str
    stage: str                          # source/extract/recognize/compile
    files: dict[str, bytes]             # 文件名 → 内容
    tags: dict[str, str]                # OSS Representation Tag

class RepStep(Protocol):
    """可插拔的内容变换步骤。"""

    # ── 声明（注册时读取，不执行）──
    step_id: str                         # 全局唯一标识，对应 RepStepRegistry key
    name: str                            # 人类可读名称
    required_input_reps: list[str]       # 必须全部存在才能执行（缺失则 step 标 skipped）
    optional_input_reps: list[str]       # 可选存在（有则用，无则跳过该输入分支）
    output_reps: list[str]               # 产出的 rep_type
    output_stage: str                    # 产出到哪个目录层级
    supported_entity_types: list[str]    # 支持的 entity_type
    modality: str                        # text / image / audio / table / graph / wiki

    # ── 执行（运行时调用）──
    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """执行步骤，返回产出列表。必须幂等。"""
        ...

    # ── 能力声明（可选覆盖）──
    def capabilities(self) -> dict[str, bool]:
        return {
            "requires_llm": False,        # 是否需要 LLM 调用
            "requires_gpu": False,        # 是否需要 GPU
            "estimated_duration_ms": 1000, # 预估耗时
        }
```

#### 6.6.2 RepStepRegistry（全局插件注册表）

```python
class RepStepRegistry:
    """全局 RepStep 注册表。支持运行时动态注册（plugin 注入）。"""

    _steps: dict[str, RepStep] = {}

    @classmethod
    def register(cls, step: RepStep):
        """注册一个 RepStep。第三方 plugin 通过此接口注入。"""
        cls._steps[step.step_id] = step

    @classmethod
    def get(cls, step_id: str) -> RepStep:
        return cls._steps[step_id]

    @classmethod
    def steps_for_entity_type(cls, entity_type: str) -> list[RepStep]:
        """返回支持该 entity_type 的所有 step。"""
        return [s for s in cls._steps.values()
                if entity_type in s.supported_entity_types]

    @classmethod
    def steps_producing_rep(cls, rep_type: str) -> list[RepStep]:
        """返回能产出该 rep_type 的所有 step。"""
        return [s for s in cls._steps.values()
                if rep_type in s.output_reps]
```

#### 6.6.3 内置 RepStep 清单（v0.1）

| step_id | name | required_input_reps | optional_input_reps | output_reps | output_stage | entity_types | modality | v0.1 |
|---|---|---|---|---|---|---|---|---|
| `parse` | 文档解析 | `raw` | — | `canonical_md`, `plain_text`, `layout_json` | extract | document | text | ✅ |
| `render_page` | 页面渲染 | `raw` | — | `page_image` | extract | document, image | image | ✅ |
| `ocr` | OCR 识别 | `page_image` | — | `ocr_text` | recognize | document | text | ✅ |
| `vlm` | VLM 视觉 | `page_image` | — | `vlm_md` | recognize | document | text | v0.2 |
| `transcribe` | 音视频转写 | `raw` | — | `transcript`, `audio_segment` | recognize | audio, video | audio | ✅ |
| `table_parse` | 表格解析 | `raw` | — | `table_parquet`, `table_md`, `table_json` | compile | table | table | ✅ |
| `compile_mind_map` | 脑图编译 | `canonical_md` | — | `mind_map` | compile | document | text | v0.2 |
| `compile_graph_json` | 关系图编译 | `canonical_md` | — | `graph_json` | compile | document | text | v0.2 |
| `compile_summary` | 摘要编译 | `canonical_md` | — | `summary` | compile | document | text | v0.2 |
| `compile_wiki_md` | Wiki 编译 | `canonical_md` | — | `wiki_md` | compile | document | wiki | v0.2 |
| `project_wiki` | Wiki 投影 | `canonical_md` | `wiki_md`, `graph_json`, `summary` | — | compile | document | wiki | v0.2 |

> `project_wiki` 是 Projector 作为 RepStep 注册的示例（§11），产出不写回 Lake 内部，而是写外部 vault。`required_input_reps` 表示必须全部存在；`optional_input_reps` 表示有则用、无则跳过该输入分支。

#### 6.6.4 内置 RepPipeline 组装

| pipeline_id | name | steps | v0.1 |
|---|---|---|---|
| `rep_pipeline_a` | 直接提取 | `parse` | ✅ |
| `rep_pipeline_b` | OCR 内容变换 | `render_page` → `ocr` | ✅ |
| `rep_pipeline_c` | VLM 内容变换 | `render_page` → `vlm` | v0.2 |
| `rep_pipeline_d_mind_map` | 脑图编译 | `compile_mind_map` | v0.2 |
| `rep_pipeline_d_graph` | 关系图编译 | `compile_graph_json` | v0.2 |
| `rep_pipeline_d_summary` | 摘要编译 | `compile_summary` | v0.2 |
| `rep_pipeline_d_wiki` | Wiki 编译 | `compile_wiki_md` | v0.2 |
| `rep_pipeline_e` | 图片渲染 | `render_page` | ✅ |
| `rep_pipeline_f` | 音频转写 | `transcribe` | ✅ |
| `rep_pipeline_g` | 表格获取 | `table_parse` | ✅ |

#### 6.6.5 第三方 RepStep 注册示例

```python
# 第三方写的 FAQ 编译 step（不需要改 Lake 代码）
class FaqCompileStep(RepStep):
    step_id = "compile_faq"
    name = "FAQ 编译"
    required_input_reps = ["canonical_md"]
    output_reps = ["faq_md"]
    output_stage = "compile"
    supported_entity_types = ["document"]
    modality = "text"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        canonical = ctx.upstream_outputs["canonical_md"]
        faq = my_faq_compiler(canonical)
        return [RepStepOutput(
            rep_type="faq_md", stage="compile",
            files={"faq.md": faq.encode()},
            tags={"transform": "faq_compiler", "modality": "text"},
        )]

# 注册
RepStepRegistry.register(FaqCompileStep())
```

### 6.7 IndexStep Plugin 体系（索引构建插件）

> **核心定位**：IndexStep 是 IndexPipeline 的可插拔步骤。每个 IndexStep 做一件事：消费 Representation 文件，构建搜索索引。新增 index_type = 新增 IndexStep + 注册，不改已有代码。IndexStep 与 RepStep 完全解耦——IndexStep 不知道 RepStep 的存在，只消费 Representation 文件。

#### 6.7.1 IndexStep Protocol

```python
@dataclass
class IndexStepContext:
    """IndexStep 执行上下文，由 IndexPipelineOrchestrator 注入。"""
    entity_id: str
    entity_type: str
    workspace_id: str
    collection_id: str
    lance_table: LanceTable              # 目标 Lance 表
    available_reps: dict[str, str]       # rep_type → OSS URI（只读访问）

class IndexStep(Protocol):
    """可插拔的索引构建步骤。"""

    # ── 声明 ──
    step_id: str                         # 全局唯一标识，对应 IndexStepRegistry key
    name: str                            # 人类可读名称
    index_type: str                      # semantic / lexical / visual / graph / table / audio
    required_reps: list[str]             # 必须全部存在才能执行（缺失则 step 标 skipped）
    optional_reps: list[str]             # 可选存在（有则合并处理，无则跳过）
    supported_modalities: list[str]      # 支持的模态

    # ── 执行 ──
    def execute(self, ctx: IndexStepContext) -> None:
        """构建索引。必须幂等。"""
        ...

    def is_built(self, ctx: IndexStepContext) -> bool:
        """检查索引是否已存在。"""
        ...

    def rebuild(self, ctx: IndexStepContext) -> None:
        """删除旧索引并重建。"""
        ...

    # ── 能力声明 ──
    def capabilities(self) -> dict[str, bool]:
        return {
            "supports_hybrid": False,     # 是否支持 hybrid search
            "requires_training": False,   # 是否需要训练（如 IVF）
        }
```

#### 6.7.2 IndexStepRegistry（全局插件注册表）

```python
class IndexStepRegistry:
    """全局 IndexStep 注册表。支持运行时动态注册。"""

    _steps: dict[str, IndexStep] = {}

    @classmethod
    def register(cls, step: IndexStep):
        cls._steps[step.step_id] = step

    @classmethod
    def steps_for_reps(cls, available_reps: list[str]) -> list[IndexStep]:
        """返回所有 required_reps 已满足的 step。"""
        return [s for s in cls._steps.values()
                if all(r in available_reps for r in s.required_reps)]
```

#### 6.7.3 内置 IndexStep 清单（v0.1）

| step_id | name | index_type | required_reps | optional_reps | supported_modalities | v0.1 |
|---|---|---|---|---|---|
| `chunk_and_embed_text` | 文本切片+嵌入 | semantic | `canonical_md`, `ocr_text`, `vlm_md`（任一） | `layout_json` | text | ✅ |
| `build_vector_index` | 向量索引 | semantic | — | — | text, image, audio | ✅ |
| `build_fts_index` | 全文索引 | lexical | — | — | text | ✅ |
| `chunk_and_embed_image` | 图片切片+嵌入 | visual | `page_image` | `layout_json` | image | ✅ |
| `chunk_and_embed_audio` | 音频切片+嵌入 | audio | `transcript`, `audio_segment` | — | audio | v0.2 |
| `build_graph_index` | 图索引 | graph | `graph_json` | — | graph | v0.2 |
| `chunk_and_embed_table` | 表格切片+嵌入 | table | `table_md`, `table_json` | `layout_json` | table | v0.2 |

#### 6.7.4 内置 IndexPipeline 组装（v0.1）

| pipeline_id | name | steps |
|---|---|---|
| `index_pipeline_text` | 文本索引 | `chunk_and_embed_text` → `build_vector_index` → `build_fts_index` |
| `index_pipeline_image` | 图片索引 | `chunk_and_embed_image` → `build_vector_index` |
| `index_pipeline_audio` | 音频索引 | `chunk_and_embed_audio` → `build_vector_index` |
| `index_pipeline_graph` | 图索引 | `build_graph_index` |
| `index_pipeline_table` | 表格索引 | `chunk_and_embed_table` → `build_vector_index` |

#### 6.7.5 IndexPipeline 触发时机

```text
RepPipeline 全部完成
        ↓
RepPipelineOrchestrator 发出 "rep_all_ready" 事件
        ↓
IndexPipelineOrchestrator 收到事件
        ↓
扫描 available_reps（从 OSS Tag 实时获取）
        ↓
IndexStepRegistry.steps_for_reps(available_reps)
        ↓
按 IndexPipeline 定义组装并执行
        ↓
索引构建完成 → Entity 可被检索
```

**关键不变量**：IndexPipeline **不触发** RepPipeline。索引构建失败不影响 Representation 文件的存在。

### 6.8 RepStep / IndexStep 并发模型

> **核心规则**：**Entity 内 RepPipeline 间并行、RepPipeline 内 step 串行、IndexPipeline 串行，Entity 间完全并行**。

#### 6.8.1 并发粒度

| 层级 | 并发策略 | 原因 | 锁粒度 |
|---|---|---|---|
| **同一 RepPipeline 内 step** | 串行（按拓扑序） | step 之间有数据依赖（如 ocr 需要 page_image） | 无锁（单 Worker 执行） |
| **同一 Entity 内 RepPipeline** | 并行 | 不同 RepPipeline 写入不同 OSS 路径，无冲突 | `rep_pipeline:{entity_id}:{pipeline_id}` |
| **同一 Entity 内 IndexPipeline** | 串行（每个 IndexPipeline 独占 Lance 写锁） | Lance 同一 dataset 写入需排他 | `index:{entity_id}` |
| **不同 Entity 的 RepPipeline** | 完全并行 | OSS 路径天然隔离 | 无锁 |
| **不同 Entity 的 IndexPipeline** | 完全并行 | Lance 数据集在不同 Entity 目录下，无冲突 | 无锁 |
| **同一 RepStep 的多实例** | 串行（per entity per pipeline） | 避免同一 Entity 同一 Pipeline 的 Rep 写入冲突 | `rep_step:{entity_id}:{pipeline_id}:{step_id}` |

> **锁粒度优化**（E2 修复）：从"Entity 级锁"改为"RepPipeline 级锁"。同一 Entity 的 `parse` 和 `render_page` 可以并行执行（写不同 OSS 路径），只有同一 RepPipeline 内的 step 才需要串行。
| **RepPipeline 与 IndexPipeline** | 不能并行 | IndexPipeline 必须等 RepPipeline 完成后（`rep_all_ready` 事件） |

#### 6.8.2 锁模型

```text
Entity 维度的锁：
  EntityLock(entity_id):
    ├─ RepLock: 同一 Entity 的 RepPipeline 互斥
    ├─ IndexLock: 同一 Entity 的 IndexPipeline 互斥
    └─ 但 RepLock 和 IndexLock 不互斥（不同阶段可并行）
    
全局维度：
  RegistryLock(RepStepRegistry | IndexStepRegistry | ProjectorStepRegistry):
    └─ 注册/注销时短时持有；查询无锁（读时复制）
```

#### 6.8.3 失败处理

| 场景 | 处理 |
|---|---|
| RepPipeline 内 step 失败 | 标 `partial_success`；继续执行后续 RepPipeline；下发 `rep_all_ready` 时附带 `failed_steps` |
| RepPipeline 整体失败（所有 step 失败） | 标 `failed`；不发 `rep_all_ready`；告警；3 次重试后入 DLQ |
| IndexPipeline 失败 | 标 `index_status=failed`；不影响 Rep；下次 Reconciler 重试 |
| ProjectorStep 失败 | 标 Projector 失败；不影响 Rep 和 Index；告警 |
| RepPipeline 死锁 / 超时 | Orchestrator 设全局超时（默认 10 min/step）；超时标 failed |

#### 6.8.4 配额

| 资源 | 默认配额 | 触发降级 |
|---|---|---|
| 同 Entity 并行 RepPipeline | 3 | 队列等待 |
| 全局并发 RepStep | 50 | 队列等待 |
| 全局并发 IndexStep | 20 | 队列等待 |
| 单 RepStep LLM 调用并发 | 5（per worker） | 队列等待 |
| 单 RepStep 显存占用 | 8 GB | 失败 + 降级到 CPU |

### 6.9 任务队列：Redis Streams（v0.1 选定）

> **设计决策**：v0.1 使用 **Redis Streams** 作为任务队列，**不使用 Celery / Kafka**。
>
> **理由**：
> - Celery 不可靠的根因是抽象层太多（broker → worker → result backend → serialization），不是 Redis 的问题
> - 直接用 Redis Streams 原语 = 去掉 Celery 这层抽象 = 更可靠
> - Kafka 对 v0.1 规模过重（Entity 级消息量低，不需要分区 / 副本 / 持久化）
> - Redis 已是 Vector-Lake 的依赖（VFS 缓存 + 锁），不引入新组件

#### 6.9.1 Stream 拓扑

```text
┌─────────────┐     XADD          ┌──────────────────────┐
│ OSS Event   │ ──────────────►   │ stream:rep_pipeline  │
│ Webhook     │                   │ (Consumer Group:      │
│ Reconciler  │                   │  rep_workers)         │
└─────────────┘                   └──────────┬───────────┘
                                             │ XREADGROUP
                                             ▼
                                  ┌──────────────────────┐
                                  │ RepStep Worker ×N     │
                                  │ (Entity 内串行)        │
                                  └──────────┬───────────┘
                                             │ XADD (rep_all_ready)
                                             ▼
                                  ┌──────────────────────┐
                                  │ stream:index_pipeline │
                                  │ (Consumer Group:      │
                                  │  index_workers)       │
                                  └──────────┬───────────┘
                                             │ XREADGROUP
                                             ▼
                                  ┌──────────────────────┐
                                  │ IndexStep Worker ×M   │
                                  │ (Entity 内串行)        │
                                  └──────────────────────┘
```

#### 6.9.2 消息格式

```json
// XADD rep_pipeline * entity_id e-123 step_id render_page workspace ws1 ...
{
  "entity_id": "e-123",
  "step_id": "render_page",
  "workspace_id": "ws1",
  "collection_id": "col1",
  "trigger": "oss_event",          // oss_event | reconciler | manual
  "input_reps": {                   // 运行时由 Orchestrator 填充（从 RepStepRegistry 解析）
    "required": ["source/original"],  // step.required_input_reps → 具体路径
    "optional": ["extract/page_image"] // step.optional_input_reps → 具体路径（可能不存在）
  },
  "trace_id": "abc-def-123",       // OpenTelemetry trace ID
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2026-06-06T10:00:00Z"
}
```

#### 6.9.3 消费协议

```python
# Worker 伪代码
async def rep_worker():
    while True:
        # 1. 读取消息（阻塞等待，超时 5s）
        entries = redis.xreadgroup(
            "rep_workers", f"worker-{WORKER_ID}",
            {"rep_pipeline": ">"},  # ">" = 只读未消费的
            count=10, block=5000
        )
        for stream, messages in entries:
            for msg_id, fields in messages:
                entity_id = fields["entity_id"]
                step_id = fields["step_id"]

                # 2. RepPipeline 级锁（而非 Entity 级锁）
                pipeline_id = fields.get("pipeline_id", "default")
                async with redis_lock(f"rep_pipeline:{entity_id}:{pipeline_id}", timeout=300):
                    try:
                        # 3. 执行 RepStep
                        step = RepStepRegistry.get(step_id)
                        result = await step.execute(ctx)
                        # 4. 成功 → XACK
                        redis.xack("rep_pipeline", "rep_workers", msg_id)
                        # 5. 如果是最后一个 RepStep → 投递到 index_pipeline
                        if all_reps_ready(entity_id):
                            redis.xadd("index_pipeline", {
                                "entity_id": entity_id, ...
                            })
                    except Exception as e:
                        # 6. 失败 → 不 ACK，等 XAUTOCLAIM 自动重试
                        logger.error(f"RepStep failed: {e}")
                        # 可选：立即 XACK + 投递到 dead_letter stream
                        if fields["retry_count"] >= fields["max_retries"]:
                            redis.xadd("stream:dead_letter", {**fields, "error": str(e)})
                            redis.xack("rep_pipeline", "rep_workers", msg_id)
```

#### 6.9.4 可靠性保证

| 场景 | Redis Streams 机制 | 效果 |
|---|---|---|
| Worker 正常处理 | `XACK` 确认 | 消息不再投递 |
| Worker OOM / 被杀 | 未 ACK 的消息 | `XAUTOCLAIM` 自动 reclaim（超时 5 min） |
| 消息积压 | `XINFO STREAM` + `XPENDING` | 监控 + 告警 |
| 重复消费 | `XACK` 幂等 + RepStep 幂等（基于 content_hash） | 安全 |
| 消息丢失 | Redis AOF / RDB 持久化 | 重启后恢复 |
| 死信 | 超过 max_retries → `stream:dead_letter` | 人工处理 |

#### 6.9.5 与 Celery 的对比

| 维度 | Celery + Redis | Redis Streams 直连 |
|---|---|---|
| **可靠性** | 低（worker OOM 丢任务、chord 不可靠） | 高（XAUTOCLAIM 自动重试） |
| **抽象层** | broker + worker + result backend + serialization | XADD / XREADGROUP / XACK |
| **可观测** | 需 Flower / Celery events | `XINFO` / `XPENDING` 原生 |
| **依赖** | Celery + Redis + (result backend) | Redis only |
| **序列化** | pickle / json / msgpack（兼容性问题） | 纯 dict（无序列化层） |
| **延迟** | 高（broker → worker → result） | 低（直连 Redis） |
| **运维** | 复杂（worker 进程管理 + concurrency pool） | 简单（asyncio + Consumer Group） |

#### 6.9.6 背压策略

```text
Redis Streams 背压机制：
  1. XADD 时设置 MAXLEN ~ 100000（近似裁剪，保留最近 10 万条）
  2. Worker 消费延迟 > 5 min → 告警（XPENDING 检测）
  3. 积压 > 50K → 触发背压：
     ├─ OSS Event Webhook 返回 429（拒绝新事件）
     ├─ Reconciler 暂停投递新任务
     └─ 管理员 API: POST /v1/admin/backpressure?mode=drain（排空模式）
  4. 锁超时策略：
     ├─ 锁超时 = step 预估耗时 × 3（如 render_page 30s → 锁超时 90s）
     ├─ 加锁时写入 worker_id + timestamp
     └─ 超时后其他 worker 可安全抢占（检查 worker_id 是否存活）
```

#### 6.9.7 v0.2 演进路径

```text
v0.1: Redis Streams（单 Redis 实例 / Sentinel）
  ├─ 2 个 Stream: rep_pipeline + index_pipeline
  ├─ 1 个 Dead Letter: stream:dead_letter
  └─ Consumer Group: rep_workers + index_workers
       ↓
v0.2: Redis Streams → Kafka（仅在以下条件满足时迁移）
  ├─ 消息量 > 10K/s
  ├─ 需要跨服务事件广播
  └─ 需要更长的消息保留（Redis 内存有限）
```

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

### 9.5 VFS MCP Server（向 LLM 暴露 Lake）

> **设计目标**：让 LLM（Claude / GPT / 开源模型）通过 **MCP (Model Context Protocol)** 直接浏览和查询 Vector-Lake，无需人工写 API 调用。
>
> **为什么选 MCP**：
> - MCP 是 LLM 工具调用的事实标准（Claude Desktop / Cursor / VS Code / 开源 Agent 框架都支持）
> - MCP 自带 schema 描述（LLM 自动知道怎么调用，不需要手写 function calling schema）
> - MCP 支持 stdio（本地）和 SSE（远程）两种传输
> - 比 REST API + OpenAPI spec 更轻量（一个 Python 文件即可启动）

#### 9.5.1 MCP Tools 定义

```python
# vector_lake_vfs_mcp/server.py
from mcp.server import Server

server = Server("vector-lake-vfs")

@server.tool()
async def vfs_list_collections(workspace_id: str) -> list[dict]:
    """列出 workspace 下所有 collection（名称 + Entity 数量 + 存储用量）"""
    ...

@server.tool()
async def vfs_list_entities(
    workspace_id: str,
    collection_id: str,
    entity_type: str | None = None,
    rag_status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """列出 collection 下所有 Entity（含元数据摘要：name / type / version / rag_status）"""
    ...

@server.tool()
async def vfs_get_entity(workspace_id: str, entity_id: str) -> dict:
    """获取 Entity 完整元数据（所有 Rep 状态 + Index 状态 + Edge + 血缘）"""
    ...

@server.tool()
async def vfs_list_reps(workspace_id: str, entity_id: str) -> list[dict]:
    """列出 Entity 的所有 Representation（rep_type / status / content_hash / pipeline_id / size）"""
    ...

@server.tool()
async def vfs_get_rep_content(
    workspace_id: str,
    entity_id: str,
    rep_type: str,
    max_length: int = 5000,
) -> str:
    """读取 Rep 文件内容（仅文本类 Rep：canonical_md / ocr_text / summary / table_schema）"""
    ...

@server.tool()
async def vfs_get_lineage(
    workspace_id: str,
    entity_id: str,
    direction: str = "both",  # upstream | downstream | both
) -> dict:
    """获取 Entity 的血缘图谱（上游 raw → 下游 Rep → Index → Projector）"""
    ...

@server.tool()
async def vfs_search(
    workspace_id: str,
    query: str,
    mode: str = "semantic",  # semantic | structural | textual
    limit: int = 10,
) -> list[dict]:
    """在 Lake 中检索（语义 / 结构 / 全文），返回命中的 Entity + Chunk + 证据"""
    ...

@server.tool()
async def vfs_get_status(workspace_id: str) -> dict:
    """获取 Lake 运行状态（Entity 数 / Rep 数 / Index 数 / Reconciler 状态 / 漂移数 / 队列积压）"""
    ...
```

#### 9.5.2 部署模式

```text
模式 A：本地 stdio（开发 / 单用户）
  Claude Desktop / Cursor → stdio → vector-lake-vfs-mcp
  配置：claude_desktop_config.json
  {
    "mcpServers": {
      "vector-lake-vfs": {
        "command": "python",
        "args": ["-m", "vector_lake_vfs_mcp"],
        "env": {"LAKE_OSS_ENDPOINT": "...", "LAKE_REDIS_URL": "..."}
      }
    }
  }

模式 B：远程 SSE（生产 / 多用户）
  LLM Agent → HTTP SSE → vector-lake-vfs-mcp-server:8000
  鉴权：Bearer Token / mTLS
  限流：Redis 令牌桶（per user）
```

#### 9.5.3 MCP Tools 与 §9 智能引擎的映射

| MCP Tool | 智能引擎能力 | 底层调用 |
|---|---|---|
| `vfs_list_collections` | — | VFS prefix scan |
| `vfs_list_entities` | — | VFS prefix scan + Tag 读取 |
| `vfs_get_entity` | — | VFS + `.entity_manifest.json` + Lance metadata |
| `vfs_list_reps` | — | VFS prefix scan + Tag 读取 |
| `vfs_get_rep_content` | — | OSS GetObject |
| `vfs_get_lineage` | `capability_lineage` | 目录层级 + Pipeline Registry 推导 |
| `vfs_search` | `capability_semantic` / `structural` / `textual` | §9.2 智能引擎路由 |
| `vfs_get_status` | — | Redis XINFO + Reconciler 状态 |

> **架构原则**：MCP Tools 与 REST API（§14）共享同一套 **Service 层**（Python 函数），不是两套独立实现。MCP Server 和 REST API 是同一套业务逻辑的两种暴露方式：
> - REST API = HTTP + JSON（面向前端 / 第三方集成）
> - MCP Tools = stdio / SSE（面向 LLM Agent）
> - 两者共享 `VectorLakeService` 类，不重复实现

#### 9.5.4 v0.1 范围

| Tool | v0.1 | required_role | 说明 |
|---|---|---|---|
| `vfs_list_collections` | ✅ | `user` | 必须 |
| `vfs_list_entities` | ✅ | `user` | 必须 |
| `vfs_get_entity` | ✅ | `user` | 必须 |
| `vfs_list_reps` | ✅ | `user` | 必须 |
| `vfs_get_rep_content` | ✅ | `user` | 必须（LLM 需要读内容做推理） |
| `vfs_get_lineage` | ✅ | `user` | 必须（LLM 需要理解数据来源） |
| `vfs_search` | ✅ | `user` | 必须（核心检索能力） |
| `vfs_get_status` | ✅ | `admin` | 运维 + LLM 自诊断（仅管理员） |

> **权限模型**：MCP Tools 按 `required_role` 分级（`admin` / `user` / `readonly`）。
> - stdio 模式：继承本地用户权限（默认 admin）
> - SSE 模式：按 Bearer Token 中的 role 字段过滤。`vfs_get_status` 仅 `admin` 可用。
> - `vfs_search` 自动过滤 `rag_status=hidden` 的 Entity（对 `user` 角色不可见）

> **实现**：v0.1 用 `mcp` Python SDK（`pip install mcp`），单文件 `server.py`，约 300 行代码。

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

> **核心定位**：Vector-Lake 是**主体**，Projector 层是它面向不同外部消费者（RAG API / Wiki / Dashboard / Web 前端）暴露数据形态的**适配器集合**。
>
> **与 RepStep 的关系**：Projector 是 **RepStep 的一种特殊形态**——它消费 Lake 内部的 Representation 文件，但产出**不写回 Lake 内部**，而是写到外部目标（vault / HTTP / TSDB）。Projector 注册到 `RepStepRegistry`，由 `RepPipelineOrchestrator` 统一编排，复用拓扑排序、幂等、partial success 等能力。
>
> **与检索层的关系**：§8 检索能力 / §9 智能引擎 是 Lake **被问** 时主动提供答案的 HTTP API；Projector 是 Lake **主动告知** 第三方的出站通道。两者正交。

### 11.1 设计目标

1. **Lake 内聚**：所有领域概念（Entity / Representation / Chunk / Edge / Event）只活在自己的边界内，不为外部消费者变形。
2. **消费解耦**：新增消费者 = 新增一个 Projector RepStep + 注册，不改 Lake 核心代码。
3. **复用 RepPipeline 编排**：Projector 不自建事件系统，复用 RepPipeline 的拓扑排序、幂等、partial success。
4. **可回放**：每个 Projector 的输出是 RepStep 产出的纯函数，支持全量重建（rebuild）。
5. **不破坏消费者独立性**：消费者（如 Wiki）即使脱离 Lake 也能继续运行——因为拿到的是落地的 `.md` 文件，不是绑定到 Lake 的句柄。
6. **幂等**：同一事件重复投影不产生副作用；artifact 命名带 idempotency key。

### 11.2 Projector 作为 RepStep

```python
class ProjectorStep(RepStep):
    """Projector 的基类。继承 RepStep，但产出不写回 Lake 内部。"""

    # RepStep 标准声明
    output_reps: list[str] = []           # Projector 不产出 Lake 内部 rep
    output_stage: str = "compile"         # 逻辑上属于 compile 层

    # Projector 特有声明
    consumer_type: str                    # 'wiki' | 'rag_api' | 'dashboard' | 'web'
    target: str                           # 投影目标描述（如 '~/wiki/' 或 '/tools/*'）

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """执行投影。返回空列表（产出不写回 Lake）。"""
        self._project(ctx)
        return []

    def _project(self, ctx: RepStepContext) -> None:
        """子类实现：把 ctx 中的 upstream_outputs 投影到外部目标。"""
        ...

    def rebuild(self, since: Optional[datetime] = None) -> int:
        """全量重建投影。"""
        ...
```

### 11.3 内置 Projector 清单

| Projector | consumer_type | 输出形态 | 落地方式 | 注册为 RepStep | 状态 |
|---|---|---|---|---|---|
| `WikiProjectorStep` | wiki | `.md` 文件 + wikilink + log.md | OSS / 本地 vault | `project_wiki` | v0.2（依赖 `compile_wiki_md`；详设见 §12） |
| `RagApiProjectorStep` | rag_api | JSON Evidence | HTTP `/tools/*` 路由（§8） | `project_rag_api` | v0.1 |
| `DashboardProjectorStep` | dashboard | 指标 / 状态卡片 | TSDB / WebSocket | `project_dashboard` | v0.2 |
| `WebProjectorStep` | web | 视图模型 | HTTP `/v1/views/*` | `project_web` | v0.2 |

> WikiProjectorStep 是本次设计重点，详设见 §12。

### 11.4 投影生命周期（复用 RepPipeline 编排）

```text
RepPipeline 执行链
─────────────────
RepStep: parse ──→ RepStep: ocr ──→ RepStep: compile_wiki_md ──→ ProjectorStep: project_wiki
                                                                    │
                                                                    ├─→ 1. 从 ctx.upstream_outputs 获取 rep
                                                                    ├─→ 2. 渲染为 .md
                                                                    ├─→ 3. 写入 ~/wiki/（带 idempotency）
                                                                    └─→ 4. 失败 → RepPipeline 的 partial success 机制
```

**与独立事件驱动方案的对比**：

| 维度 | 独立事件驱动（旧方案） | RepStep 编排（新方案） |
|---|---|---|
| 触发 | Event Bus 订阅 | RepPipelineOrchestrator 调度 |
| 依赖管理 | 手工 | 自动（拓扑排序） |
| 幂等 | 自建 | 继承 RepStep |
| 失败处理 | 自建 DLQ | 复用 RepPipeline partial success |
| 新增 Projector | 新增事件处理逻辑 | 注册一个 RepStep |

### 11.5 投影一致性等级

| 等级 | 适用 | 实现 |
|---|---|---|
| **最终一致**（默认） | 绝大多数 Projector | RepPipeline 异步执行，秒级延迟 |
| **强一致** | RAG API 的"写后即查" | 不走 Projector，直接调 Lake 内部 API（§8） |
| **离线全量重建** | 投影损坏 / schema 演进 / 新接 Projector | `rebuild()` 接口，基于 `content_hash` 重放所有事件 |

### 11.6 投影失败的恢复

| 失败类型 | 检测 | 恢复 |
|---|---|---|
| 单次投影失败 | RepPipeline step 失败标记 | 自动重试 3 次 → 标 failed → 告警 |
| 投影器进程崩溃 | 健康检查 | 启动时从 last_committed_offset 续接 |
| 目标存储不可用 | 网络/权限错误 | 指数退避重试；最终标 failed |
| 数据漂移（artifact 与 Lake 不一致） | 周期性 hash 比对 | 触发 `rebuild()` |

---

## 12. Wiki Projector 详设

> **v0.1 状态**：本章为 Wiki Projector 的**完整设计预览**（v0.2 实现），目的是锁定接口、字段映射、v0.2 落地路径。v0.1 不实现 `WikiProjectorStep`、不消费 `wiki_md` / `graph_json` / `compile_wiki_md`（均为 v0.2，§13）。
>
> v0.1 的 Projector 仅 `project_rag_api`（§11.3 / §13.4）。Wiki Projector 的 Protocol 已在 §6.6（`ProjectorStep(RepStep)`）和 §11.2 中定义，可直接实现。

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
[RepPipeline: parse → ocr → compile_wiki_md]
   │  产出 Entity + Representations
   │  写入 OSS + Lance + Parquet 镜像
   ↓
[RepPipelineOrchestrator: 调度 project_wiki RepStep]
   ↓
┌──┴──────────────────────────────────────────┐
│  ProjectorStep: project_wiki                 │
│  - 从 ctx.upstream_outputs 获取 rep          │
│  - 渲染为 .md + wikilinks                    │
│  - 写入 ~/wiki/（带 idempotency）             │
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

> **v0.1 范围声明**：聚焦"两阶段流水线 + Plugin 体系"的核心可用形态，Wiki Projector 与知识编译均为 v0.2。v0.1 不包含 Projector（§11/§12 整体推迟到 v0.2），但 Projector 作为 RepStep Plugin 注册的设计本身在 v0.1 落地（即 ProjectorStep 基类与 ProjectorStepRegistry 在 v0.1 已存在，但只有 `project_rag_api` 实例化）。

### 13.1 文件类型

```text
pdf · docx · pptx · image · audio · table
```

### 13.2 RepPipeline（v0.1 内置）

| pipeline_id | name | steps | entity_types | v0.1 |
|---|---|---|---|---|
| `rep_pipeline_a` | 直接提取 | `parse` | document | ✅ |
| `rep_pipeline_b` | OCR 内容变换 | `render_page` → `ocr` | document | ✅ |
| `rep_pipeline_e` | 图片渲染 | `render_page` | document, image | ✅ |
| `rep_pipeline_f` | 音频转写 | `transcribe` | audio | ✅ |
| `rep_pipeline_g` | 表格获取 | `table_parse` | table | ✅ |
| `rep_pipeline_c` | VLM 内容变换 | `render_page` → `vlm` | document | v0.2 |
| `rep_pipeline_d_mind_map` | 脑图编译 | `compile_mind_map` | document | v0.2 |
| `rep_pipeline_d_graph` | 关系图编译 | `compile_graph_json` | document | v0.2 |
| `rep_pipeline_d_summary` | 摘要编译 | `compile_summary` | document | v0.2 |
| `rep_pipeline_d_wiki` | Wiki 编译 | `compile_wiki_md` | document | v0.2 |

> RepPipeline 编号约定：`rep_pipeline_<family>[_<variant>]`，family = a/b/c/d/e/f/g（与 PRD v0.1 旧编号保留对应关系）。

### 13.3 IndexPipeline（v0.1 内置）

| pipeline_id | name | steps | required_reps | v0.1 |
|---|---|---|---|---|
| `index_pipeline_text` | 文本索引 | `chunk_and_embed_text` → `build_vector_index` → `build_fts_index` | `canonical_md` / `ocr_text`（任一） | ✅ |
| `index_pipeline_image` | 图片索引 | `chunk_and_embed_image` → `build_vector_index` | `page_image` | ✅ |
| `index_pipeline_audio` | 音频索引 | `chunk_and_embed_audio` → `build_vector_index` | `transcript` | v0.2 |
| `index_pipeline_graph` | 图索引 | `build_graph_index` | `graph_json` | v0.2 |
| `index_pipeline_table` | 表格索引 | `chunk_and_embed_table` → `build_vector_index` | `table_md` / `table_json` | v0.2 |

### 13.4 ProjectorStep（v0.1 内置）

| projector | registered_as | 目标消费者 | 状态 |
|---|---|---|---|
| `RagApiProjectorStep` | `project_rag_api` | 上层 RAG / Agent（§8 检索 API 路由） | ✅ v0.1 |
| `WikiProjectorStep` | `project_wiki` | Karpathy LLM Wiki / Obsidian（§12） | v0.2（依赖 `compile_wiki_md`） |
| `DashboardProjectorStep` | `project_dashboard` | 运维面板 | v0.2 |
| `WebProjectorStep` | `project_web` | 前端 SPA | v0.2 |

### 13.5 Rep

```text
raw · canonical_md · plain_text · page_image · ocr_text
transcript · transcript_segment · caption
table_parquet · table_md · table_json
```

> `vlm_md · mind_map · graph_json · wiki_md · summary` 为 v0.2，但 schema 预留。

### 13.6 Index

```text
semantic · lexical · hybrid · grep · visual
```

> `audio · table · graph` 为 v0.2，但 schema 预留。

### 13.7 状态

**Rep Status**：

```text
ready · skipped · failed · stale · deleted
```

**Index Status**（§5.10 新增）：

```text
built · stale · failed · deleted
```

### 13.8 能力

```text
ls · read · stat · grep · glob
semantic · lexical · hybrid · visual
```

> `audio · table · graph` 为 v0.2。

### 13.9 明确不在 v0.1 范围

- VLM 视觉流水线（v0.2）
- 知识编译流水线 / mind_map / graph_json / wiki_md / summary（v0.2）
- Wiki Projector 完整实现（v0.2；v0.1 仅 ProjectorStep 基类与 Registry）
- Dashboard / Web Projector（v0.2）
- 视频 keyframe / 场景切分（v0.2）
- 表格列式检索（v0.2）
- 学习型 router（v0.2）
- 多租户 / 计费（后续）
- 端到端 RAG 答案生成（上层）
- 第三方 Plugin 沙箱执行（v0.1 仅内置 RepStep/IndexStep；第三方注册限制为受信插件）
- RepStep/IndexStep 运行时动态注册（v0.1 代码内注册；HTTP 注册 API 为 v0.2）

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

### 14.5 Plugin 注册 API（v0.2）

> **v0.1 状态**：v0.1 仅支持**代码内注册**（`RepStepRegistry.register()` / `IndexStepRegistry.register()`），无 HTTP API。第三方 Plugin 需发版 Lake 时一起部署。
>
> **v0.2 状态**：新增 HTTP 动态注册 API，支持受信第三方 Plugin 热加载。

| API | 说明 | v0.1 | v0.2 |
| --- | --- | --- | --- |
| `POST /v1/rep_steps` | 动态注册 RepStep（需要 mTLS + 授权） | ❌ | ✅ |
| `POST /v1/index_steps` | 动态注册 IndexStep | ❌ | ✅ |
| `GET /v1/rep_steps` | 列出已注册 RepStep | ✅ | ✅ |
| `GET /v1/index_steps` | 列出已注册 IndexStep | ✅ | ✅ |
| `DELETE /v1/rep_steps/{step_id}` | 注销 RepStep | ❌ | ✅ |
| `DELETE /v1/index_steps/{step_id}` | 注销 IndexStep | ❌ | ✅ |
| `POST /v1/edges` | 创建 Edge | ✅ | ✅ |
| `GET /v1/edges?entity_id=...` | 查询 Edge | ✅ | ✅ |
| `DELETE /v1/edges/{edge_id}` | 删除 Edge | ✅ | ✅ |

### 14.6 Edge 操作 API（v0.1）

```json
// POST /v1/edges
{
  "src_entity_id": "...",
  "src_entity_version": 2,
  "dst_entity_id": "...",
  "dst_entity_version": 1,
  "relation": "mentions|cites|contradicts|supports|synthesizes|supersedes|derived_from",
  "weight": 0.8,
  "evidence_chunk_id": "ch_007",
  "idempotency_key": "..."
}
```

### 14.7 管理员 API（元数据可靠性，v0.1）

| API | 说明 | v0.1 |
| --- | --- | --- |
| `POST /v1/admin/rebuild_tags?scope=entity&entity_id=...` | 重建单个 Entity 的所有 OSS Tag（从 Ground Truth） | ✅ |
| `POST /v1/admin/rebuild_tags?scope=workspace&workspace_id=...` | 重建整个 workspace 的 OSS Tag（灾难恢复） | ✅ |
| `POST /v1/admin/verify?entity_id=...&mode=sampling` | 采样校验 body_hash vs Tag content_hash（1% 采样） | ✅ |
| `POST /v1/admin/verify?entity_id=...&mode=full` | 全量校验 body_hash（代价高，灾难恢复专用） | ✅ |
| `POST /v1/entities/{entity_id}/rebuild_lance` | 全量重建 Lance 数据集 | ✅ |
| `GET /v1/admin/reconcile/status` | 查看 Reconciler 状态（上次扫描时间、漂移数量） | ✅ |

> 所有 admin API 需要 mTLS + 管理员角色授权。

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
| **RepPipeline 执行延迟** | 100 页 PDF → `canonical_md` P95 | ≤ 30 s |
| | 100 页 PDF → `ocr_text`（Pipeline B）P95 | ≤ 90 s |
| | 1 小时 audio → `transcript` P95 | ≤ 5 min |
| **IndexPipeline 执行延迟** | 10K chunks → vector + FTS P95 | ≤ 60 s |
| | 1K images → visual index P95 | ≤ 30 s |
| **Projector 投影延迟** | 单页 .md 写入 ~/wiki/（v0.2）P95 | ≤ 1 s |
| **Registry 查询延迟** | RepStepRegistry.get P95 | ≤ 10 ms（内存查找） |
| **并发 Entity** | 同时 ingest 数 | ≥ 10 Entity 无冲突 |
| **可恢复** | raw → searchable 时间 | ≤ 5 min（PDF 100 页级别） |
| **一致性** | reconcile 周期 | ≤ 15 min |
| | Phase 0 延迟 | ≤ 30 min 全量采样校验（每天一次） |
| | Phase 1 延迟 | ≤ 1 min 检测 Rep↔Raw 不一致 |
| | Phase 2 延迟 | ≤ 1 min 检测 Index↔Rep 不一致（Phase 1 完成后） |
| | Phase 3 延迟 | ≤ 1 min 检测 Projector 漂移（Phase 1+2 完成后） |
| **元数据可恢复** | Tag 重建（单 Entity） | ≤ 30 s（从 Ground Truth 重建所有 Tag） |
| | Tag 重建（全 workspace，1K Entity） | ≤ 30 min |
| | Lance 重建（单 Entity，10K chunks） | ≤ 5 min |
| **v0.2 元数据架构（事务日志）** | `_current` 指针原子交换延迟 | ≤ 100 ms（OSS Conditional PUT） |
| | `_log/` 事务日志写入吞吐 | ≥ 100 commits/s（单 Entity） |
| | `_manifest/reps.jsonl` 查询延迟 | ≤ 50 ms（O(1) 读 jsonl 头部） |
| | Time Travel 回放延迟（100 commits） | ≤ 1 s |
| | Checkpoint 生成延迟（100 commits） | ≤ 5 s |
| **可用性** | retrieval gateway 月度可用性 | ≥ 99.5% |
| **可观测** | 必埋点 | RepStep/IndexStep/ProjectorStep 各阶段耗时与失败率；Registry 注册事件；两阶段一致性指标；检索 QPS / 延迟 / top1 命中率；VFS 漂移指标（vfs_drift_count / vfs_reconcile_duration / vfs_event_lag）；Tag 重建事件；body_hash 校验结果 |
| **可扩展** | 横向扩展 | RepStep/IndexStep/ProjectorStep Executor Pool 各自独立扩缩容 |
| **安全** | workspace 隔离 | 所有查询强制带 `workspace_id`；跨 ws 默认拒绝；Plugin 注册需 mTLS + 授权（v0.2） |
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
| **S15. 两阶段一致性：Rep↔Raw 校验** | raw 更新 + Rep 未重建 | Phase 1 Reconciler 检测到 `source_content_hash` 不匹配 → 标 Rep stale → 触发 RepPipeline 重建 |
| **S16. 两阶段一致性：Index↔Rep 校验** | Rep 重建后 Index 未更新 | Phase 2 Reconciler 检测到 `index_built_from_hash` ≠ `build_from_hash_set` → 标 Index stale → 触发 IndexPipeline 重建 |
| **S17. 两阶段独立性** | IndexPipeline 重建失败 | Rep 文件仍可被读，状态 `ready`；Index `status=failed`；下一次 Reconcile 重试；Rep 不受影响 |
| **S18. Projector 失败隔离** | Wiki Projector 投影失败（v0.2） | RepPipeline 标 `partial_success`；其他 step（如 compile_summary）继续执行；Rep 文件可用；Projector 单独告警 |
| **S19. Plugin 热加载** | 动态注册新 RepStep（v0.2） | `POST /v1/rep_steps` 成功后立即可用；不影响正在执行的 RepPipeline |
| **S20. Edge 状态联动** | src Entity 标 deleted | 关联 Edge 标 deleted；不可见 |
| **S21. Tag 全量丢失恢复** | 运维误清所有 OSS Tag | `POST /v1/admin/rebuild_tags` 从 Ground Truth（文件 + 路径 + .entity_manifest.json）重建所有 Tag；系统恢复可用 |
| **S22. Tag 与文件不一致** | RepStep 写文件后进程被杀（Tag 未打） | Reconciler Phase 0 检测到"文件存在但 Tag 缺失" → 标 stale → 触发重建 |
| **S23. Lance 损坏自愈** | Lance 数据文件损坏 | 查询抛 CorruptedError → 自动标 index_status=failed → 触发 rebuild_lance() → 检索恢复 |
| **S24. body_hash 校验** | Tag content_hash 与文件实际内容不匹配 | Phase 0 检测到 body_hash ≠ Tag content_hash → 以 body_hash 为准重写 Tag + 告警 |

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
| R8 | RepStep Plugin 版本兼容性（第三方 step 升级后与 Lake 不兼容） | Step 声明 `api_version`；Lake 拒绝加载不兼容版本 |
| R9 | RepStep 执行超时 / 死循环 | Step 声明 `estimated_duration_ms`；Orchestrator 设超时，超时后标 failed |
| R10 | 第三方 RepStep 的安全隔离 | v0.1 只允许内置 Step；v0.2 引入沙箱（容器 / WASM）执行第三方 Step |
| R11 | IndexStep 与 Lance 版本耦合 | IndexStep 声明 `required_lance_version`；不满足则跳过 |
| R12 | RepPipeline 与 IndexPipeline 的触发时序（Index 在 Rep 未完成时被触发） | IndexPipeline 只在收到 `rep_all_ready` 事件后调度；Orchestrator 保证顺序 |
| R13 | Wiki 投影 idempotency 漏洞（重复事件产生重复 wikilink） | artifact 命名带 `sha256(event_id + projector + target_path)`；重复事件覆盖同目标 |
| R14 | 用户手改 `.md` 与 Lake 投影冲突 | Push 模式默认 `wiki.protect_user_edits=true` 不覆盖；编辑以 `user_edited_md` Representation 形式回流到 Lake |
| R15 | Wiki vault 写入非原子（断电导致半截文件） | `os.replace` POSIX 原子 rename；OSS 端用 `PutObject → CopyObject + if-match` 替换 |
| R16 | `rebuild()` 全量重投影与增量结果不一致 | 投影函数必须是事件的纯函数；以 `content_hash` 为基准做等价性比对 |
| R17 | OSS Tag 全部丢失（跨区域复制未携带 Tag / 运维误操作） | `.entity_manifest.json` + `.version_log.jsonl` sidecar 持久化不可推导信息；`POST /v1/admin/rebuild_tags` 从 Ground Truth 重建（§5.12） |
| R18 | Tag 写入非原子（写文件后进程被杀，Tag 未打） | 两阶段写入协议 + Reconciler Phase 0 检测"文件存在但 Tag 缺失"（§5.12.2 / §5.12.3） |
| R19 | OSS 对象静默损坏（bit rot） | Phase 0 body_hash 校验（每天采样 1%）+ `POST /v1/admin/verify?mode=full` 全量校验（§5.12.3） |
| R20 | `.entity_manifest.json` sidecar 与 Tag 不一致 | sidecar 优先原则 + Conditional Write 保证原子性（§5.12.3） |
| R21 | v0.1 元数据架构缺事务日志，变更历史不可追溯 | v0.2 引入 `_log/` 事务日志（参考 Delta _delta_log，§5.12.9） |
| R22 | v0.1 写入协议非原子（先写文件再打 Tag） | v0.2 引入 `_current` 指针原子交换（参考 Iceberg compare-and-swap，§5.12.9） |
| R23 | v0.1 大规模场景（100K+ Entity）全量 LIST prefix 慢 | v0.2 引入 `_manifest/` 快速索引（参考 Iceberg Manifest List，§5.12.11） |
| R24 | v0.1 血缘每次重新计算，效率低 | v0.3 引入 Merkle 树内容寻址（参考 lakeFS Graveler，§5.12.10） |
| R25 | Entity/Rep schema 演进无规则 | v0.3 引入显式 schema_version + 兼容性规则（参考 Delta + Iceberg + Lance，§5.12.13） |
| Q1 | entity 是否需要"跨 collection 合并"？ | v0.1 不做；v0.2 讨论 `same_as` edge |
| Q2 | wiki_md / mind_map 的 LLM 编译成本 | v0.2 实现；异步、按需、按版本 |
| Q3 | graph index 用什么存储 | v0.1 用 graph_json representation + 内存遍历；v0.2 评估 Neo4j |
| Q4 | 检索结果"高亮 / 片段截取" | v0.1 给 snippet；v0.2 接 highlighter |
| Q5 | multimodal embedding 与文本是否真的同空间 | V5 明确支持，但需回归测试 |
| Q6 | VLM pipeline 的模型选型 | v0.2 评估 Qwen2-VL / GPT-4o / Gemini |
| Q7 | Wiki Projector 是否要支持 Pull 模式（`GET /v1/wiki/project/*`） | v0.2 评估；v0.1 仅 Push 模式 |
| Q8 | RepStep 之间是否允许共享状态（跨 step 缓存） | v0.1 不允许（纯函数）；v0.2 评估 `RepStepContext.cache` |
| Q9 | RepPipeline 是否支持条件分支（if/else） | v0.1 不支持（线性拓扑）；v0.2 评估 DAG 条件边 |

---

## 20. 开源技术选型与复用清单

> **目的**：Vector-Lake 系统构建优先复用成熟开源项目，只对特有能力（Entity 抽象、RepPipeline/IndexPipeline 双管线、Projector、Two-phase 一致性）做自研。本节定义 7 大类别的开源技术栈与复用路线图。
>
> **完整清单与对比**：见 [OPEN_SOURCE_STACK.md](file:///workspace/OPEN_SOURCE_STACK.md)（含 50+ 开源项目对比、7 大类别全景图、v0.1/v0.2/v0.3 复用路线图）。

### 20.1 7 大类别速查

| 类别 | 核心需求 | v0.1 选定 | v0.2 候选 |
|---|---|---|---|
| **1. 对象存储** | Entity / Rep / Index 数据落盘 | 阿里云 OSS / AWS S3 / MinIO | Apache Ozone（超大规模） |
| **2. 数据同步** | 跨桶/跨云/增量 | **juicefs sync** / **rclone** | s3sync / SeaTunnel |
| **3. 向量检索** | 多模态 RAG 检索 | **LanceDB** ✅ | — |
| **4. Pipeline 编排** | Rep/Index/Projector 调度 | 自研 RepStep/IndexStep 调度 | **Dagster**（资产为中心） |
| **5. 元数据治理** | Entity 发现 / 血缘 / 治理 | 自研 VFS | **OpenMetadata** |
| **6. 可观测性** | 监控 / 告警 / 日志 / Trace | **Prometheus + Grafana + OTel** | — |
| **7. Lake Format** | 表格式 / 版本控制 | Lance 协议 ✅ | 借鉴 Iceberg / Delta 设计 |

### 20.2 v0.1 推荐技术栈（最小可用集）

```text
┌──────────────────────────────────────────────────────────────┐
│  Vector-Lake v0.1 Stack                                       │
│                                                               │
│  Storage:        阿里云 OSS / S3 / MinIO                     │
│  Event:          OSS Event Notification / MinIO Webhook      │
│  Vector:         LanceDB（embedded）                         │
│  Pipeline:       自研 RepStep / IndexStep 调度（§6）          │
│  Queue:          Redis Streams（§6.9，不使用 Celery）         │
│  VFS→LLM:        MCP Server（§9.5，stdio / SSE）             │
│  Config:         YAML + 环境变量                              │
│  Observability:  OpenTelemetry + Prometheus + Grafana        │
│  Errors:         Sentry                                       │
└──────────────────────────────────────────────────────────────┘
```

### 20.3 v0.2 引入候选

| 项目 | 引入理由 | 复用范围 |
|---|---|---|
| **Dagster** | 资产为中心与 Entity 模型完美契合 | RepPipeline / IndexPipeline 编排 |
| **Temporal** | 持久执行 + 状态机 | Reconciler 周期任务 + Pipeline 失败重试 |
| **OpenMetadata** | 一体化数据治理 | Entity 血缘可视化 + 数据质量 |
| **Apache Kafka** | 跨服务事件 + 可靠重试 | OSS 事件 + RepStep 异步执行 |
| **JuiceFS** | POSIX 视角访问 OSS | VFS 文件级操作优化 |
| **lakeFS** | Git-like 数据湖版本控制 | Entity 零拷贝快照 / 分支（v0.3） |

### 20.4 OSS 事件通知集成模式

```text
方式 A：OSS Event Notification → Webhook → Vector-Lake VFS
  ├─ 阿里云 OSS：SMQ/MNS → Function Compute / Webhook
  ├─ AWS S3：SNS / SQS / EventBridge → Lambda / Webhook
  └─ MinIO：notify_webhook / notify_kafka / notify_redis

方式 B：OSS Event Notification → Kafka → Vector-Lake
  └─ 高吞吐 + 可靠重试（v0.2+）

方式 C：VFS 周期 Reconciler 兜底（v0.1）
  └─ Phase 0/1/2/3 15 min 周期（§5.9.3）
```

### 20.5 关键开源项目 GitHub 链接（v0.1/v0.2 直接相关）

| 项目 | 链接 | 用途 |
|---|---|---|
| **LanceDB** | https://github.com/lancedb/lancedb | ✅ 已选定主存储 |
| **MinIO** | https://github.com/minio/minio | 对象存储 / 本地开发 |
| **juicefs sync** | https://github.com/juicefs/juicefs | 跨 OSS 同步 |
| **rclone** | https://github.com/rclone/rclone | 多云/异构同步 |
| **Dagster** | https://github.com/dagster-io/dagster | v0.2 编排 |
| **OpenMetadata** | https://github.com/open-metadata/OpenMetadata | v0.2 治理 |
| **Apache Iceberg** | https://github.com/apache/iceberg | v0.2 借鉴（事务日志） |
| **Delta Lake** | https://github.com/delta-io/delta | v0.2 借鉴（Checkpoint） |
| **OpenTelemetry** | https://github.com/open-telemetry/opentelemetry | ✅ Trace 标准 |
| **Prometheus** | https://github.com/prometheus/prometheus | ✅ Metrics |
| **Grafana** | https://github.com/grafana/grafana | ✅ 可视化 |
| **Apache Tika** | https://github.com/apache/tika | RepStep `extract` |
| **Whisper** | https://github.com/openai/whisper | RepStep `asr` |
| **PaddleOCR** | https://github.com/PaddlePaddle/PaddleOCR | RepStep `recognize_text` |

### 20.6 关键决策记录

| 决策 | 选择 | 否决项 | 理由 |
|---|---|---|---|
| **对象存储** | OSS / S3 / MinIO | 自建存储 | 复用成熟基础设施 |
| **向量检索** | LanceDB | Milvus / Qdrant | Lance 与多模态场景契合；v0.1 嵌入式 |
| **Pipeline 编排** | 自研（v0.1） → Dagster（v0.2） | Airflow | 资产为中心更契合 |
| **Lake Format** | Lance 协议 | Iceberg / Delta | Entity 模型与 Table 不同，借鉴而非直接用 |
| **任务队列** | Redis Streams（v0.1） → Kafka（v0.2） | Celery / RabbitMQ | Celery 不可靠（抽象层太多）；Redis Streams 直连更可靠 |
| **VFS→LLM** | MCP Server（v0.1） | REST API + OpenAPI | MCP 是 LLM 工具调用标准；自带 schema 描述 |
| **可观测性** | OTel + Prometheus + Grafana | ELK / 商业方案 | 云原生标准 |
| **元数据治理** | 自研 VFS（v0.1） → OpenMetadata（v0.2） | DataHub / Atlas | v0.1 简单；v0.2 集成 |

---

## 21. 部署模型与运维（Deployment & Operations）

### 21.1 部署拓扑

```text
┌─────────────────────────────────────────────────────────────┐
│  Vector-Lake 部署拓扑 (v0.1)                                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ API Server   │  │ MCP Server   │  │ Reconciler   │       │
│  │ (FastAPI)    │  │ (stdio/SSE)  │  │ (周期任务)    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                │
│         └─────────────────┼─────────────────┘                │
│                           │                                  │
│                    ┌──────┴──────┐                           │
│                    │  Redis      │                           │
│                    │  (Streams)  │                           │
│                    └──────┬──────┘                           │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐                │
│         │                 │                 │                │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐         │
│  │ Worker 1    │  │ Worker 2    │  │ Worker N    │         │
│  │ (RepPipeline│  │ (IndexPipeln│  │ (Projector) │         │
│  │  Executor)  │  │  Executor)  │  │             │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                 │                 │                │
│         └─────────────────┼─────────────────┘                │
│                           │                                  │
│              ┌────────────┴────────────┐                     │
│              │    OSS / S3 / MinIO     │                     │
│              │    (Entity + Rep +      │                     │
│              │     LanceDB 数据)        │                     │
│              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### 21.2 组件说明

| 组件 | 职责 | 扩缩容 | 推荐资源 |
| --- | --- | --- | --- |
| **API Server** | REST API（§14）+ MCP HTTP 端点 | 水平扩展（无状态） | 2 CPU, 2 GB RAM |
| **MCP Server** | LLM 工具调用（stdio / SSE） | 按需启动（每个 LLM 会话一个实例） | 1 CPU, 1 GB RAM |
| **Reconciler** | 周期一致性检查（§5.9） | 单实例（通过 Redis 锁保证） | 2 CPU, 2 GB RAM |
| **Worker** | RepPipeline / IndexPipeline / Projector 执行 | 水平扩展（按队列深度） | 2-4 CPU, 4-8 GB RAM |
| **Redis** | 任务队列 + 分布式锁 + VFS 缓存 | 单实例（v0.1），哨兵（v0.2） | 2 CPU, 4 GB RAM |
| **OSS / MinIO** | Entity / Rep / LanceDB 数据存储 | 外部依赖 | 按数据量 |

### 21.3 Docker Compose 部署（推荐 v0.1）

```yaml
# docker-compose.yml
version: "3.8"
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 3s
      retries: 3

  api:
    image: vector-lake:latest
    ports:
      - "8080:8080"
    environment:
      VL_CONFIG_PATH: /etc/vector-lake/config.yaml
    volumes:
      - ./config.yaml:/etc/vector-lake/config.yaml
    depends_on:
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    command: vector-lake serve --host 0.0.0.0 --port 8080

  worker:
    image: vector-lake:latest
    environment:
      VL_CONFIG_PATH: /etc/vector-lake/config.yaml
    volumes:
      - ./config.yaml:/etc/vector-lake/config.yaml
    depends_on:
      redis:
        condition: service_healthy
    command: vector-lake worker --concurrency 4
    deploy:
      replicas: 2

  reconciler:
    image: vector-lake:latest
    environment:
      VL_CONFIG_PATH: /etc/vector-lake/config.yaml
    volumes:
      - ./config.yaml:/etc/vector-lake/config.yaml
    depends_on:
      redis:
        condition: service_healthy
    command: vector-lake reconcile --interval 900

volumes:
  redis_data:
  minio_data:
```

### 21.4 配置文件

```yaml
# config.yaml
vector_lake:
  # OSS 连接
  storage:
    type: s3              # s3 | oss | minio
    endpoint: http://minio:9000
    access_key: minioadmin
    secret_key: minioadmin
    bucket: vector-lake
    region: us-east-1

  # LanceDB 配置
  lancedb:
    uri: s3://vector-lake/lancedb/  # 直接 S3 路径
    # 或本地路径: /data/lancedb/

  # Redis 连接
  redis:
    host: redis
    port: 6379
    db: 0
    stream_maxlen: 100000   # 背压策略（§6.9.6）

  # Pipeline 配置
  pipelines:
    default_concurrency: 4
    step_timeout: 600        # RepStep 超时（秒）
    index_timeout: 300       # IndexStep 超时（秒）

  # Reconciler 配置
  reconciler:
    interval: 900            # 运行间隔（秒），默认 15min
    batch_size: 100          # 每批处理 Entity 数
    phase0_cron: "*/15 * * * *"   # Phase 0: ETag 快速扫描
    phase1_cron: "0 */2 * * *"    # Phase 1: Rep↔Raw 一致性
    phase2_cron: "0 */4 * * *"    # Phase 2: Index↔Rep 一致性

  # MCP Server 配置
  mcp:
    enabled: true
    transport: stdio          # stdio | sse
    sse_port: 8081

  # 可观测性
  observability:
    otel_endpoint: http://jaeger:4317
    prometheus_port: 9090
    log_level: INFO           # DEBUG | INFO | WARNING | ERROR
    log_format: json          # json | text

  # 软删除
  retention:
    soft_delete_days: 30      # 软删除后数据保留天数
    cleanup_interval: 86400   # 清理任务间隔（秒），每天一次

  # Plugin 注册
  plugins:
    rep_steps: []             # 额外 RepStep 包路径
    index_steps: []           # 额外 IndexStep 包路径
    projector_steps: []       # 额外 ProjectorStep 包路径
```

### 21.5 健康检查

| 端点 | 用途 | 返回 |
| --- | --- | --- |
| `GET /health` | 基本存活检查 | `{"status": "ok"}` |
| `GET /health/ready` | 就绪检查（含 Redis + OSS 连通性） | `{"status": "ready", "checks": {"redis": true, "storage": true}}` |
| `GET /health/live` | Kubernetes liveness probe | `{"status": "alive"}` |
| `GET /metrics` | Prometheus metrics | 标准 OpenMetrics 格式 |

### 21.6 启动顺序

```text
1. Redis / MinIO 启动（docker-compose 自动处理）
2. API Server 启动 → 等待 Redis + MinIO 就绪
3. Worker 启动 → 连接 Redis Streams Consumer Group
4. Reconciler 启动 → 获取 Redis 分布式锁，开始周期检查
5. MCP Server 按需启动（LLM 会话建立时）
```

### 21.7 优雅关闭

```text
1. SIGTERM → API Server 停止接受新请求
2. Worker 完成当前正在执行的 Pipeline Step（不中断）
3. Reconciler 完成当前批次后释放锁
4. 所有组件关闭 Redis 连接
5. SIGKILL（超时 30s 后强制终止）
```

### 21.8 运维命令

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f api worker

# 扩容 Worker
docker-compose up -d --scale worker=4

# 手动触发 Reconciler
vector-lake reconcile --once

# 手动重建指定 Entity
vector-lake entity rebuild --entity-id <id> --pipeline canonical_md

# 查看 Stream 队列深度
vector-lake queue status

# 清理软删除过期数据
vector-lake cleanup --dry-run
vector-lake cleanup --force
```

---

## 22. SDK 与客户端策略（SDK & Client Strategy）

### 22.1 Python SDK（v0.1 主推）

```python
# 安装
# pip install vector-lake-client

from vector_lake import VectorLakeClient

# 初始化
client = VectorLakeClient(
    base_url="http://localhost:8080",
    api_key="vl-api-key-xxx"  # 可选
)

# === Entity 管理 ===
# 创建 Entity
entity = client.entities.create(
    workspace="my-workspace",
    collection="knowledge-base",
    entity_id="pricing-2025",
    source_path="s3://bucket/pricing.pdf",
    labels={"category": "pricing", "language": "zh"}
)

# 获取 Entity
entity = client.entities.get("my-workspace", "knowledge-base", "pricing-2025")

# 列出 Entity
entities = client.entities.list(
    workspace="my-workspace",
    collection="knowledge-base",
    labels={"category": "pricing"},
    limit=50
)

# 软删除
client.entities.delete("my-workspace", "knowledge-base", "pricing-2025")

# 物理删除
client.entities.destroy("my-workspace", "knowledge-base", "pricing-2025")

# === Representation 管理 ===
# 获取 Entity 的所有 Representation
reps = client.representations.list(
    workspace="my-workspace",
    collection="knowledge-base",
    entity_id="pricing-2025"
)

# 获取特定 Representation 内容
rep_content = client.representations.get_content(
    workspace="my-workspace",
    collection="knowledge-base",
    entity_id="pricing-2025",
    rep_type="canonical_md"
)

# === 检索 ===
# 语义检索
results = client.search(
    query="2025 年定价策略是什么？",
    workspace="my-workspace",
    collection="knowledge-base",
    top_k=10,
    search_type="hybrid"  # semantic | lexical | hybrid | structural
)

# 带过滤的检索
results = client.search(
    query="定价策略",
    workspace="my-workspace",
    collection="knowledge-base",
    top_k=10,
    filters={
        "entity_type": "document",
        "labels.category": "pricing",
        "rep_types": ["canonical_md", "vlm_md"]
    },
    include_snippets=True,
    include_provenance=True
)

# 跨模态检索
results = client.search(
    query="数据中心的架构图",
    workspace="my-workspace",
    search_type="visual"
)

# === Pipeline 管理 ===
# 触发 Pipeline 重建
client.pipelines.trigger(
    workspace="my-workspace",
    collection="knowledge-base",
    entity_id="pricing-2025",
    pipeline_id="canonical_md"
)

# 查看 Pipeline 状态
status = client.pipelines.status(
    workspace="my-workspace",
    collection="knowledge-base",
    entity_id="pricing-2025"
)

# === 血缘查询 ===
# 查询 Entity 的血缘
lineage = client.lineage.get(
    workspace="my-workspace",
    collection="knowledge-base",
    entity_id="pricing-2025"
)

# 影响分析：上游变动影响哪些下游？
impact = client.lineage.impact(
    workspace="my-workspace",
    collection="knowledge-base",
    entity_id="pricing-2025",
    rep_type="canonical_md"
)
```

### 22.2 CLI 工具

```bash
# 安装
pip install vector-lake-cli

# 配置
vl config set --endpoint http://localhost:8080 --workspace my-workspace

# Entity 操作
vl entity create --collection kb --source s3://bucket/doc.pdf --labels '{"category":"pricing"}'
vl entity list --collection kb
vl entity get --collection kb --entity-id pricing-2025
vl entity delete --collection kb --entity-id pricing-2025
vl entity rebuild --collection kb --entity-id pricing-2025

# 检索
vl search "定价策略" --collection kb --top-k 10 --type hybrid
vl search "架构图" --collection kb --type visual

# 血缘
vl lineage show --collection kb --entity-id pricing-2025
vl lineage impact --collection kb --entity-id pricing-2025 --rep-type canonical_md

# 管理
vl queue status
vl health
vl reconcile --once
```

### 22.3 MCP 客户端集成（LLM 使用）

```json
// claude_desktop_config.json 或 cursor mcp.json
{
  "mcpServers": {
    "vector-lake": {
      "command": "vector-lake-mcp",
      "args": ["--config", "/path/to/config.yaml"],
      "env": {
        "VL_WORKSPACE": "my-workspace",
        "VL_COLLECTION": "knowledge-base"
      }
    }
  }
}
```

LLM 通过 MCP 自动获得以下工具（§9.5.3）：

| 工具 | 功能 |
| --- | --- |
| `vl_search` | 语义/混合检索 |
| `vl_list_entities` | 列出 Entity |
| `vl_get_entity` | 获取 Entity 详情 |
| `vl_get_representation` | 获取 Representation 内容 |
| `vl_get_lineage` | 获取血缘 |
| `vl_list_workspaces` | 列出可用工作空间 |

### 22.4 SDK 设计原则

1. **同步 API 优先** — 检索类操作同步返回，Pipeline 触发异步但可 await
2. **类型安全** — 所有方法有完整的类型注解（Pydantic models）
3. **错误可恢复** — 网络重试 + 指数退避（默认 3 次）
4. **连接池** — httpx 异步客户端，连接复用
5. **分页** — 列表类 API 统一使用 `limit` + `cursor` 分页
6. **日志透传** — SDK 端日志级别可配置，方便调试

### 22.5 多语言 SDK 路线图

| 语言 | v0.1 | v0.2 | 备注 |
| --- | --- | --- | --- |
| **Python** | 完整 SDK | 异步 + 流式 | 主推 |
| **TypeScript** | — | 检索 + MCP | 前端 / Node.js |
| **Go** | — | 高性能 Worker | 内部 Worker 实现 |
| **Rust** | — | — | v0.3 评估 |

---

## 23. 错误模型与故障排查（Error Model & Troubleshooting）

### 23.1 错误码体系

所有 API 错误统一使用以下格式：

```json
{
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Entity 'pricing-2025' not found in workspace 'my-workspace' / collection 'kb'",
    "details": {
      "workspace": "my-workspace",
      "collection": "kb",
      "entity_id": "pricing-2025"
    },
    "request_id": "req_abc123",
    "doc_url": "https://docs.vector-lake.dev/errors/ENTITY_NOT_FOUND"
  }
}
```

### 23.2 错误分类

| 类别 | HTTP 状态码 | 前缀 | 示例 | 重试策略 |
| --- | --- | --- | --- | --- |
| **客户端错误** | 400 | `INVALID_*` | `INVALID_WORKSPACE`, `INVALID_FILTER` | 不可重试 |
| **资源不存在** | 404 | `*_NOT_FOUND` | `ENTITY_NOT_FOUND`, `REP_NOT_FOUND` | 不可重试 |
| **冲突** | 409 | `*_CONFLICT` | `ENTITY_ALREADY_EXISTS`, `PIPELINE_LOCKED` | 可重试（等锁释放） |
| **服务端错误** | 500 | `INTERNAL_*` | `INTERNAL_ERROR`, `STORAGE_UNAVAILABLE` | 可重试（指数退避） |
| **服务不可用** | 503 | `*_UNAVAILABLE` | `REDIS_UNAVAILABLE`, `OSS_UNAVAILABLE` | 可重试（指数退避） |
| **Pipeline 错误** | 422 | `PIPELINE_*` | `PIPELINE_STEP_FAILED`, `PIPELINE_TIMEOUT` | 部分可重试 |
| **索引错误** | 422 | `INDEX_*` | `INDEX_BUILD_FAILED`, `INDEX_STALE` | 可重试（重建） |

### 23.3 完整错误码列表

| 错误码 | HTTP | 含义 | 处理建议 |
| --- | --- | --- | --- |
| `INVALID_REQUEST` | 400 | 请求格式错误 | 检查 JSON schema |
| `INVALID_WORKSPACE` | 400 | 工作空间名称非法 | 使用字母数字 + 连字符 |
| `INVALID_ENTITY_ID` | 400 | Entity ID 格式非法 | 遵循命名规范 |
| `INVALID_FILTER` | 400 | 检索过滤条件非法 | 检查 filter 语法 |
| `ENTITY_NOT_FOUND` | 404 | Entity 不存在 | 确认 entity_id 和 workspace |
| `REP_NOT_FOUND` | 404 | Representation 不存在 | 检查 rep_type 是否已生成 |
| `INDEX_NOT_FOUND` | 404 | 索引不存在 | 触发 IndexPipeline 重建 |
| `ENTITY_ALREADY_EXISTS` | 409 | Entity 已存在 | 使用不同 entity_id 或先删除 |
| `PIPELINE_LOCKED` | 409 | Pipeline 正在执行中 | 等待当前执行完成 |
| `PIPELINE_STEP_FAILED` | 422 | RepStep 执行失败 | 查看 worker 日志；检查输入文件 |
| `PIPELINE_TIMEOUT` | 422 | Pipeline 执行超时 | 增加 step_timeout 配置 |
| `INDEX_BUILD_FAILED` | 422 | 索引构建失败 | 检查 Rep 文件是否完整；重试 |
| `INDEX_STALE` | 422 | 索引已过期（需重建） | 等待 Reconciler 自动重建 |
| `STORAGE_UNAVAILABLE` | 503 | OSS / MinIO 不可用 | 检查 OSS 连接和凭证 |
| `REDIS_UNAVAILABLE` | 503 | Redis 不可用 | 检查 Redis 连接 |
| `RATE_LIMITED` | 429 | 请求频率超限 | 等待后重试（含 Retry-After） |
| `INTERNAL_ERROR` | 500 | 内部错误 | 查看 request_id 对应日志 |

### 23.4 故障排查指南

#### 场景 1：Entity 创建后检索不到

```text
排查步骤：
1. 确认 Entity 状态：vl entity get --collection kb --entity-id <id>
   → 检查 status 是否为 active
2. 确认 RepPipeline 完成：vl entity status --collection kb --entity-id <id>
   → 检查 rep_status 中 canonical_md 是否为 active
3. 确认 IndexPipeline 完成：vl entity status --collection kb --entity-id <id>
   → 检查 index_status 中 semantic 是否为 built
4. 如果 stuck：查看 Worker 日志
   docker-compose logs worker | grep <entity_id>
5. 手动触发：vl entity rebuild --collection kb --entity-id <id>
```

#### 场景 2：Pipeline 执行失败

```text
排查步骤：
1. 查看失败原因：vl entity status --collection kb --entity-id <id>
   → 检查 rep_status 中 last_error 字段
2. 检查 Worker 日志：docker-compose logs worker | grep ERROR
3. 常见原因：
   - 源文件损坏：检查 source/original 文件完整性
   - 模型调用失败：检查 Embedding V5 服务可用性
   - 内存不足：Worker 内存是否达到上限
   - 超时：增大 step_timeout 配置
4. 手动重试：vl entity rebuild --collection kb --entity-id <id>
```

#### 场景 3：检索结果不准确

```text
排查步骤：
1. 确认 Rep 内容质量：vl rep get --collection kb --entity-id <id> --rep-type canonical_md
   → 检查提取内容是否准确
2. 确认索引状态：vl entity status --collection kb --entity-id <id>
   → 检查 index_status 是否为 built
3. 调整检索策略：切换到不同 search_type（hybrid/semantic/lexical）
4. 添加过滤条件：使用 labels / rep_types 缩小范围
5. 查看血缘：vl lineage show --collection kb --entity-id <id>
   → 确认是否使用了正确的 Representation
```

#### 场景 4：Reconciler 不工作

```text
排查步骤：
1. 确认 Reconciler 运行：docker-compose ps reconciler
2. 查看 Reconciler 日志：docker-compose logs reconciler
3. 确认 Redis 锁：redis-cli GET "vl:reconciler:lock"
4. 手动触发：vl reconcile --once
5. 检查配置：reconciler.interval 是否正确
```

### 23.5 日志规范

| 日志级别 | 使用场景 | 示例 |
| --- | --- | --- |
| **DEBUG** | 开发调试、Pipeline Step 详细执行 | `RepStep extract started for entity=pricing-2025` |
| **INFO** | 正常业务流程 | `Entity pricing-2025 rep canonical_md published` |
| **WARNING** | 可恢复的异常、重试 | `ETag mismatch for entity=pricing-2025, will reconcile` |
| **ERROR** | Pipeline 失败、存储错误 | `RepStep vlm_md failed: API timeout after 30s` |
| **CRITICAL** | 系统级故障 | `Redis connection lost, all workers blocked` |

所有日志必须包含：`request_id`（API 请求）、`entity_id`（Entity 操作）、`pipeline_id`（Pipeline 操作）、`worker_id`（Worker 操作）。

---

## 24. 测试与质量策略（Testing & Quality Strategy）

### 24.1 测试金字塔

```text
                  ┌──────┐
                  │ E2E  │  完整 Pipeline 链路
                  │  5%  │  (OSS → Entity → Rep → Index → Search)
                  ├──────┤
                  │ 集成  │  API + Redis + OSS + LanceDB
                  │ 15%  │
                  ├──────┤
                  │ 单元  │  RepStep / IndexStep / 状态机 / 一致性
                  │ 80%  │
                  └──────┘
```

### 24.2 测试分类

| 类型 | 覆盖目标 | 工具 | 运行频率 |
| --- | --- | --- | --- |
| **单元测试** | RepStep / IndexStep / 状态机 / 一致性校验 / 血缘推导 | pytest + pytest-cov | 每次 commit |
| **集成测试** | API 端点 / Redis Streams / OSS 读写 / LanceDB 查询 | pytest + testcontainers | 每次 PR |
| **E2E 测试** | 完整 Pipeline 链路（ingest → rep → index → search） | pytest + docker-compose | 每次 release |
| **性能测试** | 检索延迟 / Pipeline 吞吐 / 并发 Worker | locust | 每次 release |
| **兼容性测试** | OSS / S3 / MinIO 后端切换 | pytest + parametrize | 每次 PR |
| **混沌测试** | Redis 宕机 / OSS 延迟 / Worker 崩溃恢复 | chaos-mesh（v0.2） | v0.2+ |

### 24.3 单元测试示例

```python
# tests/unit/test_rep_step_extract.py
def test_extract_step_pdf():
    step = ExtractRepStep()
    result = step.execute(
        RepStepContext(
            entity_id="test-001",
            input_files={"raw": "testdata/sample.pdf"}
        )
    )
    assert result.output_files["canonical_md"].exists()
    assert result.output_files["canonical_md"].read_text().startswith("#")

# tests/unit/test_consistency.py
def test_rep_raw_consistency_etag_match():
    """Phase 0: ETag 匹配 → 一致"""
    result = consistency_checker.check_phase0(
        entity_id="test-001",
        raw_etag="abc123",
        rep_etag="abc123"
    )
    assert result.status == "consistent"

def test_rep_raw_consistency_etag_mismatch():
    """Phase 0: ETag 不匹配 → 触发 Phase 1"""
    result = consistency_checker.check_phase0(
        entity_id="test-001",
        raw_etag="abc123",
        rep_etag="def456"
    )
    assert result.status == "inconsistent"
    assert result.next_action == "phase1"

# tests/unit/test_lineage.py
def test_lineage_from_directory():
    lineage = LineageResolver.resolve(
        entity_path="vector-lake/ws/kb/entity-001/"
    )
    assert lineage.edges == [
        ("source/original", "extract/canonical_md"),
        ("extract/canonical_md", "compile/mind_map"),
        ("extract/canonical_md", "compile/summary"),
    ]
```

### 24.4 集成测试示例

```python
# tests/integration/test_api_search.py
@pytest.mark.integration
async def test_search_hybrid():
    async with VectorLakeClient(base_url="http://localhost:8080") as client:
        # 创建 Entity 并等待 Pipeline 完成
        entity = await client.entities.create(...)
        await wait_for_pipeline(entity.id, "canonical_md", timeout=60)

        # 检索
        results = await client.search(
            query="定价策略",
            workspace="test-ws",
            collection="test-kb",
            top_k=5
        )
        assert len(results.items) > 0
        assert results.items[0].entity_id == entity.id

# tests/integration/test_redis_streams.py
@pytest.mark.integration
async def test_xadd_xread():
    """验证 Redis Streams 消息传递"""
    await redis.xadd("vl:rep_queue", {"entity_id": "test-001", "pipeline_id": "canonical_md"})
    messages = await redis.xread({"vl:rep_queue": "0"}, count=1)
    assert len(messages) == 1
```

### 24.5 E2E 测试场景

| 场景 | 描述 | 预期结果 |
| --- | --- | --- |
| **S1: 文档完整链路** | PDF → canonical_md → chunk → embed → search | 检索命中；snippet 正确；provenance 可追溯 |
| **S2: 图片完整链路** | PNG → page_image → ocr_text → chunk → embed → search | 跨模态检索（文本→图片）命中 |
| **S3: 音频完整链路** | MP3 → audio_segment → transcript → chunk → embed → search | 音频内容可检索 |
| **S4: 一致性修复** | 修改 raw → Reconciler 检测 → Rep 重建 → Index 重建 | 两步自动修复完成 |
| **S5: 软删除** | 删除 Entity → 30 天内仍可恢复 → 30 天后物理删除 | 数据按预期保留和清除 |
| **S6: Pipeline 失败恢复** | RepStep 调用失败 → 重试 → 最终成功 | 指数退避重试；不超过 3 次 |
| **S7: Wiki Projector** | Entity → RepPipeline → WikiProjector → ~/wiki/*.md | Wiki 文件正确生成；wikilink 有效 |

### 24.6 CI/CD 流程

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff mypy
      - run: ruff check .
      - run: mypy src/

  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit/ -v --cov=src/ --cov-report=xml

  integration-test:
    needs: unit-test
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
      minio:
        image: minio/minio
        env: {MINIO_ROOT_USER: minioadmin, MINIO_ROOT_PASSWORD: minioadmin}
        ports: ["9000:9000"]
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: pytest tests/integration/ -v -m "not slow"
```

### 24.7 质量门禁

| 指标 | v0.1 目标 | v0.2 目标 |
| --- | --- | --- |
| **单元测试覆盖率** | ≥ 80% | ≥ 90% |
| **集成测试覆盖率** | ≥ 60% | ≥ 75% |
| **类型注解覆盖率** | ≥ 90%（mypy strict） | ≥ 95% |
| **Lint 零告警** | ruff check 0 | ruff check 0 |
| **API 响应 P99** | < 500ms（检索）/ < 2s（Entity CRUD） | < 200ms / < 1s |
| **Pipeline 吞吐** | 100 Entity/小时/Worker | 500 Entity/小时/Worker |

---

## 25. 版本策略与兼容性承诺（Version Policy & Compatibility）

### 25.1 版本号规范

遵循 [Semantic Versioning 2.0](https://semver.org/)：

```text
MAJOR.MINOR.PATCH

MAJOR — 不兼容的 API 变更
MINOR — 向后兼容的新功能
PATCH — 向后兼容的 Bug 修复
```

### 25.2 版本生命周期

| 版本 | 状态 | 支持周期 | 说明 |
| --- | --- | --- | --- |
| **v0.1.x** | 开发预览 | 每 2 周发布 patch | 核心链路可用；API 可能变更 |
| **v0.2.x** | Beta | 每月发布 minor | 新增 Projector / 血缘可视化 / Dagster 编排 |
| **v0.3.x** | RC | 每季发布 minor | Merkle 树 / lakeFS 集成 / 多租户 |
| **v1.0.0** | GA | 长期支持（LTS） | API 稳定；向后兼容保证 |

### 25.3 向后兼容性承诺

**从 v1.0.0 开始**：

| 层面 | 兼容性承诺 | 例外 |
| --- | --- | --- |
| **REST API** | 不删除字段；新增字段可选；废弃字段标记 `@deprecated` 至少保留 2 个 MINOR 版本 | 安全漏洞修复 |
| **Python SDK** | 公共方法签名不变；新增可选参数；废弃方法标记 `DeprecationWarning` | — |
| **MCP 协议** | 工具名称不变；新增工具不影响已有工具；参数新增可选 | — |
| **OSS 数据格式** | Entity Tag 字段名不变；Rep 目录结构不变；Lance 表 schema 新增列可选 | — |
| **配置文件** | 新增 key 可选；已有 key 含义不变；废弃 key 标记 `@deprecated` | — |

**v0.x 期间**：不提供向后兼容性保证。API / 数据格式 / 配置可能在任何版本变更。

### 25.4 破坏性变更流程（v1.0+）

```text
1. 在 MINOR 版本中标记 @deprecated
   → 文档说明替代方案
   → 运行时 DeprecationWarning
2. 等待至少 2 个 MINOR 版本
3. 在下一个 MAJOR 版本中移除
   → CHANGELOG 明确标注
   → 迁移指南（MIGRATION.md）
```

### 25.5 数据格式演进

| 数据层 | 演进策略 | 迁移方式 |
| --- | --- | --- |
| **Entity Tag schema** | 新增字段高位预留（7/10 已用）；v0.2 新增 3 个字段 | 新增字段无需迁移；旧数据默认值 |
| **Rep 目录结构** | 新增 rep_type 目录；不修改已有目录名 | 无需迁移 |
| **LanceDB schema** | Lance 原生支持 schema evolution（add column） | 自动；新增列为 NULL |
| **Pipeline 注册表** | 新增 RepStep/IndexStep 注册；不改已有接口 | 无需迁移 |
| **Redis Streams 消息格式** | 新增字段可选；不删已有字段 | 消费者兼容新旧格式 |

### 25.6 CHANGELOG 规范

遵循 [Keep a Changelog](https://keepachangelog.com/) 格式：

```markdown
# Changelog

## [0.1.1] - 2025-xx-xx

### Added
- 新增 `vl entity status` CLI 命令

### Fixed
- 修复 ETag 比对时 OSS 返回编码不一致的问题

### Changed
- Worker 默认并发数从 2 改为 4

## [0.1.0] - 2025-xx-xx

### Added
- 初始版本：Entity CRUD + RepPipeline + IndexPipeline + Reconciler
```

### 25.7 升级指南

```bash
# 升级到新版本
pip install --upgrade vector-lake==0.2.0

# 检查配置兼容性
vector-lake config validate

# 运行数据迁移（如有）
vector-lake migrate --from 0.1.0 --to 0.2.0 --dry-run
vector-lake migrate --from 0.1.0 --to 0.2.0

# 验证升级
vector-lake health
```

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
- **Projector**：Lake 内部 RepStep Plugin 体系的一种特殊 RepStep（§6.6 / §11），消费 Representation 文件但产出不写回 Lake 内部，而是投影到外部消费者（RAG API / Wiki / Dashboard / Web）约定的格式。
- **WikiProjector**：Projector 的一种（§12），注册为 `project_wiki` RepStep，目标消费者是 Karpathy LLM Wiki / Obsidian；投影产物是 `~/wiki/` 目录的 `.md` + wikilink + index.md + log.md，可独立运行。
- **RepStep**：RepPipeline 的可插拔步骤（§6.6），实现 `PipelineStep` Protocol，做一件事：把上游 Representation 文件变换为下游 Representation 文件。新增 rep_type = 新增 RepStep + 注册。
- **IndexStep**：IndexPipeline 的可插拔步骤（§6.7），实现 `IndexStep` Protocol，做一件事：消费 Representation 文件构建搜索索引。新增 index_type = 新增 IndexStep + 注册。IndexStep 与 RepStep 完全解耦。
- **RepStepRegistry**：全局 RepStep 注册表，支持运行时动态注册（plugin 注入）。
- **IndexStepRegistry**：全局 IndexStep 注册表，支持运行时动态注册。
- **RepPipeline**：内容变换流水线，由有序 RepStep 组装，产出 Representation 文件。有血缘、有版本。
- **IndexPipeline**：索引构建流水线，由有序 IndexStep 组装，消费 Representation 文件产出搜索索引。无血缘、可重建。

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
