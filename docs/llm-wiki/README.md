# Smart Paper LLM Wiki 知识库

这是 `lf-smart-paper-service` 的 repo 内 LLM Wiki。

它参考了 Karpathy 的 LLM Wiki 模式，但做了当前项目的本地化适配：不复制现有文档原文，而是在现有代码和 `docs/` 之上维护一层可持续更新的知识层。

## 目标

- 把分散在代码、README、产品文档、实现文档里的信息压缩成可导航的知识页。
- 让后续 LLM 会话优先复用已有认知，而不是重复读整仓库。
- 保留“原始材料”和“综合结论”的分层，避免 wiki 反向污染 source of truth。

## 目录

- [index.md](./index.md): 内容索引
- [log.md](./log.md): 变更日志
- [raw/](./raw/README.md): 原始来源快照和外部参考
- [wiki/](./wiki/project-overview.md): 主题页
- [../../CLAUDE.md](../../CLAUDE.md): 当前 LLM Wiki schema

## 使用原则

- 原始材料优先来自 repo 现有文件，尤其是 `app/`、`README.md` 和 `docs/`。
- `raw/` 放来源快照和外部参考，不放二次总结。
- `wiki/` 放综合页、主题页、关系页和阶段性结论。
- 每次有意义的 ingest 都应同时更新 `index.md` 和 `log.md`。
- 当代码与文档不一致时，优先相信代码，并在 wiki 明确标注 drift。
