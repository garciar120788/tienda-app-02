"""Servicios fijos que aparecen como botones en la caja (sin control de stock)."""

# (código, texto del botón, nombre del producto)
IMPRESIONES = [
    ("IMP-BN", "B/N", "Impresión B/N"),
    ("IMP-INE-BN", "INE B/N", "Impresión INE B/N"),
    ("IMP-COLOR-CH", "Color CH", "Impresión color CH"),
    ("IMP-COLOR-MED", "Color MED", "Impresión color MED"),
    ("IMP-COLOR-GL", "Color GL", "Impresión color GL"),
    ("IMP-COLOR-XL", "Color XL", "Impresión color XL"),
    ("IMP-INE-COLOR", "INE Color", "Impresión INE color"),
]


def crear_servicios(conn):
    """Da de alta los servicios que falten (precio $0; se captura desde Inventario)."""
    for codigo, _boton, nombre in IMPRESIONES:
        conn.execute(
            """INSERT INTO productos (codigo, nombre, precio, costo, stock, stock_minimo, es_servicio)
               VALUES (%s, %s, 0, 0, 0, 0, TRUE)
               ON CONFLICT (codigo) DO NOTHING""",
            (codigo, nombre),
        )
