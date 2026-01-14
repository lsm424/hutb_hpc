from dash import html
from dash_bootstrap_components import Input

def create_header(title="HUTB HPC Cluster"):
    return html.Header(
        [
            html.Div(
                [
                    html.Span([html.I(className="fa-solid fa-location-dot mr-2"), title])
                ],
                className="flex items-center gap-4 text-gray-400 text-sm"
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.I(className="fa-solid fa-search"),
                            Input(placeholder="全局搜索...", className="bg-transparent outline-none w-48")
                        ],
                        className="flex items-center gap-2 bg-gray-800 rounded px-3 py-1.5 text-sm text-gray-400"
                    ),
                    html.Button(
                        html.I(className="fa-solid fa-rotate-right text-gray-400 text-sm"),
                        id="btn-global-refresh",
                        className="w-8 h-8 rounded-full bg-gray-800 hover:bg-gray-700 flex items-center justify-center transition-colors"
                    ),
                    html.Button(
                        [
                            html.I(className="fa-solid fa-bell text-gray-400 text-sm"),
                            html.Span(className="absolute top-0 right-0 w-2 h-2 bg-red-500 rounded-full")
                        ],
                        className="w-8 h-8 rounded-full bg-gray-800 hover:bg-gray-700 flex items-center justify-center transition-colors relative"
                    )
                ],
                className="flex items-center gap-4"
            )
        ],
        id="header",
        className="h-16 bg-gray-900/50 backdrop-blur border-b border-gray-800 flex items-center justify-between px-6 sticky top-0 z-40"
    )
