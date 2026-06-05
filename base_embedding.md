# Embedding V5 API 接口文档

## 服务概述

基于 Jina Embeddings V5 Omni 的多任务多模态 Embedding 服务，支持 **文本、图像、音频、视频** 四种模态的向量化，提供统一的 OpenAI 兼容接口。

| 项目 | 说明 |
|---|---|
| 服务端口 | `8006` |
| 协议 | HTTP / JSON |
| 接口风格 | OpenAI Embeddings 兼容 |
| 支持模态 | 文本、图像、音频、视频 |

### 架构

```
客户端 → API 网关 (:8006)
              │
              ├── 文本请求 → Router (:9001/:9002) → 4×GPU Worker（批量高效）
              │
              └── 图片/多模态请求 → 直连 Worker (:9101-9104 / :9111-9114)（逐条并行）
```

- **文本请求**（`input` 模式或 `messages` 纯文本）：通过 Router 批量转发，高效
- **图片请求**（`task="image"` + `input`）：API 层下载/缩放图片 → 直连 Worker，逐条并行 + Round-Robin
- **多模态请求**（`messages` 含 image_url/video_url/audio_url）：直连 Worker，逐条并行 + Round-Robin

---

## 接口列表

### 1. 生成 Embedding

```
POST /v1/embeddings
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model` | string | ✅ | 模型名称，固定为 `"embedding-v5"` |
| `task` | string | ✅ | 任务类型，见下表 |
| `input` | array\<string\> | ⚠️ | 输入列表，与 `messages` 二选一 |
| `messages` | array\<object\> | ⚠️ | 消息列表，与 `input` 二选一（支持多模态） |
| `dimensions` | integer | ❌ | 输出向量维度，支持 MRL 截断 |
| `encoding_format` | string | ❌ | 编码格式，默认 `"float"` |

#### task 任务类型

| task 值 | 输入方式 | 说明 | 后端模型 |
|---|---|---|---|
| `retrieval.query` | `input` 文本 | 检索-查询端，用于将用户查询转为向量 | embedding-v5-retrieval |
| `retrieval.passage` | `input` 文本 | 检索-文档端，用于将文档/段落转为向量 | embedding-v5-retrieval |
| `text-matching` | `input` 文本 | 文本语义匹配，用于计算两段文本的语义相似度 | embedding-v5-text-matching |
| `image` | `input` base64/URL | 图片 Embedding，将图片转为向量（与 retrieval 同一向量空间） | embedding-v5-retrieval |
| `video` | `input` base64/URL | 视频 Embedding，将视频转为向量（与 retrieval 同一向量空间） | embedding-v5-retrieval |
| `audio` | `input` base64/URL | 音频 Embedding，将音频转为向量（与 retrieval 同一向量空间） | embedding-v5-retrieval |

> **关键说明**：
> - `retrieval.query` 和 `retrieval.passage` 必须配对使用，查询用 `retrieval.query`，文档用 `retrieval.passage`
> - `image`/`video`/`audio` task 的向量与 `retrieval.query`/`retrieval.passage` 在同一向量空间，可直接用于跨模态检索
> - `image`/`video`/`audio` task 参照 V4 接口设计，`input` 直接传 base64 或 URL，简洁高效
> - **音频格式要求**：WAV 格式，采样率 16kHz，单声道，16-bit PCM

#### dimensions 可选维度

| 值 | 说明 |
|---|---|
| `1024` | 默认全维度（不传 `dimensions` 时） |
| `768` | 截断到 768 维 |
| `512` | 截断到 512 维 |
| `256` | 截断到 256 维 |
| `128` | 截断到 128 维 |
| `64` | 截断到 64 维 |
| `32` | 截断到 32 维 |

> MRL 截断在 API 层完成：取前 N 维后重新做 L2 归一化，保证截断后向量仍为单位向量。

#### input 字段说明

| task | input 格式 | 示例 |
|---|---|---|
| `retrieval.query` / `retrieval.passage` / `text-matching` | 文本字符串列表 | `["图书馆开放时间", "量子计算原理"]` |
| `image` | 图片 base64 或 URL 列表 | `["data:image/png;base64,...", "https://example.com/img.jpg"]` |
| `video` | 视频 base64 或 URL 列表 | `["data:video/mp4;base64,...", "https://example.com/vid.mp4"]` |
| `audio` | 音频 base64 或 URL 列表 | `["data:audio/wav;base64,..."]` |

#### messages 格式（高级用法）

**纯文本消息：**

```json
{
  "role": "user",
  "content": "文本内容"
}
```

**多模态消息（结构化内容列表）：**

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "描述文本"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
    {"type": "video_url", "video_url": {"url": "data:video/mp4;base64,..."}},
    {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,..."}}
  ]
}
```

#### 多模态内容类型

| type | 字段 | URL 格式 | 说明 |
|---|---|---|---|
| `text` | `text` | — | 文本内容 |
| `image_url` | `image_url.url` | base64 Data URI 或 HTTP URL | 图片（PNG/JPEG/GIF/WebP 等） |
| `video_url` | `video_url.url` | base64 Data URI 或 HTTP URL | 视频（MP4/AVI/MOV 等） |
| `audio_url` | `audio_url.url` | base64 Data URI 或 HTTP URL | 音频（WAV/MP3/FLAC 等） |

> **图片处理**：API 层会自动下载外部 URL 图片并缩放到安全尺寸（默认 224×224），再以 base64 传给 vLLM Worker，确保兼容性。

#### 约束

- `input` / `messages` 列表最大长度：**64**
- `input` 中每个元素必须为非空字符串
- `input` 和 `messages` 必须提供其中之一，不可同时为空
- `image`/`video`/`audio` task 必须使用 `input` 字段
- `image` task：API 层自动下载外部 URL 图片并缩放到安全尺寸（默认 224×224），支持 base64 Data URI 和 HTTP URL
- `audio` task：推荐 WAV 格式，采样率 16kHz，单声道，16-bit PCM；支持 base64 Data URI
- `video` task：支持 MP4 等常见格式，支持 base64 Data URI
- 多模态请求中，每条消息独立编码，并行处理

---

#### 请求示例

**示例 1：检索查询（纯文本）**

```bash
curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embedding-v5",
    "task": "retrieval.query",
    "input": ["图书馆开放时间", "如何借阅图书"]
  }'
```

**示例 2：检索文档 + 维度截断**

```bash
curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embedding-v5",
    "task": "retrieval.passage",
    "input": ["浙江省图书馆位于杭州", "机器学习是AI的子领域"],
    "dimensions": 256
  }'
```

**示例 3：文本匹配**

```bash
curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embedding-v5",
    "task": "text-matching",
    "input": ["今天天气很好", "人工智能改变世界"]
  }'
```

**示例 4：图片 Embedding（base64，V4 兼容风格）**

```bash
BASE64_IMG=$(base64 -w 0 photo.jpg)

curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"embedding-v5\",
    \"task\": \"image\",
    \"input\": [\"data:image/jpeg;base64,$BASE64_IMG\"]
  }"
```

**示例 5：图片 Embedding（外部 URL）**

```bash
curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embedding-v5",
    "task": "image",
    "input": ["https://example.com/photo.jpg"],
    "dimensions": 512
  }'
```

**示例 6：音频 Embedding（base64）**

```bash
BASE64_AUDIO=$(base64 -w 0 audio.wav)

curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"embedding-v5\",
    \"task\": \"audio\",
    \"input\": [\"data:audio/wav;base64,$BASE64_AUDIO\"]
  }"
```

**示例 7：视频 Embedding（base64）**

```bash
BASE64_VIDEO=$(base64 -w 0 clip.mp4)

curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"embedding-v5\",
    \"task\": \"video\",
    \"input\": [\"data:video/mp4;base64,$BASE64_VIDEO\"]
  }"
```

**示例 8：多模态消息（文本+图片混合）**

```bash
curl -X POST http://localhost:8006/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "embedding-v5",
    "task": "retrieval.passage",
    "messages": [
      {"role": "user", "content": "浙江省图书馆位于杭州"},
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "图书馆外景照片"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        ]
      }
    ]
  }'
```

---

#### 响应格式

```json
{
  "model": "embedding-v5",
  "object": "list",
  "usage": {
    "total_tokens": 12,
    "task": "retrieval.query"
  },
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.0123, -0.0456, ...]
    },
    {
      "object": "embedding",
      "index": 1,
      "embedding": [0.0789, 0.0234, ...]
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `model` | 请求中的模型名称 |
| `object` | 固定为 `"list"` |
| `usage.total_tokens` | 后端消耗的 token 总数 |
| `usage.task` | 请求的任务类型 |
| `data[].index` | 与输入列表对应的序号（0-based） |
| `data[].embedding` | 向量数据，维度取决于 `dimensions` 参数（默认 1024） |

---

### 2. 健康检查

```
GET /health
```

#### 响应示例

```json
{
  "status": "ok",
  "retrieval_endpoint": "http://127.0.0.1:9001",
  "retrieval_healthy": true,
  "text_matching_endpoint": "http://127.0.0.1:9002",
  "text_matching_healthy": true,
  "max_input_list": 64
}
```

| 字段 | 说明 |
|---|---|
| `status` | `"ok"` = 全部后端健康；`"degraded"` = 部分后端不可用 |
| `retrieval_healthy` | Retrieval 后端是否可达 |
| `text_matching_healthy` | Text-Matching 后端是否可达 |

---

## 错误码

| HTTP 状态码 | 场景 |
|---|---|
| `400` | 参数校验失败（无效 task/model/dimensions、空文本、列表超长、图片下载失败等） |
| `422` | Pydantic 请求体解析失败（字段类型错误、缺少必填字段等） |
| `500` | vLLM 后端错误、返回数据条数不一致等内部错误 |

#### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

---

## 使用场景

### 场景 1：语义检索（RAG）

```
1. 将知识库文档分段，用 task="retrieval.passage" 编码并存入向量数据库
2. 用户提问时，用 task="retrieval.query" 编码查询
3. 在向量数据库中做最近邻搜索，返回相关文档
```

### 场景 2：跨模态检索（文本查图片/音频/视频）

```
1. 将图片用 task="image" 编码，存入向量数据库
2. 将音频用 task="audio" 编码，存入同一索引
3. 将视频用 task="video" 编码，存入同一索引
4. 文本段落用 task="retrieval.passage" 编码，存入同一索引
5. 用户用文本查询（task="retrieval.query"）即可跨模态检索到相关图片/音频/视频
6. image/audio/video 和 retrieval 在同一向量空间，无需额外对齐
```

### 场景 3：文本语义相似度

```
1. 用 task="text-matching" 分别编码两段文本
2. 计算两个向量的余弦相似度
3. 相似度越高，语义越相近
```

### 场景 4：媒体相似度

```
1. 用 task="image" 分别编码两张图片（或 task="audio" 编码两段音频）
2. 计算两个向量的余弦相似度
3. 相似度越高，内容越相近
```

### 场景 5：降维加速

```
1. 传 dimensions=256 或更小值
2. API 层自动截断并重新 L2 归一化
3. 牺牲少量精度换取更小的存储和更快的检索速度
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `RETRIEVAL_ENDPOINT` | `http://127.0.0.1:9001` | Retrieval Router 地址 |
| `TEXT_MATCHING_ENDPOINT` | `http://127.0.0.1:9002` | Text-Matching Router 地址 |
| `RETRIEVAL_WORKERS` | `http://127.0.0.1:9101,...,9104` | Retrieval Worker 地址列表（逗号分隔） |
| `TEXT_MATCHING_WORKERS` | `http://127.0.0.1:9111,...,9114` | Text-Matching Worker 地址列表（逗号分隔） |
| `SERVICE_PORT` | `8006` | API 网关监听端口 |
| `MAX_INPUT_LIST` | `64` | 单次请求最大输入数量 |
| `REQUEST_TIMEOUT` | `300` | 请求超时时间（秒） |
| `MAX_IMAGE_PIXELS` | `50176` | 图片最大像素数（超过自动缩放，默认 224×224） |
