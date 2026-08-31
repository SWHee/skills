<div align="center">

# Skills

**반복되는 작업과 판단 기준을, 다시 호출할 수 있는 스킬로.**

Codex App과 Claude Code CLI에서 사용하는 개인용 AI 에이전트 스킬 아카이브입니다.

<p>
  <img alt="Codex App" src="https://img.shields.io/badge/Codex_App-supported-111827?style=flat-square">
  <img alt="Claude Code CLI" src="https://img.shields.io/badge/Claude_Code_CLI-supported-111827?style=flat-square">
  <img alt="Language Korean" src="https://img.shields.io/badge/README-한국어-4B5563?style=flat-square">
</p>

[소개](#실전에서-검증하는-ai-에이전트-스킬) · [스킬](#스킬-카탈로그) · [설치](#설치) · [검증](#품질-기준) · [구조](#저장소-구조)

</div>

---

## 실전에서 검증하는 AI 에이전트 스킬

반복해서 설명하게 되는 작업 절차, 판단 기준, 응답 방식을 독립적인 스킬로 만들고
실사용을 통해 계속 다듬습니다. 스킬 수보다 **다시 쓸 이유가 분명한가**, **지원 환경에서
실제로 동작하는가**를 우선합니다.

각 스킬은 하나의 폴더에 격리되며, 지원 런타임과 호출 방식, 검증 상태를 카탈로그에
명시합니다.

## 스킬 카탈로그

| 스킬 | 용도 | 지원 환경 | 호출 | 상태 |
| --- | --- | --- | --- | --- |
| [`falsify`](./falsify/SKILL.md) | 주장·계획·결과물의 전제와 치명적 약점을 적대적으로 검증 | Codex App · Claude Code CLI | `$falsify` · `/falsify` | [Codex 행동 검증](./docs/superpowers/plans/2026-08-31-falsify-skill.md#behavioral-validation-evidence) · Claude 호환 설계 |

`Codex 행동 검증`은 구조 검사, 실제 요청 기반 행동 테스트, 무결함 반대 사례를
통과했음을 뜻합니다. `Claude 호환 설계`는 동일한 `SKILL.md`와 공식 설치·호출 규격을
따르지만 Claude Code CLI 실통합 테스트는 아직 수행하지 않았음을 뜻합니다.

### 빠른 예시

`falsify`는 판정을 먼저 내리고 결론을 바꿀 수 있는 핵심 쟁점과 다음 검증만 남깁니다.

```text
# Codex App
$falsify 이 설계로 파이널 프로젝트를 진행해도 되는지 검증해줘.

# Claude Code CLI
/falsify 이 설계로 파이널 프로젝트를 진행해도 되는지 검증해줘.
```

각 스킬의 전체 동작 계약과 예시는 카탈로그에서 연결된 `SKILL.md`에 둡니다. 루트
README는 스킬이 늘어나도 공통 설치법과 짧은 탐색 정보만 유지합니다.

## 설치

### 1. 저장소 받기

```bash
git clone https://github.com/SWHee/skills.git
cd skills
```

스킬은 복사 대신 심볼릭 링크로 연결합니다. 저장소에서 `git pull --ff-only`를 실행하면
설치된 스킬도 함께 갱신됩니다.

설치할 폴더명을 변수로 지정합니다. 다른 스킬은 이 값만 바꿉니다.

```bash
skill_name="falsify"
```

### 2. Codex App

```bash
mkdir -p ~/.codex/skills
ln -s "$PWD/$skill_name" "$HOME/.codex/skills/$skill_name"
```

설치 후 호출법과 자동 호출 정책은 카탈로그와 각 스킬의 `SKILL.md`를 확인합니다.

`falsify`는 Codex App에서 `$falsify`를 붙인 요청에만 실행됩니다.
`falsify/agents/openai.yaml`의 `allow_implicit_invocation: false`가 자동 호출을
비활성화합니다.

### 3. Claude Code CLI

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/$skill_name" "$HOME/.claude/skills/$skill_name"
```

설치 후 호출법과 자동 호출 정책은 카탈로그와 각 스킬의 `SKILL.md`를 확인합니다.

#### `falsify` 수동 전용 설정

아래 설정은 `falsify` 전용이며, `skillOverrides`를 지원하는 Claude Code CLI
**v2.1.129 이상**이 필요합니다. 모든 프로젝트에서 자동 호출을 막으려면 기존
`~/.claude/settings.json`에 다음 항목을 병합합니다.

```json
{
  "skillOverrides": {
    "falsify": "user-invocable-only"
  }
}
```

`/skills`에서 `falsify`가 표시되고 UI 상태가 `user-only`인지 확인한 뒤 `/falsify`로
호출합니다. 이 설정을 마쳐야 Claude가 스킬을 자동으로 선택하지 않고 사용자가 호출한
요청에서만 실행됩니다. Claude Code 실행 후 `~/.claude/skills`를 처음 만들었다면 세션을
한 번 다시 시작합니다.

> [!NOTE]
> 이미 같은 이름의 파일이나 링크가 있다면 덮어쓰지 말고 기존 설치를 먼저 확인하세요.

## 품질 기준

새 스킬은 다음 기준을 통과한 뒤 카탈로그에 추가합니다.

- `SKILL.md`의 이름·설명·본문이 하나의 명확한 사용 목적을 가질 것
- 지원 런타임별 설치와 호출 방법을 명시할 것
- 구조 검증과 실제 요청 기반 행동 검증을 통과할 것
- 자동 호출, 도구 권한, 외부 변경 같은 동작 경계를 숨기지 않을 것
- 불필요한 스크립트·참고 문서·에셋을 만들지 않을 것

`falsify`의 구조 검증, Codex 행동 시나리오, 무결함 반대 사례는
[구현 계획과 결과](./docs/superpowers/plans/2026-08-31-falsify-skill.md)에 기록되어
있습니다. Claude Code CLI 실통합 테스트는 후속 검증 범위입니다.

## 저장소 구조

```text
skills/
├── <skill-name>/
│   ├── SKILL.md             공용 스킬 정의와 실행 지침
│   ├── agents/
│   │   └── openai.yaml      Codex App UI와 호출 정책
│   ├── references/          필요한 경우에만 사용하는 상세 지침
│   ├── scripts/             반복 실행이 필요한 결정적 도구
│   └── assets/              결과물에 포함되는 템플릿과 미디어
├── docs/                    설계·구현·검증 기록
└── README.md                스킬 카탈로그와 설치 안내
```

모든 선택 폴더를 미리 만들지 않습니다. 실제 스킬에 필요한 리소스만 추가합니다.

## 커밋 규칙

[Conventional Commits](https://www.conventionalcommits.org/) 타입과 한국어 명사형 설명을
사용합니다.

```text
feat: falsify 적대적 검증 스킬 추가
docs: 스킬 허브 README 개편
fix: Claude Code 호출 안내 수정
```
