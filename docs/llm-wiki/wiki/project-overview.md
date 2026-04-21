# 项目全景

## 摘要

`lf-smart-paper-service` 是 Smart Paper 智能错题本的后端服务，围绕“小学生错题收集、整理、训练、导出、分析”构建。当前仓库已经覆盖 OCR 识别、题目变式、导出、学生/家长关系、错题维护、统计分析、趋势分析，以及一套面向 LLM 供应商与 agent 配置的后台接口。

## 关键点

- 运行时框架是 FastAPI，入口在 [app/main.py](../../../app/main.py)。
- 路由聚合在 [app/api/router.py](../../../app/api/router.py)，当前已注册 `health`、`auth`、`ocr`、`variants`、`export`、`users`、`metadata`、`wrong-questions`、`statistics`、`admin`、`analysis`、`school-terms`。
- 对外能力可分成四块：
  - 题目进入系统：`/api/ocr/*`
  - 题目加工与输出：`/api/variants/*`、`/api/export`、`/api/print-pack/export`
  - 学生错题域：`/api/users/*`、`/api/wrong-questions/*`、`/api/subjects` 等 metadata
  - 统计与运营：`/api/statistics/*`、`/api/analysis/trend*`、`/api/admin/*`
- 从产品阶段看，仓库里同时存在“已实现能力”和“未来阶段规划”。wiki 后续必须持续区分 `implemented` 与 `planned`。

## 当前状态判断

- `implemented`:
  - OCR 识别与图示处理主链路
  - 变式题生成
  - 基础导出与 print pack 导出
  - 用户、学生、家长关系与学期切换
  - 错题 CRUD、学习记录、统计与趋势分析
  - agent / model provider 管理与 LLM 调用统计
- `planned or evolving`:
  - 产品文档里更完整的知识点讲解、智能讲解、导出增强等后续阶段
  - V2 前端重构带来的后端微调项

## 主要用户流

- 家长或学生上传题目图片，后端走 OCR 与题目分析链路，再沉淀为错题实体。
- 学生在错题本里进行状态更新、学习记录和练习输出。
- 系统按学生维度聚合统计，并可生成趋势分析报告。
- 管理后台可配置 agent、模型供应商，并查看 LLM 调用概况。

## 开放问题

- `docs/product/README.md` 的阶段状态与当前实际代码进度存在多少 drift，仍需继续核对。
- 趋势分析、diagram/svg、print-pack 这些较新的能力在 README 中没有完全展开，后续应继续专题 ingest。
- frontend-first 临时规则会影响近期“应优先维护哪些页面”，需要随协作状态同步更新。

## 来源

- [../../../README.md](../../../README.md)
- [../../product/README.md](../../product/README.md)
- [../../../app/main.py](../../../app/main.py)
- [../../../app/api/router.py](../../../app/api/router.py)
- [../raw/2026-04-21-repo-bootstrap.md](../raw/2026-04-21-repo-bootstrap.md)
