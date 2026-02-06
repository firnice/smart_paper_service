# 04 - 打印和导出增强

## 背景

在完成错题管理和智能讲解后，需要将这些内容整合成高质量的可打印文档。让家长和孩子能够方便地打印出练习卷、错题集、讲解资料等，支持线下学习和复习。

## 目标

- 生成高质量、排版美观的 PDF 和 Word 文档
- 支持多种文档类型（练习卷、错题集、讲解资料）
- 提供灵活的内容选择和排版选项
- 支持答案分离和答题空间设置
- 优化打印效果，符合实际使用需求

## 范围 (In Scope)

### 1. 文档类型

#### 1.1 练习卷
- **内容**: 原题 + 变式题
- **布局**: 题目顺序排列，预留答题空间
- **选项**:
  - 是否包含答案（分离或附后）
  - 是否包含讲解
  - 题目间距
  - 答题空间大小

#### 1.2 错题集
- **内容**: 错题 + 正确答案 + 错误分析
- **布局**: 每题一页或紧凑排列
- **选项**:
  - 按学科/知识点分组
  - 包含错误次数和日期
  - 包含讲解
  - 包含笔记

#### 1.3 讲解资料
- **内容**: 题目 + 详细讲解 + 知识点讲解
- **布局**: 图文并茂，步骤清晰
- **选项**:
  - 包含典型例题
  - 包含知识点总结
  - 包含练习题

#### 1.4 知识点手册
- **内容**: 知识点体系 + 讲解 + 例题
- **布局**: 章节结构，索引清晰
- **选项**:
  - 按学科组织
  - 包含知识点关联图
  - 包含练习题

### 2. 排版功能

#### 2.1 页面设置
- 纸张大小（A4/A5/Letter）
- 页边距
- 页眉页脚
  - 标题
  - 页码
  - 日期
  - 自定义文本

#### 2.2 题目排版
- 题号样式（1. / 一、 / (1) 等）
- 题目间距
- 答题空间（行数可调）
- 选择题选项排列（横排/竖排）
- 图片大小和位置

#### 2.3 答案排版
- 答案位置（题后/页后/文档末尾/单独文档）
- 答案样式（简答/详细讲解）
- 答案标注（红色/下划线等）

#### 2.4 样式定制
- 字体（宋体/黑体/楷体等）
- 字号（题目/答案/说明）
- 颜色（标题/重点/答案）
- 行间距

### 3. 内容选择

#### 3.1 题目筛选
- 按学科筛选
- 按知识点筛选
- 按难度筛选
- 按时间范围筛选
- 按掌握状态筛选
- 手动选择特定题目

#### 3.2 内容组合
- 仅原题
- 原题 + 变式题
- 原题 + 答案
- 原题 + 讲解
- 原题 + 变式题 + 讲解
- 自定义组合

#### 3.3 数量控制
- 每页题目数量
- 总题目数量
- 变式题数量
- 例题数量

### 4. 模板系统

#### 预设模板
- **简洁练习卷**: 题目紧凑，答题空间适中
- **标准错题集**: 每题配答案和简要分析
- **详细讲解版**: 图文并茂，步骤详细
- **知识点总结**: 章节清晰，重点突出
- **考前冲刺卷**: 题目精选，难度适中

#### 自定义模板
- 保存用户偏好设置
- 创建个性化模板
- 分享模板（可选）

### 5. 导出格式

#### PDF
- 高质量矢量图形
- 可搜索文本
- 页面书签
- 超链接支持

#### Word (DOCX)
- 保留样式和格式
- 支持二次编辑
- 表格和图片

#### 图片 (PNG/JPG)
- 按页导出图片
- 适合手机查看
- 可直接打印

## 非目标 (Out of Scope)

- 在线编辑器
- 协作编辑
- 云端打印服务
- 移动端原生编辑

## 数据库设计

### export_templates (导出模板)
```sql
CREATE TABLE export_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50),  -- 'practice', 'wrong_questions', 'explanation', 'knowledge_point'
    is_preset BOOLEAN DEFAULT FALSE,
    is_public BOOLEAN DEFAULT FALSE,
    config JSONB,  -- 模板配置
    created_by INTEGER,  -- 用户 ID（如果有用户系统）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### export_tasks (导出任务)
```sql
CREATE TABLE export_tasks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50),  -- 'practice', 'wrong_questions', etc.
    template_id INTEGER REFERENCES export_templates(id),
    config JSONB,  -- 导出配置
    question_ids INTEGER[],  -- 题目 ID 列表
    status VARCHAR(20),  -- 'pending', 'processing', 'completed', 'failed'
    file_url TEXT,
    file_format VARCHAR(10),  -- 'pdf', 'docx', 'png'
    file_size INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 模板配置 JSON 结构
```json
{
    "page": {
        "size": "A4",
        "orientation": "portrait",
        "margin": {
            "top": 20,
            "bottom": 20,
            "left": 15,
            "right": 15
        }
    },
    "header": {
        "enabled": true,
        "content": "{{title}} - 第 {{page}} 页",
        "font_size": 10,
        "align": "center"
    },
    "footer": {
        "enabled": true,
        "content": "生成日期：{{date}}",
        "font_size": 9,
        "align": "right"
    },
    "title": {
        "text": "错题练习卷",
        "font_size": 18,
        "font_weight": "bold",
        "align": "center",
        "margin_bottom": 20
    },
    "question": {
        "number_style": "1.",
        "font_size": 12,
        "line_height": 1.5,
        "spacing": 15,
        "answer_space": 3,
        "include_images": true,
        "image_max_width": 400
    },
    "answer": {
        "position": "end_of_document",
        "style": "detailed",
        "color": "#FF0000",
        "show_explanation": true
    },
    "variant": {
        "enabled": true,
        "count": 3,
        "label": "变式题"
    }
}
```

## 任务拆分 (按优先级)

### 1. 基础架构
- [ ] 设计导出任务数据模型
- [ ] 实现模板系统数据结构
- [ ] 选择 PDF 生成库（ReportLab / WeasyPrint）
- [ ] 选择 Word 生成库（python-docx）
- [ ] 设计导出队列系统（异步处理）

### 2. PDF 生成核心功能
- [ ] 实现基础 PDF 生成
- [ ] 实现页面布局（页边距、页眉页脚）
- [ ] 实现题目渲染（文本、编号、间距）
- [ ] 实现图片插入和排版
- [ ] 实现答案渲染

### 3. 练习卷生成
- [ ] 实现题目选择逻辑
- [ ] 实现练习卷布局
- [ ] 实现答题空间预留
- [ ] 实现答案分离
- [ ] 实现变式题整合

### 4. 错题集生成
- [ ] 实现错题集布局
- [ ] 实现错误分析展示
- [ ] 实现按知识点分组
- [ ] 实现统计信息展示

### 5. 讲解资料生成
- [ ] 实现讲解步骤渲染
- [ ] 实现知识点讲解排版
- [ ] 实现多色彩标注
- [ ] 实现图文混排

### 6. Word 导出
- [ ] 实现 Word 基础生成
- [ ] 实现样式设置
- [ ] 实现表格和图片
- [ ] 确保格式兼容性

### 7. 模板系统
- [ ] 实现预设模板
- [ ] 实现自定义模板保存
- [ ] 实现模板应用
- [ ] 实现模板预览

### 8. 高级功能
- [ ] 实现批量导出
- [ ] 实现导出历史记录
- [ ] 实现文件管理（存储、下载、删除）
- [ ] 实现导出进度通知

## 技术实现要点

### PDF 生成库选择

推荐使用 **WeasyPrint**：
- 支持 HTML/CSS 转 PDF
- 排版灵活，样式丰富
- 支持中文字体
- 生成质量高

```python
from weasyprint import HTML, CSS

def generate_pdf(html_content: str, css_style: str, output_path: str):
    """使用 WeasyPrint 生成 PDF"""
    html = HTML(string=html_content)
    css = CSS(string=css_style)
    html.write_pdf(output_path, stylesheets=[css])
```

### HTML 模板示例

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 20mm 15mm;
            @top-center {
                content: "{{title}} - 第" counter(page) "页";
                font-size: 10pt;
            }
            @bottom-right {
                content: "生成日期：{{date}}";
                font-size: 9pt;
            }
        }
        body {
            font-family: 'SimSun', serif;
            font-size: 12pt;
            line-height: 1.5;
        }
        .title {
            text-align: center;
            font-size: 18pt;
            font-weight: bold;
            margin-bottom: 20pt;
        }
        .question {
            margin-bottom: 15pt;
            page-break-inside: avoid;
        }
        .question-number {
            font-weight: bold;
        }
        .answer-space {
            border-bottom: 1px solid #ccc;
            height: 40pt;
            margin-top: 5pt;
        }
        .answer {
            color: #FF0000;
            margin-top: 5pt;
        }
        .explanation {
            background-color: #f0f0f0;
            padding: 10pt;
            margin-top: 10pt;
            border-left: 3pt solid #0066cc;
        }
        img {
            max-width: 400pt;
            display: block;
            margin: 10pt 0;
        }
    </style>
</head>
<body>
    <div class="title">{{title}}</div>

    {% for question in questions %}
    <div class="question">
        <span class="question-number">{{question.number}}.</span>
        {{question.text}}

        {% if question.image_url %}
        <img src="{{question.image_url}}" alt="题目插图">
        {% endif %}

        {% if show_answer_space %}
        <div class="answer-space"></div>
        {% endif %}

        {% if show_answer_inline %}
        <div class="answer">答案：{{question.answer}}</div>
        {% endif %}

        {% if show_explanation %}
        <div class="explanation">
            <strong>讲解：</strong>
            {{question.explanation}}
        </div>
        {% endif %}
    </div>
    {% endfor %}

    {% if show_answer_separate %}
    <div style="page-break-before: always;">
        <h2>参考答案</h2>
        {% for question in questions %}
        <div>
            <strong>{{question.number}}.</strong> {{question.answer}}
        </div>
        {% endfor %}
    </div>
    {% endif %}
</body>
</html>
```

### 导出服务实现

```python
from typing import List, Dict, Any
from jinja2 import Template
import asyncio

async def generate_practice_sheet(
    question_ids: List[int],
    config: Dict[str, Any],
    template_id: Optional[int] = None
) -> str:
    """
    生成练习卷

    Args:
        question_ids: 题目 ID 列表
        config: 导出配置
        template_id: 模板 ID

    Returns:
        导出文件的 URL
    """
    # 1. 获取题目数据
    questions = await get_questions_with_variants(question_ids)

    # 2. 获取或使用默认模板
    if template_id:
        template = await get_template(template_id)
        config = merge_config(template.config, config)

    # 3. 构建 HTML 内容
    html_content = render_html_template(questions, config)

    # 4. 生成 PDF
    output_file = f"practice_sheet_{timestamp()}.pdf"
    output_path = f"/tmp/{output_file}"

    if config.get('format') == 'pdf':
        generate_pdf(html_content, config.get('css', ''), output_path)
    elif config.get('format') == 'docx':
        generate_docx(questions, config, output_path)

    # 5. 上传到对象存储
    file_url = await upload_to_storage(output_path, output_file)

    # 6. 记录导出任务
    await save_export_task(question_ids, config, file_url)

    return file_url


def render_html_template(questions: List[Question], config: Dict) -> str:
    """渲染 HTML 模板"""
    template = Template(HTML_TEMPLATE)

    context = {
        'title': config.get('title', '练习卷'),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'questions': questions,
        'show_answer_space': config.get('answer.position') == 'inline_space',
        'show_answer_inline': config.get('answer.position') == 'inline',
        'show_answer_separate': config.get('answer.position') == 'end_of_document',
        'show_explanation': config.get('answer.show_explanation', False),
    }

    return template.render(**context)
```

### Word 文档生成

```python
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def generate_docx(questions: List[Question], config: Dict, output_path: str):
    """生成 Word 文档"""
    doc = Document()

    # 设置页面
    section = doc.sections[0]
    section.page_height = Inches(11.69)  # A4
    section.page_width = Inches(8.27)
    section.top_margin = Inches(0.79)
    section.bottom_margin = Inches(0.79)

    # 标题
    title = doc.add_heading(config.get('title', '练习卷'), level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 题目
    for idx, question in enumerate(questions, 1):
        # 题号和题目文本
        p = doc.add_paragraph()
        p.add_run(f"{idx}. ").bold = True
        p.add_run(question.text)

        # 插图
        if question.image_url:
            doc.add_picture(question.image_url, width=Inches(4))

        # 答题空间
        if config.get('answer.position') == 'inline_space':
            for _ in range(config.get('question.answer_space', 3)):
                doc.add_paragraph('_' * 50)

        # 答案
        if config.get('answer.position') == 'inline':
            answer_p = doc.add_paragraph()
            answer_run = answer_p.add_run(f"答案：{question.answer}")
            answer_run.font.color.rgb = RGBColor(255, 0, 0)

    # 分离答案页
    if config.get('answer.position') == 'end_of_document':
        doc.add_page_break()
        doc.add_heading('参考答案', level=2)
        for idx, question in enumerate(questions, 1):
            doc.add_paragraph(f"{idx}. {question.answer}")

    doc.save(output_path)
```

## API 接口

### 生成练习卷
```json
POST /api/export/practice-sheet

Request:
{
    "title": "数学练习卷",
    "template_id": 1,  // 可选，使用预设模板
    "question_ids": [1, 2, 3, 4, 5],
    "include_variants": true,
    "variant_count": 3,
    "format": "pdf",  // 'pdf', 'docx', 'png'
    "config": {
        "page": {
            "size": "A4",
            "orientation": "portrait"
        },
        "answer": {
            "position": "end_of_document",
            "show_explanation": false
        },
        "question": {
            "answer_space": 3
        }
    }
}

Response:
{
    "task_id": 123,
    "status": "processing",
    "estimated_time": 10
}
```

### 查询导出任务状态
```json
GET /api/export/tasks/123

Response:
{
    "task_id": 123,
    "status": "completed",
    "file_url": "https://storage.example.com/exports/practice_sheet_20250203.pdf",
    "file_format": "pdf",
    "file_size": 524288,
    "created_at": "2025-02-03T10:00:00Z",
    "completed_at": "2025-02-03T10:00:08Z"
}
```

### 获取模板列表
```json
GET /api/export/templates

Response:
{
    "templates": [
        {
            "id": 1,
            "name": "简洁练习卷",
            "type": "practice",
            "is_preset": true,
            "preview_url": "https://example.com/preview/1.png"
        },
        {
            "id": 2,
            "name": "详细讲解版",
            "type": "explanation",
            "is_preset": true
        }
    ]
}
```

### 创建自定义模板
```json
POST /api/export/templates

Request:
{
    "name": "我的练习卷模板",
    "type": "practice",
    "config": {
        // 完整配置
    }
}

Response:
{
    "id": 10,
    "name": "我的练习卷模板",
    "created_at": "2025-02-03T10:00:00Z"
}
```

## 验收标准

- PDF 生成质量高，可直接打印使用
- Word 文档保留格式，可二次编辑
- 生成时间：10 题以内 < 10 秒，20 题以内 < 20 秒
- 支持 A4/A5 纸张，排版美观
- 答案分离功能正常
- 模板系统稳定，配置灵活
- 文件大小合理（10 题 PDF < 2MB）
- 中文字体显示正常

## 风险与对策

### PDF 生成性能
- **风险**: 大量题目时生成速度慢
- **对策**:
  - 使用异步队列处理
  - 优化图片大小和质量
  - 分批生成大文档
  - 缓存常用内容

### 中文字体支持
- **风险**: PDF 中文显示异常
- **对策**:
  - 嵌入中文字体
  - 测试多种字体
  - 提供字体配置选项

### 排版复杂度
- **风险**: 复杂内容排版困难
- **对策**:
  - 使用成熟的模板引擎
  - 提供预设模板
  - 限制过度定制

### 文件存储
- **风险**: 导出文件占用大量存储空间
- **对策**:
  - 设置文件过期时间（7天）
  - 自动清理旧文件
  - 压缩 PDF 文件

## 优化方向

1. **模板市场**: 用户分享和下载模板
2. **在线预览**: 生成前预览效果
3. **批量导出**: 一次性导出多个文档
4. **智能排版**: 自动优化页面布局
5. **多端适配**: 手机/平板专用格式
6. **云打印**: 对接云打印服务

## 下一步

完成打印导出增强后，产品的核心功能已基本完善。可以继续开发：
- 用户登录和权限系统
- 学习进度跟踪
- 智能推荐和个性化学习路径
- 家长端和学生端功能
- 数据分析和报表
