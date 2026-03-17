# 30-print-export-image-support

## 背景

学生端此前已经支持：
- 工作台保存带图错题
- 首页 / 错题本 / 详情 / 练习 / 打印页显示题图

但真正生成打印 PDF 时，导出链路仍只吃文本字段，没有把题图渲染进 PDF。

## 本次修复

### 前端
`PrintPage` 在调用 `/api/export` 时，给每道题额外传：
- `image_url`

### 后端
导出模型 `ExportQuestionItem` 增加：
- `image_url`

导出服务 `export_service.py` 新增：
- 解析本地静态图片 URL 或 data URL
- 在练习包 PDF 中插入题图
- 控制题图最大尺寸，避免撑爆版面

## 结果

打印重做包现在不再只是纯文本题单，而是能在 PDF 中保留学生错题图片，尤其适合图文题和截图题。
