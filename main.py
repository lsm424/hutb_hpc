'''
Author: wadesmli
Date: 2026-01-14 09:09:52
LastEditors: wadesmli
LastEditTime: 2026-06-01 09:12:06
FilePath: main.py
Description: HPC Dashboard - Dash app with FastAPI backend

架构说明:
- FastAPI 作为主服务器 (backend)，处理 HTTP 请求、认证
- Dash 应用通过 WSGIMiddleware 挂载到 FastAPI 上，作为子应用
- 所有请求先经过 FastAPI 中间件处理（包括认证），然后路由到 Dash
- 登录认证由 Dash 前端页面直接处理，通过 Cookie 与 FastAPI 中间件共享状态

Copyright (c) 2026 by wadesmli, All Rights Reserved.
'''
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from components import sidebar, header
from common import utils, cfg
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from service.auth import create_auth_middleware


# =============================================================================
# 1. 创建 FastAPI 后端应用 (主服务器)
# =============================================================================
app = FastAPI(
    title="HPC Dashboard",
    description="高性能计算集群监控平台 - FastAPI后端 + Dash前端",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加认证中间件 - 所有请求先经过这里进行认证检查
app.add_middleware(create_auth_middleware(app))


# =============================================================================
# 2. 创建 Dash 前端应用
# =============================================================================

dash_app = dash.Dash(
    __name__,
    use_pages=True,
    external_scripts=[
        'https://cdn.tailwindcss.com',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/js/all.min.js'
    ],
    suppress_callback_exceptions=True,
    title='HPC管理系统'
)
dash_app._favicon = "logo.jpg"

dash_app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])


@dash_app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/login':
        return dash.page_container
    else:
        return html.Div([
            sidebar.create_sidebar(),
            html.Div([
                header.create_header(),
                dash.page_container
            ], className="flex-1 ml-52 min-h-screen flex flex-col")
        ], className="bg-gray-950 text-gray-100 flex font-sans min-h-screen")




# =============================================================================
# 3. 将 Dash 应用挂载到 FastAPI (Dash 作为子应用)
# =============================================================================

# 使用 WSGIMiddleware 将 Dash 的 Flask 服务器挂载到 FastAPI
# 这样所有以 / 开头的请求都会路由到 Dash
app.mount("/", WSGIMiddleware(dash_app.server))


# =============================================================================
# 4. 初始化 Dash 回调
# =============================================================================

from pages import login, logout
login.init_callbacks_login(dash_app)
logout.init_callbacks_logout(dash_app)


# =============================================================================
# 5. 启动入口
# =============================================================================

if __name__ == '__main__':
    port = int(cfg.get('service', 'port', fallback=8050))
    utils.kill_prev_pid(cfg.get('service', 'pid_file'))
    utils.write_pid(cfg.get('service', 'pid_file'))
    utils.kill_process_on_port(port)

    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                   HPC Dashboard 启动                      ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  后端框架: FastAPI                                        ║
    ║  前端框架: Dash (Plotly)                                  ║
    ║  访问地址: http://127.0.0.1:{port}                         ║
    ║  默认账号: admin / admin123                               ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        app,  # FastAPI 应用作为主入口
        host="0.0.0.0",
        port=port
    )
