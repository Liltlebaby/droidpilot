#!/system/bin/sh
# Magisk runs this in late_start service mode.
umask 077
module_dir="${0%/*}"
reports="$module_dir/reports"
mkdir -p "$reports" || exit 1
stamp=$(date -u +%Y%m%dT%H%M%SZ) || exit 1
pending=$(mktemp "$reports/.pending.XXXXXX") || exit 1
trap 'rm -f "$pending"' EXIT
android=$(getprop ro.build.version.release)
kernel=$(uname -r)
uptime=$(cut -d ' ' -f 1 /proc/uptime)
boot_id=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
{
    printf 'timestamp_utc=%s\n' "$stamp"
    printf 'android_version=%s\n' "${android:-unknown}"
    printf 'kernel=%s\n' "${kernel:-unknown}"
    printf 'uptime_seconds=%s\n' "${uptime:-unknown}"
    printf 'boot_id=%s\n' "${boot_id:-unavailable}"
} > "$pending" || exit 1
mv "$pending" "$reports/boot-$stamp-${pending##*.}.txt" || exit 1

# Fixed-format, space-free filenames sort oldest first by UTC timestamp.
set -- "$reports"/boot-*.txt
while [ "$#" -gt 10 ]; do
    rm -f "$1" || exit 1
    shift
done
