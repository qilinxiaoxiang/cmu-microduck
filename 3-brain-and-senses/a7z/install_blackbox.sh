#!/usr/bin/env bash
# Install the A7Z flight recorder from the Mac:  bash install_blackbox.sh   (A7Z_HOST=a7z by default)
#
# What it does, idempotently:
#   1. copies pi/blackbox.py to ~/duck/ and its unit to /etc/systemd/system/duck-blackbox.service, enables and
#      (re)starts it; one b<NNNN>-<boot8> kmsg.log + sys.jsonl pair per boot appears in ~/duck-logs/blackbox/
#   2. installs /etc/systemd/journald.conf.d/duck-blackbox.conf (persistent journal, written every second) and
#      /etc/sysctl.d/90-duck-blackbox.conf (lockup and hung-task warnings early enough to print before the watchdog
#      reset, dirty data on the card within about 1 s), applies both at once
#   3. checks, failing on any miss: installed files match the Mac copies (sha256), the service is active, a marker
#      written to /dev/kmsg reaches this boot's kmsg.log within 3 s, sys.jsonl grows by at least 5 rows in 2 s,
#      duck-thermal-log.service is active; prints the lockup settings in force, who arms the watchdog and its
#      timeout, whether earlier boots' recorder files exist, and where ~/duck-run.sh sends walk_wired.py's printed
#      messages (STOP reasons and torque refusals live only there)
#
# Undo: sudo systemctl disable --now duck-blackbox; sudo rm /etc/systemd/system/duck-blackbox.service
#       /etc/systemd/journald.conf.d/duck-blackbox.conf /etc/sysctl.d/90-duck-blackbox.conf; reboot.
# It never moves the robot and does not touch walk_wired.py, the boot configuration or the servo bus.
set -euo pipefail

HOST=${A7Z_HOST:-a7z}
HERE=$(cd "$(dirname "$0")" && pwd)
PI="$HERE/../pi"
quiet() { grep -v -E "quantum|store now|upgraded" || true; }   # OpenSSH post-quantum notice on every connection
FILES=("$PI/blackbox.py" "$PI/systemd/duck-blackbox.service" "$PI/systemd/journald-duck-blackbox.conf"
       "$PI/systemd/sysctl-duck-blackbox.conf")
SUMS=$(for f in "${FILES[@]}"; do shasum -a 256 "$f" | cut -d' ' -f1; done | tr '\n' ' ')

echo "== copy"
ssh "$HOST" 'mkdir -p ~/duck /tmp/duck-blackbox-install' 2>&1 | quiet
scp -q "${FILES[@]}" "$HOST:/tmp/duck-blackbox-install/" 2>&1 | quiet

echo "== install and check"
ssh "$HOST" "SUMS='$SUMS' bash -s" <<'EOF' 2>&1 | quiet
set -u
fail=0
bad() { echo "FAIL: $*"; fail=1; }
T=/tmp/duck-blackbox-install
install -m 644 $T/blackbox.py ~/duck/blackbox.py || bad "copy blackbox.py"
sudo -n install -m 644 $T/duck-blackbox.service /etc/systemd/system/duck-blackbox.service || bad "install unit"
sudo -n mkdir -p /etc/systemd/journald.conf.d /var/log/journal
sudo -n install -m 644 $T/journald-duck-blackbox.conf /etc/systemd/journald.conf.d/duck-blackbox.conf || bad "install journald conf"
sudo -n install -m 644 $T/sysctl-duck-blackbox.conf /etc/sysctl.d/90-duck-blackbox.conf || bad "install sysctl conf"
got=$(for f in ~/duck/blackbox.py /etc/systemd/system/duck-blackbox.service \
       /etc/systemd/journald.conf.d/duck-blackbox.conf /etc/sysctl.d/90-duck-blackbox.conf; do
       sha256sum "$f" | cut -d' ' -f1; done | tr '\n' ' ')
[ "$got" = "$SUMS" ] && echo "files: installed copies match the Mac" || bad "installed files differ from the Mac copies"
echo "sysctl applied:"
sudo -n sysctl -e -p /etc/sysctl.d/90-duck-blackbox.conf | sed 's/^/  /'
for k in $(grep -o '^[a-z_.]*' /etc/sysctl.d/90-duck-blackbox.conf); do
  [ -e /proc/sys/${k//.//} ] || echo "  $k: not in this kernel (that warning will not print)"
done
sudo -n systemctl restart systemd-journald || bad "journald restart"
sudo -n systemctl daemon-reload
sudo -n systemctl enable duck-blackbox.service >/dev/null 2>&1 || bad "enable"
sudo -n systemctl restart duck-blackbox.service || bad "start"
sleep 2
systemctl is-active --quiet duck-blackbox.service && echo "service: active" || bad "service not active"
echo "rcu stall warning after: $(cat /sys/module/rcupdate/parameters/rcu_cpu_stall_timeout 2>/dev/null || echo 'n/a') s"
echo "watchdog:"
for w in /sys/class/watchdog/watchdog*; do
  [ -e "$w" ] && echo "  $(basename $w): $(cat $w/identity 2>/dev/null) timeout $(cat $w/timeout 2>/dev/null) s state $(cat $w/state 2>/dev/null)"
done
echo "  systemd: $(systemctl show -p RuntimeWatchdogUSec -p RebootWatchdogUSec | tr '\n' ' ')"
command -v wdctl >/dev/null && sudo -n wdctl 2>/dev/null | sed 's/^/  /' | head -8
echo "  kernel cmdline: $(cat /proc/cmdline)"
cd ~/duck-logs/blackbox 2>/dev/null || { bad "no ~/duck-logs/blackbox"; exit 1; }
b=$(tr -d - < /proc/sys/kernel/random/boot_id | cut -c1-8)
k=$(ls b????-$b-kmsg.log 2>/dev/null | head -1)
[ -n "$k" ] || { bad "no kmsg.log for this boot ($b)"; exit 1; }
s=${k%-kmsg.log}-sys.jsonl
echo "this boot: $k  $s"
mark="duck-blackbox install check $(date +%s)"
echo "$mark" | sudo -n tee /dev/kmsg >/dev/null
sleep 3
grep -q "$mark" "$k" && echo "kmsg: marker on the card" || bad "kmsg marker missing"
grep -m1 -o "boot-reason: [A-Z-]*" "$k" && true
n0=$(wc -l < "$s"); sleep 2; n1=$(wc -l < "$s")
[ $((n1 - n0)) -ge 5 ] && echo "sys: $((n1 - n0)) rows in 2 s" || bad "sys only $((n1 - n0)) rows in 2 s"
head -1 "$s" | cut -c1-400
systemctl is-active --quiet duck-thermal-log.service && echo "thermal log: active (~/duck-logs/thermal.log)" \
  || bad "duck-thermal-log not active"
echo "earlier boots on the card: $(ls b????-*-kmsg.log | grep -v -- "-$b-" | wc -l | tr -d ' ') (0 right after the first install; after the next reboot it must be at least 1)"
echo "journald: $(grep -h SyncIntervalSec /etc/systemd/journald.conf.d/*.conf | tail -1), $(journalctl --disk-usage 2>/dev/null)"
if [ -f ~/duck-run.sh ]; then
  echo "~/duck-run.sh (where the brain's printed messages go):"
  sed 's/^/  /' ~/duck-run.sh | head -30
else
  echo "no ~/duck-run.sh"
fi
exit $fail
EOF
echo "== done"
