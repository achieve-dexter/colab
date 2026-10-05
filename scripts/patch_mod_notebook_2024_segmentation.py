"""Extend ever-mod notebook: 2024-2026 pull, YoY views, Part I clustering."""
import json
from pathlib import Path

NB = Path("/workspace/AAL_Ever_Modified_Vintage_2026.ipynb")

HELPER_FUNCS = '''

def build_yoy_mod_calendar_table(df_mod, target, mature_col='is_mature_mod'):
    """Ever-modified rate by calendar month and origination year (mature-enough loans)."""
    d = df_mod[df_mod[mature_col]].copy()
    d['cal_year'] = d['_vintage'].apply(lambda p: int(p.year))
    d['cal_month'] = d['_vintage'].apply(lambda p: int(p.month))
    agg = (
        d.groupby(['cal_year', 'cal_month'], observed=True)
        .agg(loan_count=(target, 'size'), modified_rate=(target, 'mean'))
        .reset_index()
    )
    agg['month_name'] = agg['cal_month'].apply(
        lambda m: pd.Timestamp(2000, int(m), 1).strftime('%b')
    )
    return agg.sort_values(['cal_month', 'cal_year'])


def plot_yoy_mod_calendar_months(yoy_df, title='Ever-modified rate — same calendar month by origination year'):
    if yoy_df is None or yoy_df.empty:
        print('YoY calendar-month chart skipped.')
        return
    years = sorted(yoy_df['cal_year'].unique())
    months = sorted(yoy_df['cal_month'].unique())
    fig, ax = plt.subplots(figsize=(12, 5))
    for yr in years:
        sub = yoy_df[yoy_df['cal_year'] == yr].set_index('cal_month').reindex(months)
        ax.plot(
            months,
            sub['modified_rate'].astype(float) * 100,
            marker='o',
            label=str(yr),
        )
    ax.set_xticks(months)
    ax.set_xticklabels([pd.Timestamp(2000, m, 1).strftime('%b') for m in months])
    ax.set_ylabel('Ever-modified rate (%)')
    ax.set_xlabel('Calendar month (vintage month)')
    ax.set_title(title)
    ax.legend(title='Origination year')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def _prepare_mod_segmentation_features(df_in, post_origination_cols, modified_flag_col):
    """Numeric + label-encoded categoricals for clustering (pre-origination only)."""
    from sklearn.preprocessing import LabelEncoder

    drop_meta = {
        modified_flag_col,
        'cluster_label',
        '_vintage',
        'is_mature_mod',
        'days_since_vintage_start',
        '_mod_start',
        'days_vintage_to_mod',
        'mob_at_mod',
    }
    exclude = set(post_origination_cols) | drop_meta
    work = df_in.drop(columns=[c for c in exclude if c in df_in.columns], errors='ignore')
    num_cols = [
        c for c in work.select_dtypes(include=[np.number]).columns
        if c not in exclude and work[c].nunique(dropna=True) > 1
    ]
    cat_cols = [
        c for c in work.select_dtypes(include=['object', 'category']).columns
        if c not in exclude and work[c].nunique(dropna=True) <= 50
    ]
    X = work[num_cols].copy()
    for col in cat_cols[:15]:
        le = LabelEncoder()
        X[col] = le.fit_transform(work[col].astype(str).fillna('MISSING'))
    X = X.replace([np.inf, -np.inf], np.nan)
    const = [c for c in X.columns if X[c].nunique(dropna=True) <= 1]
    X = X.drop(columns=const, errors='ignore')
    return X


def build_cluster_vintage_tables(df_seg, vintage_col='_vintage', cluster_col='cluster_label', target='flag_modified'):
    """Cluster mix and modified rate by vintage (string vintage labels)."""
    tmp = df_seg.copy()
    tmp['vintage_month'] = tmp[vintage_col].map(_period_to_str)
    mix = pd.crosstab(tmp['vintage_month'], tmp[cluster_col], normalize='index')
    rates = tmp.groupby([cluster_col], observed=True)[target].mean()
    rate_by_vintage = tmp.groupby(['vintage_month', cluster_col], observed=True)[target].mean().unstack(cluster_col)
    return mix, rates, rate_by_vintage

'''

SEGMENTATION_CELL = '''# --- Part I: Pre-origination clustering (why is ever-mod rising?) ---
if not globals().get('RUN_MODIFICATION_SEGMENTATION', True):
    print('RUN_MODIFICATION_SEGMENTATION=False — skip clustering.')
else:
    from sklearn.cluster import KMeans
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    seg_df = df_mod_mature.copy()
    X_seg = _prepare_mod_segmentation_features(seg_df, post_origination_cols, MODIFIED_FLAG_COL)
    if X_seg.shape[1] < 3:
        raise ValueError('Not enough pre-origination features for clustering.')

    imp = SimpleImputer(strategy='median')
    X_imp = imp.fit_transform(X_seg)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)

    k = int(globals().get('MOD_SEGMENTATION_N_CLUSTERS', 4))
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    seg_df['cluster_label'] = km.fit_predict(X_scaled)

    print('### I1. Cluster profiles (mature-enough book)')
    prof = (
        seg_df.groupby('cluster_label', observed=True)
        .agg(
            loans=('cluster_label', 'size'),
            modified_rate=(MODIFIED_FLAG_COL, 'mean'),
            median_mob_at_mod=('mob_at_mod', 'median'),
        )
        .assign(share=lambda d: d['loans'] / d['loans'].sum())
    )
    display(prof.assign(
        modified_rate=lambda d: (d['modified_rate'] * 100).round(3),
        share=lambda d: (d['share'] * 100).round(2),
        median_mob_at_mod=lambda d: d['median_mob_at_mod'].round(2),
    ))

    mix, cluster_rates, rate_by_vintage = build_cluster_vintage_tables(
        seg_df, target=MODIFIED_FLAG_COL,
    )
    print('### I2. Cluster mix by vintage (row % — watch mix shift in recent months)')
    display((mix * 100).round(2).tail(int(globals().get('MOD_SEGMENTATION_VINTAGE_TAIL', 18))))

    print('### I3. Ever-modified rate by cluster × vintage (recent tail)')
    display((rate_by_vintage.tail(int(globals().get('MOD_SEGMENTATION_VINTAGE_TAIL', 18))) * 100).round(3))

    _focus = int(globals().get('MODIFICATION_TRAILING_VINTAGES', 5))
    recent_vs = mod_mature_vintages[-_focus:] if len(mod_mature_vintages) >= _focus else mod_mature_vintages
    prior_vs = [v for v in mod_mature_vintages if v not in recent_vs]
    if recent_vs and prior_vs:
        recent = seg_df[seg_df['_vintage'].isin(recent_vs)]
        prior = seg_df[seg_df['_vintage'].isin(prior_vs)]
        mix_r = recent['cluster_label'].value_counts(normalize=True)
        mix_p = prior['cluster_label'].value_counts(normalize=True)
        comp = pd.DataFrame({
            'share_recent_%': (mix_r * 100).round(2),
            'share_prior_%': (mix_p.reindex(mix_r.index, fill_value=0) * 100).round(2),
            'mod_rate_recent_%': (recent.groupby('cluster_label')[MODIFIED_FLAG_COL].mean() * 100).round(3),
            'mod_rate_prior_%': (prior.groupby('cluster_label')[MODIFIED_FLAG_COL].mean() * 100).round(3),
        }).fillna(0)
        comp['mix_pp_change'] = (comp['share_recent_%'] - comp['share_prior_%']).round(2)
        comp['rate_pp_change'] = (comp['mod_rate_recent_%'] - comp['mod_rate_prior_%']).round(3)
        print(f'### I4. Recent {_focus} mature vintages vs earlier — cluster mix & modified rate')
        display(comp.sort_values('mix_pp_change', ascending=False))

    fig, ax = plt.subplots(figsize=(14, 5))
    tail_mix = mix.tail(int(globals().get('MOD_SEGMENTATION_VINTAGE_TAIL', 18)))
    tail_mix.plot(kind='bar', stacked=True, ax=ax, colormap='tab10')
    ax.set_title('Cluster mix by vintage (recent window)')
    ax.set_xlabel('Vintage month')
    ax.set_ylabel('Share of loans')
    ax.legend(title='Cluster', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
    plt.tight_layout()
    plt.show()

    print(
        '**How to read I4:** A rising ever-mod rate in recent months is often '
        'higher **modified rate within clusters** (rate_pp_change), '
        'more volume in high-mod clusters (mix_pp_change), or both — same logic as section E.'
    )
'''

YOY_BLOCK = '''
yoy_mod = build_yoy_mod_calendar_table(df_mod, MODIFIED_FLAG_COL)
print("### H. YoY same calendar month — ever-modified rate (2024 vs 2025 vs 2026)")
if yoy_mod.empty:
    print("No mature loans for YoY calendar view.")
else:
    display(
        yoy_mod.assign(modified_rate=lambda d: (d['modified_rate'] * 100).round(3))
        .pivot_table(index='month_name', columns='cal_year', values='modified_rate', aggfunc='first')
        .sort_index(key=lambda s: pd.to_datetime(s, format='%b').month)
    )
    plot_yoy_mod_calendar_months(yoy_mod)

'''


def main() -> None:
    nb = json.loads(NB.read_text())

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if src.startswith("# --- Ever-modified vintage monitoring configuration"):
            nb["cells"][i]["source"] = [
                "# --- Ever-modified vintage monitoring configuration ---\n"
                "import pandas as pd\n\n"
                "VINTAGE_PULL_START = '2024-01-01'  # BigQuery: 2024–2026 YTD vintages\n"
                "MODEL_ERA_START = VINTAGE_PULL_START  # alias used in filters\n"
                "VINTAGE_COL = 'loan_vintage_month'\n"
                "TIER_COL = 'borrower_origination_risk_group'\n"
                "MODIFIED_FLAG_COL = 'flag_modified'\n"
                "MOD_START_DATE_COL = 'mod_start_date'\n\n"
                "MODIFICATION_MIN_DAYS_ON_BOOK = 120\n"
                "MODIFICATION_REFERENCE_VINTAGE = '2024-01'  # PSI / decomposition reference\n"
                "MODIFICATION_TRAILING_VINTAGES = 5  # recent consecutive months focus\n"
                "MIN_PCT_MATURE_FOR_CI = 0.80\n"
                "PSI_MIN_PCT_MATURE = 0.80\n"
                "MOB_DAYS_PER_MONTH = 30\n\n"
                "RUN_MODIFICATION_SEGMENTATION = True\n"
                "MOD_SEGMENTATION_N_CLUSTERS = 4\n"
                "MOD_SEGMENTATION_VINTAGE_TAIL = 24  # rows shown in cluster mix tables\n\n"
                "AS_OF_DATE = pd.Timestamp.today().normalize()\n"
                "NOTEBOOK_REV = '2026-10-mod-2024yoy-segmentation-v1'\n\n"
                "print(\n"
                "    f'Config: VINTAGE_PULL_START={VINTAGE_PULL_START}, '\n"
                "    f'MODIFIED_FLAG_COL={MODIFIED_FLAG_COL}, '\n"
                "    f'MODIFICATION_MIN_DAYS_ON_BOOK={MODIFICATION_MIN_DAYS_ON_BOOK}, '\n"
                "    f'RUN_MODIFICATION_SEGMENTATION={RUN_MODIFICATION_SEGMENTATION}, '\n"
                "    f'AS_OF_DATE={AS_OF_DATE.date()}, NOTEBOOK_REV={NOTEBOOK_REV}'\n"
                ")\n"
            ]
            break

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "where DATE(loan_vintage_month) >= DATE('{MODEL_ERA_START}')" in src:
            src = src.replace(
                "print(f\"Loaded {len(df):,} rows | vintages from {MODEL_ERA_START}\")",
                "print(f\"Loaded {len(df):,} rows | vintages from {VINTAGE_PULL_START}\")",
            )
            nb["cells"][i]["source"] = [src]
            break

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "def _pct_mature_fraction(val):" in src and "build_yoy_mod_calendar_table" not in src:
            nb["cells"][i]["source"] = [src.rstrip() + HELPER_FUNCS]
            break

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if src.startswith("# AAL — Ever-modified vintage monitoring"):
            nb["cells"][i]["source"] = [
                "# AAL — Ever-modified vintage monitoring\n\n"
                "Vintage analysis **2024 → 2026 YTD** on `flag_modified` and `mod_start_date`.\n\n"
                "**Run order:** Authenticate → Config → BigQuery pull → Helpers → **A–H vintage analytics** → **I clustering**.\n"
            ]
            break

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if src.startswith("## Business guide"):
            nb["cells"][i]["source"] = [
                "## Business guide\n\n"
                "| Question | Section |\n"
                "|----------|--------|\n"
                "| Vintage path 2024–2026 | **A**, **C** |\n"
                "| Recent months vs baseline | **B** |\n"
                "| Tier concentration | **D** |\n"
                "| Mix vs rate (tier) | **E** |\n"
                "| Booking mix shift | **F** PSI |\n"
                "| Timing of mods | **G** |\n"
                "| **2024 vs 2025 vs 2026** same month | **H** |\n"
                "| **Pre-orig clusters** driving recent rise | **I** |\n"
            ]
            break

    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if "### G. Time to modification" in src and "### H. YoY" not in src:
            anchor = "if not mod_attrib.empty:"
            src = src.replace(anchor, YOY_BLOCK + "\n" + anchor)
            nb["cells"][i]["source"] = [src]
            break

    if not any("Part I: Pre-origination clustering" in "".join(c.get("source", [])) for c in nb["cells"]):
        nb["cells"].append(
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Part I — Pre-origination clustering\n\n"
                    "Unsupervised **K-means** on pre-origination features (no `flag_modified` / `mod_start_date` in inputs). "
                    "Compare **cluster mix** and **within-cluster ever-mod rates** for the last several mature vintages vs earlier 2024–2025 "
                    "to explain a multi-month increase (mix shift vs higher mod rate within segments).\n"
                ],
            }
        )
        nb["cells"].append(
            {
                "cell_type": "code",
                "metadata": {},
                "source": [SEGMENTATION_CELL],
                "outputs": [],
                "execution_count": None,
            }
        )

    NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print("patched", NB)


if __name__ == "__main__":
    main()
