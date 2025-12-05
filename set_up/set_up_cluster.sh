#!/bin/sh

if [ $# -eq 0 ]; then
    echo "Error: first argument must be this server number" >&2
    exit 1
fi

if [ $# -eq 1 ]; then
    echo "Error: second argument must be max server number." >&2
    exit 1
fi

create_single_agent() {
    local num="$1"
    local agent_num="$2"

    mkdir -p "$DIR"/agent/"$agent_num"
    openssl genrsa -out "agent-$num.key" 2048
    openssl req -new -key "agent-$num.key" -out "agent-$num.csr" -subj "/CN=$agent_num" -config agent.csr.cnf -extensions v3_ext
    openssl x509 -req -in "agent-$num.csr" -CA ./agent-cacert.pem -CAkey server.key -CAcreateserial -out "agent-$num.crt.pem" -days 365 -sha256 -extfile agent.csr.cnf -extensions v3_ext
    echo "JOHJOHJHJOOHOHO"
    cp ./agent-$num.crt.pem "$DIR"/agent/"$agent_num"/agent.crt.pem
    cp ./agent-$num.key "$DIR"/agent/"$agent_num"/agent.key.pem
    # "$DIR"/bin/spire-agent run -expandEnv -config "$DIR"/agent/agent.conf &
    # local pid=$!  # Capture the PID of the background spire-agent process
    # echo "$pid"
    "$DIR"/bin/spire-agent run -expandEnv -config ./agent.conf \
        >/dev/null 2>&1 </dev/null &
    pid=$!
    echo "$pid"
}


DIR="/home/carlo/spire-tutorials/artefacts"

export NUM="$1"
export MAX_NUM="$2"

export PORT=$(( 8080 + (NUM * 6 - 5)))
export FED_PORT=$(( PORT + 1 ))
export DOMAIN="$NUM".snet.example

mkdir -p "$DIR"/server/"$NUM"
openssl genrsa -out server.key 2048
rm -f ./agent-cacert.pem
openssl req -new -x509 -key server.key -out agent-cacert.pem -days 3650 -subj "/CN=SPIRE SERVER CA"

cp ./agent-cacert.pem "$DIR"/server/"$NUM"/agent-cacert.pem
"$DIR"/bin/spire-server run -expandEnv -config ./server.conf &




export AGENT_NUM="$NUM"-1
create_single_agent "$NUM" "$AGENT_NUM"

export SPIFFE_ENDPOINT_SOCKET=unix://"$DIR"/agent/"$AGENT_NUM"/api.sock

export W1_PORT=$(( PORT + 2 ))
mkdir -p "$DIR"/workloads/"$NUM"/1
"$DIR"/bin/example-workload "$W1_PORT" "$DIR"/workloads/"$NUM"/1 "$NUM" "$MAX_NUM" &

export W2_PORT=$(( PORT + 3 ))
mkdir -p "$DIR"/workloads/"$NUM"/2
"$DIR"/bin/example-workload "$W2_PORT" "$DIR"/workloads/"$NUM"/2 "$NUM" "$MAX_NUM" &




export AGENT_NUM="$NUM"-2
create_single_agent "$NUM" "$AGENT_NUM"

export SPIFFE_ENDPOINT_SOCKET=unix://"$DIR"/agent/"$AGENT_NUM"/api.sock

export W3_PORT=$(( PORT + 4 ))
mkdir -p "$DIR"/workloads/"$NUM"/3
"$DIR"/bin/example-workload "$W3_PORT" "$DIR"/workloads/"$NUM"/3 "$NUM" "$MAX_NUM" &

export W4_PORT=$(( PORT + 5 ))
mkdir -p "$DIR"/workloads/"$NUM"/4
"$DIR"/bin/example-workload "$W4_PORT" "$DIR"/workloads/"$NUM"/4 "$NUM" "$MAX_NUM" &


./register_agents_entries.sh "$NUM" "$DIR"

find . -name '[server|agent].*[pem|csr|key|srl]' -delete

find . -maxdepth 1 -regextype posix-extended -regex '.*/(server|agent).*(pem|key|csr|srl)' -type f -delete
