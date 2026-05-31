#!/bin/bash

CFG=/etc/ueransim/open5gs-ue.yaml

# gNB search list (matches any IP entry "  - <ip>")
sed -i "s/^  - [0-9].*/  - $GNB_SEARCH_LIST/" $CFG

# Subscriber identity (only set when env var is non-empty)
[ -n "$SUPI"  ] && sed -i "s/^supi: .*/supi: '$SUPI'/"   $CFG
[ -n "$KEY"   ] && sed -i "s/^key: .*/key: '$KEY'/"       $CFG
[ -n "$OP"    ] && sed -i "s/^op: .*/op: '$OP'/"          $CFG

# PLMN and authentication type
sed -i "s/^mcc: .*/mcc: '$MCC'/"         $CFG
sed -i "s/^mnc: .*/mnc: '$MNC'/"         $CFG
sed -i "s/^opType: .*/opType: '$OP_TYPE'/" $CFG

# PDU session
sed -i "s/^    apn: .*/    apn: '$SESSION_APN'/" $CFG

# TUN interface
sed -i "s/^tunNetmask: .*/tunNetmask: '$TUN_NETMASK'/" $CFG

# Primary slice — sessions.slice.sst (6-space indent)
sed -i "s/^      sst: .*/      sst: $SLICE_SST/" $CFG
# configured-nssai and default-nssai sst (2-space "  - sst:")
sed -i "s/^  - sst: .*/  - sst: $SLICE_SST/" $CFG

# Slice SD: add/replace if set
if [ -n "$SLICE_SD" ]; then
    # sessions.slice.sd
    awk -v sd="$SLICE_SD" \
        '/^      sd:/{found=1; print "      sd: " sd; next}
         /^      sst:/ && !found{print; print "      sd: " sd; found=1; next}
         {print}' \
        $CFG > /tmp/ue_cfg.tmp && mv /tmp/ue_cfg.tmp $CFG
    # configured-nssai and default-nssai sd
    awk -v sd="$SLICE_SD" \
        '/^[a-zA-Z]/{found=0}
         /^    sd:/{found=1; print "    sd: " sd; next}
         /^  - sst:/ && !found{print; print "    sd: " sd; found=1; next}
         {print}' \
        $CFG > /tmp/ue_cfg.tmp && mv /tmp/ue_cfg.tmp $CFG
fi

echo "Configuration updated. UE ready."
echo "Use: nr-ue -c $CFG"
