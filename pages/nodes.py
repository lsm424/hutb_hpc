import dash
from dash import html, dcc, Input, Output, State, callback, ALL, MATCH, ctx, ClientsideFunction, clientside_callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import random
from datetime import datetime, timedelta
from service.hpc_manager import Node, hpc_manager
from common import utils, logger
import time
import concurrent.futures

dash.register_page(__name__, path='/nodes', name='节点管理')


# 回到顶部按钮样式
back_to_top_style_hidden = {
    'position': 'fixed',
    'bottom': '30px',
    'right': '30px',
    'zIndex': 1000,
    'width': '50px',
    'height': '50px',
    'borderRadius': '50%',
    'backgroundColor': '#007bff',
    'color': 'white',
    'border': 'none',
    'fontSize': '24px',
    'cursor': 'pointer',
    'boxShadow': '0 2px 10px rgba(0,0,0,0.2)',
    'opacity': 0,  # 初始透明
    'visibility': 'hidden',  # 初始隐藏
    'transition': 'all 0.3s ease'
}

period2days = {
    '1w': 7,
    '1m': 30,
    '3m': 90,
    '6m': 180,
}

# 降采样配置：当数据量超过此值时进行降采样
MAX_CHART_POINTS = 2000  # 最大图表点数，可根据性能需求调整（默认2000点）

def downsample_history(history, max_points=MAX_CHART_POINTS):
    """
    对历史数据进行降采样，减少数据量以提高图表渲染性能
    
    使用均匀采样方法，保留首尾两点，中间点均匀分布
    
    Args:
        history: 历史数据列表，每条记录包含 timestamp 和对应的 usage 字段
        max_points: 最大保留的数据点数，默认使用 MAX_CHART_POINTS
        
    Returns:
        降采样后的历史数据列表
    """
    if not history or len(history) <= max_points:
        return history
    
    # 数据量超过阈值，进行降采样
    original_count = len(history)
    
    # 如果需要降采样，使用均匀间隔采样
    # 计算采样步长，确保最终点数不超过 max_points
    step = (original_count - 1) / (max_points - 1)
    
    sampled = []
    for i in range(max_points):
        index = int(i * step)
        # 确保索引不超出范围
        if index >= original_count:
            index = original_count - 1
        sampled.append(history[index])
        
        # 如果已经到达最后一个点，提前结束
        if index >= original_count - 1:
            break
    
    # 确保最后一个点被包含（处理浮点数误差）
    if sampled[-1] != history[-1]:
        sampled[-1] = history[-1]
    
    return sampled

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

def create_chart(title, color, history):
    # count = 7 if period == '1w' else 30 if period == '1m' else 12 if period == '3m' else 24
    # end_date = datetime.now()
    # if period == '1w':
    #     x = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]
    # elif period == '1m':
    #     x = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]
    # elif period == '3m':
    #     x = [(end_date - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]
    # else:
    #     x = [(end_date - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(count)][::-1]

    x = [datetime.fromtimestamp(x['timestamp']) for x in history]
    y = [x.get('cpu_usage', None) or x.get('mem_usage', None) or x.get('gpu_usage', None) for x in history]
    
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
    dcc.Store(id='scroll-trigger-store', data=None),
    
    html.Div([
        html.Div(id='nodes-badges', className="flex items-center gap-2 mb-4"),

        html.Div([
            html.Div([
                html.Label("分区", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='node-part-filter',
                    options=[
                        {'label': 'all', 'value': 'all'},
                        # {'label': 'gpu-a', 'value': 'gpu-a'},
                        # {'label': 'cpu-b', 'value': 'cpu-b'},
                        # {'label': 'mem-c', 'value': 'mem-c'}
                    ] + [{'label': p, 'value': p} for p in hpc_manager.partitions.keys()],
                    value='all',
                    clearable=False,
                    className="mt-1 w-48"
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
                    className="mt-1 w-48"
                )
            ]),
            html.Div(className="flex-1"),
            # html.Button([html.I(className="fa-solid fa-filter mr-1"), "筛选"], id='btn-node-filter', className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-300"),
        ], className="flex flex-wrap gap-3 items-end mb-6"),
        
        html.Div(id='nodes-grid', className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8"),
        
        # 锚点 div，用于跳转到详情面板（始终可见，即使详情面板是 hidden）
        html.Div(id='node-detail-panel-anchor', style={'scroll-margin-top': '20px'}),
        
        html.Div(id='node-detail-panel', className="hidden bg-gray-900 border border-gray-800 rounded-xl p-6 animate-fade-in-up", children=[
            html.Div([
                html.H2([
                    html.I(className="fa-solid fa-chart-line text-indigo-500"),
                    html.Span(id='detail-node-id-display', className="ml-2"),
                    html.Span("性能监控", className="text-sm font-normal text-gray-500 ml-2")
                ], className="text-lg font-bold flex items-center"),
                
                html.Div([
                    html.Button("上周", id={'type': 'period-btn', 'value': '1w'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter active"),
                    html.Button("上月", id={'type': 'period-btn', 'value': '1m'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter"),
                    html.Button("上三月", id={'type': 'period-btn', 'value': '3m'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter"),
                    html.Button("上半年", id={'type': 'period-btn', 'value': '6m'}, className="px-3 py-1 text-xs rounded hover:bg-gray-700 transition-colors chart-filter"),
                ], className="flex bg-gray-800 rounded-lg p-1")
            ], className="flex items-center justify-between mb-6"),
            
            html.Div([
                html.Div([
                    html.H3("显卡 使用率趋势", className="text-sm font-medium text-gray-400 mb-4"),
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
        ]),
        
        # 回到顶部按钮
        html.Button(
            "↑",
            id="back-to-top",
            style=back_to_top_style_hidden,
            title="回到顶部",
            n_clicks=0
        ),
    ], className="p-6 pb-96", id='nodes-content')
])

# 注意：滚动到详情面板功能已改为使用 URL hash 锚点 (#node-detail-panel-anchor)
# 点击卡片时会自动更新 URL hash，浏览器会自动滚动到锚点位置

clientside_callback(
    '''
    function scrollToAnchor(node_id, back_to_top_n_clicks) {
        if (back_to_top_n_clicks) {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
            return 0;
        }
        var anchor = document.getElementById('node-detail-panel-anchor');
        if (anchor && node_id) {
            console.log('scrollToAnchor', node_id);
            setTimeout(function() {
                // 计算 Header 的高度（sticky header）
                var header = document.querySelector('header');
                var headerHeight = 0;
                if (header) {
                    var headerRect = header.getBoundingClientRect();
                    headerHeight = headerRect.height;
                } else {
                    // 如果找不到 header，使用默认值 64px (h-16) + 一些额外空间
                    headerHeight = 80;
                }
                
                // 获取锚点的位置
                var anchorTop = anchor.getBoundingClientRect().top + window.pageYOffset;
                
                // 滚动到锚点位置，减去 Header 高度，确保不被遮挡
                window.scrollTo({
                    top: anchorTop - headerHeight,
                    behavior: 'smooth'
                });
                console.log('scrollToAnchor', anchorTop - headerHeight);
            }, 100);
        }
        return 0;
    }
    ''',
    Output('back-to-top', 'n_clicks', allow_duplicate=True),
    Input('selected-node-store', 'data'),
    Input('back-to-top', 'n_clicks'),
    prevent_initial_call=True
)

clientside_callback(
    """
    function() {
        const backButton = document.getElementById('back-to-top');
        
        function handleScroll() {
            if (window.scrollY > 300) {
                backButton.style.opacity = 1;
                backButton.style.visibility = 'visible';
            } else {
                backButton.style.opacity = 0;
                backButton.style.visibility = 'hidden';
            }
        }
        
        // 添加滚动监听
        window.addEventListener('scroll', handleScroll);
        
        // 初始检查
        handleScroll();
        
        return window.dash_clientside.no_update;
    }
    """,
    Output('back-to-top', 'n_clicks'),
    Input('url', 'pathname')
)

@callback(
    [Output('nodes-grid', 'children'),
     Output('nodes-badges', 'children'),
     Output('node-part-filter', 'value')],
    [Input('nodes-url', 'search'),
     Input('selected-node-store', 'data'),
    Input('node-part-filter', 'value'),
    Input('node-health-filter', 'value')
    ]
)
def update_node_grid(search, selected_id, part_filter, health_filter):
    params = utils.search_params(search)
    
    url_part = params.get('partition')
    url_node = params.get('node')
    
    badges = []
    if url_part:
        badges.append(html.Span(f"分区: {url_part}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))
    if url_node:
        badges.append(html.Span(f"节点: {url_node}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))
        
    filtered_nodes = Node.nodes_info
    target_part = url_part if url_part else (part_filter if part_filter != 'all' else None)
    
    if target_part:
        filtered_nodes = [n for n in filtered_nodes if n.partition.partition_name == target_part]
    if health_filter != 'all':
        filtered_nodes = [n for n in filtered_nodes if n.health == health_filter]
    if url_node:
        filtered_nodes = [n for n in filtered_nodes if n.node == url_node]
        if filtered_nodes:
            part_filter = filtered_nodes[0].partition.partition_name
        
    cards = []
    if not filtered_nodes:
        return html.Div("无匹配节点数据", className="col-span-full text-center py-12 text-gray-500"), badges
        
    for n in filtered_nodes:
        is_selected = (selected_id == n.node)
        selected_class = "selected bg-gray-800/50 ring-2 ring-indigo-500/50" if is_selected else ""
        
        # cpu_pct = round((1 - n['cpu']['free'] / n['cpu']['total']) * 100)
        # mem_pct = round((1 - n['mem']['free'] / n['mem']['total']) * 100)
        # gpu_pct = round((1 - n['gpu']['free'] / n['gpu']['total']) * 100) if n['gpu']['total'] > 0 else 0
        
        health_color = {
            '健康': 'border-emerald-500/20 text-emerald-400 bg-emerald-500/10',
            '告警': 'border-yellow-500/20 text-yellow-400 bg-yellow-500/10',
            '离线': 'border-gray-700 text-gray-400 bg-gray-800'
        }.get(n.health, 'border-gray-700 text-gray-400 bg-gray-800')
        
        card = html.Div([
            html.Div([
                html.Div([
                    html.Div(html.I(className="fa-solid fa-server"), className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center text-gray-400 group-hover:bg-indigo-500/10 group-hover:text-indigo-400 transition-colors"),
                    html.Div([
                        html.H3(f'{n.node} ({n.partition.partition_name})', className="font-medium"),
                        html.Div(f'{n.ip} ({n.cabinet})', className="text-xs text-gray-500")
                    ])
                ], className="flex items-center gap-3"),
                html.Span(n.health, className=f"text-xs px-2 py-0.5 rounded border {health_color}")
            ], className="flex items-center justify-between mb-4"),
            
            html.Div([
                html.Div([
                    html.I(className="fa-solid fa-microchip text-purple-400 w-4"),
                    html.Span(f"CPU：总 {n.cpu} / 剩余 {n.idled_cpu}"),
                    html.Div(html.Div(style={'width': f'{n.cpu_util_pct}%'}, className="h-full bg-purple-500"), className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden ml-1")
                ], className="flex items-center gap-2"),
                html.Div([
                    html.I(className="fa-solid fa-memory text-blue-400 w-4"),
                    html.Span(f"内存：总 {n.memory}GB / 剩余 {n.idled_mem}GB"),
                    html.Div(html.Div(style={'width': f'{n.mem_util_pct}%'}, className="h-full bg-blue-500"), className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden ml-1")
                ], className="flex items-center gap-2"),
                html.Div([
                    html.I(className="fa-solid fa-square text-emerald-400 w-4"),
                    html.Span(f"GPU：总 {n.card} / 剩余 {n.idled_card}"),
                    html.Div(html.Div(style={'width': f'{n.gpu_util_pct}%'}, className="h-full bg-emerald-500"), className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden ml-1")
                ], className="flex items-center gap-2"),
            ], className="space-y-3 text-sm mb-5"),
            
            html.Div([
                html.Span(["运行作业: ", html.Span(str(len(list(filter(lambda x: x.get('status') == '运行中', n.tasks)))), className="text-white font-medium")])
            ], className="flex items-center justify-between pt-4 border-t border-gray-800 text-xs text-gray-400 mb-4"),
            
            html.Div([
                dcc.Link("查看作业", href=f"/jobs?node={n.node}", className="flex-1 text-center text-xs px-3 py-2 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-gray-400 transition-colors"),
                dcc.Link("查看分区", href=f"/?partition={n.partition.partition_name}", className="flex-1 text-center text-xs px-3 py-2 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-gray-400 transition-colors")
            ], className="flex gap-2")
        ], 
        id={'type': 'node-card', 'index': n.node},
        n_clicks=0,
        className=f"node-card cursor-pointer rounded-xl border border-gray-800 bg-gray-900 hover:border-gray-700 transition p-5 group {selected_class}")
        cards.append(card)
        
    return cards, badges, part_filter

@callback(
    [Output('selected-node-store', 'data'),
     Output('nodes-url', 'hash'),
     Output('scroll-trigger-store', 'data')],
    Input({'type': 'node-card', 'index': ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def handle_card_click(n_clicks):
    if not any(n_clicks):
        return dash.no_update, dash.no_update, dash.no_update
    
    ctx_triggered = ctx.triggered_id
    if not ctx_triggered:
        return dash.no_update, dash.no_update, dash.no_update
    
    node_id = ctx_triggered['index']
    import time
    # 返回选中的节点ID、hash锚点和滚动触发器
    # 使用时间戳作为触发器，确保每次点击都会触发滚动
    return node_id, '#node-detail-panel-anchor', time.time()


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
    logger.info(f"update_detail_panel selected_id: {selected_id}, period: {period}, {ctx.triggered_id}")
    starttime = time.time()
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
        
    node = next((n for n in Node.nodes_info if n.node == selected_id), None)
    if not node:
        return btn_classes, "hidden", "", [], {}, {}, {}
        
    gpu_rows = []
    if node.card == 0:
        gpu_rows.append(html.Tr(html.Td("无GPU资源", colSpan=5, className="px-3 py-4 text-center text-gray-500")))
    else:
        # gpu_history = node.get_history('GPU', period2days[period])
        gpu_infos = node.gpu_info
        if gpu_infos:
            for idx, gpu_info in gpu_infos.items():
                usage = gpu_info['usedRatio']
                temp = int(gpu_info['temperature'])
                temp_color = "text-red-400" if temp > 75 else "text-yellow-400" if temp > 60 else "text-emerald-400"
                row = html.Tr([
                    html.Td(f"{idx}", className="px-3 py-2 text-gray-300"),
                    html.Td(gpu_info['name'], className="px-3 py-2 text-gray-400"),
                    html.Td(f"{gpu_info['memUsed']} / {gpu_info['mem']}", className="px-3 py-2 text-gray-400"),
                    html.Td([
                        html.Div(html.Div(style={'width': f'{usage}%'}, className="h-full bg-emerald-500"), className="w-16 h-2 bg-gray-800 rounded-full overflow-hidden inline-block align-middle mr-2"),
                        f"{usage}%"
                    ], className="px-3 py-2 text-gray-400"),
                    html.Td(f"{temp}C", className=f"px-3 py-2 {temp_color}")
                ], className="hover:bg-gray-800/50")
                gpu_rows.append(row)


    def get_chart_data(data_type, color, days):
        # 传递max_points参数，让数据库层面进行降采样（更高效）
        history = node.get_history(data_type, days, max_points=MAX_CHART_POINTS)
        # 数据库层面已经进行了降采样，如果数据量仍然超过阈值，再进行应用层降采样（双重保险）
        #if len(history) > MAX_CHART_POINTS:
        #    history = downsample_history(history, MAX_CHART_POINTS)
        
        ret = create_chart(data_type, color, history)
        # 注意：时间统计已由get_history内部记录，这里只记录总体时间
        return ret

    # 使用 ThreadPoolExecutor 实现并行生成
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_gpu = executor.submit(get_chart_data, "GPU", "#6366f1", period2days[period])
        future_cpu = executor.submit(get_chart_data, "CPU", "#a855f7", period2days[period])
        future_mem = executor.submit(get_chart_data, "Memory", "#3b82f6", period2days[period])
        
        gpu_fig = future_gpu.result()
        cpu_fig = future_cpu.result()
        mem_fig = future_mem.result()

    endtime = time.time()
    logger.info(f"update_detail_panel time: {endtime - starttime}s")
    return btn_classes, "bg-gray-900 border border-gray-800 rounded-xl p-6 animate-fade-in-up", f"{selected_id} 详情", gpu_rows, gpu_fig, cpu_fig, mem_fig


