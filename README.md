# TBAM GitHub Pages Human-Evaluation Pilot

This repository is a Pages-ready, browser-local pilot for the blinded TBAM
route study. It displays two static A/B full-route maps per item. It contains
only the frozen public `judge_input.json` files; videos, contact sheets, private
A/B mappings, databases, usernames, PINs, tokens, and result files are excluded.

## Important limitation

GitHub Pages has no Python or SQLite backend. Progress is stored only in the
participant's current browser. The same username and PIN can reopen progress
in that browser, but cannot recover it on another device. Clearing site data or
using private-browsing mode can erase progress.

GitHub records a Pages visitor's IP address for security purposes. The bundled
pilot notice discloses that hosting behavior and the browser-local data model.

GitHub Project Pages under the same account share one browser origin. For
collection, publish this repository from a dedicated GitHub account or use a
dedicated custom domain that hosts no other applications. Otherwise JavaScript
from another Pages repository on that account could read or alter this site's
browser storage. The local PIN is a recovery gate, not cryptographic isolation
from other pages on the same origin.

Every participant must download their
`tbam.pages_human_rater_export.v1` JSON after finishing and return it to the
researcher. `results.html` combines those files locally in the researcher's
browser and exports JSON/JSONL/CSV tables; it does not upload results anywhere.

This distribution is a pilot presentation, not the sealed formal collection
service. Do not mix its judgments with judgments collected under the earlier
video presentation. Freeze a new static-presentation protocol before formal
recruitment.

## Frozen source

- Design: `s6_design_v1`
- Maps: 30
- Public blinded items: 240
- Items per participant: 30
- Assignment: `j = (r + m) mod 8`
- Source public-manifest SHA-256:
  `318dc8b5edf6476f7daf8f9bbf5f2c9e2e64b67dcac6af4fcdb3520eed97be7c`
- Presentation: `static_route_maps_pages_v1`

The generated `site/` contains 240 byte-identical public judge inputs, totaling
19,465,583 bytes. No MP4 files are published.

## Build and verify

Rebuilding requires the sibling `human_evaluation_portal/` source and frozen
`paper_experiments/blind_artifacts/s6_v1/public/` corpus in this TBAM
workspace (or explicit `--portal` and `--artifact-root` paths). A standalone
clone can still verify and deploy the already generated, sealed `site/`.

From this TBAM workspace:

```bash
python3 build_site.py
python3 build_site.py --verify-only
```

The builder verifies every frozen source hash before copying anything. It
refuses an incomplete or changed corpus and scans the generated site for video,
database, key, token, and private-mapping files.

Preview through HTTP, not by double-clicking `index.html`:

```bash
python3 -m http.server 8000 --directory site
```

Then open `http://127.0.0.1:8000/?slot=0`.

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
https://YOUR_ACCOUNT.github.io/tbam-human-evaluation/?slot=39
```

Slots are zero-based and must not be reused. With all 40 slots completed, every
item receives exactly five judgments. For an eight-person interface pilot,
assign slots `0` through `7`; together they cover all 240 items once.

Freeze the deployed collection bundle before sending links. Do not rebuild or
redeploy the collection UI, consent text, assignment, or stimuli while a round
is active. The separate results page may be improved without changing the
collection protocol identifier.

The participant:

1. opens only their assigned slot link;
2. chooses a pseudonymous username and PIN;
3. completes the 30-item catalog in the same browser;
4. clicks **下载结果与进度 JSON**;
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
manifest, item IDs, rater IDs, and artifact hashes; keeps the unique maximum
monotonic superset for each rater; rejects conflicts and branches; and provides:

- provenance-preserving merged `results.json`;
- merged `judgments.jsonl`;
- `rater_progress.csv`;
- `item_summary.csv`.

All aggregation happens locally in the browser.

## Data handling

The published site is publicly readable. It contains blinded public stimuli
only. Never add any of the following:

- `private_mapping.json` or a method-name mapping;
- SQLite, WAL, or backup files;
- usernames or returned participant exports;
- administrator tokens, PINs, API keys, or environment files;
- non-blinded demonstration media.
