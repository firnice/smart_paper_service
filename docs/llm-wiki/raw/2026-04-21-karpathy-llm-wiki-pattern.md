# 2026-04-21 Karpathy LLM Wiki 模式

## 来源

- Original gist: <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>

## 摘要

Karpathy 的模式不是在 query 时反复对原始文档做 RAG，而是让 LLM 增量维护一个持久化 wiki。这个 wiki 是介于“原始来源”和“最终回答”之间的知识层，重点在于持续综合、交叉链接、冲突标记和低成本维护。

## 关键点

- 知识层分三层：
  - raw sources：原始文档，作为 source of truth，不让 LLM 直接改写。
  - wiki：LLM 维护的 markdown 页面集合。
  - schema：告诉 LLM 如何 ingest、query、lint 的约束文件，例如 `CLAUDE.md` 或 `AGENTS.md`。
- 典型操作有三类：
  - ingest：读入新来源，更新多个 wiki 页面、索引和日志。
  - query：先查 wiki，再回答问题；好的回答也可以反写回 wiki。
  - lint：检查矛盾、孤儿页、过时结论、缺失链接和可继续调研的空白。
- `index.md` 和 `log.md` 是两个关键辅助文件：
  - `index.md` 面向内容导航。
  - `log.md` 面向时间线与可追溯性。

## 面向本仓库的适配

- 这个仓库不是独立知识库仓，而是后端代码仓，所以 wiki 不会替代现有 `docs/`。
- 适合的做法是保留现有代码和文档不动，在 `docs/llm-wiki/` 下维护一层可增量更新的知识层。
- 根级 `CLAUDE.md` 作为 schema，其他 wiki 内容全部放到 `docs/llm-wiki/`，以符合当前仓库文档布局习惯。

## 备注

- 当前仓库已经有大量一手文档和实现文件，因此初始化重点不是“导入一堆新材料”，而是建立索引、主题页和维护规则。
- 由于项目处于 frontend-first 协调阶段，wiki 还需要明确区分“已实现后端能力”和“规划中的后端工作”。
