#!/usr/bin/env python3
"""
eval_tools.py -- offline evaluation for the GPS-GSM tracking node (paper Sec. VII).

Implements the metrics defined in the paper so that Tables III-V can be filled from
REAL logs only. Nothing here generates results; `--selftest` exercises the code on
synthetic data purely to check the arithmetic and must never be reported.

Inputs
  * device log captured from the USB debug port (lines "EVT,<ms>,<tag>,<detail>" and
    "FIX,<ms>,<lat>,<lon>,<hdop_x100>,<sats>,<speed_mps>")
  * optional handset log CSV: request_id,t0_epoch_s,t5_epoch_s (send / receive times)
  * NMEA trace files (raw $GPRMC lines) for trace-driven policy replay

Usage
  python3 eval_tools.py static   --log dev.log --ref-lat 13.xxxxxx --ref-lon 80.xxxxxx
  python3 eval_tools.py latency  --log dev.log [--handset handset.csv]
  python3 eval_tools.py replay   --nmea route1.nmea --period 60 --dth 200 --psi 30 --tmax 600
  python3 eval_tools.py selftest
"""
import argparse, csv, math, statistics as st, sys

R = 6371008.8  # mean Earth radius, m


# ---------------------------------------------------------------- geometry (Eqs. 1-3)
def nmea_to_deg(v, hemi):
    """ddmm.mmmm + hemisphere -> signed decimal degrees (Eq. 1)."""
    if not v:
        return None
    dot = v.index(".")
    deg = int(v[:dot - 2]); minutes = float(v[dot - 2:])
    d = deg + minutes / 60.0
    return -d if hemi in ("S", "W") else d


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (Eq. 2)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def enu(lat, lon, lat0, lon0):
    """Local east/north offsets (m) about a reference (Eq. 3)."""
    e = math.radians(lon - lon0) * R * math.cos(math.radians(lat0))
    n = math.radians(lat - lat0) * R
    return e, n


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return xs[f] if f == c else xs[f] + (xs[c] - xs[f]) * (k - f)


# ---------------------------------------------------------------- statistics (Eqs. 8, 10)
def horizontal_stats(fixes, lat0=None, lon0=None):
    """fixes: list of (lat, lon). Reference = surveyed point if given, else sample mean
    (then the result is precision, not accuracy)."""
    if lat0 is None:
        lat0 = st.fmean(f[0] for f in fixes); lon0 = st.fmean(f[1] for f in fixes)
    en = [enu(a, b, lat0, lon0) for a, b in fixes]
    r = [math.hypot(e, n) for e, n in en]
    se = st.pstdev([e for e, _ in en]); sn = st.pstdev([n for _, n in en])
    return {"N": len(r), "mean_m": st.fmean(r), "CEP50_m": pct(r, 0.5), "R95_m": pct(r, 0.95),
            "max_m": max(r), "2DRMS_m": 2 * math.sqrt(se ** 2 + sn ** 2)}


def wilson(k, n, z=1.96):
    """Wilson score interval for a delivery ratio k/n (Eq. 10)."""
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def summarize(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "n=0"
    return (f"n={len(xs)} mean={st.fmean(xs):.2f} median={st.median(xs):.2f} "
            f"p95={pct(xs, 0.95):.2f} min={min(xs):.2f} max={max(xs):.2f}")


# ---------------------------------------------------------------- log parsing
def read_device_log(path):
    evts, fixes = [], []
    with open(path, errors="ignore") as f:
        for line in f:
            p = line.strip().split(",")
            if p[0] == "EVT" and len(p) >= 3:
                evts.append((int(p[1]), p[2], ",".join(p[3:])))
            elif p[0] == "FIX" and len(p) >= 7:
                fixes.append((int(p[1]), float(p[2]), float(p[3]), int(p[4]), int(p[5]), float(p[6])))
    return evts, fixes


def latency_from_events(evts):
    """Pairs CMTI(t1) -> CMGS_TX(t3) -> CMGS_OK|CMGS_FAIL(t4) per request (Eq. 9)."""
    out, cur = [], None
    for ms, tag, det in evts:
        if tag == "CMTI":
            cur = {"t1": ms}
        elif tag == "CMGS_TX" and cur is not None and "t3" not in cur:
            cur["t3"] = ms
        elif tag in ("CMGS_OK", "CMGS_FAIL") and cur is not None and "t3" in cur:
            cur["t4"] = ms; cur["ok"] = tag == "CMGS_OK"; out.append(cur); cur = None
    return out


# ---------------------------------------------------------------- trace replay (Eq. 11)
def read_rmc_trace(path):
    pts = []
    with open(path, errors="ignore") as f:
        for line in f:
            if "RMC" not in line[:7]:
                continue
            p = line.strip().split("*")[0].split(",")
            if len(p) < 10 or p[2] != "A":
                continue
            t = p[1]
            secs = int(t[0:2]) * 3600 + int(t[2:4]) * 60 + float(t[4:])
            pts.append((secs, nmea_to_deg(p[3], p[4]), nmea_to_deg(p[5], p[6]),
                        float(p[7] or 0) * 0.514444, float(p[8] or 0)))
    # handle midnight rollover
    for i in range(1, len(pts)):
        if pts[i][0] < pts[i - 1][0]:
            pts[i] = (pts[i][0] + 86400,) + pts[i][1:]
    return pts


def policy_periodic(pts, period):
    rep, last = [], None
    for i, p in enumerate(pts):
        if last is None or p[0] - pts[last][0] >= period:
            rep.append(i); last = i
    return rep


def policy_adaptive(pts, dth, psi, tmax, tmin=30.0, vmin=2.8):
    rep, last = [], None
    for i, p in enumerate(pts):
        if last is None:
            rep.append(i); last = i; continue
        q = pts[last]
        if p[0] - q[0] < tmin:
            continue
        d = haversine(q[1], q[2], p[1], p[2])
        dpsi = abs((p[4] - q[4] + 180) % 360 - 180)
        if p[0] - q[0] >= tmax or d >= dth or (p[3] >= vmin and dpsi >= psi):
            rep.append(i); last = i
    return rep


def reconstruction_error(pts, rep):
    """Zero-order-hold error between true track and last reported position (Eq. 11)."""
    err, j = [], 0
    for i, p in enumerate(pts):
        while j + 1 < len(rep) and rep[j + 1] <= i:
            j += 1
        q = pts[rep[j]]
        err.append(haversine(q[1], q[2], p[1], p[2]))
    return err


# ---------------------------------------------------------------- commands
def cmd_static(a):
    _, fixes = read_device_log(a.log)
    pts = [(f[1], f[2]) for f in fixes]
    ref = (a.ref_lat, a.ref_lon) if a.ref_lat is not None else (None, None)
    s = horizontal_stats(pts, *ref)
    print("reference:", "surveyed point (accuracy)" if a.ref_lat is not None else "sample mean (precision only)")
    for k, v in s.items():
        print(f"  {k:8s} {v:.3f}" if isinstance(v, float) else f"  {k:8s} {v}")
    print("  HDOP    ", summarize([f[3] / 100 for f in fixes]))
    print("  sats    ", summarize([f[4] for f in fixes]))


def cmd_latency(a):
    evts, _ = read_device_log(a.log)
    L = latency_from_events(evts)
    ok = [x for x in L if x.get("ok")]
    print("T_proc = t3 - t1 (s):", summarize([(x["t3"] - x["t1"]) / 1000 for x in L]))
    print("T_tx   = t4 - t3 (s):", summarize([(x["t4"] - x["t3"]) / 1000 for x in ok]))
    p, lo, hi = wilson(len(ok), len(L))
    print(f"modem-confirmed ratio: {len(ok)}/{len(L)} = {p:.3f} (95% CI {lo:.3f}-{hi:.3f})")
    if a.handset:
        rows = list(csv.DictReader(open(a.handset)))
        e2e = [float(r["t5_epoch_s"]) - float(r["t0_epoch_s"]) for r in rows if r.get("t5_epoch_s")]
        print("T_e2e  = t5 - t0 (s):", summarize(e2e))
        p, lo, hi = wilson(len(e2e), len(rows))
        print(f"end-to-end delivery: {len(e2e)}/{len(rows)} = {p:.3f} (95% CI {lo:.3f}-{hi:.3f})")
    print("rejected fixes by reason:")
    rej = {}
    for _, tag, det in evts:
        if tag == "FIXREJ":
            rej[det] = rej.get(det, 0) + 1
    for k, v in sorted(rej.items(), key=lambda kv: -kv[1]):
        print(f"  {k:18s} {v}")


def cmd_replay(a):
    pts = read_rmc_trace(a.nmea)
    if len(pts) < 2:
        sys.exit("trace has fewer than 2 valid RMC fixes")
    dur = pts[-1][0] - pts[0][0]
    length = sum(haversine(pts[i - 1][1], pts[i - 1][2], pts[i][1], pts[i][2]) for i in range(1, len(pts)))
    rp = policy_periodic(pts, a.period)
    ra = policy_adaptive(pts, a.dth, a.psi, a.tmax)
    ep, ea = reconstruction_error(pts, rp), reconstruction_error(pts, ra)
    print(f"trace: {len(pts)} fixes, {dur/60:.1f} min, path length {length/1000:.3f} km (sum of Eq. 2)")
    for name, r, e in (("periodic", rp, ep), ("adaptive", ra, ea)):
        rms = math.sqrt(st.fmean(x * x for x in e))
        print(f"  {name:9s} N_SMS={len(r):4d}  err_mean={st.fmean(e):7.1f} m  err_rms={rms:7.1f} m  "
              f"err_p95={pct(e, .95):7.1f} m  err_max={max(e):7.1f} m")
    print(f"  message reduction eta = 1 - N_a/N_p = {1 - len(ra)/len(rp):.3f}  (Eq. 11)")


def cmd_selftest(_):
    """Arithmetic checks on synthetic data. NOT experimental results."""
    assert abs(nmea_to_deg("1315.75900", "N") - 13.26265) < 1e-9
    assert abs(nmea_to_deg("08001.59420", "E") - 80.02657) < 1e-9
    d = haversine(13.26265, 80.02657, 13.26265, 80.02658)
    assert 1.0 < d < 1.2, d
    p, lo, hi = wilson(95, 100)
    assert lo < p < hi
    # straight synthetic track at 10 m/s, 1 Hz
    pts = [(t, 13.0 + t * 10 / 111195.0, 80.0, 10.0, 0.0) for t in range(600)]
    assert len(policy_adaptive(pts, 200, 30, 600)) < len(policy_periodic(pts, 10))
    print("selftest passed (synthetic data, not results)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("static"); s.add_argument("--log", required=True)
    s.add_argument("--ref-lat", type=float); s.add_argument("--ref-lon", type=float)
    s = sp.add_parser("latency"); s.add_argument("--log", required=True); s.add_argument("--handset")
    s = sp.add_parser("replay"); s.add_argument("--nmea", required=True)
    s.add_argument("--period", type=float, default=60); s.add_argument("--dth", type=float, default=200)
    s.add_argument("--psi", type=float, default=30); s.add_argument("--tmax", type=float, default=600)
    sp.add_parser("selftest")
    a = ap.parse_args()
    {"static": cmd_static, "latency": cmd_latency, "replay": cmd_replay, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
