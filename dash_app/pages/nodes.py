import dash
from dash import html, dcc, Input, Output, State, callback, ALL, MATCH, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import random
from datetime import datetime, timedelta

dash.register_page(__name__, path='/nodes', name='节点管理')

# Simulated Data
def gen_nodes():
    return [
        { 'id':'node-21', 'part':'gpu-a', 'health':'健康', 'cpu':{'total':64, 'free':16}, 'mem':{'total':256, 'free':64}, 'gpu':{'total':8, 'free':2}, 'jobs':['J-102938', 'J-102944'] },
        { 'id':'node-11', 'part':'cpu-b', 'health':'健康', 'cpu':{'total':32, 'free':20}, 'mem':{'total':256, 'free':120}, 'gpu':{'total':0, 'free':0}, 'jobs':['J-102941'] },
        { 'id':'node-07', 'part':'gpu-a', 'health':'告警', 'cpu':{'total':64, 'free':8}, 'mem':{'total':256, 'free':40}, 'gpu':{'total':4, 'free':0}, 'jobs':['J-102942'] },
        { 'id':'node-33', 'part':'mem-c', 'health':'离线', 'cpu':{'total':16, 'free':0}, 'mem':{'total':1024, 'free':0}, 'gpu':{'total':2, 'free':0}, 'jobs':[] },
        { 'id':'node-45', 'part':'gpu-b', 'health':'健康', 'cpu':{'total':96, 'free':12}, 'mem':{'total':512, 'free':128}, 'gpu':{'total':8, 'free':1}, 'jobs':[] },
        { 'id':'node-46', 'part':'gpu-b', 'health':'健康', 'cpu':{'total':96, 'free':96}, 'mem':{'total':512, 'free':512}, 'gpu':{'total':8, 'free':8}, 'jobs':[] },
    ]

ALL_NODES = gen_nodes()

def create_chart(title, color, period='1w'):
    count = 7 if period == '1w' else 30 if period == '1m' else 12 if period == '3m' else 24
    
    end_date = datetime.now()
    if period == '1w':
        x = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]
    elif period == '1m':
        x = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]
    elif period == '3m':
        x = [(end_date - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]
    else:
        x = [(end_date - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]

    y = [random.randint(20, 80) for _ in range(count)]
    
    fig = go.Figure(data=[go.Scatter(
        x=x, y=y,
        mode='lines',
        fill='tozeroy',
        line=dict(color=color, width=3, shape='spline'),
        fillcolor=color.replace('rgb', 'rgba').replace(')', ', 0.1)'),
        hovertemplate='%{y}%<extra></extra>'
    )])
    
    fill_color = 'rgba(99, 102, 241, 0.1)'
    if color == '#a855f7': fill_color = 'rgba(168, 85, 247, 0.1)'
    if color == '#3b82f6': fill_color = 'rgba(59, 130, 246, 0.1)'
    fig.update_traces(fillcolor=fill_color)
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            showgrid=False,
            showticklabels=True,
            tickfont=dict(color='#9ca3af', size=10),
            tickmode='auto',
            nticks=5,
            showspikes=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#374151',
            showticklabels=True,
            tickfont=dict(color='#9ca3af'),
            range=[0,100]
        ),
        height=250,
        showlegend=False,
        hovermode='closest',
        hoverlabel=dict(bgcolor='#0f172a', bordercolor='#334155', font=dict(color='#ffffff'))
    )
    return fig

layout = html.Div([
    dcc.Location(id='nodes-url', refresh=False),
    dcc.Store(id='selected-node-store', data=None),
    dcc.Store(id='chart-period-store', data='1w'),
    
    html.Div([
        html.Div(id='nodes-badges', className="flex items-center gap-2 mb-4"),
        html.Div([
            html.Div([
                html.Label("分区", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='node-part-filter',
                    options=[
                        {'label': 'all', 'value': 'all'},
                        {'label': 'gpu-a', 'value': 'gpu-a'},
                        {'label': 'cpu-b', 'value': 'cpu-b'},
                        {'label': 'mem-c', 'value': 'mem-c'}
                    ],
                    value='all',
                    clearable=False,
                    className="mt-1 w-32"
                )
            ]),
            html.Div([
                html.Label("健康状态", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='node-health-filter',
                    options=[
                        {'label': '全部', 'value': 'all'},
                        {'label': '健康', 'value': '健康'},
                        {'label': '告警', 'value': '告警'},
                        {'label': '离线', 'value': '离线'}
                    ],
                    value='all',
                    clearable=False,
                    className="mt-1 w-32"
                )
            ]),
            html.Div(className="flex-1"),
            html.Button([html.I(className="fa-solid fa-filter mr-1"), "筛选"], id='btn-node-filter', className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-300"),
        ], className="flex flex-wrap gap-3 items-end mb-6"),
        
        html.Div(id='nodes-grid', className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 mb-8"),
        
        html.Div(id='node-detail-panel', className="hidden bg-gray-900 border border-gray-800 rounded-xl p-6 animate-fade-in-up", children=[
            html.Div([
                html.H2([
                    html.I(className="fa-solid fa-chart-line text-indigo-500"),
                    html.Span(id='detail-node-id-display', className="ml-2"),
                    html.Span("性能监控", className="text-sm font-normal text-gray-500 ml-2")
                ], className="text-lg font-bold flex items-center"),
                
                html.Div([
                    html.Button("近一周", id={'type': 'period-btn', 'value': '1w'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter active"),
                    html.Button("近一月", id={'type': 'period-btn', 'value': '1m'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter"),
                    html.Button("近三月", id={'type': 'period-btn', 'value': '3m'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter"),
                    html.Button("近六月", id={'type': 'period-btn', 'value': '6m'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter"),
                ], className="flex bg-gray-800 rounded-lg p-1")
            ], className="flex items-center justify-between mb-6"),
            
            html.Div([
                html.Div([
                    html.H3("显卡使用率趋势", className="text-sm font-medium text-gray-400 mb-4"),
                    html.Div(dcc.Graph(id='gpu-chart', config={'displayModeBar': False}), className="h-64 w-full border border-gray-800 rounded-lg bg-gray-800/20 p-2")
                ]),
                html.Div([
                    html.H3("CPU 使用率趋势", className="text-sm font-medium text-gray-400 mb-4"),
                    html.Div(dcc.Graph(id='cpu-chart', config={'displayModeBar': False}), className="h-64 w-full border border-gray-800 rounded-lg bg-gray-800/20 p-2")
                ]),
                html.Div([
                    html.H3("内存 使用率趋势", className="text-sm font-medium text-gray-400 mb-4"),
                    html.Div(dcc.Graph(id='mem-chart', config={'displayModeBar': False}), className="h-64 w-full border border-gray-800 rounded-lg bg-gray-800/20 p-2")
                ]),
            ], className="space-y-6 mb-8"),
            
            html.Div([
                html.H3("显卡状态列表", className="text-sm font-medium text-gray-400 mb-4"),
                html.Div([
                    html.Table([
                        html.Thead(
                            html.Tr([
                                html.Th("ID", className="px-3 py-2 text-left text-gray-400"),
                                html.Th("型号", className="px-3 py-2 text-left text-gray-400"),
                                html.Th("显存", className="px-3 py-2 text-left text-gray-400"),
                                html.Th("使用率", className="px-3 py-2 text-left text-gray-400"),
                                html.Th("温度", className="px-3 py-2 text-left text-gray-400"),
                            ]),
                            className="bg-gray-800"
                        ),
                        html.Tbody(id='gpu-list-body', className="divide-y divide-gray-800")
                    ], className="w-full text-xs")
                ], className="overflow-hidden border border-gray-800 rounded-lg")
            ])
        ])
    ], className="p-6 pb-96")
])

@callback(
    [Output('nodes-grid', 'children'),
     Output('nodes-badges', 'children')],
    [Input('btn-node-filter', 'n_clicks'),
     Input('nodes-url', 'search'),
     Input('selected-node-store', 'data')],
    [State('node-part-filter', 'value'),
     State('node-health-filter', 'value')]
)
def update_node_grid(n, search, selected_id, part_filter, health_filter):
    params = {}
    if search:
        search = search.lstrip('?')
        for pair in search.split('&'):
            if '=' in pair:
                key, val = pair.split('=')
                params[key] = val
    
    url_part = params.get('part')
    url_job = params.get('job')
    
    badges = []
    if url_part:
        badges.append(html.Span(f"分区: {url_part}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))
    if url_job:
        badges.append(html.Span(f"作业: {url_job}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))
        
    filtered_nodes = ALL_NODES
    target_part = url_part if url_part else (part_filter if part_filter != 'all' else None)
    
    if target_part:
        filtered_nodes = [n for n in filtered_nodes if n['part'] == target_part]
    if health_filter != 'all':
        filtered_nodes = [n for n in filtered_nodes if n['health'] == health_filter]
    if url_job:
        filtered_nodes = [n for n in filtered_nodes if url_job in n['jobs']]
        
    cards = []
    if not filtered_nodes:
        return html.Div("无匹配节点数据", className="col-span-full text-center py-12 text-gray-500"), badges
        
    for n in filtered_nodes:
        is_selected = (selected_id == n['id'])
        selected_class = "selected bg-gray-800/50 ring-2 ring-indigo-500/50" if is_selected else ""
        
        cpu_pct = round((1 - n['cpu']['free'] / n['cpu']['total']) * 100)
        mem_pct = round((1 - n['mem']['free'] / n['mem']['total']) * 100)
        gpu_pct = round((1 - n['gpu']['free'] / n['gpu']['total']) * 100) if n['gpu']['total'] > 0 else 0
        
        health_color = {
            '健康': 'border-emerald-500/20 text-emerald-400 bg-emerald-500/10',
            '告警': 'border-yellow-500/20 text-yellow-400 bg-yellow-500/10',
            '离线': 'border-gray-700 text-gray-400 bg-gray-800'
        }.get(n['health'], 'border-gray-700 text-gray-400 bg-gray-800')
        
        card = html.Div([
            html.Div([
                html.Div([
                    html.Div(html.I(className="fa-solid fa-server"), className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center text-gray-400 group-hover:bg-indigo-500/10 group-hover:text-indigo-400 transition-colors"),
                    html.Div([
                        html.H3(n['id'], className="font-medium"),
                        html.Div(n['part'], className="text-xs text-gray-500")
                    ])
                ], className="flex items-center gap-3"),
                html.Span(n['health'], className=f"text-xs px-2 py-0.5 rounded border {health_color}")
            ], className="flex items-center justify-between mb-4"),
            
            html.Div([
                html.Div([
                    html.I(className="fa-solid fa-microchip text-purple-400 w-4"),
                    html.Span("CPU", className="text-gray-400"),
                    html.Div(html.Div(style={'width': f'{cpu_pct}%'}, className="h-full bg-purple-500"), className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden ml-2")
                ], className="flex items-center gap-2"),
                html.Div([
                    html.I(className="fa-solid fa-memory text-blue-400 w-4"),
                    html.Span("MEM", className="text-gray-400"),
                    html.Div(html.Div(style={'width': f'{mem_pct}%'}, className="h-full bg-blue-500"), className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden ml-2")
                ], className="flex items-center gap-2"),
                html.Div([
                    html.I(className="fa-solid fa-square text-emerald-400 w-4"),
                    html.Span("GPU", className="text-gray-400"),
                    html.Div(html.Div(style={'width': f'{gpu_pct}%'}, className="h-full bg-emerald-500"), className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden ml-2")
                ], className="flex items-center gap-2"),
            ], className="space-y-3 text-sm mb-5"),
            
            html.Div([
                html.Span(["运行作业: ", html.Span(str(len(n['jobs'])), className="text-white font-medium")])
            ], className="flex items-center justify-between pt-4 border-t border-gray-800 text-xs text-gray-400 mb-4"),
            
            html.Div([
                dcc.Link("查看作业", href=f"/jobs?node={n['id']}", className="flex-1 text-center text-xs px-3 py-2 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-gray-400 transition-colors"),
                dcc.Link("查看分区", href=f"/?part={n['part']}", className="flex-1 text-center text-xs px-3 py-2 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-gray-400 transition-colors")
            ], className="flex gap-2")
        ], 
        id={'type': 'node-card', 'index': n['id']},
        n_clicks=0,
        className=f"node-card cursor-pointer rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-700 transition p-5 group {selected_class}")
        cards.append(card)
        
    return cards, badges

@callback(
    Output('selected-node-store', 'data'),
    Input({'type': 'node-card', 'index': ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_card_click(n_clicks):
    if not any(n_clicks):
        return dash.no_update
    
    ctx_triggered = ctx.triggered_id
    if not ctx_triggered:
        return dash.no_update
        
    return ctx_triggered['index']

@callback(
    Output('chart-period-store', 'data'),
    Input({'type': 'period-btn', 'value': ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_period_click(n_clicks):
    if not any(n for n in n_clicks if n):
        return dash.no_update
    
    ctx_triggered = ctx.triggered_id
    return ctx_triggered['value']

@callback(
    [Output({'type': 'period-btn', 'value': ALL}, 'className'),
     Output('node-detail-panel', 'className'),
     Output('detail-node-id-display', 'children'),
     Output('gpu-list-body', 'children'),
     Output('gpu-chart', 'figure'),
     Output('cpu-chart', 'figure'),
     Output('mem-chart', 'figure')],
    [Input('selected-node-store', 'data'),
     Input('chart-period-store', 'data')]
)
def update_detail_panel(selected_id, period):
    periods = ['1w', '1m', '3m', '6m']
    btn_classes = []
    for p in periods:
        base = "px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter"
        if p == period:
            btn_classes.append(f"{base} bg-gray-700 text-white")
        else:
            btn_classes.append(base)
            
    if not selected_id:
        return btn_classes, "hidden", "", [], {}, {}, {}
        
    node = next((n for n in ALL_NODES if n['id'] == selected_id), None)
    if not node:
        return btn_classes, "hidden", "", [], {}, {}, {}
        
    gpu_rows = []
    if node['gpu']['total'] == 0:
        gpu_rows.append(html.Tr(html.Td("无GPU资源", colSpan=5, className="px-3 py-4 text-center text-gray-500")))
    else:
        for i in range(node['gpu']['total']):
            usage = random.randint(10, 99)
            temp = random.randint(40, 85)
            temp_color = "text-red-400" if temp > 75 else "text-yellow-400" if temp > 60 else "text-emerald-400"
            
            row = html.Tr([
                html.Td(f"GPU-{i}", className="px-3 py-2 text-gray-300"),
                html.Td("NVIDIA A100", className="px-3 py-2 text-gray-400"),
                html.Td("72G / 80G", className="px-3 py-2 text-gray-400"),
                html.Td([
                    html.Div(html.Div(style={'width': f'{usage}%'}, className="h-full bg-emerald-500"), className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden inline-block align-middle mr-2"),
                    f"{usage}%"
                ], className="px-3 py-2 text-gray-400"),
                html.Td(f"{temp}°C", className=f"px-3 py-2 {temp_color}")
            ], className="hover:bg-gray-800/50")
            gpu_rows.append(row)
            
    gpu_fig = create_chart("GPU", "#6366f1", period)
    cpu_fig = create_chart("CPU", "#a855f7", period)
    mem_fig = create_chart("MEM", "#3b82f6", period)
    
    return btn_classes, "bg-gray-900 border border-gray-800 rounded-xl p-6 animate-fade-in-up", f"{selected_id} 详情", gpu_rows, gpu_fig, cpu_fig, mem_fig
