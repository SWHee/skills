"""Run from the repository root with python3 weekly-brief/tests/test_timing.py."""
import importlib.util
from pathlib import Path

path = Path(__file__).parents[1] / 'skills/weekly-script/scripts/estimate_time.py'
spec = importlib.util.spec_from_file_location('estimate_time', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.estimate('가' * 750) == (750, 151.4, 170.0)
assert module.estimate('안녕, 세상!\n 반가워요.') == (8, 16.5, 21.6)
assert module.estimate('에이피아이 삼 초') == (7, 16.3, 21.4)
assert module.estimate('가' * 800)[2] == 180
assert module.estimate('가' * 801)[2] > 180
try:
    module.estimate('  !!! ')
except ValueError:
    pass
else:
    raise AssertionError('Empty narration must be rejected')
print('timing checks passed')
