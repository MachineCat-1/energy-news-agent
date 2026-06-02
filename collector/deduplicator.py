import logging
from datetime import datetime

import numpy as np

import config

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        logger.info("首次加载 embedding 模型 shibing624/text2vec-base-chinese，可能需要几分钟...")
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("shibing624/text2vec-base-chinese")
        logger.info("Embedding 模型加载完成")
    return _model


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def deduplicate(news_items: list[dict]) -> list[dict]:
    """Semantic dedup by title embedding; keep earliest published item."""
    if not news_items:
        return []

    if not config.ENABLE_EIA_RSS:
        news_items = [item for item in news_items if item.get("source") != "EIA"]

    sorted_items = sorted(news_items, key=lambda x: x.get("published_at", ""))
    model = _get_model()
    titles = [item.get("title", "") for item in sorted_items]
    embeddings = model.encode(titles, show_progress_bar=False)

    kept: list[dict] = []
    kept_embeddings: list[np.ndarray] = []

    for item, emb in zip(sorted_items, embeddings):
        is_dup = False
        for kept_emb in kept_embeddings:
            if _cosine_similarity(emb, kept_emb) > config.SIMILARITY_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            kept.append(item)
            kept_embeddings.append(emb)

    if len(kept) > config.MAX_NEWS_PER_RUN:
        from output.brief_selection import DOMESTIC_SOURCE_PRIORITY

        kept.sort(key=lambda x: x.get("published_at", "") or "", reverse=True)
        kept.sort(key=lambda x: DOMESTIC_SOURCE_PRIORITY.get(x.get("source", ""), 100))
        kept = kept[: config.MAX_NEWS_PER_RUN]

    logger.info("去重: %d -> %d 条", len(news_items), len(kept))
    return kept
