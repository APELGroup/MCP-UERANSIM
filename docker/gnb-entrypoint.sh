#!/bin/bash

CFG=/etc/ueransim/open5gs-gnb.yaml

# Network interface IPs
sed -i "s/linkIp: .*/linkIp: $LINK_IP/" $CFG
sed -i "s/ngapIp: .*/ngapIp: $NGAP_IP/" $CFG
sed -i "s/gtpIp: .*/gtpIp: $GTP_IP/" $CFG

# AMF connection
sed -i "s/- address: .*/- address: $AMF_ADDRESS/" $CFG
sed -i "s/port: .*/port: $AMF_PORT/" $CFG

# PLMN identity
sed -i "s/^mcc: .*/mcc: '$MCC'/" $CFG
sed -i "s/^mnc: .*/mnc: '$MNC'/" $CFG
sed -i "s/^tac: .*/tac: $TAC/" $CFG

# Cell parameters
sed -i "s/^cellAccessType: .*/cellAccessType: $CELL_ACCESS_TYPE/" $CFG
sed -i "s/^ignoreStreamIds: .*/ignoreStreamIds: $IGNORE_STREAM_IDS/" $CFG

# Primary slice (replaces the entire slices: block)
if [ -n "$SLICE_SD" ]; then
    awk -v sst="$SLICE_SST" -v sd="$SLICE_SD" \
        '/^slices:/{print "slices:"; print "  - sst: " sst; print "    sd: " sd; skip=1; next}
         skip && /^[^ ]/{skip=0} skip{next} {print}' \
        $CFG > /tmp/gnb_cfg.tmp && mv /tmp/gnb_cfg.tmp $CFG
else
    awk -v sst="$SLICE_SST" \
        '/^slices:/{print "slices:"; print "  - sst: " sst; skip=1; next}
         skip && /^[^ ]/{skip=0} skip{next} {print}' \
        $CFG > /tmp/gnb_cfg.tmp && mv /tmp/gnb_cfg.tmp $CFG
fi

echo "Configuration updated. gNB ready."
echo "Use: nr-gnb -c $CFG"
