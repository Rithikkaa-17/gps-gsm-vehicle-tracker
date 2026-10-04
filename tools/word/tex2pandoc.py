"""Pre-process main.tex into a pandoc-friendly LaTeX file.

Resolves \\ref/\\eqref/\\cite from main.aux, replaces figures/tables/algorithm with
markers that build_docx.py turns into IEEE-formatted Word objects.
"""
import re, sys

SRC, AUX, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
tex = open(SRC).read()
aux = open(AUX).read()

labels = {}
for m in re.finditer(r'\\newlabel\{([^}@]+)\}\{\{(.*?)\}\{', aux):
    v = m.group(2).replace(r'\mbox  {', '').replace('}', '').strip()
    labels[m.group(1)] = v
cites = dict(re.findall(r'\\bibcite\{([^}]+)\}\{(\d+)\}', aux))

def brace_arg_early(s, start):
    assert s[start] == '{', s[start:start+20]
    depth, i = 0, start
    while True:
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0: return s[start + 1:i], i + 1
        i += 1

body = tex[tex.index(r'\maketitle') + len(r'\maketitle'):tex.index(r'\end{document}')]

# ---------- results switch: pick the branch matching the real file state
import os
i = body.find(r'\IfFileExists{results_table.tex}')
if i >= 0:
    j = i + len(r'\IfFileExists{results_table.tex}')
    yes, j = brace_arg_early(body, j)
    while body[j] in ' %\n': j += 1
    no, j = brace_arg_early(body, j)
    res = os.path.join(os.path.dirname(SRC), 'results_table.tex')
    if os.path.exists(res):
        yes = yes.replace(r'\input{results_table.tex}', open(res).read())
    body = body[:i] + (yes if os.path.exists(res) else no) + body[j:]

# ---------- abstract / keywords -> marked paragraphs
def grab_env(name, s):
    a = s.index(r'\begin{%s}' % name); b = s.index(r'\end{%s}' % name)
    return s[a + len(r'\begin{%s}' % name):b].strip(), a, b + len(r'\end{%s}' % name)
abs_txt, a, b = grab_env('abstract', body)
body = body[:a] + '\n\nABSTRACTMARK ' + abs_txt + '\n\n' + body[b:]
kw_txt, a, b = grab_env('IEEEkeywords', body)
body = body[:a] + '\n\nKEYWORDSMARK ' + kw_txt + '\n\n' + body[b:]

# ---------- figures, algorithm -> markers + caption paragraph
PNG = {'fig1_architecture.pdf': 'fig1_architecture.png', 'fig2_schematic.pdf': 'fig2_schematic.png',
       'fig3_flowchart.pdf': 'fig3_flowchart.png', 'fig4_sequence.pdf': 'fig4_sequence.png',
       'fig5_enhanced.pdf': 'fig5_enhanced.png', 'fig6_prototype.jpg': 'fig6_prototype.jpg'}

def brace_arg(s, start):
    """return content of {...} starting at s[start]=='{' and index after it."""
    assert s[start] == '{'
    depth, i = 0, start
    while True:
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0: return s[start + 1:i], i + 1
        i += 1

def repl_figures(s):
    out, pos = [], 0
    pat = re.compile(r'\\begin\{(figure\*?)\}(\[[^\]]*\])?')
    while True:
        m = pat.search(s, pos)
        if not m: out.append(s[pos:]); break
        env = m.group(1)
        end = s.index(r'\end{%s}' % env, m.end())
        block = s[m.end():end]
        f = re.search(r'\\includegraphics(\[[^\]]*\])?\{figs/([^}]+)\}', block).group(2)
        ci = block.index(r'\caption'); cap, _ = brace_arg(block, ci + len(r'\caption'))
        lab = re.search(r'\\label\{([^}]+)\}', block).group(1)
        wide = 'WIDE' if env.endswith('*') else 'COL'
        out.append(s[pos:m.start()])
        out.append('\n\nFIGMARK %s %s\n\nFIGCAPMARK Fig.~%s.\\ \\ %s\n\n' % (PNG[f], wide, labels[lab], cap))
        pos = end + len(r'\end{%s}' % env)
    return ''.join(out)
body = repl_figures(body)

a = body.index(r'\begin{algorithm}'); b = body.index(r'\end{algorithm}') + len(r'\end{algorithm}')
body = body[:a] + '\n\nFIGMARK alg.png COL\n\n' + body[b:]

# ---------- tables -> caption markers + tabular
def repl_tables(s):
    out, pos = [], 0
    pat = re.compile(r'\\begin\{(table\*?)\}(\[[^\]]*\])?')
    while True:
        m = pat.search(s, pos)
        if not m: out.append(s[pos:]); break
        env = m.group(1)
        end = s.index(r'\end{%s}' % env, m.end())
        block = s[m.end():end]
        ci = block.index(r'\caption'); cap, _ = brace_arg(block, ci + len(r'\caption'))
        lab = re.search(r'\\label\{([^}]+)\}', block).group(1)
        ta = block.index(r'\begin{tabular}'); tb = block.index(r'\end{tabular}') + len(r'\end{tabular}')
        tab = block[ta:tb]
        spec, _ = brace_arg(tab, len(r'\begin{tabular}'))
        widths = re.findall(r'[Lp]\{([0-9.]+)cm\}', spec)
        tab = re.sub(r'L\{', 'p{', tab).replace('@{}', '')
        wide = 'WIDE' if env.endswith('*') else 'COL'
        out.append(s[pos:m.start()])
        out.append('\n\nTABMARK %s %s %s\n\nTABCAPMARK %s\n\n%s\n\nTABENDMARK\n\n'
                   % (labels[lab], wide, ','.join(widths) or '-', cap, tab))
        pos = end + len(r'\end{%s}' % env)
    return ''.join(out)
body = repl_tables(body)

# ---------- references
a = body.index(r'\begin{thebibliography}'); b = body.index(r'\end{thebibliography}') + len(r'\end{thebibliography}')
bib = body[a:b]
items = re.split(r'\\bibitem\{([^}]+)\}', bib)[1:]
refs = []
for k, txt in zip(items[0::2], items[1::2]):
    txt = txt.replace(r'\end{thebibliography}', '').strip()
    refs.append('REFMARK [%s] %s' % (cites[k], txt))
body = body[:a] + '\n\nREFHEADMARK\n\n' + '\n\n'.join(refs) + '\n\n' + body[b:]

# ---------- sections: manual IEEE numbering
roman = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
sec_i, sub_i = -1, 0
def sec_repl(m):
    global sec_i, sub_i
    kind, star, title = m.group(1), m.group(2), m.group(3)
    if kind == 'section':
        if star:
            return '\n\\section*{%s}' % title
        sec_i += 1; sub_i = 0
        return '\n\\section*{%s.\\ %s}' % (roman[sec_i], title)
    sub_i += 1
    return '\n\\subsection*{%s.\\ %s}' % (chr(64 + sub_i), title)
body = re.sub(r'\\(section|subsection)(\*?)\{([^}]*)\}', sec_repl, body)

# ---------- references inside text
def cite_repl(m):
    nums = sorted(int(cites[k.strip()]) for k in m.group(1).split(','))
    # compress consecutive runs: [1]--[3]
    groups, run = [], [nums[0]]
    for n in nums[1:]:
        if n == run[-1] + 1: run.append(n)
        else: groups.append(run); run = [n]
    groups.append(run)
    parts = ['[%d]--[%d]' % (g[0], g[-1]) if len(g) > 2 else ', '.join('[%d]' % x for x in g) for g in groups]
    return ', '.join(parts)
body = re.sub(r'~?\\cite\{([^}]+)\}', lambda m: ('~' if m.group(0).startswith('~') else '') + cite_repl(m), body)
body = re.sub(r'\\eqref\{([^}]+)\}', lambda m: '(%s)' % labels[m.group(1)], body)
body = re.sub(r'\\ref\{([^}]+)\}', lambda m: labels[m.group(1)], body)
body = re.sub(r'\\label\{[^}]+\}', '', body)
body = re.sub(r'\s*\n\s*\n\s*\\end\{equation\}', lambda m: '\n' + chr(92) + 'end{equation}', body)

# ---------- misc macros
body = re.sub(r'\\verify\[([^\]]*)\]', r'\\textbf{[VERIFY\1]}', body)
body = body.replace(r'\verify', r'\textbf{[VERIFY]}')
body = body.replace(r'\meas', r'\textit{[meas.]}')
body = body.replace(r'\textmu ', 'µ').replace(r'\textmu', 'µ')
for junk in [r'\centering', r'\scriptsize', r'\footnotesize']:
    body = body.replace(junk, '')
body = re.sub(r'\\setlength\{\\tabcolsep\}\{[^}]*\}', '', body)
body = re.sub(r'^%.*$', '', body, flags=re.M)

body = body.replace('V_k = {}&', 'V_k = &')
body = re.sub(r'\$\\mathtt\{([^}]*)\}\$', lambda m: chr(92)+'texttt{'+m.group(1)+'}', body)
a_ = body.index(r'T_{\mathrm{e2e}} &= \underbrace')
b_ = body.index(r'\end{aligned}', a_)
body = body[:a_] + r"""T_{\mathrm{e2e}} = & T_{\mathrm{in}}+T_{\mathrm{fix}}+T_{\mathrm{proc}}+T_{\mathrm{tx}}+T_{\mathrm{net}},\\
& T_{\mathrm{in}}=t_1-t_0,\; T_{\mathrm{fix}}=t_2-t_1,\; T_{\mathrm{proc}}=t_3-t_2,\\
& T_{\mathrm{tx}}=t_4-t_3,\; T_{\mathrm{net}}=t_5-t_4
""" + body[b_:]
def _gather(m):
    inner = m.group(1).replace('&', '')
    return r'\begin{gathered}' + inner + r'\end{gathered}'
body = re.sub(r'\\begin\{aligned\}(.*?)\\end\{aligned\}', _gather, body, flags=re.S)
out = r'''\documentclass{article}
\usepackage{amsmath,amssymb}
\usepackage{booktabs}
\begin{document}
''' + body + '\n\\end{document}\n'
open(OUT, 'w').write(out)
print('ok', len(refs), 'refs')
