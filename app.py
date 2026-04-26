from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

# ===== БАЗА =====
conn = sqlite3.connect("chat.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    receiver TEXT,
    text TEXT,
    file TEXT
)
""")

conn.commit()

# ===== ОНЛАЙН =====
online_users = set()

# ===== AUTH =====

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        try:
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (u, p))
            conn.commit()
            return redirect("/login")
        except:
            return "❌ Имя занято"

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        user = cur.fetchone()

        if user:
            session["user"] = u
            return redirect("/")
        else:
            return "❌ Неверный логин"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")


# ===== WEB =====
@app.route("/")
def index():
    if "user" not in session:
        return redirect("/login")
    return render_template("index.html", username=session["user"])


# ===== ПОИСК =====
@app.route("/search")
def search():
    q = request.args.get("q", "")
    cur.execute("SELECT username FROM users WHERE username LIKE ?", (f"%{q}%",))
    users = [u[0] for u in cur.fetchall()]
    return jsonify({"users": users})


# ===== ФАЙЛЫ =====
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return jsonify({"url": "/static/uploads/" + filename})


# ===== АВАТАР =====
@app.route("/avatar/<user>")
def avatar(user):
    return redirect(f"https://ui-avatars.com/api/?name={user}")


# ===== SOCKET =====

def get_room(a, b):
    return "_".join(sorted([a, b]))


@socketio.on("connect")
def on_connect():
    if "user" in session:
        online_users.add(session["user"])
        emit("online", list(online_users), broadcast=True)


@socketio.on("disconnect")
def on_disconnect():
    if "user" in session:
        online_users.discard(session["user"])
        emit("online", list(online_users), broadcast=True)


@socketio.on("join")
def join(data):
    user = data["user"]
    target = data["target"]

    room = get_room(user, target)
    join_room(room)

    # загрузка истории
    cur.execute("""
        SELECT sender, text, file FROM messages
        WHERE (sender=? AND receiver=?)
           OR (sender=? AND receiver=?)
        ORDER BY id ASC
    """, (user, target, target, user))

    for sender, text, file in cur.fetchall():
        emit("message", {
            "sender": sender,
            "text": text,
            "file": file
        })


@socketio.on("join_channel")
def join_channel(data):
    room = data["room"]
    join_room(room)

    # история канала
    cur.execute("""
        SELECT sender, text FROM messages
        WHERE receiver=?
        ORDER BY id ASC
    """, (room,))

    for sender, text in cur.fetchall():
        emit("message", {
            "sender": sender,
            "text": text
        })


@socketio.on("send_message")
def handle_message(data):
    sender = data["sender"]
    receiver = data["receiver"]

    text = data.get("text")
    file = data.get("file")

    room = get_room(sender, receiver)

    cur.execute("""
        INSERT INTO messages (sender, receiver, text, file)
        VALUES (?, ?, ?, ?)
    """, (sender, receiver, text, file))
    conn.commit()

    emit("message", {
        "sender": sender,
        "text": text,
        "file": file
    }, to=room)


# ===== ЗАПУСК =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
