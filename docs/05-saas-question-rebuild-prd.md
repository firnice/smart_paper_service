# SaaS主导试题重建方案 - Product PRD

- ID: 05
- Topic: `saas-question-rebuild`
- Stage: `prd`
- Status: Review
- File: `05-saas-question-rebuild-prd.md`
- Upstream: N/A
- Downstream: [06-saas-question-rebuild-architecture.md](./06-saas-question-rebuild-architecture.md)

## Problem
- 家长/老师上传作业拍照后，常包含红蓝笔批注、歪斜、阴影和噪点，导致 OCR 识题不稳、图示框偏移、题目重建质量波动。
- 纯 SaaS 链路在脏图场景下失败率较高，且调用成本不可控。
- 当前缺少“低置信度回退到人工精修”的显式状态，容易出现错误自动替换。

## Goals
- 以 SaaS 为主、以本地轻量预处理为兜底，提升识题稳定性并控制调用成本。
- 将题目重建结果输出为结构化 JSON，供后续卡片化、导出和人工校对复用。
- 对低置信度结果不做强替换，统一标注为“需人工精修”。

## Success Metrics
- 题目识别成功率（含 question_box）>= 95%（标准拍照样本），>= 90%（含批注样本）。
- 图示框可用率（image_box 可裁剪且有有效内容）>= 92%。
- 结构化 JSON 通过 schema 校验比例 >= 95%。
- 低置信度样本全部标记为 `need_manual_refine`，误自动发布率 <= 1%。
- 去手写 SaaS 调用占比 <= 25%（优先本地规则法处理）。

## Scope
- In scope:
- 本地 OpenCV 预处理：拉正、置白、降噪。
- 调用现有千问视觉 SaaS：返回 `question_box` / `image_box` / `text`。
- 本地规则法去批注：红蓝笔阈值 + 连通域 + 文本行保护。
- 本地去批注失败时，按条件回退到去手写 SaaS。
- 用 OCR 文本 + 图示小图驱动 LLM 输出结构化题目 JSON。
- 输出低置信度状态为 `need_manual_refine`，进入人工精修队列。

- Out of scope:
- 替换当前 OCR SaaS 供应商。
- 追求 100% 全自动改写与发布。
- 在本阶段扩展与该链路无关的后端功能。

## User Stories
- 作为家长，我希望上传带批注的题纸后仍能得到可读题目草稿，减少手工录入。
- 作为教研人员，我希望系统保留图示并输出结构化 JSON，方便后续复用到题库。
- 作为运营/质检，我希望低置信度样本自动进入“需人工精修”，避免错误内容直接流出。

## Acceptance Criteria
1. 上传图片后，系统必须先执行本地预处理，再调用识题 SaaS。
2. 识题 SaaS 返回结果中，题目需包含 `text`，并尽量包含 `question_box`；有图示时返回 `image_box`。
3. 去批注必须默认先走本地规则法，仅在本地失败条件命中时调用去手写 SaaS。
4. LLM 重建输出必须是可通过 schema 校验的 JSON（题干、选项/小问、图示引用、元信息）。
5. 每道题都必须产出置信度；低于阈值时状态必须为 `need_manual_refine`。
6. `need_manual_refine` 状态不得自动替换线上题目内容。
7. 响应中需返回阶段性处理信息（预处理、识题、去批注、重建、置信度）。
8. 关键指标可观测：成功率、回退率、SaaS 调用占比、平均耗时。

## Risks and Open Questions
- 去批注规则在彩色教材/彩印题纸上的误伤风险需要专项样本验证。
- 去手写 SaaS 的接口 SLA 和单价波动可能影响高峰期吞吐。
- 置信度阈值需要通过离线标注样本迭代，不宜一次性拍脑袋固定。
