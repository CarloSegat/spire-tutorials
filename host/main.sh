#!/bin/sh

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
find "$DIR"/server/"$NUM" -type d -name "data" -exec rm -rf {} +
find "$DIR"/agent/"$NUM"-1 -type d -name "data" -exec rm -rf {} +
find "$DIR"/agent/"$NUM"-2 -type d -name "data" -exec rm -rf {} +

export PORT=$(( 8080 + (NUM * 4 - 3)))
export FED_PORT=$(( PORT + 1 ))
export DOMAIN="$NUM".example.snet

mkdir -p "$DIR"/server"/$NUM"
openssl genrsa -out server.key 2048
rm -f "$DIR"/agent-cacert.pem
openssl req -new -x509 -key server.key -out agent-cacert.pem -days 3650 -subj "/CN=SPIRE SERVER CA"

cp "$DIR"/agent-cacert.pem "$DIR"/server/"$NUM"/agent-cacert.pem
"$DIR"/bin/spire-server run -expandEnv -config "$DIR"/server/server.conf &
pids="$!"

export AGENT_NUM="$NUM"-1
pid1=$(create_single_agent "$NUM" "$AGENT_NUM")
pids="$pids $pid1"

export W1_PORT=$(( PORT + 2 ))
"$DIR"/bin/broker-webapp unix://"$DIR"/host/agent/"$AGENT_NUM"/api.sock "$W1_PORT"



export AGENT_NUM="$NUM"-2
pid2=$(create_single_agent "$NUM" "$AGENT_NUM")
pids="$pids $pid2"

export W2_PORT=$(( PORT + 3 ))
"$DIR"/bin/broker-webapp unix://"$DIR"/host/agent/"$AGENT_NUM"/api.sock "$W2_PORT"

echo $pids




