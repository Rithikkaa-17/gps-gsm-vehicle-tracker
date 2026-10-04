from svglib import SVG

W, H = 516, 300
s = SVG(W, H)
SZ = 6.2


def pin_r(x, y, name):  # pin label inside a box, right edge
    s.text(x - 3, y + 2.2, name, size=SZ, anchor="end")


def pin_l(x, y, name):  # pin label inside a box, left edge
    s.text(x + 3, y + 2.2, name, size=SZ, anchor="start")


def netlabel(x, y, name, side="right"):
    # small flag-style net label
    if side == "right":
        s.line([(x, y), (x + 6, y)])
        s.text(x + 8, y + 2.2, name, size=SZ, anchor="start", weight="bold")
    else:
        s.line([(x, y), (x - 6, y)])
        s.text(x - 8, y + 2.2, name, size=SZ, anchor="end", weight="bold")


# ======================= (a) BASELINE =======================
s.rect(4, 6, 176, 288, dashed=True, sw=0.5)
s.text(10, 18, "(a) Baseline wiring as documented", size=7, anchor="start", weight="bold")

# Mega
s.rect(12, 60, 58, 150, sw=0.9)
s.mtext(41, 72, ["Arduino", "Mega 2560"], size=6.6, weight_first=False)
for y, n in [(100, "D0/RX0"), (114, "D1/TX0"), (150, "D17/RX2"), (164, "D16/TX2")]:
    pin_r(70, y, n)
pin_l(12, 196, "GND")
s.line([(12, 196), (8, 196), (8, 230)])
s.ground(8, 230)
pin_l(12, 180, "USB")
s.text(41, 222, "powered from PC USB", size=5.8, style="italic")

# SIM900A (a)
s.rect(122, 86, 52, 42, sw=0.9)
s.mtext(152, 92, ["SIM900A"], size=6.6, weight_first=True)
pin_l(122, 104, "TXD")
pin_l(122, 116, "RXD")
s.line([(70, 100), (90, 100), (90, 104), (122, 104)], arrow_start=True)
s.line([(70, 114), (96, 114), (96, 116), (122, 116)], arrow_end=True)

# NEO-6M (a)
s.rect(122, 140, 52, 42, sw=0.9)
s.mtext(148, 146, ["NEO-6M"], size=6.6, weight_first=True)
pin_l(122, 158, "TX")
pin_l(122, 170, "RX")
s.line([(70, 150), (90, 150), (90, 158), (122, 158)], arrow_start=True)
s.line([(70, 164), (96, 164), (96, 170), (122, 170)], arrow_end=True)

s.text(96, 135, "(per listing)", size=5.8, style="italic")
s.text(96, 196, "(per listing)", size=5.8, style="italic")
notes = ["Pin numbers as declared in the",
         "firmware listing: SoftwareSerial",
         "gsm(0,1) and gps(17,16).",
         "Module supply and logic levels",
         "were not documented.",
         "D0/D1 are shared with the USB-",
         "serial bridge (defect D1) and",
         "D17 cannot serve as a software-",
         "serial RX pin (defect D2)."]
for i, t in enumerate(notes):
    s.text(10, 244 + i * 6.0, t, size=5.4, anchor="start")

# ======================= (b) PROPOSED =======================
s.rect(186, 6, 326, 288, dashed=True, sw=0.5)
s.text(192, 18, "(b) Proposed enhanced node", size=7, anchor="start", weight="bold")

# --- power section
s.text(196, 37, "+12 V", size=SZ, anchor="start", weight="bold")
s.text(196, 45, "vehicle", size=5.6, anchor="start")
s.fuse_h(220, 246, 34, label="F1 2 A")
s.line([(246, 34), (258, 34)])
s.dot(258, 34)
s.rect(300, 24, 62, 22, sw=0.8, fill="#EDEDED", dashed=True)
s.mtext(331, 35, ["Buck 12 V to 5 V", "(>= 2 A peak)"], size=5.8, weight_first=True)
s.line([(258, 34), (300, 34)])
s.line([(362, 34), (390, 34)])
s.dot(390, 34)
s.capacitor_v(390, 34, 56, label="C1 1000 uF", polar=True)
s.ground(390, 56)
netlabel(390, 34, "+5V_GSM")
s.ground(331, 46)

# VIN branch
s.line([(258, 34), (258, 86), (262, 86)])

# --- Mega 2560
MX0, MX1, MY0, MY1 = 262, 330, 72, 270
s.rect(MX0, MY0, MX1 - MX0, MY1 - MY0, sw=0.9)
s.mtext((MX0 + MX1) / 2, 116, ["Arduino", "Mega 2560"], size=6.8, weight_first=True)
s.text((MX0 + MX1) / 2, 132, "ATmega2560", size=5.8, style="italic")
pin_l(MX0, 86, "VIN")
pin_l(MX0, 100, "5V")
netlabel(MX0, 100, "+5V_A", side="left")
pin_l(MX0, 160, "USB")
s.text(244, 172, "(debug /", size=5.4)
s.text(244, 179, "programming)", size=5.4)
pin_l(MX0, 256, "GND")
s.line([(MX0, 256), (252, 256), (252, 262)])
s.ground(252, 262)

pins_r = [(86, "D18/TX1"), (100, "D19/RX1"), (146, "D17/RX2"), (160, "D16/TX2"),
          (198, "D20/SDA"), (210, "D21/SCL"), (222, "D2/INT4"), (244, "D3")]
for y, n in pins_r:
    pin_r(MX1, y, n)

# --- SIM900A
s.rect(420, 66, 84, 60, sw=0.9)
s.mtext(462, 76, ["SIM900A GSM"], size=6.6, weight_first=True)
pin_l(420, 86, "RXD")
pin_l(420, 100, "TXD")
pin_l(420, 112, "VCC 5V")
pin_l(420, 122, "GND")
s.text(500, 100, "SIM", size=5.8, anchor="end")
s.text(500, 108, "holder", size=5.8, anchor="end")
s.antenna(492, 66, label=None)
s.line([(MX1, 86), (420, 86)], arrow_end=True)
s.line([(420, 100), (MX1, 100)], arrow_end=True)
netlabel(420, 112, "+5V_GSM", side="left")
s.line([(420, 122), (414, 122), (414, 126)])
s.ground(414, 126)
s.text(375, 82, "UART1 9600 bit/s", size=5.6)

# --- NEO-6M
s.rect(420, 138, 84, 46, sw=0.9)
s.mtext(462, 146, ["NEO-6M GPS"], size=6.6, weight_first=True)
pin_l(420, 146 + 0, "")
pin_l(420, 156, "TX")
pin_l(420, 168, "RX")
pin_l(420, 178, "VCC")
s.text(500, 168, "patch", size=5.6, anchor="end")
s.text(500, 176, "antenna", size=5.6, anchor="end")
# TX of GPS -> RX2
s.line([(420, 156), (346, 156), (346, 146), (MX1, 146)], arrow_end=True)
# TX2 -> divider -> GPS RX
s.line([(MX1, 160), (342, 160), (342, 168), (352, 168)])
s.resistor_h(352, 378, 168, label="R1 1k")
s.line([(378, 168), (386, 168)])
s.dot(386, 168)
s.line([(386, 168), (420, 168)], arrow_end=True)
s.resistor_v(386, 168, 192)
s.text(381, 183, "R2 2k", size=SZ, anchor="end")
s.ground(386, 192)
netlabel(420, 178, "+5V_A", side="left")
s.text(378, 146 - 6, "UART2 9600 bit/s", size=5.6)

# --- MPU-6050 (proposed sensor)
s.rect(420, 196, 84, 56, sw=0.9, dashed=True, fill="#EDEDED")
s.mtext(462, 204, ["MPU-6050 IMU"], size=6.6, weight_first=True)
s.text(462, 212, "(GY-521 board)", size=5.6)
pin_l(420, 222, "SDA")
pin_l(420, 232, "SCL")
pin_l(420, 242, "INT")
s.text(500, 240, "VCC: +5V_A", size=5.4, anchor="end")
s.text(500, 247, "GND: common", size=5.4, anchor="end")
s.line([(MX1, 198), (400, 198), (400, 222), (420, 222)], arrow_end=True, arrow_start=True)
s.line([(MX1, 210), (394, 210), (394, 232), (420, 232)], arrow_end=True)
s.line([(420, 242), (388, 242), (388, 222), (MX1, 222)], arrow_end=True)
s.text(362, 192, "I2C 400 kHz", size=5.6)

# --- SOS push-button
s.line([(MX1, 244), (352, 244), (352, 250)])
s.pushbutton_v(352, 250, 270, label="S1 SOS")
s.ground(352, 270)
s.text(352, 289, "INPUT_PULLUP", size=5.4)

# legend
s.rect(194, 210, 56, 44, sw=0.4)
s.rect(198, 214, 12, 8, fill="#FFFFFF")
s.text(213, 220, "existing", size=5.6, anchor="start")
s.rect(198, 226, 12, 8, dashed=True, fill="#EDEDED")
s.text(213, 232, "added", size=5.6, anchor="start")
s.text(198, 244, "C1 at modem", size=5.4, anchor="start")
s.text(198, 250, "VCC pins", size=5.4, anchor="start")

s.save("fig2_schematic.svg")