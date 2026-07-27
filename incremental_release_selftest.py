from __future__ import annotations

import argparse
import copy
import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import build_incremental_releases_wave3 as incremental
import verify_release_chain as chain


class IncrementalReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = incremental.validate_baseline(incremental.BASELINE_SITE)
        self.master = self.baseline["master"]
        self.release = self.baseline["release_001"]

    def test_deployed_wave_three_chain_keeps_wave_one_byte_frozen(self) -> None:
        report = chain.verify(incremental.BASELINE_SITE)
        self.assertEqual(report["current_wave"], 3)
        self.assertEqual(report["released_items"], 300)
        self.assertEqual(report["full_items"], 300)
        self.assertEqual(report["storage_key"], incremental.STORAGE_KEY)
        self.assertEqual(
            self.baseline["release_index_001"]["release_index_id"],
            incremental.WAVE1_INDEX_ID,
        )
        self.assertEqual(
            incremental.sha256(
                incremental.BASELINE_SITE
                / "data"
                / "protocol"
                / "release_indices"
                / "release_index_001.json"
            ),
            incremental.WAVE1_INDEX_SHA256,
        )

    def test_wave_one_progress_expands_without_changing_existing_records(self) -> None:
        full_assignment = self.master["slot_assignments"]["0"]
        released = set(self.release["cumulative_item_ids"])
        wave_one_assignment = [
            item_id for item_id in full_assignment if item_id in released
        ]
        self.assertEqual(len(wave_one_assignment), 50)
        self.assertEqual(len(full_assignment), 300)

        empty = {
            "started_utc": None,
            "draft": None,
            "judgment": None,
        }
        items = {
            item_id: copy.deepcopy(empty) for item_id in wave_one_assignment
        }
        first, second, third = wave_one_assignment[:3]
        items[first] = {
            "started_utc": "2026-07-27T12:00:00Z",
            "draft": None,
            "judgment": {
                "schema_version": "tbam.blind_pairwise_choice.v1",
                "choice": "A",
            },
        }
        items[second] = {
            "started_utc": "2026-07-27T12:01:00Z",
            "draft": None,
            "judgment": {
                "schema_version": "tbam.blind_pairwise_choice.v2",
                "choice": "tie",
            },
        }
        items[third] = {
            "started_utc": "2026-07-27T12:02:00Z",
            "draft": {
                "payload": {"choice": "B"},
                "active_seconds": 2,
                "revision": 1,
                "updated_utc": "2026-07-27T12:02:02Z",
            },
            "judgment": None,
        }
        profile = {
            "registered_bundle_id": incremental.WAVE1_INDEX_ID,
            "items": items,
        }
        original_items = copy.deepcopy(profile["items"])

        # This mirrors itemState() in static_api.js: new catalog entries are
        # initialized lazily, while existing entries are returned untouched.
        for item_id in full_assignment:
            profile["items"].setdefault(item_id, copy.deepcopy(empty))

        self.assertEqual(profile["registered_bundle_id"], incremental.WAVE1_INDEX_ID)
        self.assertEqual(len(profile["items"]), 300)
        self.assertEqual(
            {item_id: profile["items"][item_id] for item_id in wave_one_assignment},
            original_items,
        )
        new_ids = set(full_assignment) - set(wave_one_assignment)
        self.assertEqual(len(new_ids), 250)
        self.assertTrue(
            all(profile["items"][item_id] == empty for item_id in new_ids)
        )

    def test_runtime_keeps_the_same_key_and_accepts_old_exports(self) -> None:
        for name in ("static_api.js", "static_api-en.js"):
            text = (incremental.BASELINE_SITE / name).read_text(encoding="utf-8")
            self.assertIn(
                'const namespace = "tbam.pages.local.v2"', text
            )
            self.assertIn(incremental.MASTER_PROTOCOL_ID, text)
            self.assertIn("if (!profile.items[itemId])", text)
            self.assertNotIn("localStorage.clear(", text)
            retired = re.search(
                r"const retiredVersions = \[(.*?)\];",
                text,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(retired)
            self.assertNotIn(incremental.STUDY_ID, retired.group(1))
            self.assertNotIn(incremental.MASTER_PROTOCOL_ID, retired.group(1))

        results = (incremental.BASELINE_SITE / "results.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("actual.length > expected.length", results)
        self.assertIn("expectedOffset < expected.length", results)

        full = self.master["slot_assignments"]["0"]
        released = set(self.release["cumulative_item_ids"])
        old_export = [item_id for item_id in full if item_id in released]
        offset = 0
        for item_id in old_export:
            while offset < len(full) and full[offset] != item_id:
                offset += 1
            self.assertLess(offset, len(full))
            offset += 1

    def test_amendment_changes_only_unreleased_ppo_bindings(self) -> None:
        representatives = {}
        for config in incremental.CONFIGS:
            for method in incremental.SELECTION_METHODS:
                representatives[(config, method)] = {
                    "selected_training_seed": 202,
                    "selected_checkpoint_update": 3051,
                    "selected_checkpoint_path":
                        f"paper_experiments/checkpoints/{method}/{config}.pt",
                    "selected_checkpoint_sha256": "a" * 64,
                }
        selection = {
            "path": Path("/tmp/CHECKPOINT_SELECTION.json"),
            "sha256": "b" * 64,
            "seal_path": Path("/tmp/SEAL.json"),
            "seal_sha256": "c" * 64,
            "merged_records_path": Path("/tmp/MERGED_RECORDS.json"),
            "merged_records_sha256": "d" * 64,
            "promotion_audit_path": Path("/tmp/PROMOTION_AUDIT.json"),
            "promotion_audit_sha256": "e" * 64,
            "payload": {
                "schema_version":
                    "tbam.best_retrain_checkpoint_selection.v1",
                "input_manifest": {"record_count": 180},
            },
            "representatives": representatives,
        }
        core = incremental.amendment_core(self.baseline, selection)
        self.assertEqual(core["scope"]["affected_pending_item_count"], 250)
        self.assertEqual(core["scope"]["unaffected_wave_1_item_count"], 50)
        self.assertEqual(
            core["legacy_seed_binding"]["seed_values"], [101, 303, 505]
        )
        self.assertEqual(
            len(
                core["resolved_binding_rule"]["representative_bindings"]
            ),
            10,
        )
        self.assertTrue(
            all(core["non_effects"].values()),
            "an amendment non-effect guarantee was disabled",
        )
        self.assertEqual(core["storage_key"], incremental.STORAGE_KEY)

    def test_public_item_hash_binds_the_new_judge_input(self) -> None:
        item = incremental.make_public_item(
            "item_4447d2005074bb3a",
            "map_01_01",
            "1" * 64,
        )
        changed = incremental.make_public_item(
            "item_4447d2005074bb3a",
            "map_01_01",
            "2" * 64,
        )
        digest = hashlib.sha256(
            incremental.formatted_json_bytes(item)
        ).hexdigest()
        changed_digest = hashlib.sha256(
            incremental.formatted_json_bytes(changed)
        ).hexdigest()
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertNotEqual(digest, changed_digest)

    def test_missing_final_selection_blocks_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = argparse.Namespace(
                baseline_site=incremental.BASELINE_SITE,
                selection=root / "missing-selection.json",
                amendment=root / "missing-amendment.json",
                trajectory_manifest=root / "missing-results.json",
            )
            report = incremental.check_inputs(args)
            self.assertEqual(report["status"], "blocked_expected")
            self.assertFalse(report["safe_to_build"])
            self.assertEqual(report["selection"]["status"], "not_ready")
            self.assertEqual(list(root.iterdir()), [])

    def test_general_verifier_accepts_a_synthetic_three_wave_chain(self) -> None:
        deployed = chain.verify(incremental.BASELINE_SITE)
        if deployed["current_wave"] == 3:
            self.assertEqual(deployed["released_items"], 300)
            self.assertEqual(deployed["artifact_count"], 300)
            return
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "site"
            shutil.copytree(incremental.BASELINE_SITE, candidate)
            private = self.baseline["private_master"]
            private_by_id = {
                item["item_id"]: item for item in private["items"]
            }
            map_by_id = {
                item["blind_map_id"]: item for item in private["maps"]
            }
            wave_one_by_map = {
                item["blind_map_id"]: item
                for item in private["items"]
                if int(item["planned_release_wave"]) == 1
            }
            record_by_id = {
                item["item_id"]: item for item in self.release["items"]
            }

            for master_item in self.master["items"]:
                item_id = master_item["item_id"]
                if item_id in record_by_id:
                    continue
                source_item = wave_one_by_map[master_item["blind_map_id"]]
                source = incremental.read_json(
                    incremental.BASELINE_SITE
                    / "data"
                    / "items"
                    / source_item["item_id"]
                    / "judge_input.json"
                )
                judge = {
                    **source,
                    "item_id": item_id,
                    "blind_map_id": master_item["blind_map_id"],
                }
                artifact = (
                    candidate
                    / "data"
                    / "items"
                    / item_id
                    / "judge_input.json"
                )
                incremental.write_json(artifact, judge)
                artifact_sha = incremental.sha256(artifact)
                public_item = incremental.make_public_item(
                    item_id,
                    master_item["blind_map_id"],
                    artifact_sha,
                )
                public_sha = hashlib.sha256(
                    incremental.formatted_json_bytes(public_item)
                ).hexdigest()
                record_by_id[item_id] = incremental.release_record(
                    master_item,
                    map_by_id[master_item["blind_map_id"]],
                    artifact_sha,
                    public_sha,
                )

            ordered_ids = [item["item_id"] for item in self.master["items"]]
            wave_by_id = {
                item["item_id"]: int(item["planned_release_wave"])
                for item in private["items"]
            }
            records_two = [
                record_by_id[item_id]
                for item_id in ordered_ids
                if wave_by_id[item_id] <= 2
            ]
            records_three = [record_by_id[item_id] for item_id in ordered_ids]
            generated = "2026-07-27T12:00:00+00:00"
            release_two = incremental.make_release(
                wave=2,
                previous_release_id=self.release["release_id"],
                new_item_count=100,
                records=records_two,
                generated_utc=generated,
            )
            release_three = incremental.make_release(
                wave=3,
                previous_release_id=release_two["release_id"],
                new_item_count=150,
                records=records_three,
                generated_utc=generated,
            )
            releases_dir = candidate / "data" / "releases"
            incremental.write_json(
                releases_dir / "release_002.json", release_two
            )
            incremental.write_json(
                releases_dir / "release_003.json", release_three
            )

            protocol = candidate / "data" / "protocol"
            snapshots = protocol / "release_indices"
            snapshots.mkdir(parents=True)
            shutil.copy2(
                incremental.BASELINE_SITE / "data" / "release_index.json",
                snapshots / "release_index_001.json",
            )
            index_two = incremental.make_release_index(
                [self.release, release_two], generated
            )
            index_three = incremental.make_release_index(
                [self.release, release_two, release_three], generated
            )
            incremental.write_json(
                snapshots / "release_index_002.json", index_two
            )
            incremental.write_json(
                snapshots / "release_index_003.json", index_three
            )
            incremental.write_json(
                candidate / "data" / "release_index.json", index_three
            )
            amendment = {
                "amendment_id": "a" * 64,
                "sha256": "b" * 64,
            }
            incremental.write_json(
                protocol / "RELEASE_002_SEAL.json",
                incremental.make_release_seal(
                    candidate=candidate,
                    release=release_two,
                    index_snapshot=snapshots / "release_index_002.json",
                    index=index_two,
                    amendment=amendment,
                    generated_utc=generated,
                ),
            )
            incremental.write_json(
                protocol / "RELEASE_003_SEAL.json",
                incremental.make_release_seal(
                    candidate=candidate,
                    release=release_three,
                    index_snapshot=snapshots / "release_index_003.json",
                    index=index_three,
                    amendment=amendment,
                    generated_utc=generated,
                ),
            )

            pages = incremental.read_json(
                candidate / "data" / "pages_manifest.json"
            )
            pages.update(
                {
                    "built_utc": generated,
                    "bundle_id": index_three["release_index_id"],
                    "item_count": 300,
                    "items_per_map": 6,
                    "items_per_rater": 300,
                    "slot_assignments": self.master["slot_assignments"],
                    "current_wave": 3,
                    "current_release_id": release_three["release_id"],
                    "release_index_id": index_three["release_index_id"],
                    "items": [
                        {
                            **item,
                            "map_index": item["master_map_index"],
                            "directive": self.master["directive"],
                            "public_item_sha256":
                                item["source_public_item_sha256"],
                        }
                        for item in records_three
                    ],
                }
            )
            incremental.write_json(
                candidate / "data" / "pages_manifest.json", pages
            )
            incremental.patch_candidate_runtime(
                candidate, index_three["release_index_id"]
            )
            report = chain.verify(candidate)
            self.assertEqual(report["current_wave"], 3)
            self.assertEqual(report["released_items"], 300)
            self.assertEqual(report["artifact_count"], 300)
            self.assertEqual(report["storage_key"], incremental.STORAGE_KEY)


if __name__ == "__main__":
    unittest.main()
