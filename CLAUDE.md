# Civic-Workbench agent contract

## Mission
Implement this independent project according to docs/master-spec.md, project/requirements.yaml, project/stages.yaml, and project/constraints.yaml. The unrelated build-a-web-page-for-ios project is not a code or structure dependency.

## Execution protocol
1. Read this file, project/progress.json, project/dependencies.yaml, and only the stage-specific files needed for the assigned work.
2. Follow the dependency DAG. Work on independent ready nodes in parallel only when interface contracts are stable.
3. Pick one stage or a small set of dependency-compatible tasks. Implement, test, inspect diffs, and produce evidence in the same pass.
4. Update project/progress.json, stage report(s), and traceability records whenever status changes. Never mark a requirement or stage complete without evidence.
5. Report only verified facts. Separate implemented, unit-tested, simulation-tested, CAD/tool-validated, bench-tested, and physically validated states.

## Token and context budget
- Treat stable IDs as references; do not restate the master specification in every task.
- Load detailed files on demand. Use symbol/search tools before reading large unrelated files.
- Run focused tests first; return concise failure excerpts and exact file/line references. Expand logs only to diagnose a concrete failure.
- Persist decisions and checkpoints in repository files instead of relying on chat history.
- Use subagents only for bounded, independent tasks with explicit inputs, outputs, and file ownership; otherwise coordination costs may exceed savings.
- Preserve clear naming and evidence. Do not use cryptic abbreviations that increase rework.
- Do not skip acceptance criteria to save tokens. Token efficiency must not reduce scope, correctness, safety, tests, or traceability.

## Contract and verification entry points
- Versioned data contracts live in `schemas/v1/`; the logical REST interface is `contracts/openapi.yaml`; semantics are enforced by `src/civic_workbench/contracts.py`.
- Run contract tests using `make test-contracts` or `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
- A valid TX request is not an authorization to transmit. Host policy and firmware/hardware gates remain independent; simulator state can never authorize physical TX.

## Non-negotiable technical rules
- Hardware is the original ESP32 + integrated TWAI + NXP TJA1051T/3 SO8. Do not silently substitute a board, transceiver, OBD-II adapter, ELM device, or PID abstraction.
- Support direct-CAN frame observation and a properly gated raw-frame transmission path. Do not reduce the product to a receive-only logger.
- Boot into a passive/listen-only state with hardware-enforced TX inhibit. Active transmission needs explicit software arming, physical interlock, visible state, bounded rate, audit logging, and abort.
- Never invent vehicle IDs, signals, scales, timings, ECU responses, diagnostic support, or acceptance evidence.
- Keep raw observations immutable; store decoded/candidate interpretations separately with source, confidence, and validation state.
- Implement simulation before risky live-bus workflows. Use synthetic/documented traces when no validated vehicle capture exists.
- Generate Proteus artifacts using a Python-based generator. Produce a native, importable schematic/project and validate it in the installed/official toolchain when available; do not substitute a hand-drawn image for the native artifact.
- No user hardware work is claimed as complete until the user supplies validation evidence.

## Completion report
For each stage give requirement IDs; changed paths; commands/tests executed and results; simulation/hardware boundary; unresolved risks; and next DAG nodes. Keep output concise and link durable evidence.
