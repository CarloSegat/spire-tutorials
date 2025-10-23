FROM --platform=linux/amd64 golang:latest

# Create a non-root user 'bob' with a home directory
# Using useradd since base is Debian-based (Golang)

# Copy the binary (as root, so chown it to bob)
COPY broker-webapp /usr/local/bin/broker-webapp

# Copy convenient tools from Alpine (chown to bob for consistency)
COPY --link --from=alpine:3.17 /bin/cat /bin/cat
COPY --link --from=alpine:3.17 /bin/sh /bin/sh
COPY --link --from=alpine:3.17 /bin/ls /bin/ls
COPY --link --from=alpine:3.17 /usr/bin/tee /usr/bin/tee
COPY --link --from=alpine:3.17 /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1

# Uncomment and adjust these if needed (note: apk is for Alpine; base is Debian, so use apt if installing packages)
RUN apt-get update && apt-get install -y iproute2 socat coreutils && rm -rf /var/lib/apt/lists/*

# COPY conf/agent.conf /opt/spire/conf/agent/agent.conf
# COPY conf/agent.key.pem /opt/spire/conf/agent/agent.key.pem
# COPY conf/agent.crt.pem /opt/spire/conf/agent/agent.crt.pem

# Switch to the 'bob' user for runtime
LABEL "dio"="bestiacan"

ENTRYPOINT []
CMD broker-webapp