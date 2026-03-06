# SaaS主导试题重建方案 - Architecture Design

- ID: 06
- Topic: `saas-question-rebuild`
- Stage: `architecture`
- Status: Review
- File: `06-saas-question-rebuild-architecture.md`
- Upstream: [05-saas-question-rebuild-prd.md](./05-saas-question-rebuild-prd.md)
- Downstream: [07-saas-question-rebuild-implementation.md](./07-saas-question-rebuild-implementation.md)

## Requirement Mapping
| PRD 验收项 | 设计决策 |
| --- | --- |
| 先预处理再识题 | 在 OCR 路由入口增加本地预处理链路（拉正/置白/降噪） |
| 返回 question_box/image_box/text | 沿用现有千问视觉识题接口，统一映射到标准字段 |
| 去批注优先本地 | 本地规则去批注作为主路径，失败条件触发 SaaS 回退 |
| 输出结构化 JSON | 新增重建服务，约束统一 JSON schema |
| 低置信度不自动替换 | 增加置信度评估与状态机：`ok` / `need_manual_refine` |
| 可观测性 | 输出每阶段耗时、回退原因、成功率指标 |

## System Design
- Components:
- `app/api/routes/ocr.py`：编排总流程，汇总阶段状态。
- `app/services/image_service.py`：本地预处理与本地规则去批注。
- `app/services/ocr_service.py`：识题 SaaS 适配（question_box/image_box/text）。
- `app/services/question_rebuild_service.py`（新增）：将 OCR 文本 + 图示输入 LLM，输出 JSON。
- `app/services/confidence_service.py`（新增）：融合规则与模型信号计算置信度。
- `app/services/annotation_clean_service.py`（新增，可选）：对接去手写 SaaS。

- Data flow:
1. 接收上传图像。
2. 本地预处理（拉正、置白、降噪）。
3. 调用视觉 SaaS 识题，得到 `question_box/image_box/text`。
4. 针对图示区域执行本地规则去批注（红蓝阈值 + 连通域 + 文本行保护）。
5. 若本地去批注失败，调用去手写 SaaS 获取清洁图。
6. 组合 OCR 文本 + 图示小图，调用 LLM 重建结构化题目 JSON。
7. 计算置信度并设置题目状态（`ok` 或 `need_manual_refine`）。
8. 返回结果并记录阶段指标。

- API/contracts:
- 输入：现有 `/api/ocr/extract` 上传图片接口保持不变。
- 输出（增量字段建议）：
```json
{
  "paper_id": 123,
  "items": [
    {
      "id": 1,
      "text": "1. ...",
      "question_box": {"ymin": 10, "xmin": 20, "ymax": 400, "xmax": 980},
      "image_box": {"ymin": 120, "xmin": 600, "ymax": 340, "xmax": 920},
      "rebuild_json": {"stem": "...", "options": ["A...", "B..."]},
      "confidence": 0.72,
      "status": "need_manual_refine",
      "stage_metrics": {
        "preprocess_ms": 36,
        "ocr_ms": 1460,
        "clean_ms": 91,
        "rebuild_ms": 420,
        "clean_fallback": true
      }
    }
  ]
}
```

## Data and Migration Impact
- 第一阶段建议不改数据库结构：
- `rebuild_json`、`confidence`、`status` 先作为接口返回与临时存储产物。
- 可将阶段日志写入现有日志/对象存储，降低迁移风险。
- 第二阶段若需长期沉淀，再引入数据库字段或独立结果表。

## Risk and Rollback
- Key risks:
- 本地规则法在复杂底纹题纸上误擦正文。
- 去手写 SaaS 峰值超时导致整体尾延迟上升。
- LLM 输出偶发 schema 不稳定。

- Rollback path:
- 通过 feature flag 关闭新增链路，仅保留当前 OCR 流程。
- 关闭去手写 SaaS 回退，仅保留本地规则并标记人工精修。
- 关闭自动重建，仅返回 OCR 结果与图示裁剪。

## Milestones
1. M1（1 周）：接入预处理 + 识题结果稳定性回归。
2. M2（1 周）：完成本地去批注与 SaaS 回退策略。
3. M3（1 周）：完成 LLM 结构化重建 + 置信度评分 + 状态机。
4. M4（3-5 天）：联调验收、指标看板、灰度发布。
