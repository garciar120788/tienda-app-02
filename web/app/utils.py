import os
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo


class ErrorValidacion(ValueError):
    pass


def hoy():
    """Fecha actual en la zona horaria de la tienda."""
    return datetime.now(ZoneInfo(os.environ.get("TZ", "America/Mexico_City"))).date()


# ---------- Conversión de datos de formularios / archivos ----------

def a_decimal(valor, campo, requerido=True, minimo=Decimal("0")):
    if valor is None or str(valor).strip() == "":
        if requerido:
            raise ErrorValidacion(f"{campo} es obligatorio")
        return None
    texto = str(valor).strip().replace("$", "").replace(" ", "")
    # Acepta "1,234.50" y "1234,50"
    if "," in texto and "." in texto:
        texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        d = Decimal(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ErrorValidacion(f"{campo} no es un número válido: {valor}")
    if not d.is_finite():
        raise ErrorValidacion(f"{campo} no es un número válido: {valor}")
    if minimo is not None and d < minimo:
        raise ErrorValidacion(f"{campo} no puede ser negativo")
    if d >= Decimal("10000000000"):
        raise ErrorValidacion(f"{campo} es demasiado grande")
    return d


def a_entero(valor, campo, requerido=True, minimo=0):
    if valor is None or str(valor).strip() == "":
        if requerido:
            raise ErrorValidacion(f"{campo} es obligatorio")
        return None
    texto = str(valor).strip().replace(",", "")
    try:
        f = Decimal(texto)
    except InvalidOperation:
        raise ErrorValidacion(f"{campo} debe ser un número entero: {valor}")
    if not f.is_finite() or f != f.to_integral_value():
        raise ErrorValidacion(f"{campo} debe ser un número entero: {valor}")
    n = int(f)
    if minimo is not None and n < minimo:
        raise ErrorValidacion(f"{campo} no puede ser menor que {minimo}")
    if abs(n) > 1_000_000_000:
        raise ErrorValidacion(f"{campo} es demasiado grande")
    return n


def a_codigo(valor):
    """Normaliza un código/SKU. Excel puede entregar códigos de barras como float."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).strip()
    if texto.endswith(".0") and texto[:-2].isdigit():
        texto = texto[:-2]
    return texto


def sin_acentos(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c))


def a_fecha(valor, defecto):
    if not valor:
        return defecto
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return defecto


def rango_fechas(args, dias_defecto=None):
    """Lee ?desde=&hasta= (YYYY-MM-DD). Por defecto: mes actual, o los últimos N días."""
    actual = hoy()
    if dias_defecto is not None:
        inicio = actual - timedelta(days=dias_defecto - 1)
    else:
        inicio = actual.replace(day=1)
    desde = a_fecha(args.get("desde"), inicio)
    hasta = a_fecha(args.get("hasta"), actual)
    if hasta < desde:
        desde, hasta = hasta, desde
    return desde, hasta


# ---------- Filtros de plantillas ----------

def dinero(valor):
    if valor is None:
        valor = 0
    return f"${Decimal(valor):,.2f}"


def numero(valor):
    if valor is None:
        valor = 0
    return f"{int(valor):,}"


MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def fecha_hora(valor):
    if not isinstance(valor, datetime):
        return valor or ""
    return f"{valor.day:02d}/{MESES[valor.month - 1]}/{valor.year} {valor:%H:%M}"


def fecha_corta(valor):
    if isinstance(valor, datetime):
        valor = valor.date()
    if not isinstance(valor, date):
        return valor or ""
    return f"{valor.day:02d}/{MESES[valor.month - 1]}/{valor.year}"
