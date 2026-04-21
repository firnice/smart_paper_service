# Smart Paper LLM Wiki 索引

## Schema 文件

- [CLAUDE.md](../../CLAUDE.md): 当前 wiki 的操作约束、页面规则和 ingest/query/lint 工作流。

## 核心页面

- [wiki/project-overview.md](./wiki/project-overview.md): 项目目标、当前能力、主要用户流和状态判断。
- [wiki/current-phase-and-constraints.md](./wiki/current-phase-and-constraints.md): 当前阶段约束、frontend-first 临时规则和知识维护边界。
- [wiki/backend-architecture.md](./wiki/backend-architecture.md): FastAPI 运行时结构、服务层分工和主要处理链路。
- [wiki/api-surface.md](./wiki/api-surface.md): 当前 API 面按领域分组的 inventory。
- [wiki/data-model.md](./wiki/data-model.md): 主要实体、表群分层和关键关系。
- [wiki/repo-layout.md](./wiki/repo-layout.md): 代码、迁移、文档、脚本、测试和本地产物目录职责。
- [wiki/document-map.md](./wiki/document-map.md): `docs/` 内产品文档与技术文档的地图和读取顺序。

## 原始来源条目

- [raw/2026-04-21-karpathy-llm-wiki-pattern.md](./raw/2026-04-21-karpathy-llm-wiki-pattern.md): 外部模式来源快照。
- [raw/2026-04-21-repo-bootstrap.md](./raw/2026-04-21-repo-bootstrap.md): 初始化本 wiki 时使用的仓库来源清单。
- [raw/README.md](./raw/README.md): raw 层约定。

## 建议的下一轮入库

- `docs/38-v2-backend-adaptation.md`
- `docs/05` 到 `docs/08` 的 OCR / 重建链路文档组
- `app/api/routes/ocr.py` 与 `app/services/` 下 OCR、rebuild、export、analysis 相关服务
- 活跃测试文件与当前前端联调相关回归点
