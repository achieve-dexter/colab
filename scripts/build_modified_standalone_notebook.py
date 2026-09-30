"""Restore FPD notebook from main; create standalone ever-modified monitoring notebook."""
import json
from pathlib import Path

ROOT = Path("/workspace")
FPD_PATH = ROOT / "AAL_First_Pay_Default_2026.ipynb"
MOD_PATH = ROOT / "AAL_Ever_Modified_Vintage_2026.ipynb"
MAIN_FPD = Path("/tmp/fpd_main.ipynb")
HELPERS_PATH = Path("/tmp/mod_helpers.py")


def _cell(typ: str, source: str) -> dict:
    c: dict = {"cell_type": typ, "metadata": {}, "source": [source]}
    if typ == "code":
        c["outputs"] = []
        c["execution_count"] = None
    return c


INTRO = (
    "# AAL — Ever-modified vintage monitoring\n\n"
    "Monthly **ever-modified** (`flag_modified`) analysis by **origination vintage**, "
    "with **`mod_start_date`** for months-on-book at modification.\n\n"
    "**Run order:** Authenticate → Config → BigQuery pull → Helpers → **Analytics (A–G)**.\n\n"
    "FPD segmentation and first-pay monitoring remain in `AAL_First_Pay_Default_2026.ipynb` only.\n"
)

CONFIG = '''# --- Ever-modified vintage monitoring configuration ---
import pandas as pd

MODEL_ERA_START = '2026-01-01'
VINTAGE_COL = 'loan_vintage_month'
TIER_COL = 'borrower_origination_risk_group'
MODIFIED_FLAG_COL = 'flag_modified'
MOD_START_DATE_COL = 'mod_start_date'

MODIFICATION_MIN_DAYS_ON_BOOK = 120
MODIFICATION_REFERENCE_VINTAGE = '2026-01'
MODIFICATION_TRAILING_VINTAGES = 6
MIN_PCT_MATURE_FOR_CI = 0.80
PSI_MIN_PCT_MATURE = 0.80
MOB_DAYS_PER_MONTH = 30

AS_OF_DATE = pd.Timestamp.today().normalize()
NOTEBOOK_REV = "2026-09-mod-standalone-v1"

print(
    f"Config: MODEL_ERA_START={MODEL_ERA_START}, MODIFIED_FLAG_COL={MODIFIED_FLAG_COL}, "
    f"MOD_START_DATE_COL={MOD_START_DATE_COL}, MODIFICATION_MIN_DAYS_ON_BOOK={MODIFICATION_MIN_DAYS_ON_BOOK}, "
    f"AS_OF_DATE={AS_OF_DATE.date()}, NOTEBOOK_REV={NOTEBOOK_REV}"
)
'''

BLOCKLIST = '''post_origination_cols = [
    'flag_modified',
    'mod_start_date',
    'flag_1st_pay_default',
    'days_elapsed_origination_to_dq',
    'days_elapsed_origination_to_dq_30',
    'count_dpd_30',
    'count_dpd_1_to_10',
    'flag_dq',
    'loan_prepaid_flag',
    'loan_1st_pay_default_return_code',
    'count_dpd_cured',
    'loan_no_payment_straight_to_chargeoff_flag',
    'loan_chargeoff_flag',
    'loan_contractual_chargeoff_flag',
    'flag_never_pay',
    'principal_default_percent',
    'loan_only_one_transaction_day_of_week',
    'loan_in_debt_settlement_flag',
    'loan_deceased_flag',
    'loan_total_overall_payment_amount',
]
'''

GBQ = '''sql = f"""
select *
from `ffam-data-platform-loan-ops.report_views.v_aal_early_pay_default`
where DATE(loan_vintage_month) >= DATE('{MODEL_ERA_START}')
"""

df = pandas_gbq.read_gbq(
    sql,
    project_id='ffn-dw-bigquery-prd',
    credentials=credentials,
    dialect='standard',
)
print(f"Loaded {len(df):,} rows | vintages from {MODEL_ERA_START}")
df.head()
'''

GUIDE = (
    "## Business guide\n\n"
    "| Question | Section |\n"
    "|----------|--------|\n"
    "| Which vintages have higher **ever-modified %**? | **A**, **C** |\n"
    "| Are **recent months** above earlier vintages? | **B** (bps vs baseline) |\n"
    "| **Tier** concentration within a vintage? | **D** heatmap |\n"
    "| **Mix** vs **within-tier rate**? | **E** decomposition |\n"
    "| **Booking mix** shift vs reference? | **F** PSI |\n"
    "| **When** mods occur (MOB)? | **G** `mod_start_date` |\n"
)

ANALYTICS = r'''# --- Analytics: ever-modified by vintage ---
if MODIFIED_FLAG_COL not in df.columns:
    raise KeyError(f"{MODIFIED_FLAG_COL!r} missing — re-run BigQuery after view deploy.")

df_mon = df.copy()
df_mon['_vintage'] = _vintage_period(df_mon[VINTAGE_COL])
era = pd.Period(pd.Timestamp(MODEL_ERA_START), freq='M')
df_mon = df_mon[df_mon['_vintage'] >= era].copy()

df_mod = add_modification_observability(
    df_mon,
    AS_OF_DATE,
    MODIFICATION_MIN_DAYS_ON_BOOK,
    VINTAGE_COL,
    mod_start_date_col=MOD_START_DATE_COL if MOD_START_DATE_COL in df_mon.columns else None,
    modified_flag_col=MODIFIED_FLAG_COL,
)
df_mod_mature = df_mod[df_mod['is_mature_mod']].copy()
mod_mature_vintages = sorted(df_mod_mature['_vintage'].unique())

mod_cohort_ci = cohort_table_with_ci(
    df_mod,
    MODIFIED_FLAG_COL,
    mature_col='is_mature_mod',
    event_count_col='modified_count',
    rate_col='modified_rate',
)

print("### A. Ever-modified cohort table (by vintage month)")
display(mod_cohort_ci.assign(
    modified_rate=lambda x: (x['modified_rate'] * 100).round(3),
    pct_mature=lambda x: (x['pct_mature'].map(_pct_mature_fraction) * 100).round(1),
))

mod_attrib = build_modification_vintage_attribution(
    mod_cohort_ci, 'modified_rate', MODIFICATION_TRAILING_VINTAGES,
)
print(f"### B. Vintage attribution — last {MODIFICATION_TRAILING_VINTAGES} months vs earlier baseline")
if mod_attrib.empty:
    print("Not enough mature vintages for attribution.")
else:
    display(mod_attrib.assign(
        modified_rate=lambda d: (d['modified_rate'] * 100).round(3),
        baseline_rate=lambda d: (d['baseline_rate'] * 100).round(3),
        bps_vs_baseline=lambda d: d['bps_vs_baseline'].round(1),
        share_of_loans_pct=lambda d: d['share_of_loans_pct'].round(1),
    ))

print("### C. Ever-modified rate trend + volume")
plot_vintage_outcome_trend(
    mod_cohort_ci,
    rate_col='modified_rate',
    title='Ever-modified rate by vintage (mature-enough loans, 95% CI)',
    min_pct_mature_for_ci=MIN_PCT_MATURE_FOR_CI,
)

if mod_mature_vintages:
    _, tier_mod_rates = tier_mix_and_rates(df_mod_mature, VINTAGE_COL, TIER_COL, MODIFIED_FLAG_COL)
    print("### D. Within-tier ever-modified rate heatmap")
    plot_tier_fpd_heatmap(
        tier_mod_rates,
        title='Within-tier ever-modified rate by vintage (mature-enough loans)',
    )

if len(mod_mature_vintages) >= 2:
    mod_latest, mod_prior = mod_mature_vintages[-1], mod_mature_vintages[-2]
    decomp_mom = fpd_decomposition(
        df_mod_mature[df_mod_mature['_vintage'] == mod_prior],
        df_mod_mature[df_mod_mature['_vintage'] == mod_latest],
        TIER_COL,
        MODIFIED_FLAG_COL,
    )
    print(f"### E. Mix vs rate: {_period_to_str(mod_prior)} → {_period_to_str(mod_latest)}")
    display(pd.DataFrame([{
        'modified_bps_change': round(decomp_mom['delta_fpd'] * 10000, 1),
        'mix_effect_bps': round(decomp_mom['mix_effect'] * 10000, 1),
        'rate_effect_bps': round(decomp_mom['rate_effect'] * 10000, 1),
        'interaction_bps': round(decomp_mom['interaction'] * 10000, 1),
    }]))
    plot_decomposition_waterfall(
        decomp_mom,
        label=f"{_period_to_str(mod_prior)} → {_period_to_str(mod_latest)} (ever-modified)",
    )
    mod_ref = (
        pd.Period(MODIFICATION_REFERENCE_VINTAGE, freq='M')
        if MODIFICATION_REFERENCE_VINTAGE else mod_mature_vintages[0]
    )
    if mod_ref in mod_mature_vintages and mod_ref != mod_latest:
        decomp_ref = fpd_decomposition(
            df_mod_mature[df_mod_mature['_vintage'] == mod_ref],
            df_mod_mature[df_mod_mature['_vintage'] == mod_latest],
            TIER_COL,
            MODIFIED_FLAG_COL,
        )
        print(f"### E2. vs reference {_period_to_str(mod_ref)}")
        display(pd.DataFrame([{
            'modified_bps_change': round(decomp_ref['delta_fpd'] * 10000, 1),
            'mix_effect_bps': round(decomp_ref['mix_effect'] * 10000, 1),
            'rate_effect_bps': round(decomp_ref['rate_effect'] * 10000, 1),
            'interaction_bps': round(decomp_ref['interaction'] * 10000, 1),
        }]))

psi_table = pd.DataFrame()
mod_ref = (
    pd.Period(MODIFICATION_REFERENCE_VINTAGE, freq='M')
    if MODIFICATION_REFERENCE_VINTAGE else (mod_mature_vintages[0] if mod_mature_vintages else None)
)
if mod_ref is not None and mod_ref in df_mod['_vintage'].unique():
    mature_enough = set(
        mod_cohort_ci.loc[
            mod_cohort_ci['pct_mature'].map(_pct_mature_fraction) >= PSI_MIN_PCT_MATURE,
            'vintage_month',
        ].astype(str)
    )
    ref_df = df_mod_mature[df_mod_mature['_vintage'] == mod_ref]
    psi_rows = []
    for v in mod_mature_vintages:
        if v == mod_ref or _period_to_str(v) not in mature_enough:
            continue
        cur_df = df_mod_mature[df_mod_mature['_vintage'] == v]
        tpsi = psi_categorical(ref_df[TIER_COL], cur_df[TIER_COL])
        psi_rows.append({
            'vintage_month': _period_to_str(v),
            'feature': TIER_COL,
            'psi': round(tpsi, 4),
            'flag': psi_flag(tpsi),
        })
        for col in _psi_numeric_feature_cols(df_mod_mature, post_origination_cols):
            val = psi_numeric(ref_df[col], cur_df[col])
            psi_rows.append({
                'vintage_month': _period_to_str(v),
                'feature': col,
                'psi': round(val, 4) if pd.notna(val) else np.nan,
                'flag': psi_flag(val),
            })
    if psi_rows:
        psi_table = pd.DataFrame(psi_rows)
        print(f"### F. PSI vs reference {_period_to_str(mod_ref)}")
        display(psi_table.sort_values(['vintage_month', 'feature']))
        plot_psi_heatmap(psi_table, title=f'PSI vs reference {_period_to_str(mod_ref)}')

if MOD_START_DATE_COL in df_mod.columns and 'mob_at_mod' in df_mod.columns:
    mod_timing = build_modification_timing_by_vintage(df_mod, MODIFIED_FLAG_COL)
    print("### G. Time to modification (MOB at mod_start_date)")
    if mod_timing.empty:
        print("No modified loans with mod_start_date in mature cohorts.")
    else:
        display(mod_timing.assign(
            modified_rate=lambda d: (d['modified_rate'] * 100).round(3),
            median_mob_at_mod=lambda d: d['median_mob_at_mod'].round(2),
            p25_mob_at_mod=lambda d: d['p25_mob_at_mod'].round(2),
            p75_mob_at_mod=lambda d: d['p75_mob_at_mod'].round(2),
            median_days_vintage_to_mod=lambda d: d['median_days_vintage_to_mod'].round(0),
        ))
else:
    print(f"### G. Skipped — {MOD_START_DATE_COL!r} not in pull.")

if not mod_attrib.empty:
    hot = mod_attrib.sort_values('bps_vs_baseline', ascending=False).iloc[0]
    print(
        f"\n**Summary:** Top recent vintage vs baseline: {hot['vintage_month']} "
        f"({hot['bps_vs_baseline']:+.0f} bps, {hot['modified_rate']*100:.2f}% ever-modified)."
    )
'''


def main() -> None:
    fpd_nb = json.loads(MAIN_FPD.read_text())
    FPD_PATH.write_text(json.dumps(fpd_nb, ensure_ascii=False, indent=1))

    helpers_src = HELPERS_PATH.read_text()
    mod_nb = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
            "colab": {"name": "AAL_Ever_Modified_Vintage_2026.ipynb"},
        },
        "cells": [],
    }

    for i in range(4):
        mod_nb["cells"].append(fpd_nb["cells"][i])

    mod_nb["cells"].extend(
        [
            _cell("markdown", INTRO),
            _cell("code", CONFIG),
            _cell("code", BLOCKLIST),
            _cell("code", GBQ),
            _cell("markdown", GUIDE),
            _cell("code", helpers_src),
            _cell("markdown", "## Run analytics (sections A–G)"),
            _cell("code", ANALYTICS),
        ]
    )

    MOD_PATH.write_text(json.dumps(mod_nb, ensure_ascii=False, indent=1))
    print("Wrote", MOD_PATH)
    print("Restored", FPD_PATH, "from origin/main")


if __name__ == "__main__":
    main()
