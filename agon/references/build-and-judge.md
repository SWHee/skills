# Build and judge

## Rubric map

For the selected award, map every official criterion to:

| Criterion | Feature | Observable proof | Threshold | Demo moment |
| --- | --- | --- | --- | --- |
| Official wording and locator | What the product does | What a reviewer can inspect or replay | Pass/fail or measured target | Where it appears in the demo |

Keep main-award and sponsor-prize rubrics in separate dossiers or make the secondary plan explicit in the brief. Never transfer weights between them. When official criteria have no weights, record `unpublished`; optimize for proving every criterion without inventing a score model.

## AI contract

State separately how AI assists development and how it behaves inside the product. For product AI, record inputs, outputs, tool permissions, validation, retries/timeouts, rate limits, and safe fallback. Untrusted input never gains tool authority. Confirm access to the named provider/model and the rights to data and model output. Include privacy and required disclosure.

Choose a small representative evaluation set with relevant failure or adversarial inputs. Keep prompt-development cases separate from held-out cases; do not tune on the hold-out or select only favorable outputs. Compare with a non-AI baseline when that clarifies the claimed gain. Prioritize task success, groundedness, and tool correctness over prose quality. No universal sample size, RAG, agent, or fine-tuning requirement exists.

Report the exact denominator, environment, model/prompt/data version, retry policy, latency distribution, measured cost, and limitations. A recorded or mocked output may demonstrate presentation but cannot stand in for live compliance. If the event permits AI coding but does not require product AI, do not add inference merely for appearance.

## Delivery contract

Bound the MVP, exclusions, architecture, owned tasks, and acceptance checks. Record the requested model route. `sol/medium` is a requested delegation default, not proof that a runtime can provide it; `parent` is a portable explicit option. If a named route is unavailable, retain planning and block that lane until the user explicitly selects an alternative.

Use a timezone-aware deadline. Estimate implementation, verification, and submission separately, then reserve the latter two. Include reproducible environment and demo steps, failure fallback, video/public-access needs, draft submission fields, attribution, license, and AI disclosure. List each unresolved question with an owner and next action.

## Run, verify, package

When the gate is ready and work is authorized, implement without seeking another approval. Resolve a cheap central feasibility uncertainty before changing the product around an untested replacement. A permitted spike answers one bounded question; it does not silently start the build. During a rules-defined planning-only period, keep all executable work out.

Run checks appropriate to the actual change, the AI evaluation, and the complete demo route. Before packaging, inspect the artifact without builder explanations against the applicable rubric and runnable evidence. Correct the largest eligibility, demo, or claim failure first. Use no more than two focused repair cycles by default, stop sooner if the time reserve is at risk, and do not repeat an unchanged failure.

Describe review honestly: self-review, independent review, or simulated rubric review. None predicts a judge score or winning. Package the runnable artifact, replay steps, evidence, attribution/disclosure, and remaining actions. Submission is a separate external action. Perform it only when action-specific authorization already exists, and claim submission only from a real receipt.

## Common failure → correction

| Failure | Correction |
| --- | --- |
| Broad permission treated as evidence | Keep rules, rights, need, and feasibility unresolved until evidence resolves them. |
| Synthetic data treated as problem proof | Use it for safe testing while separately establishing user and domain evidence. |
| Assumptions labeled, then implementation starts | Convert central assumptions into bounded checks before product work. |
| New rule invalidates architecture | Reopen affected readiness fields and test the replacement before editing around it. |
| Sponsor weights applied to a main prize | Use only the selected award's official rubric. |
| Held-out cases reused during tuning | Freeze the hold-out and report all its outcomes with the denominator. |
| Gate says READY after files change | Re-fingerprint, review the changed evidence, then record a fresh review. |
