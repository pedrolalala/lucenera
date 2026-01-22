"""Parsing helpers para extrair dados de entregas em diferentes formatos.

Todas as funções retornam objetos ``DeliveryData`` que podem ser facilmente
serializados, testados e utilizados pelas demais camadas do sistema.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, Optional

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class DeliveryData:
    """Representa as informações mínimas de uma entrega."""

    cliente: Optional[str] = None
    data: Optional[_dt.date] = None
    responsavel: Optional[str] = None
    endereco: Optional[str] = None
    material: Optional[str] = None
    urgencia: bool = False
    observacoes: Optional[str] = None
    origem: Optional[str] = None

    def to_payload(self) -> Dict[str, Optional[str]]:
        """Serializa para dicionário simples, útil para persistência/testes."""

        payload = {
            "cliente": self.cliente,
            "data": self.data.isoformat() if self.data else None,
            "responsavel": self.responsavel,
            "endereco": self.endereco,
            "material": self.material,
            "urgencia": self.urgencia,
            "observacoes": self.observacoes,
            "origem": self.origem,
        }
        return payload


_DATE_PATTERNS: Iterable[str] = (
    r"(?P<day>\d{1,2})[\/-](?P<month>\d{1,2})",  # 16/01 ou 16-01
)

_URGENT_TERMS: Iterable[str] = ("urgente", "prioridade", "prazo curto", "hoje")
_RESPONSAVEL_HINTS = ("responsavel", "responsável", "entregar para", "portaria")


def _parse_date(raw: str) -> Optional[_dt.date]:
    raw = raw.strip()
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if not match:
            continue
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = _dt.date.today().year
        try:
            return _dt.date(year, month, day)
        except ValueError:
            LOGGER.debug("Data fora do range detectada: %s", raw)
    return None


def parse_text_message(body: str, origem: str | None = None) -> DeliveryData:
    """Extrai dados de uma mensagem textual solta enviada via chat/email.

    Esta função cobre o exemplo clássico descrito na especificação, buscando
    termos-chaves por regex e fallback em heurísticas simples. Caso um campo
    não seja encontrado, ele permanece ``None`` para tratamento posterior.
    """

    if not body:
        return DeliveryData(origem=origem)

    lower = body.lower()
    data = _parse_date(body) or _parse_date(lower)

    cliente_match = re.search(r"cliente\s*[:\-]\s*(?P<value>.+)", body, flags=re.IGNORECASE)
    responsavel_match = re.search(
        r"respons[aá]vel\s*[:\-]\s*(?P<value>.+)", body, flags=re.IGNORECASE
    )
    endereco_match = re.search(r"end(er|)e[cç]o\s*[:\-]\s*(?P<value>.+)", body, flags=re.IGNORECASE)

    # Material pode estar em lista textual; capturamos bloco após "Material".
    material_match = re.search(
        r"material\s*[:\-]\s*(?P<value>(.+\n?)+)", body, flags=re.IGNORECASE
    )

    responsavel = None
    if responsavel_match:
        responsavel = responsavel_match.group("value").strip()
    elif "portaria" in lower:
        responsavel = "Portaria"

    urgencia = any(term in lower for term in _URGENT_TERMS)

    delivery = DeliveryData(
        cliente=cliente_match.group("value").strip() if cliente_match else None,
        data=data,
        responsavel=responsavel,
        endereco=endereco_match.group("value").strip() if endereco_match else None,
        material=material_match.group("value").strip() if material_match else None,
        urgencia=urgencia,
        observacoes=None,
        origem=origem,
    )
    return delivery


def parse_pdf_separacao(file_path: str | Path, origem: str | None = None) -> DeliveryData:
    """Extrai dados de PDF utilizando pdfplumber quando disponível.

    Retorna ``DeliveryData`` parcialmente preenchido. Quando a biblioteca
    ``pdfplumber`` não estiver instalada, registra aviso no log para futura
    instrumentação.
    """

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    try:
        import pdfplumber  # type: ignore
    except Exception as exc:  # pragma: no cover - dependência opcional
        LOGGER.warning("pdfplumber ausente para parse de PDF: %s", exc)
        return DeliveryData(origem=origem)

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return parse_text_message(text, origem=origem)


def parse_audio_notas(transcricao: str, origem: str | None = None) -> DeliveryData:
    """Recebe a transcrição de um áudio e reutiliza o parser textual."""

    return parse_text_message(transcricao, origem=origem)


def parse_generic_message(payload: Dict[str, str]) -> DeliveryData:
    """Parser resiliente para mensagens já estruturadas em dicionário."""

    delivery = DeliveryData(
        cliente=payload.get("cliente"),
        responsavel=payload.get("responsavel"),
        endereco=payload.get("endereco"),
        material=payload.get("material"),
        urgencia=payload.get("urgencia", "").lower() in {"1", "true", "yes", "sim"},
        observacoes=payload.get("observacoes"),
        origem=payload.get("origem"),
    )

    if payload.get("data"):
        try:
            delivery.data = _dt.date.fromisoformat(payload["data"])
        except ValueError:
            delivery.data = _parse_date(payload["data"])

    return delivery


__all__ = [
    "DeliveryData",
    "parse_text_message",
    "parse_pdf_separacao",
    "parse_audio_notas",
    "parse_generic_message",
]
