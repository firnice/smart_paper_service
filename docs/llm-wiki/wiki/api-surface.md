# API 面

## 摘要

当前 API 面已经从单纯的 OCR MVP 扩展为“识题 + 错题域 + 训练导出 + 统计分析 + LLM 管理”的组合服务。下面按 route group 做 inventory，方便后续查询与 drift 检查。

## 关键点

### 系统与鉴权

| Group | Endpoints | Notes |
| --- | --- | --- |
| `health` | `GET /api/health` | 健康检查 |
| `auth` | `GET /api/auth/student-login-config` | 学生登录配置 |
| `auth` | `POST /api/auth/student-login` | 学生登录 |
| `auth` | `POST /api/auth/admin-login` | 后台登录 |

### OCR 与题目处理

| Group | Endpoints | Notes |
| --- | --- | --- |
| `ocr` | `POST /api/ocr/extract` | 识题主链路 |
| `ocr` | `POST /api/ocr/extract/simple` | 简化识题 |
| `ocr` | `POST /api/ocr/diagram/svg` | 图示 SVG 生成 |
| `ocr` | `POST /api/ocr/analyze-question` | 题目分析 |
| `variants` | `POST /api/variants/generate` | 直接生成变式题 |
| `variants` | `POST /api/variants/generate-for-question` | 基于已有题目生成变式题 |

### 导出与练习输出

| Group | Endpoints | Notes |
| --- | --- | --- |
| `export` | `POST /api/export` | 导出任务创建 |
| `export` | `GET /api/export/{job_id}` | 导出任务状态 |
| `export` | `POST /api/print-pack/export` | 打印重做包导出 |

### 用户、元数据与错题域

| Group | Endpoints | Notes |
| --- | --- | --- |
| `users` | `POST /api/users` | 创建用户 |
| `users` | `GET /api/users` | 用户列表 |
| `users` | `GET /api/users/{user_id}` | 用户详情 |
| `users` | `PUT /api/users/{user_id}` | 更新用户 |
| `users` | `DELETE /api/users/{user_id}` | 删除用户 |
| `users` | `POST /api/users/parent-student-links` | 绑定家长-学生 |
| `users` | `DELETE /api/users/parent-student-links/{link_id}` | 解绑关系 |
| `users` | `GET /api/users/{parent_id}/students` | 查询家长名下学生 |
| `users` | `GET /api/users/{student_id}/parents` | 查询学生关联家长 |
| `metadata` | `GET /api/subjects` / `POST /api/subjects` | 学科字典 |
| `metadata` | `GET /api/wrong-question-categories` / `POST /api/wrong-question-categories` | 错题分类字典 |
| `metadata` | `GET /api/error-reasons` / `POST /api/error-reasons` | 错因字典 |
| `school-terms` | `GET /api/school-terms` | 学期列表 |
| `school-terms` | `PUT /api/users/{user_id}/term` | 用户当前学期切换 |
| `wrong-questions` | `POST /api/wrong-questions` | 创建错题 |
| `wrong-questions` | `GET /api/wrong-questions` | 错题列表 |
| `wrong-questions` | `GET /api/wrong-questions/{wrong_question_id}` | 错题详情 |
| `wrong-questions` | `PUT /api/wrong-questions/{wrong_question_id}` | 更新错题 |
| `wrong-questions` | `DELETE /api/wrong-questions/{wrong_question_id}` | 删除错题 |
| `wrong-questions` | `POST /api/wrong-questions/{wrong_question_id}/study-records` | 新增练习记录 |
| `wrong-questions` | `GET /api/wrong-questions/{wrong_question_id}/study-records` | 查询练习记录 |

### 统计、分析与管理后台

| Group | Endpoints | Notes |
| --- | --- | --- |
| `statistics` | `GET /api/statistics/overview` | 总览 |
| `statistics` | `GET /api/statistics/by-subject` | 按学科 |
| `statistics` | `GET /api/statistics/by-grade` | 按年级 |
| `statistics` | `GET /api/statistics/by-category` | 按分类 |
| `statistics` | `GET /api/statistics/by-error-reason` | 按错因 |
| `statistics` | `GET /api/statistics/trend` | 趋势 |
| `analysis` | `POST /api/analysis/trend` | 发起趋势分析 |
| `analysis` | `GET /api/analysis/trend/latest` | 最近一次趋势分析 |
| `analysis` | `GET /api/analysis/trend/{analysis_id}` | 指定趋势分析 |
| `analysis` | `GET /api/analysis/trend` | 历史趋势分析列表 |
| `admin` | `GET /api/admin/agents` | agent 配置列表 |
| `admin` | `GET /api/admin/agents/{node_name}` | agent 配置详情 |
| `admin` | `PUT /api/admin/agents/{node_name}` | 更新 agent 配置 |
| `admin` | `POST /api/admin/agents/{node_name}/test` | 测试 agent 配置 |
| `admin` | `GET /api/admin/model-providers` | 模型供应商列表 |
| `admin` | `POST /api/admin/model-providers` | 创建模型供应商 |
| `admin` | `PUT /api/admin/model-providers/{provider_id}` | 更新模型供应商 |
| `admin` | `DELETE /api/admin/model-providers/{provider_id}` | 删除模型供应商 |
| `admin` | `GET /api/admin/llm-stats/overview` | LLM 使用总览 |
| `admin` | `GET /api/admin/llm-logs` | LLM 调用日志 |

## 开放问题

- 当前 API inventory 只基于 route decorators 做静态扫描，后续仍应对每个 group 增补 request/response contract 级别的主题页。
- 部分新接口在 README 中尚未完整体现，wiki 未来应在“能力对外总览”和“代码真实实现”之间持续校准。

## 来源

- [../../../app/api/router.py](../../../app/api/router.py)
- `../../../app/api/routes/*.py`
- [../../../README.md](../../../README.md)
- [../raw/2026-04-21-repo-bootstrap.md](../raw/2026-04-21-repo-bootstrap.md)
