# SaaS主导试题重建方案 - Development Implementation

- ID: 07
- Topic: `saas-question-rebuild`
- Stage: `implementation`
- Status: In Progress (M1/M2/M3 基线完成)
- File: `07-saas-question-rebuild-implementation.md`
- Upstream: [06-saas-question-rebuild-architecture.md](./06-saas-question-rebuild-architecture.md)
- Downstream: [08-saas-question-rebuild-test.md](./08-saas-question-rebuild-test.md)

## Change Summary
- Code paths changed:
  - `app/services/image_service.py`
  - `app/services/annotation_clean_service.py`（新增）
  - `app/services/question_rebuild_service.py`（新增）
  - `app/services/confidence_service.py`（新增）
  - `app/api/routes/ocr.py`
  - `app/schemas/ocr.py`
  - `app/core/config.py`
  - `requirements.txt`

- Completed in this round:
  - M1：OCR 预处理管道（`deskew + white_balance + denoise`）与可降级开关。
  - M1：`/api/ocr/extract` 返回 `pipeline_metrics`（含 `preprocess_ms/ocr_ms/crop_ms`）。
  - M2：本地规则去批注升级为“红蓝阈值 + 连通域 + 文本区域保护 + inpaint 修复”。
  - M2：新增去手写 SaaS 回退适配器，主流程按质量信号触发回退。
  - M2：每题返回 `clean_source/clean_fallback/clean_fallback_reason`。
  - M3：新增结构化重建服务，优先 LLM，失败回退规则法。
  - M3：新增置信度打分服务，低于阈值自动标记 `need_manual_refine`。
  - M3：全局指标新增 `rebuild_ms/manual_refine_count`。
  - 质量修正：图示输出从“白底矩形块”改为“透明 alpha 真实抠图”，按形状保留轮廓。

## Feature Flags / Config
- `ENABLE_LOCAL_PREPROCESS=true`
- `ENABLE_ANNOTATION_SAAS_FALLBACK=false`（默认关闭）
- `ANNOTATION_CLEAN_API_URL=`
- `ANNOTATION_CLEAN_API_KEY=`
- `ANNOTATION_CLEAN_TIMEOUT_SECONDS=20`
- `ENABLE_REBUILD_JSON=false`（当前默认关闭；需要时手动开启）
- `REBUILD_CONFIDENCE_THRESHOLD=0.80`
- `FORCE_MANUAL_REFINE_ON_LOW_CONF=true`

## Implementation Details
- Core logic (implemented):
1. 路由层读取图片后走 `prepare_image_for_ocr_pipeline`，OpenCV 可用时预处理，不可用时自动回退。
2. 图示裁剪阶段调用 `crop_diagram_image_with_metadata`，产出本地规则去批注统计与抠图质量指标。
3. 基于 `original_mark_ratio / residual_mark_ratio / removed_pixels` 判断是否触发去手写 SaaS 回退。
4. 回退成功则替换图示输出并累加 `clean_fallback_count`；失败则保留本地结果并记录原因。
5. 对每题调用 `question_rebuild_service.rebuild_question_json` 产出结构化 JSON。
6. 对每题调用 `confidence_service.compute_rebuild_confidence` 计算置信度并写入状态。
7. 低于阈值时（默认 0.80）状态设为 `need_manual_refine`，不做强自动替换。

- Edge cases:
- OpenCV 缺失：本地预处理和连通域规则自动降级，不抛 500。
- 去手写 SaaS 未配置：记录 `...;saas_disabled`，保留本地结果。
- 去手写 SaaS 失败或返回无效图：记录 `...;saas_failed`，保留本地结果。
- LLM 不可用/响应异常：重建自动回退到规则法，仍可返回结构化 JSON。

## Deviations from Architecture
- Deviation: 当前 M3 为“基线实现”，置信度模型为规则加权，尚未做离线标注校准。
- Reason: 先保证端到端闭环可用与可观测，再做精度优化。
- Mitigation: 下一轮通过标注集做阈值/权重调优，并补充 A/B 结果。

## Verification
- Commands run:
```bash
./.venv/bin/python -m py_compile \
  app/api/routes/ocr.py \
  app/services/image_service.py \
  app/services/annotation_clean_service.py \
  app/services/question_rebuild_service.py \
  app/services/confidence_service.py \
  app/schemas/ocr.py \
  app/core/config.py \
  tests/test_ocr_pipeline.py

./.venv/bin/python -c "from app.api.routes.ocr import router; from app.services.question_rebuild_service import rebuild_question_json; from app.services.confidence_service import compute_rebuild_confidence; print('imports-ok', bool(router), rebuild_question_json('1. 2+2=?\\nA.3\\nB.4').get('source'))"

./.venv/bin/python tests/test_ocr_pipeline.py
```
- Key results:
- 语法校验通过。
- 路由与新增服务导入通过。
- 默认配置下回退关闭，不影响主流程；重建在 LLM 不可用时可自动回退规则法。
- 新增 OCR 流水线专项测试通过（3/3）。 
