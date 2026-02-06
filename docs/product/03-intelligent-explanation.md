# 03 - 智能讲解系统

## 背景

错题本的核心价值不仅在于收集和整理错题，更重要的是帮助孩子理解错题背后的知识点和解题方法。通过 AI 生成详细的错题讲解和知识点讲解，让孩子能够自主学习，真正掌握知识。

## 目标

- 为每道错题提供详细的解题步骤和思路讲解
- 识别题目涉及的知识点并提供系统化讲解
- 生成图文并茂、易于理解的讲解内容
- 支持多种讲解风格和难度层级

## 范围 (In Scope)

### 1. 错题讲解生成

#### 功能特性
- **逐步解题**: 分步骤展示解题过程
- **思路分析**: 解释为什么这样做，培养解题思维
- **易错点提示**: 标注常见错误和注意事项
- **多解法对比**: 提供不同解题方法（如果适用）
- **答案验证**: 最后验证答案的正确性

#### 讲解结构
```json
{
    "question_id": 123,
    "explanation": {
        "summary": "本题考查两位数乘法的计算能力",
        "steps": [
            {
                "step_number": 1,
                "title": "理解题意",
                "content": "小明买了 3 包糖果，每包 24 颗...",
                "key_point": "识别这是一个乘法问题"
            },
            {
                "step_number": 2,
                "title": "列出算式",
                "content": "3 × 24 = ?",
                "formula": "3 × 24"
            },
            {
                "step_number": 3,
                "title": "计算过程",
                "content": "使用竖式计算...",
                "calculation": "详细计算步骤"
            }
        ],
        "common_mistakes": [
            "忘记进位",
            "个位和十位相乘顺序错误"
        ],
        "tips": [
            "可以用加法验算：24 + 24 + 24 = 72",
            "记住乘法口诀表可以更快计算"
        ],
        "alternative_methods": [
            {
                "name": "分解计算法",
                "description": "24 = 20 + 4, 所以 3×24 = 3×20 + 3×4 = 60 + 12 = 72"
            }
        ],
        "answer": "72",
        "difficulty": "medium"
    }
}
```

### 2. 知识点讲解

#### 功能特性
- **知识点概念**: 清晰定义知识点
- **公式定理**: 相关的数学公式、语文规则等
- **典型例题**: 提供 2-3 个典型例题
- **知识点关联**: 展示前置知识和后续知识
- **可视化辅助**: 图表、图形等辅助理解

#### 讲解结构
```json
{
    "knowledge_point_id": 45,
    "name": "两位数乘法",
    "subject": "math",
    "grade": "小学三年级",
    "content": {
        "concept": {
            "title": "什么是两位数乘法",
            "description": "两位数乘法是指两个两位数相乘的运算...",
            "prerequisites": ["乘法口诀", "进位加法"]
        },
        "formulas": [
            {
                "name": "竖式乘法",
                "description": "将两个数垂直排列，从个位开始逐位相乘",
                "example": "图片或文字示例"
            }
        ],
        "examples": [
            {
                "title": "例题1：基础两位数乘法",
                "question": "23 × 12 = ?",
                "solution": "详细解答步骤...",
                "answer": "276"
            }
        ],
        "key_points": [
            "注意进位",
            "个位和十位分别相乘后再相加",
            "对齐位数"
        ],
        "common_errors": [
            "忘记进位",
            "位数对齐错误"
        ],
        "practice_suggestions": "多练习乘法口诀，掌握竖式计算方法",
        "related_knowledge": {
            "previous": ["乘法口诀", "一位数乘两位数"],
            "next": ["三位数乘法", "乘法分配律"]
        }
    }
}
```

### 3. 讲解管理

#### 数据存储
- 缓存已生成的讲解内容
- 支持人工审核和优化
- 版本管理（可以更新讲解内容）

#### 讲解个性化
- 根据年级调整讲解难度
- 根据学生掌握情况调整详细程度
- 支持不同的讲解风格（详细/简洁）

### 4. API 接口

#### 错题讲解
- `POST /api/explanations/question/{question_id}` - 生成错题讲解
- `GET /api/explanations/question/{question_id}` - 获取错题讲解
- `PUT /api/explanations/question/{explanation_id}` - 更新讲解内容
- `POST /api/explanations/question/{question_id}/regenerate` - 重新生成讲解

#### 知识点讲解
- `POST /api/explanations/knowledge-point/{kp_id}` - 生成知识点讲解
- `GET /api/explanations/knowledge-point/{kp_id}` - 获取知识点讲解
- `GET /api/explanations/knowledge-point/{kp_id}/examples` - 获取知识点例题

#### 讲解评价
- `POST /api/explanations/{explanation_id}/feedback` - 提交讲解反馈
- `GET /api/explanations/{explanation_id}/feedback` - 获取讲解反馈

## 非目标 (Out of Scope)

- 视频讲解生成
- 语音讲解（TTS）
- 实时互动答疑
- 个性化学习路径推荐

## 数据库设计

### question_explanations (错题讲解)
```sql
CREATE TABLE question_explanations (
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES questions(id) UNIQUE,
    summary TEXT,
    steps JSONB,  -- 解题步骤数组
    common_mistakes JSONB,  -- 易错点数组
    tips JSONB,  -- 提示数组
    alternative_methods JSONB,  -- 其他解法
    difficulty VARCHAR(20),
    style VARCHAR(20) DEFAULT 'detailed',  -- 'detailed', 'concise'
    version INTEGER DEFAULT 1,
    is_reviewed BOOLEAN DEFAULT FALSE,
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### knowledge_point_explanations (知识点讲解)
```sql
CREATE TABLE knowledge_point_explanations (
    id SERIAL PRIMARY KEY,
    knowledge_point_id INTEGER REFERENCES knowledge_points(id) UNIQUE,
    concept JSONB,  -- 概念讲解
    formulas JSONB,  -- 公式定理
    examples JSONB,  -- 典型例题
    key_points JSONB,  -- 关键点
    common_errors JSONB,  -- 常见错误
    practice_suggestions TEXT,
    related_knowledge JSONB,  -- 关联知识点
    visual_aids JSONB,  -- 可视化辅助（图片URL等）
    version INTEGER DEFAULT 1,
    is_reviewed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### explanation_feedback (讲解反馈)
```sql
CREATE TABLE explanation_feedback (
    id SERIAL PRIMARY KEY,
    explanation_id INTEGER NOT NULL,
    explanation_type VARCHAR(20),  -- 'question', 'knowledge_point'
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    is_helpful BOOLEAN,
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 任务拆分 (按优先级)

### 1. 数据模型和基础架构
- [ ] 设计讲解内容数据库 schema
- [ ] 创建数据库迁移脚本
- [ ] 实现 ORM 模型
- [ ] 设计讲解内容的 JSON 结构规范

### 2. 错题讲解生成服务
- [ ] 设计错题讲解 LLM Prompt
- [ ] 实现讲解生成服务
- [ ] 实现结果结构化解析
- [ ] 添加内容质量校验
- [ ] 实现讲解缓存机制

### 3. 知识点讲解生成服务
- [ ] 设计知识点讲解 Prompt
- [ ] 实现知识点讲解生成
- [ ] 生成典型例题
- [ ] 实现知识点关联逻辑

### 4. 讲解内容管理
- [ ] 实现讲解查询接口
- [ ] 实现讲解更新接口
- [ ] 实现讲解版本管理
- [ ] 实现人工审核标记

### 5. 讲解个性化
- [ ] 根据年级调整讲解难度
- [ ] 实现详细/简洁风格切换
- [ ] 基于反馈优化讲解质量

### 6. 可视化辅助
- [ ] 生成数学公式图片
- [ ] 生成几何图形
- [ ] 支持插入图表

### 7. 反馈和评价
- [ ] 实现讲解评价接口
- [ ] 收集用户反馈
- [ ] 分析反馈数据优化 Prompt

## 技术实现要点

### 错题讲解 Prompt 模板

```python
QUESTION_EXPLANATION_PROMPT = """
你是一位优秀的小学{grade}{subject}老师，擅长用浅显易懂的方式讲解题目。

请为以下题目生成详细的解题讲解：

题目内容：
{question_text}

要求：
1. 首先用一句话总结本题考查的知识点
2. 将解题过程分成清晰的步骤（3-5步）
3. 每个步骤包含：
   - 步骤标题
   - 详细内容
   - 关键点说明
4. 列出常见错误（2-3个）
5. 给出解题提示和技巧
6. 如果有多种解法，请提供替代方法
7. 语言要符合{grade}学生的理解水平
8. 使用鼓励性的语气

返回 JSON 格式：
{{
    "summary": "总结",
    "steps": [
        {{
            "step_number": 1,
            "title": "步骤标题",
            "content": "详细内容",
            "key_point": "关键点"
        }}
    ],
    "common_mistakes": ["错误1", "错误2"],
    "tips": ["提示1", "提示2"],
    "alternative_methods": [
        {{
            "name": "方法名",
            "description": "方法说明"
        }}
    ],
    "answer": "最终答案"
}}
"""
```

### 知识点讲解 Prompt 模板

```python
KNOWLEDGE_POINT_EXPLANATION_PROMPT = """
你是一位经验丰富的小学{grade}{subject}老师，擅长知识点讲解。

请为以下知识点生成系统化的讲解内容：

知识点名称：{knowledge_point_name}
学科：{subject}
年级：{grade}

要求：
1. 清晰定义这个知识点的概念
2. 列出需要的前置知识
3. 提供相关的公式、定理或规则
4. 生成 2-3 个典型例题（包含详细解答）
5. 总结关键点和注意事项
6. 列出常见错误
7. 给出练习建议
8. 说明与其他知识点的关系（前置和后续）
9. 语言要生动有趣，符合小学生理解水平

返回 JSON 格式：
{{
    "concept": {{
        "title": "知识点名称",
        "description": "详细描述",
        "prerequisites": ["前置知识1", "前置知识2"]
    }},
    "formulas": [
        {{
            "name": "公式名",
            "description": "说明",
            "example": "示例"
        }}
    ],
    "examples": [
        {{
            "title": "例题标题",
            "question": "题目内容",
            "solution": "详细解答",
            "answer": "答案"
        }}
    ],
    "key_points": ["关键点1", "关键点2"],
    "common_errors": ["常见错误1", "常见错误2"],
    "practice_suggestions": "练习建议",
    "related_knowledge": {{
        "previous": ["前置知识"],
        "next": ["后续知识"]
    }}
}}
"""
```

### 讲解生成服务实现

```python
async def generate_question_explanation(
    question_id: int,
    style: str = "detailed",
    regenerate: bool = False
) -> QuestionExplanation:
    """
    生成错题讲解

    Args:
        question_id: 题目 ID
        style: 讲解风格 ('detailed' or 'concise')
        regenerate: 是否强制重新生成

    Returns:
        QuestionExplanation 对象
    """
    # 1. 检查缓存
    if not regenerate:
        cached = await get_cached_explanation(question_id)
        if cached:
            return cached

    # 2. 获取题目信息
    question = await get_question(question_id)

    # 3. 构建 Prompt
    prompt = build_explanation_prompt(
        question.text,
        question.grade,
        question.subject,
        style
    )

    # 4. 调用 LLM
    response = await call_llm(prompt)

    # 5. 解析结果
    explanation_data = parse_explanation_response(response)

    # 6. 内容质量校验
    validate_explanation(explanation_data)

    # 7. 存储到数据库
    explanation = await save_explanation(question_id, explanation_data)

    return explanation
```

### 内容质量校验

```python
def validate_explanation(explanation_data: dict) -> bool:
    """
    校验讲解内容质量
    """
    # 必须包含基本元素
    required_fields = ['summary', 'steps', 'common_mistakes']
    for field in required_fields:
        if not explanation_data.get(field):
            raise ValueError(f"Missing required field: {field}")

    # 步骤数量合理
    steps = explanation_data.get('steps', [])
    if len(steps) < 2 or len(steps) > 10:
        raise ValueError(f"Invalid number of steps: {len(steps)}")

    # 每个步骤包含必要信息
    for step in steps:
        if not all(k in step for k in ['step_number', 'title', 'content']):
            raise ValueError("Invalid step structure")

    # 内容长度合理
    summary = explanation_data.get('summary', '')
    if len(summary) < 10 or len(summary) > 200:
        raise ValueError("Invalid summary length")

    return True
```

## 接口示例

### 生成错题讲解
```json
POST /api/explanations/question/123

Request:
{
    "style": "detailed",  // 'detailed' or 'concise'
    "force_regenerate": false
}

Response:
{
    "id": 456,
    "question_id": 123,
    "summary": "本题考查两位数乘法的计算能力，需要掌握竖式乘法的方法。",
    "steps": [
        {
            "step_number": 1,
            "title": "理解题意",
            "content": "小明买了 3 包糖果，每包 24 颗，问一共多少颗？这是求 3 个 24 是多少，应该用乘法。",
            "key_point": "识别出这是乘法问题"
        },
        {
            "step_number": 2,
            "title": "列出算式",
            "content": "3 × 24 = ?",
            "formula": "3 × 24"
        },
        {
            "step_number": 3,
            "title": "用竖式计算",
            "content": "先算 4×3=12，写2进1；再算 20×3=60，加上进位的10，得到70；最后 70+2=72",
            "key_point": "注意进位"
        },
        {
            "step_number": 4,
            "title": "验证答案",
            "content": "可以用加法验算：24+24+24=72，答案正确。"
        }
    ],
    "common_mistakes": [
        "忘记进位，算成 62",
        "个位和十位相乘顺序搞混",
        "进位的数字忘记加上"
    ],
    "tips": [
        "记住乘法口诀表，特别是 3 的口诀",
        "竖式计算时从个位开始，注意对齐",
        "做完后用加法验算一下"
    ],
    "alternative_methods": [
        {
            "name": "分解计算法",
            "description": "把 24 分解成 20+4，先算 3×20=60，再算 3×4=12，最后 60+12=72"
        }
    ],
    "answer": "72",
    "difficulty": "medium",
    "created_at": "2025-02-03T10:00:00Z"
}
```

### 生成知识点讲解
```json
POST /api/explanations/knowledge-point/45

Response:
{
    "id": 789,
    "knowledge_point_id": 45,
    "name": "两位数乘法",
    "subject": "math",
    "grade": "小学三年级",
    "content": {
        "concept": {
            "title": "两位数乘法",
            "description": "两位数乘法是指两个两位数相乘，或者一位数乘两位数的运算。这是小学数学中非常重要的计算技能。",
            "prerequisites": ["乘法口诀表", "一位数乘法", "进位加法"]
        },
        "formulas": [
            {
                "name": "竖式乘法",
                "description": "将两个数垂直排列，从个位开始逐位相乘，注意进位",
                "example": "  23\n× 12\n----\n  46  (23×2)\n 230  (23×10)\n----\n 276"
            }
        ],
        "examples": [
            {
                "title": "例题1：一位数乘两位数",
                "question": "3 × 24 = ?",
                "solution": "用竖式计算：先算 3×4=12，写2进1；再算 3×2=6，加进位1得7；答案是72。",
                "answer": "72"
            },
            {
                "title": "例题2：两位数乘两位数",
                "question": "23 × 12 = ?",
                "solution": "先算 23×2=46，再算 23×10=230，最后相加 46+230=276。",
                "answer": "276"
            }
        ],
        "key_points": [
            "从个位开始计算",
            "注意进位不要忘记",
            "竖式对齐很重要",
            "最后把各部分相加"
        ],
        "common_errors": [
            "忘记进位",
            "数位没对齐",
            "乘法口诀记错",
            "十位乘完忘记补0"
        ],
        "practice_suggestions": "每天练习 5-10 道乘法题，先从一位数乘两位数开始，熟练后再练习两位数乘两位数。记住：多练习，多验算！",
        "related_knowledge": {
            "previous": ["乘法口诀表", "一位数乘法", "进位加法"],
            "next": ["三位数乘法", "乘法分配律", "乘法交换律"]
        }
    },
    "created_at": "2025-02-03T10:00:00Z"
}
```

### 提交讲解反馈
```json
POST /api/explanations/456/feedback

Request:
{
    "rating": 5,
    "is_helpful": true,
    "comments": "讲解很清楚，孩子看懂了！"
}

Response:
{
    "message": "感谢您的反馈！"
}
```

## 验收标准

- 错题讲解结构清晰，步骤完整（3-5步）
- 讲解语言符合目标年级学生的理解水平
- 知识点讲解包含概念、例题、关联知识
- 生成时间 < 8 秒
- 内容通过质量校验
- 缓存命中率 > 60%（避免重复生成）
- 用户反馈 "有帮助" 比例 > 80%

## 风险与对策

### LLM 生成质量不稳定
- **风险**: 生成的讲解可能不准确或不适合年级
- **对策**:
  - 精心设计 Prompt，提供充分的示例
  - 实现多轮生成和选择最优结果
  - 添加人工审核机制
  - 收集反馈持续优化

### 讲解内容安全
- **风险**: 可能生成不当内容
- **对策**:
  - 添加内容过滤
  - 敏感词检测
  - 人工抽检

### 成本控制
- **风险**: LLM API 调用成本高
- **对策**:
  - 实现讲解缓存
  - 相似题目复用讲解
  - 使用较小的模型（如 GPT-3.5）
  - 批量生成优化

## 优化方向

1. **讲解复用**: 相似题目可以复用或微调讲解
2. **图文并茂**: 自动生成配图（几何图形、示意图）
3. **难度分级**: 同一题目提供不同难度的讲解
4. **互动式讲解**: 分步骤展示，让学生逐步思考
5. **语音讲解**: 接入 TTS，提供语音版讲解

## 下一步

完成智能讲解系统后，增强打印导出功能（任务 04），支持将错题、讲解、练习卷整合成高质量的打印文档。
