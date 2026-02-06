# -*- coding: utf-8 -*-
# tasks.py
# Celery worker para processar mensagens (Lucenera) gerando rascunhos via ChatGPT.
# - Lê a mensagem (row ou row_id)
# - Consulta histórico e prompts na função centralizada gerar_resposta_com_chatgpt
# - Gera um rascunho (ai_draft) padronizado "*Julia:* "
# - Salva no Supabase como "awaiting_approval" (ou envia automaticamente se habilitado)

import os
import json
import time
import logging
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from celery import Celery
    _celery_import_error: Optional[ImportError] = None
except ImportError as _celery_err:  # pragma: no cover - ambiente sem Celery
    Celery = None  # type: ignore[assignment]
    _celery_import_error = _celery_err

if TYPE_CHECKING:
    from celery.app.task import Task as CeleryTask
else:  # ajuda Pylance sem depender do import em runtime
    CeleryTask = Any  # type: ignore[assignment]
from dotenv import load_dotenv

# envio centralizado via Z-API
from services.zapi_client import send_text_from_row
from services.debounce_manager import DebounceManager, DebouncePayload

# ========= Carrega .env =========
load_dotenv()

# ========= Logs básicos =========
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("tasks")

# ========= Resposta automatizada =========
from services.chatgpt_responder import gerar_resposta_com_chatgpt
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import _teams_notify
from services.entregas_pdf import parse_separacao_pdf
from services.entregas_agenda import calcular_nivel

# ========= Supabase =========
from supabase_client import get_supabase_client
from supabase_helpers import _sb_update, _get_row_id

# ========= App/Fluxo =========
APPROVAL_REQUIRED = (os.getenv("APPROVAL_REQUIRED", "true").lower() == "true")
AUTO_SEND_WHATSAPP = (os.getenv("AUTO_SEND_WHATSAPP", "false").lower() == "true") and (not APPROVAL_REQUIRED)

# ========= Celery =========
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

if Celery is None:
    raise RuntimeError("Celery is not available; install the celery package") from _celery_import_error

celery = Celery("lucenera_tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=os.getenv("TZ", "America/Sao_Paulo"),
    enable_utc=False,
)

# ========= Supabase client =========
_sb = get_supabase_client()

# ========= Debounce =========
DEBOUNCE_SECONDS = int(os.getenv("DEBOUNCE_SECONDS", "60") or "60")
debounce_manager = DebounceManager(delay_seconds=DEBOUNCE_SECONDS)

# ========= Duplicates =========
DUPLICATE_WINDOW_SECONDS = max(0, int(os.getenv("DUPLICATE_WINDOW_SECONDS", "120") or "120"))
DUPLICATE_LOOKBACK_LIMIT = max(1, int(os.getenv("DUPLICATE_LOOKBACK_LIMIT", "12") or "12"))


# --------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------
def _sb_fetch_mensagem_row(row_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """Busca uma linha da tabela 'mensagens' pelo id (single)."""
    if _sb is None:
        log.error("Supabase client indisponível ao buscar mensagem")
        return None
    try:
        resp = _sb.table("mensagens").select("*").eq("id", row_id).single().execute()
        data = resp.data
        if isinstance(data, dict):
            return data
        log.warning("mensagens[%s] retornou payload inesperado: %s", row_id, type(data).__name__)
        return None
    except Exception as e:
        log.exception(f"Falha ao buscar mensagem id={row_id}: {e}")
        return None


def _normalize_duplicate_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _extract_row_text_for_duplicate(row: Dict[str, Any]) -> str:
    candidates: List[Optional[str]] = []
    texto = row.get("texto")
    if isinstance(texto, str):
        candidates.append(texto)
    body = row.get("body")
    if isinstance(body, str):
        candidates.append(body)
    mensagem = row.get("mensagem")
    if isinstance(mensagem, dict):
        candidates.extend([
            mensagem.get("text"),
            mensagem.get("body"),
            mensagem.get("mensagem"),
        ])
        meta = mensagem.get("meta") or {}
        if isinstance(meta, dict):
            candidates.extend([
                meta.get("caption"),
                meta.get("preview"),
            ])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _parse_datetime_value(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(cleaned)
        except ValueError:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(cleaned, fmt)
                    break
                except ValueError:
                    dt = None
            if dt is None:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _extract_row_datetime(row: Dict[str, Any]) -> Optional[datetime]:
    for key in ("data", "created_at", "updated_at", "timestamp"):
        dt = _parse_datetime_value(row.get(key))
        if dt:
            return dt
    mensagem = row.get("mensagem")
    if isinstance(mensagem, dict):
        meta = mensagem.get("meta") or {}
        if isinstance(meta, dict):
            for key in ("timestamp_iso_utc", "timestamp_iso_sao_paulo", "timestamp"):
                dt = _parse_datetime_value(meta.get(key))
                if dt:
                    return dt
    return None


def _safe_int_id(value: Any) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def _fetch_recent_rows_for_phone(phone: str) -> List[Dict[str, Any]]:
    if not _sb or not phone:
        return []
    fields = "id,id_num,telefone,texto,body,mensagem,data,created_at,status"
    try:
        resp = (
            _sb.table("mensagens")
            .select(fields)
            .eq("telefone", phone)
            .order("data", desc=True)
            .limit(DUPLICATE_LOOKBACK_LIMIT)
            .execute()
        )
        rows = resp.data or []
        return [row for row in rows if isinstance(row, dict)]
    except Exception as exc:
        log.warning("Falha ao consultar duplicados por data para telefone=%s: %s", phone, exc)
        try:
            resp = (
                _sb.table("mensagens")
                .select(fields)
                .eq("telefone", phone)
                .order("created_at", desc=True)
                .limit(DUPLICATE_LOOKBACK_LIMIT)
                .execute()
            )
            rows = resp.data or []
            return [row for row in rows if isinstance(row, dict)]
        except Exception as fallback_exc:
            log.exception("Falha ao consultar duplicados fallback telefone=%s: %s", phone, fallback_exc)
            return []


def _detect_duplicate(row: Dict[str, Any], row_id: Union[int, str], texto_override: Optional[str]) -> Optional[Dict[str, Any]]:
    telefone_raw = row.get("telefone") or row.get("from") or row.get("phone")
    telefone = str(telefone_raw or "").strip()
    if not telefone:
        return None

    mensagem_texto = texto_override if isinstance(texto_override, str) else _extract_row_text_for_duplicate(row)
    if not mensagem_texto:
        return None

    normalized_text = _normalize_duplicate_text(mensagem_texto)
    if not normalized_text:
        return None

    current_dt = _extract_row_datetime(row)
    duplicates: List[Dict[str, Any]] = []
    for candidate in _fetch_recent_rows_for_phone(telefone):
        candidate_id = candidate.get("id") or candidate.get("id_num")
        if candidate_id is None or str(candidate_id) == str(row_id):
            continue
        candidate_text = _extract_row_text_for_duplicate(candidate)
        if not candidate_text:
            continue
        if _normalize_duplicate_text(candidate_text) != normalized_text:
            continue
        candidate_dt = _extract_row_datetime(candidate)
        if current_dt and candidate_dt and abs((current_dt - candidate_dt).total_seconds()) > DUPLICATE_WINDOW_SECONDS:
            continue
        duplicates.append(
            {
                "id": candidate_id,
                "status": candidate.get("status"),
                "timestamp": candidate_dt,
            }
        )

    if not duplicates:
        return None

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def _sort_key(item: Dict[str, Any]) -> tuple[datetime, int]:
        ts = item.get("timestamp")
        if isinstance(ts, datetime):
            return (ts, _safe_int_id(item.get("id")))
        return (epoch, _safe_int_id(item.get("id")))

    all_candidates = duplicates + [
        {
            "id": row_id,
            "status": row.get("status"),
            "timestamp": current_dt,
        }
    ]

    base_candidate = min(all_candidates, key=_sort_key)
    base_id = base_candidate.get("id")

    return {
        "base_id": base_id,
        "normalized_text": normalized_text,
        "current_timestamp": current_dt,
        "duplicates": duplicates,
    }


def _handle_duplicate(row: Dict[str, Any], row_id: Union[int, str], texto_usuario: Optional[str]) -> Optional[Dict[str, Any]]:
    detection = _detect_duplicate(row, row_id, texto_usuario)
    if not detection:
        return None

    base_id = detection.get("base_id")
    duplicates: List[Dict[str, Any]] = detection.get("duplicates", [])
    if base_id is None:
        return None

    for candidate in duplicates:
        candidate_id = candidate.get("id")
        if candidate_id is None or str(candidate_id) == str(base_id):
            continue
        candidate_status = str(candidate.get("status") or "").lower()
        if candidate_status == "duplicate":
            continue
        try:
            _sb_update(candidate_id, {"status": "duplicate"})
        except Exception as exc:
            log.warning("Falha ao marcar duplicado existente %s: %s", candidate_id, exc)

    duplicate_meta = {
        "duplicate_of": base_id,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "window_seconds": DUPLICATE_WINDOW_SECONDS,
    }

    analysis_payload: Optional[str] = None
    raw_analysis = row.get("analysis")
    existing_analysis: Dict[str, Any]
    if isinstance(raw_analysis, str) and raw_analysis.strip():
        try:
            parsed_analysis = json.loads(raw_analysis)
            if isinstance(parsed_analysis, dict):
                existing_analysis = dict(parsed_analysis)
            else:
                existing_analysis = {"previous_analysis": parsed_analysis}
        except Exception:
            existing_analysis = {"previous_analysis": raw_analysis}
    else:
        existing_analysis = {}

    if isinstance(existing_analysis, dict):
        existing_analysis["duplicate"] = duplicate_meta
        analysis_payload = json.dumps(existing_analysis, ensure_ascii=False)
    else:
        analysis_payload = json.dumps({"duplicate": duplicate_meta}, ensure_ascii=False)

    update_payload = {
        "status": "duplicate",
        "analysis": analysis_payload,
    }

    try:
        _sb_update(row_id, update_payload)
    except Exception as exc:
        log.warning("Falha ao atualizar mensagem %s como duplicada: %s", row_id, exc)

    log.info("Mensagem ignorada (duplicada): row_id=%s base_id=%s", row_id, base_id)

    return {
        "ok": True,
        "row_id": row_id,
        "status": "duplicate",
        "sent": False,
        "duplicate_of": base_id,
    }


def _coerce_attachments(raw: Any) -> List[Dict[str, Any]]:
    """Normaliza o campo de anexos vindo do Supabase."""
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            log.warning(f"Falha ao decodificar anexos JSON: {exc}")
            return []
        if isinstance(parsed, list):
            return [entry for entry in parsed if isinstance(entry, dict)]
    return []


def _download_attachment(url: str, timeout: int = 30) -> Optional[bytes]:
    """Baixa o conteúdo binário do anexo informado."""
    if not url:
        return None
    try:
        req = Request(url, headers={"User-Agent": os.getenv("ENTREGAS_PDF_UA", "LuceneraBot/1.0")})
        with urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", 200) or 200
            if status >= 400:
                log.warning(f"Download do anexo falhou: status={status} url={url}")
                return None
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        log.warning(f"Erro de rede ao baixar anexo {url}: {exc}")
        return None
    except Exception as exc:  # pragma: no cover - erros inesperados
        log.exception(f"Erro inesperado ao baixar anexo {url}: {exc}")
        return None


def _row_chat_key(row: Dict[str, Any]) -> str:
    """
    Gera uma chave única por chat: prioriza group_id; senão telefone; senão um fallback.
    """
    gid = str(row.get("group_id") or "").strip()
    phone = str(row.get("telefone") or row.get("from") or "").strip()
    if gid:
        return f"group:{gid}"
    if phone:
        return f"phone:{phone}"
    return f"anon:{row.get('id') or time.time()}"


def _atualizar_ai_draft_e_status(row_id: Union[int, str], draft: str, status: str, extras: Optional[Dict[str, Any]] = None):
    data = {"ai_draft": draft, "status": status}
    if extras:
        data.update(extras)
    try:
        _sb_update(row_id, data)
        log.info(f"mensagens[{row_id}] atualizado: status={status}")
    except Exception as e:
        log.exception(f"Falha ao atualizar mensagens[{row_id}]: {e}")

    # Notifica Teams se status='awaiting_approval' e ai_draft preenchido
    if status == "awaiting_approval" and draft and isinstance(draft, str) and draft.strip():
        telefone = None
        mensagem = None
        try:
            # Busca row atualizada para garantir campos
            row = _sb_fetch_mensagem_row(row_id)
            if not row:
                log.warning(f"[TEAMS NOTIFY] Falha: não foi possível buscar row id={row_id} para notificação Teams.")
                return
            telefone = row.get("telefone")
            mensagem = ((row.get("mensagem") or {}).get("text") or "").strip()
            log.info(f"[TEAMS NOTIFY] Tentando notificar Teams: telefone={telefone} | msg={mensagem} | status={status}")
            _teams_notify(row, draft, route=None, channel="projetos")
            log.info(f"[TEAMS NOTIFY] Sucesso: telefone={telefone} | msg={mensagem} | status=notificado | canal=projetos")
        except Exception as e:
            log.warning(f"[TEAMS NOTIFY] Falha ao enviar para Teams: row_id={row_id}, telefone={telefone}, msg={mensagem}, erro={e}")


# --------------------------------------------------------------------------------------
# Tarefa principal
# --------------------------------------------------------------------------------------
@celery.task(name="lucenera.processar_mensagem", bind=True)
def processar_mensagem(self, row_or_id: Union[Dict[str, Any], int, str]) -> Dict[str, Any]:
    """
    Processa uma mensagem e gera rascunho (ai_draft).
    row_or_id: pode ser o dict da linha ou apenas o id.
    Retorna um resumo do processamento.
    """
    # 1) Carrega row
    if isinstance(row_or_id, (int, str)):
        row_id = _get_row_id({"id": row_or_id})  # normaliza para int
        if row_id is None:
            raise RuntimeError("mensagens[id] inválido ou ausente.")
        row = _sb_fetch_mensagem_row(row_id)
        if not row:
            raise RuntimeError(f"mensagens[{row_id}] não encontrada.")
    elif isinstance(row_or_id, dict):
        row = row_or_id
        row_id = _get_row_id(row)
        if row_id is None:
            raise RuntimeError("mensagens[row.id] inválido ou ausente.")
    else:
        raise ValueError("row_or_id deve ser dict ou id")

    # 2) Campos principais
    texto_usuario = (row.get("texto") or row.get("body") or "").strip()
    if not texto_usuario:
        _atualizar_ai_draft_e_status(row_id, "*Julia:* Mensagem vazia (sem texto).", "awaiting_approval")
        return {"ok": True, "row_id": row_id, "skipped": "sem_texto"}

    duplicate_result = _handle_duplicate(row, row_id, texto_usuario)
    if duplicate_result:
        return duplicate_result

    chat_key = _row_chat_key(row)

    debounce_result = debounce_manager.add_message(chat_key, row, texto_usuario)
    if debounce_result.get("should_schedule"):
        try:
            cast(CeleryTask, processar_mensagem_debounce).apply_async((chat_key,), countdown=DEBOUNCE_SECONDS)
        except Exception as exc:
            log.exception(f"Falha ao agendar debounce para chat_key={chat_key}: {exc}")
            # se agendamento falhar, processa imediatamente o bloco atual
            payload = debounce_manager.consume(chat_key)
            if payload:
                return _processar_bloco_debounce(chat_key, payload)
            raise

    _sb_update(row_id, {"status": "debouncing"})

    return {
        "ok": True,
        "row_id": row_id,
        "status": "debouncing",
        "sent": False,
        "buffer_count": debounce_result.get("count", 1),
    }


def _aplicar_meta_debounce(row: Dict[str, Any], row_id: Union[int, str], payload: DebouncePayload) -> Dict[str, Any]:
    combined_text = (payload.get("combined_text") or "").strip()
    mensagem = row.get("mensagem") if isinstance(row.get("mensagem"), dict) else {}
    mensagem = dict(mensagem or {})
    mensagem["text"] = combined_text
    meta = dict(mensagem.get("meta") or {})
    meta["debounce_batch_ids"] = payload.get("row_ids", [])
    meta["debounce_raw_messages"] = payload.get("raw_texts", [])
    meta["debounce_message_count"] = len(payload.get("raw_texts", []))
    meta["debounce_combined_at"] = datetime.now(timezone.utc).isoformat()
    mensagem["meta"] = meta

    updated_row = dict(row)
    updated_row["texto"] = combined_text
    if "body" in row:
        updated_row["body"] = combined_text
    updated_row["mensagem"] = mensagem

    update_fields: Dict[str, Any] = {"texto": combined_text, "mensagem": mensagem}
    if "body" in row:
        update_fields["body"] = combined_text
    _sb_update(row_id, update_fields)
    return updated_row


def _gerar_resposta_para_chat(
    row: Dict[str, Any],
    row_id: Union[int, str],
    texto_usuario: str,
    chat_key: str,
    *,
    debounce_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    user_identifier = row.get("user_id") or row.get("telefone") or row.get("from") or str(chat_key)
    try:
        resposta = gerar_resposta_com_chatgpt(
            texto_usuario,
            str(user_identifier),
            mensagem_id=row_id,
            telefone=row.get("telefone") or row.get("from"),
        )
    except Exception as exc:
        log.exception(f"Falha ao gerar resposta ChatGPT para chat_key={chat_key}: {exc}")
        _atualizar_ai_draft_e_status(row_id, "", "error", {"error": f"chatgpt_error: {exc}"})
        raise

    analysis_data: Dict[str, Any] = {
        "chat_key": chat_key,
        "used_tools": False,
        "inline": False,
        "generator": "chatgpt",
        "history_source": "table_messages",
    }
    if debounce_meta:
        analysis_data["debounce"] = debounce_meta

    extras = {
        "analysis": json.dumps(analysis_data, ensure_ascii=False)
    }

    if APPROVAL_REQUIRED:
        _atualizar_ai_draft_e_status(row_id, resposta, "awaiting_approval", extras)
        sent = False
        status = "awaiting_approval"
    else:
        if AUTO_SEND_WHATSAPP and send_text_from_row(row, resposta):
            _atualizar_ai_draft_e_status(row_id, resposta, "sent", extras)
            sent = True
            status = "sent"
        else:
            _atualizar_ai_draft_e_status(row_id, resposta, "awaiting_approval", extras)
            sent = False
            status = "awaiting_approval"

    return {
        "ok": True,
        "row_id": row_id,
        "status": status,
        "sent": sent,
        "debounced": bool(debounce_meta),
    }


def _processar_bloco_debounce(chat_key: str, payload: DebouncePayload) -> Dict[str, Any]:
    if not payload or not payload.get("rows"):
        log.info(f"Debounce vazio para chat_key={chat_key}")
        return {"ok": False, "chat_key": chat_key, "skipped": "debounce_vazio"}

    row_ids = payload.get("row_ids", []) or []
    if row_ids:
        for rid in row_ids[:-1]:
            try:
                _sb_update(rid, {"status": "debounced"})
            except Exception:
                log.debug(f"Nao foi possivel marcar mensagem {rid} como debounced")

    last_row = payload["rows"][-1]
    row_id = _get_row_id(last_row)
    if row_id is None:
        log.error(f"Row final sem id no debounce para chat_key={chat_key}")
        return {"ok": False, "chat_key": chat_key, "error": "row_id_missing"}

    combined_text = (payload.get("combined_text") or "").strip()
    base_row = _sb_fetch_mensagem_row(row_id) or last_row

    if not combined_text:
        _atualizar_ai_draft_e_status(row_id, "*Julia:* Mensagem vazia (sem texto).", "awaiting_approval")
        return {"ok": True, "row_id": row_id, "status": "awaiting_approval", "sent": False, "debounced": True, "skipped": "texto_vazio"}

    row_para_envio = _aplicar_meta_debounce(base_row, row_id, payload)

    debounce_meta = {
        "count": len(payload.get("raw_texts", [])),
        "row_ids": row_ids,
    }

    return _gerar_resposta_para_chat(row_para_envio, row_id, combined_text, chat_key, debounce_meta=debounce_meta)


@celery.task(name="lucenera.processar_mensagem_debounce", bind=True)
def processar_mensagem_debounce(self, chat_key: str) -> Dict[str, Any]:
    payload = debounce_manager.consume(chat_key)
    if not payload:
        log.info(f"Nada a processar no debounce para chat_key={chat_key}")
        return {"ok": False, "chat_key": chat_key, "skipped": "payload_vazio"}
    return _processar_bloco_debounce(chat_key, payload)

processar_mensagem_debounce = cast(CeleryTask, processar_mensagem_debounce)


@celery.task(name="lucenera.processar_entrega_pdfs", bind=True)
def processar_entrega_pdfs(self, entrega_id: Union[int, str]) -> Dict[str, Any]:
    """Processa anexos de PDFs de uma entrega programada."""
    result: Dict[str, Any] = {"ok": False, "entrega_id": entrega_id}

    if not _sb:
        log.error("Supabase indisponível ao processar PDFs de entrega")
        result["error"] = "supabase_indisponivel"
        return result

    try:
        entrega_id_int = int(entrega_id)
    except (TypeError, ValueError):
        result["error"] = "id_invalido"
        return result

    try:
        resp = _sb.table("entregas_programadas").select("*").eq("id", entrega_id_int).single().execute()
        entrega = resp.data or {}
    except Exception as exc:
        log.exception(f"Falha ao buscar entrega {entrega_id_int}: {exc}")
        result["error"] = "consulta_supabase"
        return result

    if not isinstance(entrega, dict):
        log.error(f"Entrega {entrega_id_int} retornou payload inesperado: {type(entrega).__name__}")
        result["error"] = "registro_invalido"
        return result

    anexos = _coerce_attachments(entrega.get("arquivos"))
    if not anexos:
        result.update({"ok": True, "updated_fields": [], "skipped": "sem_arquivos"})
        return result

    parse_results: List[Dict[str, Any]] = []
    for anexo in anexos:
        url = str(anexo.get("url") or anexo.get("href") or "").strip()
        if not url:
            continue
        pdf_bytes = _download_attachment(url)
        if not pdf_bytes:
            continue
        try:
            parsed = parse_separacao_pdf(pdf_bytes)
        except Exception as exc:
            log.warning(f"Falha ao parsear PDF da entrega {entrega_id_int}: {exc}")
            continue
        parsed["attachment"] = anexo.get("name") or anexo.get("filename") or url
        parse_results.append(parsed)

    if not parse_results:
        result.update({"ok": True, "updated_fields": [], "skipped": "parse_sem_resultado"})
        return result

    best = max(parse_results, key=lambda item: item.get("total_itens") or 0)
    updates: Dict[str, Any] = {}

    total_itens = best.get("total_itens")
    if isinstance(total_itens, int) and total_itens >= 0:
        updates["total_itens"] = total_itens
        updates["nivel_entrega"] = calcular_nivel(total_itens)

    data_prevista_pdf = best.get("data_prevista_pdf")
    if data_prevista_pdf and not entrega.get("data_prevista"):
        updates["data_prevista"] = data_prevista_pdf.isoformat()

    cliente_pdf = best.get("cliente_pdf")
    if cliente_pdf and not entrega.get("cliente"):
        updates["cliente"] = cliente_pdf

    if entrega.get("status") == "aguardando_pdf_parse":
        updates["status"] = "registrada"

    if updates:
        updates["updated_at"] = datetime.utcnow().isoformat()
    else:
        result.update({"ok": True, "updated_fields": [], "skipped": "sem_updates"})
        return result

    try:
        _sb.table("entregas_programadas").update(updates).eq("id", entrega_id_int).execute()
    except Exception as exc:
        log.exception(f"Falha ao atualizar entrega {entrega_id_int}: {exc}")
        result["error"] = "update_supabase"
        return result

    result.update(
        {
            "ok": True,
            "updated_fields": list(updates.keys()),
            "parsed": {
                "attachment": best.get("attachment"),
                "total_itens": total_itens,
                "cliente_pdf": cliente_pdf,
                "data_prevista_pdf": data_prevista_pdf.isoformat() if data_prevista_pdf else None,
            },
        }
    )
    log.info(
        "[entregas_pdf] entrega_id=%s atualizado com campos %s",
        entrega_id_int,
        ",".join(result["updated_fields"]),
    )
    return result


# --------------------------------------------------------------------------------------
# Tarefa auxiliar: reprocessar por id (atalho)
# --------------------------------------------------------------------------------------
@celery.task(name="lucenera.reprocessar_por_id", bind=True)
def reprocessar_por_id(self, row_id: Union[int, str]) -> Dict[str, Any]:
    """Apenas atalho para chamar processar_mensagem com um id."""
    return cast(CeleryTask, processar_mensagem).run(row_id)
