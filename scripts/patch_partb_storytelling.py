#!/usr/bin/env python3
"""Patch AAL notebook: business markdown, visuals, seasonality benchmark."""
import json
from pathlib import Path

NB_PATH = Path("/workspace/AAL_First_Pay_Default_2026.ipynb")

BUSINESS_GUIDE_CELLS = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Business guide — recommended story arc (10 min)\n\n"
            "Use this order when presenting Part B to a business audience:\n\n"
            "1. **Cohort table (A)** — \"Where is FPD by origination month?\" (levels and trends).\n"
            "2. **Vintage visuals (G)** — FPD trend with uncertainty, volume context, tier heatmap.\n"
            "3. **Decomposition waterfall (G)** — \"Was the move mix, performance, or both?\"\n"
            "4. **PSI heatmap (G)** — \"Did we change *who* we booked vs the reference month?\"\n"
            "5. **Seasonality benchmark (H)** — YoY same-calendar-month FPD (2026 vs 2025) when available.\n"
            "6. **Logistic regression (F)** — \"After controlling for tier, is any vintage month still elevated?\" "
            "(supporting evidence, not the headline).\n"
            "7. **Maturity footnote** — Rates use loans where first-pay outcome is observable "
            "(30 days after first principal payment date, or early full payment).\n"
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Business guide — PSI (Population Stability Index)\n\n"
            "**Question it answers:** Did the **mix** of loans we booked change compared to our baseline month?\n\n"
            "PSI compares the **distribution** of a factor (e.g. risk tier, PTI, NDI) between a **reference vintage** "
            "(e.g. January 2026) and each later vintage. It does **not** measure whether FPD went up or down — only "
            "whether the **population** shifted.\n\n"
            "| PSI | Typical interpretation |\n"
            "|-----|------------------------|\n"
            "| ≤ 0.10 | **Stable** — composition similar to reference |\n"
            "| 0.10 – 0.25 | **Moderate shift** — investigate with Risk/Policy |\n"
            "| > 0.25 | **Material shift** — treat as strategy/market change |\n\n"
            "**One-liner:** *PSI flags whether vintage FPD moves might be driven by **who we approved**, "
            "before blaming **how they performed**.*\n"
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Business guide — FPD decomposition (mix, rate, interaction)\n\n"
            "**Question it answers:** FPD changed from month A to month B — was that because we **booked different tiers** "
            "(mix), because **within-tier performance** changed (rate), or both?\n\n"
            "Segments use **risk tier** (`borrower_origination_risk_group`).\n\n"
            "| Term | Business meaning |\n"
            "|------|------------------|\n"
            "| **Mix effect** | If within-tier FPD rates stayed like month A but we used month B's tier mix, "
            "how much would portfolio FPD move? → **composition / approval mix** |\n"
            "| **Rate effect** | If tier mix stayed like month A but within-tier FPD looked like month B, "
            "how much would FPD move? → **credit performance / execution** |\n"
            "| **Interaction** | Remaining piece when mix and rates move together (often small) |\n\n"
            "**Basis points (bps):** 1 bp = **0.01 percentage point** on the FPD rate "
            "(e.g. 0.70% → 1.20% = +50 bps).\n\n"
            "**Note:** Decomposition compares **two vintages you select** (e.g. latest vs prior month). "
            "The cohort table answers \"how hot is July vs the year\"; decomposition answers \"why did we move MoM\".\n"
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Business guide — Logistic regression (vintage + tier)\n\n"
            "The model estimates: **FPD ~ vintage month + risk tier** (mature loans). "
            "One vintage and one tier are **reference** categories; other rows are **vs that baseline**, "
            "holding the other factor in the model.\n\n"
            "### Coefficients (log-odds scale)\n"
            "Coefficients are **not** percent FPD. For executives, use **odds ratios** = e^(coefficient):\n\n"
            "- Coef **0.05** → odds ratio ~**1.05** (~5% higher **odds** of FPD vs reference)\n"
            "- Coef **0.53** → odds ratio ~**1.70** (~70% higher **odds** of FPD vs reference)\n\n"
            "FPD is rare (~1%), so a large odds ratio is **not** the same as \"FPD rate up 70%\". "
            "Always pair with **cohort FPD %** in section A.\n\n"
            "### Other columns\n"
            "| Column | Plain language |\n"
            "|--------|----------------|\n"
            "| **Std. Err.** | Uncertainty in the estimate (smaller = more precise) |\n"
            "| **z** | Signal-to-noise; larger |z| → more evidence the effect isn't zero |\n"
            "| **P > \\|z\\|** | If true effect were zero, how often we'd see this by chance; "
            "**< 0.05** → statistically meaningful at 5% |\n"
            "| **[0.025, 0.975]** | 95% confidence interval; if it **crosses 0**, not significant at 5% |\n"
        ],
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Business guide — Seasonality & YoY benchmarks\n\n"
            "**Industry practice:** Monthly vintage FPD is often **seasonal** (tax season, holidays, marketing). "
            "Comparing July 2026 only to January–June 2026 can confuse **calendar effects** with **true deterioration**.\n\n"
            "**Leading approaches (this notebook):**\n\n"
            "1. **Primary monitoring cohort (`df`)** — `MODEL_ERA_START` (2026+) for current-era policy and scorecard.\n"
            "2. **Seasonality benchmark (`df_seasonal`)** — pull from **2025-01-01 through YTD**; "
            "compute **same calendar month YoY** (e.g. Jul-25 vs Jul-26) on mature loans.\n"
            "3. **PSI / decomposition** — still vs a **2026 reference** within the current era unless policy changed.\n\n"
            "**Caveats:** YoY is valid only if **product, policy, and score** are comparable across years. "
            "If 2026 is a new model era, treat 2025 as **context**, not a control, and prefer **month-of-year fixed effects** "
            "in multivariate models for formal testing (future enhancement).\n"
        ],
    },
]

VIZ_HELPERS = '''
def wilson_ci(successes, n, z=1.96):
    """Wilson score interval for a binomial proportion."""
    if n is None or n <= 0:
        return (np.nan, np.nan)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z / denom) * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0.0, center - margin), min(1.0, center + margin))

def cohort_table_with_ci(df_mon, target):
    """Build cohort metrics with Wilson 95% CI on mature-loan FPD rate."""
    rows = []
    for v in sorted(df_mon['_vintage'].unique()):
        g_all = df_mon[df_mon['_vintage'] == v]
        g_mat = g_all[g_all['is_mature_fpd']]
        n_mat = len(g_mat)
        fpd = int(g_mat[target].sum()) if n_mat else 0
        rate = g_mat[target].mean() if n_mat else np.nan
        lo, hi = wilson_ci(fpd, n_mat) if n_mat else (np.nan, np.nan)
        rows.append({
            'vintage_month': _period_to_str(v),
            'loan_count': len(g_all),
            'mature_loan_count': n_mat,
            'pct_mature': g_all['is_mature_fpd'].mean(),
            'fpd_count': fpd,
            'fpd_rate': rate,
            'fpd_rate_ci_low': lo,
            'fpd_rate_ci_high': hi,
        })
    return pd.DataFrame(rows)

def plot_vintage_fpd_trend(cohort_ci, title='Vintage FPD rate (mature loans, 95% CI)'):
    plot_df = cohort_ci.dropna(subset=['fpd_rate']).copy()
    if plot_df.empty:
        print('Vintage FPD trend skipped — no mature vintages.')
        return
    plot_df = plot_df.sort_values('vintage_month')
    x = np.arange(len(plot_df))
    y = plot_df['fpd_rate'] * 100
    ylo = plot_df['fpd_rate_ci_low'] * 100
    yhi = plot_df['fpd_rate_ci_high'] * 100
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.errorbar(x, y, yerr=[y - ylo, yhi - y], fmt='o-', capsize=4, color='#1f77b4', label='FPD %')
    ax1.set_xticks(x)
    ax1.set_xticklabels(plot_df['vintage_month'], rotation=45, ha='right')
    ax1.set_ylabel('FPD rate (%)')
    ax1.set_title(title)
    ax2 = ax1.twinx()
    ax2.bar(x, plot_df['loan_count'], alpha=0.2, color='gray', label='Loan count (all)')
    ax2.set_ylabel('Loan count')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    plt.tight_layout()
    plt.show()

def plot_tier_fpd_heatmap(tier_fpd_rates, title='Within-tier FPD rate by vintage (mature loans)'):
    if tier_fpd_rates is None or tier_fpd_rates.empty:
        print('Tier FPD heatmap skipped.')
        return
    data = (tier_fpd_rates.T * 100).round(3)
    fig, ax = plt.subplots(figsize=(14, max(4, 0.35 * data.shape[0])))
    sns.heatmap(data, annot=True, fmt='.2f', cmap='YlOrRd', ax=ax, cbar_kws={'label': 'FPD %'})
    ax.set_title(title)
    ax.set_xlabel('Vintage month')
    ax.set_ylabel('Risk tier')
    plt.tight_layout()
    plt.show()

def plot_psi_heatmap(psi_table, title='PSI vs reference vintage'):
    if psi_table is None or psi_table.empty:
        print('PSI heatmap skipped.')
        return
    pivot = psi_table.pivot(index='feature', columns='vintage_month', values='psi')
    fig, ax = plt.subplots(figsize=(12, max(4, 0.4 * pivot.shape[0])))
    sns.heatmap(pivot, annot=True, fmt='.3f', cmap='Blues', ax=ax, cbar_kws={'label': 'PSI'})
    ax.set_title(title)
    plt.tight_layout()
    plt.show()

def plot_decomposition_waterfall(decomp, label='Portfolio FPD change'):
    if decomp is None:
        print('Decomposition waterfall skipped.')
        return
    mix_bps = decomp['mix_effect'] * 10000
    rate_bps = decomp['rate_effect'] * 10000
    interact_bps = decomp['interaction'] * 10000
    total_bps = decomp['delta_fpd'] * 10000
    steps = ['Start\\n(prior FPD)', 'Mix', 'Rate', 'Interaction', 'End\\n(current FPD)']
    start = decomp['fpd_a'] * 10000
    vals = [0, mix_bps, rate_bps, interact_bps, 0]
    cumulative = [start, start + mix_bps, start + mix_bps + rate_bps, start + mix_bps + rate_bps + interact_bps, start + total_bps]
    fig, ax = plt.subplots(figsize=(9, 5))
    for i in range(1, 4):
        ax.bar(i, vals[i], bottom=cumulative[i - 1] if vals[i] >= 0 else cumulative[i], color=['#2ca02c', '#d62728', '#9467bd'][i - 1])
    ax.plot([0, 4], [start, cumulative[-1]], color='black', linestyle='--', alpha=0.4)
    ax.set_xticks(range(5))
    ax.set_xticklabels(steps)
    ax.set_ylabel('FPD (bps)')
    ax.set_title(f'{label}: total {total_bps:+.1f} bps')
    plt.tight_layout()
    plt.show()

def build_executive_scorecard(cohort_ci, decomp_mom, psi_table, latest_v, prior_v, ref_vintage):
    latest_row = cohort_ci[cohort_ci['vintage_month'] == _period_to_str(latest_v)].head(1)
    prior_row = cohort_ci[cohort_ci['vintage_month'] == _period_to_str(prior_v)].head(1) if prior_v is not None else pd.DataFrame()
    max_psi = psi_table['psi'].max() if psi_table is not None and len(psi_table) else np.nan
    mom_bps = decomp_mom['delta_fpd'] * 10000 if decomp_mom is not None else np.nan
    rows = [
        {'metric': 'Latest mature vintage', 'value': _period_to_str(latest_v)},
        {'metric': 'Portfolio FPD % (latest mature)', 'value': f"{latest_row['fpd_rate'].iloc[0] * 100:.3f}%" if len(latest_row) else 'n/a'},
        {'metric': 'MoM FPD change (bps)', 'value': f"{mom_bps:+.1f}" if pd.notna(mom_bps) else 'n/a'},
        {'metric': '% mature (latest vintage)', 'value': f"{latest_row['pct_mature'].iloc[0] * 100:.1f}%" if len(latest_row) else 'n/a'},
        {'metric': 'Max PSI vs reference', 'value': f"{max_psi:.4f}" if pd.notna(max_psi) else 'n/a'},
        {'metric': 'PSI reference vintage', 'value': _period_to_str(ref_vintage) if ref_vintage is not None else 'n/a'},
    ]
    return pd.DataFrame(rows)

def build_yoy_seasonal_table(df_seasonal_mon, target, tier_col=None):
    """Same calendar-month YoY FPD on mature loans (2026 vs 2025)."""
    tmp = df_seasonal_mon.copy()
    tmp['cal_month'] = tmp['_vintage'].dt.month
    tmp['cal_year'] = tmp['_vintage'].dt.year
    mat = tmp[tmp['is_mature_fpd']]
    agg = mat.groupby(['cal_year', 'cal_month'], observed=True).agg(
        loan_count=(target, 'size'),
        fpd_count=(target, 'sum'),
        fpd_rate=(target, 'mean'),
    ).reset_index()
    p25 = agg[agg['cal_year'] == 2025].rename(columns={
        'loan_count': 'loans_2025', 'fpd_count': 'fpd_2025', 'fpd_rate': 'fpd_rate_2025'
    })
    p26 = agg[agg['cal_year'] == 2026].rename(columns={
        'loan_count': 'loans_2026', 'fpd_count': 'fpd_2026', 'fpd_rate': 'fpd_rate_2026'
    })
    yoy = p25.merge(p26, on='cal_month', how='inner')
    if yoy.empty:
        return yoy
    yoy['month_name'] = yoy['cal_month'].apply(lambda m: pd.Timestamp(2000, int(m), 1).strftime('%b'))
    yoy['fpd_bps_yoy'] = (yoy['fpd_rate_2026'] - yoy['fpd_rate_2025']) * 10000
    return yoy.sort_values('cal_month')

def plot_yoy_seasonal(yoy_df, title='Same-month YoY FPD (2026 vs 2025, mature loans)'):
    if yoy_df is None or yoy_df.empty:
        print('YoY seasonal chart skipped — no overlapping mature months.')
        return
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(yoy_df))
    ax.bar(x - 0.2, yoy_df['fpd_rate_2025'] * 100, width=0.4, label='2025', color='#aec7e8')
    ax.bar(x + 0.2, yoy_df['fpd_rate_2026'] * 100, width=0.4, label='2026', color='#1f77b4')
    ax.set_xticks(x)
    ax.set_xticklabels(yoy_df['month_name'])
    ax.set_ylabel('FPD rate (%)')
    ax.set_title(title)
    ax.legend()
    plt.tight_layout()
    plt.show()
'''

SEASONAL_PULL_CELL = {
    "cell_type": "code",
    "metadata": {},
    "source": [
        "# Seasonality benchmark pull (2025 + 2026 YTD) — separate from current-era df\n"
        "if RUN_SEASONALITY_BENCHMARK:\n"
        "    _seasonal_end = SEASONALITY_COMPARISON_END or AS_OF_DATE\n"
        "    sql_seasonal = f\"\"\"\n"
        "    select *\n"
        "    from `ffam-data-platform-loan-ops.report_views.v_aal_early_pay_default`\n"
        "    where DATE(loan_vintage_month) >= DATE('{SEASONALITY_COMPARISON_START}')\n"
        "      and DATE(loan_vintage_month) <= DATE('{_seasonal_end}')\n"
        "    \"\"\"\n"
        "    df_seasonal = pandas_gbq.read_gbq(\n"
        "        sql_seasonal,\n"
        "        project_id='ffn-dw-bigquery-prd',\n"
        "        credentials=credentials,\n"
        "        dialect='standard',\n"
        "    )\n"
        "    print(\n"
        "        f\"Seasonal benchmark: {len(df_seasonal):,} rows | \"\n"
        "        f\"{SEASONALITY_COMPARISON_START} to {_seasonal_end.date()}\"\n"
        "    )\n"
        "else:\n"
        "    df_seasonal = None\n"
        "    print('RUN_SEASONALITY_BENCHMARK=False — skipping df_seasonal pull.')\n"
    ],
}

STORYTELLING_CELL = {
    "cell_type": "code",
    "metadata": {},
    "source": [
        "# --- G. Executive storytelling visuals (run after Part B analytics cell above) ---\n"
        "if not RUN_VINTAGE_MONITORING:\n"
        "    print('RUN_VINTAGE_MONITORING=False — skip storytelling visuals.')\n"
        "elif 'df_mon' not in globals() or 'cohort_table' not in globals():\n"
        "    raise RuntimeError('Run the Part B analytics cell first (creates df_mon, cohort_table, etc.).')\n"
        "else:\n"
        "    cohort_ci = cohort_table_with_ci(df_mon, TARGET)\n"
        "    print('### G1. Executive scorecard')\n"
        "    _prior_v = mature_vintages[-2] if len(mature_vintages) >= 2 else None\n"
        "    _latest_v = mature_vintages[-1] if len(mature_vintages) else None\n"
        "    scorecard = build_executive_scorecard(\n"
        "        cohort_ci, globals().get('decomp_mom'), globals().get('psi_table'),\n"
        "        _latest_v, _prior_v, globals().get('ref_vintage'),\n"
        "    )\n"
        "    display(scorecard)\n\n"
        "    print('### G2. Vintage FPD trend + volume')\n"
        "    plot_vintage_fpd_trend(cohort_ci)\n\n"
        "    print('### G3. Within-tier FPD heatmap')\n"
        "    if 'tier_fpd_rates' in globals():\n"
        "        plot_tier_fpd_heatmap(tier_fpd_rates)\n"
        "    else:\n"
        "        print('tier_fpd_rates not found — run Part B analytics section B first.')\n\n"
        "    print('### G4. PSI heatmap')\n"
        "    plot_psi_heatmap(globals().get('psi_table'))\n\n"
        "    print('### G5. Decomposition waterfall (latest vs prior mature month)')\n"
        "    if globals().get('decomp_mom') is not None:\n"
        "        plot_decomposition_waterfall(\n"
        "            decomp_mom,\n"
        "            label=f\"{_period_to_str(_prior_v)} → {_period_to_str(_latest_v)}\" if _prior_v else 'MoM',\n"
        "        )\n"
        "    else:\n"
        "        print('Need >=2 mature vintages for decomposition waterfall.')\n\n"
        "    if 'tier_fpd_rates' in globals() and tier_fpd_rates is not None and not tier_fpd_rates.empty:\n"
        "        print('### G6. Tier small multiples (FPD by vintage)')\n"
        "        tiers = tier_fpd_rates.columns[:12]\n"
        "        n = len(tiers)\n"
        "        ncol = 4\n"
        "        nrow = int(np.ceil(n / ncol))\n"
        "        fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 2.8 * nrow), sharex=True)\n"
        "        axes = np.array(axes).reshape(-1)\n"
        "        for i, t in enumerate(tiers):\n"
        "            ax = axes[i]\n"
        "            tier_fpd_rates[t].dropna().plot(ax=ax, marker='o')\n"
        "            ax.set_title(f'Tier {t}')\n"
        "            ax.set_ylabel('FPD rate')\n"
        "        for j in range(i + 1, len(axes)):\n"
        "            axes[j].axis('off')\n"
        "        plt.suptitle('Within-tier FPD by vintage (mature loans)', y=1.02)\n"
        "        plt.tight_layout()\n"
        "        plt.show()\n\n"
        "# --- H. Seasonality benchmark (YoY same calendar month) ---\n"
        "if RUN_VINTAGE_MONITORING and RUN_SEASONALITY_BENCHMARK and df_seasonal is not None:\n"
        "    print('### H. Seasonality benchmark (df_seasonal)')\n"
        "    df_seas_mon = df_seasonal.copy()\n"
        "    df_seas_mon['_vintage'] = _vintage_period(df_seas_mon[VINTAGE_COL])\n"
        "    df_seas_mon = add_fpd_maturity(\n"
        "        df_seas_mon,\n"
        "        AS_OF_DATE,\n"
        "        FPD_DAYS_AFTER_FIRST_PRINCIPAL_DUE,\n"
        "        FIRST_PRINCIPAL_PAYMENT_DATE_COL,\n"
        "        ORIGINATION_PAYMENT_AMOUNT_COL,\n"
        "        TOTAL_OVERALL_PAYMENT_COL,\n"
        "    )\n"
        "    yoy_table = build_yoy_seasonal_table(df_seas_mon, TARGET)\n"
        "    if yoy_table.empty:\n"
        "        print('No overlapping mature 2025/2026 calendar months yet.')\n"
        "    else:\n"
        "        display(yoy_table.assign(\n"
        "            fpd_rate_2025=lambda d: (d['fpd_rate_2025'] * 100).round(3),\n"
        "            fpd_rate_2026=lambda d: (d['fpd_rate_2026'] * 100).round(3),\n"
        "            fpd_bps_yoy=lambda d: d['fpd_bps_yoy'].round(1),\n"
        "        )[['month_name', 'loans_2025', 'loans_2026', 'fpd_rate_2025', 'fpd_rate_2026', 'fpd_bps_yoy']])\n"
        "        plot_yoy_seasonal(yoy_table)\n"
        "elif RUN_SEASONALITY_BENCHMARK:\n"
        "    print('### H. Seasonality skipped — df_seasonal not loaded.')\n"
    ],
}


def find_cell_index(nb, substring):
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if substring in src:
            return i
    raise ValueError(f"Cell not found: {substring!r}")


def main():
    nb = json.loads(NB_PATH.read_text())

    # Config cell
    cfg_i = find_cell_index(nb, "FPD_DAYS_AFTER_FIRST_PRINCIPAL_DUE")
    cfg = "".join(nb["cells"][cfg_i]["source"])
    if "RUN_SEASONALITY_BENCHMARK" not in cfg:
        cfg = cfg.replace(
            "AS_OF_DATE = pd.Timestamp.today().normalize()",
            "RUN_SEASONALITY_BENCHMARK = True  # pull df_seasonal for YoY same-month benchmarks\n"
            "SEASONALITY_COMPARISON_START = '2025-01-01'  # 2025 + 2026 YTD\n"
            "SEASONALITY_COMPARISON_END = None  # None -> AS_OF_DATE\n"
            "AS_OF_DATE = pd.Timestamp.today().normalize()",
        )
        cfg = cfg.replace(
            'f"AS_OF_DATE={AS_OF_DATE.date()}"',
            'f"RUN_SEASONALITY_BENCHMARK={RUN_SEASONALITY_BENCHMARK}, "\n'
            '    f"AS_OF_DATE={AS_OF_DATE.date()}"',
        )
        nb["cells"][cfg_i]["source"] = [cfg]

    # Part B header — mention G/H sections
    hdr_i = find_cell_index(nb, "# Part B — Vintage month FPD monitoring")
    hdr = "".join(nb["cells"][hdr_i]["source"])
    if "**Sections:**" in hdr and "storytelling visuals" not in hdr:
        hdr = hdr.replace(
            "**Sections:** Run configuration → cohort table",
            "**Sections:** Run configuration → cohort table → **business guides** →",
        ).replace(
            "→ optional multivariate logistic.\n",
            "→ optional multivariate logistic → **executive visuals (G)** → **seasonality YoY (H)**.\n",
        )
        nb["cells"][hdr_i]["source"] = [hdr]

    # Seasonal pull after main GBQ cell
    gbq_i = find_cell_index(nb, "where DATE(loan_vintage_month) >= DATE('{MODEL_ERA_START}')")
    if not any("df_seasonal" in "".join(c.get("source", [])) for c in nb["cells"]):
        nb["cells"].insert(gbq_i + 1, SEASONAL_PULL_CELL)

    # Business guides before helper defs
    def_i = find_cell_index(nb, "def _vintage_period")
    if not any("Business guide — PSI" in "".join(c.get("source", [])) for c in nb["cells"]):
        for offset, cell in enumerate(BUSINESS_GUIDE_CELLS):
            nb["cells"].insert(def_i + offset, cell)

    # Append viz helpers to defs cell
    def_i = find_cell_index(nb, "def _vintage_period")
    def_src = "".join(nb["cells"][def_i]["source"])
    if "def wilson_ci" not in def_src:
        nb["cells"][def_i]["source"] = [def_src + "\n" + VIZ_HELPERS]

    # Patch analytics cell: expose decomp_mom, ref_vintage, tier_fpd_rates for storytelling cell
    ana_i = find_cell_index(nb, "if not RUN_VINTAGE_MONITORING:")
    ana = "".join(nb["cells"][ana_i]["source"])
    if "decomp_mom = None" not in ana:
        ana = ana.replace(
            "    mature_vintages = sorted(df_mature['_vintage'].unique())\n\n    if PSI_REFERENCE_VINTAGE:",
            "    mature_vintages = sorted(df_mature['_vintage'].unique())\n"
            "    decomp_mom = None\n"
            "    decomp_ref = None\n"
            "    ref_vintage = None\n"
            "    tier_fpd_rates = None\n"
            "    psi_table = pd.DataFrame()\n\n    if PSI_REFERENCE_VINTAGE:",
        )
    if "globals()" not in ana and "decomp_mom = fpd_decomposition" in ana:
        pass  # variables already in cell scope for next cell in notebook

    # Ensure tier_fpd_rates assigned in section B (already is)
    nb["cells"][ana_i]["source"] = [ana]

    # Insert storytelling cell after analytics if missing
    if not any("### G1. Executive scorecard" in "".join(c.get("source", [])) for c in nb["cells"]):
        ana_i = find_cell_index(nb, "if not RUN_VINTAGE_MONITORING:")
        nb["cells"].insert(ana_i + 1, STORYTELLING_CELL)
        nb["cells"].insert(
            ana_i + 1,
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Part B — Executive visuals & seasonality (G / H)\n\n"
                    "Run the cell below **after** the Part B analytics cell. "
                    "Produces scorecard, FPD trend with 95% CI, tier heatmap, PSI heatmap, "
                    "decomposition waterfall, tier small multiples, and **YoY same-month** table/chart from `df_seasonal`.\n"
                ],
            },
        )

    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print("Patched", NB_PATH, "cells:", len(nb["cells"]))


if __name__ == "__main__":
    main()
