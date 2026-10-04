from svglib import SVG

W, H = 516, 250
s = SVG(W, H)
S = 6.1
LL = {"veh": 52, "gps": 128, "mcu": 214, "gsm": 300, "net": 386, "usr": 466}
names = {"veh": ["Vehicle", "(IMU / SOS)"], "gps": ["NEO-6M", "GPS"], "mcu": ["Arduino", "Mega 2560"],
         "gsm": ["SIM900A", "modem"], "net": ["Cellular", "network/SMSC"], "usr": ["User", "handset"]}
TOP, BOT = 30, 218
for k, x in LL.items():
    s.box(x - 30, 6, 60, 22, names[k], size=6.3)
    s.line([(x, TOP), (x, BOT)], sw=0.5, dashed=True)


def msg(a, b, y, label, dashed=False, above=True):
    xa, xb = LL[a], LL[b]
    s.line([(xa, y), (xb, y)], arrow_end=True, dashed=dashed)
    s.text((xa + xb) / 2, y - 2.5 if above else y + 7.5, label, size=S)


def selfnote(k, y, h, lines, proposed=True):
    x = LL[k]
    s.box(x - 34, y, 68, h, lines, size=5.8, proposed=proposed, bold_first=False)


def tmark(y, t):
    s.line([(14, y), (24, y)], sw=0.5)
    s.text(12, y + 2.2, t, size=6.0, anchor="end", style="italic")


# frame A
s.rect(4, 33.2, 508, 184.0, sw=0.5, fill="none")
s.rect(4, 33.2, 92, 11, sw=0.5, fill="#FFFFFF")
s.text(8, 39.6, "A: on-demand request", size=6.2, anchor="start", weight="bold")
s.line([(LL["gps"], 57.2), (LL["mcu"], 57.2)], arrow_end=True)
s.text((LL["gps"] + LL["mcu"]) / 2, 55.2, "$GPRMC / $GPGGA, 1 Hz", size=S)
msg("usr", "net", 50.8, "SMS \"Get location\""); tmark(50.8, "t0")
msg("net", "gsm", 63.6, "SMS deliver")
msg("gsm", "mcu", 76.4, "URC +CMTI: \"SM\",n"); tmark(76.4, "t1")
msg("mcu", "gsm", 89.2, "AT+CMGR=n")
msg("gsm", "mcu", 102.0, "+CMGR: sender, text")
selfnote("mcu", 106.8, 14, ["parse command,", "check sender"])
s.line([(LL["gps"], 127.6), (LL["mcu"] - 34, 127.6)], arrow_end=True)
s.text(150, 125.6, "next NMEA epoch", size=S)
selfnote("mcu", 122.8, 14, ["validate fix", "(Eq. 4)"])
tmark(135.6, "t2")
msg("mcu", "gsm", 148.4, "AT+CMGS=\"<no.>\""); tmark(148.4, "t3")
msg("gsm", "mcu", 159.6, "prompt \">\"")
msg("mcu", "gsm", 170.8, "text + Ctrl-Z (0x1A)")
msg("gsm", "net", 182.0, "SMS submit")
msg("net", "gsm", 193.2, "submit ack")
msg("gsm", "mcu", 204.4, "+CMGS: <mr>, OK"); tmark(204.4, "t4")
msg("net", "usr", 212.4, "reply SMS (lat, lon, URL)"); tmark(212.4, "t5")

# event-driven alert path noted compactly
s.rect(4, 222.0, 508, 22, sw=0.5, fill="#EDEDED", dashed=True)
s.text(10, 235.5, "B (proposed): impact / SOS / geofence event → MCU confirms event, attaches last valid fix → same AT+CMGS path with retry on timeout → alert SMS (t0' to t5')", size=6.2, anchor="start")

s.save("fig4_sequence.svg")
