import asyncio
import json
import random
import string
import websockets
import http

# --- MONKEYPATCH FOR RENDER HEALTH CHECKS (HEAD / GET) ---
import websockets.http11
from websockets.http11 import Request, parse_line, parse_headers, d
from websockets.datastructures import Headers
from websockets.http11 import Response

@classmethod
def custom_parse(cls, read_line):
    try:
        request_line = yield from parse_line(read_line)
    except EOFError as exc:
        raise EOFError("connection closed while reading HTTP request line") from exc

    try:
        method, raw_path, protocol = request_line.split(b" ", 2)
    except ValueError:
        raise ValueError(f"invalid HTTP request line: {d(request_line)}") from None
        
    if protocol != b"HTTP/1.1":
        raise ValueError(f"unsupported protocol; expected HTTP/1.1: {d(request_line)}")
        
    # Allow both GET and HEAD
    if method not in (b"GET", b"HEAD"):
        raise ValueError(f"unsupported HTTP method; expected GET; got {d(method)}")
        
    path = raw_path.decode("ascii", "surrogateescape")
    headers = yield from parse_headers(read_line)

    if "Transfer-Encoding" in headers:
        raise NotImplementedError("transfer codings aren't supported")

    if "Content-Length" in headers:
        if int(headers["Content-Length"]) != 0:
            raise ValueError("unsupported request body")

    req = cls(path, headers)
    req.method = method.decode("ascii") # Store method
    return req

# Apply the monkeypatch
websockets.http11.Request.parse = custom_parse

# Persistent room database
# Each entry: { "code": { "host": websocket, "guest": websocket, "song": dict, "p1_ready": bool, "p2_ready": bool } }
ROOMS = {}

def generate_room_code():
    """Generates a unique 4-character alphanumeric Room Code."""
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in ROOMS:
            return code

async def broadcast_to_room(room_code, payload, sender_ws=None):
    """Broadcasts a JSON payload to all connected players in a room except the sender."""
    room = ROOMS.get(room_code)
    if not room:
        return
        
    targets = []
    if room["host"] and room["host"] != sender_ws:
        targets.append(room["host"])
    if room["guest"] and room["guest"] != sender_ws:
        targets.append(room["guest"])
        
    if targets:
        message = json.dumps(payload)
        await asyncio.gather(*(t.send(message) for t in targets), return_exceptions=True)

async def handle_connection(websocket, path=None):
    """Processes WebSocket packets and relays room updates."""
    print(f"[Server] Client connected: {websocket.remote_address}")
    
    current_room = None
    current_role = None
    
    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "CREATE":
                # Create a new room
                current_room = generate_room_code()
                current_role = "HOST"
                ROOMS[current_room] = {
                    "host": websocket,
                    "guest": None,
                    "song": None,
                    "p1_ready": False,
                    "p2_ready": False
                }
                await websocket.send(json.dumps({
                    "action": "ROOM_CREATED",
                    "code": current_room
                }))
                print(f"[Server] Room {current_room} successfully created by Host.")
                
            elif action == "JOIN":
                # Join an existing room
                code = data.get("code", "").upper()
                if code in ROOMS:
                    room = ROOMS[code]
                    if room["guest"] is None:
                        current_room = code
                        current_role = "GUEST"
                        room["guest"] = websocket
                        
                        # Notify joiner
                        await websocket.send(json.dumps({
                            "action": "ROOM_JOINED",
                            "code": code,
                            "role": "GUEST"
                        }))
                        
                        # Notify host that opponent connected
                        await room["host"].send(json.dumps({
                            "action": "PLAYER_JOINED",
                            "code": code
                        }))
                        print(f"[Server] Guest connected to Room {code}.")
                    else:
                        await websocket.send(json.dumps({
                            "action": "ERROR",
                            "message": "ROOM IS FULL"
                        }))
                else:
                    await websocket.send(json.dumps({
                        "action": "ERROR",
                        "message": "ROOM NOT FOUND"
                    }))
                    
            elif action == "SELECT_SONG":
                # Host selected track: relay parameters to guest
                if current_room and current_role == "HOST":
                    ROOMS[current_room]["song"] = data.get("song")
                    await broadcast_to_room(current_room, {
                        "action": "SONG_SELECTED",
                        "song": data.get("song")
                    }, sender_ws=websocket)
                    
            elif action == "CALIBRATE":
                # Relay calibration checklists to opponent
                if current_room:
                    await broadcast_to_room(current_room, {
                        "action": "OPPONENT_CALIBRATING",
                        "shoulders": data.get("shoulders", False),
                        "hips": data.get("hips", False),
                        "knees": data.get("knees", False),
                        "ankles": data.get("ankles", False),
                        "body_in_frame": data.get("body_in_frame", False)
                    }, sender_ws=websocket)
                    
            elif action == "TELEMETRY":
                # Relay active scoring and visual skeleton vectors
                if current_room:
                    await broadcast_to_room(current_room, {
                        "action": "OPPONENT_TELEMETRY",
                        "score": data.get("score", 0),
                        "combo": data.get("combo", 0),
                        "multiplier": data.get("multiplier", 1),
                        "energy": data.get("energy", 100.0),
                        "knee_angle": data.get("knee_angle", 180.0),
                        "back_angle": data.get("back_angle", 0.0),
                        "landmarks": data.get("landmarks"), # JSON serialized coordinates
                        "is_paused": data.get("is_paused", False)
                    }, sender_ws=websocket)
                    
    except websockets.exceptions.ConnectionClosed:
        print(f"[Server] Client disconnected abruptly: {websocket.remote_address}")
    finally:
        # Cleanup room on exit
        if current_room and current_room in ROOMS:
            room = ROOMS[current_room]
            
            if current_role == "HOST":
                # Host closed: close room and notify guest
                print(f"[Server] Host disconnected. Closing Room {current_room}.")
                if room["guest"]:
                    await room["guest"].send(json.dumps({
                        "action": "ROOM_CLOSED",
                        "message": "HOST DISCONNECTED"
                    }))
                ROOMS.pop(current_room, None)
            elif current_role == "GUEST":
                # Guest disconnected: notify host
                print(f"[Server] Guest disconnected from Room {current_room}.")
                room["guest"] = None
                room["p2_ready"] = False
                if room["host"]:
                    await room["host"].send(json.dumps({
                        "action": "OPPONENT_DISCONNECTED"
                    }))

def process_request(connection, request):
    """Handles HTTP health checks from Render's load balancer."""
    path = request.path
    method = getattr(request, 'method', 'GET')
    
    # Check if this is a WebSocket upgrade request
    is_websocket = "Upgrade" in request.headers and request.headers.get("Upgrade", "").lower() == "websocket"
    
    if path == "/" and not is_websocket:
        headers = Headers()
        headers['Content-Type'] = 'text/plain'
        
        body = b"PulseFit Arena Server Live"
        headers['Content-Length'] = str(len(body))
        
        if method == "HEAD":
            return Response(200, "OK", headers, b"")
        return Response(200, "OK", headers, body)
        
    return None # Fallback to normal websocket upgrade

async def main():
    # Run on local address and public ports
    port = 8765
    async with websockets.serve(handle_connection, "0.0.0.0", port, process_request=process_request):
        print(f"[Server] PulseFit Arena Room Coordinator running on ws://localhost:{port} ...")
        await asyncio.Future() # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Server] Shutdown complete.")
