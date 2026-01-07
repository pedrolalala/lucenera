# -*- coding: utf-8 -*-
# tasks.py
# Celery worker para processar mensagens (Lucenera) usando OpenAI Assistants v2.
# - Lê a mensagem (row ou row_id)
# - Cria/usa uma Thread por chat (grupo/contato)
# - Executa o Assistant (com function calling via on_requires_action_runner)
# - Gera um rascunho (ai_draft) padronizado "Julia."
# - Salva no Supabase como "awaiting_approval" (ou envia automaticamente se habilitado)

import os
import json
import time
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from celery import Celery
from dotenv import load_dotenv

# envio centralizado via Z-API
from services.zapi_client import send_text_from_row

# ========= Carrega .env =========
load_dotenv()

# ========= Logs básicos =========
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("tasks")

# ========= OpenAI / Assistants =========
from services.openai_helpers import (
    cliente,
    formatar_resposta_julia,
    aguardar_run,
)
from services.tools_runner import on_requires_action_runner
from services.threads import get_or_create_thread_id
from services.entregas_pdf import parse_separacao_pdf
from services.entregas_agenda import calcular_nivel

# ========= Regras e contexto (opcionais) =========
from selecionar_persona import selecionar_persona
from selecionar_documento import selecionar_contexto

# ========= Supabase =========
from supabase_client import get_supabase_client
from supabase_helpers import _sb_update, _get_row_id

# ========= App/Fluxo =========
ASSISTANT_ID = os.getenv("ASSISTANT_ID_LUCENERA") or ""  # obrigatório para Assistants
APPROVAL_REQUIRED = (os.getenv("APPROVAL_REQUIRED", "true").lower() == "true")
AUTO_SEND_WHATSAPP = (os.getenv("AUTO_SEND_WHATSAPP", "false").lower() == "true") and (not APPROVAL_REQUIRED)

# ========= Celery =========
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

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


# --------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------
def _sb_fetch_mensagem_row(row_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """Busca uma linha da tabela 'mensagens' pelo id (single)."""
    try:
        resp = _sb.table("mensagens").select("*").eq("id", row_id).single().execute()
        return (resp.data or None)
    except Exception as e:
        log.exception(f"Falha ao buscar mensagem id={row_id}: {e}")
        return None


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


def _montar_instructions(row: Dict[str, Any]) -> Optional[str]:
    """
    (Opcional) Injeta instruções dinâmicas com base em persona/documento.
    Se preferir, retorne None para usar só as Instruções do Assistant.
    """
    try:
        in_group = bool(row.get("in_group"))
        group_name = str(row.get("group_name") or "").strip()
        sender_name = str(row.get("sender_name") or row.get("nome") or "").strip()

        persona = selecionar_persona(
            origem="whatsapp",
            grupo=group_name if in_group else "",
            remetente=sender_name,
        )
        contexto = selecionar_contexto(row)  # seu seletor pode ler projeto/aba/arquivo do SharePoint/Excel

        # Esqueleto simples — ajuste conforme preferir
        partes = []
        if persona:
            partes.append(f"[PERSONA]\n{json.dumps(persona, ensure_ascii=False)}")
        if contexto:
            partes.append(f"[CONTEXTO]\n{json.dumps(contexto, ensure_ascii=False)}")
        partes.append(
            "[REGRAS]\n"
            "- Responda com dados reais do contexto (SharePoint/Excel/Supabase) quando existirem.\n"
            "- Se faltar dado, faça só 1 pergunta objetiva.\n"
            "- Seja breve, direto e profissional. Não invente.\n"
            "- Formate a resposta curta para WhatsApp.\n"
        )
        return "\n\n".join(partes)
    except Exception as e:
        log.warning(f"Falha ao montar instructions dinâmicas: {e}")
        return None


def _atualizar_ai_draft_e_status(row_id: Union[int, str], draft: str, status: str, extras: Optional[Dict[str, Any]] = None):
    data = {"ai_draft": draft, "status": status}
    if extras:
        data.update(extras)
    try:
        _sb_update("mensagens", row_id, data)
        log.info(f"mensagens[{row_id}] atualizado: status={status}")
    except Exception as e:
        log.exception(f"Falha ao atualizar mensagens[{row_id}]: {e}")


def _criar_run_e_aguardar(assistant_id: str, thread_id: str, instructions: Optional[str]) -> str:
    """
    Adiciona a tool-run handler (on_requires_action_runner) e aguarda conclusão.
    Retorna o texto final do assistente (ou vazio).
    """
    run = cliente.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=instructions,
    )
    texto = aguardar_run(
        thread_id,
        run,
        timeout_s=int(os.getenv("ASSISTANTS_TIMEOUT_S", "90")),
        on_requires_action=on_requires_action_runner,  # <- IMPORTANTE: habilita as tools
    )
    return texto or ""


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
    if not ASSISTANT_ID:
        raise RuntimeError("Defina ASSISTANT_ID_LUCENERA no .env")

    # 1) Carrega row
    if isinstance(row_or_id, (int, str)):
        row_id = _get_row_id(row_or_id)  # normaliza para int
        row = _sb_fetch_mensagem_row(row_id)
        if not row:
            raise RuntimeError(f"mensagens[{row_id}] não encontrada.")
    elif isinstance(row_or_id, dict):
        row = row_or_id
        row_id = _get_row_id(row.get("id"))
    else:
        raise ValueError("row_or_id deve ser dict ou id")

    # 2) Campos principais
    texto_usuario = (row.get("texto") or row.get("body") or "").strip()
    if not texto_usuario:
        _atualizar_ai_draft_e_status(row_id, "Julia.\nMensagem vazia (sem texto).", "awaiting_approval")
        return {"ok": True, "row_id": row_id, "skipped": "sem_texto"}

    chat_key = _row_chat_key(row)

    # 3) Thread por chat
    thread_id = get_or_create_thread_id(chat_key)

    # 4) Injeta mensagem do usuário na thread
    try:
        cliente.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=texto_usuario
        )
    except Exception as e:
        log.exception(f"Falha ao criar mensagem na thread {thread_id}: {e}")
        raise

    # 5) Instruções dinâmicas (opcional)
    instructions = _montar_instructions(row)

    # 6) Executa Assistant e aguarda (com tools)
    texto = _criar_run_e_aguardar(ASSISTANT_ID, thread_id, instructions)
    resposta = formatar_resposta_julia(texto)

    # 7) Atualiza Supabase
    extras = {
        "thread_id": thread_id,
        "assistant_id": ASSISTANT_ID,
        "analysis": json.dumps({
            "chat_key": chat_key,
            "used_tools": True,
            "inline": False,
        }, ensure_ascii=False)
    }

    if APPROVAL_REQUIRED:
        _atualizar_ai_draft_e_status(row_id, resposta, "awaiting_approval", extras)
        sent = False
        status = "awaiting_approval"
    else:
        # envio automático (se habilitado)
        if AUTO_SEND_WHATSAPP and send_text_from_row(row, resposta):
            _atualizar_ai_draft_e_status(row_id, resposta, "sent", extras)
            sent = True
            status = "sent"
        else:
            _atualizar_ai_draft_e_status(row_id, resposta, "awaiting_approval", extras)
            sent = False
            status = "awaiting_approval"

    # 8) Retorno
    return {
        "ok": True,
        "row_id": row_id,
        "thread_id": thread_id,
        "assistant_id": ASSISTANT_ID,
        "status": status,
        "sent": sent,
    }


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
    return processar_mensagem(row_id)
