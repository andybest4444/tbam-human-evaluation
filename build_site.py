#!/usr/bin/env python3
"""Build and verify the static TBAM GitHub Pages pilot.

The generated site intentionally contains only public, blinded judge inputs.
It never copies videos, contact sheets, SQLite files, tokens, or private
method mappings.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_PORTAL = ROOT.parent / "human_evaluation_portal"
DEFAULT_ARTIFACT_ROOT = (
    ROOT.parent
    / "paper_experiments"
    / "blind_artifacts"
    / "s6_v1"
    / "public"
)
DEFAULT_SITE = ROOT / "site"
EXPECTED_PUBLIC_MANIFEST_SHA256 = (
    "318dc8b5edf6476f7daf8f9bbf5f2c9e2e64b67dcac6af4fcdb3520eed97be7c"
)
EXPECTED_COLLECTION_PROTOCOL_ID = (
    "52c87e87c4e62f89f4036db1d403d160a9a0add9f9e3a9df669002b47f1377f2"
)
EXPECTED_BUNDLE_ID = (
    "f5b39d33b436bdd0d30dd61b6612ad0419e150c065f90da57aa249e7e117abf5"
)
STUDY_ID = "tbam_s6_human_pages_pilot_v1"
PRESENTATION_MEDIUM = "static_route_maps_pages_v1"
ASSIGNMENT_RULE_ID = "latin_rotation_r_plus_map_mod_8_v1"
RUNTIME_FILES = (
    "index.html",
    "app.js",
    "styles.css",
    "static_api.js",
    "results.html",
    "results.js",
    "results.css",
)
COLLECTION_RUNTIME_FILES = (
    "index.html",
    "app.js",
    "styles.css",
    "static_api.js",
)
SOURCE_MIRROR_FILES = (
    ".nojekyll",
    "static_api.js",
    "results.html",
    "results.js",
    "results.css",
)
START_RUBRIC_HTML = """
            <section class="start-rubric" aria-labelledby="start-rubric-title">
              <header class="start-rubric-heading">
                <p class="kicker">统一尺度 · 所有项目适用</p>
                <h2 id="start-rubric-title">评判标准</h2>
                <p>
                  总体请直接回答完整指令，不要机械地把四个解释维度相加；
                  四维仅用于解释。
                </p>
              </header>
              <article class="start-rubric-item overall">
                <div>
                  <p class="start-rubric-primary-label">主要终点</p>
                  <h3>总体 Overall</h3>
                  <p>综合任务完成情况与可见路线行为，判断哪条路线更符合完整指令。</p>
                </div>
              </article>
              <ol class="start-rubric-grid" aria-label="四个解释维度">
                <li class="start-rubric-item">
                  <span aria-hidden="true">01</span>
                  <div>
                    <h3>地形 Terrain</h3>
                    <p>哪条路线更少出现与到达目标无关的不必要升降？</p>
                  </div>
                </li>
                <li class="start-rubric-item">
                  <span aria-hidden="true">02</span>
                  <div>
                    <h3>掩体 Cover</h3>
                    <p>哪条路线更合理地利用隐蔽区域，而非无理由暴露？</p>
                  </div>
                </li>
                <li class="start-rubric-item">
                  <span aria-hidden="true">03</span>
                  <div>
                    <h3>协同 Coordination</h3>
                    <p>比较同编号时间标记：暴露时是否分散、隐蔽时是否聚集？</p>
                  </div>
                </li>
                <li class="start-rubric-item">
                  <span aria-hidden="true">04</span>
                  <div>
                    <h3>效率 Efficiency</h3>
                    <p>在不牺牲上述要求时，哪条路线更直接、少停留或绕行？</p>
                  </div>
                </li>
              </ol>
              <p class="start-rubric-note">
                <strong>作答原则：</strong>
                两条路线相当时可选“平局”；单个解释维度证据不足时可选“不清楚”。
                只依据匿名路线图中的可见证据，不猜测生成方法。
              </p>
            </section>
"""
START_RUBRIC_CSS = """

/* GitHub Pages start-page evaluation criteria. */
.start-rubric {
  max-width: 690px;
  margin-top: 26px;
  padding: 22px;
  border: 1px solid rgba(18, 60, 59, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.66);
  box-shadow: 0 14px 38px rgba(31, 50, 47, 0.08);
}

.start-rubric-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  column-gap: 18px;
  align-items: end;
}

.start-rubric-heading .kicker {
  grid-column: 1 / -1;
  margin-bottom: 7px;
}

.start-rubric-heading h2 {
  margin: 0;
  color: var(--forest);
  font-size: 25px;
  letter-spacing: -0.025em;
}

.start-rubric-heading > p:last-child {
  max-width: 450px;
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  text-align: right;
}

.start-rubric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 9px;
  margin: 9px 0 0;
  padding: 0;
  list-style: none;
}

.start-rubric-item {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 10px;
  min-height: 94px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: rgba(250, 250, 246, 0.86);
}

.start-rubric-item.overall {
  display: block;
  min-height: 0;
  margin-top: 17px;
  border-color: rgba(27, 87, 83, 0.2);
  background: var(--mint-light);
}

.start-rubric-item > span {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: white;
  color: var(--forest-2);
  font-size: 10px;
  font-weight: 850;
}

.start-rubric-item h3 {
  margin: 3px 0 5px;
  color: var(--forest);
  font-size: 14px;
}

.start-rubric-primary-label {
  margin: 0 0 4px;
  color: var(--forest-2);
  font-size: 11px;
  font-weight: 850;
  letter-spacing: 0.14em;
}

.start-rubric-item p {
  margin: 0;
  color: #59645f;
  font-size: 13px;
  line-height: 1.55;
}

.start-rubric-item .start-rubric-primary-label {
  margin: 0 0 4px;
  color: var(--forest-2);
  font-size: 11px;
}

.start-rubric-note {
  margin: 14px 0 0;
  padding-top: 13px;
  border-top: 1px solid var(--line);
  color: #56615d;
  font-size: 13px;
  line-height: 1.65;
}

.start-rubric-note strong {
  color: var(--forest);
}

@media (max-width: 760px) {
  .start-rubric {
    padding: 18px;
  }

  .start-rubric-heading {
    display: block;
  }

  .start-rubric-heading > p:last-child {
    margin-top: 8px;
    text-align: left;
  }

  .start-rubric-grid {
    grid-template-columns: 1fr;
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portal", type=Path, default=DEFAULT_PORTAL)
    parser.add_argument(
        "--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT
    )
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        handle.write("\n")


def repository_commit(path: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and len(value) == 40 else None


def checked_public_items(
    artifact_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = artifact_root / "public_manifest.json"
    if sha256(manifest_path) != EXPECTED_PUBLIC_MANIFEST_SHA256:
        raise RuntimeError("the S6 public manifest is not the frozen source")
    manifest = load_json(manifest_path)
    records = manifest.get("items")
    if (
        manifest.get("schema_version") != "tbam.blind_artifacts_public.v1"
        or manifest.get("status") != "complete_frozen_artifacts"
        or manifest.get("design_id") != "s6_design_v1"
        or manifest.get("item_count") != 240
        or not isinstance(records, list)
        or len(records) != 240
    ):
        raise RuntimeError("the S6 public manifest is incomplete")

    map_ids = sorted({str(record.get("blind_map_id")) for record in records})
    if len(map_ids) != 30:
        raise RuntimeError("expected exactly 30 blind maps")
    map_index = {map_id: index for index, map_id in enumerate(map_ids)}
    item_position: dict[str, int] = defaultdict(int)
    checked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        item_id = str(record.get("item_id"))
        blind_map_id = str(record.get("blind_map_id"))
        if item_id in seen or blind_map_id not in map_index:
            raise RuntimeError("duplicate item or invalid blind map")
        seen.add(item_id)
        position = item_position[blind_map_id]
        item_position[blind_map_id] += 1
        if position >= 8:
            raise RuntimeError("a blind map contains more than eight items")

        public_item_path = artifact_root / str(record["public_item_path"])
        if (
            not public_item_path.is_file()
            or sha256(public_item_path) != record["public_item_sha256"]
        ):
            raise RuntimeError(f"public item changed: {item_id}")
        public_item = load_json(public_item_path)
        if (
            public_item.get("schema_version") != "tbam.blind_item_public.v1"
            or public_item.get("item_id") != item_id
            or public_item.get("blind_map_id") != blind_map_id
            or bool(public_item.get("both_completed"))
            != bool(record.get("both_completed"))
        ):
            raise RuntimeError(f"invalid public item: {item_id}")
        artifacts = public_item.get("artifacts")
        if not isinstance(artifacts, dict):
            raise RuntimeError(f"missing artifact declaration: {item_id}")
        required = {"A_video", "B_video", "contact_sheet", "judge_input"}
        if set(artifacts) != required:
            raise RuntimeError(f"unexpected artifact set: {item_id}")
        for name in required:
            source = artifact_root / str(artifacts[name]["path"])
            if not source.is_file() or sha256(source) != artifacts[name]["sha256"]:
                raise RuntimeError(f"public artifact changed: {item_id}/{name}")

        judge_source = artifact_root / str(artifacts["judge_input"]["path"])
        judge_payload = load_json(judge_source)
        if (
            judge_payload.get("schema_version")
            != "tbam.blind_judge_input.v1"
            or judge_payload.get("item_id") != item_id
            or set(judge_payload.get("routes", {})) != {"A", "B"}
        ):
            raise RuntimeError(f"invalid judge input: {item_id}")
        checked.append(
            {
                "item_id": item_id,
                "blind_map_id": blind_map_id,
                "both_completed": bool(record["both_completed"]),
                "map_index": map_index[blind_map_id],
                "item_index": position,
                "directive": str(public_item["directive"]),
                "judge_source": judge_source,
                "judge_input_path": (
                    f"data/items/{item_id}/judge_input.json"
                ),
                "public_item_sha256": str(record["public_item_sha256"]),
                "input_artifact_sha256": {
                    "A_video": str(artifacts["A_video"]["sha256"]),
                    "B_video": str(artifacts["B_video"]["sha256"]),
                    "judge_input": str(artifacts["judge_input"]["sha256"]),
                },
            }
        )
    if set(item_position.values()) != {8}:
        raise RuntimeError("every blind map must contain exactly eight items")
    return manifest, checked


def transformed_index(portal: Path) -> str:
    source = (portal / "web" / "index.html").read_text(encoding="utf-8")
    source = source.replace('href="/styles.css"', 'href="styles.css"')
    marker = '<script src="/app.js" defer></script>'
    replacement = (
        '<script src="static_api.js" defer></script>\n'
        '    <script src="app.js" defer></script>'
    )
    if marker not in source:
        raise RuntimeError("portal script tag changed unexpectedly")
    source = source.replace(marker, replacement)
    viewport = '<meta name="viewport" content="width=device-width, initial-scale=1">'
    source = source.replace(
        viewport,
        viewport
        + '\n    <link rel="icon" href="data:image/svg+xml;base64,'
        + "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9"
        + "IjAgMCA2NCA2NCI+PHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiByeD0iMTIi"
        + "IGZpbGw9IiMxZTJiM2IiLz48cGF0aCBkPSJNMTMgNDQgMjggMTdsOSAxNyA3LTEw"
        + "IDggMjBaIiBmaWxsPSIjZmZmIi8+PC9zdmc+\">"
        + '\n    <meta name="robots" content="noindex,nofollow">'
        + '\n    <meta name="referrer" content="no-referrer">'
        + '\n    <meta http-equiv="Content-Security-Policy" '
        + "content=\"default-src 'self'; script-src 'self'; "
        + "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
        + "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        + "form-action 'self'\">",
    )
    source = source.replace(
        "<title>TBAM 匿名路线人工评判</title>",
        "<title>TBAM 匿名路线人工评判 · Pages Pilot</title>",
    )
    rubric_marker = "          <div class=\"auth-panel\">"
    rubric_replacement = (
        START_RUBRIC_HTML
        + "          </div>\n\n"
        + rubric_marker
    )
    auth_hero_close = "          </div>\n\n" + rubric_marker
    if source.count(auth_hero_close) != 1:
        raise RuntimeError("portal auth hero changed unexpectedly")
    source = source.replace(auth_hero_close, rubric_replacement, 1)
    if 'href="/' in source or 'src="/' in source:
        raise RuntimeError("generated Pages index still contains a root URL")
    return source


def transformed_styles(portal: Path) -> str:
    source = (portal / "web" / "styles.css").read_text(encoding="utf-8")
    return source.rstrip() + START_RUBRIC_CSS.rstrip() + "\n"


def transformed_app(portal: Path) -> str:
    source = (portal / "web" / "app.js").read_text(encoding="utf-8")
    storage_before = "    state.config.study_id,\n"
    storage_after = "    state.config.storage_namespace_id,\n"
    if source.count(storage_before) != 1:
        raise RuntimeError("portal local-draft namespace changed unexpectedly")
    source = source.replace(storage_before, storage_after, 1)

    recovery_before = """    let draft = item.draft;
    if (!draft) {
      try {
        const local = JSON.parse(localStorage.getItem(localDraftKey(itemId)));
        if (local?.payload) {
          draft = { ...local, revision: 0 };
          toast("已恢复此浏览器中尚未同步的本地草稿。");
        }
      } catch {
        // Ignore malformed recovery data.
      }
    }
    applyDraft(draft);
    setSaveState(
      draft?.revision ? `草稿已同步 · v${draft.revision}` : "尚无服务器草稿",
      Boolean(draft?.revision),
    );
"""
    recovery_after = """    let draft = item.draft;
    let recoveredLocalDraft = false;
    try {
      const local = JSON.parse(localStorage.getItem(localDraftKey(itemId)));
      const localTime = Date.parse(local?.saved_utc || "") || 0;
      const storedTime = Date.parse(draft?.updated_utc || "") || 0;
      if (local?.payload && (!draft || localTime > storedTime)) {
        draft = {
          ...local,
          revision: Number(draft?.revision || 0),
        };
        recoveredLocalDraft = true;
        toast("已恢复此浏览器中更新的未同步草稿。");
      }
    } catch {
      // Ignore malformed recovery data.
    }
    applyDraft(draft);
    if (recoveredLocalDraft) {
      setSaveState("正在保存恢复的浏览器草稿…", false);
      window.setTimeout(() => saveDraft(false), 0);
    } else {
      setSaveState(
        draft?.revision ? `草稿已同步 · v${draft.revision}` : "尚无浏览器草稿",
        Boolean(draft?.revision),
      );
    }
"""
    if source.count(recovery_before) != 1:
        raise RuntimeError("portal local-draft recovery changed unexpectedly")
    return source.replace(recovery_before, recovery_after, 1)


def stable_collection_binding(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "study_id": manifest["study_id"],
        "study_mode": manifest["study_mode"],
        "storage_mode": manifest["storage_mode"],
        "presentation_medium": manifest["presentation_medium"],
        "source_public_manifest_sha256": (
            manifest["source_public_manifest_sha256"]
        ),
        "source_design_id": manifest["source_design_id"],
        "assignment_rule_id": manifest["assignment_rule_id"],
        "rater_slot_min": manifest["rater_slot_min"],
        "rater_slot_max": manifest["rater_slot_max"],
        "item_count": manifest["item_count"],
        "map_count": manifest["map_count"],
        "items_per_map": manifest["items_per_map"],
        "items_per_rater": manifest["items_per_rater"],
        "judgments_per_item_if_all_slots_complete": manifest[
            "judgments_per_item_if_all_slots_complete"
        ],
        "both_completed_count": manifest["both_completed_count"],
        "directive": manifest["directive"],
        "consent_version": manifest["consent_version"],
        "consent_text_sha256": manifest["consent_text_sha256"],
        "collection_runtime_sha256": {
            name: manifest["runtime_sha256"][name]
            for name in COLLECTION_RUNTIME_FILES
        },
        "items": [
            {
                "item_id": item["item_id"],
                "blind_map_id": item["blind_map_id"],
                "both_completed": item["both_completed"],
                "map_index": item["map_index"],
                "item_index": item["item_index"],
                "directive": item["directive"],
                "judge_input_path": item["judge_input_path"],
                "public_item_sha256": item["public_item_sha256"],
                "input_artifact_sha256": item["input_artifact_sha256"],
            }
            for item in manifest["items"]
        ],
    }


def collection_digest(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            stable_collection_binding(manifest),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def stable_bundle_binding(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "collection_protocol_id": manifest["collection_protocol_id"],
        "runtime_sha256": manifest["runtime_sha256"],
    }


def bundle_digest(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            stable_bundle_binding(manifest),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def build_site(portal: Path, artifact_root: Path, site: Path) -> None:
    portal = portal.expanduser().resolve()
    artifact_root = artifact_root.expanduser().resolve()
    site = site.expanduser().resolve()
    if site in {ROOT, ROOT.parent, Path("/")}:
        raise RuntimeError("refusing to use a source or filesystem root as --site")
    if site.exists():
        marker = site / ".tbam-pages-generated"
        old_manifest = site / "data" / "pages_manifest.json"
        if not marker.is_file() and not old_manifest.is_file():
            raise RuntimeError("refusing to replace an unrecognized site directory")
    manifest, items = checked_public_items(artifact_root)
    staging = site.with_name(f".{site.name}.building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    (staging / "index.html").write_text(
        transformed_index(portal), encoding="utf-8"
    )
    (staging / "app.js").write_text(
        transformed_app(portal), encoding="utf-8"
    )
    (staging / "styles.css").write_text(
        transformed_styles(portal), encoding="utf-8"
    )
    for name in (
        ".nojekyll",
        "static_api.js",
        "results.html",
        "results.js",
        "results.css",
    ):
        source = ROOT / "src" / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, staging / name)
    (staging / ".tbam-pages-generated").write_text(
        "generated by build_site.py\n", encoding="utf-8"
    )

    public_items: list[dict[str, Any]] = []
    for item in items:
        destination = staging / item["judge_input_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item["judge_source"], destination)
        if sha256(destination) != item["input_artifact_sha256"]["judge_input"]:
            raise RuntimeError(f"copied judge input changed: {item['item_id']}")
        public_items.append(
            {
                key: value
                for key, value in item.items()
                if key != "judge_source"
            }
        )

    runtime_hashes = {
        name: sha256(staging / name) for name in RUNTIME_FILES
    }
    consent_text = (ROOT / "src" / "PILOT_TEST_NOTICE.txt").read_text(
        encoding="utf-8"
    )
    consent_text_sha256 = hashlib.sha256(
        consent_text.encode("utf-8")
    ).hexdigest()
    pages_manifest = {
        "schema_version": "tbam.github_pages_bundle.v1",
        "status": "complete_browser_local_pilot",
        "study_id": STUDY_ID,
        "study_mode": "pilot",
        "storage_mode": "browser_local",
        "presentation_medium": PRESENTATION_MEDIUM,
        "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "portal_source_commit": repository_commit(portal),
        "source_design_id": str(manifest["design_id"]),
        "source_public_manifest_sha256": (
            EXPECTED_PUBLIC_MANIFEST_SHA256
        ),
        "source_public_manifest_generated_utc": str(
            manifest["generated_utc"]
        ),
        "assignment_rule_id": ASSIGNMENT_RULE_ID,
        "rater_slot_min": 0,
        "rater_slot_max": 39,
        "item_count": 240,
        "map_count": 30,
        "items_per_map": 8,
        "items_per_rater": 30,
        "judgments_per_item_if_all_slots_complete": 5,
        "both_completed_count": int(manifest["both_completed_count"]),
        "directive": str(manifest["directive"]),
        "consent_version": "pages-pilot-notice-v2",
        "consent_text": consent_text,
        "consent_text_sha256": consent_text_sha256,
        "runtime_sha256": runtime_hashes,
        "items": public_items,
    }
    pages_manifest["collection_protocol_id"] = collection_digest(
        pages_manifest
    )
    pages_manifest["bundle_id"] = bundle_digest(pages_manifest)
    if (
        pages_manifest["collection_protocol_id"]
        != EXPECTED_COLLECTION_PROTOCOL_ID
        or pages_manifest["bundle_id"] != EXPECTED_BUNDLE_ID
    ):
        raise RuntimeError(
            "generated collection or bundle differs from the sealed IDs; "
            f"collection={pages_manifest['collection_protocol_id']}, "
            f"bundle={pages_manifest['bundle_id']}; review the change and "
            "explicitly rotate the expected IDs"
        )
    write_json(staging / "data" / "pages_manifest.json", pages_manifest)

    verify_site(staging)
    if site.exists():
        shutil.rmtree(site)
    staging.rename(site)
    report = verify_site(site)
    print(json.dumps(report, indent=2, sort_keys=True))


def verify_site(site: Path) -> dict[str, Any]:
    site = site.expanduser().resolve()
    manifest_path = site / "data" / "pages_manifest.json"
    manifest = load_json(manifest_path)
    items = manifest.get("items")
    if (
        manifest.get("schema_version") != "tbam.github_pages_bundle.v1"
        or manifest.get("status") != "complete_browser_local_pilot"
        or manifest.get("study_id") != STUDY_ID
        or manifest.get("study_mode") != "pilot"
        or manifest.get("storage_mode") != "browser_local"
        or manifest.get("presentation_medium") != PRESENTATION_MEDIUM
        or manifest.get("source_design_id") != "s6_design_v1"
        or manifest.get("assignment_rule_id") != ASSIGNMENT_RULE_ID
        or manifest.get("source_public_manifest_sha256")
        != EXPECTED_PUBLIC_MANIFEST_SHA256
        or manifest.get("rater_slot_min") != 0
        or manifest.get("rater_slot_max") != 39
        or manifest.get("item_count") != 240
        or manifest.get("map_count") != 30
        or manifest.get("items_per_map") != 8
        or manifest.get("items_per_rater") != 30
        or manifest.get("judgments_per_item_if_all_slots_complete") != 5
        or manifest.get("consent_version") != "pages-pilot-notice-v2"
        or manifest.get("collection_protocol_id")
        != collection_digest(manifest)
        or manifest.get("collection_protocol_id")
        != EXPECTED_COLLECTION_PROTOCOL_ID
        or manifest.get("bundle_id") != bundle_digest(manifest)
        or manifest.get("bundle_id") != EXPECTED_BUNDLE_ID
        or not isinstance(items, list)
        or len(items) != 240
    ):
        raise RuntimeError("invalid generated Pages manifest")
    if (
        hashlib.sha256(
            str(manifest.get("consent_text", "")).encode("utf-8")
        ).hexdigest()
        != manifest.get("consent_text_sha256")
        or manifest.get("consent_text")
        != (ROOT / "src" / "PILOT_TEST_NOTICE.txt").read_text(
            encoding="utf-8"
        )
    ):
        raise RuntimeError("generated consent text hash mismatch")
    runtime_hashes = manifest.get("runtime_sha256")
    if not isinstance(runtime_hashes, dict) or set(runtime_hashes) != set(
        RUNTIME_FILES
    ):
        raise RuntimeError("generated runtime hash set is incomplete")
    for name in RUNTIME_FILES:
        runtime_path = site / name
        if (
            not runtime_path.is_file()
            or sha256(runtime_path) != runtime_hashes[name]
        ):
            raise RuntimeError(f"generated runtime changed: {name}")
    for name in SOURCE_MIRROR_FILES:
        source_path = ROOT / "src" / name
        generated_path = site / name
        if (
            not source_path.is_file()
            or not generated_path.is_file()
            or sha256(source_path) != sha256(generated_path)
        ):
            raise RuntimeError(f"generated source mirror changed: {name}")
    index = (site / "index.html").read_text(encoding="utf-8")
    if 'href="/' in index or 'src="/' in index:
        raise RuntimeError("generated Pages index contains a root URL")
    seen: set[str] = set()
    map_counts: dict[str, int] = defaultdict(int)
    expected_files = {
        ".nojekyll",
        ".tbam-pages-generated",
        "data/pages_manifest.json",
        *RUNTIME_FILES,
    }
    judge_bytes = 0
    for item in items:
        item_id = str(item["item_id"])
        blind_map_id = str(item.get("blind_map_id"))
        hashes = item.get("input_artifact_sha256")
        if (
            item_id in seen
            or not item_id.startswith("item_")
            or not blind_map_id.startswith("map_")
            or not isinstance(item.get("both_completed"), bool)
            or not isinstance(item.get("map_index"), int)
            or not isinstance(item.get("item_index"), int)
            or not isinstance(item.get("directive"), str)
            or not isinstance(hashes, dict)
            or set(hashes) != {"A_video", "B_video", "judge_input"}
            or any(
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in hashes.values()
            )
        ):
            raise RuntimeError(f"invalid generated item metadata: {item_id}")
        seen.add(item_id)
        map_counts[blind_map_id] += 1
        relative = Path(str(item["judge_input_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe judge input path: {item_id}")
        path = (site / relative).resolve()
        try:
            path.relative_to(site)
        except ValueError as error:
            raise RuntimeError(
                f"judge input escapes site root: {item_id}"
            ) from error
        expected = item["input_artifact_sha256"]["judge_input"]
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"generated judge input mismatch: {item_id}")
        expected_files.add(relative.as_posix())
        judge_bytes += path.stat().st_size
    if len(map_counts) != 30 or set(map_counts.values()) != {8}:
        raise RuntimeError("generated assignment map grouping is invalid")
    if manifest.get("both_completed_count") != sum(
        item["both_completed"] for item in items
    ):
        raise RuntimeError("generated both-completed count is invalid")
    map_ids = sorted(map_counts)
    assignment_counts = {item_id: 0 for item_id in seen}
    for map_index, map_id in enumerate(map_ids):
        candidates = [
            item for item in items if item["blind_map_id"] == map_id
        ]
        if any(
            item["map_index"] != map_index
            or item["item_index"] != item_index
            for item_index, item in enumerate(candidates)
        ):
            raise RuntimeError(
                f"generated assignment order is invalid: {map_id}"
            )
        for slot in range(40):
            selected = candidates[(slot + map_index) % 8]
            assignment_counts[selected["item_id"]] += 1
    if set(assignment_counts.values()) != {5}:
        raise RuntimeError("generated slot coverage is not exactly five")
    forbidden_suffixes = {
        ".mp4",
        ".sqlite",
        ".sqlite3",
        ".wal",
        ".pem",
        ".key",
    }
    forbidden_names = {"private_mapping.json", "private_manifest.json"}
    actual_files = set()
    for path in site.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"symlink is forbidden in Pages site: {path}")
        if not path.is_file():
            continue
        actual_files.add(path.relative_to(site).as_posix())
        if path.suffix.lower() in forbidden_suffixes or path.name in forbidden_names:
            raise RuntimeError(f"forbidden file in Pages site: {path}")
        if "token" in path.name.lower():
            raise RuntimeError(f"token-like file in Pages site: {path}")
    if actual_files != expected_files:
        extra = sorted(actual_files - expected_files)
        missing = sorted(expected_files - actual_files)
        raise RuntimeError(
            f"generated Pages file set mismatch; extra={extra}, missing={missing}"
        )
    return {
        "status": "verified_pages_site",
        "site": str(site),
        "study_id": manifest["study_id"],
        "bundle_id": manifest["bundle_id"],
        "source_public_manifest_sha256": (
            manifest["source_public_manifest_sha256"]
        ),
        "items": len(items),
        "judge_input_bytes": judge_bytes,
        "site_files": sum(1 for path in site.rglob("*") if path.is_file()),
        "site_bytes": sum(
            path.stat().st_size for path in site.rglob("*") if path.is_file()
        ),
    }


def main() -> int:
    args = parse_args()
    if args.verify_only:
        print(
            json.dumps(
                verify_site(args.site),
                indent=2,
                sort_keys=True,
            )
        )
    else:
        build_site(args.portal, args.artifact_root, args.site)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
