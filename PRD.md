# Vector-Lake 智能知识搜索引擎层 — PRD

> **版本**：v0.2 修订版
> **状态**：待评审
> **目标读者**：产品 / 架构 / 工程 / 算法
> **核心定位**：把 OSS 数据湖升级为可被智能引擎直接调用的"知识搜索引擎层"。
> **修订说明**：基于 v0.1 review + 架构讨论 + 开源项目对标，核心变更：(25) **支持输入格式清单（§6.5）**：新增完整格式支持清单，覆盖 5 大 entity_type 共 50+ 种文件格式——文档格式 14 种（md/doc/docx/pdf/ppt/pptx + WPS 系列 .wps/.wpt/.dps/.dpt + txt/rtf/odt/html）；表格格式 9 种（csv/xls/xlsx + WPS 系列 .et/.ett + tsv/parquet/json）；图片格式 9 种（Jina V5 Omni 全量：jpg/png/gif/webp/bmp/tiff/avif/heic/svg）；音频格式 6 种（Jina V5 Omni 全量：wav/mp3/flac/ogg/m4a/opus）；视频格式 7 种（Jina V5 Omni 全量：mp4/avi/mov/mkv/webm/flv/wmv）；新增格式→entity_type→Pipeline 路由总表（§6.5.6）、格式不支持时的处理策略（§6.5.7）、v0.2 格式扩展计划（§6.5.8）；§2.1 entity_type 取值新增 table；§6.4.1 判定表更新引用 §6.5；RepStep transcribe 扩展支持 video entity_type；(26) **排版保留与 Rep 对齐（§4.3.1）**：索引时保留排版信息，chunk 增加 `layout` 字段（含 blocks/bbox/page_number/page_size），与 Representation 对齐；新增 layout_json 完整 Schema（8 种 block 类型 + start_pos/end_pos 区间映射）；IndexStep chunk_and_embed_text/image/table 新增 `optional_reps: layout_json`；RepStep parse 产出新增 `layout_json`；排版一致性保证（layout↔canonical_md 覆盖率检测 + chunk↔layout 区间重叠校验 + layout↔page_image 引用完整性）；排版在多 Rep 间共享（同一 Entity 的 canonical_md/ocr_text/vlm_md 共享同一份 layout_json）；锚点跳转机制（5 种锚点类型：Markdown slug / 页码 / bbox 坐标 / 字符偏移 / 时间戳）；锚点跳转 REST API（anchor-jump + cross_rep_anchors 跨 Rep 一致性）；block_id 作为锚点唯一标识保证跨 Rep 定位一致；(27) **OCR+VLM 合并为视觉识别 Pipeline**：`rep_pipeline_b`（OCR）+ `rep_pipeline_c`（VLM）合并为 `rep_pipeline_b`（视觉识别），步骤 `render_page` → `visual_recognize`，单步同时产出 `ocr_text` + `vlm_md`；RepStep `ocr` + `vlm` 合并为 `visual_recognize`；消除 pipeline_c 编号，family 缩减为 a/b/d/e/f/g；同步更新依赖图、Pipeline 映射表、RepPipeline JSON 示例、PIPELINE_REGISTRY 代码块、RepStep 清单、OSS Tag 示例；(28) **Rep 继承链与级联传播（§5.13）**：新增 §5.13 Rep 继承链与级联传播——Rep Tag 从 7→9 个字段（新增 `input_content_hash` + `content_hash`），每个 Rep 记录直接上游的内容指纹；§5.9.1 `source_content_hash` 语义修正为 `input_content_hash`（直接上游，不一定是 raw）；新增 Rep 继承链定义（§5.13.1，含完整继承图示例 + 9 种 Rep 的 input_content_hash 映射表）；新增 Rep 变动级联传播（§5.13.2，含 BFS 级联算法 + 5 步级联场景）；新增 Index 增量重建（§5.13.3，required_reps ready 即可触发，不等全部 Rep ready，v0.1 先全量等待 v0.2 切增量）；新增继承链可观测性 API（§5.13.4，4 个查询端点）；新增继承链 vs 血缘对比（§5.13.5）；§5.7.1 Rep 联动表新增"上游 Rep content_hash 变化"行 + 引用 §5.13；§5.9.1 校验场景新增"上游 Rep 更新但下游 Rep 未重建"场景；Tag 示例 transform=ocr→visual_recognize；(29) **补全缺失的 3 条 Pipeline**：新增 `rep_pipeline_h` 视频关键帧抽取（RepStep `extract_keyframes`，依赖 ffmpeg，输出 `keyframe_image` + `keyframe_timeline`，适用于所有视频格式）；新增 `index_pipeline_video` 视频双模态索引（IndexStep `chunk_and_embed_video`，required_reps 为 `transcript` + `keyframe_image`，同时索引音轨和关键帧）；新增 `index_pipeline_structural` 结构化检索（IndexStep `register_duckdb_view`，将 `table_parquet` 注册到嵌入式 DuckDB 视图）；§2.2 树状图补全 video/structural/audio/table 分支；§6.1 映射总表新增 H 行；§6.5.6 路由总表 video 行从 F+E 改为 F+H；§6.8.3 IndexStep 表新增 `chunk_and_embed_video` + `register_duckdb_view`；§6.7.4/§13.2 RepPipeline 编号 family 扩展为 a/b/d/e/f/g/h；§13.3 IndexPipeline 补全 video/structural；§6.8.1 v0.1 限制 5 Index 调整为 text/image/video/structural/graph；(30) **完整变动管理（§5.14）**：新增 §5.14 完整变动管理（Change Management），集中覆盖 10 个变动相关维度——5.14.1 变动检测（5 个检测源：OSS 事件/Reconciler 周期/API 写入/Phase 0/Edge 主动）；5.14.2 变动分类（7 类 C1-C7：Raw/Rep 内容/Rep 状态/Index/Schema/Entity 元数据/Projector 配置）；5.14.3 变动追踪（两层日志 L1 version_log + L2 _log/v0.2 事务日志 + v0.1 简化追踪方案 6 项操作字段）；5.14.4 变动通知（4 个通知目标：Reconciler/Worker/Projector/Edge Resolver + change_detected 消息格式）；5.14.5 变动回滚（5 类回滚策略 + 3 条不变量：不删除历史/不破坏外引用/不绕过 Reconciler）；5.14.6 变动冲突（5 个冲突场景 + 3 条解决原则：锁优先/版本兜底/Reconciler 终极裁决）；5.14.7 变动回放/Time Travel（v0.1 基础快照 + v0.2 snapshot/diff API + v0.3 完整 Time Travel）；5.14.8 批量变动（3 种批量场景 API：批量导入/批量重打标签/批量删除 + 统一响应格式）；5.14.9 跨 Entity 变动（强/弱/嵌入 3 种 Edge 引用类型 + 决策矩阵）；5.14.10 投影端变动（Projector 4 步响应：评估/计算 diff/应用差异/记录历史 + 3 种同步模式 Realtime/Batch/On-demand）；5.14.11 变动 SLA 与可观测性（5 项 SLA 指标 + /changes/stats 端点）；(31) **Watch Mode 自动构建（§5.15）**：新增 §5.15 Watch Mode（自动构建模式），核心承诺"指定目录上传即自动构建索引，无需调用 API"；包含 10 个子节：5.15.1 启用与配置（OSS 监听 + 本地监听 + Reconciler 兜底 3 种源 + config.yaml 完整配置）；5.15.2 自动构建流程（5 步：检测→解析路径→创建 Entity→RepPipeline→Index）+ Redis Streams `vl:watch_ingest` 消息格式；5.15.3 entity_id 命名策略（5 种：filename/filepath/uuid/hash/template + 冲突处理）；5.15.4 4 类事件自动处理（新建/修改/删除/重命名）；5.15.5 文件过滤与安全（白/黑名单 + 大小限制 + 并发限流 + 文件稳定期 30s + 访问控制）；5.15.6 批量上传优化（5s flush 批量聚合 + 4 项性能指标）；5.15.7 与显式 API 协调（3 种范式并存 + 数据模型完全一致）；5.15.8 错误处理与告警（5 类错误 + Dead Letter 队列）；5.15.9 可观测性（3 个 API 端点 + 4 个 Prometheus 指标）；5.15.10 v0.1 实施范围（14 项功能 v0.1/v0.2 分布）；(32) **Watch Mode 监听/接入策略解耦**：§5.15.1 重构为 Watch Strategy（监听策略）+ Ingest Strategy（接入策略）两层解耦设计——Watch Strategy 只管"检测 prefix 下的文件变动"（prefix + type + recursive + 限流），Ingest Strategy 管"文件怎么变成 Entity"（entity_id_strategy + labels + allowed_extensions + max_file_size + on_conflict）；一个 Watch Strategy 绑定一个 Ingest Strategy，多个 Watch Strategy 可复用同一 Ingest Strategy；新增 5 个预置 Ingest Strategy（standard_doc/wps_doc/multimedia/tabular/web_crawl）+ 5 个 Watch Strategy 示例；§5.15.2 自动构建流程拆为 6 步（Watch 检测→Watch 匹配→Ingest 决定→投递消息→RepPipeline→Index ready）；§5.15.3 新增 on_conflict 冲突处理策略（update/skip/error）；§5.15.5 明确过滤规则归属 Ingest Strategy、限流归属 Watch Strategy；消息格式新增 watch_strategy_id + ingest_strategy_id + on_conflict 字段。(33) **§5.15 Watch Mode 深度 review 修复**：新增 §5.15.11 高级场景（9 个子节覆盖生产落地关键问题）——5.15.11.1 运行时更新 Watch/Ingest Strategy（Watch Strategy 热更新字段表 + Ingest Strategy 热更新字段表 + PATCH/PUT/DELETE API + Ingest Strategy 删除保护（409 Conflict + bound_watch_strategies 引用检查 + force=true 强制删除）+ 生命周期状态机 initializing/active/paused/error/stopped + 缓冲队列）；5.15.11.2 多租户隔离（workspace 强绑定 + cross_workspace_read 显式授权 + 5 维隔离机制）；5.15.11.3 竞态与一致性（4 类竞态 + Redis 分布式锁 lock:watch:entity:{entity_id} + 等待队列 + Entity/Rep/Index 三层幂等 + 同 Entity 多 RepPipeline 并发 RepPipeline 级锁引用 §6.9）；5.15.11.4 Dead Letter TTL 与自动清理（retention_days/cleanup_interval/max_total_size_gb 完整配置 + 5min/1h/6h 指数退避重试 + 清理失败 3 次重试 + WatchCleanupFailed 告警 + 4 类告警规则）；5.15.11.5 多 Watch Strategy 冲突（启动时拒绝重叠 prefix + allow_conflict opt-in + 父子 prefix 最长匹配去重机制 Longest Prefix Match + processed_by Redis 标记 + ETag 差异检测 create/update/skip 三态）；5.15.11.6 Per-Collection 配额（v0.1 仅全局默认 + v0.2 per-collection 覆盖 + default + overrides 两层 + 4 类配额项 + 429 拒绝 + 令牌桶限流）；5.15.11.7 Delete-Only Watch（event_filter.types=[deleted] + auto_create_entity=false + 全功能 vs 仅删除对比表）；5.15.11.8 文件删除/中途失败边界（5 类场景：raw 已拷贝 RepPipeline 中途删 / 半截上传 / 格式损坏 / Watcher 宕机堆积 / API 创建 Entity 的 source_oss_path 外部删除 + source_oss_path/source_etag/source_type 三字段 + Reconciler Phase 1 兜底检测）；5.15.11.9 MCP Tool 暴露（8 个 Tool 表 watch_list/status/create/pause/resume/replay/dead_letter_list/replay + v0.1 列标注 + watch:read/write/admin 权限模型）；§5.15.8 错误处理表扩展为 8 类（新增 OSS API 限流 + ETag 重复事件）；§5.15.9 可观测性 API 端点从 3 个扩展为 8 个（新增 ingest_strategy 详情 + 5 个运行时管理端点）+ Prometheus 指标从 4 个扩展为 8 个 + 新增结构化 JSON 日志规范；§5.15.10 v0.1 实施范围表从 14 行扩展为 25 行（新增 Ingest/Watch 解耦、5 种 entity_id 策略、on_conflict、TTL、多租户、运行时更新、多 Watch 冲突检测、Ingest Strategy 删除保护、Watch Listener 启动/关闭、MCP Tool、Per-collection 配额 v0.1 全局默认等项）；§20.6 启动顺序补充 Watch Listener 启动流程（6 步：加载配置→配置校验→初始化监听→注册 Producer→状态上报→开始接收事件 + prefix 重叠检测引用 §5.15.11.5）；§20.7 优雅关闭补充 Watch Listener 关闭流程（5 步：停止接收→缓冲队列处理→状态上报→关闭监听→关闭 Producer + 缓冲上限 10000 条 + 本地暂存超限部分）；§20.8 运维命令补充 Watch/Ingest/Dead Letter 管理（watch list/status/pause/resume/replay + ingest list/show/update + dead-letter list/replay/cleanup）。(34) **PRD 框架整理**：修复 §5.12/§5.13 顺序颠倒（5.13 在 5.12 前→交换为正确顺序）；修复 §25.5 评审清单旧编号 19.6→25.5；修复全文交叉引用（§6.6→§6.7 RepStep、§6.7→§6.8 IndexStep、§6.8→§6.9 并发模型、§6.9→§6.10 Redis Streams、§8.7→§8.6 DuckDB、§20→§19 开源选型、§21→§20 部署、§22→§21 SDK、§21.6/7/8→§20.6/7/8 等）；新增文档头部完整目录（§0-§25 共 26 章 + 83 子节）。(35) **PRD 化繁为简**：修复 §5.9.3 重复编号→§5.9.4；§4 删除实现级行为代码（Entity Python 类方法 ~150 行、L1-L3 Stage 函数 ~200 行、PyArrow/Pydantic schema ~105 行），保留 Schema JSON 定义；§5.12.9-5.12.13 五节压缩为一节对比表（~190 行→~15 行）；§5.14 七个 v0.2 子节压缩为占位（~120 行→~28 行）；§5.15.11.5/6/7 三个 v0.2 子节压缩为占位（~206 行→~9 行）；§4.2 Rep Tag 表引用 §4.6 去重 + Tag 字段数修正 7→9；修订记录 #1-#24 移至 §25.6 变更历史；§7/§10/§16/§17 空壳章节加待补充标注。(36) **URL Entity 支持**：§4.1 标题从"1 OSS Object = 1 Entity"扩展为"1 Source = 1 Entity"；Entity Schema 新增 `source_type` 字段（oss | url）；新增 URL Entity 完整设计——1 URL = 1 Entity，`entity_id_strategy` 新增 `url_hash`（推荐）/ `url_path` / `template`；URL 抓取后写入 `source/original` + `.meta.json` sidecar（存 source_url / fetched_at / http_etag / content_type 等抓取元数据）；新增文件 Entity vs URL Entity 对比表；§4.5 新增 `fetch_url` 标准 RepStep（输入 source_url → 输出 source/original，按 Content-Type 路由 entity_type，Reconciler 定期 HEAD 请求检测变更）；§5.15.1 新增第 5 个预置 Ingest Strategy `web_crawl`（source_type: url + crawl_config + poll_config）；预置策略数从 4 更新为 5。(37) **v0.1 核心流路定义**：§6.7.3 RepStep 清单新增 `fetch_url`（URL 抓取）、`parse_html`（HTML→MD）、`convert_to_pdf`（办公文档转 PDF，依赖 LibreOffice headless）三个 v0.1 RepStep；`render_page` 输入扩展为 `raw` / `source/pdf`；§6.7.4 RepPipeline 组装新增 `rep_pipeline_url`（fetch_url → parse_html），`rep_pipeline_b` 更新为 `convert_to_pdf` → `render_page` → `visual_recognize`；§6.3 映射表新增 `url` entity_type 行；新增 §6.7.6 v0.1 核心流路"一切皆 MD"——流路 1：URL → HTML → MD（fetch_url → parse_html）；流路 2：Office → PDF → VLM → MD（convert_to_pdf → render_page → visual_recognize）；流路 3：直接 MD（parse）；含完整 v0.1 Pipeline 路由总表（12 行）。(38) **实现就绪缺失文档补全**：§9.5 新增集中式 API Reference（8 子节 31 个 REST 端点 + 8 个 MCP Tool）；§9.7 新增 HTTP 错误码定义（10 个状态码 + 统一错误响应格式）；§9.8 新增认证与授权（v0.1 workspace 级 API Key，v0.2 OAuth2+RBAC）；§6.11 新增 Redis Key 命名规范（15 个 Key 模式 + 命名规则）；§19.7 新增 config.yaml 完整 Schema（14 个顶级配置块 + 环境变量注入 + 6 个热更新字段）；原 §9.5 VFS MCP Server 重编号为 §9.6。

## 目录

- [§0. 一句话定义](#0-一句话定义)
- [§1. 产品概述](#1-产品概述)
  - [§1.1 背景](#11-背景)
  - [§1.2 产品愿景](#12-产品愿景)
  - [§1.3 目标（Goals）](#13-目标goals)
  - [§1.4 非目标（Non-Goals）](#14-非目标non-goals)
  - [§1.5 用户角色（User Personas）](#15-用户角色user-personas)
  - [§1.6 竞争定位（Competitive Positioning）](#16-竞争定位competitive-positioning)
- [§2. 核心抽象（Core Abstractions）](#2-核心抽象core-abstractions)
  - [§2.1 一等公民定义](#21-一等公民定义)
  - [§2.2 核心链路](#22-核心链路)
  - [§2.3 一句话架构](#23-一句话架构)
  - [§2.4 Representation 是"认知视角"](#24-representation-是认知视角)
  - [§2.5 Lineage 是一等公民](#25-lineage-是一等公民)
  - [§2.6 Pipeline 是两套独立的一等公民](#26-pipeline-是两套独立的一等公民)
- [§3. 架构设计](#3-架构设计)
  - [§3.1 分层架构](#31-分层架构)
  - [§3.2 模块划分](#32-模块划分)
  - [§3.3 数据流：事件驱动 + 实时 VFS](#33-数据流事件驱动-实时-vfs)
- [§4. 数据模型](#4-数据模型)
  - [§4.1 Entity（1 OSS Object = 1 Entity）](#41-entity1-oss-object-1-entity)
  - [§4.2 Representation（认知视角）](#42-representation认知视角)
  - [§4.3 Chunk（检索粒度，索引方法）](#43-chunk检索粒度索引方法)
  - [§4.4 跨 Entity 关系（作为 graph_json representation）](#44-跨-entity-关系作为-graphjson-representation)
  - [§4.5 Pipeline（两套独立流水线）](#45-pipeline两套独立流水线)
  - [§4.6 存储模型：Entity 目录自包含 + Rep 写 OSS / Index 写 Parquet → Lance](#46-存储模型entity-目录自包含-rep-写-oss-index-写-parquet-lance)
- [§5. 状态模型（分层）](#5-状态模型分层)
  - [§5.1 OSS Object Tag — 用户意图](#51-oss-object-tag-用户意图)
  - [§5.2 Entity Status — 知识对象状态](#52-entity-status-知识对象状态)
  - [§5.3 Pipeline Run Status — 处理状态](#53-pipeline-run-status-处理状态)
  - [§5.4 Representation Status — 单个视角是否可用](#54-representation-status-单个视角是否可用)
  - [§5.5 Chunk Status — 检索可见性](#55-chunk-status-检索可见性)
  - [§5.6 版本与发布](#56-版本与发布)
  - [§5.7 状态联动规则（两阶段）](#57-状态联动规则两阶段)
  - [§5.8 内容寻址变更检测](#58-内容寻址变更检测)
  - [§5.9 两阶段一致性校验](#59-两阶段一致性校验)
  - [§5.10 Index Status（独立状态模型）](#510-index-status独立状态模型)
  - [§5.11 Edge 生命周期](#511-edge-生命周期)
  - [§5.12 元数据可靠性与重建策略](#512-元数据可靠性与重建策略)
  - [§5.13 Rep 继承链与级联传播（Rep Inheritance & Cascade）](#513-rep-继承链与级联传播rep-inheritance-cascade)
  - [§5.14 完整变动管理（Change Management）](#514-完整变动管理change-management)
  - [§5.15 Watch Mode（自动构建模式）](#515-watch-mode自动构建模式)
- [§6. Pipeline 定义](#6-pipeline-定义)
  - [§6.1 Pipeline 是一等公民](#61-pipeline-是一等公民)
  - [§6.2 Pipeline 编排原则](#62-pipeline-编排原则)
  - [§6.3 Pipeline 与 Entity Type 的映射](#63-pipeline-与-entity-type-的映射)
  - [§6.4 边界与混合型 Entity](#64-边界与混合型-entity)
  - [§6.5 支持输入格式清单（Supported Input Formats）](#65-支持输入格式清单supported-input-formats)
  - [§6.6 Pipeline 之间的级联与避免重复](#66-pipeline-之间的级联与避免重复)
  - [§6.7 RepStep Plugin 体系（内容变换插件）](#67-repstep-plugin-体系内容变换插件)
  - [§6.8 IndexStep Plugin 体系（索引构建插件）](#68-indexstep-plugin-体系索引构建插件)
  - [§6.9 RepStep / IndexStep 并发模型](#69-repstep-indexstep-并发模型)
  - [§6.10 任务队列：Redis Streams（v0.1 选定）](#610-任务队列redis-streamsv01-选定)
- [§7. 多模态 Embedding 策略](#7-多模态-embedding-策略)
  - [§7.1 Embedding V5 Task 映射表](#71-embedding-v5-task-映射表)
  - [§7.2 查询端统一用 retrieval.query](#72-查询端统一用-retrievalquery)
  - [§7.3 双向量策略（音频场景）](#73-双向量策略音频场景)
- [§8. 检索能力（Retrieval Capabilities）](#8-检索能力retrieval-capabilities)
  - [§8.1 Virtual File System（VFS）— 文件系统级能力](#81-virtual-file-systemvfs-文件系统级能力)
  - [§8.2 能力清单](#82-能力清单)
  - [§8.3 Hybrid Search（v0.1 核心检索模式）](#83-hybrid-searchv01-核心检索模式)
  - [§8.4 预览能力（Preview）](#84-预览能力preview)
  - [§8.5 工具协议](#85-工具协议)
  - [§8.6 DuckDB 统一访问 — 表格型 Entity 的 SQL 查询](#86-duckdb-统一访问-表格型-entity-的-sql-查询)
- [§9. 智能引擎（Intelligent Engine）](#9-智能引擎intelligent-engine)
  - [§9.1 目标](#91-目标)
  - [§9.1.1 三类一等检索能力](#911-三类一等检索能力)
  - [§9.2 流程](#92-流程)
  - [§9.3 路由策略（v0.1 规则版）](#93-路由策略v01-规则版)
  - [§9.4 智能引擎与 §8 检索能力的映射](#94-智能引擎与-8-检索能力的映射)
  - [§9.5 API Reference（v0.1 端点汇总）](#95-api-referencev01-端点汇总)
  - [§9.6 VFS MCP Server（向 LLM 暴露 Lake）](#96-vfs-mcp-server向-llm-暴露-lake)
- [§10. 设计原则（不可妥协）](#10-设计原则不可妥协)
- [§11. Projector 层（多目标投影）](#11-projector-层多目标投影)
  - [§11.1 设计目标](#111-设计目标)
  - [§11.2 Projector 作为 RepStep](#112-projector-作为-repstep)
  - [§11.3 内置 Projector 清单](#113-内置-projector-清单)
  - [§11.4 投影生命周期（复用 RepPipeline 编排）](#114-投影生命周期复用-reppipeline-编排)
  - [§11.5 投影一致性等级](#115-投影一致性等级)
  - [§11.6 投影失败的恢复](#116-投影失败的恢复)
- [§12. Wiki Projector 详设](#12-wiki-projector-详设)
  - [§12.1 设计目标](#121-设计目标)
  - [§12.2 投影范围](#122-投影范围)
  - [§12.3 字段映射表（Lake 内部 → Wiki 格式）](#123-字段映射表lake-内部-wiki-格式)
  - [§12.4 关系边（edge）到 Wikilink 渲染](#124-关系边edge到-wikilink-渲染)
  - [§12.5 推送策略](#125-推送策略)
  - [§12.6 反向回写（用户手改识别）](#126-反向回写用户手改识别)
  - [§12.7 SCHEMA.md / index.md / log.md 维护责任](#127-schemamd-indexmd-logmd-维护责任)
  - [§12.8 数据流（一次 ingest 到 wiki 落地）](#128-数据流一次-ingest-到-wiki-落地)
  - [§12.9 反向验证（不变量）](#129-反向验证不变量)
  - [§12.10 Wiki Projector v0.1 范围](#1210-wiki-projector-v01-范围)
  - [§12.11 与 Karpathy LLM Wiki 的对位](#1211-与-karpathy-llm-wiki-的对位)
- [§13. v0.1 范围](#13-v01-范围)
  - [§13.1 文件类型](#131-文件类型)
  - [§13.2 RepPipeline（v0.1 内置）](#132-reppipelinev01-内置)
  - [§13.3 IndexPipeline（v0.1 内置）](#133-indexpipelinev01-内置)
  - [§13.4 ProjectorStep（v0.1 内置）](#134-projectorstepv01-内置)
  - [§13.5 Rep](#135-rep)
  - [§13.6 Index](#136-index)
  - [§13.7 状态](#137-状态)
  - [§13.8 能力](#138-能力)
  - [§13.9 明确不在 v0.1 范围](#139-明确不在-v01-范围)
- [§14. API 设计（v0.1 形态）](#14-api-设计v01-形态)
  - [§14.1 内部管线 API（异步）](#141-内部管线-api异步)
  - [§14.2 检索 API（同步，对上层应用）](#142-检索-api同步对上层应用)
  - [§14.3 Entity 操作 API（对应 Entity 类方法）](#143-entity-操作-api对应-entity-类方法)
  - [§14.4 统一响应](#144-统一响应)
  - [§14.5 Plugin 注册 API（v0.2）](#145-plugin-注册-apiv02)
  - [§14.6 Edge 操作 API（v0.1）](#146-edge-操作-apiv01)
  - [§14.7 管理员 API（元数据可靠性，v0.1）](#147-管理员-api元数据可靠性v01)
- [§15. 非功能需求（NFR）](#15-非功能需求nfr)
- [§16. 关键场景（v0.1 验收用例）](#16-关键场景v01-验收用例)
- [§17. 里程碑](#17-里程碑)
- [§18. 风险与开放问题](#18-风险与开放问题)
- [§19. 开源技术选型与复用清单](#19-开源技术选型与复用清单)
  - [§19.1 7 大类别速查](#191-7-大类别速查)
  - [§19.2 v0.1 推荐技术栈（最小可用集）](#192-v01-推荐技术栈最小可用集)
  - [§19.3 v0.2 引入候选](#193-v02-引入候选)
  - [§19.4 OSS 事件通知集成模式](#194-oss-事件通知集成模式)
  - [§19.5 关键开源项目 GitHub 链接（v0.1/v0.2 直接相关）](#195-关键开源项目-github-链接v01v02-直接相关)
  - [§19.6 关键决策记录](#196-关键决策记录)
- [§20. 部署模型与运维](#20-部署模型与运维)
  - [§20.1 部署拓扑](#201-部署拓扑)
  - [§20.2 组件说明](#202-组件说明)
  - [§20.3 Docker Compose 部署（推荐 v0.1）](#203-docker-compose-部署推荐-v01)
  - [§20.4 配置文件](#204-配置文件)
  - [§20.5 健康检查](#205-健康检查)
  - [§20.6 启动顺序](#206-启动顺序)
  - [§20.7 优雅关闭](#207-优雅关闭)
  - [§20.8 运维命令](#208-运维命令)
- [§21. SDK 与客户端策略](#21-sdk-与客户端策略)
  - [§21.1 Python SDK（v0.1 主推）](#211-python-sdkv01-主推)
  - [§21.2 CLI 工具](#212-cli-工具)
  - [§21.3 MCP 客户端集成（LLM 使用）](#213-mcp-客户端集成llm-使用)
  - [§21.4 SDK 设计原则](#214-sdk-设计原则)
  - [§21.5 多语言 SDK 路线图](#215-多语言-sdk-路线图)
- [§22. 错误模型与故障排查](#22-错误模型与故障排查)
  - [§22.1 错误码体系](#221-错误码体系)
  - [§22.2 错误分类](#222-错误分类)
  - [§22.3 完整错误码列表](#223-完整错误码列表)
  - [§22.4 故障排查指南](#224-故障排查指南)
  - [§22.5 日志规范](#225-日志规范)
- [§23. 测试与质量策略](#23-测试与质量策略)
  - [§23.1 测试金字塔](#231-测试金字塔)
  - [§23.2 测试分类](#232-测试分类)
  - [§23.3 单元测试示例](#233-单元测试示例)
  - [§23.4 集成测试示例](#234-集成测试示例)
  - [§23.5 E2E 测试场景](#235-e2e-测试场景)
  - [§23.6 CI/CD 流程](#236-cicd-流程)
  - [§23.7 质量门禁](#237-质量门禁)
- [§24. 版本策略与兼容性承诺](#24-版本策略与兼容性承诺)
  - [§24.1 版本号规范](#241-版本号规范)
  - [§24.2 版本生命周期](#242-版本生命周期)
  - [§24.3 向后兼容性承诺](#243-向后兼容性承诺)
  - [§24.4 破坏性变更流程（v1.0+）](#244-破坏性变更流程v10)
  - [§24.5 数据格式演进](#245-数据格式演进)
  - [§24.6 CHANGELOG 规范](#246-changelog-规范)
  - [§24.7 升级指南](#247-升级指南)
- [§25. 附录](#25-附录)
  - [§25.1 与现有组件的对接](#251-与现有组件的对接)
  - [§25.2 Chunking UseCase 字段映射](#252-chunking-usecase-字段映射)
  - [§25.3 名词表](#253-名词表)
  - [§25.4 开源项目 Review：血缘方案对比](#254-开源项目-review血缘方案对比)
  - [§25.5 评审清单（Review Checklist）](#255-评审清单review-checklist)
  - [§25.6 变更历史](#256-变更历史)

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
| **数据工程师 / Pipeline 开发者** | 开发 RepStep / IndexStep / ProjectorStep Plugin；定义 RepPipeline 拓扑；调试 Pipeline 编排 | 清晰的 Plugin 接口（Protocol）；可复用的 Step 注册机制；丰富的日志与调试工具 | Python SDK (§21) + CLI + RepStepRegistry API |
| **AI 应用开发者** | 构建 RAG 应用、Agent、问答系统；调用检索 API 获取知识证据 | 统一的检索入口（semantic + structural + textual）；可解释的检索结果（provenance + snippet）；低延迟 | REST API + MCP Server (§9.6) + Python SDK |
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
| **Representation** | Entity 的"认知视角"（canonical_md / vlm_md / mind_map / graph_json / page_image / ...） | **派生产物**，血缘关系从目录层级推导 |
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
    ├── RepPipeline B: "视觉识别" ──► rep(vlm_md)
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
  → [Rep 级联] page_image stale → vlm_md stale
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
  ├── rep_pipeline_b: "视觉识别"
  │     └── render_page → visual_recognize: raw → page_image → vlm_md
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
  │         消费: canonical_md / vlm_md
  │
  ├── index_pipeline_image: "图片索引"
  │     └── chunk_and_embed_image → build_vector_index
  │         消费: page_image
  │
  ├── index_pipeline_video: "视频双模态索引"
  │     └── chunk_and_embed_audio → build_vector_index
  │         └── chunk_and_embed_image → build_vector_index
  │         消费: transcript + keyframe_image（音轨 + 关键帧）
  │
  ├── index_pipeline_structural: "结构化检索"
  │     └── register_duckdb_view（将 table_parquet 注册到嵌入式 DuckDB）
  │         消费: table_parquet
  │
  ├── index_pipeline_audio: "音频索引（纯音频）" (v0.2)
  │     └── chunk_and_embed_audio → build_vector_index
  │         消费: transcript
  │
  ├── index_pipeline_table: "表格文本索引" (v0.2)
  │     └── chunk_and_embed_table → build_vector_index
  │         消费: table_md / table_json
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
│      visual_recognize → vlm_md                              │
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

### 4.1 Entity（1 Source = 1 Entity）

**Entity 属性视图（从 OSS Tag + 路径实时组装，非持久化文件）**：

```json
{
  "entity_id": "abc123",              // ← 从 OSS 目录名解析
  "entity_type": "document",          // ← OSS Tag: entity_type
  "workspace_id": "ws_001",           // ← 从 OSS 路径前缀解析
  "collection_id": "kb_001",          // ← 从 OSS 路径前缀解析
  "name": "pricing.pdf",              // ← OSS Tag: name
  "source_type": "oss",               // ← OSS Tag: source_type（oss | url）
  "source_uri": "oss://bucket/.../abc123/source/original",  // ← source_type=oss 时从 OSS 路径组装；source_type=url 时为原始 URL
  "content_hash": "sha256_xxx",       // ← OSS Tag: content_hash
  "version": 1,                       // ← OSS Tag: version
  "status": "enabled",                // ← OSS Tag: rag_status
  "labels": ["pricing", "finance"],   // ← OSS Tag: labels（逗号分隔解析）
  "created_at": "...",                // ← OSS 对象的 LastModified
  "updated_at": "..."                 // ← OSS Tag 变更时间
}
```

> **注意**：不存在 entity.json 文件。所有属性从 OSS Tag + 路径实时读取。URL Entity 额外使用 `.meta.json` sidecar 存储抓取元数据。

**entity_type 取值（v0.1）**：

```text
document · table · image · audio · video
```

> `document` 包含 pdf/doc/docx/ppt/pptx/md/wps/wpt/dps/dpt/txt 等；`table` 包含 csv/xls/xlsx/et/ett/tsv/parquet/json 等；`image` 包含 jpg/png/gif/webp/bmp/tiff/avif/heic/svg 等（Jina V5 Omni 全量支持）；`audio` 包含 wav/mp3/flac/ogg/m4a/opus 等（Jina V5 Omni 全量支持）；`video` 包含 mp4/avi/mov/mkv/webm/flv/wmv 等（Jina V5 Omni 全量支持）。完整格式清单见 §6.5。

**entity_id 生成规则**：

- `entity_id = UUIDv7`（时间排序，可读性好，避免 hash 碰撞）。
- 目录名即 entity_id，VFS 扫描时直接从目录名解析。
- 同一 raw object 重复上传时，content_hash 检测到相同则复用已有 entity_id。

**URL Entity（source_type=url）**：

> 核心模型：**1 URL = 1 Entity**。URL 是 Entity 的"来源地址"，不是 Entity 本身。抓取后写入 OSS `source/original`，后续 RepPipeline / IndexPipeline 与文件 Entity 完全一致。

- `entity_id_strategy: url_hash`（推荐）：`sha256(url)[:16]`，URL 稳定唯一
- `entity_id_strategy: url_path`：URL path 部分（如 `docs.example.com/api`），可读性强
- `entity_id_strategy: template`：自定义模板（如 `{domain}/{path}`）
- 同 URL 不重复创建：`on_conflict: update`，重复抓取 = 内容更新
- URL 锚点不算不同 Entity：`https://example.com/page#s1` 与 `https://example.com/page` 是同一 Entity（锚点在 chunk 级别处理）

**URL Entity 的 `.meta.json` sidecar**（存于 `{entity_id}/source/.meta.json`）：

```json
{
  "source_type": "url",
  "source_url": "https://docs.example.com/api/v2/auth",
  "fetched_at": "2026-06-06T10:30:00Z",
  "next_poll_at": "2026-06-06T11:30:00Z",
  "http_status": 200,
  "http_etag": "\"abc123\"",
  "http_last_modified": "Fri, 06 Jun 2026 08:00:00 GMT",
  "content_type": "text/html; charset=utf-8",
  "content_length": 45230,
  "fetch_duration_ms": 320
}
```

**文件 Entity vs URL Entity 对比**：

| 维度 | 文件 Entity（source_type=oss） | URL Entity（source_type=url） |
| --- | --- | --- |
| Raw 来源 | 用户上传到 OSS | `fetch_url` RepStep 抓取后写入 OSS |
| `source/original` | 用户原始文件 | URL 响应体 |
| `.meta.json` sidecar | 可选 | **必须**（存 source_url + 抓取元数据） |
| 变更检测 | OSS Event / ETag | Reconciler poll + HTTP ETag / Last-Modified |
| 后续 Pipeline | 完全一致 | 完全一致 |

> Entity 行为接口详见 §5 Pipeline 体系与 §6 搜索与检索。

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
  "pipeline_id": "pipeline_b",                     // ← OSS Tag: pipeline_id
  "transform": "visual_recognize",                  // ← OSS Tag: transform
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
| `recognize/` | L2 | 从 extract 识别/转写 | Pipeline B/C: page_image → vlm_md |
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

> Representation Tag 9 字段详见 §4.6。

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
| canonical_md / vlm_extracted_md | 按标题+段落切 text chunk（ChunkingWithSlidingWindowUseCase） | text |
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

> 映射逻辑：遍历 layout_json 中与 chunk 区间 `[start_pos, end_pos)` 重叠的 blocks，收集 type / level / text / bbox 等字段，组装为 ChunkLayout（含 page_number / page_width / page_height / source_rep / layout_version）。

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
vlm_md ────────┘
               │
               ├─ IndexStep chunk_and_embed_text(canonical_md + layout_json)
               └─ IndexStep chunk_and_embed_text(vlm_md + layout_json)

关键：layout_json 是 Entity 级别的共享 Rep，不随 Rep 类型变化。
所有文本类 Rep（canonical_md / vlm_md）的 chunk
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
  └─③ 切换视角：同一锚点跳转到 vlm_md
      URL: /ws/kb/abc123/vlm_md#q3-pricing
      行为：定位到同一标题锚点（共享 layout_json 保证位置一致）
```

**锚点类型与跳转规则**：

| 锚点类型 | 字段 | 跳转目标 | 适用 Rep |
| --- | --- | --- | --- |
| **Markdown 锚点** | `anchor` (slug) | `canonical_md#q3-pricing` | canonical_md / vlm_md |
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
    "vlm_md": "#q3-pricing",
    "page_image": "?page=7&bbox=72,120,540,144"
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
  "name": "视觉识别",
  "entity_types": ["document"],
  "steps": [
    { "step_id": "render_page", "required_input_reps": ["raw"], "output_reps": ["page_image"] },
    { "step_id": "visual_recognize", "required_input_reps": ["page_image"], "output_reps": ["vlm_md"] }
  ],
  "enabled": true,
  "priority": 2
}
```

> `step_id` 对应 `RepStepRegistry`（§6.7）中的 key；运行期由 `RepPipelineOrchestrator` 通过 `RepStepRegistry.get(step_id)` 解析为具体 RepStep 实例。

**RepPipeline 特征**：
- 每个 step 是一个 `RepStep`（§6.6），实现 `PipelineStep` Protocol
- step 产出 Representation 文件（.md / .json / .png 等），写入 OSS
- step 之间有血缘关系（上游变 → 下游 stale）
- step 可由第三方 Plugin 注入（注册到 `RepStepRegistry`）

**URL Entity 的 RepPipeline**：

> URL Entity 的首个 RepStep 是 `fetch_url`——从 URL 抓取内容写入 `source/original`，后续步骤与文件 Entity 完全一致。

```json
{
  "pipeline_id": "rep_pipeline_url",
  "pipeline_type": "rep",
  "name": "URL 抓取 + 解析",
  "entity_types": ["document", "table", "image"],
  "steps": [
    { "step_id": "fetch_url", "required_input_reps": [], "output_reps": ["source/original"], "config": { "method": "GET", "timeout": "30s", "follow_redirects": true, "max_content_size": "50MB", "render_js": false } },
    { "step_id": "parse", "required_input_reps": ["source/original"], "output_reps": ["canonical_md"] },
    { "step_id": "parse_html", "required_input_reps": ["source/original"], "output_reps": ["canonical_md"], "condition": "content_type == text/html" }
  ],
  "enabled": true
}
```

**`fetch_url` RepStep 行为**：
- **输入**：Entity Tag 中的 `source_url`（从 `.meta.json` 读取）
- **输出**：`source/original`（HTTP 响应体原样写入 OSS）+ `.meta.json` sidecar（抓取元数据）
- **副作用**：更新 Entity Tag（`content_hash` / `entity_type` / `source_type: url` / `source_etag: HTTP ETag`）
- **Content-Type 路由**：根据 HTTP `Content-Type` 设置 `entity_type`（text/html→document, application/pdf→document, image/*→image, application/json→table）
- **变更检测**：Reconciler 对 `source_type=url` 的 Entity 定期 HEAD 请求，检查 ETag / Last-Modified；内容变化时重新执行 `fetch_url`，覆盖 `source/original`，触发下游 Rep 重建

#### 4.5.2 IndexPipeline（索引构建流水线）

```json
{
  "pipeline_id": "index_pipeline_text",
  "pipeline_type": "index",
  "name": "文本索引构建",
  "required_reps": ["canonical_md", "vlm_md"],
  "steps": [
    { "step_id": "chunk_and_embed_text", "required_reps": ["canonical_md", "vlm_md"] },
    { "step_id": "build_vector_index",   "index_type": "semantic" },
    { "step_id": "build_fts_index",      "index_type": "lexical" }
  ],
  "enabled": true
}
```

> `step_id` 对应 `IndexStepRegistry`（§6.8）中的 key；运行期由 `IndexPipelineOrchestrator` 通过 `IndexStepRegistry.get(step_id)` 解析为具体 IndexStep 实例。

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
3. **两套 OSS Object Tagging** — Entity Tag（7个，打在 original 上）+ Representation Tag（9个，打在每个 rep 文件上），作为运行时加速缓存（Tag 可从 Ground Truth 重建）。
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

##### Representation Tag Schema（9 个 Tag，打在 representation 文件上）

| Key | 取值 | 说明 |
| --- | --- | --- |
| `rep_type` | `canonical_md` / `vlm_md` / `page_image` / ... | 认知视角类型 |
| `pipeline_id` | `pipeline_a` / `pipeline_b` / ... | 产出该 rep 的流水线 |
| `transform` | `parse` / `visual_recognize` / `llm_compile` / `render` | 具体变换方法 |
| `modality` | `text` / `image` / `audio` / `table` | 模态 |
| `status` | `ready` / `stale` / `failed` / `deleted` | representation 状态 |
| `model_version` | `paddleocr_v3` / `qwen2vl_v3` / ... | 产出该 rep 的模型版本 |
| `entity_version` | `3` | 所属 Entity 版本 |
| `input_content_hash` | `sha256:abc...` | 直接上游 Rep 的 content_hash（见 §5.13.1） |
| `content_hash` | `sha256:def...` | 本 Rep 文件内容的 SHA-256 |

> 9/10 Tag 位已用，预留 1 个给 v0.2。`input_content_hash` 和 `content_hash` 是 Rep 继承链的关键字段（§5.13.1）。

**示例**：

```text
oss://bucket/vector-lake/ws_001/kb_001/abc123/recognize/vlm_extracted.md
  x-oss-tagging:
    rep_type=vlm_md
    pipeline_id=pipeline_b
    transform=visual_recognize
    modality=text
    status=ready
    model_version=qwen2vl_v3
    entity_version=3
    input_content_hash=sha256:page_image_hash
    content_hash=sha256:vlm_md_hash

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

| 维度 | OSS Tag (9个/rep文件) | Sidecar .meta.json |
| --- | --- | --- |
| **文件数量** | 0 额外文件 | +N 个/Entity（80% 膨胀） |
| **写入成本** | PutObjectTagging（不重写对象） | PutObject 小文件 |
| **孤儿检测** | Tag 始终与对象绑定，删除对象 Tag 自动消失 | 需额外检测逻辑 |
| **工具可见性** | OSS 控制台直接看 Tag | 需自定义工具 |
| **Schema 灵活性** | 固定 9 字段，128B/value | 任意 JSON |
| **Evolution** | 预留 1 个 Tag 空位 | JSON 加字段无限制 |

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
- **v0.1 限制**：每个 Entity 最多 5 个 Index（text / image / video / structural / [graph v0.2]），metadata 大小可控
- **v0.2 迁移**：Index metadata 迁移到 `_manifest/indexes.jsonl`

#### `representations.lance`（Entity 目录内，核心检索表）

每行 = 一个可检索单元。一个 `canonical_md` representation 切成 50 行，每行有自己的 text + vector。`chunk_index` 区分同一 representation 的不同切分段。

##### representations.lance 字段定义

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `entity_id` | utf8 | ✓ | 所属 Entity |
| `rep_type` | utf8 | ✓ | 认知视角类型（canonical_md / vlm_md / …） |
| `chunk_index` | int32 | ✓ | 同一 rep 的切分序号 |
| `entity_version` | int32 | ✓ | 冗余加速（权威值在 OSS Tag） |
| `pipeline_id` | utf8 | ✓ | 产出流水线 |
| `transform` | utf8 | ✓ | parse / ocr / vlm / llm_compile |
| `modality` | utf8 | ✓ | text / image / audio / table |
| `model_version` | utf8 | | 产出该 rep 的模型版本 |
| `text` | utf8 | ✓ | 原文（建 FTS 索引） |
| `embedding_text` | utf8 | | 向量化文本（可能与 text 不同） |
| `start_pos` | int32 | ✓ | 在 rep 中的字符偏移 |
| `end_pos` | int32 | ✓ | 在 rep 中的字符结束偏移 |
| `token_count` | int32 | ✓ | token 数 |
| `chunk_chars` | int32 | ✓ | 字符数 |
| `page_number` | int32 | | 页码 |
| `section_header` | utf8 | | 章节标题 |
| `section_level` | int32 | | 章节层级 |
| `anchor` | utf8 | | 锚点（HTML/PDF） |
| `doc_title` | utf8 | | 文档标题 |
| `image_uri` | utf8 | | 图片 OSS URI（modality=image） |
| `audio_uri` | utf8 | | 音频 OSS URI（modality=audio） |
| `table_data` | utf8 | | 表格 JSON（modality=table） |
| `vector` | fixed_size_list\<float, 1024\> | ✓ | Jina V5 向量 |
| `status` | utf8 | ✓ | active / stale / hidden / deleted |
| `content_hash` | utf8 | | chunk 内容的 SHA-256 |
| `created_at` | timestamp(us, UTC) | ✓ | 创建时间 |
| `updated_at` | timestamp(us, UTC) | ✓ | 更新时间 |

> 主键约束（Lance 不强制，应用层保证）：PRIMARY KEY = (entity_id, rep_type, chunk_index)

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

> 三类索引：(1) 向量索引 `IVF_HNSW_SQ`（cosine 度量，Jina V5 推荐）；(2) 全文检索索引 BM25（`text` 列，支持中英文）；(3) 标量索引（`status` / `rep_type` / `modality` / `entity_version` 列，过滤加速）。

**索引选择策略**：

| 行数 | 向量索引 | num_partitions | 说明 |
| --- | --- | --- | --- |
| < 10K | 不建索引（暴力搜索） | - | Lance 自动全量扫描，延迟 < 50ms |
| 10K - 100K | `IVF_HNSW_SQ` | 32 | 小规模，SQ 量化足够 |
| 100K - 1M | `IVF_HNSW_SQ` | 256 | 中等规模，推荐默认配置 |
| > 1M | `IVF_HNSW_PQ` | 1024 | 大规模，PQ 压缩节省内存 |

> v0.1 每个 Entity 的 Lance 表通常 < 10K 行（1个文档 × 5个rep × 50个chunk = 250行），不需要建向量索引，暴力搜索即可。索引在跨 Entity 汇聚查询时才需要。

##### 查询模式

| 模式 | 说明 | 典型过滤条件 |
| --- | --- | --- |
| 语义检索 | 向量搜索 | `status='active'`, `modality='text'` |
| 全文检索 | BM25 关键词匹配 | `status='active'` |
| 混合检索 | 语义 + BM25 + RRF 重排 | `status='active'` |
| 按 Rep 过滤 | 限定 `rep_type` | `rep_type='vlm_md'` |
| 按变换方法过滤 | 限定 `transform` | `transform='parse'` |
| 按页码定位 | 限定 `page_number` | `page_number=3` |
| 多模态检索 | 跨模态同一向量空间 | `modality IN ('text','image')` |

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
   ├─ Pipeline B: input=page_image, output=[vlm_md]
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
        └─► recognize/vlm_extracted_md (L2, Pipeline B: visual_recognize)
```

**目录层级带来的推导加速**：

| 推导需求 | 仅用目录层级 | + Pipeline 注册表 |
| --- | --- | --- |
| "vlm_md 的上游在哪？" | 一定是 `extract/` 下 → 缩小搜索范围 | `page_image`（Pipeline B 声明） |
| "raw 变了，影响谁？" | `extract/` + `recognize/` + `compile/` 全部 | 精确到具体 rep_type |
| "新增 recognize/xxx.md" | 上游一定是 `extract/` 下 | 查 Pipeline 注册表确定具体哪个 |

**推导实现要点**：

> 目录层级 → 血缘深度映射：source=L0, extract=L1, recognize=L2, compile=L3。按层级扫描 Entity 目录获取 existing_reps，再遍历 Pipeline 注册表匹配 input_rep → output_reps 边，构建血缘 DAG。rep_type 推导优先匹配路径约定表，fallback 到 OSS Tag。

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
| **跨 rep_type merge** | Pipeline 声明 `input_reps: [canonical_md, vlm_md]`（多上游） |
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

> Lance manifest metadata 记录已同步的 Parquet 文件列表，只同步新文件，重复触发不会重复写入。

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

> Rebuild 前记录当前 Lance version 快照；重建成功则更新 OSS Tag sync_state=ready；失败则回滚到快照 version 并标记 sync_state=failed。

**Rebuild vs Incremental Sync 选择策略**：

> 自动选择逻辑：碎片率过高（avg < 500 行/fragment）→ rebuild；累计增量 > 20 次 → rebuild；索引退化 → rebuild；否则 → incremental。

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

> 扫描 staging/ 目录，对比 Lance manifest metadata 中已同步文件列表，计算变更集（新增 / 删除 / 替换 Parquet）。同时检测 raw content_hash 变化（触发 full_rebuild）和 Rep OSS Tag status 变化。

**Stage 2：Lock（防止并发同步）**

> 原子获取同步锁：检查 OSS Tag sync_state，若为 syncing/rebuilding 则拒绝；通过 CopyObject + x-oss-copy-source-if-match 实现 CAS 更新 sync_state。超时 300s 强制解锁。

**Stage 3：Transform（Parquet → Lance）**

> 读取新增 staging Parquet，Schema 对齐 + 类型转换（list\<float\> → fixed_size_list\<float\>），按 (entity_id, rep_type, chunk_index) 去重，追加写入 Lance。

**Stage 4：Delete（处理删除）**

> Lance schema 不存 source_parquet 字段，用 manifest metadata 记录"Parquet → 行 ID 范围"映射。删除时按范围做 Lance deletion，并更新 manifest metadata。

**Stage 5：Index（建/更新索引）**

> Lance 写入后建/更新三类索引：向量索引 IVF_HNSW_SQ（cosine）、FTS 索引（text 列）、标量索引（status / rep_type / modality）。已有索引则增量优化。

**Stage 6：Compact（碎片整理，自动触发）**

> 碎片率过高时（平均每个 fragment < 500 行）自动触发 compact，合并 fragment 并物理重写。

**Stage 7：Atomic Switch（原子切换）**

> Lance 原生 MVCC 原子切换：commit 新 version → 更新 manifest metadata（记录已同步 Parquet + last_sync_at）→ 更新 OSS Tag sync_state=ready → 旧 version 保留 5 个（回滚窗口）。

**Stage 8：Cleanup（清理 staging）**

> 已同步的 staging Parquet 保留最近 1 个版本（debug 用），删除更早版本。

##### 失败处理

| 失败点 | 检测 | 恢复策略 |
| --- | --- | --- |
| **网络中断（Stage 3-5）** | sync timeout | OSS Tag 标 `failed`；下次 reconcile 重新检测 |
| **Lance 写入失败** | Lance 抛异常 | 回滚 OSS Tag 到 `failed`；不更新 `sync_version` |
| **OSS Tag 写入失败（Stage 7）** | API 抛异常 | Lance 已更新但 tag 未更新 → 标记 `sync_state=stale`；reconcile 时对比 Lance version 和 OSS Tag version 修复 |
| **实体被删除（中间态）** | 扫不到 original | 触发 Entity 软删除流程；清理 Lance |
| **Rebuild 失败** | 验证不通过 | 回滚到 snapshot_version；OSS Tag 标 `failed` |

**幂等性保证**：

> 同一变更多次同步结果一致。实现：(1) Lance manifest metadata 记录已同步 Parquet 文件列表；(2) 重复 append 触发 dedupe（主键去重）；(3) 重复 delete 幂等（Lance deletion vector 重复标记无副作用）。

**断点续传**：

> sync 失败后，从 OSS Tag sync_error 记录的失败 stage 恢复继续。

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
| `GET /lineage/{entity_id}?direction=upstream&rep_type=vlm_md` | 从 vlm_md 向上追溯到 raw（辅助能力） |
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
| raw object `content_hash` 变化 | entity.version++；沿 Rep 继承链（§5.13.2）向下级联：所有下游 Rep 文件 OSS Tag `status`→`stale`；按拓扑排序触发 RepPipeline 重建 |
| 上游 Rep `content_hash` 变化 | 沿 Rep 继承链（§5.13.2）向下级联：直接下游 Rep `status`→`stale`；继续级联直到叶子节点；按拓扑排序触发 RepPipeline 重建 |
| Rep OSS Tag `status`→`ready` | 触发增量 Index 评估（§5.13.3）；若所有 Rep ready → 触发 `rep_all_ready` 事件 → 全量 Index 一致性校验 |
| Rep OSS Tag `status`→`stale` | 沿 Rep 继承链（§5.13.2）向下级联：下游 Rep `status`→`stale`；触发下游 RepPipeline 重建 |
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

**校验内容**：每个 Rep 文件的内容是否与它声明的**直接上游 Rep** 的 `content_hash` 一致（通过 `input_content_hash` Tag 追踪）。

```text
Reconciler 周期任务（每 15 min）— Rep 阶段
  ├─ 扫描所有 Rep 文件的 Representation Tag
  ├─ 对比 Rep Tag 的 input_content_hash vs 直接上游 Rep 的 content_hash
  │   ├─ pipeline_a (parse): 上游 = raw → input_content_hash 应 == raw.content_hash
  │   ├─ pipeline_b (visual_recognize): 上游 = page_image → input_content_hash 应 == page_image.content_hash
  │   └─ pipeline_d (compile_*): 上游 = canonical_md → input_content_hash 应 == canonical_md.content_hash
  ├─ 不匹配 → 标 Rep stale → 触发 RepPipeline 重建
  ├─ 检查 Rep 文件是否存在（OSS 404 → 标 failed）
  └─ 检查 Rep 文件的 body_hash vs Tag 中的 content_hash（防篡改/损坏）
```

**校验场景**：

| 场景 | 检测方式 | 修复 |
|---|---|---|
| Raw 更新但 Rep 未重建 | `input_content_hash` 不匹配（A 类 Rep: input=raw） | 标 stale → RepPipeline 重建 |
| 上游 Rep 更新但下游 Rep 未重建 | `input_content_hash` 不匹配（D 类 Rep: input=canonical_md） | 标 stale → RepPipeline 重建（§5.13.2 级联） |
| Rep 文件损坏/丢失 | OSS 404 或 `body_hash` 不匹配 | 标 failed → RepPipeline 重建 |
| RepPipeline 升级后旧 Rep 过时 | `pipeline_version` Tag 不匹配 | 标 stale → RepPipeline 重建 |
| Rep 被意外删除 | OSS 404 | 标 deleted → RepPipeline 重建（如果上游 Rep 仍在） |

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

#### 5.9.4 Phase 3：Projector 一致性校验

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
  "ready_reps": ["canonical_md", "vlm_md"],
  "failed_reps": [],
  "skipped_reps": [],
  "rep_content_hashes": {
    "canonical_md": "sha256:abc...",
    "vlm_md": "sha256:def..."
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

#### 5.12.9 成熟项目参照与演进路线

> v0.1 采用 sidecar 持久化 + Reconciler 兜底方案；以下为 v0.2/v0.3 演进参照。

| 演进方向 | 参照项目 | 核心思路 | 目标版本 |
| --- | --- | --- | --- |
| 事务日志 + 原子指针交换 | Delta Lake / Iceberg | 每次写入生成 commit 文件（JSON），原子交换 manifest 指针；读路径只解析最新指针 | v0.2 |
| Merkle 树血缘 | lakeFS Graveler | MetaRange → Range → Record 三层 Merkle，任意层级内容变更向上传播根哈希 | v0.3 |
| 三层元数据架构 | Iceberg Manifest List | Manifest List → Manifest → Data File 三层，支持分区裁剪 + 文件级统计 | v0.2 |
| MVCC + 不可变 Manifest | Lance spec | 每个 version 是不可变 Manifest（JSON），指向一组不可变 Data Fragment；快照隔离 | v0.2 |
| Schema Evolution | Iceberg / Avro | 字段 ID 永久绑定 + 映射层（field_id → column_name），支持加列/删列/改名/改类型 | v0.3 |

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


### 5.13 Rep 继承链与级联传播（Rep Inheritance & Cascade）

> **核心问题**：Rep 之间有继承关系——一个 Rep 可能基于另一个 Rep 生成（如 `mind_map` 基于 `canonical_md`）。当上游 Rep 变化时，必须沿继承链级联传播，确保所有下游 Rep 和 Index 最终一致。

#### 5.13.1 Rep 继承链定义

每个 Rep 通过 `input_content_hash` Tag 记录其**直接上游 Rep** 的内容指纹，形成一条可追溯的继承链：

```text
继承链示例（Entity: pricing-2025.pdf）

raw (content_hash=sha256:aaa)
  │
  ├─ pipeline_a: parse
  │   └─ canonical_md (input_content_hash=sha256:aaa, content_hash=sha256:bbb)
  │       │
  │       ├─ pipeline_d: compile_mind_map
  │       │   └─ mind_map (input_content_hash=sha256:bbb, content_hash=sha256:ccc)
  │       │
  │       ├─ pipeline_d: compile_summary
  │       │   └─ summary (input_content_hash=sha256:bbb, content_hash=sha256:ddd)
  │       │
  │       └─ pipeline_d: compile_wiki_md
  │           └─ wiki_md (input_content_hash=sha256:bbb, content_hash=sha256:eee)
  │
  └─ pipeline_b: render_page → visual_recognize
      ├─ page_image (input_content_hash=sha256:aaa, content_hash=sha256:fff)
      ├─ vlm_md (input_content_hash=sha256:fff, content_hash=sha256:hhh)
```

**`input_content_hash` 的语义**：

| Rep 类型 | 直接上游 | `input_content_hash` 取值 |
| --- | --- | --- |
| `canonical_md` (pipeline_a) | raw | `raw.content_hash` |
| `page_image` (pipeline_b) | raw | `raw.content_hash` |
| `vlm_md` (pipeline_b) | page_image | `page_image.content_hash` |
| `mind_map` (pipeline_d) | canonical_md | `canonical_md.content_hash` |
| `summary` (pipeline_d) | canonical_md | `canonical_md.content_hash` |
| `wiki_md` (pipeline_d) | canonical_md | `canonical_md.content_hash` |
| `transcript` (pipeline_f) | raw | `raw.content_hash` |
| `table_parquet` (pipeline_g) | raw | `raw.content_hash` |

> **关键**：`input_content_hash` 记录的是**直接上游**，不是 raw。这样 Reconciler 可以精确检测任意层级的 Rep 漂移。

#### 5.13.2 Rep 变动级联传播

当任意 Rep 的 `content_hash` 发生变化时，沿继承链**向下级联**标记所有下游 Rep 为 stale：

```text
场景：raw 更新（content_hash: sha256:aaa → sha256:aaa'）

Step 1: 检测 raw 变化
  raw.content_hash 变化 → entity.version++

Step 2: 级联标记（沿继承链向下遍历）
  canonical_md: input_content_hash=sha256:aaa ≠ raw.content_hash=sha256:aaa' → stale
  page_image:   input_content_hash=sha256:aaa ≠ raw.content_hash=sha256:aaa' → stale

Step 3: 二级级联（canonical_md 变 stale → 下游也 stale）
  mind_map:  input_content_hash=sha256:bbb ≠ canonical_md.content_hash (stale) → stale
  summary:   input_content_hash=sha256:bbb ≠ canonical_md.content_hash (stale) → stale
  wiki_md:   input_content_hash=sha256:bbb ≠ canonical_md.content_hash (stale) → stale

Step 4: 二级级联（page_image 变 stale → 下游也 stale）
  vlm_md:     input_content_hash=sha256:fff ≠ page_image.content_hash (stale) → stale

Step 5: 触发重建（按拓扑排序）
  1. 先重建 pipeline_a (canonical_md) + pipeline_b (page_image)  ← 可并行
  2. canonical_md ready → 重建 pipeline_d (mind_map/summary/wiki_md)
  3. page_image ready → 重建 pipeline_b (vlm_md)
  4. 所有 Rep ready → rep_all_ready → IndexPipeline 评估重建
```

**级联算法**：

```python
def cascade_invalidate(entity_id: str, changed_rep_type: str):
    """从变更的 Rep 开始，沿继承链向下级联标记 stale。"""
    # 1. 从 Pipeline 注册表构建继承图
    #    edge: (upstream_rep_type) → (downstream_rep_type)
    inheritance_graph = build_inheritance_graph(entity_id)

    # 2. BFS 遍历下游
    queue = [changed_rep_type]
    while queue:
        current = queue.pop(0)
        downstream_reps = inheritance_graph.get_downstream(current)
        for ds_rep in downstream_reps:
            # 标记 stale
            update_rep_tag(entity_id, ds_rep, status="stale")
            # 继续向下级联
            queue.append(ds_rep)

    # 3. 触发重建（按拓扑排序，保证上游先完成）
    rebuild_order = topological_sort(stale_reps)
    for rep_type in rebuild_order:
        pipeline_id = get_pipeline_for_rep(rep_type)
        trigger_rebuild(entity_id, pipeline_id)
```

#### 5.13.3 Index 增量重建（基于继承链优化）

当前设计：Index 重建依赖 `rep_all_ready` 事件，**所有 Rep 收敛后才触发**。但这可能导致不必要的等待。

**优化策略**：IndexPipeline 按 `required_reps` 独立触发，不等全部 Rep ready：

```text
场景：canonical_md 变了，但 vlm_md 没变

旧逻辑（全量等待）：
  canonical_md stale → 等待所有 Rep ready → rep_all_ready → 重建所有 Index

新逻辑（增量触发）：
  canonical_md ready → 立即评估依赖 canonical_md 的 Index：
    ├─ index_pipeline_text (required: canonical_md) → canonical_md ready → 立即重建
    └─ index_pipeline_image (required: page_image) → page_image 未变 → 不重建

  vlm_md ready → 评估依赖 vlm_md 的 Index：
    └─ index_pipeline_text (required: canonical_md, optional: vlm_md) → 已基于新 canonical_md 重建 → 跳过
```

**Index 增量重建规则**：

| 条件 | 动作 |
| --- | --- |
| Index 的 `required_reps` 中有任一 stale | 等待，不重建 |
| Index 的 `required_reps` 全部 ready，`optional_reps` 有 stale | 可重建（跳过 optional 输入），但标记 `partial` |
| Index 的 `required_reps` + `optional_reps` 全部 ready | 完整重建 |
| Index 的 `index_built_from_hash` == 当前 Rep 的 `content_hash` 并集 | 跳过（已一致） |

**`rep_all_ready` 事件保留但语义调整**：

```text
旧语义：所有 Rep ready → 触发 Index 评估
新语义：所有 Rep ready → 触发"全量 Index 一致性校验"（兜底）
        单个 Rep ready → 触发"增量 Index 评估"（即时）
```

> v0.1 实现建议：先实现全量等待（简单可靠），v0.2 切换到增量触发。

#### 5.13.4 Rep 继承链的可观测性

| 查询 | API | 说明 |
| --- | --- | --- |
| 查看 Rep 的直接上游 | `GET /entities/{id}/reps/{rep_type}/upstream` | 返回 input_content_hash 对应的上游 Rep |
| 查看 Rep 的所有下游 | `GET /entities/{id}/reps/{rep_type}/downstream` | 返回继承链中所有依赖该 Rep 的下游 Rep |
| 查看完整继承图 | `GET /entities/{id}/inheritance-graph` | 返回 DAG 形式的继承关系图 |
| 模拟级联影响 | `POST /entities/{id}/reps/{rep_type}/cascade-preview` | 预览"如果该 Rep 变更，哪些下游会 stale" |

#### 5.13.5 继承链与血缘的区别

| 维度 | 继承链（Inheritance） | 血缘（Lineage） |
| --- | --- | --- |
| **定义** | Rep 之间的直接依赖关系（谁是谁的输入） | Entity 之间的关系（谁引用了谁） |
| **粒度** | Rep 级（同一 Entity 内） | Entity 级（跨 Entity） |
| **存储** | `input_content_hash` Tag + Pipeline 注册表 | 目录层级 + Pipeline 注册表 |
| **用途** | 变动检测 + 级联传播 + Index 增量重建 | 影响分析 + 数据溯源 + 跨 Entity 检索 |
| **方向** | 自上而下（上游→下游） | 双向（上游/下游） |

### 5.14 完整变动管理（Change Management）

> **目标**：把所有"变动"相关的设计集中在一个章节，覆盖检测、分类、追踪、通知、回滚、冲突、回放、批量、跨 Entity、投影端 10 个维度。

#### 5.14.1 变动检测（Detection）

**5 个检测源**：

| 检测源 | 信号 | 触发组件 | 延迟 | 可靠性 |
| --- | --- | --- | --- | --- |
| **OSS 事件通知** | S3 EventNotification / OSS MNS（ObjectCreated/Removed/Updated） | VFS Listener | < 1s | 中（可能丢失） |
| **Reconciler 周期扫描** | 主动 LIST 目录 + ETag 比对 | Reconciler | 15min | 高（兜底） |
| **API 写入** | 用户显式 PUT/DELETE/POST | API Server | 即时 | 高 |
| **Reconciler Phase 0** | 主动 HeadObject 取 ETag | Reconciler | 15min | 高（兜底） |
| **Edge 变动** | Edge API 主动触发 | API Server | 即时 | 高 |

> **v0.1 设计**：API 写入即主路径，OSS 事件作为加速（v0.2），Reconciler 作为兜底（v0.1 全程开启）。

#### 5.14.2 变动分类（Classification）

按 scope 划分 **7 类变动**，每类有独立的处理流程：

| 类别 | 检测信号 | 影响范围 | 处理流程 | 可回滚 |
| --- | --- | --- | --- | --- |
| **C1. Raw 变动** | `raw.content_hash` 变化 | 整个 Entity 所有下游 Rep + Index | 沿 Rep 继承链级联（§5.13.2） | ✅（保留旧 raw） |
| **C2. Rep 内容变动** | `rep.content_hash` 变化 | 下游 Rep + 依赖该 Rep 的 Index | 沿继承链级联 + Index 增量重建 | ✅（保留旧 Rep） |
| **C3. Rep 状态变动** | `rep.status` 变化（ready/stale/failed/deleted） | Index 评估 + Edge 评估 | 触发 Index 评估（§5.13.3） | ✅（状态机可回退） |
| **C4. Index 变动** | `index_status` 变化 / Index 重建 | 不影响其他 Index | 触发 IndexPipeline 重建 | ✅（保留旧 Index） |
| **C5. Schema 变动** | Pipeline 升级 / 模型升级 / 字段新增 | 受影响 Entity 全量 | 触发对应 Rep / Index 全量重建 | ⚠️（需 migration） |
| **C6. Entity 元数据变动** | labels / rag_status / version | 该 Entity 的可见性 + 检索过滤 | 更新 Entity Tag + 触发 Projector 同步 | ✅ |
| **C7. Projector 配置变动** | protect_user_edits / output_dir 变更 | 投影目标 | 触发 ProjectorStep rebuild() | ✅ |

#### 5.14.3 变动追踪（Tracking）

> v0.2 待展开。核心思路：基于 L1 version_log 和 L2 _log 实现变动事件的有序记录与查询。

#### 5.14.4 变动通知（Notification）

> v0.2 待展开。核心思路：变动事件通过 Redis Streams 推送给 Reconciler/Worker/Projector 等订阅方。

#### 5.14.5 变动回滚（Rollback）

**回滚策略**：

| 类别 | 回滚方式 | 保留期 | 触发方式 |
| --- | --- | --- | --- |
| **Raw** | 软删除新 raw，恢复旧 raw 版本 | 30 天（与 soft_delete 策略一致） | API `restore_raw(entity_id, version)` |
| **Rep** | 标记新 Rep 为 `superseded`，重新激活旧 Rep | 30 天 | API `restore_rep(entity_id, rep_type, version)` |
| **Index** | Lance dataset 版本切换（Lance 原生支持） | 30 天 | API `restore_index(entity_id, index_type, version)` |
| **Entity 元数据** | 读 `.version_log.jsonl` 反向回放 | 永久（append-only） | API `restore_entity(entity_id, version)` |
| **Projector** | 重新触发 `rebuild()` 从旧 Rep | 跟随 Rep 保留期 | API `restore_projector(...)` |

**回滚的不变量**：
- **不删除历史**：所有版本始终可访问（受保留期限制）
- **不破坏外引用**：被引用对象先恢复，再恢复引用者
- **不绕过 Reconciler**：回滚后 Reconciler 自动重新校验一致性

#### 5.14.6 变动冲突（Conflict）

> v0.2 待展开。核心思路：多写冲突场景（同 Entity 并发、跨 Entity 级联）的检测与解决策略。

#### 5.14.7 变动回放（Replay / Time Travel）

> v0.2 待展开。核心思路：基于 version_log 的 Time Travel 查询，支持回溯到任意历史版本。

#### 5.14.8 批量变动（Batch Operations）

> v0.2 待展开。核心思路：批量 Entity 的变动检测、分类与处理优化。

#### 5.14.9 跨 Entity 变动（Cross-Entity Change）

> v0.2 待展开。核心思路：Edge 级联变动（如 graph_json 中 cites 关系变更）的传播机制。

#### 5.14.10 投影端变动（Projector Sync）

**Projector 如何响应 Lake 变动**：

```text
Lake 变动（C1-C6 任意类别）
  │
  ▼
Projector Listener（订阅 Redis Streams change_detected 事件）
  │
  ├─ 1. 评估：变动是否影响该 Projector 的目标输出？
  │     └─ 例：WikiProjector 只关心 content 类 Rep，不关心 raw 字节变化
  │
  ├─ 2. 计算差异（diff）：本次产出 vs 旧产出的差异
  │     └─ 例：WikiProjector 重新生成某个 .md 文件
  │
  ├─ 3. 应用差异到目标
  │     ├─ protect_user_edits=true → 3-way merge（保留用户编辑）
  │     └─ protect_user_edits=false → 直接覆盖
  │
  └─ 4. 记录同步历史（Projector 目录 .meta.json）
        └─ last_sync, last_input_hash, output_version
```

**Projector 同步模式**：

| 模式 | 触发时机 | 适用场景 | 代价 |
| --- | --- | --- | --- |
| **Realtime** | Lake 变动 → 立即同步 | 交互式 Wiki / Dashboard | 高（频繁） |
| **Batch** | 周期同步（每 5 min） | 离线 Dashboard / 静态 RAG | 低 |
| **On-demand** | 用户显式触发 | 调试 / 一次性导出 | 最低 |

#### 5.14.11 变动 SLA 与可观测性

> v0.2 待展开。核心思路：变动检测延迟、传播延迟、重建完成时间等 SLA 指标与告警。

### 5.15 Watch Mode（自动构建模式）

> **核心承诺**：用户只需在**指定目录**上传文件，系统**自动感知**并**自动构建**索引——无需调用任何 API。
>
> 这是与"显式 API 调用"并列的第二种数据接入范式，**大幅降低接入门槛**，让用户像使用 Dropbox/网盘一样使用 Vector-Lake。

#### 5.15.1 启用与配置

> **核心设计**：监听策略（Watch Strategy）和接入策略（Ingest Strategy）**解耦**。监听只管"检测 prefix 下的文件变动"，接入策略管"文件怎么变成 Entity"。一个监听策略可绑定不同的接入策略，一个接入策略也可被多个监听策略复用。

**配置示例**（`config.yaml`）：

```yaml
vector_lake:
  watch_mode:
    enabled: true

    # ============================================================
    # 接入策略（Ingest Strategy）—— 定义"文件如何变成 Entity"
    # ============================================================
    ingest_strategies:
      # 策略 1：标准文档接入
      standard_doc:
        entity_id_strategy: filename         # filename | filepath | uuid | hash | template
        inherit_labels_from: collection      # collection | prefix_path | none
        default_labels:
          source: auto-watch
          ingestion: auto
        allowed_extensions: [".pdf", ".md", ".docx", ".pptx", ".txt"]
        max_file_size_mb: 500
        auto_create_entity: true             # 新文件自动创建 Entity
        on_conflict: update                  # update | skip | error（同 entity_id 已存在时）

      # 策略 2：WPS 文档接入
      wps_doc:
        entity_id_strategy: filename
        inherit_labels_from: collection
        default_labels:
          source: auto-watch
          ingestion: auto
          format: wps
        allowed_extensions: [".wps", ".wpt", ".dps", ".dpt", ".et", ".ett"]
        max_file_size_mb: 500
        auto_create_entity: true
        on_conflict: update

      # 策略 3：多媒体接入
      multimedia:
        entity_id_strategy: uuid             # 多媒体文件名可能重复，用 uuid
        inherit_labels_from: prefix_path     # 从路径继承（如 incoming/audio/ → label: audio）
        default_labels:
          source: auto-watch
          ingestion: auto
        allowed_extensions: [".jpg", ".png", ".mp3", ".wav", ".mp4", ".mkv"]
        max_file_size_mb: 2000               # 多媒体文件更大
        auto_create_entity: true
        on_conflict: skip                    # 多媒体用 uuid 不会冲突

      # 策略 4：表格数据接入
      tabular:
        entity_id_strategy: filepath         # 路径含版本信息
        inherit_labels_from: prefix_path
        default_labels:
          source: auto-watch
          ingestion: auto
          format: tabular
        allowed_extensions: [".csv", ".xlsx", ".xls", ".parquet", ".json"]
        max_file_size_mb: 1000
        auto_create_entity: true
        on_conflict: update

      # 策略 5：URL 爬取接入
      web_crawl:
        description: "URL 爬取接入"
        source_type: url
        entity_id_strategy: url_hash
        allowed_content_types:
          - text/html
          - application/pdf
          - text/markdown
          - text/plain
          - application/json
        max_content_size: 50MB
        on_conflict: update
        crawl_config:
          method: GET
          timeout: 30s
          follow_redirects: true
          render_js: false              # v0.2: headless browser
          auth:
            type: bearer                # bearer / basic / api_key（v0.2: oauth2）
            token_secret: vault:web_crawl_token
        poll_config:
          change_detection: etag        # etag / last_modified / content_hash
          poll_interval: 1h
          max_retries: 3
          retry_backoff: exponential

    # ============================================================
    # 监听策略（Watch Strategy）—— 定义"监听哪个 prefix"
    # ============================================================
    watch_strategies:
      # 监听 1：生产环境 OSS 前缀
      - strategy_id: prod-incoming
        type: oss                            # oss | local | reconciler
        workspace: my-workspace
        collection: knowledge-base
        prefix: incoming/                    # 监听这个前缀
        recursive: true                      # 递归监听子目录
        ingest_strategy: standard_doc        # ← 绑定接入策略
        require_stable_seconds: 30           # 文件稳定期（防半上传）
        max_concurrent_ingest: 10            # 并发限流

      # 监听 2：WPS 文件专用前缀
      - strategy_id: prod-wps
        type: oss
        workspace: my-workspace
        collection: knowledge-base
        prefix: incoming-wps/
        recursive: true
        ingest_strategy: wps_doc             # ← 绑定不同的接入策略
        require_stable_seconds: 30
        max_concurrent_ingest: 5

      # 监听 3：多媒体前缀
      - strategy_id: prod-media
        type: oss
        workspace: my-workspace
        collection: media-base
        prefix: media-incoming/
        recursive: true
        ingest_strategy: multimedia          # ← 绑定多媒体接入策略
        require_stable_seconds: 60           # 大文件需更长稳定期
        max_concurrent_ingest: 3

      # 监听 4：本地开发目录
      - strategy_id: dev-local
        type: local
        workspace: dev-workspace
        collection: local-inbox
        watch_dir: /data/inbox/
        poll_interval: 5                     # 周期扫描间隔（秒）
        ingest_strategy: standard_doc        # ← 复用同一接入策略

      # 监听 5：表格数据前缀
      - strategy_id: prod-tabular
        type: oss
        workspace: my-workspace
        collection: data-base
        prefix: data-incoming/
        recursive: true
        ingest_strategy: tabular
        require_stable_seconds: 10

    # === 兜底（任何场景都建议开启）===
    reconciler_fallback:
      enabled: true
      scan_interval: 900           # 15min 一次全量扫描（兜底）
      verify_entity_count: true   # 对比 OSS 实际文件数与 Entity 数
```

**解耦关系图**：

```text
Watch Strategy（监听策略）          Ingest Strategy（接入策略）
┌──────────────────────┐           ┌──────────────────────┐
│ prod-incoming        │──────────▶│ standard_doc         │
│ (prefix: incoming/)  │           │ (filename, .pdf/.md) │
└──────────────────────┘           └──────────────────────┘
┌──────────────────────┐           ┌──────────────────────┐
│ prod-wps             │──────────▶│ wps_doc              │
│ (prefix: incoming-wps/)│          │ (filename, .wps/.et) │
└──────────────────────┘           └──────────────────────┘
┌──────────────────────┐           ┌──────────────────────┐
│ prod-media           │──────────▶│ multimedia           │
│ (prefix: media-incoming/)│        │ (uuid, .mp4/.png)    │
└──────────────────────┘           └──────────────────────┘
┌──────────────────────┐           ┌──────────────────────┐
│ dev-local            │──────────▶│ standard_doc         │ ← 复用
│ (dir: /data/inbox/)  │           │ (filename, .pdf/.md) │
└──────────────────────┘           └──────────────────────┘
┌──────────────────────┐           ┌──────────────────────┐
│ prod-tabular         │──────────▶│ tabular              │
│ (prefix: data-incoming/)│         │ (filepath, .csv/.xlsx)│
└──────────────────────┘           └──────────────────────┘

关键：多个 Watch Strategy 可绑定同一 Ingest Strategy（复用）
     一个 Watch Strategy 只绑定一个 Ingest Strategy（明确）
```

**3 种监听源**：

| 类型 | 适用场景 | 延迟 | 可靠性 | 配置 |
| --- | --- | --- | --- | --- |
| **OSS 事件** | 生产环境（云端） | < 1s | 中（事件可能丢失） | `type: oss` |
| **本地 inotify / FSEvents** | 开发/边缘节点 | < 1s | 中（重启后丢失） | `type: local` |
| **Reconciler 周期扫描** | 兜底（任何场景） | 15min | 高 | `reconciler_fallback` |

#### 5.15.2 自动构建流程

```text
用户上传文件到 incoming/ 目录
  │
  ▼
[1] Watch Strategy 检测到新文件（OSS 事件 / inotify / Reconciler 扫描）
  │
  ▼
[2] Watch Strategy 匹配配置（prefix → strategy_id → ingest_strategy）
  ├─ 确定文件属于哪个 Watch Strategy（按 prefix 匹配）
  ├─ 查找绑定的 Ingest Strategy
  └─ 文件过滤（extension / size / 稳定期）
  │
  ▼
[3] Ingest Strategy 决定如何创建 Entity
  ├─ 应用 entity_id_strategy → 生成 entity_id
  ├─ 继承元数据（labels / collection default tags）
  ├─ 应用 on_conflict 策略（update / skip / error）
  └─ 写入 raw 对象 + Entity Tag + .entity_manifest.json
  │
  ▼
[4] 投递消息到 Redis Streams：`vl:watch_ingest` Stream
  │
  ▼
[5] Worker 消费消息，执行 RepPipeline
  ├─ Entity.ingest() → 触发 pipeline_a/b/e/f/g/h
  ├─ 沿 Rep 继承链（§5.13）自动构建所有 Rep
  └─ rep_all_ready 事件触发 IndexPipeline 重建
  │
  ▼
[6] Index 就绪，可检索
  └─ 用户可在 API / MCP / SDK 中查询
```

**消息格式**（Redis Streams `vl:watch_ingest`）：

```json
{
  "event_type": "watch_ingest",
  "watch_strategy_id": "prod-incoming",
  "ingest_strategy_id": "standard_doc",
  "workspace": "my-workspace",
  "collection": "knowledge-base",
  "entity_id": "pricing-2025",
  "source_path": "incoming/2025/pricing.pdf",
  "oss_path": "s3://bucket/incoming/2025/pricing.pdf",
  "raw_path": "s3://bucket/vector-lake/my-workspace/knowledge-base/pricing-2025/source/original.pdf",
  "entity_type_hint": "document",
  "mime_type": "application/pdf",
  "size_bytes": 1234567,
  "labels": {"source": "auto-watch", "ingestion": "auto"},
  "on_conflict": "update",
  "ts": "2026-06-06T10:00:00Z"
}
```

#### 5.15.3 entity_id 命名策略与冲突处理

**命名策略**（Ingest Strategy 配置）：

| 策略 | 示例输入 | 生成的 entity_id | 适用场景 |
| --- | --- | --- | --- |
| **filename** | `pricing-2025.pdf` | `pricing-2025` | 文件名已具备语义 |
| **filepath** | `incoming/2025/q3/pricing.pdf` | `incoming-2025-q3-pricing` | 路径含版本/日期信息 |
| **uuid** | `pricing.pdf` | `a3f8b2c1-...` | 文件名冲突/无语义 |
| **hash** | `pricing.pdf` | `sha256:abc123...` | 内容寻址，去重友好 |
| **template** | `pricing.pdf` | `{date}-{filename}` | 模板化命名 |

**冲突处理策略**（Ingest Strategy 的 `on_conflict` 配置）：

| 策略 | 行为 | 适用场景 |
| --- | --- | --- |
| **update** | 视为更新，触发 C1 Raw 变动级联（§5.14.2） | 同名文件更新内容（文档迭代） |
| **skip** | 跳过，不创建也不更新 | 避免重复处理（uuid 策略不会冲突） |
| **error** | 返回错误，记录到 Dead Letter | 严格模式，不允许覆盖 |

#### 5.15.4 4 类事件的自动处理

| 事件 | 检测 | 自动处理 | 用户感知 |
| --- | --- | --- | --- |
| **新建文件** | OSS Created / inotify CREATE | 自动创建 Entity + 构建索引 | 文件可检索 |
| **修改文件** | OSS Updated（ETag 变化） | 触发 C1 Raw 变动级联 + Rep 重建 + Index 重建 | 检索结果自动更新 |
| **删除文件** | OSS Removed / inotify DELETE | 触发 Entity 软删除（30 天可恢复） | 检索不再命中 |
| **重命名文件** | 拆解为"新建 + 删除" | 旧 Entity 软删除 + 新 Entity 创建 | 历史可追溯 |

#### 5.15.5 文件过滤与安全

**过滤规则归属**：文件过滤（白/黑名单、大小限制）属于 **Ingest Strategy**，不是 Watch Strategy。Watch Strategy 只管"检测 prefix 下的文件变动"，Ingest Strategy 决定"哪些文件可以接入、怎么接入"。

**Ingest Strategy 过滤配置**：

```yaml
ingest_strategies:
  standard_doc:
    allowed_extensions: [".pdf", ".md", ".docx"]    # 白名单
    blocked_patterns: ["*.tmp", ".*", "~*"]        # 黑名单（临时文件）
    max_file_size_mb: 500                          # 大小限制
    auto_create_entity: true
    on_conflict: update
```

**Watch Strategy 限流配置**：

```yaml
watch_strategies:
  - strategy_id: prod-incoming
    prefix: incoming/
    ingest_strategy: standard_doc
    require_stable_seconds: 30                     # 文件稳定期（防半上传）
    max_concurrent_ingest: 10                      # 并发限流
```

**文件稳定期判定**：
- 文件 mtime 30 秒内无变化 → 视为稳定，开始处理
- 防止上传过程中被半截读取（特别是大文件）

**访问控制**：
- Watcher 只能监听自己有读权限的 prefix
- 创建的 Entity 默认继承 watcher 所属 workspace
- 跨 workspace 监听需要显式授权

#### 5.15.6 批量上传优化

**大量文件同时上传**（如 1000 个文件）：

```text
1000 个文件同时上传
  │
  ▼
[1] OSS 一次性发送 1000 个事件（可能在 1 分钟内陆续到达）
  │
  ▼
[2] Watch Listener 批量聚合（按 collection 分组）
  └─ 每 5s flush 一次，避免逐个投递
  │
  ▼
[3] 批量 API 创建 Entity（§5.14.8）
  └─ POST /entities/batch 单次 50 个
  │
  ▼
[4] 批量 RepPipeline 执行
  └─ 同 RepPipeline 类型聚合执行，复用模型加载
  │
  ▼
[5] 批量 Index 重建
  └─ Lance dataset append 批量操作
```

**性能指标**：

| 指标 | v0.1 目标 | v0.2 目标 |
| --- | --- | --- |
| 单文件处理延迟（API → Index ready） | < 30s | < 10s |
| 批量吞吐（1000 文件） | < 30min | < 10min |
| OSS 事件 → API 触发延迟 P99 | < 5s | < 1s |
| 漏检率（事件丢失） | < 0.1%（Reconciler 兜底） | < 0.01% |

#### 5.15.7 与显式 API 的协调

**3 种数据接入范式并存**：

| 范式 | 触发 | 适用 | 关系 |
| --- | --- | --- | --- |
| **Watch Mode（自动）** | 文件上传到指定目录 | 简单场景、批量导入 | 主路径 |
| **显式 API** | `POST /entities` | 复杂元数据、特殊处理 | 与 Watch 并列 |
| **混合** | 部分 Watch + 部分 API | 高级用户 | 完全兼容 |

**协调规则**：
- Watch 创建的 Entity 与 API 创建的 Entity 在数据模型上完全一致
- 都可以被 API 进一步操作（更新 labels、删除等）
- 都可以被 Watch 路径监听（修改文件触发 C1 变动）

#### 5.15.8 错误处理与告警

> **错误处理总览**见本节；**Dead Letter TTL/清理细节**、**自动重试调度**、**告警规则**详见 §5.15.11.4。

| 错误 | 检测 | 处理 | 告警 |
| --- | --- | --- | --- |
| **文件格式不支持** | 扩展名不在 Ingest Strategy 白名单 | 跳过 + 记录到 `_watch_dead_letter/{ws}/{col}/{watch_strategy_id}/{date}/`（§5.15.11.4） | WARN 日志 |
| **文件损坏** | RepPipeline `parse` 步骤失败 | 标 `rep_status=failed` + 写入 Dead Letter | ERROR + 通知 |
| **OSS 事件丢失** | Reconciler 周期扫描发现 Entity 缺失 | 自动补建（Reconciler 兼任） | INFO 日志 |
| **Watch Strategy 宕机** | 心跳检测（watch_strategy_state=error） | 自动重启 + 从 Redis Streams 游标继续 | CRITICAL |
| **磁盘满** | OSS 写入失败 | 暂停 Watch（state=paused）+ 告警 | CRITICAL |
| **Ingest Strategy 配置错误** | 启动时校验 | 拒绝启动该 strategy（state=error） + 报告错误 | CRITICAL |
| **OSS API 限流** | 5xx / 429 响应 | 指数退避重试 + 触发 §5.15.11.6 配额告警 | WARN |
| **ETag 相同重复事件** | ETag diff 检测（§5.15.11.5） | 静默 skip | DEBUG |

**Dead Letter 队列**：

```text
目录结构（按 watch_strategy_id 隔离）：
vector-lake/
  └── {ws}/
      └── {col}/
          └── _watch_dead_letter/
              ├── {watch_strategy_id}/
              │   ├── 2026-06-06/
              │   │   ├── pricing.pdf.error.json
              │   │   └── report.docx.error.json
              │   └── _index.jsonl
              └── _cleanup.jsonl
```

- **保留原始文件 + 错误日志**：`.error.json` 含原文件引用、错误码、时间戳
- **TTL 清理**：默认 30 天后自动清理（可配置 `dead_letter_retention_days`）
- **手动 replay**：将 `.error.json` 移到原 prefix 下，自动重试
- **自动 replay**：失败后 5min / 1h / 6h 指数退避，3 次后永久 dead letter

#### 5.15.9 可观测性

> **命名规范**：所有 API 端点、Prometheus 指标、日志字段统一以 **`watch_strategy_id`**（监听策略 ID）和 **`ingest_strategy_id`**（接入策略 ID）作为主键维度，不再使用已废弃的 `watcher_id` / `oss_watchers`。

**API 端点**：

```python
# 查看所有 Watch Strategy 状态
GET /watch/strategies
  → {
      "watch_strategies": [
        {
          "watch_strategy_id": "prod-incoming",
          "ingest_strategy_id": "standard_doc",
          "type": "oss",
          "prefix": "incoming/",
          "workspace": "my-workspace",
          "collection": "knowledge-base",
          "status": "active",            # active | paused | error | initializing
          "last_event_at": "2026-06-06T10:00:00Z",
          "events_last_hour": 23,
          "entities_managed": 1523,
          "lag_p99_seconds": 2.3,
          "concurrent_ingest": 7,
          "max_concurrent_ingest": 10
        },
        {
          "watch_strategy_id": "prod-media",
          "ingest_strategy_id": "multimedia",
          ...
        }
      ]
    }

# 查看某 Watch Strategy 的历史事件
GET /watch/strategies/{watch_strategy_id}/events?from=...&to=...&event_type=...&limit=100
  → 返回事件流（created/updated/deleted/failed/skipped）

# 查看某 Ingest Strategy 详情
GET /watch/ingest_strategies/{ingest_strategy_id}
  → {
      "ingest_strategy_id": "standard_doc",
      "entity_id_strategy": "filename",
      "on_conflict": "update",
      "allowed_extensions": [".pdf", ".md", ".docx", ".pptx", ".txt"],
      "max_file_size_mb": 500,
      "bound_watch_strategies": ["prod-incoming", "dev-local"],
      "stats": {
        "ingested_total": 1523,
        "conflicts_skipped": 12,
        "conflicts_errored": 0
      }
    }

# 手动重放 Watch（补偿漏处理）
POST /watch/strategies/{watch_strategy_id}/replay
  {
    "from": "2026-06-01T00:00:00Z",
    "to":   "2026-06-06T00:00:00Z",
    "dry_run": false           # true=只统计不执行
  }

# 运行时管理 Watch Strategy（详见 §5.15.11.1）
POST   /watch/strategies                    # 新建
PATCH  /watch/strategies/{id}               # 改 prefix/限流等
DELETE /watch/strategies/{id}               # 停用
POST   /watch/strategies/{id}:pause         # 暂停
POST   /watch/strategies/{id}:resume        # 恢复
```

**监控指标**（Prometheus）：

| 指标 | 含义 |
| --- | --- |
| `watch_events_total{watch_strategy_id,ingest_strategy_id,event_type,result}` | 事件总数（按结果：ok/skipped/errored） |
| `watch_lag_seconds{watch_strategy_id}` | OSS 事件到处理的延迟 P50/P95/P99 |
| `watch_dead_letter_total{watch_strategy_id,error_class}` | 死信队列数（按错误类别） |
| `watch_entities_managed{watch_strategy_id}` | 当前管理的 Entity 数 |
| `watch_concurrent_ingest{watch_strategy_id}` | 当前并发接入数 |
| `watch_ingest_duration_seconds{watch_strategy_id,ingest_strategy_id}` | 单文件接入耗时分布 |
| `watch_oss_events_lost_total{watch_strategy_id}` | Reconciler 补单次数（兜底触发计数） |
| `watch_strategy_state{watch_strategy_id,state}` | 当前状态（active=1/paused=0/error=-1） |

**日志字段**（结构化 JSON 日志）：

```json
{
  "ts": "2026-06-06T10:00:00.123Z",
  "level": "INFO",
  "event": "watch_ingest_completed",
  "watch_strategy_id": "prod-incoming",
  "ingest_strategy_id": "standard_doc",
  "workspace": "my-workspace",
  "collection": "knowledge-base",
  "entity_id": "pricing-2025",
  "source_path": "incoming/2025/pricing.pdf",
  "duration_ms": 4521,
  "rep_count": 5,
  "result": "ok"                    # ok | skipped | errored
}
```

#### 5.15.10 v0.1 实施范围

| 功能 | v0.1 | v0.2 |
| --- | --- | --- |
| **OSS 事件监听** | ✅（S3 EventNotification / Aliyun OSS MNS） | ✅ |
| **本地目录 inotify** | ✅（开发模式） | ✅ |
| **Reconciler 周期兜底** | ✅（15min 默认） | ✅（可配置） |
| **Ingest Strategy 5 个预置**（standard_doc / wps_doc / multimedia / tabular / web_crawl） | ✅ | ✅ |
| **Watch Strategy 5 个示例** | ✅ | ✅ |
| **Watch / Ingest 解耦** | ✅ | ✅ |
| **5 种 entity_id 策略**（filename/filepath/uuid/hash/template） | ✅（filename/filepath/uuid） | ✅（全 5 种） |
| **on_conflict 三策略**（update/skip/error） | ✅ | ✅ |
| **4 类事件自动处理**（created/updated/deleted/renamed） | ✅ | ✅ |
| **修改触发 C1 变动级联** | ✅ | ✅ |
| **删除触发软删除（30 天）** | ✅ | ✅ |
| **文件过滤（白/黑名单 + 大小 + 稳定期）** | ✅ | ✅ |
| **批量聚合**（5s flush） | ✅ | ✅（1s flush） |
| **死信队列 + TTL 清理** | ✅ | ✅ |
| **手动 replay** | ✅ | ✅ |
| **嵌套子目录递归** | ✅ | ✅ |
| **多租户隔离（workspace 隔离 Watch）** | ✅ | ✅ |
| **运行时更新 Watch Strategy**（PATCH API） | ✅ | ✅ |
| **多 Watch Strategy 同 prefix 冲突检测** | ✅ | ✅ |
| **Per-collection 配额** | ✅（仅全局默认） | ✅（+ per-collection 覆盖） |
| **多 OSS bucket 同时监听** | ❌ | ✅ |
| **S3 EventBridge 集成** | ❌ | ✅ |
| **MCP Tool：`watch_list` / `watch_status` / `watch_replay`** | ✅ | ✅ |
| **Ingest Strategy 删除保护**（409 Conflict + bound_watch_strategies 引用检查） | ✅ | ✅ |
| **Watch Listener 启动/关闭流程**（§20.6 / §20.7） | ✅ | ✅ |
| **Watch 事件 SSE 实时推送** | ❌ | ✅ |

#### 5.15.11 高级场景

> 前面 10 节覆盖了 Watch Mode 的"主干流程"。本节集中处理生产落地中必然遇到的 9 类**高级场景**，确保 PRD 完整可实现。

##### 5.15.11.1 运行时更新 Watch / Ingest Strategy

**为什么需要**：用户改完 `config.yaml` 后，**不应**必须重启整个 Vector-Lake 进程（重启期间会丢失事件）。监听/接入策略应支持热更新。

**Watch Strategy 热更新**（无需重启）：

| 字段 | 可热更新 | 行为 |
| --- | --- | --- |
| `max_concurrent_ingest` | ✅ | 立即生效（令牌桶扩容/缩容） |
| `require_stable_seconds` | ✅ | 对**新接收**的事件生效 |
| `prefix` | ✅ | Reconciler 下一轮扫描时切换 |
| `ingest_strategy`（换绑定） | ✅ | 对**新接入**生效，旧 Entity 不变 |
| `recursive` | ✅ | 同 prefix |
| `type`（oss→local 等） | ❌ | 需 stop → recreate |
| `workspace` / `collection` | ❌ | 需 stop → recreate（涉及数据迁移） |

**Ingest Strategy 热更新**（无需重启）：

| 字段 | 可热更新 | 行为 |
| --- | --- | --- |
| `allowed_extensions` | ✅ | 对**新接入**生效，旧 Entity 不变 |
| `blocked_patterns` | ✅ | 对**新接入**生效 |
| `max_file_size_mb` | ✅ | 对**新接入**生效 |
| `default_labels` | ✅ | 对**新接入**生效，旧 Entity 不变 |
| `on_conflict` | ✅ | 对**新接入**生效 |
| `entity_id_strategy` | ✅ | 对**新接入**生效，旧 Entity 不变 |
| `inherit_labels_from` | ✅ | 对**新接入**生效 |

> **注意**：Ingest Strategy 热更新只影响**新接入的文件**，已创建的 Entity 不受影响。如需更新旧 Entity 的 labels，需通过 API 显式调用 `Entity.update_labels()`。

**API**：

```python
# Watch Strategy 管理
# 部分更新（PATCH 语义）
PATCH /watch/strategies/{id}
  { "max_concurrent_ingest": 20, "require_stable_seconds": 60 }
  → 200 OK，返回新 config + 生效时间戳

# 替换（PUT 语义，必须提供全部必填字段）
PUT /watch/strategies/{id}
  { ... 完整 watch_strategy 配置 ... }

# 暂停 / 恢复
POST /watch/strategies/{id}:pause
  → 后续事件进入 Redis Streams 缓冲（缓冲上限 10000 条），不丢
POST /watch/strategies/{id}:resume
  → 消费缓冲 + 恢复实时监听

# 删除（停用）
DELETE /watch/strategies/{id}
  → state=stopped，不再接收事件，已创建 Entity 不受影响

# Ingest Strategy 管理
# 部分更新（PATCH 语义）
PATCH /watch/ingest_strategies/{id}
  { "allowed_extensions": [".pdf", ".md", ".docx"], "on_conflict": "skip" }
  → 200 OK，返回新 config + 生效时间戳 + bound_watch_strategies 列表

# 替换（PUT 语义）
PUT /watch/ingest_strategies/{id}
  { ... 完整 ingest_strategy 配置 ... }

# 删除（需引用检查）
DELETE /watch/ingest_strategies/{id}
  → 若 bound_watch_strategies 非空 → 409 Conflict + 返回引用列表
  → 若 bound_watch_strategies 为空 → 200 OK，删除成功
```

**Ingest Strategy 删除保护**：

```python
# 删除前检查引用
def delete_ingest_strategy(ingest_strategy_id):
    bound = list_watch_strategies(ingest_strategy=ingest_strategy_id)
    if bound:
        return {
            "error": "VL-INGEST-REFERENCED",
            "message": f"Ingest Strategy '{ingest_strategy_id}' is referenced by {len(bound)} Watch Strategies",
            "bound_watch_strategies": [s.strategy_id for s in bound],
            "hint": "Unbind or delete Watch Strategies first, or use force=true"
        }, 409
    else:
        delete_strategy_config(ingest_strategy_id)
        return {"ok": True}, 200

# 强制删除（同时解绑所有 Watch Strategy）
DELETE /watch/ingest_strategies/{id}?force=true
  → 所有 bound Watch Strategy 的 ingest_strategy 字段置空 → state=error
  → 删除 Ingest Strategy → 200 OK
  → 需 admin role
```

**Watch Strategy 生命周期状态机**：

```text
                 POST /strategies
initializing ──────────────────▶ active ◀─── resume ─── paused
   │                              │  ▲
   │ startup-failed               │  │ patch（热更新）
   ▼                              │  │
  error ────── admin/retry ───────┘  │
                                     │
                          delete ──▶ stopped
```

- **active**：正在接收事件
- **paused**：暂停接收，新事件进缓冲队列
- **initializing**：启动中（最长 30s 超时则 `error`）
- **error**：启动失败或运行异常，需管理员介入（`POST /strategies/{id}:retry`）
- **stopped**：已删除，不再接收任何事件

##### 5.15.11.2 多租户隔离

**核心原则**：Watch Strategy **强绑定 workspace**，跨 workspace 监听需显式授权。

**隔离规则**：

| 维度 | 隔离机制 |
| --- | --- |
| **配置可见性** | 用户只能看到/管理自己 workspace 下的 Watch Strategy（admin role 例外） |
| **OSS prefix 隔离** | Watch 只能监听自己 workspace 有读权限的 OSS prefix；跨 workspace 监听需 `cross_workspace_read: true` 标志（admin 授权） |
| **资源配额** | 见 §5.15.11.6 per-collection 配额 |
| **指标命名空间** | Prometheus 指标带 `workspace` label，可按 workspace 聚合 |
| **日志脱敏** | 不同 workspace 的 OSS path 在共享日志中按 workspace 隔离 bucket |

**配置示例**（admin 显式跨 workspace 授权）：

```yaml
watch_strategies:
  - strategy_id: shared-public-docs
    type: oss
    workspace: public-workspace                # 源 workspace
    cross_workspace_read:                     # 显式授权
      - workspace: tenant-a
        prefix: shared-incoming/                # 只读此子 prefix
        read_only: true
    collection: shared-knowledge-base
    prefix: shared-incoming/
    ingest_strategy: standard_doc
```

**多租户事件总线**：`vl:watch_ingest` Stream 按 `workspace` 字段路由到对应 worker 池（v0.1 单租户可忽略，v0.2 多租户必须）。

##### 5.15.11.3 竞态与一致性

**4 类典型竞态**：

1. **同文件并发事件**（OSS 短时间内连发多个事件）
2. **Watcher 与 API 同时写**（同一 entity_id 被 Watch 路径和显式 API 同时创建）
3. **同文件正在处理时再次上传**（半上传 vs 已处理）
4. **同 Entity 多 RepPipeline 并发**（同一 Entity 的 rep_pipeline_a 和 rep_pipeline_b 同时执行，写同一 Entity 目录）

**解决方案**：

| 竞态 | 解决方案 | 锁粒度 |
| --- | --- | --- |
| **同文件并发事件** | Redis 分布式锁 `lock:watch:entity:{entity_id}`，锁持有者执行 ingest，**其他事件按事件类型聚合**（多次 created → 1 次 + 1 次 update；created + deleted → 取消） | entity_id |
| **Watcher vs API 冲突** | 统一锁入口：API 创建也走 `Entity.ingest()`，与 Watch 路径共享同一锁（见 §5.15.3 on_conflict 策略） | entity_id |
| **同文件正在处理时再次上传** | 锁 + 队列：检测到"锁已存在"，把事件入 Redis Streams 等待队列，锁释放后 FIFO 处理 | entity_id + 等待队列 |
| **同 Entity 多 RepPipeline 并发** | RepPipeline 级锁 `lock:rep:{ws}:{col}:{entity_id}:{rep_type}`（见 §6.9 并发模型），不同 RepPipeline 可并行执行，同一条 RepPipeline 串行执行；写入同一 Entity 目录时通过 OSS 原子性保证（不同 Rep 写不同子目录 `extract/` / `recognize/` / `compile/`，无交叉） | rep_type |

**锁释放策略**：

```python
# 锁获取（带超时）
lock_key = f"lock:watch:entity:{ws}:{col}:{entity_id}"
acquired = redis.set(lock_key, worker_id, nx=True, ex=300)  # 5min TTL
if not acquired:
    # 已有锁持有者 → 入等待队列
    redis.lpush(f"queue:watch:wait:{entity_id}", event_json)
    return  # 不阻塞 watcher

try:
    ingest_file(...)
finally:
    # 处理完后消费等待队列里的下一条
    next_event = redis.rpop(f"queue:watch:wait:{entity_id}")
    redis.delete(lock_key)
    if next_event:
        # 触发下一轮（异步）
        enqueue_watch_event(next_event)
```

**幂等保证**：

- Entity 创建幂等：相同 `(entity_id, content_hash)` 第二次创建返回"已存在"，不重复执行 RepPipeline
- RepPipeline 幂等：所有 RepStep 声明 idempotent（§6.2），重跑结果一致
- IndexPipeline 幂等：Lance dataset append 操作天然幂等（PK 相同则覆盖）

##### 5.15.11.4 Dead Letter TTL 与自动清理

> 上一节 §5.15.8 已定义目录结构，本节明确 **TTL 配置**、**清理流程** 和 **监控告警**。

**配置**：

```yaml
watch_mode:
  dead_letter:
    enabled: true
    retention_days: 30                # 默认 30 天
    cleanup_interval_hours: 6         # 每天清理 4 次
    max_total_size_gb: 100            # 全局硬上限（防磁盘爆）
    max_per_strategy_gb: 10           # 单 strategy 硬上限
    auto_retry:                       # 自动重试（指数退避）
      enabled: true
      max_attempts: 3                 # 3 次后永久 dead letter
      backoff_schedule: [300, 3600, 21600]   # 5min / 1h / 6h
```

**清理流程**（Reconciler Phase 5 兼任）：

```text
[1] 扫描 _watch_dead_letter/ 目录
    ├─ 收集所有 .error.json 文件
    ├─ 读取 ts 字段
    └─ 按 (watch_strategy_id, date) 聚合
[2] 应用清理规则
    ├─ 超过 retention_days → 删除
    ├─ 超过 max_total_size_gb → 删最老的
    └─ 超过 max_per_strategy_gb → 该 strategy 的最老的
[3] 记录到 _cleanup.jsonl 审计日志
    { "ts": ..., "deleted": ["path1", ...], "reason": "ttl_expired" }
[4] 清理失败处理
    ├─ OSS 删除失败（网络/权限）→ 记录到 _cleanup.jsonl（status=failed + error_message）
    ├─ 下次 cleanup_interval 后重试（最多 3 次）
    └─ 3 次仍失败 → 告警 `WatchCleanupFailed` + 标记为 stuck，需管理员手动处理
[5] 触发监控
    - watch_dead_letter_total gauge 下降
    - watch_cleanup_total{reason,status} counter 增加（status=ok/failed）
```

**自动重试**（5min/1h/6h 退避）：

```text
失败事件 → 写入 _watch_dead_letter/{ws}/{col}/{strategy_id}/{date}/{file}.error.json
  │
  ▼
[5min 后] Retry Worker 扫描 .error.json
  ├─ 重新执行 ingest
  ├─ 成功 → 删除 .error.json
  └─ 失败 → 写 retry_count + last_retry_at，调度 [1h 后]
[1h 后] 同上，失败则 [6h 后]
[6h 后] 同上，失败则标 permanent_dead
  └─ 不再自动重试，需手动 replay（`POST /watch/dead_letter:replay`）
```

**告警规则**：

| 规则 | 触发条件 | 级别 |
| --- | --- | --- |
| `WatchDeadLetterBurst` | 1h 内新增 > 100 条 | WARN |
| `WatchDeadLetterStale` | 某 strategy 连续 7 天每天都有新死信 | WARN |
| `WatchDeadLetterDiskFull` | dead_letter 总大小 > max_total_size_gb × 0.9 | CRITICAL |
| `WatchAutoRetryExhausted` | 出现 permanent_dead 事件 | ERROR |

##### 5.15.11.5 多 Watch Strategy 冲突

> v0.2 待展开。核心思路：多 Watch 监听同一前缀时，启动阶段拒绝重叠前缀（allow_conflict opt-in），运行时通过 Longest Prefix Match 去重 + processed_by Redis 标记 + ETag diff 检测避免重复处理。

##### 5.15.11.6 Per-Collection 配额

> v0.2 待展开（v0.1 仅支持全局默认配额）。核心思路：per-collection 覆盖 Entity 数 / Chunk 数 / 存储量 / QPS 四类配额，超限返回 429 + token bucket 限流。

##### 5.15.11.7 Delete-Only Watch

> v0.2 待展开。核心思路：event_filter.types=[deleted] + auto_create_entity=false，仅监听删除事件用于清理外部索引。

##### 5.15.11.8 文件删除/中途失败的边界处理

**场景 1**：文件已写入 OSS 且 Watch 已开始 ingest，但 **RepPipeline 执行过程中文件被删除**。

```text
[1] Watch 检测到 incoming/x.pdf
[2] 复制到 raw/x/source/original.pdf（已写入）
[3] RepPipeline 执行中（canonical_md 正在生成）
[4] 用户/外部系统删除 incoming/x.pdf
[5] RepPipeline 完成
[6] Entity 已存在（raw 完整），Index 已就绪
```

**处理**：

- raw 已物理拷贝到 Lake 内部（`vector-lake/{ws}/{col}/...`），与原 OSS 文件解耦
- Entity **保留**，不被删除
- Reconciler 不会"清理"该 Entity（因为 raw 完整、Rep 完整、Index 完整）
- 适合场景：用户上传后又撤回，但 Lake 已被使用过应保留副本

**场景 2**：文件**仍在上传中**（半截读取）。

- `require_stable_seconds: 30` 已防御：30s 内 mtime 变化视为不稳定
- Worker 重试：发现 mtime 变化 → 等待下一轮稳定后再处理

**场景 3**：文件上传成功但**格式探测失败**（如声称 .pdf 实际是损坏文件）。

- 写入 raw 成功（文件存在），RepPipeline `parse` 步骤失败
- `rep_status=failed`，写入 Dead Letter
- 用户可手动 replay 或修改后重新上传

**场景 4**：Watcher **宕机期间**事件堆积。

- OSS 事件有 24h 重试窗口（S3）/ 7 天（Aliyun OSS MNS）
- Watcher 重启后从 Redis Streams 游标继续消费
- Reconciler 兜底：每 15min 扫一次 OSS prefix，对比 Entity 列表，**自动补建**缺失的 Entity

**场景 5**：API 创建的 Entity 对应的 OSS 文件被外部删除。

> 通过 API（非 Watch）创建的 Entity，其 raw 文件已拷贝到 Lake 内部，但原始 OSS 路径可能被外部流程删除。如果该 Entity 关联了 `source_oss_path`，Delete-Only Watch（§5.15.11.7）可检测到删除并触发软删除。

**`source_oss_path` 字段**：

```python
# Entity Manifest 中记录来源 OSS 路径（v0.1 所有 Entity 均记录）
{
  "entity_id": "pricing-2025",
  "source_oss_path": "incoming/2025/pricing.pdf",   # 原始 OSS 路径
  "source_etag": "\"abc123...\"",                    # 原始 ETag
  "source_type": "watch",                            # watch | api | reconciler
  ...
}
```

| `source_type` | 含义 | Delete-Only Watch 能否检测删除 |
| --- | --- | --- |
| `watch` | Watch 自动创建 | ✅（prefix 匹配即可） |
| `api` | API 显式创建 | ✅（需 `source_oss_path` 在 Delete-Only Watch 的 prefix 范围内） |
| `reconciler` | Reconciler 补建 | ✅（同 api） |

- **v0.1**：所有 Entity（无论 watch/api/reconciler 创建）均记录 `source_oss_path` + `source_etag` + `source_type`
- **Reconciler 兜底**：即使没有 Delete-Only Watch，Reconciler 也会周期性检查 `source_oss_path` 是否仍存在，不存在则触发软删除（Phase 1 校验）
- **API 创建时**：`POST /entities` 可选传入 `source_oss_path`，不传则 `source_type=api` + `source_oss_path=null`（Reconciler 无法检测外部删除）

##### 5.15.11.9 MCP Tool 暴露

**MCP Server 暴露给 LLM 的 Watch 相关 Tool**：

| MCP Tool | 输入 | 输出 | 说明 | v0.1 |
| --- | --- | --- | --- | --- |
| `watch_list` | `{ workspace?, status? }` | `{ watch_strategies: [...] }` | 列出 Watch Strategy | ✅ |
| `watch_status` | `{ watch_strategy_id }` | `{ status, lag, entities, ... }` | 查看单个策略状态 | ✅ |
| `watch_create` | `{ ...config }` | `{ watch_strategy_id }` | 新建策略（需 `watch:admin` role） | ✅ |
| `watch_pause` | `{ watch_strategy_id }` | `{ ok }` | 暂停（需 `watch:write` role） | ✅ |
| `watch_resume` | `{ watch_strategy_id }` | `{ ok }` | 恢复（需 `watch:write` role） | ✅ |
| `watch_replay` | `{ watch_strategy_id, from, to }` | `{ replayed: int, failed: int }` | 补单（需 `watch:write` role） | ✅ |
| `watch_dead_letter_list` | `{ watch_strategy_id, limit? }` | `{ errors: [...] }` | 查看死信 | ✅ |
| `watch_dead_letter_replay` | `{ error_id }` | `{ ok }` | 重放单个死信（需 `watch:write` role） | ✅ |

**权限**：所有 Tool 走 MCP 权限模型（§5.15.11.2），需要 `watch:read` / `watch:write` / `watch:admin` role。

**LLM 典型用法**（自然语言 → Tool 调用）：

> LLM: "帮我看下 production 的 incoming/ 目录最近一小时有没有失败的文件"
> → 解析为 `watch_status({watch_strategy_id: "prod-incoming"})` + `watch_dead_letter_list({watch_strategy_id: "prod-incoming", limit: 10})`

---

## 6. Pipeline 定义

### 6.1 Pipeline 是一等公民

同一 Entity 可以走多条并行流水线，每条产出不同的 Representation：

| Pipeline | 输入 | 产出 Representation | 产出 Chunk 类型 | Embedding 策略 |
| --- | --- | --- | --- | --- |
| **A. 直接提取** | raw | canonical_md, plain_text | text chunks | `retrieval.passage` on embedding_text |
| **B. 视觉识别** | raw → page_image | page_image, vlm_md | image chunks + text chunks | `image` on page_image; `retrieval.passage` on vlm_md |
| **D. 知识编译** | canonical_md | mind_map, graph_json, wiki_md, summary | text chunks | `retrieval.passage` on summary/caption |
| **E. 图片向量** | raw → page_image | page_image | image chunks | `image` on page_image |
| **F. 音频转写** | raw → audio_segment | audio_segment, transcript, transcript_segment | audio chunks + text chunks | `audio` on segment; `retrieval.passage` on transcript |
| **G. 表格获取** | raw (CSV / Excel / SQL) | table_parquet, table_md, table_json | table chunks | `retrieval.passage` on table_md/table_json text；table_parquet 供 DuckDB 查询 |
| **H. 视频关键帧** | raw (mp4/avi/mov/mkv/webm) | keyframe_image, keyframe_timeline | image chunks | `image` on keyframe；时间戳锚点（§4.3.1） |

### 6.2 Pipeline 编排原则

- **idempotent**：所有 pipeline 可重跑，重跑结果应一致或单调升级。
- **append-only on raw**：raw object 永不修改；重建只写新 representation。
- **parallel**：多条 pipeline 可并行执行，互不阻塞。
- **partial success 优先**：单条 pipeline 失败不阻塞其他 pipeline 的产出可用。
- **可追加**：新 pipeline 可随时注册，对已有 entity 按需重跑。

### 6.3 Pipeline 与 Entity Type 的映射

| entity_type | 默认 Pipeline | 可选 Pipeline | 备注 |
| --- | --- | --- | --- |
| **url** | **URL (抓取+解析)** | B (视觉识别) | URL → HTML → MD；PDF 类型 URL 走 B |
| document | A (直接提取) | B (视觉识别), D (知识编译), E (图片向量) | 文档默认走文本提取；办公文档走 B（转 PDF → VLM） |
| image | E (图片向量) | B (视觉识别), D (知识编译) | 单图走 E，多图可走 A→B |
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
| B (视觉识别) | 依赖 E (page_image) 或自己生成 page_image | 需先有图片才能视觉识别 |
| D (知识编译) | 依赖 A (canonical_md) | 编译对象是 canonical_md |
| G (表格) | 通常无依赖 | raw 直接解析，但 PDF 表格需先 A→表格抽取 |

**依赖图可视化**：

```text
                raw
                 │
    ┌────────┬───┴────┬────────┬────────┐
    ▼        ▼        ▼        ▼        ▼
    A        B        E        G
    │        │        │
    │        │        │
    │ (canonical_md)  │ (page_image)
    ▼        ▼        ▼
   D (知识编译)    B 依赖 E 的 page_image
```

**Pipeline 调度规则**：

1. **拓扑排序**：D 必须等 A 完成；B 必须等 E（或自己生成 page_image）
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
.mp4 .avi .mov .mkv          → video       → F (transcribe) + H (extract_keyframes)
.webm .flv .wmv              → video       → F (transcribe) + H (extract_keyframes)
```

#### 6.5.7 格式不支持时的处理

| 场景 | 处理方式 |
| --- | --- |
| 扩展名不在清单中 | 返回 `INVALID_ENTITY_ID` 错误，提示支持的格式列表 |
| 扩展名匹配但内容损坏 | RepStep `parse` 失败 → `PIPELINE_STEP_FAILED`，Worker 日志记录具体错误 |
| WPS 格式但 LibreOffice 不可用 | 降级为 `UNSUPPORTED_FORMAT` 错误，提示安装 LibreOffice |
| 新格式需求 | 注册自定义 RepStep（§6.7.5），在 Plugin 配置中声明 `supported_extensions` |

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

### 6.7 RepStep Plugin 体系（内容变换插件）

> **核心定位**：RepStep 是 RepPipeline 的可插拔步骤。每个 RepStep 做一件事：把上游 Representation 文件变换为下游 Representation 文件。新增 rep_type = 新增 RepStep + 注册，不改已有代码。

#### 6.7.1 RepStep Protocol

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

#### 6.7.2 RepStepRegistry（全局插件注册表）

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

#### 6.7.3 内置 RepStep 清单（v0.1）

| step_id | name | required_input_reps | optional_input_reps | output_reps | output_stage | entity_types | modality | v0.1 |
|---|---|---|---|---|---|---|---|---|
| `fetch_url` | URL 抓取 | — | — | `source/original` | extract | document, table, image | text | ✅ |
| `parse_html` | HTML 解析 | `source/original` | — | `canonical_md` | extract | document | text | ✅ |
| `convert_to_pdf` | 办公文档转 PDF | `raw` | — | `source/pdf` | extract | document | text | ✅ |
| `parse` | 文档解析 | `raw` | — | `canonical_md`, `plain_text`, `layout_json` | extract | document | text | ✅ |
| `render_page` | 页面渲染 | `raw` / `source/pdf` | — | `page_image` | extract | document, image | image | ✅ |
| `visual_recognize` | 视觉识别（VLM） | `page_image` | — | `vlm_md` | recognize | document | text | ✅ |
| `transcribe` | 音视频转写 | `raw` | — | `transcript`, `audio_segment` | recognize | audio, video | audio | ✅ |
| `extract_keyframes` | 视频关键帧抽取 | `raw` | — | `keyframe_image`, `keyframe_timeline` | extract | video | image | ✅ |
| `table_parse` | 表格解析 | `raw` | — | `table_parquet`, `table_md`, `table_json` | compile | table | table | ✅ |
| `compile_mind_map` | 脑图编译 | `canonical_md` | — | `mind_map` | compile | document | text | v0.2 |
| `compile_graph_json` | 关系图编译 | `canonical_md` | — | `graph_json` | compile | document | text | v0.2 |
| `compile_summary` | 摘要编译 | `canonical_md` | — | `summary` | compile | document | text | v0.2 |
| `compile_wiki_md` | Wiki 编译 | `canonical_md` | — | `wiki_md` | compile | document | wiki | v0.2 |
| `project_wiki` | Wiki 投影 | `canonical_md` | `wiki_md`, `graph_json`, `summary` | — | compile | document | wiki | v0.2 |

> `project_wiki` 是 Projector 作为 RepStep 注册的示例（§11），产出不写回 Lake 内部，而是写外部 vault。`required_input_reps` 表示必须全部存在；`optional_input_reps` 表示有则用、无则跳过该输入分支。

#### 6.7.4 内置 RepPipeline 组装

| pipeline_id | name | steps | v0.1 |
|---|---|---|---|
| `rep_pipeline_url` | URL 抓取 + 解析 | `fetch_url` → `parse_html` | ✅ |
| `rep_pipeline_a` | 直接提取 | `parse` | ✅ |
| `rep_pipeline_b` | 视觉识别 | `convert_to_pdf`（办公文档时）→ `render_page` → `visual_recognize` | ✅ |
| `rep_pipeline_d_mind_map` | 脑图编译 | `compile_mind_map` | v0.2 |
| `rep_pipeline_d_graph` | 关系图编译 | `compile_graph_json` | v0.2 |
| `rep_pipeline_d_summary` | 摘要编译 | `compile_summary` | v0.2 |
| `rep_pipeline_d_wiki` | Wiki 编译 | `compile_wiki_md` | v0.2 |
| `rep_pipeline_e` | 图片渲染 | `render_page` | ✅ |
| `rep_pipeline_f` | 音频转写 | `transcribe` | ✅ |
| `rep_pipeline_g` | 表格获取 | `table_parse` | ✅ |
| `rep_pipeline_h` | 视频关键帧抽取 | `extract_keyframes` | ✅ |

> RepPipeline 编号约定：`rep_pipeline_<family>[_<variant>]`，family = a/b/d/e/f/g/h。`h` 族为视频专用（关键帧抽取，依赖 ffmpeg）。

#### 6.7.5 第三方 RepStep 注册示例

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

#### 6.7.6 v0.1 核心流路：一切皆 MD

> **v0.1 设计哲学**：所有 Pipeline 的最终目标都是产出 Markdown（`canonical_md` / `vlm_md`），作为后续 IndexPipeline 的统一输入。v0.1 聚焦三条核心流路：

**流路 1：URL → HTML → MD**

```text
URL Entity (source_type=url)
  │
  ▼
fetch_url          ← HTTP GET，写入 source/original + .meta.json
  │
  ▼
parse_html         ← readability + html2md，提取正文 → canonical_md
  │
  ▼
IndexPipeline      ← chunk_and_embed_text → Lance 索引
```

- 适用：网页、API 文档、博客、在线帮助
- `fetch_url` 按 `Content-Type` 路由：`text/html` → `parse_html`；`application/pdf` → 走流路 2；`text/markdown` → 直接作为 `canonical_md`

**流路 2：Office → PDF → VLM → MD**

```text
文件 Entity (entity_type=document, 格式=doc/docx/ppt/pptx/wps/wpt/dps/dpt)
  │
  ▼
convert_to_pdf     ← LibreOffice headless 转换，输出 source/pdf
  │
  ▼
render_page        ← pdf2image 逐页渲染，输出 page_image
  │
  ▼
visual_recognize   ← VLM 视觉识别，输出 vlm_md
  │
  ▼
IndexPipeline      ← chunk_and_embed_text → Lance 索引
```

- 适用：Word / WPS / PPT / DPS 等办公文档
- PDF 文件跳过 `convert_to_pdf`，直接从 `render_page` 开始
- `convert_to_pdf` 依赖 LibreOffice headless（`soffice --headless --convert-to pdf`）

**流路 3：直接 MD**

```text
文件 Entity (entity_type=document, 格式=md/txt/rtf)
  │
  ▼
parse              ← md 直接作为 canonical_md；txt/rtf 轻量提取
  │
  ▼
IndexPipeline      ← chunk_and_embed_text → Lance 索引
```

- 适用：Markdown、纯文本、RTF
- `.md` 文件几乎零处理成本，直接作为 `canonical_md`

**v0.1 Pipeline 路由总表**：

| 输入来源 | 格式 | 流路 | Pipeline | 关键 RepStep |
| --- | --- | --- | --- | --- |
| URL | text/html | 1 | `rep_pipeline_url` | `fetch_url` → `parse_html` |
| URL | application/pdf | 2 | `rep_pipeline_b` | `fetch_url` → `render_page` → `visual_recognize` |
| URL | text/markdown | 3 | `rep_pipeline_url` | `fetch_url` → 直接 `canonical_md` |
| 文件 | .pdf | 2 | `rep_pipeline_b` | `render_page` → `visual_recognize` |
| 文件 | .doc/.docx/.ppt/.pptx | 2 | `rep_pipeline_b` | `convert_to_pdf` → `render_page` → `visual_recognize` |
| 文件 | .wps/.wpt/.dps/.dpt | 2 | `rep_pipeline_b` | `convert_to_pdf` → `render_page` → `visual_recognize` |
| 文件 | .md | 3 | `rep_pipeline_a` | `parse`（直接 copy） |
| 文件 | .txt/.rtf | 3 | `rep_pipeline_a` | `parse`（轻量提取） |
| 文件 | .csv/.xlsx/.json | — | `rep_pipeline_g` | `table_parse` |
| 文件 | .jpg/.png 等 | — | `rep_pipeline_e` | `render_page` |
| 文件 | .mp3/.wav 等 | — | `rep_pipeline_f` | `transcribe` |
| 文件 | .mp4/.avi 等 | — | `rep_pipeline_h` + `rep_pipeline_f` | `extract_keyframes` + `transcribe` |

> **v0.1 不支持的流路**：JS 渲染页面（需 headless browser，v0.2）、递归爬取子页面（v0.2）、Sitemap 解析（v0.2）。

### 6.8 IndexStep Plugin 体系（索引构建插件）

> **核心定位**：IndexStep 是 IndexPipeline 的可插拔步骤。每个 IndexStep 做一件事：消费 Representation 文件，构建搜索索引。新增 index_type = 新增 IndexStep + 注册，不改已有代码。IndexStep 与 RepStep 完全解耦——IndexStep 不知道 RepStep 的存在，只消费 Representation 文件。

#### 6.8.1 IndexStep Protocol

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

#### 6.8.2 IndexStepRegistry（全局插件注册表）

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

#### 6.8.3 内置 IndexStep 清单（v0.1）

| step_id | name | index_type | required_reps | optional_reps | supported_modalities | v0.1 |
|---|---|---|---|---|---|
| `chunk_and_embed_text` | 文本切片+嵌入 | semantic | `canonical_md`, `vlm_md`（任一） | `layout_json` | text | ✅ |
| `build_vector_index` | 向量索引 | semantic | — | — | text, image, audio | ✅ |
| `build_fts_index` | 全文索引 | lexical | — | — | text | ✅ |
| `chunk_and_embed_image` | 图片切片+嵌入 | visual | `page_image` | `layout_json` | image | ✅ |
| `chunk_and_embed_audio` | 音频切片+嵌入 | audio | `transcript`, `audio_segment` | — | audio | v0.2 |
| `chunk_and_embed_video` | 视频双模态切片+嵌入 | audio + visual | `transcript` + `keyframe_image` | `keyframe_timeline` | video | ✅ |
| `build_graph_index` | 图索引 | graph | `graph_json` | — | graph | v0.2 |
| `chunk_and_embed_table` | 表格切片+嵌入 | table | `table_md`, `table_json` | `layout_json` | table | v0.2 |
| `register_duckdb_view` | DuckDB 结构化注册 | structural | `table_parquet` | — | table | ✅ |

#### 6.8.4 内置 IndexPipeline 组装（v0.1）

| pipeline_id | name | steps |
|---|---|---|
| `index_pipeline_text` | 文本索引 | `chunk_and_embed_text` → `build_vector_index` → `build_fts_index` |
| `index_pipeline_image` | 图片索引 | `chunk_and_embed_image` → `build_vector_index` |
| `index_pipeline_video` | 视频双模态索引 | `chunk_and_embed_audio` → `build_vector_index` → `chunk_and_embed_image` → `build_vector_index`（音轨 + 关键帧） |
| `index_pipeline_structural` | 结构化检索 | `register_duckdb_view`（将 table_parquet 注册到 DuckDB 嵌入式视图） |
| `index_pipeline_audio` | 音频索引（纯音频） | `chunk_and_embed_audio` → `build_vector_index` |
| `index_pipeline_graph` | 图索引 | `build_graph_index` |
| `index_pipeline_table` | 表格索引（文本检索） | `chunk_and_embed_table` → `build_vector_index` |

> **`index_pipeline_video` vs `index_pipeline_audio`**：video 实体走 video（含音轨 + 关键帧），audio 实体走 audio（仅音轨）。`index_pipeline_structural` 是表格类 Entity 的结构化检索通道，不与 `index_pipeline_table` 互斥，两者可同时存在（结构化 + 文本联合检索）。

#### 6.8.5 IndexPipeline 触发时机

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

#### 6.8.6 IndexPipeline 参数配置（v0.1）

> IndexPipeline 的行为由 **IndexStrategy** 控制——类似 Ingest Strategy 控制"文件如何变成 Entity"，IndexStrategy 控制"MD 如何变成索引"。

**IndexStrategy 定义**：

```yaml
index_strategies:
  - id: default_text
    pipeline: index_pipeline_text
    chunking:
      method: markdown_heading          # markdown_heading | library | fixed_size | semantic | sentence
      config:
        chunk_tokens: 256               # 单 chunk 最大 token 数
        window_size: 9                  # 滑动窗口大小（奇数，自动调整）
        max_window_length: 12000        # 窗口最大字符数
        target_max_length: 10000        # 窗口目标最大字符数
        max_table_length: 3000          # 表格保护最大长度（超长表格强制截断）
        heading_levels: [1, 2, 3]       # 按哪些标题级别切分
        respect_code_blocks: true       # 代码块不切断
        respect_table_blocks: true      # 表格不切断
    embedding:
      model: jina-embeddings-v5-text-small  # 引用 config.yaml embedding.models 中的 key
      dimension: 1024                   # 输出向量维度
      batch_size: 64                    # 单次 embedding API 调用的最大文档数
      task: "retrieval.passage"         # Jina 任务类型：retrieval.passage | retrieval.query | text-matching
    fts:
      enabled: true                     # 是否构建全文索引
      tokenizer: icu                    # icu（多语言）| simple（英文）| cjk（中日韩）
    vector_index:
      metric: cosine                    # cosine | l2 | ip
    entity_types: [document, url]       # 适用的 entity_type
    input_reps: [canonical_md, vlm_md]  # 可消费的 Rep 类型
```

**Chunking 方法**：

| 方法 | 说明 | 适用场景 | v0.1 |
| --- | --- | --- | --- |
| `markdown_heading` | 按标题切分 + token 阈值 + 滑动窗口（`ChunkingWithSlidingWindowUseCase`） | 结构化文档、API 文档、技术文档 | ✅ 默认 |
| `library` | 完整标题层级保留 + 表格/代码块边界保护 + 滑动窗口 | 知识库/长文档（保留完整 heading_path） | ✅ |
| `fixed_size` | 固定字符数 + 滑窗重叠 | 无标题结构的纯文本 | ✅ |
| `semantic` | 基于 embedding 相似度在语义断点切分 | 长文无明确结构 | v0.2 |
| `sentence` | 按句子边界切分 | 短文本、对话记录 | v0.2 |

**`markdown_heading` 切分规则**（v0.1 默认，对应 `ChunkingWithSlidingWindowUseCase`）：

```text
输入：canonical_md

步骤 1：按标题分割（MarkdownSplitter.split_by_headers）
  ├─ 匹配 H1-H6 标题行
  ├─ 每个标题开始一个新 chunk（标题行归入该 chunk）
  └─ 产出 header_chunks：[{text, header, level, start_pos}]

步骤 2：检测表格边界（TableDetector.find_tables）
  ├─ 识别 Markdown 表格（|...| 行）
  └─ 产出 tables：[{start, end, content}]

步骤 3：按 token 阈值切分（_split_by_tokens）
  ├─ 对每个 header_chunk：
  │   ├─ token_count ≤ chunk_tokens（默认 256）→ 直接保留
  │   ├─ token_count > chunk_tokens → 按段落分割
  │   │   ├─ 段落间合并（不超 chunk_tokens）
  │   │   ├─ 单段落超限 → 按句子切分（。！？.!?）
  │   │   └─ 单句子超限 → 按字符强制截断
  │   └─ 产出 token_chunks：[Chunk(text, start_pos, token_count, metadata)]
  └─ 每个 chunk 的 metadata 包含 {header, level, chunk_type}

步骤 4：应用滑动窗口（_apply_sliding_window）
  ├─ 对每个 chunk i，取窗口 [i - half_window, i + half_window]
  │   （window_size=9 时，half_window=4，窗口覆盖 9 个 chunk）
  ├─ 拼接窗口内所有 chunk 的 embedding_text → 作为当前 chunk 的 embedding_text
  ├─ 如果窗口总长度 > max_window_length（默认 12000）→ 中心优先截断
  │   ├─ 保留中心 chunk 全文
  │   ├─ 从中心向两侧扩展，优先加入较短的邻居
  │   └─ 超限的邻居被跳过
  └─ 产出 windowed_chunks：每个 chunk 保留原始 text，embedding_text 为窗口拼接文本
```

**`library` 切分规则**（知识库场景，保留完整标题层级）：

```text
输入：canonical_md（user_role=library 时自动切换）

步骤 1：提取文档标题（_extract_library_title）
  ├─ 优先从 H1 标题提取
  └─ 回退到文件名（去除 .md 后缀、URL 解码）

步骤 2：按标题切分并保留完整层级（MarkdownSplitter.split_library_sections）
  ├─ 维护 current_headers 字典：{Header 1: "xxx", Header 2: "yyy", ...}
  ├─ 遇到新标题时，清除同级及更低级的旧标题
  └─ 产出 sections：[{metadata: {Header 1: ..., Header 2: ...}, content, start_pos}]

步骤 3：过滤目录块和分隔线
  ├─ _is_library_table_of_contents：检测目录/索引块（链接密度 > 50%）
  └─ _is_library_separator_block：过滤纯分隔线（---/***/___）

步骤 4：构建 embedding 文本
  ├─ heading_levels = "标题1-标题2-标题3"（完整层级路径）
  ├─ embedding_text = "Heading Levels：{heading_levels}。Content：{content}"
  └─ token_count ≤ library_chunk_limit（默认 512）→ 直接保留

步骤 5：超长内容安全切分（_split_library_content）
  ├─ 检测表格边界 + 代码块边界 → 保护区域
  ├─ 在保护区域外寻找自然断点（双换行 > 句号 > 换行）
  ├─ 表格超 max_table_length（默认 3000）→ 强制截断
  └─ 合并切分后的碎片（分隔线、代码围栏）

步骤 6：应用滑动窗口（同 markdown_heading）
```

**Chunk 数据模型**：

```json
{
  "text": "中心块原始文本",
  "embedding_text": "窗口拼接文本（用于向量化）",
  "start_pos": 1234,
  "token_count": 256,
  "chunk_chars": 1024,
  "metadata": {
    "header": "3.2 架构设计",
    "level": 2,
    "chunk_type": "header_chunk | library_markdown | forced_split | ...",
    "heading_levels": "第3章-3.2 架构设计-3.2.1 存储层",
    "anchors": "section-3-2-1",
    "title": "系统设计文档",
    "window_size": 9,
    "window_index": 5,
    "chunk_index": 5
  }
}
```

> **关键设计**：`text` 存储中心块原文（用于检索结果展示），`embedding_text` 存储窗口拼接文本（用于向量化）。两者分离，确保检索命中时展示精确内容，而向量化时利用上下文窗口提升语义理解。

**Embedding 模型选择**：

| 模型 | Provider | 维度 | 特点 | v0.1 |
| --- | --- | --- | --- | --- |
| `jina-embeddings-v5-text-small` | Jina AI | 1024 | 多语言、LoRA 任务适配（retrieval.passage/query/text-matching/code/query-by-table） | ✅ 默认 |
| `jina-embeddings-v5-text-large` | Jina AI | 2048 | 高精度、LoRA 任务适配 | v0.2 |
| `jina-embeddings-v3` | Jina AI | 1024（可配置 256/512/1024/2048） | 多语言、多任务 | 兼容 |
| `bge-m3` | 本地 | 1024 | 多语言、本地部署、无 API 费用 | ✅ |
| `text-embedding-3-small` | OpenAI | 1536 | 英文优化 | v0.2 |
| `text-embedding-3-large` | OpenAI | 3072 | 高精度 | v0.2 |

**维度选择策略**：

| 维度 | 存储成本 | 检索质量 | 适用场景 |
| --- | --- | --- | --- |
| 256 | 最低 | 一般 | 大规模粗筛 |
| 512 | 低 | 较好 | 平衡场景 |
| **1024** | **中** | **好** | **v0.1 默认，推荐** |
| 2048 | 高 | 最佳 | 高精度需求 |

> **同一 Collection 内所有 Entity 必须使用相同的 embedding 模型和维度**。模型/维度变更需要全量重建索引。

**IndexStrategy 与 Ingest Strategy 的关系**：

```text
Ingest Strategy（接入策略）     IndexStrategy（索引策略）
  ┌──────────────────┐          ┌──────────────────┐
  │ 文件/URL → Entity │          │ MD → Chunk → 索引 │
  │                  │          │                  │
  │ · entity_id 策略  │          │ · chunking 方法   │
  │ · 文件过滤       │          │ · embedding 模型  │
  │ · on_conflict    │          │ · 输出维度        │
  └──────────────────┘          └──────────────────┘
         ↓                              ↓
    RepPipeline                    IndexPipeline
```

- Ingest Strategy 决定"用什么 RepPipeline 处理"→ 产出 `canonical_md` / `vlm_md`
- IndexStrategy 决定"用什么参数建索引"→ 产出 Lance 向量索引 + FTS 索引
- 一个 Collection 绑定一个 IndexStrategy（v0.1）；v0.2 支持 per-entity-type 绑定

**v0.1 IndexStrategy 预置**：

| ID | chunking | embedding | dimension | 适用 |
| --- | --- | --- | --- | --- |
| `default_text` | markdown_heading | jina-embeddings-v5-text-small | 1024 | 文档/URL（默认） |
| `library_text` | library | jina-embeddings-v5-text-small | 1024 | 知识库/长文档 |
| `local_text` | markdown_heading | bge-m3 | 1024 | 本地部署场景 |
| `fixed_size_text` | fixed_size | jina-embeddings-v5-text-small | 1024 | 无标题结构的纯文本 |

### 6.9 RepStep / IndexStep 并发模型

> **核心规则**：**Entity 内 RepPipeline 间并行、RepPipeline 内 step 串行、IndexPipeline 串行，Entity 间完全并行**。

#### 6.9.1 并发粒度

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

#### 6.9.2 锁模型

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

#### 6.9.3 失败处理

| 场景 | 处理 |
|---|---|
| RepPipeline 内 step 失败 | 标 `partial_success`；继续执行后续 RepPipeline；下发 `rep_all_ready` 时附带 `failed_steps` |
| RepPipeline 整体失败（所有 step 失败） | 标 `failed`；不发 `rep_all_ready`；告警；3 次重试后入 DLQ |
| IndexPipeline 失败 | 标 `index_status=failed`；不影响 Rep；下次 Reconciler 重试 |
| ProjectorStep 失败 | 标 Projector 失败；不影响 Rep 和 Index；告警 |
| RepPipeline 死锁 / 超时 | Orchestrator 设全局超时（默认 10 min/step）；超时标 failed |

#### 6.9.4 配额

| 资源 | 默认配额 | 触发降级 |
|---|---|---|
| 同 Entity 并行 RepPipeline | 3 | 队列等待 |
| 全局并发 RepStep | 50 | 队列等待 |
| 全局并发 IndexStep | 20 | 队列等待 |
| 单 RepStep LLM 调用并发 | 5（per worker） | 队列等待 |
| 单 RepStep 显存占用 | 8 GB | 失败 + 降级到 CPU |

### 6.10 任务队列：Redis Streams（v0.1 选定）

> **设计决策**：v0.1 使用 **Redis Streams** 作为任务队列，**不使用 Celery / Kafka**。
>
> **理由**：
> - Celery 不可靠的根因是抽象层太多（broker → worker → result backend → serialization），不是 Redis 的问题
> - 直接用 Redis Streams 原语 = 去掉 Celery 这层抽象 = 更可靠
> - Kafka 对 v0.1 规模过重（Entity 级消息量低，不需要分区 / 副本 / 持久化）
> - Redis 已是 Vector-Lake 的依赖（VFS 缓存 + 锁），不引入新组件

#### 6.10.1 Stream 拓扑

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

#### 6.10.2 消息格式

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

#### 6.10.3 消费协议

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

#### 6.10.4 可靠性保证

| 场景 | Redis Streams 机制 | 效果 |
|---|---|---|
| Worker 正常处理 | `XACK` 确认 | 消息不再投递 |
| Worker OOM / 被杀 | 未 ACK 的消息 | `XAUTOCLAIM` 自动 reclaim（超时 5 min） |
| 消息积压 | `XINFO STREAM` + `XPENDING` | 监控 + 告警 |
| 重复消费 | `XACK` 幂等 + RepStep 幂等（基于 content_hash） | 安全 |
| 消息丢失 | Redis AOF / RDB 持久化 | 重启后恢复 |
| 死信 | 超过 max_retries → `stream:dead_letter` | 人工处理 |

#### 6.10.5 与 Celery 的对比

| 维度 | Celery + Redis | Redis Streams 直连 |
|---|---|---|
| **可靠性** | 低（worker OOM 丢任务、chord 不可靠） | 高（XAUTOCLAIM 自动重试） |
| **抽象层** | broker + worker + result backend + serialization | XADD / XREADGROUP / XACK |
| **可观测** | 需 Flower / Celery events | `XINFO` / `XPENDING` 原生 |
| **依赖** | Celery + Redis + (result backend) | Redis only |
| **序列化** | pickle / json / msgpack（兼容性问题） | 纯 dict（无序列化层） |
| **延迟** | 高（broker → worker → result） | 低（直连 Redis） |
| **运维** | 复杂（worker 进程管理 + concurrency pool） | 简单（asyncio + Consumer Group） |

#### 6.10.6 背压策略

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

#### 6.10.7 v0.2 演进路径

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

### 6.11 Redis Key 命名规范

> **全局前缀**：所有 Key 以 `vl:` 开头，避免与其他应用冲突。

| Key 模式 | 类型 | 用途 | TTL |
| --- | --- | --- | --- |
| `vl:lock:rep:{ws}:{col}:{entity_id}:{rep_type}` | String | RepPipeline 级分布式锁 | 300s（step_timeout） |
| `vl:lock:index:{ws}:{col}:{entity_id}:{index_type}` | String | IndexPipeline 级分布式锁 | 300s |
| `vl:lock:watch:entity:{entity_id}` | String | Watch 竞态锁 | 60s |
| `vl:stream:rep:{ws}:{col}` | Stream | RepPipeline 任务流 | 无限 |
| `vl:stream:index:{ws}:{col}` | Stream | IndexPipeline 任务流 | 无限 |
| `vl:stream:watch:{ws}` | Stream | Watch 事件流 | 无限 |
| `vl:cg:rep-worker:{ws}:{col}` | Consumer Group | Rep Worker 消费组 | — |
| `vl:cg:index-worker:{ws}:{col}` | Consumer Group | Index Worker 消费组 | — |
| `vl:processed:{ws}:{col}:{entity_id}:{event_id}` | String | 事件去重标记 | 24h |
| `vl:etag:{ws}:{col}:{entity_id}` | String | 上次处理的 ETag | 7d |
| `vl:entity:status:{ws}:{col}:{entity_id}` | Hash | Entity 运行时状态 | 无限 |
| `vl:rep:status:{ws}:{col}:{entity_id}:{rep_type}` | Hash | Rep 运行时状态 | 无限 |
| `vl:index:status:{ws}:{col}:{entity_id}:{index_type}` | Hash | Index 运行时状态 | 无限 |
| `vl:dead-letter:{ws}` | Stream | Dead Letter 队列 | retention_days |
| `vl:stats:{ws}` | Hash | Workspace 统计计数器 | 无限 |

**命名规则**：
- 层级用 `:` 分隔
- 动态部分用 `{placeholder}` 表示
- TTL 优先使用可配置值（如 `step_timeout`、`retention_days`）
- Consumer Group 名 = `vl:cg:{角色}:{ws}:{col}`

---

## 7. 多模态 Embedding 策略

> v0.1 待补充，详见 §25.5 评审清单。

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
| `vlm_md` | Markdown 渲染 | 同 canonical_md |
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
    { "rep_type": "vlm_md", "status": "ready", "preview_url": "/preview/abc123?rep_type=vlm_md" },
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
      │    │    vlm_md            image_emb
      ▼    ▼
  mind_map summary
      │
      ▼
   graph_json

   ← 点击 vlm_md → 预览 VLM 提取结果
   ← 高亮 raw → page_image → vlm_md 链路
   ← 右键 page_image → "查看影响" → 高亮 vlm_md, image_emb
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

### 8.6 DuckDB 统一访问 — 表格型 Entity 的 SQL 查询

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
| **§8.6 DuckDB SQL** | **`capability_structural`** | **数值 / 聚合 / JOIN** | **TableRow** |
| **§8.6 DuckDB 联邦** | **`capability_structural_federated`** | **跨表 JOIN** | **TableRow（多 Entity）** |
| **§8.6 DuckDB + Lance** | **`capability_hybrid_structural_semantic`** | **结构化 + 语义** | **TableRow + Chunk** |

### 9.5 API Reference（v0.1 端点汇总）

> 以下为 v0.1 全部 REST API 端点集中汇总。各端点的详细请求/响应格式见对应章节。

#### 9.5.1 Entity 管理

| 方法 | 路径 | 说明 | 章节 |
| --- | --- | --- | --- |
| POST | `/api/v1/workspaces/{ws}/collections/{col}/entities` | 创建 Entity（上传文件或指定 URL） | §9.1 |
| GET | `/api/v1/workspaces/{ws}/collections/{col}/entities` | 列出 Entity（分页 + 过滤） | §9.1 |
| GET | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}` | 获取 Entity 详情 | §9.1 |
| PATCH | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}` | 更新 Entity 元数据（labels/status） | §9.1 |
| DELETE | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}` | 删除 Entity（逻辑删除） | §9.1 |

#### 9.5.2 Representation 管理

| 方法 | 路径 | 说明 | 章节 |
| --- | --- | --- | --- |
| GET | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}/representations` | 列出所有 Rep | §9.1 |
| GET | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}/representations/{rep_type}` | 获取指定 Rep 内容 | §9.1 |
| POST | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}/representations/{rep_type}/rebuild` | 触发 Rep 重建 | §9.1 |

#### 9.5.3 搜索与检索

| 方法 | 路径 | 说明 | 章节 |
| --- | --- | --- | --- |
| POST | `/api/v1/workspaces/{ws}/collections/{col}/search` | 混合检索（语义 + 全文 + 结构化） | §8 |
| POST | `/api/v1/workspaces/{ws}/collections/{col}/query` | SQL 查询（DuckDB） | §8.6 |
| GET | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}/anchor-jump` | 锚点跳转 | §4.3.1 |

#### 9.5.4 Lineage 与一致性

| 方法 | 路径 | 说明 | 章节 |
| --- | --- | --- | --- |
| GET | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}/lineage` | 查询血缘关系 | §5.13.4 |
| GET | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}/consistency` | 一致性校验状态 | §5.9 |
| POST | `/api/v1/workspaces/{ws}/collections/{col}/entities/{entity_id}/reconcile` | 手动触发 Reconciler | §5.9 |

#### 9.5.5 Watch / Ingest Strategy 管理

| 方法 | 路径 | 说明 | 章节 |
| --- | --- | --- | --- |
| GET | `/api/v1/workspaces/{ws}/watch-strategies` | 列出 Watch Strategy | §5.15.11.9 |
| POST | `/api/v1/workspaces/{ws}/watch-strategies` | 创建 Watch Strategy | §5.15.11.9 |
| GET | `/api/v1/workspaces/{ws}/watch-strategies/{id}` | 查看 Watch Strategy 详情 | §5.15.11.9 |
| PATCH | `/api/v1/workspaces/{ws}/watch-strategies/{id}` | 更新 Watch Strategy | §5.15.11.9 |
| DELETE | `/api/v1/workspaces/{ws}/watch-strategies/{id}` | 删除 Watch Strategy | §5.15.11.9 |
| POST | `/api/v1/workspaces/{ws}/watch-strategies/{id}/pause` | 暂停 Watch | §5.15.11.9 |
| POST | `/api/v1/workspaces/{ws}/watch-strategies/{id}/resume` | 恢复 Watch | §5.15.11.9 |
| GET | `/api/v1/workspaces/{ws}/ingest-strategies` | 列出 Ingest Strategy | §5.15.11.9 |
| GET | `/api/v1/workspaces/{ws}/ingest-strategies/{id}` | 查看 Ingest Strategy 详情 | §5.15.11.9 |
| PATCH | `/api/v1/workspaces/{ws}/ingest-strategies/{id}` | 更新 Ingest Strategy | §5.15.11.9 |

#### 9.5.6 Dead Letter 管理

| 方法 | 路径 | 说明 | 章节 |
| --- | --- | --- | --- |
| GET | `/api/v1/workspaces/{ws}/dead-letters` | 列出 Dead Letter | §5.15.8 |
| POST | `/api/v1/workspaces/{ws}/dead-letters/{id}/replay` | 重试 Dead Letter | §5.15.8 |
| POST | `/api/v1/workspaces/{ws}/dead-letters/cleanup` | 清理过期 Dead Letter | §5.15.8 |

#### 9.5.7 可观测性

| 方法 | 路径 | 说明 | 章节 |
| --- | --- | --- | --- |
| GET | `/api/v1/workspaces/{ws}/stats` | Workspace 统计 | §5.15.9 |
| GET | `/api/v1/workspaces/{ws}/changes/stats` | 变动统计 | §5.14.11 |
| GET | `/metrics` | Prometheus 指标 | §5.15.9 |
| GET | `/health` | 健康检查 | §20 |

#### 9.5.8 MCP Tool（VFS）

| Tool | 说明 | 章节 |
| --- | --- | --- |
| `vfs_ls` | 列出目录 | §8.1 |
| `vfs_stat` | 文件元信息 | §8.1 |
| `vfs_read` | 读取文件内容 | §8.1 |
| `vfs_glob` | 模式匹配搜索 | §8.1 |
| `vfs_grep` | 内容搜索 | §8.1 |
| `search` | 语义+全文混合检索 | §8.3 |
| `watch_list` | 列出 Watch Strategy | §5.15.11.9 |
| `watch_status` | Watch 运行状态 | §5.15.11.9 |

### 9.6 VFS MCP Server（向 LLM 暴露 Lake）

> **设计目标**：让 LLM（Claude / GPT / 开源模型）通过 **MCP (Model Context Protocol)** 直接浏览和查询 Vector-Lake，无需人工写 API 调用。
>
> **为什么选 MCP**：
> - MCP 是 LLM 工具调用的事实标准（Claude Desktop / Cursor / VS Code / 开源 Agent 框架都支持）
> - MCP 自带 schema 描述（LLM 自动知道怎么调用，不需要手写 function calling schema）
> - MCP 支持 stdio（本地）和 SSE（远程）两种传输
> - 比 REST API + OpenAPI spec 更轻量（一个 Python 文件即可启动）

#### 9.6.1 MCP Tools 定义

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
    """读取 Rep 文件内容（仅文本类 Rep：canonical_md / vlm_md / summary / table_schema）"""
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

#### 9.6.2 部署模式

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

#### 9.6.3 MCP Tools 与 §9 智能引擎的映射

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

#### 9.6.4 v0.1 范围

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

### 9.7 HTTP 错误码定义

| HTTP 状态码 | 错误码 | 说明 | 典型场景 |
| --- | --- | --- | --- |
| 400 | `INVALID_REQUEST` | 请求参数不合法 | 缺少必填字段 / 格式错误 |
| 401 | `UNAUTHORIZED` | 未认证 | 缺少 API Key |
| 403 | `FORBIDDEN` | 无权限 | 跨 workspace 访问 |
| 404 | `NOT_FOUND` | 资源不存在 | Entity / Rep / Index 不存在 |
| 409 | `CONFLICT` | 资源冲突 | 同 URL Entity 已存在 / Ingest Strategy 绑定中不可删除 |
| 422 | `UNPROCESSABLE` | 业务逻辑不合法 | 不支持的文件格式 / Pipeline 配置错误 |
| 429 | `RATE_LIMITED` | 请求限流 | 超过 QPS / 配额限制 |
| 500 | `INTERNAL_ERROR` | 内部错误 | 未预期异常 |
| 502 | `UPSTREAM_ERROR` | 上游服务错误 | Embedding API 超时 / VLM API 不可用 |
| 503 | `SERVICE_UNAVAILABLE` | 服务暂不可用 | Reconciler 正在启动 / 维护模式 |

**错误响应格式**：

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Entity already exists with source_url=https://example.com/doc",
    "details": {
      "entity_id": "abc123",
      "conflict_field": "source_url"
    }
  }
}
```

**v0.1 限制**：错误码不细分子类型，`details` 为可选扩展字段。

### 9.8 认证与授权（v0.1：API Key）

> v0.1 采用最简方案：**workspace 级 API Key**。v0.2 扩展为 OAuth2 + RBAC。

**认证方式**：

| 方式 | Header | 示例 | v0.1 |
| --- | --- | --- | --- |
| API Key | `X-API-Key: {key}` | `X-API-Key: vl_ws001_abc123` | ✅ |
| Bearer Token | `Authorization: Bearer {token}` | v0.2 OAuth2 | ❌ |

**授权模型**：

```
API Key → workspace_id → 该 workspace 下所有资源
```

- 1 个 API Key 绑定 1 个 workspace
- API Key 在 config.yaml 中配置（`auth.api_keys`）
- 跨 workspace 访问返回 403
- v0.2 新增 `cross_workspace_read` 显式授权

**权限分级**（v0.2 实现，v0.1 全部为 admin）：

| 角色 | 权限 | v0.1 |
| --- | --- | --- |
| `admin` | 全部操作 | ✅（默认） |
| `write` | 创建/更新/删除 Entity + 触发 Pipeline | v0.2 |
| `read` | 查询/搜索/预览 | v0.2 |

**MCP Server 认证**：
- MCP Tool 调用通过 `X-API-Key` header 传递
- 每个 MCP session 绑定一个 workspace

---

## 10. 设计原则（不可妥协）

> v0.1 待补充，详见 §25.5 评审清单。

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
| `rep_pipeline_url` | URL 抓取+解析 | `fetch_url` → `parse_html` | document | ✅ |
| `rep_pipeline_b` | 视觉识别 | `convert_to_pdf`（办公文档时）→ `render_page` → `visual_recognize` | document | ✅ |
| `rep_pipeline_e` | 图片渲染 | `render_page` | document, image | ✅ |
| `rep_pipeline_f` | 音频转写 | `transcribe` | audio | ✅ |
| `rep_pipeline_g` | 表格获取 | `table_parse` | table | ✅ |
| `rep_pipeline_d_mind_map` | 脑图编译 | `compile_mind_map` | document | v0.2 |
| `rep_pipeline_d_graph` | 关系图编译 | `compile_graph_json` | document | v0.2 |
| `rep_pipeline_d_summary` | 摘要编译 | `compile_summary` | document | v0.2 |
| `rep_pipeline_d_wiki` | Wiki 编译 | `compile_wiki_md` | document | v0.2 |

> RepPipeline 编号约定：`rep_pipeline_<family>[_<variant>]`，family = a/b/d/e/f/g/h。

### 13.3 IndexPipeline（v0.1 内置）

| pipeline_id | name | steps | required_reps | v0.1 |
|---|---|---|---|---|
| `index_pipeline_text` | 文本索引 | `chunk_and_embed_text` → `build_vector_index` → `build_fts_index` | `canonical_md` / `vlm_md`（任一） | ✅ |
| `index_pipeline_image` | 图片索引 | `chunk_and_embed_image` → `build_vector_index` | `page_image` | ✅ |
| `index_pipeline_video` | 视频双模态索引 | `chunk_and_embed_audio` → `build_vector_index` → `chunk_and_embed_image` → `build_vector_index` | `transcript` + `keyframe_image` | ✅ |
| `index_pipeline_structural` | 结构化检索 | `register_duckdb_view` | `table_parquet` | ✅ |
| `index_pipeline_audio` | 音频索引（纯音频） | `chunk_and_embed_audio` → `build_vector_index` | `transcript` | v0.2 |
| `index_pipeline_graph` | 图索引 | `build_graph_index` | `graph_json` | v0.2 |
| `index_pipeline_table` | 表格文本索引 | `chunk_and_embed_table` → `build_vector_index` | `table_md` / `table_json` | v0.2 |

### 13.4 ProjectorStep（v0.1 内置）

| projector | registered_as | 目标消费者 | 状态 |
|---|---|---|---|
| `RagApiProjectorStep` | `project_rag_api` | 上层 RAG / Agent（§8 检索 API 路由） | ✅ v0.1 |
| `WikiProjectorStep` | `project_wiki` | Karpathy LLM Wiki / Obsidian（§12） | v0.2（依赖 `compile_wiki_md`） |
| `DashboardProjectorStep` | `project_dashboard` | 运维面板 | v0.2 |
| `WebProjectorStep` | `project_web` | 前端 SPA | v0.2 |

### 13.5 Rep

```text
raw · canonical_md · plain_text · page_image · vlm_md
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
| | 100 页 PDF → `vlm_md`（Pipeline B）P95 | ≤ 90 s |
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

> v0.1 待补充，详见 §25.5 评审清单。

| 场景 | 触发 | 期望 |
| --- | --- | --- |
| **S1. PDF 全文检索** | 录入 pricing.pdf | hybrid (semantic + lexical) 命中；带页码 + section snippet |
| **S2. PDF 双流水线** | 同一 PDF 走 Pipeline A + B | canonical_md 和 vlm_md 的 chunks 都可被检索到 |
| **S3. 图片反查** | 录入 chart.png | 用文本"柱状图" → visual 命中 |
| **S4. 录音转写检索** | 录入 meeting.wav | 用文本"Q3 定价" → 命中 transcript_segment + audio 时间戳 |
| **S5. 隐藏不删** | 把 doc 标 hidden | 检索默认不可见；`include_hidden=true` 仍可取 |
| **S6. 软删除** | 标 deleted | OSS 原文件保留；chunks 软删除；UI 不可见 |
| **S7. 版本切换** | raw 更新 | 旧版本 active 直到新版本 publish 成功；检索无中断 |
| **S8. Reconcile** | content_hash 变化 | reconcile 检测到变化，触发 pipeline 重跑 |
| **S9. Pipeline 追加** | 注册新 pipeline | 对已有 entity 按需重跑；不影响已有 representation |
| **S10. 视角预览** | 检索命中 pricing.pdf 的 chunk | 点击 → 预览 canonical_md（定位到第7页）；切换 → 预览 page_image / vlm_md / mind_map |
| **S11. 视角面板** | 打开 entity 详情 | 列出所有可用 representation + 状态 + preview_url；skipped/failed 的灰显 |
| **S12. 血缘级联失效** | raw 更新（content_hash 变化） | 沿 lineage 级联：page_image/vlm_md/canonical_md 全部标 stale；对应 chunks 检索不再命中 |
| **S13. 血缘级联重建** | S12 之后 | pipeline 自动重跑；新 representation ready → chunks active → 检索恢复 |
| **S14. 中间节点失效** | page_image 重建失败 | 下游 vlm_md 保持 stale；上游 canonical_md 不受影响（不同 lineage 分支） |
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

> v0.1 待补充，详见 §25.5 评审清单。

| 里程碑 | 周期 | 交付 |
| --- | --- | --- |
| **M0. Schema 冻结** | W1 | Entity / Representation / Chunk / Edge / Pipeline schema review 通过 |
| **M1. Ingest + Detect** | W2 | raw → entity + detect 跑通；content_hash 落盘 |
| **M2. Pipeline A (直接提取)** | W3-4 | canonical_md → chunks → text embedding → semantic index |
| **M3. Pipeline B (VLM)** | W5 | page_image → vlm_md → chunks → text embedding |
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
| R1 | 文档版面解析准确率影响 canonical_md 质量 | quality 字段记录 confidence；fallback 到 vlm_md |
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

## 19. 开源技术选型与复用清单

> **目的**：Vector-Lake 系统构建优先复用成熟开源项目，只对特有能力（Entity 抽象、RepPipeline/IndexPipeline 双管线、Projector、Two-phase 一致性）做自研。本节定义 7 大类别的开源技术栈与复用路线图。
>
> **完整清单与对比**：见 [OPEN_SOURCE_STACK.md](file:///workspace/OPEN_SOURCE_STACK.md)（含 50+ 开源项目对比、7 大类别全景图、v0.1/v0.2/v0.3 复用路线图）。

### 19.1 7 大类别速查

| 类别 | 核心需求 | v0.1 选定 | v0.2 候选 |
|---|---|---|---|
| **1. 对象存储** | Entity / Rep / Index 数据落盘 | 阿里云 OSS / AWS S3 / MinIO | Apache Ozone（超大规模） |
| **2. 数据同步** | 跨桶/跨云/增量 | **juicefs sync** / **rclone** | s3sync / SeaTunnel |
| **3. 向量检索** | 多模态 RAG 检索 | **LanceDB** ✅ | — |
| **4. Pipeline 编排** | Rep/Index/Projector 调度 | 自研 RepStep/IndexStep 调度 | **Dagster**（资产为中心） |
| **5. 元数据治理** | Entity 发现 / 血缘 / 治理 | 自研 VFS | **OpenMetadata** |
| **6. 可观测性** | 监控 / 告警 / 日志 / Trace | **Prometheus + Grafana + OTel** | — |
| **7. Lake Format** | 表格式 / 版本控制 | Lance 协议 ✅ | 借鉴 Iceberg / Delta 设计 |

### 19.2 v0.1 推荐技术栈（最小可用集）

```text
┌──────────────────────────────────────────────────────────────┐
│  Vector-Lake v0.1 Stack                                       │
│                                                               │
│  Storage:        阿里云 OSS / S3 / MinIO                     │
│  Event:          OSS Event Notification / MinIO Webhook      │
│  Vector:         LanceDB（embedded）                         │
│  Pipeline:       自研 RepStep / IndexStep 调度（§6）          │
│  Queue:          Redis Streams（§6.9，不使用 Celery）         │
│  VFS→LLM:        MCP Server（§9.6，stdio / SSE）             │
│  Config:         YAML + 环境变量                              │
│  Observability:  OpenTelemetry + Prometheus + Grafana        │
│  Errors:         Sentry                                       │
└──────────────────────────────────────────────────────────────┘
```

### 19.3 v0.2 引入候选

| 项目 | 引入理由 | 复用范围 |
|---|---|---|
| **Dagster** | 资产为中心与 Entity 模型完美契合 | RepPipeline / IndexPipeline 编排 |
| **Temporal** | 持久执行 + 状态机 | Reconciler 周期任务 + Pipeline 失败重试 |
| **OpenMetadata** | 一体化数据治理 | Entity 血缘可视化 + 数据质量 |
| **Apache Kafka** | 跨服务事件 + 可靠重试 | OSS 事件 + RepStep 异步执行 |
| **JuiceFS** | POSIX 视角访问 OSS | VFS 文件级操作优化 |
| **lakeFS** | Git-like 数据湖版本控制 | Entity 零拷贝快照 / 分支（v0.3） |

### 19.4 OSS 事件通知集成模式

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

### 19.5 关键开源项目 GitHub 链接（v0.1/v0.2 直接相关）

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

### 19.6 关键决策记录

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

### 19.7 config.yaml 完整 Schema（v0.1）

> v0.1 全部配置项集中定义。运行时可通过 API 热更新的字段标注 `🔥`。

```yaml
# vector-lake config.yaml — v0.1

server:
  host: "0.0.0.0"
  port: 8000
  workers: 4                          # API Server worker 数
  cors_origins: ["*"]

storage:
  backend: oss                        # oss | s3 | minio | local
  oss:
    endpoint: "https://oss-cn-hangzhou.aliyuncs.com"
    bucket: "vector-lake"
    access_key_id: "${OSS_ACCESS_KEY_ID}"
    access_key_secret: "${OSS_ACCESS_KEY_SECRET}"
    prefix: "vector-lake"             # OSS 根前缀
  local:                              # backend=local 时使用
    root: "./data"

lance:
  data_dir: "./lance_data"            # LanceDB 数据目录
  cache_size_mb: 512                  # Lance 读缓存

redis:
  url: "redis://localhost:6379/0"
  max_connections: 20
  key_prefix: "vl"                    # 全局 key 前缀

embedding:
  default_model: "jina-embeddings-v5-text-small"
  models:
    jina-embeddings-v5-text-small:
      provider: jina
      api_key: "${JINA_API_KEY}"
      dimension: 1024
      max_batch_size: 64
      task_type: "retrieval.passage"     # LoRA 任务适配：retrieval.passage | retrieval.query | text-matching | code | query-by-table
    jina-embeddings-v5-text-large:
      provider: jina
      api_key: "${JINA_API_KEY}"
      dimension: 2048
      max_batch_size: 32
      task_type: "retrieval.passage"
    bge-m3:
      provider: local
      model_path: "./models/bge-m3"
      dimension: 1024

vlm:
  default_model: "qwen-vl-max"
  models:
    qwen-vl-max:
      provider: dashscope
      api_key: "${DASHSCOPE_API_KEY}"
      max_pages_per_minute: 30
    gpt-4o:
      provider: openai
      api_key: "${OPENAI_API_KEY}"
      max_pages_per_minute: 20

pipeline:
  max_concurrent_rep: 8               # 同一 Entity 最大并发 RepPipeline
  max_concurrent_index: 4             # 同一 Entity 最大并发 IndexPipeline
  step_timeout: 300                   # 单步超时（秒）
  retry_max: 3
  retry_backoff: exponential          # linear | exponential

reconciler:
  enabled: true
  poll_interval: 60                   # 扫描间隔（秒）
  batch_size: 100                     # 每次扫描 Entity 数
  phase0_on_startup: true             # 启动时执行 Phase 0 全量校验

watch:
  enabled: true
  file_stable_period: 30              # 文件稳定期（秒）
  batch_flush_interval: 5             # 批量聚合间隔（秒）
  buffer_limit: 10000                 # 缓冲队列上限
  dead_letter:
    retention_days: 7
    cleanup_interval: 3600            # 清理间隔（秒）
    max_total_size_gb: 10
    retry_schedule: [300, 3600, 21600] # 重试间隔（秒）：5min, 1h, 6h

convert_to_pdf:
  libreoffice_path: "/usr/bin/soffice"
  timeout: 120                        # 转换超时（秒）
  max_concurrent: 4                   # 最大并发转换数

fetch_url:
  timeout: 30                         # HTTP 请求超时（秒）
  follow_redirects: true
  max_content_size: 52428800          # 50MB
  user_agent: "VectorLake/0.1"
  default_poll_interval: 3600         # URL 变更检测间隔（秒）

auth:
  enabled: true                       # v0.1: workspace 级 API Key
  type: api_key                       # api_key（v0.1）| oauth2（v0.2）
  api_keys:                           # workspace → API Key 映射
    ws_001: "${WS_001_API_KEY}"
    ws_002: "${WS_002_API_KEY}"

logging:
  level: INFO
  format: json                        # json | text
  output: stdout                      # stdout | file
  file_path: "./logs/vector-lake.log"

metrics:
  enabled: true
  port: 9090                          # Prometheus metrics 端口
  path: "/metrics"
```

**环境变量注入**：所有 `${VAR}` 格式的值从环境变量读取，未设置时启动报错。

**热更新字段**（通过 PATCH API 修改，无需重启）：
- `watch.dead_letter.retention_days` 🔥
- `watch.dead_letter.cleanup_interval` 🔥
- `watch.file_stable_period` 🔥
- `pipeline.step_timeout` 🔥
- `reconciler.poll_interval` 🔥
- `fetch_url.default_poll_interval` 🔥

---

## 20. 部署模型与运维

### 20.1 部署拓扑

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

### 20.2 组件说明

| 组件 | 职责 | 扩缩容 | 推荐资源 |
| --- | --- | --- | --- |
| **API Server** | REST API（§14）+ MCP HTTP 端点 | 水平扩展（无状态） | 2 CPU, 2 GB RAM |
| **MCP Server** | LLM 工具调用（stdio / SSE） | 按需启动（每个 LLM 会话一个实例） | 1 CPU, 1 GB RAM |
| **Reconciler** | 周期一致性检查（§5.9） | 单实例（通过 Redis 锁保证） | 2 CPU, 2 GB RAM |
| **Worker** | RepPipeline / IndexPipeline / Projector 执行 | 水平扩展（按队列深度） | 2-4 CPU, 4-8 GB RAM |
| **Redis** | 任务队列 + 分布式锁 + VFS 缓存 | 单实例（v0.1），哨兵（v0.2） | 2 CPU, 4 GB RAM |
| **OSS / MinIO** | Entity / Rep / LanceDB 数据存储 | 外部依赖 | 按数据量 |

### 20.3 Docker Compose 部署（推荐 v0.1）

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

### 20.4 配置文件

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

### 20.5 健康检查

| 端点 | 用途 | 返回 |
| --- | --- | --- |
| `GET /health` | 基本存活检查 | `{"status": "ok"}` |
| `GET /health/ready` | 就绪检查（含 Redis + OSS 连通性） | `{"status": "ready", "checks": {"redis": true, "storage": true}}` |
| `GET /health/live` | Kubernetes liveness probe | `{"status": "alive"}` |
| `GET /metrics` | Prometheus metrics | 标准 OpenMetrics 格式 |

### 20.6 启动顺序

```text
1. Redis / MinIO 启动（docker-compose 自动处理）
2. API Server 启动 → 等待 Redis + MinIO 就绪
3. Worker 启动 → 连接 Redis Streams Consumer Group
4. Watch Listener 启动 → 加载 Watch Strategy 配置 → 连接 OSS EventNotification / inotify → 注册 Redis Streams Producer
5. Reconciler 启动 → 获取 Redis 分布式锁，开始周期检查
6. MCP Server 按需启动（LLM 会话建立时）
```

**Watch Listener 启动细节**：

```text
Watch Listener 启动流程：
  │
  ▼
[1] 加载 config.yaml 中的 watch_strategies + ingest_strategies
  │
  ▼
[2] 配置校验
  ├─ 检查 prefix 重叠冲突（§5.15.11.5）
  ├─ 检查 ingest_strategy 引用是否存在
  ├─ 检查 workspace/collection 权限
  └─ 校验失败 → state=error + 告警
  │
  ▼
[3] 初始化 OSS EventNotification / inotify 监听
  ├─ OSS: 配置 S3 EventNotification → SQS/SNS → Watch Listener
  ├─ OSS (Aliyun): 配置 OSS MNS → Watch Listener
  └─ Local: inotify 监听本地目录
  │
  ▼
[4] 注册 Redis Streams Producer（vl:watch_ingest）
  │
  ▼
[5] 状态上报 → state=active + Prometheus watch_strategy_state=1
  │
  ▼
[6] 开始接收事件 → 进入 §5.15.2 自动构建流程
```

### 20.7 优雅关闭

```text
1. SIGTERM → API Server 停止接受新请求
2. Watch Listener 停止接收新事件 → 缓冲队列中的事件继续投递到 Redis Streams（不丢）
3. Worker 完成当前正在执行的 Pipeline Step（不中断）
4. Reconciler 完成当前批次后释放锁
5. 所有组件关闭 Redis 连接
6. SIGKILL（超时 30s 后强制终止）
```

**Watch Listener 关闭细节**：

```text
Watch Listener 关闭流程：
  │
  ▼
[1] 收到 SIGTERM → 停止接收 OSS/inotify 新事件
  │
  ▼
[2] 缓冲队列处理
  ├─ Redis Streams 缓冲队列 ≤ 10000 条 → 继续投递
  ├─ 缓冲队列 > 10000 → 超出部分写入本地暂存（重启后恢复）
  └─ 等待队列中的事件全部投递完成（最长 10s）
  │
  ▼
[3] 状态上报 → state=stopped + Prometheus watch_strategy_state=0
  │
  ▼
[4] 关闭 OSS EventNotification / inotify 连接
  │
  ▼
[5] 关闭 Redis Streams Producer 连接
```

### 20.8 运维命令

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f api worker watch-listener

# 扩容 Worker
docker-compose up -d --scale worker=4

# 手动触发 Reconciler
vector-lake reconcile --once

# 手动重建指定 Entity
vector-lake entity rebuild --entity-id <id> --pipeline canonical_md

# 查看 Stream 队列深度
vector-lake queue status

# Watch Strategy 管理
vector-lake watch list                           # 列出所有 Watch Strategy
vector-lake watch status <strategy_id>           # 查看单个 Strategy 状态
vector-lake watch pause <strategy_id>            # 暂停
vector-lake watch resume <strategy_id>           # 恢复
vector-lake watch replay <strategy_id> --from 2026-06-01 --to 2026-06-06  # 补单

# Ingest Strategy 管理
vector-lake ingest list                          # 列出所有 Ingest Strategy
vector-lake ingest show <strategy_id>            # 查看详情 + bound Watch Strategy
vector-lake ingest update <strategy_id> --set allowed_extensions=.pdf,.md  # 热更新

# Dead Letter 管理
vector-lake dead-letter list <strategy_id> --limit 20  # 查看死信
vector-lake dead-letter replay <error_id>              # 重放单个死信
vector-lake dead-letter cleanup --older-than 30d      # 清理过期死信

# 清理软删除过期数据
vector-lake cleanup --dry-run
vector-lake cleanup --force
```

---

## 21. SDK 与客户端策略

### 21.1 Python SDK（v0.1 主推）

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

### 21.2 CLI 工具

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

### 21.3 MCP 客户端集成（LLM 使用）

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

LLM 通过 MCP 自动获得以下工具（§9.6.3）：

| 工具 | 功能 |
| --- | --- |
| `vl_search` | 语义/混合检索 |
| `vl_list_entities` | 列出 Entity |
| `vl_get_entity` | 获取 Entity 详情 |
| `vl_get_representation` | 获取 Representation 内容 |
| `vl_get_lineage` | 获取血缘 |
| `vl_list_workspaces` | 列出可用工作空间 |

### 21.4 SDK 设计原则

1. **同步 API 优先** — 检索类操作同步返回，Pipeline 触发异步但可 await
2. **类型安全** — 所有方法有完整的类型注解（Pydantic models）
3. **错误可恢复** — 网络重试 + 指数退避（默认 3 次）
4. **连接池** — httpx 异步客户端，连接复用
5. **分页** — 列表类 API 统一使用 `limit` + `cursor` 分页
6. **日志透传** — SDK 端日志级别可配置，方便调试

### 21.5 多语言 SDK 路线图

| 语言 | v0.1 | v0.2 | 备注 |
| --- | --- | --- | --- |
| **Python** | 完整 SDK | 异步 + 流式 | 主推 |
| **TypeScript** | — | 检索 + MCP | 前端 / Node.js |
| **Go** | — | 高性能 Worker | 内部 Worker 实现 |
| **Rust** | — | — | v0.3 评估 |

---

## 22. 错误模型与故障排查

### 22.1 错误码体系

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

### 22.2 错误分类

| 类别 | HTTP 状态码 | 前缀 | 示例 | 重试策略 |
| --- | --- | --- | --- | --- |
| **客户端错误** | 400 | `INVALID_*` | `INVALID_WORKSPACE`, `INVALID_FILTER` | 不可重试 |
| **资源不存在** | 404 | `*_NOT_FOUND` | `ENTITY_NOT_FOUND`, `REP_NOT_FOUND` | 不可重试 |
| **冲突** | 409 | `*_CONFLICT` | `ENTITY_ALREADY_EXISTS`, `PIPELINE_LOCKED` | 可重试（等锁释放） |
| **服务端错误** | 500 | `INTERNAL_*` | `INTERNAL_ERROR`, `STORAGE_UNAVAILABLE` | 可重试（指数退避） |
| **服务不可用** | 503 | `*_UNAVAILABLE` | `REDIS_UNAVAILABLE`, `OSS_UNAVAILABLE` | 可重试（指数退避） |
| **Pipeline 错误** | 422 | `PIPELINE_*` | `PIPELINE_STEP_FAILED`, `PIPELINE_TIMEOUT` | 部分可重试 |
| **索引错误** | 422 | `INDEX_*` | `INDEX_BUILD_FAILED`, `INDEX_STALE` | 可重试（重建） |

### 22.3 完整错误码列表

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

### 22.4 故障排查指南

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

### 22.5 日志规范

| 日志级别 | 使用场景 | 示例 |
| --- | --- | --- |
| **DEBUG** | 开发调试、Pipeline Step 详细执行 | `RepStep extract started for entity=pricing-2025` |
| **INFO** | 正常业务流程 | `Entity pricing-2025 rep canonical_md published` |
| **WARNING** | 可恢复的异常、重试 | `ETag mismatch for entity=pricing-2025, will reconcile` |
| **ERROR** | Pipeline 失败、存储错误 | `RepStep vlm_md failed: API timeout after 30s` |
| **CRITICAL** | 系统级故障 | `Redis connection lost, all workers blocked` |

所有日志必须包含：`request_id`（API 请求）、`entity_id`（Entity 操作）、`pipeline_id`（Pipeline 操作）、`worker_id`（Worker 操作）。

---

## 23. 测试与质量策略

### 23.1 测试金字塔

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

### 23.2 测试分类

| 类型 | 覆盖目标 | 工具 | 运行频率 |
| --- | --- | --- | --- |
| **单元测试** | RepStep / IndexStep / 状态机 / 一致性校验 / 血缘推导 | pytest + pytest-cov | 每次 commit |
| **集成测试** | API 端点 / Redis Streams / OSS 读写 / LanceDB 查询 | pytest + testcontainers | 每次 PR |
| **E2E 测试** | 完整 Pipeline 链路（ingest → rep → index → search） | pytest + docker-compose | 每次 release |
| **性能测试** | 检索延迟 / Pipeline 吞吐 / 并发 Worker | locust | 每次 release |
| **兼容性测试** | OSS / S3 / MinIO 后端切换 | pytest + parametrize | 每次 PR |
| **混沌测试** | Redis 宕机 / OSS 延迟 / Worker 崩溃恢复 | chaos-mesh（v0.2） | v0.2+ |

### 23.3 单元测试示例

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

### 23.4 集成测试示例

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

### 23.5 E2E 测试场景

| 场景 | 描述 | 预期结果 |
| --- | --- | --- |
| **S1: 文档完整链路** | PDF → canonical_md → chunk → embed → search | 检索命中；snippet 正确；provenance 可追溯 |
| **S2: 图片完整链路** | PNG → page_image → vlm_md → chunk → embed → search | 跨模态检索（文本→图片）命中 |
| **S3: 音频完整链路** | MP3 → audio_segment → transcript → chunk → embed → search | 音频内容可检索 |
| **S4: 一致性修复** | 修改 raw → Reconciler 检测 → Rep 重建 → Index 重建 | 两步自动修复完成 |
| **S5: 软删除** | 删除 Entity → 30 天内仍可恢复 → 30 天后物理删除 | 数据按预期保留和清除 |
| **S6: Pipeline 失败恢复** | RepStep 调用失败 → 重试 → 最终成功 | 指数退避重试；不超过 3 次 |
| **S7: Wiki Projector** | Entity → RepPipeline → WikiProjector → ~/wiki/*.md | Wiki 文件正确生成；wikilink 有效 |

### 23.6 CI/CD 流程

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

### 23.7 质量门禁

| 指标 | v0.1 目标 | v0.2 目标 |
| --- | --- | --- |
| **单元测试覆盖率** | ≥ 80% | ≥ 90% |
| **集成测试覆盖率** | ≥ 60% | ≥ 75% |
| **类型注解覆盖率** | ≥ 90%（mypy strict） | ≥ 95% |
| **Lint 零告警** | ruff check 0 | ruff check 0 |
| **API 响应 P99** | < 500ms（检索）/ < 2s（Entity CRUD） | < 200ms / < 1s |
| **Pipeline 吞吐** | 100 Entity/小时/Worker | 500 Entity/小时/Worker |

---

## 24. 版本策略与兼容性承诺

### 24.1 版本号规范

遵循 [Semantic Versioning 2.0](https://semver.org/)：

```text
MAJOR.MINOR.PATCH

MAJOR — 不兼容的 API 变更
MINOR — 向后兼容的新功能
PATCH — 向后兼容的 Bug 修复
```

### 24.2 版本生命周期

| 版本 | 状态 | 支持周期 | 说明 |
| --- | --- | --- | --- |
| **v0.1.x** | 开发预览 | 每 2 周发布 patch | 核心链路可用；API 可能变更 |
| **v0.2.x** | Beta | 每月发布 minor | 新增 Projector / 血缘可视化 / Dagster 编排 |
| **v0.3.x** | RC | 每季发布 minor | Merkle 树 / lakeFS 集成 / 多租户 |
| **v1.0.0** | GA | 长期支持（LTS） | API 稳定；向后兼容保证 |

### 24.3 向后兼容性承诺

**从 v1.0.0 开始**：

| 层面 | 兼容性承诺 | 例外 |
| --- | --- | --- |
| **REST API** | 不删除字段；新增字段可选；废弃字段标记 `@deprecated` 至少保留 2 个 MINOR 版本 | 安全漏洞修复 |
| **Python SDK** | 公共方法签名不变；新增可选参数；废弃方法标记 `DeprecationWarning` | — |
| **MCP 协议** | 工具名称不变；新增工具不影响已有工具；参数新增可选 | — |
| **OSS 数据格式** | Entity Tag 字段名不变；Rep 目录结构不变；Lance 表 schema 新增列可选 | — |
| **配置文件** | 新增 key 可选；已有 key 含义不变；废弃 key 标记 `@deprecated` | — |

**v0.x 期间**：不提供向后兼容性保证。API / 数据格式 / 配置可能在任何版本变更。

### 24.4 破坏性变更流程（v1.0+）

```text
1. 在 MINOR 版本中标记 @deprecated
   → 文档说明替代方案
   → 运行时 DeprecationWarning
2. 等待至少 2 个 MINOR 版本
3. 在下一个 MAJOR 版本中移除
   → CHANGELOG 明确标注
   → 迁移指南（MIGRATION.md）
```

### 24.5 数据格式演进

| 数据层 | 演进策略 | 迁移方式 |
| --- | --- | --- |
| **Entity Tag schema** | 新增字段高位预留（7/10 已用）；v0.2 新增 3 个字段 | 新增字段无需迁移；旧数据默认值 |
| **Rep 目录结构** | 新增 rep_type 目录；不修改已有目录名 | 无需迁移 |
| **LanceDB schema** | Lance 原生支持 schema evolution（add column） | 自动；新增列为 NULL |
| **Pipeline 注册表** | 新增 RepStep/IndexStep 注册；不改已有接口 | 无需迁移 |
| **Redis Streams 消息格式** | 新增字段可选；不删已有字段 | 消费者兼容新旧格式 |

### 24.6 CHANGELOG 规范

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

### 24.7 升级指南

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

## 25. 附录

### 25.1 与现有组件的对接

| 现有组件 | 对接方式 |
| --- | --- |
| **OSS Data Lake** | 直接读写；raw 路径即 source of truth |
| **Embedding V5** | 调 `/v1/embeddings`；按 §7.1 task 映射表选 task |
| **Chunking UseCase** | Pipeline A/B 的 chunk 阶段调用 `ChunkingWithSlidingWindowUseCase`；字段映射见下表 |
| **LanceDB** | representations.lance（vector + FTS + scalar filter）；hybrid search 原生支持 |

### 25.2 Chunking UseCase 字段映射

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

### 25.3 名词表

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

### 25.4 开源项目 Review：血缘方案对比

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

### 25.5 评审清单（Review Checklist）

- [ ] 1 OSS Object = 1 Entity 是否覆盖所有 v0.1 场景？
- [ ] Representation 的血缘 DAG 是否满足可重建？
- [ ] Chunk 作为检索粒度是否能定位到页/段/时间戳？
- [ ] Pipeline 并行调度是否满足 partial success？
- [ ] Lance representations.lance（vector + FTS + scalar filter）是否满足 hybrid search？
- [ ] 状态模型 + version 是否能区分"用户意图"与"处理状态"？
- [ ] content_hash 变更检测是否比 etag 更可靠？
- [ ] v0.1 范围是否足够小、足够完整？
- [ ] 与现有 OSS / V5 / Chunking 的对接路径是否清晰？


### 25.6 变更历史

> 以下为早期修订记录（#1-#24），完整设计决策演进详见本节。

(1) 1 OSS Object = 1 Entity

(2) Representation 是"认知视角"而非中间产物

(3) Pipeline 是一等公民，同一 Entity 可走多条并行流水线

(4) Chunk 是索引方法，不是存储概念

(5) 1 张 Lance 表 = representations.lance（内嵌 vector），PK = `(entity_id, rep_type, chunk_index)`

(6) 零持久化元数据，全部从两套 OSS Tag（Entity Tag 7个 + Representation Tag 7个）+ VFS 扫描实时获取

(7) 血缘不存于任何字段或 Tag，从**目录层级 + Pipeline 注册表**实时推导（目录层级即血缘深度：source/ → extract/ → recognize/ → compile/，_index/ 为系统目录）

(8) 表格型 Entity（entity_type=table）通过 DuckDB + compile/table.parquet 提供 SQL 统一查询，DuckDB 进程内嵌入、OSS 原生读取

(9) 三类一等检索能力（semantic / structural / textual）通过 §9 智能引擎统一路由与证据融合，DuckDB 作为 structural 的对等能力，与 Lance 协同工作

(10) Pipeline 间强依赖（拓扑排序）+ 混合型 Entity 启发式发现 + entity_type 6 级判定链

(11) **新增 Projector 层（§11）**：把 Lake 内部数据单向投影到多种外部消费者（RAG API / Wiki / Dashboard / Web），Lake 主体地位不动摇

(12) **新增 Wiki Projector 详设（§12）**：把 Karpathy LLM Wiki 视为 Lake 内部 Projector 的一种目标格式，Lake 主动把 Entity/Representation/Edge/Event 投影为 `~/wiki/` 目录的 .md + wikilink + index.md + log.md，wiki 独立可运行

(13) **RepPipeline 与 IndexPipeline 解耦（§2.2 / §3.1 / §4.5）**：Representation 生成（内容变换）和 Index 生成（搜索结构构建）是两件本质不同的事，拆为两套独立流水线，各自有独立的 Plugin 体系（RepStep / IndexStep）

(14) **RepStep Plugin 体系（§6.7）**：可插拔的内容变换步骤，新增 rep_type = 新增 RepStep + 注册，不改已有代码

(15) **IndexStep Plugin 体系（§6.8）**：可插拔的索引构建步骤，新增 index_type = 新增 IndexStep + 注册，与 RepStep 完全解耦

(16) **Projector 作为 RepStep 注册（§11）**：Projector 不再是独立事件驱动，而是 RepStep 的一种特殊形态，复用 RepPipeline 的编排能力

(17) **两阶段一致性模型（§2.5 / §5.7 / §5.9）**：一致性校验拆为 Rep↔Raw（内容一致性）和 Index↔Rep（索引一致性）两条独立链，Reconciler 也拆为两阶段执行，先修 Rep 再修 Index

(18) **专家 review 修复（v0.2 完善）**：P1 修复 §13 v0.1 范围对齐 Wiki Projector 是 v0.2；P2 拆 `input_reps` 为 `required_input_reps` + `optional_input_reps` 解决循环依赖；P3 §4.5 JSON schema 加 step_id 注释；S1-S11 + O1-O2 全面修复（§2.6/§3.2/§4.6 重写、§5.9.3 Projector 一致性、§5.10 Index Status、§5.11 Edge 生命周期、§5.9.4 rep_all_ready 精确定义、§6.9 并发模型、§14.5 Plugin 注册 API、§16 S15-S20 验收用例）；§2.4 术语统一 vlm_extracted_md → vlm_md；§11.3 表格对齐 WikiProjectorStep 状态为 v0.2

(19) **元数据可靠性与重建策略（§5.12）**：从可靠平台视角审视"零持久化"架构的元数据不可恢复风险，调整为"准零持久化"原则——运行时零持久化，但不可推导信息（rag_status/labels/version）以 `.entity_manifest.json` + `.version_log.jsonl` sidecar 持久化；新增 Reconciler Phase 0 body_hash 校验、Tag 写入原子性协议、Lance 损坏自愈、VFS 漂移监控、灾难恢复流程、管理员 API（§14.7）；§4.6 核心决策更新为"准零持久化"；§5.9 Reconciler 增加 Phase 0；§15 NFR 增加元数据可恢复指标；§16 增加 S21-S24 验收场景；§18 增加 R17-R20 风险

(20) **成熟项目参照优化（§5.12.9 - §5.12.14）**：参照 Delta Lake、Apache Iceberg、lakeFS、Lance 4 个成熟数据湖项目的元数据架构，识别当前 PRD 6 大设计缺口（事务日志、原子指针、三层元数据、Merkle 血缘、MVCC Manifest、Schema Evolution）；§4.6.x 新增 v0.2 三层元数据架构预览（事务日志 + 原子指针 + 快速索引）；§5.12.9 新增事务日志 + 原子指针交换（参考 Delta _delta_log + Iceberg compare-and-swap）；§5.12.10 新增 Merkle 树血缘（参考 lakeFS Graveler）；§5.12.11 新增三层元数据架构（参考 Iceberg Manifest List）；§5.12.12 新增 MVCC + 不可变 Manifest（参考 Lance spec）；§5.12.13 新增 Schema Evolution 规则；§5.12.14 明确 v0.1/v0.2 实施路径与设计哲学；§5.10.2 标注 v0.2 Manifest 显式化升级；§15 NFR 新增 v0.2 元数据架构指标（原子交换延迟 / 事务日志吞吐 / Time Travel / Checkpoint）；§18 风险新增 R21-R25

(21) **开源技术选型与复用（§20 + [OPEN_SOURCE_STACK.md](file:///workspace/OPEN_SOURCE_STACK.md)）**：从 OSS 数据管理 / 同步 / 向量检索 / Pipeline 编排 / 元数据治理 / 可观测性 / Lake Format 7 大类别盘点 50+ 开源项目；v0.1 选定最小可用集（OSS / MinIO + LanceDB + 自研调度 + OTel + Prometheus + Grafana + Sentry）；v0.2 引入候选（Dagster / Temporal / OpenMetadata / Kafka / JuiceFS / lakeFS）；新增 §19 包含 7 大类别速查、v0.1 最小可用集、v0.2 候选、OSS 事件通知集成模式、关键开源项目 GitHub 链接表、7 项关键决策记录（为何选 LanceDB / 为何自研调度 / 为何借鉴而非直接用 Iceberg）

(22) **Redis Streams 任务队列 + VFS MCP Server**：§6.10 新增 Redis Streams 任务队列设计（Stream 拓扑 / 消息格式 / 消费协议 / 可靠性保证 / 与 Celery 对比 / v0.2 演进路径），确认 v0.1 不使用 Celery（Celery 不可靠的根因是抽象层太多，直接用 Redis Streams 原语更可靠）；§9.5 新增 VFS MCP Server 设计（8 个 MCP Tools / stdio+SSE 双模式部署 / 与智能引擎映射 / v0.1 全量实现），向 LLM 暴露 Lake 的浏览/查询/检索能力；§19 v0.1 技术栈更新（Queue: Redis Streams / VFS→LLM: MCP Server）；§19.6 关键决策新增"任务队列"和"VFS→LLM"两条记录

(23) **产品级 Review 修复（17 项）**：C4 Entity Tag 从 10→7（移除 workspace_id/collection_id/entity_id，预留 3 个给 v0.2）；C2 Entity=触发器（generate_*/build_* 只投递消息到 Redis Streams，Worker 执行）；F1 OSS PutObject 不支持 if-match（v0.1 last-writer-wins + Reconciler 修复，v0.2 CopyObject+if-match）；C1 元数据写入状态机（CLEAN/FILE_WRITTEN/MANIFEST_WRITTEN/TAG_MISSING 四态 + Reconciler 自动修复）；F2 Phase 0 改为 ETag 校验（HeadObject 零下载，代价 O(file_size)→O(1)）；C3 消息格式增加 input_reps（Orchestrator 填充具体路径）；C5 MCP+REST 共享 Service 层；E3 软删除不删 Lance（deleted 保留 30 天，destroy 才物理删）；E2 锁粒度从 Entity 级改为 RepPipeline 级；E6 Redis Streams 背压策略（MAXLEN+告警+429+锁超时策略）；E5 MCP 权限模型（admin/user/readonly + required_role）；E4 Index 重建优先级（high/medium/low 分批重建）；E1 多文件 Rep 目录级 .meta.json；F3 OSS LIST 1000 限制 + VFS Redis 缓存；F5 Lance metadata 限制（v0.1 最多 5 个 Index）

(24) **完整 PRD 补充（§1.5/§1.6/§20-§24）**：新增用户角色（5 类 Personas）与竞争定位（与 Elasticsearch/Pinecone/LlamaIndex/lakeFS/OpenMetadata 6 维对比）；新增部署模型（Docker Compose 一键部署 + 拓扑图 + 8 条运维命令）；新增 SDK 策略（Python SDK + CLI + MCP 集成 + 多语言路线图）；新增错误模型（17 个错误码 + 4 个故障排查场景）；新增测试策略（测试金字塔 + 7 个 E2E 场景 + CI/CD 流程 + 6 项质量门禁）；新增版本策略（SemVer + 生命周期 + 5 层向后兼容承诺 + 数据格式演进 + CHANGELOG 规范）

---

> **本 PRD 是设计基线（baseline）**。任何对核心抽象的修改（entity / representation / pipeline / chunk / 状态机）都应先回到本文件评审，再写代码。
