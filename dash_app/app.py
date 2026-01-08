import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from components import sidebar, header

# Initialize Dash app
app = dash.Dash(
    __name__, 
    use_pages=True, 
    external_scripts=[
        'https://cdn.tailwindcss.com', 
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/js/all.min.js'
    ],
    suppress_callback_exceptions=True
)

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    # Sidebar
    sidebar.create_sidebar(),
    # Main Content
    html.Div([
        header.create_header(),
        dash.page_container
    ], className="flex-1 ml-64 min-h-screen flex flex-col")
], className="bg-gray-950 text-gray-100 flex font-sans min-h-screen")

# Callback to handle active state of nav links
@app.callback(
    [Output(f"nav-{page}", "className") for page in ["dashboard", "jobs", "nodes", "daily"]],
    [Input("url", "pathname")]
)
def update_active_links(pathname):
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

if __name__ == '__main__':
    app.run(debug=True, port=8050)
