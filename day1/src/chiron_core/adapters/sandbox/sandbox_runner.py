import sys
import os
import traceback
import socket


def enforce_network_blocking():
    # monkeypatch sul modulo socket per impedire chiamate esterne a runtime
    def _blocked(*args, **kwargs):
        raise PermissionError("Sandbox Security: Network access is disabled.")

    socket.socket = _blocked
    socket.create_connection = _blocked
    socket.getaddrinfo = _blocked
    socket.gethostbyname = _blocked
    socket.gethostbyname_ex = _blocked
    socket.getnameinfo = _blocked


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: sandbox_runner.py <script_path>\n")
        sys.exit(1)

    script_path = sys.argv[1]
    if not os.path.exists(script_path):
        sys.stderr.write(f"Script not found: {script_path}\n")
        sys.exit(1)

    # blocco la rete prima di importare o far partire il codice utente
    enforce_network_blocking()

    with open(script_path, "r", encoding="utf-8") as f:
        code_content = f.read()

    execution_globals = {
        "__name__": "__main__",
        "__file__": os.path.abspath(script_path),
        "__doc__": None,
    }

    try:
        compiled_code = compile(code_content, script_path, "exec")
        exec(compiled_code, execution_globals)
    except PermissionError as e:
        sys.stderr.write(f"SecurityError: {e}\n")
        sys.exit(2)
    except Exception:
        # stampo il traceback su stderr così l'agente può leggerlo e autocorreggersi
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
