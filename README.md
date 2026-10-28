# Tienda: inventario y punto de venta

Aplicación web para administrar una tienda pequeña: login, inventario (con carga desde Excel/CSV), caja con lector de código de barras, descuento automático de stock, cancelación de ventas, historial de movimientos, alertas de stock bajo y reportes.

Corre en **2 contenedores Docker**:

| Contenedor   | Imagen               | Función                                          |
|--------------|----------------------|--------------------------------------------------|
| `tienda-web` | Python 3.12 + Flask  | Página web (puerto 8080 por defecto)             |
| `tienda-db`  | PostgreSQL 16        | Base de datos (no se expone fuera de Docker)     |

Los datos se guardan en el volumen `tienda_db_data`, así que no se pierden al reiniciar o actualizar.

---

## 1. Requisitos (Linux)

Docker Engine con el plugin Compose v2. En Ubuntu/Debian:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER     # para usar docker sin sudo (cierra sesión y vuelve a entrar)
docker compose version            # debe responder v2.x
```

## 2. Instalación

```bash
cd tienda
bash scripts/configurar.sh        # pregunta nombre, usuario, contraseña y puerto; genera .env
docker compose up -d --build
```

Abre `http://localhost:8080` (o `http://IP-DEL-SERVIDOR:8080` desde otra computadora o tablet de la red) e inicia sesión con el usuario que elegiste.

> Si prefieres hacerlo a mano: `cp .env.example .env`, edita los valores `CAMBIAR...` y genera la clave con `openssl rand -hex 32`.

Si el firewall está activo, abre el puerto: `sudo ufw allow 8080/tcp`.

## 3. Uso diario

| Sección        | Qué hace |
|----------------|----------|
| **Caja**       | Escanea el código de barras (o escribe el nombre y presiona Enter). Escribe `3*7501234567890` para agregar 3 piezas de una vez. Captura el pago para calcular el cambio. **F2** cobra. Al cobrar se descuenta el stock. Los botones de **Impresiones** (B/N, INE B/N, Color CH/MED/GL/XL, INE Color) agregan 1; para varias, escribe la cantidad en el buscador (ej. `10`) y toca el botón. |
| **Inventario** | Alta y edición de productos, búsqueda, filtro de stock bajo y exportación a CSV. En el detalle de cada producto: **Entrada** (llegó mercancía) o **Ajuste** (conteo físico o merma, con motivo obligatorio) y el historial de movimientos. |
| **Importar**   | Sube un `.xlsx` o `.csv` (descarga la plantilla desde la misma pantalla). Se muestra una vista previa con productos nuevos, productos a actualizar y errores. Para los productos que ya existen eliges si el stock se **suma** o se **reemplaza**. |
| **Ventas**     | Historial por fechas. En cada venta puedes imprimirla o **cancelarla** con un motivo; las piezas regresan al inventario. |
| **Reportes**   | Total vendido, ganancia bruta, ticket promedio, canceladas, productos más vendidos y ventas por día. Exportación del detalle a CSV. |

Las **alertas de stock bajo** aparecen en la barra superior y en el inicio cuando el stock de un producto llega a su `stock mínimo`.

**Servicios** (como las impresiones) se venden sin control de stock: no descuentan inventario ni generan alertas. Las 7 impresiones se crean solas con precio $0; captura su precio en Inventario (busca `IMP-`). Mientras estén en $0 la caja no deja venderlas. Puedes marcar cualquier otro producto como servicio desde su formulario.

**Desactivar un producto** lo oculta de la caja sin borrar su historial. No hay borrado definitivo, para no perder las ventas pasadas.

**Lector de código de barras:** sirve cualquier lector USB o Bluetooth que funcione como teclado (la mayoría). No necesita configuración.

## 4. Formato del archivo de importación

Primera fila con encabezados (se aceptan con o sin acentos y mayúsculas):

| codigo | nombre | precio | costo | stock | stock_minimo |
|--------|--------|--------|-------|-------|--------------|
| 7501234567890 | Refresco 600 ml | 18.50 | 12.00 | 24 | 6 |

- Obligatorios: `codigo`, `nombre`, `precio`.
- CSV separado por coma o punto y coma; acepta UTF-8 y Windows-1252.
- En Excel, deja la columna `codigo` con formato **Texto** para no perder ceros a la izquierda (la plantilla ya viene así).

## 5. Respaldos

```bash
bash scripts/respaldo.sh                                    # crea backups/tienda_FECHA.sql.gz (guarda los últimos 30)
bash scripts/restaurar.sh backups/tienda_2026-10-26_210000.sql.gz   # reemplaza los datos actuales
```

Respaldo automático diario a las 23:30 con `crontab -e`:

```
30 23 * * * bash /ruta/a/tienda/scripts/respaldo.sh >> /ruta/a/tienda/backups/respaldo.log 2>&1
```

Copia la carpeta `backups/` a otro disco o a la nube de vez en cuando.

## 6. Comandos útiles

```bash
docker compose ps                  # estado de los contenedores
docker compose logs -f web         # ver logs de la app
docker compose restart web         # reiniciar la app
docker compose down                # detener (los datos se conservan)
docker compose up -d --build       # actualizar después de cambiar el código
```

**Olvidé la contraseña:**

```bash
docker compose exec web python -c "
from werkzeug.security import generate_password_hash as h; import psycopg, os
c = psycopg.connect(host='db', dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])
c.execute('UPDATE usuarios SET password_hash=%s WHERE username=%s', (h('NuevaClave123'), os.environ['ADMIN_USER'])); c.commit()"
```

> ⚠️ `docker compose down -v` **borra el volumen con todos los datos**. Úsalo solo si quieres empezar de cero.

## 7. Seguridad

- Las contraseñas se guardan con hash, nunca en texto plano.
- La sesión expira tras `SESSION_MINUTES` minutos sin actividad (60 por defecto).
- Después de 5 intentos fallidos de login, esa IP queda bloqueada 10 minutos.
- Todos los formularios llevan protección CSRF.
- La base de datos solo es accesible desde el contenedor web.
- La app corre como usuario sin privilegios dentro del contenedor.
- Está pensada para la **red local**. Para publicarla en internet, ponla detrás de un proxy con HTTPS (Caddy o Nginx con Let's Encrypt) y agrega `SESSION_COOKIE_SECURE=true` en el servicio `web` del `docker-compose.yml`.

## 8. Estructura

```
tienda/
├── docker-compose.yml
├── .env.example
├── scripts/            configurar.sh, respaldo.sh, restaurar.sh
├── backups/
└── web/
    ├── Dockerfile
    ├── requirements.txt
    ├── wsgi.py
    └── app/
        ├── schema.sql      tablas (se crean solas al arrancar)
        ├── auth.py         login, logout, cambio de contraseña
        ├── inicio.py       panel principal
        ├── inventario.py   productos, stock, importación/exportación
        ├── ventas.py       caja, ventas, cancelaciones
        ├── reportes.py     reportes y exportación
        ├── templates/      vistas HTML (Bootstrap 5, incluido localmente: funciona sin internet)
        └── static/
```
