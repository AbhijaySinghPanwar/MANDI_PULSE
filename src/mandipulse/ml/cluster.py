"""Model C: market segmentation (spec 9.3).

KMeans on standardised market x commodity features (analysis/queries/ml/cluster_features.sql);
k chosen from ml.cluster_k_range: the largest k whose silhouette is within 0.02 of the best
(silhouettes for k = 3-5 differ by < 0.02, and k = 5 gives clearly distinct, nameable segments).
Each cluster is named in plain English from its centroid (z-scores).
"""

import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from mandipulse.config import get_settings
from mandipulse.ml.evaluate import REPORT_ML_DIR, save_artifacts
from mandipulse.queries import QUERY_ROOT, TABLE_ROOT, run_sql

SILHOUETTE_TOLERANCE = 0.02
FEATURES = [
    "cv",
    "price_index",
    "report_freq",
    "seasonal_amplitude",
    "crash_rate",
    "n_markets_within_50km",
]


def load_features() -> pd.DataFrame:
    df = run_sql((QUERY_ROOT / "ml" / "cluster_features.sql").read_text(encoding="utf-8"))
    (TABLE_ROOT / "ml").mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLE_ROOT / "ml" / "cluster_features.csv", index=False)
    return df


def _matrix(df: pd.DataFrame) -> np.ndarray:
    x = df[FEATURES].astype(float).copy()
    x["n_markets_within_50km"] = np.log1p(x["n_markets_within_50km"])  # long right tail
    return x.to_numpy()


def name_cluster(z: pd.Series) -> str:
    """Plain-English name from the centroid's z-scores (most distinctive traits first)."""
    if z["report_freq"] <= -1.0 and z["cv"] >= 1.0:
        return "Erratic & under-priced, thin reporting"
    if z["price_index"] >= 1.0 and z["n_markets_within_50km"] <= -0.8:
        return "Isolated premium market"
    if z["price_index"] <= -0.5 and z["report_freq"] <= -0.8:
        return "Under-priced, sparse reporting"
    if z["cv"] >= 0.7 and z["crash_rate"] >= 0.7:
        return "Volatile & crash-prone"
    if z["cv"] <= -0.4 and z["report_freq"] >= 0.3:
        return "Stable, regular market"
    if z["n_markets_within_50km"] >= 0.6:
        return "Well-connected market"
    return "Typical market"


def run_clustering() -> dict:
    cfg = get_settings()["ml"]
    seed = cfg["random_seed"]
    df = load_features()
    scaler = StandardScaler()
    x = scaler.fit_transform(_matrix(df))
    scores, fits = {}, {}
    for k in cfg["cluster_k_range"]:
        km = KMeans(n_clusters=k, n_init=20, random_state=seed).fit(x)
        scores[k] = round(float(silhouette_score(x, km.labels_, random_state=seed)), 4)
        fits[k] = km
    # Silhouettes are close for small k, so take the MOST detailed k whose separation is within
    # SILHOUETTE_TOLERANCE of the best (more, still well-separated, nameable segments).
    best = max(scores.values())
    k = max(kk for kk, s in scores.items() if s >= best - SILHOUETTE_TOLERANCE)
    km = fits[k]
    df["cluster_id"] = km.labels_
    centroids = pd.DataFrame(km.cluster_centers_, columns=FEATURES)
    names = {i: name_cluster(centroids.loc[i]) for i in centroids.index}
    # make duplicate names unique by their next most distinctive trait
    seen: dict[str, int] = {}
    for i in sorted(names, key=lambda i: -int((df["cluster_id"] == i).sum())):
        n = names[i]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[i] = f"{n} ({seen[n]})"
    df["cluster_name"] = df["cluster_id"].map(names)

    profile = (
        df.groupby(["cluster_id", "cluster_name"])
        .agg(
            n_series=("market_key", "size"),
            **{f: (f, "median") for f in FEATURES},
            n_suspect_series=("is_suspect_series", "sum"),
        )
        .reset_index()
    )
    suspect = df[df["is_suspect_series"]]
    metrics = {
        "features": FEATURES,
        "n_series": int(len(df)),
        "silhouette_by_k": {str(kk): s for kk, s in scores.items()},
        "chosen_k": int(k),
        "cluster_profiles_median": json.loads(profile.to_json(orient="records")),
        "centroid_z_scores": {
            names[i]: {f: round(float(v), 2) for f, v in centroids.loc[i].items()}
            for i in centroids.index
        },
        "suspect_series": {
            "n_in_clustering": int(len(suspect)),
            "by_cluster": suspect["cluster_name"].value_counts().to_dict(),
        },
    }
    save_artifacts(
        "market_cluster", {"kmeans": km, "scaler": scaler, "names": names}, metrics, FEATURES
    )
    df.to_csv(REPORT_ML_DIR / "market_clusters.csv", index=False)
    return metrics


if __name__ == "__main__":
    print(json.dumps(run_clustering(), indent=2))
