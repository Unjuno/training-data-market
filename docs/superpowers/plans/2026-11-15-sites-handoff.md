# Sites handoff implementation plan

**Goal:** Supply the approved v0.4 design and a verified static UI to the newly created public repository, ready for ChatGPT Sites to read.
**Architecture:** Preserve the supplied vanilla HTML/CSS/JavaScript interface. This delivery is a static demo, not a deployed shared-learning system. Keep ML and server-side acceptance items explicit rather than simulating success.
**Tech Stack:** Browser ES modules; Node.js 22 for build/tests; no runtime dependencies.
**Spec:** docs/spec-v0.4.md

## Constraints
- Maximum 10 picks, 400-character optional reason; all displayed model metrics remain labelled synthetic.
- Do not publish datasets, checkpoints, credentials or private evaluation data.
- No Vercel deployment, paid services, or changes to account permissions.
- Existing accepted layout is preserved. Sites publication requires Sites runtime/tools; no invented deployment URL.

## Review focus
Repeated ID submission must not remove a pick; saving an empty selection must replace the saved selection; corrupt/blocked storage must not crash; untrusted text must never become HTML; export must not include secrets.

## Tasks
- [x] T1: Add selection/storage regression tests; run red; fix and run green.
- [x] T2: Add a dependency-free allowlisted static build; verify files and forbidden-file exclusion.
- [x] T3: Add README, Sites prompt/implementation handoff, security and acceptance status. Preserve the approved full spec.
- [ ] T4: Run unit tests, browser smoke checks and review; publish through the connected GitHub account and verify remote content.

## Decisions
The user has already approved the project direction and asked to finish setup. No new product-design round. The original starter is isolated here; original attachments remain unchanged. A complete real-data MVP is not claimed until v0.4 AC-01–18 are verified.
