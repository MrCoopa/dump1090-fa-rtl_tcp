# --- Stage 1: Build ---
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    librtlsdr-dev \
    libusb-1.0-0-dev \
    libncurses-dev \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . /src

# Compile dump1090 (with RTLSDR and RTL-TCP support) and view1090
RUN make clean && make -j$(nproc) BLADERF=no HACKRF=no LIMESDR=no SOAPYSDR=no dump1090 view1090

# --- Stage 2: Runtime ---
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    librtlsdr0 \
    libusb-1.0-0 \
    libncurses6 \
    lighttpd \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /src/dump1090 /usr/local/bin/dump1090
COPY --from=builder /src/view1090 /usr/local/bin/view1090
COPY --from=builder /src/public_html /usr/share/skyaware/html
COPY lighttpd.conf /etc/lighttpd/lighttpd.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Ports:
# 8080  - SkyAware Web Map
# 30001 - Raw input
# 30002 - Raw output
# 30003 - BaseStation / SBS output
# 30004 - Beast input
# 30005 - Beast output
# 10001 - FlightAware TSV output
EXPOSE 8080 30001 30002 30003 30004 30005 10001

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--quiet"]
