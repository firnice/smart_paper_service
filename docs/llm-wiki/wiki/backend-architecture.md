# 后端架构

## 摘要

当前后端是标准的 FastAPI 分层结构，`app/main.py` 负责应用生命周期、middleware 和静态资源挂载，`app/api/routes/` 负责 HTTP 接口编排，`app/services/` 承担 OCR、图像、导出、LLM 调用、趋势分析等服务逻辑，`app/db/` 负责会话和模型。

## 关键点

- 应用入口：
  - [app/main.py](../../../app/main.py) 在启动时调用 `ensure_default_model_providers`，说明模型供应商种子数据是运行期初始化的一部分。
  - 应用挂载了限流、中间件安全头、CORS、trace id 注入，以及 `/static` 静态目录。
- 路由层：
  - [app/api/router.py](../../../app/api/router.py) 按业务域聚合 route modules。
  - route 组已经不只服务 OCR MVP，还包含 admin、analysis、school terms 和 metadata 等辅助能力。
- 服务层：
  - `image_service.py`、`ocr_service.py`、`question_rebuild_service.py`、`diagram_llm_service.py`：OCR 与题目重建链路核心。
  - `variant_service.py`：举一反三题目生成。
  - `export_service.py`、`print_filename_service.py`：导出与打印命名逻辑。
  - `trend_analysis_service.py`：学生趋势分析异步处理。
  - `llm_client_service.py`、`agent_config_service.py`：模型调用与配置编排。
- 数据层：
  - `app/db/session.py` 提供数据库会话。
  - `app/db/models/` 同时承载业务实体、统计实体和 LLM 管理实体。

## 主要运行链路

### OCR 到错题沉淀

- `ocr` 路由接收图片。
- 图像服务负责预处理、裁剪、图示处理、可能的去手写清理。
- OCR 服务和题目分析 / 重建服务把识别结果转成结构化输出。
- 后续结果可与 `wrong_questions` 领域衔接，进入维护、训练和统计。

### 错题维护

- `wrong_questions` 路由负责错题 CRUD、筛选、学习记录读写。
- `users`、`subjects`、`error_reasons`、`school_terms` 等辅助域提供筛选和归属上下文。
- `statistics` 和 `analysis` 以学生维度读取沉淀数据。

### LLM 管理

- `admin` 路由提供 agent config 与 model provider 管理。
- `llm_call_log` 和统计接口支持后端观察 LLM 使用情况。
- `main.py` 的启动 seeding 与这套配置体系相互配合。

## 当前风险

- 仓库的架构文档跨度较大，部分能力已经演进到比 README 更复杂的状态，wiki 需要持续吸收新文档和代码变更。
- OCR / diagram / rebuild / analysis 这几条 LLM 相关链路跨越多个 service 文件，后续如果只读某一页 wiki 可能还不够，需要继续增加专题页。

## 来源

- [../../../app/main.py](../../../app/main.py)
- [../../../app/api/router.py](../../../app/api/router.py)
- [../../../README.md](../../../README.md)
- [../raw/2026-04-21-repo-bootstrap.md](../raw/2026-04-21-repo-bootstrap.md)
