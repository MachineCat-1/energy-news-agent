import logging
import uuid

import chromadb

import config

logger = logging.getLogger(__name__)

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        _collection = client.get_or_create_collection(
            name="analysis_skills",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def save_skill(date: str, analyst_strategy: str, score: float) -> None:
    """Store high-scoring analysis strategy."""
    collection = _get_collection()
    doc_id = f"{date}_{uuid.uuid4().hex[:8]}"
    document = f"日期: {date}\n策略: {analyst_strategy}\n评分: {score}"
    collection.add(
        ids=[doc_id],
        documents=[document],
        metadatas=[{"date": date, "score": score}],
    )
    logger.info("已保存 skill memory: date=%s score=%.1f", date, score)


def recall_similar_skills(current_date: str, top_k: int = 3) -> list[dict]:
    """Recall similar high-scoring strategies."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    try:
        results = collection.query(
            query_texts=[f"日期: {current_date} 能源新闻分析策略"],
            n_results=min(top_k, collection.count()),
        )
    except Exception as exc:
        logger.warning("skill memory 召回失败: %s", exc)
        return []

    skills: list[dict] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        skills.append({"date": meta.get("date", ""), "strategy": doc, "score": meta.get("score", 0)})
    return skills
