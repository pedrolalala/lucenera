# -*- coding: utf-8 -*-
# services/tools_runner.py
# Integra Assistants v2 (requires_action) com as suas funções Python.

from __future__ import annotations

import json
from typing import Any, Dict, List

from tools_lucenera import minhas_funcoes  # nome_da_tool -> função Python


def _to_json_str(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "erro": f"json_dump_error: {e}"})


def _call_function(fn, fargs_obj: Any) -> Any:
    """
    Tenta kwargs (fn(**dict)). Se não der, tenta passar o dict como único argumento (fn(dict)).
    """
    if isinstance(fargs_obj, dict):
        try:
            return fn(**fargs_obj)
        except TypeError:
            return fn(fargs_obj)
    return fn(fargs_obj)


def on_requires_action_runner(run: Any) -> List[Dict[str, str]]:
    """
    Lê tool_calls do 'run', executa as funções mapeadas em 'minhas_funcoes'
    e retorna [{"tool_call_id": "...", "output": "<string JSON>"}]
    """
    ra = getattr(run, "required_action", None)
    sto = getattr(ra, "submit_tool_outputs", None)
    tool_calls = getattr(sto, "tool_calls", None) if sto else None
    if not tool_calls:
        return []

    outputs: List[Dict[str, str]] = []

    for call in tool_calls:
        fn_name = getattr(getattr(call, "function", None), "name", "") or ""
        args_raw = getattr(getattr(call, "function", None), "arguments", "") or "{}"

        # parse arguments
        try:
            fargs = json.loads(args_raw)
        except Exception:
            fargs = {}

        fn = minhas_funcoes.get(fn_name)
        if not fn:
            outputs.append({
                "tool_call_id": call.id,
                "output": _to_json_str({"ok": False, "erro": f"funcao_nao_encontrada: {fn_name}"})
            })
            continue

        try:
            result = _call_function(fn, fargs)
            outputs.append({
                "tool_call_id": call.id,
                "output": _to_json_str(result if result is not None else {"ok": True})
            })
        except Exception as e:
            outputs.append({
                "tool_call_id": call.id,
                "output": _to_json_str({"ok": False, "erro": str(e)})
            })

    return outputs
