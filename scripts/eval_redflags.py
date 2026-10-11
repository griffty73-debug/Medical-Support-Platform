"""Evaluates the red-flag rules on the labelled synthetic test set in eval/redflag_cases.csv.

Compares the production rules (backend/triage.py, with negation and past-history
filtering) against the same patterns used as plain keyword matching. The test set
is synthetic and has not been reviewed by a physician; it measures software
behaviour, not clinical performance.

    .venv/bin/python scripts/eval_redflags.py            # summary and the cases each method gets wrong
    .venv/bin/python scripts/eval_redflags.py --json     # machine-readable summary
"""
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import triage  # noqa: E402

CASES = ROOT / 'eval' / 'redflag_cases.csv'
LEVELS = ('emergency', 'urgent', 'routine')


def keyword_only(text):
    """Baseline: the same patterns, but every match counts (no negation or history check)."""
    flags = [{'label': label, 'level': level} for pattern, level, label, _ in triage._COMPILED if pattern.search(text)]
    return triage.level_of(flags)


def rules(text):
    return triage.assess('', text)['level']


def score(cases, predict):
    predicted = [predict(c['text']) for c in cases]
    def rate(hit, total):
        return round(hit / total, 3) if total else None
    need = [c['expected'] != 'routine' for c in cases]
    flagged = [p != 'routine' for p in predicted]
    tp = sum(n and f for n, f in zip(need, flagged))
    fp = sum(f and not n for n, f in zip(need, flagged))
    emergency = [i for i, c in enumerate(cases) if c['expected'] == 'emergency']
    controls = [i for i, c in enumerate(cases) if c['group'] in ('negated', 'history')]
    return {
        'accuracy_3_level': rate(sum(p == c['expected'] for p, c in zip(predicted, cases)), len(cases)),
        'sensitivity_any_flag': rate(tp, sum(need)),
        'specificity_any_flag': rate(sum(not n and not f for n, f in zip(need, flagged)), len(cases) - sum(need)),
        'precision_any_flag': rate(tp, tp + fp),
        'emergency_recall': rate(sum(predicted[i] == 'emergency' for i in emergency), len(emergency)),
        'false_flags_on_negated_or_history': f'{sum(flagged[i] for i in controls)}/{len(controls)}',
        'wrong': [(c['id'], c['expected'], p, c['text']) for p, c in zip(predicted, cases) if p != c['expected']],
    }


def main():
    with CASES.open(encoding='utf-8') as fh:
        cases = list(csv.DictReader(fh))
    assert all(c['expected'] in LEVELS for c in cases)
    started = time.perf_counter()
    for _ in range(20):
        for c in cases:
            rules(c['text'])
    per_case_ms = (time.perf_counter() - started) / (20 * len(cases)) * 1000
    groups = {g: sum(c['group'] == g for c in cases) for g in ('positive', 'negated', 'history', 'routine')}
    result = {'cases': len(cases), 'groups': groups, 'rules': score(cases, rules),
              'keyword_only': score(cases, keyword_only), 'rules_ms_per_case': round(per_case_ms, 3)}
    if '--json' in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"{len(cases)} cases: {groups}")
    print(f"{'metric':38}{'rules':>10}{'keyword only':>15}")
    for key in ('accuracy_3_level', 'sensitivity_any_flag', 'specificity_any_flag', 'precision_any_flag',
                'emergency_recall', 'false_flags_on_negated_or_history'):
        print(f"{key:38}{str(result['rules'][key]):>10}{str(result['keyword_only'][key]):>15}")
    print(f"rules: {per_case_ms:.3f} ms per case")
    for name in ('rules', 'keyword_only'):
        print(f'\n{name} — cases with a different level ({len(result[name]["wrong"])}):')
        for case_id, expected, got, text in result[name]['wrong']:
            print(f'  #{case_id:>3} expected {expected:9} got {got:9} {text}')


main()
