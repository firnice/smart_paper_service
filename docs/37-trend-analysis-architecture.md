# LLM 错题趋势分析 - Architecture Design

- ID: 37
- Topic: `trend-analysis`
- Stage: `architecture`
- Status: Draft
- File: `37-trend-analysis-architecture.md`
- Upstream: [36-trend-analysis-prd.md](./36-trend-analysis-prd.md)
- Downstream: N/A

## Requirement Mapping
| PRD 验收项 | 设计决策 |
| --- | --- |
| 异步执行 | FastAPI BackgroundTasks（不引入 Celery） |
| 结果持久化 | `trend_analyses` 表存储完整报告 JSON |
| 分析 API | `app/api/routes/analysis.py` |
| 前端展示 | 错题本页面"AI 学习分析"区域 + 轮询 |
| 历史报告 | `GET /api/analysis/trend?student_id=X` 列表 |

## System Design

### 数据模型

```sql
CREATE TABLE trend_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    -- pending → running → completed / failed
    start_date DATE,
    end_date DATE,
    subject_filter VARCHAR(64),          -- null = 全部学科
    input_snapshot TEXT,                  -- 分析时的统计数据快照 (JSON)
    analysis_result TEXT,                 -- LLM 返回的分析报告 (JSON)
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE INDEX idx_trend_analyses_student ON trend_analyses(student_id);
CREATE INDEX idx_trend_analyses_status ON trend_analyses(status);
```

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/analysis/trend` | 发起趋势分析（异步） |
| GET | `/api/analysis/trend/{id}` | 查询分析结果 |
| GET | `/api/analysis/trend/latest` | 查询学生最新分析 |
| GET | `/api/analysis/trend` | 列出学生的历史分析报告 |

**发起分析请求**:
```json
POST /api/analysis/trend
{
  "student_id": 1,
  "start_date": "2026-01-01",   // 可选
  "end_date": "2026-03-26",     // 可选
  "subject_filter": null         // 可选，null=全学科
}
Response: { "id": 5, "status": "pending" }
```

**查询结果**:
```json
GET /api/analysis/trend/5
{
  "id": 5,
  "status": "completed",
  "created_at": "2026-03-26T10:00:00",
  "completed_at": "2026-03-26T10:00:25",
  "analysis_result": {
    "summary": "...",
    "subject_analyses": [...],
    "weak_points": [...],
    "trend_description": "...",
    "overall_suggestions": [...],
    "encouragement": "..."
  }
}
```

### 异步执行流程

```python
@router.post("/api/analysis/trend")
def create_trend_analysis(
    payload: TrendAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    analysis = TrendAnalysis(
        student_id=payload.student_id,
        status="pending",
        start_date=payload.start_date,
        end_date=payload.end_date,
        subject_filter=payload.subject_filter,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    background_tasks.add_task(run_trend_analysis_task, analysis.id)
    return {"id": analysis.id, "status": "pending"}
```

### 分析服务

```python
# trend_analysis_service.py

def run_trend_analysis_task(analysis_id: int):
    """BackgroundTask 入口"""
    db = SessionLocal()  # 独立 session（BackgroundTask 外层 session 已关闭）
    try:
        analysis = db.query(TrendAnalysis).get(analysis_id)
        analysis.status = "running"
        db.commit()

        # 1. 收集统计数据
        snapshot = collect_student_stats(db, analysis.student_id, ...)
        analysis.input_snapshot = json.dumps(snapshot, ensure_ascii=False)
        db.commit()

        # 2. 构建 prompt
        prompt = build_analysis_prompt(snapshot, analysis)

        # 3. 调用 LLM
        llm_client, config = get_llm_client_for_agent(db, "trend_analyze")
        response = llm_client.chat_completions(...)

        # 4. 解析结果
        result = parse_analysis_result(response)

        # 5. 保存
        analysis.analysis_result = json.dumps(result, ensure_ascii=False)
        analysis.status = "completed"
        analysis.completed_at = func.now()
        db.commit()
    except Exception as exc:
        analysis.status = "failed"
        analysis.error_message = str(exc)
        db.commit()
    finally:
        db.close()
```

### LLM Prompt 设计

**System Prompt**:
```
你是一位经验丰富的小学教育专家，擅长从错题数据中分析学生的学习状况。
请根据数据给出专业、具体、鼓励性的分析和建议。
仅返回严格 JSON，不要输出任何其他内容。
```

**User Prompt**:
```
学生：{name}，{grade}
分析时段：{date_range}

【错题统计】
- 总计 {total} 道错题，其中新错题 {new} 道，复习中 {reviewing} 道，已掌握 {mastered} 道
- 掌握率：{mastery_rate}%

【各学科错题分布】
{subject_breakdown}

【高频错因 TOP5】
{reason_breakdown}

【近期学习趋势】（每日做对/做错次数）
{daily_trend}

请分析以上数据，返回 JSON：
{
  "summary": "总体评价（2-3句话）",
  "subject_analyses": [
    {"subject": "学科", "severity": "正常/需关注/需重点加强",
     "detail": "详细分析", "suggestions": ["建议1", "建议2"]}
  ],
  "weak_points": ["薄弱点1", "薄弱点2"],
  "trend_description": "趋势描述",
  "overall_suggestions": [
    {"priority": "high/medium/low", "content": "建议内容"}
  ],
  "encouragement": "鼓励语"
}
```

### 前端轮询策略

```javascript
async function pollAnalysis(analysisId) {
  const MAX_RETRIES = 30;
  const INTERVAL_MS = 2000;

  for (let i = 0; i < MAX_RETRIES; i++) {
    const result = await getTrendAnalysis(analysisId);
    if (result.status === "completed") return result;
    if (result.status === "failed") throw new Error(result.error_message || "分析失败");
    await new Promise(r => setTimeout(r, INTERVAL_MS));
  }
  throw new Error("分析超时，请稍后查看历史报告");
}
```

### 改动文件清单

| 文件 | 改动 |
|------|------|
| `app/db/models/trend_analysis.py` | **新建** TrendAnalysis 模型 |
| `app/db/models/__init__.py` | 注册新模型 |
| `app/services/trend_analysis_service.py` | **新建** 分析服务 |
| `app/api/routes/analysis.py` | **新建** 分析路由 |
| `app/schemas/analysis.py` | **新建** 分析 Schema |
| `app/api/router.py` | 注册 analysis 路由 |
| `alembic/versions/xxx_add_trend_analyses.py` | **新建** 迁移脚本 |
| `src/pages/QuestionBankPage.jsx` 或 `StudentDashboardPage.jsx` | 增加"AI 分析"区域 |
| `src/services/api.js` | 增加分析相关 API |
| `src/services/studentDemo.js` | Demo 分析结果 |

### 超时与重试

- BackgroundTask 内部 LLM 调用超时：180 秒（由 agent 配置控制）。
- 前端轮询超时：60 秒（30 次 × 2 秒间隔）。
- 异常恢复：检测 `status="running"` 超过 5 分钟的记录，自动标记为 `failed`（可选定时任务，本期不实现）。

### Demo 模式

```javascript
export function demoTrendAnalysis(studentId) {
  return {
    id: Date.now(),
    status: "completed",
    analysis_result: {
      summary: "小红同学近期在数学方面有明显进步，但语文看图写话仍需加强练习。",
      subject_analyses: [
        { subject: "数学", severity: "正常", detail: "...", suggestions: [...] },
        { subject: "语文", severity: "需关注", detail: "...", suggestions: [...] },
      ],
      weak_points: ["看图写话的描述完整性", "两位数进位加法"],
      trend_description: "整体呈进步趋势，数学掌握率提升明显",
      overall_suggestions: [
        { priority: "high", content: "每天练习一道看图写话" },
      ],
      encouragement: "你的数学进步很大，继续加油！语文也会越来越好的！"
    }
  };
}
```
