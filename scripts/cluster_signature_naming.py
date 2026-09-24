"""Logic for automated cluster signature naming (injected into notebook alignment cell)."""

CLUSTER_NAMING_SOURCE = r'''
def _cluster_vocab_bucket(z):
    """Map contrast z-score to low / mid / high bucket."""
    if pd.isna(z):
        return 1
    if z >= 0.45:
        return 2
    if z <= -0.45:
        return 0
    return 1


# Controlled vocabulary (low, mid, high) per naming feature
CLUSTER_FEATURE_VOCAB = {
    'loan_origination_loan_amount': ('Small loans', 'Mid-size loans', 'Large loans'),
    'borrower_origination_risk_group': ('Low tier', 'Mid tier', 'High tier'),
    'loan_origination_interest_rate': ('Lower pricing', 'Typical pricing', 'Higher pricing'),
    'loan_application_NDI_ratio': ('Stronger NDI', 'Typical NDI', 'Tighter NDI'),
    'loan_application_PTI_ratio': ('Lower PTI', 'Typical PTI', 'Higher PTI'),
    'fdr_vs_aal_payment_variance': ('Low pay variance', 'Typical pay variance', 'High pay variance'),
    'borrower_home_owner_flag': ('Renter-heavy', 'Mixed housing', 'High homeowner'),
    'days_elapsed_negotiation': ('Shorter negotiation', 'Typical negotiation', 'Longer negotiation'),
    'monthly_loan_payment_amount': ('Smaller payment', 'Mid payment', 'Larger payment'),
    'avg_monthly_draft': ('Smaller draft', 'Typical draft', 'Larger draft'),
}

CLUSTER_NAMING_FEATURES = tuple(CLUSTER_FEATURE_VOCAB.keys())
CLUSTER_NAMING_ANCHORS = ('loan_origination_loan_amount', 'borrower_origination_risk_group')


def _cluster_profile_frame(numerical_characteristics_mean):
    prof = numerical_characteristics_mean.copy()
    if 'cluster_label' in prof.columns:
        prof = prof.set_index('cluster_label')
    return prof


def _contrast_z_scores(profile_df, features):
    """Contrast each cluster vs mean of other clusters (per feature)."""
    rows = {}
    clusters = list(profile_df.index)
    for cid in clusters:
        others = [c for c in clusters if c != cid]
        if not others:
            continue
        other_mean = profile_df.loc[others, features].mean()
        std = profile_df[features].std(ddof=0).replace(0, np.nan)
        contrast = profile_df.loc[cid, features] - other_mean
        rows[cid] = (contrast / std).replace([np.inf, -np.inf], np.nan)
    return pd.DataFrame(rows).T


def _structural_phrases_for_cluster(cid, z_row, top_n=2, anchor_top_k=5):
    ranked = z_row.abs().sort_values(ascending=False)
    ranked = ranked.dropna()
    top_features = list(ranked.head(max(anchor_top_k, top_n)).index)

    selected = []
    for feat in CLUSTER_NAMING_ANCHORS:
        if feat in top_features and feat in CLUSTER_FEATURE_VOCAB:
            bucket = _cluster_vocab_bucket(z_row.get(feat))
            phrase = CLUSTER_FEATURE_VOCAB[feat][bucket]
            if phrase not in selected:
                selected.append(phrase)

    for feat in ranked.index:
        if len(selected) >= top_n + len(CLUSTER_NAMING_ANCHORS):
            break
        if feat not in CLUSTER_FEATURE_VOCAB:
            continue
        bucket = _cluster_vocab_bucket(z_row.get(feat))
        phrase = CLUSTER_FEATURE_VOCAB[feat][bucket]
        if phrase not in selected:
            selected.append(phrase)
        if len(selected) >= max(top_n, 2) + 2:  # allow up to ~4 short phrases
            break

    # Cap at 3 phrases for readability on PCA legend
    return selected[:3]


def _fpd_rank_map(cluster_default_rates):
    ordered = cluster_default_rates.sort_values()
    n = len(ordered)
    return {cid: i + 1 for i, cid in enumerate(ordered.index)}


def build_cluster_assignments_signature(numerical_characteristics_mean, cluster_default_rates):
    """Build cluster_assignment dict used by PCA plot + automated summary."""
    profile = _cluster_profile_frame(numerical_characteristics_mean)
    features = [f for f in CLUSTER_NAMING_FEATURES if f in profile.columns]
    if not features:
        raise ValueError('No naming features found in numerical_characteristics_mean.')

    z_scores = _contrast_z_scores(profile, features)
    fpd_ranks = _fpd_rank_map(cluster_default_rates)
    n_clusters = len(fpd_ranks)
    highest_fpd_id = cluster_default_rates.idxmax()

    assignment = {}
    for cid in sorted(profile.index):
        phrases = _structural_phrases_for_cluster(cid, z_scores.loc[cid])
        structural = ' · '.join(phrases) if phrases else 'Mixed profile'
        rank = fpd_ranks[cid]
        rank_suffix = f'(FPD rank {rank}/{n_clusters})'

        if cid == highest_fpd_id:
            brand = f'Cluster {cid} — Highest FPD · {structural}'
            description = (
                f'Highest FPD in this portfolio ({cluster_default_rates.loc[cid]*100:.2f}%). '
                f'Signature (vs other clusters): {structural}. {rank_suffix}'
            )
        else:
            brand = f'Cluster {cid} — {structural}'
            description = f'Pre-origination signature (vs other clusters): {structural}. {rank_suffix}'

        assignment[cid] = {
            'name': f'{brand} {rank_suffix}',
            'display_name': f'{brand} {rank_suffix}',
            'structural_name': structural,
            'description': description,
            'fpd_rank': int(rank),
            'n_clusters': int(n_clusters),
            'is_highest_fpd': bool(cid == highest_fpd_id),
            'signature_phrases': phrases,
            'contrast_z': z_scores.loc[cid].sort_values(key=abs, ascending=False).head(5).to_dict(),
        }
    return assignment
'''
