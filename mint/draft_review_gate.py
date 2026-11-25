"""Reviewable pre-derivation summaries. Original need records remain authoritative."""
from .draft_progress import tracked
from .template_draft import DraftError, _candidate_budget, _numbers_supported, _text
import json


def review_cards(cfg, collected, context, emit, ask):
    """Create bounded, source-linked formulations; fall back to literal quotes
    without discarding any obligation. Summaries are review aids, not evidence.
    """
    records = collected["requirements"]
    decisions = collected["decisions"]
    state = collected["state_evidence"]
    budget = _candidate_budget(cfg)

    def payload(group, ids):
        return {"context": context, "function": group["function"], "items": [
            {"id": rid, "quote": records[rid]["quote"], "change": decisions[rid]["change"],
             "metric": decisions[rid].get("metric"),
             "linked": [{"id": k, "quote": state[k]["quote"]} for k in
                        dict.fromkeys(decisions[rid].get("reference_refs", []) +
                                      decisions[rid].get("dossier_refs", []))]}
            for rid in ids]}

    def size(value):
        return len(json.dumps(value, ensure_ascii=False))

    jobs = []
    for group in collected["groups"]:
        ids = [rid for rid in group["requirement_ids"] if decisions[rid]["change"] != "already_supported"]
        batch = []
        for rid in ids:
            if batch and (len(batch) >= 6 or size(payload(group, batch + [rid])) > budget):
                jobs.append((group, batch))
                batch = []
            batch.append(rid)
        if batch:
            jobs.append((group, batch))

    cards = []
    for group, ids in tracked(emit, "target_review_summary", jobs):
        data = payload(group, ids)
        # Keep every original record even on error or oversize; no partial
        # summary is accepted as a complete list of needs.
        card = {"id": "V" + str(len(cards) + 1), "group": group["id"],
                "function": group["function"], "need_refs": list(ids),
                "text": "\n".join(records[rid]["quote"] for rid in ids),
                "status": "original_quotes"}
        if size(data) <= budget:
            try:
                answer = ask(cfg, "target_review_summary", data)
            except DraftError:
                answer = {}
            text = _text(answer, "text")
            refs = answer.get("need_refs")
            allowed_refs = list(dict.fromkeys(ids + [k for item in data["items"] for k in
                                                    [r["id"] for r in item["linked"]]]))
            if (text and len(text) <= 3000 and isinstance(refs, list)
                    and all(isinstance(r, str) for r in refs) and sorted(refs) == sorted(ids)
                    and _numbers_supported(text, allowed_refs, {**state, **records})):
                card.update(text=text, status="model_summary")
        cards.append(card)
    return cards


def validate_review(collected, excluded, notes):
    """Only pre-verified candidate obligations can be excluded. Notes are
    separate expert comments, never replacements for source quotations."""
    allowed = {rid for g in collected["groups"] for rid in g["requirement_ids"]
               if collected["decisions"][rid]["change"] != "already_supported"}
    if not isinstance(excluded, (list, tuple, set)) or any(not isinstance(r, str) for r in excluded):
        raise ValueError("Invalid exclusions")
    if not set(excluded) <= allowed:
        raise ValueError("Unknown or ineligible requirement")
    group_ids = {g["id"] for g in collected["groups"]}
    if not isinstance(notes, dict) or any(k not in group_ids or not isinstance(v, str) or len(v) > 1000
                                          for k, v in notes.items()):
        raise ValueError("Invalid expert comments")
    return set(excluded), {k: v.strip() for k, v in notes.items() if v.strip()}
