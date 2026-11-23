from __future__ import annotations

import os
import re
import sqlite3
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATABASE = Path(os.environ.get("DATABASE") or (BASE_DIR / "notes.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB por petición
MAX_NOTE_CONTENT = 10_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notes_user_updated ON notes(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tags_user_name ON tags(user_id, name);
CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag_id);
"""


def init_db() -> None:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


init_db()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def current_user():
    if not hasattr(g, "user"):
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            g.user = get_db().execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if g.user is None:
                session.clear()
    return g.user


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Inicia sesión para continuar.", "info")
            target = request.full_path
            target = target.removesuffix("?")
            return redirect(url_for("login", next=target))
        return view(*args, **kwargs)

    return wrapped


def safe_next(target: str | None) -> str:
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("notes")


TAG_SPLITTER = re.compile(r"[,;]+")
LIKE_ESCAPE = " ESCAPE '\\'"


def normalize_tag(name: str) -> str:
    return " ".join(name.strip().lstrip("#").lower().split())


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for part in TAG_SPLITTER.split(raw):
        name = normalize_tag(part)
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def get_note(note_id: int):
    return get_db().execute(
        "SELECT * FROM notes WHERE id = ? AND user_id = ?",
        (note_id, current_user()["id"]),
    ).fetchone()


def note_tags(note_id: int) -> list[str]:
    rows = get_db().execute(
        """
        SELECT t.name
        FROM tags t
        JOIN note_tags nt ON nt.tag_id = t.id
        WHERE nt.note_id = ?
        ORDER BY t.name
        """,
        (note_id,),
    ).fetchall()
    return [row["name"] for row in rows]


def all_user_tags():
    return get_db().execute(
        """
        SELECT t.name, COUNT(nt.note_id) AS count
        FROM tags t
        LEFT JOIN note_tags nt ON nt.tag_id = t.id
        WHERE t.user_id = ?
        GROUP BY t.id
        HAVING count > 0
        ORDER BY count DESC, t.name
        """,
        (current_user()["id"],),
    ).fetchall()


def replace_note_tags(note_id: int, names: list[str]) -> None:
    db = get_db()
    user_id = current_user()["id"]
    db.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    for name in names:
        db.execute(
            "INSERT OR IGNORE INTO tags (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )
        tag_id = db.execute(
            "SELECT id FROM tags WHERE user_id = ? AND name = ?", (user_id, name)
        ).fetchone()["id"]
        db.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (note_id, tag_id),
        )
    cleanup_unused_tags()


def cleanup_unused_tags() -> None:
    get_db().execute(
        """
        DELETE FROM tags
        WHERE user_id = ?
          AND NOT EXISTS (SELECT 1 FROM note_tags nt WHERE nt.tag_id = tags.id)
        """,
        (current_user()["id"],),
    )


def validate_note_form():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    tags_raw = request.form.get("tags", "")
    errors = []
    if not title:
        errors.append("El título es obligatorio.")
    elif len(title) > 200:
        errors.append("El título no puede superar los 200 caracteres.")
    if not content:
        errors.append("El contenido no puede estar vacío.")
    if len(content) > MAX_NOTE_CONTENT:
        errors.append(
            f"El contenido no puede superar los {MAX_NOTE_CONTENT} caracteres."
        )
    if len(tags_raw) > 500:
        errors.append("Las etiquetas no pueden superar los 500 caracteres.")
    return (
        title,
        content,
        tags_raw,
        parse_tags(tags_raw),
        errors,
    )


@app.route("/")
def index():
    return redirect(url_for("notes") if current_user() else url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("notes"))

    username = ""
    if request.method == "POST":
        username = " ".join(request.form.get("username", "").split())
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []
        if len(username) < 3 or len(username) > 50:
            errors.append("El usuario debe tener entre 3 y 50 caracteres.")
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres.")
        if password != confirm:
            errors.append("Las contraseñas no coinciden.")
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            try:
                get_db().execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                get_db().commit()
            except sqlite3.IntegrityError:
                flash("Ese nombre de usuario ya está en uso.", "error")
            else:
                flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
                return redirect(url_for("login"))

    return render_template("register.html", username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("notes"))

    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"¡Hola, {user['username']}!", "success")
            return redirect(safe_next(request.args.get("next")))
        flash("Usuario o contraseña incorrectos.", "error")

    return render_template("login.html", username=username)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


@app.route("/notes")
@login_required
def notes():
    query = request.args.get("q", "").strip()
    tag = normalize_tag(request.args.get("tag", ""))
    user_id = current_user()["id"]

    clauses = ["n.user_id = ?"]
    params: list[str | int] = [user_id]

    if query:
        pattern = like_pattern(query)
        clauses.append(
            "("
            f"n.title LIKE ?{LIKE_ESCAPE}"
            f" OR n.content LIKE ?{LIKE_ESCAPE}"
            " OR EXISTS ("
            "   SELECT 1 FROM note_tags nt JOIN tags t ON t.id = nt.tag_id"
            f"   WHERE nt.note_id = n.id AND t.user_id = ? AND t.name LIKE ?{LIKE_ESCAPE}"
            " )"
            ")"
        )
        params.extend([pattern, pattern, user_id, pattern])

    if tag:
        clauses.append(
            "EXISTS ("
            " SELECT 1 FROM note_tags nt JOIN tags t ON t.id = nt.tag_id"
            " WHERE nt.note_id = n.id AND t.user_id = ? AND t.name = ?"
            ")"
        )
        params.extend([user_id, tag])

    rows = get_db().execute(
        f"SELECT n.* FROM notes n WHERE {' AND '.join(clauses)}"
        " ORDER BY n.updated_at DESC, n.id DESC",
        params,
    ).fetchall()

    notes_list = [{"note": row, "tags": note_tags(row["id"])} for row in rows]
    return render_template(
        "notes.html",
        notes=notes_list,
        q=query,
        tag=tag,
        tags=all_user_tags(),
    )


@app.route("/notes/new", methods=["GET", "POST"])
@login_required
def new_note():
    values = {"title": "", "content": "", "tags": ""}

    if request.method == "POST":
        title, content, tags_raw, parsed_tags, errors = validate_note_form()
        values = {"title": title, "content": content, "tags": tags_raw}
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            db = get_db()
            cursor = db.execute(
                "INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)",
                (current_user()["id"], title, content),
            )
            replace_note_tags(cursor.lastrowid, parsed_tags)
            db.commit()
            flash("Nota creada.", "success")
            return redirect(url_for("note_detail", note_id=cursor.lastrowid))

    return render_template(
        "note_form.html",
        heading="Nueva nota",
        action=url_for("new_note"),
        note=None,
        values=values,
    )


@app.route("/notes/<int:note_id>")
@login_required
def note_detail(note_id: int):
    note = get_note(note_id)
    if note is None:
        abort(404)
    return render_template("note_detail.html", note=note, tags=note_tags(note_id))


@app.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
@login_required
def edit_note(note_id: int):
    note = get_note(note_id)
    if note is None:
        abort(404)

    if request.method == "POST":
        title, content, tags_raw, parsed_tags, errors = validate_note_form()
        values = {"title": title, "content": content, "tags": tags_raw}
        if errors:
            for error in errors:
                flash(error, "error")
        else:
            db = get_db()
            db.execute(
                "UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP"
                " WHERE id = ? AND user_id = ?",
                (title, content, note_id, current_user()["id"]),
            )
            replace_note_tags(note_id, parsed_tags)
            db.commit()
            flash("Nota actualizada.", "success")
            return redirect(url_for("note_detail", note_id=note_id))
    else:
        values = {
            "title": note["title"],
            "content": note["content"],
            "tags": ", ".join(note_tags(note_id)),
        }

    return render_template(
        "note_form.html",
        heading="Editar nota",
        action=url_for("edit_note", note_id=note_id),
        note=note,
        values=values,
    )


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(note_id: int):
    if get_note(note_id) is None:
        abort(404)
    db = get_db()
    db.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, current_user()["id"]))
    cleanup_unused_tags()
    db.commit()
    flash("Nota eliminada.", "success")
    return redirect(url_for("notes"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
