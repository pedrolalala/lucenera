# -*- coding: utf-8 -*-
"""
start_lucenera.py  (sem janela/horário)
Sobe Flask + ngrok, configura webhook da Z-API e mantém rodando com watchdog.

Requer:

Uso (PowerShell):
    & ".venv/Scripts/python.exe" "./start_lucenera.py"
"""

import os, sys, time, json, signal, subprocess, requests, threading
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ===== ENV =====
HOST          = os.getenv("HOST", "0.0.0.0")
PORT          = int(os.getenv("PORT", "5000"))
FLASK_DEBUG   = os.getenv("FLASK_DEBUG", "false").lower() == "true"

ZAPI_BASE     = (os.getenv("ZAPI_BASE") or "https://api.z-api.io").rstrip("/")
ZAPI_ID_INSTANCE = os.getenv("ZAPI_ID_INSTANCE", "")
ZAPI_TOKEN    = os.getenv("ZAPI_TOKEN", "")
ZAPI_CLIENT   = os.getenv("ZAPI_CLIENT_TOKEN")  # opcional (algumas contas exigem)
WEBHOOK_PATH  = os.getenv("WEBHOOK_PATH", "/webhook/whatsapp")

NGROK_BIN     = os.getenv("NGROK_BIN", "ngrok")   # ex: C:\Users\...\ngrok.exe
NGROK_REGION  = os.getenv("NGROK_REGION", "sa")   # 'sa' = South America
# Cloudflared / Cloudflare Tunnel
CF_BIN        = os.getenv("CF_BIN", "cloudflared")
CF_CONFIG     = BASE_DIR / ".cloudflared" / "config.yml"
CF_TUNNEL_NAME = os.getenv("CF_TUNNEL_NAME", "apilucenera")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL") or os.getenv("APP_PUBLIC_URL")

# ===== Arquivos de log/PIDs =====
PIDFILE   = BASE_DIR / "lucenera_bot.pid"
NGROK_LOG = BASE_DIR / "ngrok.log"
CF_LOG = BASE_DIR / "cloudflared.log"
APP_LOG   = BASE_DIR / "app.log"

# ===== Util =====
def write_pidfile(p):
    try:
        PIDFILE.write_text(json.dumps(p), encoding="utf-8")
    except Exception:
        pass

def read_pidfile():
    if PIDFILE.exists():
        try:
            return json.loads(PIDFILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def kill_proc(pid):
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def kill_ngrok_processes():
    """Try to kill any lingering ngrok processes (Windows/posix)."""
    try:
        if os.name == 'nt':
            # attempt to kill by image name
            subprocess.run(["taskkill", "/IM", "ngrok.exe", "/F"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "ngrok"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[cleanup] ngrok: tentativa de finalização efetuada.")
    except Exception as e:
        print("[cleanup] ngrok: falha ao tentar finalizar:", e)


def wait_for_tunnel_ready(public_url: str, timeout: int = 60) -> bool:
    """Wait until the public_url/ping returns 2xx or until timeout.

    Returns True if reachable, False otherwise.
    """
    if not public_url:
        return False
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(public_url.rstrip('/') + '/ping', timeout=5)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def ensure_cloudflared_running() -> None:
    """Ensure cloudflared is running for PUBLIC_BASE_URL.

    Strategy:
    - If a Windows service named 'cloudflared' exists, try to start it.
    - Otherwise, spawn a background cloudflared subprocess (tunnel run).
    The created subprocess is stored in globals()['cloudflared_proc'] for later management.
    """
    if not PUBLIC_BASE_URL:
        return

    # First try to detect a cloudflared service (Windows)
    if os.name == 'nt':
        try:
            r = subprocess.run(["sc", "query", "cloudflared"], capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            if 'SERVICE_NAME' in out or 'STATE' in out:
                # service exists; ensure it's running
                if 'RUNNING' in out:
                    print("[cloudflared] Serviço 'cloudflared' já está em execução.")
                else:
                    print("[cloudflared] Iniciando serviço 'cloudflared'...")
                    try:
                        subprocess.run(["sc", "start", "cloudflared"], check=False)
                        time.sleep(2)
                    except Exception as e:
                        print("[cloudflared] Falha ao iniciar serviço:", e)
                return
        except Exception:
            pass

    # Fallback: start cloudflared as a subprocess
    try:
        if not globals().get('cloudflared_proc') or not _is_pid_running(getattr(globals().get('cloudflared_proc'), 'pid', None)):
            print("[cloudflared] Iniciando cloudflared em foreground (subprocess)...")
            p = start_cloudflared()
            globals()['cloudflared_proc'] = p
            print(f"[cloudflared] PID = {getattr(p, 'pid', None)}")
            # give some time to connect
            time.sleep(2)
    except Exception as e:
        print("[cloudflared] Erro ao iniciar cloudflared:", e)

def start_flask():
    py = sys.executable  # mesmo venv
    # The project uses `main.py` as the Flask entrypoint in this workspace.
    # Historically this script expected `app.py` — start the actual file.
    app_path = str(BASE_DIR / "main.py")
    app_out = open(APP_LOG, "a", buffering=1, encoding="utf-8")
    # Observação: app.py já lê HOST/PORT do .env
    # run Python in unbuffered mode so logs are flushed to `app.log` promptly
    # Protegemos a criação do subprocesso contra OSError (recursos insuficientes)
    try:
        p = subprocess.Popen([py, "-u", app_path],
                             stdout=app_out, stderr=app_out, cwd=str(BASE_DIR))
        return p
    except OSError as e:
        print(f"[start_flask] Erro ao iniciar Flask (Popen): {e}", flush=True)
        # retry simples e conservador
        try:
            time.sleep(2)
            p = subprocess.Popen([py, "-u", app_path],
                                 stdout=app_out, stderr=app_out, cwd=str(BASE_DIR))
            return p
        except Exception as e2:
            print(f"[start_flask] Segunda tentativa falhou: {e2}", flush=True)
            return None

def start_ngrok():
    ngrok_out = open(NGROK_LOG, "a", buffering=1, encoding="utf-8")
    args = [NGROK_BIN, "http", str(PORT)]
    # region ajuda a latência/conectividade
    if NGROK_REGION:
        args += [f"--region={NGROK_REGION}"]
    p = subprocess.Popen(args, stdout=ngrok_out, stderr=ngrok_out, cwd=str(BASE_DIR))
    return p


def start_cloudflared():
    cf_out = open(CF_LOG, "a", buffering=1, encoding="utf-8")
    cfg = str(CF_CONFIG)
    # comando: cloudflared --config <config.yml> tunnel run <name>
    args = [CF_BIN, "--config", cfg, "tunnel", "run", CF_TUNNEL_NAME]
    p = subprocess.Popen(args, stdout=cf_out, stderr=cf_out, cwd=str(BASE_DIR))
    return p


def _is_pid_running(pid) -> bool:
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    # Windows: use tasklist to check
    if os.name == 'nt':
        try:
            out = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}'], text=True, stderr=subprocess.DEVNULL)
            return str(pid) in out
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

def wait_ngrok_url(timeout=60):
    """Espera a API local do ngrok (4040) ficar de pé e retorna a https public_url."""
    api = "http://127.0.0.1:4040/api/tunnels"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(api, timeout=3)
            if r.ok:
                data = r.json()
                for t in data.get("tunnels", []):
                    pub = t.get("public_url") or ""
                    if pub.startswith("https://"):
                        return pub
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Não consegui obter a URL pública do ngrok (porta 4040).")

def set_zapi_webhook(public_base_url: str):
    """Configura o webhook 'Ao receber' na Z-API para apontar ao seu endpoint."""
    if not (ZAPI_ID_INSTANCE and ZAPI_TOKEN):
        print("[zapi] PULEI: faltando ZAPI_ID_INSTANCE/ZAPI_TOKEN no .env")
        return
    webhook = f"{public_base_url.rstrip('/')}{WEBHOOK_PATH}"
    url = f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}/update-webhook-received"
    headers = {}
    if ZAPI_CLIENT:
        headers["Client-Token"] = ZAPI_CLIENT

    body = {"value": webhook}
    r = requests.put(url, json=body, headers=headers, timeout=20)
    if r.status_code >= 300:
        raise RuntimeError(f"Falha ao configurar webhook na Z-API: {r.status_code} - {r.text}")

    print(f"[zapi] Webhook RECEIVED atualizado para: {webhook}")

    # (Opcional) também marcar "Notificar as enviadas por mim"
    # try:
    #     url2 = f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}/update-webhook-received-delivery"
    #     requests.put(url2, json=body, headers=headers, timeout=20)
    #     print("[zapi] Webhook DELIVERY atualizado também.")
    # except Exception as e:
    #     print("[zapi] Aviso ao atualizar DELIVERY:", e)

def healthcheck():
    """Retorna (ok_flask, ok_ngrok) para watchdog."""
    ok_local = False
    ok_tunnel = False
    try:
        r = requests.get(f"http://127.0.0.1:{PORT}/ping", timeout=3)
        ok_local = r.status_code < 500
    except Exception:
        ok_local = False
    # If PUBLIC_BASE_URL is set, verify the public /ping endpoint through the tunnel
    if PUBLIC_BASE_URL:
        try:
            rr = requests.get(f"{PUBLIC_BASE_URL.rstrip('/')}/ping", timeout=5)
            ok_tunnel = rr.status_code < 500
        except Exception:
            ok_tunnel = False
    else:
        try:
            # If using ngrok local API, check it. Otherwise, we just assume tunnel process presence
            rr = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=3)
            ok_tunnel = rr.ok and "tunnels" in rr.json()
        except Exception:
            ok_tunnel = False

    return ok_local, ok_tunnel

def print_dashboard_urls(public_url: str):
    print("\n=== URLs úteis ===")
    print(f"- Admin local:            http://127.0.0.1:{PORT}/admin")
    if PUBLIC_BASE_URL:
        print(f"- Admin via public:       {public_url}/admin")
    else:
        print(f"- Admin via ngrok:        {public_url}/admin")
    print(f"- Ping local:             http://127.0.0.1:{PORT}/ping")
    if not PUBLIC_BASE_URL:
        print(f"- ngrok Web UI (local):   http://127.0.0.1:4040/inspect/http")
    print(f"- Webhook público:        {public_url}{WEBHOOK_PATH}")
    print("===================\n")

def main():
    # Read previous PIDs
    pids = read_pidfile() or {}
    prev_app_pid = pids.get('app_pid')
    prev_ngrok_pid = pids.get('ngrok_pid')

    app_running = _is_pid_running(prev_app_pid)
    ngrok_running = _is_pid_running(prev_ngrok_pid)

    # If PUBLIC_BASE_URL is provided, we won't autostart ngrok (use the paid domain)
    if PUBLIC_BASE_URL:
        print(f"[start] PUBLIC_BASE_URL is set -> using {PUBLIC_BASE_URL}; ngrok autostart disabled.")
        # Try to ensure no leftover ngrok processes are running (avoids conflicts)
        try:
            kill_ngrok_processes()
        except Exception:
            pass

    # Start or reuse Flask
    app_proc = None
    if app_running:
        print(f"[start] Found existing Flask process (pid={prev_app_pid}), reusing it.")
        class DummyP:
            def __init__(self, pid): self.pid = pid
        app_proc = DummyP(prev_app_pid)
    else:
        app_proc = start_flask()
        print(f"[start] Flask PID = {getattr(app_proc, 'pid', None)}")
        # Aguarda Flask subir e responder /ping
        flask_ready = False
        for _ in range(20):  # até 20 tentativas (~20s)
            try:
                r = requests.get(f"http://127.0.0.1:{PORT}/ping", timeout=2)
                if r.status_code == 200:
                    flask_ready = True
                    print("[start] Flask /ping respondeu OK.")
                    break
            except Exception:
                pass
            time.sleep(1)
        if not flask_ready:
            print("[start] Flask não respondeu /ping após 20s. Verifique logs.")

    # Start or reuse ngrok unless a public base URL was provided
    ngrok_proc = None
    # If PUBLIC_BASE_URL is configured, ensure cloudflared is running to serve it.
    cloudflared_proc = None
    if PUBLIC_BASE_URL:
        public_url = PUBLIC_BASE_URL
        # If a cloudflared proc was previously stored, try to reuse it
        prev_tunnel_pid = pids.get('tunnel_pid')
        if prev_tunnel_pid and _is_pid_running(prev_tunnel_pid):
            class DummyCF:
                def __init__(self, pid): self.pid = pid
            cloudflared_proc = DummyCF(prev_tunnel_pid)
            globals()['cloudflared_proc'] = cloudflared_proc
            print(f"[start] Reusing existing tunnel process (pid={prev_tunnel_pid}) for PUBLIC_BASE_URL")
        else:
            try:
                globals()['cloudflared_proc'] = start_cloudflared()
                cloudflared_proc = globals().get('cloudflared_proc')
                print(f"[start] cloudflared PID = {getattr(cloudflared_proc,'pid',None)}")
                # give cloudflared a few seconds to establish
                time.sleep(3)
                # Ensure cloudflared/service is running (attempt service start or subprocess start)
                try:
                    ensure_cloudflared_running()
                    ok = wait_for_tunnel_ready(public_url, timeout=60)
                    if not ok:
                        print("[start] Aviso: tunnel público não respondeu dentro do timeout (60s). Ainda assim continuando; veja cloudflared.log para detalhes.")
                    else:
                        print("[start] Tunnel público respondeu com sucesso.")
                except Exception as e:
                    print("[start] Aviso: falha ao verificar tunnel:", e)
            except Exception as e:
                print("[start] Aviso: falha ao iniciar cloudflared:", e)
    else:
        if ngrok_running:
            print(f"[start] Found existing ngrok process (pid={prev_ngrok_pid}), reusing it.")
            class DummyP2:
                def __init__(self, pid): self.pid = pid
            ngrok_proc = DummyP2(prev_ngrok_pid)
            public_url = wait_ngrok_url(timeout=90)
            print(f"[ngrok] Reused URL pública: {public_url}")
        else:
            ngrok_proc = start_ngrok()
            print(f"[start] ngrok PID = {ngrok_proc.pid}")
            # 3) pega URL pública
            public_url = wait_ngrok_url(timeout=90)
            print(f"[ngrok] URL pública: {public_url}")

    # 4) configura webhook Z-API
    # Run initial webhook update in background so startup can't block on network issues
    def _set_webhook_bg(url):
        try:
            set_zapi_webhook(url)
        except Exception as e:
            print("[zapi] ERRO ao configurar webhook (background):", e)

    threading.Thread(target=_set_webhook_bg, args=(public_url,), daemon=True).start()

    # 5) salva PIDs (some processes may be None when PUBLIC_BASE_URL is set)
    try:
        app_pid_val = getattr(app_proc, "pid", None)
        # support either ngrok or cloudflared pid
        tunnel_pid_val = None
        try:
            tunnel_pid_val = getattr(globals().get('cloudflared_proc', None), 'pid', None) or getattr(ngrok_proc, 'pid', None)
        except Exception:
            tunnel_pid_val = None
    except Exception:
        app_pid_val = None
        tunnel_pid_val = None
    write_pidfile({"app_pid": app_pid_val, "tunnel_pid": tunnel_pid_val})

    print_dashboard_urls(public_url)

    # 6) watchdog (loop infinito até CTRL+C)
    # keep references to cloudflared/ngrok process objects
    cloudflared_proc = globals().get('cloudflared_proc', None)
    last_ok_ts = time.time()
    while True:
        ok_flask, ok_tunnel = healthcheck()

        if ok_flask and ok_tunnel:
            last_ok_ts = time.time()
        else:
            # se ngrok caiu → reinicia ngrok e reconfigura webhook
            if not ok_tunnel:
                print("[watchdog] Tunnel caiu. Reiniciando e atualizando webhook...")
                # Try restart cloudflared if PUBLIC_BASE_URL is set, else fall back to ngrok behavior
                try:
                    if PUBLIC_BASE_URL:
                        try:
                            # restart cloudflared
                            if globals().get('cloudflared_proc'):
                                kill_proc(getattr(globals().get('cloudflared_proc'), 'pid', None))
                            globals()['cloudflared_proc'] = start_cloudflared()
                            print(f"[cloudflared] PID = {getattr(globals().get('cloudflared_proc'), 'pid', None)}")
                            time.sleep(3)
                        except Exception as e:
                            print("[watchdog] Erro ao reiniciar cloudflared:", e)
                    else:
                        # fallback to ngrok behavior
                        try: kill_proc(getattr(ngrok_proc, 'pid', None))
                        except Exception: pass
                        ngrok_proc = start_ngrok()
                        print(f"[ngrok] PID = {getattr(ngrok_proc,'pid',None)}")
                        time.sleep(3)

                except Exception as e:
                    print("[watchdog] Erro ao reiniciar tunnel:", e)

                # try to update webhook (blocking here is acceptable for recovery)
                try:
                    set_zapi_webhook(public_url)
                except Exception as e:
                    print("[zapi] ERRO ao reconfigurar webhook:", e)

                print_dashboard_urls(public_url)
                try:
                    app_pid_val = getattr(app_proc, "pid", None)
                    tunnel_pid_val = getattr(globals().get('cloudflared_proc', None), 'pid', None) or getattr(ngrok_proc, 'pid', None)
                except Exception:
                    app_pid_val = None
                    tunnel_pid_val = None
                write_pidfile({"app_pid": app_pid_val, "tunnel_pid": tunnel_pid_val})
                last_ok_ts = time.time()

            # se flask caiu → reinicia app
            if not ok_flask:
                print("[watchdog] Flask /ping falhou. Reiniciando app (main.py)...")
                try: kill_proc(getattr(app_proc, 'pid', None))
                except Exception: pass
                app_proc = start_flask()
                time.sleep(2)
                write_pidfile({"app_pid": getattr(app_proc, 'pid', None), "tunnel_pid": getattr(globals().get('cloudflared_proc', None), 'pid', None)})
                last_ok_ts = time.time()

        # fallback: se ficar muito tempo sem ok (ex: 5min), reinicia flask por segurança
        if time.time() - last_ok_ts > 300:
            print("[fallback] 5 min sem OK. Reiniciando Flask preventivamente.")
            try: kill_proc(getattr(app_proc, 'pid', None))
            except Exception: pass
            app_proc = start_flask()
            last_ok_ts = time.time()
            write_pidfile({"app_pid": getattr(app_proc, 'pid', None), "tunnel_pid": getattr(globals().get('cloudflared_proc', None), 'pid', None) or getattr(ngrok_proc, 'pid', None)})

        time.sleep(10)

def _graceful_exit(*_args):
    pids = read_pidfile()
    print("\n[stop] Encerrando processos…")
    try: kill_proc(pids.get("tunnel_pid") or pids.get("ngrok_pid"))
    except Exception: pass
    try: kill_proc(pids.get("app_pid"))
    except Exception: pass
    try: PIDFILE.unlink(missing_ok=True)
    except Exception: pass
    sys.exit(0)

if __name__ == "__main__":
    # CTRL+C / encerramento limpo
    try:
        if os.name != "nt":
            signal.signal(signal.SIGTERM, _graceful_exit)
            signal.signal(signal.SIGINT, _graceful_exit)
        else:
            # No Windows, SIGTERM nem sempre dispara; tratamos KeyboardInterrupt
            pass
        main()
    except KeyboardInterrupt:
        _graceful_exit()
