# WhatAI 图示能力接入 - Development Implementation

- ID: 23
- Topic: `whatai-diagram-client`
- Stage: `implementation`
- Status: Completed
- File: `23-whatai-diagram-client-implementation.md`
- Upstream: [22-whatai-diagram-client-architecture.md](./22-whatai-diagram-client-architecture.md)
- Downstream: [24-whatai-diagram-client-test.md](./24-whatai-diagram-client-test.md)

## Backend Changes
- `app/services/llm_client_service.py`（新增）
  - 新增 `BaseLlmClient` + `SiliconflowClient` + `WhataiClient`。
  - 统一 IO 日志与错误封装。
- `app/core/llm_settings.py`
  - 新增 `WhataiSettings` 与 `load_whatai_settings()`。
- `app/services/diagram_llm_service.py`（新增）
  - `generate_diagram_crop()`：whatai flash 模型识别 box 后裁剪。
  - `generate_diagram_svg()`：whatai pro 模型生成 SVG。
- `app/api/routes/ocr.py`
  - 接入模式2/3产物并返回：`diagram_local_image_url` / `diagram_llm_image_url` / `diagram_svg_url`。
- `app/services/storage_service.py`
  - 新增 `upload_question_asset(..., suffix)` 支持 `.svg`。
- `app/services/ocr_service.py` / `question_rebuild_service.py` / `variant_service.py`
  - 切到 `SiliconflowClient`，统一走基线 BaseClient。
- `app/schemas/ocr.py`
  - 扩展响应字段。

## Frontend Changes
- `lf-smart-paper-web/src/pages/student/StudentDashboardPage.jsx`
  - 解析并消费 `diagram_local_image_url` / `diagram_llm_image_url` / `diagram_svg_url`。
  - 三模式策略按后端字段路由：
    - `original_crop`
    - `llm_crop`
    - `llm_svg`
