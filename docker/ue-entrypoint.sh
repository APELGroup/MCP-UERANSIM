#!/bin/bash

# Replace value in the configuration file
sed -i "s/gnbSearchList: .*/gnbSearchList: $GNB_SEARCH_LIST/" /etc/ueransim/open5gs-ue.yaml

echo "Configuration updated. UE ready."
echo "Use: nr-ue -c /etc/ueransim/open5gs-ue.yaml"