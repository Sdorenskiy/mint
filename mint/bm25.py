"""Поиск по словам: BM25 с морфологией и бустом точных фраз."""

import logging
import os
import pickle
import re
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np

from .stemmer import english_stem, russian_stem

logger = logging.getLogger("MINT")


_BM25_TOKEN_RE = re.compile(r"[а-яёa-z0-9_-]+")

_BM25_ALNUM_RE = re.compile(r"[а-яёa-z0-9]")

_CYRILLIC_WORD_RE = re.compile(r"^[а-я]+$")

_LATIN_WORD_RE = re.compile(r"^[a-z]+$")


# Подпись формата индекса: при смене токенизации старый индекс пересобирается автоматически.
# mint20-stem3: английские слова тоже приводятся к основе (Porter2).
BM25_INDEX_SIGNATURE = "mint20-stem3"


def normalize_token(token: str) -> str:
    """Нижний регистр, ё→е; русские слова от 5 букв и английские от 4 — к основе. Короткие слова, аббревиатуры
    и слова с цифрами не трогаются. Язык определяется по каждому слову, поэтому смешанные тексты (русский
    документ с английскими терминами) обрабатываются верно."""
    t = token.lower().replace("ё", "е")
    if len(t) >= 5 and _CYRILLIC_WORD_RE.match(t):
        return russian_stem(t)
    if len(t) >= 4 and _LATIN_WORD_RE.match(t):
        return english_stem(t)
    return t


def bm25_tokenize(text):
    return [normalize_token(t) for t in _BM25_TOKEN_RE.findall((text or "").lower()) if _BM25_ALNUM_RE.search(t)]


BM25_RAW_STOP_WORDS = frozenset({
    "что", "такое", "это", "как", "для", "при", "из", "на", "в", "с", "по",
    "за", "от", "до", "о", "об", "к", "у", "и", "а", "но", "или", "не", "же",
    "бы", "ли", "также", "то", "если", "где", "когда", "потому", "который",
    "его", "ее", "их", "она", "он", "они", "мы", "вы", "я", "ты", "со", "во",
    "под", "над", "между", "через", "весь", "вся", "всё", "все", "этот", "эта",
    # вопросительные и служебные слова вопросов: в документах не встречаются, но раньше считались значимыми
    "сколько", "какой", "какая", "какое", "какие", "каких", "каким", "какими", "каков", "какова",
    "каково", "каковы", "почему", "зачем", "чем", "кто", "кого", "кому", "чей", "чья", "чьё", "чьи",
    "куда", "откуда", "можно", "нужно", "надо", "есть", "мне", "нам", "расскажи", "опиши", "подскажи",
    "скажи", "объясни", "покажи",
    # English
    "a", "an", "the", "and", "or", "but", "not", "no", "of", "in", "on", "at", "to", "for", "from", "by", "with",
    "about", "as", "into", "over", "under", "between", "through", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "has", "have", "had", "it", "its", "this", "that", "these", "those", "there", "here",
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how", "can", "could", "should", "would",
    "will", "shall", "may", "might", "must", "i", "you", "he", "she", "we", "they", "me", "us", "them", "my",
    "our", "your", "their", "if", "then", "than", "so", "also", "any", "all", "some", "such", "each", "other",
    "tell", "describe", "explain", "show", "please", "list",
})

BM25_STOP_WORDS = frozenset(normalize_token(w) for w in BM25_RAW_STOP_WORDS)


def _min_gap(a, b):
    """Минимальное расстояние между позициями из двух отсортированных списков."""
    i = j = 0
    best = 1 << 30
    while i < len(a) and j < len(b):
        d = a[i] - b[j]
        if abs(d) < best:
            best = abs(d)
            if best <= 1:
                return best
        if d < 0:
            i += 1
        else:
            j += 1
    return best


class LightweightBM25:
    """BM25 с защитой от IDF-коллапса, бустом точной фразы и близости соседних слов запроса."""

    PAIR_SLOP = 3                 # соседние слова запроса стоят в документе не дальше 3 слов друг от друга
    PAIR_PROXIMITY_BOOST = 2.0    # бонус за каждую такую пару
    EXACT_PHRASE_BOOST = 10.0
    MAX_PHRASE_TOKENS = 8         # длинные запросы (фрагменты документа) фразой не ищутся
    MAX_PROXIMITY_TERMS = 12
    _PHRASE_PREFIX_RE = re.compile(
        r'^(?:что входит в состав|состав|из чего состоит|компоненты|архитектура|структура|'
        r'что такое|что значит|расшифруй|расшифровка)\s+'
    )

    def __init__(self, corpus, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avg_doc_len = 1.0
        self.doc_lengths = []
        self.doc_token_positions = []
        self.df = {}
        self.idf = {}
        self.postings = {}

        if self.corpus_size == 0:
            return

        total_len = 0
        post = defaultdict(lambda: ([], []))
        for idx, doc in enumerate(corpus):
            tokens = bm25_tokenize(doc)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)
            positions = {}
            for pos, token in enumerate(tokens):
                positions.setdefault(token, []).append(pos)
            self.doc_token_positions.append(positions)
            for token, plist in positions.items():
                ids, tfs = post[token]
                ids.append(idx)
                tfs.append(len(plist))

        self.avg_doc_len = (total_len / self.corpus_size) or 1.0
        for token, (ids, tfs) in post.items():
            self.postings[token] = (np.array(ids, dtype=np.int32), np.array(tfs, dtype=np.float32))
            self.df[token] = len(ids)
            # Порог IDF (0.25) не даёт частотным терминам (названиям систем, аббревиатурам) обнулиться
            val = np.log((self.corpus_size - len(ids) + 0.5) / (len(ids) + 0.5) + 1.0)
            self.idf[token] = max(float(val), 0.25)

    def get_scores(self, query, extra_terms=None, phrase=None):
        """query — исходный вопрос; extra_terms — дополнительные термины [(токен, вес)]: расшифровки
        сокращений, слова расширения запроса; phrase — словосочетание для буста точной фразы
        (по умолчанию — вопрос без вводных слов «что такое», «состав» и т. п.)."""
        scores = np.zeros(self.corpus_size)
        if self.corpus_size == 0:
            return scores
        query_tokens = bm25_tokenize(query)
        doc_len = np.asarray(self.doc_lengths, dtype=np.float32)
        norm = self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)

        # 1. Базовый скоринг BM25 (по спискам вхождений)
        for token, weight in [(t, 1.0) for t in query_tokens] + list(extra_terms or []):
            if token in BM25_STOP_WORDS:
                continue
            p = self.postings.get(token)
            if p is None:
                continue
            ids, tf = p
            scores[ids] += weight * self.idf[token] * (tf * (self.k1 + 1)) / (tf + norm[ids])

        # 2. Буст точного совпадения словосочетания
        if phrase is None:
            phrase = self._PHRASE_PREFIX_RE.sub("", (query or "").lower()).strip()
        phrase_tokens = bm25_tokenize(phrase)
        if 2 <= len(phrase_tokens) <= self.MAX_PHRASE_TOKENS and all(t in self.postings for t in phrase_tokens):
            candidates = set(self.postings[phrase_tokens[0]][0].tolist())
            for t in phrase_tokens[1:]:
                candidates &= set(self.postings[t][0].tolist())
            for idx in candidates:
                positions = self.doc_token_positions[idx]
                p_sets = [set(positions[t]) for t in phrase_tokens]
                for start_pos in positions[phrase_tokens[0]]:
                    if all((start_pos + off) in p_sets[off] for off in range(1, len(phrase_tokens))):
                        scores[idx] += self.EXACT_PHRASE_BOOST
                        break

        # 3. Близость: соседние значимые слова вопроса стоят рядом и в документе
        significant = [t for t in query_tokens if t not in BM25_STOP_WORDS]
        if 2 <= len(significant) <= self.MAX_PROXIMITY_TERMS:
            pairs = list(dict.fromkeys((a, b) for a, b in zip(significant, significant[1:]) if a != b))
            for a, b in pairs:
                pa, pb = self.postings.get(a), self.postings.get(b)
                if pa is None or pb is None:
                    continue
                for idx in np.intersect1d(pa[0], pb[0]).tolist():
                    positions = self.doc_token_positions[idx]
                    if _min_gap(positions[a], positions[b]) <= self.PAIR_SLOP:
                        scores[idx] += self.PAIR_PROXIMITY_BOOST
        return scores


_TOKEN_SPAN_RE = re.compile(r"[а-яёa-z0-9_-]+", re.IGNORECASE)


def query_term_weights(query, extra_terms=None, idf=None):
    """Веса значимых слов запроса для выбора фрагмента: IDF из индекса BM25 (если есть) × вес термина."""
    weights = {}
    for token, w in [(t, 1.0) for t in bm25_tokenize(query)] + list(extra_terms or []):
        if token in BM25_STOP_WORDS or len(token) < 2:
            continue
        val = w * (idf.get(token, 1.0) if idf else 1.0)
        if val > weights.get(token, 0.0):
            weights[token] = val
    return weights


def _snap_window(text, start, size):
    """Окно [start, start+size) внутри текста, сдвинутое к границам слов."""
    n = len(text)
    start = max(0, min(start, n - size))
    end = min(n, start + size)
    if start > 0:
        sp = text.find(" ", start, min(n, start + 40))
        if sp != -1:
            start = sp + 1
    if end < n:
        sp = text.rfind(" ", max(start, end - 40), end)
        if sp != -1:
            end = sp
    return start, end


def densest_span(text, term_weights, size):
    """Участок текста не длиннее size с наибольшим весом разных слов запроса: (начало, конец, балл).
    Балл 0 и (0, 0) — слов запроса в тексте нет."""
    hits = []
    if term_weights:
        for m in _TOKEN_SPAN_RE.finditer(text or ""):
            tok = normalize_token(m.group(0))
            if tok in term_weights:
                hits.append((m.start(), m.end(), tok))
    if not hits:
        return 0, 0, 0.0
    best = (-1.0, 0, 0)
    j = 0
    for i in range(len(hits)):
        while hits[j][0] < hits[i][1] - size:   # окно, заканчивающееся на hits[i], не длиннее size
            j += 1
        terms = {h[2] for h in hits[j:i + 1]}
        score = sum(term_weights[t] for t in terms)
        if score > best[0]:
            best = (score, hits[j][0], hits[i][1])
    score, c_start, c_end = best
    return c_start, c_end, float(score)


def best_window(text, term_weights, size):
    """Самый «плотный» по словам запроса фрагмент текста длиной до size символов.
    Возвращает (фрагмент, балл); балл 0 — слов запроса в тексте нет (тогда берётся начало)."""
    text = text or ""
    if len(text) <= size:
        return text, 0.0
    c_start, c_end, score = densest_span(text, term_weights, size)
    if not score:
        s0, e0 = _snap_window(text, 0, size)
        return text[s0:e0].strip(), 0.0
    center = (c_start + c_end) // 2
    s0, e0 = _snap_window(text, center - size // 2, size)
    return text[s0:e0].strip(), score


def passage_around(text, inner, size):
    """Фрагмент длиной до size символов вокруг подстроки inner (найденного child-фрагмента)."""
    text = text or ""
    if len(text) <= size:
        return text
    pos = text.find(inner) if inner else -1
    if pos == -1:
        return None
    if len(inner) >= size:
        return inner[:size]
    s0, e0 = _snap_window(text, pos + len(inner) // 2 - size // 2, size)
    if s0 > pos:                      # окно не должно отрезать начало найденного фрагмента
        s0 = pos
        e0 = min(len(text), pos + size)
    return text[s0:e0].strip()


def save_bm25_index(parent_store, path: Path):
    try:
        if not parent_store:
            if path.exists():
                path.unlink()
            return True
        # путь заголовков входит в индексируемый текст: слова из названий разделов тоже ищутся
        texts = [((pd.get("heading_path") or "") + "\n" + (pd.get("text") or "")).strip()
                 for pd in parent_store.values()]
        engine = LightweightBM25(texts)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".pkl")
        try:
            with os.fdopen(fd, "wb") as f:
                pickle.dump({
                    "signature": BM25_INDEX_SIGNATURE,
                    "state": engine.__dict__,
                    "parent_ids": list(parent_store.keys()),
                }, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения BM25-индекса: {str(e)}")
        return False


def load_bm25_index(path: Path):
    try:
        if not path.exists():
            return None, None
        with open(path, "rb") as f:
            data = pickle.load(f)
        if not isinstance(data, dict) or data.get("signature") != BM25_INDEX_SIGNATURE:
            return None, None   # индекс старого формата (v17) — будет пересобран
        engine = LightweightBM25.__new__(LightweightBM25)
        engine.__dict__.update(data["state"])
        parent_ids = data.get("parent_ids") or []
        if not parent_ids:
            return None, None
        return engine, parent_ids
    except Exception as e:
        logger.info(f"BM25-индекс будет пересобран ({str(e)[:120]})")
        return None, None
