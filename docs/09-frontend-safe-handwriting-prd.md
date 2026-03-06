# 前端去手写安全修复 - Product PRD

- ID: 09
- Topic: `frontend-safe-handwriting`
- Stage: `prd`
- Status: Review
- File: `09-frontend-safe-handwriting-prd.md`
- Upstream: N/A
- Downstream: [10-frontend-safe-handwriting-architecture.md](./10-frontend-safe-handwriting-architecture.md)

## Problem
- 当前“自动去手写”会把题干印刷内容一起清除，出现大面积白块。
- 元素删除按矩形整块擦除，无法按字体/图形真实形状抠除。

## Goals
- 自动去手写默认“保守安全”，优先保留题干内容。
- 删除逻辑改为像素级掩膜，不再整块矩形覆盖。
- 当误删风险高时自动中止并提示手动精修。

## Success Metrics
- 自动去手写场景下，题干误删率显著下降（以文本区暗像素损失率作为代理指标）。
- 元素删除后不再出现大块矩形白斑。
- 用户可通过提示区分“已擦除”与“安全保护触发”。

## Scope
- In scope:
- 前端 `StudentDashboardPage.jsx` 的手写检测与擦除逻辑。
- 像素级擦除、文本行保护、风险阈值保护。
- 提示文案与结果反馈（擦除像素/保护像素）。

- Out of scope:
- 新增后端接口。
- 新增 SaaS 去手写链路。
- 题目重建功能（按当前要求保持关闭）。

## Acceptance Criteria
1. 自动去手写不能再按矩形整块填充。
2. 文本行区域必须有保护策略，避免整体误删。
3. 风险阈值超限时必须拒绝自动改图并提示用户。
4. 元素扫描后的删除应体现为“按形状擦除”，而非“矩形补丁”。
