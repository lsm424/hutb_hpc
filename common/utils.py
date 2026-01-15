import os
import signal

def Unit2int(unit: str) -> float:
    unit = unit.strip()
    "TiB, GiB, MiB, KiB转GiB"
    if unit.endswith('TiB'):
        return float(unit[:-3]) * 1024
    elif unit.endswith('GiB'):
        return float(unit[:-3])
    elif unit.endswith('MiB'):
        return float(unit[:-3]) * 1024 * 1024
    elif unit.endswith('KiB'):
        return float(unit[:-3]) * 1024

def search_params(search: str) -> dict:
    parameters = {}
    search = search.lstrip('?')
    try:
        for slice in search.split("&"):
            try:
                x, y = slice.split("=")
                parameters[x] = y
            except:
                pass
    except:
        pass
    return parameters



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