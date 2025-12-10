
#!/bin/sh

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(echo "$SCRIPT_PATH" | sed -n 's#^\(.*spire-tutorials\).*#\1#p')"
DIR="$BASE_DIR"/artefacts

MY_NUM=$1
OTHER_NUM=$2

# ID_AND_PARENT=$("$DIR"/bin/spire-server entry show -socketPath "$DIR"/server/"$MY_NUM"/api.sock | awk -F': ' '/Entry/ {printf $2} /Parent/ {printf " %s\n", $2;}')


FEDERATES_WITH_FLAGS=$("$DIR"/bin/spire-server federation list -socketPath "$DIR"/server/"$MY_NUM"/api.sock | awk '/Trust domain/ {print "-federatesWith spiffe://"$4}' )

"$DIR"/bin/spire-server entry show -socketPath "$DIR"/server/"$MY_NUM"/api.sock | awk -F': ' '/Entry/ {printf $2} /SPIFFE/ {printf " %s", $2}  /Parent/ {printf " %s\n", $2;}' |
while IFS= read -r line
do
    echo "Processing entry update: $line"
    ENTRY_ID=$(echo $line | awk -F' ' '{print $1}')
    SPIFFE_ID=$(echo $line | awk -F' ' '{print $2}')
    PARENT_ID=$(echo $line | awk -F' ' '{print $3}')

    echo "SPIFFE_ID $SPIFFE_ID"
    echo "FEDERATES_WITH_FLAGS is $FEDERATES_WITH_FLAGS"

    "$DIR"/bin/spire-server entry update \
	-entryID "$ENTRY_ID" \
	-socketPath "$DIR"/server/"$MY_NUM"/api.sock \
	-selector unix:user:"$USER" \
	-parentID "$PARENT_ID" \
	-spiffeID "$SPIFFE_ID" \
    $FEDERATES_WITH_FLAGS 
done