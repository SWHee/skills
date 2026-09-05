<div align="center">

# Falsify

### 좋은 계획은 반례를 견딘다.

주장·계획·결정·변경 사항을 가장 강한 관련 반례로 검증하는 명시적 적대적 검토 스킬입니다.

[Quick start](#quick-start) · [Modes](#modes) · [What it returns](#what-it-returns) · [Runtime](#runtime)

</div>

## What Falsify does

Falsify는 찬성하거나 자동으로 반대하지 않습니다. 현재 근거로 결정을 지지할 수 있는지
판단하고, 결론을 바꿀 만한 약점만 남깁니다.

```text
판정 → 근거 → 결과 → 가장 작은 다음 행동
```

코드에는 diff·영향받는 호출부·테스트를, 계획에는 전제·의존성·실패 조건을 먼저 봅니다.
확인하지 못한 사실은 결함으로 꾸며내지 않고 미확인으로 구분합니다.

## Quick start

```text
# Codex App
$falsify 이 기능 출시 계획을 검토해줘.

# Claude Code CLI
/falsify 이 diff를 검토해줘.
```

기본 호출은 결정에 영향을 주는 쟁점을 최대 세 개까지 다룹니다. 이 모드는 호출한 요청에만
적용되며, 다음 대화로 이어지지 않습니다.

## Modes

| Option | Use it when |
| --- | --- |
| `--quick` | 가장 위험한 실패 가능성만 빠르게 확인할 때 |
| `--deep` | 독립적인 실패 경로·대안·판정 전환 근거까지 볼 때 |
| `--focus <topic>` | 보안, 비용, 실현 가능성 등 특정 관점을 우선할 때 |
| `--recheck` | 이전 지적과 수정 근거를 대조할 때 |
| `--help` | 사용법만 볼 때 |
| `--off` | 이번 요청에서는 일반 응답으로 처리할 때 |

```text
$falsify --quick 이 PR diff를 검토해줘.
$falsify --deep --focus 보안 이 인증 설계를 검증해줘.
$falsify --recheck 이전 지적과 수정 diff를 비교해줘.
```

`--quick`과 `--deep`을 함께 쓰면 마지막 옵션이 적용됩니다. `--focus`와 `--recheck`는
다른 모드와 조합할 수 있습니다. 모든 옵션은 프롬프트 지시이며, CLI 설정을 바꾸지 않습니다.

## What it returns

```text
판정: 현재 근거로는 조건부 진행 가능.

근거: 호환 가능한 마이그레이션과 롤백 절차는 확인됐다.
남은 위험: 실제 복구 경로를 실행한 증거는 없다.
다음 행동: 배포 전 스테이징에서 복구 리허설 한 번을 실행한다.
```

중대한 결함이 없으면 그 사실을 말합니다. 억지 반론을 만들거나, 긴 위험 목록으로 결론을
흐리지 않습니다. 수정 요청이 함께 있으면 해당 수정과 필요한 검증까지 수행할 수 있습니다.

## Runtime

Codex App에서는 `$falsify`로 호출합니다. Claude Code CLI에서는 `/falsify`를 사용하려면
스킬을 연결하고 명시적 호출 전용 설정을 적용하세요.

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/falsify" "$HOME/.claude/skills/falsify"
```

Codex의 명시적 호출 정책은 [agents/openai.yaml](./agents/openai.yaml)에 있습니다. 전체
실행 규칙은 [SKILL.md](./SKILL.md)에서 확인할 수 있습니다.

## Development

[행동 회귀 사례](./tests/behavioral.md)는 옵션, 근거 수준, 재검증, 범위 제어를 점검합니다.
구조 검사는 다음 명령으로 실행합니다.

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py falsify
```
