"""Cálculo de custos estimados para entregas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class EstimatedCost:
    """Representa o custo total e detalhes do cálculo."""

    total: float
    base_rate: float
    distance_component: float
    volume_component: float
    urgency_component: float


DEFAULT_BASE_RATE = 35.0
KM_RATE = 3.0
VOLUME_RATE = 45.0
URGENCY_SURCHARGE = 0.15


def estimar_custo_entrega(
    distancia_km: Optional[float],
    volume_m3: Optional[float],
    urgente: bool,
    *,
    base_rate: float = DEFAULT_BASE_RATE,
    km_rate: float = KM_RATE,
    volume_rate: float = VOLUME_RATE,
    urgency_surcharge: float = URGENCY_SURCHARGE,
) -> EstimatedCost:
    """Calcula custo aproximado baseado nos parâmetros fornecidos."""

    distance_component = (distancia_km or 0.0) * km_rate
    volume_component = max(volume_m3 or 0.0, 0.0) * volume_rate
    urgency_component = base_rate * urgency_surcharge if urgente else 0.0
    total = base_rate + distance_component + volume_component + urgency_component
    return EstimatedCost(
        total=round(total, 2),
        base_rate=base_rate,
        distance_component=round(distance_component, 2),
        volume_component=round(volume_component, 2),
        urgency_component=round(urgency_component, 2),
    )


__all__ = ["EstimatedCost", "estimar_custo_entrega"]
