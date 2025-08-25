# Alpine Linux base
FROM alpine:3.16 AS builder

# Install required dependencies
RUN apk add --no-cache \
    gcc g++ cmake ninja make \
    libc-dev linux-headers git \
    lksctp-tools-dev lksctp-tools \
    musl-dev

# Clone UERANSIM
WORKDIR /opt
RUN git clone https://github.com/aligungr/UERANSIM.git
WORKDIR /opt/UERANSIM

# Build UERANSIM
RUN make

# Final image
FROM alpine:3.16

# Install required runtime libraries
RUN apk add --no-cache \
    lksctp-tools \
    libstdc++ \
    bash

# Copy executables and configuration files
COPY --from=builder /opt/UERANSIM/build/nr-gnb /usr/local/bin/
COPY --from=builder /opt/UERANSIM/config/open5gs-gnb.yaml /etc/ueransim/

# Label for container type identification
LABEL ueransim.type=gnb

# Default values for arguments
ENV LINK_IP="127.0.0.1" \
    NGAP_IP="127.0.0.1" \
    GTP_IP="127.0.0.1" \
    AMF_ADDRESS="127.0.0.5" \
    AMF_PORT="38412"

# Script for dynamic configuration
COPY gnb-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/gnb-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/gnb-entrypoint.sh"]