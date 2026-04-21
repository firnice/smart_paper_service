# 数据模型

## 摘要

当前数据模型可以分成三层：题目采集与生成、学生错题域、LLM/分析运营域。`wrong_questions` 是学习侧核心实体，`users` 是角色与归属核心实体，`agent_configs` / `model_providers` / `llm_call_logs` 把 LLM 调用从纯代码配置提升成了可管理的数据域。

## 关键点

### 集群 1：采集与生成

| Models | Role |
| --- | --- |
| `Paper`, `Question`, `QuestionImage` | OCR 与题目识别后的原始承接实体 |
| `Variant` | 变式题内容 |
| `Export` | 导出任务与输出状态 |

### 集群 2：用户与错题领域

| Models | Role |
| --- | --- |
| `User` | 统一用户实体，区分 `student` / `parent` / `teacher` / `admin` |
| `StudentProfile` | 学生档案扩展信息 |
| `ParentStudentLink` | 家长与学生多对多关系 |
| `SchoolTerm` | 学期维度 |
| `Subject` | 学科字典 |
| `WrongQuestionCategory` | 错题分类字典 |
| `ErrorReason` | 错因字典 |
| `WrongQuestion` | 学生错题主实体 |
| `WrongQuestionErrorReason` | 错题与错因关联表 |
| `StudyRecord` | 练习与掌握记录 |
| `WrongQuestionPrintHistory` | 打印历史 |

### 集群 3：分析与 LLM 运维

| Models | Role |
| --- | --- |
| `TrendAnalysis` | 学生趋势分析任务与结果 |
| `AgentConfig` | agent 级别模型配置 |
| `ModelProvider` | 模型供应商配置 |
| `LlmCallLog` | LLM 调用日志 |

## 关键关系

- [user.py](../../../app/db/models/user.py) 中：
  - `User` 与 `StudentProfile` 是一对一。
  - `User` 通过 `ParentStudentLink` 同时扮演家长端和学生端关联角色。
  - `User` 作为学生拥有 `wrong_questions`、`study_records` 和 `print_history`。
- [wrong_question.py](../../../app/db/models/wrong_question.py) 中：
  - `WrongQuestion` 关联 `student`、`created_by_user`、`paper`、`question`、`subject`、`category`、`term`。
  - `WrongQuestion` 通过 `WrongQuestionErrorReason` 连接多个 `ErrorReason`。
  - `WrongQuestion` 通过 `StudyRecord` 跟踪练习和掌握趋势。
- [trend_analysis.py](../../../app/db/models/trend_analysis.py) 目前是偏任务记录型模型，持有输入快照、结果 JSON、状态和时间边界。

## 解读

- 这个模型结构说明仓库已经不只是“识题工具后端”，而是向“学生学习闭环后端”演进。
- `WrongQuestion` 既承接上游 OCR/Question 数据，也承接下游统计、打印、分析数据，是当前领域中心。
- LLM 管理模型的存在说明多供应商、多 agent 节点已经成为系统一级能力，而不是散落在配置文件里的实现细节。

## 开放问题

- `Paper` / `Question` / `WrongQuestion` 三层实体的边界和流转规则后续值得单独建专题页。
- `TrendAnalysis.student_id` 当前是简单整型字段，没有显式外键声明，是否为有意设计需要继续核对。
- `LlmCallLog`、`AgentConfig`、`ModelProvider` 相关关系后续应继续 ingest。

## 来源

- [../../../app/db/models/__init__.py](../../../app/db/models/__init__.py)
- [../../../app/db/models/user.py](../../../app/db/models/user.py)
- [../../../app/db/models/wrong_question.py](../../../app/db/models/wrong_question.py)
- [../../../app/db/models/trend_analysis.py](../../../app/db/models/trend_analysis.py)
- [../../../README.md](../../../README.md)
