# GPS–GSM Vehicle Tracking Node with Validated, Event-Driven SMS Reporting

Low-cost vehicle tracker built on an **Arduino Mega 2560**, a **u-blox NEO-6M** GPS receiver and a **SIM900A** GSM modem. It answers SMS location requests with a Google Maps link, and its enhanced firmware adds:

- **NMEA fix validation:** checksum, RMC status, GGA fix quality, satellite count, HDOP and a speed-plausibility gate.
- **Event-driven reporting:** reports on displacement, course change or a heartbeat interval instead of a fixed timer.
- **Geofence and unauthorised-movement alerts,** with hysteresis so that GPS noise does not trigger false alarms.
- **Impact and SOS alerts,** using an MPU-6050 accelerometer and a push-button.
- **Acknowledgement-aware SMS:** waits for `+CMGS`, retries with back-off and queues undelivered alerts in EEPROM.

> **Status:** the baseline request → reply prototype was demonstrated on campus. The enhanced firmware compiles (19.9 kB flash, 1.8 kB RAM) but **has not yet been tested on hardware**. Every threshold marked `[CAL]` still needs calibration.

## Repository layout

| Path | Contents |
|---|---|
| `paper/` | 6-page IEEE conference paper prepared for SSD'27, SCI track (`main.tex`, `main.pdf`, `main.docx`) |
| `paper/figs/` | Original figures as editable SVG and PDF, plus the Python scripts that generate them |
| `firmware/vts_enhanced/` | Arduino sketch for the enhanced node |
| `analysis/make_results_table.py` | Builds the paper's results table (Table III) from real E1/E3 logs; see `TEST_PROCEDURE.md` |
| `analysis/eval_tools.py` | Turns device logs and NMEA traces into the paper's metrics (CEP50/R95, latency breakdown, Wilson delivery intervals, reporting-policy replay) |
| `tools/word/` | Scripts that convert the LaTeX paper to the IEEE-formatted Word file |

## Hardware wiring (proposed)

| Arduino Mega 2560 | Connects to |
|---|---|
| D18 TX1 / D19 RX1 | SIM900A RXD / TXD |
| D16 TX2 (via 1k/2k divider) / D17 RX2 | NEO-6M RX / TX |
| D20 SDA / D21 SCL / D2 | MPU-6050 SDA / SCL / INT |
| D3 | SOS push-button to GND |
| — | SIM900A on a separate 5 V, ≥2 A supply with a 1000 µF capacitor; all grounds common |

## Build and flash

1. Open `firmware/vts_enhanced/vts_enhanced.ino` in the Arduino IDE.
2. Select the board **Arduino Mega or Mega 2560**.
3. Set `AUTH_NUMBERS` to the authorised phone number(s).
4. Upload.

The sketch logs events as CSV on the USB serial port at 115200 bit/s.

SMS commands, accepted only from authorised numbers: `GET LOCATION`, `STATUS`, `TRACK ON`, `TRACK OFF`, `ARM`, `DISARM`, `FENCE <radius_m>`.

## Evaluation

```bash
python3 analysis/eval_tools.py static  --log e1.log --ref-lat <lat> --ref-lon <lon>
python3 analysis/eval_tools.py latency --log e3.log --handset handset.csv
python3 analysis/eval_tools.py replay  --nmea route.nmea --period 60 --dth 200
```


