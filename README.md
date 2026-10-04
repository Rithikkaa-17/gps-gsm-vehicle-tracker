# GPS–GSM Vehicle Tracking Node

Low-cost vehicle tracker built on an **Arduino Mega 2560**, a **u-blox NEO-6M** GPS receiver and a **SIM900A** GSM modem. It answers an SMS location request with a Google Maps link and sends automatic alerts to authorised phone numbers.

## Features

- **NMEA fix validation:** checksum, RMC status, GGA fix quality, satellite count, HDOP and a speed-plausibility gate.
- **Event-driven reporting:** reports on displacement, course change or a heartbeat interval instead of a fixed timer.
- **Geofence and unauthorised-movement alerts,** with hysteresis so that GPS noise does not trigger false alarms.
- **Impact and SOS alerts,** using an MPU-6050 accelerometer and a push-button.
- **Acknowledgement-aware SMS:** waits for `+CMGS`, retries with back-off and queues undelivered alerts in EEPROM.
- **Compact:** 19.9 kB flash and 1.8 kB RAM on the ATmega2560.

## Repository layout

| Path | Contents |
|---|---|
| `firmware/vts_enhanced/` | Arduino sketch for the tracking node |
| `analysis/eval_tools.py` | Turns device logs and NMEA traces into metrics (CEP50/R95, latency breakdown, delivery ratio with Wilson intervals, reporting-policy replay) |
| `analysis/make_results_table.py` | Builds a results table from device logs |
| `TEST_PROCEDURE.md` | Step-by-step procedure for static-positioning and latency tests |

## Hardware wiring

| Arduino Mega 2560 | Connects to |
|---|---|
| D18 TX1 / D19 RX1 | SIM900A RXD / TXD |
| D16 TX2 (via 1k/2k divider) / D17 RX2 | NEO-6M RX / TX |
| D20 SDA / D21 SCL / D2 | MPU-6050 SDA / SCL / INT |
| D3 | SOS push-button to GND |
| — | SIM900A on a separate 5 V, ≥2 A supply with a 1000 µF capacitor; all grounds common |

Check the logic level of your SIM900A board's TTL header before connecting it to the Mega.

## Build and flash

1. Open `firmware/vts_enhanced/vts_enhanced.ino` in the Arduino IDE.
2. Select the board **Arduino Mega or Mega 2560**.
3. Set `AUTH_NUMBERS` to the authorised phone number(s).
4. Upload.

Thresholds marked `[CAL]` in the sketch (HDOP limit, impact level, displacement and course triggers, geofence hysteresis) are starting values; adjust them for your vehicle and environment.

The sketch logs events as CSV on the USB serial port at 115200 bit/s.

## SMS commands

Accepted only from authorised numbers, case-insensitive:

| Command | Action |
|---|---|
| `GET LOCATION` | Reply with the current position and a map link |
| `STATUS` | Reply with the current state |
| `TRACK ON` / `TRACK OFF` | Enable or disable adaptive position reports |
| `ARM` | Set a small fence around the current position |
| `FENCE <radius_m>` | Set a fence of the given radius around the current position |
| `DISARM` | Disable the fence |

## Log analysis

```bash
python3 analysis/eval_tools.py static  --log e1.log --ref-lat <lat> --ref-lon <lon>
python3 analysis/eval_tools.py latency --log e3.log --handset handset.csv
python3 analysis/eval_tools.py replay  --nmea route.nmea --period 60 --dth 200
```

See `TEST_PROCEDURE.md` for how to record the logs.

## Authors

Rithikkaa S J and Rahul S G, Dept. of Electronics and Communication Engineering, Amrita Vishwa Vidyapeetham, Chennai. The first version of the prototype was built with Rohit P. and Rishivesh.
