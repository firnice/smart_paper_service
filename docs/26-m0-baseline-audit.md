# M0 基线审计与启动修复（claw-01）

## 目标

在正式进入功能开发前，先确认 `lf-smart-paper-service` 满足以下最小基线：

- 后端服务可启动
- 数据库迁移可执行
- Swagger 文档可访问
- 健康检查接口可用
- 当前仓库结构与文档资产完整可用

## 本次结论

本阶段结论：**项目代码骨架完整，运行环境曾损坏，现已修复并恢复可运行状态。**

已验证通过：

- `./start_service.sh dev` 可启动服务
- `alembic upgrade head` 可执行
- Swagger 可访问：`http://127.0.0.1:8000/docs`
- 健康检查可访问：`GET /api/health`

## 审计范围

### 关键文档

已核查：

- `README.md`
- `AGENTS.md`
- `docs/CODE_LAYOUT.md`
- `start_service.sh`

### 关键目录

已核查：

- `app/api/routes/`
- `app/schemas/`
- `app/services/`
- `app/db/models/`
- `alembic/versions/`
- `docs/`
- `tests/`
- `scripts/`

## 发现的问题

### 1. Python 虚拟环境损坏

审计时发现仓库内原有 `.venv` 为不完整环境，存在以下问题：

- 缺失 `.venv/bin/activate`
- 缺失 `pip`
- 无法导入 `fastapi`
- 无法导入 `uvicorn`
- 无法直接执行 Alembic

这会导致：

- `./start_service.sh dev` 启动失败
- 后端服务无法拉起
- 数据库迁移无法执行

### 2. 系统缺少 venv 组件

宿主机初始状态下缺少 Python 3.12 venv 所需组件，导致无法正确创建标准虚拟环境。

## 修复动作

本次已执行：

1. 安装 `python3.12-venv`
2. 重建仓库内 `.venv`
3. 重新安装 `requirements.txt`
4. 执行 `alembic upgrade head`
5. 启动开发服务并验证接口

## 当前运行方式

在仓库根目录执行：

```bash
./start_service.sh dev
```

默认端口：

- `8000`

可访问地址：

- Swagger：`http://127.0.0.1:8000/docs`
- Health：`http://127.0.0.1:8000/api/health`

## 当前基线判断

### 已满足

- FastAPI 服务可运行
- Swagger 自动文档可用
- 本地 SQLite + 本地文件存储模式已具备基础落地条件
- 项目目录结构已符合现有工程规范
- README / AGENTS / CODE_LAYOUT 文档资产已存在

### 尚待进入后续里程碑处理

- 基于更细颗粒度里程碑重新梳理功能交付边界
- 校验 README 中列出的接口与实际实现的一致性
- 检查前后端联调点与字段契约是否完全对齐
- 补充更明确的里程碑文档与规则沉淀

## 后续建议顺序

### M1：用户与学生基础能力

优先完成：

- 用户创建 / 列表 / 详情 / 更新
- 学生档案建模核查
- 家长-学生关系绑定 / 解绑 / 查询
- 学生简版登录

### M2：错题本基础录入

优先完成：

- 学科字典
- 错题分类字典
- 错误原因字典
- 错题创建 / 列表 / 详情

## 分支说明

由于仓库当前实际默认主分支为 `main`，不存在 `master`，因此本轮开发按产品确认采用：

- 基线分支：`main`
- 开发分支：`claw-01`

后续如需统一命名策略，可单独进行分支治理，但不应阻塞当前开发。
