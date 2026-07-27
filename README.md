# TBAM E9 GitHub Pages Human-Evaluation Collection — PAUSED

> **Collection is paused.** The research team is verifying that every method is
> represented by its best fully trained model. The deployed v4 protocol rejects
> registration, draft writes, submissions, and judgment revisions. Do not ask
> participants to rate the current catalog.

The previous v3 protocol
`9801e9289fc3a42769fdf335e5904141c891c14c528b23320169b7a7502af44f`
is retired precisely by study/protocol key. Its active store, session, and
draft keys cannot be read by v4. A redacted browser-local archive (no
pseudonym, PIN, PIN salt, or PIN hash) may be downloaded from the pause page
for safekeeping, but it is not a formal experimental result.

This repository is a Pages-ready, sealed browser-local paused interface for
the internal blinded TBAM E9 route evaluation. It displays two static A/B
full-route maps per item. It contains only the frozen public
`judge_input.json` files; videos, contact sheets, private A/B mappings,
databases, usernames, PINs, tokens, and result files are excluded. Each item
asks one forced-choice question only: which route is better overall, A or B.
There are no completion-condition branches, dimension ratings, ties,
confidence ratings, evidence fields, or written rationales.

## Important limitation

GitHub Pages has no Python or SQLite backend. In an active protocol, progress
would be stored only in the participant's current browser. The paused v4
protocol does not create participants or accept any progress writes.

GitHub records a Pages visitor's IP address for security purposes. The bundled
evaluation notice discloses that hosting behavior, the browser-local data
model, voluntary participation, and anonymous aggregate research use.

GitHub Project Pages under the same account share one browser origin. For
collection, publish this repository from a dedicated GitHub account or use a
dedicated custom domain that hosts no other applications. Otherwise JavaScript
from another Pages repository on that account could read or alter this site's
browser storage. The local PIN is a recovery gate, not cryptographic isolation
from other pages on the same origin.

In a future active, verified round, every participant must download their
`tbam.pages_human_rater_export.v2` JSON after finishing and return it to the
researcher. `results.html` combines those files locally in the researcher's
browser and exports JSON/JSONL/CSV tables; it does not upload results anywhere.

This distribution is a pause barrier, not an active collection presentation.
Its `results.html` entry also fails closed while the pause status is present.

## Paused deployment source

- Design: `e9_human_pairwise_v2`
- Maps: 60 balanced E9 evaluation instances (10 per configuration)
- Public blinded items: 360
- Items per map: all six pairwise comparisons among AZ, UCT, JointPPO, and
  MAPPO+AgentID; method identities remain private
- Items per participant: all 360
- Participant slots: 5 (`0` through `4`)
- Assignment: five frozen round-robin orderings of the complete catalog
- Response: one required `A` or `B` choice per item
- Map sizes: 8, 16, 24, and 32
- Agent counts: 2, 3, and 4
- Horizons: 48, 96, 144, and 192
- Source public-manifest SHA-256: `3f05c6ff1ccb8c18ff74e88c45d5e5771de00994a3354aea79e0b369ea4cfbae`
- Collection status: `collection_paused_for_model_selection_review`
- Study mode: `paused_review`
- Collection protocol ID: `4fe6437171bd203d801fba2ad515cc527603e5bfd652c2e5c8a13decf0da6649`
- Deployment bundle ID: `f88dd19749f0bdfac7e4582f75f18b533aa47aa73b463f0a33e6e21564fb3525`
- Presentation: `static_route_maps_bilingual_variable_scale_pages_v1`

The generated `site/` contains only byte-identical public `judge_input.json`
files. No MP4 files are required or published.

## Build and verify

Rebuilding requires the sibling `human_evaluation_portal/` source and frozen
`paper_experiments/blind_artifacts/e9_human_pairwise_v2/public/` corpus in this TBAM
workspace (or explicit `--portal` and `--artifact-root` paths). A standalone
clone can still verify and deploy the already generated, sealed `site/`.

From this TBAM workspace:

```bash
python3 build_site.py
python3 build_site.py --verify-only
```

The builder verifies every frozen source hash before copying anything. It
refuses an incomplete or changed corpus and scans the generated site for video,
database, key, token, and private-mapping files. A deliberate corpus or
protocol migration must first use an explicit local candidate build:

```bash
python3 build_site.py --allow-unsealed-identifiers --site .site-e9-candidate
python3 build_site.py --allow-unsealed-identifiers \
  --verify-only --site .site-e9-candidate
```

The GitHub Pages workflow never uses this exception and therefore refuses an
unreviewed or unsealed deployment.

Preview through HTTP, not by double-clicking `index.html`:

```bash
python3 -m http.server 8000 --directory site
```

Then open `http://127.0.0.1:8000/?slot=0`.
Use the **English / 中文** button in the header to switch languages. Both
versions share the same assigned slot, browser session, drafts, submissions,
and exported result. The direct English URL is
`http://127.0.0.1:8000/index-en.html?slot=0`.

## Publish with GitHub Pages

1. On GitHub, create an empty **public** repository, for example
   `tbam-human-evaluation`. Do not initialize it with a README or license.
2. In this local repository, add that repository as `origin` and push `main`:

   ```bash
   git remote add origin https://github.com/YOUR_ACCOUNT/tbam-human-evaluation.git
   git push -u origin main
   ```

3. Open the GitHub repository, select **Settings → Pages**, and choose
   **GitHub Actions** as the source.
4. Open the **Actions** tab and wait for `Deploy GitHub Pages` to finish.
5. The site will be:

   ```text
   https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/
   ```

The included workflow publishes only `site/`.

## Retired operational notes — do not assign links while paused

The following describes the retired collection workflow for audit context only.
Do not send any slot link until a new trained-best-model corpus and protocol
have been independently verified and deployed.

There is no global slot allocator on Pages. The researcher must send each
participant a different slot link:

```text
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/?slot=0
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/?slot=1
...
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/?slot=4
```

Slots are zero-based and must not be reused. Every slot contains every one of
the 360 items exactly once, in a different frozen order. Four completed slots
give every item four judgments; all five completed slots give every item five
judgments.

Freeze the deployed collection bundle before sending links. Do not rebuild or
redeploy the collection UI, consent text, assignment, or stimuli while a round
is active. The separate results page may be improved without changing the
collection protocol identifier.

The participant:

1. opens only their assigned slot link;
2. chooses a pseudonymous username and PIN;
3. completes the 360-item catalog, over as many sessions as needed;
   each item requires only one A/B selection and can be reopened to replace
   that selection;
4. clicks **下载结果与进度 JSON** or
   **Download results and progress JSON**;
5. sends that JSON file to the researcher.

To resume on another browser, the participant must first export the full
browser backup and import it on the other browser. A username and PIN alone
cannot retrieve data from GitHub Pages.

## Retired result-combination notes

The paused deployment intentionally disables this entry. These notes remain
only to document how an eventual replacement protocol may be operated.

Open:

```text
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/results.html
```

Select all returned participant JSON files. The tool validates the study,
manifest, item IDs, rater IDs, and artifact hashes; keeps the export with the
largest judgment set and latest export time for each rater; allows an answer to
be replaced by that rater's later submission; and provides:

- provenance-preserving merged `results.json`;
- merged `judgments.jsonl`;
- `rater_progress.csv`;
- `item_summary.csv` with A/B counts per blinded item.

All aggregation happens locally in the browser.

## Data handling

The published site is publicly readable. It contains blinded public stimuli
only. Never add any of the following:

- `private_mapping.json` or a method-name mapping;
- SQLite, WAL, or backup files;
- usernames or returned participant exports;
- administrator tokens, PINs, API keys, or environment files;
- non-blinded demonstration media.
