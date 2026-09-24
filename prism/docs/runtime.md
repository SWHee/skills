# Prism

Codex에서 로컬 Claude Code CLI를 호출해 일반·적대적 읽기 전용 코드 검토를 받는 개인용 플러그인입니다.
OpenAI 공식 플러그인이 아니며, [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc)의 검토 경험을 반대 방향으로 구현했습니다.

```text
$prism 현재 변경을 Claude로 검토해줘.
$prism main 대비 변경을 적대적으로 검토해줘. 재시도와 중복 처리에 집중해줘.
$prism 설정 상태를 확인해줘.
```

Codex 구현 → Claude 읽기 전용 검토 → Codex 결과 전달에서 종료합니다.
자동 수용·기각, 수정, 테스트 실행, 재검토 루프는 없습니다. 이후 “타당한 지적을 확인하고 수정해줘”는 별도의 Codex 요청입니다.

## 설계와 범위

원본 기준: `db52e28f4d9ded852ab3942cea316258ae4ef346` / v1.0.6 / 2026-07-08. 2026-09-24 확인.
소스·프롬프트는 직접 작성했으며 원본 코드를 복사하지 않았습니다.

| 결정 | 이유 |
| --- | --- |
| 스킬 하나, 일반·적대적 모드 | 동일한 입력 수집·실행·결과 처리를 공유 |
| Python 표준 라이브러리 + `claude -p` | MCP, SDK 패키지, 서버·브로커 없이 실행 |
| 호스트의 실행 세션으로 대기·취소 | 별도의 백그라운드 작업 DB·데몬·상태 명령 생략 |
| Opus 5.5 고정, high/xhigh 선택 | 현재 Codex가 작업 위험도를 보고 강도를 선택; 추가 판단용 LLM 호출 없음 |
| safe-mode + restricted + Read/Glob/Grep만 제공 | 커스텀 훅·MCP·스킬·쓰기·셸 실행 없이 주변 코드 탐색 |
| diff를 한 번 전달하고 필요 파일은 읽기 | 저장소 전체를 프롬프트에 반복해서 넣지 않음 |
| 240KB 입력 상한, 초과 시 실패 | 조용한 잘림과 검토 누락 방지; `--path`로 명시적 축소 |
| 10분 타임아웃, 재시도 없음 | 비용과 대기 범위를 제한 |
| 검토 전후 변경 지문 비교 | 검토 대상이 바뀌면 stale 경고; 자동 재호출 없음 |

위 내용은 구조 단순화이며 속도·비용 향상을 실측한 벤치마크는 아닙니다.
원본의 rescue·transfer·Stop gate는 v1에 포함하지 않습니다. 일반 모드도 Claude 프롬프트 기반 검토이며 Codex의 네이티브 `/review`와 동일한 엔진은 아닙니다.

## 요구 사항과 설치

macOS/Linux, Python 3.10+, Git, 인증된 Claude Code CLI가 필요합니다. CLI는 `--safe-mode`, `--restricted`, `--json-schema`를 지원해야 합니다.
리뷰 입력과 읽는 코드가 구성된 Claude 제공자에게 전달되고 해당 계정의 사용량을 소비합니다.
`--bare`는 구독 인증을 사용하지 않으므로 기본값으로 사용하지 않습니다.

플러그인 패키지는 `.codex-plugin/plugin.json`에 구성했습니다. 이 저장소의 기존 방식처럼 스킬을 직접 연결해서 사용할 수도 있습니다. 저장소 루트에서:

```bash
ln -s "$PWD/prism/skills/prism" ~/.codex/skills/prism
```

이미 같은 이름이 있으면 대상을 확인하고 덮어쓰지 마세요. 새 Codex 작업에서 스킬을 선택합니다.
호스트에 따라 플러그인 스킬은 네임스페이스가 붙을 수 있습니다. 앱 슬래시 명령을 등록하는 패키지는 아닙니다.

## 직접 실행

```bash
python3 prism/skills/prism/scripts/review.py --check
python3 prism/skills/prism/scripts/review.py --cwd /path/to/repo --dry-run
python3 prism/skills/prism/scripts/review.py --cwd /path/to/repo --mode adversarial --focus '재시도 시 중복 처리'
python3 prism/skills/prism/scripts/review.py --cwd /path/to/repo --base main
```

기본 범위는 HEAD 대비 최종 작업 트리와 추적되지 않은 파일입니다. staged/unstaged를 합쳐 최종 결과를 검토합니다. 깨끗한 작업 트리는 호출 없이 종료합니다.
`--base`는 merge-base부터 HEAD까지의 커밋 변경만 검토하며 주변 파일과 버전이 일치하도록 깨끗한 checkout을 요구합니다.
`--path src/example.py`를 반복해 범위를 제한할 수 있습니다. 경로는 저장소 루트 기준이며 glob을 확장하지 않습니다.
추적되지 않은 binary·symlink는 별도 검토가 필요하다는 오류를 냅니다. 추적된 binary는 diff 메타데이터만 제공되므로 내용 검토를 보장하지 않습니다.

모델은 `claude-opus-5-5`로 고정하며 Sonnet으로 대체하지 않습니다. 스킬 호출 시 현재 Codex가 작업 문맥과 범위 내 diff를 짧게 확인해 `--effort high` 또는 `xhigh`를 선택하고 이유를 알립니다. 국소적이고 계약이 명확한 변경은 high, 복잡한 동시성·권한 경계·비가역 데이터 변경·여러 구성 요소의 실패 경로 추적은 xhigh입니다. 파일 수만으로 올리지 않으며 불명확할 때는 high입니다. 별도 모델 호출이나 재검토는 추가하지 않습니다. 추론 강도가 높아지면 리뷰 호출 자체의 시간·사용량은 늘 수 있습니다.

직접 CLI 실행은 high가 기본이며 `--effort xhigh`로 변경합니다. `--timeout`도 선택 사항입니다. `--output /absolute/new-report.json`은 전체 보고서를 권한 0600으로 저장하며 기존 파일을 덮어쓰지 않습니다.
기본적으로 JSON을 stdout으로 출력합니다. 보고서에는 범위, 지문, 지적, 한계, stale 여부, CLI가 제공하는 사용량이 들어갑니다.
시작 로그와 보고서에 요청 모델·추론 강도를 기록합니다. JSON은 완료 시 반환하므로 대기 중 상태 안내는 Codex가 담당합니다.
지문은 선택한 diff와 untracked 입력을 비교합니다. 검토 도중 다른 참고 파일이 바뀌는 것까지 감지하는 저장소 스냅샷은 아닙니다.

Claude에는 읽기 도구만 노출하지만 이는 별도 OS 파일시스템 샌드박스를 만드는 기능은 아닙니다. 관리자 정책은 Claude CLI에 계속 적용됩니다.
로그인 오류는 터미널에서 `claude auth status`로 확인합니다. 터미널에서는 로그인되어 있는데 Codex에서만 실패한다면 샌드박스의 인증 접근 제한일 수 있으므로 호스트의 승인된 실행 권한을 사용합니다. 실제 미로그인일 때 `claude auth login`을 실행합니다. 검토 실패를 승인으로 간주하거나 Codex가 대체 결과를 생성하지 않습니다.

## 핵심 검증

```bash
python3 -m unittest discover -s prism/tests -v
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py prism/skills/prism
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py prism
```

변경 수집·범위·read-only 실행 인자·결과 오류·타임아웃을 로컬에서 검사합니다. 실제 Claude 품질·비용·대형 저장소 성능은 사용 중 관찰합니다.

2026-09-24 실호출: 사용자 승인 후 약 32KB를 Claude Opus 5.5로 검토하여 JSON 왕복 성공. 전체 47.8초, CLI 실행 46.5초, 1초 샘플 최대 프로세스 합산 RSS 약 247MiB. 정상 종료 후 잔류 Claude 프로세스와 관찰한 projects/sessions/debug/todos/tasks 파일 증가는 없었습니다. 이는 1회 관찰이며 장기 누수 검증은 아닙니다.

검토에서 발견한 비정상 종료 문제를 보완했습니다. Claude는 호스트와 같은 프로세스 그룹에 유지하고, Python 래퍼의 SIGTERM/SIGHUP/SIGINT 및 타임아웃에서 자식에게 SIGTERM을 보낸 뒤 최대 3초 대기하고 필요시 SIGKILL·회수합니다. 종료된 자식에 대한 정리 호출은 원래 오류를 가리지 않습니다. 호스트의 그룹 SIGKILL은 Claude에도 전달됩니다. **Python 부모 PID만 SIGKILL하면 어떤 Python 정리 코드도 실행할 수 없으므로**, 호스트는 실행 그룹 전체를 취소해야 합니다. Codex 앱의 실제 취소 신호 방식은 별도로 검증하지 않았습니다.

모델·강도 전달과 SIGTERM/SIGHUP/SIGINT 자식 회수는 모의 CLI로 검사합니다. 실제 모델을 반복 호출하는 부하 테스트는 하지 않습니다.

참고: [원본 검토 명령](https://github.com/openai/codex-plugin-cc/blob/db52e28f4d9ded852ab3942cea316258ae4ef346/plugins/codex/commands/adversarial-review.md), [Claude CLI](https://code.claude.com/docs/en/cli-reference), [구조화된 출력](https://code.claude.com/docs/en/headless).
