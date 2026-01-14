import dash
from common import utils
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import random
from service.hpc_manager import hpc_manager, Task, map2resourcedesc

dash.register_page(__name__, path='/jobs', name='作业管理')

# # Simulated Data
# def gen_jobs(count=50):
#     users = ['alice', 'bob', 'carol', 'dave', 'eve', 'frank', 'grace', 'heidi']
#     parts = ['gpu-a', 'cpu-b', 'mem-c', 'gpu-b']
#     statuses = ['运行中', '排队中', '已完成', '失败', '已取消']
#     data = []
    
#     for i in range(count):
#         job_id = f'J-{102938 + i}'
#         st = random.choice(statuses)
#         is_que = st == '排队中'
#         is_done = st in ['已完成', '失败', '已取消']
        
#         cpu = random.choice([4, 8, 16, 32, 64, 128])
#         mem = random.choice([16, 32, 64, 128, 256, 512])
#         gpu = random.choice([1, 2, 4, 8]) if random.random() > 0.5 else 0
        
#         start_time = '-' if is_que else f"12:{10 + random.randint(0, 49)}"
#         end_time = f"14:{10 + random.randint(0, 49)}" if is_done else '-'
#         user = random.choice(users)
#         node = '-' if is_que else f"node-{10 + random.randint(0, 19)}"
#         part = random.choice(parts)
        
#         status_color_class = ""
#         if st == '运行中':
#             status_color_class = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
#         elif st == '排队中':
#             status_color_class = "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
#         elif st == '失败':
#             status_color_class = "bg-red-500/10 text-red-400 border-red-500/20"
#         else:
#             status_color_class = "bg-gray-800 text-gray-400 border-gray-700"
            
#         status_html = f'<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs border {status_color_class}">{st}</span>'
#         user_html = f'<div class="flex items-center gap-2"><div class="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs">{user[0].upper()}</div>{user}</div>'

#         view_part_html = f'<a href="/?part={part}" class="text-xs px-2 py-1 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-indigo-300 transition-colors" style="text-decoration: none;">查看</a>'
#         view_node_html = (f'<a href="/nodes?node={node}" class="text-xs px-2 py-1 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-indigo-300 transition-colors" style="text-decoration: none;">查看</a>' if node != '-' else '-')

#         data.append({
#             'id': job_id,
#             'status': st,
#             'status_html': status_html,
#             'resources': f"{cpu}C / {mem}G / {gpu}G",
#             'cpu': cpu, 'mem': mem, 'gpu': gpu,
#             'start': start_time,
#             'end': end_time,
#             'user': user,
#             'user_html': user_html,
#             'node': node,
#             'part': part,
#             'view_part_html': view_part_html,
#             'view_node_html': view_node_html
#         })
        
#     return pd.DataFrame(data)


columnDefs = [
    {"headerName": "作业ID", "field": "slurmJobId", "sortable": True, "filter": True, "flex": 7, "cellClass": "font-mono text-gray-300"},
    {"headerName": "状态", "field": "status_html", "cellRenderer": "markdown", "sortable": True, "flex": 6},
    {"headerName": "CPU/内存/GPU", "field": "resources", "sortable": False, "flex": 16},
    {"headerName": "开始时间", "field": "submitTime", "sortable": True, "cellClass": "text-gray-400", "flex": 12},
    {"headerName": "结束时间", "field": "endTime", "sortable": True, "cellClass": "text-gray-500", "flex": 12,},
    {"headerName": "运行时长", "field": "duration", "sortable": True, "flex": 11},
    {"headerName": "申请人", "field": "createBy", "cellRenderer": "markdown", "sortable": True, "flex": 10},
    {"headerName": "节点", "field": "node_html", "cellRenderer": "markdown", "flex": 7, "cellClass": "text-gray-400"},
    {"headerName": "分区", "field": "partition_html", "cellRenderer": "markdown", "flex": 7},
    # {"headerName": "查看节点", "field": "view_node_html", "cellRenderer": "markdown", "minWidth": 110}
    # {"headerName": "查看分区", "field": "view_part_html", "cellRenderer": "markdown", "minWidth": 110},
]

layout = html.Div([
    dcc.Location(id='jobs-url', refresh=False),
    
    html.Div([
        html.Div(id='jobs-badges', className="flex items-center gap-2 mb-4"),
        
        html.Div([
            html.Div([
                html.Label("状态", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='job-status-filter',
                    options=[
                        {'label': '全部', 'value': 'all'},
                        {'label': '运行中', 'value': '运行中'},
                        {'label': '排队中', 'value': '排队中'},
                        {'label': '已完成', 'value': '已完成'},
                        {'label': '已取消', 'value': '已取消'},
                        {'label': '失败', 'value': '失败'}
                    ],
                    value='all',
                    clearable=False,
                    className="mt-1 w-32"
                )
            ], className="flex flex-col"),
            html.Div([
                html.Label("用户", className="text-xs text-gray-400"),
                dcc.Input(id='job-user-filter', placeholder="按申请人", className="mt-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white w-40")
            ], className="flex flex-col"),
            # html.Div([
            #     html.Label("资源需求", className="text-xs text-gray-400"),
            #     dcc.Input(id='job-res-filter', placeholder="例如: cpu>32 gpu>=2", className="mt-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white w-64")
            # ]),
            html.Div(className="flex-1"),
            # html.Button([html.I(className="fa-solid fa-filter mr-1"), "筛选"], id='btn-job-filter', className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-300"),
            # html.Button([html.I(className="fa-solid fa-download mr-1"), "导出"], id='btn-job-export', className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-300 ml-2"),
        ], className="flex flex-wrap gap-3 items-end mb-6"),
        
        dag.AgGrid(
            id="jobs-grid",
            columnDefs=columnDefs,
            # rowData=df_jobs.to_dict("records"),
            defaultColDef={"resizable": True, "sortable": True, "filter": True},
            dashGridOptions={
                "domLayout": "autoHeight", 
                "rowHeight": 48, 
                "pagination": True,
                "paginationPageSize": 10,
                "paginationPageSizeSelector": [10, 20, 50, 100],
                "enableRangeSelection": True,
                "enableCellTextSelection": True,
                "clipboard": {
                    "enabled": True
                },
            },
            className="ag-theme-alpine-dark",
            dangerously_allow_code=True,
            style={"height": None}
        )
    ], className="p-6")
])

@callback(
    [Output('jobs-grid', 'rowData'),
     Output('jobs-badges', 'children')],
    [Input('jobs-url', 'search'),
    Input('job-status-filter', 'value'),
     Input('job-user-filter', 'value'),
    #  Input('job-res-filter', 'value')
     ]
)
def update_jobs(search, status, user, res_str=None):
    params = utils.search_params(search)
    
    part_param = params.get('partition')
    node_param = params.get('node')
    
    badges = []
    if part_param:
        badges.append(html.Span(f"分区: {part_param}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))
    if node_param:
        badges.append(html.Span(f"节点: {node_param}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))

    filtered_df = pd.DataFrame(Task.tasks_info)  # regenerate to keep links consistent
    filtered_df['status_html'] = filtered_df['status'].apply(map2status_html)
    filtered_df['resources'] = filtered_df.apply(map2resourcedesc, axis=1)
    filtered_df['partition_html'] = filtered_df['partition'].apply(map2partition)
    filtered_df['node_html'] = filtered_df['nodes'].apply(map2node)

    if part_param:
        filtered_df = filtered_df[filtered_df['partition'] == part_param]
    if node_param:
        filtered_df = filtered_df[filtered_df['node'] == node_param]

    if status and status != 'all':
        filtered_df = filtered_df[filtered_df['status'] == status]
        
    if user:
        filtered_df = filtered_df[filtered_df['createBy'].str.contains(user, case=False)]
        
    if res_str:
        parts = res_str.split(' ')
        for p in parts:
            if not p: continue
            import re
            m = re.match(r'(cpu|gpu|mem)\s*([><=]+)\s*(\d+)', p)
            if m:
                key, op, val = m.groups()
                val = int(val)
                if op == '>':
                    filtered_df = filtered_df[filtered_df[key] > val]
                elif op == '<':
                    filtered_df = filtered_df[filtered_df[key] < val]
                elif op == '>=':
                    filtered_df = filtered_df[filtered_df[key] >= val]
                elif op == '<=':
                    filtered_df = filtered_df[filtered_df[key] <= val]
                elif op == '=' or op == '==':
                    filtered_df = filtered_df[filtered_df[key] == val]

    return filtered_df.to_dict("records"), badges

def map2status_html(status):
    status_color_class = ""
    if status == '运行中':
        status_color_class = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
    elif status == '排队中':
        status_color_class = "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
    elif status == '失败':
        status_color_class = "bg-red-500/10 text-red-400 border-red-500/20"
    else:
        status_color_class = "bg-gray-800 text-gray-400 border-gray-700"
    status_html = f'<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs border {status_color_class}">{status}</span>'
    return status_html


def map2partition(partition):
    view_part_html = f'<a href="/?partition={partition}" class="text-xs px-2 py-1 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-indigo-300 transition-colors" style="text-decoration: none;">{partition}</a>'
    return view_part_html

def map2node(node):
    if node:
        view_node_html = (f'<a href="/nodes?node={node}" class="text-xs px-2 py-1 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-indigo-300 transition-colors" style="text-decoration: none;">{node}</a>' if node != '-' else '-')
    else:
        view_node_html = '-'
    return view_node_html
