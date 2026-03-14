# M1 用户与学生基础能力验收记录（claw-01）

## 目标

验证 `lf-smart-paper-service` 中第一阶段用户基础能力是否达到可演示、可联调、可在 Swagger 中直接调试的程度。

本阶段关注范围：

- 用户创建 / 查询 / 更新
- 学生档案建模
- 家长-学生关系绑定 / 查询 / 解绑
- 学生简版登录

## 本次结论

**M1 基础链路已具备可演示性。**

已完成真实接口验证，核心正向流程可用，关键冲突场景具备预期拦截行为。

## 已验证接口

### 用户相关

- `POST /api/users`
- `GET /api/users`
- `GET /api/users/{user_id}`
- `PUT /api/users/{user_id}`

### 家长-学生关系

- `POST /api/users/parent-student-links`
- `DELETE /api/users/parent-student-links/{link_id}`（本轮未执行删除，但接口已暴露）
- `GET /api/users/{parent_id}/students`
- `GET /api/users/{student_id}/parents`

### 登录相关

- `POST /api/auth/student-login`

## 正向流程验证结果

### 场景 1：创建家长

创建成功，返回 `201/200` 风格用户实体（当前实现为创建成功返回用户对象）。

### 场景 2：创建学生（含 student_profile）

创建成功，返回用户信息，并正确包含：

- `student_no`
- `grade`
- `class_name`
- `school_name`
- `guardian_note`

### 场景 3：绑定家长与学生

绑定成功，返回关系对象：

- `id`
- `parent_id`
- `student_id`
- `relation_type`
- `created_at`

### 场景 4：按家长查询学生

返回学生列表，包含：

- `link_id`
- `relation_type`
- `student`（含完整用户与 student_profile 信息）

### 场景 5：按学生查询家长

返回家长列表，结构正确。

### 场景 6：学生登录

学生登录验证成功。

在提供 `student_no` 的情况下，可正确命中对应学生档案。

### 场景 7：用户更新

更新用户字段（如 `phone`）成功，更新后查询结果一致。

## 边界场景验证结果

### 1. 重复绑定同一家长-学生关系

结果：**正确拦截**

- HTTP 状态：`409`
- 返回：`Parent-student link already exists`

### 2. 绑定时 parent_id 不是家长角色

结果：**正确拦截**

- HTTP 状态：`400`
- 返回：`parent_id must be role=parent`

### 3. 学生改为非学生角色

结果：**允许更新，且 student_profile 被移除**

- HTTP 状态：`200`
- 更新后 `student_profile = null`

这说明当前实现对“角色切换导致学生档案删除”已有处理逻辑。

### 4. 重名学生登录（不带 student_no）

结果：**正确拦截**

- HTTP 状态：`409`
- 返回：`Multiple students matched. Please provide student_no for verification.`

### 5. 重名学生登录（带 student_no）

结果：**正确命中并登录成功**

- HTTP 状态：`200`

## 本阶段判断

### 已达到

- 可在 Swagger 中直接调试
- 可支撑前端“用户 / 学生 / 家长关系 / 学生登录”基础联调
- 基本冲突处理逻辑存在
- 数据模型与接口方向一致

### 尚建议后续继续增强

- 增补自动化测试脚本，而不只依赖手工 smoke test
- 明确创建接口返回码规范（统一 201 / 200 风格）
- 明确角色切换是否允许删除 student_profile（产品规则需沉淀到 AGENTS / docs）
- 对 `/api/users` 查询增加更多筛选与排序说明
- 对登录策略（自动创建、重名冲突、student_no 回填）补产品说明

## Swagger 与运行信息

- Swagger：`http://127.0.0.1:8000/docs`
- Health：`http://127.0.0.1:8000/api/health`

## 建议的下一阶段

建议进入 **M2：错题本基础录入**，范围包括：

- 学科字典
- 错题分类字典
- 错误原因字典
- 错题创建
- 错题列表
- 错题详情
