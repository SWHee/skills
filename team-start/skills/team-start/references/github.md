# GitHub 기능과 권한

공식 문서 확인일: 2026-09-26. 실제 API·조직 정책이 우선하며 403을 무조건 유료 제한으로 분류하지 않는다.

- [계정 종류](https://docs.github.com/en/get-started/learning-about-github/types-of-github-accounts): Repository는 코드·이슈 공간, Organization은 팀 소유와 접근 관리를 위한 계정이다. 짧은 협업은 개인 저장소 초대도 가능하다.
- [조직 생성](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/creating-a-new-organization-from-scratch): 일반 새 조직은 공식 UI에서 생성하도록 안내한다. 스킬은 결제나 조직 전체 정책을 변경하지 않는다.
- [Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets): 무료 공개 저장소는 지원. 비공개는 개인 Pro 또는 조직 Team/Enterprise 등 소유 계정의 적합한 요금제 필요. 개인 Pro가 별도 무료 조직의 기능을 올려주지 않는다.
- [CLI 저장소 생성](https://cli.github.com/manual/gh_repo_create), [REST 저장소](https://docs.github.com/en/rest/repos/repos): 생성·설정 권한을 확인한다. 빈 원격 저장소의 첫 커밋은 Contents API로 만든 후 main을 확정한다.
- [협업자 API](https://docs.github.com/en/rest/collaborators/collaborators): 저장소 초대와 실제 쓰기 권한을 구분한다. 조직 정책·SSO·외부 협업자 제한으로 실패할 수 있다. 스킬은 조직 멤버십을 바꾸지 않는다.
- [Projects CLI](https://cli.github.com/manual/gh_project): OAuth 토큰은 project scope가 필요하다. 필요할 때 `gh auth refresh --hostname github.com -s project`를 사용자가 인증할 수 있게 안내한다. 기존 인증 종류에 맞게 대응하고 토큰을 표시하지 않는다.
- [Projects GraphQL](https://docs.github.com/en/graphql/reference/projects): createProjectV2, createProjectV2View(BOARD_LAYOUT), updateProjectV2View, linkProjectV2ToRepository, updateProjectV2Collaborators, addProjectV2ItemById를 사용한다. 공개 ProjectV2 조회 필드에는 협업자 역할 목록이 없으므로 권한 요청 성공과 현재 권한 확인을 구분한다. Projects classic API를 v2에 사용하지 않는다.
- [Projects 권한](https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-your-project/managing-access-to-your-projects): 저장소·보드 권한 별도. 보드 URL 뒤 `/settings/access` 또는 UI Settings > Manage access에서 확인한다. 실제 UI 경로가 다르면 화면의 링크를 따른다. 조직 외부 협업자가 보드에 추가되지 않으면 실패 이유와 가능한 수동 선택지를 설명하며 조직 멤버로 자동 승격하지 않는다.
- [Contents 권한](https://docs.github.com/en/rest/repos/contents): 워크플로 작성에는 Contents 외 Workflows 쓰기 또는 OAuth workflow scope도 필요할 수 있다.
- [필수 검사](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks): 최근 7일 내 성공, 현재 main의 실제 run/job/check 출처를 확인한 후 연결한다. skip/neutral을 이 도구의 성공 증거로 쓰지 않는다.

요금제 필드나 추가 user scope에 의존하지 않는다. [rulesets 조회](https://docs.github.com/en/rest/repos/rules#get-all-repository-rulesets)의 명확한 업그레이드 요구 응답만 지원 불가로 분류하며 일반 403·SSO·인증 오류와 구분한다. [main의 유효 규칙 조회](https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch)로 저장소·조직의 활성 규칙을 확인하고 기존 branch protection도 함께 확인한다. 규칙 조회가 실패하면 직접 쓰기를 진행하지 않는다. 조직의 기존 상위 규칙은 우회하거나 약화하지 않는다. 새 저장소에도 상위 규칙이 첫 커밋을 막으면 해당 단계를 실패로 보고하고 관리자의 구체적 조치를 안내한다. 무료 Actions도 무제한 비용을 보장하지 않으며 유료 runner·결제 설정을 켜지 않는다.
