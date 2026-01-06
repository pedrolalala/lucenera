import requests
url = 'http://127.0.0.1:5000/webhook/whatsapp'
payload = {
    "phone": "5516996060007",
    "text": "Teste automático: funciona? Olá!",
    "fromMe": False,
    "type": "message",
    "status": "",
}
print('Posting to', url)
r = requests.post(url, json=payload, timeout=10)
print('status', r.status_code)
try:
    print(r.json())
except Exception:
    print(r.text)
