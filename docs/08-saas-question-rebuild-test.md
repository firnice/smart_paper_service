# SaaS主导试题重建方案 - Test Validation

- ID: 08
- Topic: `saas-question-rebuild`
- Stage: `test`
- Status: In Progress (待执行样本回归)
- File: `08-saas-question-rebuild-test.md`
- Upstream: [07-saas-question-rebuild-implementation.md](./07-saas-question-rebuild-implementation.md)
- Downstream: N/A

## Test Plan
- Test scope:
- 本地预处理有效性（拉正、置白、降噪）。
- SaaS 识题字段完整性（`question_box/image_box/text`）。
- 本地去批注质量与回退触发准确性。
- 结构化重建 JSON 可用性（LLM 正常 / LLM 降级两种路径）。
- 置信度与状态机（`ok` / `need_manual_refine`）一致性。

- Environment:
- 后端：`lf-smart-paper-service` 本地环境。
- 样本集：A 组干净题纸 50 张；B 组轻度红蓝批注 50 张；C 组重度手写/遮挡 30 张。
- SaaS：现网千问视觉服务 + 去手写 SaaS（仅回退时启用）。

## Test Cases
| ID | Scenario | Expected | Actual | Result |
| --- | --- | --- | --- | --- |
| 1 | 上传歪斜图片 | 预处理后方向正确，识题正常 | 待执行 | 待执行 |
| 2 | 灰暗底色图片 | 置白后可读性提升，识题成功 | 待执行 | 待执行 |
| 2.1 | OpenCV 不可用 | 自动回退标准化链路，不报 500 | 通过导入与编译路径验证（`cv2` 缺失不会导致路由导入失败） | 通过（静态） |
| 2.2 | `/api/ocr/extract` 响应 | 包含 `pipeline_metrics` 且有 `clean_ms/rebuild_ms/manual_refine_count` | 通过 schema 与路由构建校验，字段已接入 | 通过（静态） |
| 3 | 红笔批注图示 | 本地规则法清理有效，`clean_source=local_rule` | 待执行 | 待执行 |
| 4 | 蓝笔批注图示 | 本地规则法清理有效，`clean_source=local_rule` | 待执行 | 待执行 |
| 5 | 本地清理不足且 SaaS 可用 | 自动触发回退，`clean_fallback=true` | 待执行 | 待执行 |
| 5.1 | 本地清理不足且 SaaS 关闭 | 不报错，`clean_fallback=false` 且 reason 含 `saas_disabled` | 待执行 | 待执行 |
| 5.2 | SaaS 返回无效图 | 保留本地结果，reason 含 `saas_failed` | 待执行 | 待执行 |
| 5.3 | 图示抠图形状 | 输出透明 PNG，非整块白底矩形 | 专项脚本验证 alpha 通道存在且覆盖率合理 | 通过 |
| 6 | LLM 可用 | 返回 `rebuild_json.source=llm` | 在当前环境调用 `rebuild_question_json` 返回 `llm` | 通过 |
| 6.1 | LLM 不可用 | 回退规则法，`rebuild_json.source=heuristic` | 通过专项脚本校验了回退契约（source in {llm, heuristic}） | 通过（契约） |
| 7 | 低置信度样本 | `status=need_manual_refine` | 待执行 | 待执行 |
| 7.1 | 高置信度样本 | `status=ok` | 待执行 | 待执行 |

## Defects
- Severity: 暂无阻断缺陷。
- Repro steps: 未发现失败用例。
- Status: Open（等待真实样本回归）。

## Execution Notes
- 2026-03-05 本地执行：`./.venv/bin/python tests/test_ocr_pipeline.py`
- 结果：4/4 通过
  - `annotation_rule_cleaning`
  - `rebuild_contract`
  - `shape_cutout_has_alpha`
  - `confidence_assessment`

## Final Verdict
- Go / No-Go: No-Go（待样本回归与阈值校准完成后再转 Go）。
- Remaining risks:
- 彩色教材和复杂背景下，规则阈值在不同机型拍照条件下可能波动。
- 去手写 SaaS 的 SLA、成本与峰值限流会影响回退成功率。
- 置信度阈值未经过离线标注集校准，仍需迭代。
