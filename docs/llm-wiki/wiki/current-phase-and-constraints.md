# 当前阶段与约束

## 摘要

当前仓库有一个非常关键的临时协作规则：frontend-first。也就是说，后端现阶段主要处理用户明确提出的阻塞性修复，而不是主动扩展新功能。这个约束必须进入 wiki，因为它会直接影响后续 ingest、优先级判断和“下一步建议”。

## 关键点

- 来自 [AGENTS.md](../../../AGENTS.md) 的硬约束：
  - 只在当前 repo 内修改文件。
  - backend 命令从 repo root 运行。
  - 运行时产物留在 `storage/` 和 `logs/`。
  - 不要依赖父目录工作路径。
- 当前临时规则：
  - backend 只处理用户请求的 blocking fixes。
  - 不要主动扩大 backend feature scope。
  - 这个规则在 frontend interaction/UI 确认完成后再移除。
- 来自 [docs/CODE_LAYOUT.md](../../CODE_LAYOUT.md) 的布局约束：
  - 正常文档放 `docs/`。
  - 代码放 `app/`。
  - 测试放 `tests/`。
  - 迁移放 `alembic/versions/`。

## 对 Wiki 的影响

- wiki 里的“next steps”不能默认写成“继续扩后端功能”，而应偏向：
  - 记录现状
  - 识别 drift
  - 沉淀阻塞点
  - 支持前端联调
- 如果产品文档提出了很多后端未来能力，wiki 必须把这些能力标成 `planned`，不能混写成当前执行目标。
- 根级 `CLAUDE.md` 是特例，但不应成为新增根级文档的借口；其他知识文件继续收口到 `docs/llm-wiki/`。

## 当前工作判断

- 这不是一个“空白阶段等待设计”的仓库，而是一个已经有相当多实现、同时还在持续演化的后端。
- 近期最合理的 wiki 维护方向不是写大而全架构圣经，而是建立足够稳定的索引、状态页和专题入口，帮助后续快速定位事实。

## 开放问题

- frontend-first 临时规则何时移除，需要后续在 wiki 中同步。
- 近期哪些 topic 最容易成为前端联调阻塞点，仍需根据用户请求继续增量补充。

## 来源

- [../../../AGENTS.md](../../../AGENTS.md)
- [../../CODE_LAYOUT.md](../../CODE_LAYOUT.md)
- [../../38-v2-backend-adaptation.md](../../38-v2-backend-adaptation.md)
