# --- Stage 1: Build ---
FROM alpine:latest AS builder

RUN apk add --no-cache \
    build-base \
    pkgconf \
    librtlsdr-dev \
    libusb-compat-dev \
    ncurses-dev \
    zlib-dev \
    zstd-dev \
    linux-headers \
    git \
    bash

WORKDIR /src
COPY . /src

# Compile dump1090 (with RTLSDR and RTL-TCP support) and view1090, strip debug symbols
RUN make clean && \
    make -j$(nproc) BLADERF=no HACKRF=no LIMESDR=no SOAPYSDR=no dump1090 view1090 && \
    strip /src/dump1090 /src/view1090

# Clone and compile readsb
RUN git clone --depth 1 https://github.com/wiedehopf/readsb.git /src/readsb-src && \
    cd /src/readsb-src && \
    make -j$(nproc) RTLSDR=yes OPTIMIZE="-O3" readsb viewadsb && \
    strip /src/readsb-src/readsb /src/readsb-src/viewadsb

# Clone and prepare tar1090 and tar1090-db
RUN git clone --depth 1 https://github.com/wiedehopf/tar1090.git /src/tar1090-src && \
    git clone --depth 1 https://github.com/wiedehopf/tar1090-db.git /src/tar1090-db && \
    git clone --depth 1 https://github.com/wiedehopf/graphs1090.git /src/graphs1090-src && \
    mkdir -p /src/tar1090-web && \
    cp -r /src/tar1090-src/html/* /src/tar1090-web/ && \
    DB_VERSION=$(cd /src/tar1090-db && git rev-parse --short HEAD 2>/dev/null || echo "db") && \
    TAR_VERSION=$(cd /src/tar1090-src && git rev-parse --short HEAD 2>/dev/null || echo "1.0") && \
    cp -r /src/tar1090-db/db /src/tar1090-web/db-$DB_VERSION && \
    sed -i "s#let databaseFolder = \"[^\"]*\";#let databaseFolder = \"db-$DB_VERSION\";#" /src/tar1090-web/index.html && \
    echo "{\"tar1090Version\": \"$TAR_VERSION\", \"databaseVersion\": \"$DB_VERSION\"}" > /src/tar1090-web/version.json && \
    (cd /src/tar1090-web && bash /src/tar1090-src/cachebust.sh /src/tar1090-src/cachebust.list /src/tar1090-web)

# --- Stage 2: Minimal Runtime ---
FROM alpine:latest

RUN apk add --no-cache \
    librtlsdr \
    libusb \
    ncurses-libs \
    zlib \
    zstd-libs \
    curl \
    lighttpd \
    tzdata \
    bash \
    jq \
    coreutils \
    gawk \
    procps \
    collectd \
    collectd-rrdtool \
    collectd-python \
    collectd-disk \
    rrdtool \
    font-dejavu \
    python3 && \
    rm -rf /var/cache/apk/*

WORKDIR /app

COPY --from=builder /src/dump1090 /usr/local/bin/dump1090
COPY --from=builder /src/view1090 /usr/local/bin/view1090
COPY --from=builder /src/readsb-src/readsb /usr/local/bin/readsb
COPY --from=builder /src/readsb-src/viewadsb /usr/local/bin/viewadsb
COPY --from=builder /src/public_html /usr/share/skyaware/html
COPY --from=builder /src/tar1090-web /usr/local/share/tar1090/html
COPY --from=builder /src/graphs1090-src /usr/share/graphs1090
COPY --from=builder /src/graphs1090-src/default /etc/default/graphs1090
COPY tar1090.sh /usr/local/bin/tar1090.sh
COPY lighttpd.conf /etc/lighttpd/lighttpd.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /usr/local/bin/tar1090.sh /entrypoint.sh /usr/share/graphs1090/*.sh && \
    mkdir -p /usr/local/share/tar1090/aircraft_sil /run/graphs1090 /var/lib/collectd/rrd

# Ports:
# 8080  - tar1090 & SkyAware Web Map
# 30001 - Raw input
# 30002 - Raw output
# 30003 - BaseStation / SBS output
# 30004 - Beast input
# 30005 - Beast output
# 10001 - FlightAware TSV output
EXPOSE 8080 30001 30002 30003 30004 30005 10001

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--quiet"]
