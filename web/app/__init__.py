import os
import secrets
from datetime import timedelta

from flask import Flask, abort, jsonify, redirect, request, session, url_for

from . import db
from .utils import fecha_corta, fecha_hora, dinero, numero


# Rutas que no requieren sesión iniciada
RUTAS_PUBLICAS = {"auth.login", "static", "salud"}


def create_app():
    app = Flask(__name__)

    secret = os.environ.get("SECRET_KEY", "")
    if not secret or secret.startswith("CAMBIAR"):
        raise RuntimeError("Define SECRET_KEY en el archivo .env (puedes generarla con: openssl rand -hex 32)")

    app.config.update(
        SECRET_KEY=secret,
        STORE_NAME=os.environ.get("STORE_NAME", "Mi Tienda"),
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=int(os.environ.get("SESSION_MINUTES", "60"))),
        SESSION_REFRESH_EACH_REQUEST=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
        SESSION_COOKIE_NAME="tienda_sesion",
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB para archivos de importación
    )

    db.init_app(app)

    from .auth import bp as auth_bp
    from .inicio import bp as inicio_bp
    from .inventario import bp as inventario_bp
    from .ventas import bp as ventas_bp
    from .reportes import bp as reportes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inicio_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(reportes_bp)

    app.add_template_filter(dinero, "dinero")
    app.add_template_filter(fecha_hora, "fecha_hora")
    app.add_template_filter(fecha_corta, "fecha_corta")
    app.add_template_filter(numero, "numero")

    @app.get("/salud")
    def salud():
        return {"ok": True}

    # ---------- Seguridad: sesión obligatoria y protección CSRF ----------
    @app.before_request
    def proteger():
        if request.endpoint in RUTAS_PUBLICAS:
            return None
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify(ok=False, error="La sesión expiró. Vuelve a iniciar sesión."), 401
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return None

    @app.before_request
    def verificar_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            enviado = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            esperado = session.get("csrf_token")
            if not esperado or not enviado or not secrets.compare_digest(enviado, esperado):
                if request.path.startswith("/api/"):
                    return jsonify(ok=False, error="Token de seguridad inválido. Recarga la página."), 400
                abort(400, "Token de seguridad inválido. Recarga la página e intenta de nuevo.")
        return None

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return session["csrf_token"]

    @app.context_processor
    def contexto_global():
        datos = {"csrf_token": csrf_token, "store_name": app.config["STORE_NAME"], "alertas_stock": 0}
        if session.get("user_id"):
            fila = db.get_db().execute(
                "SELECT count(*) AS n FROM productos WHERE activo AND NOT es_servicio AND stock <= stock_minimo"
            ).fetchone()
            datos["alertas_stock"] = fila["n"]
        return datos

    @app.after_request
    def cabeceras_seguridad(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    from .errores import registrar_errores
    registrar_errores(app)

    return app
