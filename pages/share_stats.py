import dash
from dash import html, dcc, callback, Input, Output
import dash_ag_grid as dag
import plotly.graph_objects as go
from datetime import datetime, timedelta

from service.share_stats import get_share_stats

dash.register_page(__name__, path='/share-stats', name='共享统计')

# --- 主题常量（与全站深色风格一致的语义色） ---
ACCENT_INDIGO = "#6366f1"
ACCENT_CYAN = "#22d3ee"
ACCENT_EMERALD = "#34d399"
ACCENT_AMBER = "#fbbf24"
GRID_COLOR = "#1f2937"


def get_year_options():
    current_year = datetime.now().year
    return [{'label': f'{y}年', 'value': y} for y in range(current_year, 2023, -1)]


def get_month_options():
    options = [{'label': '全年', 'value': 'all'}]
    options += [{'label': f'{m}月', 'value': str(m)} for m in range(1, 13)]
    return options


def get_date_range(year, month):
    """根据年份+月份下拉值计算统计区间 (YYYY-MM-DD)"""
    year = int(year)
    if month in (None, '', 'all'):
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31, 23, 59, 59)
    else:
        m = int(month)
        start = datetime(year, m, 1)
        end = datetime(year + (m == 12), (m % 12) + 1, 1) - timedelta(seconds=1)
    now = datetime.now()
    if end > now:
        end = now
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _dark_axis():
    return {
        "gridcolor": GRID_COLOR,
        "zerolinecolor": "#374151",
        "linecolor": "#374151",
    }


def make_monthly_figure(monthly_rows):
    fig = go.Figure()
    months = [r["month"] for r in monthly_rows]
    gpu_hours = [r["gpu_hours"] for r in monthly_rows]
    tasks = [r["tasks"] for r in monthly_rows]

    fig.add_bar(
        x=months, y=gpu_hours, name="卡时 (h)",
        marker_color=ACCENT_INDIGO, marker_line_width=0,
        hovertemplate="%{x}<br>卡时: %{y:,.2f} h<extra></extra>",
    )
    fig.add_scatter(
        x=months, y=tasks, name="任务数", yaxis="y2",
        mode="lines+markers", line={"color": ACCENT_EMERALD, "width": 2},
        marker={"size": 6},
        hovertemplate="%{x}<br>任务数: %{y}<extra></extra>",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#9ca3af", "size": 12},
        margin={"l": 60, "r": 60, "t": 30, "b": 30},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0},
        xaxis={**_dark_axis()},
        yaxis={"title": "卡时 (h)", "gridcolor": GRID_COLOR, "zerolinecolor": "#374151"},
        yaxis2={"title": "任务数", "overlaying": "y", "side": "right", "showgrid": False},
        bargap=0.35,
    )
    return fig


def make_node_gpu_figure(node_rows, top_n=15):
    rows = node_rows[:top_n][::-1]  # 倒序让最大的显示在最上方
    fig = go.Figure()
    fig.add_bar(
        y=[r["node"] for r in rows],
        x=[r["gpu_hours"] for r in rows],
        orientation="h",
        marker_color=ACCENT_CYAN, marker_line_width=0,
        text=[f"{r['gpu_hours']:,.1f}" for r in rows],
        textposition="outside",
        textfont={"color": "#9ca3af", "size": 11},
        cliponaxis=False,
        hovertemplate="%{y}<br>卡时: %{x:,.2f} h<extra></extra>",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#9ca3af", "size": 12},
        margin={"l": 90, "r": 50, "t": 10, "b": 40},
        xaxis={"title": "卡时 (h)", **_dark_axis()},
        yaxis={**_dark_axis()},
    )
    return fig


def kpi_card(icon, icon_class, value_id, label, sub_id=None, sub_text=""):
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        html.I(className=f"fa-solid {icon}"),
                        className=f"w-10 h-10 rounded-lg flex items-center justify-center {icon_class}",
                    ),
                    html.Div(
                        [
                            html.Div(id=value_id, className="text-2xl font-semibold text-white leading-tight"),
                            html.Div(label, className="text-xs text-gray-400 mt-1"),
                        ],
                        className="ml-3",
                    ),
                ],
                className="flex items-center",
            ),
            html.Div(id=sub_id, children=sub_text, className="text-[11px] text-gray-500 mt-3") if (sub_id or sub_text) else None,
        ],
        className="rounded-xl border border-gray-800 bg-gray-900 p-5 hover:border-gray-700 transition-colors",
    )


node_columns = [
    {"headerName": "节点", "field": "node", "sortable": True, "cellClass": "font-mono text-gray-300", "headerClass": "header-center", "flex": 1.5},
    {"headerName": "任务数", "field": "task_count", "sortable": True, "headerClass": "header-center", "flex": 1},
    {"headerName": "节点时长 (h)", "field": "node_hours", "sortable": True, "headerClass": "header-center", "flex": 1.2},
    {"headerName": "卡时 (h)", "field": "gpu_hours", "sortable": True, "headerClass": "header-center", "flex": 1.2},
    {"headerName": "卡时占比", "field": "gpu_hours_pct", "sortable": True, "headerClass": "header-center", "flex": 1},
    {"headerName": "平均并行卡数", "field": "avg_cards", "sortable": True, "headerClass": "header-center", "flex": 1.2},
]

layout = html.Div([
    html.Div([
        # Hero Section
        html.Section([
            html.Img(
                src="https://images.unsplash.com/photo-1558494949-ef010cbdcc31?q=80&w=1400&auto=format&fit=crop",
                className="w-full h-48 object-cover opacity-40"
            ),
            html.Div([
                html.Div([
                    html.H1("共享统计", className="text-2xl font-semibold text-white"),
                    html.P("统计共享机时：任务总时长、节点总时长（去重叠）与卡时。", className="text-gray-300")
                ], className="space-y-2")
            ], className="absolute inset-0 flex items-center px-6 bg-gradient-to-r from-gray-900/80 to-transparent")
        ], className="relative rounded-xl overflow-hidden border border-gray-800 bg-gray-900"),

        # Filters Section
        html.Section([
            html.Div([
                html.Div([
                    html.Label("年份", className="text-xs text-gray-400"),
                    dcc.Dropdown(
                        id='share-year',
                        options=get_year_options(),
                        value=2025,
                        clearable=False,
                        className="mt-1 w-36"
                    )
                ], className="flex flex-col"),
                html.Div([
                    html.Label("月份", className="text-xs text-gray-400"),
                    dcc.Dropdown(
                        id='share-month',
                        options=get_month_options(),
                        value='all',
                        clearable=False,
                        className="mt-1 w-36"
                    )
                ], className="flex flex-col"),
                html.Button(
                    [html.I(className="fa-solid fa-magnifying-glass mr-2"), "查询"],
                    id='share-stats-query',
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm text-white transition-colors"
                ),
                html.Button(
                    html.I(className="fa-solid fa-rotate-right"),
                    id='share-stats-refresh',
                    title="强制刷新（绕过缓存重新拉取任务数据）",
                    className="w-9 h-9 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-gray-300 transition-colors"
                ),
                html.Div(className="flex-1"),
                html.Div(id='share-stats-updated', className="text-xs text-gray-500")
            ], className="flex flex-wrap gap-3 items-end"),
        ], className="bg-gray-900 rounded-xl p-6 border border-gray-800"),

        dcc.Loading(
            html.Div([
                # KPI Cards Section
                html.Section([
                    html.Div(
                        [
                            kpi_card("fa-list-check", "bg-indigo-500/10 text-indigo-400",
                                     "share-kpi-tasks", "任务总数",
                                     sub_id="share-kpi-tasks-sub"),
                            kpi_card("fa-hourglass-half", "bg-cyan-500/10 text-cyan-400",
                                     "share-kpi-task-hours", "任务总时长 (h)",
                                     sub_id="share-kpi-task-hours-sub"),
                            kpi_card("fa-server", "bg-emerald-500/10 text-emerald-400",
                                     "share-kpi-node-hours", "节点总时长 (h)"),
                            kpi_card("fa-microchip", "bg-amber-500/10 text-amber-400",
                                     "share-kpi-gpu-hours", "卡时 (h)"),
                        ],
                        className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4"
                    ),
                    html.Div(id='share-kpi-note', className="text-xs text-gray-500 mt-3"),
                ], className="bg-gray-900 rounded-xl p-6 border border-gray-800"),

                # Charts Section
                html.Section([
                    html.Div([
                        # 月度趋势
                        html.Div([
                            html.H2("月度趋势", className="font-medium text-white mb-4"),
                            dcc.Graph(
                                id="share-chart-monthly",
                                config={"displayModeBar": False},
                                style={"height": "340px"},
                            )
                        ], className="bg-gray-900 rounded-xl p-6 border border-gray-800 xl:col-span-3"),
                        # 节点卡时 Top 15
                        html.Div([
                            html.H2("节点卡时 Top 15", className="font-medium text-white mb-4"),
                            dcc.Graph(
                                id="share-chart-node-gpu",
                                config={"displayModeBar": False},
                                style={"height": "340px"},
                            )
                        ], className="bg-gray-900 rounded-xl p-6 border border-gray-800 xl:col-span-2"),
                    ], className="grid grid-cols-1 xl:grid-cols-5 gap-4")
                ]),

                # Node Details Section
                html.Section([
                    html.Div([
                        html.H2("各节点卡时统计", className="font-medium text-white"),
                        html.Span(
                            "卡时 = 任务时长 × 卡数（多节点任务按节点均摊）",
                            className="text-xs text-gray-500"
                        ),
                    ], className="flex items-center justify-between mb-4 flex-wrap gap-2"),
                    dag.AgGrid(
                        id="share-node-grid",
                        columnDefs=node_columns,
                        defaultColDef={"resizable": True},
                        dashGridOptions={
                            "domLayout": "autoHeight",
                            "rowHeight": 44,
                            "pagination": True,
                            "paginationPageSize": 20,
                            "paginationPageSizeSelector": [10, 20, 50, 100],
                            "enableCellTextSelection": True,
                        },
                        className="ag-theme-alpine-dark",
                        style={"height": None}
                    )
                ], className="bg-gray-900 rounded-xl p-6 border border-gray-800"),
            ], className="mt-5 space-y-5"),
            type="circle",
            color=ACCENT_INDIGO,
            delay_show=250,
        ),
    ], className="p-6 space-y-5")
])


@callback(
    [
        Output("share-kpi-tasks", "children"),
        Output("share-kpi-tasks-sub", "children"),
        Output("share-kpi-task-hours", "children"),
        Output("share-kpi-task-hours-sub", "children"),
        Output("share-kpi-node-hours", "children"),
        Output("share-kpi-gpu-hours", "children"),
        Output("share-kpi-note", "children"),
        Output("share-stats-updated", "children"),
        Output("share-chart-monthly", "figure"),
        Output("share-chart-node-gpu", "figure"),
        Output("share-node-grid", "rowData"),
    ],
    [
        Input("share-year", "value"),
        Input("share-month", "value"),
        Input("share-stats-query", "n_clicks"),
        Input("share-stats-refresh", "n_clicks"),
    ],
    prevent_initial_call=False,
)
def update_share_stats(year, month, n_query, n_refresh):
    ctx = dash.callback_context
    force_refresh = False
    if ctx.triggered:
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        force_refresh = trigger_id == "share-stats-refresh"

    start_date, end_date = get_date_range(year, month)
    stats = get_share_stats(start_date, end_date, force_refresh=force_refresh)

    node_rows = stats.get("node_rows", [])
    monthly_rows = stats.get("monthly", [])

    task_count = stats.get("task_count", 0)
    skipped_count = stats.get("skipped_count", 0)
    running_count = stats.get("running_count", 0)

    tasks_sub = f"共拉取 {task_count} 条任务记录" if task_count else "暂无任务记录"
    task_hours_sub = f"含运行中任务 {running_count} 条（按当前时刻计入）" if running_count else "仅统计已结束任务"

    notes = [f"统计范围 {start_date} ~ {end_date}"]
    if skipped_count:
        notes.append(f"已跳过 {skipped_count} 条无有效时间的记录")

    return (
        f"{task_count}",
        tasks_sub,
        f"{stats.get('total_task_hours', 0):,.2f}",
        task_hours_sub,
        f"{stats.get('total_node_hours', 0):,.2f}",
        f"{stats.get('total_gpu_hours', 0):,.2f}",
        " · ".join(notes),
        f"数据更新于 {stats.get('updated_at', '-')}",
        make_monthly_figure(monthly_rows),
        make_node_gpu_figure(node_rows),
        node_rows,
    )
