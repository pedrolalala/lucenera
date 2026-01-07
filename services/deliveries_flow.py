"""Delivery confirmation wizard for whitelisted phones."""
from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import re

from services.config_equipes import ENTREGADORES_WHATS
from supabase_utils import (
    create_delivery_session,
    finalize_delivery_session,
    get_open_delivery_session,
    insert_delivery,
    create_signed_url,
    upload_to_storage,
    update_delivery_session,
)
from services.zapi_client import download_media_bytes

STATE_WAITING_CODE = "AGUARDANDO_CODIGO"
STATE_WAITING_PHOTO = "AGUARDANDO_FOTO"
STATE_WAITING_RECEIVER = "AGUARDANDO_RECEBEDOR"
STATE_WAITING_OBSERVATION = "AGUARDANDO_OBSERVACAO"
STATE_DONE = "FINALIZADO"
STATE_CANCELLED = "CANCELADO"
TEXT_START = "Vamos registrar a entrega. Qual o código da obra?"
TEXT_NEED_CODE = "Não encontrei o código da obra. Pode enviar somente os números?"
TEXT_AFTER_CODE = "Perfeito. Agora me mande *1 foto* da entrega finalizada."
TEXT_NEED_PHOTO = "Nao encontrei a foto. Pode enviar uma imagem da entrega?"
TEXT_AFTER_PHOTO = "Obrigado! Quem foi a pessoa que recebeu na obra?"
TEXT_NEED_RECEIVER = "Preciso do nome de quem recebeu a entrega."
TEXT_AFTER_RECEIVER = "Se tudo certo responda NÃO; se houve algo descreva aqui."
TEXT_FINAL = "Entrega registrada e finalizada ✅ Obrigado!"
TEXT_CANCELLED = "Fluxo cancelado. Envie 'entrega finalizada' para iniciar novamente."
TEXT_NO_SESSION = "Nenhuma confirmacao de entrega ativa. Envie 'entrega finalizada' para iniciar."
TEXT_SAVE_ERROR = "Não consegui salvar a entrega no sistema. Avise o administrador."
TEXT_DOWNLOAD_FAIL = "Não consegui baixar a imagem. Envie novamente."
TEXT_UPLOAD_FAIL = "Não consegui salvar a foto no sistema. Envie novamente."

START_KEYWORDS = {
    "entrega finalizada",
    "registrar entrega",
    "confirmar entrega",
}
STATUS_KEYWORDS = {
    "status",
    "andamento",
    "etapa",
    "progresso",
}
CANCEL_COMMANDS = {
    "cancelar",
    "cancel",
    "parar",
    "pare",
}

STEP_PROMPTS = {
    STATE_WAITING_CODE: "Falta informar o código da obra.",
    STATE_WAITING_PHOTO: "Falta enviar a foto da entrega.",
    STATE_WAITING_RECEIVER: "Falta informar quem recebeu a entrega.",
    STATE_WAITING_OBSERVATION: "Falta informar se há alguma observação.",
}

DELIVERY_STORAGE_BUCKET = "entregas"
SIGNED_URL_TTL_SECONDS = 3600


_SESSION_CACHE: Dict[str, Dict[str, Any]] = {}


def _normalize_phone(value: Optional[str]) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _norm_text(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.strip().lower().split())


def get_text(payload: Optional[Dict[str, Any]]) -> str:
    if not isinstance(payload, dict):
        return ""
    mensagem = payload.get("mensagem")
    if isinstance(mensagem, dict):
        for key in ("text", "body", "message"):
            val = mensagem.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    if isinstance(mensagem, str) and mensagem.strip():
        return mensagem.strip()
    for key in ("text", "body", "message"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def get_phone(payload: Optional[Dict[str, Any]]) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("telefone", "phone", "chat_phone", "raw_telefone"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            norm = _normalize_phone(val)
            if norm:
                return norm
    return ""


logger = logging.getLogger("deliveries.flow")


def _extract_media_info(payload: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    if not isinstance(payload, dict):
        return {}

    media_keys = ("image", "media", "document")
    message_media_keys = ("image", "media", "document")
    id_keys = (
        "id",
        "media_id",
        "mediaId",
        "file_id",
        "fileId",
        "document_id",
        "documentId",
        "image_id",
        "imageId",
        "messageId",
    )
    url_keys = (
        "url",
        "link",
        "downloadUrl",
        "download_url",
        "imageUrl",
        "image_url",
        "mediaUrl",
        "media_url",
        "fileUrl",
        "file_url",
    )

    def _scan(value: Any) -> Dict[str, Optional[str]]:
        if isinstance(value, dict):
            media_id: Optional[str] = None
            for key in id_keys:
                candidate = value.get(key)
                if isinstance(candidate, str):
                    candidate = candidate.strip()
                    if candidate:
                        media_id = candidate
                        break

            media_url: Optional[str] = None
            for key in url_keys:
                candidate = value.get(key)
                if isinstance(candidate, str):
                    candidate = candidate.strip()
                    if candidate:
                        media_url = candidate
                        break
            if media_id or media_url:
                return {
                    "media_id": media_id.strip() if isinstance(media_id, str) else media_id,
                    "media_url": media_url.strip() if isinstance(media_url, str) else media_url,
                }
            for nested in value.values():
                found = _scan(nested)
                if found:
                    return found
        if isinstance(value, list):
            for item in value:
                found = _scan(item)
                if found:
                    return found
        if isinstance(value, str) and value.strip():
            return {"media_id": None, "media_url": value.strip()}
        return {}

    candidates = []
    for key in media_keys:
        if key in payload:
            candidates.append(payload.get(key))

    message = payload.get("message")
    if isinstance(message, dict):
        for key in message_media_keys:
            if key in message:
                candidates.append(message.get(key))

    for candidate in candidates:
        found = _scan(candidate)
        if found:
            return found

    return {}


def _extract_obra_codigo(text: Optional[str]) -> str:
    if not text:
        return ""
    digits = re.findall(r"\d+", text)
    if not digits:
        return ""
    return "".join(digits)


def _build_photo_path(obra_codigo: str, phone: str) -> str:
    safe_obra = obra_codigo or "unknown"
    safe_phone = "".join(ch for ch in phone if ch.isdigit()) or "anon"
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    return f"{safe_obra}/{date_part}/{time_part}_{safe_phone}.jpg"


def _normalize_storage_path(path_value: Optional[str]) -> str:
    path = str(path_value or "").strip().strip('"').strip("'").strip()
    if path.startswith("entregas/"):
        path = path[len("entregas/") :]
    return path


def _is_cancel_command(text_norm: str) -> bool:
    if not text_norm:
        return False
    for keyword in CANCEL_COMMANDS:
        if text_norm == keyword or text_norm.startswith(f"{keyword} "):
            return True
    return False


def _teams_notify(event: str, payload: Dict[str, Any], teams_notify_func: Optional[Callable[[str, Dict[str, Any]], None]]) -> None:
    if teams_notify_func:
        try:
            teams_notify_func(event, payload)
        except Exception as exc:
            logger.warning("DELIVERY_TEAMS_FAIL event=%s error=%s", event, exc)


def handle_event(
    row: Dict[str, Any],
    phone: str,
    *,
    raw_event: Optional[Dict[str, Any]] = None,
    supabase_client=None,
    teams_notify_func: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Optional[str]:
    phone_norm = _normalize_phone(phone) or get_phone(row) or get_phone(raw_event)
    if phone_norm not in ENTREGADORES_WHATS:
        return None

    text = get_text(row) or get_text(raw_event)
    text_norm = _norm_text(text)

    logger.info("DELIVERY_SESSION_LOOKUP phone=%s", phone_norm)
    try:
        session = get_open_delivery_session(phone_norm, supabase_client)
    except Exception:
        logger.exception("SUPABASE_DELIVERY_ERROR action=get_open_session phone=%s", phone_norm)
        return TEXT_SAVE_ERROR

    session_id = session.get("id") if isinstance(session, dict) else None
    current_step = (session.get("step") or "").strip().upper() if session else ""
    if session_id:
        cache_entry = _SESSION_CACHE.setdefault(phone_norm, {})
        cache_entry.setdefault("session_id", session_id)
    if session_id:
        logger.info(
            "DELIVERY_SESSION_LOOKUP_RESULT phone=%s found=True session_id=%s step=%s",
            phone_norm,
            session_id,
            current_step or "-",
        )
    else:
        logger.info(
            "DELIVERY_SESSION_LOOKUP_RESULT phone=%s found=False session_id=- step=-",
            phone_norm,
        )

    if _is_cancel_command(text_norm):
        if session_id:
            try:
                finalize_delivery_session(session_id, {"step": STATE_CANCELLED}, supabase_client)
            except Exception:
                logger.exception("Failed to cancel session session_id=%s", session_id)
                return TEXT_SAVE_ERROR
            _SESSION_CACHE.pop(phone_norm, None)
        return TEXT_CANCELLED

    if text_norm in STATUS_KEYWORDS:
        if not session:
            return TEXT_NO_SESSION
        step = (session.get("step") or "").strip().upper()
        pending = STEP_PROMPTS.get(step, "Fluxo finalizado.")
        return pending

    if any(keyword in text_norm for keyword in START_KEYWORDS):
        if session_id:
            try:
                finalize_delivery_session(session_id, {"step": STATE_CANCELLED}, supabase_client)
            except Exception:
                logger.exception("Failed to finalize stale session session_id=%s", session_id)
        logger.info("DELIVERY_SESSION_CREATE_ATTEMPT phone=%s", phone_norm)
        try:
            session = create_delivery_session(
                phone_norm,
                supabase_client,
                obra_codigo=None,
                foto_media_id=None,
                foto_path=None,
                recebedor_nome=None,
                observacao=None,
            )
        except Exception:
            logger.exception("SUPABASE_DELIVERY_ERROR action=create_session phone=%s", phone_norm)
            return TEXT_SAVE_ERROR
        session_id = session.get("id") if isinstance(session, dict) else None
        logger.info(
            "DELIVERY_SESSION_CREATE_OK phone=%s session_id=%s step=%s",
            phone_norm,
            session_id or "-",
            STATE_WAITING_CODE,
        )
        _SESSION_CACHE[phone_norm] = {"session_id": session_id, "obra_codigo": None}
        _teams_notify("start", {"phone": phone_norm}, teams_notify_func)
        return TEXT_START

    if not session or not session_id:
        return TEXT_NO_SESSION

    step = current_step or STATE_WAITING_CODE

    if step == STATE_WAITING_CODE:
        obra_codigo = _extract_obra_codigo(text)
        if not obra_codigo:
            return TEXT_NEED_CODE
        try:
            updated = update_delivery_session(
                session_id,
                {
                    "step": STATE_WAITING_PHOTO,
                    "obra_codigo": obra_codigo,
                },
                supabase_client,
            )
        except Exception:
            logger.exception("Failed to store obra codigo session_id=%s", session_id)
            return TEXT_SAVE_ERROR
        if not updated:
            return TEXT_SAVE_ERROR
        session = updated
        cache_entry = _SESSION_CACHE.setdefault(phone_norm, {})
        cache_entry.update({"session_id": session_id, "obra_codigo": obra_codigo})
        logger.info("DELIVERY_SET_OBRA phone=%s obra=%s", phone_norm, obra_codigo)
        return TEXT_AFTER_CODE

    if step == STATE_WAITING_PHOTO:
        obra_codigo = (session.get("obra_codigo") or "").strip() if isinstance(session, dict) else ""
        if not obra_codigo:
            return TEXT_NEED_CODE
        media_info = _extract_media_info(row) or _extract_media_info(raw_event)
        media_url_raw = media_info.get("media_url") if media_info else None
        media_id_raw = media_info.get("media_id") if media_info else None
        media_url = media_url_raw.strip() if isinstance(media_url_raw, str) else None
        media_id = media_id_raw.strip() if isinstance(media_id_raw, str) else None
        has_photo = bool((media_url or "").strip() or (media_id or "").strip())
        logger.info(
            "DELIVERY_MEDIA_IDENTIFIED phone=%s media_id=%s media_url_present=%s",
            phone_norm,
            media_id or "-",
            bool(media_url),
        )
        if not has_photo:
            return TEXT_NEED_PHOTO
        object_path = _build_photo_path(obra_codigo, phone_norm)
        object_path = _normalize_storage_path(object_path)
        media_context = dict(media_info or {})
        if media_url and "media_url" not in media_context:
            media_context["media_url"] = media_url
        if media_id and "media_id" not in media_context:
            media_context["media_id"] = media_id

        pre_update: Dict[str, Any] = {}
        if media_id or media_url:
            pre_update["foto_media_id"] = media_id or media_url
        if media_url:
            pre_update["foto_url"] = media_url
        if pre_update:
            try:
                update_delivery_session(session_id, pre_update, supabase_client)
            except Exception:
                logger.warning(
                    "DELIVERY_PHOTO_PREUPDATE_FAIL phone=%s session_id=%s",
                    phone_norm,
                    session_id,
                )
        logger.info(
            "DELIVERY_MEDIA_DOWNLOAD_ATTEMPT phone=%s media_id=%s media_url=%s",
            phone_norm,
            media_id or "-",
            media_url or "-",
        )
        try:
            media_bytes, media_content_type = download_media_bytes(media_context)
        except Exception:
            logger.exception(
                "DELIVERY_PHOTO_DOWNLOAD_FAIL phone=%s media_id=%s media_url=%s",
                phone_norm,
                media_id or "-",
                media_url or "-",
            )
            return TEXT_DOWNLOAD_FAIL
        bytes_len = len(media_bytes)
        logger.info(
            "DELIVERY_MEDIA_DOWNLOAD_OK phone=%s bytes_len=%s content_type=%s",
            phone_norm,
            bytes_len,
            (media_content_type or "-")[:200],
        )
        content_type = media_content_type or "image/jpeg"
        logger.info(
            "DELIVERY_UPLOAD_START bucket=%s path=%s bytes_len=%s content_type=%s",
            DELIVERY_STORAGE_BUCKET,
            object_path,
            bytes_len,
            content_type,
        )
        try:
            upload_result = upload_to_storage(
                bucket=DELIVERY_STORAGE_BUCKET,
                object_path=object_path,
                content_bytes=media_bytes,
                content_type=content_type,
                client=supabase_client,
            )
        except Exception:
            logger.exception(
                "DELIVERY_UPLOAD_EXCEPTION bucket=%s path=%s",
                DELIVERY_STORAGE_BUCKET,
                object_path,
            )
            return TEXT_UPLOAD_FAIL

        upload_ok = bool(upload_result and upload_result.get("ok"))
        upload_error = (upload_result or {}).get("error") if upload_result else "upload failed"
        logger.info(
            "DELIVERY_UPLOAD_RESULT bucket=%s path=%s ok=%s error=%s",
            DELIVERY_STORAGE_BUCKET,
            (upload_result or {}).get("path") or object_path,
            upload_ok,
            upload_error or "-",
        )
        if not upload_ok:
            return TEXT_UPLOAD_FAIL

        foto_url_signed = None
        try:
            foto_url_signed = create_signed_url(
                bucket=DELIVERY_STORAGE_BUCKET,
                object_path=object_path,
                expires_seconds=SIGNED_URL_TTL_SECONDS,
                client=supabase_client,
            )
        except Exception:
            logger.warning(
                "DELIVERY_PHOTO_SIGNED_URL_FAIL phone=%s bucket=%s path=%s",
                phone_norm,
                DELIVERY_STORAGE_BUCKET,
                object_path,
            )
        update_fields: Dict[str, Any] = {
            "step": STATE_WAITING_RECEIVER,
            "foto_media_id": media_id or media_url,
            "foto_path": object_path,
        }
        if media_url:
            update_fields.setdefault("foto_url", media_url)
        if not media_url and foto_url_signed:
            update_fields["foto_url"] = foto_url_signed
        try:
            updated = update_delivery_session(session_id, update_fields, supabase_client)
        except Exception:
            logger.exception("Failed to store delivery photo session_id=%s", session_id)
            return TEXT_SAVE_ERROR
        if not updated:
            return TEXT_SAVE_ERROR
        session = updated
        cache_entry = _SESSION_CACHE.setdefault(phone_norm, {})
        cache_entry.update(
            {
                "session_id": session_id,
                "obra_codigo": obra_codigo,
                "foto_media_id": media_id or media_url,
                "foto_path": object_path,
                "foto_url": foto_url_signed,
            }
        )
        logger.info(
            "DELIVERY_PHOTO_ACCEPTED phone=%s obra=%s media_id=%s",
            phone_norm,
            obra_codigo,
            media_id or media_url or "-",
        )
        return TEXT_AFTER_PHOTO

    if step == STATE_WAITING_RECEIVER:
        if not text_norm:
            return TEXT_NEED_RECEIVER
        receiver_name = (text or "").strip()
        update_payload: Dict[str, Any] = {
            "step": STATE_WAITING_OBSERVATION,
            "recebedor_nome": receiver_name,
        }
        try:
            updated = update_delivery_session(session_id, update_payload, supabase_client)
        except Exception:
            logger.exception("Failed to store receiver session_id=%s", session_id)
            return TEXT_SAVE_ERROR
        if not updated:
            return TEXT_SAVE_ERROR
        session = updated
        cache_entry = _SESSION_CACHE.setdefault(phone_norm, {})
        cache_entry.update({"session_id": session_id, "recebedor_nome": receiver_name})
        return TEXT_AFTER_RECEIVER

    if step == STATE_WAITING_OBSERVATION:
        obs_norm = _norm_text(text)
        observacao = None
        text_clean = (text or "").strip()
        null_markers = {
            "nao",
            "ok",
            "sem",
            "tudo certo",
            "sem observacao",
            "sem observacoes",
            "sem obs",
        }
        if text_clean and obs_norm not in null_markers:
            observacao = text_clean
        cache_entry = _SESSION_CACHE.setdefault(phone_norm, {})
        cache_entry.update({"observacao": observacao})
        obra_codigo = cache_entry.get("obra_codigo") or (
            (session.get("obra_codigo") or "").strip() if isinstance(session, dict) else ""
        )
        recebedor = cache_entry.get("recebedor_nome") or (
            (session.get("recebedor_nome") or "").strip() if isinstance(session, dict) else ""
        )
        foto_path = cache_entry.get("foto_path") or (session.get("foto_path") if isinstance(session, dict) else None)
        foto_media_id = cache_entry.get("foto_media_id") or (
            (session.get("foto_media_id") or None) if isinstance(session, dict) else None
        )
        foto_url = cache_entry.get("foto_url") or (
            (session.get("foto_url") or None) if isinstance(session, dict) else None
        )
        foto_path = _normalize_storage_path(foto_path)
        itens_mencionados_values = sorted({match.upper() for match in re.findall(r"\bL\d{1,4}\b", text_clean or "", re.IGNORECASE)})
        itens_mencionados = ",".join(itens_mencionados_values) if itens_mencionados_values else None
        try:
            delivery_row = insert_delivery(
                {
                    "obra_codigo": obra_codigo,
                    "entregador_phone": phone_norm,
                    "recebedor_nome": recebedor or "",
                    "observacao": observacao,
                    "foto_path": foto_path,
                    "foto_url": foto_url,
                    "itens_mencionados": itens_mencionados,
                },
                supabase_client,
            )
        except Exception:
            logger.exception("Failed to insert delivery obra=%s phone=%s", obra_codigo, phone_norm)
            return TEXT_SAVE_ERROR
        delivery_id = delivery_row.get("id") if isinstance(delivery_row, dict) else None
        try:
            final_session = finalize_delivery_session(
                session_id,
                {
                    "step": STATE_DONE,
                },
                supabase_client,
            )
        except Exception:
            logger.exception("Failed to finalize session session_id=%s", session_id)
            return TEXT_SAVE_ERROR
        session = final_session or session
        logger.info(
            "DELIVERY_FINALIZED phone=%s obra=%s delivery_id=%s",
            phone_norm,
            obra_codigo or "-",
            delivery_id or "-",
        )
        _teams_notify(
            "finish",
            {
                "phone": phone_norm,
                "obra_codigo": obra_codigo,
                "recebedor_nome": recebedor,
                "observacao": observacao,
                "foto_path": foto_path,
                "foto_media_id": foto_media_id,
                "foto_url": foto_url,
                "delivery_id": delivery_id,
                "itens_mencionados": itens_mencionados,
            },
            teams_notify_func,
        )
        _SESSION_CACHE.pop(phone_norm, None)
        return TEXT_FINAL

    return None
