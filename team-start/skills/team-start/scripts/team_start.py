#!/usr/bin/env python3
"""Create a new team's GitHub workspace. Python 3.9+, git and authenticated gh."""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import string
import subprocess
import sys
import uuid

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SETTINGS = {"has_issues": True, "has_wiki": False, "has_discussions": False,
            "allow_squash_merge": True, "allow_merge_commit": False,
            "allow_rebase_merge": False, "delete_branch_on_merge": True}
LABELS = {"applied": "적용 확인", "pending": "초대 수락 대기", "deferred": "보류",
          "unsupported": "지원되지 않음", "failed": "실패"}


class Stop(Exception):
    pass


class Deferred(Stop):
    """Expected user work or an unapplied choice; preserve and keep observing."""


class APIError(Stop):
    def __init__(self, status=None, insufficient_scopes=False, feature_unavailable=False):
        self.feature_unavailable = feature_unavailable
        self.status = status
        self.insufficient_scopes = insufficient_scopes
        if insufficient_scopes:
            super().__init__("GitHub 인증 권한 부족. Projects에는 project 권한이 필요합니다. "
                             "gh auth refresh --hostname github.com -s project로 본인 인증 후 같은 프로젝트에서 재개하세요.")
            return
        super().__init__(f"GitHub 요청 실패 ({status or 'network/GraphQL'}). "
                         "인증·권한·조직 정책과 GitHub 상태를 확인하세요. 자동 재시도하지 않았습니다.")


def command(args, cwd=None, data=None):
    try:
        p = subprocess.run(args, cwd=cwd, input=data, text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(f"{args[0]} 실행 불가 또는 시간 초과. 결과 확인 후 재개하세요.") from e
    if p.returncode:
        # Do not echo commands, server responses, credential helpers or token-bearing stderr.
        raise Stop(f"{args[0]} 실행 실패 (exit {p.returncode}). 로그인·로컬 변경·도구 설치를 확인하세요.")
    return p.stdout.strip()


class GitHub:
    def __init__(self, writable=False):
        self.writable = writable

    def api(self, method, path, body=None, missing=False):
        if method != "GET" and not self.writable and not (
                path == "graphql" and body and body.get("query", "").lstrip().startswith("query")
                and not re.search(r"\bmutation\b", body["query"])):
            raise Stop("읽기 전용 모드에서 변경 요청을 차단했습니다.")
        args = ["gh", "api", "--hostname", "github.com", "--method", method, path,
                "-H", "Accept: application/vnd.github+json"]
        if body is not None:
            args += ["--input", "-"]
        try:
            p = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                               text=True, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise APIError() from e
        try:
            result = json.loads(p.stdout) if p.stdout.strip() else None
        except json.JSONDecodeError as error:
            raise APIError() from error
        errors = result.get("errors", []) if isinstance(result, dict) else []
        insufficient = any(isinstance(e, dict) and e.get("type") == "INSUFFICIENT_SCOPES" for e in errors)
        if p.returncode:
            match = re.search(r"HTTP (\d{3})", p.stderr)
            status = int(match[1]) if match else None
            if missing and status == 404:
                return None
            # Only the explicit rules API upgrade response establishes a tier limit.
            unavailable = (status == 403 and isinstance(result, dict)
                           and re.fullmatch(r"repos/[^/]+/[^/]+/(?:rulesets|rules/branches/[^/?]+)(?:\?.*)?", path)
                           and result.get("message") in {
                               "Upgrade to GitHub Pro or make this repository public to enable this feature.",
                               "Upgrade to GitHub Team or make this repository public to enable this feature."})
            raise APIError(status, insufficient_scopes=insufficient, feature_unavailable=bool(unavailable))
        if errors:
            raise APIError(insufficient_scopes=insufficient)
        return result

    def graphql(self, query, **variables):
        return self.api("POST", "graphql", {"query": query, "variables": variables})["data"]

    def mutate(self, name, input_type, value, selection="clientMutationId"):
        q = f"mutation($input:{input_type}!){{{name}(input:$input){{{selection}}}}}"
        return self.graphql(q, input=value)[name]

    def pages(self, path):
        items, page = [], 1
        while True:
            sep = "&" if "?" in path else "?"
            batch = self.api("GET", f"{path}{sep}per_page=100&page={page}")
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def connection(self, node_id, typename, field, selection):
        items, cursor = [], None
        while True:
            q = (f"query($id:ID!,$cursor:String){{node(id:$id){{... on {typename}{{"
                 f"{field}(first:100,after:$cursor){{nodes{{{selection}}}"
                 "pageInfo{hasNextPage endCursor}}}}}")
            node = self.graphql(q, id=node_id, cursor=cursor)["node"]
            if node is None:
                raise Stop("기록한 GitHub 자원을 찾을 수 없습니다. 재생성하지 않습니다.")
            result = node[field]
            items.extend(result["nodes"])
            if not result["pageInfo"]["hasNextPage"]:
                return items
            cursor = result["pageInfo"]["endCursor"]


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize(raw):
    allowed = {"owner", "name", "path", "description", "visibility", "profile", "members",
               "board", "ai", "approvals", "development", "undecided", "ci", "protection"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise Stop("지원하지 않는 설정 필드입니다. references/interface.md를 확인하세요.")
    s = {"description": "", "visibility": "private", "profile": "hackathon", "members": [],
         "board": True, "ai": False, "development": "미정 — 코드와 실행 방법을 정한 뒤 추가합니다.",
         "undecided": ["기술 스택", "담당 구역", "코드 스타일", "라이선스"],
         "ci": None, "protection": True, **raw}
    for key in ("owner", "name"):
        if not isinstance(s.get(key), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", s[key]):
            raise Stop(f"올바른 {key}이 필요합니다.")
    if s["name"] in (".", "..") or not isinstance(s.get("path"), str) or not Path(s["path"]).is_absolute():
        raise Stop("새 프로젝트의 절대 경로가 필요합니다.")
    s["path"] = str(Path(s["path"]).expanduser().resolve())
    if s["visibility"] not in ("private", "public") or s["profile"] not in ("hackathon", "team"):
        raise Stop("visibility는 private/public, profile은 hackathon/team입니다.")
    s.setdefault("approvals", 0 if s["profile"] == "hackathon" else 1)
    if type(s["approvals"]) is not int or not 0 <= s["approvals"] <= 2:
        raise Stop("approvals는 0~2입니다.")
    for k in ("board", "ai", "protection"):
        if type(s[k]) is not bool:
            raise Stop(f"{k}는 boolean입니다.")
    for k in ("description", "development"):
        if not isinstance(s[k], str):
            raise Stop(f"{k}는 문자열입니다.")
    if len(s["description"]) > 240 or "\n" in s["description"]:
        raise Stop("description은 한 줄 240자 이내입니다.")
    if not isinstance(s["undecided"], list) or not all(isinstance(x, str) for x in s["undecided"]):
        raise Stop("undecided는 문자열 목록입니다.")
    if not isinstance(s["members"], list) or len(s["members"]) > 10:
        raise Stop("members는 최대 10명의 GitHub 로그인 목록입니다.")
    if any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", x) for x in s["members"]):
        raise Stop("members에는 이메일 대신 GitHub 로그인을 입력하세요.")
    if len({x.lower() for x in s["members"]}) != len(s["members"]):
        raise Stop("팀원이 중복되었습니다.")
    if s["ci"] is not None:
        ci = s["ci"]
        if not isinstance(ci, dict) or set(ci) != {"steps", "evidence_paths"}:
            raise Stop("ci에는 steps와 evidence_paths만 지정합니다.")
        if not isinstance(ci["steps"], list) or not ci["steps"]:
            raise Stop("검증한 CI 단계가 필요합니다.")
        for step in ci["steps"]:
            if not isinstance(step, dict) or not isinstance(step.get("name"), str):
                raise Stop("CI 단계마다 name이 필요합니다.")
            if "uses" in step:
                if set(step) - {"name", "uses", "with"} or not isinstance(step["uses"], str) or not re.fullmatch(
                        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}", step["uses"]):
                    raise Stop("외부 action은 공식 저장소에서 확인한 전체 commit SHA로 지정합니다.")
                if "with" in step and not isinstance(step["with"], dict):
                    raise Stop("action의 with는 객체여야 합니다.")
            elif set(step) != {"name", "run"} or not isinstance(step["run"], str) or not step["run"].strip():
                raise Stop("실행 단계에는 name과 실제 run 명령이 필요합니다.")
        if not any(step.get("uses", "").startswith("actions/checkout@") for step in ci["steps"]) or not any("run" in step for step in ci["steps"]):
            raise Stop("CI에는 checkout과 실제 검사 run 단계가 필요합니다.")
        if re.search(r"secrets\s*[.\[]", json.dumps(ci["steps"]), re.IGNORECASE):
            raise Stop("v1 CI에는 secrets 참조를 넣지 않습니다.")
        paths = ci["evidence_paths"]
        if not isinstance(paths, list) or not paths:
            raise Stop("코드 존재 확인에 사용할 evidence_paths가 필요합니다.")
        for p in paths:
            if not isinstance(p, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", p) or any(
                    part in ("..", ".git", ".team-start") for part in Path(p).parts) or Path(p).is_absolute():
                raise Stop("evidence_paths는 저장소 내부의 코드·manifest 경로여야 합니다.")
    return s


def render(s, board=None):
    values = {**s, "repo_url": f"https://github.com/{s['owner']}/{s['name']}",
              "board": board or ("초기 설정 후 링크를 추가합니다." if s["board"] else "사용하지 않습니다."),
              "review": f"다른 팀원 {s['approvals']}명의 승인을 받은 뒤 합칩니다." if s["approvals"] else
                        "PR을 공유하고 확인한 뒤 합칩니다. 승인 인원은 강제하지 않습니다.",
              "merge": "Squash merge를 사용하고 병합된 작업 브랜치는 자동 삭제합니다.",
              "members": "\n".join(f"- @{m}: 개발 참여 (초대 수락·권한 확인 필요)" for m in s["members"]) or "팀원과 담당 역할은 미정입니다.",
              "undecided": "\n".join(f"- {x}" for x in s["undecided"]) or "현재 기록된 미정 사항이 없습니다."}
    files = {}
    for name in ["README.md", "CONTRIBUTING.md"] + (["AGENTS.md"] if s["ai"] else []):
        files[name] = string.Template((ASSETS / (name + ".tmpl")).read_text()).substitute(values)
    files[".gitignore"] = ".team-start/\n.env\n.env.*\n!.env.example\n.DS_Store\n"
    for name in ("bug.yml", "task.yml"):
        files[".github/ISSUE_TEMPLATE/" + name] = (ASSETS / name).read_text()
    files[".github/pull_request_template.md"] = (ASSETS / "pull_request_template.md").read_text()
    return files


def ci_workflow(ci):
    # JSON is a YAML subset; avoids a runtime YAML dependency and interpolation mistakes.
    return json.dumps({"name": "Team Start CI", "on": {"push": {"branches": ["main"]},
                       "pull_request": {}, "workflow_dispatch": {}}, "permissions": {"contents": "read"},
                       "concurrency": {"group": "team-start-${{ github.ref }}", "cancel-in-progress": True},
                       "jobs": {"verify": {"name": "team-start-verify", "runs-on": "ubuntu-latest",
                                           "timeout-minutes": 15, "steps": ci["steps"]}}}, ensure_ascii=False, indent=2) + "\n"


class Runner:
    def __init__(self, spec, gh, apply=False):
        self.s, self.gh, self.apply = normalize(spec), gh, apply
        self.root = Path(self.s["path"])
        self.statefile = self.root / ".team-start/state.json"
        self.state = read_json(self.statefile) if self.statefile.exists() else {}
        if self.state:
            if self.state.get("version") != 1:
                raise Stop("지원하지 않는 실행 기록입니다.")
            old = self.state["spec"]
            for key in ("owner", "name", "path", "visibility", "profile", "members", "board", "ai", "approvals", "protection"):
                if old[key] != self.s[key]:
                    raise Stop(f"재개 중 {key} 변경은 지원하지 않습니다. 새 초기 설정과 혼동하지 마세요.")
        self.base = f"repos/{self.s['owner']}/{self.s['name']}"
        self.results = {}
        self.repo = None
        self.accepted = []
        self.queued_files = {}

    def save(self):
        if self.apply:
            self.state["spec"] = self.s
            tmp = self.statefile.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")
            os.chmod(tmp, 0o600)
            tmp.replace(self.statefile)

    def report(self, key, status, detail, **extra):
        self.results[key] = {"status": status, "label": LABELS[status], "detail": detail, **extra}

    def stage(self, key, fn):
        try:
            fn()
        except Deferred as e:
            self.report(key, "deferred", str(e))
        except (Stop, OSError, ValueError, KeyError) as e:
            self.report(key, "failed", str(e))

    def remember(self, key, value):
        self.state[key] = value
        self.save()

    def creation(self, key, request):
        self.remember(key, True)
        try:
            return request()
        except APIError as error:
            if error.status in (400, 401, 403, 404, 422) or error.insufficient_scopes:
                # A definite rejection can be retried after the cause is resolved.
                # Transport/5xx ambiguity keeps its journal and requires reconciliation.
                self.state.pop(key, None)
                self.save()
            raise

    def manage(self, key, current, desired, write):
        """Compare before writing. A pending value also reconciles a lost response."""
        managed = self.state.setdefault("managed", {})
        entry = managed.get(key)
        if current == desired:
            if self.apply:
                managed[key] = {"value": desired}
                self.save()
            return True
        if entry and current != entry.get("value") and current != entry.get("pending"):
            raise Deferred(f"{key}: 팀원이 변경한 설정입니다. 보존하며 다음 점검에서도 차이를 확인합니다.")
        if not self.apply:
            raise Deferred(f"{key}: 원하는 설정과 다릅니다. apply에서 차이를 확인하세요.")
        managed[key] = {"value": current, "pending": desired}
        self.save()
        write()
        # Keep pending until a subsequent read verifies the result.
        return False

    def preflight(self):
        viewer = self.gh.api("GET", "user")
        owner = self.gh.api("GET", f"users/{self.s['owner']}")
        if owner["type"] not in ("User", "Organization"):
            raise Stop("개인 계정 또는 조직만 지원합니다.")
        if owner["type"] == "User" and viewer["login"].lower() != owner["login"].lower():
            raise Stop("다른 개인 계정 소유의 저장소를 만들 수 없습니다.")
        if self.state.get("actor") not in (None, viewer["id"]):
            raise Stop("초기 생성 때와 다른 GitHub 계정입니다.")
        self.viewer, self.owner = viewer, owner
        self.report("identity", "applied", "GitHub 로그인과 소유자 확인", actor=viewer["login"], owner=owner["login"])

    def repository(self):
        repo = self.gh.api("GET", self.base, missing=True)
        if self.state.get("repo"):
            if not repo or repo["id"] != self.state["repo"]["id"]:
                raise Stop("저장소 ID가 생성 기록과 다릅니다. 생성·수정하지 않습니다.")
        elif repo:
            if not self.state.get("repo_pending") or repo.get("description") != self.marker:
                raise Stop("같은 이름의 기존 저장소입니다. 인수하거나 덮어쓰지 않습니다.")
        elif not self.apply:
            self.report("repository", "deferred", "아직 생성되지 않았습니다.")
            return
        else:
            if self.state.get("repo_pending"):
                # A 404 can hide a completed create after permissions changed. Do not recreate.
                raise Stop("저장소 생성 응답이 불확실합니다. 원격 생성 여부를 확인해야 합니다.")
            endpoint = "user/repos" if self.owner["type"] == "User" else f"orgs/{self.s['owner']}/repos"
            repo = self.creation("repo_pending", lambda: self.gh.api("POST", endpoint, {"name": self.s["name"], "description": self.marker,
                                                "private": self.s["visibility"] == "private", "auto_init": False}))
        if repo.get("private") != (self.s["visibility"] == "private"):
            raise Stop("저장소 공개 여부가 계획과 다릅니다. 자동 변경하지 않습니다.")
        if not repo.get("permissions", {}).get("admin"):
            raise Stop("생성된 저장소의 관리자 권한이 필요합니다.")
        self.repo = repo
        if self.apply and not self.state.get("repo"):
            self.remember("repo", {"id": repo["id"], "node_id": repo["node_id"], "url": repo["html_url"]})
            self.remember("initial_settings", {k: repo.get(k) for k in SETTINGS})
        self.report("repository", "applied", "저장소 ID·공개 여부·관리 권한 확인", url=repo["html_url"], id=repo["id"])

    @property
    def marker(self):
        return f"team-start:{self.state['run_id']}"

    def bootstrap(self):
        if self.state.get("bootstrap_done"):
            self.gh.api("GET", self.base + "/git/ref/heads/main")
            self.report("bootstrap", "applied", "main 초기화 기록 확인")
            return
        content = render(self.s)["README.md"]
        initial = self.gh.api("GET", self.base + "/contents/README.md", missing=True)
        if not initial:
            if not self.apply:
                raise Stop("초기 README가 없습니다.")
            if self.gh.pages(self.base + "/branches"):
                raise Stop("초기화 전에 다른 브랜치가 발견됐습니다. 덮어쓰지 않습니다.")
            self.remember("bootstrap_pending", digest(content))
            self.gh.api("PUT", self.base + "/contents/README.md", {
                "message": "chore: 팀 프로젝트 초기 안내 구성",
                "content": base64.b64encode(content.encode()).decode()})
            initial = self.gh.api("GET", self.base + "/contents/README.md")
        actual = digest(base64.b64decode(initial["content"]).decode())
        if actual != self.state.get("bootstrap_pending"):
            raise Stop("초기 README가 생성 기록과 다릅니다. 사용자 내용을 보존합니다.")
        repo = self.gh.api("GET", self.base)
        if repo["default_branch"] != "main":
            if not self.apply:
                raise Stop("기본 브랜치 main 전환 대기")
            self.gh.api("POST", self.base + "/branches/" + repo["default_branch"] + "/rename", {"new_name": "main"})
        self.gh.api("GET", self.base + "/git/ref/heads/main")
        if self.apply:
            self.state["files"] = {"README.md": actual}
            self.remember("bootstrap_done", True)
        self.report("bootstrap", "applied", "main 초기 커밋 확인")

    def settings(self):
        desired = {**SETTINGS, "description": self.s["description"], "default_branch": "main"}
        repo = self.gh.api("GET", self.base)
        current = {k: repo.get(k) for k in desired}
        if "settings" not in self.state.get("managed", {}):
            baseline = {**self.state["initial_settings"], "description": self.marker,
                        "default_branch": repo["default_branch"]}
            self.state.setdefault("managed", {})["settings"] = {"value": baseline}
        if not self.manage("settings", current, desired, lambda: self.gh.api("PATCH", self.base, desired)):
            fresh = self.gh.api("GET", self.base)
            if {k: fresh.get(k) for k in desired} != desired:
                raise Stop("설정 재조회 불일치")
            self.manage("settings", desired, desired, lambda: None)
        self.report("settings", "applied", "저장소 협업 설정 재조회 완료")

    def members(self):
        pending = {i["invitee"]["login"].lower(): i for i in self.gh.pages(self.base + "/invitations") if i.get("invitee")}
        for login in self.s["members"]:
            self.stage("member:" + login, lambda login=login: self.member(login, pending))
        if not self.s["members"]:
            self.report("members", "deferred", "참여할 GitHub 계정을 지정하지 않았습니다.")

    def member(self, login, pending):
        key = "member:" + login
        permission = self.gh.api("GET", self.base + f"/collaborators/{login}/permission", missing=True)
        role = permission.get("permission") if permission else None
        if role in ("write", "maintain", "admin"):
            if login.lower() != self.viewer["login"].lower():
                self.accepted.append(login)
            self.report(key, "applied", "저장소 쓰기 접근 확인", role=role)
            return
        if login.lower() in pending:
            self.report(key, "pending", "저장소 초대 수락을 기다립니다.")
            return
        sent = self.state.setdefault("invitations", {})
        if login in sent:
            raise Stop("기존 초대가 사라졌거나 권한이 변경됐습니다. 자동 재초대하지 않습니다.")
        if not self.apply:
            self.report(key, "deferred", "초대가 아직 발송되지 않았습니다.")
            return
        sent[login] = "requested"
        self.save()
        try:
            self.gh.api("PUT", self.base + f"/collaborators/{login}", {"permission": "push"})
        except APIError as error:
            if error.status in (400, 401, 403, 404, 422) or error.insufficient_scopes:
                sent.pop(login, None)
                self.save()
            raise
        current = self.gh.api("GET", self.base + f"/collaborators/{login}/permission", missing=True)
        if current and current.get("permission") in ("write", "maintain", "admin"):
            self.accepted.append(login)
            self.report(key, "applied", "저장소 쓰기 접근 재조회 완료")
        else:
            invitations = self.gh.pages(self.base + "/invitations")
            if not any(i.get("invitee", {}).get("login", "").lower() == login.lower() for i in invitations):
                raise Stop("초대 발송 결과를 확인할 수 없습니다.")
            self.report(key, "pending", "초대를 발송했습니다. 수락은 아직 확인되지 않았습니다.")

    def get_project(self):
        return self.gh.graphql("query($id:ID!){node(id:$id){... on ProjectV2{"
                               "id title url public closed owner{... on User{id} ... on Organization{id}}}}}",
                               id=self.state["project"]["id"])["node"]

    def board(self):
        if not self.s["board"]:
            return
        if not self.state.get("project"):
            title = self.s["name"] + " [" + self.marker + "]"
            candidates = self.gh.connection(self.owner["node_id"], self.owner["type"], "projectsV2", "id title url public")
            candidates = [p for p in candidates if p["title"] == title]
            if candidates and not self.state.get("project_pending"):
                raise Stop("보드 생성 기록 없이 같은 식별자의 보드가 발견됐습니다.")
            if len(candidates) > 1:
                raise Stop("보드 식별자가 중복됐습니다. 자동으로 선택하지 않습니다.")
            if candidates:
                project = candidates[0]
            elif not self.apply:
                self.report("board", "deferred", "보드가 아직 생성되지 않았습니다.")
                return
            elif self.state.get("project_pending"):
                raise Stop("보드 생성 결과가 불확실합니다. 재생성하지 않습니다.")
            else:
                project = self.creation("project_pending", lambda: self.gh.mutate("createProjectV2", "CreateProjectV2Input", {
                    "ownerId": self.owner["node_id"], "title": title}, "projectV2{id title url public}"))["projectV2"]
            if self.apply:
                self.remember("project", {"id": project["id"], "url": project["url"]})
            else:
                self.report("board", "deferred", "생성된 보드를 발견했습니다. apply로 기록을 복구하세요.")
                return
        project = self.get_project()
        if not project or project["owner"]["id"] != self.owner["node_id"] or project["closed"]:
            raise Stop("기록한 보드가 없거나 소유자·열림 상태가 변경됐습니다.")
        desired = {"title": self.s["name"], "public": False}
        if not self.manage("board_settings", {k: project[k] for k in desired}, desired,
                           lambda: self.gh.mutate("updateProjectV2", "UpdateProjectV2Input",
                                                 {"projectId": project["id"], **desired})):
            project = self.get_project()
            if {k: project[k] for k in desired} != desired:
                raise Stop("보드 이름·비공개 설정을 확인할 수 없습니다.")
        self.manage("board_settings", desired, desired, lambda: None)
        self.report("board", "applied", "비공개 작업 보드 확인", url=project["url"], id=project["id"])
        self.stage("board_link", self.board_link)
        self.stage("board_view", self.board_view)
        for login in self.s["members"]:
            self.stage("board_member:" + login, lambda login=login: self.board_member(login))

    def board_link(self):
        pid, rid = self.state["project"]["id"], self.repo["node_id"]
        repos = self.gh.connection(pid, "ProjectV2", "repositories", "id")
        if not any(r["id"] == rid for r in repos):
            if not self.apply or self.state.get("board_linked"):
                raise Stop("보드와 저장소의 연결이 없거나 변경됐습니다.")
            self.gh.mutate("linkProjectV2ToRepository", "LinkProjectV2ToRepositoryInput", {"projectId": pid, "repositoryId": rid})
            if not any(r["id"] == rid for r in self.gh.connection(pid, "ProjectV2", "repositories", "id")):
                raise Stop("보드 연결 재조회 실패")
        if self.apply:
            self.remember("board_linked", True)
        self.report("board_link", "applied", "보드와 저장소 연결 확인")

    def board_view(self):
        pid = self.state["project"]["id"]
        views = self.gh.connection(pid, "ProjectV2", "views", "id name layout")
        name = "Team Start " + self.state["run_id"][:8]
        candidates = [v for v in views if v["id"] == self.state.get("view_id")] if self.state.get("view_id") else [v for v in views if v["name"] == name]
        if len(candidates) > 1:
            raise Stop("보드 뷰가 중복되었습니다.")
        if not candidates:
            if not self.apply or self.state.get("view_id") or self.state.get("view_pending"):
                raise Stop("보드 뷰가 없거나 생성 결과가 불확실합니다.")
            self.creation("view_pending", lambda: self.gh.mutate("createProjectV2View", "CreateProjectV2ViewInput", {
                "projectId": pid, "name": name, "layout": "BOARD_LAYOUT"}))
            candidates = [v for v in self.gh.connection(pid, "ProjectV2", "views", "id name layout") if v["name"] == name]
        if len(candidates) != 1:
            raise Stop("보드 뷰를 확인할 수 없습니다.")
        view = candidates[0]
        if self.apply:
            self.remember("view_id", view["id"])
        desired = {"name": "Board", "layout": "BOARD_LAYOUT"}
        self.state.setdefault("managed", {}).setdefault("board_view", {
            "value": {"name": name, "layout": "BOARD_LAYOUT"}})
        current = {k: view[k] for k in desired}
        if not self.manage("board_view", current, desired, lambda: self.gh.mutate(
                "updateProjectV2View", "UpdateProjectV2ViewInput", {"viewId": view["id"], "name": "Board"})):
            fresh = next(v for v in self.gh.connection(pid, "ProjectV2", "views", "id name layout") if v["id"] == view["id"])
            if {k: fresh[k] for k in desired} != desired:
                raise Stop("보드 뷰 이름 변경 후 재조회 불일치")
            self.manage("board_view", desired, desired, lambda: None)
        field = self.gh.graphql("query($id:ID!){node(id:$id){... on ProjectV2{field(name:\"Status\"){"
                                "... on ProjectV2SingleSelectField{id options{id name}}}}}}", id=pid)["node"]["field"]
        names = {o["name"] for o in field["options"]} if field else set()
        if not {"Todo", "In Progress", "Done"} <= names:
            self.report("board_view", "deferred", "보드 뷰는 생성됨. Status의 할 일·진행 중·완료 구성을 UI에서 확인하세요.")
        else:
            self.report("board_view", "applied", "보드 뷰와 Todo·In Progress·Done 상태 확인")

    def board_member(self, login):
        grants = self.state.setdefault("board_grants", {})
        if self.apply and login not in grants:
            user = self.gh.api("GET", "users/" + login)
            # The public ProjectV2 query does not expose current collaborator roles.
            # A mutation receipt is NOT a read-back proof of enduring access.
            grants[login] = "requested"
            self.save()
            self.gh.mutate("updateProjectV2Collaborators", "UpdateProjectV2CollaboratorsInput", {
                "projectId": self.state["project"]["id"], "collaborators": [{"userId": user["node_id"], "role": "WRITER"}]})
            grants[login] = "request_succeeded"
            self.save()
        self.report("board_member:" + login, "deferred",
                    "보드 권한 요청 기록이 있습니다. 현재 권한은 보드 Settings > Manage access에서 별도 확인 필요." if login in grants else
                    "보드 권한 요청 전입니다. 저장소 접근 권한과 별개입니다.")

    def file(self, path, content):
        endpoint = self.base + "/contents/" + path
        current = self.gh.api("GET", endpoint + "?ref=main", missing=True)
        if current and current.get("type") != "file":
            raise Stop(f"{path}: 일반 파일이 아닙니다.")
        old = base64.b64decode(current["content"]).decode() if current else None
        files = self.state.setdefault("files", {})
        pending = self.state.setdefault("file_pending", {})
        wanted = digest(content)
        if old is not None and digest(old) == wanted:
            if self.apply:
                files[path] = wanted
                pending.pop(path, None)
                self.save()
            return True
        baseline = files.get(path)
        if (old is None and baseline is not None) or (old is not None and digest(old) not in (baseline, pending.get(path))):
            raise Deferred(f"{path}: 사용자가 수정·삭제한 파일입니다. 보존하며 다음 점검에서도 차이를 확인합니다.")
        if not self.apply:
            raise Deferred(f"{path}: 생성 내용과 다릅니다. 적용 또는 검토가 필요합니다.")
        if self.main_requires_pr():
            self.queued_files[path] = content
            return False
        pending[path] = wanted
        self.save()
        body = {"message": "chore: 팀 초기 설정 안내 갱신", "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
        if current:
            body["sha"] = current["sha"]
        self.gh.api("PUT", endpoint, body)
        fresh = self.gh.api("GET", endpoint + "?ref=main")
        if digest(base64.b64decode(fresh["content"]).decode()) != wanted:
            raise Stop(f"{path}: 저장 후 재조회 불일치")
        files[path] = wanted
        pending.pop(path, None)
        self.save()
        return True

    def main_requires_pr(self):
        if hasattr(self, "_main_requires_pr"):
            return self._main_requires_pr
        legacy = self.gh.api("GET", self.base + "/branches/main").get("protected", False)
        try:
            effective = self.gh.pages(self.base + "/rules/branches/main")
        except APIError as error:
            if not error.feature_unavailable:
                raise
            effective = []
        # Includes active organization rules. Use a PR conservatively for active rules.
        self._main_requires_pr = bool(legacy or effective)
        return self._main_requires_pr

    def documents(self):
        board = self.state.get("project", {}).get("url")
        for path, content in render(self.s, board).items():
            self.stage("file:" + path, lambda p=path, c=content: self.file_report(p, c))

    def file_report(self, path, content):
        if self.file(path, content):
            self.report("file:" + path, "applied", "원격 파일 내용 확인")
        else:
            self.report("file:" + path, "deferred", "main 보호 규칙에 따라 초기 설정 PR에서 검토할 변경입니다.")

    def issue(self):
        marker = "<!-- " + self.marker + ":onboarding -->"
        known = self.state.get("issue")
        issues = [self.gh.api("GET", self.base + "/issues/" + str(known["number"]))] if known else self.gh.pages(self.base + "/issues?state=all")
        found = [i for i in issues if marker in (i.get("body") or "") and not i.get("pull_request")]
        if len(found) > 1:
            raise Stop("온보딩 이슈 식별자가 중복됐습니다.")
        if not found:
            if not self.apply or known or self.state.get("issue_pending"):
                raise Stop("온보딩 이슈가 없거나 생성 결과가 불확실합니다.")
            found = [self.creation("issue_pending", lambda: self.gh.api("POST", self.base + "/issues", {"title": "팀 시작 체크리스트", "body":
                "- [ ] 팀원 초대 수락과 저장소 접근 확인\n- [ ] 작업 보드 접근 확인\n- [ ] 실행 방법 확정\n- [ ] 첫 작업과 담당자 등록\n\n" + marker}))]
        issue = found[0]
        if known and issue["id"] != known["id"]:
            raise Stop("온보딩 이슈 ID 불일치")
        if self.apply:
            self.remember("issue", {k: issue[k] for k in ("id", "node_id", "number", "html_url")})
        self.report("issue", "applied", "팀 시작 체크리스트 확인", url=issue["html_url"])
        if self.state.get("project"):
            self.stage("board_item", lambda: self.board_item(issue))

    def board_item(self, issue):
        pid = self.state["project"]["id"]
        item_id = self.state.get("board_item")
        if not item_id:
            items = self.gh.connection(pid, "ProjectV2", "items", "id content{... on Issue{id}}")
            matches = [i for i in items if (i.get("content") or {}).get("id") == issue["node_id"]]
            if len(matches) > 1:
                raise Stop("보드 이슈 연결이 중복됐습니다.")
            if matches:
                item_id = matches[0]["id"]
            elif not self.apply:
                raise Stop("보드 이슈 연결 기록이 없습니다. apply로 초기 설정을 재개하세요.")
            else:
                # GitHub reuses an existing item for the same content ID. Its list
                # index can lag behind the node, so retain and verify the returned ID.
                result = self.gh.mutate("addProjectV2ItemById", "AddProjectV2ItemByIdInput",
                                       {"projectId": pid, "contentId": issue["node_id"]}, "item{id}")
                item_id = result["item"]["id"]
            if self.apply:
                self.remember("board_item", item_id)
        item = self.gh.graphql("query($id:ID!){node(id:$id){... on ProjectV2Item{"
                               "id isArchived project{id} content{... on Issue{id}}}}}", id=item_id)["node"]
        if not item or item["project"]["id"] != pid or (item.get("content") or {}).get("id") != issue["node_id"]:
            raise Stop("기록한 보드 항목이 없거나 연결이 변경됐습니다. 재생성하지 않습니다.")
        if item["isArchived"]:
            self.report("board_item", "deferred", "팀원이 보관한 보드 항목입니다. 보관 상태를 유지했습니다.")
            return
        self.report("board_item", "applied", "온보딩 이슈의 보드 연결을 항목 ID로 직접 확인")

    def ci(self):
        ci = self.s["ci"]
        if ci is None:
            self.report("ci", "deferred", "코드·설치·검사 명령 미정. 동작하지 않는 CI를 만들지 않았습니다.")
            return
        if not self.state.get("bootstrap_done"):
            raise Stop("CI는 초기 생성 이후 코드가 추가된 저장소에서 연결합니다.")
        for path in ci["evidence_paths"]:
            result = self.gh.api("GET", self.base + "/contents/" + path + "?ref=main", missing=True)
            if not isinstance(result, dict) or result.get("type") != "file" or not result.get("size"):
                raise Stop("CI의 코드·manifest 파일이 main에 없습니다: " + path)
        workflow = ".github/workflows/team-start.yml"
        if not self.file(workflow, ci_workflow(ci)):
            self.report("ci", "deferred", "CI 설정 PR 병합 후 실제 실행을 확인하세요.")
            return
        head = self.gh.api("GET", self.base + "/git/ref/heads/main")["object"]["sha"]
        runs = self.gh.api("GET", self.base + "/actions/workflows/team-start.yml/runs?branch=main&per_page=100")["workflow_runs"]
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
        runs = [r for r in runs if r["head_sha"] == head and r["event"] in ("push", "workflow_dispatch")]
        latest = max(runs, key=lambda r: (r["run_number"], r.get("run_attempt", 1))) if runs else None
        if not latest or latest["conclusion"] != "success" or dt.datetime.fromisoformat(latest["updated_at"].replace("Z", "+00:00")) < cutoff:
            self.report("ci", "deferred", "현재 main의 최근 CI 성공을 기다립니다. 필수 검사로 지정하지 않았습니다.")
            return
        jobs = self.gh.api("GET", self.base + f"/actions/runs/{latest['id']}/jobs?per_page=100")["jobs"]
        if not any(j["name"] == "team-start-verify" and j["conclusion"] == "success" for j in jobs):
            raise Stop("실제 verify 작업 성공을 확인하지 못했습니다.")
        checks = self.gh.api("GET", self.base + f"/commits/{head}/check-runs?per_page=100")["check_runs"]
        match = [c for c in checks if c["name"] == "team-start-verify" and c["conclusion"] == "success" and c.get("app", {}).get("slug") == "github-actions"]
        if not match:
            raise Stop("GitHub Actions 검사 출처 확인 실패")
        self.ci_check = {"context": "team-start-verify", "integration_id": match[0]["app"]["id"]}
        self.report("ci", "applied", "현재 main의 CI와 실제 검사 성공 확인", url=latest["html_url"])

    def protection(self):
        if not self.s["protection"]:
            return
        name = "team-start-main-" + self.state["run_id"][:8]
        known = self.state.get("ruleset_id")
        try:
            candidates = self.gh.pages(self.base + "/rulesets?includes_parents=false")
        except APIError as error:
            if not error.feature_unavailable:
                raise
            self.report("protection", "unsupported", "GitHub API가 현재 비공개 저장소의 보호 규칙에 요금제 업그레이드가 필요함을 확인했습니다. 문서상 절차는 강제되지 않습니다.")
            return
        candidates = [r for r in candidates if r["id"] == known] if known else [r for r in candidates if r["name"] == name]
        if known and not candidates:
            raise Deferred("팀원이 보호 규칙을 삭제했습니다. 재생성하지 않으며 다음 점검에서도 차이를 확인합니다.")
        if len(candidates) > 1:
            raise Stop("보호 규칙 식별자가 중복됐습니다.")
        rule = self.gh.api("GET", self.base + "/rulesets/" + str(candidates[0]["id"])) if candidates else None
        previous = self.state.get("managed", {}).get("rules", {}).get("value") or {}
        applied_approvals = next((r["parameters"]["required_approving_review_count"]
                                 for r in (rule or {}).get("rules", []) if r["type"] == "pull_request"), 0)
        previous_approvals = next((r["parameters"]["required_approving_review_count"]
                                  for r in previous.get("rules", []) if r["type"] == "pull_request"), 0)
        approvals = self.s["approvals"] if len(self.accepted) >= self.s["approvals"] else 0
        approvals = max(approvals, previous_approvals, applied_approvals)
        rules = [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "pull_request", "parameters": {
            "required_approving_review_count": approvals, "allowed_merge_methods": ["squash"], "dismiss_stale_reviews_on_push": False,
            "require_code_owner_review": False, "require_last_push_approval": False,
            "required_review_thread_resolution": False}}]
        if hasattr(self, "ci_check"):
            rules.append({"type": "required_status_checks", "parameters": {
                "required_status_checks": [self.ci_check], "strict_required_status_checks_policy": False, "do_not_enforce_on_create": False}})
        else:
            # Retain actual enforcement even if the write receipt was lost.
            existing_check = next((r for r in (rule or {}).get("rules", []) if r["type"] == "required_status_checks"), None)
            if existing_check or self.state.get("required_ci"):
                rules.append(existing_check or self.state["required_ci"])
        desired = {"name": name, "target": "branch", "enforcement": "active",
                   "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
                   "bypass_actors": [], "rules": rules}
        current = {k: rule[k] for k in desired} if rule else None
        if not self.apply and not rule:
            raise Deferred("보호 규칙이 아직 없습니다.")
        def write():
            if rule:
                self.gh.api("PUT", self.base + "/rulesets/" + str(rule["id"]), desired)
            else:
                created = self.gh.api("POST", self.base + "/rulesets", desired)
                self.remember("ruleset_id", created["id"])
        if not self.manage("rules", current, desired, write):
            candidates = self.gh.pages(self.base + "/rulesets?includes_parents=false")
            rule = next((r for r in candidates if r["name"] == name), None)
            if not rule:
                raise Stop("보호 규칙 저장 후 확인 실패")
            fresh = self.gh.api("GET", self.base + "/rulesets/" + str(rule["id"]))
            if {k: fresh[k] for k in desired} != desired:
                raise Stop("보호 규칙 재조회 불일치")
        self.manage("rules", desired, desired, lambda: None)
        if self.apply and rule:
            self.remember("ruleset_id", rule["id"])
        if self.apply and hasattr(self, "ci_check"):
            self.remember("required_ci", rules[-1])
        self.report("protection", "applied", "main의 PR·삭제·강제 푸시 방지 규칙 확인")
        if len(self.accepted) < self.s["approvals"]:
            self.report("reviews", "pending", "검토자의 쓰기 접근 확인 후 승인 인원 요건을 활성화합니다.")
        else:
            self.report("reviews", "applied", f"필수 승인 {approvals}명 확인")

    def setup_pr(self):
        if not self.queued_files:
            return
        fingerprint = digest(json.dumps(self.queued_files, sort_keys=True))[:16]
        branch = "codex/team-start-" + fingerprint
        records = self.state.setdefault("setup_prs", {})
        record = records.setdefault(branch, {})
        refpath = self.base + "/git/ref/heads/" + branch
        ref = self.gh.api("GET", refpath, missing=True)
        if ref and ref["object"]["sha"] != record.get("commit"):
            raise Stop("초기 설정 브랜치가 다른 커밋을 가리킵니다. 덮어쓰지 않습니다.")
        if not ref:
            if record.get("commit"):
                raise Stop("초기 설정 브랜치 생성 결과가 불확실하거나 삭제됐습니다.")
            head = self.gh.api("GET", self.base + "/git/ref/heads/main")["object"]["sha"]
            base = self.gh.api("GET", self.base + "/git/commits/" + head)
            tree = self.gh.api("POST", self.base + "/git/trees", {"base_tree": base["tree"]["sha"], "tree": [
                {"path": p, "mode": "100644", "type": "blob", "content": c} for p, c in self.queued_files.items()]})
            commit = self.gh.api("POST", self.base + "/git/commits", {
                "message": "chore: 팀 초기 설정 보완", "tree": tree["sha"], "parents": [head]})
            record["commit"] = commit["sha"]
            self.save()
            self.gh.api("POST", self.base + "/git/refs", {"ref": "refs/heads/" + branch, "sha": commit["sha"]})
        marker = "<!-- " + self.marker + ":" + fingerprint + " -->"
        prs = self.gh.pages(self.base + "/pulls?state=all&head=" + self.s["owner"] + ":" + branch + "&base=main")
        matches = [pr for pr in prs if marker in (pr.get("body") or "")]
        if len(matches) > 1 or (prs and not matches):
            raise Stop("같은 브랜치의 다른 PR이 있습니다. 자동 인수하지 않습니다.")
        if not matches:
            if record.get("pending"):
                raise Stop("PR 생성 결과가 불확실합니다. 원격 상태를 확인하세요.")
            record["pending"] = True
            self.save()
            matches = [self.gh.api("POST", self.base + "/pulls", {
                "title": "chore: 팀 초기 설정 보완", "head": branch, "base": "main",
                "body": "초기 설정에서 보류한 문서 또는 CI를 추가합니다. 변경 내용을 검토한 뒤 병합하세요.\n\n" + marker})]
        pr = matches[0]
        if pr["state"] != "open":
            raise Stop("기존 설정 PR이 닫혔습니다. 병합 또는 거절 내용을 검토하세요.")
        self.state.setdefault("file_pending", {}).update({p: digest(c) for p, c in self.queued_files.items()})
        record["url"] = pr["html_url"]
        self.save()
        self.report("setup_pr", "deferred", "보호 규칙을 유지한 채 변경 PR을 준비했습니다. 검토·병합 후 재개하세요.", url=pr["html_url"])

    def checkout(self):
        url = f"https://github.com/{self.s['owner']}/{self.s['name']}.git"
        gitdir = self.root / ".git"
        if not gitdir.exists():
            if not self.apply:
                self.report("checkout", "deferred", "로컬 Git 작업 폴더 미생성")
                return
            if any(p.name != ".team-start" for p in self.root.iterdir()):
                raise Stop("대상 폴더에 사용자 파일이 있습니다. checkout하지 않습니다.")
            command(["git", "init", "-b", "main", str(self.root)])
            command(["git", "remote", "add", "origin", url], cwd=self.root)
            (gitdir / "info/exclude").write_text(".team-start/\n")
        origin = command(["git", "remote", "get-url", "origin"], cwd=self.root)
        if origin != url:
            raise Stop("로컬 origin이 대상 저장소와 다릅니다.")
        if command(["git", "status", "--porcelain"], cwd=self.root):
            raise Deferred("로컬 변경이 있습니다. 작업을 보존하고 동기화를 보류합니다.")
        if command(["git", "symbolic-ref", "--short", "HEAD"], cwd=self.root) != "main":
            raise Deferred("main이 아닌 로컬 브랜치를 보존했습니다.")
        if self.apply:
            command(["git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential", "fetch", "origin", "main"], cwd=self.root)
            local_main = command(["git", "for-each-ref", "--format=%(objectname)", "refs/heads/main"], cwd=self.root)
            if local_main and int(command(["git", "rev-list", "--count", "origin/main..HEAD"], cwd=self.root)):
                raise Deferred("원격에 없는 사용자 커밋을 보존하고 동기화를 보류했습니다.")
            # merge --ff-only also initializes an unborn main, without reset/clean.
            command(["git", "merge", "--ff-only", "origin/main"], cwd=self.root)
            command(["git", "branch", "--set-upstream-to=origin/main", "main"], cwd=self.root)
        local = command(["git", "rev-parse", "HEAD"], cwd=self.root)
        remote = self.gh.api("GET", self.base + "/git/ref/heads/main")["object"]["sha"]
        if local != remote:
            raise Deferred("로컬 main이 원격 main과 다릅니다. 사용자 커밋은 보존했습니다.")
        self.report("checkout", "applied", "로컬 main과 원격 main 일치", path=str(self.root))

    def run(self):
        self.preflight()
        if self.apply:
            self.remember("actor", self.viewer["id"])
        self.repository()
        if not self.repo:
            return self.results
        self.bootstrap()
        self.stage("settings", self.settings)
        self.stage("members", self.members)
        self.stage("board", self.board)
        self.stage("documents", self.documents)
        self.stage("issue", self.issue)
        self.stage("ci", self.ci)
        if self.apply:
            self.stage("setup_pr", self.setup_pr)
        # Protection last: bootstrapping must not lock itself out.
        self.stage("protection", self.protection)
        self.stage("checkout", self.checkout)
        return self.results


@contextlib.contextmanager
def apply_lock(spec):
    root = Path(spec["path"])
    state = root / ".team-start/state.json"
    if (root / ".team-start").is_symlink() or (root / ".git").is_symlink():
        raise Stop("실행 기록 또는 Git 디렉터리의 심볼릭 링크는 지원하지 않습니다.")
    if not state.exists() and root.exists() and any(p.name != ".team-start" for p in root.iterdir()):
        raise Stop("신규 생성 대상은 빈 폴더여야 합니다. 기존 프로젝트 적용은 지원하지 않습니다.")
    if any((p / ".git").exists() for p in root.parents):
        raise Stop("기존 Git 저장소 내부에 새 프로젝트를 생성하지 않습니다.")
    (root / ".team-start").mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / ".team-start/lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise Stop("다른 초기 설정 실행이 진행 중입니다.") from e
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "apply", "check"])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--spec", type=Path)
    group.add_argument("--path", type=Path, help="기존 Team Start 프로젝트 경로")
    parser.add_argument("--offline", action="store_true", help="plan에서 GitHub 조회 생략")
    args = parser.parse_args()
    try:
        if args.offline and args.mode != "plan":
            raise Stop("--offline은 plan에서만 사용할 수 있습니다.")
        raw = read_json(args.spec) if args.spec else read_json(args.path / ".team-start/state.json")["spec"]
        spec = normalize(raw)
        gh = GitHub(writable=args.mode == "apply")
        if args.mode == "plan":
            runner = Runner(spec, gh)
            if not args.offline:
                runner.preflight()
                exists = gh.api("GET", runner.base, missing=True)
                if exists and (not runner.state.get("repo") or exists["id"] != runner.state["repo"]["id"]):
                    raise Stop("같은 이름의 기존 저장소가 있습니다.")
            print(json.dumps({"mode": "plan", "spec": spec, "files": render(spec),
                              "preflight": runner.results, "remote_mutations": False,
                              "note": "추천안입니다. 사용자 미확정 선택·초대 권한은 실행 전에 해소하세요."}, ensure_ascii=False, indent=2))
            return 0
        if args.mode == "apply":
            with apply_lock(spec):
                runner = Runner(spec, gh, apply=True)
                if not runner.state:
                    runner.state = {"version": 1, "run_id": uuid.uuid4().hex, "spec": spec}
                    runner.save()
                results = runner.run()
        else:
            runner = Runner(spec, gh)
            if not runner.state:
                raise Stop("생성 기록이 없습니다. 기존 임의 저장소는 점검 대상으로 인수하지 않습니다.")
            results = runner.run()
        print(json.dumps({"mode": args.mode, "results": results}, ensure_ascii=False, indent=2))
        return 1 if any(v["status"] == "failed" for v in results.values()) else 0
    except (Stop, OSError, ValueError, KeyError) as e:
        print(json.dumps({"status": "failed", "detail": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
