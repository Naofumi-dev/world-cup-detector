# Deployment

The frontend deploys to **Vercel** (static React) and the backend to a
**stateful host** (here, a Hostinger VPS) so that recorded results and retrains
persist. Deploy the backend first — the frontend needs its public URL.

---

## 1. Backend → VPS

The app self-seeds from `data/results.csv` and trains the model on first start,
so no database setup is required.

### Option A — Docker (simplest)

```bash
# on the VPS, with the repo cloned
cd world-cup-detector/backend
docker build -t wcd-backend .
docker run -d --name wcd-backend --restart unless-stopped \
  -p 8000:8000 \
  -e WCD_CORS_ORIGINS="https://<your-vercel-domain>.vercel.app" \
  -v wcd-data:/app/data -v wcd-models:/app/models \
  wcd-backend
```

The volumes keep the SQLite DB and trained model across restarts.

### Option B — systemd + venv

```bash
cd /opt/world-cup-detector/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`/etc/systemd/system/wcd.service`:

```ini
[Unit]
Description=World Cup Detector API
After=network.target

[Service]
WorkingDirectory=/opt/world-cup-detector/backend
Environment=WCD_CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
ExecStart=/opt/world-cup-detector/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now wcd
```

### Expose it (HTTPS)

Put nginx in front and terminate TLS (browsers block mixed content, so the API
must be HTTPS to be called from the Vercel site):

```nginx
server {
    server_name api.your-domain.com;
    location / { proxy_pass http://127.0.0.1:8000; }
}
```

```bash
sudo certbot --nginx -d api.your-domain.com   # free TLS
```

Open ports 80/443 in the VPS firewall. The public API base is then
`https://api.your-domain.com`.

---

## 2. Frontend → Vercel

Import the GitHub repo at your Vercel team, then:

| Setting | Value |
| --- | --- |
| **Root Directory** | `frontend` |
| **Framework Preset** | Vite (auto-detected) |
| **Build Command** | `npm run build` (default) |
| **Output Directory** | `dist` (default) |
| **Environment Variable** | `VITE_API_URL` = `https://api.your-domain.com` |

Deploy. Then add the resulting Vercel domain to the backend's
`WCD_CORS_ORIGINS` and restart the backend.

> `VITE_API_URL` is baked in at build time — changing it requires a redeploy.

---

## Config reference

| Variable | Where | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | Vercel (frontend) | Backend base URL for production builds |
| `WCD_CORS_ORIGINS` | VPS (backend) | Comma-separated allowed browser origins |
| `WCD_DB_PATH` | VPS (backend) | Override SQLite path (default `data/wcd.db`) |
