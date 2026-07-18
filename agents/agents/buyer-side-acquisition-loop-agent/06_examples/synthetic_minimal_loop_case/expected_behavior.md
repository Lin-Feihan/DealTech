# Expected behavior: synthetic minimal loop case

This controlled case demonstrates one bounded repair loop.

1. Iteration 1 evaluates the **Strategic Thesis Gate**.
2. **Buyer Strategic Need**, **Strategic Rationale**, **Target Attractiveness**, and
   **Industry / Competitive Position** are explicit, but the **Strategic Fit** claim
   has no admissible evidence for **Target Capability & Business Quality**.
3. PCE returns `Not Certified`. Gate A separately returns
   `FAIL_RESEARCH_GAP`.
4. Gap Diagnosis creates one `EVIDENCE_MISSING` gap.
5. The Loop Controller routes only to **Target Capability & Business Quality**.
6. The re-planner creates one focused research question. The controlled researcher
   step appends one Source and one Evidence record; it does not replace the original
   missing-evidence record.
7. PCE returns `Certified` for the repaired claim. Gate A separately returns `PASS`.
8. The loop stops after exactly two iterations, within its budget.

No full-deal decision or acquisition strategy report is produced.
