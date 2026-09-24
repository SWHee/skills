<div align="center">

<img src="assets/banner.svg" alt="Team Start — 하나의 출발점에서 연결되는 팀" width="760">

# Team Start

### 함께 일할 준비부터.

Codex 앱의 새 대화에서 프로젝트를 설명하면 새 팀 저장소의 협업 환경을 준비하는 플러그인입니다. 팀원은 설치 없이 GitHub를 사용합니다.

[시작하기](#시작하기) · [설치](#설치) · [실행과 확인](#실제-적용과-확인) · [검증](#검증)

</div>

> 문서 미리보기: 구현 패키지는 아직 이 저장소에 게시되지 않았습니다. 아래 설치·실행 명령과 참조 경로는 구현 소스를 보유한 로컬 환경 기준입니다.

## 시작하기

```text
$team-start 4명이 2주 해커톤을 합니다. 무료로 시작할 팀 저장소를 준비해줘.
$team-start 새 프로젝트의 GitHub 협업 설정을 계획만 세워줘.
$team-start /absolute/project/path에서 시작한 초기 설정을 점검해줘.
```

설명에서 이미 정한 내용을 읽고 소유자·이름·공개 여부·팀원·저장 위치 등 필요한 것만 질문합니다.

| 준비하는 것 | 범위 |
| --- | --- |
| 팀 작업 공간 | 새 저장소, GitHub Projects 보드, 팀원 초대 |
| 협업 문서 | README, 협업 안내, 이슈·PR 서식 |
| 선택적 설정 | AI 안내, 실제 검증 명령이 있는 경우 CI |

코드가 없으면 CI는 보류하고, 이후 검증한 명령으로 이어서 준비합니다.

기존 임의 저장소 개조, 앱 개발, 배포 연결, 결제, 조직 전체 정책 변경은 포함하지 않습니다. 새 조직 생성과 팀원 초대 수락은 사용자가 진행합니다. 무료 비공개 저장소에서 보호 규칙을 강제할 수 없다는 제약을 표시합니다.

## 설치

Python 3.9+, git, 로그인된 GitHub CLI(`gh`)가 필요합니다. 이 폴더는 Codex 플러그인 소스이며 개발 중에는 아래 스킬 하나를 연결합니다. 기존 경로가 있으면 덮어쓰지 않습니다.

```bash
mkdir -p ~/.codex/skills
ln -s /absolute/path/to/skills-harry/team-start/skills/team-start ~/.codex/skills/team-start
```

새 Codex 대화의 스킬 선택기에서 `team-start`를 확인합니다. 플러그인으로 별도 설치할 때는 위 직접 연결과 중복 사용하지 않습니다. 마켓플레이스 등록은 이 소스 패키지에 포함되지 않습니다.

## 실제 적용과 확인

<details>
<summary>직접 실행하는 plan / apply / check</summary>

실행 계약(`skills/team-start/references/interface.md`)의 JSON을 준비해 도우미를 호출합니다. 보통은 스킬이 대화에서 대신 작성합니다.

```bash
python3 team-start/skills/team-start/scripts/team_start.py plan --spec /absolute/spec.json
python3 team-start/skills/team-start/scripts/team_start.py apply --spec /absolute/spec.json
python3 team-start/skills/team-start/scripts/team_start.py check --path /absolute/project/path
```

</details>

plan/check는 원격을 변경하지 않습니다. apply만 허용된 작업을 수행합니다. `.team-start`의 Git 제외 기록을 보존해야 다른 대화에서 재개할 수 있습니다. 사용자 수정은 덮어쓰지 않으며 보호된 main에 추가할 문서·CI는 PR로 제안합니다. PR 자동 병합은 하지 않습니다.

보드 권한 요청 성공만으로 현재 접근 가능하다고 표시하지 않습니다. Codex가 브라우저로 보드의 Manage access를 읽거나 사용자가 확인해야 합니다. 생성 결과는 적용 확인·초대 수락 대기·보류·지원 불가·실패로 나뉘며, 종료 코드 0에도 보류가 있을 수 있습니다.

## 검증

<details>
<summary>모의 API 테스트와 구조 검사</summary>

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s team-start/tests -v
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py team-start/skills/team-start
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py team-start
```

모의 API 검증과 실제 GitHub 검증은 `tests/validation.md`에 구분합니다. `tests/behavioral.md`는 새 대화에서 스킬을 평가할 때 사용합니다. 두 문서는 구현 패키지에 포함될 예정입니다.

</details>
