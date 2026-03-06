# 前端去手写安全修复 - Architecture Design

- ID: 10
- Topic: `frontend-safe-handwriting`
- Stage: `architecture`
- Status: Review
- File: `10-frontend-safe-handwriting-architecture.md`
- Upstream: [09-frontend-safe-handwriting-prd.md](./09-frontend-safe-handwriting-prd.md)
- Downstream: [11-frontend-safe-handwriting-implementation.md](./11-frontend-safe-handwriting-implementation.md)

## Requirement Mapping
| PRD 验收项 | 设计决策 |
| --- | --- |
| 不按矩形整块擦除 | 引入 `eraseMask`，仅擦除掩膜像素 |
| 文本行保护 | 基于暗像素行密度构建 `textRowMask`，手写模式下保护非强笔画像素 |
| 风险阈值保护 | 计算文本区候选擦除比率，超过阈值中止 |
| 形状擦除 | 元素检测保留连通域像素集合 `pixelIndices` |

## Design
- 输入：`imageUrl + elements + hiddenIds + options`。
- 预分析：
1. 全图计算灰度、彩色笔掩膜、暗像素行密度。
2. 构建文本行掩膜 `textRowMask`。
- 擦除候选：
1. 对每个待删元素建立局部背景环采样。
2. 像素级判断是否为前景笔迹（深色/高对比/红蓝笔）。
3. 手写模式下对文本行像素执行保护门。
- 安全门：
1. 统计文本行印刷暗像素的候选擦除比率。
2. 超阈值则抛出保护错误，拒绝写入新图。
- 输出：`{ dataUrl, removedPixels, protectedPixels }`。

## Tradeoffs
- 选择“保守保护”会残留部分手写，但可避免误删题干。
- 使用连通域像素集合会增加前端内存占用，但换来形状级擦除准确性。
