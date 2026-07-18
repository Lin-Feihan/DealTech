# v0.1.0-rc1 release checklist

## Release contract

- [x] The complete recorded A → B → C pipeline executes under one case ID and run ID.
- [x] All 17 named buyer-side M&A modules execute.
- [x] Gate A, Gate B and Gate C execute with append-only histories.
- [x] Gate failures use Gap Diagnosis → Memory Update → Loop Controller → targeted Re-plan.
- [x] A → B and A/B → C bundles use repository-relative references and SHA-256 hashes.
- [x] PCE, ER/BRB, calculation replay and Human Review retain separate authority boundaries.
- [x] Final reporting, cross-block consistency and delivery verification execute.
- [x] Decision State and delivery permission are documented as decision support, not transaction approval.

## Package, commands and release content

- [x] `pyproject.toml` parses and exposes version `0.1.0rc1`.
- [x] `python -m pip install -e . --no-deps` succeeds in the existing environment.
- [x] Console and module entry points resolve.
- [x] Recorded case validation, `FULL_PIPELINE`, run resume and Human Review resume are documented.
- [x] `.env.example` contains names only and is not excluded by `.gitignore`.
- [x] Source, prompts, schemas, tests, public fixtures, the blank teacher template and curated `sample_output/` are publishable.
- [x] Unrestricted outputs, credentials, raw live responses, caches, local state, confidential local attachments and temporary audit notes are excluded.
- [x] Curated `sample_output/` contains exactly nine consistent artifacts.

## Local verification

- [x] Python compilation succeeded.
- [x] RC1 targeted tests: 8 passed.
- [x] All new-agent tests: 244 passed.
- [x] Affected Acquisition Strategy tests: 12 passed.
- [x] Recorded full-pipeline smoke test and case readiness check succeeded.
- [x] Release verification script succeeded.
- [x] Segmented repository verification completed: 321 passed and one known pre-existing test failed.
- [x] Protected-path test side effects were restored; protected paths have no diff.
- [x] CI workflow is `LOCALLY VALIDATED, NOT YET RUN ON GITHUB ACTIONS`.

## Explicitly pending

- [ ] Paid live end-to-end validation; not authorized or performed.
- [ ] GitHub Actions execution; impossible until the workflow is pushed.
- [ ] Repository-owner license decision. No license is present; Apache-2.0 is recommended.
- [ ] Owner acceptance of the known unrelated repository test failure.
- [ ] Commit, push, tag, release and pull request; intentionally not performed.

Final audit result: `READY_TO_COMMIT_WITH_DOCUMENTED_LIMITATIONS`.
