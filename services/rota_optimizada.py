"""Heurísticas simples de roteirização para equipes de entrega."""
from __future__ import annotations

import dataclasses
from typing import Iterable, List, Optional, Sequence

from services.logistica_parser import DeliveryData
from utils.google_maps_client import GoogleMapsClient, GeoPoint


@dataclasses.dataclass(slots=True)
class RouteStop:
    """Representa uma parada ordenada na rota."""

    delivery: DeliveryData
    position: int
    distance_from_prev_km: float


def _build_geo_points(
    deliveries: Sequence[DeliveryData], maps_client: GoogleMapsClient
) -> List[GeoPoint]:
    geo_points: List[GeoPoint] = []
    for delivery in deliveries:
        if not delivery.endereco:
            geo_points.append(GeoPoint(latitude=None, longitude=None, endereco=""))
            continue
        location = maps_client.geocode(delivery.endereco)
        geo_points.append(location)
    return geo_points


def calcular_rota_gulosa(
    deliveries: Sequence[DeliveryData],
    origem: Optional[str],
    maps_client: GoogleMapsClient,
) -> List[RouteStop]:
    """Aplica heurística gulosa (vizinho mais próximo) com apoio do Google Maps."""

    if not deliveries:
        return []

    geo_points = _build_geo_points(deliveries, maps_client)
    route: List[RouteStop] = []
    visited = set()
    current_index = -1
    previous_point = maps_client.geocode(origem) if origem else None

    for position in range(len(deliveries)):
        next_index = None
        shortest_distance = float("inf")
        base_point = previous_point or geo_points[current_index] if current_index >= 0 else None
        for idx, point in enumerate(geo_points):
            if idx in visited:
                continue
            if base_point is None or point.latitude is None or point.longitude is None:
                estimated = maps_client.estimate_distance_km(origem or "", deliveries[idx].endereco or "")
            else:
                estimated = maps_client.distance_between(base_point, point)
            if estimated < shortest_distance:
                shortest_distance = estimated
                next_index = idx
        if next_index is None:
            break
        visited.add(next_index)
        previous_point = geo_points[next_index]
        route.append(
            RouteStop(
                delivery=deliveries[next_index],
                position=position + 1,
                distance_from_prev_km=shortest_distance if shortest_distance != float("inf") else 0.0,
            )
        )
        current_index = next_index
    return route


def gerar_ordem_otimizada(
    deliveries: Sequence[DeliveryData],
    origem: Optional[str] = None,
    maps_client: Optional[GoogleMapsClient] = None,
) -> List[RouteStop]:
    """Interface principal: retorna rota sugerida mantendo agnosticismo de cliente."""

    maps_client = maps_client or GoogleMapsClient()
    return calcular_rota_gulosa(deliveries, origem, maps_client)


def calcular_distancia_total(route: Iterable[RouteStop]) -> float:
    """Soma a distância aproximada percorrida."""

    return sum(stop.distance_from_prev_km for stop in route)


__all__ = [
    "RouteStop",
    "gerar_ordem_otimizada",
    "calcular_rota_gulosa",
    "calcular_distancia_total",
]
