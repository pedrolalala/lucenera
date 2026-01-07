from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv, find_dotenv

from supabase_client import require_supabase
from supabase_utils import DELIVERY_SESSIONS_TABLE


def _bootstrap_env() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    primary = find_dotenv(str(repo_root / ".env"))
    if primary:
        load_dotenv(primary)
    load_dotenv(repo_root / ".env")


def main() -> int:
    _bootstrap_env()
    sb = require_supabase()

    now = datetime.now(timezone.utc)
    payload = {
        "entregador_phone": "5599990000",
        "step": "AGUARDANDO_CODIGO",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "obra_codigo": "DIAGNOSTICO",
    }
    print(f">> Inserindo em {DELIVERY_SESSIONS_TABLE}: {json.dumps(payload, ensure_ascii=False)}")
    response = sb.table(DELIVERY_SESSIONS_TABLE).insert(payload).execute()
    data = getattr(response, "data", None)
    print(
        ">> Resultado:",
        json.dumps(data if isinstance(data, list) else [data], ensure_ascii=False, default=str),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
