# --- Stage 1: Build ---
FROM alpine:latest AS builder

RUN apk add --no-cache \
    build-base \
    pkgconf \
    librtlsdr-dev \
    libusb-compat-dev \
    ncurses-dev \
    linux-headers

WORKDIR /src
COPY . /src

# Compile dump1090 (with RTLSDR and RTL-TCP support) and view1090, strip debug symbols
RUN make clean && \
    make -j$(nproc) BLADERF=no HACKRF=no LIMESDR=no SOAPYSDR=no dump1090 view1090 && \
    strip /src/dump1090 /src/view1090

# --- Stage 2: Minimal Runtime ---
FROM alpine:latest

RUN apk add --no-cache \
    librtlsdr \
    libusb \
    ncurses-libs \
    lighttpd \
    tzdata && \
    rm -rf /var/cache/apk/*

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
