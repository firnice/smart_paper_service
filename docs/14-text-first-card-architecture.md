# 文本优先错题卡片策略 - Architecture Design

- ID: 14
- Topic: `text-first-card`
- Stage: `architecture`
- Status: Review
- File: `14-text-first-card-architecture.md`
- Upstream: [13-text-first-card-prd.md](./13-text-first-card-prd.md)
- Downstream: [15-text-first-card-implementation.md](./15-text-first-card-implementation.md)

## Design Decisions
- 主流程：`OCR item -> text normalization -> form.content`。
- 默认清空 `form.image_data/image_name`，避免旧抠图内容进入卡片。
- 图示可选：使用前端 SVG 模板根据题干生成替代图示 data URL。
- 抠图链路保留代码但通过开关 `ENABLE_IMAGE_CROP_WORKFLOW=false` 隐藏入口。

## Data Flow
1. 上传图片并调用真实识别。
2. 选择题目后仅应用文字内容到表单。
3. 用户可选点击“生成替代图示”。
4. 预览卡片展示文字为主，图示为可选模板图。
