"""[unit] Formal evidence checks and human content review are separate; no semantic model calls."""
import csv
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness
W = harness.make_project(prefix='mint_answer_eval_')
app = harness.load_mint(W, include_ui=False)
from mint import evaluation as ev
check = harness.Checker()
cfg = app.Settings()
q = ev.Question(1, 'How long?', ['policy.txt'], contains=['three years'], expected_answer='Three years.')
result = {'answer': 'Thirty years [Source: policy.txt].', 'error': False,
          'context': '=== ИСТОЧНИК: policy.txt ===\nThree years.', 'sources': ['policy.txt'],
          'citations': [{'ok': True}], 'citations_invalid': []}
r = ev.judge_answer(q, result)
check(r['cites_expected'] and r['ok'] and r['content_review'] == 'unreviewed',
      'wrong fact with valid citation passes only formal checks; content remains unreviewed')
check(r['contains_in_answer'] is False, 'missing source phrase remains a separate observation')
missing = ev.judge_answer(q, dict(result, context='other source', sources=['other.txt']))
check(not missing['ok'] and missing['reason'] == 'search', 'valid-looking citation cannot override missing context')
run = SimpleNamespace(cfg=cfg, questions=[q], answers={'rows': {1: [r]}, 'summary': {'repeat': 1}})
with patch.object(ev, 'ask_llm', side_effect=AssertionError('no duplicate model checking')):
    ev.review_answer(run, 1, 0, 'incorrect')
check(not run.answers['summary']['content_reviews'].get('correct')
      and run.answers['summary']['content_reviews']['incorrect'] == 1 and r['ok'],
      'human incorrect verdict is counted independently from formal evidence')
for verdict in ev.CONTENT_REVIEWS:
    ev.review_answer(run, 1, 0, verdict)
    check(r['content_review'] == verdict, f'review supports {verdict}')
try:
    ev.review_answer(run, 1, 0, 'anything')
    check(False, 'invalid verdict rejected')
except ValueError:
    check(True, 'invalid verdict rejected')
path = W / 'questions.csv'; path.write_text(ev.questions_csv([q]), encoding='utf-8')
loaded = ev.load_questions(path)[0]
check(loaded.expected_answer == q.expected_answer and loaded.contains == q.contains, 'expected answer survives CSV round trip')
rows = ev.question_rows([q], SimpleNamespace(parent_store={'p': {'source': 'policy.txt'}}))
reloaded, issues = ev.rows_to_questions(rows)
check(not issues and reloaded[0].expected_answer == q.expected_answer, 'expected answer survives question editor round trip')
data = ev.answers_csv(run)
check('Three years.' in data and 'Thirty years' in data and 'неверно' in data, 'export includes expected answer, actual answer and manual verdict')
report = '\n'.join(ev.answers_report_lines(run))
check('правильность фактов' in report and 'верный ответ' not in report, 'report explains limits without claiming correct answers')
cur = run.answers['summary']; prev = dict(cur); prev.pop('evaluation_version')
check(not ev.compare_answers(cur, prev)['compatible'] and not ev.compare_answers(cur, prev)['deltas'],
      'old false-positive metrics cannot be compared as the same evaluation method')
check(ev.latest_answers([('old', {'answers': prev})]) is None, 'old evaluation is not selected as comparison baseline')
check.finish()
