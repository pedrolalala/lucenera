"""Parser dedicado para mensagens de entregas recebidas via Microsoft Teams."""
from __future__ import annotations

import dataclasses
import datetime as _dt
import logging
import re
from typing import Dict, Optional

LOGGER = logging.getLogger(__name__)

_URGENT_TERMS = {
    "urgente",
    "assim que possivel",
    "assim que possível",
    "hoje",
    "imediato",
    "sedex",
    "prioridade",
    "para agora",
}

_DATE_PATTERN = re.compile(r"(?P<day>\d{1,2})[\/-](?P<month>\d{1,2})(?:[\/-](?P<year>\d{2,4}))?", re.IGNORECASE)


@dataclasses.dataclass(slots=True)
class ParsedEntrega:
    """Estrutura intermediária antes de persistir a entrega."""

    cliente: Optional[str]
    endereco: Optional[str]
    responsavel: Optional[str]
    data_entrega: Optional[_dt.date]
    materiais: Optional[str]
    urgencia: bool
    canal_origem: str
    raw_mensagem: str

    def to_record(self) -> Dict[str, object]:
        """Converte para dicionário pronto para ser salvo no Supabase."""

        return {
            "cliente": self.cliente,
            "endereco": self.endereco,
            "responsavel": self.responsavel,
            "data_entrega": self.data_entrega.isoformat() if self.data_entrega else None,
            "materiais": self.materiais,
            "urgencia": self.urgencia,
            "canal_origem": self.canal_origem,
            "raw_mensagem": self.raw_mensagem,
        }


def _normalize_text(texto: Optional[str]) -> str:
    return (texto or "").strip()


def _detectar_urgencia(texto: str) -> bool:
    texto_lower = texto.lower()
    for termo in _URGENT_TERMS:
        if termo in texto_lower:
            return True
    return False


def _extrair_por_rotulo(texto: str, rotulo: str) -> Optional[str]:
    padrao = re.compile(rf"{rotulo}\s*[:\-]\s*(?P<valor>.+)", re.IGNORECASE)
    match = padrao.search(texto)
    if match:
        return match.group("valor").strip()
    return None


def _extrair_data(texto: str) -> Optional[_dt.date]:
    match = _DATE_PATTERN.search(texto)
    if not match:
        return None
    day = int(match.group("day"))
    month = int(match.group("month"))
    year = match.group("year")
    if year:
        year_value = int(year)
        if year_value < 100:
            year_value += 2000
    else:
        year_value = _dt.date.today().year
    try:
        return _dt.date(year_value, month, day)
    except ValueError:
        LOGGER.debug("Data inválida encontrada em mensagem do Teams: %s", match.group(0))
        return None


def parse_entrega_teams(payload: Dict[str, object]) -> ParsedEntrega:
    """Extrai dados relevantes da mensagem enviada via Teams."""

    raw_mensagem = payload.get("mensagem") if isinstance(payload, dict) else None
    mensagem = _normalize_text(raw_mensagem if isinstance(raw_mensagem, str) else None)
    anexos = payload.get("anexos") if isinstance(payload, dict) else None

    cliente = _extrair_por_rotulo(mensagem, "cliente")
    endereco = _extrair_por_rotulo(mensagem, "endereco") or _extrair_por_rotulo(mensagem, "endereço")
    responsavel = _extrair_por_rotulo(mensagem, "responsavel") or _extrair_por_rotulo(mensagem, "responsável")
    data_entrega = _extrair_data(mensagem)

    materiais = _extrair_por_rotulo(mensagem, "material") or _extrair_por_rotulo(mensagem, "materiais")

    if anexos:
        materiais = (materiais or "") + "\n[Anexos disponíveis para processamento futuro]"

    urgencia = _detectar_urgencia(mensagem)

    parsed = ParsedEntrega(
        cliente=cliente,
        endereco=endereco,
        responsavel=responsavel,
        data_entrega=data_entrega,
        materiais=materiais,
        urgencia=urgencia,
        canal_origem="teams",
        raw_mensagem=mensagem,
    )
    return parsed


__all__ = ["ParsedEntrega", "parse_entrega_teams"]
