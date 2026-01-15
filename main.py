import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from components import sidebar, header
from common import utils, cfg

# Initialize Dash app
app = dash.Dash(
    __name__, 
    use_pages=True, 
    external_scripts=[
        'https://cdn.tailwindcss.com', 
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/js/all.min.js'
    ],
    suppress_callback_exceptions=True,
    title='HPC管理系统'  # 设置网站标题

)
app._favicon = "logo.jpg"  # 设置浏览器标签页图标


app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    # Sidebar
    sidebar.create_sidebar(),
    # Main Content
    html.Div([
        header.create_header(),
        dash.page_container
    ], className="flex-1 ml-52 min-h-screen flex flex-col")
], className="bg-gray-950 text-gray-100 flex font-sans min-h-screen")

if __name__ == '__main__':
    utils.kill_prev_pid(cfg.get('service', 'pid_file'))
    utils.write_pid(cfg.get('service', 'pid_file'))
    utils.kill_process_on_port(cfg.get('service', 'port'))
    app.run(debug=False, port=cfg.get('service', 'port'), host='0.0.0.0')
