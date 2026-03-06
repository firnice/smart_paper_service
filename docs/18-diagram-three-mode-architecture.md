# 图示三模式策略 - Architecture Design

- ID: 18
- Topic: `diagram-three-mode`
- Stage: `architecture`
- Status: Review
- File: `18-diagram-three-mode-architecture.md`
- Upstream: [17-diagram-three-mode-prd.md](./17-diagram-three-mode-prd.md)
- Downstream: [19-diagram-three-mode-implementation.md](./19-diagram-three-mode-implementation.md)

## Strategy Routing
- `diagramRenderMode=original_crop`
  - 图示来源：上传原图快照（无则退化到题目截图）。
  - 应用后进入抠图编辑区。
- `diagramRenderMode=llm_crop`
  - 图示来源：`item.diagramImageUrl`。
  - 无图示时返回可操作提示并建议切换模式。
- `diagramRenderMode=llm_svg`
  - 图示来源：根据识别文本生成 SVG data URL。

## Key States
- `diagramRenderMode`：当前策略。
- `sourceImageSnapshot`：上传原图快照，用于原图抠图模式回填。
- `currentDiagramModeMeta`：当前模式标签与提示。
