# lf-smart-paper-service

Smart Paper（智能错题本）后端服务，覆盖以下两类能力：

- Phase 1（已实现）：OCR 识别、变式题生成、PDF 导出
- Phase 2（本次补齐）：用户/学生/家长关系、错题本维护、多维度统计分析

## 当前能力清单

### 1) OCR + 变式 + 导出

- `GET /api/health` 健康检查
- `POST /api/ocr/extract` 上传图片并识别题干（含入库）
- `POST /api/ocr/extract/simple` 上传图片并识别题干（不入库）
- `POST /api/variants/generate` 生成同类变式题
- `POST /api/export` 生成导出任务（PDF）
- `GET /api/export/{job_id}` 查询导出状态

### 2) 用户与关系管理（新增）

- `POST /api/users` 创建用户（支持 `student`/`parent` 等角色）
- `GET /api/users` 用户列表（支持 role/status/keyword）
- `GET /api/users/{user_id}` 用户详情
- `PUT /api/users/{user_id}` 更新用户
- `POST /api/users/parent-student-links` 绑定家长-学生关系
- `DELETE /api/users/parent-student-links/{link_id}` 解绑家长-学生关系
- `GET /api/users/{parent_id}/students` 查询家长名下学生
- `GET /api/users/{student_id}/parents` 查询学生关联家长

### 2.1) 学生登录校验（简版）

- `POST /api/auth/student-login` 学生登录校验（姓名必填，学号/年级可选）
- 若系统中不存在该姓名的学生，会自动创建一个基础学生档案后返回登录成功（便于演示与冷启动）

### 3) 错题本维护（新增，学生维度）

- `GET /api/subjects` 学科列表
- `POST /api/subjects` 新增学科
- `GET /api/wrong-question-categories` 错题分类列表
- `POST /api/wrong-question-categories` 新增错题分类
- `GET /api/error-reasons` 错误原因列表
- `POST /api/error-reasons` 新增错误原因
- `POST /api/wrong-questions` 创建错题
- `GET /api/wrong-questions` 错题列表（支持多条件筛选）
- `GET /api/wrong-questions/{id}` 错题详情
- `PUT /api/wrong-questions/{id}` 更新错题（含错误原因多对多更新）
- `DELETE /api/wrong-questions/{id}` 删除错题
- `POST /api/wrong-questions/{id}/study-records` 新增练习记录
- `GET /api/wrong-questions/{id}/study-records` 查询练习记录

### 4) 统计分析（新增）

- `GET /api/statistics/overview`
- `GET /api/statistics/by-subject`
- `GET /api/statistics/by-grade`
- `GET /api/statistics/by-category`
- `GET /api/statistics/by-error-reason`
- `GET /api/statistics/trend`

> 统计接口统一按 `student_id` 聚合，支持 `start_date` / `end_date` 时间范围。

## 数据关系（核心）

- `users`：统一用户表，区分 `student` / `parent` 等角色
- `student_profiles`：学生档案（年级、班级、学校）
- `parent_student_links`：家长与学生多对多关系
- `subjects`：学科字典
- `wrong_question_categories`：错题分类
- `error_reasons`：错误原因字典（可绑定分类）
- `wrong_questions`：学生错题主表（学科、年级、分类、状态、错因）
- `wrong_question_error_reasons`：错题与错误原因多对多关系
- `study_records`：错题练习记录与掌握趋势

## 快速启动

> 所有命令都在 `lf-smart-paper-service/` 目录执行。

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 配置 LLM（可选）

```bash
cp app/core/llm_secrets.example.py app/core/llm_secrets.py
```

在 `app/core/llm_secrets.py` 填入：

- `SILICONFLOW_API_KEY`
- `SILICONFLOW_BASE_URL`
- `SILICONFLOW_MODEL`
- `SILICONFLOW_OCR_MODEL`

### 3) 初始化数据库

```bash
alembic upgrade head
```

会自动创建新表并写入基础数据（学科、错题分类、错误原因）。

### 4) 启动服务

```bash
./start.sh
```

- Swagger: `http://localhost:8000/docs`
- 健康检查: `http://localhost:8000/api/health`

### 5) 冒烟测试与示例脚本

```bash
./.venv/bin/python tests/test_mvp.py
./.venv/bin/python scripts/generate_sample_pdf.py
```

示例 PDF 会输出到 `storage/exports/sample_practice_sheet.pdf`。

## 示例：学生错题本闭环

### 1) 创建家长与学生

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"张妈妈","role":"parent","status":"active"}'
```

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "name":"张小明",
    "role":"student",
    "status":"active",
    "student_profile":{"grade":"三年级","class_name":"3班","school_name":"实验小学"}
  }'
```

### 2) 绑定家长与学生

```bash
curl -X POST http://localhost:8000/api/users/parent-student-links \
  -H "Content-Type: application/json" \
  -d '{"parent_id":1,"student_id":2,"relation_type":"mother"}'
```

### 2.1) 学生登录校验（简版）

```bash
curl -X POST http://localhost:8000/api/auth/student-login \
  -H "Content-Type: application/json" \
  -d '{"name":"张小明","student_no":"S-1001","grade":"三年级"}'
```

### 3) 新增错题（含分类与错误原因）

```bash
curl -X POST http://localhost:8000/api/wrong-questions \
  -H "Content-Type: application/json" \
  -d '{
    "student_id":2,
    "title":"两位数乘法",
    "content":"23 × 14 = ?",
    "subject_id":1,
    "grade":"三年级",
    "category_id":2,
    "error_reason_ids":[3,4],
    "status":"new",
    "difficulty":"medium"
  }'
```

### 4) 新增练习记录并查看统计

```bash
curl -X POST http://localhost:8000/api/wrong-questions/1/study-records \
  -H "Content-Type: application/json" \
  -d '{"result":"incorrect","mastery_level":2,"time_spent_seconds":180}'
```

```bash
curl "http://localhost:8000/api/statistics/overview?student_id=2"
```

## 目录结构

```text
app/
  api/routes/        # API 路由层
  schemas/           # Pydantic 请求/响应模型
  services/          # OCR/变式/导出等服务
  db/models/         # SQLAlchemy 数据模型
  core/              # 配置
alembic/             # 数据库迁移脚本
docs/
  product/           # 产品与阶段任务文档
  export/            # 导出排版设计说明
scripts/             # 开发辅助脚本
tests/               # 手工/冒烟测试脚本
logs/                # 本地日志目录（不提交）
storage/             # 本地存储目录（不提交）
```

## 开发规范（目录）

- 运行代码只放在 `app/`。
- 迁移脚本只放在 `alembic/versions/`。
- 测试脚本放在 `tests/`，例如 `tests/test_mvp.py`。
- 开发辅助脚本放在 `scripts/`，例如 `scripts/generate_sample_pdf.py`。
- 文档统一放在 `docs/`，避免散落在项目根目录。
- 本地产物（`*.db`、`logs/`、`storage/`、测试导出文件）不提交到 Git。
