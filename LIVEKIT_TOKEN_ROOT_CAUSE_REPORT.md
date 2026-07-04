# LIVEKIT_TOKEN_ROOT_CAUSE_REPORT

## Scope
Investigate the Voice V2 LiveKit failure:

- `could not establish signal connection:`
- `invalid token`

Goal: identify the exact reason the generated LiveKit token is rejected.

## Verdict
The LiveKit browser token is structurally valid, but it is signed with credentials that are not accepted by the configured LiveKit server.

Exact root cause:
- the running backend generates JWTs with `iss=APIFsfcFzUaWokA`
- those JWTs are signed using the configured `LIVEKIT_API_SECRET`
- the target LiveKit cloud endpoint `wss://cp-d8w41gwq.livekit.cloud` rejects both:
  - the browser join token on signal connect
  - the backend admin API credentials on RoomService requests

That means the configured `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` pair does not belong to the LiveKit project behind `cp-d8w41gwq.livekit.cloud`, or the secret has been rotated and the backend is still using the old one.

This is not a claim-shape bug in the generated JWT.

## Token Generation Path
Runtime source path:

1. `backend/voice_v2/voice_routes_v2.py`
   - `POST /api/voice/v2/session`
   - calls `generate_user_token(...)`
2. `backend/voice_v2/livekit_manager.py`
   - reads:
     - `LIVEKIT_URL`
     - `LIVEKIT_API_KEY`
     - `LIVEKIT_API_SECRET`
   - generates token via `livekit.api.AccessToken(...).with_identity(...).with_ttl(...).with_grants(...).to_jwt()`

Relevant code:
- `backend/voice_v2/livekit_manager.py`
- `backend/voice_v2/voice_routes_v2.py`

## Running Configuration Verified
From the running `cortex-backend` container:

- `LIVEKIT_URL = wss://cp-d8w41gwq.livekit.cloud`
- `LIVEKIT_API_KEY = APIFsfcFzUaWokA`
- `LIVEKIT_API_SECRET` present, length `44`

These values match what the backend is actively using to sign tokens.

## Captured Generated JWT
A fresh token was captured from a live call to:
- `POST https://localhost/api/voice/v2/session`

Sample generated token:
- `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...wm_O1EcTt1CNPoBkhoU0_0LTIUrTCMv2EG9mky7O_ZA`

JWT header decoded:
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

JWT payload decoded:
```json
{
  "exp": 1781456398,
  "iss": "APIFsfcFzUaWokA",
  "name": "rtc-test-user-2",
  "nbf": 1781452798,
  "sub": "rtc-test-user-2",
  "video": {
    "canPublish": true,
    "canPublishData": true,
    "canSubscribe": true,
    "room": "cortex-83ba3a45",
    "roomJoin": true
  }
}
```

## Claim Verification
Requested fields verified:

- `iss`: present and equals configured API key `APIFsfcFzUaWokA`
- `sub`: present and equals user identity
- `identity`: encoded as LiveKit `sub`; backend also returned matching `identity` in session response
- `room`: present under `video.room`
- `exp`: present and reasonable, approximately 60 minutes after issue time

Observed claim shape is normal for a LiveKit access token.

## Comparison Against Actual LiveKit Server
### 1. Direct browser-style signal join validation
Using the official Python LiveKit RTC SDK, a fresh backend-generated token was used against:
- `wss://cp-d8w41gwq.livekit.cloud`

Observed result:
- repeated signal handshake failures
- final error:
  - `401 Unauthorized - invalid token`

This reproduces the browser failure outside the browser.

### 2. Direct LiveKit admin API validation
Using the official Python LiveKit admin SDK with the same configured:
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- server host `cp-d8w41gwq.livekit.cloud`

A RoomService `ListRooms` call returned HTTP `401`.

This is decisive because it shows the server rejects the configured project credentials themselves, not just one specific browser token instance.

## Room Creation Flow Verification
Current room flow in code:

1. `POST /api/voice/v2/session` creates a local CortexPrime session record via `voice_session_store.create(...)`
2. backend generates a user join token
3. backend starts the Pipecat background pipeline
4. pipeline creates an agent token and tries to join the same LiveKit room via `LiveKitTransport`

Important finding:
- there is no explicit LiveKit `CreateRoom` call anywhere in the Voice V2 path
- the code does not use `LiveKitAPI.CreateRoomRequest`
- room existence depends on successful participant connection to LiveKit

Consequence:
- because both user and agent tokens are rejected by the target LiveKit server, the room never materializes in LiveKit even though the local CortexPrime session record is created successfully

So the room flow is failing before any valid LiveKit room join can occur.

## What Was Ruled Out
The following were ruled out as primary causes:

- malformed JWT header: header is standard `HS256`
- missing issuer: `iss` is present
- missing subject/identity: `sub` is present and correct
- missing room grant: `video.room` and `video.roomJoin=true` are present
- expired token: `exp` is valid at generation time
- wrong token TTL: token lifetime is normal
- frontend-only bug: failure reproduced with official SDK outside the browser

## Exact Root Cause Statement
The token is rejected because the configured LiveKit credentials do not match the LiveKit cloud project at `cp-d8w41gwq.livekit.cloud`.

In practical terms, one of these is true:
- `LIVEKIT_API_KEY` is for a different LiveKit project than `LIVEKIT_URL`
- `LIVEKIT_API_SECRET` does not match the configured API key
- the secret was rotated in LiveKit Cloud and `backend/.env` still contains the old secret
- the `LIVEKIT_URL` points to a different cloud project than the one that issued `APIFsfcFzUaWokA`

Because the claim set is valid and both admin API auth and RTC signal auth fail with `401 invalid token`, the failure is a credential-to-server mismatch, not a JWT payload construction bug.

## Recommended Remediation
1. In LiveKit Cloud, open the project for `cp-d8w41gwq.livekit.cloud` and verify the exact API key/secret pair.
2. Replace backend `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` with the active credentials for that project.
3. If the current key belongs to a different project, either:
   - point `LIVEKIT_URL` to the matching project endpoint, or
   - replace the key/secret with ones belonging to `cp-d8w41gwq.livekit.cloud`.
4. Restart the backend container after updating env.
5. Re-run:
   - admin API `ListRooms`
   - `POST /api/voice/v2/session`
   - RTC connect with returned token

## Confidence
High.

The failure was reproduced through two independent official LiveKit paths:
- admin API auth returned `401`
- RTC signal connect returned `401 invalid token`

That combination isolates the fault to LiveKit credential/server mismatch.