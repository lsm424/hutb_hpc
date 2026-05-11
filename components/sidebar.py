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
                    dcc.Link(
                        [
                            html.I(className="fa-solid fa-calendar-day w-5 text-center"),
                            html.Span("日报"),
                        ],
                        href="/daily",
                        className="flex items-center gap-3 px-3 py-3 rounded-lg transition-colors nav-link",  # px-4 -> px-3
                        id="nav-daily"
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
    [Output(f"nav-{page}", "className") for page in ["dashboard", "jobs", "nodes", "daily", "users"]],
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
    for page in ["dashboard", "jobs", "nodes", "daily", "users"]:
        # Match logic
        is_active = False
        if page == "dashboard" and (pathname == "/" or pathname == "/dashboard"):
            is_active = True
        elif f"/{page}" in str(pathname):
            is_active = True

        if page == "users":
            # Use submenu styling for users
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


# Callback to toggle user submenu and update parent active state
@callback(
    Output("user-submenu", "style"),
    Output("user-menu-icon", "className"),
    Output("nav-users-parent", "className"),
    Input("nav-users-parent", "n_clicks"),
    Input("url", "pathname"),
    State("user-submenu", "style"),
)
def toggle_user_menu(n_clicks, pathname, current_style):
    # Base classes
    parent_base_class = "flex items-center gap-3 px-3 py-3 rounded-lg transition-colors cursor-pointer"
    parent_active_class = "bg-gray-800 text-white"
    parent_inactive_class = "text-gray-400 hover:bg-gray-800 hover:text-white"

    # Check if users page is active
    is_users_active = pathname and "/users" in pathname

    # Set parent active state
    if is_users_active:
        parent_class = f"{parent_base_class} {parent_active_class}"
    else:
        parent_class = f"{parent_base_class} {parent_inactive_class}"

    # Default: expanded if users page is active
    if n_clicks is None:
        if is_users_active:
            return {"height": "auto", "opacity": "1"}, "fa-solid fa-chevron-down ml-auto text-xs transition-transform", parent_class
        else:
            return {"height": "0px", "opacity": "0"}, "fa-solid fa-chevron-down ml-auto text-xs transition-transform -rotate-90", parent_class

    # Toggle based on clicks
    is_expanded = current_style and current_style.get("height") != "0px"

    if is_expanded:
        return {"height": "0px", "opacity": "0"}, "fa-solid fa-chevron-down ml-auto text-xs transition-transform -rotate-90", parent_class
    else:
        return {"height": "auto", "opacity": "1"}, "fa-solid fa-chevron-down ml-auto text-xs transition-transform", parent_class
