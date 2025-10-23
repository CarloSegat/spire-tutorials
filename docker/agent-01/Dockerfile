FROM --platform=linux/amd64 my/local/spire-agent:1.13.1 as diobastardo

FROM archlinux:multilib-devel-20251019.0.436919

COPY --from=diobastardo /opt/spire /opt/spire

COPY --link --from=alpine:3.17 /bin/cat /bin/cat
COPY --link --from=alpine:3.17 /bin/sh /bin/sh
COPY --link --from=alpine:3.17 /bin/ls /bin/ls
COPY --link --from=alpine:3.17 /usr/bin/tail /usr/bin/tail
COPY --link --from=alpine:3.17 /usr/bin/tee /usr/bin/tee
COPY --link --from=alpine:3.17 /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1

COPY conf/agent.conf /opt/spire/conf/agent/agent.conf
COPY conf/agent.key.pem /opt/spire/conf/agent/agent.key.pem
COPY conf/agent.crt.pem /opt/spire/conf/agent/agent.crt.pem

WORKDIR /opt/spire

ENTRYPOINT ["/opt/spire/bin/spire-agent", "run"]