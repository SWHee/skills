# skills

개인용 커스텀 Claude 스킬 모음집. 스킬 하나당 폴더 하나, 폴더명이 스킬명입니다.

## 구조

```
<skill-name>/
  SKILL.md      # name, description 프론트매터 + 스킬 본문
  ...           # 스크립트, 레퍼런스 등 필요한 파일
```

## 스킬 목록

| 스킬 | 설명 |
| --- | --- |
| _(아직 없음)_ | |

## 설치

```bash
ln -s "$PWD/<skill-name>" ~/.claude/skills/<skill-name>
```

## 커밋 규칙

Conventional Commits 타입(`feat:`, `fix:`, `chore:`, `docs:` 등) + 한국어 설명.

```
feat: graphify 스킬 추가
docs: README 스킬 목록 갱신
```
