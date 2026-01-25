import dash
from common import utils
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import random
from service.user import user_service

dash.register_page(__name__, path='/users', name='用户管理')


columnDefs = [
    {"headerName": "用户名", "field": "username", "sortable": True, "filter": True, "flex": 12,},
    {"headerName": "昵称", "field": "realname", "cellRenderer": "markdown", "sortable": True, "flex": 12},
    {"headerName": "邮箱", "field": "email", "sortable": False, "flex": 6},
    {"headerName": "手机号", "field": "phone", "sortable": False, "flex": 8},
    {"headerName": "角色", "field": "role_name", "sortable": True, "flex": 20},
    {"headerName": "注册时间", "field": "register_time", "sortable": True, "flex": 12},
    {"headerName": "状态", "field": "status_html", "cellRenderer": "markdown","sortable": True, "flex": 5},
    {"headerName": "作业", "field": "jobs", "cellRenderer": "markdown", "sortable": False, "flex": 5},
]

layout = html.Div([
    dcc.Location(id='users-url', refresh=False),
    
    html.Div([
        html.Div(id='users-badges', className="flex items-center gap-2 mb-4"),
        
        html.Div([
            html.Div([
                html.Label("状态", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='user-status-filter',
                    options=[
                        # {'label': '全部', 'value': None},
                        {'label': '正常', 'value': '正常'},
                        {'label': '冻结', 'value': '冻结'},
                        {'label': '注册待审核', 'value': '注册待审核'},
                    ],
                    value=None,
                    clearable=True,
                    className="mt-1 w-48"
                )
            ], className="flex flex-col"),
            html.Div([
                html.Label("角色", className="text-xs text-gray-400"),
                dcc.Dropdown(
                    id='user-role-filter',
                    options=[
                        # {'label': '全部', 'value': None},
                        {'label': '超算用户', 'value': '超算用户'},
                        {'label': '访客', 'value': '访客'},
                        {'label': '管理员', 'value': '管理员'},
                        {'label': '安全保密管理员', 'value': '安全保密管理员'},
                        {'label': '安全审计员', 'value': '安全审计员'},
                        {'label': '湘江实验室管理员', 'value': '湘江实验室管理员'},
                    ],
                    value=None,
                    clearable=True,
                    className="mt-1 w-48"
                )
            ], className="flex flex-col"),
            html.Div([
                html.Label("用户", className="text-xs text-gray-400"),
                dcc.Input(id='user-user-filter', placeholder="用户名或昵称", className="mt-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white w-48")
            ], className="flex flex-col"),
            # html.Div([
            #     html.Label("资源需求", className="text-xs text-gray-400"),
            #     dcc.Input(id='user-res-filter', placeholder="例如: cpu>32 gpu>=2", className="mt-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white w-64")
            # ]),
            html.Div(className="flex-1"),
            # html.Button([html.I(className="fa-solid fa-filter mr-1"), "筛选"], id='btn-user-filter', className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-300"),
            # html.Button([html.I(className="fa-solid fa-download mr-1"), "导出"], id='btn-user-export', className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-300 ml-2"),
        ], className="flex flex-wrap gap-3 items-end mb-6"),
        
        dag.AgGrid(
            id="users-grid",
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
    [Output('users-grid', 'rowData'),
     Output('users-badges', 'children'),
     Output('user-user-filter', 'value')],
    [Input('users-url', 'search'),
    Input('user-status-filter', 'value'),
     Input('user-user-filter', 'value'),
     Input('user-role-filter', 'value'),
    #  Input('user-res-filter', 'value')
     ]
)
def update_jobs(search, status, user, role, res_str=None):
    params = utils.search_params(search)
    
    username_param = params.get('username', None) or user or ''
    
    badges = []
    # if username_param:
    #     badges.append(html.Span(f"用户: {username_param}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))
    # if status:
    #     badges.append(html.Span(f"状态: {status}", className="px-2 py-0.5 bg-indigo-900/50 text-indigo-300 rounded text-xs border border-indigo-700/50"))
    users = user_service.get_and_update_users(username=username_param, status=status, role=role)
    if not users:
        return [], badges, username_param
    filtered_df = pd.DataFrame(users)  # regenerate to keep links consistent
    filtered_df['status_html'] = filtered_df['status'].apply(map2status_html)
    filtered_df['jobs'] = filtered_df['username'].apply(map2jobs)

    return filtered_df.to_dict("records"), badges, username_param

def map2status_html(status):
    status_color_class = ""
    if status == '正常':
        status_color_class = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
    elif status == '冻结':
        status_color_class = "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
    elif status == '注册待审核':
        status_color_class = "bg-red-500/10 text-red-400 border-red-500/20"
    else:
        status_color_class = "bg-gray-800 text-gray-400 border-gray-700"
    status_html = f'<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs border {status_color_class}">{status}</span>'
    return status_html


def map2jobs(username):
    if username:
        view_jobs_html = (f'<a href="/jobs?username={username}" class="text-xs px-2 py-1 rounded border border-gray-700 hover:bg-gray-800 hover:text-white text-indigo-300 transition-colors" style="text-decoration: none;">查看</a>' if username != '-' else '-')
    else:
        view_jobs_html = '-'
    return view_jobs_html
