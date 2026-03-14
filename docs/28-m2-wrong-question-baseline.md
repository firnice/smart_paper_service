# M2 错题本基础录入验收记录（claw-01）

## 目标

验证错题本基础录入链路是否可用，范围包括：

- 学科字典
- 错题分类字典
- 错误原因字典
- 错题创建
- 错题列表
- 错题详情

## 本次结论

**M2 主链路可用，并已修复一个导致字典列表接口 500 的兼容性问题。**

本阶段完成后，错题本的“字典准备 → 创建错题 → 列表查看 → 详情查看”闭环已经能够演示。

## 本次验证接口

### 字典类

- `GET /api/subjects`
- `POST /api/subjects`
- `GET /api/wrong-question-categories`
- `POST /api/wrong-question-categories`
- `GET /api/error-reasons`
- `POST /api/error-reasons`

### 错题类

- `POST /api/wrong-questions`
- `GET /api/wrong-questions`
- `GET /api/wrong-questions/{wrong_question_id}`

## 正向流程验证结果

### 1. 学科字典

- 可正常查询已有学科
- 可新增学科（示例：`math-m2` / `数学M2`）

### 2. 错题分类字典

- 可正常查询已有分类
- 可新增分类（示例：`计算错误M2`）

### 3. 错误原因字典

- 可新增带 `category_id` 的错误原因
- 可按分类过滤查询错误原因

### 4. 错题创建

使用以下对象成功创建：

- `student_id = 3`
- 学科：`数学M2`
- 分类：`计算错误M2`
- 错因：`审题不清M2`

创建成功后，响应中可正确返回：

- 学生摘要
- 学科摘要
- 分类摘要
- 错误原因列表
- 状态 / 难度 / 年级 / 备注等字段

### 5. 错题列表

按 `student_id=3` 查询时，可正确返回刚创建的错题。

### 6. 错题详情

可按 `wrong_question_id` 正常查询详情。

## 边界场景验证结果

### 1. 错误原因与分类不匹配

结果：**正确拦截**

- HTTP 状态：`400`
- 返回：`Error reason {id} does not belong to category {category_id}`

### 2. 非学生用户创建错题

结果：**正确拦截**

- HTTP 状态：`400`
- 返回：`student_id must be role=student`

## 本次发现并修复的问题

### 问题：字典列表接口返回 500

受影响接口：

- `GET /api/subjects`
- `GET /api/wrong-question-categories`

根因：

- 旧字典数据中 `created_at` 存在空值
- Pydantic 响应模型将 `created_at` 定义为必填 `datetime`
- 列表序列化时因历史数据不满足约束而报错

修复策略：

- 将元数据响应模型中的 `created_at` 调整为可空
- 保证旧数据兼容，不阻塞现有接口可用性

受影响模型：

- `SubjectResponse`
- `WrongQuestionCategoryResponse`
- `ErrorReasonResponse`

## 当前判断

### 已达到

- 错题本基础录入闭环可演示
- Swagger 中相关接口可直接调试
- 基础数据校验存在
- 分类与错因一致性校验存在
- 学生角色校验存在

### 后续建议

- 对旧字典数据补一次 `created_at` 数据修复迁移，避免长期依赖接口兼容层
- 在 M3 中继续验证：
  - 错题更新
  - 错题删除
  - 多条件筛选
  - 错因关系更新

## Swagger 与运行信息

- Swagger：`http://127.0.0.1:8000/docs`
- Health：`http://127.0.0.1:8000/api/health`

## 建议下一阶段

进入 **M3：错题维护增强**，范围包括：

- 更新错题
- 删除错题
- 多条件筛选
- 错误原因关系更新
