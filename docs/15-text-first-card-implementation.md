# 文本优先错题卡片策略 - Development Implementation

- ID: 15
- Topic: `text-first-card`
- Stage: `implementation`
- Status: Completed
- File: `15-text-first-card-implementation.md`
- Upstream: [14-text-first-card-architecture.md](./14-text-first-card-architecture.md)
- Downstream: [16-text-first-card-test.md](./16-text-first-card-test.md)

## Changed Files
- `lf-smart-paper-web/src/pages/student/StudentDashboardPage.jsx`

## Implemented
1. 新增文本优先开关：`ENABLE_IMAGE_CROP_WORKFLOW=false`。
2. 新增 `normalizeTextForCard`，统一 OCR 文本清洗。
3. 新增 `buildDiagramReplacementDataUrl`，支持模板图示生成。
4. `onApplyOcrItem` 改为仅应用文字，清空图片字段。
5. 新增 `onApplyGeneratedDiagram`，一键生成替代图示并回填卡片。
6. OCR 列表 UI 改为“应用该题 + 生成替代图示”，移除“精修图片”。
7. 隐藏元素编辑/抠图操作区，预览支持纯文字卡片。
