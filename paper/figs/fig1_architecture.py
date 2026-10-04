from svglib import SVG

W, H = 516, 182
s = SVG(W, H)

# ---- vehicle node enclosure
s.rect(78, 8, 340, 98, dashed=True, fill="#FFFFFF", sw=0.6)
s.text(84, 18, "In-vehicle tracking node", size=6.8, anchor="start", style="italic")

# satellites
s.box(6, 30, 58, 34, ["GPS", "satellites"], size=6.8)
s.text(35, 75, "L1 C/A", size=6.2)
s.text(35, 83, "1575.42 MHz", size=6.2)
s.line([(64, 47), (92, 47)], arrow_end=True)

# antenna + NEO-6M
s.box(92, 30, 58, 34, ["u-blox NEO-6M", "GPS receiver"], size=6.6)
s.line([(150, 47), (178, 47)], arrow_end=True)
s.text(164, 41, "UART", size=6)
s.text(164, 57, "NMEA", size=6)

# Mega enclosure
s.rect(178, 24, 160, 74, fill="#FFFFFF", sw=0.9)
s.text(258, 34, "Arduino Mega 2560 (ATmega2560)", size=6.8, weight="bold")
s.box(184, 42, 42, 30, ["NMEA", "parsing"], size=6.4, bold_first=False)
s.box(237, 42, 42, 30, ["Fix", "validation"], size=6.4, proposed=True, bold_first=False)
s.box(290, 42, 44, 30, ["Event /", "report logic"], size=6.4, proposed=True, bold_first=False)
s.line([(226, 57), (237, 57)], arrow_end=True)
s.line([(279, 57), (290, 57)], arrow_end=True)
s.text(258, 88, "decimal-degree conversion, message build", size=6.0)

# SIM900A
s.line([(338, 50), (354, 50)], arrow_end=True)
s.line([(354, 64), (338, 64)], arrow_end=True)
s.text(346, 46, "AT", size=5.8)
s.box(354, 34, 58, 44, ["SIMCom", "SIM900A", "GSM modem"], size=6.6)
s.antenna(400, 34)

# ---- external side (second row)
s.box(354, 128, 70, 36, ["GSM network", "(BTS / SMSC)"], size=6.6)
s.box(230, 128, 74, 36, ["User handset", "(authorised no.)"], size=6.6)
s.box(100, 128, 82, 36, ["Map service", "(link opened from SMS)"], size=6.6)

# reply path (solid) : modem -> network -> handset -> maps
s.line([(372, 78), (372, 128)], arrow_end=True)
s.text(368, 120, "Reply / alert SMS", size=6.0, anchor="end")
s.line([(354, 140), (304, 140)], arrow_end=True)
s.line([(230, 146), (182, 146)], arrow_end=True)
s.text(206, 141, "URL", size=6.0)

# request path (dashed) : handset -> network -> modem
s.line([(304, 154), (354, 154)], dashed=True, arrow_end=True)
s.text(329, 172, "Request SMS", size=6.0)
s.line([(400, 128), (400, 78)], dashed=True, arrow_end=True)
s.text(404, 120, "Request SMS (URC +CMTI)", size=6.0, anchor="start")

# legend
s.rect(440, 10, 70, 60, fill="#FFFFFF", sw=0.5)
s.rect(446, 16, 14, 9, fill="#FFFFFF")
s.text(464, 23, "Implemented", size=6, anchor="start")
s.rect(446, 30, 14, 9, dashed=True, fill="#EDEDED")
s.text(464, 37, "Proposed", size=6, anchor="start")
s.line([(446, 49), (460, 49)], arrow_end=True)
s.text(464, 51, "Data / reply", size=6, anchor="start")
s.line([(446, 61), (460, 61)], dashed=True, arrow_end=True)
s.text(464, 63, "Request", size=6, anchor="start")

s.save("fig1_architecture.svg")
