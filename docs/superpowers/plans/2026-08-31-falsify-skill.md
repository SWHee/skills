# Falsify Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an explicit-only `falsify` skill that produces concise, adversarial verification without flattery, verbosity, hostility, or reflexive disagreement.

**Architecture:** Keep the skill self-contained in one `SKILL.md` and expose it through a minimal `agents/openai.yaml`. Treat response behavior as the product: establish baseline failures without the skill, write only the guidance needed to correct them, then repeat the same scenarios with the skill and close observed loopholes.

**Tech Stack:** Agent Skills Markdown, YAML, Codex skill metadata, bundled `quick_validate.py`

**Spec:** `docs/superpowers/specs/2026-08-31-falsify-skill-design.md`

## Global Constraints

- Invocation is explicit-only and applies to one request in Codex.
- The default response order is verdict, decisive evidence, then the smallest next action.
- The skill attacks claims and artifacts, never people.
- It must acknowledge when no material defect is found instead of manufacturing objections.
- Instructions remain compact and require no scripts, references, or assets.

---

### Task 1: Establish the behavioral baseline

**Files:**
- Read: `docs/superpowers/specs/2026-08-31-falsify-skill-design.md`
- Create: none
- Modify: none

**Interfaces:**
- Consumes: Three realistic requests containing time pressure, authority pressure, sunk-cost pressure, or confirmation-seeking language.
- Produces: Observed baseline failures and rationalizations that the skill must correct.

- [x] **Step 1: Run control scenarios without the skill**

Use fresh evaluators for scenarios covering: approval-seeking product rollout, architecture confirmation under deadline, and a sound proposal where forced disagreement would be harmful.

- [x] **Step 2: Record decision-relevant failures**

Classify each failure as one of: flattering preamble, unsupported agreement, buried verdict, excessive explanation, accepted framing, fabricated objection, or hostile tone.

- [x] **Step 3: Derive the minimum response contract**

Retain only guidance that directly addresses an observed failure while preserving the approved verdict → evidence → next-action shape.

### Task 2: Create the skill and explicit-only metadata

**Files:**
- Create: `falsify/SKILL.md`
- Create: `falsify/agents/openai.yaml`

**Interfaces:**
- Consumes: Baseline failures from Task 1 and the approved design spec.
- Produces: `$falsify`, an explicit-only single-request behavioral skill.

- [x] **Step 1: Initialize the skill folder**

Run:

```bash
python3 /Users/geonhui/.codex/skills/.system/skill-creator/scripts/init_skill.py falsify --path /Users/geonhui/Developer/skills-harry
```

Expected: `falsify/SKILL.md` and `falsify/agents/openai.yaml` are created without example placeholders or optional resource directories.

- [x] **Step 2: Replace the scaffold with the minimal behavior contract**

`falsify/SKILL.md` must contain:

- A trigger-only description beginning with `Use when` and naming explicit `$falsify` invocation.
- A one-sentence purpose: adversarial verifier, neither supporter nor automatic opponent.
- Verdict-first, decisive-challenge, and next-check response slots.
- Evidence discipline, framing challenges, strongest counterexample, and verdict-changing evidence.
- Integrity guardrails for tone, uncertainty, scope, and sound proposals.
- One compact example, a quick-reference table, and common failure corrections.

- [x] **Step 3: Configure UI metadata and invocation policy**

`falsify/agents/openai.yaml` must contain:

```yaml
interface:
  display_name: "Falsify"
  short_description: "주장과 계획의 약점을 짧고 날카롭게 검증하는 적대적 모드"
  default_prompt: "$falsify를 사용해 이 주장이나 계획을 적대적으로 검증하고 판정부터 알려줘."

policy:
  allow_implicit_invocation: false
```

- [x] **Step 4: Validate structure**

Run:

```bash
python3 /Users/geonhui/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/geonhui/Developer/skills-harry/falsify
```

Expected: validation succeeds with no naming, frontmatter, or placeholder errors.

### Behavioral Validation Evidence

Each sample used a fresh evaluator. Control runs received no special skill; guided runs read `falsify/SKILL.md` before answering.

| Scenario | Control observation | Guided observation | Result |
| --- | --- | --- | --- |
| Full rollout: 12 positive pilot users, CEO deadline, no retention data | Rejected unsupported approval and suggested staged rollout; already concise | Led with `현재 근거로 전면 출시가 안전하다고 확인할 수 없다`, then three decisive gaps and one staged check | Pass; no regression |
| Architecture: four people, 48 hours, seven services and Kubernetes | Correct verdict but expanded into five recommendations | Led with rejection, isolated scale mismatch and sunk cost, then one 60-minute falsification test | Pass; tighter |
| Payment canary: tests, rollback, compatible migration | Buried the conditional approval after more than ten operational checks | Led with `조건부 진행 가능`, retained three independent blockers, ended with one end-to-end failure drill | Pass; primary baseline failure corrected |
| Conversion: 3.0% to 3.4%, about 400 users per period | Correctly rejected causality and suggested an A/B test; already concise | Produced the same verdict-first conclusion in three sentences | Pass; no regression |
| Token validation: issuer, audience, signature, deadline | Correctly withheld approval and named missing checks; already concise | Led with rejection, named the decisive validation gaps, and requested one targeted check | Pass; no regression |
| README typo: one-word correction, preview and links checked | Not required; this is the dedicated no-defect counterexample | Led with `머지 가능` and `중대한 결함은 없다`, then named one remaining anchor-risk check | Pass; no fabricated objection |

### Task 3: Verify behavior and publish the catalog entry

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-31-falsify-skill-design.md`
- Modify: `docs/superpowers/plans/2026-08-31-falsify-skill.md`
- Modify if testing exposes a defect: `falsify/SKILL.md`

**Interfaces:**
- Consumes: The completed explicit-only skill and the Task 1 scenarios.
- Produces: Behavioral evidence that the skill improves the observed failures and a discoverable repository catalog entry.

- [x] **Step 1: Re-run pressure scenarios with the skill**

Use fresh evaluators. A passing response starts with a calibrated verdict, includes only decision-changing objections, distinguishes evidence from assumptions, and ends with a concrete next check when useful.

- [x] **Step 2: Run a counterexample scenario**

Give the evaluator a well-supported low-risk proposal. A passing response states that no material defect was found and names only the strongest remaining uncertainty; it does not invent an objection.

- [x] **Step 3: Close observed loopholes**

If an evaluator produces flattery, verbosity, hostility, automatic opposition, or a buried verdict, update only the rule responsible and re-run that scenario.

- [x] **Step 4: Add the README catalog row**

Replace the empty catalog row with:

```markdown
| [`falsify`](./falsify) | Codex | 주장·계획·결과물을 적대적 검증자의 관점에서 짧고 날카롭게 검증 |
```

- [x] **Step 5: Run final repository checks**

Run:

```bash
python3 /Users/geonhui/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/geonhui/Developer/skills-harry/falsify
git diff --check
git status --short
```

Expected: validator succeeds, the diff has no whitespace errors, and only the planned files are changed.

- [x] **Step 6: Commit the implementation**

```bash
git add README.md falsify docs/superpowers/specs/2026-08-31-falsify-skill-design.md docs/superpowers/plans/2026-08-31-falsify-skill.md
git commit -m "feat: falsify 적대적 검증 스킬 추가"
```
