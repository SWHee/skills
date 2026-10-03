"""Behavioral tests with a stateful GitHub double; no network, invitations or credentials."""
import base64
import contextlib
import copy
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

SCRIPT = Path(__file__).resolve().parents[1] / "skills/team-start/scripts/team_start.py"
spec = importlib.util.spec_from_file_location("team_start", SCRIPT)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class FakeGitHub:
    def __init__(self, plan="free", org=False):
        self.viewer = {"login": "lead", "id": 1, "node_id": "U1", "type": "User", "plan": {"name": plan}}
        self.owner = {"login": "team", "id": 2, "node_id": "O2", "type": "Organization", "plan": {"name": plan}} if org else self.viewer
        self.repo = None
        self.files = {}
        self.head = None
        self.branch_name = "main"
        self.invites = []
        self.permissions = {"lead": "admin"}
        self.projects = []
        self.views = []
        self.links = []
        self.items = []
        self.issues = []
        self.rules = []
        self.rules_available = plan != "free"
        self.effective_rules = []
        self.calls = []
        self.lost = None
        self.project_denied = False
        self.runs = []
        self.jobs = []
        self.checks = []
        self.prs = []
        self.refs = {}
        self.trees = {}
        self.commits = {}
        self.seq = 0

    def new_id(self):
        self.seq += 1
        return self.seq

    def advance(self):
        self.head = "sha" + str(self.new_id())
        return self.head

    def api(self, method, path, body=None, missing=False):
        self.calls.append((method, path, copy.deepcopy(body)))
        result = self._api(method, path, body, missing)
        if self.lost == (method, path):
            self.lost = None
            raise t.APIError()
        return copy.deepcopy(result)

    def _api(self, method, path, body, missing):
        url = urlsplit(path)
        p, qs = url.path, parse_qs(url.query)
        if method == "GET" and p == "user":
            return self.viewer
        if method == "GET" and p.startswith("users/"):
            name = p.split("/")[-1]
            return self.owner if name == self.owner["login"] else {"login": name, "node_id": "U-" + name}
        if method == "GET" and p.startswith("orgs/"):
            return self.owner
        if method == "POST" and (p == "user/repos" or p.endswith("/repos")):
            if self.repo:
                raise t.APIError(422)
            self.repo = {"id": 100, "node_id": "R100", "html_url": "https://github.com/lead/demo", "default_branch": "main",
                         "permissions": {"admin": True}, **{k: False for k in t.SETTINGS}, **body}
            return self.repo
        base = "repos/" + self.owner["login"] + "/demo"
        if p == base:
            if not self.repo:
                if missing:
                    return None
                raise t.APIError(404)
            if method == "PATCH":
                self.repo.update(body)
            return self.repo
        rest = p.removeprefix(base)
        if rest.startswith("/contents/"):
            filename = rest.removeprefix("/contents/")
            if method == "GET":
                if filename not in self.files:
                    if missing:
                        return None
                    raise t.APIError(404)
                return {"type": "file", "sha": t.digest(self.files[filename]), "size": len(self.files[filename]),
                        "content": base64.b64encode(self.files[filename].encode()).decode()}
            if method == "PUT":
                if body.get("sha") and body["sha"] != t.digest(self.files[filename]):
                    raise t.APIError(409)
                self.files[filename] = base64.b64decode(body["content"]).decode()
                self.advance()
                return {"content": {"sha": t.digest(self.files[filename])}}
        if rest.startswith("/git/ref/heads/"):
            name = rest.removeprefix("/git/ref/heads/")
            sha = self.head if name == "main" else self.refs.get(name)
            if sha:
                return {"object": {"sha": sha}}
            if missing:
                return None
            raise t.APIError(404)
        if rest == "/branches":
            return [{"name": self.branch_name}] if self.head else []
        if rest == "/branches/main":
            return {"protected": bool(self.rules)}
        if rest.endswith("/rename"):
            self.branch_name = body["new_name"]
            self.repo["default_branch"] = self.branch_name
            return {}
        if rest == "/invitations":
            return self.invites
        if rest.endswith("/permission"):
            name = rest.split("/")[-2]
            return {"permission": self.permissions.get(name, "none")}
        if rest.startswith("/collaborators/") and method == "PUT":
            self.invites.append({"invitee": {"login": rest.split("/")[-1]}})
            return {}
        if rest == "/issues":
            if method == "POST":
                self.issues.append({"id": 20, "node_id": "I20", "number": 1,
                                    "html_url": "https://github.com/lead/demo/issues/1", **body})
                return self.issues[-1]
            return self.issues
        if rest.startswith("/issues/"):
            return self.issues[0]
        if rest in ("/rulesets", "/rules/branches/main") and self.repo["private"] and not self.rules_available:
            raise t.APIError(403, feature_unavailable=True)
        if rest == "/rules/branches/main":
            return self.effective_rules + [rule for ruleset in self.rules if ruleset["enforcement"] == "active" for rule in ruleset["rules"]]
        if rest == "/rulesets":
            if method == "POST":
                self.rules.append({"id": 30, **copy.deepcopy(body)})
                return self.rules[-1]
            return self.rules
        if rest.startswith("/rulesets/"):
            rule = next(x for x in self.rules if str(x["id"]) == rest.split("/")[-1])
            if method == "PUT":
                rule.update(copy.deepcopy(body))
            return rule
        if rest.startswith("/actions/workflows/"):
            return {"workflow_runs": self.runs}
        if rest.startswith("/actions/runs/"):
            return {"jobs": self.jobs}
        if rest.endswith("/check-runs"):
            return {"check_runs": self.checks}
        if rest == "/git/trees":
            sha = "tree" + str(self.new_id())
            self.trees[sha] = body["tree"]
            return {"sha": sha}
        if rest == "/git/commits":
            sha = "commit" + str(self.new_id())
            self.commits[sha] = body
            return {"sha": sha}
        if rest.startswith("/git/commits/"):
            return {"tree": {"sha": "tree-main"}}
        if rest == "/git/refs":
            self.refs[body["ref"].removeprefix("refs/heads/")] = body["sha"]
            return {"object": {"sha": body["sha"]}}
        if rest == "/pulls":
            if method == "POST":
                self.prs.append({"id": 99, "state": "open", "html_url": "https://github.com/lead/demo/pull/2", **body})
                return self.prs[-1]
            head = qs.get("head", [":"])[0].split(":")[-1]
            return [p for p in self.prs if p["head"] == head]
        raise AssertionError((method, path, body))

    def pages(self, path):
        return self.api("GET", path)

    def connection(self, node_id, typename, field, selection):
        self.calls.append(("GET-GRAPHQL", field, None))
        if self.project_denied:
            raise t.APIError(403)
        return copy.deepcopy({"projectsV2": self.projects, "views": self.views,
                              "repositories": self.links, "items": self.items}[field])

    def graphql(self, query, **variables):
        self.calls.append(("GET-GRAPHQL", query, variables))
        if "... on ProjectV2Item{" in query:
            found = next((i for i in self.items if i["id"] == variables["id"]), None)
            return {"node": {**copy.deepcopy(found), "project": {"id": "P1"}, "isArchived": found.get("isArchived", False)} if found else None}
        if "field(name:" in query:
            return {"node": {"field": {"id": "STATUS", "options": [{"id": n, "name": n} for n in ("Todo", "In Progress", "Done")]}}}
        return {"node": copy.deepcopy(next((p for p in self.projects if p["id"] == variables["id"]), None))}

    def mutate(self, name, typ, value, selection="clientMutationId"):
        self.calls.append(("MUTATION", name, copy.deepcopy(value)))
        if self.project_denied:
            raise t.APIError(403)
        result = {}
        if name == "createProjectV2":
            self.projects.append({"id": "P1", "url": "https://github.com/users/lead/projects/1", "title": value["title"], "public": False,
                                  "owner": {"id": self.owner["node_id"]}, "closed": False})
            result = {"projectV2": self.projects[-1]}
        elif name == "updateProjectV2":
            self.projects[0].update({k: v for k, v in value.items() if k != "projectId"})
        elif name == "linkProjectV2ToRepository":
            self.links.append({"id": value["repositoryId"]})
        elif name == "createProjectV2View":
            self.views.append({"id": "V1", "name": value["name"], "layout": value["layout"]})
        elif name == "updateProjectV2View":
            next(v for v in self.views if v["id"] == value["viewId"])["name"] = value["name"]
        elif name == "updateProjectV2Collaborators":
            pass
        elif name == "addProjectV2ItemById":
            self.items.append({"id": "ITEM1", "content": {"id": value["contentId"]}})
            result = {"item": {"id": "ITEM1"}}
        else:
            raise AssertionError(name)
        if self.lost == name:
            self.lost = None
            raise t.APIError()
        return copy.deepcopy(result)

    def success(self):
        self.runs = [{"id": 8, "head_sha": self.head, "event": "push", "run_number": 1, "conclusion": "success",
                      "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "html_url": "https://github.com/lead/demo/actions/runs/8"}]
        self.jobs = [{"name": "team-start-verify", "conclusion": "success"}]
        self.checks = [{"name": "team-start-verify", "conclusion": "success", "app": {"id": 15368, "slug": "github-actions"}}]


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.s = t.normalize({"owner": "lead", "name": "demo", "path": str(self.root)})
        self.gh = FakeGitHub()
        self.checkout = patch.object(t.Runner, "checkout", lambda r: None)
        self.checkout.start()
        self.addCleanup(self.checkout.stop)

    def run_flow(self, apply=True):
        if apply:
            with t.apply_lock(self.s):
                runner = t.Runner(self.s, self.gh, apply=True)
                if not runner.state:
                    runner.state = {"version": 1, "run_id": "a" * 32, "spec": self.s}
                    runner.save()
                result = runner.run()
        else:
            runner = t.Runner(self.s, self.gh)
            result = runner.run()
        return runner, result

    def no_failures(self, results):
        self.assertFalse({k: v for k, v in results.items() if v["status"] == "failed"})

    def ci_spec(self):
        return {"steps": [{"name": "Checkout", "uses": "actions/checkout@" + "a" * 40},
                          {"name": "Test", "run": "python3 -m unittest discover -s tests"}],
                "evidence_paths": ["tests/test_app.py"]}

    def test_free_private_without_code(self):
        runner, results = self.run_flow()
        self.no_failures(results)
        self.assertEqual(results["protection"]["status"], "unsupported")
        self.assertEqual(results["ci"]["status"], "deferred")
        self.assertFalse(self.rules_mutations())
        self.assertNotIn("AGENTS.md", self.gh.files)
        self.assertIn(".team-start/", self.gh.files[".gitignore"])
        self.assertEqual(len(self.gh.projects), 1)
        self.assertEqual(len(self.gh.issues), 1)
        self.assertIn("projects/1", self.gh.files["README.md"])
        self.assertEqual(runner.statefile.stat().st_mode & 0o777, 0o600)

    def rules_mutations(self):
        return [x for x in self.gh.calls if x[0] != "GET" and "/rulesets" in x[1]]

    def test_second_apply_is_noop(self):
        self.run_flow()
        self.gh.calls.clear()
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertTrue(all(c[0] in ("GET", "GET-GRAPHQL") for c in self.gh.calls), self.gh.calls)

    def test_check_is_read_only_even_with_drift(self):
        runner, _ = self.run_flow()
        before = runner.statefile.read_bytes()
        self.gh.repo["allow_merge_commit"] = True
        self.gh.calls.clear()
        _, result = self.run_flow(False)
        self.assertEqual(result["settings"]["status"], "deferred")
        self.assertEqual(runner.statefile.read_bytes(), before)
        self.assertTrue(all(c[0] in ("GET", "GET-GRAPHQL") for c in self.gh.calls))

    def test_public_protection_and_pending_reviewer(self):
        self.s.update(visibility="public", members=["dev"], approvals=1)
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(result["member:dev"]["status"], "pending")
        self.assertEqual(result["reviews"]["status"], "pending")
        self.assertEqual(self.gh.rules[0]["rules"][2]["parameters"]["required_approving_review_count"], 0)
        self.assertEqual(result["board_member:dev"]["status"], "deferred")
        self.gh.permissions["dev"] = "write"
        self.gh.invites = []
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(self.gh.rules[0]["rules"][2]["parameters"]["required_approving_review_count"], 1)
        self.gh.permissions.pop("dev")
        _, result = self.run_flow()
        self.assertEqual(self.gh.rules[0]["rules"][2]["parameters"]["required_approving_review_count"], 1)

    def test_lost_rule_update_does_not_weaken_after_reviewer_leaves(self):
        self.s.update(visibility="public", members=["dev"], approvals=1)
        self.run_flow()
        self.gh.permissions["dev"] = "write"
        self.gh.invites = []
        self.gh.lost = ("PUT", "repos/lead/demo/rulesets/30")
        self.run_flow()
        self.gh.permissions.pop("dev")
        self.run_flow()
        self.assertEqual(self.gh.rules[0]["rules"][2]["parameters"]["required_approving_review_count"], 1)

    def test_stale_ci_and_wrong_check_source_are_not_success(self):
        self.s["protection"] = False
        self.run_flow()
        self.s["ci"] = self.ci_spec()
        self.gh.files["tests/test_app.py"] = "import unittest\n"
        self.run_flow()
        self.gh.success()
        self.gh.runs[0]["updated_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
        _, result = self.run_flow()
        self.assertEqual(result["ci"]["status"], "deferred")
        self.gh.success()
        self.gh.checks[0]["app"]["slug"] = "unrelated-app"
        _, result = self.run_flow()
        self.assertEqual(result["ci"]["status"], "failed")

    def test_board_item_verification_ignores_stale_list_index(self):
        original = self.gh.connection
        def stale(node_id, typename, field, selection):
            if field == "items":
                return []
            return original(node_id, typename, field, selection)
        with patch.object(self.gh, "connection", side_effect=stale):
            _, result = self.run_flow()
            self.no_failures(result)
            self.gh.calls.clear()
            _, result = self.run_flow()
            self.no_failures(result)
            self.assertFalse(any(c[0] == "MUTATION" for c in self.gh.calls))
            self.assertEqual(len(self.gh.items), 1)

    def test_board_denial_preserves_other_work(self):
        self.gh.project_denied = True
        _, result = self.run_flow()
        self.assertEqual(result["board"]["status"], "failed")
        self.assertEqual(result["settings"]["status"], "applied")
        self.assertIn("CONTRIBUTING.md", self.gh.files)
        self.gh.project_denied = False
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(len(self.gh.projects), 1)

    def test_definite_create_rejection_can_retry_after_permission_fix(self):
        original = self.gh.api
        def rejected(method, path, body=None, missing=False):
            if method == "POST" and path == "user/repos":
                raise t.APIError(403)
            return original(method, path, body, missing)
        with patch.object(self.gh, "api", side_effect=rejected):
            with self.assertRaises(t.APIError):
                self.run_flow()
        _, result = self.run_flow()
        self.no_failures(result)

    def test_graphql_scope_rejection_does_not_poison_creation_journal(self):
        original = self.gh.mutate
        def rejected(name, typ, value, selection="clientMutationId"):
            if name == "createProjectV2":
                raise t.APIError(insufficient_scopes=True)
            return original(name, typ, value, selection)
        with patch.object(self.gh, "mutate", side_effect=rejected):
            runner, result = self.run_flow()
            self.assertNotIn("project_pending", runner.state)
            self.assertEqual(result["board"]["status"], "failed")
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(len(self.gh.projects), 1)

    def test_check_detects_removed_remote_document(self):
        self.run_flow()
        self.gh.files.pop("CONTRIBUTING.md")
        _, result = self.run_flow(False)
        self.assertEqual(result["file:CONTRIBUTING.md"]["status"], "deferred")
        _, result = self.run_flow()
        self.assertNotIn("CONTRIBUTING.md", self.gh.files)

    def test_private_organization_uses_repository_capability(self):
        self.gh = FakeGitHub(plan="free", org=True)
        self.gh.viewer["plan"] = {"name": "pro"}
        self.s["owner"] = "team"
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(result["protection"]["status"], "unsupported")

    def test_lost_repository_response_recovers_by_marker(self):
        self.gh.lost = ("POST", "user/repos")
        with self.assertRaises(t.APIError):
            self.run_flow()
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(sum(c[:2] == ("POST", "user/repos") for c in self.gh.calls), 1)

    def test_uncertain_repository_absence_does_not_recreate(self):
        self.gh.lost = ("POST", "user/repos")
        with self.assertRaises(t.APIError):
            self.run_flow()
        self.gh.repo = None
        with self.assertRaisesRegex(t.Stop, "불확실"):
            self.run_flow()
        self.assertEqual(sum(c[:2] == ("POST", "user/repos") for c in self.gh.calls), 1)

    def test_lost_board_view_issue_responses_do_not_duplicate(self):
        for failure in ("createProjectV2", "createProjectV2View", ("POST", "repos/lead/demo/issues")):
            with self.subTest(failure=failure):
                self.gh = FakeGitHub()
                self.root = Path(self.tmp.name) / ("p" + str(len(list(Path(self.tmp.name).iterdir()))))
                self.s["path"] = str(self.root)
                self.gh.lost = failure
                self.run_flow()
                _, result = self.run_flow()
                self.no_failures(result)
                self.assertEqual(len(self.gh.projects), 1)
                self.assertEqual(len(self.gh.views), 1)
                self.assertEqual(len(self.gh.issues), 1)

    def test_existing_repository_rejected(self):
        self.gh.repo = {"id": 123, "description": "someone else's project"}
        with self.assertRaisesRegex(t.Stop, "기존 저장소"):
            self.run_flow()
        self.assertTrue(all(c[0] == "GET" for c in self.gh.calls))

    def test_repository_replacement_rejected(self):
        self.run_flow()
        self.gh.repo["id"] = 999
        self.gh.calls.clear()
        with self.assertRaisesRegex(t.Stop, "ID"):
            self.run_flow()
        self.assertTrue(all(c[0] == "GET" for c in self.gh.calls))

    def test_user_edits_files_settings_and_rules_preserved(self):
        self.s["visibility"] = "public"
        self.run_flow()
        self.gh.files["README.md"] = "our README"
        self.gh.repo["allow_merge_commit"] = True
        self.gh.rules[0]["enforcement"] = "disabled"
        _, result = self.run_flow()
        self.assertEqual(result["file:README.md"]["status"], "deferred")
        self.assertEqual(result["settings"]["status"], "deferred")
        self.assertEqual(result["protection"]["status"], "deferred")
        self.assertEqual(self.gh.files["README.md"], "our README")
        self.assertTrue(self.gh.repo["allow_merge_commit"])
        self.assertEqual(self.gh.rules[0]["enforcement"], "disabled")

    def test_write_verification_mismatch_is_still_failed(self):
        original = self.gh.api
        def stale_write(method, path, body=None, missing=False):
            result = original(method, path, body, missing)
            if method == "PATCH" and path == "repos/lead/demo":
                self.gh.repo["description"] = "unexpected response"
            return result
        with patch.object(self.gh, "api", side_effect=stale_write):
            _, result = self.run_flow()
        self.assertEqual(result["settings"]["status"], "failed")

    def test_legacy_protection_alone_still_queues_pr(self):
        self.s["protection"] = False
        self.run_flow()
        original = self.gh.api
        def legacy(method, path, body=None, missing=False):
            if path == "repos/lead/demo/branches/main":
                return {"protected": True}
            return original(method, path, body, missing)
        self.s["development"] = "python3 app.py"
        with patch.object(self.gh, "api", side_effect=legacy):
            _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(len(self.gh.prs), 1)

    def test_member_invitation_lost_response_is_not_repeated(self):
        self.s["members"] = ["dev"]
        self.gh.lost = ("PUT", "repos/lead/demo/collaborators/dev")
        self.run_flow()
        _, result = self.run_flow()
        self.assertEqual(result["member:dev"]["status"], "pending")
        self.assertEqual(len(self.gh.invites), 1)

    def test_lost_file_response_recovers_without_extra_write(self):
        self.gh.lost = ("PUT", "repos/lead/demo/contents/CONTRIBUTING.md")
        self.run_flow()
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(sum(c[:2] == ("PUT", "repos/lead/demo/contents/CONTRIBUTING.md") for c in self.gh.calls), 1)

    def test_unknown_private_plan_uses_actual_capability(self):
        self.gh.viewer["plan"] = None
        self.gh.rules_available = True
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(result["protection"]["status"], "applied")

    def test_unrelated_rules_permission_error_stays_failed_and_blocks_file_write(self):
        self.run_flow()
        self.s["development"] = "python3 app.py"
        original = self.gh.api
        def denied(method, path, body=None, missing=False):
            if "/rules" in path:
                raise t.APIError(403)
            return original(method, path, body, missing)
        self.gh.calls.clear()
        with patch.object(self.gh, "api", side_effect=denied):
            _, result = self.run_flow()
        self.assertEqual(result["protection"]["status"], "failed")
        self.assertTrue(any(v["status"] == "failed" for k, v in result.items() if k.startswith("file:")))
        self.assertFalse(any(c[0] == "PUT" and "/contents/" in c[1] for c in self.gh.calls))

    def test_inherited_rules_require_pr_even_when_branch_flag_is_false(self):
        self.s["protection"] = False
        self.gh.rules_available = True
        self.run_flow()
        self.gh.effective_rules = [{"type": "pull_request"}]
        self.assertFalse(self.gh.api("GET", "repos/lead/demo/branches/main")["protected"])
        self.s["development"] = "python3 app.py"
        self.gh.calls.clear()
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(len(self.gh.prs), 1)
        self.assertFalse(any(c[0] == "PUT" and "/contents/" in c[1] for c in self.gh.calls))

    def test_view_rename_response_loss_and_customization_are_preserved(self):
        self.gh.lost = "updateProjectV2View"
        self.run_flow()
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual([v["name"] for v in self.gh.views], ["Board"])
        self.gh.views[0]["name"] = "Our board"
        self.gh.calls.clear()
        _, result = self.run_flow()
        self.assertEqual(result["board_view"]["status"], "deferred")
        self.assertEqual(self.gh.views[0]["name"], "Our board")
        self.assertTrue(all(c[0] in ("GET", "GET-GRAPHQL") for c in self.gh.calls))
        _, result = self.run_flow(False)
        self.assertEqual(result["board_view"]["status"], "deferred")

    def test_later_ci_waits_for_actual_success(self):
        self.gh.viewer["plan"]["name"] = "pro"
        self.s["protection"] = False
        self.run_flow()
        self.s["ci"] = self.ci_spec()
        _, result = self.run_flow()
        self.assertEqual(result["ci"]["status"], "failed")
        self.gh.files["tests/test_app.py"] = "import unittest\n"
        _, result = self.run_flow()
        self.assertEqual(result["ci"]["status"], "deferred")
        self.gh.success()
        _, result = self.run_flow()
        self.assertEqual(result["ci"]["status"], "applied")
        self.gh.jobs[0]["conclusion"] = "skipped"
        _, result = self.run_flow()
        self.assertEqual(result["ci"]["status"], "failed")

    def test_protected_ci_uses_one_pr_and_never_weakens_rules(self):
        self.s["visibility"] = "public"
        self.run_flow()
        self.s["ci"] = self.ci_spec()
        self.gh.files["tests/test_app.py"] = "import unittest\n"
        _, result = self.run_flow()
        self.assertEqual(result["setup_pr"]["status"], "deferred")
        self.assertNotIn(".github/workflows/team-start.yml", self.gh.files)
        self.run_flow()
        self.assertEqual(len(self.gh.prs), 1)
        branch = self.gh.prs[0]["head"]
        commit = self.gh.commits[self.gh.refs[branch]]
        for item in self.gh.trees[commit["tree"]]:
            self.gh.files[item["path"]] = item["content"]
        self.gh.advance()
        self.gh.success()
        _, result = self.run_flow()
        self.no_failures(result)
        self.assertEqual(self.gh.rules[0]["rules"][-1]["type"], "required_status_checks")
        self.gh.runs[0]["conclusion"] = "failure"
        _, result = self.run_flow()
        self.assertEqual(self.gh.rules[0]["rules"][-1]["type"], "required_status_checks")

    def test_lost_pr_response_recovers(self):
        self.s["visibility"] = "public"
        self.run_flow()
        self.s["development"] = "python3 app.py"
        self.gh.lost = ("POST", "repos/lead/demo/pulls")
        self.run_flow()
        _, result = self.run_flow()
        self.assertEqual(result["setup_pr"]["status"], "deferred")
        self.assertEqual(len(self.gh.prs), 1)

    def test_actor_and_target_cannot_be_changed(self):
        runner, _ = self.run_flow()
        runner.remember("actor", 1)
        self.gh.viewer["id"] = 77
        with self.assertRaisesRegex(t.Stop, "다른 GitHub 계정"):
            self.run_flow()
        self.s["visibility"] = "public"
        with self.assertRaisesRegex(t.Stop, "visibility"):
            self.run_flow()


class InterfaceTests(unittest.TestCase):
    def test_transport_blocks_rest_and_graphql_mutations_without_subprocess(self):
        gh = t.GitHub()
        with patch.object(t.subprocess, "run") as run:
            for method, endpoint, body in [("POST", "user/repos", {}), ("PUT", "repos/o/r", {}),
                                            ("POST", "graphql", {"query": "mutation{a}"})]:
                with self.assertRaises(t.Stop):
                    gh.api(method, endpoint, body)
            run.assert_not_called()

    def test_transport_explicit_get_and_graphql_query(self):
        gh = t.GitHub()
        with patch.object(t.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"data":{"ok":true}}', '')) as run:
            gh.api("GET", "user")
            self.assertIn("GET", run.call_args.args[0])
            gh.graphql("query{viewer{login}}")
            self.assertEqual(json.loads(run.call_args.kwargs["input"])["query"], "query{viewer{login}}")

    def test_pagination_collects_all_pages(self):
        gh = t.GitHub()
        with patch.object(gh, "api", side_effect=[list(range(100)), [100]]) as api:
            self.assertEqual(len(gh.pages("repos/o/r/issues?state=all")), 101)
            self.assertIn("&per_page=100&page=2", api.call_args.args[1])

    def test_graphql_connection_paginates_and_balances_query(self):
        gh = t.GitHub()
        with patch.object(gh, "graphql", side_effect=[
            {"node": {"views": {"nodes": [{"id": "1"}], "pageInfo": {"hasNextPage": True, "endCursor": "c"}}}},
            {"node": {"views": {"nodes": [{"id": "2"}], "pageInfo": {"hasNextPage": False}}}},
        ]) as gql:
            self.assertEqual(len(gh.connection("P", "ProjectV2", "views", "id")), 2)
            query = gql.call_args.args[0]
            self.assertEqual(query.count("{"), query.count("}"))
            self.assertEqual(gql.call_args.kwargs["cursor"], "c")

    def test_graphql_scope_failure_has_actionable_redacted_message(self):
        response = json.dumps({"errors": [{"type": "INSUFFICIENT_SCOPES", "message": "do not echo server secret"}]})
        for code in (0, 1):
            with self.subTest(code=code), patch.object(t.subprocess, "run", return_value=subprocess.CompletedProcess([], code, response, "")):
                with self.assertRaises(t.APIError) as err:
                    t.GitHub().graphql("query{viewer{projectsV2(first:1){nodes{id}}}}")
                self.assertTrue(err.exception.insufficient_scopes)
                self.assertIn("gh auth refresh", str(err.exception))
                self.assertNotIn("server secret", str(err.exception))

    def test_preflight_needs_no_plan_scope(self):
        gh = FakeGitHub()
        gh.viewer["plan"] = None
        runner = t.Runner({"owner": "lead", "name": "demo", "path": "/private/tmp/unused-team-start-plan"}, gh)
        runner.preflight()
        self.assertEqual(runner.results["identity"]["status"], "applied")
        self.assertEqual([c[1] for c in gh.calls], ["user", "users/lead"])

    def test_only_explicit_rules_upgrade_response_is_unsupported(self):
        upgrade = "Upgrade to GitHub Pro or make this repository public to enable this feature."
        cases = [(403, "repos/lead/demo/rulesets", upgrade, True),
                 (403, "repos/lead/demo/rules/branches/main?per_page=100&page=1", upgrade, True),
                 (403, "user", upgrade, False),
                 (403, "repos/lead/demo/rulesets", "Resource not accessible by integration", False),
                 (403, "repos/lead/demo/rulesets", "SSO authorization required", False),
                 (429, "repos/lead/demo/rulesets", upgrade, False)]
        for status, path, message, expected in cases:
            with self.subTest(status=status, path=path, message=message):
                response = subprocess.CompletedProcess([], 1, json.dumps({"message": message}), f"HTTP {status}")
                with patch.object(t.subprocess, "run", return_value=response), self.assertRaises(t.APIError) as err:
                    t.GitHub().api("GET", path)
                self.assertEqual(err.exception.feature_unavailable, expected)
                self.assertNotIn(message, str(err.exception))

    def test_api_errors_do_not_echo_secrets(self):
        with patch.object(t.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "secret-token HTTP 403")):
            with self.assertRaises(t.APIError) as err:
                t.GitHub().api("GET", "user")
            self.assertEqual(err.exception.status, 403)
            self.assertNotIn("secret-token", str(err.exception))

    def test_plan_offline_does_not_write_target_or_call_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new"
            src = Path(tmp) / "spec.json"
            src.write_text(json.dumps({"owner": "lead", "name": "demo", "path": str(target)}))
            with patch.object(sys := t.sys, "argv", [str(SCRIPT), "plan", "--spec", str(src), "--offline"]), \
                 patch.object(t.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(t.main(), 0)
                run.assert_not_called()
            self.assertFalse(target.exists())
            self.assertFalse(json.loads(out.getvalue())["remote_mutations"])

    def test_refuses_nonempty_and_nested_git_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("user work")
            with self.assertRaises(t.Stop), t.apply_lock({"path": str(root)}):
                pass
            (root / ".git").mkdir()
            with self.assertRaises(t.Stop), t.apply_lock({"path": str(root / "child")}):
                pass

    def test_ai_is_opt_in_and_rule_defaults_differ(self):
        s = t.normalize({"owner": "lead", "name": "demo", "path": "/tmp/demo", "profile": "team"})
        self.assertEqual(s["approvals"], 1)
        self.assertNotIn("AGENTS.md", t.render(s))
        s["ai"] = True
        self.assertIn("AGENTS.md", t.render(s))
        self.assertNotIn("CODEOWNERS", t.render(s))

    def test_workflow_has_read_only_permissions_and_no_fake_test(self):
        ci = {"steps": [{"name": "Test", "run": "npm test"}], "evidence_paths": ["package.json"]}
        wf = json.loads(t.ci_workflow(ci))
        self.assertEqual(wf["permissions"], {"contents": "read"})
        self.assertEqual(wf["jobs"]["verify"]["steps"], ci["steps"])
        self.assertNotIn("pull_request_target", wf["on"])


class CheckoutTests(unittest.TestCase):
    def test_real_git_checkout_then_preserves_dirty_and_diverged_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / "source", root / "target"
            source.mkdir()
            t.command(["git", "init", "-b", "main", str(source)])
            (source / "README.md").write_text("hello")
            t.command(["git", "add", "README.md"], cwd=source)
            t.command(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                       "commit", "-m", "fixture"], cwd=source)
            expected_head = t.command(["git", "rev-parse", "HEAD"], cwd=source)
            (target / ".team-start").mkdir(parents=True)
            (target / ".team-start/state.json").write_text("{}")
            spec = {"owner": "lead", "name": "demo", "path": str(target)}
            gh = FakeGitHub()
            gh.head = expected_head
            runner = t.Runner(spec, gh, apply=True)
            original = t.command
            def local_transport(args, cwd=None, data=None):
                if "fetch" in args:
                    return original(["git", "fetch", str(source), "main:refs/remotes/origin/main"], cwd=cwd)
                return original(args, cwd=cwd, data=data)
            with patch.object(t, "command", side_effect=local_transport):
                runner.checkout()
                self.assertEqual((target / "README.md").read_text(), "hello")
                self.assertEqual(runner.results["checkout"]["status"], "applied")
                self.assertEqual(t.command(["git", "status", "--porcelain"], cwd=target), "")
                t.command(["git", "switch", "-c", "feature/work"], cwd=target)
                with self.assertRaisesRegex(t.Deferred, "로컬 브랜치"):
                    runner.checkout()
                self.assertEqual(t.command(["git", "branch", "--show-current"], cwd=target), "feature/work")
                t.command(["git", "switch", "main"], cwd=target)
                (target / "README.md").write_text("user edit")
                with self.assertRaisesRegex(t.Deferred, "로컬 변경"):
                    runner.checkout()
                self.assertEqual((target / "README.md").read_text(), "user edit")
                t.command(["git", "add", "README.md"], cwd=target)
                t.command(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                           "commit", "-m", "user change"], cwd=target)
                with self.assertRaisesRegex(t.Deferred, "사용자 커밋"):
                    runner.checkout()
                self.assertEqual((target / "README.md").read_text(), "user edit")


if __name__ == "__main__":
    unittest.main()
