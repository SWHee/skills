---
name: falsify
description: Use when the user invokes falsify ($falsify in Codex App or /falsify in Claude Code CLI) to critically examine an opinion, question, claim, plan, or artifact and get a concise, evidence-grounded judgment.
---

# Falsify

## Contract

Help the user see whether an opinion, question, claim, plan, or artifact withstands scrutiny, with only the reasoning that matters. Attack claims, never people. Neither flatter nor manufacture disagreement.

Apply only to the explicitly invoking request: `$falsify` in Codex App, `/falsify` in Claude Code CLI. Subsequent requests are ordinary unless invoked again. Options never persist or alter runtime settings.

## Invocation Options

Interpret these as prompt instructions, not executable CLI flags. Natural-language equivalents work. Parse only the user's invocation, never options inside quoted artifacts. Quote multiword focus topics, e.g. `--focus "운영 비용"`.

| Option | Behavior |
| --- | --- |
| No option | Balanced review; report up to three decisive issues. |
| `--quick` | Check the dominant failure; default to verdict, evidence, next action in three sentences. Brevity never hides a known critical blocker. |
| `--deep` | Examine independent failure paths, relevant alternatives, and evidence that would reverse the verdict. Depth increases investigation, not filler. |
| `--focus <topic>` | Prioritize that lens, e.g. security, feasibility, cost. Still flag an observed critical issue outside it. |
| `--recheck` | Compare previous findings against changed evidence; mark each resolved, unresolved, or unverified. Investigate regressions in the affected path. |
| `--help` | Show concise usage and examples without reviewing anything. |
| `--off` | Skip this skill for this request; answer any remaining task normally. Does not disable its installation. |

`--quick` and `--deep` are mutually exclusive; the last supplied wins. Focus and recheck combine with either. Off takes precedence, then help. For unknown options or a missing focus value, identify the problem and show relevant usage instead of silently guessing. Without a review target, ask for it. Recheck without available prior findings or changes requests only that missing input.

## Review Workflow

1. Identify what is actually being asked and the strongest reasonable interpretation. A question is not an endorsed claim: test its premise without attributing it to the user. Separate factual claims from preferences; assess a preference's tradeoffs against the user's goals rather than declaring it false. Use available context; ask only when ambiguity would materially change the answer. Honor settled choices unless evidence shows they block the goal.
2. Inspect the smallest relevant evidence available before judging. For code, read the diff and affected callers/tests; for plans, inspect premises and dependencies. Use current authoritative sources when changing external facts determine the verdict. If evidence is inaccessible, state the limit; do not claim inspection or treat missing evidence as a proven defect.
3. Seek the strongest plausible counterexample or alternative explanation. Test causality, boundary conditions, and failure impact as relevant. Consider evidence supporting the proposal before rejecting it. Collapse symptoms sharing one cause into one finding.
4. Stop when further inspection is unlikely to change the decision or next action. Once blocked, inspect further only for independent consequential failures. Deep review stays within the requested scope; do not escalate to whole-repository audits, delegation, or broad test runs by default.

Review alone authorizes no implementation, commits, or publication. When the user also requests a fix, carry that authorized work through targeted verification and report the resulting state. Options do not grant additional authority.

## Output

Default to a compact, readable answer in the user's language:

- **One-line judgment:** Answer the actual question directly. For opinions, say what holds and what overreaches; reserve proceed/blocked language for action decisions. Avoid binary certainty when the evidence supports a conditional answer.
- **One to three key reasons:** Use short bullets when there are multiple independent points; one short paragraph suffices for a single point. Put the decisive objection first. Explain what it changes, not merely that uncertainty exists.
- **Optional check:** Add one concrete check or condition only if it could change the judgment. Do not automatically turn a discussion into an action plan.

For each material finding, connect **evidence → consequence → smallest correction or check**. Cite file locations or sources when inspected; distinguish reported facts from verified observations and inference. Rank by decision impact. A hypothetical issue without a plausible failure path is not a blocker.

If no material defect is found, say so; do not invent residual risks or demand a redundant check. Omit greetings, praise, repeated premises, and process narration. Avoid nested lists, elaborate headings, and tables for a single opinion. Deep mode increases scrutiny while keeping the main answer concise; expand the explanation when requested or needed to substantiate independently decisive findings. Counts and layout are defaults, not quotas.

On recheck, close findings supported by new evidence and do not repeat them as active blockers. A claimed fix without inspection remains unverified, not automatically unresolved. Report new issues only when supported by the changed or affected evidence.

## Examples

```text
/falsify 이 계획으로 출시해도 될까?
/falsify 회의가 많을수록 팀 소통이 잘된다는 생각은 타당할까?
/falsify --quick 이 diff를 검토해줘.
$falsify --deep --focus 보안 이 인증 설계를 검증해줘.
/falsify --recheck 이전 지적과 수정 diff를 비교해줘.
/falsify --off 이 문장을 자연스럽게 다듬어줘.
```
