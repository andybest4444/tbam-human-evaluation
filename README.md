# TBAM E9 GitHub Pages Human-Evaluation Collection

This repository is a Pages-ready, sealed browser-local collection interface for
the internal blinded TBAM E9 route evaluation. It displays two static A/B
full-route maps per item. It contains only the frozen public
`judge_input.json` files; videos, contact sheets, private A/B mappings,
databases, usernames, PINs, tokens, and result files are excluded. Each item
asks one forced-choice question only: which route is better overall, A or B.
There are no completion-condition branches, dimension ratings, ties,
confidence ratings, evidence fields, or written rationales.

## Important limitation

GitHub Pages has no Python or SQLite backend. Progress is stored only in the
participant's current browser. The same username and PIN can reopen progress
in that browser, but cannot recover it on another device. Clearing site data or
using private-browsing mode can erase progress.

GitHub records a Pages visitor's IP address for security purposes. The bundled
evaluation notice discloses that hosting behavior, the browser-local data
model, voluntary participation, and anonymous aggregate research use.

GitHub Project Pages under the same account share one browser origin. For
collection, publish this repository from a dedicated GitHub account or use a
dedicated custom domain that hosts no other applications. Otherwise JavaScript
from another Pages repository on that account could read or alter this site's
browser storage. The local PIN is a recovery gate, not cryptographic isolation
from other pages on the same origin.

Every participant must download their
`tbam.pages_human_rater_export.v2` JSON after finishing and return it to the
researcher. `results.html` combines those files locally in the researcher's
browser and exports JSON/JSONL/CSV tables; it does not upload results anywhere.

This distribution is the internal static-route collection presentation. Do not
mix its judgments with judgments collected under an earlier presentation or
protocol. Freeze and verify the static-presentation bundle before assigning
participant links, and do not change it during a collection round.

## Frozen source

- Design: `e9_human_pairwise_v1`
- Maps: 36 balanced E9 evaluation instances
- Public blinded items: 216
- Items per map: all six pairwise comparisons among AZ, UCT, JointPPO, and
  MAPPO+AgentID; method identities remain private
- Items per participant: all 216
- Participant slots: 5 (`0` through `4`)
- Assignment: five frozen round-robin orderings of the complete catalog
- Response: one required `A` or `B` choice per item
- Map sizes: 8, 16, 24, and 32
- Agent counts: 2, 3, and 4
- Horizons: 48, 96, 144, and 192
- Source public-manifest SHA-256:
  `9441c978a4552b234d725ad1a8a87df76969d426e1a2dc99c22f3e5f8f95fad4`
- Collection protocol ID:
  `9dcbcf36e3a192e8f34569e8ccf0cc7575c89a2f0d1c0416a3d8330f7c864bae`
- Deployment bundle ID:
  `9108225b043c091ca87fbcca1f95d2b9962c2b70071a83d0948bacdf92040f0f`
- Presentation: `static_route_maps_bilingual_variable_scale_pages_v1`

The generated `site/` contains only byte-identical public `judge_input.json`
files. No MP4 files are required or published.

## Build and verify

Rebuilding requires the sibling `human_evaluation_portal/` source and frozen
`paper_experiments/blind_artifacts/e9_human_pairwise_v1/public/` corpus in this TBAM
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

## Assign participant links

There is no global slot allocator on Pages. The researcher must send each
participant a different slot link:

```text
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/?slot=0
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/?slot=1
...
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/?slot=4
```

Slots are zero-based and must not be reused. Every slot contains every one of
the 216 items exactly once, in a different frozen order. Four completed slots
give every item four judgments; all five completed slots give every item five
judgments.

Freeze the deployed collection bundle before sending links. Do not rebuild or
redeploy the collection UI, consent text, assignment, or stimuli while a round
is active. The separate results page may be improved without changing the
collection protocol identifier.

The participant:

1. opens only their assigned slot link;
2. chooses a pseudonymous username and PIN;
3. completes the 216-item catalog, over as many sessions as needed;
   each item requires only one A/B selection and can be reopened to replace
   that selection;
4. clicks **下载结果与进度 JSON** or
   **Download results and progress JSON**;
5. sends that JSON file to the researcher.

To resume on another browser, the participant must first export the full
browser backup and import it on the other browser. A username and PIN alone
cannot retrieve data from GitHub Pages.

## Combine returned results

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
