import os, subprocess, time
f = open(os.path.expanduser("~/duck/pwrlog.txt"), "a")
last = None
f.write(f"{time.time():.2f} start\n"); f.flush(); os.fsync(f.fileno())
while True:
    v = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True).stdout.strip()
    t = time.time()
    if v != last or int(t) % 5 == 0 and int(t * 10) % 10 == 0:
        f.write(f"{t:.2f} {v}\n"); f.flush(); os.fsync(f.fileno())
        last = v
    time.sleep(0.1)
