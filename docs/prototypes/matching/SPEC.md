# 人岗匹配系统 - UI 设计规范

## 1. 设计概述

**项目名称**: 人岗匹配系统 Web UI
**设计风格**: 现代简洁、专业优雅
**主题**: 浅色主题，配合蓝色渐变强调
**目标用户**: HR、招聘专员、求职者和企业

## 2. 配色方案

### 主色调
```css
--primary: #4F46E5;        /* 主色 - 靛蓝 */
--primary-light: #818CF8;  /* 主色浅 */
--primary-dark: #3730A3;   /* 主色深 */
--accent: #06B6D4;         /* 强调色 - 青色 */
```

### 背景色
```css
--bg-primary: #FAFBFC;     /* 主背景 - 极浅灰白 */
--bg-secondary: #F3F4F6;   /* 次背景 - 浅灰 */
--bg-card: #FFFFFF;        /* 卡片背景 */
--bg-dark: #1E293B;        /* 深色背景区域 */
```

### 文字色
```css
--text-primary: #1E293B;   /* 主文字 - 深灰黑 */
--text-secondary: #64748B; /* 次文字 - 中灰 */
--text-muted: #94A3B8;     /* 弱化文字 */
```

### 功能色
```css
--success: #10B981;        /* 成功 - 绿色 */
--warning: #F59E0B;        /* 警告 - 橙色 */
--danger: #EF4444;         /* 危险 - 红色 */
--info: #3B82F6;           /* 信息 - 蓝色 */
```

### 匹配度颜色
```css
--match-perfect: #10B981;  /* 90+分 - 完美匹配 */
--match-good: #3B82F6;     /* 70-89分 - 良好 */
--match-ok: #F59E0B;       /* 50-69分 - 一般 */
--match-poor: #EF4444;     /* <50分 - 不推荐 */
```

## 3. 字体

- **中文**: "Noto Sans SC", "PingFang SC", "Microsoft YaHei"
- **英文/数字**: "DM Sans", "Inter", system-ui
- **等宽**: "JetBrains Mono" (用于代码/技能标签)

```css
--font-display: 'DM Sans', sans-serif;
--font-body: 'Noto Sans SC', sans-serif;
--font-mono: 'JetBrains Mono', monospace;

--text-xs: 12px;
--text-sm: 14px;
--text-base: 16px;
--text-lg: 18px;
--text-xl: 20px;
--text-2xl: 24px;
--text-3xl: 30px;
```

## 4. 布局结构

### 整体布局
- 左侧: 简历管理 + 岗位管理 (宽度 320px)
- 中间: 主工作区 (flex: 1)
- 右侧: 详情面板 (400px, 可收起)

### 响应式断点
```css
--breakpoint-sm: 640px;
--breakpoint-md: 768px;
--breakpoint-lg: 1024px;
--breakpoint-xl: 1280px;
```

## 5. 组件设计

### 5.1 简历上传区域
- 虚线边框拖拽区域
- 支持点击上传和拖拽上传
- 上传进度动画
- 支持 PDF/DOCX/TXT 格式
- 预览缩略图

### 5.2 简历卡片
- 头像占位 (圆形)
- 姓名 + 当前位置
- 技能标签 (最多显示5个, hover显示全部)
- 匹配度进度条
- 操作按钮 (查看、匹配、删除)

### 5.3 岗位卡片
- 公司 Logo 占位
- 职位名称
- 薪资范围 (如果有)
- 技能要求标签
- 匹配简历数量徽章

### 5.4 匹配结果卡片
- 排名序号 (1, 2, 3...)
- 简历摘要 (姓名、现职)
- 大圆环匹配度得分 (带动画)
- 匹配技能列表
- 缺失技能列表
- 推荐理由文本

### 5.5 技能标签
- 圆角胶囊形状
- 分类颜色区分:
  - 编程语言: 蓝色
  - 框架: 紫色
  - 数据库: 绿色
  - 工具: 灰色
  - 软技能: 橙色

### 5.6 进度条/环
- 圆环形进度 (SVG)
- 线性进度条
- 颜色随分值变化
- 数字滚动动画

## 6. 交互效果

### 动画
- 页面加载: 卡片依次淡入 (stagger: 50ms)
- 悬停: 轻微上浮 + 阴影加深
- 点击: 涟漪效果
- 匹配度计算: 数字滚动 + 进度条填充
- 面板展开: 滑动 + 淡入

### 过渡
```css
--transition-fast: 150ms ease;
--transition-base: 200ms ease;
--transition-slow: 300ms ease;
--transition-spring: 500ms cubic-bezier(0.34, 1.56, 0.64, 1);
```

## 7. 页面区域

### 7.1 顶部导航
- Logo + 标题
- 快捷操作按钮
- 用户头像 (可选)

### 7.2 左侧边栏
- 简历管理模块
  - 简历列表 (可搜索/筛选)
  - 添加简历按钮
  - 批量操作
- 岗位管理模块
  - 岗位列表
  - 添加岗位按钮
  - 岗位筛选

### 7.3 主工作区
- 简历 vs 岗位 选择器
- 匹配结果列表 (可排序)
- 批量匹配操作

### 7.4 右侧详情面板
- 简历完整信息
- 岗位完整信息
- 匹配分析详情
- 建议生成

## 8. 视觉效果细节

### 阴影
```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);
--shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1);
--shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.1);
```

### 圆角
```css
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-xl: 16px;
--radius-full: 9999px;
```

### 渐变
```css
--gradient-primary: linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%);
--gradient-card: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%);
--gradient-hero: linear-gradient(135deg, #1E293B 0%, #334155 50%, #475569 100%);
```

## 9. 状态设计

### 空状态
- 插画图标
- 引导文案
- 快捷操作按钮

### 加载状态
- 骨架屏
- 脉冲动画

### 错误状态
- 图标 + 错误信息
- 重试按钮

### 成功状态
- 绿色对勾动画
- 成功消息Toast

## 10. 推荐等级视觉

| 得分 | 等级 | 圆环颜色 | 徽章 |
|------|------|----------|------|
| ≥90 | 强烈推荐 | 绿色 #10B981 | 绿色 "S" 级 |
| 70-89 | 建议面试 | 蓝色 #3B82F6 | 蓝色 "A" 级 |
| 50-69 | 可考虑 | 橙色 #F59E0B | 橙色 "B" 级 |
| <50 | 不推荐 | 红色 #EF4444 | 红色 "C" 级 |