<div align="center">

# skills

### 자주 쓰는 판단 방식을, 다시 호출할 수 있는 에이전트 스킬로.

Codex App을 중심으로 관리하는 개인용 AI 에이전트 스킬 아카이브입니다.

</div>

## Collection

| Skill | What it does | Runtime |
| --- | --- | --- |
| [Atelier](./atelier/README.md) | 역할·비용·위험에 따라 Codex와 Claude 모델을 조율하는 소프트웨어 작업실 | Codex App + Claude Code CLI |
| [Falsify](./falsify/README.md) | 의견·의문·계획의 전제를 검증하고 판단과 핵심 근거만 읽기 쉽게 전달 | Codex App · Claude Code CLI |
| [Agon](./agon/README.md) | AI 해커톤의 규칙·문제·증거를 구현 전에 확정하고 실행하는 참가 스킬 | Codex App · Claude Code CLI |

각 폴더의 `README.md`에는 사람을 위한 사용 안내와 예시가, `SKILL.md`에는 에이전트가
따르는 실행 계약이 있습니다.

## Plugins

| Plugin | What it does | Skills |
| --- | --- | --- |
| [Rationale](./rationale/README.md) | 비용·설계·연쇄 영향을 조사해 기술 결정을 돕고 개인 ADR 작성·검토 연결 | `rationale`, `rationale-write`, `rationale-review` |

플러그인은 관련 스킬을 하나로 묶습니다. 설치와 개발용 실행 방법은 해당 플러그인의 README를 따릅니다.

## Install

저장소를 받은 뒤 원하는 스킬 폴더를 Codex에 심볼릭 링크로 연결합니다.

```bash
git clone https://github.com/SWHee/skills.git
cd skills

skill_name="atelier"
mkdir -p ~/.codex/skills
ln -s "$PWD/$skill_name" "$HOME/.codex/skills/$skill_name"
```

다른 스킬은 `skill_name`만 바꾸면 됩니다. 이미 같은 이름이 설치되어 있다면 먼저
대상을 확인하세요. 심볼릭 링크 설치는 저장소를 갱신하면 스킬도 함께 갱신됩니다.

Claude Code CLI에서 사용하는 방법, 런타임 조건, 모델 조합은 각 스킬 README에서
설명합니다.

## Conventions

- 스킬 폴더 하나가 하나의 독립된 작업 방식입니다.
- `SKILL.md`는 실행 규칙, `README.md`는 사용법, `agents/openai.yaml`은 Codex UI 메타데이터를 담당합니다.
- `scripts/`와 `references/`는 반복 실행이나 세부 판단에 실제로 필요할 때만 둡니다.

## Verify

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-folder>
```

스킬별 추가 테스트와 검증 범위는 해당 README에 있습니다.
