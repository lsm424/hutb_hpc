from dash import html, dcc, callback, Output, Input, State

def create_sidebar():
    return html.Aside(
        [
            # Logo / Brand
            html.Div(
                [
                    html.Img(
                        src="/assets/logo1.png",
                        className="h-8 w-8 mr-3",
                        style={
                            "objectFit": "contain",
                            "background": "transparent",     # 保证背景透明
                            "backgroundColor": "transparent" # 保证dash inline style为透明
                        }
                    ),
                    html.Span("HPC Admin", className="font-bold text-lg tracking-wide"),
                ],
                className="h-16 flex items-center px-4 border-b border-gray-800"  # px-6 -> px-4
            ),
            # Navigation
            html.Nav(
                [
                    dcc.Link(
                        [
                            html.I(className="fa-solid fa-gauge w-5 text-center"),
                            html.Span("总览"),
                        ],
                        href="/",
                        className="flex items-center gap-3 px-3 py-3 rounded-lg transition-colors nav-link",  # px-4 -> px-3
                        id="nav-dashboard"
                    ),
                    dcc.Link(
                        [
                            html.I(className="fa-solid fa-network-wired w-5 text-center"),
                            html.Span("节点管理"),
                        ],
                        href="/nodes",
                        className="flex items-center gap-3 px-3 py-3 rounded-lg transition-colors nav-link",  # px-4 -> px-3
                        id="nav-nodes"
                    ),
                    dcc.Link(
                        [
                            html.I(className="fa-solid fa-list-check w-5 text-center"),
                            html.Span("作业管理"),
                        ],
                        href="/jobs",
                        className="flex items-center gap-3 px-3 py-3 rounded-lg transition-colors nav-link",  # px-4 -> px-3
                        id="nav-jobs"
                    ),
                    # 用户管理二级菜单
                    html.Div(
                        [
                            # 一级菜单标题
                            html.Div(
                                [
                                    html.I(className="fa-solid fa-users w-5 text-center"),
                                    html.Span("用户管理"),
                                    html.I(className="fa-solid fa-chevron-down ml-auto text-xs transition-transform", id="user-menu-icon"),
                                ],
                                className="flex items-center gap-3 px-3 py-3 rounded-lg transition-colors cursor-pointer text-gray-400 hover:bg-gray-800 hover:text-white",
                                id="nav-users-parent"
                            ),
                            # 二级菜单
                            html.Div(
                                [
                                    dcc.Link(
                                        [
                                            html.I(className="fa-solid fa-circle text-[6px] w-5 text-center"),
                                            html.Span("平台用户查看"),
                                        ],
                                        href="/users",
                                        className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors nav-link text-sm",
                                        id="nav-users"
                                    ),
                                ],
                                className="ml-4 mt-1 space-y-1 overflow-hidden transition-all",
                                id="user-submenu"
                            ),
                        ],
                        className="space-y-1"
                    ),
                    # 数据统计二级菜单
                    html.Div(
                        [
                            # 一级菜单标题
                            html.Div(
                                [
                                    html.I(className="fa-solid fa-chart-column w-5 text-center"),
                                    html.Span("数据统计"),
                                    html.I(className="fa-solid fa-chevron-down ml-auto text-xs transition-transform", id="stats-menu-icon"),
                                ],
                                className="flex items-center gap-3 px-3 py-3 rounded-lg transition-colors cursor-pointer text-gray-400 hover:bg-gray-800 hover:text-white",
                                id="nav-stats-parent"
                            ),
                            # 二级菜单
                            html.Div(
                                [
                                    dcc.Link(
                                        [
                                            html.I(className="fa-solid fa-circle text-[6px] w-5 text-center"),
                                            html.Span("日报"),
                                        ],
                                        href="/daily",
                                        className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors nav-link text-sm",
                                        id="nav-daily"
                                    ),
                                    dcc.Link(
                                        [
                                            html.I(className="fa-solid fa-circle text-[6px] w-5 text-center"),
                                            html.Span("共享统计"),
                                        ],
                                        href="/share-stats",
                                        className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors nav-link text-sm",
                                        id="nav-share-stats"
                                    ),
                                ],
                                className="ml-4 mt-1 space-y-1 overflow-hidden transition-all",
                                id="stats-submenu"
                            ),
                        ],
                        className="space-y-1"
                    ),
                ],
                className="flex-1 px-2 py-6 space-y-2"  # px-4 -> px-2
            ),
            # User Profile
            html.Div(
                html.Div(
                    [
                        html.Img(src="https://ui-avatars.com/api/?name=Admin&background=random", className="w-8 h-8 rounded-full"),
                        html.Div(
                            [
                                html.Div("Administrator", className="font-medium"),
                                html.Div("Online", className="text-xs text-gray-500"),
                            ],
                            className="text-sm"
                        )
                    ],
                    className="flex items-center gap-3 px-3 py-2"  # px-4 -> px-3
                ),
                className="p-4 border-t border-gray-800"
            )
        ],
        className="w-52 fixed inset-y-0 left-0 bg-gray-900 border-r border-gray-800 flex flex-col z-50"
    )


# Callback to handle active state of nav links
@callback(
    [Output(f"nav-{page}", "className") for page in ["dashboard", "jobs", "nodes", "daily", "share-stats", "users"]],
    [Input("url", "pathname"), Input('url', 'search')]
)
def update_active_links(pathname, search):
    base_class = "flex items-center gap-3 px-3 py-3 rounded-lg transition-colors nav-link"
    active_class = "bg-gray-800 text-white"
    inactive_class = "text-gray-400 hover:bg-gray-800 hover:text-white"

    # Submenu base class (smaller padding for submenu items)
    submenu_base_class = "flex items-center gap-3 px-3 py-2 rounded-lg transition-colors nav-link text-sm"

    # Normalize pathname
    if pathname == "/" or pathname is None:
        pathname = "/dashboard" # Treat root as dashboard
    elif pathname.endswith("/"):
        pathname = pathname[:-1]

    outputs = []
    for page in ["dashboard", "jobs", "nodes", "daily", "share-stats", "users"]:
        # Match logic
        is_active = False
        if page == "dashboard" and (pathname == "/" or pathname == "/dashboard"):
            is_active = True
        elif f"/{page}" in str(pathname):
            is_active = True

        if page in ("users", "daily", "share-stats"):
            # Use submenu styling for submenu items
            if is_active:
                outputs.append(f"{submenu_base_class} {active_class}")
            else:
                outputs.append(f"{submenu_base_class} {inactive_class}")
        else:
            if is_active:
                outputs.append(f"{base_class} {active_class}")
            else:
                outputs.append(f"{base_class} {inactive_class}")
    return outputs


def _make_submenu_toggler(parent_id, submenu_id, icon_id, active_paths):
    """为一组一级/二级菜单注册展开折叠与高亮回调"""

    @callback(
        Output(submenu_id, "style"),
        Output(icon_id, "className"),
        Output(parent_id, "className"),
        Input(parent_id, "n_clicks"),
        Input("url", "pathname"),
        State(submenu_id, "style"),
    )
    def toggle_submenu(n_clicks, pathname, current_style):
        # Base classes
        parent_base_class = "flex items-center gap-3 px-3 py-3 rounded-lg transition-colors cursor-pointer"
        parent_active_class = "bg-gray-800 text-white"
        parent_inactive_class = "text-gray-400 hover:bg-gray-800 hover:text-white"

        icon_down = "fa-solid fa-chevron-down ml-auto text-xs transition-transform"
        icon_folded = "fa-solid fa-chevron-down ml-auto text-xs transition-transform -rotate-90"

        # Check if any child page is active
        is_active = bool(pathname) and any(p in pathname for p in active_paths)

        # Set parent active state
        if is_active:
            parent_class = f"{parent_base_class} {parent_active_class}"
        else:
            parent_class = f"{parent_base_class} {parent_inactive_class}"

        # Default: expanded if child page is active
        if n_clicks is None:
            if is_active:
                return {"height": "auto", "opacity": "1"}, icon_down, parent_class
            else:
                return {"height": "0px", "opacity": "0"}, icon_folded, parent_class

        # Toggle based on clicks
        is_expanded = current_style and current_style.get("height") != "0px"

        if is_expanded:
            return {"height": "0px", "opacity": "0"}, icon_folded, parent_class
        else:
            return {"height": "auto", "opacity": "1"}, icon_down, parent_class

    return toggle_submenu


# 用户管理二级菜单展开/折叠
_make_submenu_toggler("nav-users-parent", "user-submenu", "user-menu-icon", ["/users"])
# 数据统计二级菜单展开/折叠
_make_submenu_toggler("nav-stats-parent", "stats-submenu", "stats-menu-icon", ["/daily", "/share-stats"])
