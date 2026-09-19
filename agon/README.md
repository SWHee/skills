<div align="center">

# Agon

### 무엇을 만들지 결정하기 전에, 무엇을 증명해야 하는지 확정한다.

AI 해커톤의 규칙, 문제 근거, 심사 기준, AI 실현 가능성, 제출 계획을 하나의 실행 계약으로 묶는 스킬입니다.

</div>

## Why Agon

시간이 짧을수록 바로 코드를 쓰고 싶지만, 해커톤은 규칙 위반·근거 없는 문제 선택·검증되지 않은 핵심 모델 하나로 전체 결과가 무너질 수 있습니다. Agon은 `DISCOVER → READY → BUILD → VERIFY → PACKAGE` 흐름에서 구현 전에 여섯 책임을 확인하고, 준비가 되면 승인 질문을 반복하지 않고 실행합니다.

로컬 `gate.py`는 매니페스트와 근거 파일의 구조·시간·해시 일관성을 검사합니다. 온라인 규칙의 최신성, 법적 적합성, 문서의 의미나 리뷰의 정직성을 인증하지는 않습니다.

## Quick start

```text
$agon 이 해커톤 규칙과 아이디어를 검토하고 MVP까지 만들어줘.
$agon --phase plan 이 트랙의 준비 계약만 확정해줘.
$agon --implementer parent 현재 런타임에서 직접 구현해줘.
$agon --phase review 현재 제출 패키지를 심사 기준으로 검토해줘.
```

Codex에서는 `$agon`을 사용합니다. Claude Code 같은 대화형 런타임에서는 `/agon`을 자연어 호출로 사용할 수 있지만 별도 슬래시 명령 등록을 뜻하지 않습니다. 구현 요청의 기본 경로는 `sol/medium`이며 이는 요청 경로일 뿐 실제 사용 가능성을 보장하지 않습니다. 명시한 모델을 사용할 수 없으면 조용히 교체하지 않고 해당 구현 경로를 막습니다. `parent`를 명시하면 현재 에이전트가 처리할 수 있습니다.

## Readiness

구현은 다음 항목이 모두 성립할 때 시작합니다.

1. 현재 공식 규칙과 코딩 가능 시간이 확인됨
2. 사용자·워크플로·실패 결과·현재 대안과 문제 근거가 있음
3. 선택한 문제, 강한 대안, 비AI 기준선과 선택 이유가 있음
4. 선택한 상의 공식 심사 항목이 기능·증거·임계값·데모 순간에 연결됨
5. AI 입출력·도구·권리·평가·비용/지연·실패 대안이 정해짐
6. 범위·담당·검증·마감·시간 예비분·데모/제출 계획이 정해짐

새 규칙, 트랙, 데이터 권리, 모델/도구, 주요 범위, 마감이 바뀌면 영향받는 준비 상태를 다시 평가합니다. 사용자의 포괄적 승인은 규칙 충돌이나 기술 불확실성을 해결한 근거가 아닙니다. 반대로 준비와 구현 위임이 이미 끝났다면 최종 사람 승인을 형식적으로 한 번 더 요구하지 않습니다.

## Gate walkthrough

프로젝트에서는 기본적으로 `hackathon/agon/`에 파일을 둡니다. 기존에 같은 역할을 하는 문서가 있다면 재사용합니다.

```bash
mkdir -p hackathon/agon/sources
cp <skill-root>/assets/brief.template.md hackathon/agon/brief.md
cp <skill-root>/assets/gate.template.json hackathon/agon/gate.json
```

공식 페이지를 `sources/official-rules.txt` 등 로컬 스냅샷으로 보존한 뒤 `gate.json`의 URL, 시간, 규칙, 심사 기준, 예산을 실제 값으로 바꿉니다. 템플릿은 이 프로젝트 경로를 가리키므로 실제 snapshot과 brief가 생기기 전에는 의도적으로 구조 검사에 실패합니다.

```bash
python3 <skill-root>/scripts/gate.py fingerprint hackathon/agon/gate.json
```

출력된 fingerprint와 여섯 준비 책임을 검토합니다. 그 뒤 `review`에 `ready`, 리뷰어, 시간, fingerprint, 근거를 기록하고 실제 시각으로 확인합니다.

```bash
python3 <skill-root>/scripts/gate.py check hackathon/agon/gate.json
```

종료 코드는 `ready=0`, 구조는 유효하지만 차단됨=`1`, JSON·스키마·경로·CLI 오류=`2`입니다. `--now ISO8601`은 결정적 테스트 전용입니다. 필수 파일을 채운 pending 템플릿에도 fingerprint를 만들 수 있으므로 그 자체가 구현 승인은 아닙니다. 자세한 필드는 [gate-format.md](./references/gate-format.md)에 있습니다.

## Evaluation and packaging

개발용 사례와 hold-out을 분리하고, 실패·적대 입력을 포함한 대표 사례에서 비AI 기준선과 비교합니다. 전체 분모, 환경, 모델/프롬프트/데이터 버전, 재시도, 지연, 비용, 한계를 기록합니다. 녹화·mock·계획 상태를 실제 동작처럼 쓰지 않습니다.

패키징 전에는 빌더 설명 없이 실행물과 공식 심사 기준을 대조하고 데모를 재생합니다. 제출은 별도 외부 행동입니다. 이미 제출 권한이 구체적으로 주어진 경우에만 수행하며 실제 접수증이 있어야 제출 완료라고 말합니다.

## Development

```bash
python3 agon/tests/test_gate.py
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py agon
```

[행동 회귀 사례](./tests/behavioral.md)는 준비되지 않은 구현 압력, 규칙 변경, 코딩 시작 전 계획, 준비 완료 후 중복 승인 방지를 점검합니다. 원격 최신성이나 법률 검토는 로컬 테스트 범위가 아닙니다.

Agon은 [rignore/skills의 ai-hackathon-runner](https://github.com/rignore/skills/tree/main/ai-hackathon-runner)를 조사 참고자료로 검토했습니다. 문구와 구현은 이 저장소의 요구에 맞게 새로 작성했습니다.
