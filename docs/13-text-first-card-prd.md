# 文本优先错题卡片策略 - Product PRD

- ID: 13
- Topic: `text-first-card`
- Stage: `prd`
- Status: Review
- File: `13-text-first-card-prd.md`
- Upstream: N/A
- Downstream: [14-text-first-card-architecture.md](./14-text-first-card-architecture.md)

## Problem
- 抠图与去手写在复杂批注场景下误删明显，影响可用性。
- 用户核心诉求是“拿到可编辑题干卡片”，而非保留原图文字。

## Goals
- 题目文本区采用 OCR/LLM 提取文本直接生成卡片。
- 默认不走抠图链路，不把原图抠图结果作为主输入。
- 图示区支持“替代图示”生成（模板作图），作为可选能力。

## Acceptance Criteria
1. 应用识别结果时，默认只填充文字内容。
2. 抠图/精修入口不出现在主流程。
3. 支持一键生成替代图示并写入卡片预览。
4. 无图示时仍可保存完整文字卡片。
