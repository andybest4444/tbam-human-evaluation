# TBAM staged human evaluation

Status: **Wave 1 is frozen, verified, and open for collection.**

Live site:
<https://andybest4444.github.io/tbam-human-evaluation/>

This is a blinded, browser-local A/B route-evaluation study. Each item shows
two complete route maps and asks only which route is better overall. The
interface supports Chinese and English, saves progress in the current browser,
allows a submitted choice to be revised, and advances automatically after each
submission.

## Frozen staged design

The complete logical design was frozen before collection began:

- 50 retained blinded maps (the 32×32 condition is excluded);
- six anonymous route pairs per map;
- 300 stable logical items;
- five complete participant-slot orderings;
- immutable private A/B orientations.

Wave 1 releases 50 verified items, one for every retained map. The other 250
items remain unavailable until their final stimuli are independently verified.
Later waves must be cumulative and append-only: they may add items but cannot
remove or modify anything already released. Participant progress is bound to
the stable master protocol, so a later wave appears in the same catalog without
invalidating earlier answers.

Frozen identifiers:

- Master protocol:
  `022be20aa0b9d495951ea32e569b26e1987398a3f64e3949ece5530d88ff730d`
- Wave-1 release:
  `4e506991e37db574e9c9a0a7c1690246df3aa3aa3d9b8e9923684b04675eca79`
- Wave-1 release index:
  `212230a7565da1626c07649f3805ce50526be262ada0dfd927c095b54cdc9970`

The formal public manifests and seals are documented in
[`staged_protocol/`](staged_protocol/).

## Assigning participants

Give each participant a different slot URL:

```text
https://andybest4444.github.io/tbam-human-evaluation/?slot=0
https://andybest4444.github.io/tbam-human-evaluation/?slot=1
https://andybest4444.github.io/tbam-human-evaluation/?slot=2
https://andybest4444.github.io/tbam-human-evaluation/?slot=3
https://andybest4444.github.io/tbam-human-evaluation/?slot=4
```

Each participant currently sees all 50 Wave-1 items in a frozen slot-specific
order. If all five slots are completed, every released item receives five
judgments.

The participant should:

1. open only their assigned slot link;
2. choose a pseudonymous username and local PIN;
3. answer the released A/B items, over one or more sessions;
4. download their result/progress JSON and return it to the researcher.

The username and PIN restore progress only in the same browser. To move to a
different browser or device, the participant must export a full browser backup
and import it there.

## Combining returned results

Open:
<https://andybest4444.github.io/tbam-human-evaluation/results.html>

Select the returned participant JSON files. Aggregation runs locally in the
researcher's browser and can export merged JSON, JSONL, participant-progress
CSV, and item-summary CSV files. No participant result is uploaded by the
static site.

## Verification and local preview

Verify the committed public bundle:

```bash
python3 verify_site.py --verify-only
```

The verifier checks the protocol and release digests, public seals, complete
assignment structure, exact released-artifact hashes, artifact count, and
absence of reserved internal identifiers or disallowed data/model/video files.

Preview through HTTP:

```bash
python3 -m http.server 8000 --directory site
```

Then open `http://127.0.0.1:8000/?slot=0`.

The included GitHub Actions workflow verifies and deploys only `site/`.
Participant exports, browser data, credentials, internal mappings, model
checkpoints, and unreleased trajectories must never be committed.
