"""Read the BNO085 and print roll/pitch/yaw.

Usage on the Pi:   python3 imu_read.py [seconds]        (software I2C bus 3: GPIO4 SDA pin 7, GPIO27 SCL pin 13)
Usage on the A7Z:  python3 imu_read.py [seconds] 7      (TWI7 hardware I2C on pins 3 and 5, rsetup "Enable TWI7")
Needs: pip install adafruit-circuitpython-bno08x adafruit-extended-bus; on the Pi, the i2c-gpio overlay in config.txt.
"""
import math
import sys
import time

from adafruit_bno08x import BNO_REPORT_ACCELEROMETER, BNO_REPORT_ROTATION_VECTOR
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_extended_bus import ExtendedI2C

bno = BNO08X_I2C(ExtendedI2C(int(sys.argv[2]) if len(sys.argv) > 2 else 3), address=0x4A)
bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
bno.enable_feature(BNO_REPORT_ACCELEROMETER)
end = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 10)
while time.time() < end:
    i, j, k, r = bno.quaternion
    ax, ay, az = bno.acceleration
    roll = math.degrees(math.atan2(2 * (r * i + j * k), 1 - 2 * (i * i + j * j)))
    pitch = math.degrees(math.asin(max(-1, min(1, 2 * (r * j - k * i)))))
    yaw = math.degrees(math.atan2(2 * (r * k + i * j), 1 - 2 * (j * j + k * k)))
    print(f"roll {roll:7.1f}  pitch {pitch:7.1f}  yaw {yaw:7.1f}   acc {ax:5.2f} {ay:5.2f} {az:5.2f} m/s2", flush=True)
    time.sleep(0.5)
