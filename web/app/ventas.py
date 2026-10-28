from decimal import Decimal

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from .db import get_db
from .inventario import registrar_movimiento
from .servicios import IMPRESIONES
from .utils import ErrorValidacion, a_decimal, a_entero, rango_fechas

bp = Blueprint("ventas", __name__)


# ======================= Caja (punto de venta) =======================

@bp.get("/caja")
def caja():
    filas = get_db().execute(
        "SELECT id, codigo, nombre, precio::text AS precio, activo FROM productos WHERE codigo = ANY(%s)",
        ([c for c, _, _ in IMPRESIONES],),
    ).fetchall()
    por_codigo = {f["codigo"]: f for f in filas}
    impresiones = [
        {"etiqueta": etiqueta, **por_codigo[codigo]}
        for codigo, etiqueta, _ in IMPRESIONES
        if codigo in por_codigo and por_codigo[codigo]["activo"]
    ]
    return render_template("ventas/caja.html", impresiones=impresiones)


@bp.get("/api/productos")
def api_buscar_productos():
    """Busca productos activos por código exacto o por nombre/código parcial."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(ok=True, exacto=None, resultados=[])
    conn = get_db()
    campos = "id, codigo, nombre, precio::text AS precio, stock, es_servicio"
    exacto = conn.execute(
        f"SELECT {campos} FROM productos WHERE activo AND codigo = %s", (q,)
    ).fetchone()
    like = f"%{q}%"
    resultados = conn.execute(
        f"""SELECT {campos} FROM productos
            WHERE activo AND (codigo ILIKE %s OR nombre ILIKE %s)
            ORDER BY (nombre ILIKE %s) DESC, nombre LIMIT 15""",
        (like, like, f"{q}%"),
    ).fetchall()
    return jsonify(ok=True, exacto=exacto, resultados=resultados)


@bp.post("/api/ventas")
def api_registrar_venta():
    datos = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        items = datos.get("items")
        if not isinstance(items, list) or not items:
            raise ErrorValidacion("La venta no tiene productos")
        if len(items) > 500:
            raise ErrorValidacion("Demasiados productos en una sola venta")

        # Agrupar cantidades por producto
        cantidades = {}
        for it in items:
            if not isinstance(it, dict):
                raise ErrorValidacion("Formato de venta inválido")
            pid = a_entero(it.get("producto_id"), "Producto", minimo=1)
            cant = a_entero(it.get("cantidad"), "Cantidad", minimo=1)
            cantidades[pid] = cantidades.get(pid, 0) + cant

        # Bloquear filas de productos (en orden por id para evitar bloqueos cruzados)
        ids = sorted(cantidades)
        productos = conn.execute(
            "SELECT * FROM productos WHERE id = ANY(%s) ORDER BY id FOR UPDATE", (ids,)
        ).fetchall()
        por_id = {p["id"]: p for p in productos}

        problemas = []
        for pid in ids:
            p = por_id.get(pid)
            if p is None or not p["activo"]:
                problemas.append(f"Producto #{pid} no está disponible")
            elif p["es_servicio"]:
                if p["precio"] <= 0:
                    problemas.append(f"«{p['nombre']}» no tiene precio; defínelo en Inventario")
            elif p["stock"] < cantidades[pid]:
                problemas.append(f"«{p['nombre']}»: pediste {cantidades[pid]}, solo hay {p['stock']}")
        if problemas:
            raise ErrorValidacion("No se puede registrar la venta:\n" + "\n".join(problemas))

        # El precio siempre se toma de la base de datos, no del navegador
        total = sum((por_id[pid]["precio"] * cantidades[pid] for pid in ids), Decimal("0"))
        pago = a_decimal(datos.get("pago"), "Pago", requerido=False)
        if pago is not None and pago < total:
            raise ErrorValidacion(f"El pago (${pago:,.2f}) es menor que el total (${total:,.2f})")

        venta = conn.execute(
            "INSERT INTO ventas (total, pago) VALUES (%s, %s) RETURNING id", (total, pago)
        ).fetchone()
        for pid in ids:
            p, cant = por_id[pid], cantidades[pid]
            conn.execute(
                """INSERT INTO venta_detalle
                       (venta_id, producto_id, cantidad, precio_unitario, costo_unitario, subtotal)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (venta["id"], pid, cant, p["precio"], p["costo"], p["precio"] * cant),
            )
            if p["es_servicio"]:
                continue  # los servicios no descuentan stock
            nuevo_stock = p["stock"] - cant
            conn.execute(
                "UPDATE productos SET stock = %s, actualizado = now() WHERE id = %s", (nuevo_stock, pid)
            )
            registrar_movimiento(conn, pid, "venta", -cant, nuevo_stock, venta_id=venta["id"])
        conn.commit()
    except ErrorValidacion as e:
        conn.rollback()
        return jsonify(ok=False, error=str(e)), 400

    return jsonify(ok=True, venta_id=venta["id"], total=str(total),
                   cambio=str(pago - total) if pago is not None else None)


# ======================= Historial =======================

@bp.get("/ventas")
def lista():
    desde, hasta = rango_fechas(request.args, dias_defecto=7)
    estado = request.args.get("estado", "")
    condiciones = ["v.fecha >= %s::date", "v.fecha < %s::date + 1"]
    params = [desde, hasta]
    if estado in ("completada", "cancelada"):
        condiciones.append("v.estado = %s")
        params.append(estado)
    conn = get_db()
    ventas = conn.execute(
        f"""SELECT v.*,
                   (SELECT sum(cantidad) FROM venta_detalle d WHERE d.venta_id = v.id) AS piezas
            FROM ventas v WHERE {' AND '.join(condiciones)}
            ORDER BY v.fecha DESC LIMIT 1000""",
        params,
    ).fetchall()
    total = sum((v["total"] for v in ventas if v["estado"] == "completada"), Decimal("0"))
    return render_template("ventas/lista.html", ventas=ventas, desde=desde, hasta=hasta,
                           estado=estado, total=total)


@bp.get("/ventas/<int:vid>")
def detalle(vid):
    conn = get_db()
    venta = conn.execute("SELECT * FROM ventas WHERE id = %s", (vid,)).fetchone()
    if not venta:
        abort(404)
    lineas = conn.execute(
        """SELECT d.*, p.codigo, p.nombre FROM venta_detalle d
           JOIN productos p ON p.id = d.producto_id
           WHERE d.venta_id = %s ORDER BY d.id""",
        (vid,),
    ).fetchall()
    return render_template("ventas/detalle.html", venta=venta, lineas=lineas,
                           nueva=request.args.get("nueva") == "1")


@bp.post("/ventas/<int:vid>/cancelar")
def cancelar(vid):
    conn = get_db()
    motivo = (request.form.get("motivo") or "").strip()[:300]
    if not motivo:
        flash("Escribe el motivo de la cancelación.", "danger")
        return redirect(url_for("ventas.detalle", vid=vid))

    venta = conn.execute("SELECT * FROM ventas WHERE id = %s FOR UPDATE", (vid,)).fetchone()
    if not venta:
        abort(404)
    if venta["estado"] == "cancelada":
        conn.rollback()
        flash("Esta venta ya estaba cancelada.", "warning")
        return redirect(url_for("ventas.detalle", vid=vid))

    lineas = conn.execute(
        "SELECT d.producto_id, sum(d.cantidad) AS cantidad FROM venta_detalle d "
        "JOIN productos p ON p.id = d.producto_id "
        "WHERE d.venta_id = %s AND NOT p.es_servicio "
        "GROUP BY d.producto_id ORDER BY d.producto_id",
        (vid,),
    ).fetchall()
    for ln in lineas:
        fila = conn.execute(
            "UPDATE productos SET stock = stock + %s, actualizado = now() WHERE id = %s RETURNING stock",
            (ln["cantidad"], ln["producto_id"]),
        ).fetchone()
        registrar_movimiento(conn, ln["producto_id"], "cancelacion", ln["cantidad"], fila["stock"],
                             venta_id=vid, nota=f"Cancelación venta #{vid}: {motivo}")
    conn.execute(
        "UPDATE ventas SET estado = 'cancelada', cancelada_en = now(), motivo_cancelacion = %s WHERE id = %s",
        (motivo, vid),
    )
    conn.commit()
    flash(f"Venta #{vid} cancelada. El stock fue devuelto al inventario.", "success")
    return redirect(url_for("ventas.detalle", vid=vid))
