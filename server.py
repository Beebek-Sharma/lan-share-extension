# server.py
from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, join_room, emit
import qrcode
import os
import socket
import argparse
from collections import defaultdict

app = Flask(__name__, static_folder='static')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Track usernames per room so clients can show names
rooms = defaultdict(dict)  # room -> { sid: name }
sid_to_room = {}

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't actually send packets; used to determine local IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

@app.route('/')
def index():
    return send_from_directory('static', 'client.html')

@app.route('/qr.png')
def qr_image():
    # Serve the generated QR code file if present
    try:
        return send_from_directory('.', 'lan_share_qr.png')
    except Exception:
        return ('', 404)

@socketio.on('join-room')
def handle_join(data):
    room = data.get('room', 'default')
    name = data.get('name') or f"User-{request.sid[-4:]}"
    join_room(room)
    rooms[room][request.sid] = name
    sid_to_room[request.sid] = room
    # Send existing peers to the joiner (id + name)
    current = [{ 'id': sid, 'name': nm } for sid, nm in rooms[room].items() if sid != request.sid]
    emit('peers', current)
    # Notify others about this joiner
    emit('peer-joined', { 'id': request.sid, 'name': name }, room=room, include_self=False)

@socketio.on('signal')
def handle_signal(data):
    to = data.get('to')
    emit('signal', data, to=to)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    room = sid_to_room.pop(sid, None)
    name = None
    if room:
        name = rooms[room].pop(sid, None)
        if not rooms[room]:
            rooms.pop(room, None)
    payload = { 'id': sid, 'name': name } if name else sid
    if room:
        emit('peer-left', payload, room=room, include_self=False)
    else:
        emit('peer-left', payload, broadcast=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="LAN Share Signaling Server")
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--no-qr', action='store_true', help='Do not create QR file')
    args = parser.parse_args()

    ip = get_local_ip()
    port = args.port
    url = f"http://{ip}:{port}/"

    if not args.no_qr:
        try:
            img = qrcode.make(url)
            qr_file = "lan_share_qr.png"
            img.save(qr_file)
            print(f"📱 QR code saved as {qr_file} (points to {url})")
        except Exception as e:
            print("⚠️ Could not generate QR code:", e)

    print(f"\n🔗 Open on other devices: {url}\n")

    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
