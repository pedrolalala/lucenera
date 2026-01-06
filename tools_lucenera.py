# -*- coding: utf-8 -*-
# C:\script python\lucenera\tools_lucenera.py

from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

def validar_codigo_promocional(*, codigo: str, validade: str) -> Dict[str, Any]:
    codigo = (codigo or "").strip()
    validade_str = (validade or "").strip()
    if not codigo:
        return {"ok": False, "erro": "codigo_nao_informado", "mensagem_usuario": "Informe um código."}
    if not validade_str:
        return {"ok": False, "erro": "validade_nao_informada", "codigo": codigo,
                "mensagem_usuario": "Informe validade YYYY-MM-DD."}
    try:
        validade_dt = datetime.strptime(validade_str, "%Y-%m-%d").date()
    except ValueError:
        return {"ok": False, "erro": "formato_de_data_invalido", "codigo": codigo,
                "validade": validade_str, "mensagem_usuario": "Use YYYY-MM-DD."}

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    valido = validade_dt >= hoje
    return {
        "ok": True,
        "codigo": codigo,
        "validade": validade_dt.isoformat(),
        "valido": bool(valido),
        "status": "válido" if valido else "expirado",
        "mensagem_usuario": f"Código {codigo}: {'válido' if valido else 'expirado'}."
    }

# mapping usado pelo runner:
minhas_funcoes = {
    "validar_codigo_promocional": validar_codigo_promocional,
}

# (opcional, só para CRIAR/atualizar o Assistant)
TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "validar_codigo_promocional",
            "description": "Valida um código promocional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo": {"type": "string"},
                    "validade": {"type": "string", "description": "YYYY-MM-DD"}
                },
                "required": ["codigo", "validade"],
                "additionalProperties": False
            }
        }
    },
]
