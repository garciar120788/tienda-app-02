#!/usr/bin/env bash
# Crea el archivo .env con contraseñas y clave secreta aleatorias.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo "Ya existe un archivo .env; no se modificó. Bórralo primero si quieres generarlo de nuevo."
  exit 1
fi

aleatorio() { od -An -tx1 -N "$(( $1 / 2 ))" /dev/urandom | tr -d ' \n'; }

read -r -p "Nombre de la tienda [Mi Tienda]: " TIENDA
TIENDA=${TIENDA:-Mi Tienda}
read -r -p "Usuario para iniciar sesión [admin]: " USUARIO
USUARIO=${USUARIO:-admin}
while true; do
  read -r -s -p "Contraseña para '$USUARIO' (mínimo 8 caracteres): " PASS; echo
  read -r -s -p "Repite la contraseña: " PASS2; echo
  if [ "${#PASS}" -lt 8 ]; then echo "Muy corta, intenta de nuevo."; continue; fi
  if [ "$PASS" != "$PASS2" ]; then echo "No coinciden, intenta de nuevo."; continue; fi
  case "$PASS" in *"'"*) echo "La contraseña no puede contener comillas simples ('), intenta de nuevo."; continue;; esac
  break
done
read -r -p "Puerto web [8080]: " PUERTO
PUERTO=${PUERTO:-8080}

umask 077
cat > .env <<ENV
STORE_NAME='${TIENDA//\'/}'
WEB_PORT=$PUERTO
TZ=America/Mexico_City
POSTGRES_DB=tienda
POSTGRES_USER=tienda
POSTGRES_PASSWORD=$(aleatorio 32)
SECRET_KEY=$(aleatorio 64)
ADMIN_USER=$USUARIO
ADMIN_PASSWORD='$PASS'
SESSION_MINUTES=60
ENV

echo
echo "Listo: se creó .env (solo lectura para tu usuario)."
echo "Ahora ejecuta:  docker compose up -d --build"
echo "y abre:         http://localhost:$PUERTO"
