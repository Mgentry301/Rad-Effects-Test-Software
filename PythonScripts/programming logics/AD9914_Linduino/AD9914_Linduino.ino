/*
 * AD9914_Linduino.ino
 *
 * Linduino DC2026 firmware for AD9914 register access via USB-serial.
 *
 * Wiring (Linduino -> EVB P101C, 3.3 V buffered side):
 *   D13 SCK   ->  P101C 39  (SCLK)
 *   D11 MOSI  ->  P101C 38  (SDIO)
 *   D12 MISO  <-  P101C 37  (SDO)
 *   D10 CS    ->  P101C 40  (CSB)
 *   D7        ->  MASTER_RESET pin   (P102 pin 3)  -- active high, default LOW
 *   D8        ->  EXT_PWR_DWN  pin   (P102 pin 1)  -- active high, default LOW
 *   D9        ->  IO_UPDATE    pin                 -- rising edge latches
 *   D6        ->  SYNC_IO      pin                 -- high pulse resets SPI
 *                                                     state machine without
 *                                                     touching register contents
 *   GND       ->  EVB GND  (any P101A GND)
 *
 * Set Linduino JP3 to 3.3 V to match P101C buffered I/O.
 * EVB jumpers: P203/P204/P205 = Disable (release on-board Cypress).
 *              P202 = Enable (per datasheet external mode).
 *              IOCFG = 1000 (parallel-port hardwired).
 *
 * Serial protocol (115200 8N1, line-terminated by '\n'):
 *   ID                  -> "AD9914-LINDUINO v1"
 *   RESET               -> pulse MASTER_RESET high 10 ms then low, "OK"
 *   PWRDN 0|1           -> set EXT_PWR_DWN level, "OK"
 *   IOU                 -> pulse IO_UPDATE high ~2 us, "OK"
 *   SYNCIO              -> pulse SYNC_IO high ~2 us (resets SPI engine,
 *                          preserves register contents), "OK"
 *   INIT                -> full boot: pwrdn=0, master reset,
 *                          CFR1 <- SDIO_INPUT_ONLY, IO_UPDATE, verify.
 *                          "OK" if CFR1 read-back matches, else "ERR ..."
 *   W AA DDDDDDDD       -> write 32-bit hex DDDDDDDD to addr AA (hex), "OK"
 *   R AA                -> read 32-bit reg AA, returns "DDDDDDDD" (hex)
 *   BITRATE N           -> set SPI clock divisor (Arduino SPI divider:
 *                          2,4,8,16,32,64,128 -> 8/4/2/1/0.5/0.25/0.125 MHz
 *                          on a 16 MHz Uno), "OK"
 *   anything else       -> "ERR cmd"
 */

#include <SPI.h>

static const uint8_t PIN_CS       = 10;
static const uint8_t PIN_RESET    = 7;
static const uint8_t PIN_PWRDN    = 8;
static const uint8_t PIN_IOUPDATE = 9;
static const uint8_t PIN_SYNCIO   = 6;

static const uint8_t  READ_BIT  = 0x80;
static const uint8_t  ADDR_MASK = 0x7F;
static const uint8_t  CFR1_ADDR = 0x00;
static const uint32_t CFR1_SDIO_INPUT_ONLY = 0x00000002UL;

// 1 MHz default. Plenty for register polling, generous timing margin for
// the buffered EVB header and breadboard jumpers.
static SPISettings spiSettings(1000000, MSBFIRST, SPI_MODE0);

static void spiWriteReg(uint8_t addr, uint32_t value) {
  uint8_t instr = addr & ADDR_MASK;  // R/!W = 0 for write
  SPI.beginTransaction(spiSettings);
  digitalWrite(PIN_CS, LOW);
  SPI.transfer(instr);
  SPI.transfer((value >> 24) & 0xFF);
  SPI.transfer((value >> 16) & 0xFF);
  SPI.transfer((value >>  8) & 0xFF);
  SPI.transfer( value        & 0xFF);
  digitalWrite(PIN_CS, HIGH);
  SPI.endTransaction();
}

static uint32_t spiReadReg(uint8_t addr) {
  uint8_t instr = READ_BIT | (addr & ADDR_MASK);
  uint32_t val = 0;
  SPI.beginTransaction(spiSettings);
  digitalWrite(PIN_CS, LOW);
  SPI.transfer(instr);
  val |= ((uint32_t)SPI.transfer(0)) << 24;
  val |= ((uint32_t)SPI.transfer(0)) << 16;
  val |= ((uint32_t)SPI.transfer(0)) <<  8;
  val |= ((uint32_t)SPI.transfer(0));
  digitalWrite(PIN_CS, HIGH);
  SPI.endTransaction();
  return val;
}

static void pulseIOUpdate() {
  digitalWrite(PIN_IOUPDATE, HIGH);
  delayMicroseconds(2);
  digitalWrite(PIN_IOUPDATE, LOW);
}

static void pulseSyncIO() {
  // Resets the AD9914 serial port state machine without clearing
  // register contents. Useful when SPI gets out of sync (e.g. after a
  // glitched CSB or partial transaction).
  digitalWrite(PIN_SYNCIO, HIGH);
  delayMicroseconds(2);
  digitalWrite(PIN_SYNCIO, LOW);
}

static void doMasterReset() {
  digitalWrite(PIN_RESET, HIGH);
  delay(10);
  digitalWrite(PIN_RESET, LOW);
  delay(10);
}

static bool doInit() {
  digitalWrite(PIN_PWRDN, LOW);
  delay(5);
  doMasterReset();
  // Make sure the SPI engine is in a known state before we touch CFR1.
  pulseSyncIO();
  // Switch to 4-wire SPI mode (SDO driven, SDIO input only).
  spiWriteReg(CFR1_ADDR, CFR1_SDIO_INPUT_ONLY);
  pulseIOUpdate();
  delay(2);
  uint32_t got = spiReadReg(CFR1_ADDR);
  return got != 0xFFFFFFFFUL
      && got != 0
      && (got & CFR1_SDIO_INPUT_ONLY) == CFR1_SDIO_INPUT_ONLY;
}

static bool parseHex(const char *s, uint32_t &out) {
  if (!s || !*s) return false;
  uint32_t v = 0;
  while (*s) {
    char c = *s++;
    uint8_t d;
    if      (c >= '0' && c <= '9') d = c - '0';
    else if (c >= 'a' && c <= 'f') d = 10 + (c - 'a');
    else if (c >= 'A' && c <= 'F') d = 10 + (c - 'A');
    else return false;
    v = (v << 4) | d;
  }
  out = v;
  return true;
}

static void handleLine(char *line) {
  while (*line == ' ') line++;
  if (!*line) return;
  char *arg = strchr(line, ' ');
  if (arg) { *arg = 0; arg++; while (*arg == ' ') arg++; }

  if (!strcmp(line, "ID")) {
    Serial.println(F("AD9914-LINDUINO v1"));
    return;
  }
  if (!strcmp(line, "RESET")) {
    doMasterReset();
    Serial.println(F("OK"));
    return;
  }
  if (!strcmp(line, "IOU")) {
    pulseIOUpdate();
    Serial.println(F("OK"));
    return;
  }
  if (!strcmp(line, "SYNCIO")) {
    pulseSyncIO();
    Serial.println(F("OK"));
    return;
  }
  if (!strcmp(line, "INIT")) {
    Serial.println(doInit() ? F("OK") : F("ERR init-readback"));
    return;
  }
  if (!strcmp(line, "PWRDN")) {
    if (!arg) { Serial.println(F("ERR pwrdn-arg")); return; }
    digitalWrite(PIN_PWRDN, (arg[0] != '0') ? HIGH : LOW);
    Serial.println(F("OK"));
    return;
  }
  if (!strcmp(line, "BITRATE")) {
    if (!arg) { Serial.println(F("ERR br-arg")); return; }
    uint32_t hz;
    if (!parseHex(arg, hz) && (hz = atol(arg)) == 0) {
      Serial.println(F("ERR br-num"));
      return;
    }
    spiSettings = SPISettings(hz, MSBFIRST, SPI_MODE0);
    Serial.println(F("OK"));
    return;
  }
  if (!strcmp(line, "W")) {
    if (!arg) { Serial.println(F("ERR w-args")); return; }
    char *v = strchr(arg, ' ');
    if (!v) { Serial.println(F("ERR w-args")); return; }
    *v = 0; v++;
    uint32_t a, d;
    if (!parseHex(arg, a) || !parseHex(v, d)) {
      Serial.println(F("ERR w-hex"));
      return;
    }
    spiWriteReg((uint8_t)(a & 0x7F), d);
    Serial.println(F("OK"));
    return;
  }
  if (!strcmp(line, "R")) {
    if (!arg) { Serial.println(F("ERR r-args")); return; }
    uint32_t a;
    if (!parseHex(arg, a)) { Serial.println(F("ERR r-hex")); return; }
    uint32_t d = spiReadReg((uint8_t)(a & 0x7F));
    char tmp[12];
    snprintf(tmp, sizeof(tmp), "%08lX", (unsigned long)d);
    Serial.println(tmp);
    return;
  }
  Serial.println(F("ERR cmd"));
}

void setup() {
  pinMode(PIN_CS,        OUTPUT); digitalWrite(PIN_CS,        HIGH);
  pinMode(PIN_RESET,     OUTPUT); digitalWrite(PIN_RESET,     LOW);
  pinMode(PIN_PWRDN,     OUTPUT); digitalWrite(PIN_PWRDN,     LOW);
  pinMode(PIN_IOUPDATE,  OUTPUT); digitalWrite(PIN_IOUPDATE,  LOW);
  pinMode(PIN_SYNCIO,    OUTPUT); digitalWrite(PIN_SYNCIO,    LOW);

  SPI.begin();
  Serial.begin(115200);
  Serial.setTimeout(50);
}

void loop() {
  static char buf[80];
  static uint8_t blen = 0;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n' || blen >= sizeof(buf) - 1) {
      buf[blen] = 0;
      handleLine(buf);
      blen = 0;
    } else {
      buf[blen++] = c;
    }
  }
}
