from svglib import SVG

W, H = 516, 236
s = SVG(W, H)
S = 6.2


def ex(x, y, w, h, lines):      # existing, unchanged
    return s.box(x, y, w, h, lines, size=S)


def rw(x, y, w, h, lines):      # existing, reworked
    s.rect(x, y, w, h, fill="#EDEDED", sw=1.0)
    s.mtext(x + w / 2, y + h / 2, lines, size=S, weight_first=True)


def nw(x, y, w, h, lines):      # new / proposed
    return s.box(x, y, w, h, lines, size=S, proposed=True)


# layer captions
for x, t in [(8, "Sensing"), (110, "Acquisition and validation"), (236, "Event and decision logic"), (392, "Communication")]:
    s.text(x, 12, t, size=6.6, anchor="start", weight="bold", style="italic")

# MCU firmware boundary
s.rect(104, 18, 280, 176, dashed=True, fill="none", sw=0.6)
s.text(378, 190, "ATmega2560 firmware", size=6, anchor="end", style="italic")

# sensing
ex(8, 30, 80, 30, ["NEO-6M GPS", "NMEA @ 1 Hz"])
nw(8, 76, 80, 30, ["MPU-6050 IMU", "3-axis accel., I2C"])
nw(8, 122, 80, 30, ["SOS push-button", "D3, pull-up"])

# acquisition
rw(112, 30, 108, 30, ["NMEA parser", "non-blocking, RMC + GGA"])
nw(112, 76, 108, 30, ["Fix validator", "checksum, status, HDOP, v_max"])
nw(112, 122, 108, 30, ["Impact / SOS detector", "|a| threshold + confirm"])
s.line([(88, 45), (112, 45)], arrow_end=True)
s.line([(166, 60), (166, 76)], arrow_end=True)
s.line([(88, 91), (100, 91), (100, 132), (112, 132)], arrow_end=True)
s.line([(88, 142), (112, 142)], arrow_end=True)

# decision
rw(238, 30, 96, 30, ["Request handler", "whitelist, commands"])
nw(238, 72, 96, 30, ["Geofence monitor", "Eq. (5), hysteresis"])
nw(238, 114, 96, 30, ["Reporting policy", "Eq. (7)"])
nw(342, 30, 40, 128, ["Event", "arbiter", "", "priority:", "SOS,", "impact,", "fence,", "request,", "periodic"])
s.line([(220, 91), (228, 91), (228, 87), (238, 87)], arrow_end=True)          # validator -> fence
s.line([(228, 91), (228, 129), (238, 129)], arrow_end=True)                    # validator -> policy
s.line([(334, 45), (342, 45)], arrow_end=True)
s.line([(334, 87), (342, 87)], arrow_end=True)
s.line([(334, 129), (342, 129)], arrow_end=True)
s.line([(220, 150), (342, 150)], arrow_end=True)                               # impact/SOS -> arbiter

# EEPROM
nw(112, 164, 270, 20, ["EEPROM (4 KB): configuration, fence, pending-alert queue, position history"])
s.line([(362, 158), (362, 164)], arrow_end=True, arrow_start=True)

# communication
ex(394, 30, 114, 26, ["Message composer", "decimal degrees + map URL"])
nw(394, 68, 114, 34, ["GSM link manager", "AT state machine, CREG/CSQ,", "+CMGS timeout, retry"])
ex(394, 114, 114, 26, ["SIM900A modem", "2G GSM, SMS text mode"])
ex(394, 152, 114, 26, ["User handset", "reply / alert SMS"])
s.line([(382, 43), (394, 43)], arrow_end=True)
s.line([(451, 56), (451, 68)], arrow_end=True)
s.line([(451, 102), (451, 114)], arrow_end=True, arrow_start=True)
s.line([(440, 140), (440, 152)], arrow_end=True)
s.line([(462, 152), (462, 140)], dashed=True, arrow_end=True)
# incoming SMS -> request handler (dashed, routed over the top)
s.line([(394, 127), (389, 127), (389, 22), (286, 22), (286, 30)], dashed=True, arrow_end=True)
s.text(468, 148, "request", size=5.6, anchor="start")

# legend
s.rect(8, 202, 500, 30, sw=0.4)
s.rect(16, 210, 14, 9)
s.text(34, 217, "existing, unchanged", size=6, anchor="start")
s.rect(124, 210, 14, 9, fill="#EDEDED", sw=1.0)
s.text(142, 217, "existing function, reworked", size=6, anchor="start")
s.rect(260, 210, 14, 9, dashed=True, fill="#EDEDED")
s.text(278, 217, "proposed (to be implemented and validated)", size=6, anchor="start")
s.line([(16, 227), (30, 227)], dashed=True, arrow_end=True)
s.text(34, 229, "incoming request path", size=6, anchor="start")
s.line([(150, 227), (164, 227)], arrow_end=True)
s.text(168, 229, "data / control flow", size=6, anchor="start")

s.save("fig5_enhanced.svg")