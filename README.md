<div align="center">

# Skills

**반복되는 판단과 작업 방식을 재사용 가능한 에이전트 스킬로.**

Codex App을 중심으로 관리하는 개인용 AI 에이전트 스킬 허브입니다.

</div>

## 스킬

| 스킬 | 용도 | 환경 | 호출 |
| --- | --- | --- | --- |
| [Atelier](./atelier/SKILL.md) | 역할·위험·비용에 따라 Codex와 Claude 모델을 교차 배치해 구현과 독립 검토를 조율 | Codex App + Claude Code CLI | `$atelier` |
| [Falsify](./falsify/SKILL.md) | 주장·계획·결과물의 전제와 치명적 약점을 적대적으로 검증 | Codex App · Claude Code CLI | `$falsify` · `/falsify` |

각 폴더의 `SKILL.md`가 해당 스킬의 공식 동작 계약입니다. 별도 설계·구현 계획 문서를
중복 관리하지 않습니다.

## 설치

저장소를 받은 뒤 필요한 스킬 폴더를 심볼릭 링크로 연결합니다.

```bash
git clone https://github.com/SWHee/skills.git
cd skills

skill_name="atelier"
mkdir -p ~/.codex/skills
ln -s "$PWD/$skill_name" "$HOME/.codex/skills/$skill_name"
```

다른 스킬은 `skill_name`만 변경합니다. 같은 이름의 파일이나 링크가 이미 있다면
덮어쓰지 말고 기존 설치를 먼저 확인하세요. 새 스킬은 다음 Codex 요청부터 사용할 수
있습니다.

### Atelier 준비

Atelier는 Codex가 작업을 지휘하고 로컬 Claude Code CLI를 Anthropic 실행 경로로
사용합니다. Claude CLI가 설치되고 로그인된 환경에서 다음 사전 점검을 실행합니다.

```bash
./atelier/scripts/claude-lane.sh --check
```

샌드박스에서만 인증이 보이지 않으면 Codex의 승인 경로로 다시 실행합니다. 실제
터미널에서도 실패하면 `claude auth login`으로 로그인하세요. 요청 모델과 실행 결과의
canonical model이 다르면 Atelier는 조용히 대체하지 않고 실패 처리합니다.

```text
$atelier 이 기능을 설계는 Terra/medium, 구현은 Sonnet/low,
검토는 Sol/high로 배정해 구현과 검증까지 완료해줘.
```

### Falsify를 Claude Code에서도 사용하기

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/falsify" "$HOME/.claude/skills/falsify"
```

Falsify는 명시적 호출 전용입니다. Claude Code CLI에서는 `skillOverrides`를 지원하는
버전에서 `falsify`를 `user-invocable-only`로 설정하세요. Codex의 호출 정책은
[`falsify/agents/openai.yaml`](./falsify/agents/openai.yaml)에 정의되어 있습니다.

## 검증

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py atelier
atelier/scripts/test-claude-lane.sh
```

Atelier는 구조 검사, 격리된 브리지 회귀 테스트, 실제 Claude 인증·읽기 전용 호출,
모델 불일치 차단을 검증했습니다. Falsify는 판정 우선, 핵심 반론, 무결함 반대 사례를
검증했습니다.

## 구조

```text
skills/
├── atelier/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/
│   └── scripts/
├── falsify/
│   ├── SKILL.md
│   └── agents/openai.yaml
└── README.md
```

선택 폴더는 실제 실행에 필요할 때만 추가합니다.
