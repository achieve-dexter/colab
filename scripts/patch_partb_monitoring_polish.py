"""Patch AAL_First_Pay_Default_2026.ipynb — Part B monitoring polish."""
import json
from pathlib import Path

NB_PATH = Path(__file__).resolve().parents[1] / "AAL_First_Pay_Default_2026.ipynb"


def cell_text(c):
    return "".join(c.get("source", []))


def set_cell_text(c, text):
    c["source"] = [line if line.endswith("\n") else line + "\n" for line in text.split("\n")]
    if c["source"] and c["source"][-1] == "\n":
        c["source"].pop()


def main():
    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))

    # --- Config cell ---
    for c in nb["cells"]:
        s = cell_text(c)
        if "PSI_REFERENCE_VINTAGE = '2026-01'" in s and "RUN_VINTAGE_MONITORING" in s:
            if "MONITORING_TRAILING_VINTAGES" not in s:
                s = s.replace(
                    "PSI_REFERENCE_VINTAGE = '2026-01'  # or None → first full mature vintage\n",
                    "PSI_REFERENCE_VINTAGE = '2026-01'  # baseline month for PSI; None → first full mature vintage\n"
                    "MONITORING_TRAILING_VINTAGES = 3  # emerging risks + scorecard: last N origination months\n"
                    "RUN_MOB_CURVES = False  # True only when a MOB performance dataset is available\n"
                    "MIN_PCT_MATURE_FOR_CI = 0.80  # hide wide CIs on immature vintages (e.g. Sep 2026)\n"
                    "PSI_MIN_PCT_MATURE = 0.80  # exclude immature vintages from PSI heatmap/table\n",
                )
            set_cell_text(c, s)
            break

    helpers = None
    analytics = None
    story = None
    cluster_cell = None
    for i, c in enumerate(nb["cells"]):
        s = cell_text(c)
        if "def plot_vintage_fpd_trend" in s:
            helpers = c
        if "Emerging risks" in s and "RUN_VINTAGE_MONITORING" in s:
            analytics = c
        if "G. Executive storytelling visuals" in s:
            story = c
        if 'CRITICAL - Ultra-High Default Segment' in s:
            cluster_cell = c

    assert helpers is not None
    hs = cell_text(helpers)

    # plot_vintage_fpd_trend
    old_plot = """def plot_vintage_fpd_trend(cohort_ci, title='Vintage FPD rate (mature loans, 95% CI)'):
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
    ax2.set_ylabel('Loan count')"""

    new_plot = """def plot_vintage_fpd_trend(
    cohort_ci,
    title='Vintage FPD rate (mature loans, 95% CI)',
    min_pct_mature_for_ci=None,
):
    min_pct = min_pct_mature_for_ci
    if min_pct is None:
        min_pct = globals().get('MIN_PCT_MATURE_FOR_CI', 0.80)
    plot_df = cohort_ci.copy()
    plot_df = plot_df.sort_values('vintage_month')
    if plot_df.empty:
        print('Vintage FPD trend skipped — no vintages.')
        return
    x = np.arange(len(plot_df))
    y = plot_df['fpd_rate'].astype(float) * 100
    ylo = plot_df['fpd_rate_ci_low'].astype(float) * 100
    yhi = plot_df['fpd_rate_ci_high'].astype(float) * 100
    pct_m = plot_df['pct_mature'].fillna(0).astype(float)
    ci_ok = pct_m >= float(min_pct)
    fig, ax1 = plt.subplots(figsize=(12, 5))
    if ci_ok.any():
        ax1.plot(x[ci_ok], y[ci_ok], 'o-', color='#1f77b4', label='FPD % (mature enough for CI)')
        ax1.errorbar(
            x[ci_ok],
            y[ci_ok],
            yerr=[(y - ylo)[ci_ok], (yhi - y)[ci_ok]],
            fmt='none',
            ecolor='#9ecae1',
            elinewidth=1.5,
            capsize=3,
            alpha=0.45,
        )
    if (~ci_ok).any():
        ax1.plot(
            x[~ci_ok],
            y[~ci_ok],
            'o',
            color='#bdbdbd',
            linestyle='None',
            label='FPD % (immature — CI hidden)',
        )
    ax1.set_xticks(x)
    ax1.set_xticklabels(plot_df['vintage_month'], rotation=45, ha='right')
    ax1.set_ylabel('FPD rate (%)')
    ax1.set_title(title)
    ax1.legend(loc='upper left', fontsize=8)
    ax2 = ax1.twinx()
    ax2.bar(x, plot_df['loan_count'], alpha=0.2, color='gray', label='Loan count (all)')
    ax2.set_ylabel('Loan count')"""

    if old_plot not in hs:
        raise SystemExit('plot_vintage_fpd_trend block not found')
    hs = hs.replace(old_plot, new_plot)

    # Add trailing scorecard + emerging risks helpers before build_executive_scorecard_rag
    insert_anchor = "def build_executive_scorecard_rag("
    if "def build_trailing_vintage_scorecards(" not in hs:
        trailing_helpers = '''

def _cohort_row_for_vintage(cohort_ci, vintage):
    vstr = _period_to_str(vintage)
    return cohort_ci[cohort_ci['vintage_month'] == vstr].head(1)


def _mom_decomp_for_vintage(df_mature, tier_col, target, vintage, prior_vintage):
    if prior_vintage is None:
        return None
    return fpd_decomposition(
        df_mature,
        vintage,
        prior_vintage,
        tier_col,
        target,
    )


def build_trailing_vintage_scorecards(
    cohort_ci,
    psi_table,
    ref_vintage,
    df_mature,
    tier_col,
    target,
    trailing_vintages,
    policy=None,
):
    """One scorecard row-set per origination month (last N months)."""
    policy = policy or {}
    g_mom = policy.get('mom_bps_green', 15)
    r_mom = policy.get('mom_bps_red', 30)
    g_ref = policy.get('ref_bps_green', 20)
    r_ref = policy.get('ref_bps_red', 40)
    g_psi = policy.get('psi_green', 0.10)
    r_psi = policy.get('psi_red', 0.25)
    g_mat = policy.get('mature_green', 0.95)
    a_mat = policy.get('mature_amber', 0.80)

    ref_row = (
        _cohort_row_for_vintage(cohort_ci, ref_vintage)
        if ref_vintage is not None else pd.DataFrame()
    )
    ref_fpd = ref_row['fpd_rate'].iloc[0] if len(ref_row) else np.nan

    rows = []
    for i, v in enumerate(trailing_vintages):
        vstr = _period_to_str(v)
        row = _cohort_row_for_vintage(cohort_ci, v)
        prior_v = trailing_vintages[i - 1] if i > 0 else None
        decomp = _mom_decomp_for_vintage(df_mature, tier_col, target, v, prior_v)
        mom_bps = decomp['delta_fpd'] * 10000 if decomp is not None else np.nan
        psi_v = (
            psi_table[psi_table['vintage_month'] == vstr]['psi'].max()
            if psi_table is not None and len(psi_table) else np.nan
        )
        fpd_pct = row['fpd_rate'].iloc[0] * 100 if len(row) and pd.notna(row['fpd_rate'].iloc[0]) else np.nan
        pct_mature = row['pct_mature'].iloc[0] if len(row) else np.nan
        vs_ref_bps = (row['fpd_rate'].iloc[0] - ref_fpd) * 10000 if len(row) and pd.notna(ref_fpd) and pd.notna(row['fpd_rate'].iloc[0]) else np.nan
        rows.extend([
            {
                'vintage_month': vstr,
                'metric': 'Portfolio FPD %',
                'value': f"{fpd_pct:.3f}%" if pd.notna(fpd_pct) else 'n/a (immature)',
                'policy_status': 'n/a' if pd.isna(fpd_pct) else 'n/a',
            },
            {
                'vintage_month': vstr,
                'metric': '% loans mature for FPD',
                'value': f"{pct_mature:.1f}%" if pd.notna(pct_mature) else 'n/a',
                'policy_status': _rag_mature_pct(pct_mature / 100 if pd.notna(pct_mature) else np.nan, g_mat, a_mat),
            },
            {
                'vintage_month': vstr,
                'metric': 'MoM FPD change vs prior month (bps)',
                'value': f"{mom_bps:+.1f}" if pd.notna(mom_bps) else 'n/a',
                'policy_status': _rag_abs_bps(mom_bps, g_mom, r_mom) if pd.notna(mom_bps) else 'n/a',
            },
            {
                'vintage_month': vstr,
                'metric': f"FPD vs reference {_period_to_str(ref_vintage)} (bps)",
                'value': f"{vs_ref_bps:+.1f}" if pd.notna(vs_ref_bps) else 'n/a',
                'policy_status': _rag_abs_bps(vs_ref_bps, g_ref, r_ref) if pd.notna(vs_ref_bps) else 'n/a',
            },
            {
                'vintage_month': vstr,
                'metric': 'Max PSI vs reference',
                'value': f"{psi_v:.4f}" if pd.notna(psi_v) else 'n/a',
                'policy_status': _rag_psi(psi_v, g_psi, r_psi) if pd.notna(psi_v) else 'n/a',
            },
        ])
    return pd.DataFrame(rows)


def build_emerging_risks_markdown(
    trailing_vintages,
    cohort_ci,
    df_mature,
    psi_table,
    ref_vintage,
    tier_col,
    target,
):
    """Markdown summary for the last N origination months (maturity-aware)."""
    lines = [
        f"## Emerging risks — last **{len(trailing_vintages)}** origination month(s)",
        f"PSI reference vintage: **{_period_to_str(ref_vintage)}** (set `PSI_REFERENCE_VINTAGE`; default is first month of `MODEL_ERA_START`).",
        "",
    ]
    for i, v in enumerate(trailing_vintages):
        vstr = _period_to_str(v)
        row = _cohort_row_for_vintage(cohort_ci, v)
        pct_m = row['pct_mature'].iloc[0] if len(row) else 0
        fpd = row['fpd_rate'].iloc[0] if len(row) else np.nan
        lines.append(f"### {_period_to_str(v)} ({pct_m:.0f}% mature for FPD)")
        if pd.isna(fpd) or pct_m < 80:
            lines.append(
                "- **Interpretation:** Most loans are not yet observable for FPD; treat rates/PSI as **directional only** until maturity catches up."
            )
        prior_v = trailing_vintages[i - 1] if i > 0 else None
        if prior_v is not None:
            d = _mom_decomp_for_vintage(df_mature, tier_col, target, v, prior_v)
            if d is not None:
                lines.append(
                    f"- Portfolio FPD vs prior month ({_period_to_str(prior_v)}): **{(d['delta_fpd']*10000):+.1f} bps** "
                    f"(mix {(d['mix_effect']*10000):+.1f}, rate {(d['rate_effect']*10000):+.1f})."
                )
                tier_rate_chg = (d['r_b'] - d['r_a']).sort_values(ascending=False)
                tier_mix_chg_pp = ((d['p_b'] - d['p_a']) * 100).sort_values(ascending=False)
                lines.append("- Top tier **rate** movers (bps vs prior month):")
                for t, val in tier_rate_chg.head(3).items():
                    lines.append(f"  - Tier {t}: {(val*10000):+.1f} bps")
                lines.append("- Top tier **mix** shifts (pp vs prior month):")
                for t, val in tier_mix_chg_pp.head(3).items():
                    lines.append(f"  - Tier {t}: {val:+.2f} pp")
        latest_psi = (
            psi_table[psi_table['vintage_month'] == vstr].sort_values('psi', ascending=False).head(3)
            if psi_table is not None and len(psi_table) else pd.DataFrame()
        )
        if len(latest_psi):
            lines.append("- Highest PSI vs reference:")
            for _, prow in latest_psi.iterrows():
                lines.append(f"  - {prow['feature']}: PSI={prow['psi']} ({prow['flag']})")
        lines.append("")
    return "\\n".join(lines)


def validate_mob_curve_support(df, candidate_cols=None):
    """Document whether the report view supports true MOB curves."""
    candidate_cols = candidate_cols or (
        'days_on_book',
        'days_since_origination',
        'loan_days_on_book',
        '_days_since_orig',
    )
    present = [c for c in candidate_cols if c in df.columns]
    col = resolve_days_on_book_column(df, candidate_cols)
    out = {
        'days_column': col,
        'columns_present': present,
        'verdict': 'not_supported',
        'detail': (
            'This report view exposes a final `flag_1st_pay_default` outcome, not MOB-conditional performance. '
            'Bucketing by days/MOB and re-using the vintage FPD rate produces flat misleading lines. '
            'Use RUN_MOB_CURVES=True only after loading a dedicated MOB dataset.'
        ),
    }
    if col is None:
        out['detail'] = (
            'No days-on-book column found in the report view. MOB curves require a separate MOB dataset.'
        )
    return out

'''
        hs = hs.replace(insert_anchor, trailing_helpers + insert_anchor)

    # tier small multiples x-axis
    old_g6 = """    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows), sharex=True)
    axes = np.atleast_1d(axes).flatten()
    for ax, tier in zip(axes, tiers):
        tier_series = tier_fpd_rates.loc[tier].dropna()
        ax.plot(tier_series.index.astype(str), tier_series.values, marker='o')
        ax.set_title(f'Tier {tier}')
        ax.set_ylabel('FPD rate')
        ax.tick_params(axis='x', rotation=45)
    for ax in axes[len(tiers):]:
        ax.axis('off')
    fig.suptitle('Within-tier FPD by vintage (mature loans)', y=1.02)
    plt.tight_layout()"""

    new_g6 = """    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows), sharex=True)
    axes = np.atleast_1d(axes).flatten()
    x_labels = [str(v) for v in tier_fpd_rates.columns]
    for ax, tier in zip(axes, tiers):
        tier_series = tier_fpd_rates.loc[tier].dropna()
        ax.plot(tier_series.index.astype(str), tier_series.values, marker='o', markersize=4)
        ax.set_title(f'Tier {tier}', fontsize=10)
        ax.set_ylabel('FPD rate', fontsize=8)
        ax.tick_params(axis='y', labelsize=7)
        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels, rotation=60, ha='right', fontsize=7)
    for ax in axes[len(tiers):]:
        ax.axis('off')
    fig.suptitle('Within-tier FPD by vintage (mature loans)', y=1.02)
    plt.tight_layout()"""

    if old_g6 in hs:
        hs = hs.replace(old_g6, new_g6)
    elif "Within-tier FPD by vintage (mature loans)" in hs:
        pass  # may live in story cell only

    set_cell_text(helpers, hs)

    # Analytics: PSI filter + emerging risks
    if analytics is not None:
        as_ = cell_text(analytics)
        if "psi_vintages =" not in as_:
            as_ = as_.replace(
                "    if PSI_REFERENCE_VINTAGE:\n        ref_vintage = pd.Period(PSI_REFERENCE_VINTAGE, freq='M')\n    else:\n        ref_vintage = mature_vintages[0] if mature_vintages else None\n",
                "    if PSI_REFERENCE_VINTAGE:\n        ref_vintage = pd.Period(PSI_REFERENCE_VINTAGE, freq='M')\n    else:\n        ref_vintage = mature_vintages[0] if mature_vintages else None\n\n    all_vintages = sorted(df_mon['_vintage'].unique())\n    _trail_n = globals().get('MONITORING_TRAILING_VINTAGES', 3)\n    trailing_vintages = all_vintages[-_trail_n:] if len(all_vintages) else []\n",
            )

        # Filter PSI to sufficiently mature vintages
        marker = "    psi_table = compute_psi_by_vintage("
        if marker in as_ and "PSI_MIN_PCT_MATURE" not in as_.split(marker)[1][:400]:
            as_ = as_.replace(
                marker,
                "    _psi_min_mature = globals().get('PSI_MIN_PCT_MATURE', 0.80)\n"
                "    _mature_enough = cohort_table[cohort_table['pct_mature'] >= _psi_min_mature * 100]['vintage_month'].tolist()\n"
                "    _psi_vintages = [v for v in mature_vintages if _period_to_str(v) in _mature_enough]\n"
                "    psi_table = compute_psi_by_vintage(",
            )
            as_ = as_.replace(
                "compute_psi_by_vintage(\n        df_mon,\n        ref_vintage,\n        mature_vintages,",
                "compute_psi_by_vintage(\n        df_mon,\n        ref_vintage,\n        _psi_vintages,",
            )

        old_em = """    # --- Emerging risks (latest mature vintage) ---
    if len(mature_vintages) >= 2:
        latest_v = mature_vintages[-1]
        prior_v = mature_vintages[-2]
        d = decomp_mom
        tier_rate_chg = (d['r_b'] - d['r_a']).sort_values(ascending=False)
        tier_mix_chg_pp = ((d['p_b'] - d['p_a']) * 100).sort_values(ascending=False)
        latest_psi = (
            psi_table[psi_table['vintage_month'] == _period_to_str(latest_v)]
            .sort_values('psi', ascending=False)
            .head(5)
            if len(psi_table)
            else pd.DataFrame()
        )
        summary_lines = [
            f"## Emerging risks — latest mature vintage **{_period_to_str(latest_v)}**",
            f"1. Portfolio FPD vs prior month ({_period_to_str(prior_v)}): **{(d['delta_fpd']*10000):+.1f} bps** "
            f"(mix {(d['mix_effect']*10000):+.1f}, rate {(d['rate_effect']*10000):+.1f}, interaction {(d['interaction']*10000):+.1f}).",
            "2. Tiers — largest within-tier FPD increase (rate effect drivers):",
        ]
        for t, val in tier_rate_chg.head(3).items():
            summary_lines.append(f"   - Tier {t}: {(val*10000):+.1f} bps vs prior month")
        summary_lines.append("3. Tiers — largest mix shift (percentage points):")
        for t, val in tier_mix_chg_pp.head(3).items():
            summary_lines.append(f"   - Tier {t}: {val:+.2f} pp vs prior month")
        summary_lines.append("4. Highest PSI vs reference (latest vintage):")
        if len(latest_psi):
            for _, row in latest_psi.iterrows():
                summary_lines.append(f"   - {row['feature']}: PSI={row['psi']} ({row['flag']})")
        else:
            summary_lines.append("   - (no PSI rows)")
        from IPython.display import Markdown, display as ipy_display
        ipy_display(Markdown("\\n".join(summary_lines)))"""

        new_em = """    # --- Emerging risks (last N origination months) ---
    if trailing_vintages:
        cohort_ci_preview = cohort_table_with_ci(df_mon, TARGET)
        from IPython.display import Markdown, display as ipy_display
        ipy_display(
            Markdown(
                build_emerging_risks_markdown(
                    trailing_vintages,
                    cohort_ci_preview,
                    df_mature,
                    psi_table,
                    ref_vintage,
                    TIER_COL,
                    TARGET,
                )
            )
        )"""

        if old_em in as_:
            as_ = as_.replace(old_em, new_em)
        set_cell_text(analytics, as_)

    # Story cell: scorecard trailing + MOB gate + plot call
    if story is not None:
        ss = cell_text(story)
        ss = ss.replace(
            "    print('### G1. Executive scorecard')\n    _prior_v = mature_vintages[-2] if len(mature_vintages) >= 2 else None\n    _latest_v = mature_vintages[-1] if len(mature_vintages) else None\n    _policy = {",
            "    print('### G1. Executive scorecard (last origination months)')\n    _trail_n = globals().get('MONITORING_TRAILING_VINTAGES', 3)\n    _all_v = sorted(df_mon['_vintage'].unique())\n    _trailing = _all_v[-_trail_n:] if len(_all_v) else []\n    _prior_v = mature_vintages[-2] if len(mature_vintages) >= 2 else None\n    _latest_v = mature_vintages[-1] if len(mature_vintages) else None\n    _policy = {",
        )
        ss = ss.replace(
            "    display(build_executive_scorecard_rag(\n        cohort_ci,\n        decomp_mom,\n        psi_table,\n        _latest_v,\n        _prior_v,\n        ref_vintage,\n        policy=_policy,\n    ))",
            "    display(build_trailing_vintage_scorecards(\n        cohort_ci,\n        psi_table,\n        ref_vintage,\n        df_mature,\n        TIER_COL,\n        TARGET,\n        _trailing,\n        policy=_policy,\n    ))",
        )
        ss = ss.replace(
            "    plot_vintage_fpd_trend(cohort_ci)",
            "    plot_vintage_fpd_trend(cohort_ci, min_pct_mature_for_ci=MIN_PCT_MATURE_FOR_CI)",
        )

        mob_old = "    print('### G7. MOB curves')\n    mob_table = build_mob_fpd_table(df_mon, TARGET)\n    plot_mob_fpd_curves(mob_table)"
        mob_new = """    print('### G7. MOB curves')
    _mob_check = validate_mob_curve_support(df_mon)
    print('MOB data check:', _mob_check)
    if globals().get('RUN_MOB_CURVES', False):
        mob_table = build_mob_fpd_table(df_mon, TARGET)
        plot_mob_fpd_curves(mob_table)
    else:
        print(
            'MOB curves skipped (RUN_MOB_CURVES=False). '
            + _mob_check.get('detail', '')
        )"""
        if mob_old in ss:
            ss = ss.replace(mob_old, mob_new)
        set_cell_text(story, ss)

    if cluster_cell is not None:
        cs = cell_text(cluster_cell)
        cs = cs.replace(
            '"name": "CRITICAL - Ultra-High Default Segment",',
            '"name": "Highest FPD Segment",',
        )
        set_cell_text(cluster_cell, cs)

    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Patched", NB_PATH)


if __name__ == "__main__":
    main()
