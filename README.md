# HPC 资源监控平台 (Dash 版)

基于 [Plotly Dash](https://dash.plotly.com/) 的高性能计算 (HPC) 资源监控 Web 应用，对接华为 HPC 后端 API，支持分区、作业、节点、用户等资源的实时监控与历史数据分析。

## 功能模块

| 模块 | 说明 |
|------|------|
| **总览 (Dashboard)** | 分区资源使用概览、实时利用率趋势、用户活跃度统计 |
| **作业管理 (Jobs)** | 作业列表、多维度筛选（状态、分区、用户）、作业操作 |
| **节点管理 (Nodes)** | 节点状态监控网格、CPU/内存/GPU 历史曲线、GPU 状态列表 |
| **日报 (Daily Report)** | 每日运行报告，含资源统计、用户统计、异常节点与排队作业 |
| **用户管理 (Users)** | 用户列表、状态筛选、注册审核 |

## 技术栈

| 类别 | 技术 |
|------|------|
| **Web 框架** | Dash 3.x、Dash Bootstrap Components、Dash AG Grid |
| **可视化** | Plotly |
| **数据库** | MySQL + SQLAlchemy + PyMySQL |
| **后端 API** | HPC 平台接口 (hpc.hutb.edu.cn) |
| **样式** | Tailwind CSS (CDN)、自定义暗色主题 |
| **调度** | APScheduler (定时任务) |

## 数据来源

- **实时数据**：HPC 平台 REST API（登录态、分区、作业、节点、用户）
- **历史数据**：MySQL 存储（节点 CPU/内存/GPU 历史、日报）

## 快速开始

### 1. 环境准备

- Python 3.8+
- MySQL 5.7+ / 8.0+

```bash
# 创建并激活虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

复制或编辑 `config.ini`：

```ini
[account]
user=your_hpc_username
passwd=your_encrypted_password
signature=your_signature

[mysql]
dsn=mysql+pymysql://user:password@host:3306/hpc?charset=utf8mb4

[service]
port=8050
pid_file=./assets/hpc_dash.pid
```

### 4. 初始化数据库

执行 `docs/db.sql` 创建表：

```bash
mysql -u user -p hpc < docs/db.sql
```

### 5. 启动应用

```bash
python main.py
```

访问：[http://127.0.0.1:8050/](http://127.0.0.1:8050/)

## 项目结构

```
├── main.py              # 应用入口
├── config.ini           # 配置（账号、MySQL、服务端口）
├── requirements.txt
├── assets/              # 静态资源、Token、Logo
├── common/              # 公共模块
│   ├── ecript.py        # 加密工具
│   └── utils.py         # 工具函数
├── components/          # 布局组件
│   ├── header.py        # 顶部栏
│   └── sidebar.py       # 侧边栏
├── infra/               # 外部依赖
│   └── hpc_api.py       # HPC 平台 API 封装
├── models/              # 数据模型
│   ├── base.py          # SQLAlchemy Base
│   └── model.py         # 表定义
├── pages/               # Dash 页面
│   ├── dashboard.py     # 总览
│   ├── jobs.py          # 作业管理
│   ├── nodes.py         # 节点管理
│   ├── daily.py         # 日报
│   └── users.py         # 用户管理
├── service/             # 业务逻辑
│   ├── hpc_manager.py   # 分区/作业/节点/日报服务
│   └── user.py          # 用户服务
└── docs/                # 文档与脚本
    ├── db.sql           # 建表脚本
    ├── PRD.md
    ├── Metrics_Framework.md
    └── design/          # 设计稿
```

## 数据库表

| 表名 | 说明 |
|------|------|
| `t_daily_report_info` | 日报汇总 |
| `t_node_cpu_history_info` | 节点 CPU 历史 |
| `t_node_mem_history_info` | 节点内存历史 |
| `t_node_gpu_history_info` | 节点 GPU 历史 |
| `t_hpc_user_info` | HPC 用户信息 |

## 注意事项

- **登录**：HPC 平台使用加密登录，`passwd` 和 `signature` 需与平台约定格式；登录成功后会写入 `assets/token.txt` 复用 Token。
- **UI**：使用 Tailwind + 自定义 CSS 实现暗色主题。
- **端口占用**：启动时会检测并释放配置端口，避免重复启动冲突。
