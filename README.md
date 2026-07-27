# TBAM staged human evaluation

Status: **Wave 3 is frozen, verified, and open for collection.**

Live site:
<https://andybest4444.github.io/tbam-human-evaluation/>

This is a blinded, browser-local route-evaluation study. Each item shows two
complete route maps and asks whether Route A is better overall, Route B is
better overall, or the two are tied. The interface supports Chinese and
English, saves progress in the current browser, allows a submitted choice to
be revised, and advances automatically after each submission.

## Tie-option amendment

The interface added a Tie option on 2026-07-27 without changing the study ID,
master protocol ID, storage namespace, released items, or browser-store schema.
Existing progress and `tbam.blind_pairwise_choice.v1` A/B judgments remain
unchanged. Any judgment submitted after this interface update uses
`tbam.blind_pairwise_choice.v2`, whose allowed choices are `A`, `B`, and
`tie`. Keeping the two judgment schema versions distinct makes the change in
available response options explicit during analysis.

## Frozen staged design

The complete logical design was frozen before collection began:

- 50 retained blinded maps (the 32×32 condition is excluded);
- six anonymous route pairs per map;
- 300 stable logical items;
- five complete participant-slot orderings;
- immutable private A/B orientations.

The current cumulative Wave 3 release contains all 300 verified items: the 50
immutable Wave-1 items plus 250 append-only items released in Waves 2 and 3.
Each later wave is cumulative and cannot remove or modify anything released
earlier. Participant progress remains bound to the stable master protocol, so
the added items appear in the same catalog without invalidating earlier
answers.

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

Each participant currently sees all 300 cumulative items in a frozen
slot-specific order. The first 50 are the unchanged Wave-1 items and the
remaining 250 were appended in Waves 2 and 3. If all five slots are completed,
every released item receives five judgments.

The participant should:

1. open only their assigned slot link;
2. choose a pseudonymous username and local PIN;
3. answer the released A/B/Tie items, over one or more sessions;
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

## Append-only PPO release pipeline

These commands run from the complete TBAM workspace, not from a standalone
checkout of this Pages repository. Do not rerun `build_staged_protocol.py`:
it is the historical Wave 1 builder.
Wave 1, its 50 judge inputs, and all of its seals are immutable. The final
MAPPO-with-AgentID and JointPPO stimuli must use
`build_incremental_releases_wave3.py`, which fails closed until the complete
validation-only 180-record selection and ten full-suite trajectory runs exist.

```bash
# Safe at any time; read-only and expected to report blocked until inputs exist.
python3 build_incremental_releases_wave3.py check-inputs

# Once the authoritative 180-record selection exists:
python3 build_incremental_releases_wave3.py freeze-amendment --dry-run
python3 build_incremental_releases_wave3.py freeze-amendment
python3 build_incremental_releases_wave3.py plan-trajectories --dry-run --print-commands
python3 build_incremental_releases_wave3.py plan-trajectories

# Run every command in TASK_MANIFEST.json, then hash and validate the outputs.
python3 build_incremental_releases_wave3.py collect-trajectories
python3 build_incremental_releases_wave3.py check-inputs

# Build a new candidate and separate private provenance bundle. This command
# refuses to write into site/ and never overwrites an existing candidate.
python3 build_incremental_releases_wave3.py build
python3 verify_site.py --site .site-staged-wave3-candidate --verify-only
python3 incremental_release_selftest.py
```

Promotion is a separate, deliberate review step. The production storage key
uses only the unchanged study and master protocol identifiers, so adding the
remaining 250 stable item IDs preserves existing usernames, A/B judgments,
tie judgments, and drafts. New item states are initialized lazily. The
currently active study must never be added to `retiredVersions`.

Preview through HTTP:

```bash
python3 -m http.server 8000 --directory site
```

Then open `http://127.0.0.1:8000/?slot=0`.

The included GitHub Actions workflow verifies and deploys only `site/`.
Participant exports, browser data, credentials, internal mappings, model
checkpoints, and unreleased trajectories must never be committed.
