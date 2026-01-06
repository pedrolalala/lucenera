# -*- coding: utf-8 -*-
"""Rotas relacionadas à agenda de entregas integradas ao Teams."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser
from flask import Blueprint, current_app, jsonify, request

from supabase_client import get_supabase
from services.entregas_agenda import calcular_nivel

log = logging.getLogger("teams_entregas")

teams_entregas_bp = Blueprint("teams_entregas", __name__)

FIELD_PATTERNS = {
    "cliente": [r"(?im)^cliente[:\-]\s*(.+)$", r"(?im)^cliente\s*[-–]\s*(.+)$"],
    "quando": [r"(?im)^(?:quando|data|dia)[:\-]\s*(.+)$"],
    "tipo": [r"(?im)^(?:tipo|modalidade|entrega/retirada)[:\-]\s*(.+)$"],
    "endereco": [r"(?im)^(?:end[ée]re?co|local)[:\-]\s*(.+)$"],
    "responsavel_nome": [r"(?im)^(?:respons[áa]vel|contato)[:\-]\s*(.+)$"],
    "responsavel_tel": [r"(?im)^(?:tel|telefone|whatsapp)[:\-]\s*(.+)$"],
    "material_desc": [r"(?im)^(?:material|itens|produto[s]?|materiais)[:\-]\s*(.+)$"],
    "observacoes": [r"(?im)^(?:observa[cç][ãa]o(?:es)?|obs)[:\-]\s*(.+)$"],
    "total_itens": [r"(?im)^(?:total\s*(?:de\s*)?itens|qtde|quantidade)[:\-]\s*(\d+)$"],
}


def _compare_token(incoming: Optional[str], expected: Optional[str]) -> bool:
    if not expected:
        return True
    if not incoming:
        return False
    try:
        return hmac.compare_digest(incoming.strip(), expected.strip())
    except Exception:
        return False


def _validate_signature(raw_body: bytes) -> bool:
    expected = os.getenv("TEAMS_ENTREGAS_TOKEN")
    if not expected:
        return True

    header_sig = request.headers.get("X-Signature")
    header_token = request.headers.get("X-Token")
    if header_sig:
        try:
            algo, signature = header_sig.split("=", 1)
        except ValueError:
            signature = ""
            algo = "sha256"
        algo = algo.lower()
        if algo not in {"sha256", "sha1"}:
            algo = "sha256"
        digestmod = hashlib.sha256 if algo == "sha256" else hashlib.sha1
        computed = hmac.new(expected.encode("utf-8"), raw_body or b"", digestmod).hexdigest()
        return hmac.compare_digest(signature, computed)
    return _compare_token(header_token or request.args.get("token"), expected)


def _extract_field(name: str, text: str) -> Optional[str]:
    patterns = FIELD_PATTERNS.get(name, [])
    for pattern in patterns:
        match = re_search(pattern, text)
        if match:
            return match.strip()
    return None


def re_search(pattern: str, text: str) -> Optional[str]:
    import re

    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1)
    return None


def _only_digits(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _parse_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = date_parser.parse(value, dayfirst=True, fuzzy=True)
        return dt.date().isoformat()
    except Exception:
        return None


def _detect_periodo(text: str) -> Optional[str]:
    lower = text.lower()
    if "manhã" in lower or "manha" in lower:
        return "manha"
    if "tarde" in lower:
        return "tarde"
    if "noite" in lower:
        return "noite"
    return None


def _detect_tipo(value: Optional[str], text: str) -> Optional[str]:
    candidate = (value or "").strip().lower()
    if "retirada" in candidate or "retira" in candidate:
        return "retirada"
    if "entrega" in candidate:
        return "entrega"
    lower = text.lower()
    if "retirada" in lower:
        return "retirada"
    if "entrega" in lower:
        return "entrega"
    return candidate or None


def _sanitize_attachments(attachments: Any) -> List[Dict[str, Any]]:
    safe: List[Dict[str, Any]] = []
    if not isinstance(attachments, list):
        return safe
    for entry in attachments:
        if not isinstance(entry, dict):
            continue
        payload: Dict[str, Any] = {}
        name = entry.get("name") or entry.get("filename")
        url = entry.get("url") or entry.get("href")
        if name:
            payload["name"] = str(name)
        if url:
            payload["url"] = str(url)
        if payload:
            safe.append(payload)
    return safe


@teams_entregas_bp.route("/webhook/teams/entregas", methods=["POST"])
def registrar_entrega_programada():
    raw_body = request.get_data(cache=False, as_text=False) or b""
    if not _validate_signature(raw_body):
        return jsonify({"success": False, "error": "Token inválido."}), 403

    try:
        payload = request.get_json(force=True) or {}
    except Exception as exc:
        log.exception("Payload inválido no webhook de entregas: %s", exc)
        return jsonify({"success": False, "error": "JSON inválido"}), 400

    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "error": "Campo 'text' obrigatório."}), 400

    author = (payload.get("author") or "").strip() or "Teams"
    msg_id = (payload.get("msg_id") or "").strip() or None
    attachments = _sanitize_attachments(payload.get("attachments"))

    cliente = _extract_field("cliente", text)
    quando_txt = _extract_field("quando", text)
    data_prevista = _parse_date(quando_txt)
    periodo = _detect_periodo(text)
    tipo_txt = _extract_field("tipo", text)
    tipo = _detect_tipo(tipo_txt, text)
    endereco = _extract_field("endereco", text)
    responsavel_nome = _extract_field("responsavel_nome", text)
    responsavel_tel = _only_digits(_extract_field("responsavel_tel", text))
    material_desc = _extract_field("material_desc", text)
    observacoes = _extract_field("observacoes", text)
    total_itens_raw = _extract_field("total_itens", text)

    if not observacoes:
        observacoes = text

    try:
        total_itens = int(total_itens_raw) if total_itens_raw else 0
    except ValueError:
        total_itens = 0
    nivel = calcular_nivel(total_itens)
    status = "aguardando_pdf_parse" if attachments else "registrada"

    registro = {
        "cliente": cliente,
        "tipo": tipo,
        "data_prevista": data_prevista,
        "periodo": periodo,
        "endereco": endereco,
        "responsavel_nome": responsavel_nome,
        "responsavel_tel": responsavel_tel,
        "material_desc": material_desc,
        "observacoes": observacoes,
        "arquivos": attachments or None,
        "total_itens": total_itens,
        "nivel_entrega": nivel,
        "status": status,
        "criado_por": author,
        "origem_teams_msg": msg_id,
        "updated_at": datetime.utcnow().isoformat(),
    }

    registro = {k: v for k, v in registro.items() if v is not None}

    sb = get_supabase()
    if not sb:
        log.error("Supabase indisponível ao registrar entrega")
        return jsonify({"success": False, "error": "Supabase não configurado."}), 500

    try:
        resp = sb.table("entregas_programadas").upsert(
            registro,
            on_conflict="cliente,data_prevista,endereco",
        ).execute()
        saved = (resp.data or [None])[0]
        entrega_id = saved.get("id") if isinstance(saved, dict) else None
    except Exception as exc:
        current_app.logger.exception("Falha ao inserir entrega programada: %s", exc)
        return jsonify({"success": False, "error": "Falha ao salvar entrega."}), 500

    task_enqueued = False
    if attachments and entrega_id:
        try:
            from lucenera.tasks import processar_entrega_pdfs  # import tardio

            task_async = getattr(processar_entrega_pdfs, "delay")(entrega_id)
            task_enqueued = True
            task_id = getattr(task_async, "id", None)
            log.info(
                "[teams_entregas] processamento de PDFs enfileirado: entrega_id=%s task_id=%s",
                entrega_id,
                task_id,
            )
        except Exception:
            log.exception("Falha ao enfileirar processamento de PDFs", extra={"entrega_id": entrega_id})

    return jsonify(
        {
            "success": True,
            "entrega_id": entrega_id,
            "task_enqueued": task_enqueued,
        }
    )
