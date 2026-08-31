# The image untrusted submissions run inside. Built once (see build_runners.py),
# then reused as the base for every throwaway container.
#
# Deliberately minimal:
#   - no build toolchain, no package manager cache, no extra site-packages
#   - runs as a non-root user
#   - source is injected at runtime into a tmpfs at /box by run.sh; the image
#     itself carries no submission code and its rootfs is mounted read-only
FROM python:3.12-slim

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin runner

COPY run.sh /usr/local/bin/run.sh
RUN chmod 0555 /usr/local/bin/run.sh

USER runner
WORKDIR /box

ENTRYPOINT ["/usr/local/bin/run.sh"]
