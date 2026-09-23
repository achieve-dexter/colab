import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "AAL_First_Pay_Default_2026.ipynb"
nb = json.loads(p.read_text(encoding="utf-8"))


def join(c):
    return "".join(c.get("source", []))


def setc(c, t):
    c["source"] = [ln + "\n" for ln in t.split("\n")]
    if c["source"] and c["source"][-1] == "\n":
        c["source"].pop()


HELPER = """

def _pct_mature_fraction(val):
    \"\"\"Normalize pct_mature to 0-1 whether stored as fraction or percent.\"\"\"
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return np.nan
    v = float(val)
    return v / 100.0 if v > 1.5 else v


def _vintage_months_mature_enough(cohort_table, min_fraction=None):
    min_fraction = min_fraction if min_fraction is not None else globals().get('PSI_MIN_PCT_MATURE', 0.80)
    if cohort_table is None or cohort_table.empty:
        return set()
    ok = cohort_table['pct_mature'].map(_pct_mature_fraction) >= float(min_fraction)
    return set(cohort_table.loc[ok, 'vintage_month'].astype(str))

"""

for c in nb["cells"]:
    s = join(c)
    if "def _cohort_row_for_vintage" in s and "_pct_mature_fraction" not in s:
        s = s.replace("def _cohort_row_for_vintage", HELPER + "def _cohort_row_for_vintage")
        setc(c, s)

REPLACEMENTS = [
    (
        "        pct_m = row['pct_mature'].iloc[0] if len(row) else 0\n        fpd = row['fpd_rate'].iloc[0] if len(row) else np.nan\n        lines.append(f\"### {_period_to_str(v)} ({pct_m:.0f}% mature for FPD)\")\n        if pd.isna(fpd) or pct_m < 80:",
        "        pct_m = _pct_mature_fraction(row['pct_mature'].iloc[0]) if len(row) else 0.0\n        fpd = row['fpd_rate'].iloc[0] if len(row) else np.nan\n        lines.append(f\"### {_period_to_str(v)} ({pct_m * 100:.0f}% mature for FPD)\")\n        if pd.isna(fpd) or pct_m < globals().get('PSI_MIN_PCT_MATURE', 0.80):",
    ),
    (
        "        pct_mature = row['pct_mature'].iloc[0] if len(row) else np.nan\n",
        "        pct_mature = _pct_mature_fraction(row['pct_mature'].iloc[0]) if len(row) else np.nan\n",
    ),
    (
        "                'value': f\"{pct_mature:.1f}%\" if pd.notna(pct_mature) else 'n/a',\n                'policy_status': _rag_mature_pct(pct_mature / 100 if pd.notna(pct_mature) else np.nan, g_mat, a_mat),",
        "                'value': f\"{pct_mature * 100:.1f}%\" if pd.notna(pct_mature) else 'n/a',\n                'policy_status': _rag_mature_pct(pct_mature if pd.notna(pct_mature) else np.nan, g_mat, a_mat),",
    ),
    (
        "    pct_m = plot_df['pct_mature'].fillna(0).astype(float)\n    ci_ok = pct_m >= float(min_pct)",
        "    pct_m = plot_df['pct_mature'].map(_pct_mature_fraction).fillna(0).astype(float)\n    ci_ok = pct_m >= float(min_pct)",
    ),
    (
        "        cohort_table.loc[cohort_table['pct_mature'] >= _psi_min_mature * 100, 'vintage_month'].astype(str)",
        "        cohort_table.loc[cohort_table['pct_mature'].map(_pct_mature_fraction) >= _psi_min_mature, 'vintage_month'].astype(str)",
    ),
]

for c in nb["cells"]:
    s = join(c)
    orig = s
    for a, b in REPLACEMENTS:
        s = s.replace(a, b)
    if s != orig:
        setc(c, s)

for c in nb["cells"]:
    s = join(c)
    if "def plot_vintage_fpd_trend" in s and "y_plot = y.copy()" not in s:
        s = s.replace(
            "    y = plot_df['fpd_rate'].astype(float) * 100\n",
            "    y = plot_df['fpd_rate'].astype(float) * 100\n    y_plot = y.copy()\n",
        )
        s = s.replace(
            "        ax1.plot(x[ci_ok], y[ci_ok], 'o-', color='#1f77b4', label='FPD % (mature enough for CI)')\n",
            "        ax1.plot(x[ci_ok], y_plot[ci_ok], 'o-', color='#1f77b4', label='FPD % (mature enough for CI)')\n",
        )
        s = s.replace(
            "    if (~ci_ok).any():\n        ax1.plot(\n            x[~ci_ok],\n            y[~ci_ok],\n",
            "    if (~ci_ok).any():\n        y_plot[~ci_ok] = np.nan\n        ax1.plot(\n            x[~ci_ok],\n            y_plot[~ci_ok],\n",
        )
        setc(c, s)

for c in nb["cells"]:
    s = join(c)
    if "### G6. Tier small multiples" in s and "MaxNLocator" not in s:
        s = s.replace(
            "        fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 2.8 * nrow), sharex=True)\n",
            "        from matplotlib.ticker import MaxNLocator\n        fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3.2 * nrow), sharex=True)\n",
        )
        s = s.replace(
            "        x_pos = np.arange(len(tier_fpd_rates.index))\n        x_labels = [str(c) for c in tier_fpd_rates.index]\n",
            "        _ok_v = _vintage_months_mature_enough(cohort_table, PSI_MIN_PCT_MATURE)\n        tier_plot = tier_fpd_rates.loc[[i for i in tier_fpd_rates.index if str(i) in _ok_v]]\n        if tier_plot.empty:\n            tier_plot = tier_fpd_rates\n        x_pos = np.arange(len(tier_plot.index))\n        x_labels = [str(c) for c in tier_plot.index]\n",
        )
        s = s.replace(
            "            ax.plot(x_pos, tier_fpd_rates[t].values, marker='o', markersize=4)\n",
            "            ax.plot(x_pos, tier_plot[t].values, marker='o', markersize=4)\n",
        )
        s = s.replace(
            "            ax.set_xticks(range(len(x_labels)))\n            ax.set_xticklabels(x_labels, rotation=60, ha='right', fontsize=7)\n",
            "            ax.set_xticks(x_pos)\n            ax.set_xticklabels(x_labels, rotation=90, ha='center', fontsize=6)\n            ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))\n",
        )
        setc(c, s)

for c in nb["cells"]:
    s = join(c)
    if "RUN_VINTAGE_MONITORING = True" in s and "PART_B_NOTEBOOK_REV" not in s:
        s = s.replace(
            "print(\n    f\"Config:",
            'PART_B_NOTEBOOK_REV = "2026-09-trailing-monitoring-v2"\nprint(\n    f"Config:',
        )
        old_tail = 'f"AS_OF_DATE={AS_OF_DATE.date()}"\n)'
        new_tail = (
            'f"AS_OF_DATE={AS_OF_DATE.date()}, PART_B_NOTEBOOK_REV={PART_B_NOTEBOOK_REV}, "\n'
            '    f"MONITORING_TRAILING_VINTAGES={MONITORING_TRAILING_VINTAGES}, RUN_MOB_CURVES={RUN_MOB_CURVES}"\n)'
        )
        s = s.replace(old_tail, new_tail)
        setc(c, s)

p.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok")
