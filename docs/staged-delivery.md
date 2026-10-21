# Staged Delivery Plan

This plan is the execution order and acceptance contract; it is not a statement of completed implementation. Stable stage IDs are defined in project/stages.yaml and dependencies in project/dependencies.yaml.

## Delivery flow

S00 Environment and repository discovery
→ S01 Requirements, schemas and contracts
→ S02 Hardware and firmware foundation
→ S03 CAN core and transport
→ Parallel branches after contracts stabilize:
- S04 Browser engineering UI
- S05 Persistence and export
Then:
- S06 Identifier discovery and signal analysis (needs S01, S03, S05)
- S07 Gated raw TX and diagnostic framework (needs S01, S03, S06)
- S08 Virtual CAN lab (needs S01, S03, S04)
- S09 Python Proteus generator (needs S02, S08)
→ S10 Integration and end-to-end workflows
→ S11 Hardening and regression
→ S12 Packaging and evidence handoff

## Work protocol per stage

1. Read acceptance criteria and dependencies; inspect the current repository and existing interfaces before editing.
2. Write or refine small contracts/schema needed for the stage before expanding implementation.
3. Implement the smallest complete vertical slice; add unit and contract tests as the code is written.
4. Run focused tests, then stage-level integration tests. Preserve concise failure output with exact path/line and command.
5. Review the complete diff for compatibility, safety states, untracked/generated files, and unexpected scope.
6. Update the stage report, progress ledger, and requirement traceability with evidence and unresolved gaps.
7. Mark complete only after every acceptance criterion passes. An unavailable physical tool or vehicle must be recorded as a blocker, not silently waived.

## Stage summaries

| Stage | Outcome | Primary evidence |
|---|---|---|
| S00 | Toolchain, repository, hardware, Proteus and risks inventoried | Environment report and decisions |
| S01 | Versioned frame/session/analysis/TX contracts are stable | Schema and contract tests |
| S02 | ESP32 + TJA1051T/3 firmware/hardware foundation is reproducible | Build output, pin review, schematic source |
| S03 | Frame capture, state reporting, transport and gated TX core work | Driver tests, loopback/mocks, fault tests |
| S04 | Main browser workbench works on synthetic and connected sources | UI journey and accessibility tests |
| S05 | Sessions persist and export/import without raw-data mutation | Round-trip and migration tests |
| S06 | Analysis ranks and records evidence-based candidates | Known-answer datasets and provenance |
| S07 | Active transmission/diagnostic framework has guardrails | Simulation tests, TX audit and interlock tests |
| S08 | Virtual CAN scenarios are deterministic and interactive | Scenario fixtures and repeatable results |
| S09 | Python generator creates native Proteus artifacts | Generator tests, manifest, tool validation status |
| S10 | End-to-end workflows join all modules without safety bypass | E2E and boundary tests |
| S11 | Faults, load, regressions and recovery behavior are measured | Test/fault/performance reports |
| S12 | Setup and final evidence package is reproducible | Traceability audit and final handoff |

## Token-efficient agent workflow

- Reference Sxx and REQ-xxx IDs in task requests instead of repeating the whole product definition.
- Load only directly relevant specification files and code symbols; keep CLAUDE.md as a compact routing contract.
- Use DAG-ready parallel work only for independent module owners and agreed interfaces.
- Run targeted tests before the full suite; expand logs only where a concrete failure requires it.
- Store decisions, file ownership, commands, results, and next-ready DAG nodes in durable reports.
- Do not trade away scope, safety, tests, or proof to lower token use.
