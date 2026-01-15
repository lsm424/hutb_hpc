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
    # INSERT_YOUR_CODE
    # 兼容给windows和linux，启动前杀死占用端口8050的进程（优先于PID文件）
    def kill_process_on_port(port):
        import sys
        import subprocess

        try:
            if sys.platform.startswith('win'):
                # windows
                # 查询占用端口的PID
                cmd_find = f'netstat -ano | findstr :{port}'
                output = subprocess.check_output(cmd_find, shell=True, text=True)
                for line in output.strip().splitlines():
                    parts = line.split()
                    # 最后一项为PID
                    if len(parts) >= 5:
                        pid = int(parts[-1])
                        if pid != os.getpid():
                            try:
                                subprocess.call(f'taskkill /PID {pid} /F', shell=True)
                            except Exception:
                                pass
            else:
                # unix/linux/mac
                cmd = f"lsof -i :{port} -t"
                result = subprocess.check_output(cmd, shell=True, text=True)
                for line in result.strip().splitlines():
                    pid = int(line.strip())
                    if pid != os.getpid():
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except Exception:
                            pass
        except Exception:
            # 忽略所有异常
            pass

    kill_process_on_port(8050)
    app.run(debug=False, port=8050, host='0.0.0.0')
