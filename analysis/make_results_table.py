#!/usr/bin/env python3
"""
make_results_table.py -- build paper/results_table.tex from REAL E1/E3 logs.

The paper includes results_table.tex automatically when it exists (Sec. VII-D).
Nothing here estimates or fills in values: a cell with no data is printed as "--".

Inputs (all captured from the node's USB log at 115200 bit/s):
  --site  "Open sky:e1_open.log:13.xxxxxxx:80.xxxxxxx"    (repeatable; ref = surveyed point,
                                                           or omit lat/lon to use the mean)
  --cold  boot1.log boot2.log ...    one log per power-up after a cold start
  --hot   hot1.log hot2.log ...      one log per power-up with backup supply retained
  --e3log e3.log                     device log during the latency test
  --handset handset.csv              request_id,t0_epoch_s,t5_epoch_s (t5 empty = no reply)

Example:
  python3 analysis/make_results_table.py \
     --site "Open sky:e1_open.log:13.2626512:80.0265733" \
     --site "Near building:e1_bldg.log" \
     --cold c1.log c2.log c3.log --hot h1.log h2.log h3.log \
     --e3log e3.log --handset handset.csv --out paper/results_table.tex
"""
import argparse, csv, statistics as st
import eval_tools as ev


def fmt(x, nd=1):
    return '--' if x is None else f'{x:.{nd}f}'


def ttff_s(path):
    evts, _ = ev.read_device_log(path)
    boot = next((ms for ms, tag, _ in evts if tag == 'BOOT'), None)
    fix = next((ms for ms, tag, _ in evts if tag == 'TTFF'), None)
    return None if boot is None or fix is None else (fix - boot) / 1000.0


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def site_row(spec):
    parts = spec.split(':')
    label, path = parts[0], parts[1]
    ref = (float(parts[2]), float(parts[3])) if len(parts) >= 4 else (None, None)
    evts, fixes = ev.read_device_log(path)
    if not fixes:
        return label, None
    s = ev.horizontal_stats([(f[1], f[2]) for f in fixes], *ref)
    rej = sum(1 for _, tag, _ in evts if tag == 'FIXREJ')
    acc = len(fixes)
    s['hdop'] = st.median(f[3] / 100 for f in fixes)
    s['rej_pct'] = 100.0 * rej / (rej + acc) if rej + acc else None
    s['surveyed'] = ref[0] is not None
    return label, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', action='append', default=[])
    ap.add_argument('--cold', nargs='*', default=[])
    ap.add_argument('--hot', nargs='*', default=[])
    ap.add_argument('--e3log')
    ap.add_argument('--handset')
    ap.add_argument('--out', default='paper/results_table.tex')
    a = ap.parse_args()

    cold = med([ttff_s(p) for p in a.cold]); hot = med([ttff_s(p) for p in a.hot])
    rows = [site_row(s) for s in a.site]
    surveyed = all(r[1] and r[1]['surveyed'] for r in rows) if rows else False

    L = [r'\begin{table}[!t]',
         r'\caption{Measured Performance of the Prototype (E1, E3)}',
         r'\label{tab:results}', r'\centering', r'\scriptsize', r'\setlength{\tabcolsep}{3pt}',
         r'\begin{tabular}{@{}lcccccc@{}}', r'\toprule',
         r'\multicolumn{7}{@{}l}{\textit{E1: static positioning (TTFF median: cold %s~s, hot %s~s; %d/%d power-ups)}}\\'
         % (fmt(cold), fmt(hot), len(a.cold), len(a.hot)),
         r'Site & $N$ & CEP50 (m) & R95 (m) & 2DRMS (m) & HDOP & Rejected (\%) \\', r'\midrule']
    for label, s in rows:
        if s is None:
            L.append(f'{label} & 0 & -- & -- & -- & -- & -- \\\\')
        else:
            L.append(f"{label} & {s['N']} & {fmt(s['CEP50_m'],2)} & {fmt(s['R95_m'],2)} & {fmt(s['2DRMS_m'],2)} & "
                     f"{fmt(s['hdop'],2)} & {fmt(s['rej_pct'])} \\\\")
    if a.e3log:
        evts, _ = ev.read_device_log(a.e3log)
        lat = ev.latency_from_events(evts)
        ok = [x for x in lat if x.get('ok')]
        tproc = med([(x['t3'] - x['t1']) / 1000 for x in lat])
        ttx = med([(x['t4'] - x['t3']) / 1000 for x in ok])
        e2e, n_req = [], 0
        if a.handset:
            rows_h = list(csv.DictReader(open(a.handset)))
            n_req = len(rows_h)
            e2e = [float(r['t5_epoch_s']) - float(r['t0_epoch_s']) for r in rows_h if r.get('t5_epoch_s')]
        p, lo, hi = ev.wilson(len(e2e), n_req) if n_req else (None, None, None)
        L += [r'\midrule',
              r'\multicolumn{7}{@{}l}{\textit{E3: request-to-reply latency (s) and delivery}}\\',
              r'Requests & $n$ & $T_{\mathrm{proc}}$ med. & $T_{\mathrm{tx}}$ med. & $T_{\mathrm{e2e}}$ med. & $T_{\mathrm{e2e}}$ P95 & $\hat{p}$ [95\% CI] \\',
              r'\midrule',
              f"All & {n_req} & {fmt(tproc,2)} & {fmt(ttx,2)} & {fmt(med(e2e))} & "
              f"{fmt(ev.pct(e2e,0.95) if e2e else None)} & "
              + ('--' if p is None else f'{p:.3f} [{lo:.3f}, {hi:.3f}]') + r' \\']
    L += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    note = ('Errors are relative to surveyed reference points.' if surveyed else
            'Errors are relative to the long-term mean of each session (precision, not accuracy).')
    L.append('% ' + note)
    open(a.out, 'w').write('\n'.join(L) + '\n')
    print('wrote', a.out, '|', note)


if __name__ == '__main__':
    main()
