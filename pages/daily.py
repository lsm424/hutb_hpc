import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from datetime import datetime, timedelta
import random

dash.register_page(__name__, path='/daily', name='日报')

# --- Mock Data Generators ---

def get_dates():
    dates = []
    today = datetime.now()
    for i in range(7):
        date = today - timedelta(days=i)
        dates.append({"label": date.strftime("%Y-%m-%d"), "value": date.strftime("%Y-%m-%d")})
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
    html.Header([
        html.Div([
            html.I(className="fa-solid fa-location-dot mr-2"),
            html.Span("HPC Cluster A")
        ], className="flex items-center gap-4 text-gray-400 text-sm"),
        
        html.Div([
            html.Label("日期", className="text-xs text-gray-400 mr-2"),
            dcc.Dropdown(
                id='daily-date-picker',
                options=get_dates(),
                value=get_dates()[0]['value'],
                clearable=False,
                className="w-40 text-sm",
                style={'backgroundColor': '#1f2937', 'border': '1px solid #374151', 'color': '#fff'}
            )
        ], className="flex items-center")
    ], className="h-16 bg-gray-900/50 backdrop-blur border-b border-gray-800 flex items-center justify-between px-6 sticky top-0 z-40"),

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
                    {"headerName": "分区", "field": "partition", "sortable": True},
                    {"headerName": "运行作业", "field": "total_jobs", "sortable": True},
                    {"headerName": "排队作业", "field": "queued_jobs", "sortable": True},
                    {"headerName": "成功率", "field": "success_rate"},
                    {"headerName": "CPU分配", "field": "cpu_alloc"},
                    {"headerName": "GPU分配", "field": "gpu_alloc"},
                    {"headerName": "节点状态 (正常/总)", "field": "nodes_status"}
                ],
                defaultColDef={"flex": 1, "minWidth": 100, "resizable": True},
                style={"height": "250px", "width": "100%"},
                className="ag-theme-alpine-dark",
                dashGridOptions={"domLayout": "autoHeight"}
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
                            {"headerName": "节点ID", "field": "node_id", "sortable": True, "cellClass": "font-mono"},
                            {"headerName": "所属分区", "field": "partition"},
                            {"headerName": "状态", "field": "status", "cellStyle": {'color': '#ef4444'}},
                            {"headerName": "原因", "field": "reason"},
                            {"headerName": "持续时间", "field": "duration"}
                        ],
                        defaultColDef={"flex": 1},
                        style={"height": "300px"},
                        className="ag-theme-alpine-dark"
                    )
                ]),
                
                # Queued Jobs
                html.Div([
                    html.H3("排队作业明细", className="text-sm text-gray-400 mb-2"),
                    dag.AgGrid(
                        id="daily-queued-jobs-grid",
                        columnDefs=[
                            {"headerName": "作业ID", "field": "job_id", "cellClass": "font-mono"},
                            {"headerName": "用户", "field": "user"},
                            {"headerName": "分区", "field": "partition"},
                            {"headerName": "提交时间", "field": "submit_time"},
                            {"headerName": "等待时间", "field": "wait_time"},
                            {"headerName": "排队原因", "field": "reason"}
                        ],
                        defaultColDef={"flex": 1},
                        style={"height": "300px"},
                        className="ag-theme-alpine-dark"
                    )
                ])
            ], className="grid grid-cols-1 lg:grid-cols-2 gap-6")
        ], className="bg-gray-900 rounded-xl p-6 border border-gray-800")

    ], className="p-6 space-y-6")
])

# --- Callbacks ---

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
    # 1. Resource Stats
    resource_data = generate_partition_stats(selected_date)
    
    # 2. User Stats
    user_data = generate_user_stats(selected_date)
    
    # 3. Abnormal Nodes
    abnormal_nodes = generate_abnormal_nodes(selected_date)
    
    # 4. Queued Jobs
    queued_jobs = generate_queued_jobs(selected_date)
    
    return (
        resource_data,
        f"{user_data['total_users']}",
        f"{user_data['online_users']}",
        abnormal_nodes,
        queued_jobs,
        selected_date
    )
