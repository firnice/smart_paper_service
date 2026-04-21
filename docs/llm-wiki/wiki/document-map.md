# 文档地图

## 摘要

`docs/` 目录已经积累了较多产品和技术文档，但它们的语义层次并不完全一致。对于后续 LLM ingest，最重要的是先分清“产品分期文档”、“实现四件套文档”和“局部专题说明”，避免把它们混成同一种来源。

## 关键点

### 分组 1：产品路线图

- [docs/product/README.md](../../product/README.md) 是产品阶段入口。
- `docs/product/00` 到 `docs/product/05` 更偏产品愿景、阶段目标和路线图。
- 这些文档适合回答“为什么要做”与“计划做到哪里”，不适合直接当作“代码已实现事实”。

### 分组 2：实现四件套

- `docs/05` 到 `docs/24` 明显采用 `prd -> architecture -> implementation -> test` 的四件套节奏。
- 这类文档最适合按 topic ingest，因为它们天然提供了“需求、设计、实现、验证”的完整链路。
- 例子：
  - `05-08`: SaaS 主导试题重建
  - `09-12`: 前端安全去手写
  - `13-16`: text-first card
  - `17-20`: diagram three-mode
  - `21-24`: whatai diagram client

### 分组 3：基线与专题说明

- `docs/25` 到 `docs/38` 更多是功能串联、审计、适配和专项方案。
- 这批文档更像当前实现与未来改造的混合层，需要按文件逐一判断 `implemented` 和 `planned`。
- 特别是 [docs/38-v2-backend-adaptation.md](../../38-v2-backend-adaptation.md)，它直接连接当前 frontend-first 协作阶段。

### 分组 4：运维与约束文档

- [docs/CODE_LAYOUT.md](../../CODE_LAYOUT.md): 仓库目录约束。
- [docs/export/PDF_排版改进说明.md](../../export/PDF_排版改进说明.md): 导出链路的专项说明。

## 建议阅读顺序

1. 根级 [README.md](../../../README.md)
2. [docs/product/README.md](../../product/README.md)
3. [docs/CODE_LAYOUT.md](../../CODE_LAYOUT.md)
4. 与当前用户请求最相关的 topic 文档组
5. 再回到 `app/` 下对应代码核对实现状态

## 开放问题

- 现有很多文档已经有阶段跨度，后续 wiki 可能需要为“topic 与代码映射”单独建页。
- 部分实现文档状态可能已经过时，后续 lint 应显式标注哪些文档存在 drift。

## 来源

- [../../product/README.md](../../product/README.md)
- [../../CODE_LAYOUT.md](../../CODE_LAYOUT.md)
- `../../*.md`
- [../raw/2026-04-21-repo-bootstrap.md](../raw/2026-04-21-repo-bootstrap.md)
