# lf-smart-paper-service

JuYiFanSan (Smart Paper) 后端服务，负责题目识别、变式题生成与导出任务。

## API (MVP)

- `GET /api/health` 健康检查
- `POST /api/ocr/extract` 上传试卷图片并提取题干
  - `multipart/form-data`：`file`
- `POST /api/variants/generate` 生成同类变式题
  - JSON：`{ "source_text": "...", "count": 3, "grade": "小学", "subject": "math" }`
- `POST /api/export` 创建导出任务
  - JSON：`{ "title": "...", "original_text": "...", "variants": ["..."], "include_images": true }`

## 目录结构

```
app/
  api/routes/        # 路由层
  schemas/           # Pydantic 请求/响应模型
  services/          # 业务逻辑（OCR/生成/导出/存储）
  core/              # 配置与基础设施
  utils/             # 工具方法
```

## 开发

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

健康检查：`http://localhost:8000/api/health`

## 下一步接入

- Qwen2.5-VL 或其他 OCR + Layout 模型
- OpenCV/PIL 图像裁剪
- S3/OSS 对象存储
- LLM 变式题生成
