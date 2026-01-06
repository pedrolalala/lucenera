# -*- coding: utf-8 -*-
"""Utilidades para agenda e capacidade de entregas programadas."""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

from supabase_client import get_supabase

log = logging.getLogger("entregas_agenda")

try:
    CAPACIDADE_PADRAO = int(os.getenv("ENTREGAS_CAPACIDADE_DIA", "10"))
except Exception:
    CAPACIDADE_PADRAO = 10


def to_int(value: Any, default: int = 0) -> int:
    """Converte value em int sempre que possível."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        try:
            return int(float(cleaned.replace(",", ".")))
        except Exception:
            digits = "".join(ch for ch in cleaned if ch.isdigit())
            return int(digits) if digits else default
    return default


def calcular_nivel(total_itens: Optional[int]) -> int:
    """Calcula o nível de carga conforme número de itens.

    Nível mínimo é 1 mesmo para total desconhecido ou zero.
    """
    try:
        total = int(total_itens or 0)
    except Exception:
        total = 0

    if total <= 5:
        return 1
    if total <= 10:
        return 2
    if total <= 20:
        return 3
    if total <= 40:
        return 4
    return 5


def soma_niveis_do_dia(dia: date) -> int:
    """Soma dos níveis planejados para o dia informado."""
    sb = get_supabase()
    if not sb:
        log.warning("Supabase indisponível ao somar níveis do dia %s", dia)
        return 0

    iso = dia.isoformat()
    try:
        resp = sb.table("entregas_programadas").select("nivel_entrega,status").eq("data_prevista", iso).execute()
    except Exception as exc:
        log.exception("Falha ao consultar entregas do dia %s: %s", iso, exc)
        return 0

    total = 0
    for row in (resp.data or []):
        if not isinstance(row, dict):
            continue
        status_val = row.get("status")
        status = str(status_val or "").strip().lower()
        if status in {"cancelada", "cancelado"}:
            continue
        try:
            total += to_int(row.get("nivel_entrega"))
        except Exception:
            continue
    return total


def verificar_disponibilidade(
    dia: date,
    nivel_novo: int,
    capacidade_dia: Optional[int] = None,
) -> bool:
    """Retorna True se houver capacidade remanescente para o nível solicitado."""
    capacidade = capacidade_dia or CAPACIDADE_PADRAO
    atual = soma_niveis_do_dia(dia)
    disponivel = (atual + max(nivel_novo, 0)) <= capacidade
    log.info(
        "[agenda] disponibilidade dia=%s atual=%s novo=%s cap=%s -> %s",
        dia,
        atual,
        nivel_novo,
        capacidade,
        disponivel,
    )
    return disponivel


def sugerir_proxima_data_disponivel(
    data_inicial: date,
    nivel_novo: int,
    janela: int = 14,
    capacidade_dia: Optional[int] = None,
) -> Optional[date]:
    """Busca a primeira data disponível dentro da janela informada."""
    capacidade = capacidade_dia or CAPACIDADE_PADRAO
    for offset in range(janela + 1):
        dia = data_inicial + timedelta(days=offset)
        if verificar_disponibilidade(dia, nivel_novo, capacidade):
            return dia
    return None
