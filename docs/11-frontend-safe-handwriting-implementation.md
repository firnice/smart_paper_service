# 前端去手写安全修复 - Development Implementation

- ID: 11
- Topic: `frontend-safe-handwriting`
- Stage: `implementation`
- Status: Completed
- File: `11-frontend-safe-handwriting-implementation.md`
- Upstream: [10-frontend-safe-handwriting-architecture.md](./10-frontend-safe-handwriting-architecture.md)
- Downstream: [12-frontend-safe-handwriting-test.md](./12-frontend-safe-handwriting-test.md)

## Changed Files
- `lf-smart-paper-web/src/pages/student/StudentDashboardPage.jsx`

## Key Changes
1. `detectHandwritingElements`：
- 降低暗像素阈值，减少正文误入候选。
- 每个连通域保留 `pixelIndices`，用于后续形状擦除。
- 取消手写候选的邻近框合并，避免框扩张误删。

2. `detectScanElements`：
- 记录连通域 `pixelIndices`，支持按形状擦除。

3. `eraseSelectedElements`：
- 函数签名升级为 `(..., options = {})`。
- 新增全图灰度/彩笔/文本行分析。
- 新增像素级 `eraseMask` 与 `protectedMask`。
- 手写模式启用文本行保护门与风险阈值保护（高风险直接中止）。
- 擦除结果改为连通域级背景采样填充，避免矩形白块。
- 返回结构改为 `{ dataUrl, removedPixels, protectedPixels }`。

4. 调用端更新：
- `onApplyElementErase` 与 `onAutoRemoveHandwriting` 适配新返回值。
- 自动去手写启用 `mode: handwriting` + `protectTextRows: true`。
- 新增“零可安全擦除像素”提示。

## Notes
- 题目重建功能保持关闭（`ENABLE_REBUILD_JSON=false` 已在后端默认关闭）。
