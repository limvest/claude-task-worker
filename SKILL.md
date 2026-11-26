---
name: claude-task-worker
description: Delegate substantial coding, test, or analysis work to the locally authenticated Claude Code CLI as one bounded task per fresh session, without project or conversation context. Use when the user wants Claude as a worker or requests nocontext delegation. Codex retains the full project context, decomposition, review, and integration; Claude receives only the current task contract and necessary inputs. Skip trivial edits or tasks requiring unavailable shared state.
---

# Claude task worker

Codex owns the full project context, task selection, evidence, review and integration. Claude is a fresh, single-task worker, not a second project owner. Optimize both context volume and useful progress; more workers or tests alone are not progress.

## Required execution rules

1. From the first dispatch, use a fresh session, exactly one bounded task, and only its indispensable inputs. Keep the full project and conversation context with Codex.
2. At the first observable evidence that an answering model differs from the requested model, stop that worker and record the mismatch. Reject its output, pause dependent dispatch/integration, and divide the work into smaller pieces , make it have lesser context ,and retry to same model. if the answering model differs, breakdown the task into smaller portion, eliminating more context. do not pause goal.
Unrelated running tasks need not be terminated.

## Nocontext single-task delegation

**Nocontext means no inherited project or conversation context.** It does not mean withholding the inputs, contracts, or accurate purpose necessary to do the assigned work. Keep material intent and provenance truthful; never strip context to evade safeguards.

- Codex alone maintains the overall objective, user conversation, project history, architecture decisions, work queue, dependencies, earlier reports, and final synthesis. Do not send this orchestration context to Claude, even as a compressed handoff or a link to the original chat.
- Give each invocation exactly one independently reviewable task, with one completion condition. For example, ask for the execution order of a specified callback, not an investigation of the whole feature plus implementation and a rollout plan. Several files or focused verification may serve the same task; unrelated deliverables require separate packets.
- Supply only the current task contract: action, owned output, indispensable source/data and caller/type contracts, relevant constraints, and acceptance condition. Include a brief purpose only when it changes correct execution or is needed to keep the task truthful. Do not attach general background merely because it is available.
- Start a fresh isolated session for every task and correction. Codex reviews the result and extracts the exact missing symbol, interface, defect, or evidence for the next packet. Do not resume the worker, forward its previous report, or ask it to reconstruct the project from other files. If an earlier finding is indispensable, state only that specific verified contract with its provenance.
- Keep the worker local to its assignment: return the requested artifact and precise unresolved inputs. Codex decides the next task, conducts broader research, and combines results. Parallel workers may each have one independent task; this rule does not require serial execution.

Use a short TASK.md shaped around this contract (omit inapplicable fields):

```text
Task: one concrete action and completion condition.
Inputs: explicit file allowlist; why each input is necessary.
Output/ownership: exact artifact or editable files.
Constraints: only those affecting this task; brief accurate purpose if needed.
Acceptance: one relevant check, or source citations for analysis-only work.
Missing inputs: name the exact missing contract; do not guess or broaden scope.
```

Before dispatch, remove every paragraph or file that serves only to explain the wider project. Confirm the packet is sufficient for this one task without hidden dependencies. Fresh-session flags prevent chat reuse; they do not make an oversized handoff into nocontext delegation.

## Build the smallest sufficient packet

- Assign one owner per file set. Parallelize independent work; give shared foundations one owner and integrate consumers after the interface is available. Use the user-requested parallelism, limited by independent ready work and observed CLI/provider capacity. Claude CLI processes are separate from Codex subagent slots; do not apply the Codex slot count to CLI dispatch.
- Create a fresh packet from an explicit file allowlist. Include `TASK.md`, the changed function/class, required caller/type contracts, relevant existing tests, and a verification entrypoint only when the task needs one. Explain each supporting file's purpose briefly in TASK.md. Do not copy the repository or entire preceding packet for a correction.
- For follow-ups, construct a new allowlisted packet containing only the current affected code, relevant regression tests, the specific defect, and newly needed evidence. Leave previous reports, transcripts, unrelated sources and superseded implementations with Codex.
- Slice evidence by the actual dependency: relevant symbol rows instead of a whole import catalog; required function and initializer ranges instead of entire modules. Retain source hashes, original line numbers and enough surrounding flow to prevent misleading excerpts. If a larger unit is essential, state why; never truncate away necessary behavior just to hit a size target.
- Before dispatch, record the single task and explicit file allowlist, and review file count, total bytes and the largest files. A small correction should normally fit in a handful of files. Tens of files or hundreds of KB require checking for reusable catalogs, duplicated evidence or a task that should be split. Bytes measure packet size, not tokens actually read.
- Keep TASK.md within the single-task contract above. Do not append the overall goal, full handoff, general policies, or unrelated platform/account/licensing discussion. Necessary behavioral constraints and provenance belong in the packet; project narration does not.
- Do not send full chat history, credentials, live account data, raw dumps or unrelated settings. Do not replace original behavior with fixtures, guessed defaults, identity transformations or dummy bases and call it recovered. Distinguish confirmed, inferred and unresolved behavior.

## Execute

Use the installed authenticated CLI directly; no new wrapper package or global CLI configuration is needed. Check auth once without printing identity fields; sandbox-hidden keychain access may require scoped escalation. Never extract credentials.

**Default: `--model claude-opus-5-5 --effort medium`.** Honor a newer explicit user preference. Do not silently increase effort or change models after a refusal. Use an explicit canonical model ID, not an alias. A requested model is not proof of the model that answered: provider-side switching may still occur.

```bash
python3 SKILL_DIR/scripts/dispatch.py run --packet /absolute/packet-a --packet /absolute/packet-b --jobs 3
python3 SKILL_DIR/scripts/dispatch.py status --batch /absolute/batch-path
```

The helper copies the prepared packet into an isolated directory and starts a fresh `claude -p --no-session-persistence --restricted` invocation with explicit tool permissions. Do not resume or continue previous worker chats. Preserve approval boundaries; do not add bypass flags or tools to circumvent a refusal.

### Model identity guard

The dispatcher reads `stream-json` assistant/message-start model fields while the process runs and checks the final `modelUsage` keys as well. A system/init model field describes configuration, not proof of the answering model. Any observed answering-model mismatch terminates the worker process group, records `state: model_mismatch`, requested/observed models, detection event/time, and `output_accepted: false`, and exits unsuccessfully. Keep its artifacts isolated; do not integrate them or release dependent tasks. If answering-model metadata is absent, record `model_unverified` and withhold acceptance.

Detection is limited to what the CLI exposes: a route disclosed only in the final result can only be rejected at completion. Do not claim to prevent a hidden provider switch before it is reported. Rerouting alone does not prove excess context or identify its cause. Preserve any reported `safety_stops`; redispatch a stripped-down request 

## Continuous orchestration

- Keep a compact work queue with task ID, owned files, dependencies, ready/running/review/done/blocked state, live handle and next action. Codex owns this context; each Claude session receives only its packet.
- Decompose independent work ahead of dispatch and keep the next ready packets prepared. Dispatch ready work immediately; do not wait for the entire current batch to finish before starting another independent batch.
- While Claude computes, keep doing useful orchestration: prepare the next packets, extract missing evidence, resolve dependency contracts, briefly review completed deltas, integrate completed modules, run batched acceptance at integration points, and publish within existing authorization. Delegate substantial implementation and analysis instead of repeating the worker's reasoning in Codex.
- Process results individually as they arrive. Release dependent tasks after a brief interface and scope check; do not require a separate full test pass for every prerequisite; keep unrelated workers running. Do not let repeated status polling or reporting replace preparing and dispatching work.
- Wait only when no independent preparation, review, integration or ready dispatch remains. Before waiting, inspect the queue for the next useful action. Poll a specific live handle; an observation timeout is not terminal failure. Never restart a quiet worker or create duplicate owners just to fill capacity.
- Increase concurrency when independent packets are ready and capacity permits. On real resource or rate-limit failures, reduce dispatch pressure and preserve running work. Do not create speculative busywork, repeat unchanged blockers or consume tokens solely to keep workers occupied.
- Preserve live handles and queue state across turns. Do not end an active work turn solely because a worker is running when useful independent work remains. Honor explicit pause/stop requests; never promise continuous execution beyond actual tool/session availability.
- Keep user-facing progress brief and respect requests for fewer reports within host requirements. Record details in the work ledger rather than repeatedly loading or narrating them.

## Speed-first validation

- Prioritize useful implementation and integration over repeated checking. Workers should finish their owned changes and return them promptly; do not make each packet run the entire inherited test suite.
- Choose a small check only when needed to establish that the worker's deliverable is usable (for example syntax, one changed behavior, or an interface contract). Analysis-only packets have no test command; never run a nonexistent harness.
- Integrate independent returned changes into a staging copy, preserving originals. At a meaningful integration point, run the relevant existing suite once across the combined result. Correct actual failures there and rerun only affected checks; broaden only for a demonstrated cross-module concern.
- Do not repeat a worker's unchanged successful checks in Codex by default. Reuse its receipt, exact command and result. Re-run when integration changes the tested context, the reported result is unreliable, or a concrete defect requires verification.
- Do not add a separate review worker or a new test file for every change. Add targeted tests only for substantial new behavior, a real regression or a necessary unresolved contract; avoid tests that merely assert wording, evidence metadata or implementation structure.
- Keep source-fidelity limits explicit even when deferring validation. Unchecked integration is pending validation, not recovered or verified. Preserve required repository checks and proportionate checks before publishing or irreversible actions; speed does not authorize skipping them.

## Review and integrate

- Read compact receipts, RESULT.md and relevant diffs, not full transcripts or unchanged evidence. Ask for changed files, exact tests actually run and unresolved dependencies; avoid repeated narrative reports.
- Receipts record requested model/effort, actual `modelUsage` keys, `safety_stops`, packet size and permission denials. Report deviations accurately. Safety-stop counts support an intervention finding but do not identify the exact triggering phrase. Do not assume overload or blame a keyword without evidence. Do not disable safeguards or disguise a task to prevent switching.
- Review the changed behavior, source fidelity and ownership briefly; inspect test integrity when tests changed. Apply the batched validation policy above instead of duplicating checks. A denied command is not a passed test; a passing fixture is not product equivalence. Reused functions and tests are not new recovery.
- Integrate only scoped accepted changes; preserve originals. Save hashes, accepted/rejected changes, verified tests and unresolved inputs. Publish only within existing authorization, excluding private logs and unrelated data.
- When blocked, request only the missing evidence or contract. Do not repeatedly redispatch an unchanged blocker, repeat the entire investigation, or inflate completion counts. Give one meaningful batch report rather than frequent status-only turns.
