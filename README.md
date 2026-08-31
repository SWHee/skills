# skills

개인용 커스텀 AI 에이전트 스킬 모음집. 스킬 하나당 폴더 하나, 폴더명이 스킬명입니다.

## 구조

```
<skill-name>/
  SKILL.md      # name, description 프론트매터 + 스킬 본문
  ...           # 스크립트, 레퍼런스 등 필요한 파일
```

## 스킬 목록

| 스킬 | 환경 | 설명 |
| --- | --- | --- |
| [`falsify`](./falsify) | Codex | 주장·계획·결과물을 적대적 검증자의 관점에서 짧고 날카롭게 검증 |

## 설치

```bash
ln -s "$PWD/<skill-name>" ~/.codex/skills/<skill-name>
```

명시적 스킬은 `$<skill-name>`으로 호출합니다.

현재 `falsify`의 1회성 explicit-only 호출 정책은 Codex에서 검증되었습니다. 다른 런타임용 패키징은 각 스킬의 환경 표기를 따릅니다.

## 커밋 규칙

Conventional Commits 타입(`feat:`, `fix:`, `chore:`, `docs:` 등) + 한국어 설명.

```
feat: graphify 스킬 추가
docs: README 스킬 목록 갱신
```
