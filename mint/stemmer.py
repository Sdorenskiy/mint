"""Русский стеммер (Snowball) для BM25 и глоссария — без внешних зависимостей."""

from functools import lru_cache


# «документ», «документа», «документов» → «документ»: поиск по словам не зависит от падежа и числа.

_VOWELS = frozenset("аеиоуыэюя")


def _stem_endings(spec, group):
    return [(s, group) for s in spec.split()]


def _by_length(endings):
    return sorted(endings, key=lambda e: len(e[0]), reverse=True)


# (окончание, группа): группа 1 — допустима только после «а» или «я»
_ST_PERFECTIVE_GERUND = _by_length(_stem_endings("в вши вшись", 1) +
                                   _stem_endings("ив ивши ившись ыв ывши ывшись", 2))

_ST_ADJECTIVE = _by_length(_stem_endings(
    "ее ие ые ое ими ыми ей ий ый ой ем им ым ом его ого ему ому их ых ую юю ая яя ою ею", 2))

_ST_PARTICIPLE = _by_length(_stem_endings("ем нн вш ющ щ", 1) + _stem_endings("ивш ывш ующ", 2))

_ST_REFLEXIVE = _by_length(_stem_endings("ся сь", 2))

_ST_VERB = _by_length(
    _stem_endings("ла на ете йте ли й л ем н ло но ет ют ны ть ешь нно", 1) +
    _stem_endings("ила ыла ена ейте уйте ите или ыли ей уй ил ыл им ым ен ило ыло ено ят ует уют "
                  "ит ыт ены ить ыть ишь ую ю", 2))

_ST_NOUN = _by_length(_stem_endings(
    "а ев ов ие ье е иями ями ами еи ии и ией ей ой ий й иям ям ием ем ам ом о у ах иях ях ы ь ию ью ю ия ья я", 2))

_ST_DERIVATIONAL = ["ость", "ост"]

_ST_SUPERLATIVE = ["ейше", "ейш"]


def _stem_regions(word):
    """RV — после первой гласной; R2 — по правилам Snowball."""
    n = len(word)
    rv = r2 = n
    i = 0
    while i < n and word[i] not in _VOWELS:
        i += 1
    if i < n:
        rv = i + 1
        j = rv
        while j < n and word[j] in _VOWELS:
            j += 1
        if j < n:
            j += 1
            while j < n and word[j] not in _VOWELS:
                j += 1
            if j < n:
                j += 1
                while j < n and word[j] in _VOWELS:
                    j += 1
                if j < n:
                    r2 = j + 1
    return rv, r2


def _stem_remove(word, rv, endings):
    """Самое длинное окончание из списка внутри RV; None — не найдено или нарушено условие «после а/я»."""
    for suffix, group in endings:
        start = len(word) - len(suffix)
        if start >= rv and word.endswith(suffix):
            if group == 1 and not (start - 1 >= rv and word[start - 1] in "ая"):
                return None
            return word[:start]
    return None


@lru_cache(maxsize=200_000)
def russian_stem(word: str) -> str:
    """Основа слова. Ожидает слово в нижнем регистре из кириллических букв."""
    word = word.replace("ё", "е")
    rv, r2 = _stem_regions(word)
    if rv >= len(word):
        return word

    res = _stem_remove(word, rv, _ST_PERFECTIVE_GERUND)
    if res is not None:
        word = res
    else:
        res = _stem_remove(word, rv, _ST_REFLEXIVE)
        if res is not None:
            word = res
        res = _stem_remove(word, rv, _ST_ADJECTIVE)
        if res is not None:
            word = res
            res = _stem_remove(word, rv, _ST_PARTICIPLE)
            if res is not None:
                word = res
        else:
            res = _stem_remove(word, rv, _ST_VERB)
            if res is None:
                res = _stem_remove(word, rv, _ST_NOUN)
            if res is not None:
                word = res

    if word.endswith("и") and len(word) - 1 >= rv:
        word = word[:-1]

    for suffix in _ST_DERIVATIONAL:
        if word.endswith(suffix) and len(word) - len(suffix) >= r2:
            word = word[:-len(suffix)]
            break

    superlative = False
    for suffix in _ST_SUPERLATIVE:
        if word.endswith(suffix) and len(word) - len(suffix) >= rv:
            word = word[:-len(suffix)]
            superlative = True
            break
    if word.endswith("нн") and len(word) - 2 >= rv:
        word = word[:-1]
    elif not superlative and word.endswith("ь") and len(word) - 1 >= rv:
        word = word[:-1]
    return word


# ---------------------------------------------------------------- English (Porter2 / Snowball English)
# «requirements», «required», «requiring» → «requir»: the same for English words in documents and queries.

_EN_VOWELS = frozenset("aeiouy")
_EN_DOUBLES = ("bb", "dd", "ff", "gg", "mm", "nn", "pp", "rr", "tt")
_EN_LI_ENDINGS = frozenset("cdeghkmnrt")
_EN_EXCEPTIONS = {
    "skis": "ski", "skies": "sky", "dying": "die", "lying": "lie", "tying": "tie", "idly": "idl",
    "gently": "gentl", "ugly": "ugli", "early": "earli", "only": "onli", "singly": "singl",
    "sky": "sky", "news": "news", "howe": "howe", "atlas": "atlas", "cosmos": "cosmos", "bias": "bias",
    "andes": "andes",
}
_EN_EXCEPTIONS_1A = frozenset({"inning", "outing", "canning", "herring", "earring", "proceed", "exceed", "succeed"})


def _en_is_vowel(word, i):
    return word[i] in _EN_VOWELS


def _en_regions(word):
    """R1 и R2 по правилам Porter2 (с исключениями gener-, commun-, arsen-)."""
    n = len(word)
    r1 = n
    for prefix in ("gener", "commun", "arsen"):
        if word.startswith(prefix):
            r1 = len(prefix)
            break
    else:
        for i in range(1, n):
            if not _en_is_vowel(word, i) and _en_is_vowel(word, i - 1):
                r1 = i + 1
                break
    r2 = n
    for i in range(r1 + 1, n):
        if not _en_is_vowel(word, i) and _en_is_vowel(word, i - 1):
            r2 = i + 1
            break
    return r1, r2


def _en_short_syllable_end(word):
    """Слово оканчивается коротким слогом: согласная + гласная + согласная (не w, x, Y) или гласная + согласная
    в начале слова."""
    n = len(word)
    if n >= 3 and not _en_is_vowel(word, n - 3) and _en_is_vowel(word, n - 2) \
            and not _en_is_vowel(word, n - 1) and word[n - 1] not in "wxY":
        return True
    return n == 2 and _en_is_vowel(word, 0) and not _en_is_vowel(word, 1)


def _en_is_short(word, r1):
    return r1 >= len(word) and _en_short_syllable_end(word)


def _en_has_vowel(s):
    return any(c in _EN_VOWELS for c in s)


@lru_cache(maxsize=200_000)
def english_stem(word: str) -> str:
    """Основа английского слова (Porter2). Ожидает слово в нижнем регистре из латинских букв."""
    if len(word) <= 2:
        return word
    if word in _EN_EXCEPTIONS:
        return _EN_EXCEPTIONS[word]
    if word.startswith("'"):
        word = word[1:]
    # y в начале слова и после гласной — согласная (Y)
    chars = list(word)
    if chars and chars[0] == "y":
        chars[0] = "Y"
    for i in range(1, len(chars)):
        if chars[i] == "y" and chars[i - 1] in _EN_VOWELS:
            chars[i] = "Y"
    word = "".join(chars)
    r1, r2 = _en_regions(word)

    # Step 0: притяжательные формы
    for suf in ("'s'", "'s", "'"):
        if word.endswith(suf):
            word = word[:-len(suf)]
            break

    # Step 1a
    if word.endswith("sses"):
        word = word[:-2]
    elif word.endswith(("ied", "ies")):
        word = word[:-3] + ("i" if len(word) > 4 else "ie")
    elif word.endswith(("us", "ss")):
        pass
    elif word.endswith("s"):
        if _en_has_vowel(word[:-2]):
            word = word[:-1]
    if word in _EN_EXCEPTIONS_1A:
        return word

    # Step 1b
    for suf in ("eedly", "eed"):
        if word.endswith(suf):
            if len(word) - len(suf) >= r1:
                word = word[:-len(suf)] + "ee"
            break
    else:
        for suf in ("ingly", "edly", "ing", "ed"):
            if word.endswith(suf):
                stem = word[:-len(suf)]
                if _en_has_vowel(stem):
                    word = stem
                    if word.endswith(("at", "bl", "iz")):
                        word += "e"
                    elif word.endswith(_EN_DOUBLES):
                        word = word[:-1]
                    elif _en_is_short(word, r1):
                        word += "e"
                break

    # Step 1c: y → i после согласной (не первой буквы)
    if len(word) > 2 and word[-1] in "yY" and word[-2] not in _EN_VOWELS:
        word = word[:-1] + "i"

    # Step 2 (в R1)
    step2 = (
        ("ization", "ize"), ("ational", "ate"), ("fulness", "ful"), ("ousness", "ous"), ("iveness", "ive"),
        ("tional", "tion"), ("biliti", "ble"), ("lessli", "less"), ("entli", "ent"), ("ation", "ate"),
        ("alism", "al"), ("aliti", "al"), ("ousli", "ous"), ("iviti", "ive"), ("fulli", "ful"), ("enci", "ence"),
        ("anci", "ance"), ("abli", "able"), ("izer", "ize"), ("ator", "ate"), ("alli", "al"), ("bli", "ble"),
        ("ogi", "og"), ("li", ""),
    )
    for suf, rep in step2:
        if word.endswith(suf):
            if len(word) - len(suf) >= r1:
                if suf == "ogi":
                    if word[:-3].endswith("l"):
                        word = word[:-3] + rep
                elif suf == "li":
                    if len(word) >= 3 and word[-3] in _EN_LI_ENDINGS:
                        word = word[:-2]
                else:
                    word = word[:-len(suf)] + rep
            break

    # Step 3 (в R1; ative — в R2)
    step3 = (("ational", "ate"), ("tional", "tion"), ("alize", "al"), ("icate", "ic"), ("iciti", "ic"),
             ("ative", ""), ("ical", "ic"), ("ness", ""), ("ful", ""))
    for suf, rep in step3:
        if word.endswith(suf):
            if len(word) - len(suf) >= r1 and (suf != "ative" or len(word) - len(suf) >= r2):
                word = word[:-len(suf)] + rep
            break

    # Step 4 (в R2)
    step4 = ("ement", "ance", "ence", "able", "ible", "ment", "ant", "ent", "ism", "ate", "iti", "ous", "ive",
             "ize", "ion", "al", "er", "ic")
    for suf in step4:
        if word.endswith(suf):
            if len(word) - len(suf) >= r2:
                if suf == "ion":
                    if word[:-3].endswith(("s", "t")):
                        word = word[:-3]
                else:
                    word = word[:-len(suf)]
            break

    # Step 5
    if word.endswith("e"):
        stem = word[:-1]
        if len(stem) >= r2 or (len(stem) >= r1 and not _en_short_syllable_end(stem)):
            word = stem
    elif word.endswith("ll") and len(word) - 1 >= r2:
        word = word[:-1]
    return word.replace("Y", "y")
