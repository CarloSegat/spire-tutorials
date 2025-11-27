
#!/bin/sh

SCRIPT_PATH="$(realpath "$0")"
DIR="$(dirname "$SCRIPT_PATH")"

MY_NUM=$1
OTHER_NUM=$2

ID_AND_PARENT=$("$DIR"/bin/spire-server entry show -socketPath "$DIR"/server/"$MY_NUM"/api.sock | awk -F': ' '/Entry/ {printf $2} /Parent/ {printf " %s\n", $2;}')

"$DIR"/bin/spire-server entry show -socketPath "$DIR"/server/"$MY_NUM"/api.sock | awk -F': ' '/Entry/ {printf $2} /SPIFFE/ {printf " %s", $2}  /Parent/ {printf " %s\n", $2;}' |
while IFS= read -r line
do
    echo "Processing: $line"
    ENTRY_ID=$(echo $line | awk -F' ' '{print $1}')
    SPIFFE_ID=$(echo $line | awk -F' ' '{print $2}')
    PARENT_ID=$(echo $line | awk -F' ' '{print $3}')

    echo "SPIFFE_ID $SPIFFE_ID"

    "$DIR"/bin/spire-server entry update \
	-entryID "$ENTRY_ID" \
	-socketPath /home/carlo/spire-tutorials/host/server/"$MY_NUM"/api.sock \
	-federatesWith spiffe://"$OTHER_NUM".snet.example \
	-selector unix:user:carlo \
	-parentID "$PARENT_ID" \
	-spiffeID "$SPIFFE_ID"
done
