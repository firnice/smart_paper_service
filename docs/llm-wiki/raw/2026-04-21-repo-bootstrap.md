# 2026-04-21 仓库初始化来源清单

## 目的

本文件记录初始化 `docs/llm-wiki/` 时实际使用的仓库来源，作为第一批综合页的 source snapshot。

## 基础仓库规则

- [../../../AGENTS.md](../../../AGENTS.md): 仓库作用域、运行目录和 frontend-first 临时规则。
- [../../CODE_LAYOUT.md](../../CODE_LAYOUT.md): 代码、文档、脚本、测试和运行产物的目录规范。

## 产品与能力总览

- [../../../README.md](../../../README.md): 后端对外能力总览、启动方式、核心数据关系。
- [../../product/README.md](../../product/README.md): 产品路线图、阶段文档入口、功能完成度判断。

## 运行时入口

- [../../../app/main.py](../../../app/main.py): FastAPI app、lifespan、middleware、静态资源挂载。
- [../../../app/api/router.py](../../../app/api/router.py): 路由聚合入口。

## API Inventory 来源

- `app/api/routes/*.py`
- 初始化时使用 `rg "@router\\.(get|post|put|delete|patch)\\(" app/api/routes` 做路由扫描。

## 数据模型 Inventory 来源

- [../../../app/db/models/__init__.py](../../../app/db/models/__init__.py): 模型清单。
- [../../../app/db/models/user.py](../../../app/db/models/user.py): 用户、家长、学生关系起点。
- [../../../app/db/models/wrong_question.py](../../../app/db/models/wrong_question.py): 错题主实体。
- [../../../app/db/models/trend_analysis.py](../../../app/db/models/trend_analysis.py): 趋势分析记录模型。

## 初始化时识别到的文档分组

- `docs/05` 到 `docs/08`: SaaS 主导试题重建链路
- `docs/09` 到 `docs/12`: 前端安全去手写链路
- `docs/13` 到 `docs/24`: 卡片化、图示、多模态客户端等分阶段实现文档
- `docs/25` 到 `docs/38`: 上传识别流、基线审计、错题维护、导出、agent config、趋势分析、V2 后端适配

## 工作假设

- 代码与文档冲突时，以代码和当前路由/模型为准。
- `docs/product/` 更偏产品分期和愿景，不等同于“已实现”。
- 当前阶段应显式记录 backend blocking fixes only 的协作约束，避免 wiki 把规划误写成当前执行目标。
