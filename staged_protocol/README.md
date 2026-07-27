# Frozen staged human evaluation — Wave 1

Status: `frozen_staged_collection_wave1`

The complete logical design was frozen before the first judgment:

- 50 retained blinded maps;
- six anonymous route pairs per map;
- 300 stable item IDs;
- five complete participant-slot orderings;
- immutable private A/B orientations.

The public site currently exposes 50 independently verified items, one per
retained map. The remaining 250 master items have no released stimulus. Their
checkpoint, trajectory, and artifact bindings remain pending in the private
master and cannot be rated.

The master assignment and release manifests are deliberately separate. Browser
progress is keyed by the stable master protocol ID and stable item IDs, not by
the current release index. A future release must be cumulative and append-only:
it may add newly verified items, but it cannot remove a released item or change
its ID, A/B orientation, path, or artifact hash.

GitHub Pages stores progress only in the participant's browser. A pseudonym and
PIN restore progress in that same browser. Moving to another browser requires
the provided backup export/import flow.

## Frozen identifiers

- Master protocol ID:
  `022be20aa0b9d495951ea32e569b26e1987398a3f64e3949ece5530d88ff730d`
- Wave-1 release ID:
  `4e506991e37db574e9c9a0a7c1690246df3aa3aa3d9b8e9923684b04675eca79`
- Wave-1 release-index ID:
  `212230a7565da1626c07649f3805ce50526be262ada0dfd927c095b54cdc9970`

These identifiers are verified by `MASTER_SEAL.json` and
`RELEASE_001_SEAL.json`. The public repository contains no private method
mapping, participant data, PIN material, database, or unreleased trajectory.

## Collection and reporting note

Items are released in stages according to a schedule fixed outside the public
rater interface. Raters are not shown method identities or release reasons.
The staged schedule must be disclosed in the paper because calendar order,
learning, fatigue, or rater drift can correlate with release wave.
