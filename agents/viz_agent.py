"""
VizAgent — 2D UMAP embedding map of all jobs in ChromaDB.
Two-panel interactive HTML: left=domain, right=outcome.
Gold star = new/highlighted job.
Axis-word summary via Spearman(TF-IDF, UMAP coord).
Dense-region keyword labels via cluster centroids.
"""
import os
import re

import numpy as np

import config


# ── Final-round jobs (deep interview — panel/technical rounds) ────────────────
# Matched by substring against ChromaDB filename metadata (case-insensitive).
# Add new entries here as needed.
FINAL_ROUND_SUBSTRINGS = [
    ("Senior Scientist, Cell Therapy Discovery at AstraZeneca",         "AZ"),
    ("Scientist II - Computational Biology _PC 892 _ Miltenyi",         "Miltenyi"),
    ("Senior Scientist – Research Computational Biology (ARIA)",         "Amgen"),
    ("Data Scientist, Computational Biology - Silver Spring",            "UTHR"),
    ("AI Solution Engineer _ KellyOCG",                                  "KellyOCG (AZ)"),
    ("steampunk",                                                         "Steampunk"),
]

# ── Outcome colours ───────────────────────────────────────────────────────────
OUTCOME_COLORS = {
    "applied":      "#888888",
    "rejected":     "#E05C5C",
    "0_slow":       "#E09A3A",
    "interviewed":  "#4A90D9",
    "interviewing": "#3ABD7A",
    "new":          "#FFD700",
}
OUTCOME_ORDER = ["new", "interviewing", "interviewed", "applied", "0_slow", "rejected"]

# ── Domain keyword patterns (ported from job_rag/analysis/umap_emb_plot.py) ───
_DOMAIN_PATTERNS = {
    "single-cell":    [r"single.?cell", r"scrna", r"scatac", r"10x genomics",
                       r"seurat", r"scanpy"],
    "cell-therapy":   [r"cell.?therap", r"car.?t", r"adoptive", r"tcr.?t",
                       r"tumor.?infiltrat", r"nk cell"],
    "structural":     [r"structural bio", r"cryo.?em", r"protein struct",
                       r"molecular dock", r"alphafold", r"rosetta"],
    "clinical":       [r"\bclinical\b", r"\bhl7\b", r"\bfhir\b", r"\behr\b",
                       r"clinical trial", r"clinical data"],
    "AI/ML":          [r"machine.?learn", r"deep.?learn", r"\bllm\b", r"\bgpt\b",
                       r"neural net", r"\bmlops\b", r"transformer",
                       r"reinforcement"],
    "spatial":        [r"spatial.?omic", r"spatial transcr", r"visium",
                       r"slide.?seq", r"merfish"],
    "production":     [r"\bgmp\b", r"\bcmc\b", r"process dev", r"scale.?up",
                       r"\bcdmo\b", r"tech transfer", r"\bcgmp\b"],
    "RWE/healthcare": [r"\brwe\b", r"\brwd\b", r"real.?world", r"\bhealthcare\b",
                       r"claims data", r"electronic health", r"\bpayer\b"],
    "R&D/discovery":  [r"\br&d\b", r"\bdiscovery\b", r"\bpreclinical\b",
                       r"\btranslational\b", r"early.?stage"],
}
DOMAIN_COLORS = {
    "single-cell":    "#1F77B4",
    "cell-therapy":   "#D62728",
    "structural":     "#9467BD",
    "clinical":       "#FF7F0E",
    "AI/ML":          "#2CA02C",
    "spatial":        "#17BECF",
    "production":     "#8C564B",
    "RWE/healthcare": "#BCBD22",
    "R&D/discovery":  "#E377C2",
    "other":          "#7F7F7F",
}


def _company_label(metadata: dict) -> str:
    folder = metadata.get("job_folder", "")
    leaf = folder.split("/")[-1]
    name = re.sub(r"^\d[\d.]*_?", "", leaf)
    return name if name else leaf


def _tag_domain(text: str) -> str:
    t = text.lower()
    scores = {d: sum(len(re.findall(p, t)) for p in pats)
              for d, pats in _DOMAIN_PATTERNS.items()}
    best = max(scores.values())
    if best == 0:
        return "other"
    return next(d for d, s in scores.items() if s == best)


def _axis_words(tfidf_matrix, vocab, coords, top_n: int = 5):
    """Spearman correlation of each TF-IDF feature vs UMAP-1 and UMAP-2."""
    from scipy.stats import spearmanr
    r1 = np.array([spearmanr(tfidf_matrix[:, j], coords[:, 0]).statistic
                   for j in range(len(vocab))])
    r2 = np.array([spearmanr(tfidf_matrix[:, j], coords[:, 1]).statistic
                   for j in range(len(vocab))])
    return {
        "x_pos": vocab[np.argsort(r1)[-top_n:][::-1]].tolist(),
        "x_neg": vocab[np.argsort(r1)[:top_n]].tolist(),
        "y_pos": vocab[np.argsort(r2)[-top_n:][::-1]].tolist(),
        "y_neg": vocab[np.argsort(r2)[:top_n]].tolist(),
    }


def _region_labels(coords, documents, n_clusters: int = 8, top_n: int = 3):
    """
    K-means cluster centroids → top TF-IDF terms per cluster → region label annotations.
    Returns list of {x, y, label} dicts.
    """
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_ids = km.fit_predict(coords)

    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=3000,
                          stop_words="english", min_df=2, max_df=0.8)
    tfidf = vec.fit_transform(documents).toarray()
    vocab = np.array(vec.get_feature_names_out())

    annotations = []
    for c in range(n_clusters):
        mask = cluster_ids == c
        if mask.sum() < 3:
            continue
        centroid = coords[mask].mean(axis=0)
        mean_tfidf = tfidf[mask].mean(axis=0)
        top_terms = vocab[np.argsort(mean_tfidf)[-top_n:][::-1]].tolist()
        annotations.append({
            "x": float(centroid[0]),
            "y": float(centroid[1]),
            "label": " · ".join(top_terms),
        })
    return annotations


class VizAgent:
    """
    Pull all embeddings from ChromaDB, run UMAP, render a two-panel interactive
    Plotly HTML map (domain + outcome) with axis-word annotations and region labels.
    """

    def __init__(self, collection):
        self._collection = collection

    def run(self, highlight_id: str | None = None, output_path: str | None = None) -> str:
        """
        Generate the 2D UMAP map.
        highlight_id: ChromaDB doc_id (== jd_path) of the new job to highlight.
        output_path: where to save the HTML. Defaults to {PROJECT_DIR}/embedding_map.html.
        Returns the output path.
        """
        if output_path is None:
            output_path = os.path.join(config._PROJECT_DIR, "embedding_map.html")

        print("  Fetching embeddings from DB...")
        results = self._collection.get(include=["embeddings", "metadatas", "documents"])
        ids        = results["ids"]
        embeddings = np.array(results["embeddings"])
        metadatas  = results["metadatas"]
        documents  = results["documents"]

        if len(ids) < 5:
            print("  [viz] Not enough data points to plot (need ≥ 5).")
            return output_path

        print(f"  Running UMAP on {len(ids)} points...")
        try:
            import umap as umap_lib
        except ImportError:
            print("  [viz] umap-learn not installed. Run: pip install umap-learn")
            return output_path

        reducer = umap_lib.UMAP(n_components=2, random_state=42,
                                n_neighbors=15, min_dist=0.1, metric="cosine")
        coords = reducer.fit_transform(embeddings)

        highlight_idx = ids.index(highlight_id) if highlight_id and highlight_id in ids else None

        # ── TF-IDF for axis words + region labels ─────────────────────────────
        print("  Computing TF-IDF axis annotations...")
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(ngram_range=(1, 2), max_features=4000,
                              stop_words="english", min_df=3, max_df=0.85,
                              sublinear_tf=True)
        tfidf_mat  = vec.fit_transform([d or "" for d in documents]).toarray()
        vocab      = np.array(vec.get_feature_names_out())
        axis_words = _axis_words(tfidf_mat, vocab, coords, top_n=4)
        regions    = _region_labels(coords, [d or "" for d in documents],
                                    n_clusters=9, top_n=3)

        # ── Tag domains ───────────────────────────────────────────────────────
        combined = [m.get("filename", "") + " " + (d or "")
                    for m, d in zip(metadatas, documents)]
        domains  = [_tag_domain(t) for t in combined]

        self._save_html(
            ids, coords, metadatas, domains,
            highlight_idx, axis_words, regions, output_path,
        )

        print(f"  Saved map → {output_path}")
        return output_path

    def _make_traces(self, ids, coords, metadatas, color_by: str,
                     color_map: dict, color_order: list,
                     tag_list: list, highlight_idx) -> list:
        """Build Plotly traces grouped by category for a single panel."""
        import plotly.graph_objects as go

        groups: dict = {k: {"x": [], "y": [], "text": []} for k in color_order}

        for i, (doc_id, meta) in enumerate(zip(ids, metadatas)):
            if i == highlight_idx:
                key = "new"
            else:
                key = tag_list[i]
                if key not in groups:
                    key = "other" if "other" in groups else color_order[-1]

            label = _company_label(meta)
            hover = (
                f"<b>{label}</b><br>"
                f"Outcome: {meta.get('outcome', 'applied')}<br>"
                f"{color_by.capitalize()}: {tag_list[i]}<br>"
                f"<i>{meta.get('filename', '')[:60]}</i>"
            )
            groups[key]["x"].append(float(coords[i, 0]))
            groups[key]["y"].append(float(coords[i, 1]))
            groups[key]["text"].append(hover)

        traces = []
        for key in color_order:
            g = groups[key]
            if not g["x"]:
                continue
            is_new = key == "new"
            color  = OUTCOME_COLORS["new"] if is_new else color_map.get(key, "#888888")
            traces.append(go.Scatter(
                x=g["x"], y=g["y"],
                mode="markers",
                name=key,
                marker=dict(
                    color=color,
                    size=18 if is_new else 7,
                    symbol="star" if is_new else "circle",
                    line=dict(width=2 if is_new else 0.4,
                              color="black" if is_new else color),
                    opacity=1.0 if is_new else 0.78,
                ),
                text=g["text"],
                hovertemplate="%{text}<extra></extra>",
            ))
        return traces

    def _save_html(self, ids, coords, metadatas, domains,
                   highlight_idx, axis_words, regions, output_path):
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        outcomes = [m.get("outcome", "applied") for m in metadatas]

        new_label = ""
        if highlight_idx is not None:
            new_label = f"  ★ {_company_label(metadatas[highlight_idx])}"

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=["Coloured by Domain", "Coloured by Outcome"],
            horizontal_spacing=0.08,
        )

        domain_order = list(DOMAIN_COLORS.keys()) + ["new"]
        outcome_order_full = OUTCOME_ORDER

        for trace in self._make_traces(ids, coords, metadatas, "domain",
                                       DOMAIN_COLORS, domain_order,
                                       domains, highlight_idx):
            fig.add_trace(trace, row=1, col=1)

        for trace in self._make_traces(ids, coords, metadatas, "outcome",
                                       OUTCOME_COLORS, outcome_order_full,
                                       outcomes, highlight_idx):
            t = go.Scatter(trace)
            t.showlegend = False
            fig.add_trace(t, row=1, col=2)

        # ── Final-round star overlay (both panels) ────────────────────────────
        # Match by filename substring (case-insensitive) against FINAL_ROUND_SUBSTRINGS.
        first_final = True
        for i, meta in enumerate(metadatas):
            if i == highlight_idx:
                continue
            fname = meta.get("filename", "").lower()
            matched_label = None
            for substr, short_label in FINAL_ROUND_SUBSTRINGS:
                if substr.lower() in fname:
                    matched_label = short_label
                    break
            if matched_label is None:
                continue
            x, y = float(coords[i, 0]), float(coords[i, 1])
            hover = (
                f"<b>⭐ {matched_label} (final round)</b><br>"
                f"Outcome: {meta.get('outcome', '?')}<br>"
                f"<i>{meta.get('filename', '')[:60]}</i>"
            )
            for col in (1, 2):
                fig.add_trace(go.Scatter(
                    x=[x], y=[y],
                    mode="markers+text",
                    marker=dict(symbol="star", size=16, color="#FF4500",
                                line=dict(color="darkred", width=1.5)),
                    text=[matched_label],
                    textposition="top center",
                    textfont=dict(size=8, color="#CC2200", family="Calibri bold"),
                    hovertext=[hover],
                    hovertemplate="%{hovertext}<extra></extra>",
                    showlegend=(col == 1 and first_final),
                    name="final round ⭐",
                    legendgroup="final_round",
                ), row=1, col=col)
            first_final = False

        # ── Axis-word annotations (left panel) ───────────────────────────────
        aw = axis_words

        axis_text = (
            f"← {aw['x_neg'][0]}, {aw['x_neg'][1]}   "
            f"{aw['x_pos'][0]}, {aw['x_pos'][1]} →<br>"
            f"↓ {aw['y_neg'][0]}, {aw['y_neg'][1]}   "
            f"{aw['y_pos'][0]}, {aw['y_pos'][1]} ↑"
        )
        fig.add_annotation(
            x=0.01, y=0.01, xref="x domain", yref="y domain",
            text=axis_text, showarrow=False, font=dict(size=9, color="#555555"),
            align="left", bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#CCCCCC", borderwidth=1,
            row=1, col=1,
        )

        # ── Region keyword labels (left panel only) ───────────────────────────
        for region in regions:
            fig.add_annotation(
                x=region["x"], y=region["y"],
                xref="x", yref="y",
                text=f"<i>{region['label']}</i>",
                showarrow=False,
                font=dict(size=8, color="#333333"),
                bgcolor="rgba(255,255,255,0.6)",
                bordercolor="rgba(180,180,180,0.4)",
                borderwidth=1,
                row=1, col=1,
            )

        fig.update_layout(
            title=dict(
                text=f"Job Application Embedding Map (UMAP · {len(ids)} JDs){new_label}",
                font=dict(size=15),
            ),
            width=1300, height=680,
            template="plotly_white",
            hovermode="closest",
            font=dict(family="Calibri, sans-serif", size=12),
            legend=dict(title="Domain", itemsizing="constant"),
        )
        fig.update_xaxes(title_text="UMAP-1")
        fig.update_yaxes(title_text="UMAP-2")

        fig.write_html(output_path, include_plotlyjs="cdn")

