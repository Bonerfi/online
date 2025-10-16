import os
import socket
import threading
import pickle

HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', 5555))  # Render sets PORT automatically

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

clients = []
players = {}

def handle_client(conn, addr):
    player_id = addr[1]
    players[player_id] = {"x": 100, "y": 100, "direction": "down"}
    print(f"[CONNECTED] Player {player_id}")
    clients.append(conn)

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            
            try:
                update = pickle.loads(data)
            except Exception as e:
                print(f"[WARN] Non-pickle data from {addr}: {e}")
                continue  # Skip this message
            
            players[player_id].update(update)


            # Broadcast
            state_data = pickle.dumps(players)
            for c in clients:
                c.sendall(state_data)
    finally:
        print(f"[DISCONNECTED] Player {player_id}")
        clients.remove(conn)
        del players[player_id]
        conn.close()

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

