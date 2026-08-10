"""Tiền lọc cận nghĩa bằng similarity — file 03, Agent 3, "Ghi chú kỹ thuật".

Spec: "Chỉ gửi cho Agent 3 các nhóm có similarity > ngưỡng (vd 0.75) — đây là bước lọc
trước bằng thuật toán rẻ tiền, để LLM (đắt hơn) chỉ xử lý các ứng viên đã được lọc."

LỰA CHỌN TRIỂN KHAI: spec gợi ý DeepSeek embedding API hoặc sentence-transformers chạy
local. Cả hai đều có vấn đề ở giai đoạn này:
  - DeepSeek hiện KHÔNG cung cấp endpoint embedding công khai;
  - sentence-transformers kéo theo torch (~2GB), quá nặng cho một bước lọc rẻ tiền, và
    mâu thuẫn với chính mục đích "thuật toán rẻ" của bước này.

Nên ở đây dùng TF-IDF cosine trên định nghĩa tiếng Anh (thuần Python, không dependency).
Nó đủ tốt cho việc lọc thô, và `EmbeddingBackend` bên dưới để sẵn chỗ cắm embedding
thật khi cần nâng chất lượng — chỉ cần implement `embed()` và truyền vào
`group_similar_senses`, không phải sửa cluster service.
"""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z]+")

# Stopword tối thiểu: định nghĩa từ điển đầy "to/of/the/a", nếu không loại thì mọi cặp
# định nghĩa đều "giống nhau" một cách giả tạo.
_STOPWORDS = {
    "a", "an", "the", "to", "of", "in", "on", "for", "with", "or", "and", "that",
    "this", "is", "are", "be", "being", "been", "by", "as", "at", "it", "its",
    "something", "someone", "sth", "sb", "which", "when", "who",
}


@dataclass
class SenseVector:
    sense_id: str
    surface_form: str
    definition_en: str


class EmbeddingBackend(ABC):
    """Điểm cắm cho embedding thật (sentence-transformers, API...) về sau."""

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


def _tfidf_vectors(docs: Sequence[str]) -> list[dict[str, float]]:
    tokenized = [_tokenize(d) for d in docs]
    n = len(tokenized)
    df: Counter[str] = Counter()
    for tokens in tokenized:
        df.update(set(tokens))

    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        tf = Counter(tokens)
        total = sum(tf.values()) or 1
        vec = {
            term: (count / total) * math.log((1 + n) / (1 + df[term]) + 1)
            for term, count in tf.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({k: v / norm for k, v in vec.items()})
    return vectors


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(term, 0.0) for term, value in a.items())


def group_similar_senses(
    senses: Sequence[SenseVector],
    threshold: float = 0.75,
    max_group_size: int = 6,
    backend: EmbeddingBackend | None = None,
) -> list[list[SenseVector]]:
    """Gom các sense có similarity > `threshold` thành nhóm ứng viên cho Agent 3.

    Dùng single-linkage (union-find): nếu A~B và B~C thì A, B, C vào cùng nhóm — hợp lý
    ở đây vì cụm cận nghĩa thực tế thường là chuỗi liên tiếp
    (significant ~ substantial ~ considerable).
    """
    if len(senses) < 2:
        return []

    if backend is not None:
        raw = backend.embed([s.definition_en for s in senses])
        vectors = [_normalize_dense(v) for v in raw]
        sim = _dense_cosine
    else:
        vectors = _tfidf_vectors([s.definition_en for s in senses])  # type: ignore[assignment]
        sim = cosine  # type: ignore[assignment]

    parent = list(range(len(senses)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for i in range(len(senses)):
        for j in range(i + 1, len(senses)):
            if sim(vectors[i], vectors[j]) >= threshold:  # type: ignore[arg-type]
                union(i, j)

    groups: dict[int, list[SenseVector]] = {}
    for idx, sense in enumerate(senses):
        groups.setdefault(find(idx), []).append(sense)

    return [g[:max_group_size] for g in groups.values() if len(g) >= 2]


def _normalize_dense(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _dense_cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
