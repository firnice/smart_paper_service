# 图示三模式策略 - Development Implementation

- ID: 19
- Topic: `diagram-three-mode`
- Stage: `implementation`
- Status: Completed
- File: `19-diagram-three-mode-implementation.md`
- Upstream: [18-diagram-three-mode-architecture.md](./18-diagram-three-mode-architecture.md)
- Downstream: [20-diagram-three-mode-test.md](./20-diagram-three-mode-test.md)

## Changed Files
- `lf-smart-paper-web/src/pages/student/StudentDashboardPage.jsx`

## Implemented
1. 新增 `DIAGRAM_RENDER_MODES` 三模式配置。
2. 新增 `diagramRenderMode` 状态与头部切换 Tabs。
3. 新增 `sourceImageSnapshot` 保存上传原图基底。
4. 重构 `onApplyOcrItem(item, silent, mode)`：
- `original_crop`：回填原图基底并进入可抠图状态。
- `llm_crop`：优先应用 `diagramImageUrl`。
- `llm_svg`：生成 SVG 替代图写入卡片。
5. OCR 列表改为“按当前策略应用”。
6. 原图抠图编辑区显示条件改为 `isOriginalCropMode`。
