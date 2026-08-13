"""
技能关键词提取器 V2
包含常见编程语言、框架、工具、软技能等关键词库
支持同义词匹配和部分匹配
"""

import re
from typing import List

# ==================== 技能库 ====================

# 编程语言
LANGUAGES = {
    'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Go', 'Rust',
    'Ruby', 'PHP', 'Swift', 'Kotlin', 'Scala', 'R', 'MATLAB', 'Perl',
    'Shell', 'Bash', 'PowerShell', 'SQL', 'HTML', 'CSS', 'SASS', 'LESS',
    'Lua', 'Dart', 'Objective-C', 'VB.NET', 'Pascal', 'Haskell', 'Clojure',
    'Elixir', 'Erlang', 'F#', 'Julia', 'Groovy', 'JavaScript', 'JS', 'TS'
}

# 技能同义词映射
SYNONYMS = {
    # 编程语言
    'python': 'Python', 'py': 'Python', 'python3': 'Python',
    'java': 'Java',
    'javascript': 'JavaScript', 'js': 'JavaScript', 'es6': 'JavaScript', 'es5': 'JavaScript',
    'typescript': 'TypeScript', 'ts': 'TypeScript',
    'c++': 'C++', 'cpp': 'C++',
    'c#': 'C#', 'csharp': 'C#',
    'go': 'Go', 'golang': 'Go',
    'rust': 'Rust', 'rs': 'Rust',
    'ruby': 'Ruby', 'rb': 'Ruby',
    'php': 'PHP',
    'swift': 'Swift',
    'kotlin': 'Kotlin', 'kt': 'Kotlin',
    'scala': 'Scala',
    'sql': 'SQL', 'mysql': 'MySQL',
    'html': 'HTML', 'htm': 'HTML',
    'css': 'CSS', 'scss': 'CSS', 'sass': 'CSS',

    # 前端框架
    'react': 'React', 'reactjs': 'React', 'react.js': 'React',
    'vue': 'Vue', 'vuejs': 'Vue', 'vue.js': 'Vue',
    'angular': 'Angular', 'angularjs': 'Angular', 'angular.js': 'Angular',
    'svelte': 'Svelte',
    'jquery': 'jQuery', 'jq': 'jQuery',
    'bootstrap': 'Bootstrap',
    'tailwind': 'Tailwind', 'tailwindcss': 'Tailwind',
    'element': 'Element UI', 'elementui': 'Element UI',
    'antd': 'Ant Design', 'ant design': 'Ant Design',
    'nextjs': 'Next.js', 'next.js': 'Next.js', 'next': 'Next.js',
    'nuxt': 'Nuxt.js', 'nuxtjs': 'Nuxt.js', 'nuxt.js': 'Nuxt.js',
    'gatsby': 'Gatsby',
    'vite': 'Vite',
    'webpack': 'Webpack',
    'parcel': 'Parcel',
    'redux': 'Redux',
    'vuex': 'Vuex',
    'mobx': 'MobX',
    'rxjs': 'RxJS',
    'threejs': 'Three.js', 'three.js': 'Three.js',
    'd3': 'D3.js', 'd3js': 'D3.js',
    'chartjs': 'Chart.js', 'chart.js': 'Chart.js',
    'echarts': 'ECharts',
    'axios': 'Axios',
    'fetch': 'Fetch',
    'websocket': 'WebSocket', 'ws': 'WebSocket',
    'rest': 'REST', 'restful': 'REST',
    'graphql': 'GraphQL', 'gql': 'GraphQL',

    # 后端框架
    'django': 'Django',
    'flask': 'Flask',
    'fastapi': 'FastAPI',
    'spring': 'Spring', 'springframework': 'Spring',
    'springboot': 'Spring Boot', 'spring boot': 'Spring Boot',
    'springcloud': 'Spring Cloud', 'spring cloud': 'Spring Cloud',
    'nodejs': 'Node.js', 'node.js': 'Node.js', 'node': 'Node.js',
    'expressjs': 'Express', 'express.js': 'Express', 'express': 'Express',
    'koa': 'Koa', 'koajs': 'Koa',
    'nestjs': 'NestJS', 'nest.js': 'NestJS', 'nest': 'NestJS',
    'fastify': 'Fastify',
    'rubyonrails': 'Ruby on Rails', 'rails': 'Ruby on Rails', 'ror': 'Ruby on Rails',
    'laravel': 'Laravel',
    'symfony': 'Symfony',
    'codeigniter': 'CodeIgniter', 'ci': 'CodeIgniter',
    'aspnet': 'ASP.NET', 'asp.net': 'ASP.NET',
    'aspnetcore': 'ASP.NET Core', 'asp.net core': 'ASP.NET Core',
    'gin': 'Gin', 'gingo': 'Gin',
    'iris': 'Iris',
    'echo': 'Echo',
    'beego': 'Beego',
    'fiber': 'Fiber',
    'hono': 'Hono',

    # 数据库
    'mysql': 'MySQL',
    'postgresql': 'PostgreSQL', 'postgres': 'PostgreSQL', 'pg': 'PostgreSQL',
    'mongodb': 'MongoDB', 'mongo': 'MongoDB',
    'redis': 'Redis',
    'elasticsearch': 'Elasticsearch', 'es': 'Elasticsearch',
    'oracle': 'Oracle',
    'sqlserver': 'SQL Server', 'mssql': 'SQL Server', 'sql server': 'SQL Server',
    'sqlite': 'SQLite',
    'cassandra': 'Cassandra',
    'dynamodb': 'DynamoDB', 'dynamo': 'DynamoDB',
    'neo4j': 'Neo4j',
    'influxdb': 'InfluxDB',
    'memcached': 'Memcached',
    'rabbitmq': 'RabbitMQ', 'rabbit': 'RabbitMQ',
    'kafka': 'Kafka',
    'mqtt': 'MQTT',
    'hbase': 'HBase',
    'hive': 'Hive',
    'spark': 'Spark',
    'presto': 'Presto',
    'clickhouse': 'ClickHouse',
    'tidb': 'TiDB', 'ti db': 'TiDB',

    # 大数据/云计算
    'hadoop': 'Hadoop',
    'hdfs': 'HDFS',
    'mapreduce': 'MapReduce',
    'flink': 'Flink',
    'storm': 'Storm',
    'aws': 'AWS', 'amazon web services': 'AWS', 'amazonws': 'AWS',
    'azure': 'Azure', 'microsoft azure': 'Azure',
    'gcp': 'GCP', 'google cloud': 'GCP', 'google cloud platform': 'GCP',
    'aliyun': '阿里云', '阿里云': '阿里云', 'ali cloud': '阿里云',
    'tencentcloud': '腾讯云', '腾讯云': '腾讯云',
    'huaweicloud': '华为云', '华为云': '华为云',
    'ksyun': '金山云', '金山云': '金山云',
    'docker': 'Docker',
    'kubernetes': 'Kubernetes', 'k8s': 'Kubernetes',
    'helm': 'Helm',
    'jenkins': 'Jenkins',
    'gitlabci': 'GitLab CI', 'gitlab ci': 'GitLab CI',
    'githubactions': 'GitHub Actions', 'github actions': 'GitHub Actions',
    'travisci': 'Travis CI', 'travis ci': 'Travis CI',
    'circleci': 'CircleCI', 'circle ci': 'CircleCI',
    'ansible': 'Ansible',
    'terraform': 'Terraform',
    'puppet': 'Puppet',
    'chef': 'Chef',
    'vagrant': 'Vagrant',
    'openstack': 'OpenStack',
    'vmware': 'VMware',
    'prometheus': 'Prometheus',
    'grafana': 'Grafana',
    'elk': 'ELK', 'elastic stack': 'ELK',

    # AI/机器学习
    'tensorflow': 'TensorFlow', 'tf': 'TensorFlow',
    'pytorch': 'PyTorch',
    'keras': 'Keras',
    'caffe': 'Caffe',
    'mxnet': 'MXNet',
    'scikit-learn': 'Scikit-learn', 'sklearn': 'Scikit-learn',
    'pandas': 'Pandas',
    'numpy': 'NumPy',
    'scipy': 'SciPy',
    'matplotlib': 'Matplotlib',
    'seaborn': 'Seaborn',
    'opencv': 'OpenCV', 'cv': 'OpenCV',
    'pillow': 'Pillow', 'pil': 'Pillow',
    'nltk': 'NLTK',
    'spacy': 'SpaCy',
    'gensim': 'Gensim',
    'jieba': 'jieba',
    'lstm': 'LSTM',
    'cnn': 'CNN',
    'rnn': 'RNN',
    'transformer': 'Transformer',
    'bert': 'BERT',
    'gpt': 'GPT',
    'word2vec': 'Word2Vec',
    'embedding': 'Embedding',
    'nlp': 'NLP', '自然语言处理': 'NLP',
    'xgboost': 'XGBoost',
    'lightgbm': 'LightGBM',
    'catboost': 'CatBoost',
    'randomforest': 'Random Forest', 'random forest': 'Random Forest',
    'svm': 'SVM',
    'kmeans': 'K-Means', 'k-means': 'K-Means',
    'ml': '机器学习', '机器学习': '机器学习', 'ml': '机器学习', 'machine learning': '机器学习',
    'dl': '深度学习', '深度学习': '深度学习', 'deep learning': '深度学习',
    'ai': 'AI', '人工智能': 'AI',

    # DevOps/运维
    'linux': 'Linux',
    'unix': 'Unix',
    'windowsserver': 'Windows Server',
    'nginx': 'Nginx',
    'apache': 'Apache',
    'tomcat': 'Tomcat',
    'git': 'Git',
    'svn': 'SVN',
    'gitlab': 'GitLab',
    'github': 'GitHub',
    'bitbucket': 'Bitbucket',
    'cicd': 'CI/CD', 'ci cd': 'CI/CD', '持续集成': 'CI/CD',
    'devops': 'DevOps',
    'sre': 'SRE',
    'agile': 'Agile', '敏捷开发': 'Agile',
    'scrum': 'Scrum',
    'kanban': 'Kanban',
    'tdd': 'TDD', '测试驱动开发': 'TDD',
    'jira': 'Jira',
    'confluence': 'Confluence',

    # 软件工程
    'uml': 'UML',
    '设计模式': '设计模式', 'design pattern': '设计模式',
    '数据结构': '数据结构', 'data structure': '数据结构',
    '算法': '算法', 'algorithm': '算法',
    '面向对象': '面向对象', 'oop': '面向对象', '面向对象编程': '面向对象',
    '微服务': '微服务', 'microservice': '微服务', 'microservices': '微服务',
    '分布式': '分布式', 'distributed': '分布式',
    '高并发': '高并发', 'high concurrency': '高并发', 'high concurrency': '高并发',
    '缓存': '缓存', 'cache': '缓存',
    '消息队列': '消息队列', 'mq': '消息队列', 'message queue': '消息队列',
    '负载均衡': '负载均衡', 'load balance': '负载均衡', 'lb': '负载均衡',
    '限流': '限流', 'rate limit': '限流',
    '熔断': '熔断', 'circuit breaker': '熔断',
    '降级': '降级', 'degradation': '降级',
    'cap': 'CAP',
    'base': 'BASE',
    'api': 'API', 'restful api': 'REST',
    'sdk': 'SDK',
    'ide': 'IDE',
    'tcp': 'TCP', 'udp': 'UDP', 'http': 'HTTP', 'https': 'HTTPS',
    'oauth': 'OAuth', 'jwt': 'JWT', 'sso': 'SSO',
    'oauth2': 'OAuth',
    '安全': '安全', 'security': '安全', '加密': '加密', 'encryption': '加密',
    '并发': '并发', 'concurrency': '并发',
    '异步': '异步', 'async': '异步',
    '性能优化': '性能优化', 'optimization': '性能优化',
    '源码': '源码', 'source code': '源码',
}

# 前端框架/库
FRONTEND = {
    'React', 'Vue', 'Angular', 'Svelte', 'jQuery', 'Bootstrap', 'Tailwind',
    'Element UI', 'Ant Design', 'MUI', 'Chakra UI', 'Semantic UI',
    'Next.js', 'Nuxt.js', 'Gatsby', 'Vite', 'Webpack', 'Parcel',
    'Redux', 'Vuex', 'MobX', 'RxJS', 'Three.js', 'D3.js', 'Chart.js',
    'ECharts', 'Axios', 'Fetch', 'WebSocket', 'REST', 'GraphQL'
}

# 后端框架
BACKEND = {
    'Django', 'Flask', 'FastAPI', 'Spring', 'Spring Boot', 'Spring Cloud',
    'Node.js', 'Express', 'Koa', 'NestJS', 'Fastify', 'Ruby on Rails',
    'Laravel', 'Symfony', 'CodeIgniter', 'ASP.NET', 'ASP.NET Core',
    'Gin', 'Iris', 'Echo', 'Beego', 'Saber', 'Fiber', 'Hono'
}

# 数据库
DATABASE = {
    'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch', 'Oracle',
    'SQL Server', 'SQLite', 'Cassandra', 'DynamoDB', 'Neo4j', 'InfluxDB',
    'Memcached', 'RabbitMQ', 'Kafka', 'MQTT', 'HBase', 'Hive',
    'Spark', 'Presto', 'ClickHouse', 'TiDB'
}

# 大数据/云计算
BIGDATA_CLOUD = {
    'Hadoop', 'HDFS', 'MapReduce', 'Spark', 'Flink', 'Storm', 'Kafka',
    'AWS', 'Azure', 'GCP', '阿里云', '腾讯云', '华为云', '金山云',
    'Docker', 'Kubernetes', 'K8S', 'Helm', 'Jenkins', 'GitLab CI', 'GitHub Actions',
    'Travis CI', 'CircleCI', 'Ansible', 'Terraform', 'Puppet', 'Chef',
    'Vagrant', 'OpenStack', 'VMware', 'Prometheus', 'Grafana', 'ELK'
}

# AI/机器学习
AI_ML = {
    'TensorFlow', 'PyTorch', 'Keras', 'Caffe', 'MXNet', 'Scikit-learn',
    'Pandas', 'NumPy', 'SciPy', 'Matplotlib', 'Seaborn', 'OpenCV',
    'Pillow', 'NLTK', 'SpaCy', 'Gensim', 'jieba', 'LSTM', 'CNN', 'RNN',
    'Transformer', 'BERT', 'GPT', 'Word2Vec', 'Embedding', 'NLP',
    'XGBoost', 'LightGBM', 'CatBoost', 'Random Forest', 'SVM', 'K-Means',
    '机器学习', '深度学习', 'AI'
}

# DevOps/运维
DEVOPS = {
    'Linux', 'Unix', 'Windows Server', 'Nginx', 'Apache', 'Tomcat',
    'Jenkins', 'Git', 'SVN', 'GitLab', 'GitHub', 'Bitbucket',
    'Docker', 'Kubernetes', 'Ansible', 'Terraform', 'Puppet', 'Chef',
    'Prometheus', 'Grafana', 'ELK', 'Zabbix', 'Nagios', 'Splunk',
    'CI/CD', 'DevOps', 'SRE', 'Agile', 'Scrum', 'Kanban', 'Jira', 'Confluence'
}

# 软件工程
SOFTWARE_ENGINEERING = {
    'UML', '设计模式', '数据结构', '算法', '面向对象', 'OOP',
    '敏捷开发', 'Scrum', 'Kanban', 'TDD', '单元测试', '集成测试',
    '系统设计', '微服务', '分布式', '高并发', '缓存', '消息队列',
    '负载均衡', '限流', '熔断', '降级', 'CAP', 'BASE', 'API',
    'SDK', 'IDE', 'TCP', 'UDP', 'HTTP', 'HTTPS', 'OAuth', 'JWT', 'SSO',
    '安全', '加密', '并发', '异步', '性能优化', '源码'
}

# 软技能
SOFT_SKILLS = {
    '沟通', '团队协作', '领导力', '项目管理', '时间管理', '问题解决',
    '分析能力', '学习能力', '创新能力', '适应能力', '抗压能力',
    '文档编写', '演讲', '英语', '日语', '韩语'
}

# 专业领域
DOMAINS = {
    '金融', '电商', '教育', '医疗', '游戏', '社交', '出行', '内容',
    '企业服务', 'SaaS', 'B2B', 'B2C', 'C2C', 'O2O', '物联网', '5G',
    '区块链', '元宇宙', 'AR', 'VR', '信息安全', '网络安全',
    '风控', '反欺诈', '推荐系统', '搜索', '广告', '增长黑客'
}


def get_all_skills() -> set:
    """获取所有技能关键词（标准化后）"""
    all_skills = set()
    all_skills.update(LANGUAGES)
    all_skills.update(FRONTEND)
    all_skills.update(BACKEND)
    all_skills.update(DATABASE)
    all_skills.update(BIGDATA_CLOUD)
    all_skills.update(AI_ML)
    all_skills.update(DEVOPS)
    all_skills.update(SOFTWARE_ENGINEERING)
    all_skills.update(DOMAINS)
    return all_skills


def normalize_skill(skill: str) -> str:
    """标准化技能名称"""
    skill_lower = skill.lower().strip()
    # 检查同义词
    if skill_lower in SYNONYMS:
        return SYNONYMS[skill_lower]
    return skill


def extract_skills(text: str, enable_fuzzy: bool = True) -> list:
    """
    从文本中提取技能关键词

    Args:
        text: 待分析的文本
        enable_fuzzy: 是否启用模糊匹配

    Returns:
        提取到的技能列表（标准化后）
    """
    if not text:
        return []

    found_skills = set()
    all_skills = get_all_skills()
    text_lower = text.lower()

    # 方法1: 精确匹配（使用单词边界）
    for skill in all_skills:
        if skill.isascii():
            # 英文技能使用正则匹配
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found_skills.add(skill)
        else:
            # 中文技能直接包含匹配
            if skill in text:
                found_skills.add(skill)

    # 方法2: 同义词匹配
    for short_form, standard_form in SYNONYMS.items():
        if short_form != standard_form:  # 避免自我映射
            pattern = r'\b' + re.escape(short_form) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.add(standard_form)

    # 方法3: 模糊匹配（可选）
    if enable_fuzzy:
        fuzzy_skills = [
            ('java', 'Java'), ('spring', 'Spring Boot'), ('springboot', 'Spring Boot'),
            ('springcloud', 'Spring Cloud'), ('python', 'Python'), ('js', 'JavaScript'),
            ('ts', 'TypeScript'), ('go', 'Go'), ('golang', 'Go'),
            ('node', 'Node.js'), ('react', 'React'), ('vue', 'Vue'),
            ('angular', 'Angular'), ('flask', 'Flask'), ('django', 'Django'),
            ('fastapi', 'FastAPI'), ('gin', 'Gin'), ('express', 'Express'),
            ('mysql', 'MySQL'), ('mongo', 'MongoDB'), ('postgres', 'PostgreSQL'),
            ('redis', 'Redis'), ('es', 'Elasticsearch'), ('kafka', 'Kafka'),
            ('docker', 'Docker'), ('k8s', 'Kubernetes'), ('aws', 'AWS'),
            ('git', 'Git'), ('linux', 'Linux'), ('nginx', 'Nginx'),
            ('tf', 'TensorFlow'), ('pytorch', 'PyTorch'), ('sklearn', 'Scikit-learn'),
            ('ml', '机器学习'), ('dl', '深度学习'), ('ai', 'AI'),
            ('nlp', 'NLP'), ('cnn', 'CNN'), ('rnn', 'RNN'),
            ('高并发', '高并发'), ('分布式', '分布式'), ('微服务', '微服务'),
            ('缓存', '缓存'), ('消息队列', '消息队列'), ('负载均衡', '负载均衡'),
        ]
        for fuzzy, standard in fuzzy_skills:
            pattern = r'\b' + re.escape(fuzzy) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.add(standard)

    # 去重并按类别排序
    return list(found_skills)


def get_skill_category(skill: str) -> str:
    """获取技能所属类别"""
    if skill in LANGUAGES:
        return '编程语言'
    elif skill in FRONTEND:
        return '前端技术'
    elif skill in BACKEND:
        return '后端框架'
    elif skill in DATABASE:
        return '数据库'
    elif skill in BIGDATA_CLOUD:
        return '大数据/云'
    elif skill in AI_ML:
        return 'AI/机器学习'
    elif skill in DEVOPS:
        return 'DevOps/运维'
    elif skill in SOFTWARE_ENGINEERING:
        return '软件工程'
    elif skill in DOMAINS:
        return '专业领域'
    else:
        return '其他'


def categorize_skills(skills: list) -> dict:
    """对技能列表进行分类"""
    categories = {}
    for skill in skills:
        category = get_skill_category(skill)
        if category not in categories:
            categories[category] = []
        categories[category].append(skill)
    return categories


# 测试
if __name__ == '__main__':
    test_text = """
    熟练使用Python和Java进行后端开发，熟悉Spring Boot、Django框架，
    掌握MySQL、Redis数据库，了解Elasticsearch，有分布式系统开发经验。
    熟练使用Git、Docker、K8s，了解AWS云服务。
    有机器学习项目经验，熟悉TensorFlow、PyTorch。
    使用Go + Gin进行微服务开发，有高并发经验。
    """
    skills = extract_skills(test_text)
    print("提取的技能：", skills)
    print("\n技能分类：")
    for cat, sk in categorize_skills(skills).items():
        print(f"  {cat}: {sk}")

    # 测试同义词
    test2 = "熟练使用spring、vue、react、k8s、docker、es、mq进行开发"
    skills2 = extract_skills(test2)
    print("\n同义词测试：", skills2)