# -*- coding: utf-8 -*-
"""Gerenciador simples de debounce em memoria por chat."""
from __future__ import annotations

import threading
import time
import logging
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("debounce.manager")


class DebouncePayload(Dict[str, Any]):
    """Dicionario tipado contendo os dados agregados do debounce."""


class DebounceManager:
    """Controla o agrupamento temporario de mensagens por chat_id."""

    def __init__(self, delay_seconds: int = 60) -> None:
        self.delay_seconds = max(int(delay_seconds or 0), 0)
        self._lock = threading.Lock()
        self._entries: Dict[str, Dict[str, Any]] = {}

    def add_message(self, chat_key: str, row: Dict[str, Any], texto: str) -> Dict[str, Any]:
        """Adiciona uma mensagem ao buffer do chat e retorna dados de controle."""
        if not chat_key:
            raise ValueError("chat_key obrigatório para debounce")

        normalized = str(chat_key)
        now = time.monotonic()
        row_id = row.get("id") or row.get("row_id")
        texto_limpo = (texto or "").strip()

        with self._lock:
            LOGGER.debug("Debounce acquire for chat_key=%s", normalized)
            entry = self._entries.get(normalized)
            if entry is None:
                entry = {
                    "first_ts": now,
                    "rows": [],
                    "texts": [],
                    "row_ids": [],
                    "scheduled": False,
                }
                self._entries[normalized] = entry
                LOGGER.debug("Debounce created buffer chat_key=%s", normalized)

            entry["rows"].append(row)
            entry["texts"].append(texto_limpo)
            if row_id is not None:
                entry["row_ids"].append(row_id)
            entry["last_ts"] = now

            should_schedule = not entry["scheduled"]
            if should_schedule:
                entry["scheduled"] = True

            result = {
                "should_schedule": should_schedule,
                "count": len(entry["texts"]),
                "row_ids": list(entry["row_ids"]),
            }
        LOGGER.debug(
            "Debounce buffered chat_key=%s count=%d scheduled=%s",
            normalized,
            result.get("count", 0),
            result.get("should_schedule"),
        )
        return result

    def consume(self, chat_key: str) -> Optional[DebouncePayload]:
        """Remove e retorna o payload agregado para o chat informado."""
        normalized = str(chat_key)
        with self._lock:
            entry = self._entries.pop(normalized, None)

        if entry is None:
            return None

        texts = [t for t in entry.get("texts", []) if t]
        combined = "\n".join(texts).strip()

        LOGGER.debug(
            "Debounce consume chat_key=%s count=%d combined_started=%r",
            normalized,
            len(texts),
            combined[:48] if combined else "",
        )
        payload: DebouncePayload = DebouncePayload(
            chat_id=normalized,
            combined_text=combined,
            rows=list(entry.get("rows", [])),
            row_ids=list(entry.get("row_ids", [])),
            raw_texts=list(entry.get("texts", [])),
            first_ts=entry.get("first_ts"),
            last_ts=entry.get("last_ts"),
        )
        return payload

    def peek_size(self, chat_key: str) -> int:
        """Retorna a quantidade de mensagens acumuladas sem consumir."""
        normalized = str(chat_key)
        with self._lock:
            entry = self._entries.get(normalized)
            if not entry:
                return 0
            return len(entry.get("texts", []))


__all__ = ["DebounceManager", "DebouncePayload"]
