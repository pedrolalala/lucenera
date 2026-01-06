import json
import traceback
import os
import sys

if __name__ == '__main__':
    print('cwd:', os.getcwd())
    print('sys.path (first 8):', sys.path[:8])
    print('files in cwd:', os.listdir('.'))

    # Ensure project root is on sys.path (script lives in tools/ which becomes sys.path[0])
    project_root = os.path.abspath(os.path.join(os.getcwd()))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from supabase_client import healthcheck, get_supabase
    except Exception as e:
        print('import error:', e)
        print('traceback:')
        traceback.print_exc()
        sys.exit(2)

    try:
        info = healthcheck()
    except Exception as e:
        info = {'error': str(e), 'trace': traceback.format_exc()}

    print('HEALTHCHECK:')
    print(json.dumps(info, ensure_ascii=False, indent=2))

    try:
        sb = get_supabase()
        if sb is None:
            print('get_supabase() returned None')
        else:
            print('get_supabase() OK, trying a small select...')
            out = sb.table('mensagens').select('*').limit(1).execute()
            # out may be a Dict-like or Response depending on supabase lib
            try:
                status = getattr(out, 'status_code', None) or out.get('status_code')
            except Exception:
                status = None
            data = None
            try:
                data = out.data
            except Exception:
                data = out.get('data') if isinstance(out, dict) else None
            print('select status:', status)
            print('data preview:', data)
    except Exception as e:
        print('select_error:', str(e))
        traceback.print_exc()
