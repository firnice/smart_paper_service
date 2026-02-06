# 02 - 错题管理和整理

## 背景

在完成 MVP 的 OCR 识别和变式题生成后，需要建立完整的错题管理系统，让用户能够系统化地收集、分类、检索和分析错题，形成个性化的错题库。

## 目标

- 建立完整的错题数据库和管理系统
- 实现错题的多维度分类和标签
- 提供强大的错题检索和筛选功能
- 统计分析错题数据，生成学习报告

## 范围 (In Scope)

### 1. 数据模型设计
- **试卷/作业管理** (`papers`)
  - 上传时间、来源（考试/作业/练习）
  - 学科、年级
  - 关联的错题列表

- **错题管理** (`wrong_questions`)
  - 题目内容（复用 MVP 的 questions 表）
  - 错误状态（首次错误、已复习、已掌握）
  - 错误次数统计
  - 收藏/重点标记
  - 自定义笔记

- **分类和标签** (`categories`, `tags`, `knowledge_points`)
  - 学科分类（数学、语文、英语等）
  - 题型分类（选择、填空、应用题等）
  - 知识点标签（可多选）
  - 难度等级（简单、中等、困难）
  - 自定义标签

- **学习记录** (`study_records`)
  - 复习时间
  - 答题结果
  - 用时统计
  - 掌握程度评估

### 2. 核心功能

#### 2.1 错题收集
- 从 OCR 识别结果创建错题
- 手动添加错题
- 批量导入错题
- 关联原始试卷图片

#### 2.2 错题整理
- 自动分类（基于 OCR 识别结果）
- 手动分类和标签
- 批量编辑（批量打标签、分类）
- 错题去重检测

#### 2.3 错题检索
- 按学科筛选
- 按知识点筛选
- 按难度筛选
- 按时间范围筛选
- 按掌握状态筛选
- 关键词搜索（题目内容）
- 组合筛选

#### 2.4 错题分析
- 错题统计（总数、各科占比）
- 知识点薄弱分析
- 错误率趋势图
- 高频错题排行
- 学习进度报告

### 3. API 接口

#### 错题管理
- `POST /api/wrong-questions` - 创建错题
- `GET /api/wrong-questions` - 获取错题列表（支持筛选）
- `GET /api/wrong-questions/{id}` - 获取错题详情
- `PUT /api/wrong-questions/{id}` - 更新错题
- `DELETE /api/wrong-questions/{id}` - 删除错题
- `PATCH /api/wrong-questions/batch` - 批量更新

#### 试卷管理
- `POST /api/papers` - 创建试卷记录
- `GET /api/papers` - 获取试卷列表
- `GET /api/papers/{id}` - 获取试卷详情
- `PUT /api/papers/{id}` - 更新试卷信息

#### 分类和标签
- `GET /api/categories` - 获取分类列表
- `GET /api/tags` - 获取标签列表
- `POST /api/tags` - 创建自定义标签
- `GET /api/knowledge-points` - 获取知识点列表

#### 统计分析
- `GET /api/statistics/overview` - 总体统计
- `GET /api/statistics/by-subject` - 按学科统计
- `GET /api/statistics/by-knowledge-point` - 按知识点统计
- `GET /api/statistics/trend` - 错误率趋势

### 4. 智能功能

#### 自动分类
- 基于 OCR 识别内容自动判断学科
- 基于题目内容自动识别题型
- LLM 辅助识别知识点

#### 知识点识别
- 使用 LLM 分析题目内容
- 匹配预设知识点库
- 支持多知识点关联

#### 错题去重
- 基于题目文本相似度检测
- 提示用户重复题目
- 支持合并或保留

## 非目标 (Out of Scope)

- 复杂的权限管理（多用户协作）
- 社交分享功能
- 题库推荐算法
- 实时同步功能

## 数据库设计

### papers (试卷/作业)
```sql
CREATE TABLE papers (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    source VARCHAR(50),  -- 'exam', 'homework', 'practice'
    subject VARCHAR(50),  -- 'math', 'chinese', 'english'
    grade VARCHAR(20),
    exam_date DATE,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image_urls TEXT[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### wrong_questions (错题)
```sql
CREATE TABLE wrong_questions (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER REFERENCES papers(id),
    question_id INTEGER REFERENCES questions(id),
    status VARCHAR(20) DEFAULT 'new',  -- 'new', 'reviewing', 'mastered'
    error_count INTEGER DEFAULT 1,
    is_bookmarked BOOLEAN DEFAULT FALSE,
    notes TEXT,
    difficulty VARCHAR(20),  -- 'easy', 'medium', 'hard'
    first_error_date DATE DEFAULT CURRENT_DATE,
    last_review_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### categories (分类)
```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    type VARCHAR(50),  -- 'subject', 'question_type', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### tags (标签)
```sql
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### knowledge_points (知识点)
```sql
CREATE TABLE knowledge_points (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    subject VARCHAR(50),
    grade VARCHAR(20),
    parent_id INTEGER REFERENCES knowledge_points(id),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### question_tags (题目标签关联)
```sql
CREATE TABLE question_tags (
    question_id INTEGER REFERENCES questions(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (question_id, tag_id)
);
```

### question_knowledge_points (题目知识点关联)
```sql
CREATE TABLE question_knowledge_points (
    question_id INTEGER REFERENCES questions(id),
    knowledge_point_id INTEGER REFERENCES knowledge_points(id),
    PRIMARY KEY (question_id, knowledge_point_id)
);
```

### study_records (学习记录)
```sql
CREATE TABLE study_records (
    id SERIAL PRIMARY KEY,
    wrong_question_id INTEGER REFERENCES wrong_questions(id),
    study_date DATE DEFAULT CURRENT_DATE,
    result VARCHAR(20),  -- 'correct', 'incorrect', 'skipped'
    time_spent INTEGER,  -- 秒
    mastery_level INTEGER,  -- 1-5
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 任务拆分 (按优先级)

### 1. 数据库迁移和模型
- [ ] 设计完整的数据库 schema
- [ ] 创建数据库迁移脚本
- [ ] 实现 SQLAlchemy ORM 模型
- [ ] 添加索引优化查询性能

### 2. 错题基础 CRUD
- [ ] 实现错题创建接口
- [ ] 实现错题查询接口（支持分页）
- [ ] 实现错题更新接口
- [ ] 实现错题删除接口
- [ ] 实现批量操作接口

### 3. 分类和标签系统
- [ ] 预设基础分类数据（学科、题型）
- [ ] 实现标签管理接口
- [ ] 实现题目打标签功能
- [ ] 实现按分类/标签筛选

### 4. 知识点识别
- [ ] 建立基础知识点库（小学数学、语文）
- [ ] 实现 LLM 知识点识别服务
- [ ] 设计 Prompt 提取题目知识点
- [ ] 实现知识点自动关联
- [ ] 支持手动调整知识点

### 5. 智能分类
- [ ] 实现学科自动识别
- [ ] 实现题型自动识别
- [ ] 实现难度自动评估
- [ ] 批量自动分类功能

### 6. 检索和筛选
- [ ] 实现多维度筛选
- [ ] 实现全文搜索
- [ ] 实现组合查询
- [ ] 优化查询性能

### 7. 统计分析
- [ ] 实现基础统计接口
- [ ] 实现按学科统计
- [ ] 实现按知识点统计
- [ ] 实现时间趋势分析
- [ ] 生成学习报告

### 8. 错题去重
- [ ] 实现文本相似度计算
- [ ] 实现去重检测逻辑
- [ ] 提供去重建议接口

## 技术实现要点

### 知识点识别 Prompt 示例
```python
KNOWLEDGE_POINT_PROMPT = """
你是一位小学教学专家。请分析以下题目涉及的知识点。

题目内容：
{question_text}

学科：{subject}
年级：{grade}

请返回一个 JSON 数组，包含该题目涉及的所有知识点名称。
知识点应该具体明确，例如："两位数加法"、"比较大小"、"图形面积计算"等。

只返回 JSON 数组，不要其他内容。
"""
```

### 自动分类逻辑
```python
def auto_classify_question(question_text: str) -> dict:
    """
    使用 LLM 自动分类题目
    返回: {
        "subject": "math",
        "question_type": "application",
        "difficulty": "medium",
        "knowledge_points": ["两位数乘法", "应用题"]
    }
    """
```

### 相似度检测
```python
from difflib import SequenceMatcher

def detect_duplicate(new_question: str, existing_questions: list) -> list:
    """
    检测题目相似度
    返回相似度 > 0.8 的题目列表
    """
    duplicates = []
    for existing in existing_questions:
        similarity = SequenceMatcher(None, new_question, existing.text).ratio()
        if similarity > 0.8:
            duplicates.append({
                "question_id": existing.id,
                "similarity": similarity
            })
    return duplicates
```

## 接口示例

### 创建错题
```json
POST /api/wrong-questions
{
    "paper_id": 123,
    "question_text": "小明有 8 个苹果，小红有 5 个苹果...",
    "subject": "math",
    "grade": "小学二年级",
    "notes": "加法运算出错",
    "tags": ["加法", "应用题"]
}
```

### 查询错题
```json
GET /api/wrong-questions?subject=math&status=new&knowledge_point=加法&page=1&limit=20

Response:
{
    "total": 45,
    "page": 1,
    "limit": 20,
    "items": [
        {
            "id": 1,
            "question_text": "...",
            "subject": "math",
            "status": "new",
            "error_count": 1,
            "knowledge_points": ["两位数加法", "进位"],
            "tags": ["加法", "应用题"],
            "created_at": "2025-02-01"
        }
    ]
}
```

### 获取统计数据
```json
GET /api/statistics/overview

Response:
{
    "total_questions": 128,
    "by_status": {
        "new": 45,
        "reviewing": 60,
        "mastered": 23
    },
    "by_subject": {
        "math": 80,
        "chinese": 35,
        "english": 13
    },
    "recent_trend": [
        {"date": "2025-02-01", "count": 5},
        {"date": "2025-02-02", "count": 3}
    ],
    "weak_knowledge_points": [
        {"name": "两位数乘法", "error_count": 12},
        {"name": "分数计算", "error_count": 8}
    ]
}
```

## 验收标准

- 错题数据完整存储，包含分类和标签信息
- 知识点识别准确率 > 75%
- 自动分类准确率 > 80%
- 查询接口支持复杂筛选，响应时间 < 500ms
- 统计接口准确反映学习情况
- 错题去重能准确识别相似题目

## 风险与对策

### 知识点库建设
- **风险**: 知识点体系复杂，难以完整覆盖
- **对策**:
  - 先从常见知识点开始，逐步扩充
  - 支持用户自定义知识点
  - 利用 LLM 动态识别

### 分类准确性
- **风险**: 自动分类可能不准确
- **对策**:
  - 提供手动修正功能
  - 记录用户修正数据，优化模型
  - 不确定时提供多个选项供用户选择

### 性能问题
- **风险**: 数据量大时查询性能下降
- **对策**:
  - 添加数据库索引
  - 实现分页查询
  - 使用缓存（Redis）
  - 异步处理统计计算

## 下一步

完成错题管理系统后，接入智能讲解功能（任务 03），为每道错题提供详细的解题思路和知识点讲解。
