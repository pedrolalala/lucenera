# -*- coding: utf-8 -*-
"""Rotinas para extração de informações de PDFs de separação/entrega."""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

log = logging.getLogger("entregas_pdf")

try:  # pdfplumber é opcional
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None  # type: ignore

DATE_PATTERN = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")
ITEM_PATTERN = re.compile(r"^\s*([A-Z0-9]{3,}[^\n]*?(\b\d{1,4}\b))", re.IGNORECASE)
CLIENT_PATTERN = re.compile(r"(?im)^(?:cliente|obra|loja)[:\-]\s*(.+)$")


def parse_separacao_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Extrai informações básicas do PDF de separação.

    Retorna dict com campos que podem ser usados para atualizar a entrega.
    Lança RuntimeError se pdfplumber não estiver disponível.
    """
    if pdfplumber is None:
        raise RuntimeError("pdfplumber não está instalado neste ambiente")

    if not pdf_bytes:
        raise ValueError("PDF vazio recebido para parse")

    linhas: List[str] = []
    clientes: List[str] = []
    datas: List[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            texto = page.extract_text() or ""
            for raw_line in texto.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                linhas.append(line)
                match_cliente = CLIENT_PATTERN.search(line)
                if match_cliente:
                    clientes.append(match_cliente.group(1).strip())
                for match_data in DATE_PATTERN.findall(line):
                    datas.append(match_data)

    total_itens = 0
    itens_detectados: List[str] = []
    for line in linhas:
        if ITEM_PATTERN.match(line):
            itens_detectados.append(line)
    total_itens = len(itens_detectados)

    data_prevista_pdf = None
    for raw in datas:
        try:
            data_prevista_pdf = datetime.strptime(raw, "%d/%m/%Y").date()
            break
        except ValueError:
            try:
                data_prevista_pdf = datetime.strptime(raw, "%d/%m/%y").date()
                break
            except ValueError:
                continue

    cliente_pdf = clientes[0].strip() if clientes else None

    log.info(
        "[entregas_pdf] Parse concluído: cliente=%s data=%s itens=%s",
        cliente_pdf,
        data_prevista_pdf,
        total_itens,
    )

    return {
        "cliente_pdf": cliente_pdf,
        "data_prevista_pdf": data_prevista_pdf,
        "total_itens": total_itens,
        "itens": itens_detectados,
    }
