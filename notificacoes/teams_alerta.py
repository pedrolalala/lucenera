"""Helpers para alertas no canal de Falhas do Microsoft Teams."""
import logging
import os
from typing import Any, Optional

import requests

_LOG = logging.getLogger("teams.alerta")

_DEFAULT_HINT = (
    "Verifique o log de processamento para entender a falha. "
    "Mensagem pode estar malformada ou sem contexto suficiente."
)


def enviar_falha_para_teams(
    *,
    telefone: Optional[str] = None,
    mensagem: Optional[str] = None,
    erro: Optional[str] = None,
    mensagem_id: Optional[Any] = None,
    dica: Optional[str] = None,
) -> bool:
    """Envia notificacao de falha para o canal dedicado no Teams."""
    webhook = (
        os.getenv("TEAMS_FALHAS_WEBHOOK")
        or os.getenv("TEAMS_WEBHOOK_FALHAS")
        or ""
    )
    if not webhook:
        _LOG.warning("TEAMS_FALHAS_WEBHOOK_MISSING")
        return False

    telefone_txt = (telefone or "desconhecido").strip() or "desconhecido"
    mensagem_txt = (mensagem or "(sem mensagem)").strip() or "(sem mensagem)"
    erro_txt = (erro or "(sem detalhes)").strip() or "(sem detalhes)"
    dica_txt = (dica or _DEFAULT_HINT).strip() or _DEFAULT_HINT

    linhas: list[str] = [
        "🚨 Falha registrada no fluxo Lucenera",
        f"• Telefone: {telefone_txt}",
        f"• Mensagem: {mensagem_txt}",
        f"• Erro: {erro_txt}",
    ]
    if mensagem_id is not None:
        linhas.insert(1, f"• Mensagem ID: {mensagem_id}")
    linhas.append(f"• Dica: {dica_txt}")

    conteudo_formatado = "\n".join(linhas).strip()
    if not conteudo_formatado:
        conteudo_formatado = "🚨 Falha registrada no fluxo Lucenera, sem detalhes adicionais disponíveis."

    print(f"[LOG] Enviando falha para Teams: {conteudo_formatado}")

    try:
        resp = requests.post(webhook, json={"text": conteudo_formatado}, timeout=10)
        if resp.status_code >= 400:
            _LOG.warning(
                "TEAMS_FALHAS_WEBHOOK_POST_FAIL status=%s body=%s",
                resp.status_code,
                resp.text[:300],
            )
            return False
        return True
    except Exception as exc:  # pragma: no cover - depende de rede externa
        _LOG.exception("TEAMS_FALHAS_WEBHOOK_EXCEPTION err=%s", exc)
        return False
