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
    ], className="flex-1 ml-52 min-h-screen flex flex-col")
], className="bg-gray-950 text-gray-100 flex font-sans min-h-screen")

if __name__ == '__main__':
    import os
    import signal

    PID_FILE = './assets/hpc_dash.pid'

    def kill_prev_pid(pid_file):
        if os.path.isfile(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    prev_pid_str = f.read().strip()
                    if prev_pid_str:
                        prev_pid = int(prev_pid_str)
                        if prev_pid != os.getpid():
                            os.kill(prev_pid, signal.SIGTERM)
            except Exception as e:
                # Swallow all errors (process may not exist or not owned, etc.)
                pass

    def write_pid(pid_file):
        with open(pid_file, 'w+') as f:
            f.write(str(os.getpid()))

    kill_prev_pid(PID_FILE)
    write_pid(PID_FILE)
    app.run(debug=False, port=8050, host='0.0.0.0')
