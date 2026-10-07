"""Replay the stored linked example; semantic grounding still requires human review."""
import importlib.util
import json
from pathlib import Path

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('timing', root.parent / 'skills/weekly-script/scripts/estimate_time.py')
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)
case = json.loads((root / 'connected-case.json').read_text())

for stage in ('before', 'after'):
    script = case['script_' + stage]
    expected = script
    for original, spoken in case['pronunciation'].items():
        expected = expected.replace(original, spoken)
    assert expected == case['spoken_' + stage], 'Pronunciation copy differs from complete narration'
    assert script.startswith('안녕하세요. 18팀 인공지능 해리입니다.')
    assert script.endswith('이상 인공지능 파트 주간 브리핑 마치겠습니다. 감사합니다.')
    assert '#' not in expected and '예상 약' not in expected
    count, target, slow = timing.estimate(expected)
    assert 140 <= target <= 160, (stage, count, target)
    assert slow <= 180, (stage, slow)
    print(stage, count, target, slow)

before, after = (case['script_' + s].split('\n\n') for s in ('before', 'after'))
assert len(before) == len(after)
changed = [i for i, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
assert len(changed) == 1 and before[changed[0]].startswith('두 번째는')
assert '재현 테스트는 아직 진행하지 않았' in after[changed[0]]

# Only the second topic and its speaker note may change, including headings.
def outside_second(text):
    start = text.index('### 어떤 어려움이 있었나? - 2.')
    end = text.index('### 어떤 어려움이 있었나? - 3.')
    text = text[:start] + text[end:]
    start = text.index('### 2. 검색 지연 조사')
    end = text.index('### 3. null 응답 처리 협업')
    return text[:start] + text[end:]

assert outside_second(case['material_before']) == outside_second(case['material_after'])
assert '다음 주 로그 추가 예정입니다.' in case['material_after'].split('### 어떤 어려움이 있었나?')[0]
assert '상단 주요 구현 및 진행 사항의 두 번째 항목' in case['notice']
print('linked timing, pronunciation-copy and partial-edit checks passed')
