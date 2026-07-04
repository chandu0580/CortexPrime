# LOCAL_CERTIFICATE_REMEDIATION_REPORT

## Objective

Replace the untrusted self-signed local nginx certificate with a trusted `mkcert`-issued localhost certificate and verify local HTTPS, WSS, and Voice V2 session creation.

## Changes Applied

### 1. Installed `mkcert`

Installed `mkcert` locally via `winget`.

### 2. Installed local development CA

Ran `mkcert -install` to create and trust a local development CA in the Windows trust store.

Result:

- A new local `mkcert` CA was created.
- The CA was installed into the Windows system trust store.

### 3. Replaced nginx localhost certificate

Generated a trusted localhost certificate directly into the nginx-mounted cert paths:

- `infra/nginx/certs/cert.pem`
- `infra/nginx/certs/key.pem`

Generated names:

- `localhost`
- `127.0.0.1`
- `::1`

Generated certificate properties observed after reload:

- Subject: `OU=LAPTOP-JEE2HMET\\chandu s@LAPTOP-JEE2HMET (Chandu Yadav), O=mkcert development certificate`
- Issuer: `CN=mkcert LAPTOP-JEE2HMET\\chandu s@LAPTOP-JEE2HMET (Chandu Yadav), OU=LAPTOP-JEE2HMET\\chandu s@LAPTOP-JEE2HMET (Chandu Yadav), O=mkcert development CA`
- Thumbprint: `D46E9634AAAB5F0F7F826BA2F7E2BD86977EB49E`
- SANs:
  - `DNS:localhost`
  - `IP:127.0.0.1`
  - `IP:::1`
- Expiry: `2028-09-14`

### 4. Restarted nginx container

Restarted `cortex-nginx` with:

- `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env restart cortex-nginx`

Post-restart status:

- `cortex-nginx` healthy

## Verification Results

### HTTPS trust

Fresh browser navigation to `https://localhost` succeeded.

Additional TLS validation from the Windows client stack returned:

- `SslPolicyErrors: None`
- empty chain-status errors

Conclusion:

- `https://localhost` now presents a trusted certificate.

### WSS trust

`wss://localhost/ws` successfully completed a WebSocket handshake.

Observed client state:

- `State: Open`

Conclusion:

- `wss://localhost` now connects successfully over trusted TLS.

### Voice session endpoint

Authenticated `POST https://localhost/api/voice/v2/session` succeeded after obtaining a live access token from the running backend.

Observed response included:

- `session_id`: created successfully
- `room_name`: created successfully
- `token`: returned successfully
- `livekit_url`: returned successfully
- `identity`: `e2e-user`

Conclusion:

- Voice session creation now works over trusted local HTTPS.

## Root Cause Resolved

The previous failure was caused by nginx serving a self-signed localhost certificate that was not trusted by the browser or Windows TLS client stack.

This remediation replaced that certificate with an `mkcert` certificate chained to a trusted local development CA, which resolved:

- `ERR_CERT_AUTHORITY_INVALID` in the browser
- WSS trust failures on `wss://localhost/ws`
- HTTPS trust failures blocking `POST /api/voice/v2/session`

## Artifacts Affected

- [infra/nginx/certs/cert.pem](c:\projects\cortexprime\infra\nginx\certs\cert.pem)
- [infra/nginx/certs/key.pem](c:\projects\cortexprime\infra\nginx\certs\key.pem)
- [LOCAL_CERTIFICATE_AUDIT.md](c:\projects\cortexprime\LOCAL_CERTIFICATE_AUDIT.md)

## Final Status

All requested remediation steps completed successfully:

1. `mkcert` local CA installed.
2. Trusted localhost certificate generated.
3. `infra/nginx/certs/cert.pem` replaced.
4. `infra/nginx/certs/key.pem` replaced.
5. nginx restarted.
6. `https://localhost` verified trusted.
7. `wss://localhost` verified connected.
8. `POST /api/voice/v2/session` verified successful.