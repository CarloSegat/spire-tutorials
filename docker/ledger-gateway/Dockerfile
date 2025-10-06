FROM alpine:3.17

COPY ledger-gateway /bin/ledger-gateway

# Copy convenient tools to be used in the tutorial
COPY --link --from=alpine:3.17 /bin/cat /bin/cat
COPY --link --from=alpine:3.17 /bin/sh /bin/sh
COPY --link --from=alpine:3.17 /bin/ls /bin/ls
COPY --link --from=alpine:3.17 /usr/bin/tee /usr/bin/tee
COPY --link --from=alpine:3.17 /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1

WORKDIR /home
ENTRYPOINT []

CMD ledger-gateway
