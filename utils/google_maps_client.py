"""Cliente fino para encapsular chamadas ao Google Maps API."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional, cast

import logging

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GeoPoint:
    latitude: Optional[float]
    longitude: Optional[float]
    endereco: str


def _haversine_distance(point_a: GeoPoint, point_b: GeoPoint) -> float:
    coords = (point_a.latitude, point_a.longitude, point_b.latitude, point_b.longitude)
    if any(value is None for value in coords):
        return float("inf")
    lat1, lon1, lat2, lon2 = map(math.radians, cast(tuple[float, float, float, float], coords))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    earth_radius_km = 6371
    return earth_radius_km * c


class GoogleMapsClient:
    """Wrapper simples que tenta usar googlemaps, mas possui fallback leve."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        self._client = None
        if self.api_key:
            try:
                import googlemaps  # type: ignore

                self._client = googlemaps.Client(key=self.api_key)
            except Exception as exc:  # pragma: no cover - dependência opcional
                LOGGER.warning("Falha ao iniciar googlemaps.Client: %s", exc)
                self._client = None

    def geocode(self, endereco: Optional[str]) -> GeoPoint:
        if not endereco:
            return GeoPoint(latitude=None, longitude=None, endereco="")
        if self._client:
            try:
                result = self._client.geocode(endereco)
                if result:
                    location = result[0]["geometry"]["location"]
                    return GeoPoint(latitude=location.get("lat"), longitude=location.get("lng"), endereco=endereco)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("Falha ao geocodificar '%s': %s", endereco, exc)
        return GeoPoint(latitude=None, longitude=None, endereco=endereco)

    def distance_between(self, origin: GeoPoint, destination: GeoPoint) -> float:
        if self._client and None not in {origin.endereco, destination.endereco}:
            try:
                matrix = self._client.distance_matrix(origin.endereco, destination.endereco, units="metric")
                rows = matrix.get("rows") if isinstance(matrix, dict) else None
                if rows:
                    elements = rows[0].get("elements")
                    if elements and elements[0].get("status") == "OK":
                        distance_m = elements[0]["distance"]["value"]
                        return distance_m / 1000.0
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("Erro ao consultar distance_matrix: %s", exc)
        if origin.latitude is None or destination.latitude is None:
            return float("inf")
        return _haversine_distance(origin, destination)

    def estimate_distance_km(self, origem: Optional[str], destino: Optional[str]) -> float:
        origin_point = self.geocode(origem)
        destination_point = self.geocode(destino)
        resultado = self.distance_between(origin_point, destination_point)
        if math.isinf(resultado):
            return 0.0
        return round(resultado, 2)


__all__ = ["GeoPoint", "GoogleMapsClient"]
