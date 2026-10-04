---
title: "E1 and E3 Test Procedure — Results for the SSD'27 Paper"
geometry: margin=2cm
fontsize: 10pt
---

These two experiments produce real data for **Table III** of the paper. Once the logs exist, one command builds the table and the paper includes it automatically, still at 6 pages. Plan about 3–5 days of work before the **2 Nov 2026** deadline.

# 0. One-time setup (½ day)

1. Wire the board as in Fig. 4(b): modem on D18/D19, GPS on D16/D17 through the 1 k/2 k divider, and the modem on its own 5 V ≥ 2 A supply with a common ground.
2. In `firmware/vts_enhanced/vts_enhanced.ino`, set `AUTH_NUMBERS` to the phone you will text from, then upload.
3. Open a serial logger at **115200 bit/s** and save to a file. Any of these works: Arduino IDE Serial Monitor (copy all the text into a file), PuTTY with session logging, or `pio device monitor --baud 115200 > file.log`.
4. **Check:** you should see `EVT,…,BOOT`, then `EVT,…,CREG,registered`, then `STAT` lines every 10 s. `FIX,…` lines appear once the GPS has a fix.

# 1. E1 — static positioning (2–3 days)

**Sites.** Use three sites and keep the antenna fixed at each: open sky (rooftop or open ground), partial obstruction (under trees or beside one building), and near a building (close to a tall wall).

**Reference point (recommended).** Read each site's coordinates from a surveyed campus benchmark or a satellite map at maximum zoom, to 7 decimals. If you have no reference, leave the coordinates out: the script then reports precision (spread around the mean) instead of accuracy, and labels it that way.

**Procedure per site.**

1. Power the node and start logging, saving to `e1_<site>.log`.
2. Leave it running for **at least 1 hour** without moving it.
3. Stop logging.

**TTFF.**

* **Cold start:** remove the NEO-6M's backup cell or leave the receiver unpowered for more than 4 h. Then power up and log to `cold_N.log` until the `TTFF` line appears. Repeat **10 times** (cold starts can be spread over days).
* **Hot start:** power-cycle the node for about 10 s with the backup kept, log to `hot_N.log`, and repeat **10 times**.

# 2. E3 — request-to-reply latency and delivery (1 day)

1. Keep the node at one fixed outdoor spot and log to `e3.log`.
2. Send **"GET LOCATION"** from the authorised phone, wait for the reply, then wait 30 s. Repeat **100 times**. That takes about 1.5 h; splitting it into 4 × 25 at different times of day is better.
3. Record send and receive times **to the second** in `handset.csv`:

```
request_id,t0_epoch_s,t5_epoch_s
1,1761895200,1761895209
2,1761895260,
```

Leave `t5` empty if no reply arrives within 5 min. Epoch seconds can come from an SMS-backup app export (most show times to the second) or from a phone stopwatch synced to network time. Keep the phone's clock on automatic network time.

4. Note the signal quality: the `CSQ` value appears in the log after any retry. You can also send `STATUS`.

# 3. Build the table (5 minutes)

```bash
cd analysis
python3 make_results_table.py \
  --site "Open sky:../logs/e1_open.log:13.xxxxxxx:80.xxxxxxx" \
  --site "Partial obstr.:../logs/e1_trees.log:13.xxxxxxx:80.xxxxxxx" \
  --site "Near building:../logs/e1_bldg.log:13.xxxxxxx:80.xxxxxxx" \
  --cold ../logs/cold_*.log --hot ../logs/hot_*.log \
  --e3log ../logs/e3.log --handset ../logs/handset.csv \
  --out ../paper/results_table.tex
cd ../paper && pdflatex main.tex && pdflatex main.tex
```

The paper now shows **Table III (Measured Performance)** in place of the "Planned Analysis" paragraph.

# 4. After the table exists

* Edit three sentences to state the measured findings:
    * the last sentence of the abstract;
    * the first sentence of Sec. VIII (Discussion);
    * the "next step" sentence of the Conclusion.
* Keep every raw log; reviewers may ask for them, and they should go in the GitHub repo under `logs/`.
* Report the numbers exactly as the script prints them, with no rounding up and no discarded runs. If you exclude a run (for example a battery failure), say so in the text.
