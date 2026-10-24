#include <Arduino.h>
// MicroDuck touch readout on the Seeed XIAO ESP32-S3 (D-013, ../../PLAN.md).
// Reads the five copper pads with the ESP32-S3 touch peripheral at 50 Hz and serves them two ways:
//   USB serial, 115200: one line per sample, "T,<ms>,<L1>,<R1>,<L2>,<R2>,<M>" (raw counts; on the S3 a touch raises them).
//   I2C slave 0x2A on D4 (SDA) / D5 (SCL): a 24-byte block, uint32 LE sequence number then the five uint32 LE counts.
// Pads: L1 D0 (GPIO1, T1), R1 D1 (GPIO2, T2), L2 D2 (GPIO3, T3), R2 D3 (GPIO4, T4), M D8 (GPIO7, T7).
// The I2C side is untested until the A7Z overlay for pins 29/31 exists.

#include <Wire.h>

static const uint8_t PAD_PINS[5] = {1, 2, 3, 4, 7};
static const uint8_t I2C_ADDR = 0x2A;
static const uint32_t PERIOD_MS = 20;

static volatile uint32_t block[6];   // seq, L1, R1, L2, R2, M

static void onRequest() {
  uint8_t out[24];
  noInterrupts();
  for (int i = 0; i < 6; i++) {
    uint32_t v = block[i];
    out[4 * i] = v & 0xFF;
    out[4 * i + 1] = (v >> 8) & 0xFF;
    out[4 * i + 2] = (v >> 16) & 0xFF;
    out[4 * i + 3] = (v >> 24) & 0xFF;
  }
  interrupts();
  Wire.write(out, sizeof(out));
}

void setup() {
  Serial.begin(115200);
  Wire.onRequest(onRequest);
  Wire.begin(I2C_ADDR, D4, D5, 100000);   // slave: address, SDA, SCL, clock; the core's slave init enables the internal pull-ups
}

void loop() {
  static uint32_t next = 0, seq = 0;
  uint32_t now = millis();
  if ((int32_t)(now - next) < 0) return;
  next = now + PERIOD_MS;

  uint32_t v[5];
  for (int i = 0; i < 5; i++) v[i] = touchRead(PAD_PINS[i]);

  noInterrupts();
  block[0] = ++seq;
  for (int i = 0; i < 5; i++) block[i + 1] = v[i];
  interrupts();

  Serial.printf("T,%lu,%lu,%lu,%lu,%lu,%lu\n", (unsigned long)now, (unsigned long)v[0], (unsigned long)v[1],
                (unsigned long)v[2], (unsigned long)v[3], (unsigned long)v[4]);
}
