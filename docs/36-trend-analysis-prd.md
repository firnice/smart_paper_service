# LLM 错题趋势分析 - Product PRD

- ID: 36
- Topic: `trend-analysis`
- Stage: `prd`
- Status: Draft
- File: `36-trend-analysis-prd.md`
- Upstream: [32-agent-config-prd.md](./32-agent-config-prd.md)
- Downstream: [37-trend-analysis-architecture.md](./37-trend-analysis-architecture.md)

## Problem
- 家长/老师无法快速了解学生的错题趋势和薄弱环节。
- 当前统计页面只有数量统计（错题数、掌握率等），缺少深度分析和专业建议。
- 没有按学科/时间段的深度分析，无法指出学生具体应该关注什么。
- 缺少"怎么学"的专业指导（情况是否严重、改进方向、学习建议）。

## Goals
- 提供 LLM 驱动的错题趋势分析功能，生成专业分析报告。
- 报告包含：总体评价、各学科分析、薄弱知识点、改进建议、趋势描述。
- 异步执行（LLM 调用耗时较长），不阻塞用户操作。
- 分析结果持久化保存，支持查看历史报告。
- 支持多学科汇总评价和单学科深度指导。

## Success Metrics
- 分析报告在 30 秒内完成生成。
- 报告内容覆盖：总评 + 各学科分析 + 薄弱点 + 建议 + 鼓励语。
- 历史报告可查看、可对比。
- 用户满意度：报告建议被认为"有参考价值"占比 >= 70%。

## Scope
- In scope:
  - `trend_analyses` 数据库表。
  - 异步分析服务（FastAPI BackgroundTasks）。
  - 分析 API（发起 / 查询 / 查最新）。
  - 前端"AI 学习分析"区域：触发分析、轮询结果、展示报告。
  - 历史报告列表。
  - Demo 模式支持。

- Out of scope:
  - 自动定时分析（本期为手动触发）。
  - 分析报告的 PDF 导出。
  - 家长端推送通知。
  - 与外部教育知识图谱对接。

## User Stories
- 作为家长，我想点一个按钮，让 AI 帮我分析孩子最近的错题情况，告诉我应该关注什么。
- 作为家长，我想看到各学科的具体分析：哪些学科有问题、情况是否严重、怎么改进。
- 作为学生，我想看到鼓励性的反馈，知道自己的进步方向。
- 作为家长，我想查看之前的分析报告，对比孩子的进步情况。

## 分析报告结构

```json
{
  "summary": "整体评价（2-3句话，概括学习状态和主要发现）",
  "subject_analyses": [
    {
      "subject": "数学",
      "severity": "需要关注",
      "error_count": 5,
      "mastered_count": 2,
      "detail": "详细分析（高频错因、知识点薄弱区域）",
      "suggestions": ["建议1", "建议2"]
    }
  ],
  "weak_points": ["薄弱知识点1", "薄弱知识点2"],
  "trend_description": "近期趋势描述（进步/退步/平稳，对比上次）",
  "overall_suggestions": [
    { "priority": "high", "content": "最重要的改进建议" },
    { "priority": "medium", "content": "次要建议" }
  ],
  "encouragement": "给学生的鼓励话语"
}
```

## Acceptance Criteria
1. 点击"生成分析报告"后，系统异步执行分析，UI 显示加载状态。
2. 分析完成后（通常 10-30 秒），结果自动展示在页面上。
3. 报告包含 summary、subject_analyses、weak_points、suggestions、encouragement 全部字段。
4. 各学科分析能准确反映该学科的错题数量和掌握情况。
5. 分析结果持久化保存，可在历史列表中查看。
6. 分析失败时显示友好的错误提示，不影响其他功能。
7. Demo 模式下返回预设分析结果，无延迟。
