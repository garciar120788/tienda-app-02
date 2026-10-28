import csv
import io

from flask import Blueprint, Response, render_template, request

from .db import get_db
from .utils import rango_fechas

bp = Blueprint("reportes", __name__, url_prefix="/reportes")

RANGO_SQL = "v.fecha >= %(desde)s::date AND v.fecha < %(hasta)s::date + 1"


@bp.get("/")
def index():
    desde, hasta = rango_fechas(request.args)
    p = {"desde": desde, "hasta": hasta}
    conn = get_db()

    resumen = conn.execute(
        f"""SELECT count(*) FILTER (WHERE estado = 'completada') AS ventas,
                   COALESCE(sum(total) FILTER (WHERE estado = 'completada'), 0) AS total,
                   count(*) FILTER (WHERE estado = 'cancelada') AS canceladas,
                   COALESCE(sum(total) FILTER (WHERE estado = 'cancelada'), 0) AS total_cancelado
            FROM ventas v WHERE {RANGO_SQL}""",
        p,
    ).fetchone()
    ganancia = conn.execute(
        f"""SELECT COALESCE(sum(d.subtotal - d.costo_unitario * d.cantidad), 0) AS ganancia,
                   COALESCE(sum(d.cantidad), 0) AS piezas
            FROM venta_detalle d JOIN ventas v ON v.id = d.venta_id
            WHERE v.estado = 'completada' AND {RANGO_SQL}""",
        p,
    ).fetchone()
    por_dia = conn.execute(
        f"""SELECT (v.fecha)::date AS dia, count(*) AS ventas, sum(v.total) AS total
            FROM ventas v WHERE v.estado = 'completada' AND {RANGO_SQL}
            GROUP BY 1 ORDER BY 1 DESC""",
        p,
    ).fetchall()
    top = conn.execute(
        f"""SELECT pr.id, pr.codigo, pr.nombre, sum(d.cantidad) AS piezas, sum(d.subtotal) AS total,
                   sum(d.subtotal - d.costo_unitario * d.cantidad) AS ganancia
            FROM venta_detalle d
            JOIN ventas v ON v.id = d.venta_id
            JOIN productos pr ON pr.id = d.producto_id
            WHERE v.estado = 'completada' AND {RANGO_SQL}
            GROUP BY pr.id, pr.codigo, pr.nombre
            ORDER BY piezas DESC, total DESC LIMIT 15""",
        p,
    ).fetchall()

    ticket_promedio = (resumen["total"] / resumen["ventas"]) if resumen["ventas"] else 0
    return render_template(
        "reportes/index.html", desde=desde, hasta=hasta, resumen=resumen, ganancia=ganancia,
        por_dia=por_dia, top=top, ticket_promedio=ticket_promedio,
    )


@bp.get("/exportar.csv")
def exportar():
    desde, hasta = rango_fechas(request.args)
    filas = get_db().execute(
        f"""SELECT v.id AS venta, to_char(v.fecha, 'YYYY-MM-DD HH24:MI') AS fecha, v.estado,
                   pr.codigo, pr.nombre, d.cantidad, d.precio_unitario, d.costo_unitario, d.subtotal
            FROM venta_detalle d
            JOIN ventas v ON v.id = d.venta_id
            JOIN productos pr ON pr.id = d.producto_id
            WHERE {RANGO_SQL}
            ORDER BY v.fecha, v.id, d.id""",
        {"desde": desde, "hasta": hasta},
    ).fetchall()
    out = io.StringIO()
    out.write("﻿")
    w = csv.writer(out)
    w.writerow(["venta", "fecha", "estado", "codigo", "producto", "cantidad",
                "precio_unitario", "costo_unitario", "subtotal"])
    for f in filas:
        w.writerow([f["venta"], f["fecha"], f["estado"], f["codigo"], f["nombre"], f["cantidad"],
                    f["precio_unitario"], f["costo_unitario"], f["subtotal"]])
    nombre = f"ventas_{desde}_a_{hasta}.csv"
    return Response(out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})
