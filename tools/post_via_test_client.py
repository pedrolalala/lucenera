import time
import traceback
import os
import sys
# Ensure project root is importable when running from tools/
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from main import app  # noqa: E402
from supabase_client import get_supabase  # noqa: E402

payload = {
    "phone": "5516996060007",
    "text": "Teste via test_client: Está aparecendo?",
    "fromMe": False,
    "type": "message",
    "status": "",
}

with app.test_client() as c:
    print('Posting via app.test_client to /webhook/whatsapp')
    rv = c.post('/webhook/whatsapp', json=payload)
    print('status', rv.status_code)
    try:
        print('resp json:', rv.get_json())
    except Exception:
        print('resp data:', rv.data[:400])

# Wait a short moment then query supabase for the last inserted
try:
    sb = get_supabase()
    if not sb:
        print('Supabase client is None')
    else:
        time.sleep(1)
        q = (
            sb.table('mensagens')
            .select('*')
            .eq('telefone', '5516996060007')
            .order('id_num', desc=True)
            .limit(1)
            .execute()
        )
        print('select status:', getattr(q, 'status_code', None))
        print('select data preview:', q.data if hasattr(q, 'data') else q)
except Exception as e:
    print('error querying supabase:', e)
    traceback.print_exc()
