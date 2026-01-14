import dash
from dash import html, dcc, Input, Output, State, callback, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import random
from datetime import datetime
from service.hpc_manager import hpc_manager
from common.utils import search_params

dash.register_page(__name__, path='/', name='总览')

# Simulated Data
def generate_partitions():
    partitions = [
        {'id': 'gpu-a', 'name': 'gpu-a', 'totalCpu': 640, 'freeCpu': 128, 'totalMem': 2048, 'freeMem': 600, 'totalGpu': 64, 'freeGpu': 12, 'jobCount': 48, 'nodeCount': 32},
        {'id': 'cpu-b', 'name': 'cpu-b', 'totalCpu': 1024, 'freeCpu': 300, 'totalMem': 4096, 'freeMem': 1800, 'totalGpu': 0, 'freeGpu': 0, 'jobCount': 21, 'nodeCount': 44},
        {'id': 'mem-c', 'name': 'mem-c', 'totalCpu': 256, 'freeCpu': 90, 'totalMem': 8192, 'freeMem': 5000, 'totalGpu': 8, 'freeGpu': 4, 'jobCount': 12, 'nodeCount': 18},
    ]
    # Add some random variation
    for p in partitions:
        p['freeCpu'] = max(0, min(p['totalCpu'], p['freeCpu'] + random.randint(-20, 20)))
        p['freeMem'] = max(0, min(p['totalMem'], p['freeMem'] + random.randint(-200, 200)))
        if p['totalGpu'] > 0:
            p['freeGpu'] = max(0, min(p['totalGpu'], p['freeGpu'] + random.randint(-2, 2)))
        p['jobCount'] = max(0, p['jobCount'] + random.randint(-3, 3))
        p['updatedAt'] = datetime.now().strftime("%H:%M:%S")
    return partitions

def calculate_util_rate(p):
    cpu_util = 1 - (p['freeCpu'] / p['totalCpu'])
    mem_util = 1 - (p['freeMem'] / p['totalMem'])
    gpu_util = (1 - (p['freeGpu'] / p['totalGpu'])) if p['totalGpu'] > 0 else 0
    return (cpu_util + mem_util + gpu_util) / 3

layout = html.Div([
    # Top Banner
    html.Section([
        html.Img(
            src="https://images.unsplash.com/photo-1544197150-b99a580bb7a8?q=80&w=1400&auto=format&fit=crop",
            alt="datacenter",
            className="w-full h-48 object-cover opacity-40"
        ),
        html.Div([
            html.Div([
                html.H1("分区资源总览", className="text-2xl font-semibold"),
                html.P("近实时刷新，快速洞察CPU/内存/GPU利用率。", className="text-gray-300")
            ], className="space-y-2")
        ], className="absolute inset-0 flex items-center px-6 bg-gradient-to-r from-gray-900/80 to-transparent"),
                    
        html.Div([
            html.Div([
                html.Div([
                    html.Div(hpc_manager.total_user, id='total-users', className="text-2xl font-semibold"),
                    html.Div("总用户数", className="text-xs text-gray-400")
                ], className="text-right"),
                html.Div([
                    html.Div(hpc_manager.user_active, id='online-users', className="text-2xl font-semibold text-emerald-400"),
                    html.Div(["在线用户数"], className="text-xs text-gray-400")
                ], className="text-right"),
            ], className="flex flex-row gap-8"),
        ], className="flex flex-col gap-2 absolute right-8 top-1/2 -translate-y-1/2"),
    # className 参数设置了 Tailwind CSS 的样式类：
    # - relative: 设为相对定位，为后代的绝对定位元素布局提供参考。
    # - rounded-xl: 大圆角边框。
    # - overflow-hidden: 超出容器部分隐藏，防止溢出（如图片圆角）。
    # - mb-6: 下外边距为 1.5rem（24px）。
    ], className="relative rounded-xl overflow-hidden "),

    # Partitions Grid Section
    html.Section([
        html.Div([
            html.Div([
                html.Label("分区", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='partition-filter',
                    options=[ {'label': 'all', 'value': 'all'}] + 
                        [{'label': p, 'value': p} for p in hpc_manager.partitions],
                    value='all',
                    clearable=False,
                    className="mt-1 w-32"
                )
            ]),
            html.Div([
                html.Label("排序", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='sort-key',
                    options=[
                        {'label': '剩余CPU', 'value': 'free_cpu'},
                        {'label': '剩余内存', 'value': 'free_mem'},
                        {'label': '剩余GPU卡数', 'value': 'free_gpu'},
                        {'label': '作业数', 'value': 'jobs'},
                        {'label': '节点数', 'value': 'nodes'}
                    ],
                    value='free_cpu',
                    clearable=False,
                    className="mt-1 w-32"
                )
            ]),
            html.Div(className="flex-1"),
            html.Div([
                html.Label("刷新间隔", className="text-xs text-gray-400 mr-2"),
                dcc.Slider(
                    id='refresh-interval-slider',
                    min=10,
                    max=60,
                    step=10,
                    value=10,
                    marks=None,
                    tooltip={"placement": "bottom", "always_visible": True},
                    className="w-40"
                ),
            ], className="flex items-center gap-2")
        ], className="flex flex-wrap gap-3 items-end mb-6"),

        html.Div(id='partitions-grid', className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4")
    ], className="bg-gray-900 rounded-xl p-6 border border-gray-800"),

    dcc.Interval(id='interval-component', interval=10000, n_intervals=0)
])

# Callbacks
# @callback(
#     [Output('online-users', 'children')],
#     [Input('timewin-dropdown', 'value')]
# )
# def update_user_stats(window):
#     return hpc_manager.user_active

@callback(
    Output('interval-component', 'interval'), 
    Input('refresh-interval-slider', 'value')
)
def update_interval(value):
    return value * 1000

@callback(
    Output('partitions-grid', 'children'),
    Output('online-users', 'children'),
    Output('total-users', 'children'),
    Output('partition-filter', 'value'),
    [Input('interval-component', 'n_intervals'),
     Input('partition-filter', 'value'),
     Input('sort-key', 'value'),     
     Input('url', 'search')]
)
def update_partitions(n, partition_filter, sort_val, search):
    partions = list(hpc_manager.partitions.values())

    params = search_params(search)
    if params.get('partition', '') in hpc_manager.partitions:
        partition_filter = params['partition']

    if partition_filter != 'all':
        partions = [p for p in partions if p.partition_name == partition_filter]

    if sort_val == 'free_cpu':
        partions.sort(key=lambda p: p.idled_cpu, reverse=True)
    elif sort_val == 'free_mem':
        partions.sort(key=lambda p: p.idled_mem, reverse=True)
    elif sort_val == 'free_gpu':
        partions.sort(key=lambda p: p.idled_card, reverse=True)
    elif sort_val == 'jobs':
        partions.sort(key=lambda p: len(p.tasks), reverse=True)
    elif sort_val == 'nodes':
        partions.sort(key=lambda p: len(p.nodes), reverse=True)

    cards = []
    for p in partions:
        status_color = "text-red-400" if p.is_stressed else "text-emerald-400"
        status_text = "紧张" if p.is_stressed else "正常"
        
        gpu_type = f'({p.card_type})' if p.card_type else ''
        card = html.Div([
            html.Div([
                html.H3(f"{p.partition_name}{gpu_type} 分区", className="font-medium"),
                html.Span([
                    html.I(className="fa-solid fa-signal mr-1"),
                    status_text
                ], className=f"text-xs {status_color}")
            ], className="flex items-center justify-between"),
            
            html.Div([
                # CPU
                html.Div([
                    html.I(className="fa-solid fa-microchip text-purple-400"),
                    html.Span(f"CPU：总 {p.total_cpu} / 剩余 {p.idled_cpu}"),
                    html.Div([
                        html.Div(style={'width': f'{p.cpu_util_pct}%'}, className="h-2 bg-purple-500")
                    ], className="flex-1 h-2 bg-gray-800 rounded overflow-hidden")
                ], className="flex items-center gap-2 text-sm"),
                
                # Mem
                html.Div([
                    html.I(className="fa-solid fa-memory text-blue-400"),
                    html.Span(f"内存：总 {p.total_mem_str} / 剩余 {p.idled_mem_str}"),
                    html.Div([
                        html.Div(style={'width': f'{p.mem_util_pct}%'}, className="h-2 bg-blue-500")
                    ], className="flex-1 h-2 bg-gray-800 rounded overflow-hidden")
                ], className="flex items-center gap-2 text-sm"),
                
                # GPU
                html.Div([
                    html.I(className="fa-solid fa-square text-emerald-400"),
                    html.Span(f"GPU：总 {p.total_card} / 剩余 {p.idled_card}"),
                    html.Div([
                        html.Div(style={'width': f'{p.gpu_util_pct}%'}, className="h-2 bg-emerald-500")
                    ], className="flex-1 h-2 bg-gray-800 rounded overflow-hidden")
                ], className="flex items-center gap-2 text-sm"),
            ], className="mt-4 space-y-3"),
            
            html.Div(f"作业数：{len(p.tasks)} | 节点数：{len(p.nodes)} | 更新时间：{p.updated_at}", className="mt-4 text-xs text-gray-400"),
            
            html.Div([
                dcc.Link("查看作业", href=f"/jobs?partition={p.partition_name}", className="flex-1 text-center text-sm px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded transition-colors border border-gray-700 text-gray-300"),
                dcc.Link("查看节点", href=f"/nodes?partition={p.partition_name}", className="flex-1 text-center text-sm px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded transition-colors border border-gray-700 text-gray-300")
            ], className="mt-4 flex gap-2")
        ], className="rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-700 transition p-4")
        cards.append(card)
        
    return cards, hpc_manager.user_active, hpc_manager.total_user, partition_filter
