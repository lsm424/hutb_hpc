# HPC 资源监控平台 (Dash版)

这是一个基于 [Plotly Dash](https://dash.plotly.com/) 框架开发的高性能计算 (HPC) 资源监控 Web 应用。
本项目高度还原了设计稿的 UI 风格（暗色主题），并实现了核心的业务交互流程。

## 功能模块

1.  **总览 (Dashboard)**: 分区资源使用概览、实时利用率趋势、用户活跃度统计。
2.  **作业管理 (Jobs)**: 作业列表查询、多维度筛选（状态、分区、用户）、作业操作。
3.  **节点管理 (Nodes)**: 节点状态监控网格、详细信息面板（CPU/内存/GPU 实时曲线）、GPU 状态列表。
4.  **日报 (Daily Report)**: 每日运行报告，包含资源统计、用户统计及异常情况汇总。

## 技术栈

*   **Python**: 3.8+
*   **Dash**: 2.15.0+ (核心 Web 框架)
*   **Dash Bootstrap Components**: 布局与基础组件
*   **Dash AG Grid**: 高级数据表格
*   **Plotly**: 数据可视化图表
*   **Tailwind CSS**: 实用工具优先的 CSS 框架 (通过 CDN 引入)

## 本地开发环境设置

### 1. 环境准备

确保已安装 Python 3.8 或更高版本。建议使用虚拟环境进行开发。

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scriptsctivate

# 激活虚拟环境 (Linux/macOS)
source venv/bin/activate
```

### 2. 安装依赖

项目根目录下提供了 `requirements.txt` 文件。

```bash
pip install -r requirements.txt
```

### 3. 运行应用

```bash
python app.py
```

启动后，在浏览器中访问：[http://127.0.0.1:8050/](http://127.0.0.1:8050/)

## 项目结构

```
├── main.py                 # 应用入口文件
├── requirements.txt       # 项目依赖
├── pages/                 # 页面模块 (Dash Pages)
│   ├── dashboard.py       # 总览页面
│   ├── jobs.py            # 作业管理页面
│   ├── nodes.py           # 节点管理页面
│   └── daily.py           # 日报页面
├── components/            # 公共组件
│   ├── sidebar.py         # 侧边栏导航
│   └── header.py          # 顶部通栏
├── service/               # 业务逻辑与数据服务
│   ├── __init__.py
│   └── api.py             # 模拟数据接口
└── assets/                # 静态资源
    └── custom.css         # 自定义样式覆盖
```

## 注意事项

*   **UI 风格**: 本项目使用 Tailwind CSS 进行样式定制，并通过 `assets/custom.css` 覆盖部分 Dash 组件默认样式以匹配暗色主题设计。
*   **数据来源**: 目前阶段使用 `service/api.py` 或页面内部的模拟数据生成器提供展示数据。
