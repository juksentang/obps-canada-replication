"""Shared figure style: SciencePlots 'science' style (Computer Modern via LaTeX, matching the manuscript text)
with a colour-blind-safe two-hue palette and thin, recessive chrome. Import and call apply() before plotting; wrap any label
containing unicode symbols or LaTeX-special characters with tx()."""
import re, matplotlib
import matplotlib.pyplot as plt
import scienceplots  # noqa: F401  (registers the styles)
BLUE, ORANGE, MUTED, INK, SEC, GRID = '#2a78d6', '#eb6834', '#898781', '#0b0b0b', '#52514e', '#e6e5e0'
def apply(base_fontsize=8):
    plt.style.use(['science'])
    matplotlib.rcParams.update({
        'font.size': base_fontsize, 'axes.labelsize': base_fontsize, 'axes.titlesize': base_fontsize + 1,
        'xtick.labelsize': base_fontsize - 0.5, 'ytick.labelsize': base_fontsize - 0.5, 'legend.fontsize': base_fontsize - 0.5,
        'axes.edgecolor': '#9a9994', 'axes.linewidth': 0.6, 'xtick.color': SEC, 'ytick.color': SEC, 'axes.labelcolor': SEC,
        'xtick.direction': 'out', 'ytick.direction': 'out', 'xtick.top': False, 'ytick.right': False, 'xtick.minor.visible': False, 'ytick.minor.visible': False,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': False, 'grid.color': GRID, 'grid.linewidth': 0.5,
        'lines.linewidth': 1.4, 'lines.markersize': 5, 'legend.frameon': False, 'figure.dpi': 150, 'savefig.dpi': 300,
        'text.latex.preamble': r'\usepackage{amsmath}\usepackage{amssymb}\usepackage{siunitx}',
    })
def tx(s):
    """Make a plain-text label safe for LaTeX rendering. Existing $...$ math is kept; a $ followed by a digit is treated as currency."""
    if s is None: return s
    s = re.sub(r'\$(?=[\dM])', '\u0001', s)
    parts = re.split(r'(\$[^$]*\$)', s); out = []
    for i, p in enumerate(parts):
        if i % 2 == 1: out.append(p); continue
        p = (p.replace('%', r'\%').replace('&', r'\&').replace('_', r'\_').replace('#', r'\#')
               .replace('×', r'$\times$').replace('≤', r'$\leq$').replace('≥', r'$\geq$').replace('−', r'$-$').replace('–', '--').replace('—', '---')
               .replace('\u0001M', r'\$M').replace('\u0001', r'\$').replace('tCO2e', r'tCO$_2$e'))
        out.append(p)
    return ''.join(out)
def panel_title(ax, letter, text, **kw):
    ax.set_title(r'\textbf{' + letter + r'}\;\;' + tx(text), loc='left', color=INK, pad=5, **kw)
