# 原题重做与举一反三 - Architecture Design

- ID: 35
- Topic: `practice-redo`
- Stage: `architecture`
- Status: Draft
- File: `35-practice-redo-architecture.md`
- Upstream: [34-practice-redo-prd.md](./34-practice-redo-prd.md)
- Downstream: N/A

## Requirement Mapping
| PRD 验收项 | 设计决策 |
| --- | --- |
| 原题重做弹窗 | 新建 `PracticeModal.jsx` 组件 |
| 批量多选重做 | `QuestionBankPage` 增加多选模式 + `PracticeSession.jsx` |
| 举一反三 | 后端 `POST /api/variants/generate-for-question` + 前端弹窗 |
| 快速标记掌握 | 错题卡片增加状态切换按钮，调用现有 update API |
| 打印集成 | 错题本增加"打印选中"按钮，跳转 PrintPage |

## System Design

### 组件架构

```
QuestionBankPage.jsx (错题本主页)
├── 多选模式开关
├── 每个错题卡片
│   ├── StatusToggle 快速标记
│   ├── [重做] → PracticeModal (单题重做)
│   └── [举一反三] → VariantModal (LLM 出题)
├── 底部工具栏 (多选模式)
│   ├── [批量重做] → PracticeSession (批量模式)
│   └── [打印选中] → navigate to PrintPage
└── PracticeModal / VariantModal / PracticeSession
```

### 新建前端组件

**`src/components/practice/PracticeModal.jsx`**
```jsx
// 单题重做弹窗
Props: { question, onResult, onClose }
- 展示题目 (title, content, imageUrl)
- 三个按钮: 做对了 / 做错了 / 跳过
- 点击后调用 onResult(questionId, result)
- 创建 study_record, 刷新错题状态
```

**`src/components/practice/VariantModal.jsx`**
```jsx
// 举一反三弹窗
Props: { question, onClose }
- 调用 generateVariantsForQuestion API
- Loading 状态: "AI 正在出题..."
- 逐题展示:
  - 题目文本
  - [查看答案] 折叠面板 (answer + hint)
  - [做对了] [做错了] [下一题]
- 全部完成后显示汇总
```

**`src/components/practice/PracticeSession.jsx`**
```jsx
// 批量练习会话
Props: { questions[], mode: "redo"|"variant", onComplete, onExit }
- 进度条: 第 N/M 题
- 使用 PracticeModal 逐题展示
- 完成后汇总: X 道做对, Y 道做错, Z 道跳过
```

### 后端接口

#### 举一反三 (新增)

```
POST /api/variants/generate-for-question
Request: { wrong_question_id: int, count: int = 3 }
Response: {
  source_question_id: int,
  items: [
    { text: str, answer: str?, hint: str? }
  ]
}
```

**LLM Prompt**:
```
你是小学{grade}的出题老师。根据以下原题，出{count}道类似但数字/情境不同的练习题。
每道题要有参考答案和一句解题提示。

原题：{question_text}
学科：{subject}

请返回严格 JSON 数组:
[{"text": "题目文本", "answer": "参考答案", "hint": "一句解题提示"}]
```

#### 快速标记 (复用已有)
```
PUT /api/wrong-questions/{id}
Body: { status: "mastered" }
```

#### 创建学习记录 (复用已有)
```
POST /api/wrong-questions/{id}/study-records
Body: { student_id, result: "correct"|"incorrect"|"skipped", mastery_level }
```

### 改动文件清单

| 文件 | 改动 |
|------|------|
| `src/components/practice/PracticeModal.jsx` | **新建** |
| `src/components/practice/VariantModal.jsx` | **新建** |
| `src/components/practice/PracticeSession.jsx` | **新建** |
| `src/pages/QuestionBankPage.jsx` | 多选模式、快速标记、重做/举一反三/打印入口 |
| `src/pages/student/StudentDashboardPage.jsx` | 错题卡片增加操作按钮 |
| `src/pages/PrintPage.jsx` | 支持 URL query 预选 |
| `src/services/api.js` | 增加 generateVariantsForQuestion |
| `src/services/studentDemo.js` | Demo 模式变体生成 |
| `app/services/variant_service.py` | 结构化输出 + agent 配置 |
| `app/schemas/variants.py` | 新增 VariantItem 等 |
| `app/api/routes/variants.py` | 新增 generate-for-question 端点 |

### 数据流

**原题重做**:
```
用户点 [重做] → PracticeModal 显示题目
→ 用户标记结果 → POST study_record → PUT wrong_question.status
→ 刷新列表 → 统计更新
```

**举一反三**:
```
用户点 [举一反三] → VariantModal → POST /api/variants/generate-for-question
→ 后端 LLM 生成变体 → 前端逐题展示
→ 用户做题 → 显示汇总（变体结果不入库）
```

### Demo 模式

```javascript
// studentDemo.js 新增
export function demoGenerateVariants(wrongQuestionId) {
  const question = findQuestion(wrongQuestionId);
  return {
    source_question_id: question.id,
    items: [
      { text: `(变式1) ${question.content.replace(/\d+/g, () => Math.floor(Math.random()*100))}`,
        answer: "参考答案", hint: "注意审题" },
      { text: `(变式2) 类似题目...`, answer: "参考答案", hint: "方法相同" },
    ]
  };
}
```
