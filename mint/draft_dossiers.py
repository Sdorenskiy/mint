"""Supplemental, function-directed evidence discovery over the existing RAG.

A dossier is not an authority for an obligation. Every candidate is a verified
original quotation; the existing full scan and attribution gates still apply.
No parallel search index, no platform-specific constants.
"""
from collections import Counter, defaultdict
import hashlib
import json

from .draft_progress import tracked
from .i18n import get_lang
from .template_draft import DraftError, _candidate_budget, _candidates, _normalized, _quote_key

# Each query covers a small, coherent group. All are investigation dimensions,
# not required functionality; an empty result means not established.
FACET_QUERIES = (
    (("purpose", "participants", "direction"),
     "назначение участники источник получатель направление ответственность обмен",
     "purpose participants source destination direction responsibility exchange"),
    (("data_categories", "data_content", "data_format"),
     "виды передаваемых данных категории сведений состав атрибуты поля сообщения формат схема",
     "transferred data types information categories content attributes fields message format schema"),
    (("interface", "trigger", "timing"),
     "интерфейс протокол способ взаимодействия событие периодичность расписание сроки",
     "interface protocol interaction event trigger frequency schedule timing"),
    (("performance", "capacity"),
     "показатели назначения производительность пропускная способность объём нагрузка задержка время",
     "performance objectives throughput volume capacity load latency time"),
    (("security", "data_constraints"),
     "категория доступа конфиденциальность класс защищенности персональные данные безопасность подписание шифрование хранение ограничения",
     "access category confidentiality protection class personal data security signing encryption retention restrictions"),
    (("reliability", "operations"),
     "ошибка повтор доставка восстановление отказ мониторинг журналирование контроль",
     "error retry delivery recovery failure monitoring logging control"),
)
FACETS = tuple(facet for group, _, _ in FACET_QUERIES for facet in group)


def _size(value):
    return len(json.dumps(value, ensure_ascii=False))


def _row(span):
    return {"id": span["id"], "source": span["source"], "section": span["section"],
            "text": span["text"], **({"table_context": span["table_context"]} if span.get("table_context") else {})}


def _candidate_rows(spans, lanes, budget, base, limit=12):
    """Balance existing ranked routes, preserving entire original spans."""
    order, seen = [], set()
    for i in range(max((len(lane) for lane in lanes), default=0)):
        for lane in lanes:
            if i < len(lane) and lane[i] not in seen:
                seen.add(lane[i])
                order.append(lane[i])
    rows, used = [], _size(base) + 100
    limits = Counter()
    for sid in order:
        row = _row(spans[sid])
        row["parts"] = [{"n": i, "text": line} for i, line in
                        enumerate(row.pop("text").splitlines(), 1)]
        if not any(part["text"].strip() for part in row["parts"]):
            continue
        cost = _size(row) + 2
        if len(rows) >= limit:
            limits["row_limit_omitted"] += 1
        elif used + cost > budget:
            limits["budget_omitted"] += 1
        else:
            rows.append(row)
            used += cost
    return rows, limits


def _validated_facts(reply, rows, facets, spans, counts):
    """Resolve numbered original line ranges; never accept generated quotes."""
    allowed = {row["id"]: row for row in rows}
    valid, seen = [], set()
    items = reply.get("items") if isinstance(reply, dict) else None
    malformed = not isinstance(items, list)
    if malformed:
        counts["invalid_payload"] += 1
    if isinstance(items, list) and len(items) >= 12:
        counts["response_limit"] += 1
        malformed = len(items) > 12
    for item in items[:12] if isinstance(items, list) else []:
        if not isinstance(item, dict):
            code = "invalid_item"
        else:
            sid, facet = item.get("span_id"), item.get("facet")
            first, last = item.get("first"), item.get("last")
            if not isinstance(sid, str) or sid not in allowed:
                code = "invalid_span"
            elif not isinstance(facet, str) or facet not in facets:
                code = "invalid_facet"
            elif (type(first) is not int or type(last) is not int or
                  not 1 <= first <= last <= len(allowed[sid]["parts"]) or last - first >= 4):
                code = "invalid_range"
            else:
                quote = "\n".join(p["text"] for p in allowed[sid]["parts"][first - 1:last])
                if not quote.strip() or _normalized(quote) not in _normalized(spans[sid]["text"]):
                    code = "nonliteral_selection"
                else:
                    key = (sid, facet, _normalized(quote))
                    if key in seen:
                        counts["duplicate_facts"] += 1
                        continue
                    seen.add(key)
                    valid.append({"span_id": sid, "facet": facet, "quote": quote})
                    continue
        counts[code] += 1
        counts["invalid_quotes"] += 1
        malformed = True
    return valid, malformed


def collect_dossiers(cfg, evidence, references, profile, context, emit, ask, *, reset_cache=False):
    """Use existing hybrid/lexical retrieval and exact original selections."""
    from .draft_checkpoint import DraftStageCheckpoint
    jobs = [(pid, facets, ru if get_lang() == "ru" else en)
            for pid in profile for facets, ru, en in FACET_QUERIES]
    dossiers = {pid: {"function": p["name"], "facets": {f: {"status": "not_searched",
                  "facts": []} for f in FACETS}} for pid, p in profile.items()}
    counts = Counter()
    spans = evidence.spans
    pool = {sid: {"id": sid, "source": s["source"], "section": s["section"], "quote": s["text"]}
            for sid, s in spans.items()}
    cache = DraftStageCheckpoint(cfg, "target_dossier")
    for pid, facets, terms in tracked(emit, "target_dossier", jobs):
        p = profile[pid]
        query = terms + " " + context["target"] + " " + p["name"]
        hits = evidence.find(query, k=6)
        fallback = [row["id"] for row in _candidates(query, pool,
                                                    size=min(5000, _candidate_budget(cfg) // 3))]
        anchors = [sid for sid in p["refs"] if sid in spans]
        roots = list(dict.fromkeys(anchors[:6] + hits[:6] + fallback[:6]))
        linked, gaps = references.related(roots, budget=min(6000, _candidate_budget(cfg) // 3))
        counts.update({"searches": 1, "hybrid_hits": len(hits), "fallback_hits": len(fallback)})
        counts["reference_gaps"] += sum(gaps.values())
        base = {"context": context, "function": {k: p[k] for k in ("id", "name", "description")},
                "facets": list(facets), "selection_format": "original_parts_v1"}
        rows, limits = _candidate_rows(spans, [anchors, hits, [r["id"] for r in linked], fallback],
                                       _candidate_budget(cfg), base)
        counts.update(limits)
        counts["supplied_spans"] += len(rows)
        limited = bool(limits) or any(v for k, v in gaps.items() if k != "cycle")
        if any(v for k, v in gaps.items() if k != "cycle"):
            counts["reference_limited_searches"] += 1
        if set(anchors + hits + fallback) - set(roots):
            counts["reference_root_limit"] += 1
            limited = True
        if not rows:
            counts["limited_searches"] += int(limited)
            for facet in facets:
                dossiers[pid]["facets"][facet]["status"] = "context_limit" if limited else "not_found"
            continue
        payload = {**base, "evidence": rows}
        if reset_cache:
            cache.clear(payload)
        saved = cache.load(payload)
        reply = None
        if saved and set(saved) == {"validated"}:
            try:
                reply = json.loads(saved["validated"])
                counts["cache_hits"] += 1
            except (ValueError, TypeError):
                pass
        if reply is None:
            try:
                reply = ask(cfg, "target_dossier", payload)
            except DraftError:
                counts["batch_errors"] += 1
                counts["limited_searches"] += int(limited)
                for facet in facets:
                    dossiers[pid]["facets"][facet]["status"] = "error"
                continue
        valid, malformed = _validated_facts(reply, rows, facets, spans, counts)
        if not malformed:
            cache.save(payload, {"validated": json.dumps(reply, ensure_ascii=False)})
        for fact in valid:
            dossiers[pid]["facets"][fact["facet"]]["facts"].append(fact)
        counts["facts"] += len(valid)
        items = reply.get("items") if isinstance(reply, dict) else None
        limited = limited or (isinstance(items, list) and len(items) >= 12)
        counts["limited_searches"] += int(limited)
        for facet in facets:
            row = dossiers[pid]["facets"][facet]
            row["status"] = ("found_partial" if limited or malformed else "found") if row["facts"] else (
                "context_limit" if limited else "error" if malformed else "not_found")
    return dossiers, counts


def merge_dossier_quotes(records, dossiers, spans, documents):
    """Append exact quotes before the existing typing stage. Preserve every
    original R-ID and quote, attach all provenance, and associate facts with IDs.
    """
    revisions = {name: hashlib.sha256(md.encode("utf-8")).hexdigest() for name, md in documents}
    keys = {_quote_key(r): rid for rid, r in records.items()}
    initial = len(records)
    for pid, dossier in dossiers.items():
        for facet, row in dossier["facets"].items():
            for fact in row["facts"]:
                span = spans[fact["span_id"]]
                quote = fact["quote"]
                # Recheck even a cached/externally constructed dossier.
                if not quote.strip() or _normalized(quote) not in _normalized(span["text"]):
                    row["status"] = "error"
                    continue
                row_data = {"source": span["source"], "section": span["section"], "quote": quote}
                if span.get("table_context"):
                    row_data["table_context"] = span["table_context"]
                key = _quote_key(row_data)
                rid = keys.get(key)
                if rid is None:
                    rid = "R" + str(len(records) + 1)
                    keys[key] = rid
                    records[rid] = {"id": rid, **row_data, "source_spans": []}
                record = records[rid]
                location = {"source": span["source"], "revision": revisions[span["source"]],
                            "section": span["section"], "fragment": span["fragment"], "quote": record["quote"]}
                if location not in record["source_spans"]:
                    record["source_spans"].append(location)
                fact["record_id"] = rid
                labels = record.setdefault("dossier_facets", [])
                label = {"function": pid, "facet": facet}
                if label not in labels:
                    labels.append(label)
    return len(records) - initial


def dossier_context(records, dossiers):
    """Map full-scan and supplemental records to candidate function context
    by original fragment position. This is only a retrieval hint.
    """
    positions = defaultdict(set)
    by_function = {}
    for pid, dossier in dossiers.items():
        ids = list(dict.fromkeys(fact["record_id"] for row in dossier["facets"].values()
                                 for fact in row["facts"] if "record_id" in fact))
        by_function[pid] = ids
        for rid in ids:
            for span in records[rid]["source_spans"]:
                positions[(span["source"], span["fragment"])].add(pid)
    return positions, by_function


def summarize_dossiers(dossiers, decisions, outcomes, proposals):
    """Expose unreflected characteristics, never interpret a mere hit as coverage."""
    counts = Counter()
    covered_proposals = [p for p in proposals if p.get("assessment") == "model_supported"
                         and all(outcomes.get(rid) == "model_covered" for rid in p["need_refs"])]
    for pid, dossier in dossiers.items():
        for facet, row in dossier["facets"].items():
            ids = list(dict.fromkeys(f["record_id"] for f in row["facts"] if "record_id" in f))
            row["coverage"] = {}
            for rid in ids:
                d = decisions.get(rid, {})
                if d.get("function") == pid and outcomes.get(rid) in {"model_covered", "already_supported"}:
                    status = outcomes[rid]
                elif d.get("status") == "model_supported" and d.get("change") == "external":
                    status = "external"
                elif any(rid in p["state_refs"] + p["constraint_refs"]
                         and any(decisions.get(need, {}).get("function") == pid for need in p["need_refs"])
                         for p in covered_proposals):
                    status = "linked_context"
                else:
                    status = "unresolved"
                row["coverage"][rid] = status
            counts[row["status"]] += 1
            counts["unresolved_facts"] += sum(s == "unresolved" for s in row["coverage"].values())
            counts["covered_facts"] += sum(s == "model_covered" for s in row["coverage"].values())
    return counts
