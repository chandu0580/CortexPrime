# The CONTAINED worker image (ADR-089).
#
# Deliberately minimal, and every line of that minimalism is load-bearing for
# the CodeTrust.FIXED claim:
#
#   * python:3.12-alpine and nothing else -- no `pip install`, no requirements
#     file, no Kubernetes SDK. The worker imports only the standard library, so
#     there is no dependency tree in which undeclared behaviour could live.
#   * one source file, copied read-only, owned by root and run by a non-root
#     user that cannot modify it.
#   * no shell entrypoint, no wrapper script: the container's PID 1 is the
#     interpreter running the one module.
#
# This image is CONTAINED, not SANDBOXED and never SEALED. It shares the host
# kernel (Phase 9.7 established by execution that this host offers only runc on
# one shared kernel, with no /dev/kvm). The hardening below is real and is
# measured by the harness; it is not virtualization and is never described as
# such.
FROM python:3.12-alpine

# A fixed, non-root identity. 65532 is the conventional "nonroot" uid and is
# chosen so the running user owns nothing on the filesystem it executes from.
RUN addgroup -g 65532 -S nonroot && adduser -u 65532 -S nonroot -G nonroot

WORKDIR /worker
COPY --chown=root:root worker.py /worker/worker.py
RUN chmod 0444 /worker/worker.py

USER 65532:65532

EXPOSE 8080

# No shell form: PID 1 is the interpreter, so a `docker exec`-free container has
# no shell process to inherit and the worker cannot fork one from its own
# entrypoint.
ENTRYPOINT ["python", "-u", "/worker/worker.py"]
