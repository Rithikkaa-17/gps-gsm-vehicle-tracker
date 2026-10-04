from svglib import SVG

W, H = 252, 450
s = SVG(W, H)
CX = 104        # main spine
BW = 132        # box width
S = 6.3
XL = 12         # left loop-back rail


def pbox(y, h, lines, proposed=False):
    s.box(CX - BW / 2, y, BW, h, lines, size=S, proposed=proposed, bold_first=False)
    return y + h


def down(y1, y2):
    s.line([(CX, y1), (CX, y2)], arrow_end=True)


s.terminal(CX, 12, 60, 16, "START", size=6.8)
down(20, 27)
y = pbox(27, 18, ["Initialise MCU: UART1/2, I2C, EEPROM state"])
down(y, y + 7)
y = pbox(y + 7, 18, ["Initialise GPS receiver (UART2, 9600 bit/s)"])
down(y, y + 7)
y = pbox(y + 7, 26, ["Initialise GSM: AT, ATE0, AT+CMGF=1,", "AT+CNMI; wait for AT+CREG? = 1 or 5"], proposed=True)
yloop = y + 9
down(y, y + 15)
s.dot(CX, yloop)
y = pbox(y + 15, 18, ["Read available NMEA bytes (non-blocking)"])
down(y, y + 8)

# decision 1 : fix valid
yd = y + 8 + 19
s.diamond(CX, yd, 118, 38, ["Checksum OK and", "fix valid? (Eq. 4)"])
s.text(CX - 5, yd + 27, "Yes", size=S, anchor="end")
down(yd + 19, yd + 29)
y = pbox(yd + 29, 18, ["Store valid fix (lat, lon, speed, course)"], proposed=True)
yj = y + 7
down(y, y + 14)
s.dot(CX, yj)
# No branch -> stale -> rejoin below store box
s.line([(CX + 59, yd), (CX + 80, yd)], arrow_end=True)
s.text(CX + 69, yd - 3, "No", size=S)
s.box(CX + 80, yd - 13, 62, 26, ["Increment", "fix age"], size=S, proposed=True, bold_first=False)
s.line([(CX + 111, yd + 13), (CX + 111, yj), (CX + 2, yj)], arrow_end=True)

y = pbox(y + 14, 28, ["Check requests and events: SMS from", "authorised no., geofence, impact, SOS"], proposed=True)
down(y, y + 8)

# decision 2 : report needed
yd2 = y + 8 + 20
s.diamond(CX, yd2, 118, 40, ["Reporting condition", "met? (Eq. 7)"])
s.line([(CX - 59, yd2), (XL, yd2), (XL, yloop), (CX - 2, yloop)], arrow_end=True)
s.text(CX - 63, yd2 - 3, "No", size=S, anchor="end")
s.text(CX - 5, yd2 + 28, "Yes", size=S, anchor="end")
down(yd2 + 20, yd2 + 30)
y = pbox(yd2 + 30, 18, ["Compose SMS: lat, lon, fix age, event code"])
down(y, y + 7)
ysend = y + 7
y = pbox(ysend, 18, ["Send with AT+CMGS; start timer T_ack"])
down(y, y + 8)

# decision 3 : ack
yd3 = y + 8 + 19
s.diamond(CX, yd3, 118, 38, ["+CMGS received", "before T_ack?"])
s.text(CX - 5, yd3 + 27, "Yes", size=S, anchor="end")
down(yd3 + 19, yd3 + 29)
y = pbox(yd3 + 29, 18, ["Log outcome; update last-report state"], proposed=True)
# continue monitoring -> loop rail
s.line([(CX, y), (CX, y + 8), (XL, y + 8), (XL, yd2)])
s.text(CX - 10, y + 16, "continue monitoring", size=5.8, anchor="middle")

# No -> retry box
s.line([(CX + 59, yd3), (CX + 80, yd3)], arrow_end=True)
s.text(CX + 69, yd3 - 3, "No", size=S)
s.box(CX + 80, yd3 - 22, 62, 44, ["n < N: retry", "after back-off;", "else queue in", "EEPROM"], size=S, proposed=True, bold_first=False)
s.line([(CX + 111, yd3 - 22), (CX + 111, ysend + 9), (CX + BW / 2, ysend + 9)], arrow_end=True)
s.text(CX + 115, yd3 - 32, "retry", size=5.8, anchor="start")
# queue -> continue
s.line([(CX + 111, yd3 + 22), (CX + 111, y + 8), (CX, y + 8)])

s.save("fig3_flowchart.svg")
print("bottom", y + 16)
