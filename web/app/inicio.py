from flask import Blueprint, render_template

from .db import get_db

bp = Blueprint("inicio", __name__)


@bp.get("/")
def index():
    conn = get_db()
    hoy = conn.execute(
        """
        SELECT count(*) AS ventas, COALESCE(sum(total), 0) AS total
        FROM ventas
        WHERE estado = 'completada' AND fecha >= current_date AND fecha < current_date + 1
        """
    ).fetchone()
    mes = conn.execute(
        """
        SELECT count(*) AS ventas, COALESCE(sum(total), 0) AS total
        FROM ventas
        WHERE estado = 'completada' AND fecha >= date_trunc('month', current_date)
        """
    ).fetchone()
    inventario = conn.execute(
        """
        SELECT count(*) AS productos,
               COALESCE(sum(stock), 0) AS piezas,
               COALESCE(sum(stock * costo), 0) AS valor_costo
        FROM productos WHERE activo AND NOT es_servicio
        """
    ).fetchone()
    bajos = conn.execute(
        """
        SELECT id, codigo, nombre, stock, stock_minimo
        FROM productos
        WHERE activo AND NOT es_servicio AND stock <= stock_minimo
        ORDER BY stock, nombre
        LIMIT 10
        """
    ).fetchall()
    recientes = conn.execute(
        """
        SELECT v.id, v.fecha, v.total, v.estado,
               (SELECT sum(cantidad) FROM venta_detalle d WHERE d.venta_id = v.id) AS piezas
        FROM ventas v ORDER BY v.fecha DESC LIMIT 8
        """
    ).fetchall()
    return render_template(
        "inicio.html", hoy=hoy, mes=mes, inventario=inventario, bajos=bajos, recientes=recientes
    )
