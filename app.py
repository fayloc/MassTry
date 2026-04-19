from flask import Flask, render_template, request
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config['SECRET_KEY'] = 'masstry_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

users = {}

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("join")
def handle_join(name):
    users[request.sid] = name
    send(f"🔵 {name} вошёл в чат", broadcast=True)

@socketio.on("message")
def handle_message(msg):
    name = users.get(request.sid, "Anon")
    send(f"{name}: {msg}", broadcast=True)

@socketio.on("disconnect")
def handle_disconnect():
    name = users.get(request.sid, "Anon")
    send(f"🔴 {name} вышел", broadcast=True)
    users.pop(request.sid, None)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
