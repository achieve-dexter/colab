"""Add Part C ever-modified vintage monitoring to AAL_First_Pay_Default_2026.ipynb."""
import json
from pathlib import Path

NOTEBOOK = Path("/workspace/AAL_First_Pay_Default_2026.ipynb")


def main() -> None:
    nb = json.loads(NOTEBOOK.read_text())

    # --- config cell ---
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if src.startswith("# --- Part B run configuration"):
            if "RUN_MODIFICATION_MONITORING" not in src:
                insert = (
                    "\n# --- Part C: ever-modified (flag_modified) vintage monitoring ---\n"
                    "RUN_MODIFICATION_MONITORING = True\n"
                    "MODIFIED_FLAG_COL = 'flag_modified'\n"
                    "MODIFICATION_MIN_DAYS_ON_BOOK = 120  # min days from vintage month start before rate is comparable\n"
                    "MODIFICATION_REFERENCE_VINTAGE = '2026-01'  # None -> first mature vintage\n"
                    "MODIFICATION_TRAILING_VINTAGES = 6  # focus on recent origination months\n"
                )
                src = src.replace(
                    "PART_B_NOTEBOOK_REV = ",
                    insert + "PART_B_NOTEBOOK_REV = ",
                )
                src = src.replace(
                    'f"MONITORING_TRAILING_VINTAGES={MONITORING_TRAILING_VINTAGES}, RUN_MOB_CURVES={RUN_MOB_CURVES}"',
                    'f"MONITORING_TRAILING_VINTAGES={MONITORING_TRAILING_VINTAGES}, RUN_MOB_CURVES={RUN_MOB_CURVES}, '
                    'f"RUN_MODIFICATION_MONITORING={RUN_MODIFICATION_MONITORING}"',
                )
                nb["cells"][i]["source"] = [src]
            break

    # --- blocklist ---
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if src.startswith("# Master post-origination / leakage blocklist"):
            if "flag_modified" not in src:
                src = src.replace(
                    "'loan_deceased_flag',\n",
                    "'loan_deceased_flag',\n    'flag_modified',\n",
                )
                nb["cells"][i]["source"] = [src]
            break

    # --- helpers cell ---
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "def cohort_table_with_ci(df_mon, target):" in src and "mature_col=" not in src:
            src = src.replace(
                "def cohort_table_with_ci(df_mon, target):\n"
                '    """Build cohort metrics with Wilson 95% CI on mature-loan FPD rate."""',
                "def cohort_table_with_ci(\n"
                "    df_mon,\n"
                "    target,\n"
                "    mature_col='is_mature_fpd',\n"
                "    event_count_col='fpd_count',\n"
                "    rate_col='fpd_rate',\n"
                "):\n"
                '    """Build cohort metrics with Wilson 95% CI on mature-loan outcome rate."""',
            )
            src = src.replace(
                "g_mat = g_all[g_all['is_mature_fpd']]",
                "g_mat = g_all[g_all[mature_col]]",
            )
            old_block = (
                "        rows.append({\n"
                "            'vintage_month': _period_to_str(v),\n"
                "            'loan_count': len(g_all),\n"
                "            'mature_loan_count': n_mat,\n"
                "            'pct_mature': g_all['is_mature_fpd'].mean(),\n"
                "            'fpd_count': fpd,\n"
                "            'fpd_rate': rate,\n"
                "            'fpd_rate_ci_low': lo,\n"
                "            'fpd_rate_ci_high': hi,\n"
                "        })"
            )
            new_block = (
                "        row = {\n"
                "            'vintage_month': _period_to_str(v),\n"
                "            'loan_count': len(g_all),\n"
                "            'mature_loan_count': n_mat,\n"
                "            'pct_mature': g_all[mature_col].mean(),\n"
                "        }\n"
                "        row[event_count_col] = fpd\n"
                "        row[rate_col] = rate\n"
                "        row[rate_col + '_ci_low'] = lo\n"
                "        row[rate_col + '_ci_high'] = hi\n"
                "        rows.append(row)"
            )
            if old_block not in src:
                raise SystemExit("cohort rows block not found")
            src = src.replace(old_block, new_block)
            nb["cells"][i]["source"] = [src]
            helpers_idx = i
            break
    else:
        raise SystemExit("cohort_table_with_ci not found")

    src = "".join(nb["cells"][helpers_idx]["source"])
    if "def add_modification_observability" not in src:
        insert = '''

def add_modification_observability(df_in, as_of_date, min_days_on_book, vintage_col):
    """
    Loans need enough time on book before ever-modified rates are comparable across vintages.
    Uses vintage month start vs AS_OF_DATE (same vintage-month grain as Part B).
    """
    work = df_in.copy()
    if '_vintage' not in work.columns:
        work['_vintage'] = _vintage_period(work[vintage_col])
    as_of = pd.Timestamp(as_of_date).normalize()
    vintage_start = work['_vintage'].apply(lambda p: p.to_timestamp())
    work['days_since_vintage_start'] = (as_of - vintage_start).dt.days
    work['is_mature_mod'] = work['days_since_vintage_start'] >= int(min_days_on_book)
    return work


def plot_vintage_outcome_trend(
    cohort_ci,
    rate_col='fpd_rate',
    title='Vintage outcome rate (mature loans, 95% CI)',
    min_pct_mature_for_ci=None,
):
    """Same layout as FPD trend; parameterized rate column."""
    min_pct = min_pct_mature_for_ci
    if min_pct is None:
        min_pct = globals().get('MIN_PCT_MATURE_FOR_CI', 0.80)
    plot_df = cohort_ci.copy().sort_values('vintage_month')
    if plot_df.empty:
        print('Vintage outcome trend skipped — no vintages.')
        return
    lo_col, hi_col = rate_col + '_ci_low', rate_col + '_ci_high'
    x = np.arange(len(plot_df))
    y = plot_df[rate_col].astype(float) * 100
    y_plot = y.copy()
    ylo = plot_df[lo_col].astype(float) * 100
    yhi = plot_df[hi_col].astype(float) * 100
    pct_m = plot_df['pct_mature'].map(_pct_mature_fraction).fillna(0).astype(float)
    ci_ok = pct_m >= float(min_pct)
    fig, ax1 = plt.subplots(figsize=(12, 5))
    if ci_ok.any():
        ax1.plot(x[ci_ok], y_plot[ci_ok], 'o-', color='#2ca02c', label='Rate % (mature enough for CI)')
        ax1.errorbar(
            x[ci_ok], y[ci_ok],
            yerr=[(y - ylo)[ci_ok], (yhi - y)[ci_ok]],
            fmt='none', ecolor='#98df8a', elinewidth=1.5, capsize=3, alpha=0.45,
        )
    if (~ci_ok).any():
        y_plot = y_plot.copy()
        y_plot[~ci_ok] = np.nan
        ax1.plot(x[~ci_ok], y_plot[~ci_ok], 'o', color='#bdbdbd', linestyle='None',
                 label='Rate % (immature — CI hidden)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(plot_df['vintage_month'], rotation=45, ha='right')
    ax1.set_ylabel('Rate (%)')
    ax1.set_title(title)
    ax2 = ax1.twinx()
    ax2.bar(x, plot_df['loan_count'], alpha=0.2, color='gray', label='Loan count (all)')
    ax2.set_ylabel('Loan count')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=8)
    plt.tight_layout()
    plt.show()


def build_modification_vintage_attribution(cohort_ci, rate_col, trailing_n, baseline_exclude_trailing=True):
    """
    Rank recent vintages vs baseline (earlier mature vintages) on modified rate (bps).
    """
    if cohort_ci is None or cohort_ci.empty:
        return pd.DataFrame()
    d = cohort_ci.dropna(subset=[rate_col]).sort_values('vintage_month').copy()
    if d.empty:
        return pd.DataFrame()
    trail = d.tail(int(trailing_n))
    if baseline_exclude_trailing and len(d) > len(trail):
        base = d.iloc[: -len(trail)]
    else:
        base = d.iloc[: max(1, len(d) - 1)]
    base_rate = float(base[rate_col].mean()) if len(base) else np.nan
    out = trail.copy()
    out['baseline_rate'] = base_rate
    out['bps_vs_baseline'] = (out[rate_col] - base_rate) * 10000
    out['share_of_loans_pct'] = out['loan_count'] / out['loan_count'].sum() * 100
    return out.sort_values('bps_vs_baseline', ascending=False)

'''
        needle = "def plot_decomposition_waterfall(decomp, label='Portfolio FPD change'):"
        nb["cells"][helpers_idx]["source"] = [src.replace(needle, insert + needle)]

    # --- insert Part C markdown + code after Part B analytics (cell 21) ---
    part_c_md = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Part C — Ever-modified rate by vintage (`flag_modified`)\n\n"
            "Tracks **ever modified** share by **origination vintage month** to answer: *Is the recent rise in modifications concentrated in specific vintages, or broad-based?*\n\n"
            "**Observability:** Unlike FPD, modifications can occur later on book. Rates use loans with at least "
            "`MODIFICATION_MIN_DAYS_ON_BOOK` days since vintage month start (config). Immature vintages are shown with volume but CIs may be hidden.\n\n"
            "Run **after** the Part B analytics cell (`df_mon` exists). Set `RUN_MODIFICATION_MONITORING = False` to skip.\n"
        ],
    }

    part_c_code = {
        "cell_type": "code",
        "metadata": {},
        "source": [
            "if not globals().get('RUN_MODIFICATION_MONITORING', False):\n"
            "    print('RUN_MODIFICATION_MONITORING=False — skip Part C ever-modified monitoring.')\n"
            "elif 'df_mon' not in globals():\n"
            "    raise RuntimeError('Run Part B analytics first (creates df_mon).')\n"
            "elif MODIFIED_FLAG_COL not in df_mon.columns:\n"
            "    raise KeyError(\n"
            "        f\"{MODIFIED_FLAG_COL!r} not in report view — refresh BigQuery pull after view deploy.\"\n"
            "    )\n"
            "else:\n"
            "    df_mod = add_modification_observability(\n"
            "        df_mon, AS_OF_DATE, MODIFICATION_MIN_DAYS_ON_BOOK, VINTAGE_COL\n"
            "    )\n"
            "    df_mod_mature = df_mod[df_mod['is_mature_mod']].copy()\n"
            "    mod_mature_vintages = sorted(df_mod_mature['_vintage'].unique())\n"
            "\n"
            "    mod_cohort_ci = cohort_table_with_ci(\n"
            "        df_mod,\n"
            "        MODIFIED_FLAG_COL,\n"
            "        mature_col='is_mature_mod',\n"
            "        event_count_col='modified_count',\n"
            "        rate_col='modified_rate',\n"
            "    )\n"
            "    print('### C1. Ever-modified cohort table (by vintage month)')\n"
            "    display(mod_cohort_ci.assign(\n"
            "        modified_rate=lambda x: (x['modified_rate'] * 100).round(3),\n"
            "        pct_mature=lambda x: (x['pct_mature'].map(_pct_mature_fraction) * 100).round(1),\n"
            "    ))\n"
            "\n"
            "    _mod_trail = globals().get('MODIFICATION_TRAILING_VINTAGES', 6)\n"
            "    mod_attrib = build_modification_vintage_attribution(\n"
            "        mod_cohort_ci, 'modified_rate', _mod_trail\n"
            "    )\n"
            "    print(f'### C2. Vintage attribution — last {_mod_trail} origination months vs earlier baseline')\n"
            "    if mod_attrib.empty:\n"
            "        print('Not enough mature vintages for attribution.')\n"
            "    else:\n"
            "        display(mod_attrib.assign(\n"
            "            modified_rate=lambda d: (d['modified_rate'] * 100).round(3),\n"
            "            baseline_rate=lambda d: (d['baseline_rate'] * 100).round(3),\n"
            "            bps_vs_baseline=lambda d: d['bps_vs_baseline'].round(1),\n"
            "            share_of_loans_pct=lambda d: d['share_of_loans_pct'].round(1),\n"
            "        )[[\n"
            "            'vintage_month', 'loan_count', 'share_of_loans_pct',\n"
            "            'modified_rate', 'baseline_rate', 'bps_vs_baseline', 'mature_loan_count',\n"
            "        ]])\n"
            "\n"
            "    print('### C3. Ever-modified rate trend + volume')\n"
            "    plot_vintage_outcome_trend(\n"
            "        mod_cohort_ci,\n"
            "        rate_col='modified_rate',\n"
            "        title='Ever-modified rate by vintage (mature-enough loans, 95% CI)',\n"
            "    )\n"
            "\n"
            "    if len(mod_mature_vintages) >= 1:\n"
            "        tier_mix_mod, tier_mod_rates = tier_mix_and_rates(\n"
            "            df_mod_mature, VINTAGE_COL, TIER_COL, MODIFIED_FLAG_COL\n"
            "        )\n"
            "        print('### C4. Within-tier ever-modified rate heatmap')\n"
            "        plot_tier_fpd_heatmap(\n"
            "            tier_mod_rates,\n"
            "            title='Within-tier ever-modified rate by vintage (mature-enough loans)',\n"
            "        )\n"
            "\n"
            "    if len(mod_mature_vintages) >= 2:\n"
            "        mod_latest = mod_mature_vintages[-1]\n"
            "        mod_prior = mod_mature_vintages[-2]\n"
            "        decomp_mod_mom = fpd_decomposition(\n"
            "            df_mod_mature[df_mod_mature['_vintage'] == mod_prior],\n"
            "            df_mod_mature[df_mod_mature['_vintage'] == mod_latest],\n"
            "            TIER_COL,\n"
            "            MODIFIED_FLAG_COL,\n"
            "        )\n"
            "        print(\n"
            "            f\"### C5. Mix vs rate decomposition (ever-modified): \"\n"
            "            f\"{_period_to_str(mod_prior)} → {_period_to_str(mod_latest)}\"\n"
            "        )\n"
            "        display(pd.DataFrame([{\n"
            "            'modified_bps_change': round(decomp_mod_mom['delta_fpd'] * 10000, 1),\n"
            "            'mix_effect_bps': round(decomp_mod_mom['mix_effect'] * 10000, 1),\n"
            "            'rate_effect_bps': round(decomp_mod_mom['rate_effect'] * 10000, 1),\n"
            "            'interaction_bps': round(decomp_mod_mom['interaction'] * 10000, 1),\n"
            "        }]))\n"
            "\n"
            "        if MODIFICATION_REFERENCE_VINTAGE:\n"
            "            mod_ref = pd.Period(MODIFICATION_REFERENCE_VINTAGE, freq='M')\n"
            "        else:\n"
            "            mod_ref = mod_mature_vintages[0]\n"
            "        if mod_ref in mod_mature_vintages and mod_ref != mod_latest:\n"
            "            decomp_mod_ref = fpd_decomposition(\n"
            "                df_mod_mature[df_mod_mature['_vintage'] == mod_ref],\n"
            "                df_mod_mature[df_mod_mature['_vintage'] == mod_latest],\n"
            "                TIER_COL,\n"
            "                MODIFIED_FLAG_COL,\n"
            "            )\n"
            "            print(f\"### C5b. vs reference vintage {_period_to_str(mod_ref)}\")\n"
            "            display(pd.DataFrame([{\n"
            "                'modified_bps_change': round(decomp_mod_ref['delta_fpd'] * 10000, 1),\n"
            "                'mix_effect_bps': round(decomp_mod_ref['mix_effect'] * 10000, 1),\n"
            "                'rate_effect_bps': round(decomp_mod_ref['rate_effect'] * 10000, 1),\n"
            "                'interaction_bps': round(decomp_mod_ref['interaction'] * 10000, 1),\n"
            "            }]))\n"
            "\n"
            "    # Executive bullets (auto)\n"
            "    if not mod_attrib.empty:\n"
            "        hot = mod_attrib.sort_values('bps_vs_baseline', ascending=False).iloc[0]\n"
            "        print(\n"
            "            '\\n**Summary:** Highest recent vintage vs baseline: '\n"
            "            f\"{hot['vintage_month']} ({hot['bps_vs_baseline']:+.0f} bps vs earlier vintages, \"\n"
            "            f\"rate {hot['modified_rate']*100:.2f}%). \"\n"
            "            'Use C4 heatmap to see if specific tiers drive the vintage.'\n"
            "        )\n"
        ],
        "outputs": [],
        "execution_count": None,
    }

    # find Part B analytics cell index
    insert_at = None
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "### A. Cohort table (vintage month)" in src and "RUN_VINTAGE_MONITORING" in src:
            insert_at = i + 1
            break
    if insert_at is None:
        raise SystemExit("Part B analytics cell not found")

    if not any("Part C — Ever-modified" in "".join(c.get("source", [])) for c in nb["cells"]):
        nb["cells"].insert(insert_at, part_c_code)
        nb["cells"].insert(insert_at, part_c_md)

    NOTEBOOK.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print("patched", NOTEBOOK)


if __name__ == "__main__":
    main()
