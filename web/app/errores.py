import logging

from flask import jsonify, render_template, request

log = logging.getLogger(__name__)


def registrar_errores(app):
    def responder(codigo, titulo, mensaje):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error=mensaje), codigo
        return render_template("error.html", codigo=codigo, titulo=titulo, mensaje=mensaje), codigo

    @app.errorhandler(400)
    def e400(e):
        return responder(400, "Solicitud inválida", getattr(e, "description", "Solicitud inválida"))

    @app.errorhandler(404)
    def e404(_e):
        return responder(404, "No encontrado", "La página o el registro que buscas no existe.")

    @app.errorhandler(413)
    def e413(_e):
        return responder(413, "Archivo muy grande", "El archivo excede el límite de 5 MB.")

    @app.errorhandler(500)
    def e500(e):
        log.exception("Error interno: %s", e)
        return responder(500, "Error interno", "Ocurrió un error inesperado. Intenta de nuevo.")
