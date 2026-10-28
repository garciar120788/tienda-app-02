import logging
import os
import time
from pathlib import Path

import psycopg
from flask import g
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash

log = logging.getLogger(__name__)

SCHEMA = Path(__file__).with_name("schema.sql")
LOCK_ID = 7_310_001  # candado para que solo un proceso aplique el esquema a la vez


def _conninfo():
    tz = os.environ.get("TZ", "America/Mexico_City")
    return dict(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "tienda"),
        user=os.environ.get("DB_USER", "tienda"),
        password=os.environ.get("DB_PASSWORD", ""),
        options=f"-c TimeZone={tz}",
        connect_timeout=5,
    )


def connect():
    return psycopg.connect(**_conninfo(), row_factory=dict_row)


def get_db():
    """Una conexión por petición; se cierra al terminar (lo no confirmado se descarta)."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _esperar_bd(intentos=30):
    for i in range(1, intentos + 1):
        try:
            return connect()
        except psycopg.OperationalError as e:
            log.warning("Base de datos no disponible (intento %s/%s): %s", i, intentos, e)
            time.sleep(2)
    raise RuntimeError("No fue posible conectar con la base de datos")


def inicializar():
    """Aplica el esquema y crea el usuario inicial si no existe ninguno."""
    with _esperar_bd() as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            conn.execute(SCHEMA.read_text(encoding="utf-8"))
            n = conn.execute("SELECT count(*) AS n FROM usuarios").fetchone()["n"]
            if n == 0:
                usuario = os.environ.get("ADMIN_USER", "admin").strip() or "admin"
                password = os.environ.get("ADMIN_PASSWORD", "")
                if not password or password.startswith("CAMBIAR"):
                    raise RuntimeError("Define ADMIN_PASSWORD en el archivo .env para crear el usuario inicial")
                conn.execute(
                    "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
                    (usuario, generate_password_hash(password)),
                )
                log.info("Usuario inicial '%s' creado", usuario)
            from .servicios import crear_servicios
            crear_servicios(conn)
            # Limpieza de intentos de login antiguos
            conn.execute("DELETE FROM intentos_login WHERE fecha < now() - interval '1 day'")
            conn.commit()
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
            conn.commit()


def init_app(app):
    logging.basicConfig(level=logging.INFO)
    inicializar()
    app.teardown_appcontext(close_db)
