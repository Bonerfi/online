import socket
import threading
import pickle
import time
import random

HOST = '0.0.0.0'
PORT = 5555

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

clients = []
players = {}   # {player_id: {"x":..., "y":..., "direction":..., "health":..., "speed":..., "rapid":...}}
bullets = []   # [{"x":..., "y":..., "dx":..., "dy":..., "owner":...}]
powerups = []  # [{"x":..., "y":..., "type":...}]

MAP_WIDTH, MAP_HEIGHT = 1280, 720

# --- Client Handling ---
def handle_client(conn, addr):
    player_id = addr[1]
    players[player_id] = {
        "x": random.randint(100, 500),
        "y": random.randint(100, 500),
        "direction": "down",
        "health": 100,
        "speed": 5,
        "rapid": False
    }
    print(f"[CONNECTED] Player {player_id}")
    clients.append(conn)

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break

            update = pickle.loads(data)

            if update.get("type") == "player_update":
                players[player_id].update(update["data"])

            elif update.get("type") == "shoot":
                shoot_bullet(player_id)

            broadcast_state()
    finally:
        print(f"[DISCONNECTED] Player {player_id}")
        if conn in clients:
            clients.remove(conn)
        if player_id in players:
            del players[player_id]
        conn.close()

# --- Bullet Logic ---
def shoot_bullet(player_id):
    player = players[player_id]
    x, y = player["x"], player["y"]
    direction = player["direction"]
    speed = 10
    dx, dy = 0, 0
    if direction == "up": dy = -speed
    elif direction == "down": dy = speed
    elif direction == "left": dx = -speed
    elif direction == "right": dx = speed

    bullets.append({"x": x, "y": y, "dx": dx, "dy": dy, "owner": player_id})


# --- Broadcast Game State ---
def broadcast_state():
    state_data = pickle.dumps({
        "players": players,
        "bullets": bullets,
        "powerups": powerups
    })
    for c in clients[:]:
        try:
            c.sendall(state_data)
        except:
            if c in clients:
                clients.remove(c)

# --- Game Loop Threads ---
def bullet_updater():
    while True:
        time.sleep(0.02)
        to_remove = []

        for b in bullets[:]:
            b["x"] += b["dx"]
            b["y"] += b["dy"]

            if not (0 <= b["x"] <= MAP_WIDTH and 0 <= b["y"] <= MAP_HEIGHT):
                to_remove.append(b)
                continue

            for pid, pdata in players.items():
                if pid == b["owner"]:
                    continue
                px, py = pdata["x"], pdata["y"]
                if (px < b["x"] < px + 48) and (py < b["y"] < py + 48):
                    pdata["health"] -= 25
                    to_remove.append(b)
                    print(f"[HIT] Player {pid} by {b['owner']} → {pdata['health']} HP")
                    if pdata["health"] <= 0:
                        pdata["health"] = 100
                        pdata["x"], pdata["y"] = random.randint(100, 500), random.randint(100, 500)
                        pdata["speed"] = 5
                        pdata["rapid"] = False
                        print(f"[RESPAWN] Player {pid}")
                    break

        for b in to_remove:
            if b in bullets:
                bullets.remove(b)

        broadcast_state()


def powerup_spawner():
    """Periodically spawns random power-ups."""
    while True:
        time.sleep(5)
        if len(powerups) < 5:  # limit number on map
            x = random.randint(50, MAP_WIDTH - 50)
            y = random.randint(50, MAP_HEIGHT - 50)
            ptype = random.choice(["health", "speed", "rapid"])
            powerups.append({"x": x, "y": y, "type": ptype})
            print(f"[SPAWN] Power-up {ptype} at ({x}, {y})")
        broadcast_state()


def powerup_checker():
    """Check if any player picks up a power-up."""
    while True:
        time.sleep(0.1)
        for pid, pdata in list(players.items()):
            px, py = pdata["x"], pdata["y"]
            for p in powerups[:]:
                if (px < p["x"] < px + 48) and (py < p["y"] < py + 48):
                    # Apply effect
                    if p["type"] == "health":
                        pdata["health"] = min(100, pdata["health"] + 30)
                    elif p["type"] == "speed":
                        pdata["speed"] = 8
                        threading.Timer(5, lambda: pdata.update({"speed": 5})).start()
                    elif p["type"] == "rapid":
                        pdata["rapid"] = True
                        threading.Timer(5, lambda: pdata.update({"rapid": False})).start()

                    powerups.remove(p)
                    print(f"[PICKUP] Player {pid} got {p['type']}")
                    broadcast_state()
                    break

# --- Start Threads ---
threading.Thread(target=bullet_updater, daemon=True).start()
threading.Thread(target=powerup_spawner, daemon=True).start()
threading.Thread(target=powerup_checker, daemon=True).start()

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
