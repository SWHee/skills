# 실행 계약

`python3 <skill-root>/scripts/team_start.py plan|apply|check --spec <absolute-json>`

기존 초기 설정은 `apply|check --path <absolute-project-folder>`로 이어간다. `plan --offline`만 인증 없이 실행할 수 있다. plan/check는 원격 변경뿐 아니라 실행 기록·프로젝트 파일도 변경하지 않는다. plan은 JSON으로 문서 초안을 반환하며 호출한 에이전트가 필요할 때 별도 산출물로 보관한다.

## 입력 예

```json
{
  "owner": "YOUR_LOGIN_OR_ORG",
  "name": "new-team-project",
  "path": "/absolute/path/to/new-team-project",
  "description": "팀이 함께 만드는 프로젝트",
  "visibility": "private",
  "profile": "hackathon",
  "members": [],
  "board": true,
  "ai": false,
  "protection": true,
  "approvals": 0,
  "development": "미정 — 기술 스택과 실행 방법을 정한 뒤 추가합니다.",
  "undecided": ["기술 스택", "담당 구역", "코드 스타일", "라이선스"],
  "ci": null
}
```

예시의 소유자·경로는 반드시 실제 선택으로 치환한다. `members`는 초대해도 된다고 사용자가 지정한 GitHub 로그인만 입력한다. 빈 목록은 초대 없음이다. v1은 개발자 쓰기 권한을 제공하며 관리자·조직 멤버 초대와 팀 그룹 생성은 하지 않는다. 보드는 같은 소유자 아래 비공개로 생성하고 지정한 개발자에게 WRITER를 요청한다. 개인 저장소 소유자는 본인 계정만 가능하다.

필수: owner, name, path. 그 외 기본값은 위 예와 같으며 team 프로필의 approvals 기본값은 1이다. 지원 호스트는 github.com. 대상은 임시 폴더가 아닌 지속적인 프로젝트 보관 위치를 사용한다. 대상 폴더는 비어 있어야 하며 다른 Git 저장소 안에는 만들지 않는다. Git 설정·전역 인증 설정은 바꾸지 않는다. description은 한 줄 240자 이내다.

재개 시 대상, 공개 여부, 프로필, 멤버, 기능 선택과 승인 인원은 고정한다. description, development, undecided, ci는 새 spec으로 갱신할 수 있다. 이 제한은 기존 저장소 운영 도구로 확장되지 않게 하기 위한 것이다. CI가 필요해진 경우 `.team-start/state.json`을 직접 편집하지 않고 저장된 spec을 복사해 ci를 채운 새 입력을 제공한다.

## CI 입력

`ci`는 `steps`와 `evidence_paths`를 가진 객체다.

- evidence_paths: 원격 main에서 실제 코드를 확인할 상대 파일 경로 목록. 설치 manifest와 검사 대상 코드를 포함한다.
- steps: GitHub Actions 순서의 객체 목록. `name`+`uses`+선택적 `with`, 또는 `name`+`run`만 허용한다.
- actions/checkout과 실제 검사 run 단계를 포함한다. 외부 action의 `uses`는 공식 저장소에서 확인한 40자리 commit SHA여야 한다. 꾸며낸 SHA를 사용하지 않는다.
- 검증한 런타임 설정, 의존성 설치, 실제 검사 명령을 넣는다. 스크립트는 사용자가 승인한 이 명령을 Actions에 기록하며 자체 로컬 실행하지 않는다. 에이전트가 명령 유효성을 먼저 검증한다.
- 워크플로는 ubuntu-latest, 15분 제한, contents:read, push(main)/pull_request/workflow_dispatch, 고유 검사 이름 team-start-verify를 사용한다. secrets, 배포와 임의 workflow 구조는 지원하지 않는다.
- 저장소가 비어 있거나 명령이 아직 없으면 ci:null을 유지한다. 지원하지 않는 환경은 문서와 다음 행동으로 남긴다.

보호된 main에서는 변경 PR을 반환한다. PR 병합 → main CI 성공 → apply 순으로 필수 검사를 활성화한다. check는 확인만 하며 필수 검사를 추가하지 않는다. 최근 성공이 없으면 기존 필수 검사는 그대로 유지한다.

## 출력과 복구

JSON `results`의 항목은 status, label, detail과 필요한 id/url/path를 포함한다.

| status | 의미 |
| --- | --- |
| applied | 해당 항목을 실제 조회하여 확인 |
| pending | 초대 수락 또는 검토자 참여 대기 |
| deferred | 미정·CI·설정 PR·수동 확인·사용자 변경 보존 등 후속 확인 필요 |
| unsupported | 저장소 API가 기능의 요금제 제한을 명확히 확인 |
| failed | 요청 실패·자원 식별 충돌·저장 후 검증 불일치 |

종료 코드 0: 조회·처리 완료, 보류/지원 불가가 포함될 수 있음. 1: 일부 단계 실패. 2: 입력/신원/대상 확인 실패로 전체 진행 중단. 어느 코드도 일괄적인 ‘완료’ 판단에 쓰지 않는다.

생성 전 의도를 로컬에 기록한다. 저장소 설명/보드 임시 제목/이슈 본문의 실행 식별자와 저장된 자원 ID로 응답 손실을 복구한다. 저장소·보드 식별자는 생성 확인 후 사용자 제목으로 바꾸지만 로컬 ID는 유지한다. 목록은 페이지 끝까지 조회한다. 404는 권한 상실일 수도 있으므로 생성 시도 후 자원을 못 찾으면 자동 재생성하지 않는다. 권한 문제를 해결한 뒤 재개하고, 불확실한 기록을 지워 우회하지 않는다.

`.team-start`는 Git 제외, 로컬 상태 파일은 소유자 읽기/쓰기 권한으로 기록한다. 비밀값은 넣지 않는다. 생성 기록을 잃으면 임의 저장소를 인수하지 않는다. 로컬 원본 폴더와 실행 기록을 함께 보존해야 하며 임시 폴더는 재부팅·정리 시 사라질 수 있다. 수정·삭제된 파일이나 설정은 덮어쓰지 않고 보류로 보고한다. 자동으로 관리 대상에서 제외하지 않으므로 다음 점검에서도 차이를 확인한다. 로컬 작업 브랜치·미커밋 변경·원격에 없는 커밋도 보존하고 동기화만 보류한다. check가 드리프트를 보고하면 변경 내용을 검토하며 이 도구 밖의 수동 변경은 사용자의 별도 요청 범위에서 다룬다.
