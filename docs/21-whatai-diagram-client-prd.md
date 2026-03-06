# WhatAI 图示能力接入 - Product PRD

- ID: 21
- Topic: `whatai-diagram-client`
- Stage: `prd`
- Status: Review
- File: `21-whatai-diagram-client-prd.md`
- Upstream: N/A
- Downstream: [22-whatai-diagram-client-architecture.md](./22-whatai-diagram-client-architecture.md)

## Requirement
- 图示模式 2：使用 `https://api.whatai.cc/v1/chat/completions` + `gemini-3.1-flash-image-preview`。
- 图示模式 3：使用 `https://api.whatai.cc/v1/chat/completions` + `gemini-3.1-pro-preview`。
- 区分硅基流动与 WhatAI 客户端，并统一接入基线 `BaseClient`。
- `BaseClient` 需要记录输入输出（带安全截断）。

## Goals
1. OCR 主流程返回三类图示：本地抠图、LLM抠图、LLM SVG。
2. 前端三模式可直接消费后端字段切换。
3. 统一 LLM 调用规范，便于后续扩展与排障。
