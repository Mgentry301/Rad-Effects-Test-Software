/*
  ADP5055 PMBus bridge for Linduino (DC2026) / Arduino Uno
  ========================================================

  Tiny serial protocol over USB-CDC @ 115200 baud, line-oriented (\n):

      P                      -> "ADP5055-LINDUINO v1\n"
      A <hex_addr>           -> set 7-bit I2C address (e.g. "A 70"); resp "OK\n"
      R <hex_cmd>            -> read 1 byte from PMBus register cmd; resp "<hex>\n" or "ERR <n>\n"
      W <hex_cmd> <hex_val>  -> write 1 byte to PMBus register cmd; resp "OK\n" or "ERR <n>\n"
      S                      -> scan I2C bus; resp "<hex> <hex> ...\n" of responders

  PMBus read transaction:
      START + (addr<<1|W) + cmd + REPEATED-START + (addr<<1|R) + read + NACK + STOP

  Wiring (Linduino DC2026 / Uno):
      SDA = A4   ->  ADP5055 SDA test point on EVALZ
      SCL = A5   ->  ADP5055 SCL test point on EVALZ
      GND        ->  ADP5055 GND test point on EVALZ
      DO NOT connect VCC.
*/

#include <Wire.h>

static uint8_t g_addr = 0x70;
static char    g_buf[64];
static uint8_t g_len = 0;

static int hex_nibble(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return 10 + c - 'a';
  if (c >= 'A' && c <= 'F') return 10 + c - 'A';
  return -1;
}

static bool parse_hex(const char *p, uint16_t *out) {
  uint16_t v = 0;
  bool any = false;
  while (*p == ' ') p++;
  while (*p && *p != ' ' && *p != '\n' && *p != '\r') {
    int n = hex_nibble(*p++);
    if (n < 0) return false;
    v = (v << 4) | (uint16_t)n;
    any = true;
  }
  *out = v;
  return any;
}

static void print_hex_byte(uint8_t v) {
  static const char hex[] = "0123456789ABCDEF";
  Serial.print(hex[(v >> 4) & 0xF]);
  Serial.print(hex[v & 0xF]);
}

static void handle_read(const char *args) {
  uint16_t cmd;
  if (!parse_hex(args, &cmd) || cmd > 0xFF) { Serial.println(F("ERR 1")); return; }
  Wire.beginTransmission(g_addr);
  Wire.write((uint8_t)cmd);
  uint8_t err = Wire.endTransmission(false); // repeated start
  if (err) { Serial.print(F("ERR ")); Serial.println(err + 10); return; }
  uint8_t n = Wire.requestFrom((uint8_t)g_addr, (uint8_t)1, (uint8_t)true);
  if (n != 1) { Serial.println(F("ERR 20")); return; }
  uint8_t v = Wire.read();
  print_hex_byte(v);
  Serial.println();
}

static void handle_write(const char *args) {
  uint16_t cmd, val;
  const char *p = args;
  while (*p == ' ') p++;
  if (!parse_hex(p, &cmd) || cmd > 0xFF) { Serial.println(F("ERR 1")); return; }
  while (*p && *p != ' ') p++;
  if (!parse_hex(p, &val) || val > 0xFF) { Serial.println(F("ERR 2")); return; }
  Wire.beginTransmission(g_addr);
  Wire.write((uint8_t)cmd);
  Wire.write((uint8_t)val);
  uint8_t err = Wire.endTransmission(true);
  if (err) { Serial.print(F("ERR ")); Serial.println(err + 10); return; }
  Serial.println(F("OK"));
}

static void handle_addr(const char *args) {
  uint16_t a;
  if (!parse_hex(args, &a) || a > 0x7F) { Serial.println(F("ERR 1")); return; }
  g_addr = (uint8_t)a;
  Serial.println(F("OK"));
}

static void handle_scan() {
  for (uint8_t a = 0x08; a < 0x78; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      print_hex_byte(a);
      Serial.print(' ');
    }
  }
  Serial.println();
}

static void process_line(char *line) {
  while (*line == ' ') line++;
  char c = *line;
  switch (c) {
    case 'P': case 'p':
      Serial.println(F("ADP5055-LINDUINO v1"));
      break;
    case 'A': case 'a': handle_addr(line + 1); break;
    case 'R': case 'r': handle_read(line + 1); break;
    case 'W': case 'w': handle_write(line + 1); break;
    case 'S': case 's': handle_scan(); break;
    case 0: case '\r': case '\n': break;
    default: Serial.println(F("ERR 99"));
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(100000); // 100 kHz is safe; raise to 400000 if signal integrity allows
  Serial.println("ADP5055-LINDUINO v1 ready");
  delay(100);
  Serial.println(F("ADP5055-LINDUINO v1 ready"));
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (g_len > 0) {
        g_buf[g_len] = 0;
        process_line(g_buf);
        g_len = 0;
      }
    } else if (g_len < sizeof(g_buf) - 1) {
      g_buf[g_len++] = c;
    } else {
      g_len = 0; // overflow, discard
      Serial.println(F("ERR 98"));
    }
  }
}
