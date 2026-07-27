#!/usr/bin/env python3
"""Build append-only Wave 2/3 human-evaluation releases.

This program is deliberately separate from ``build_staged_protocol.py``.
The latter is the historical Wave-1 builder and must never be rerun to
"upgrade" the live study.  This builder treats every Wave-1 byte as an
immutable input, resolves the pre-release PPO seed inconsistency through a
sealed private amendment, and creates a new candidate tree rather than
writing into ``site/``.

The pipeline is fail closed:

* ``check-inputs`` may be run before JointPPO validation is complete.
* ``freeze-amendment`` requires the complete authoritative 180-record
  validation selection and never overwrites an existing amendment.
* ``plan-trajectories`` emits the ten deterministic trajectory-recording
  tasks selected using validation data only.
* ``collect-trajectories`` hash-binds and validates all ten completed tasks.
* ``build`` requires completed, hashed trajectory results and writes a fresh
  candidate directory containing cumulative release_002 and release_003.

No command removes a browser key, changes the study/master identifiers, or
modifies the frozen Wave-1 files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
BASELINE_SITE = HERE / "site"
PRIVATE_MASTER = (
    WORKSPACE
    / "paper_experiments"
    / "blind"
    / "e9_best_models_staged_v1"
    / "PRIVATE_MASTER_ASSIGNMENT.json"
)
PRIVATE_MASTER_SEAL = PRIVATE_MASTER.with_name("PRIVATE_MASTER_SEAL.json")
DEFAULT_SELECTION = (
    WORKSPACE
    / "paper_experiments"
    / "best_retrain_results"
    / "v1"
    / "validation"
    / "authoritative_180_v1"
    / "CHECKPOINT_SELECTION.json"
)
DEFAULT_AMENDMENT = (
    PRIVATE_MASTER.parent
    / "AMENDMENT_001_VALIDATION_SELECTED_PPO_BINDING.json"
)
DEFAULT_AMENDMENT_SEAL = (
    PRIVATE_MASTER.parent
    / "AMENDMENT_001_VALIDATION_SELECTED_PPO_BINDING_SEAL.json"
)
DEFAULT_TRAJECTORY_ROOT = (
    WORKSPACE
    / "paper_experiments"
    / "best_retrain_results"
    / "v1"
    / "human_trajectories"
    / "v1"
)
DEFAULT_TRAJECTORY_MANIFEST = DEFAULT_TRAJECTORY_ROOT / "RESULTS_MANIFEST.json"
DEFAULT_CANDIDATE = HERE / ".site-staged-wave3-candidate"
DEFAULT_PRIVATE_RELEASE = (
    WORKSPACE
    / "paper_experiments"
    / "blind"
    / "e9_best_models_staged_v1"
    / "release_003_private"
)

STUDY_ID = "tbam_e9_best_models_staged_pages_v1"
MASTER_PROTOCOL_ID = (
    "022be20aa0b9d495951ea32e569b26e1987398a3f64e3949ece5530d88ff730d"
)
STORAGE_NAMESPACE = "tbam.pages.local.v2"
STORAGE_KEY = (
    f"{STORAGE_NAMESPACE}:{STUDY_ID}:{MASTER_PROTOCOL_ID}:store"
)
PRESENTATION_MEDIUM = "static_route_maps_bilingual_staged_pages_v1"
CONSENT_VERSION = "pages-e9-best-models-staged-consent-v1"
RELEASE_RULE_ID = "cumulative_append_only_artifact_binding_v1"
FROZEN_STATUS = "frozen_staged_collection_wave1"
DESIGN_ID = "e9_human_pairwise_v2"
WAVE1_RELEASE_ID = (
    "4e506991e37db574e9c9a0a7c1690246df3aa3aa3d9b8e9923684b04675eca79"
)
WAVE1_INDEX_ID = (
    "212230a7565da1626c07649f3805ce50526be262ada0dfd927c095b54cdc9970"
)
WAVE1_INDEX_SHA256 = (
    "71bddc88527d00fb95654b6e2052679d55bb113d743aee41712c38ce2fc2fa95"
)
WAVE1_HASHES = {
    "data/master_assignment.json":
        "15e28a7465f0fdd46d72fec47e60121f068567764b20094d33837984b3156bda",
    "data/releases/release_001.json":
        "5002bce380fc71954f81530105965a178df68e4c314636c61fad9029600f1285",
    "data/protocol/MASTER_SEAL.json":
        "8e3c189069a6037f91d0c1285630879a3d87ee9cedda42e2eafb98e5ee20bef7",
    "data/protocol/RELEASE_001_SEAL.json":
        "09608e094f85e24aad10dfd581df78cae577bcd4ae51f89c4238a95e6bbeecfc",
}
PRIVATE_MASTER_SHA256 = (
    "69f28bf9b8f697aaf3af5fe7ca75eadd6d8abafca5f157567c2f030ef7491c18"
)
PRIVATE_MASTER_SEAL_SHA256 = (
    "6bbf18c95da8372c1a65ad45cf94b5dbe883e3915107d19ce235e9518c7e7a5d"
)
CONFIGS = (
    "map08_k3",
    "map16_k3",
    "map24_k3",
    "agents_k2",
    "agents_k4",
)
SELECTION_METHODS = ("jointppo", "mappo_aid")
PRIVATE_TO_SELECTION_METHOD = {
    "jointppo_full": "jointppo",
    "mappo_full": "mappo_aid",
}
SELECTION_TO_EVALUATOR_METHOD = {
    "jointppo": "jointppo",
    "mappo_aid": "mappo",
}
FROZEN_EXISTING_METHODS = {"az_full", "uct_full"}
NEW_PPO_METHODS = set(PRIVATE_TO_SELECTION_METHOD)
EXPECTED_TRAINING_SEEDS = {101, 202, 303}
EXPECTED_CANDIDATE_UPDATES = {900, 1200, 1800, 2400, 3000, 3051}
SUITE_BY_CONFIG = {
    "map08_k3": "e9_map08_k3_v1.json",
    "map16_k3": "e9_map16_k3_v1.json",
    "map24_k3": "e9_map24_k3_v1.json",
    "agents_k2": "e9_agents_k2_v1.json",
    "agents_k4": "e9_agents_k4_v1.json",
}
ASSET_VERSION = "e9-best-models-staged-wave3-tie-v1"
OLD_ASSET_VERSION = "e9-best-models-staged-wave1-tie-v2"
PUBLIC_FORBIDDEN = re.compile(
    r"(az_full|uct_full|jointppo_full|mappo_full|mappo_aid|private_mapping)",
    re.IGNORECASE,
)
TEXT_SUFFIXES = {".html", ".js", ".json", ".css", ".txt"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def formatted_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_path(raw: str | Path) -> Path:
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (WORKSPACE / path).resolve()


def display_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(WORKSPACE.resolve()))
    except ValueError:
        return str(path)


def write_new_json(path: Path, payload: Any) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(formatted_json_bytes(payload))
    temporary.replace(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(formatted_json_bytes(payload))


def validate_baseline(site: Path = BASELINE_SITE) -> dict[str, Any]:
    site = site.resolve()
    for relative, expected in WAVE1_HASHES.items():
        path = site / relative
        require(path.is_file(), f"missing frozen Wave-1 file: {path}")
        require(
            sha256(path) == expected,
            f"frozen Wave-1 file changed: {path}",
        )
    require(
        sha256(PRIVATE_MASTER) == PRIVATE_MASTER_SHA256,
        "frozen private master changed",
    )
    require(
        sha256(PRIVATE_MASTER_SEAL) == PRIVATE_MASTER_SEAL_SHA256,
        "frozen private master seal changed",
    )

    master = read_json(site / "data/master_assignment.json")
    release = read_json(site / "data/releases/release_001.json")
    current_index = read_json(site / "data/release_index.json")
    if current_index.get("release_index_id") == WAVE1_INDEX_ID:
        wave1_index_path = site / "data/release_index.json"
    else:
        wave1_index_path = (
            site
            / "data"
            / "protocol"
            / "release_indices"
            / "release_index_001.json"
        )
    require(
        wave1_index_path.is_file()
        and sha256(wave1_index_path) == WAVE1_INDEX_SHA256,
        "frozen Wave-1 release-index snapshot changed or is missing",
    )
    index = read_json(wave1_index_path)
    private = read_json(PRIVATE_MASTER)
    require(master.get("study_id") == STUDY_ID, "Wave-1 study ID changed")
    require(
        master.get("master_protocol_id") == MASTER_PROTOCOL_ID,
        "Wave-1 master protocol ID changed",
    )
    require(
        release.get("release_id") == WAVE1_RELEASE_ID,
        "Wave-1 release ID changed",
    )
    require(
        index.get("release_index_id") == WAVE1_INDEX_ID,
        "frozen Wave-1 release-index ID changed",
    )
    require(
        current_index.get("master_protocol_id") == MASTER_PROTOCOL_ID
        and isinstance(current_index.get("releases"), list)
        and current_index["releases"]
        and current_index["releases"][0].get("release_id")
        == WAVE1_RELEASE_ID,
        "current deployed release chain does not descend from frozen Wave 1",
    )
    require(len(master.get("items", [])) == 300, "invalid master item count")
    require(len(release.get("items", [])) == 50, "invalid Wave-1 item count")
    require(len(private.get("items", [])) == 300, "invalid private item count")

    released_ids = set(release["cumulative_item_ids"])
    artifact_hashes: dict[str, str] = {}
    for item in release["items"]:
        item_id = str(item["item_id"])
        artifact = site / item["judge_input_path"]
        expected = item["input_artifact_sha256"]["judge_input"]
        require(artifact.is_file(), f"missing Wave-1 artifact: {item_id}")
        require(sha256(artifact) == expected, f"Wave-1 artifact changed: {item_id}")
        artifact_hashes[item_id] = expected
    require(
        set(artifact_hashes) == released_ids,
        "Wave-1 artifact set differs from its release",
    )

    master_ids = [item["item_id"] for item in master["items"]]
    private_ids = [item["item_id"] for item in private["items"]]
    require(master_ids == private_ids, "public/private master item order differs")
    pending = [
        item for item in private["items"]
        if int(item["planned_release_wave"]) in (2, 3)
    ]
    require(len(pending) == 250, "private master does not have 250 pending items")
    require(
        Counter(int(item["planned_release_wave"]) for item in pending)
        == {2: 100, 3: 150},
        "private master release-wave counts changed",
    )
    return {
        "site": site,
        "master": master,
        "release_001": release,
        "release_index_001": index,
        "current_release_index": current_index,
        "private_master": private,
        "released_ids": released_ids,
        "wave1_artifact_hashes": artifact_hashes,
    }


def resolve_sealed_workspace_path(raw: str | Path) -> Path:
    path = workspace_path(raw)
    try:
        path.relative_to(WORKSPACE.resolve())
    except ValueError as error:
        raise RuntimeError(f"sealed path escapes workspace: {path}") from error
    return path


def validate_sealed_file_record(
    record: Any,
    *,
    expected_path: Path | None = None,
    label: str,
) -> Path:
    require(isinstance(record, dict), f"{label}: invalid sealed file record")
    require(
        isinstance(record.get("path"), str),
        f"{label}: sealed file path is missing",
    )
    path = resolve_sealed_workspace_path(record["path"])
    if expected_path is not None:
        require(
            path == expected_path.resolve(),
            f"{label}: sealed file path mismatch",
        )
    require(path.is_file(), f"{label}: sealed file is missing: {path}")
    require(
        int(record.get("bytes", -1)) == path.stat().st_size,
        f"{label}: sealed file size changed: {path}",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))
        is not None
        and sha256(path) == record["sha256"],
        f"{label}: sealed file hash changed: {path}",
    )
    return path


def validate_selection(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    require(path.is_file(), f"authoritative selection is missing: {path}")
    root = path.parent
    merged_path = root / "MERGED_RECORDS.json"
    audit_path = root / "PROMOTION_AUDIT.json"
    seal_path = root / "SEAL.json"
    for required_path in (merged_path, audit_path, seal_path):
        require(
            required_path.is_file(),
            f"authoritative selection bundle is incomplete: {required_path}",
        )

    seal = read_json(seal_path)
    require(
        seal.get("schema_version")
        == "tbam.best_retrain_authoritative_selection_seal.v1"
        and seal.get("immutable") is True
        and seal.get("status") == "sealed_authoritative_selection",
        "authoritative selection seal is not immutable and terminal",
    )
    sealed_files = seal.get("files")
    require(
        isinstance(sealed_files, list) and sealed_files,
        "authoritative selection seal has no bound files",
    )
    sealed_paths = {
        validate_sealed_file_record(
            record,
            label=f"authoritative seal files[{index}]",
        ).resolve()
        for index, record in enumerate(sealed_files)
    }
    required_outputs = {
        path.resolve(),
        merged_path.resolve(),
        audit_path.resolve(),
    }
    require(
        required_outputs.issubset(sealed_paths),
        "authoritative seal does not bind selection, merged records, and "
        "promotion audit",
    )
    external = seal.get("external_bindings")
    require(
        isinstance(external, list) and external,
        "authoritative selection seal has no external bindings",
    )
    for index, record in enumerate(external):
        validate_sealed_file_record(
            record,
            label=f"authoritative seal external_bindings[{index}]",
        )

    selection = read_json(path)
    require(
        selection.get("schema_version")
        == "tbam.best_retrain_checkpoint_selection.v1",
        "unexpected authoritative selection schema",
    )
    require(
        selection.get("status") in {"complete", "complete_authoritative"},
        "selection is not complete",
    )
    require(
        selection.get("test_or_human_results_read") is False,
        "selection is not validation-only",
    )
    input_manifest = selection.get("input_manifest", {})
    require(
        resolve_sealed_workspace_path(input_manifest.get("path", ""))
        == merged_path
        and input_manifest.get("sha256") == sha256(merged_path)
        and input_manifest.get("record_count") == 180,
        "selection is not hash-bound to the complete merged 180-record matrix",
    )

    merged = read_json(merged_path)
    records = merged.get("records")
    require(
        merged.get("schema_version")
        == "tbam.best_retrain_authoritative_records.v1"
        and merged.get("status") in {"complete", "complete_authoritative"}
        and merged.get("record_count") == 180
        and merged.get("group_count") == 30
        and merged.get("test_or_human_results_read") is False
        and merged.get("formal_full_matrix_selection") is True
        and isinstance(records, list)
        and len(records) == 180,
        "authoritative merged validation records are incomplete",
    )
    expected_routes = {
        (config, method, seed, update)
        for config in CONFIGS
        for method in SELECTION_METHODS
        for seed in EXPECTED_TRAINING_SEEDS
        for update in EXPECTED_CANDIDATE_UPDATES
    }
    records_by_route: dict[
        tuple[str, str, int, int], dict[str, Any]
    ] = {}
    for record in records:
        key = (
            str(record.get("config_id")),
            str(record.get("method")),
            int(record.get("training_seed", -1)),
            int(record.get("checkpoint_update", -1)),
        )
        require(
            key in expected_routes and key not in records_by_route,
            f"unexpected or duplicate authoritative validation route: {key}",
        )
        records_by_route[key] = record
    require(
        set(records_by_route) == expected_routes,
        "authoritative 180-record route matrix is incomplete",
    )

    audit = read_json(audit_path)
    require(
        audit.get("schema_version")
        == "tbam.best_retrain_promotion_audit.v1"
        and audit.get("status") == "pass"
        and audit.get("authoritative_selector_complete") is True
        and audit.get("record_count") == 180
        and audit.get("selection_count") == 30
        and audit.get("human_catalog_representative_count") == 10
        and audit.get("mappo_checkpoint_count") == 15
        and audit.get("mappo_checkpoint_sha256_reproduced") is True
        and audit.get("mappo_mismatch_count") == 0
        and audit.get("test_or_human_results_used_for_selection") is False,
        "authoritative MAPPO promotion audit did not pass",
    )
    validate_sealed_file_record(
        audit.get("selection"),
        expected_path=path,
        label="promotion audit selection",
    )
    staged_mappo_path = validate_sealed_file_record(
        audit.get("staged_mappo_selection"),
        label="promotion audit staged MAPPO selection",
    )
    selections = selection.get("selections")
    representatives = selection.get("human_catalog_representatives")
    require(
        isinstance(selections, list) and len(selections) == 30,
        "selection must contain 30 method/config/seed groups",
    )
    require(
        isinstance(representatives, list) and len(representatives) == 10,
        "selection must contain ten human-catalog representatives",
    )
    expected_groups = {
        (config, method, seed)
        for config in CONFIGS
        for method in SELECTION_METHODS
        for seed in EXPECTED_TRAINING_SEEDS
    }
    observed_groups = {
        (
            str(item.get("config_id")),
            str(item.get("method")),
            int(item.get("training_seed", -1)),
        )
        for item in selections
    }
    require(
        observed_groups == expected_groups,
        "selection group matrix is incomplete or unexpected",
    )
    for item in selections:
        selected = item.get("selected", {})
        route = (
            str(item.get("config_id")),
            str(item.get("method")),
            int(item.get("training_seed", -1)),
            int(selected.get("checkpoint_update", -1)),
        )
        require(
            int(selected.get("checkpoint_update", -1))
            in EXPECTED_CANDIDATE_UPDATES,
            "selection contains an ineligible checkpoint update",
        )
        source = records_by_route.get(route)
        require(source is not None, f"selected route absent from merged records: {route}")
        for field in (
            "checkpoint_global_step",
            "checkpoint_path",
            "checkpoint_sha256",
            "evaluation_path",
            "evaluation_sha256",
        ):
            require(
                str(selected.get(field)) == str(source.get(field)),
                f"selected/merged record mismatch for {route}: {field}",
            )

    authoritative_mappo = {
        (
            str(item["config_id"]),
            str(item["method"]),
            int(item["training_seed"]),
        ): str(item["selected"]["checkpoint_sha256"])
        for item in selections
        if item.get("method") == "mappo_aid"
    }
    staged_mappo = read_json(staged_mappo_path)
    staged_rows = staged_mappo.get("selections")
    require(
        isinstance(staged_rows, list) and len(staged_rows) == 15,
        "staged MAPPO selection bound by promotion audit is incomplete",
    )
    staged_mappo_hashes = {
        (
            str(item["config_id"]),
            str(item["method"]),
            int(item["training_seed"]),
        ): str(item["selected"]["checkpoint_sha256"])
        for item in staged_rows
    }
    require(
        len(authoritative_mappo) == 15
        and staged_mappo_hashes == authoritative_mappo,
        "authoritative selection does not reproduce all 15 staged MAPPO "
        "checkpoint hashes",
    )

    expected_representatives = {
        (config, method)
        for config in CONFIGS
        for method in SELECTION_METHODS
    }
    observed_representatives: dict[tuple[str, str], dict[str, Any]] = {}
    selected_rows = {
        (
            str(item["config_id"]),
            str(item["method"]),
            int(item["training_seed"]),
        ): item["selected"]
        for item in selections
    }
    for representative in representatives:
        key = (
            str(representative.get("config_id")),
            str(representative.get("method")),
        )
        require(
            key not in observed_representatives,
            f"duplicate human representative: {key}",
        )
        seed = int(representative.get("selected_training_seed", -1))
        require(seed in EXPECTED_TRAINING_SEEDS, f"invalid representative seed: {key}")
        chosen = selected_rows.get((key[0], key[1], seed))
        require(chosen is not None, f"representative has no selected group: {key}")
        require(
            int(representative.get("selected_checkpoint_update", -1))
            == int(chosen["checkpoint_update"]),
            f"representative checkpoint update mismatch: {key}",
        )
        require(
            representative.get("selected_checkpoint_path")
            == chosen["checkpoint_path"],
            f"representative checkpoint path mismatch: {key}",
        )
        require(
            representative.get("selected_checkpoint_sha256")
            == chosen["checkpoint_sha256"],
            f"representative checkpoint hash mismatch: {key}",
        )
        checkpoint = workspace_path(representative["selected_checkpoint_path"])
        require(checkpoint.is_file(), f"representative checkpoint missing: {checkpoint}")
        require(
            sha256(checkpoint) == representative["selected_checkpoint_sha256"],
            f"representative checkpoint bytes changed: {checkpoint}",
        )
        observed_representatives[key] = dict(representative)
    require(
        set(observed_representatives) == expected_representatives,
        "human representative matrix is incomplete",
    )
    return {
        "path": path,
        "sha256": sha256(path),
        "seal_path": seal_path,
        "seal_sha256": sha256(seal_path),
        "merged_records_path": merged_path,
        "merged_records_sha256": sha256(merged_path),
        "promotion_audit_path": audit_path,
        "promotion_audit_sha256": sha256(audit_path),
        "payload": selection,
        "representatives": observed_representatives,
    }


def amendment_core(
    baseline: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    private = baseline["private_master"]
    pending = [
        item for item in private["items"]
        if int(item["planned_release_wave"]) in (2, 3)
    ]
    legacy_counts: dict[str, Counter[int]] = {
        method: Counter() for method in sorted(NEW_PPO_METHODS)
    }
    for item in pending:
        for arm in ("A", "B"):
            method = item[arm]["method"]
            if method in legacy_counts:
                legacy_counts[method][int(item[arm]["training_seed"])] += 1
    bindings = []
    for (config, method), representative in sorted(
        selection["representatives"].items()
    ):
        bindings.append(
            {
                "config_id": config,
                "method": method,
                "selected_training_seed": int(
                    representative["selected_training_seed"]
                ),
                "selected_checkpoint_update": int(
                    representative["selected_checkpoint_update"]
                ),
                "selected_checkpoint_path":
                    representative["selected_checkpoint_path"],
                "selected_checkpoint_sha256":
                    representative["selected_checkpoint_sha256"],
                "selection_source": "sealed_validation_only",
            }
        )
    return {
        "schema_version": "tbam.human_staged_amendment.v1",
        "status": "frozen_before_any_ppo_human_release",
        "amendment_number": 1,
        "study_id": STUDY_ID,
        "master_protocol_id": MASTER_PROTOCOL_ID,
        "release_rule_id": RELEASE_RULE_ID,
        "scope": {
            "affected_release_waves": [2, 3],
            "affected_pending_item_count": len(pending),
            "affected_pending_item_ids": sorted(
                item["item_id"] for item in pending
            ),
            "unaffected_wave_1_item_count": 50,
        },
        "reason": (
            "The frozen private master inherited legacy PPO seed labels "
            "101/303/505 before the final best-retrain protocol fixed seeds "
            "101/202/303 and validation-only representative selection. "
            "No PPO stimulus had been released when this inconsistency was "
            "resolved."
        ),
        "legacy_seed_binding": {
            "status": "superseded_placeholder_for_pending_ppo_arms_only",
            "seed_values": [101, 303, 505],
            "occurrence_counts": {
                method: {
                    str(seed): count
                    for seed, count in sorted(counts.items())
                }
                for method, counts in legacy_counts.items()
            },
        },
        "resolved_binding_rule": {
            "unit": "method x retained configuration",
            "rule": (
                "Use the single human-catalog representative selected by "
                "the same frozen validation-only lexicographic rule used "
                "for checkpoint selection."
            ),
            "formal_numeric_reporting_unchanged": (
                "Formal reward/success reporting retains all independently "
                "selected training seeds; representatives are only for "
                "human-stimulus generation."
            ),
            "representative_bindings": bindings,
        },
        "selection": {
            "path": display_path(selection["path"]),
            "sha256": selection["sha256"],
            "seal": {
                "path": display_path(selection["seal_path"]),
                "sha256": selection["seal_sha256"],
            },
            "merged_records": {
                "path": display_path(selection["merged_records_path"]),
                "sha256": selection["merged_records_sha256"],
            },
            "promotion_audit": {
                "path": display_path(selection["promotion_audit_path"]),
                "sha256": selection["promotion_audit_sha256"],
                "status": "pass",
                "record_count": 180,
                "selection_count": 30,
                "mappo_checkpoint_sha256_reproduced": True,
            },
            "schema_version":
                selection["payload"]["schema_version"],
            "record_count":
                selection["payload"]["input_manifest"]["record_count"],
            "test_or_human_results_read": False,
        },
        "frozen_inputs": {
            "private_master": {
                "path": display_path(PRIVATE_MASTER),
                "sha256": PRIVATE_MASTER_SHA256,
            },
            "private_master_seal": {
                "path": display_path(PRIVATE_MASTER_SEAL),
                "sha256": PRIVATE_MASTER_SEAL_SHA256,
            },
            "wave_1_release_id": WAVE1_RELEASE_ID,
            "wave_1_release_index_id": WAVE1_INDEX_ID,
        },
        "non_effects": {
            "study_id_unchanged": True,
            "master_protocol_id_unchanged": True,
            "storage_namespace_and_key_unchanged": True,
            "master_item_ids_unchanged": True,
            "private_method_pairs_and_A_B_orientations_unchanged": True,
            "slot_assignments_and_order_unchanged": True,
            "wave_1_item_ids_and_artifact_hashes_unchanged": True,
            "existing_browser_profiles_judgments_and_drafts_unchanged": True,
            "no_released_item_is_removed_or_replaced": True,
        },
        "storage_key": STORAGE_KEY,
    }


def build_amendment(
    baseline: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    core = amendment_core(baseline, selection)
    return {
        **core,
        "amendment_id": canonical_digest(core),
        "generated_utc": utc_now(),
    }


def validate_amendment(
    path: Path,
    selection: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    path = path.expanduser().resolve()
    require(path.is_file(), f"frozen amendment is missing: {path}")
    amendment = read_json(path)
    core = {
        key: value
        for key, value in amendment.items()
        if key not in {"amendment_id", "generated_utc"}
    }
    require(
        amendment.get("amendment_id") == canonical_digest(core),
        "amendment digest mismatch",
    )
    expected = amendment_core(baseline, selection)
    require(core == expected, "amendment content does not match current inputs")
    return {
        "path": path,
        "sha256": sha256(path),
        "payload": amendment,
        "amendment_id": amendment["amendment_id"],
    }


def freeze_amendment(args: argparse.Namespace) -> dict[str, Any]:
    baseline = validate_baseline(args.baseline_site)
    selection = validate_selection(args.selection)
    amendment = build_amendment(baseline, selection)
    seal_core = {
        "schema_version": "tbam.human_staged_amendment_seal.v1",
        "status": amendment["status"],
        "study_id": STUDY_ID,
        "master_protocol_id": MASTER_PROTOCOL_ID,
        "amendment_id": amendment["amendment_id"],
        "amendment": {
            "path": display_path(args.amendment),
            "sha256": canonical_digest(amendment),
        },
        "selection": {
            "path": display_path(selection["path"]),
            "sha256": selection["sha256"],
            "seal_path": display_path(selection["seal_path"]),
            "seal_sha256": selection["seal_sha256"],
            "merged_records_path":
                display_path(selection["merged_records_path"]),
            "merged_records_sha256":
                selection["merged_records_sha256"],
            "promotion_audit_path":
                display_path(selection["promotion_audit_path"]),
            "promotion_audit_sha256":
                selection["promotion_audit_sha256"],
        },
        "private_master_sha256": PRIVATE_MASTER_SHA256,
    }
    # The on-disk JSON hash is only available after serialization.  Dry-run
    # reports the semantic digest; a real freeze writes the amendment first
    # and then replaces this field with its exact file hash.
    if args.dry_run:
        return {
            "status": "ready_to_freeze",
            "dry_run": True,
            "amendment_path": str(args.amendment.resolve()),
            "seal_path": str(args.amendment_seal.resolve()),
            "amendment_id": amendment["amendment_id"],
            "semantic_sha256": canonical_digest(amendment),
            "representative_count": 10,
        }
    require(
        not args.amendment.resolve().exists(),
        f"amendment already exists: {args.amendment}",
    )
    require(
        not args.amendment_seal.resolve().exists(),
        f"amendment seal already exists: {args.amendment_seal}",
    )
    write_new_json(args.amendment, amendment)
    seal_core["amendment"]["sha256"] = sha256(args.amendment)
    seal = {
        **seal_core,
        "seal_id": canonical_digest(seal_core),
        "generated_utc": utc_now(),
    }
    try:
        write_new_json(args.amendment_seal, seal)
    except BaseException:
        # Both paths were absent on entry; remove the just-created amendment
        # so a failed pair cannot look frozen on a later run.
        args.amendment.resolve().unlink(missing_ok=True)
        raise RuntimeError(
            "amendment/seal pair could not be frozen atomically"
        )
    return {
        "status": "frozen",
        "amendment_path": str(args.amendment.resolve()),
        "amendment_sha256": sha256(args.amendment),
        "seal_path": str(args.amendment_seal.resolve()),
        "seal_sha256": sha256(args.amendment_seal),
        "amendment_id": amendment["amendment_id"],
    }


def selected_indices_by_config(
    private_master: dict[str, Any],
) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = {config: [] for config in CONFIGS}
    for record in private_master["maps"]:
        config = str(record["config_id"])
        if config in grouped:
            grouped[config].append(int(record["source_instance_index"]))
    for config, indices in grouped.items():
        require(len(indices) == 10, f"expected ten human maps for {config}")
        require(len(set(indices)) == 10, f"duplicate human map index for {config}")
    return grouped


def trajectory_plan(
    baseline: dict[str, Any],
    selection: dict[str, Any],
    amendment: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    selected_indices = selected_indices_by_config(baseline["private_master"])
    tasks = []
    python = (
        "/common/home/jl4015/miniforge3/envs/tbam_cu128/bin/python3.10"
    )
    evaluator = WORKSPACE / "paper_experiments" / "evaluate.py"
    for (config, method), representative in sorted(
        selection["representatives"].items()
    ):
        suite = (
            WORKSPACE
            / "paper_experiments"
            / "suites"
            / "e9_scale_v1"
            / SUITE_BY_CONFIG[config]
        )
        require(suite.is_file(), f"missing E9 suite: {suite}")
        task_id = f"human50m__{method}__{config}"
        result = output_root / "evaluation" / method / config / "result.json"
        events = result.with_name("events.jsonl")
        log = result.with_name("stdout.log")
        checkpoint = workspace_path(
            representative["selected_checkpoint_path"]
        )
        command = [
            python,
            str(evaluator),
            "--method",
            SELECTION_TO_EVALUATOR_METHOD[method],
            "--checkpoint",
            str(checkpoint),
            "--instances",
            str(suite),
            "--device",
            "cpu",
            "--json-out",
            str(result),
            "--jsonl-out",
            str(events),
            "--record-trajectories",
            "--reward-profile",
            "full",
            "--quiet",
        ]
        tasks.append(
            {
                "task_id": task_id,
                "config_id": config,
                "method": method,
                "evaluator_method": SELECTION_TO_EVALUATOR_METHOD[method],
                "selected_training_seed": int(
                    representative["selected_training_seed"]
                ),
                "checkpoint_update": int(
                    representative["selected_checkpoint_update"]
                ),
                "checkpoint_path": display_path(checkpoint),
                "checkpoint_sha256":
                    representative["selected_checkpoint_sha256"],
                "suite_path": display_path(suite),
                "suite_sha256": sha256(suite),
                "evaluation_source_indices": list(range(54)),
                "human_catalog_source_indices": selected_indices[config],
                "result_path": display_path(result),
                "events_path": display_path(events),
                "log_path": display_path(log),
                "command": command,
            }
        )
    return {
        "schema_version": "tbam.best_retrain_human_trajectory_tasks.v1",
        "status": "planned_not_run",
        "generated_utc": utc_now(),
        "study_id": STUDY_ID,
        "master_protocol_id": MASTER_PROTOCOL_ID,
        "amendment": {
            "path": display_path(amendment["path"]),
            "sha256": amendment["sha256"],
            "amendment_id": amendment["amendment_id"],
        },
        "selection": {
            "path": display_path(selection["path"]),
            "sha256": selection["sha256"],
            "seal_path": display_path(selection["seal_path"]),
            "seal_sha256": selection["seal_sha256"],
            "merged_records_path":
                display_path(selection["merged_records_path"]),
            "merged_records_sha256":
                selection["merged_records_sha256"],
            "promotion_audit_path":
                display_path(selection["promotion_audit_path"]),
            "promotion_audit_sha256":
                selection["promotion_audit_sha256"],
        },
        "record_trajectories": True,
        "complete_suite_evaluation_required": True,
        "task_count": len(tasks),
        "tasks": tasks,
    }


def plan_trajectories(args: argparse.Namespace) -> dict[str, Any]:
    baseline = validate_baseline(args.baseline_site)
    selection = validate_selection(args.selection)
    amendment = validate_amendment(args.amendment, selection, baseline)
    plan = trajectory_plan(
        baseline,
        selection,
        amendment,
        args.trajectory_root,
    )
    if not args.dry_run:
        write_new_json(args.out, plan)
    return {
        "status": "ready" if args.dry_run else "planned",
        "dry_run": bool(args.dry_run),
        "task_count": len(plan["tasks"]),
        "out": str(args.out.resolve()),
        "commands": [task["command"] for task in plan["tasks"]]
        if args.print_commands
        else None,
    }


def collect_trajectory_results(args: argparse.Namespace) -> dict[str, Any]:
    baseline = validate_baseline(args.baseline_site)
    selection = validate_selection(args.selection)
    amendment = validate_amendment(args.amendment, selection, baseline)
    task_path = args.task_manifest.expanduser().resolve()
    require(task_path.is_file(), f"trajectory task manifest missing: {task_path}")
    actual = read_json(task_path)
    expected = trajectory_plan(
        baseline,
        selection,
        amendment,
        args.trajectory_root,
    )
    require(
        {
            key: value
            for key, value in actual.items()
            if key != "generated_utc"
        }
        == {
            key: value
            for key, value in expected.items()
            if key != "generated_utc"
        },
        "trajectory task manifest does not match the frozen inputs",
    )

    completed_tasks = []
    for task in actual["tasks"]:
        result_path = workspace_path(task["result_path"])
        events_path = workspace_path(task["events_path"])
        require(result_path.is_file(), f"trajectory result missing: {result_path}")
        require(events_path.is_file(), f"trajectory event log missing: {events_path}")
        require(result_path.stat().st_size > 0, f"empty result: {result_path}")
        require(events_path.stat().st_size > 0, f"empty event log: {events_path}")
        completed_tasks.append(
            {
                **task,
                "result_sha256": sha256(result_path),
                "events_sha256": sha256(events_path),
            }
        )
    manifest = {
        "schema_version": "tbam.best_retrain_human_trajectory_results.v1",
        "status": "completed",
        "generated_utc": utc_now(),
        "study_id": STUDY_ID,
        "master_protocol_id": MASTER_PROTOCOL_ID,
        "selection": actual["selection"],
        "amendment": actual["amendment"],
        "task_manifest": {
            "path": display_path(task_path),
            "sha256": sha256(task_path),
        },
        "task_count": len(completed_tasks),
        "tasks": completed_tasks,
    }

    output = args.out.expanduser().resolve()
    require(not output.exists(), f"results manifest already exists: {output}")
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    require(not temporary.exists(), f"temporary output exists: {temporary}")
    try:
        write_json(temporary, manifest)
        routes, verified = validate_trajectory_manifest(
            temporary,
            baseline,
            selection,
            amendment,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "status": "completed_and_validated",
        "out": str(output),
        "sha256": sha256(output),
        "task_count": len(completed_tasks),
        "route_count": len(routes),
        "verified_manifest_sha256": verified["sha256"],
    }


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def validate_public_trajectory(
    trajectory: Any,
    *,
    agent_count: int,
    map_size: int,
    horizon: int,
    start: list[int],
    goal: list[int],
    success: bool,
    steps: int,
    label: str,
) -> list[dict[str, Any]]:
    require(isinstance(trajectory, list) and trajectory, f"{label}: no trajectory")
    require(
        isinstance(success, bool)
        and isinstance(steps, int)
        and 0 <= steps <= horizon
        and len(trajectory) == steps + 1,
        f"{label}: trajectory length/result steps mismatch",
    )
    require(
        isinstance(start, list)
        and isinstance(goal, list)
        and len(start) == 2
        and len(goal) == 2
        and all(isinstance(value, int) for value in start + goal),
        f"{label}: invalid start/goal",
    )
    action_names = ("up", "down", "left", "right", "stay")
    action_deltas = ((-1, 0), (1, 0), (0, -1), (0, 1), (0, 0))
    cleaned = []
    for expected_t, frame in enumerate(trajectory):
        require(isinstance(frame, dict), f"{label}: invalid frame")
        require(frame.get("t") == expected_t, f"{label}: noncontiguous time")
        positions = frame.get("positions")
        require(
            isinstance(positions, list) and len(positions) == agent_count,
            f"{label}: invalid positions",
        )
        for position in positions:
            require(
                isinstance(position, list)
                and len(position) == 2
                and all(isinstance(value, int) for value in position)
                and all(0 <= value < map_size for value in position),
                f"{label}: invalid position",
            )
        reached = frame.get("reached_mask")
        active = frame.get("active_mask")
        require(
            isinstance(reached, list)
            and isinstance(active, list)
            and len(reached) == agent_count
            and len(active) == agent_count
            and all(isinstance(value, bool) for value in reached + active)
            and all(a is (not r) for a, r in zip(active, reached)),
            f"{label}: invalid active/reached mask",
        )
        require(
            reached
            == [
                position == goal
                for position in positions
            ],
            f"{label}: reached mask disagrees with positions",
        )
        actions = frame.get("agent_actions")
        names = frame.get("agent_action_names")
        if expected_t == 0:
            require(
                actions is None
                and names is None
                and positions == [start] * agent_count,
                f"{label}: invalid initial frame",
            )
        else:
            require(
                isinstance(actions, list)
                and len(actions) == agent_count
                and all(isinstance(value, int) and 0 <= value <= 4 for value in actions),
                f"{label}: invalid actions",
            )
            require(
                isinstance(names, list)
                and names == [action_names[value] for value in actions],
                f"{label}: invalid action names",
            )
            previous = cleaned[-1]
            for agent, action in enumerate(actions):
                old_position = previous["positions"][agent]
                if previous["active_mask"][agent]:
                    delta = action_deltas[action]
                    expected_position = [
                        old_position[0] + delta[0],
                        old_position[1] + delta[1],
                    ]
                else:
                    expected_position = old_position
                require(
                    positions[agent] == expected_position,
                    f"{label}: action/position transition mismatch",
                )
                require(
                    not previous["reached_mask"][agent]
                    or reached[agent],
                    f"{label}: reached state is not monotone",
                )
        cleaned.append(
            {
                "t": expected_t,
                "positions": positions,
                "agent_actions": actions,
                "agent_action_names": names,
                "reached_mask": reached,
                "active_mask": active,
            }
        )
    require(
        all(cleaned[-1]["reached_mask"]) is success,
        f"{label}: success flag disagrees with terminal state",
    )
    require(
        success or steps == horizon,
        f"{label}: unsuccessful trajectory ended before the horizon",
    )
    return cleaned


def validate_trajectory_manifest(
    path: Path,
    baseline: dict[str, Any],
    selection: dict[str, Any],
    amendment: dict[str, Any],
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, Any]]:
    path = path.expanduser().resolve()
    require(path.is_file(), f"trajectory results manifest is missing: {path}")
    manifest = read_json(path)
    require(
        manifest.get("schema_version")
        == "tbam.best_retrain_human_trajectory_results.v1",
        "unexpected trajectory-results schema",
    )
    require(manifest.get("status") == "completed", "trajectory results incomplete")
    require(manifest.get("task_count") == 10, "expected ten trajectory tasks")
    require(
        manifest.get("selection", {}).get("sha256") == selection["sha256"],
        "trajectory results target another selection",
    )
    require(
        manifest.get("amendment", {}).get("amendment_id")
        == amendment["amendment_id"],
        "trajectory results target another amendment",
    )
    tasks = manifest.get("tasks")
    require(isinstance(tasks, list) and len(tasks) == 10, "invalid trajectory tasks")
    expected_groups = {
        (config, method)
        for config in CONFIGS
        for method in SELECTION_METHODS
    }
    observed: set[tuple[str, str]] = set()
    route_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    private_maps = {
        (record["config_id"], record["source_instance_id"]): record
        for record in baseline["private_master"]["maps"]
        if record["config_id"] in CONFIGS
    }
    for task in tasks:
        config = str(task.get("config_id"))
        method = str(task.get("method"))
        key = (config, method)
        require(key in expected_groups and key not in observed, f"invalid task: {key}")
        observed.add(key)
        representative = selection["representatives"][key]
        require(
            task.get("checkpoint_path")
            == representative["selected_checkpoint_path"],
            f"trajectory checkpoint path mismatch: {key}",
        )
        require(
            task.get("checkpoint_sha256")
            == representative["selected_checkpoint_sha256"],
            f"trajectory checkpoint hash mismatch: {key}",
        )
        result_path = workspace_path(task["result_path"])
        require(result_path.is_file(), f"trajectory result missing: {result_path}")
        require(
            sha256(result_path) == task.get("result_sha256"),
            f"trajectory result hash mismatch: {key}",
        )
        result = read_json(result_path)
        require(result.get("schema_version") == "tbam.paper_eval.v1", f"bad result: {key}")
        require(
            result.get("method") == SELECTION_TO_EVALUATOR_METHOD[method],
            f"trajectory evaluator method mismatch: {key}",
        )
        result_checkpoint = result.get("checkpoint", {})
        require(
            result_checkpoint.get("sha256")
            == representative["selected_checkpoint_sha256"],
            f"result checkpoint hash mismatch: {key}",
        )
        require(
            workspace_path(result_checkpoint.get("path", ""))
            == workspace_path(representative["selected_checkpoint_path"]),
            f"result checkpoint path mismatch: {key}",
        )
        if method == "mappo_aid":
            require(result_checkpoint.get("agent_id") is True, "MAPPO lacks AgentID")
        evaluation = result.get("evaluation", {})
        require(
            evaluation.get("policy") == "deterministic_greedy"
            and evaluation.get("record_trajectories") is True
            and evaluation.get("reward_profile", {}).get("name") == "full",
            f"invalid trajectory evaluation settings: {key}",
        )
        suite_path = (
            WORKSPACE
            / "paper_experiments"
            / "suites"
            / "e9_scale_v1"
            / SUITE_BY_CONFIG[config]
        ).resolve()
        suite = read_json(suite_path)
        suite_sha = sha256(suite_path)
        result_suite = result.get("instance_suite", {})
        require(
            workspace_path(result_suite.get("path", "")) == suite_path
            and result_suite.get("sha256") == suite_sha
            and result_suite.get("selected_source_indices") == list(range(54)),
            f"trajectory result did not evaluate the complete frozen suite: {key}",
        )
        episodes = result.get("instances")
        require(isinstance(episodes, list) and len(episodes) == 54, f"bad episodes: {key}")
        by_id = {episode.get("instance_id"): episode for episode in episodes}
        require(len(by_id) == 54 and None not in by_id, f"duplicate episodes: {key}")
        for instance in suite["instances"]:
            source_key = (config, instance["instance_id"])
            if source_key not in private_maps:
                continue
            map_record = private_maps[source_key]
            require(
                map_record.get("source_suite_sha256") == suite_sha
                and int(map_record.get("source_instance_index", -1))
                == int(instance["index"])
                and map_record.get("terrain") == instance.get("terrain")
                and map_record.get("cover") == instance.get("cover"),
                f"private human-map binding changed: {source_key}",
            )
            episode = by_id.get(instance["instance_id"])
            require(episode is not None, f"missing human episode: {key}/{source_key}")
            require(
                episode.get("index") == instance.get("index")
                and episode.get("start") == instance.get("start")
                and episode.get("goal") == instance.get("goal")
                and episode.get("terrain") == instance.get("terrain")
                and episode.get("cover") == instance.get("cover")
                and isinstance(episode.get("success"), bool)
                and isinstance(episode.get("steps"), int),
                f"trajectory episode/source-suite mismatch: {key}/{source_key}",
            )
            trajectory = validate_public_trajectory(
                episode.get("trajectory"),
                agent_count=int(map_record["k_agents"]),
                map_size=int(map_record["n"]),
                horizon=int(map_record["max_steps"]),
                start=instance["start"],
                goal=instance["goal"],
                success=episode["success"],
                steps=episode["steps"],
                label=f"{method}/{config}/{instance['instance_id']}",
            )
            route_lookup[
                (
                    "jointppo_full" if method == "jointppo" else "mappo_full",
                    config,
                    instance["instance_id"],
                )
            ] = {
                "completed": bool(episode["success"]),
                "completion_step": (
                    int(episode["steps"]) if episode["success"] else None
                ),
                "trajectory": trajectory,
                "private_provenance": {
                    "task_id": task["task_id"],
                    "result_path": display_path(result_path),
                    "result_sha256": task["result_sha256"],
                    "checkpoint_path":
                        representative["selected_checkpoint_path"],
                    "checkpoint_sha256":
                        representative["selected_checkpoint_sha256"],
                    "selected_training_seed": int(
                        representative["selected_training_seed"]
                    ),
                },
            }
    require(observed == expected_groups, "trajectory task matrix incomplete")
    require(len(route_lookup) == 100, "expected 100 new PPO map routes")
    return route_lookup, {
        "path": path,
        "sha256": sha256(path),
        "payload": manifest,
    }


def make_public_item(
    item_id: str,
    blind_map_id: str,
    judge_input_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "tbam.e9_human_item_public.v1",
        "design_id": DESIGN_ID,
        "item_id": item_id,
        "blind_map_id": blind_map_id,
        "directive": (
            "Reach the goal efficiently, avoid unnecessary elevation "
            "change, prefer concealed cells, and maintain separation "
            "while exposed but gather while concealed."
        ),
        "question": "Which route better follows the directive overall?",
        "artifact": {
            "judge_input_path": f"items/{item_id}/judge_input.json",
            "judge_input_sha256": judge_input_sha256,
        },
    }


def release_record(
    master_item: dict[str, Any],
    map_record: dict[str, Any],
    artifact_sha256: str,
    source_public_item_sha256: str,
) -> dict[str, Any]:
    item_id = master_item["item_id"]
    return {
        "item_id": item_id,
        "blind_map_id": master_item["blind_map_id"],
        "master_map_index": int(master_item["master_map_index"]),
        "item_index": int(master_item["item_index"]),
        "judge_input_path": f"data/items/{item_id}/judge_input.json",
        "input_artifact_sha256": {"judge_input": artifact_sha256},
        "source_public_item_sha256": source_public_item_sha256,
        "map_size": int(map_record["n"]),
        "agent_count": int(map_record["k_agents"]),
        "horizon": int(map_record["max_steps"]),
        "artifact_status": "released_immutable",
    }


def make_release(
    *,
    wave: int,
    previous_release_id: str,
    new_item_count: int,
    records: list[dict[str, Any]],
    generated_utc: str,
) -> dict[str, Any]:
    core = {
        "schema_version": "tbam.human_staged_release.v1",
        "status": FROZEN_STATUS,
        "study_id": STUDY_ID,
        "master_protocol_id": MASTER_PROTOCOL_ID,
        "release_rule_id": RELEASE_RULE_ID,
        "wave_number": wave,
        "previous_release_id": previous_release_id,
        "new_item_count": new_item_count,
        "cumulative_item_count": len(records),
        "cumulative_item_ids": [item["item_id"] for item in records],
        "items": records,
    }
    return {
        **core,
        "release_id": canonical_digest(core),
        "generated_utc": generated_utc,
    }


def make_release_index(
    releases: list[dict[str, Any]],
    generated_utc: str,
) -> dict[str, Any]:
    descriptors = [
        {
            "wave_number": release["wave_number"],
            "path": (
                f"data/releases/release_{release['wave_number']:03d}.json"
            ),
            "release_id": release["release_id"],
            "previous_release_id": release["previous_release_id"],
            "new_item_count": release["new_item_count"],
            "cumulative_item_count": release["cumulative_item_count"],
        }
        for release in releases
    ]
    current = releases[-1]
    core = {
        "schema_version": "tbam.human_staged_release_index.v1",
        "status": FROZEN_STATUS,
        "study_id": STUDY_ID,
        "master_protocol_id": MASTER_PROTOCOL_ID,
        "release_rule_id": RELEASE_RULE_ID,
        "current_wave": current["wave_number"],
        "current_release_id": current["release_id"],
        "cumulative_item_count": current["cumulative_item_count"],
        "releases": descriptors,
    }
    return {
        **core,
        "release_index_id": canonical_digest(core),
        "generated_utc": generated_utc,
    }


def make_release_seal(
    *,
    candidate: Path,
    release: dict[str, Any],
    index_snapshot: Path,
    index: dict[str, Any],
    amendment: dict[str, Any],
    generated_utc: str,
) -> dict[str, Any]:
    release_path = (
        candidate
        / "data"
        / "releases"
        / f"release_{release['wave_number']:03d}.json"
    )
    core = {
        "schema_version": "tbam.human_staged_seal.v1",
        "status": FROZEN_STATUS,
        "study_id": STUDY_ID,
        "master_protocol_id": MASTER_PROTOCOL_ID,
        "release_id": release["release_id"],
        "release_index_id": index["release_index_id"],
        "release": {
            "path": (
                f"site/data/releases/release_{release['wave_number']:03d}.json"
            ),
            "sha256": sha256(release_path),
        },
        "release_index_snapshot": {
            "path": (
                "site/data/protocol/release_indices/"
                f"release_index_{release['wave_number']:03d}.json"
            ),
            "sha256": sha256(index_snapshot),
        },
        "amendment": {
            "amendment_id": amendment["amendment_id"],
            "sha256": amendment["sha256"],
        },
        "released_item_count": release["cumulative_item_count"],
    }
    return {
        **core,
        "seal_id": canonical_digest(core),
        "generated_utc": generated_utc,
    }


def patch_candidate_runtime(candidate: Path, release_index_id: str) -> None:
    for name in ("static_api.js", "static_api-en.js"):
        path = candidate / name
        text = path.read_text(encoding="utf-8")
        old = f'const expectedReleaseIndexId = "{WAVE1_INDEX_ID}";'
        new = f'const expectedReleaseIndexId = "{release_index_id}";'
        require(text.count(old) == 1, f"unexpected release-index constant in {name}")
        path.write_text(text.replace(old, new), encoding="utf-8")
    for name in ("index.html", "index-en.html", "results.html"):
        path = candidate / name
        text = path.read_text(encoding="utf-8")
        require(OLD_ASSET_VERSION in text, f"missing old asset version in {name}")
        path.write_text(
            text.replace(OLD_ASSET_VERSION, ASSET_VERSION),
            encoding="utf-8",
        )


def leakage_scan(candidate: Path) -> None:
    for path in candidate.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        require(
            PUBLIC_FORBIDDEN.search(path.read_text(encoding="utf-8")) is None,
            f"private identifier leaked into candidate: {path}",
        )


def build_candidate(args: argparse.Namespace) -> dict[str, Any]:
    baseline = validate_baseline(args.baseline_site)
    selection = validate_selection(args.selection)
    amendment = validate_amendment(args.amendment, selection, baseline)
    routes, trajectory_manifest = validate_trajectory_manifest(
        args.trajectory_manifest,
        baseline,
        selection,
        amendment,
    )
    destination = args.candidate.resolve()
    require(
        destination != BASELINE_SITE.resolve(),
        "refusing to build directly into the live site directory",
    )
    require(not destination.exists(), f"candidate already exists: {destination}")
    require(
        not args.private_out.resolve().exists(),
        f"private release output already exists: {args.private_out}",
    )
    staging = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    require(not staging.exists(), f"staging path already exists: {staging}")
    private_destination = args.private_out.resolve()
    private_staging = private_destination.with_name(
        f".{private_destination.name}.{os.getpid()}.tmp"
    )
    require(
        not private_staging.exists(),
        f"private staging path already exists: {private_staging}",
    )
    generated_utc = utc_now()
    private = baseline["private_master"]
    public_master = baseline["master"]
    private_by_id = {item["item_id"]: item for item in private["items"]}
    map_by_blind_id = {
        item["blind_map_id"]: item for item in private["maps"]
        if item["config_id"] in CONFIGS
    }
    wave1_private_by_map = {
        item["blind_map_id"]: item
        for item in private["items"]
        if int(item["planned_release_wave"]) == 1
    }
    existing_routes: dict[tuple[str, str], dict[str, Any]] = {}
    for blind_map_id, item in wave1_private_by_map.items():
        judge = read_json(
            baseline["site"]
            / "data"
            / "items"
            / item["item_id"]
            / "judge_input.json"
        )
        for arm in ("A", "B"):
            method = item[arm]["method"]
            require(method in FROZEN_EXISTING_METHODS, "bad Wave-1 method mapping")
            existing_routes[(method, blind_map_id)] = judge["routes"][arm]
    require(len(existing_routes) == 100, "could not recover all frozen AZ/UCT routes")

    private_item_records = []
    public_item_payloads: dict[str, dict[str, Any]] = {}
    try:
        shutil.copytree(baseline["site"], staging, copy_function=shutil.copy2)
        record_by_id = {
            item["item_id"]: item for item in baseline["release_001"]["items"]
        }
        for master_item in public_master["items"]:
            item_id = master_item["item_id"]
            private_item = private_by_id[item_id]
            wave = int(private_item["planned_release_wave"])
            if wave == 1:
                continue
            map_record = map_by_blind_id[master_item["blind_map_id"]]
            config = map_record["config_id"]
            instance_id = map_record["source_instance_id"]
            wave1_judge = read_json(
                baseline["site"]
                / "data"
                / "items"
                / wave1_private_by_map[master_item["blind_map_id"]]["item_id"]
                / "judge_input.json"
            )
            arms: dict[str, dict[str, Any]] = {}
            arm_provenance: dict[str, Any] = {}
            for arm in ("A", "B"):
                method = private_item[arm]["method"]
                if method in FROZEN_EXISTING_METHODS:
                    route = existing_routes[(method, master_item["blind_map_id"])]
                    arm_provenance[arm] = {
                        "method": method,
                        "source": "immutable_wave_1_route",
                        "source_wave_1_item_id":
                            wave1_private_by_map[master_item["blind_map_id"]][
                                "item_id"
                            ],
                    }
                else:
                    route = routes[(method, config, instance_id)]
                    arm_provenance[arm] = {
                        "method": method,
                        **route["private_provenance"],
                    }
                arms[arm] = {
                    key: value
                    for key, value in route.items()
                    if key != "private_provenance"
                }
            judge = {
                "schema_version": "tbam.blind_judge_input.v1",
                "design_id": DESIGN_ID,
                "item_id": item_id,
                "blind_map_id": master_item["blind_map_id"],
                "directive": public_master["directive"],
                "map": wave1_judge["map"],
                "routes": {"A": arms["A"], "B": arms["B"]},
            }
            artifact = staging / "data" / "items" / item_id / "judge_input.json"
            write_json(artifact, judge)
            artifact_sha = sha256(artifact)
            public_item = make_public_item(
                item_id,
                master_item["blind_map_id"],
                artifact_sha,
            )
            public_item_sha = hashlib.sha256(
                formatted_json_bytes(public_item)
            ).hexdigest()
            public_item_payloads[item_id] = public_item
            record_by_id[item_id] = release_record(
                master_item,
                map_record,
                artifact_sha,
                public_item_sha,
            )
            private_item_records.append(
                {
                    "item_id": item_id,
                    "blind_map_id": master_item["blind_map_id"],
                    "planned_release_wave": wave,
                    "pair_type": private_item["pair_type"],
                    "orientation_swapped": private_item["orientation_swapped"],
                    "A": arm_provenance["A"],
                    "B": arm_provenance["B"],
                    "judge_input_sha256": artifact_sha,
                    "source_public_item_path":
                        f"public_items/{item_id}/public_item.json",
                    "source_public_item_sha256": public_item_sha,
                }
            )
        require(len(record_by_id) == 300, "did not construct all 300 release records")
        ordered_ids = [item["item_id"] for item in public_master["items"]]
        wave_by_id = {
            item["item_id"]: int(item["planned_release_wave"])
            for item in private["items"]
        }
        records2 = [
            record_by_id[item_id]
            for item_id in ordered_ids
            if wave_by_id[item_id] <= 2
        ]
        records3 = [record_by_id[item_id] for item_id in ordered_ids]
        require(len(records2) == 150 and len(records3) == 300, "bad release sizes")
        release1 = baseline["release_001"]
        release2 = make_release(
            wave=2,
            previous_release_id=release1["release_id"],
            new_item_count=100,
            records=records2,
            generated_utc=generated_utc,
        )
        release3 = make_release(
            wave=3,
            previous_release_id=release2["release_id"],
            new_item_count=150,
            records=records3,
            generated_utc=generated_utc,
        )
        releases_dir = staging / "data" / "releases"
        write_json(releases_dir / "release_002.json", release2)
        write_json(releases_dir / "release_003.json", release3)

        protocol_dir = staging / "data" / "protocol"
        snapshot_dir = protocol_dir / "release_indices"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            baseline["site"] / "data/release_index.json",
            snapshot_dir / "release_index_001.json",
        )
        index2 = make_release_index([release1, release2], generated_utc)
        index3 = make_release_index([release1, release2, release3], generated_utc)
        write_json(snapshot_dir / "release_index_002.json", index2)
        write_json(snapshot_dir / "release_index_003.json", index3)
        write_json(staging / "data/release_index.json", index3)

        seal2 = make_release_seal(
            candidate=staging,
            release=release2,
            index_snapshot=snapshot_dir / "release_index_002.json",
            index=index2,
            amendment=amendment,
            generated_utc=generated_utc,
        )
        seal3 = make_release_seal(
            candidate=staging,
            release=release3,
            index_snapshot=snapshot_dir / "release_index_003.json",
            index=index3,
            amendment=amendment,
            generated_utc=generated_utc,
        )
        write_json(protocol_dir / "RELEASE_002_SEAL.json", seal2)
        write_json(protocol_dir / "RELEASE_003_SEAL.json", seal3)

        pages = read_json(staging / "data/pages_manifest.json")
        pages.update(
            {
                "built_utc": generated_utc,
                "bundle_id": index3["release_index_id"],
                "item_count": 300,
                "items_per_map": 6,
                "items_per_rater": 300,
                "slot_assignments": public_master["slot_assignments"],
                "current_wave": 3,
                "current_release_id": release3["release_id"],
                "release_index_id": index3["release_index_id"],
                "items": [
                    {
                        **item,
                        "map_index": item["master_map_index"],
                        "directive": public_master["directive"],
                        "public_item_sha256":
                            item["source_public_item_sha256"],
                    }
                    for item in records3
                ],
            }
        )
        write_json(staging / "data/pages_manifest.json", pages)
        patch_candidate_runtime(staging, index3["release_index_id"])
        (staging / ".tbam-pages-generated").write_text(
            "generated by build_incremental_releases.py; cumulative wave 3\n",
            encoding="utf-8",
        )
        leakage_scan(staging)

        private_manifest = {
            "schema_version": "tbam.human_staged_private_release.v1",
            "status": "private_do_not_distribute",
            "generated_utc": generated_utc,
            "study_id": STUDY_ID,
            "master_protocol_id": MASTER_PROTOCOL_ID,
            "amendment": {
                "path": display_path(amendment["path"]),
                "sha256": amendment["sha256"],
                "amendment_id": amendment["amendment_id"],
            },
            "selection": {
                "path": display_path(selection["path"]),
                "sha256": selection["sha256"],
            },
            "trajectory_results": {
                "path": display_path(trajectory_manifest["path"]),
                "sha256": trajectory_manifest["sha256"],
            },
            "release_002_id": release2["release_id"],
            "release_003_id": release3["release_id"],
            "release_index_003_id": index3["release_index_id"],
            "items": private_item_records,
        }
        private_staging.mkdir(parents=True, exist_ok=False)
        for item_id, public_item in public_item_payloads.items():
            public_item_path = (
                private_staging
                / "public_items"
                / item_id
                / "public_item.json"
            )
            write_json(public_item_path, public_item)
            require(
                sha256(public_item_path)
                == record_by_id[item_id]["source_public_item_sha256"],
                f"serialized public-item hash mismatch: {item_id}",
            )
        write_json(private_staging / "PRIVATE_RELEASE.json", private_manifest)
        private_seal_core = {
            "schema_version": "tbam.human_staged_private_release_seal.v1",
            "status": "sealed",
            "private_release_sha256": sha256(
                private_staging / "PRIVATE_RELEASE.json"
            ),
            "amendment_id": amendment["amendment_id"],
            "release_003_id": release3["release_id"],
            "release_index_003_id": index3["release_index_id"],
        }
        write_json(
            private_staging / "SEAL.json",
            {
                **private_seal_core,
                "seal_id": canonical_digest(private_seal_core),
                "generated_utc": generated_utc,
            },
        )

        # Validate the complete public tree before either public or private
        # output becomes visible at its final path.
        sys.path.insert(0, str(HERE))
        from verify_site import verify  # pylint: disable=import-outside-toplevel

        verification = verify(staging)
        staging.replace(destination)
        try:
            private_staging.replace(private_destination)
        except BaseException:
            # Both final paths were absent on entry, so rolling back the
            # just-created public candidate cannot delete user data.
            shutil.rmtree(destination)
            raise
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        if private_staging.exists():
            shutil.rmtree(private_staging)
        raise

    return {
        "status": "candidate_built",
        "candidate": str(destination),
        "private_release": str(private_destination),
        "release_002_id": verification["release_ids"][1],
        "release_003_id": verification["release_ids"][2],
        "release_index_id": verification["release_index_id"],
        "released_items": verification["released_items"],
        "storage_key": STORAGE_KEY,
    }


def check_inputs(args: argparse.Namespace) -> dict[str, Any]:
    baseline = validate_baseline(args.baseline_site)
    report: dict[str, Any] = {
        "status": "blocked_expected",
        "baseline": {
            "status": "verified_immutable_wave_1",
            "study_id": STUDY_ID,
            "master_protocol_id": MASTER_PROTOCOL_ID,
            "storage_key": STORAGE_KEY,
            "released_items": 50,
            "full_items": 300,
        },
        "selection": {"status": "missing"},
        "amendment": {"status": "not_checked"},
        "trajectory_results": {"status": "not_checked"},
        "safe_to_build": False,
    }
    try:
        selection = validate_selection(args.selection)
    except (FileNotFoundError, RuntimeError) as error:
        report["selection"] = {
            "status": "not_ready",
            "path": str(args.selection.resolve()),
            "reason": str(error),
        }
        return report
    report["selection"] = {
        "status": "ready",
        "path": str(selection["path"]),
        "sha256": selection["sha256"],
        "representatives": len(selection["representatives"]),
    }
    try:
        amendment = validate_amendment(
            args.amendment, selection, baseline
        )
    except (FileNotFoundError, RuntimeError) as error:
        report["amendment"] = {
            "status": "not_ready",
            "path": str(args.amendment.resolve()),
            "reason": str(error),
        }
        return report
    report["amendment"] = {
        "status": "ready",
        "path": str(amendment["path"]),
        "sha256": amendment["sha256"],
        "amendment_id": amendment["amendment_id"],
    }
    try:
        routes, trajectory = validate_trajectory_manifest(
            args.trajectory_manifest,
            baseline,
            selection,
            amendment,
        )
    except (FileNotFoundError, RuntimeError) as error:
        report["trajectory_results"] = {
            "status": "not_ready",
            "path": str(args.trajectory_manifest.resolve()),
            "reason": str(error),
        }
        return report
    report["trajectory_results"] = {
        "status": "ready",
        "path": str(trajectory["path"]),
        "sha256": trajectory["sha256"],
        "route_count": len(routes),
    }
    report["status"] = "ready"
    report["safe_to_build"] = True
    return report


def add_common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--baseline-site", type=Path, default=BASELINE_SITE)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check-inputs")
    add_common_inputs(check)
    check.add_argument(
        "--trajectory-manifest",
        type=Path,
        default=DEFAULT_TRAJECTORY_MANIFEST,
    )

    freeze = subparsers.add_parser("freeze-amendment")
    add_common_inputs(freeze)
    freeze.add_argument(
        "--amendment-seal",
        type=Path,
        default=DEFAULT_AMENDMENT_SEAL,
    )
    freeze.add_argument("--dry-run", action="store_true")

    plan = subparsers.add_parser("plan-trajectories")
    add_common_inputs(plan)
    plan.add_argument(
        "--trajectory-root", type=Path, default=DEFAULT_TRAJECTORY_ROOT
    )
    plan.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_TRAJECTORY_ROOT / "TASK_MANIFEST.json",
    )
    plan.add_argument("--dry-run", action="store_true")
    plan.add_argument("--print-commands", action="store_true")

    collect = subparsers.add_parser("collect-trajectories")
    add_common_inputs(collect)
    collect.add_argument(
        "--trajectory-root", type=Path, default=DEFAULT_TRAJECTORY_ROOT
    )
    collect.add_argument(
        "--task-manifest",
        type=Path,
        default=DEFAULT_TRAJECTORY_ROOT / "TASK_MANIFEST.json",
    )
    collect.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_TRAJECTORY_MANIFEST,
    )

    build = subparsers.add_parser("build")
    add_common_inputs(build)
    build.add_argument(
        "--trajectory-manifest",
        type=Path,
        default=DEFAULT_TRAJECTORY_MANIFEST,
    )
    build.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    build.add_argument("--private-out", type=Path, default=DEFAULT_PRIVATE_RELEASE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "check-inputs":
        report = check_inputs(args)
    elif args.command == "freeze-amendment":
        report = freeze_amendment(args)
    elif args.command == "plan-trajectories":
        report = plan_trajectories(args)
    elif args.command == "collect-trajectories":
        report = collect_trajectory_results(args)
    elif args.command == "build":
        report = build_candidate(args)
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
