#!/usr/bin/env python3
import json
from pathlib import Path

NB_PATH = Path("/workspace/AAL_First_Pay_Default_2026.ipynb")

NEW_HELPER_BLOCK = r'''
def _rag_abs_bps(val, green, red):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 'n/a'
    a = abs(float(val))
    if a <= green:
        return 'green'
    if a <= red:
        return 'amber'
    return 'red'

def _rag_psi(val, green, red):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 'n/a'
    v = float(val)
    if v <= green:
        return 'green'
    if v <= red:
        return 'amber'
    return 'red'

def _rag_mature_pct(val, green, amber_min):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 'n/a'
    v = float(val)
    if v >= green:
        return 'green'
    if v >= amber_min:
        return 'amber'
    return 'red'

def resolve_days_on_book_column(df, candidates, post_orig_cols=None):
    """Pick first usable days-on-book column (not on leakage blocklist)."""
    block = set(post_orig_cols or [])
    for col in candidates:
        if col in df.columns and col not in block:
            return col
    if '_days_since_orig' in df.columns:
        return '_days_since_orig'
    return None

def build_mob_fpd_table(df_in, target, vintage_col, days_col, max_mob=6, days_per_mob=30):
    """MOB FPD: among loans that reached MOB m, portfolio FPD rate."""
    work = df_in.copy()
    if days_col is None or days_col not in work.columns:
        return pd.DataFrame()
    days = pd.to_numeric(work[days_col], errors='coerce')
    work['_days_on_book'] = days
    if '_vintage' not in work.columns:
        work['_vintage'] = _vintage_period(work[vintage_col])
    rows = []
    for v in sorted(work['_vintage'].dropna().unique()):
        g = work[work['_vintage'] == v]
        for m in range(0, max_mob + 1):
            cutoff = m * days_per_mob
            elig = g[g['_days_on_book'] >= cutoff]
            if elig.empty:
                continue
            rows.append({
                'vintage_month': _period_to_str(v),
                'mob': m,
                'loan_count': len(elig),
                'fpd_rate': elig[target].mean(),
            })
    return pd.DataFrame(rows)

def plot_mob_fpd_curves(mob_table, title='FPD rate by months on book (MOB), by vintage'):
    if mob_table is None or mob_table.empty:
        print('MOB curve skipped — no days-on-book data.')
        return
    fig, ax = plt.subplots(figsize=(12, 6))
    for vintage, g in mob_table.groupby('vintage_month'):
        g = g.sort_values('mob')
        ax.plot(g['mob'], g['fpd_rate'] * 100, marker='o', label=vintage)
    ax.set_xlabel('Months on book (MOB)')
    ax.set_ylabel('FPD rate (%)')
    ax.set_title(title)
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
    plt.tight_layout()
    plt.show()

def build_executive_scorecard_rag(
    cohort_ci,
    decomp_mom,
    psi_table,
    latest_v,
    prior_v,
    ref_vintage,
    policy=None,
):
    """Scorecard with red/amber/green policy status per KPI."""
    policy = policy or {}
    g_mom = policy.get('mom_bps_green', 15)
    r_mom = policy.get('mom_bps_red', 30)
    g_ref = policy.get('ref_bps_green', 20)
    r_ref = policy.get('ref_bps_red', 40)
    g_psi = policy.get('psi_green', 0.10)
    r_psi = policy.get('psi_red', 0.25)
    g_mat = policy.get('mature_green', 0.95)
    a_mat = policy.get('mature_amber', 0.80)

    latest_row = cohort_ci[cohort_ci['vintage_month'] == _period_to_str(latest_v)].head(1)
    ref_row = (
        cohort_ci[cohort_ci['vintage_month'] == _period_to_str(ref_vintage)].head(1)
        if ref_vintage is not None else pd.DataFrame()
    )
    max_psi = psi_table['psi'].max() if psi_table is not None and len(psi_table) else np.nan
    mom_bps = decomp_mom['delta_fpd'] * 10000 if decomp_mom is not None else np.nan
    vs_ref_bps = np.nan
    if len(latest_row) and len(ref_row):
        vs_ref_bps = (latest_row['fpd_rate'].iloc[0] - ref_row['fpd_rate'].iloc[0]) * 10000
    pct_mature = latest_row['pct_mature'].iloc[0] if len(latest_row) else np.nan
    fpd_pct = latest_row['fpd_rate'].iloc[0] * 100 if len(latest_row) else np.nan

    return pd.DataFrame([
        {
            'metric': 'Portfolio FPD % (latest mature vintage)',
            'value': f"{fpd_pct:.3f}%" if pd.notna(fpd_pct) else 'n/a',
            'policy_status': 'n/a',
        },
        {
            'metric': 'MoM FPD change (bps)',
            'value': f"{mom_bps:+.1f}" if pd.notna(mom_bps) else 'n/a',
            'policy_status': _rag_abs_bps(mom_bps, g_mom, r_mom),
        },
        {
            'metric': 'FPD vs reference vintage (bps)',
            'value': f"{vs_ref_bps:+.1f}" if pd.notna(vs_ref_bps) else 'n/a',
            'policy_status': _rag_abs_bps(vs_ref_bps, g_ref, r_ref),
        },
        {
            'metric': 'Max PSI vs reference',
            'value': f"{max_psi:.4f}" if pd.notna(max_psi) else 'n/a',
            'policy_status': _rag_psi(max_psi, g_psi, r_psi),
        },
        {
            'metric': '% mature (latest vintage)',
            'value': f"{pct_mature * 100:.1f}%" if pd.notna(pct_mature) else 'n/a',
            'policy_status': _rag_mature_pct(pct_mature, g_mat, a_mat),
        },
        {
            'metric': 'Latest mature vintage',
            'value': _period_to_str(latest_v) if latest_v is not None else 'n/a',
            'policy_status': 'n/a',
        },
        {
            'metric': 'PSI / FPD reference vintage',
            'value': _period_to_str(ref_vintage) if ref_vintage is not None else 'n/a',
            'policy_status': 'n/a',
        },
    ])
'''


def main():
    nb = json.loads(NB_PATH.read_text())

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "CREDIT_MODEL_DOMINANCE_MIN_SHARE" in src and "RUN_VINTAGE_MONITORING" in src:
            if "POLICY_FPD_MOM_BPS_GREEN" not in src:
                insert = (
                    "\n# --- Policy RAG thresholds (tune to risk policy) ---\n"
                    "POLICY_FPD_MOM_BPS_GREEN = 15\n"
                    "POLICY_FPD_MOM_BPS_RED = 30\n"
                    "POLICY_FPD_VS_REF_BPS_GREEN = 20\n"
                    "POLICY_FPD_VS_REF_BPS_RED = 40\n"
                    "POLICY_PSI_GREEN = 0.10\n"
                    "POLICY_PSI_RED = 0.25\n"
                    "POLICY_PCT_MATURE_GREEN = 0.95\n"
                    "POLICY_PCT_MATURE_AMBER = 0.80\n"
                    "\n# --- MOB curves ---\n"
                    "DAYS_ON_BOOK_COL_CANDIDATES = ['days_since_origination', 'days_elapsed_since_origination']\n"
                    "MOB_DAYS_PER_MONTH = 30\n"
                    "MOB_CURVE_MAX = 6\n"
                )
                src = src.replace(
                    "AS_OF_DATE = pd.Timestamp.today().normalize()",
                    insert + "AS_OF_DATE = pd.Timestamp.today().normalize()",
                )
                nb["cells"][i]["source"] = [src]
            break

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "def build_executive_scorecard(" in src and "build_executive_scorecard_rag" not in src:
            pos = src.find("def build_executive_scorecard(")
            nb["cells"][i]["source"] = [src[:pos] + NEW_HELPER_BLOCK.strip() + "\n\n" + src[pos:]]
            break

    old_logit = (
        "    # --- F. Optional multivariate vintage trend (mature loans) ---\n"
        "    try:\n"
        "        import statsmodels.formula.api as smf\n"
        "        model_df = df_mature.copy()\n"
        "        model_df['vintage_month'] = model_df['_vintage'].astype(str)\n"
        "        model_df['tier'] = model_df[TIER_COL].astype(str)\n"
        "        logit = smf.logit(f\"{TARGET} ~ C(vintage_month) + C(tier)\", data=model_df).fit(disp=0)\n"
        "        print(\"### F. Logistic regression (statsmodels): FPD ~ vintage + tier\")\n"
        "        display(logit.summary2().tables[1])"
    )
    new_logit = (
        "    # --- F. Multivariate models (mature loans) ---\n"
        "    try:\n"
        "        import statsmodels.formula.api as smf\n"
        "        model_df = df_mature.copy()\n"
        "        model_df['vintage_month'] = model_df['_vintage'].astype(str)\n"
        "        model_df['tier'] = model_df[TIER_COL].astype(str)\n"
        "        model_df['calendar_month'] = model_df['_vintage'].apply(lambda x: x.month).astype('category')\n"
        "\n"
        "        logit = smf.logit(\n"
        "            f\"{TARGET} ~ C(vintage_month) + C(tier) + C(calendar_month)\",\n"
        "            data=model_df,\n"
        "        ).fit(disp=0)\n"
        "        print(\"### F1. Logistic: FPD ~ vintage + tier + calendar month (seasonality control)\")\n"
        "        display(logit.summary2().tables[1])\n"
        "\n"
        "        logit_season = smf.logit(\n"
        "            f\"{TARGET} ~ C(tier) + C(calendar_month)\",\n"
        "            data=model_df,\n"
        "        ).fit(disp=0)\n"
        "        print(\"### F2. Logistic: FPD ~ tier + calendar month (seasonality benchmark)\")\n"
        "        display(logit_season.summary2().tables[1])"
    )
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if old_logit in src:
            nb["cells"][i]["source"] = [src.replace(old_logit, new_logit)]
            break

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "### G1. Executive scorecard" in src and "build_executive_scorecard_rag" not in src:
            src = src.replace(
                "    scorecard = build_executive_scorecard(\n"
                "        cohort_ci, globals().get('decomp_mom'), globals().get('psi_table'),\n"
                "        _latest_v, _prior_v, globals().get('ref_vintage'),\n"
                "    )\n"
                "    display(scorecard)\n",
                "    _policy = {\n"
                "        'mom_bps_green': POLICY_FPD_MOM_BPS_GREEN,\n"
                "        'mom_bps_red': POLICY_FPD_MOM_BPS_RED,\n"
                "        'ref_bps_green': POLICY_FPD_VS_REF_BPS_GREEN,\n"
                "        'ref_bps_red': POLICY_FPD_VS_REF_BPS_RED,\n"
                "        'psi_green': POLICY_PSI_GREEN,\n"
                "        'psi_red': POLICY_PSI_RED,\n"
                "        'mature_green': POLICY_PCT_MATURE_GREEN,\n"
                "        'mature_amber': POLICY_PCT_MATURE_AMBER,\n"
                "    }\n"
                "    scorecard = build_executive_scorecard_rag(\n"
                "        cohort_ci, globals().get('decomp_mom'), globals().get('psi_table'),\n"
                "        _latest_v, _prior_v, globals().get('ref_vintage'), policy=_policy,\n"
                "    )\n"
                "    display(scorecard)\n"
                "    print('Policy RAG: green = within tolerance, amber = watch, red = escalate.')\n",
            )
            mob = (
                "\n    print('### G7. MOB curves (FPD by months on book)')\n"
                "    _dob_col = resolve_days_on_book_column(df_mon, DAYS_ON_BOOK_COL_CANDIDATES, post_origination_cols)\n"
                "    if _dob_col is None and '_days_since_orig' in df_mon.columns:\n"
                "        _dob_col = '_days_since_orig'\n"
                "    print(f'Days-on-book column: {_dob_col}')\n"
                "    mob_table = build_mob_fpd_table(\n"
                "        df_mon, TARGET, VINTAGE_COL, _dob_col,\n"
                "        max_mob=MOB_CURVE_MAX, days_per_mob=MOB_DAYS_PER_MONTH,\n"
                "    )\n"
                "    if not mob_table.empty:\n"
                "        display(mob_table.assign(fpd_rate_pct=lambda d: (d['fpd_rate'] * 100).round(3)))\n"
                "        plot_mob_fpd_curves(mob_table)\n"
            )
            anchor = "        plt.show()\n\n# --- H. Seasonality benchmark"
            if anchor in src and "### G7. MOB" not in src:
                src = src.replace(anchor, "        plt.show()\n" + mob + "\n# --- H. Seasonality benchmark")
            nb["cells"][i]["source"] = [src]
            break

    if not any("Policy scorecard (red / amber / green)" in "".join(c.get("source", [])) for c in nb["cells"]):
        md = {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Business guide — Policy scorecard (red / amber / green)\n\n"
                "Executive scorecard KPIs use thresholds from the config cell. "
                "**Green** = within policy tolerance; **amber** = watch / investigate; **red** = escalate.\n\n"
                "| KPI | Green | Amber | Red |\n"
                "|-----|-------|-------|-----|\n"
                "| MoM FPD (bps) | |Δ| ≤ `POLICY_FPD_MOM_BPS_GREEN` | between green & red | |Δ| > `POLICY_FPD_MOM_BPS_RED` |\n"
                "| FPD vs reference (bps) | |Δ| ≤ `POLICY_FPD_VS_REF_BPS_GREEN` | between | |Δ| > `POLICY_FPD_VS_REF_BPS_RED` |\n"
                "| Max PSI | ≤ `POLICY_PSI_GREEN` | ≤ `POLICY_PSI_RED` | > `POLICY_PSI_RED` |\n"
                "| % mature | ≥ `POLICY_PCT_MATURE_GREEN` | ≥ `POLICY_PCT_MATURE_AMBER` | below amber |\n"
            ],
        }
        idx = next(
            i for i, c in enumerate(nb["cells"])
            if "## Business guide — Seasonality" in "".join(c.get("source", []))
        )
        nb["cells"].insert(idx + 1, md)

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "def add_fpd_maturity(" in src and "work['_days_since_orig'] = (as_of - first_due)" not in src:
            needle = "    work['_fpd_first_principal_date'] = first_due\n"
            repl = (
                needle
                + "    work['_days_since_orig'] = (as_of - first_due).dt.days  # MOB curves when loan DOB column absent\n"
            )
            if needle in src:
                src = src.replace(needle, repl)
                nb["cells"][i]["source"] = [src]
            break

    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print("done", NB_PATH)


if __name__ == "__main__":
    main()
