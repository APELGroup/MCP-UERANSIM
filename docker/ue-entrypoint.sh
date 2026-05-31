#!/bin/bash

# Replace the IP entry under gnbSearchList (YAML array item format: "  - <ip>")
sed -i "s/- .*/- $GNB_SEARCH_LIST/" /etc/ueransim/open5gs-ue.yaml

echo "Configuration updated. UE ready."
echo "Use: nr-ue -c /etc/ueransim/open5gs-ue.yaml"