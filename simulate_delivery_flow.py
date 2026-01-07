"""Simulate delivery wizard flow against Supabase."""

import json

from supabase_client import get_supabase_client
from services.deliveries_flow import handle_event

PHONE = "5516992089829"


def snapshot(label: str) -> None:
    supabase = get_supabase_client()
    if supabase is None:
        raise RuntimeError("Supabase client indisponível para snapshot")
    resp = (
        supabase
        .table("delivery_sessions")
        .select("*")
        .eq("entregador_phone", PHONE)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    print(f"{label}: {json.dumps(resp.data, ensure_ascii=False)}")


def run() -> None:
    supabase = get_supabase_client()
    if supabase is None:
        raise RuntimeError("Supabase client indisponível para simulação")
    start_event = {"telefone": PHONE, "mensagem": {"text": "Entrega finalizada"}}
    reply1 = handle_event(start_event, PHONE, raw_event=start_event, supabase_client=supabase)
    print("reply_start:", reply1)
    snapshot("after_start")

    code_event = {"telefone": PHONE, "mensagem": {"text": "25180"}}
    reply2 = handle_event(code_event, PHONE, raw_event=code_event, supabase_client=supabase)
    print("reply_code:", reply2)
    snapshot("after_code")
if __name__ == "__main__":
    run()
