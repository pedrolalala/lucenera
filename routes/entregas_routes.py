"""Blueprint com rotas REST para consultas e cadastro de entregas."""
from __future__ import annotations

import datetime as _dt
from http import HTTPStatus
from typing import Any, Dict, List, Optional, cast

from flask import Blueprint, jsonify, request

from services.classificador_entrega import DeliveryScore, classificar_entrega
from services.custo_estimado import EstimatedCost, estimar_custo_entrega
from services.logistica_parser import DeliveryData, parse_generic_message, parse_text_message
from services.rota_optimizada import RouteStop, calcular_distancia_total, gerar_ordem_otimizada
from services.supabase_entregas import (
    listar_entregas_por_data,
    listar_statuses,
    salvar_entrega,
)
from utils.google_maps_client import GoogleMapsClient

entregas_bp = Blueprint("entregas", __name__, url_prefix="/entregas")

_maps_client = GoogleMapsClient()


def _infer_delivery_from_payload(payload: Dict[str, Any]) -> DeliveryData:
    """Determina o parser adequado com base no conteúdo recebido."""

    if "texto" in payload:
        return parse_text_message(payload.get("texto", ""), origem="post_entregas")
    return parse_generic_message(payload)


@entregas_bp.get("/dia")
def listar_entregas_do_dia() -> Any:
    hoje = _dt.date.today()
    registros = listar_entregas_por_data(hoje)
    return jsonify({"data": hoje.isoformat(), "entregas": registros})


@entregas_bp.post("")
def registrar_entrega() -> Any:
    payload = request.get_json(silent=True) or {}
    delivery = _infer_delivery_from_payload(payload)

    distancia_km: Optional[float] = None
    if delivery.endereco:
        distancia_km = _maps_client.estimate_distance_km(payload.get("origem"), delivery.endereco)

    score: DeliveryScore = classificar_entrega(delivery, distancia_km=distancia_km)
    cost: EstimatedCost = estimar_custo_entrega(distancia_km, payload.get("volume_m3"), delivery.urgencia)

    registro = delivery.to_payload()
    registro_data = cast(Dict[str, Any], registro)
    registro_data.update(
        {
            "pontuacao": score.total,
            "detalhes_pontuacao": score.breakdown,
            "custo_estimado": cost.total,
            "custo_componentes": {
                "base": cost.base_rate,
                "distancia": cost.distance_component,
                "volume": cost.volume_component,
                "urgencia": cost.urgency_component,
            },
            "status": payload.get("status", "pendente"),
        }
    )

    criado = salvar_entrega(registro_data)
    retorno = {"entrega": criado, "pontuacao": score.total, "custo_estimado": cost.total}
    return jsonify(retorno), HTTPStatus.CREATED


@entregas_bp.get("/rota")
def obter_rota_otimizada() -> Any:
    hoje = _dt.date.today()
    registros = listar_entregas_por_data(hoje)
    deliveries: List[DeliveryData] = [parse_generic_message(reg) for reg in registros]
    route: List[RouteStop] = gerar_ordem_otimizada(deliveries, origem=request.args.get("origem"), maps_client=_maps_client)

    rota_serializada = [
        {
            "ordem": stop.position,
            "cliente": stop.delivery.cliente,
            "endereco": stop.delivery.endereco,
            "distancia_prev_km": stop.distance_from_prev_km,
        }
        for stop in route
    ]
    distancia_total = calcular_distancia_total(route)

    return jsonify({
        "data": hoje.isoformat(),
        "rota": rota_serializada,
        "distancia_total_km": distancia_total,
    })


@entregas_bp.get("/status")
def listar_status_entregas() -> Any:
    registros = listar_statuses()
    return jsonify({"status": registros})
