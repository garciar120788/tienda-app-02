from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

MAX_INTENTOS = 5
VENTANA_MIN = 10


def _ip():
    return request.remote_addr or "desconocida"


def _destino_seguro(destino):
    """Evita redirecciones a otros sitios después del login."""
    if not destino:
        return url_for("inicio.index")
    p = urlparse(destino)
    if p.scheme or p.netloc or not destino.startswith("/"):
        return url_for("inicio.index")
    return destino


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("inicio.index"))

    if request.method == "POST":
        conn = get_db()
        fallidos = conn.execute(
            "SELECT count(*) AS n FROM intentos_login WHERE ip = %s AND fecha > now() - make_interval(mins => %s)",
            (_ip(), VENTANA_MIN),
        ).fetchone()["n"]
        if fallidos >= MAX_INTENTOS:
            flash(f"Demasiados intentos fallidos. Espera {VENTANA_MIN} minutos e intenta de nuevo.", "danger")
            return render_template("auth/login.html"), 429

        usuario = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        fila = conn.execute(
            "SELECT id, username, password_hash FROM usuarios WHERE username = %s", (usuario,)
        ).fetchone()

        if fila and check_password_hash(fila["password_hash"], password):
            conn.execute("DELETE FROM intentos_login WHERE ip = %s", (_ip(),))
            conn.commit()
            session.clear()
            session.permanent = True
            session["user_id"] = fila["id"]
            session["username"] = fila["username"]
            return redirect(_destino_seguro(request.args.get("next")))

        conn.execute("INSERT INTO intentos_login (ip) VALUES (%s)", (_ip(),))
        conn.commit()
        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("auth/login.html")


@bp.post("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/cuenta/password", methods=["GET", "POST"])
def cambiar_password():
    if request.method == "POST":
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        confirmar = request.form.get("confirmar", "")
        conn = get_db()
        fila = conn.execute(
            "SELECT password_hash FROM usuarios WHERE id = %s", (session["user_id"],)
        ).fetchone()

        if not fila or not check_password_hash(fila["password_hash"], actual):
            flash("La contraseña actual no es correcta.", "danger")
        elif len(nueva) < 8:
            flash("La nueva contraseña debe tener al menos 8 caracteres.", "danger")
        elif nueva != confirmar:
            flash("La confirmación no coincide con la nueva contraseña.", "danger")
        else:
            conn.execute(
                "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                (generate_password_hash(nueva), session["user_id"]),
            )
            conn.commit()
            flash("Contraseña actualizada.", "success")
            return redirect(url_for("inicio.index"))

    return render_template("auth/password.html")
