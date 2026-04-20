# 打印历史记录 + 打印包文件命名 · 设计文档

- **日期**：2026-04-20
- **范围**：`smart_paper_service`（后端）+ `smart_paper_web`（前端 PrintPage）
- **影响接口**：`POST /api/print-pack/export`、`GET /api/wrong-questions`

---

## 1. 背景与目标

当前打印流程存在两个痛点：

1. **重复打印问题**：`PrintPage` 默认勾选前 6 道非 `mastered` 错题，但没有考虑"历史上是否已经打印过"。学生很容易把上次已经打印的题再次默认勾上，造成重复打印。
2. **文件名不可读**：导出的 PDF 统一命名为 `智能错题本-打印重做包-YYYY-MM-DD.pdf`。家长下载多份后无法从文件名区分学生、学科、学期，难以归档。

本设计在保持最小改动的前提下，解决这两个问题。

## 2. 功能需求

### 需求 1：记录打印过的错题，再次进入打印页时不默认勾选

- 判定范围：**终身已打印**（历史上任意一次成功导出 PDF 即算"已打印"）
- 不禁用手动勾选：用户可随时手动勾选已打印过的题
- 视觉标记：在选题列表展示徽章 `已打印 {N} 次 · 最近 {MM-DD}`
- 存储方式：新建关联表 `wrong_question_print_history`

### 需求 2：打印包文件名改为可读格式

命名规则：`{姓}-{年级}-{学期}-{学科}-{YYYYMMDD-HHMM}.pdf`

示例：
- `李-三年级-上-数学-20260420-1435.pdf`
- `王-四年级-下-语文_英语-20260420-1712.pdf`
- `学生-未分类-20260420-1435.pdf`（未登录，且无法关联错题 → 年级/学期/学科段均为空时被省略）

规则细节：
- **姓**：`User.name` 首字符（中文取姓，英文取首词首字）；为空或无 student_id → `学生`
- **年级**：取学生 `student_profile.current_term` 拆出的年级部分；无 `current_term` → 回退 `student_profile.grade`；仍为空 → 空字符串
- **学期**：`上` 或 `下`，来源同上；无 → 空字符串
- **学科**：对打印包内所有题目的 `wrong_question.subject.name` 去重，按 `subject.id` 升序用 `_` 拼接；全空 → `未分类`
- **时间**：`datetime.now()` 格式化为 `YYYYMMDD-HHMM`，精确到分钟
- **空段处理**：任何为空字符串的段都在最终拼接时省略（详见 §5.3），避免出现 `李--上-...` 这样的双连字符

## 3. 非功能约束

- 不引入新的基础设施（队列、缓存）
- 打印历史写入与 `exports` 记录在同一事务中，保证一致性
- `GET /api/wrong-questions` 聚合 `print_count`/`last_printed_at` 必须一次 SQL 完成，不得 N+1
- 徽章仅在**打印选题页**展示，不扩散到其他列表

## 4. 数据模型

### 新增表：`wrong_question_print_history`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK, autoincrement | |
| `wrong_question_id` | Integer | FK → `wrong_questions.id` ON DELETE CASCADE, index | 被打印的错题 |
| `export_id` | Integer | FK → `exports.id` ON DELETE CASCADE, index | 所属打印包 |
| `student_id` | Integer | FK → `users.id`, index | 冗余字段，便于按学生过滤 |
| `printed_at` | DateTime | index, default `func.now()` | 打印时间，与 `exports.created_at` 一致 |

**索引**：
- `ix_wqph_wrong_question_id`（单列）：服务于 GROUP BY 聚合
- `ix_wqph_student_printed`（`student_id`, `printed_at`）：服务于学生打印历史筛选

**Alembic 迁移**：新建 migration 文件 `xxxx_add_wrong_question_print_history.py`，`upgrade()` 创建表与索引，`downgrade()` drop 整张表。

### 不变更的表

- `exports`：不动
- `wrong_questions`：不动（不添加冗余 `print_count`/`last_printed_at` 字段）

## 5. 后端实现

### 5.1 `POST /api/print-pack/export` 改造

位置：`app/api/routes/export.py` + `app/services/export_service.py`

**流程变化**：

1. 原流程：`create_print_pack_export` 生成 PDF → 上传存储 → 写 `exports` 记录 → commit
2. 新流程：在同一事务内，**仅当 `status == "completed"`**：
   - 从 `items` 收集 `source_question_id`，去重、过滤 `None`
   - 批量插入 `wrong_question_print_history`，每条记录 `printed_at = export.created_at`
   - 调用 `build_print_pack_filename(db, student_id, item_source_ids)` 生成文件名
3. commit；返回响应时附带 `filename`

**失败处理**：PDF 生成/上传失败时，`exports` 记录仍写入（含失败状态），但 **不写 `print_history`**；`filename` 字段返回 `None`。

**响应 schema 扩展** (`app/schemas/export.py`)：

```python
class PrintPackExportResponse(BaseModel):
    id: int
    status: str
    download_url: Optional[str] = None
    filename: Optional[str] = None   # 新增
```

### 5.2 `GET /api/wrong-questions` 聚合字段

位置：`app/services/wrong_question_service.py`（列表查询）+ `app/schemas/wrong_question.py`（响应 schema）

**SQL 思路**：LEFT JOIN 一个子查询的聚合结果：

```sql
SELECT wq.*,
       COALESCE(h.cnt, 0) AS print_count,
       h.last_at AS last_printed_at
FROM wrong_questions wq
LEFT JOIN (
    SELECT wrong_question_id,
           COUNT(*) AS cnt,
           MAX(printed_at) AS last_at
    FROM wrong_question_print_history
    WHERE student_id = :sid
    GROUP BY wrong_question_id
) h ON h.wrong_question_id = wq.id
WHERE wq.student_id = :sid
```

**响应字段新增**：

```python
class WrongQuestionOut(BaseModel):
    ...
    print_count: int = 0
    last_printed_at: Optional[datetime] = None
```

### 5.3 文件名构造 `build_print_pack_filename`

位置：新增 `app/services/print_filename_service.py`

**签名**：

```python
def build_print_pack_filename(
    db: Session,
    student_id: Optional[int],
    source_question_ids: list[int],
    now: datetime = None,
) -> str: ...
```

**步骤**：

1. **姓**：
   - `student_id` 为空 → `"学生"`
   - 查 `User.name`，空字符串 → `"学生"`
   - 非空：`name.strip().split()[0][0]`（英文首词首字 / 中文姓）
2. **年级 + 学期**：
   - 查 `StudentProfile` JOIN `SchoolTerm` (`current_term_id`)
   - 若有 `current_term`：`grade = current_term.grade`，`semester = current_term.semester`
   - 若无：`grade = student_profile.grade or ""`，`semester = ""`
3. **学科**：
   - 若 `source_question_ids` 为空 → `"未分类"`
   - `SELECT DISTINCT s.id, s.name FROM wrong_questions wq JOIN subjects s ON ... WHERE wq.id IN :ids ORDER BY s.id`
   - 全空 → `"未分类"`
   - 多个 → `"_".join(names)`
4. **时间**：`now or datetime.now()` → `strftime("%Y%m%d-%H%M")`
5. **拼接**：按顺序 `[surname, grade, semester, subjects, time_str]`，过滤空字符串后用 `-` 连接，追加 `.pdf`

**示例实现片段**：

```python
parts = [surname, grade, semester, subjects_str, time_str]
parts = [p for p in parts if p]
return "-".join(parts) + ".pdf"
```

### 5.4 旧版 `/api/export` 不接入

`POST /api/export`（单题/变式导出路径）**不写 print_history**、**不改文件名**。当前 `ExportQuestionItem` 没有 `source_question_id`，无法关联回 `wrong_question_id`，且该流程非本次需求范围。

## 6. 前端实现

### 6.1 错题列表映射扩展

位置：`smart_paper_web/src/pages/print/helpers.js` 的 `mapWrongQuestionToPrintQuestion`

新增字段：

```js
printCount: item?.print_count || 0,
lastPrintedAt: item?.last_printed_at || "",
hasBeenPrinted: (item?.print_count || 0) > 0,
```

同时新增工具函数 `formatShortDate(iso)` → `"MM-DD"` 字符串（iso 为空时返回 `""`）。

### 6.2 默认勾选逻辑

位置：`smart_paper_web/src/pages/PrintPage.jsx` 的 `resolveInitialSelection`（31-47 行）

**变更**：过滤条件从 `status !== "mastered"` 改为 `status !== "mastered" && !hasBeenPrinted`；`requestedIds`（URL 指定）与 `previousIds`（跨步骤保留）优先级不变。

不足 6 道时不补足，直接返回更短的数组——避免默认把打印过的勾上。

### 6.3 徽章展示

位置：`smart_paper_web/src/pages/print/components/SelectQuestionsStep.jsx`

在 `FullQuestionCard`、`CompactQuestionCard`、`ListQuestionRow` 三处 metadata 行末尾追加：

```jsx
{question.hasBeenPrinted ? (
  <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
    <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
    已打印 {question.printCount} 次 · 最近 {formatShortDate(question.lastPrintedAt)}
  </span>
) : null}
```

List 视图若空间紧张，放在 mastery 徽章旁；极窄视口下允许换行。

### 6.4 导出结果展示

位置：`PrintPage.jsx:566-595` 的 `handleExport`

- 保留 `window.open(downloadUrl, "_blank")` 行为
- toast 改为：`PDF 已生成：{filename}`（若后端返回 `filename`）
- `Content-Disposition` 的设置留给后续优化（当前 storage 是本地 `/static/`，浏览器默认使用 URL 尾部文件名）

### 6.5 不改动

- `buildPrintExportPayload`：items 已传 `source_question_id`，无须变化
- `TermContext`、其他页面（QuestionBank/QuestionDetail 等）：不加徽章

## 7. 测试策略

### 7.1 后端测试（`tests/`）

- `test_print_history_model.py`：新建 `wrong_question_print_history` 表与索引存在
- `test_print_pack_export_history.py`：
  - 成功导出 → `print_history` 有 N 条记录（N = 去重后 source_question_id 数）
  - 失败导出 → `print_history` 无记录
  - `items` 中含相同 `source_question_id` 的多条（原题+AI 同类题）→ 历史记录去重为 1 条
  - `source_question_id = None`（AI 独立题）→ 跳过，不报错
- `test_wrong_questions_list_print_stats.py`：聚合字段正确，N+1 检查（通过 SQLAlchemy event 断言 query 数 ≤ 2）
- `test_print_filename_builder.py`：
  - 无学生 id → `学生-...`
  - 中文名 / 英文名 / 空名
  - 无 current_term → 降级为 profile.grade
  - 多学科拼接与去重
  - 全空学科 → `未分类`

### 7.2 前端测试（如项目已有前端测试框架则补充；否则手工验证）

- 手工：打开 PrintPage，刷新页面，观察默认勾选不包含已打印过的题
- 手工：查看徽章在 Full/Compact/List 三视图下的显示
- 手工：导出后 toast 显示新文件名

## 8. 实施顺序建议

1. 后端数据模型 + Alembic 迁移
2. 后端 `print_filename_service` + 单元测试
3. 后端 `export_service.create_print_pack_export` 改造 + 测试
4. 后端 `GET /api/wrong-questions` 聚合 + 测试
5. 前端 `helpers.js` 字段映射 + `formatShortDate`
6. 前端 `resolveInitialSelection` 排除已打印
7. 前端 `SelectQuestionsStep` 徽章
8. 前端 `handleExport` toast
9. 手工回归打印主流程

## 9. 风险与权衡

| 风险 | 处理 |
|---|---|
| 历史 exports 没有对应 print_history，旧题显示 `print_count=0` | 可接受。如需回溯，可写一次性脚本从 `exports.variants_json` 反解并补录（非本次范围） |
| 文件名含中文在部分 Windows 压缩工具下乱码 | 当前下载走浏览器直链，浏览器会正确处理 UTF-8 文件名；留作后续优化点 |
| `status == "completed"` 的 export 仍可能下游失败 | 同事务保证：若下游失败 → exports 也回滚，print_history 不会孤立 |
| 一次打印包内学科数量多时文件名过长 | 学科名称通常 2 字内，N 科拼接可接受；极端情况下文件名在 Windows 限制内（255 字符）依然安全 |

## 10. 不在范围内

- 旧版 `POST /api/export` 不改造
- 不给 QuestionBank、QuestionDetail 等非打印页加徽章
- 不做已打印题的"筛选/隐藏"开关
- 不支持"按打印历史反向查找"功能（如"这份打印包包含哪些题"——可查 `variants_json`）
- 不配置下载响应的 `Content-Disposition`
