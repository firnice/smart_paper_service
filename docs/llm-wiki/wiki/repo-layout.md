# 仓库布局

## 摘要

当前仓库的目录边界比较清晰，业务代码集中在 `app/`，文档集中在 `docs/`，迁移脚本在 `alembic/`，本地产物固定在 `storage/` 和 `logs/`。LLM Wiki 需要遵守这个结构，不应打散既有布局。

## 关键点

| Path | Responsibility |
| --- | --- |
| `app/` | FastAPI 运行时代码 |
| `app/api/routes/` | HTTP 路由层 |
| `app/services/` | 业务服务与 LLM/OCR/导出逻辑 |
| `app/db/` | 会话、base 和模型 |
| `app/schemas/` | Pydantic 请求/响应模型 |
| `app/core/` | 配置、鉴权、限流、trace、日志 |
| `alembic/` | 迁移脚本 |
| `docs/` | 产品和技术文档 |
| `docs/llm-wiki/` | 本次新增的知识层，不替代既有 `docs/` |
| `scripts/` | 开发辅助脚本 |
| `tests/` | 冒烟与回归测试 |
| `storage/` | 本地存储产物 |
| `logs/` | 本地运行日志 |

## 对 Wiki 重要的放置规则

- 普通 markdown 文档仍然应放在 `docs/` 下。
- 根级 [CLAUDE.md](../../../CLAUDE.md) 是 schema 例外，不应扩展成更多根级说明文件。
- wiki 的综合页统一放在 `docs/llm-wiki/wiki/`。
- wiki 的来源快照统一放在 `docs/llm-wiki/raw/`。
- 不要把运行时代码、脚本或测试放到 wiki 目录。

## 仓库特定约束

- 所有 backend 命令都应从 repo root 运行。
- 路径逻辑不能依赖父目录。
- 当前阶段不要主动扩展 backend feature scope，除非是用户明确要求的 blocking fix。

## 开放问题

- `.claude/`、`.superpowers/` 等辅助目录在长期上是否需要单独文档化，取决于它们是否会影响主要开发流程。
- 如果后续 wiki 继续增长，是否需要增加 topic 子目录而不是全部平铺在 `wiki/` 下。

## 来源

- [../../../AGENTS.md](../../../AGENTS.md)
- [../../CODE_LAYOUT.md](../../CODE_LAYOUT.md)
- [../../../README.md](../../../README.md)
