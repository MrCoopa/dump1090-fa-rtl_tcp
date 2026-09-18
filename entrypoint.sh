#!/bin/bash
set -e

# Cleanup on exit
cleanup() {
    echo "[adsb-container] Stopping background processes..."
    pkill -P $$ || true
    exit 0
}
trap cleanup SIGTERM SIGINT SIGHUP SIGQUIT

# Ensure shared run directories exist and setup unified symlinks
mkdir -p /run/adsb-data /run/tar1090 /run/graphs1090 /var/lib/collectd/rrd /usr/local/share/tar1090/aircraft_sil
rm -rf /run/dump1090-fa /run/readsb
ln -s /run/adsb-data /run/dump1090-fa
ln -s /run/adsb-data /run/readsb

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

# HeyWhatsThat Panorama Integration (upintheair.json)
HW_ID="${HEYWHATSTHAT_ID:-$HEYWHATSTHAT_PANORAMA_ID}"
if [ -n "$HW_ID" ]; then
    UPINTHEAIR="/usr/local/share/tar1090/html/upintheair.json"
    if [ ! -f "$UPINTHEAIR" ] || [ "$FORCE_HEYWHATSTHAT_DOWNLOAD" = "true" ] || [ "$FORCE_HEYWHATSTHAT_DOWNLOAD" = "1" ]; then
        echo "[adsb-container] Downloading HeyWhatsThat terrain outline for ID: $HW_ID..."
        ALTS="${HEYWHATSTHAT_ALTS:-3048,6096,9144,12192}"
        curl -sSL -m 30 "http://www.heywhatsthat.com/api/upintheair.json?id=${HW_ID}&refraction=0.25&alts=${ALTS}" -o "$UPINTHEAIR" \
            && echo "[adsb-container] HeyWhatsThat upintheair.json successfully installed with altitudes: ${ALTS}m" \
            || echo "[adsb-container] Warning: Failed to download HeyWhatsThat upintheair.json"
    fi
fi

# Ensure VRS-style colored filled polygons are active in tar1090
if [ -f /usr/local/bin/patch-vrs-outline.py ]; then
    python3 /usr/local/bin/patch-vrs-outline.py /usr/local/share/tar1090/html/script*.js 2>/dev/null || true
fi

# Start lighttpd for web map (tar1090 & skyaware)
echo "[adsb-container] Starting lighttpd webserver on port 8080..."
lighttpd -f /etc/lighttpd/lighttpd.conf

# Start tar1090 background history daemon
if [ "${ENABLE_TAR1090}" != "0" ] && [ "${ENABLE_TAR1090}" != "false" ]; then
    echo "[adsb-container] Starting tar1090 track history daemon..."
    export INTERVAL="${INTERVAL:-8}"
    export HISTORY_SIZE="${HISTORY_SIZE:-450}"
    export CHUNK_SIZE="${CHUNK_SIZE:-60}"
    export ENABLE_978="${ENABLE_978:-no}"
    /usr/local/bin/tar1090.sh /run/tar1090 /run/adsb-data &
fi

# Configure and start graphs1090 (collectd + rrdtool)
if [ "${ENABLE_GRAPHS1090}" != "0" ] && [ "${ENABLE_GRAPHS1090}" != "false" ]; then
    echo "[adsb-container] Configuring collectd for graphs1090..."
    mkdir -p /etc/collectd /var/lib/collectd/rrd/localhost /run/graphs1090 /usr/share/graphs1090/data-symlink
    ln -snf /run/adsb-data /usr/share/graphs1090/data-symlink/data

    cat << 'EOF' > /etc/collectd/collectd.conf
Hostname "localhost"
FQDNLookup false
Interval 60
Timeout 2
ReadThreads 5
WriteThreads 1

TypesDB "/usr/share/graphs1090/dump1090.db" "/usr/share/collectd/types.db"

LoadPlugin syslog
<Plugin syslog>
    LogLevel info
</Plugin>

LoadPlugin rrdtool
LoadPlugin table
LoadPlugin interface
LoadPlugin cpu
LoadPlugin aggregation
LoadPlugin match_regex
LoadPlugin df
LoadPlugin disk
<LoadPlugin python>
    Globals true
</LoadPlugin>

<Plugin rrdtool>
    DataDir "/var/lib/collectd/rrd"
    RRARows 3000
    RRATimespan 174000
    RRATimespan 696000
    RRATimespan 2784000
    RRATimespan 16008000
    RRATimespan 96048000
    RRATimespan 576288000
    XFF 0.8
</Plugin>

<Plugin "aggregation">
    <Aggregation>
        Plugin "cpu"
        Type "cpu"
        GroupBy "Host"
        GroupBy "TypeInstance"
        CalculateAverage true
    </Aggregation>
</Plugin>

<Plugin "df">
    MountPoint "/"
    IgnoreSelected false
</Plugin>

<Plugin "interface">
</Plugin>

<Plugin table>
    <Table "/sys/class/thermal/thermal_zone0/temp">
        Instance localhost
        Separator " "
        <Result>
            Type gauge
            InstancePrefix "cpu_temp"
            ValuesFrom 0
        </Result>
    </Table>
</Plugin>

<Plugin "disk">
    Disk "mmcblk0"
    Disk "mmcblk1"
    Disk "sda"
    Disk "sdb"
    Disk "nvme0n1"
    Disk "vda"
    IgnoreSelected false
</Plugin>

<Plugin python>
    ModulePath "/usr/share/graphs1090"
    LogTraces true
    Interactive false
    Import "dump1090"
    <Module dump1090>
        <Instance localhost>
            URL "file:///usr/share/graphs1090/data-symlink"
        </Instance>
    </Module>
    Import "system_stats"
    <Module system_stats>
        placeholder "true"
    </Module>
</Plugin>

<Chain "PostCache">
    <Rule>
        <Match regex>
            Plugin "^cpu$"
            PluginInstance "^[0-9]+$"
        </Match>
        <Target write>
            Plugin "aggregation"
        </Target>
        Target stop
    </Rule>
    Target "write"
</Chain>
EOF

    # Detect network interfaces
    for path in /sys/class/net/*; do
        [ -e "$path" ] || continue
        iface=$(basename "$path")
        case "$iface" in
            lo) ;;
            *)
                sed -i -e "/<Plugin \"interface\">/a\\    Interface \"$iface\"" /etc/collectd/collectd.conf 2>/dev/null || true
                ;;
        esac
    done

    # Detect block devices
    for path in /sys/class/block/*; do
        [ -e "$path" ] || continue
        d=$(basename "$path")
        case "$d" in
            loop*|ram*) ;;
            *)
                sed -i -e "/<Plugin \"disk\">/a\\    Disk \"$d\"" /etc/collectd/collectd.conf 2>/dev/null || true
                ;;
        esac
    done

    # If CPU thermal sensor is not accessible, remove Table block to prevent harmless warning
    if [ ! -f /sys/class/thermal/thermal_zone0/temp ]; then
        sed -i -e '/<Table "\/sys\/class\/thermal/,/<\/Table>/d' /etc/collectd/collectd.conf 2>/dev/null || true
    fi

    # Configure graphs1090 defaults if specified
    if [ -n "$GRAPHS1090_COLORSCHEME" ]; then
        sed -i -e "s/^colorscheme=.*/colorscheme=${GRAPHS1090_COLORSCHEME}/" /etc/default/graphs1090 2>/dev/null || true
    fi
    if [ -n "$GRAPHS1090_RANGE" ]; then
        sed -i -e "s/^range=.*/range=${GRAPHS1090_RANGE}/" /etc/default/graphs1090 2>/dev/null || true
    fi

    echo "[adsb-container] Starting collectd..."
    collectd -C /etc/collectd/collectd.conf || echo "[adsb-container] Warning: Failed to start collectd"

    echo "[adsb-container] Starting graphs1090 service daemon..."
    /usr/share/graphs1090/service-graphs1090.sh &
fi

# If the first argument is a distinct executable (e.g. bash), execute it
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ] && [ "$1" != "dump1090" ] && [ "$1" != "readsb" ]; then
    exec "$@"
fi

# Determine decoder choice
DECODER_CHOICE=$(echo "${DECODER:-auto}" | tr '[:upper:]' '[:lower:]')
if [ "$1" = "dump1090" ]; then
    DECODER_CHOICE="dump1090"
    shift
elif [ "$1" = "readsb" ]; then
    DECODER_CHOICE="readsb"
    shift
fi

# Determine input source: RTL-TCP vs direct RTL-SDR
RTL_TARGET_IP="${RTL_TCP_IP:-${RTL_TCP_HOST:-${IP}}}"
RTL_TARGET_PORT="${RTL_TCP_PORT:-${PORT:-1234}}"

MAIN_PID=""

if [ "$DECODER_CHOICE" = "dump1090" ]; then
    echo "[adsb-container] Selected decoder: dump1090"
    DUMP_ARGS=""
    if [ -n "$RTL_TARGET_IP" ]; then
        case "$RTL_TARGET_IP" in
            *:*) DUMP_ARGS="$DUMP_ARGS --device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}" ;;
            *)   DUMP_ARGS="$DUMP_ARGS --device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}:${RTL_TARGET_PORT}" ;;
        esac
    else
        DUMP_ARGS="$DUMP_ARGS --device-type rtlsdr"
        if [ -n "$DEVICE_INDEX" ]; then DUMP_ARGS="$DUMP_ARGS --device $DEVICE_INDEX"; fi
    fi

    if [ -n "$GAIN" ]; then DUMP_ARGS="$DUMP_ARGS --gain $GAIN"; fi
    if [ "$ENABLE_AGC" = "1" ] || [ "$ENABLE_AGC" = "true" ]; then DUMP_ARGS="$DUMP_ARGS --enable-agc"; fi
    if [ -n "$FREQ" ]; then DUMP_ARGS="$DUMP_ARGS --freq $FREQ"; fi
    if [ -n "$PPM" ]; then DUMP_ARGS="$DUMP_ARGS --ppm $PPM"; fi
    if [ -n "$LAT" ]; then DUMP_ARGS="$DUMP_ARGS --lat $LAT"; fi
    if [ -n "$LON" ]; then DUMP_ARGS="$DUMP_ARGS --lon $LON"; fi
    if [ -n "$MAX_RANGE" ]; then DUMP_ARGS="$DUMP_ARGS --max-range $MAX_RANGE"; fi

    if [ "$AGGRESSIVE" = "1" ] || [ "$AGGRESSIVE" = "true" ] || [ "$FIX_2BIT" = "1" ] || [ "$FIX_2BIT" = "true" ]; then
        DUMP_ARGS="$DUMP_ARGS --fix-2bit"
    elif [ "$FIX" = "1" ] || [ "$FIX" = "true" ]; then
        DUMP_ARGS="$DUMP_ARGS --fix"
    fi

    if [ "$NET" != "0" ] && [ "$NET" != "false" ]; then
        DUMP_ARGS="$DUMP_ARGS --net --write-json /run/adsb-data"
    fi

    DUMP_ARGS="$DUMP_ARGS $@"
    echo "[adsb-container] Starting dump1090: /usr/local/bin/dump1090 $DUMP_ARGS"
    /usr/local/bin/dump1090 $DUMP_ARGS &
    MAIN_PID=$!

else
    # readsb or auto
    echo "[adsb-container] Selected decoder: readsb (Mode: ${DECODER_CHOICE})"

    if [ -n "$RTL_TARGET_IP" ]; then
        # RTL-TCP: dump1090 handles network RTL-TCP demodulation and feeds Beast stream to readsb
        echo "[adsb-container] RTL-TCP source specified (${RTL_TARGET_IP}:${RTL_TARGET_PORT}). Starting dump1090 demodulator bridge..."
        BRIDGE_ARGS=""
        case "$RTL_TARGET_IP" in
            *:*) BRIDGE_ARGS="--device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}" ;;
            *)   BRIDGE_ARGS="--device-type rtltcp --net-rtl-tcp ${RTL_TARGET_IP}:${RTL_TARGET_PORT}" ;;
        esac
        if [ -n "$GAIN" ]; then BRIDGE_ARGS="$BRIDGE_ARGS --gain $GAIN"; fi
        if [ "$ENABLE_AGC" = "1" ] || [ "$ENABLE_AGC" = "true" ]; then BRIDGE_ARGS="$BRIDGE_ARGS --enable-agc"; fi
        if [ -n "$FREQ" ]; then BRIDGE_ARGS="$BRIDGE_ARGS --freq $FREQ"; fi
        if [ -n "$PPM" ]; then BRIDGE_ARGS="$BRIDGE_ARGS --ppm $PPM"; fi
        if [ -n "$LAT" ]; then BRIDGE_ARGS="$BRIDGE_ARGS --lat $LAT"; fi
        if [ -n "$LON" ]; then BRIDGE_ARGS="$BRIDGE_ARGS --lon $LON"; fi
        if [ -n "$MAX_RANGE" ]; then BRIDGE_ARGS="$BRIDGE_ARGS --max-range $MAX_RANGE"; fi

        /usr/local/bin/dump1090 $BRIDGE_ARGS --net --net-bo-port 30006 --net-ro-port 0 --net-sbs-port 0 --net-bi-port 0 --quiet &

        READSB_ARGS="--net --net-only --net-connector 127.0.0.1,30006,beast_in"
        READSB_ARGS="$READSB_ARGS --net-bo-port 30005 --net-ro-port 30002 --net-sbs-port 30003 --net-bi-port 30004"
        READSB_ARGS="$READSB_ARGS --write-json /run/adsb-data --range-outline-hours ${RANGE_OUTLINE_HOURS:-24}"
        if [ -n "$LAT" ]; then READSB_ARGS="$READSB_ARGS --lat $LAT"; fi
        if [ -n "$LON" ]; then READSB_ARGS="$READSB_ARGS --lon $LON"; fi
        if [ -n "$MAX_RANGE" ]; then READSB_ARGS="$READSB_ARGS --max-range $MAX_RANGE"; fi

        READSB_ARGS="$READSB_ARGS $@"
        echo "[adsb-container] Starting readsb in network mode: /usr/local/bin/readsb $READSB_ARGS"
        /usr/local/bin/readsb $READSB_ARGS &
        MAIN_PID=$!
    else
        # Direct RTL-SDR USB dongle with readsb
        READSB_ARGS="--device-type rtlsdr --net --write-json /run/adsb-data --range-outline-hours ${RANGE_OUTLINE_HOURS:-24}"
        if [ -n "$DEVICE_INDEX" ]; then READSB_ARGS="$READSB_ARGS --device $DEVICE_INDEX"; fi
        if [ -n "$GAIN" ]; then
            if [ "$GAIN" = "max" ]; then
                READSB_ARGS="$READSB_ARGS --gain 49.6"
            else
                READSB_ARGS="$READSB_ARGS --gain $GAIN"
            fi
        fi
        if [ "$ENABLE_AGC" = "1" ] || [ "$ENABLE_AGC" = "true" ]; then READSB_ARGS="$READSB_ARGS --enable-agc"; fi
        if [ -n "$FREQ" ]; then READSB_ARGS="$READSB_ARGS --freq $FREQ"; fi
        if [ -n "$PPM" ]; then READSB_ARGS="$READSB_ARGS --ppm $PPM"; fi
        if [ -n "$LAT" ]; then READSB_ARGS="$READSB_ARGS --lat $LAT"; fi
        if [ -n "$LON" ]; then READSB_ARGS="$READSB_ARGS --lon $LON"; fi
        if [ -n "$MAX_RANGE" ]; then READSB_ARGS="$READSB_ARGS --max-range $MAX_RANGE"; fi

        if [ "$FIX" = "0" ] || [ "$FIX" = "false" ]; then
            READSB_ARGS="$READSB_ARGS --no-fix"
        fi

        READSB_ARGS="$READSB_ARGS $@"
        echo "[adsb-container] Starting readsb: /usr/local/bin/readsb $READSB_ARGS"
        /usr/local/bin/readsb $READSB_ARGS &
        MAIN_PID=$!
    fi
fi

wait $MAIN_PID
