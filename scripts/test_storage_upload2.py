from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import find_dotenv, load_dotenv

from supabase_client import require_supabase

BUCKET = "entregas"


def _bootstrap_env() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    primary = find_dotenv(str(repo_root / ".env"))
    if primary:
        load_dotenv(primary)
    load_dotenv(repo_root / ".env")


def main() -> int:
    _bootstrap_env()
    sb = require_supabase()
    storage = sb.storage.from_(BUCKET)
    now = datetime.now(timezone.utc)
    path = f"diagnostics/{now.strftime('%Y%m%d/%H%M%S')}_storage_check.txt"
    content = f"diagnostic upload at {now.isoformat()}\n"
    print(f">> Uploading diagnostic file to bucket={BUCKET} path={path}")
    response = storage.upload(
        path,
        content.encode("utf-8"),
        file_options={"content-type": "text/plain", "upsert": "true"},
    )
    print(
        ">> Upload response:",
        response,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
