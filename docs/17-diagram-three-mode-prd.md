# 图示三模式策略 - Product PRD

- ID: 17
- Topic: `diagram-three-mode`
- Stage: `prd`
- Status: Review
- File: `17-diagram-three-mode-prd.md`
- Upstream: N/A
- Downstream: [18-diagram-three-mode-architecture.md](./18-diagram-three-mode-architecture.md)

## Problem
- 单一图示路径难以覆盖所有题型：抠图易失败，LLM抠图不总是返回，生成图需要兜底。

## Goals
- 同一题支持三种可切换图示策略：
1. 原图抠图
2. LLM识别抠图
3. LLM识别生成新图（SVG）
- 策略可在前端快速切换并立即应用到卡片。

## Acceptance Criteria
1. OCR 区域必须提供三模式切换入口。
2. 每题“按当前策略应用”可根据当前模式写入卡片。
3. 三种模式都能独立工作并给出清晰提示。
4. 原图抠图模式下显示并启用抠图编辑区。
