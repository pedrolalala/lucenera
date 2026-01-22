"""Recebe webhooks do Microsoft Teams com pedidos de entrega."""
from __future__ import annotations

import datetime as _dt
import logging
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from services.supabase_entregas import registrar_entrega
from services.teams_parser import ParsedEntrega, parse_entrega_teams

LOGGER = logging.getLogger(__name__)

teams_bp = Blueprint("teams", __name__, url_prefix="/teams")


@teams_bp.post("/entregas")
def receber_entregas() -> tuple:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        LOGGER.warning("Payload inválido recebido no webhook do Teams: %s", payload)
        return jsonify({"erro": "payload inválido"}), HTTPStatus.BAD_REQUEST

    parsed: ParsedEntrega = parse_entrega_teams(payload)
    registro = registrar_entrega(parsed)

    resposta = {
        "recebido_em": _dt.datetime.utcnow().isoformat(),
        "entrega": registro,
        "status": "registrado",
    }
    return jsonify(resposta), HTTPStatus.CREATED
