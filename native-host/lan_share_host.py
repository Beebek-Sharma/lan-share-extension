import sys, os, json, struct, subprocess, socket, time

# Native Messaging helpers

def send_message(msg: dict):
    data = json.dumps(msg).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) == 0:
        return None
    msg_len = struct.unpack('<I', raw_len)[0]
    data = sys.stdin.buffer.read(msg_len)
    if not data:
        return None
    return json.loads(data.decode('utf-8'))


def is_port_open(port: int, host: str = '127.0.0.1', timeout: float = 0.2) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _append(host_log: str, line: str):
    try:
        with open(host_log, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception:
        pass


def _read_tail(path: str, max_bytes: int = 2000) -> str | None:
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read().decode('utf-8', errors='ignore')
            return data
    except Exception:
        return None


def start_server(project_dir: str, port: int = 5000) -> dict:
    # If already up, short-circuit
    if is_port_open(port):
        return {"started": True, "ready": True, "alreadyRunning": True, "port": port}

    py = sys.executable or 'python'
    server_py = os.path.join(project_dir, 'server.py')
    if not os.path.exists(server_py):
        return {"started": False, "error": f"server.py not found in {project_dir}"}

    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    host_log = os.path.join(project_dir, 'lan_share_host.log')
    server_log = os.path.join(project_dir, 'lan_share_server.log')
    _append(host_log, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] start requested on port {port} using {py}")

    try:
        # Redirect server stdout/stderr to a logfile for diagnostics
        logf = open(server_log, 'ab', buffering=0)
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        subprocess.Popen([py, server_py, '--port', str(port)], cwd=project_dir,
                          stdout=logf, stderr=logf,
                          creationflags=flags, env=env)
    except Exception as e:
        _append(host_log, f"spawn failed: {e}")
        return {"started": False, "error": f"spawn failed: {e}"}

    # Wait for readiness up to ~8 seconds
    deadline = time.time() + 8.0
    while time.time() < deadline:
        if is_port_open(port):
            return {"started": True, "ready": True, "port": port}
        time.sleep(0.3)

    log_tail = _read_tail(server_log)
    if log_tail:
        _append(host_log, "timeout waiting for server; tail follows:\n" + log_tail)
    return {"started": True, "ready": False, "port": port, "error": "timeout", "logTail": (log_tail or None)}


def find_pid_by_port(port: int) -> int | None:
    """Find PID listening on the given TCP port (best-effort, Windows/Unix)."""
    try:
        if os.name == 'nt':
            out = subprocess.check_output(['netstat', '-ano', '-p', 'tcp'], text=True, errors='ignore')
            target = f":{port}"
            for line in out.splitlines():
                if 'LISTENING' in line and target in line:
                    parts = line.split()
                    pid = int(parts[-1])
                    return pid
        else:
            # lsof is common on macOS/Linux
            out = subprocess.check_output(['lsof', '-i', f':{port}', '-sTCP:LISTEN', '-Pn'], text=True, errors='ignore')
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    return int(parts[1])
    except Exception:
        pass
    return None


def stop_server(port: int = 5000) -> dict:
    if not is_port_open(port):
        return {"stopped": True, "alreadyStopped": True, "port": port}
    pid = find_pid_by_port(port)
    if pid is None:
        return {"stopped": False, "error": "pid-not-found", "port": port}
    try:
        if os.name == 'nt':
            subprocess.check_call(['taskkill', '/PID', str(pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, 15)  # SIGTERM
    except Exception as e:
        return {"stopped": False, "error": f"kill-failed: {e}", "port": port, "pid": pid}
    # small grace period
    for _ in range(10):
        if not is_port_open(port):
            return {"stopped": True, "port": port, "pid": pid}
        time.sleep(0.2)
    return {"stopped": False, "error": "port-still-open", "port": port, "pid": pid}


def main():
    # project_dir is parent of this file's directory
    here = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.abspath(os.path.join(here, os.pardir))

    req = read_message()
    if not req:
        # No message; gracefully exit
        return

    action = req.get('action')
    port = int(req.get('port') or 5000)
    if action == 'start':
        res = start_server(project_dir, port=port)
        send_message(res)
    elif action == 'stop':
        res = stop_server(port=port)
        send_message(res)
    else:
        send_message({"error": "unknown action", "received": req})


if __name__ == '__main__':
    # Ensure stdio is in binary mode on Windows
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    main()
