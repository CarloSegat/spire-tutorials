#!/bin/sh

if [ $# -eq 0 ]; then
    echo "Error: First argument is required." >&2
    exit 1
fi

create_single_agent() {
    local num="$1"
    local agent_num="$2"

    mkdir -p "$DIR"/agent/"$agent_num"
    openssl genrsa -out "agent-$num.key" 2048
    openssl req -new -key "agent-$num.key" -out "agent-$num.csr" -subj "/CN=$agent_num" -config agent.csr.cnf -extensions v3_ext
    openssl x509 -req -in "agent-$num.csr" -CA "$DIR"/agent-cacert.pem -CAkey server.key -CAcreateserial -out "agent-$num.crt.pem" -days 365 -sha256 -extfile agent.csr.cnf -extensions v3_ext
    cp "$DIR"/"agent-$num.crt.pem" "$DIR"/agent/"$agent_num"/agent.crt.pem
    cp "$DIR"/"agent-$num.key" "$DIR"/agent/"$agent_num"/agent.key.pem
    # "$DIR"/bin/spire-agent run -expandEnv -config "$DIR"/agent/agent.conf &
    # local pid=$!  # Capture the PID of the background spire-agent process
    # echo "$pid"
    "$DIR"/bin/spire-agent run -expandEnv -config "$DIR"/agent/agent.conf \
        >/dev/null 2>&1 </dev/null &
    pid=$!
    echo "$pid"
}



SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname $SCRIPT_PATH)"

export NUM="$1"



# delete all data folders or the agents will try to reuse the svids, which will not be valid (because in insecure mode)
find "$DIR"/server/"$NUM" -delete
find "$DIR"/agent/"$NUM"-1 -delete
find "$DIR"/agent/"$NUM"-2 -delete
find "$DIR"/workloads/"$NUM"-1 -delete
find "$DIR"/workloads/"$NUM"-2 -delete

export PORT=$(( 8080 + (NUM * 4 - 3)))
export FED_PORT=$(( PORT + 1 ))
export DOMAIN="$NUM".snet.example

mkdir -p "$DIR"/server"/$NUM"
openssl genrsa -out server.key 2048
rm -f "$DIR"/agent-cacert.pem
openssl req -new -x509 -key server.key -out agent-cacert.pem -days 3650 -subj "/CN=SPIRE SERVER CA"

cp "$DIR"/agent-cacert.pem "$DIR"/server/"$NUM"/agent-cacert.pem
"$DIR"/bin/spire-server run -expandEnv -config "$DIR"/server/server.conf &




export AGENT_NUM="$NUM"-1
create_single_agent "$NUM" "$AGENT_NUM"

export W1_PORT=$(( PORT + 2 ))
export SPIFFE_ENDPOINT_SOCKET=unix://"$DIR"/agent/"$AGENT_NUM"/api.sock
mkdir -p "$DIR"/workloads"/$AGENT_NUM"
"$DIR"/bin/broker-webapp "$W1_PORT" "$DIR"/workloads"/$AGENT_NUM" &




export AGENT_NUM="$NUM"-2
create_single_agent "$NUM" "$AGENT_NUM"

export W2_PORT=$(( PORT + 3 ))
export SPIFFE_ENDPOINT_SOCKET=unix://"$DIR"/agent/"$AGENT_NUM"/api.sock
mkdir -p "$DIR"/workloads"/$AGENT_NUM"
"$DIR"/bin/broker-webapp "$W2_PORT" "$DIR"/workloads"/$AGENT_NUM" &

./register_entries.sh "$NUM"

find . -name '[server|agent].*[pem|csr|key|srl]' -delete

find . -maxdepth 1 -regextype posix-extended -regex '.*/(server|agent).*(pem|key|csr|srl)' -type f -delete
