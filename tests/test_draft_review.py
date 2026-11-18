"""Local real-document quality review: persistence, privacy and denominators."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint import draft_review as dr


def test_local_review():
    with TemporaryDirectory() as tmp:
        cfg = SimpleNamespace(log_path=Path(tmp), llm_model="fictional-model")
        secret = "Внутреннее_ТЗ_с_коммерческой_тайной.docx"
        q = "Сохранять конфиденциальный журнал не менее 30 суток."
        result = {"requirements": [
            {"id": "R1", "source": secret, "section": "7.1", "quote": q},
            {"id": "R2", "source": secret, "section": "7.2", "quote": "Шифровать резервные копии."}],
            "used": {"R1"}, "results": [{"field": "7.1", "status": "unchecked", "text": q, "refs": ["R1"]}],
            "metrics": {"total_seconds": 123.5, "stages": {"extract": {"llm_calls": 2, "llm_seconds": 80.0}}}}
        key = ("test", True, "template-fingerprint", (("secret", 2, 3),))
        one = dr.save_run(cfg, key, secret, [secret], result, "hash-of-prompt")
        assert len(one) == 32
        assert dr.load_run(cfg, one)["requirements"][0]["quote"] == q
        assert dr.load_run(cfg, one)["requirements"][0]["linked"]
        assert dr.list_runs(cfg)[0]["id"] == one
        data = dr.save_marks(cfg, one, {"R1": "covered", "R2": "missing"},
                             ["Ещё одно пропущенное требование из раздела 5"],
                             ["Необоснованное утверждение о сроке запуска"])
        assert data["marks"]["R1"] == "covered"
        current = dr.load_run(cfg, one)
        scores = dr.summary(current)
        assert (scores["reviewed"], scores["covered"], scores["missing"],
                scores["unsupported_claims"], scores["applicable_reviewed"]) == (2, 1, 2, 1, 3)
        assert scores["coverage_of_reviewed_applicable"] == 0.3333
        exported = json.dumps(dr.export_summary(current), ensure_ascii=False)
        assert secret not in exported and q not in exported
        assert "Ещё одно пропущенное" not in exported and "Необоснованное" not in exported
        assert "llm_api_key" not in exported and dr.FORMAT in exported
        assert dr.load_run(cfg, one)["meta"]["metrics"]["total_seconds"] == 123.5
        for verdict in ("invented", "true"):
            try:
                dr.save_marks(cfg, one, {"R1": verdict})
                raise AssertionError("invalid verdict accepted")
            except ValueError:
                pass
        try:
            dr.save_marks(cfg, one, {"R999": "covered"})
            raise AssertionError("foreign ID accepted")
        except ValueError:
            pass
        try:
            dr.load_run(cfg, "../audit.json")
            raise AssertionError("path traversal accepted")
        except ValueError:
            pass
        two = dr.save_run(cfg, key, secret, [secret], result, "changed-prompt")
        assert two != one
        dr.save_marks(cfg, two, {"R1": "covered", "R2": "covered"})
        diff = dr.compare(current, dr.load_run(cfg, two))
        assert diff["covered_delta"] == 1 and diff["missed_delta"] == -2
        three = dr.save_run(cfg, ("different",), secret, [secret], result)
        try:
            dr.compare(current, dr.load_run(cfg, three))
            raise AssertionError("different inputs compared")
        except ValueError:
            pass
        assert dr.summary(dr.load_run(cfg, three))["coverage_of_reviewed_applicable"] is None
        assert len(dr.list_runs(cfg)) == 3


if __name__ == "__main__":
    test_local_review()
    print("ИТОГ: локальный разбор черновика, ручные пропуски и выдуманные факты, безопасный экспорт")
