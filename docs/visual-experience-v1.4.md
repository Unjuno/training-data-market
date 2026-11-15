# Training Data Market — Game-first Visual Experience v1.4

Status: implemented for the existing live and static demo frontends; user engagement is **not yet measured**.

## What changed

- **Same product identity, clearer hierarchy.** Dark mission cockpit and luminous lime primary action retained, but hero height reduced so the game action sits closer to the first screen.
- **Data gallery is now the bright interaction surface.** Cream background, white cards, category-specific pastel art, readable labels, loss and vote counts, consistent selection CTA. Synthetic placeholders remain visibly labeled; the UI must not imply undisclosed CIFAR-10 rights or invented metrics.
- **User decision loop visible.** Recommend a sample → forecast the comparison → view experimentally measured results. Actual training runs only after server-governed deadline.
- **High-contrast voting anchor.** The ballot stays dark, visually separated from the light gallery, with selected state and note-save distinction preserved.
- **Mobile interaction.** Gallery uses two columns at 390px where feasible, metrics use a readable 2×2 panel, and the floating shortcut links to exploration while empty, switching to the ballot only after selecting an image.
- **Typography and spacing.** Long instructional prose is less prominent; direct actions and result indicators have higher contrast. Respect `prefers-reduced-motion` and visible keyboard focus.

## Visual tokens (implementation defaults)

| Role | Value |
|---|---|
| Canvas | `#0c1217` |
| Primary action | `#c9f77b` |
| Dark surface | `#14251f` |
| Light gallery | `#f4f6ef` |
| Paper cards | `#ffffff` |
| Gallery foreground | `#1a2a25` |
| Borders | `#dbe4da` |
| Misclassification cue | `#f48567` family |

## Evidence and limits

- Chromium 144 screenshot inspection at 390, 820 and 1440 px.
- Mock API and synthetic sample cards used for visual captures; no claim of actual user delight, CIFAR-10 photo license, or Sites live deployment.
- Browser layout expectations: no horizontal overflow at 390/820/1440; text metrics must not wrap; mobile exploration anchor should appear before 1550px (baseline 1921px); desktop exploration before 1300px (baseline 1376px).
- Functional regressions run using project Node/Python suites and `python -m tests_e2e.visual_v14`; independent integration test required before shipping production.

## Next empirical UX test

Minimum 8 first-time participants, representative mobile devices, same dataset and round. Record successful first recommendation without instructions, time to first recommendation, percentage who correctly explain that recommendations are batched (not instant training), percentage who find their forecast score, and interest in returning. Tentative exploratory gates: ≥80% completion within 2 minutes, ≥90% correct deadline comprehension, ≥70% able to locate result. These are product targets, not measured outcomes.

## Implementation boundaries

`experience.css` layers on `styles.css`, `live.css`, and `game.css`. `backend/service.py` serves it for API mode; `scripts/build.mjs` copies it into `dist/` for Sites/static handoff. No model training, API payload or persisted vote semantics were changed in this version.
