# 01 - JuYiFanSan MVP Backend Tasks

## 背景
面向小学阶段的错题整理工具需要后端完成题干提取、插图裁剪、同类题生成与导出。目标是实现“拍照即录入、一键推同类”的核心闭环。

## 目标
- 从试卷图片中提取“去手写”的题干文本，并识别插图坐标。
- 对识别出的插图进行裁剪并存储，文本与插图关联入库。
- 基于题干生成 3 道同类变式题。
- 输出可打印的 PDF 或 Word 文档。

## 范围 (In Scope)
- OCR + 版面分析（Qwen2.5-VL 或等效多模态模型）
- 插图裁剪（OpenCV/PIL）
- 变式题生成（LLM）
- 导出（PDF/DOCX）
- API 端点与基础校验
- 数据存储（题干、插图、生成结果、导出任务）

## 非目标 (Out of Scope)
- 登录与权限体系
- 前端 UI
- 题库推荐与个性化学习路径
- 复杂评分或知识图谱构建

## 交付物
- API 实现与请求/响应模型
- 题目与导出任务的数据库结构
- 图像裁剪与对象存储上传流程
- LLM Prompt 与结果结构化解析
- 导出文件生成与下载

## 任务拆分 (按优先级)
1. **数据模型与存储**
   - 设计表结构：`papers`、`questions`、`question_images`、`variants`、`exports`
   - 统一字段：`id`、`created_at`、`updated_at`、`status`
2. **OCR 识别服务**
   - 接入 Qwen2.5-VL（或适配器），实现图片 -> JSON 解析
   - Prompt 规则：忽略手写、返回题干与插图坐标
   - 结果校验与容错（空文本、坐标缺失）
3. **插图裁剪与存储**
   - 基于坐标裁剪插图并保存
   - 上传对象存储（S3/OSS），返回 URL
   - 关联 `questions` 与 `question_images`
4. **变式题生成**
   - 设计 LLM Prompt，输入题干输出 3 道同类题
   - 结果结构化与敏感词过滤（如涉隐私）
5. **导出服务**
   - 生成 PDF/DOCX：原题（去手写）+ 变式题 + 插图
   - 输出文件保存与下载链接
6. **API 路由**
   - `/api/ocr/extract`
   - `/api/variants/generate`
   - `/api/export`
7. **测试与日志**
   - 关键路径单测（OCR 解析、裁剪、生成、导出）
   - 结构化日志与错误码约定

## 接口定义 (MVP)
- `POST /api/ocr/extract`
  - 入参：`multipart/form-data`，`file`
  - 出参：题干文本与插图 URL 列表
- `POST /api/variants/generate`
  - 入参：`{ "source_text": "...", "count": 3, "grade": "小学", "subject": "math" }`
  - 出参：`variants: [ ... ]`
- `POST /api/export`
  - 入参：`{ "title": "...", "original_text": "...", "variants": ["..."], "include_images": true }`
  - 出参：`{ "export_url": "...", "status": "ready" }`

## 依赖与配置
- `QWEN_VL_API_KEY` / `QWEN_VL_ENDPOINT`
- `LLM_API_KEY` / `LLM_ENDPOINT`
- `OBJECT_STORAGE_BUCKET` / `OBJECT_STORAGE_ENDPOINT`
- `EXPORT_STORAGE_DIR`

## 验收标准
- OCR 输出可稳定解析 JSON，题干无手写痕迹。
- 插图裁剪正确并可访问（URL 可用）。
- 变式题生成符合题型逻辑，数量正确。
- 导出文件可打印，包含原题与变式题。
- API 返回稳定、错误码清晰。

## 风险与对策
- OCR 识别误差：增加重试与人工回退标记。
- 插图坐标错误：在服务端增加边界校验与可视化调试开关。
- LLM 生成不稳定：固定 prompt + 温度上限 + 结果规则校验。
