from dash import html, dcc, callback, Output, Input

def create_sidebar():
    return html.Aside(
        [
            # Logo / Brand
            html.Div(
                [
                    html.I(className="fa-solid fa-server text-indigo-500 text-xl mr-3"),
                    html.Span("HPC Admin", className="font-bold text-lg tracking-wide"),
                ],
                className="h-16 flex items-center px-6 border-b border-gray-800"
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
                        className="flex items-center gap-3 px-4 py-3 rounded-lg transition-colors nav-link",
                        id="nav-dashboard"
                    ),
                    dcc.Link(
                        [
                            html.I(className="fa-solid fa-list-check w-5 text-center"),
                            html.Span("作业管理"),
                        ],
                        href="/jobs",
                        className="flex items-center gap-3 px-4 py-3 rounded-lg transition-colors nav-link",
                        id="nav-jobs"
                    ),
                    dcc.Link(
                        [
                            html.I(className="fa-solid fa-network-wired w-5 text-center"),
                            html.Span("节点管理"),
                        ],
                        href="/nodes",
                        className="flex items-center gap-3 px-4 py-3 rounded-lg transition-colors nav-link",
                        id="nav-nodes"
                    ),
                    dcc.Link(
                        [
                            html.I(className="fa-solid fa-calendar-day w-5 text-center"),
                            html.Span("日报"),
                        ],
                        href="/daily",
                        className="flex items-center gap-3 px-4 py-3 rounded-lg transition-colors nav-link",
                        id="nav-daily"
                    ),
                ],
                className="flex-1 px-4 py-6 space-y-2"
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
                    className="flex items-center gap-3 px-4 py-2"
                ),
                className="p-4 border-t border-gray-800"
            )
        ],
        className="w-64 fixed inset-y-0 left-0 bg-gray-900 border-r border-gray-800 flex flex-col z-50"
    )


# Callback to handle active state of nav links
@callback(
    [Output(f"nav-{page}", "className") for page in ["dashboard", "jobs", "nodes", "daily"]],
    [Input("url", "pathname"), Input('url', 'search')]
)
def update_active_links(pathname, search):
    base_class = "flex items-center gap-3 px-4 py-3 rounded-lg transition-colors nav-link"
    active_class = "bg-gray-800 text-white"
    inactive_class = "text-gray-400 hover:bg-gray-800 hover:text-white"
    
    # Normalize pathname
    if pathname == "/" or pathname is None:
        pathname = "/dashboard" # Treat root as dashboard
    elif pathname.endswith("/"):
        pathname = pathname[:-1]
        
    outputs = []
    for page in ["dashboard", "jobs", "nodes", "daily"]:
        # Match logic
        is_active = False
        if page == "dashboard" and (pathname == "/" or pathname == "/dashboard"):
            is_active = True
        elif f"/{page}" in str(pathname):
            is_active = True
            
        if is_active:
            outputs.append(f"{base_class} {active_class}")
        else:
            outputs.append(f"{base_class} {inactive_class}")
    return outputs
