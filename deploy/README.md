# macOS public-demo deployment

The public demo is a dedicated host:

`https://elevator.oosu.dev/`

It must be published as its own hostname, not mounted below another application. The Python
process listens only on `127.0.0.1:4174`; the Mac mini's existing TLS/reverse-proxy or Cloudflare
tunnel publishes the dedicated hostname.

## 1. Install/update the launchd service

From a clone of this repository on the Mac mini:

```bash
git fetch origin main
git switch main
git pull --ff-only
PYTHON_BIN="$(command -v python3)" PORT=4174 bash deploy/install_macos.sh
curl -fsS http://127.0.0.1:4174/api/health
```

The installer creates `~/Library/LaunchAgents/dev.oosu.elevator-queue-lab.plist`, keeps the
process alive, and writes logs to `~/Library/Logs/elevator-queue-lab/`.

## 2. Publish `elevator.oosu.dev`

Create a new DNS/tunnel hostname for `elevator.oosu.dev` in the same Cloudflare zone used by
`oosu.dev`. Point only that hostname at the Mac mini ingress. Do not modify unrelated application
hostnames or routes.

For the locally managed `macmini` Cloudflare Tunnel, provision the hostname only after the
loopback service and ingress rule are healthy:

```bash
MACMINI_TUNNEL_ID="$(cloudflared tunnel list | awk '$2 == "macmini" {print $1; exit}')"
test -n "$MACMINI_TUNNEL_ID"
cloudflared tunnel route dns --overwrite-dns "$MACMINI_TUNNEL_ID" elevator.oosu.dev
```

Use the UUID resolved from `tunnel list`, rather than relying on a tunnel-name argument: a local
cloudflared config may already define a default `tunnel:` value and cause a name lookup to target
the wrong tunnel.

Do not create the DNS route before the origin is ready; a public hostname that resolves to a
nonexistent service is considered a failed release, not partial completion.

If Caddy terminates the host on the Mac mini, use `Caddyfile.example`. If nginx is the ingress,
use `nginx-location.conf.example`. If Cloudflare Tunnel maps hostnames directly to local services,
add an ingress entry equivalent to:

```yaml
- hostname: elevator.oosu.dev
  service: http://127.0.0.1:4174
```

Validate the existing proxy/tunnel configuration before reloading it.

## 3. Public acceptance

```bash
curl -fsS https://elevator.oosu.dev/api/health
BASE_URL=https://elevator.oosu.dev/ npm run test:e2e
python scripts/audit_release.py --live-url https://elevator.oosu.dev/
```

Only after all three pass should README/ROADMAP mark the public-demo gate complete.
