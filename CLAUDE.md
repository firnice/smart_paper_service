# CLAUDE.md

本文件是当前仓库的 repo-local LLM Wiki schema。

这个根级 markdown 文件是有意保留的例外。仓库内普通文档仍然应放在 `docs/` 下，但 `CLAUDE.md` 这类 schema 文件按惯例放在仓库根目录。

## 目标

- 将 `docs/llm-wiki/` 维护为 `lf-smart-paper-service` 的持久知识层。
- 将仓库现有代码与文档视为 source material，将 wiki 视为 LLM 持续维护的综合层。
- 优先更新 wiki，而不是在后续会话里反复从零理解整个仓库。

## 仓库约束

- 以 [AGENTS.md](./AGENTS.md) 作为基础工作约束。
- 仅修改当前仓库内文件。
- 所有 backend 命令从 repo root 运行。
- 运行时产物保留在 `storage/` 与 `logs/`。
- 不要引入依赖父目录工作路径的逻辑。
- 当前临时协作规则是 frontend-first：在前端交互/UI 未确认完成前，backend 仅处理用户明确提出的阻塞性修复。

## 知识库布局

- `docs/llm-wiki/raw/`：原始来源快照，保持不可变或仅追加。
- `docs/llm-wiki/wiki/`：由 LLM 维护的综合主题页。
- `docs/llm-wiki/index.md`：内容索引。
- `docs/llm-wiki/log.md`：追加式活动日志。
- `docs/llm-wiki/README.md`：面向人的入口说明。

## 来源优先级

当来源之间出现冲突时，按以下优先级处理：

1. `app/` 下的运行时代码
2. `app/db/models/` 下的数据模型与 `alembic/` 迁移脚本
3. 根级 [README.md](./README.md)
4. `docs/` 下的技术与产品文档
5. `tests/` 下的测试文件

如果代码和文档不一致，wiki 必须明确标注 drift，而不是静默选择其一。

## 页面约定

- 仓库叙述与综合内容默认使用中文。
- 文件路径、标识符、环境变量、路由路径、模型名保持英文原样。
- 以高密度综合为主，不复制原文。
- 普通 wiki 页面通常包含：
  - `## 摘要`
  - `## 关键点`
  - `## 开放问题` 或 `## 当前风险`
  - `## 来源`
- 使用相对 markdown 链接。
- 明确区分 `planned` 与 `implemented`。
- 已实现结论尽量锚定到具体代码、路由或模型文件。
- 不要把大段来源原文直接粘贴进 wiki。

## 原始来源规则

- `docs/llm-wiki/raw/` 下的文件使用 `YYYY-MM-DD-topic.md` 命名。
- raw 条目用于保存来源快照、采集记录或外部参考。
- raw 文件创建后不要重写，只允许做小的事实或元数据修正。
- 如果来源已经存在于仓库内，优先在 raw 文件中链接原文件，而不是复制整篇内容。

## 入库工作流

当有新来源进入时：

1. 判断来源是否已经存在于仓库中，还是外部/对话型来源。
2. 如果是外部来源，或需要保留当日快照，就在 `docs/llm-wiki/raw/` 下新增条目。
3. 更新 `docs/llm-wiki/wiki/` 下一个或多个综合页面。
4. 更新 `docs/llm-wiki/index.md`。
5. 向 `docs/llm-wiki/log.md` 追加一条日志。
6. 如果新来源改变了长期维护规则，也同步更新本文件。

本仓库常见的 ingest 触发条件：

- `docs/` 下新增一组 `PRD / architecture / implementation / test` 文档
- 新增一个 route group 或明显改变现有路由契约
- 数据模型发生有意义变更
- OCR、rebuild、export、statistics、admin LLM 配置等主链路发生新变化
- 当前协作约束或阶段边界发生变化

## 查询工作流

- 优先从 wiki 回答，再按需下钻 raw 文件和源码。
- 明确区分事实、推断和解释。
- 如果某次问答沉淀出了长期有效的项目知识，应该反写回 wiki，而不是留在聊天记录里。

适合反写回 wiki 的知识包括：

- 架构对比
- 迁移或 rollout 清单
- 数据模型关系解释
- 重要实现轮次的“变了什么、为什么变”

## 巡检工作流

定期检查 wiki：

- 是否存在缺少有效入链的页面
- 是否缺少相关功能、路由、模型之间的链接
- 是否把 planned 内容写成了 implemented
- 是否存在 code/docs drift
- 阶段状态是否过期
- 是否缺少来源引用
- README、`docs/` 与运行时代码之间是否互相矛盾

如果 lint 导致 wiki 发生修改，必须同步更新 `index.md` 并在 `log.md` 追加记录。

## 本仓库的优先跟踪主题

wiki 需要优先保持以下主题最新：

- API 面和路由归属
- OCR 与题目重建链路
- 错题生命周期、训练与打印流程
- 用户 / 学生 / 家长关系模型
- 统计与趋势分析流程
- admin agent / model-provider 配置
- 仓库布局与文档地图
- 当前阶段约束与 frontend-first 协作状态

## 不要做

- 除本根级 schema 外，不要在 `docs/llm-wiki/` 之外创建知识页。
- 不要把既有产品文档原样改写成 wiki。
- 未核对代码前，不要把规划性文档当成已实现事实。
- 在 frontend-first 临时规则生效期间，不要主动扩展 backend feature scope。
- 不要在仓库根目录散落无关 markdown 文件。

## 初始引导清单

本次 bootstrap 创建了以下核心页面：

- `docs/llm-wiki/wiki/project-overview.md`
- `docs/llm-wiki/wiki/backend-architecture.md`
- `docs/llm-wiki/wiki/api-surface.md`
- `docs/llm-wiki/wiki/data-model.md`
- `docs/llm-wiki/wiki/repo-layout.md`
- `docs/llm-wiki/wiki/document-map.md`
- `docs/llm-wiki/wiki/current-phase-and-constraints.md`

本次 bootstrap 创建了以下 raw 来源条目：

- `docs/llm-wiki/raw/2026-04-21-karpathy-llm-wiki-pattern.md`
- `docs/llm-wiki/raw/2026-04-21-repo-bootstrap.md`
