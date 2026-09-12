#!/bin/bash
set -e

# Cleanup on exit
cleanup() {
    echo "[dump1090-tar1090] Stopping background processes..."
    pkill -P $$ || true
    exit 0
}
trap cleanup SIGTERM SIGINT SIGHUP SIGQUIT

# Ensure run directories exist
mkdir -p /run/dump1090-fa
mkdir -p /run/tar1090
mkdir -p /usr/local/share/tar1090/aircraft_sil

# If LAT and LON are provided, configure tar1090 config.js receiver location
CONFIG_JS="/usr/local/share/tar1090/html/config.js"
if [ -f "$CONFIG_JS" ]; then
    if [ -n "$LAT" ]; then
        if grep -q "SiteLat" "$CONFIG_JS"; then
            sed -i "s/SiteLat = .*/SiteLat = ${LAT};/" "$CONFIG_JS"
        else
            echo "SiteLat = ${LAT};" >> "$CONFIG_JS"
        fi
    fi
    if [ -n "$LON" ]; then
        if grep -q "SiteLon" "$CONFIG_JS"; then
            sed -i "s/SiteLon = .*/SiteLon = ${LON};/" "$CONFIG_JS"
        else
            echo "SiteLon = ${LON};" >> "$CONFIG_JS"
        fi
    fi
    if [ -n "$SITE_NAME" ]; then
        if grep -q "SiteName" "$CONFIG_JS"; then
            sed -i "s/SiteName = .*/SiteName = \"${SITE_NAME}\";/" "$CONFIG_JS"
        else
            echo "SiteName = \"${SITE_NAME}\";" >> "$CONFIG_JS"
        fi
    fi
fi

# Start lighttpd for web map (tar1090 & skyaware)
echo "[dump1090-tar1090] Starting lighttpd webserver on port 8080..."
lighttpd -f /etc/lighttpd/lighttpd.conf

# Start tar1090 background history daemon
if [ "${ENABLE_TAR1090}" != "0" ] && [ "${ENABLE_TAR1090}" != "false" ]; then
    echo "[dump1090-tar1090] Starting tar1090 track history daemon..."
    export INTERVAL="${INTERVAL:-8}"
    export HISTORY_SIZE="${HISTORY_SIZE:-450}"
    export CHUNK_SIZE="${CHUNK_SIZE:-60}"
    export ENABLE_978="${ENABLE_978:-no}"
    /usr/local/bin/tar1090.sh /run/tar1090 /run/dump1090-fa &
fi

# If the first argument is an executable not starting with '-', run it
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ] && [ "$1" != "dump1090" ]; then
    exec "$@"
fi

ARGS=""

# RTL-TCP configuration (IP and PORT variables)
RTL_TARGET_IP="${RTL_TCP_IP:-${RTL_TCP_HOST:-${IP}}}"
RTL_TARGET_PORT="${RTL_TCP_PORT:-${PORT:-1234}}"

if [ -n "$RTL_TARGET_IP" ]; then
    case "$RTL_TARGET_IP" in
        *:*)
            ARGS="$ARGS --device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}"
            ;;
        *)
            ARGS="$ARGS --device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}:${RTL_TARGET_PORT}"
            ;;
    esac
else
    ARGS="$ARGS --device-type rtlsdr"
    if [ -n "$DEVICE_INDEX" ]; then
        ARGS="$ARGS --device $DEVICE_INDEX"
    fi
fi

# Gain configuration
if [ -n "$GAIN" ]; then
    ARGS="$ARGS --gain $GAIN"
fi

# AGC
if [ "$ENABLE_AGC" = "1" ] || [ "$ENABLE_AGC" = "true" ]; then
    ARGS="$ARGS --enable-agc"
fi

# Frequency
if [ -n "$FREQ" ]; then
    ARGS="$ARGS --freq $FREQ"
fi

# PPM error correction
if [ -n "$PPM" ]; then
    ARGS="$ARGS --ppm $PPM"
fi

# Location
if [ -n "$LAT" ]; then
    ARGS="$ARGS --lat $LAT"
fi
if [ -n "$LON" ]; then
    ARGS="$ARGS --lon $LON"
fi
if [ -n "$MAX_RANGE" ]; then
    ARGS="$ARGS --max-range $MAX_RANGE"
fi

# Aggressive mode / CRC error correction
if [ "$AGGRESSIVE" = "1" ] || [ "$AGGRESSIVE" = "true" ] || [ "$FIX_2BIT" = "1" ] || [ "$FIX_2BIT" = "true" ]; then
    ARGS="$ARGS --fix-2bit"
elif [ "$FIX" = "1" ] || [ "$FIX" = "true" ]; then
    ARGS="$ARGS --fix"
fi

# Networking & JSON output for SkyAware and tar1090 web interfaces
if [ "$NET" = "1" ] || [ "$NET" = "true" ] || [ -z "$NET" ]; then
    if [ "$NET" != "0" ] && [ "$NET" != "false" ]; then
        ARGS="$ARGS --net --write-json /run/dump1090-fa"
    fi
fi

# Append any arguments passed as CMD or extra args
if [ "$1" = "dump1090" ]; then
    shift
fi
ARGS="$ARGS $@"

echo "[dump1090-tar1090] Starting dump1090: /usr/local/bin/dump1090 $ARGS"
/usr/local/bin/dump1090 $ARGS &
DUMP_PID=$!

wait $DUMP_PID
