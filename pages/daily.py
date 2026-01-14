import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from datetime import datetime, timedelta
import random
from service.hpc_manager import hpc_manager

dash.register_page(__name__, path='/daily', name='日报')

# --- Mock Data Generators ---

def get_dates():
    dates = hpc_manager.get_daily_report_days()
    dates = list(map(lambda x: {"label": x, "value": x}, dates))
    return dates

def generate_partition_stats(date_str):
    partitions = ["defq", "gpu_v100", "gpu_a800", "cpu_large"]
    data = []
    for p in partitions:
        total_nodes = random.randint(10, 50)
        normal_nodes = total_nodes - random.randint(0, 5)
        data.append({
            "partition": p,
            "total_jobs": random.randint(100, 1000),
            "queued_jobs": random.randint(0, 50),
            "success_rate": f"{random.randint(90, 100)}%",
            "cpu_alloc": f"{random.randint(40, 95)}%",
            "mem_alloc": f"{random.randint(30, 80)}%",
            "gpu_alloc": f"{random.randint(20, 90)}%" if "gpu" in p else "N/A",
            "nodes_status": f"{normal_nodes}/{total_nodes}"
        })
    return data

def generate_user_stats(date_str):
    return {
        "total_users": random.randint(50, 200),
        "online_users": random.randint(10, 50)
    }

def generate_abnormal_nodes(date_str):
    nodes = []
    count = random.randint(0, 5)
    for i in range(count):
        nodes.append({
            "node_id": f"node-{random.randint(1, 100):03d}",
            "partition": random.choice(["gpu_v100", "defq"]),
            "status": "Down",
            "reason": random.choice(["Disk Full", "GPU Error", "Network Timeout"]),
            "duration": f"{random.randint(1, 24)}h"
        })
    return nodes

def generate_queued_jobs(date_str):
    jobs = []
    count = random.randint(0, 10)
    for i in range(count):
        jobs.append({
            "job_id": str(random.randint(10000, 99999)),
            "user": f"user{random.randint(1, 20)}",
            "partition": random.choice(["gpu_v100", "gpu_a800"]),
            "submit_time": (datetime.now() - timedelta(hours=random.randint(1, 10))).strftime("%H:%M:%S"),
            "wait_time": f"{random.randint(10, 120)} min",
            "reason": random.choice(["No Resources", "Priority Low"])
        })
    return jobs

# --- Layout ---

layout = html.Div([
    # Header (Sticky)
    # dbc.Location(id='daily-location', refresh=False),
    html.Header([
        html.Div([
            html.I(className="fa-solid fa-location-dot mr-2"),
            html.Span("HUTB HPC Cluster")
        ], className="flex items-center gap-4 text-gray-400 text-sm"),
        
        html.Div([
            html.Label("日期", className="text-xs text-gray-400 mr-2"),
            dcc.Dropdown(
                id='daily-date-picker',
                # options=get_dates(),
                # value=get_dates()[0]['value'],
                clearable=False,
                className="w-40 text-sm",
                style={'backgroundColor': '#1f2937', 'border': '1px solid #374151', 'color': '#fff'}
            )
        ], className="flex items-center")
        # className 详细释义:
        # h-16              高度为4rem (Tailwind)
        # bg-gray-900/50    背景为灰色900，透明度50%
        # backdrop-blur     应用背景模糊（毛玻璃效果）
        # border-b          下边框
        # border-gray-800   边框为灰色800
        # flex              使用flex布局
        # items-center      纵向居中排列
        # justify-between   主轴两端对齐（左右分散）
        # px-6              x方向内边距1.5rem
        # sticky            粘性定位
        # top-0             距顶部0px（与sticky配合，实现吸顶）
        # z-40              z-index为40，防止被其它元素遮挡
        ],
        className="h-16 bg-gray-900/50 backdrop-blur border-b border-gray-800 flex items-center justify-between px-6 sticky top-0 z-40",
    ),

    html.Div([
        # Hero Section
        html.Section([
            html.Img(
                src="https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1400&auto=format&fit=crop",
                className="w-full h-48 object-cover opacity-40"
            ),
            html.Div([
                html.Div([
                    html.H1("集群日报", className="text-2xl font-semibold text-white"),
                    html.P("按日汇总资源利用、用户与异常情况。", className="text-gray-300")
                ], className="space-y-2")
            ], className="absolute inset-0 flex items-center px-6 bg-gradient-to-r from-gray-900/80 to-transparent")
        ], className="relative rounded-xl overflow-hidden border border-gray-800 bg-gray-900"),

        # Resource Stats Section
        html.Section([
            html.Div([
                html.H2("资源统计（分区维度）", className="font-medium text-white"),
                html.Span(id="resource-date-label", className="text-xs text-gray-400")
            ], className="flex items-center justify-between mb-4"),
            
            dag.AgGrid(
                id="daily-resource-grid",
                columnDefs=[
                    {"headerName": "分区", "field": "partition", "sortable": True, 'flex': 1.5},
                    {"headerName": "运行作业", "field": "total_jobs", "sortable": True, 'flex': 1.1, },
                    {"headerName": "排队作业", "field": "queued_jobs", "sortable": True, 'flex': 1.1,},
                    # {"headerName": "成功率", "field": "success_rate", "sortable": True, 'flex': 1.1,},
                    {"headerName": "CPU分配", "field": "cpu_alloc", "sortable": True, 'flex': 1.1,},
                    {"headerName": "GPU分配", "field": "gpu_alloc", "sortable": True, 'flex': 1.1,},
                    {"headerName": "节点状态 (正常/总)", "field": "nodes_status", "sortable": True, 'flex': 1.1,},
                ],
                defaultColDef={"resizable": True, "cellStyle": {"textAlign": "center"}, 
                   },
                className="ag-theme-alpine-dark",
                dashGridOptions={
                    "domLayout": "normal",
                    # "headerHeight": 32
                }
            )
        ], className="bg-gray-900 rounded-xl p-6 border border-gray-800"),

        # User Stats Section
        html.Section([
            html.Div([
                html.H2("用户统计", className="font-medium text-white"),
            ], className="flex items-center justify-between mb-4"),
            
            html.Div([
                html.Div([
                    html.Div("总用户数", className="text-xs text-gray-400 mb-1"),
                    html.Div(id="daily-total-users", className="text-2xl font-semibold text-white")
                ], className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-center"),
                
                html.Div([
                    html.Div("在线用户数", className="text-xs text-gray-400 mb-1"),
                    html.Div(id="daily-online-users", className="text-2xl font-semibold text-emerald-400")
                ], className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-center"),
            ], className="grid grid-cols-2 md:grid-cols-4 gap-6")
        ], className="bg-gray-900 rounded-xl p-6 border border-gray-800"),

        # Abnormal Stats Section
        html.Section([
            html.Div([
                html.H2("异常情况", className="font-medium text-white"),
            ], className="flex items-center justify-between mb-4"),
            
            html.Div([
                # Abnormal Nodes
                html.Div([
                    html.H3("异常节点", className="text-sm text-gray-400 mb-2"),
                    dag.AgGrid(
                        id="daily-abnormal-nodes-grid",
                        columnDefs=[
                            {"headerName": "节点ID", "field": "node_id", "sortable": True, "cellClass": "font-mono", 'headerClass': 'header-center', 'flex': 1},
                            {"headerName": "所属分区", "field": "partition", 'headerClass': 'header-center', 'flex': 1},
                            {"headerName": "状态", "field": "status", "cellStyle": {'color': '#ef4444'}, 'flex': 1, 'headerClass': 'header-center'},
                            {"headerName": "原因", "field": "reason", 'flex': 2, 'headerClass': 'header-center'},
                            # {"headerName": "持续时间", "field": "duration"}
                        ],
                        defaultColDef={"flex": 1, "cellStyle": {"textAlign": "center"},},
                        style={"height": "300px"},
                        className="ag-theme-alpine-dark"
                    )
                ], className="mb-6"),
                
                # Queued Jobs
                html.Div([
                    html.H3("排队作业明细", className="text-sm text-gray-400 mb-2"),
                    dag.AgGrid(
                        id="daily-queued-jobs-grid",
                        columnDefs=[
                            {"headerName": "作业ID", "field": "job_id", "cellClass": "font-mono", 'headerClass': 'header-center', 'flex': 1},
                            {"headerName": "用户", "field": "user", 'headerClass': 'header-center', 'flex': 1},
                            {"headerName": "分区", "field": "partition", 'headerClass': 'header-center', 'flex': 1},
                            {"headerName": "申请资源", "field": "resource", 'headerClass': 'header-center', 'flex': 1.9},
                            {"headerName": "提交时间", "field": "submit_time", 'headerClass': 'header-center', 'flex': 1.9},
                            {"headerName": "等待时间", "field": "wait_time", 'headerClass': 'header-center', 'flex': 1.5},
                        ],
                        defaultColDef={"flex": 1, "cellStyle": {"textAlign": "center"}},
                        style={"height": "300px"},
                        className="ag-theme-alpine-dark"
                    )
                ])
            ], className="flex flex-col gap-6")
        ], className="bg-gray-900 rounded-xl p-6 border border-gray-800")

    # className="p-6 space-y-6" 是 Tailwind CSS 的类名组合，用于给这个最外层 <div> 添加样式，含义如下：
    # - p-6    ：为容器的所有内边距（padding）设置为 1.5rem (24px)
    # - space-y-6 ：让子元素之间（垂直方向）自动有 1.5rem (24px) 的间隔

    ], className="p-6")
])

# --- Callbacks ---

@callback(
    [Output("daily-date-picker", "value"), Output('daily-date-picker', 'options')],
    [Input("url", "pathname")]
)
def update_daily_location(pathname):
    dates = get_dates()
    return dates[0]['value'], dates

@callback(
    [Output("daily-resource-grid", "rowData"),
     Output("daily-total-users", "children"),
     Output("daily-online-users", "children"),
     Output("daily-abnormal-nodes-grid", "rowData"),
     Output("daily-queued-jobs-grid", "rowData"),
     Output("resource-date-label", "children")],
    [Input("daily-date-picker", "value")]
)
def update_daily_report(selected_date):
    statistic_data = hpc_manager.get_daily_statistic(selected_date)
    # 1. Resource Stats
    resource_data = statistic_data.get('partition_info', []) # generate_partition_stats()
    
    # 2. User Stats
    user_data = {
        "total_users": statistic_data.get('total_users', 0),
        "online_users": statistic_data.get('online_users', 0)
    }  # generate_user_stats(selected_date)
    
    # 3. Abnormal Nodes
    abnormal_nodes = statistic_data.get('exception_nodes', []) # generate_abnormal_nodes(selected_date)
    
    # 4. Queued Jobs
    queued_jobs = statistic_data.get('queuing_jobs', []) # generate_queued_jobs(selected_date)
    
    return (
        resource_data,
        f"{user_data['total_users']}",
        f"{user_data['online_users']}",
        abnormal_nodes,
        queued_jobs,
        selected_date
    )
