#!/usr/bin/env python3
"""Verify the public, frozen staged-evaluation bundle without private data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_STATUS = "frozen_staged_collection_wave1"
EXPECTED_STUDY_ID = "tbam_e9_best_models_staged_pages_v1"
EXPECTED_MASTER_PROTOCOL_ID = (
    "022be20aa0b9d495951ea32e569b26e1987398a3f64e3949ece5530d88ff730d"
)
EXPECTED_PRESENTATION_MEDIUM = "static_route_maps_bilingual_staged_pages_v1"
EXPECTED_CONSENT_VERSION = "pages-e9-best-models-staged-consent-v1"
EXPECTED_ASSET_VERSION = "e9-best-models-staged-wave1-tie-v2"
EXPECTED_MASTER_ITEMS = 300
EXPECTED_RELEASED_ITEMS = 50
EXPECTED_MAPS = 50
EXPECTED_SLOTS = 5
TEXT_SUFFIXES = {".html", ".js", ".json", ".css", ".txt"}
FORBIDDEN_SUFFIXES = {
    ".sqlite",
    ".sqlite3",
    ".db",
    ".pt",
    ".pth",
    ".ckpt",
    ".mp4",
}
# SHA-256 values of reserved internal identifier tokens. Keeping only their
# digests here prevents the public verifier itself from disclosing the labels.
FORBIDDEN_TOKEN_DIGESTS = {
    "c887a14b0e6a86c4c61657403e149e4a1e1a1045d9e93e28987117b2e2551334",
    "cc425394648003b7d92fe5fde0aafe144cc79acf42ece901920e5853e6826744",
    "8850d2e29daf2ba957a5bd39e487bfa5e2d045f92c30bad43e071e1b3b1c1ad9",
    "75002eb15722b9ad6c8698b5435f38f091c3c69b49f8d7d551179def1958b09d",
    "9cd78d8b38b152bad4371f45f5942bbc274f5611cf14cbd53c6b9c43e6bc2e49",
}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return payload


def canonical_digest(payload: Any) -> str:
    data = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def without(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in keys}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(site: Path) -> dict[str, Any]:
    site = site.resolve()
    master_path = site / "data" / "master_assignment.json"
    index_path = site / "data" / "release_index.json"
    release_path = site / "data" / "releases" / "release_001.json"
    pages_path = site / "data" / "pages_manifest.json"
    master_seal_path = site / "data" / "protocol" / "MASTER_SEAL.json"
    release_seal_path = site / "data" / "protocol" / "RELEASE_001_SEAL.json"
    required = (
        master_path,
        index_path,
        release_path,
        pages_path,
        master_seal_path,
        release_seal_path,
        site / "index.html",
        site / "index-en.html",
        site / "results.html",
    )
    require(all(path.is_file() for path in required), "required site file missing")

    master = read_json(master_path)
    index = read_json(index_path)
    release = read_json(release_path)
    pages = read_json(pages_path)
    master_seal = read_json(master_seal_path)
    release_seal = read_json(release_seal_path)

    master_id = str(master.get("master_protocol_id", ""))
    private_core_digest = str(master.get("private_master_core_sha256", ""))
    expected_master_id = canonical_digest(
        {
            "public_core": without(
                master, "master_protocol_id", "generated_utc"
            ),
            "private_core_sha256": private_core_digest,
        }
    )
    require(
        len(master_id) == 64 and master_id == expected_master_id,
        "master protocol digest mismatch",
    )

    release_id = str(release.get("release_id", ""))
    require(
        release_id
        == canonical_digest(without(release, "release_id", "generated_utc")),
        "release digest mismatch",
    )
    index_id = str(index.get("release_index_id", ""))
    require(
        index_id
        == canonical_digest(
            without(index, "release_index_id", "generated_utc")
        ),
        "release-index digest mismatch",
    )

    require(
        master.get("status") == EXPECTED_STATUS
        and release.get("status") == EXPECTED_STATUS
        and index.get("status") == EXPECTED_STATUS,
        "unexpected collection status",
    )
    require(
        master.get("study_id") == EXPECTED_STUDY_ID
        and release.get("study_id") == EXPECTED_STUDY_ID
        and index.get("study_id") == EXPECTED_STUDY_ID
        and pages.get("study_id") == EXPECTED_STUDY_ID,
        "study ID changed; existing browser progress would not be preserved",
    )
    require(
        master_id == EXPECTED_MASTER_PROTOCOL_ID,
        "master protocol ID changed; existing browser progress would not be preserved",
    )
    require(
        master.get("presentation_medium") == EXPECTED_PRESENTATION_MEDIUM
        and pages.get("presentation_medium") == EXPECTED_PRESENTATION_MEDIUM
        and master.get("consent_version") == EXPECTED_CONSENT_VERSION
        and pages.get("consent_version") == EXPECTED_CONSENT_VERSION,
        "progress-bound presentation or consent identifier changed",
    )
    require(
        release.get("master_protocol_id") == master_id
        and index.get("master_protocol_id") == master_id
        and index.get("current_release_id") == release_id
        and pages.get("collection_protocol_id") == master_id
        and pages.get("current_release_id") == release_id
        and pages.get("release_index_id") == index_id,
        "cross-manifest identifier mismatch",
    )

    master_items = master.get("items", [])
    master_ids = {
        item.get("item_id") for item in master_items if isinstance(item, dict)
    }
    require(
        len(master_items) == EXPECTED_MASTER_ITEMS
        and len(master_ids) == EXPECTED_MASTER_ITEMS
        and None not in master_ids,
        "master item catalog mismatch",
    )
    require(
        len(master.get("maps", [])) == EXPECTED_MAPS
        and master.get("map_count") == EXPECTED_MAPS
        and master.get("items_per_map") == 6,
        "master map catalog mismatch",
    )
    for slot in range(EXPECTED_SLOTS):
        assignment = master.get("slot_assignments", {}).get(str(slot), [])
        require(
            len(assignment) == EXPECTED_MASTER_ITEMS
            and len(set(assignment)) == EXPECTED_MASTER_ITEMS
            and set(assignment) == master_ids,
            f"slot {slot} assignment mismatch",
        )

    release_items = release.get("items", [])
    released_ids = {
        item.get("item_id") for item in release_items if isinstance(item, dict)
    }
    require(
        len(release_items) == EXPECTED_RELEASED_ITEMS
        and len(released_ids) == EXPECTED_RELEASED_ITEMS
        and released_ids.issubset(master_ids)
        and set(release.get("cumulative_item_ids", [])) == released_ids
        and index.get("cumulative_item_count") == EXPECTED_RELEASED_ITEMS
        and pages.get("item_count") == EXPECTED_RELEASED_ITEMS,
        "released item catalog mismatch",
    )

    expected_artifacts: set[Path] = set()
    for item in release_items:
        artifact = (site / str(item["judge_input_path"])).resolve()
        require(
            site in artifact.parents and artifact.is_file(),
            f"released artifact missing: {item['item_id']}",
        )
        require(
            file_digest(artifact)
            == item["input_artifact_sha256"]["judge_input"],
            f"released artifact digest mismatch: {item['item_id']}",
        )
        expected_artifacts.add(artifact)
    actual_artifacts = {
        path.resolve()
        for path in (site / "data" / "items").glob("*/judge_input.json")
    }
    require(
        actual_artifacts == expected_artifacts,
        "site contains missing or extra route artifacts",
    )

    require(
        master_seal.get("master_protocol_id") == master_id
        and master_seal.get("public_master", {}).get("sha256")
        == file_digest(master_path)
        and release_seal.get("master_protocol_id") == master_id
        and release_seal.get("release_id") == release_id
        and release_seal.get("release_index_id") == index_id
        and release_seal.get("release", {}).get("sha256")
        == file_digest(release_path)
        and release_seal.get("release_index", {}).get("sha256")
        == file_digest(index_path),
        "public seal mismatch",
    )

    token_pattern = re.compile(r"[a-z0-9_]+")
    for path in site.rglob("*"):
        if not path.is_file():
            continue
        require(
            path.suffix.lower() not in FORBIDDEN_SUFFIXES,
            f"forbidden site file: {path}",
        )
        if path.suffix.lower() in TEXT_SUFFIXES:
            for token in token_pattern.findall(
                path.read_text(encoding="utf-8").lower()
            ):
                require(
                    hashlib.sha256(token.encode("utf-8")).hexdigest()
                    not in FORBIDDEN_TOKEN_DIGESTS,
                    f"reserved internal identifier found in: {path}",
                )

    runtime_requirements = {
        "index.html": (
            f"styles.css?v={EXPECTED_ASSET_VERSION}",
            "既有选择和进度保持不变",
        ),
        "index-en.html": (
            f"styles.css?v={EXPECTED_ASSET_VERSION}",
            "existing choices and progress remain unchanged",
        ),
        "app.js": (
            'value="tie"',
            'choice === "tie"',
            'choice !== "tie"',
            "row.choice_tie",
        ),
        "app-en.js": (
            'value="tie"',
            "Choose Tie",
            "row.choice_tie",
        ),
        "static_api.js": (
            'const namespace = "tbam.pages.local.v2"',
            '"tbam.blind_pairwise_choice.v1"',
            '"tbam.blind_pairwise_choice.v2"',
            '[null, "A", "B", "tie"]',
        ),
        "static_api-en.js": (
            'const namespace = "tbam.pages.local.v2"',
            '"tbam.blind_pairwise_choice.v1"',
            '"tbam.blind_pairwise_choice.v2"',
            '[null, "A", "B", "tie"]',
        ),
        "results.html": (
            f"results.js?v={EXPECTED_ASSET_VERSION}",
            '<th scope="col">平局</th>',
        ),
        "results.js": (
            'new Set(["A", "B", "tie"])',
            "LEGACY_JUDGMENT_SCHEMA",
            "TIE_JUDGMENT_SCHEMA",
            '"choice_tie"',
        ),
        "styles.css": (
            "grid-template-columns: repeat(3, minmax(0, 1fr));",
        ),
    }
    for name, fragments in runtime_requirements.items():
        runtime = (site / name).read_text(encoding="utf-8")
        for fragment in fragments:
            require(
                fragment in runtime,
                f"tie-compatible runtime requirement missing from {name}: {fragment}",
            )

    return {
        "status": "verified_frozen_staged_wave1",
        "master_protocol_id": master_id,
        "release_id": release_id,
        "release_index_id": index_id,
        "full_items": len(master_ids),
        "released_items": len(released_ids),
        "artifact_count": len(actual_artifacts),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.site), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
