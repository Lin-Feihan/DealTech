# Workflow Overview — Merger Strategy Agent

Status: **Framework only with business workflow diagram integrated**.

The user-provided workflow image defines a merger case framework agent for merger transactions. The agent starts from a user intent such as:

> I am evaluating a potential merger between [Buyer] and [Target]. Can you analyze whether this deal makes strategic and financial sense?

The agent then clarifies missing information, plans a multi-step merger case workflow, performs iterative tool use, and generates a `Merger Case Memo`.

Current repository status remains **Framework only** because no real merger case input, source registry, evidence table, or claim-to-evidence map has been provided yet. The workflow is therefore implemented as a runnable scaffold that honestly outputs framework-only status instead of fabricating a merger case-run.

## Workflow architecture from the image

1. **Intent** — user asks for merger analysis between Buyer and Target.
2. **Clarification / Planning** — LLM clarifies missing details and builds a multi-step plan.
3. **Merger Strategy Agent execution** — agent works through 15 memo modules.
4. **Offline analysis** — financial model, valuation, scenario and sensitivity analysis.
5. **Online retrieval** — SEC filings, company corpus, industry data, market data, news, equity research.
6. **Extended tool use** — API search, browser, precedent/comparable datasets, contract/report corpus.
7. **Output** — structured merger case memo with recommendations and caveats.
