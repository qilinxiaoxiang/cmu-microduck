# Run on the Pi via: ssh duck 'bash -s' < install.sh   (unit files must already be in ~/duck/systemd, duck_cam.sh in ~/duck)
set -e
pkill -f "pi_imu_uart.py" || true
pkill -f "duck/pwrlog.py" || true
sleep 1
sudo cp ~/duck/systemd/duck-imu.service ~/duck/systemd/duck-pwrlog.service ~/duck/systemd/duck-cam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now duck-imu.service duck-pwrlog.service duck-cam.service
sleep 12
systemctl is-active duck-imu.service duck-pwrlog.service duck-cam.service
journalctl -u duck-imu.service -n 3 --no-pager | tail -2
tail -1 ~/duck/pwrlog.txt
