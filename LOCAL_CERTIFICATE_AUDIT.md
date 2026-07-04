# LOCAL_CERTIFICATE_AUDIT

## Scope

Investigated the local TLS trust failure blocking:

- `POST https://localhost/api/voice/v2/session`
- `wss://localhost/ws`

Observed browser error:

- `net::ERR_CERT_AUTHORITY_INVALID`

Goal:

- Restore successful browser HTTPS and WSS connections against local `https://localhost`.

## Findings

### 1. Certificate source

Local TLS terminates in nginx.

- [docker-compose.prod.yml](c:\projects\cortexprime\docker-compose.prod.yml) mounts `./infra/nginx/certs` into `/etc/nginx/certs`.
- [infra/nginx/conf.d/cortex.conf](c:\projects\cortexprime\infra\nginx\conf.d\cortex.conf) configures:
  - `ssl_certificate /etc/nginx/certs/cert.pem;`
  - `ssl_certificate_key /etc/nginx/certs/key.pem;`
- [scripts/generate-certs.sh](c:\projects\cortexprime\scripts\generate-certs.sh) generates those files as a self-signed certificate for local or staging use and explicitly warns that browsers will show a warning.

The cert files do exist locally:

- `infra/nginx/certs/cert.pem`
- `infra/nginx/certs/key.pem`

### 2. Nginx certificate content

The on-disk certificate is a self-signed leaf certificate, not a CA-signed chain.

Observed metadata from `infra/nginx/certs/cert.pem`:

- Subject: `CN=localhost, O=CortexPrime, L=City, S=State, C=US`
- Issuer: `CN=localhost, O=CortexPrime, L=City, S=State, C=US`
- Thumbprint: `211D5F6C13B92CA1CE2A44702B3EEB7E365B8F6E`
- Valid from: `2026-06-07 17:28:21`
- Valid until: `2027-06-07 17:28:21`
- SANs:
  - `DNS:localhost`
  - `IP:127.0.0.1`

This cert is structurally suitable for local `https://localhost`, but it is self-signed and therefore only works if that exact certificate is trusted by the client.

### 3. Served HTTPS certificate chain

The live `https://localhost:443` endpoint presents the same certificate nginx has on disk.

Client-side TLS validation against the live endpoint returned:

- `SslPolicyErrors: RemoteCertificateChainErrors`
- `ChainStatus: UntrustedRoot`

This means the failure is not caused by hostname mismatch or expiry. The failure is that the certificate chain terminates in a root the client does not trust.

### 4. Windows trust-store status

The current user Windows root store already contains two trusted self-signed `CN=localhost` certificates:

- `A4C0E4E01C9A3912FFDBFA3596D37D83BC1E767F`
- `1AC53B0743716E049DF794CFE15C115215E3117B`

Those do not match the certificate nginx is currently serving:

- Served thumbprint: `211D5F6C13B92CA1CE2A44702B3EEB7E365B8F6E`

Conclusion:

- The machine may already trust older `localhost` certificates.
- It does not trust the specific self-signed certificate currently mounted into nginx.
- Because the served cert is self-signed, trust depends on importing that exact certificate, or replacing it with a certificate chained to a trusted local CA.

No matching `localhost` or `CortexPrime` root was found in the machine-wide root store during this audit.

### 5. Browser trust status

A fresh browser navigation to `https://localhost` fails immediately with:

- `net::ERR_CERT_AUTHORITY_INVALID`

That confirms the failure is reproducible in a new browser context and is not limited to the voice route.

### 6. WebSocket trust status

`wss://localhost/ws` fails for the same TLS reason.

Client-side connection attempt result:

- `Could not establish trust relationship for the SSL/TLS secure channel`
- inner TLS error: `The remote certificate is invalid according to the validation procedure`

Because nginx terminates both HTTPS and WSS on the same `localhost:443` certificate, the WebSocket failure is expected whenever the HTTPS cert is untrusted.

## Root Cause

The local nginx instance is serving a self-signed `localhost` certificate that is not trusted by the browser or the Windows TLS client stack.

More specifically:

- The repo generator created `infra/nginx/certs/cert.pem` as a self-signed leaf cert.
- That cert is mounted directly into nginx.
- The cert currently served by nginx has thumbprint `211D5F6C13B92CA1CE2A44702B3EEB7E365B8F6E`.
- Windows currently trusts different `localhost` self-signed certificates, not this one.
- As a result, both `https://localhost/api/voice/v2/session` and `wss://localhost/ws` fail with authority-invalid / untrusted-root errors.

## Recommended Remediation

### Preferred local fix

Use a locally trusted development CA and regenerate the `localhost` certificate from that CA instead of using a raw self-signed leaf certificate.

Practical options:

1. Use `mkcert` to generate a trusted local `localhost` certificate.
2. Mount the generated cert and key into `infra/nginx/certs/cert.pem` and `infra/nginx/certs/key.pem`.
3. Restart nginx so it serves the new certificate.

This is the cleanest fix because browsers and WSS clients will trust the local CA once installed.

### Alternative local fix

Import the exact current `infra/nginx/certs/cert.pem` certificate into the Windows trusted root store for the current user.

This can work because the leaf is self-signed, but it is less durable:

- Regenerating the cert will change the thumbprint and break trust again.
- Trust becomes tied to one specific file rather than a reusable local CA.

## Verification Criteria After Fix

After installing a trusted local certificate and restarting nginx, re-verify all of the following:

1. Fresh browser navigation to `https://localhost` loads without certificate warning.
2. `POST https://localhost/api/voice/v2/session` no longer fails with `ERR_CERT_AUTHORITY_INVALID`.
3. `wss://localhost/ws` connects without TLS trust errors.
4. Live TLS inspection no longer reports `UntrustedRoot`.

## Bottom Line

This is a trust problem, not an application bug.

The local stack is serving a valid-for-name but untrusted self-signed certificate. Until nginx serves a certificate chained to a trusted local CA, both browser HTTPS requests and WebSocket connections to `https://localhost` will continue to fail.