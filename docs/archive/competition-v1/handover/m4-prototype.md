# 人岗匹配系统

一个智能简历与岗位匹配系统，支持简历解析、技能提取、岗位匹配和测试数据生成。

## 功能特性

| 功能 | 说明 |
|------|------|
| 简历解析 | 支持文本、PDF、Word格式简历自动解析 |
| 技能提取 | 自动识别500+技能关键词，支持同义词匹配 |
| 岗位匹配 | 智能计算匹配度，生成推荐建议 |
| 批量匹配 | 支持多简历vs多岗位的批量排名 |
| 测试数据 | 自动生成测试数据进行功能验证 |

## 项目结构

```
人岗匹配/
├── skill_extractor.py      # 技能关键词提取器
│   ├── 编程语言库 (50+)
│   ├── 框架库 (40+)
│   ├── 数据库/云服务库 (60+)
│   ├── AI/机器学习库 (30+)
│   └── 同义词映射 (200+)
│
├── resume_parser.py        # 简历解析器
│   ├── 个人信息提取
│   ├── 教育经历解析
│   ├── 工作经历解析
│   └── 技能自动提取
│
├── job_parser.py           # 岗位描述解析器
│   ├── 职位信息提取
│   ├── 任职要求解析
│   ├── 加分项提取
│   └── 技能要求提取
│
├── matcher.py              # 人岗匹配器
│   ├── 技能匹配算法
│   ├── 权重计算
│   ├── 批量匹配
│   └── 推荐建议生成
│
├── file_parser.py          # 文件解析器 (可选)
│   ├── PDF解析 (pdfplumber)
│   ├── Word解析 (python-docx)
│   └── 批量文件处理
│
├── generate_test_data.py   # 测试数据生成器
│   ├── 随机简历生成
│   ├── 随机岗位生成
│   └── 批量数据导出
│
├── main.py                 # 主程序 (文本版)
├── resume_matcher_app.py   # 应用 (支持文件解析)
├── requirements.txt        # 依赖列表
└── jobs/                   # 岗位描述目录
    └── 高级后端工程师.txt
```

## 快速开始

### 1. 安装依赖

```bash
pip install pdfplumber python-docx mammoth
```

### 2. 运行测试

```bash
python main.py
```

### 3. 使用示例

#### 简历与岗位匹配
```python
from matcher import match_resume_job

resume = """
姓名：张三
地点：北京
技能：Python, Java, MySQL, Redis, Docker
"""

job = """
【后端工程师】
要求：Python, Java, MySQL, Redis
"""

result = match_resume_job(resume, job)
print(f"匹配得分: {result['skills_match']['total_score']}分")
print(f"推荐: {result['recommendation']}")
```

#### 批量匹配排名
```python
from matcher import batch_match

resumes = [
    "姓名：A\n技能：Python, Django, MySQL",
    "姓名：B\n技能：Java, Spring, MySQL",
]

jobs = [
    "【Python开发】\n要求：Python, Django, MySQL",
]

results = batch_match(resumes, jobs)
# results 已按匹配度排序
```

## 匹配算法

### 技能匹配流程

```
1. 简历解析 → 提取个人信息、教育经历、技能列表
2. 岗位解析 → 提取职位要求、技能要求
3. 技能标准化 → 同义词转换 (springboot → Spring Boot)
4. 匹配计算 → 精确匹配 + 模糊匹配
5. 权重计算 → 编程语言1.5x, 后端框架1.3x, 数据库1.2x
6. 评分 + 推荐建议
```

### 评分规则

| 项目 | 说明 |
|------|------|
| 基础分 | 技能匹配加权总分 |
| 核心技能bonus | 匹配编程语言+框架+数据库 +10分 |
| 匹配率 | 匹配技能数 / 岗位要求技能数 |

### 推荐等级

| 得分 | 推荐 |
|------|------|
| ≥90分 | 强烈推荐 |
| ≥70分 | 建议面试 |
| ≥50分 | 可考虑 |
| <50分 | 不太推荐 |

## 技能库

### 支持的技能类别

- **编程语言**: Python, Java, Go, JavaScript, C++, Rust 等 50+
- **前端框架**: React, Vue, Angular, Next.js 等 30+
- **后端框架**: Spring Boot, Django, Gin, Flask 等 30+
- **数据库**: MySQL, Redis, MongoDB, Elasticsearch 等 30+
- **云/DevOps**: AWS, Docker, Kubernetes, Jenkins 等 40+
- **AI/ML**: TensorFlow, PyTorch, NLP 等 25+
- **软件工程**: 分布式, 微服务, 高并发 等 30+

### 同义词支持

系统自动识别以下变体：

```
python    → Python
springboot → Spring Boot
k8s       → Kubernetes
es        → Elasticsearch
mq        → 消息队列
高并发    → 高并发
微服务    → 微服务
```

## 批量数据生成

```python
from generate_test_data import generate_dataset

# 生成10份简历和5个岗位
dataset = generate_dataset(num_resumes=10, num_jobs=5)

# 保存到文件
from generate_test_data import save_test_data
save_test_data()
```

生成文件：
- `test_resumes.json` - 简历列表
- `test_jobs.json` - 岗位列表
- `test_dataset.json` - 完整数据集

## 文件格式支持

| 格式 | 扩展名 | 依赖 |
|------|--------|------|
| 文本 | .txt | 内置 |
| PDF | .pdf | pdfplumber |
| Word | .docx | python-docx |
| Word | .doc | mammoth/textract |

## 扩展开发

### 添加新技能

在 `skill_extractor.py` 中添加：

```python
# 添加到对应类别
LANGUAGES.add('新语言')

# 添加同义词
SYNONYMS['新语言简称'] = '新语言'
```

### 自定义权重

在 `matcher.py` 中修改：

```python
SKILL_WEIGHTS = {
    '编程语言': 2.0,   # 提高权重
    '后端框架': 1.5,
    # ...
}
```

## 性能

- 单次匹配: <10ms
- 批量100简历 vs 10岗位: <1秒
- 技能提取: 500+关键词 / <5ms

## 许可证

MIT License