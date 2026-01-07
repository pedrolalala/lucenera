"""Diagnostic script for delivery Supabase access."""

import os
import traceback

from supabase_client import ensure_env_loaded, get_supabase_client

ensure_env_loaded()

DELIVERY_SESSIONS_TABLE = os.getenv("DELIVERY_SESSIONS_TABLE", "delivery_sessions")


def _print_header(title: str) -> None:
    print("\n===" + title + "===")


def main() -> None:
    url = os.getenv("SUPABASE_URL", "<unset>")
    service_role = os.getenv("SUPABASE_SERVICE_ROLE", "")
    print(f"SUPABASE_URL={url}")
    print(f"SUPABASE_KEY_PREFIX={service_role[:12] if service_role else '<empty>'}")

    client = get_supabase_client()
    if client is None:
        print("Supabase client indisponível (verifique variáveis SUPABASE_*)")
        return

    try:
        _print_header("SELECT LAST SESSION")
        resp = (
            client
            .table(DELIVERY_SESSIONS_TABLE)
            .select("*")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        print(resp.data)
    except Exception:
        print("Error selecting last session:")
        traceback.print_exc()

    try:
        _print_header("INSERT TEST SESSION")
        insert_payload = {
            "entregador_phone": "5516992089829",
            "obra_codigo": "99999",
            "step": "TESTE_PY",
        }
        resp = client.table(DELIVERY_SESSIONS_TABLE).insert(insert_payload).execute()
        print(resp.data)
    except Exception:
        print("Error inserting test session:")
        traceback.print_exc()

    try:
        _print_header("SELECT RECENT SESSIONS")
        resp = (
            client
            .table(DELIVERY_SESSIONS_TABLE)
            .select("*")
            .eq("entregador_phone", "5516992089829")
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        print(resp.data)
    except Exception:
        print("Error selecting sessions after insert:")
        traceback.print_exc()
if __name__ == "__main__":
    main()
