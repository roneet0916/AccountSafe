# AccountSafe — Production Deployment Playbook

**Target architecture**

| Layer    | Host             | URL                          |
|----------|------------------|------------------------------|
| Frontend | Vercel           | `https://accountsafe.vercel.app` |
| Backend  | Oracle Cloud VM  | `https://<your-domain>`      |
| DB       | Postgres in Docker on same VM | internal only |

Backend VM (from this deploy): **Ubuntu on `140.245.20.107`**.

---

## 0. Prerequisites

- Oracle Cloud VM created (Ampere A1 or any shape), Ubuntu 22.04 LTS.
- SSH access as `ubuntu` user.
- A hostname that resolves to the VM's public IP. Cheapest paths:
  - **DuckDNS** (recommended): sign up at <https://www.duckdns.org>, create a
    subdomain like `accountsafe.duckdns.org`, point it at `140.245.20.107`.
    Keep the token for auto-refresh (optional).
  - **sslip.io** (zero signup): just use `140-245-20-107.sslip.io` — it
    auto-resolves to `140.245.20.107`.
  - A real domain (Cloudflare Registrar, Namecheap, etc.).

> Let's Encrypt will **not** issue certificates for a bare IP address, which is
> why a hostname is mandatory. Browsers will also block HTTPS (Vercel) → HTTP
> (bare IP) calls as mixed content.

---

## 1. Open ports in the Oracle Cloud Console

Oracle restricts traffic at **two** layers; both must allow 80/443.

1. **VCN Security List** (cloud-level firewall):
   - OCI Console → *Networking* → *Virtual Cloud Networks* → your VCN → *Security Lists* → the default list.
   - Add two **Ingress Rules**:
     - Source `0.0.0.0/0`, IP Protocol TCP, Dest Port `80`
     - Source `0.0.0.0/0`, IP Protocol TCP, Dest Port `443`

2. **OS-level firewall** (handled by `oracle-bootstrap.sh` in step 3).

---

## 2. Point DNS at the VM

DuckDNS example:
```
accountsafe.duckdns.org  A  140.245.20.107
```
Verify from your laptop **before** moving on:
```bash
dig +short accountsafe.duckdns.orgclear
# should print 140.245.20.107
```

---

## 3. Bootstrap the VM (run once)

SSH in and clone the repo:
```bash
ssh ubuntu@140.245.20.107
git clone https://github.com/<your-user>/AccountSafe.git
cd AccountSafe
make oracle-bootstrap
```

What this does:
- Installs Docker Engine + Compose plugin (ARM + x86 supported).
- Creates a 4 GB swap file (Ampere A1 has no swap by default).
- Opens ports 22/80/443 via `ufw` and removes Oracle's default `REJECT` iptables rule.
- Installs `fail2ban` for SSH brute-force protection.
- Enables unattended security upgrades.

**Log out and back in** so Docker group membership takes effect:
```bash
exit
ssh ubuntu@140.245.20.107
cd AccountSafe
docker ps   # should work without sudo
```

---

## 4. Configure secrets

```bash
cp .env.oracle.example .env
nano .env
```

Required values:
- `DOMAIN` — your hostname (e.g. `accountsafe.duckdns.org`).
- `PUBLIC_IP` — `140.245.20.107`.
- `LETSENCRYPT_EMAIL` — your email (for cert expiry notifications).
- `SECRET_KEY` — generate once:
  ```bash
  docker run --rm python:3.11-slim python -c \
    "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null \
    || python3 -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- `ENCRYPTION_KEY` — generate once:
  ```bash
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `DB_PASSWORD` — `openssl rand -base64 32`.
- `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` — Gmail + [app password](https://myaccount.google.com/apppasswords).
- `TURNSTILE_SECRET_KEY` — from Cloudflare Turnstile dashboard.

---

## 5. Issue the TLS certificate (run once)

```bash
make oracle-ssl-init
```

This spins up a throwaway nginx on :80, runs `certbot certonly --webroot`,
saves the cert to `./certbot/conf/live/$DOMAIN/`, and tears the temporary
server down. If it fails with a rate-limit error, re-run with `STAGING=1
./scripts/oracle-init-ssl.sh` first to validate the pipeline, then switch back.

---

## 6. Start the stack

```bash
make oracle-up
```

Verify:
```bash
make oracle-ps
curl -I https://accountsafe.duckdns.org/health
# HTTP/2 200
curl -I https://accountsafe.duckdns.org/api/health/
# HTTP/2 200 (or whatever your health endpoint returns)
```

Create the Django superuser:
```bash
make oracle-shell
python manage.py createsuperuser
exit
```

Django admin is then at `https://accountsafe.duckdns.org/admin/`.

---

## 7. Deploy the frontend to Vercel

In the Vercel dashboard for this project:

1. **Root Directory**: `frontend`.
2. **Framework Preset**: Create React App (auto-detected).
3. **Environment Variables** (Production + Preview scopes both):
   - `REACT_APP_API_URL` = `https://accountsafe.duckdns.org/api/`
   - `REACT_APP_PROJECT_NAME` = `AccountSafe`
   - `REACT_APP_LOGO_URL` = `https://accountsafe.vercel.app/logo.png`
   - `REACT_APP_TURNSTILE_SITE_KEY` = your Turnstile **site** key (not secret).
4. Trigger a redeploy. The `REACT_APP_API_URL` is baked into the bundle, so
   **any URL change requires a Vercel rebuild**, not just a backend restart.

---

## 8. Smoke test the full flow

From your laptop:
```bash
# CORS preflight from Vercel origin
curl -i -X OPTIONS https://accountsafe.duckdns.org/api/check-username/ \
    -H 'Origin: https://accountsafe.vercel.app' \
    -H 'Access-Control-Request-Method: GET'
# Expect: HTTP/2 200 with Access-Control-Allow-Origin: https://accountsafe.vercel.app
```

In the browser, open <https://accountsafe.vercel.app>, open DevTools → Network,
and attempt a login. All requests should go to `https://accountsafe.duckdns.org/api/*`
and return without CORS errors.

---

## 9. Redeploy loop

Code changes on `main`:
```bash
ssh ubuntu@140.245.20.107
cd AccountSafe
make oracle-deploy   # = git reset --hard origin/main + build + migrate + restart
```

Roll back:
```bash
git reset --hard <previous-sha>
make oracle-deploy
```

---

## 10. Backups & restore

Backups run every 6 hours to `./backups/` (gzip-compressed SQL).
Retention: 7 daily / 4 weekly / 3 monthly. To trigger one on demand:
```bash
make oracle-backup
```

Restore:
```bash
gunzip -c backups/last/accountsafe-latest.sql.gz | \
    docker compose -f docker-compose.oracle.yml exec -T db \
    psql -U "$DB_USER" "$DB_NAME"
```

Off-site copy (recommended — Oracle Block Storage is not a backup):
```bash
# Example: sync to your S3 / B2 / Drive. Add to crontab.
rclone sync ./backups remote:accountsafe-backups --max-age 30d
```

---

## 11. Observability

- `make oracle-logs` — tail everything.
- `docker compose -f docker-compose.oracle.yml logs -f backend` — just Django.
- Backend logs are JSON in production (see `settings.py LOGGING`). Pipe into any
  log collector (Loki, Vector, CloudWatch agent, etc.) if desired.
- Set `SENTRY_DSN` in `.env` to enable error tracking. Completely opt-in.

---

## 12. Common failure modes

| Symptom | Fix |
|---|---|
| `make oracle-ssl-init` → `DNS problem: NXDOMAIN` | Your DuckDNS/sslip record doesn't resolve yet. Recheck DNS, wait a few minutes. |
| `make oracle-ssl-init` → `Connection refused` during HTTP-01 | Port 80 is blocked. Verify the OCI Security List (step 1) **and** `sudo ufw status`. |
| Frontend gets CORS error from `*.vercel.app` preview | Confirm `CORS_ALLOWED_ORIGIN_REGEXES` in `settings.py` matches your preview URL pattern. |
| `CSRF verification failed` in Django admin | Ensure `https://<DOMAIN>` is in `CSRF_TRUSTED_ORIGINS` (the compose file sets this from `.env`). |
| Gunicorn returns 502 through nginx | `docker compose -f docker-compose.oracle.yml logs backend` — usually a migration failure or missing env var. |
| `SECURE_SSL_REDIRECT` infinite loop | Nginx must send `X-Forwarded-Proto: https` (it does in `nginx.oracle.conf`). If you put Cloudflare proxy in front, ensure SSL mode is "Full (strict)". |
| ARM image build fails on x86 laptop | Don't build locally — build on the VM (`make oracle-up` does this). If you must, use `docker buildx build --platform linux/arm64`. |

---

## 13. Hardening checklist (optional but recommended)

- [ ] Disable SSH password auth (`/etc/ssh/sshd_config`: `PasswordAuthentication no`). Oracle defaults to key-only already.
- [ ] Change the SSH port (update `ufw` + OCI Security List + `sshd_config`).
- [ ] Put Cloudflare in front of `$DOMAIN` for DDoS protection. If you do, set
      SSL mode to "Full (strict)" and keep the Let's Encrypt cert on the origin.
- [ ] Enable Oracle Cloud Bastion or restrict SSH ingress to your home IP.
- [ ] Rotate `SECRET_KEY` and `DB_PASSWORD` on a schedule.
- [ ] Mirror `./backups` to off-site storage (S3/B2/Drive).
