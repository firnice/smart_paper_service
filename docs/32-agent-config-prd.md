# Agent 配置管理系统 - Product PRD

- ID: 32
- Topic: `agent-config`
- Stage: `prd`
- Status: Draft
- File: `32-agent-config-prd.md`
- Upstream: N/A
- Downstream: [33-agent-config-architecture.md](./33-agent-config-architecture.md)

## Problem
- 所有 LLM 调用点（OCR 识别、题目分析、图表裁剪、SVG 生成）的模型配置硬编码在环境变量中，修改需要重启服务。
- 不同 agent 节点使用不同 LLM 提供商（SiliconFlow、WhatAI），配置分散，难以统一管理。
- 缺少管理后台，运营无法动态切换模型、调整参数、启停节点。
- 随着举一反三、趋势分析等新 LLM 节点增加，配置管理复杂度倍增。

## Goals
- 建立统一的 Agent 配置注册中心，所有 LLM 调用点通过 `node_name` 读取配置。
- 配置存入数据库，支持运行时动态修改，无需重启。
- 提供管理后台 API 和 UI，支持查看、修改、测试各 agent 节点。
- 保持向后兼容：数据库无配置时自动回退到环境变量默认值。

## Success Metrics
- 所有 LLM 调用点统一走 agent 配置服务，零硬编码模型名。
- 管理员可在 UI 上修改任意 agent 的模型并立即生效。
- 测试连通性功能可在 3 秒内返回验证结果。
- 现有功能（OCR、题目分析、SVG 生成）在改造后回归测试通过。

## Scope
- In scope:
  - `agent_configs` 数据库表设计与 Alembic 迁移。
  - `agent_config_service.py` 配置读取 + LLM 客户端工厂。
  - Admin CRUD API（列出 / 查询 / 更新 / 测试）。
  - 改造 `ocr_service`、`question_analysis_service`、`diagram_llm_service` 使用 agent 配置。
  - 前端管理页面 Agent 配置卡片。

- Out of scope:
  - 管理员认证（阶段五实施，本阶段 API 无鉴权保护）。
  - Prompt 版本管理与 A/B 测试。
  - Agent 调用统计与成本核算。

## User Stories
- 作为管理员，我希望在后台看到所有 LLM agent 节点及其当前配置（模型、温度、超时等）。
- 作为管理员，我希望修改某个 agent 的模型后，下一次该 agent 的调用立即使用新模型。
- 作为管理员，我希望禁用某个 agent（如趋势分析），使前端对应功能变为不可用。
- 作为管理员，我希望在保存前测试某个 agent 配置的连通性，确认模型可正常返回。

## Agent 节点定义

| node_name | display_name | provider | 说明 |
|-----------|-------------|----------|------|
| ocr_recognize | OCR 试卷识别 | siliconflow | 调用视觉模型识别试卷 |
| question_analyze | 题目智能分析 | siliconflow | 分析题目推断学科/分类/错因 |
| diagram_crop | 图表区域裁剪 | whatai | 识别图片中的图表区域 |
| diagram_svg | SVG 图表生成 | whatai | 根据文字生成 SVG 图 |
| question_generate | 举一反三出题 | siliconflow | 根据原题生成类似练习题 |
| trend_analyze | 错题趋势分析 | siliconflow | 分析错题数据生成学习报告 |

## Acceptance Criteria
1. `GET /api/admin/agents` 返回所有 6 个 agent 节点，包含实际生效的配置和来源标记（database/default）。
2. `PUT /api/admin/agents/{node_name}` 可修改模型、温度、超时、prompt 等字段。
3. `POST /api/admin/agents/{node_name}/test` 发送测试 prompt 并返回成功/失败 + 耗时。
4. 数据库无配置记录时，自动使用 AGENT_DEFAULTS + 环境变量，系统正常运行。
5. 现有 OCR、题目分析、SVG 生成功能改造后回归正常。
6. 前端管理页面可展示和修改 agent 配置。

## Risks and Open Questions
- API Key 安全性：agent 配置表不直接存储明文密钥，通过 `api_key_ref` 引用 provider 级别密钥。
- 缓存策略：当前每次请求从 DB 读取配置（SQLite 读取延迟极低），后续迁移到 PostgreSQL 时可加 TTL 缓存。
- Prompt 管理：本阶段 system_prompt 和 user_prompt_template 均可为空（使用代码默认值），后续可扩展为必填。
