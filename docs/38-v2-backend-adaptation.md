# 38 - V2 后端适配方案

## 背景

V2 产品重设计主要是前端交互重组，后端已具备绝大部分能力。本文档梳理后端需要的微调和新增工作。

产品设计全文见: `docs/product/05-v2-product-redesign.md`

## 现有 API 能力盘点

### 已就绪（无需改动）

| API | 用途 | V2 对应功能 |
|-----|------|------------|
| `POST /api/ocr/extract` | OCR 识别 | 中央录入-识别 |
| `POST /api/ocr/analyze-question` | LLM 题目分析 | 中央录入-分析 |
| `POST /api/wrong-questions` | 创建错题 | 中央录入-保存 |
| `PUT /api/wrong-questions/{id}` | 更新错题（含掌握状态） | 掌握标记 |
| `DELETE /api/wrong-questions/{id}` | 删除错题 | 错题管理 |
| `GET /api/wrong-questions/{id}` | 错题详情 | 错题详情页 |
| `POST /api/variants/generate-for-question` | 变式题生成 | 快速训练-举一反三 |
| `POST /api/export` | 导出 PDF | 快速训练-单条打印 |
| `GET /api/export/{job_id}` | 查询导出状态 | 打印状态查询 |
| `GET /api/statistics/overview` | 统计总览 | 工作台-统计栏 |
| `GET /api/statistics/by-subject` | 学科统计 | 我的-学科分布 |
| `GET /api/statistics/trend` | 趋势统计 | 我的-趋势图 |
| `POST /api/analysis/trend` | LLM 趋势分析 | 我的-分析报告 |
| `GET /api/analysis/trend/latest` | 最新分析报告 | 我的-分析入口 |
| `GET /api/subjects` | 学科列表 | 筛选栏-学科选项 |
| `GET /api/auth/student-login-config` | 登录配置 | 登录页 |
| `POST /api/auth/student-login` | 学生登录 | 登录页 |

### 需要微调

#### 1. 错题列表接口增强筛选

**当前**: `GET /api/wrong-questions` 支持基础筛选

**V2 需要**: 增加组合筛选参数

```python
# app/api/routes/wrong_questions.py

@router.get("/wrong-questions")
async def list_wrong_questions(
    # 已有参数
    student_id: int = Query(...),
    subject: str = Query(None),
    status: str = Query(None),          # new / reviewing / mastered
    page: int = Query(1),
    limit: int = Query(20),
    # 新增参数
    mastery: str = Query(None),         # mastered / unmastered（简化的掌握筛选）
    term: str = Query(None),            # 学期筛选，如 "三年级上"
    sort_by: str = Query("created_at"), # 排序字段
    sort_order: str = Query("desc"),    # 排序方向
):
    ...
```

**改动量**: 小 — 在现有 query 构建逻辑中增加 WHERE 条件

#### 2. 题目分析接口增加地区参数（可选）

**当前**: `POST /api/ocr/analyze-question` 分析时不考虑地区

**V2 设计**: 按地区教材知识点归类

```python
# 新增可选参数
class AnalyzeQuestionRequest(BaseModel):
    question_text: str
    subject: str = None
    grade: str = None
    region: str = None  # 新增: "北京" / "上海" 等，影响知识点归类
```

**改动量**: 小 — 在 LLM prompt 中增加地区上下文

**建议**: 此项可以 Phase V2-3 再做，先上线通用版

### 需要新增

#### 3. 批量练习卷生成接口

V2 的"批量回归"功能需要一个新接口，将选定的多道错题组合成练习卷并导出。

```python
# app/api/routes/export.py 新增

@router.post("/export/practice-sheet")
async def create_practice_sheet(
    request: PracticeSheetRequest,
    background_tasks: BackgroundTasks,
):
    """
    生成练习卷 PDF
    - 支持指定题目 ID 列表
    - 支持随机选择模式
    """
    ...

class PracticeSheetRequest(BaseModel):
    student_id: int
    mode: str  # "manual" / "random"

    # manual 模式
    question_ids: list[int] = None

    # random 模式
    random_count: int = None        # 随机数量，None 表示全部
    random_filter: dict = None      # 随机筛选条件（学科、学期等）

    # 输出选项
    include_answers: bool = False   # 是否包含答案
    include_variants: bool = False  # 是否包含举一反三变式题
```

**实现方案**:
1. 根据 `mode` 获取题目列表
2. 复用现有 `export_service.py` 的 PDF 生成逻辑
3. 返回 `job_id`，前端通过 `GET /api/export/{job_id}` 轮询状态

**改动量**: 中 — 新增一个路由函数 + 复用已有导出服务

#### 4. 未读消息计数接口（可选）

V2 "我的"页面有消息红点功能。

```python
# app/api/routes/users.py 新增

@router.get("/users/{user_id}/unread-count")
async def get_unread_count(user_id: int):
    """
    获取未读消息数量
    当前场景：趋势分析报告完成通知
    """
    return {"unread_count": count}
```

**建议**: Phase V2-4 再实现，当前可以前端轮询 `GET /api/analysis/trend/latest` 判断是否有新报告

## 数据库影响

### 无需新增表

V2 的所有功能都可以通过现有数据模型支持：
- `wrong_questions` 表已有 `status` 字段（掌握状态）
- `wrong_questions` 表已有学科、学期等分类字段
- `study_records` 表已有 `mastery_level` 字段

### 可选索引优化

如果数据量增大，建议添加组合索引：

```sql
-- 加速工作台筛选查询
CREATE INDEX idx_wq_student_status_subject
ON wrong_questions (student_id, status, subject_id);

-- 加速学期筛选
CREATE INDEX idx_wq_student_term
ON wrong_questions (student_id, school_term);
```

## 改动优先级

| 优先级 | 改动项 | 工作量 | 依赖 |
|--------|--------|--------|------|
| P0 | 错题列表筛选增强 | 0.5 天 | 无 |
| P1 | 批量练习卷生成接口 | 1 天 | 复用 export_service |
| P2 | 分析接口增加地区参数 | 0.5 天 | 需要地区知识点 prompt |
| P3 | 未读消息计数接口 | 0.5 天 | 需要消息/通知表设计 |

**总工作量预估: 约 2-3 天**

## 测试要点

1. **筛选增强** — 验证组合筛选（学科 + 学期 + 掌握状态）返回正确结果
2. **批量练习卷** — 验证手动模式和随机模式都能正确生成 PDF
3. **向后兼容** — 确保新参数为可选，不影响现有前端调用

## 文件影响清单

| 文件 | 改动类型 | 改动量 |
|------|----------|--------|
| `app/api/routes/wrong_questions.py` | 增加筛选参数 | 小 |
| `app/api/routes/export.py` | 新增批量练习卷接口 | 中 |
| `app/schemas/export.py` | 新增 PracticeSheetRequest | 小 |
| `app/services/export_service.py` | 适配批量练习卷逻辑 | 小（复用） |
| `app/services/question_analysis_service.py` | 可选：增加地区 prompt | 小 |

---

**最后更新**: 2026-03-27
