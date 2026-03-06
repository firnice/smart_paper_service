# WhatAI 图示能力接入 - Architecture Design

- ID: 22
- Topic: `whatai-diagram-client`
- Stage: `architecture`
- Status: Review
- File: `22-whatai-diagram-client-architecture.md`
- Upstream: [21-whatai-diagram-client-prd.md](./21-whatai-diagram-client-prd.md)
- Downstream: [23-whatai-diagram-client-implementation.md](./23-whatai-diagram-client-implementation.md)

## Client Layering
- `BaseLlmClient`：
  - 统一 OpenAI-compatible `chat/completions` 请求。
  - 统一错误类型：`LlmHttpError` / `LlmNetworkError` / `LlmClientError`。
  - 基线日志：请求 payload（脱敏/截断）+ 响应 body（截断）。
- `SiliconflowClient`：复用基线 client，承载现有 OCR/重建/变体。
- `WhataiClient`：复用基线 client，承载图示模式 2/3。

## Diagram Pipeline
- 模式 2（LLM识别抠图）：
1. 用 flash-image 模型识别 `diagram_box`。
2. 在题目快照上按 box 执行裁剪。
3. 上传为 `diagram_llm_image_url`。
- 模式 3（LLM生成SVG）：
1. 用 pro-preview 模型生成 `<svg>...</svg>`。
2. 存储为静态资源并返回 `diagram_svg_url`。

## Response Contract Extension
- `diagram_local_image_url`
- `diagram_llm_image_url`
- `diagram_svg_url`
- `diagram_image_url` 作为兼容字段，优先回填 LLM 抠图。
