-- Esquema de la tienda. Se aplica automáticamente al arrancar la app
-- (todas las sentencias son idempotentes).

CREATE TABLE IF NOT EXISTS usuarios (
    id              SERIAL PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    creado          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS intentos_login (
    id      SERIAL PRIMARY KEY,
    ip      TEXT NOT NULL,
    fecha   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_intentos_login_ip_fecha ON intentos_login (ip, fecha);

CREATE TABLE IF NOT EXISTS productos (
    id              SERIAL PRIMARY KEY,
    codigo          TEXT NOT NULL UNIQUE,          -- SKU o código de barras
    nombre          TEXT NOT NULL,
    precio          NUMERIC(12,2) NOT NULL CHECK (precio >= 0),
    costo           NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (costo >= 0),
    stock           INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    stock_minimo    INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    creado          TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos (lower(nombre));

CREATE TABLE IF NOT EXISTS ventas (
    id                  SERIAL PRIMARY KEY,
    fecha               TIMESTAMPTZ NOT NULL DEFAULT now(),
    total               NUMERIC(12,2) NOT NULL,
    pago                NUMERIC(12,2),
    estado              TEXT NOT NULL DEFAULT 'completada'
                        CHECK (estado IN ('completada', 'cancelada')),
    cancelada_en        TIMESTAMPTZ,
    motivo_cancelacion  TEXT
);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas (fecha);

CREATE TABLE IF NOT EXISTS venta_detalle (
    id              SERIAL PRIMARY KEY,
    venta_id        INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    producto_id     INTEGER NOT NULL REFERENCES productos(id),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(12,2) NOT NULL,
    costo_unitario  NUMERIC(12,2) NOT NULL DEFAULT 0,
    subtotal        NUMERIC(12,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_venta_detalle_venta ON venta_detalle (venta_id);
CREATE INDEX IF NOT EXISTS idx_venta_detalle_producto ON venta_detalle (producto_id);

-- Registro de cada cambio de stock: alta, entrada, ajuste, importación, venta, cancelación
CREATE TABLE IF NOT EXISTS movimientos (
    id                  SERIAL PRIMARY KEY,
    producto_id         INTEGER NOT NULL REFERENCES productos(id),
    fecha               TIMESTAMPTZ NOT NULL DEFAULT now(),
    tipo                TEXT NOT NULL
                        CHECK (tipo IN ('alta', 'entrada', 'ajuste', 'importacion', 'venta', 'cancelacion')),
    cantidad            INTEGER NOT NULL,        -- positivo suma, negativo resta
    stock_resultante    INTEGER NOT NULL,
    venta_id            INTEGER REFERENCES ventas(id),
    nota                TEXT
);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto_fecha ON movimientos (producto_id, fecha DESC);

-- v2: servicios (ej. impresiones) que se venden sin control de stock
ALTER TABLE productos ADD COLUMN IF NOT EXISTS es_servicio BOOLEAN NOT NULL DEFAULT FALSE;
