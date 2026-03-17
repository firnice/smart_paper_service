# 31-metadata-created-at-backfill

## 背景

日志中曾出现元数据接口 500：
- `/api/subjects`
- `/api/wrong-question-categories`

根因是部分历史基础数据的 `created_at` 为 `NULL`，而相关序列化/消费逻辑会假定它存在。

## 本次修复

新增迁移：
- `7c1d2f4a9e21_backfill_metadata_created_at.py`

对以下表中的历史空值执行回填：
- `subjects`
- `wrong_question_categories`
- `error_reasons`

回填方式：
- `created_at IS NULL` → `CURRENT_TIMESTAMP`

## 结果

元数据脏数据被补平，避免后续接口、排序或前端展示再次踩到 `NULL created_at`。