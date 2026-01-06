# Installing services for Lucenera (Windows)

This file explains how to install Cloudflare Tunnel (cloudflared) and the Lucenera launcher (`start_lucenera.py`) as persistent services on Windows. These steps require an Administrator account.

1) Prepare
- Open PowerShell as Administrator.
- From the repository root (e.g., `C:\script python\lucenera`) run:
  - Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

2) Install cloudflared as a service
- If `cloudflared` is installed and in PATH you can run:

  cloudflared service install

  This registers a Windows service named `cloudflared` that will run the tunnel configured at `.cloudflared\config.yml`.

- Verify the service was created and started:

  Get-Service cloudflared

3) Install the Lucenera launcher as a Windows service
- Recommended: NSSM (Non-Sucking Service Manager).
  - Download NSSM from https://nssm.cc/download and extract `nssm.exe` to a folder in your PATH (or use the full path to nssm.exe).

- Example NSSM commands (run in Administrator PowerShell from repo root):

  $venv = "C:\script python\lucenera\.venv\Scripts\python.exe"
  $launcher = "C:\script python\lucenera\start_lucenera.py"

  nssm install lucenera "$venv" "$launcher"
  nssm set lucenera AppDirectory "C:\script python\lucenera"
  nssm set lucenera Start SERVICE_AUTO_START
  nssm start lucenera

- Verify:

  Get-Service lucenera

4) Alternative without NSSM: Windows Scheduled Task
- If you cannot install NSSM, create a Scheduled Task that runs at startup with highest privileges and runs the same python command (pointing to `.venv\Scripts\python.exe start_lucenera.py`). This is less ideal but works without extra binaries.

5) Validate
- After installation, confirm:
  - cloudflared service is running and `cloudflared tunnel run NAME` is active (the service will run the configured tunnel).
  - The lucenera service is running and listening on port 5000: `netstat -ano | findstr :5000` or visit `http://127.0.0.1:5000/ping` on the host.
  - From outside, `https://apilucenera.site/ping` should return 200 (after DNS/Cloudflare config is in place).

6) Troubleshooting
- If `cloudflared service install` reports Access Denied: you must run PowerShell as Administrator.
- If cloudflared is not found: install it and ensure it's in PATH, or use the absolute path to the binary.
- If NSSM is not available: follow the NSSM download page and place `nssm.exe` somewhere in PATH, then re-run the commands above.

7) Automation
- A helper script is provided at `scripts\install_services.ps1`. Run it as Administrator. It will attempt cloudflared install and will try nssm if present.

If you'd like, I can: (A) run lightweight safety edits to further harden the webhook updater (timeouts/retries added already), (B) generate a signed service wrapper, or (C) produce a one-click zip containing NSSM and a small service config — tell me which you prefer.
