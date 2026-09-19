# The CONTAINED rollback worker image (ADR-124). Same shape as the restart
# worker's (ADR-089), and every line of that minimalism is load-bearing for the
# CodeTrust.FIXED claim: the standard library only, one source file copied
# read-only and owned by root, a non-root runtime user, and no shell entrypoint.
#
# CONTAINED, not SANDBOXED and never SEALED: it shares the host kernel.
FROM python:3.12-alpine

RUN addgroup -g 65532 -S nonroot && adduser -u 65532 -S nonroot -G nonroot

WORKDIR /worker
COPY --chown=root:root worker.py /worker/worker.py
RUN chmod 0444 /worker/worker.py

USER 65532:65532

EXPOSE 8080

ENTRYPOINT ["python", "-u", "/worker/worker.py"]
