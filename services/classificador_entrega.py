"""Classificador de entregas atribuindo pontuação de 1 a 10."""
from __future__ import annotations

import dataclasses
from typing import Dict, Optional

from services.logistica_parser import DeliveryData


@dataclasses.dataclass(slots=True)
class DeliveryScore:
    """Retorna a pontuação total e o detalhamento usado no cálculo."""

    total: int
    breakdown: Dict[str, int]

    def capped(self, minimum: int = 1, maximum: int = 10) -> "DeliveryScore":
        """Garante que a pontuação final esteja dentro da escala definida."""

        capped_total = max(minimum, min(maximum, self.total))
        return DeliveryScore(total=capped_total, breakdown=self.breakdown)


def classificar_quantidade_itens(material: Optional[str]) -> int:
    """Pontua de forma heurística com base na quantidade estimada de itens."""

    if not material:
        return 1
    linhas = [line.strip() for line in material.splitlines() if line.strip()]
    if not linhas:
        return 1
    if len(linhas) >= 10:
        return 4
    if len(linhas) >= 5:
        return 3
    if len(linhas) >= 2:
        return 2
    return 1


def classificar_urgencia(urgencia: bool) -> int:
    """Adiciona pontos extras quando urgência é mencionada."""

    return 2 if urgencia else 0


def classificar_destino(responsavel: Optional[str]) -> int:
    """Portaria recebe bônus, demais retornam pontuação neutra."""

    if not responsavel:
        return 0
    responsavel_normalizado = responsavel.strip().lower()
    if "portaria" in responsavel_normalizado:
        return 1
    if any(role in responsavel_normalizado for role in {"engenheiro", "arquiteto", "obra"}):
        return 1
    return 0


def classificar_distancia(distancia_km: Optional[float]) -> int:
    """Traduz distância aproximada em pontuação incremental."""

    if distancia_km is None:
        return 0
    if distancia_km > 60:
        return 3
    if distancia_km > 30:
        return 2
    if distancia_km > 10:
        return 1
    return 0


def classificar_transporte_por_volume(volume_m3: Optional[float]) -> int:
    """Avalia impacto do volume/peso no esforço logístico."""

    if volume_m3 is None:
        return 0
    if volume_m3 > 2.5:
        return 3
    if volume_m3 > 1.0:
        return 2
    if volume_m3 > 0.3:
        return 1
    return 0


def classificar_entrega(delivery: DeliveryData, *, distancia_km: Optional[float] = None,
                        volume_m3: Optional[float] = None) -> DeliveryScore:
    """Combina critérios individuais em uma única nota."""

    breakdown: Dict[str, int] = {}
    breakdown["quantidade_itens"] = classificar_quantidade_itens(delivery.material)
    breakdown["urgencia"] = classificar_urgencia(delivery.urgencia)
    breakdown["destino"] = classificar_destino(delivery.responsavel)
    breakdown["distancia"] = classificar_distancia(distancia_km)
    breakdown["volume"] = classificar_transporte_por_volume(volume_m3)

    total = sum(breakdown.values())
    return DeliveryScore(total=total, breakdown=breakdown).capped()


__all__ = [
    "DeliveryScore",
    "classificar_entrega",
    "classificar_quantidade_itens",
    "classificar_urgencia",
    "classificar_destino",
    "classificar_distancia",
    "classificar_transporte_por_volume",
]
