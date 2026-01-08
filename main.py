import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from components import sidebar, header
from service.hpc_manager import hpc_manager

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

if __name__ == '__main__':
    app.run(debug=False, port=8050)
