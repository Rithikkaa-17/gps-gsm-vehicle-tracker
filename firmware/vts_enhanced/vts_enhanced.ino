/*
 * vts_enhanced.ino  --  Reference firmware for the PROPOSED enhanced node
 * Target : Arduino Mega 2560 (ATmega2560), NEO-6M on Serial2, SIM900A on Serial1,
 *          optional MPU-6050 on I2C (D20/D21), SOS push-button on D3 (to GND).
 *
 * STATUS : Compiles for atmega2560. NOT yet tested on hardware. Every threshold
 *          marked [CAL] is a placeholder that must be calibrated experimentally
 *          (see paper Sec. VII) before any performance claim is made.
 *
 * Wiring (proposed, Fig. 2b):
 *   NEO-6M TX  -> D17 (RX2)          NEO-6M RX <- D16 (TX2) via 1k/2k divider
 *   SIM900A TXD-> D19 (RX1)          SIM900A RXD <- D18 (TX1)   [VERIFY TTL level]
 *   MPU-6050 SDA/SCL -> D20/D21      SOS button D3 -> GND (INPUT_PULLUP)
 *   SIM900A VCC from a separate 5 V / >=2 A supply; common ground.
 *
 * SMS commands (from whitelisted numbers only, case-insensitive):
 *   GET LOCATION | STATUS | TRACK ON | TRACK OFF | ARM | DISARM | FENCE <radius_m>
 *
 * Debug/measurement log on USB Serial (115200 bit/s), one CSV record per event:
 *   EVT,<millis>,<tag>,<detail>   -- tags used for latency decomposition (Eq. 9):
 *   CMTI (t1), FIXOK (t2), CMGS_TX (t3), CMGS_OK (t4), CMGS_FAIL, FIXREJ, ...
 */

#include <Wire.h>
#include <EEPROM.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

// ----------------------------------------------------------------- configuration
#define GPS_PORT   Serial2
#define GSM_PORT   Serial1
#define DBG        Serial

static const char *AUTH_NUMBERS[] = { "+91XXXXXXXXXX" };   // [EDIT] authorised handset(s)
static const uint8_t N_AUTH = sizeof(AUTH_NUMBERS) / sizeof(AUTH_NUMBERS[0]);

// Fix validation (Eq. 4)
static const uint8_t  MIN_SATS        = 4;
static const uint16_t HDOP_MAX_x100   = 300;     // HDOP <= 3.00          [CAL]
static const float    V_MAX_MPS       = 45.0f;   // plausibility gate     [CAL]
static const uint32_t FIX_STALE_MS    = 5000;    // fix older -> stale

// Adaptive reporting (Eq. 7)
static const float    D_TH_M          = 200.0f;  // displacement trigger  [CAL]
static const float    PSI_TH_DEG      = 30.0f;   // course-change trigger [CAL]
static const float    V_MIN_MPS       = 2.8f;    // ~10 km/h, course valid
static const uint32_t T_MIN_MS        = 30000UL; // min spacing of reports
static const uint32_t T_MAX_MS        = 600000UL;// heartbeat (10 min)

// Geofence (Eq. 5)
static const float    FENCE_HYST_M    = 15.0f;   // hysteresis h          [CAL]
static const uint8_t  FENCE_N_CONSEC  = 3;       // consecutive fixes
static const float    ARM_RADIUS_M    = 50.0f;   // radius used by ARM    [CAL]

// Impact detection (Eq. 6)
static const float    A_TH_G          = 4.0f;    // |a| threshold         [CAL]
static const uint32_t IMPACT_CONFIRM_MS = 10000; // post-event window
static const float    V_STOP_MPS      = 1.5f;    // "stopped" after impact
static const uint32_t IMU_PERIOD_MS   = 10;      // 100 Hz polling

// SMS transmission
static const uint32_t CMGS_TIMEOUT_MS = 60000UL; // T_ack
static const uint8_t  N_RETRY         = 3;
static const uint32_t BACKOFF_MS[N_RETRY] = { 5000UL, 10000UL, 20000UL };

// SOS button
static const uint8_t  PIN_SOS         = 3;
static const uint32_t SOS_HOLD_MS     = 2000;

// ----------------------------------------------------------------- data types
struct Fix {                 // coordinates as int32 in 1e-7 degrees: an AVR "double"
  int32_t lat_e7, lon_e7;    // is only 32 bits, so float would lose ~1 m resolution
  float   speed_mps, course_deg;
  uint16_t hdop_x100;
  uint8_t  sats, quality;
  uint32_t utc_hhmmss;
  uint32_t t_ms;             // millis() when accepted
  bool     valid;
};

enum EventType : uint8_t { EV_NONE = 0, EV_REQUEST, EV_PERIODIC, EV_FENCE, EV_IMPACT, EV_SOS, EV_STATUS };

struct PendingMsg { uint8_t type; int32_t lat_e7, lon_e7; uint32_t utc; };

struct Config {
  uint16_t magic;            // 0x5654 'VT'
  uint8_t  version;
  uint8_t  tracking;         // adaptive reporting enabled
  uint8_t  fence_on;
  int32_t  fc_lat_e7, fc_lon_e7;
  float    fence_r_m;
};

// EEPROM layout: [0..31] config | [32..] queue (8 x 13 B) | [160..] history ring (64 x 12 B)
static const int EE_CFG = 0, EE_Q = 32, EE_HIST = 160;
static const uint8_t Q_LEN = 8, H_LEN = 64;

// ----------------------------------------------------------------- state
static Fix      g_fix = {0}, g_lastReported = {0};
static uint32_t g_lastReportMs = 0;
static Config   g_cfg;
static uint8_t  g_fenceOutsideCnt = 0, g_fenceInsideCnt = 0;
static bool     g_fenceOutside = false;
static bool     g_imuOk = false;
static uint32_t g_impactMs = 0;      // 0 = no pending impact
static uint32_t g_lastImuMs = 0;
static uint32_t g_sosDownMs = 0;
static bool     g_sosLatched = false;
static uint8_t  g_histIdx = 0;
static uint32_t g_rejected = 0, g_accepted = 0;

// pending GGA fields (merged with RMC of the same epoch)
static uint8_t  gga_quality = 0, gga_sats = 0;
static uint16_t gga_hdop_x100 = 9999;

// ================================================================= utilities
static void logEvt(const char *tag, const char *detail) {
  DBG.print(F("EVT,")); DBG.print(millis()); DBG.print(','); DBG.print(tag);
  DBG.print(','); DBG.println(detail ? detail : "");
}

static const float R_EARTH = 6371008.8f;    // mean Earth radius (m)
static const float DEG2RAD = 0.017453292519943f;

// Equirectangular distance from integer deltas (adequate below ~10 km; Eq. 3).
// Offline evaluation uses the haversine form (Eq. 2) in double precision.
static float distM(int32_t lat1, int32_t lon1, int32_t lat2, int32_t lon2) {
  float phi_m = ((float)lat1 + (float)lat2) * 0.5e-7f * DEG2RAD;
  float dy = (float)(lat2 - lat1) * 1e-7f * DEG2RAD * R_EARTH;
  float dx = (float)(lon2 - lon1) * 1e-7f * DEG2RAD * R_EARTH * cosf(phi_m);
  return sqrtf(dx * dx + dy * dy);
}

static float angDiff(float a, float b) {          // smallest |a-b| in degrees
  float d = fabsf(a - b);
  while (d > 360.0f) d -= 360.0f;
  return d > 180.0f ? 360.0f - d : d;
}

static void fmtE7(char *out, int32_t v) {         // 13.2626512 style, 7 decimals
  if (v < 0) { *out++ = '-'; v = -v; }
  ltoa(v / 10000000L, out, 10);
  out += strlen(out);
  *out++ = '.';
  char frac[8]; ltoa(v % 10000000L, frac, 10);
  for (int i = strlen(frac); i < 7; i++) *out++ = '0';
  strcpy(out, frac);
}

// ================================================================= NMEA parsing
static char    nmea[96];
static uint8_t nmeaLen = 0;

static int hexVal(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  c = toupper(c);
  return (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
}

// XOR checksum between '$' and '*' must equal the two hex digits after '*'.
static bool nmeaChecksumOk(const char *s) {
  if (s[0] != '$') return false;
  uint8_t cs = 0; const char *p = s + 1;
  while (*p && *p != '*') cs ^= (uint8_t)*p++;
  if (*p != '*') return false;
  int h = hexVal(p[1]), l = hexVal(p[2]);
  return h >= 0 && l >= 0 && cs == (uint8_t)((h << 4) | l);
}

// Split in place on ',' (and '*'); returns number of fields.
static uint8_t splitFields(char *s, char **f, uint8_t maxf) {
  uint8_t n = 0; f[n++] = s;
  for (char *p = s; *p && n < maxf; p++) {
    if (*p == ',' || *p == '*') { *p = 0; f[n++] = p + 1; }
  }
  return n;
}

// ddmm.mmmmm / dddmm.mmmmm + hemisphere -> 1e-7 deg, integer arithmetic (Eq. 1)
static bool nmeaToE7(const char *v, const char *hemi, bool isLon, int32_t *out) {
  if (!v || !*v || !hemi || !*hemi) return false;
  const char *dot = strchr(v, '.');
  int degDigits = isLon ? 3 : 2;
  if (!dot || (dot - v) != degDigits + 2) return false;
  int32_t deg = 0;
  for (int i = 0; i < degDigits; i++) { if (!isdigit(v[i])) return false; deg = deg * 10 + (v[i] - '0'); }
  // minutes scaled by 1e5 (5 decimals; NEO-6M outputs 5)
  int32_t minE5 = (int32_t)(v[degDigits] - '0') * 10 + (v[degDigits + 1] - '0');
  minE5 *= 100000L;
  int32_t frac = 0, scale = 10000L;
  for (const char *p = dot + 1; *p && isdigit(*p) && scale > 0; p++, scale /= 10) frac += (int32_t)(*p - '0') * scale;
  minE5 += frac;
  if (minE5 >= 6000000L) return false;
  int32_t e7 = deg * 10000000L + (minE5 * 100L + 30L) / 60L;   // (min*1e5)*100/60 = deg*1e7, rounded
  if (hemi[0] == 'S' || hemi[0] == 'W') e7 = -e7;
  else if (hemi[0] != 'N' && hemi[0] != 'E') return false;
  if ((!isLon && labs(e7) > 900000000L) || (isLon && labs(e7) > 1800000000L)) return false;
  *out = e7;
  return true;
}

static void handleGGA(char **f, uint8_t n) {
  if (n < 9) return;
  gga_quality = (uint8_t)atoi(f[6]);
  gga_sats    = (uint8_t)atoi(f[7]);
  gga_hdop_x100 = f[8][0] ? (uint16_t)(atof(f[8]) * 100.0f + 0.5f) : 9999;
}

// Candidate fix from RMC (+ latest GGA quality); accepted only if Eq. (4) holds.
static void handleRMC(char **f, uint8_t n) {
  if (n < 10) return;
  Fix c = {0};
  bool ok = (f[2][0] == 'A');
  ok = ok && nmeaToE7(f[3], f[4], false, &c.lat_e7) && nmeaToE7(f[5], f[6], true, &c.lon_e7);
  c.speed_mps  = f[7][0] ? atof(f[7]) * 0.514444f : 0.0f;   // knots -> m/s
  c.course_deg = f[8][0] ? atof(f[8]) : 0.0f;
  c.utc_hhmmss = (uint32_t)atol(f[1]);
  c.quality = gga_quality; c.sats = gga_sats; c.hdop_x100 = gga_hdop_x100;
  c.t_ms = millis();

  const char *why = NULL;
  if (!ok)                               why = "status_or_format";
  else if (c.quality < 1)                why = "gga_quality";
  else if (c.sats < MIN_SATS)            why = "sats";
  else if (c.hdop_x100 > HDOP_MAX_x100)  why = "hdop";
  else if (g_fix.valid) {                // kinematic plausibility gate
    float dt = (c.t_ms - g_fix.t_ms) * 1e-3f;
    if (dt > 0.2f && distM(g_fix.lat_e7, g_fix.lon_e7, c.lat_e7, c.lon_e7) / dt > V_MAX_MPS) why = "speed_gate";
  }
  if (why) { g_rejected++; logEvt("FIXREJ", why); return; }
  c.valid = true;
  g_fix = c;
  g_accepted++;
  if (g_accepted == 1) logEvt("TTFF", "first_valid_fix");    // TTFF = this ms - BOOT ms
}

static void processSentence(char *s) {
  if (!nmeaChecksumOk(s)) { g_rejected++; logEvt("FIXREJ", "checksum"); return; }
  char *f[20];
  uint8_t n = splitFields(s, f, 20);
  const char *id = f[0] + 3;            // skip "$GP"/"$GN" talker
  if (strncmp(id, "GGA", 3) == 0) handleGGA(f, n);
  else if (strncmp(id, "RMC", 3) == 0) handleRMC(f, n);
}

static void gpsPoll() {                 // non-blocking: consume what is buffered
  while (GPS_PORT.available()) {
    char ch = (char)GPS_PORT.read();
    if (ch == '$') nmeaLen = 0;
    if (ch == '\r' || ch == '\n') {
      if (nmeaLen > 6) { nmea[nmeaLen] = 0; processSentence(nmea); }
      nmeaLen = 0;
    } else if (nmeaLen < sizeof(nmea) - 1) {
      nmea[nmeaLen++] = ch;
    } else {
      nmeaLen = 0;                      // overlong sentence -> discard
    }
  }
}

static bool fixFresh() { return g_fix.valid && (millis() - g_fix.t_ms) <= FIX_STALE_MS; }

// ================================================================= GSM link layer
static char gsmLine[128];
static uint8_t gsmLen = 0;
static void handleUrc(const char *line);

// Background services that must keep running while we wait on the modem.
static void serviceWhileWaiting() { gpsPoll(); }

// Read one line from the modem (non-blocking). Returns true when a line is ready.
static bool gsmReadLine() {
  while (GSM_PORT.available()) {
    char ch = (char)GSM_PORT.read();
    if (ch == '>' && gsmLen == 0) { gsmLine[0] = '>'; gsmLine[1] = 0; return true; }  // CMGS prompt has no EOL
    if (ch == '\n') { gsmLine[gsmLen] = 0; gsmLen = 0; if (gsmLine[0]) return true; }
    else if (ch != '\r' && gsmLen < sizeof(gsmLine) - 1) gsmLine[gsmLen++] = ch;
  }
  return false;
}

// Send an AT command and wait for `expect` (or ERROR) within timeout.
static bool atCmd(const char *cmd, const char *expect, uint32_t timeout_ms) {
  if (cmd) { GSM_PORT.print(cmd); GSM_PORT.print("\r"); }
  uint32_t t0 = millis();
  while (millis() - t0 < timeout_ms) {
    serviceWhileWaiting();
    if (gsmReadLine()) {
      if (strstr(gsmLine, expect)) return true;
      if (strstr(gsmLine, "ERROR")) return false;
      if (strncmp(gsmLine, "+CMTI", 5) == 0) handleUrc(gsmLine);   // keep URCs
    }
  }
  return false;
}

static bool gsmInit() {
  for (uint8_t i = 0; i < 10; i++) { if (atCmd("AT", "OK", 1000)) break; if (i == 9) return false; }
  atCmd("ATE0", "OK", 1000);                  // echo off
  atCmd("AT+CMGF=1", "OK", 2000);             // SMS text mode
  atCmd("AT+CNMI=2,1,0,0,0", "OK", 2000);     // URC +CMTI on new SMS
  atCmd("AT+CPMS=\"SM\",\"SM\",\"SM\"", "OK", 3000);
  uint32_t t0 = millis();
  while (millis() - t0 < 60000UL) {           // wait for network registration
    GSM_PORT.print("AT+CREG?\r");
    uint32_t t1 = millis();
    while (millis() - t1 < 1500) {
      serviceWhileWaiting();
      if (gsmReadLine() && strncmp(gsmLine, "+CREG:", 6) == 0) {
        char *c = strchr(gsmLine, ',');
        if (c && (c[1] == '1' || c[1] == '5')) { logEvt("CREG", "registered"); return true; }
      }
    }
  }
  logEvt("CREG", "timeout");
  return false;
}

static int gsmSignalCsq() {                     // 0..31, 99 = unknown
  GSM_PORT.print("AT+CSQ\r");
  uint32_t t0 = millis();
  while (millis() - t0 < 2000) {
    serviceWhileWaiting();
    if (gsmReadLine() && strncmp(gsmLine, "+CSQ:", 5) == 0) return atoi(gsmLine + 6);
  }
  return 99;
}

// One SMS attempt: AT+CMGS -> '>' -> body + Ctrl-Z -> '+CMGS:' within T_ack.
static bool smsSendOnce(const char *num, const char *body) {
  char cmd[40];
  snprintf(cmd, sizeof(cmd), "AT+CMGS=\"%s\"", num);
  logEvt("CMGS_TX", num);                                    // t3
  if (!atCmd(cmd, ">", 5000)) { logEvt("CMGS_FAIL", "no_prompt"); return false; }
  GSM_PORT.print(body);
  GSM_PORT.write(0x1A);
  if (atCmd(NULL, "+CMGS:", CMGS_TIMEOUT_MS)) { logEvt("CMGS_OK", gsmLine); return true; }  // t4
  logEvt("CMGS_FAIL", "timeout_or_error");
  return false;
}

// ================================================================= EEPROM store
static void cfgDefaults() {
  memset(&g_cfg, 0, sizeof(g_cfg));
  g_cfg.magic = 0x5654; g_cfg.version = 1; g_cfg.fence_r_m = ARM_RADIUS_M;
}
static void cfgLoad() { EEPROM.get(EE_CFG, g_cfg); if (g_cfg.magic != 0x5654 || g_cfg.version != 1) cfgDefaults(); }
static void cfgSave() { EEPROM.put(EE_CFG, g_cfg); }

static void queuePush(const PendingMsg &m) {
  for (uint8_t i = 0; i < Q_LEN; i++) {
    PendingMsg q; EEPROM.get(EE_Q + i * sizeof(PendingMsg), q);
    if (q.type == EV_NONE || q.type == 0xFF) { EEPROM.put(EE_Q + i * sizeof(PendingMsg), m); logEvt("QUEUE", "push"); return; }
  }
  logEvt("QUEUE", "full_drop");
}

static void histPush(const Fix &f) {
  struct { int32_t a, b; uint32_t t; } h = { f.lat_e7, f.lon_e7, f.utc_hhmmss };
  EEPROM.put(EE_HIST + (g_histIdx % H_LEN) * 12, h);   // EEPROM.put skips unchanged bytes
  g_histIdx++;
}

// ================================================================= messaging
static const char *evName(uint8_t t) {
  switch (t) {
    case EV_REQUEST: return "LOC"; case EV_PERIODIC: return "TRK"; case EV_FENCE: return "FENCE";
    case EV_IMPACT: return "IMPACT"; case EV_SOS: return "SOS"; case EV_STATUS: return "STATUS";
    default: return "?";
  }
}

// Body: event tag, decimal-degree coordinates, fix age, map link (fits one 160-char SMS).
static void composeBody(char *out, size_t n, uint8_t type, const Fix &f) {
  if (!f.valid) { snprintf(out, n, "%s: NO VALID GPS FIX", evName(type)); return; }
  char la[16], lo[16];
  fmtE7(la, f.lat_e7); fmtE7(lo, f.lon_e7);
  // keep 5 decimals (~1.1 m) in the link to stay within one SMS segment
  la[strlen(la) - 2] = 0; lo[strlen(lo) - 2] = 0;
  unsigned long age = (millis() - f.t_ms) / 1000UL;
  snprintf(out, n, "%s %s,%s age=%lus hdop=%u.%02u sat=%u\nhttps://maps.google.com/?q=%s,%s",
           evName(type), la, lo, age, f.hdop_x100 / 100, f.hdop_x100 % 100, f.sats, la, lo);
}

// Retry-aware transmission (Fig. 3): N attempts with back-off, then EEPROM queue.
static bool reportEvent(uint8_t type, const char *num) {
  char body[161];
  composeBody(body, sizeof(body), type, g_fix);
  for (uint8_t a = 0; a < N_RETRY; a++) {
    if (smsSendOnce(num, body)) {
      if (g_fix.valid) { g_lastReported = g_fix; histPush(g_fix); }
      g_lastReportMs = millis();
      return true;
    }
    uint32_t t0 = millis();
    while (millis() - t0 < BACKOFF_MS[a]) serviceWhileWaiting();
    int csq = gsmSignalCsq();
    char d[12]; itoa(csq, d, 10); logEvt("CSQ", d);
  }
  PendingMsg m = { type, g_fix.lat_e7, g_fix.lon_e7, g_fix.utc_hhmmss };
  queuePush(m);
  return false;
}

static void notifyAll(uint8_t type) { for (uint8_t i = 0; i < N_AUTH; i++) reportEvent(type, AUTH_NUMBERS[i]); }

static void flushQueue() {
  for (uint8_t i = 0; i < Q_LEN; i++) {
    PendingMsg q; EEPROM.get(EE_Q + i * sizeof(PendingMsg), q);
    if (q.type == EV_NONE || q.type == 0xFF) continue;
    char body[161], la[16], lo[16];
    fmtE7(la, q.lat_e7); fmtE7(lo, q.lon_e7);
    snprintf(body, sizeof(body), "QUEUED %s %s,%s utc=%06lu", evName(q.type), la, lo, (unsigned long)q.utc);
    if (smsSendOnce(AUTH_NUMBERS[0], body)) { q.type = EV_NONE; EEPROM.put(EE_Q + i * sizeof(PendingMsg), q); }
    else return;                                 // link still bad; try later
  }
}

// ================================================================= incoming SMS
static bool isAuthorised(const char *num) {
  for (uint8_t i = 0; i < N_AUTH; i++) if (strcmp(num, AUTH_NUMBERS[i]) == 0) return true;
  return false;
}

static void handleCommand(const char *from, char *text) {
  for (char *p = text; *p; p++) *p = toupper(*p);
  while (*text == ' ') text++;
  if (strncmp(text, "GET LOCATION", 12) == 0)      reportEvent(EV_REQUEST, from);
  else if (strncmp(text, "STATUS", 6) == 0)        reportEvent(EV_STATUS, from);
  else if (strncmp(text, "TRACK ON", 8) == 0)      { g_cfg.tracking = 1; cfgSave(); reportEvent(EV_STATUS, from); }
  else if (strncmp(text, "TRACK OFF", 9) == 0)     { g_cfg.tracking = 0; cfgSave(); reportEvent(EV_STATUS, from); }
  else if (strncmp(text, "ARM", 3) == 0 || strncmp(text, "FENCE", 5) == 0) {
    if (!fixFresh()) { reportEvent(EV_STATUS, from); return; }   // replies "NO VALID GPS FIX"
    g_cfg.fence_on = 1; g_cfg.fc_lat_e7 = g_fix.lat_e7; g_cfg.fc_lon_e7 = g_fix.lon_e7;
    g_cfg.fence_r_m = (text[0] == 'F') ? (float)atoi(text + 5) : ARM_RADIUS_M;
    if (g_cfg.fence_r_m < 2.0f * FENCE_HYST_M) g_cfg.fence_r_m = 2.0f * FENCE_HYST_M;
    g_fenceOutside = false; g_fenceOutsideCnt = g_fenceInsideCnt = 0;
    cfgSave(); reportEvent(EV_STATUS, from);
  }
  else if (strncmp(text, "DISARM", 6) == 0)        { g_cfg.fence_on = 0; cfgSave(); reportEvent(EV_STATUS, from); }
  else logEvt("CMD", "unknown");
}

// "+CMTI: "SM",<idx>"  ->  AT+CMGR=<idx>  ->  header line + text line  ->  AT+CMGD
static bool g_inUrc = false;
static void handleUrc(const char *line) {
  if (g_inUrc) { logEvt("CMTI", "deferred"); return; }       // stays in SIM storage
  struct Guard { Guard() { g_inUrc = true; } ~Guard() { g_inUrc = false; } } guard;
  const char *c = strrchr(line, ',');
  if (!c) return;
  int idx = atoi(c + 1);
  logEvt("CMTI", c + 1);                                     // t1
  char cmd[16]; snprintf(cmd, sizeof(cmd), "AT+CMGR=%d", idx);
  GSM_PORT.print(cmd); GSM_PORT.print("\r");
  char from[24] = "", text[64] = "";
  bool haveHdr = false;
  uint32_t t0 = millis();
  while (millis() - t0 < 5000) {
    serviceWhileWaiting();
    if (!gsmReadLine()) continue;
    if (strncmp(gsmLine, "+CMGR:", 6) == 0) {                // +CMGR: "REC UNREAD","+91...",...
      char *q1 = strchr(gsmLine, ','); char *q2 = q1 ? strchr(q1 + 2, '"') : NULL;
      if (q1 && q2 && q1[1] == '"') { size_t L = q2 - (q1 + 2); if (L < sizeof(from)) { memcpy(from, q1 + 2, L); from[L] = 0; } }
      haveHdr = true;
    } else if (haveHdr && strcmp(gsmLine, "OK") != 0 && !text[0]) {
      strncpy(text, gsmLine, sizeof(text) - 1);
    } else if (strcmp(gsmLine, "OK") == 0) break;
  }
  snprintf(cmd, sizeof(cmd), "AT+CMGD=%d", idx);
  atCmd(cmd, "OK", 5000);
  if (!isAuthorised(from)) { logEvt("CMD", "unauthorised"); return; }
  handleCommand(from, text);
}

// ================================================================= detectors
static void geofenceCheck() {                                // Eq. (5)
  if (!g_cfg.fence_on || !fixFresh()) return;
  static uint32_t lastSeen = 0;
  if (g_fix.t_ms == lastSeen) return;                        // once per new fix
  lastSeen = g_fix.t_ms;
  float d = distM(g_cfg.fc_lat_e7, g_cfg.fc_lon_e7, g_fix.lat_e7, g_fix.lon_e7);
  if (!g_fenceOutside) {
    g_fenceOutsideCnt = (d > g_cfg.fence_r_m + FENCE_HYST_M) ? g_fenceOutsideCnt + 1 : 0;
    if (g_fenceOutsideCnt >= FENCE_N_CONSEC) { g_fenceOutside = true; logEvt("FENCE", "exit"); notifyAll(EV_FENCE); }
  } else {
    g_fenceInsideCnt = (d < g_cfg.fence_r_m - FENCE_HYST_M) ? g_fenceInsideCnt + 1 : 0;
    if (g_fenceInsideCnt >= FENCE_N_CONSEC) { g_fenceOutside = false; logEvt("FENCE", "reentry"); }
  }
}

static bool imuInit() {
  Wire.begin(); Wire.setClock(400000);
  Wire.beginTransmission(0x68); Wire.write(0x6B); Wire.write(0x00);   // PWR_MGMT_1: wake
  if (Wire.endTransmission() != 0) return false;
  Wire.beginTransmission(0x68); Wire.write(0x1C); Wire.write(0x18);   // ACCEL_CONFIG: +-16 g
  return Wire.endTransmission() == 0;
}

static bool imuReadG(float *amag) {                          // |a| in g (Eq. 6)
  Wire.beginTransmission(0x68); Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(0x68, 6) != 6) return false;
  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();
  const float s = 1.0f / 2048.0f;                            // LSB/g at +-16 g
  *amag = sqrtf((float)ax * ax + (float)ay * ay + (float)az * az) * s;
  return true;
}

static void impactCheck() {
  if (!g_imuOk || millis() - g_lastImuMs < IMU_PERIOD_MS) return;
  g_lastImuMs = millis();
  float a;
  if (!imuReadG(&a)) return;
  if (g_impactMs == 0 && a > A_TH_G) { g_impactMs = millis(); logEvt("IMPACT", "candidate"); }
  if (g_impactMs && millis() - g_impactMs > IMPACT_CONFIRM_MS) {
    // confirm: vehicle stationary (or no fix) after the window; else treat as pothole/bump
    bool stopped = !fixFresh() || g_fix.speed_mps < V_STOP_MPS;
    logEvt("IMPACT", stopped ? "confirmed" : "rejected_moving");
    if (stopped) notifyAll(EV_IMPACT);
    g_impactMs = 0;
  }
}

static void sosCheck() {
  bool down = digitalRead(PIN_SOS) == LOW;
  if (down && g_sosDownMs == 0) g_sosDownMs = millis();
  if (!down) { g_sosDownMs = 0; g_sosLatched = false; }
  if (down && !g_sosLatched && millis() - g_sosDownMs >= SOS_HOLD_MS) {
    g_sosLatched = true; logEvt("SOS", "pressed"); notifyAll(EV_SOS);
  }
}

// Adaptive reporting policy, Eq. (7)
static void reportingPolicy() {
  if (!g_cfg.tracking) return;
  uint32_t now = millis();
  if (now - g_lastReportMs < T_MIN_MS) return;
  bool trig = (now - g_lastReportMs >= T_MAX_MS);            // heartbeat
  if (fixFresh() && g_lastReported.valid) {
    float d = distM(g_lastReported.lat_e7, g_lastReported.lon_e7, g_fix.lat_e7, g_fix.lon_e7);
    bool turn = g_fix.speed_mps >= V_MIN_MPS && angDiff(g_fix.course_deg, g_lastReported.course_deg) >= PSI_TH_DEG;
    trig = trig || d >= D_TH_M || turn;
  } else if (fixFresh()) trig = true;                        // first valid fix
  if (trig) notifyAll(EV_PERIODIC);
}

// ================================================================= main
void setup() {
  DBG.begin(115200);
  GPS_PORT.begin(9600);
  GSM_PORT.begin(9600);
  pinMode(PIN_SOS, INPUT_PULLUP);
  cfgLoad();
  g_imuOk = imuInit();
  logEvt("BOOT", g_imuOk ? "imu_ok" : "imu_absent");
  if (!gsmInit()) logEvt("GSM", "init_failed");
  g_lastReportMs = millis();
}

void loop() {
  gpsPoll();
  if (gsmReadLine() && strncmp(gsmLine, "+CMTI", 5) == 0) handleUrc(gsmLine);
  sosCheck();
  impactCheck();
  geofenceCheck();
  reportingPolicy();
  static uint32_t lastFlush = 0, lastStat = 0;
  if (millis() - lastFlush > 120000UL) { lastFlush = millis(); flushQueue(); }
  if (millis() - lastStat > 10000UL) {                       // periodic fix-quality log
    lastStat = millis();
    char d[48];
    snprintf(d, sizeof(d), "acc=%lu rej=%lu valid=%d", (unsigned long)g_accepted, (unsigned long)g_rejected, fixFresh());
    logEvt("STAT", d);
    if (fixFresh()) { char la[16], lo[16]; fmtE7(la, g_fix.lat_e7); fmtE7(lo, g_fix.lon_e7);
      DBG.print(F("FIX,")); DBG.print(millis()); DBG.print(','); DBG.print(la); DBG.print(','); DBG.print(lo);
      DBG.print(','); DBG.print(g_fix.hdop_x100); DBG.print(','); DBG.print(g_fix.sats); DBG.print(',');
      DBG.println(g_fix.speed_mps); }
  }
}
