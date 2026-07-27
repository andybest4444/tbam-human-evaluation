#!/usr/bin/env python3
"""Public-only verifier for cumulative staged human-evaluation releases."""

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
EXPECTED_ASSIGNMENT_RULE = "complete_master_catalog_round_robin_5slots_v1"
EXPECTED_RELEASE_RULE = "cumulative_append_only_artifact_binding_v1"
EXPECTED_MASTER_ITEMS = 300
EXPECTED_MAPS = 50
EXPECTED_SLOTS = 5
EXPECTED_WAVE_COUNTS = {
    1: {"new": 50, "cumulative": 50, "items_per_map": 1},
    2: {"new": 100, "cumulative": 150, "items_per_map": 3},
    3: {"new": 150, "cumulative": 300, "items_per_map": 6},
}
EXPECTED_WAVE1_RELEASE_ID = (
    "4e506991e37db574e9c9a0a7c1690246df3aa3aa3d9b8e9923684b04675eca79"
)
EXPECTED_WAVE1_INDEX_ID = (
    "212230a7565da1626c07649f3805ce50526be262ada0dfd927c095b54cdc9970"
)
EXPECTED_WAVE1_HASHES = {
    "data/master_assignment.json":
        "15e28a7465f0fdd46d72fec47e60121f068567764b20094d33837984b3156bda",
    "data/releases/release_001.json":
        "5002bce380fc71954f81530105965a178df68e4c314636c61fad9029600f1285",
    "data/protocol/MASTER_SEAL.json":
        "8e3c189069a6037f91d0c1285630879a3d87ee9cedda42e2eafb98e5ee20bef7",
    "data/protocol/RELEASE_001_SEAL.json":
        "09608e094f85e24aad10dfd581df78cae577bcd4ae51f89c4238a95e6bbeecfc",
}
EXPECTED_WAVE1_INDEX_SHA256 = (
    "71bddc88527d00fb95654b6e2052679d55bb113d743aee41712c38ce2fc2fa95"
)
EXPECTED_ASSET_VERSION_BY_WAVE = {
    1: "e9-best-models-staged-wave1-tie-v2",
    2: "e9-best-models-staged-wave3-tie-v1",
    3: "e9-best-models-staged-wave3-tie-v1",
}
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
# Digests avoid spelling private method labels in a public site verifier.
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
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def safe_child(site: Path, relative: str, label: str) -> Path:
    candidate = (site / relative).resolve()
    require(
        site == candidate or site in candidate.parents,
        f"{label} escapes site root",
    )
    return candidate


def release_binding(item: dict[str, Any]) -> str:
    return json.dumps(
        {
            "item_id": item.get("item_id"),
            "blind_map_id": item.get("blind_map_id"),
            "master_map_index": item.get("master_map_index"),
            "item_index": item.get("item_index"),
            "judge_input_path": item.get("judge_input_path"),
            "input_artifact_sha256": item.get("input_artifact_sha256"),
            "source_public_item_sha256": item.get("source_public_item_sha256"),
            "map_size": item.get("map_size"),
            "agent_count": item.get("agent_count"),
            "horizon": item.get("horizon"),
            "artifact_status": item.get("artifact_status"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def verify_master(site: Path) -> tuple[dict[str, Any], set[str]]:
    master_path = site / "data/master_assignment.json"
    require(master_path.is_file(), "master assignment is missing")
    require(
        file_digest(master_path)
        == EXPECTED_WAVE1_HASHES["data/master_assignment.json"],
        "frozen master bytes changed; browser progress would be invalidated",
    )
    master = read_json(master_path)
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
        master.get("master_protocol_id") == EXPECTED_MASTER_PROTOCOL_ID
        and expected_master_id == EXPECTED_MASTER_PROTOCOL_ID,
        "master protocol digest mismatch",
    )
    require(
        master.get("schema_version")
        == "tbam.human_staged_master.public.v1"
        and master.get("status") == EXPECTED_STATUS
        and master.get("study_id") == EXPECTED_STUDY_ID
        and master.get("presentation_medium")
        == EXPECTED_PRESENTATION_MEDIUM
        and master.get("consent_version") == EXPECTED_CONSENT_VERSION
        and master.get("assignment_rule_id") == EXPECTED_ASSIGNMENT_RULE
        and master.get("release_rule_id") == EXPECTED_RELEASE_RULE,
        "master version-bound fields changed",
    )
    items = master.get("items")
    require(
        isinstance(items, list) and len(items) == EXPECTED_MASTER_ITEMS,
        "master item count mismatch",
    )
    ids = [item.get("item_id") for item in items]
    id_set = set(ids)
    require(
        len(id_set) == EXPECTED_MASTER_ITEMS
        and all(re.fullmatch(r"item_[0-9a-f]{16}", str(item)) for item in ids),
        "master item identities are invalid",
    )
    require(
        master.get("map_count") == EXPECTED_MAPS
        and master.get("items_per_map") == 6
        and len(master.get("maps", [])) == EXPECTED_MAPS,
        "master map dimensions changed",
    )
    for slot in range(EXPECTED_SLOTS):
        assignment = master.get("slot_assignments", {}).get(str(slot))
        require(
            isinstance(assignment, list)
            and len(assignment) == EXPECTED_MASTER_ITEMS
            and len(set(assignment)) == EXPECTED_MASTER_ITEMS
            and set(assignment) == id_set,
            f"master assignment changed for slot {slot}",
        )
    seal_path = site / "data/protocol/MASTER_SEAL.json"
    require(
        seal_path.is_file()
        and file_digest(seal_path)
        == EXPECTED_WAVE1_HASHES["data/protocol/MASTER_SEAL.json"],
        "frozen master seal changed",
    )
    seal = read_json(seal_path)
    require(
        seal.get("master_protocol_id") == EXPECTED_MASTER_PROTOCOL_ID
        and seal.get("public_master", {}).get("sha256")
        == file_digest(master_path),
        "master seal does not bind the frozen master",
    )
    return master, id_set


def verify_release_chain(
    site: Path,
    master_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    index_path = site / "data/release_index.json"
    require(index_path.is_file(), "current release index is missing")
    index = read_json(index_path)
    require(
        index.get("schema_version")
        == "tbam.human_staged_release_index.v1"
        and index.get("status") == EXPECTED_STATUS
        and index.get("study_id") == EXPECTED_STUDY_ID
        and index.get("master_protocol_id") == EXPECTED_MASTER_PROTOCOL_ID
        and index.get("release_rule_id") == EXPECTED_RELEASE_RULE,
        "release-index version-bound fields changed",
    )
    index_id = str(index.get("release_index_id", ""))
    require(
        index_id
        == canonical_digest(
            without(index, "release_index_id", "generated_utc")
        ),
        "current release-index digest mismatch",
    )
    descriptors = index.get("releases")
    require(
        isinstance(descriptors, list)
        and 1 <= len(descriptors) <= 3
        and index.get("current_wave") == len(descriptors),
        "release-index wave list is invalid",
    )
    releases: list[dict[str, Any]] = []
    previous_id: str | None = None
    previous_ids: set[str] = set()
    immutable: dict[str, str] = {}
    records: dict[str, dict[str, Any]] = {}
    for offset, descriptor in enumerate(descriptors):
        wave = offset + 1
        expected = EXPECTED_WAVE_COUNTS[wave]
        require(
            descriptor.get("wave_number") == wave,
            f"release descriptor {wave} has wrong wave number",
        )
        expected_relative = f"data/releases/release_{wave:03d}.json"
        require(
            descriptor.get("path") == expected_relative,
            f"release descriptor {wave} has unexpected path",
        )
        release_path = safe_child(site, expected_relative, f"release {wave}")
        require(release_path.is_file(), f"release {wave} is missing")
        release = read_json(release_path)
        release_id = str(release.get("release_id", ""))
        require(
            release_id
            == canonical_digest(
                without(release, "release_id", "generated_utc")
            ),
            f"release {wave} digest mismatch",
        )
        require(
            release.get("schema_version") == "tbam.human_staged_release.v1"
            and release.get("status") == EXPECTED_STATUS
            and release.get("study_id") == EXPECTED_STUDY_ID
            and release.get("master_protocol_id")
            == EXPECTED_MASTER_PROTOCOL_ID
            and release.get("release_rule_id") == EXPECTED_RELEASE_RULE
            and release.get("wave_number") == wave
            and release.get("previous_release_id") == previous_id
            and release.get("new_item_count") == expected["new"]
            and release.get("cumulative_item_count")
            == expected["cumulative"],
            f"release {wave} metadata is invalid",
        )
        require(
            descriptor.get("release_id") == release_id
            and descriptor.get("previous_release_id") == previous_id
            and descriptor.get("new_item_count") == expected["new"]
            and descriptor.get("cumulative_item_count")
            == expected["cumulative"],
            f"release descriptor {wave} does not bind its release",
        )
        cumulative_ids = release.get("cumulative_item_ids")
        release_items = release.get("items")
        require(
            isinstance(cumulative_ids, list)
            and isinstance(release_items, list)
            and len(cumulative_ids) == expected["cumulative"]
            and len(set(cumulative_ids)) == expected["cumulative"]
            and len(release_items) == expected["cumulative"]
            and set(cumulative_ids).issubset(master_ids),
            f"release {wave} item dimensions are invalid",
        )
        current_ids = set(cumulative_ids)
        require(
            previous_ids.issubset(current_ids)
            and len(current_ids - previous_ids) == expected["new"],
            f"release {wave} is not append-only",
        )
        by_id: dict[str, dict[str, Any]] = {}
        for item in release_items:
            item_id = str(item.get("item_id", ""))
            artifact_hash = item.get("input_artifact_sha256", {}).get(
                "judge_input"
            )
            require(
                item_id in current_ids
                and item_id not in by_id
                and item.get("artifact_status") == "released_immutable"
                and re.fullmatch(r"[0-9a-f]{64}", str(artifact_hash))
                and re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(item.get("source_public_item_sha256", "")),
                ),
                f"release {wave} has invalid item record: {item_id}",
            )
            binding = release_binding(item)
            if item_id in immutable:
                require(
                    immutable[item_id] == binding,
                    f"released item changed in wave {wave}: {item_id}",
                )
            immutable[item_id] = binding
            by_id[item_id] = item
            records[item_id] = item
        require(
            set(by_id) == current_ids,
            f"release {wave} item records differ from cumulative IDs",
        )
        if wave == 1:
            require(
                release_id == EXPECTED_WAVE1_RELEASE_ID
                and file_digest(release_path)
                == EXPECTED_WAVE1_HASHES["data/releases/release_001.json"],
                "frozen Wave-1 release bytes changed",
            )
        releases.append(release)
        previous_id = release_id
        previous_ids = current_ids

    current = releases[-1]
    require(
        index.get("current_release_id") == current["release_id"]
        and index.get("cumulative_item_count")
        == current["cumulative_item_count"],
        "current release pointer is invalid",
    )
    if len(releases) == 1:
        require(
            index_id == EXPECTED_WAVE1_INDEX_ID,
            "frozen Wave-1 index ID changed",
        )
    return releases, index, records


def verify_index_snapshots_and_seals(
    site: Path,
    releases: list[dict[str, Any]],
    current_index: dict[str, Any],
) -> None:
    protocol = site / "data/protocol"
    wave1_seal_path = protocol / "RELEASE_001_SEAL.json"
    require(
        wave1_seal_path.is_file()
        and file_digest(wave1_seal_path)
        == EXPECTED_WAVE1_HASHES["data/protocol/RELEASE_001_SEAL.json"],
        "frozen Wave-1 release seal changed",
    )
    for wave, release in enumerate(releases, start=1):
        if len(releases) == 1 and wave == 1:
            snapshot_path = site / "data/release_index.json"
        else:
            snapshot_path = (
                protocol
                / "release_indices"
                / f"release_index_{wave:03d}.json"
            )
        require(snapshot_path.is_file(), f"release-index snapshot {wave} missing")
        snapshot = read_json(snapshot_path)
        require(
            snapshot.get("release_index_id")
            == canonical_digest(
                without(snapshot, "release_index_id", "generated_utc")
            )
            and snapshot.get("current_wave") == wave
            and len(snapshot.get("releases", [])) == wave
            and snapshot.get("current_release_id") == release["release_id"],
            f"release-index snapshot {wave} is invalid",
        )
        if wave == 1:
            require(
                snapshot.get("release_index_id") == EXPECTED_WAVE1_INDEX_ID
                and file_digest(snapshot_path) == EXPECTED_WAVE1_INDEX_SHA256,
                "Wave-1 release-index snapshot changed",
            )
            seal = read_json(wave1_seal_path)
            require(
                seal.get("master_protocol_id") == EXPECTED_MASTER_PROTOCOL_ID
                and seal.get("release_id") == EXPECTED_WAVE1_RELEASE_ID
                and seal.get("release_index_id") == EXPECTED_WAVE1_INDEX_ID
                and seal.get("release", {}).get("sha256")
                == EXPECTED_WAVE1_HASHES["data/releases/release_001.json"]
                and seal.get("release_index", {}).get("sha256")
                == EXPECTED_WAVE1_INDEX_SHA256,
                "Wave-1 release seal is invalid",
            )
            continue
        seal_path = protocol / f"RELEASE_{wave:03d}_SEAL.json"
        require(seal_path.is_file(), f"release seal {wave} missing")
        seal = read_json(seal_path)
        seal_core = without(seal, "seal_id", "generated_utc")
        release_path = (
            site / "data/releases" / f"release_{wave:03d}.json"
        )
        require(
            seal.get("seal_id") == canonical_digest(seal_core)
            and seal.get("master_protocol_id") == EXPECTED_MASTER_PROTOCOL_ID
            and seal.get("release_id") == release["release_id"]
            and seal.get("release_index_id")
            == snapshot["release_index_id"]
            and seal.get("release", {}).get("sha256")
            == file_digest(release_path)
            and seal.get("release_index_snapshot", {}).get("sha256")
            == file_digest(snapshot_path)
            and seal.get("released_item_count")
            == release["cumulative_item_count"]
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str(seal.get("amendment", {}).get("amendment_id", "")),
            )
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str(seal.get("amendment", {}).get("sha256", "")),
            ),
            f"release seal {wave} is invalid",
        )
    require(
        current_index["release_index_id"]
        == read_json(
            (
                site / "data/release_index.json"
                if len(releases) == 1
                else protocol
                / "release_indices"
                / f"release_index_{len(releases):03d}.json"
            )
        )["release_index_id"],
        "current index differs from its current-wave snapshot",
    )


def verify_pages_manifest(
    site: Path,
    master: dict[str, Any],
    current_release: dict[str, Any],
    index: dict[str, Any],
) -> dict[str, Any]:
    path = site / "data/pages_manifest.json"
    require(path.is_file(), "Pages manifest missing")
    pages = read_json(path)
    current_ids = set(current_release["cumulative_item_ids"])
    current_count = current_release["cumulative_item_count"]
    wave = current_release["wave_number"]
    require(
        pages.get("schema_version") == "tbam.github_pages_bundle.v1"
        and pages.get("study_id") == EXPECTED_STUDY_ID
        and pages.get("collection_protocol_id")
        == EXPECTED_MASTER_PROTOCOL_ID
        and pages.get("source_public_manifest_sha256")
        == EXPECTED_MASTER_PROTOCOL_ID
        and pages.get("presentation_medium")
        == EXPECTED_PRESENTATION_MEDIUM
        and pages.get("consent_version") == EXPECTED_CONSENT_VERSION
        and pages.get("assignment_rule_id") == EXPECTED_ASSIGNMENT_RULE
        and pages.get("release_rule_id") == EXPECTED_RELEASE_RULE
        and pages.get("full_item_count") == EXPECTED_MASTER_ITEMS
        and pages.get("map_count") == EXPECTED_MAPS
        and pages.get("item_count") == current_count
        and pages.get("items_per_rater") == current_count
        and pages.get("items_per_map")
        == EXPECTED_WAVE_COUNTS[wave]["items_per_map"]
        and pages.get("current_wave") == wave
        and pages.get("current_release_id") == current_release["release_id"]
        and pages.get("release_index_id") == index["release_index_id"]
        and pages.get("bundle_id") == index["release_index_id"],
        "Pages manifest does not match the current cumulative release",
    )
    page_items = pages.get("items")
    require(
        isinstance(page_items, list)
        and len(page_items) == current_count
        and {item.get("item_id") for item in page_items} == current_ids,
        "Pages manifest item set differs from current release",
    )
    release_by_id = {
        item["item_id"]: item for item in current_release["items"]
    }
    for page_item in page_items:
        release_item = release_by_id[page_item["item_id"]]
        require(
            page_item.get("judge_input_path")
            == release_item["judge_input_path"]
            and page_item.get("input_artifact_sha256")
            == release_item["input_artifact_sha256"]
            and page_item.get("public_item_sha256")
            == release_item["source_public_item_sha256"],
            f"Pages manifest artifact binding changed: {page_item['item_id']}",
        )
    for slot in range(EXPECTED_SLOTS):
        full = master["slot_assignments"][str(slot)]
        expected_visible = [item for item in full if item in current_ids]
        require(
            pages.get("slot_assignments", {}).get(str(slot))
            == expected_visible,
            f"Pages visible assignment differs for slot {slot}",
        )
    return pages


def verify_artifacts(
    site: Path,
    current_release: dict[str, Any],
) -> int:
    expected_paths: set[Path] = set()
    for item in current_release["items"]:
        artifact = safe_child(
            site, str(item["judge_input_path"]), item["item_id"]
        )
        require(artifact.is_file(), f"artifact missing: {item['item_id']}")
        require(
            file_digest(artifact)
            == item["input_artifact_sha256"]["judge_input"],
            f"artifact hash mismatch: {item['item_id']}",
        )
        judge = read_json(artifact)
        require(
            judge.get("schema_version") == "tbam.blind_judge_input.v1"
            and judge.get("design_id") == "e9_human_pairwise_v2"
            and judge.get("item_id") == item["item_id"]
            and judge.get("blind_map_id") == item["blind_map_id"]
            and set(judge.get("routes", {})) == {"A", "B"},
            f"anonymous judge input is invalid: {item['item_id']}",
        )
        expected_paths.add(artifact)
    actual_paths = {
        path.resolve()
        for path in (site / "data/items").glob("*/judge_input.json")
    }
    require(
        actual_paths == expected_paths,
        "site contains missing, extra, or unreleased judge artifacts",
    )
    return len(actual_paths)


def verify_runtime(site: Path, index: dict[str, Any], wave: int) -> None:
    expected_asset = EXPECTED_ASSET_VERSION_BY_WAVE[wave]
    runtime_requirements = {
        "app.js": (
            'value="tie"',
            'choice === "tie"',
            'choice !== "tie"',
            "row.choice_tie",
            "await openItem(nextItem.item_id)",
        ),
        "app-en.js": (
            'value="tie"',
            "Choose Tie",
            "row.choice_tie",
            "await openItem(nextItem.item_id)",
        ),
        "static_api.js": (
            'const namespace = "tbam.pages.local.v2"',
            f'const expectedMasterProtocolId = "{EXPECTED_MASTER_PROTOCOL_ID}"',
            f'const expectedReleaseIndexId = "{index["release_index_id"]}"',
            '"tbam.pages_local_store.v2"',
            '"tbam.blind_pairwise_choice.v1"',
            '"tbam.blind_pairwise_choice.v2"',
            '[null, "A", "B", "tie"]',
        ),
        "static_api-en.js": (
            'const namespace = "tbam.pages.local.v2"',
            f'const expectedMasterProtocolId = "{EXPECTED_MASTER_PROTOCOL_ID}"',
            f'const expectedReleaseIndexId = "{index["release_index_id"]}"',
            '"tbam.pages_local_store.v2"',
            '"tbam.blind_pairwise_choice.v1"',
            '"tbam.blind_pairwise_choice.v2"',
            '[null, "A", "B", "tie"]',
        ),
        "results.js": (
            'new Set(["A", "B", "tie"])',
            "LEGACY_JUDGMENT_SCHEMA",
            "TIE_JUDGMENT_SCHEMA",
            '"choice_tie"',
            "expectedOffset < expected.length",
        ),
        "styles.css": (
            "grid-template-columns: repeat(3, minmax(0, 1fr));",
        ),
    }
    for name, fragments in runtime_requirements.items():
        text = (site / name).read_text(encoding="utf-8")
        for fragment in fragments:
            require(
                fragment in text,
                f"runtime requirement missing from {name}: {fragment}",
            )
    for name in ("index.html", "index-en.html", "results.html"):
        text = (site / name).read_text(encoding="utf-8")
        require(
            f"?v={expected_asset}" in text,
            f"asset cache-buster is stale in {name}",
        )
    for name in ("static_api.js", "static_api-en.js"):
        text = (site / name).read_text(encoding="utf-8")
        retired_match = re.search(
            r"const retiredVersions = \[(.*?)\];",
            text,
            flags=re.DOTALL,
        )
        require(retired_match is not None, f"retiredVersions missing in {name}")
        require(
            EXPECTED_MASTER_PROTOCOL_ID not in retired_match.group(1)
            and EXPECTED_STUDY_ID not in retired_match.group(1),
            f"current progress namespace was incorrectly retired in {name}",
        )
        require(
            "localStorage.clear(" not in text,
            f"destructive storage clearing found in {name}",
        )


def verify_no_private_leakage(site: Path) -> None:
    token_pattern = re.compile(r"[a-z0-9_]+")
    for path in site.rglob("*"):
        if not path.is_file():
            continue
        require(
            path.suffix.lower() not in FORBIDDEN_SUFFIXES,
            f"forbidden site file: {path}",
        )
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        for token in token_pattern.findall(
            path.read_text(encoding="utf-8").lower()
        ):
            require(
                hashlib.sha256(token.encode("utf-8")).hexdigest()
                not in FORBIDDEN_TOKEN_DIGESTS,
                f"reserved internal identifier found in: {path}",
            )


def verify(site: Path) -> dict[str, Any]:
    site = site.expanduser().resolve()
    require(site.is_dir(), f"site directory missing: {site}")
    master, master_ids = verify_master(site)
    releases, index, _records = verify_release_chain(site, master_ids)
    verify_index_snapshots_and_seals(site, releases, index)
    pages = verify_pages_manifest(site, master, releases[-1], index)
    artifact_count = verify_artifacts(site, releases[-1])
    verify_runtime(site, index, releases[-1]["wave_number"])
    verify_no_private_leakage(site)
    return {
        "status": "verified_frozen_staged_release_chain",
        "study_id": EXPECTED_STUDY_ID,
        "master_protocol_id": EXPECTED_MASTER_PROTOCOL_ID,
        "current_wave": releases[-1]["wave_number"],
        "release_ids": [item["release_id"] for item in releases],
        "release_index_id": index["release_index_id"],
        "full_items": len(master_ids),
        "released_items": releases[-1]["cumulative_item_count"],
        "items_per_rater": pages["items_per_rater"],
        "artifact_count": artifact_count,
        "storage_key": (
            "tbam.pages.local.v2:"
            f"{EXPECTED_STUDY_ID}:{EXPECTED_MASTER_PROTOCOL_ID}:store"
        ),
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
