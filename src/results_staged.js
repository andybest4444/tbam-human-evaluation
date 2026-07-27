"use strict";

const MANIFEST_URL = "./data/pages_manifest.json";
const MANIFEST_SCHEMA = "tbam.github_pages_bundle.v1";
const PAGES_EXPORT_SCHEMA = "tbam.pages_human_rater_export.v2";
const JUDGMENT_SCHEMA = "tbam.blind_pairwise_choice.v1";
const MERGED_EXPORT_SCHEMA = "tbam.merged_pairwise_choices.v1";
const EXPECTED_STUDY_ID =
  "tbam_e9_best_models_staged_pages_v1";
const EXPECTED_DESIGN_ID = "e9_human_pairwise_v2";
const EXPECTED_ASSIGNMENT_RULE =
  "complete_master_catalog_round_robin_5slots_v1";
const EXPECTED_RELEASE_RULE =
  "cumulative_append_only_artifact_binding_v1";
const EXPECTED_FULL_ITEM_COUNT = 300;
const EXPECTED_MAP_COUNT = 50;
const MAX_ITEMS_PER_MAP = 6;
const EXPECTED_RATER_SLOT_MIN = 0;
const EXPECTED_RATER_SLOT_MAX = 4;
const MAX_DURATION_SECONDS = 43200;
const PAGES_EXPORT_FIELDS = [
  "schema_version",
  "study_id",
  "judge_system_id",
  "rater_slot",
  "presentation_medium",
  "collection_protocol_id",
  "registered_bundle_id",
  "bundle_id",
  "source_public_manifest_sha256",
  "assignment_rule_id",
  "assignment_item_ids",
  "full_master_item_count",
  "current_wave",
  "current_release_id",
  "release_index_id",
  "exported_utc",
  "judgments",
];
const JUDGMENT_FIELDS = [
  "schema_version",
  "study_id",
  "item_id",
  "judge_type",
  "judge_system_id",
  "presentation_variant",
  "presented_routes",
  "input_artifact_sha256",
  "control_item",
  "attention_check_passed",
  "choice",
  "started_utc",
  "completed_utc",
  "duration_seconds",
];
const ARTIFACT_HASH_FIELDS = ["judge_input"];
const PAIRWISE_CHOICES = new Set(["A", "B"]);
const HASH_PATTERN = /^[a-f0-9]{64}$/i;
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$/;
const ISO_TIMESTAMP_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

const state = {
  manifest: null,
  itemById: new Map(),
  expectedPerRater: 0,
  selectedFileCount: 0,
  validExports: [],
  latestExports: [],
  judgments: [],
  raterRows: [],
  itemRows: [],
};

const elements = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  loadManifest();
});

function cacheElements() {
  const ids = [
    "manifest-state",
    "manifest-message",
    "file-input",
    "drop-zone",
    "clear-button",
    "messages",
    "metric-files",
    "metric-files-detail",
    "metric-raters",
    "metric-judgments",
    "metric-complete",
    "metric-complete-detail",
    "metric-coverage",
    "metric-coverage-detail",
    "rater-body",
    "item-body",
    "download-judgments",
    "download-wrapper",
    "download-raters",
    "download-items",
    "bundle-label",
  ];
  for (const id of ids) {
    elements[id] = document.getElementById(id);
  }
}

function bindEvents() {
  elements["file-input"].addEventListener("change", (event) => {
    importFiles(Array.from(event.target.files || []));
  });
  elements["clear-button"].addEventListener("click", clearResults);
  elements["download-judgments"].addEventListener(
    "click",
    downloadMergedJudgments,
  );
  elements["download-wrapper"].addEventListener(
    "click",
    downloadMergedWrapper,
  );
  elements["download-raters"].addEventListener("click", downloadRaterProgress);
  elements["download-items"].addEventListener("click", downloadItemSummary);

  const dropZone = elements["drop-zone"];
  for (const eventName of ["dragenter", "dragover"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      if (!elements["file-input"].disabled) {
        dropZone.classList.add("dragging");
      }
    });
  }
  for (const eventName of ["dragleave", "drop"]) {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.remove("dragging");
    });
  }
  dropZone.addEventListener("drop", (event) => {
    if (!elements["file-input"].disabled) {
      importFiles(Array.from(event.dataTransfer?.files || []));
    }
  });
}

async function loadManifest() {
  setManifestStatus("loading", "正在加载公开实验清单…");
  try {
    const response = await fetch(MANIFEST_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const manifest = await response.json();
    validateManifest(manifest);

    state.manifest = manifest;
    state.itemById = new Map(
      manifest.items.map((item) => [item.item_id, item]),
    );
    state.expectedPerRater = inferExpectedPerRater(manifest);

    elements["file-input"].disabled = false;
    elements["drop-zone"].classList.remove("disabled");
    setManifestStatus(
      "ready",
      `清单已验证 · ${manifest.items.length.toLocaleString()} 个项目`,
    );
    elements["bundle-label"].textContent =
      `Bundle ${manifest.bundle_id} · ${manifest.presentation_medium} · ` +
      `source ${manifest.source_public_manifest_sha256.slice(0, 12)}…`;
    render();
  } catch (error) {
    elements["file-input"].disabled = true;
    elements["drop-zone"].classList.add("disabled");
    setManifestStatus("error", "公开实验清单加载失败");
    showMessages([
      {
        level: "error",
        text:
          `无法读取或验证 ${MANIFEST_URL}：${errorMessage(error)}。` +
          "请通过 GitHub Pages 或本地 HTTP 服务器打开本站。",
      },
    ]);
  }
}

function validateManifest(manifest) {
  assertPlainObject(manifest, "pages_manifest.json");
  if (manifest.schema_version !== MANIFEST_SCHEMA) {
    throw new Error(`不支持的清单版本 ${String(manifest.schema_version)}`);
  }
  assertNonEmptyString(manifest.study_id, "manifest.study_id");
  if (manifest.study_id !== EXPECTED_STUDY_ID) {
    throw new Error("manifest.study_id 不是当前 E9 人工评判版本");
  }
  if (manifest.source_design_id !== EXPECTED_DESIGN_ID) {
    throw new Error("manifest.source_design_id 不是当前 E9 盲化设计");
  }
  assertSha256(manifest.bundle_id, "manifest.bundle_id");
  assertSha256(
    manifest.collection_protocol_id,
    "manifest.collection_protocol_id",
  );
  assertNonEmptyString(
    manifest.presentation_medium,
    "manifest.presentation_medium",
  );
  assertSha256(
    manifest.source_public_manifest_sha256,
    "manifest.source_public_manifest_sha256",
  );
  assertNonEmptyString(
    manifest.assignment_rule_id,
    "manifest.assignment_rule_id",
  );
  if (
    !Number.isInteger(manifest.item_count) ||
    manifest.item_count <= 0 ||
    !Number.isInteger(manifest.map_count) ||
    manifest.map_count <= 0 ||
    !Number.isInteger(manifest.items_per_map) ||
    manifest.items_per_map <= 0 ||
    manifest.map_count !== EXPECTED_MAP_COUNT ||
    manifest.items_per_map > MAX_ITEMS_PER_MAP ||
    manifest.map_count * manifest.items_per_map !== manifest.item_count ||
    manifest.items_per_rater !== manifest.item_count ||
    manifest.full_item_count !== EXPECTED_FULL_ITEM_COUNT ||
    manifest.judgments_per_item_if_all_slots_complete !== 5 ||
    manifest.assignment_rule_id !== EXPECTED_ASSIGNMENT_RULE ||
    manifest.release_rule_id !== EXPECTED_RELEASE_RULE ||
    manifest.rater_slot_min !== EXPECTED_RATER_SLOT_MIN ||
    manifest.rater_slot_max !== EXPECTED_RATER_SLOT_MAX
  ) {
    throw new Error(
      "manifest 的 Pages 分配参数不完整或内部不一致",
    );
  }
  if (!Array.isArray(manifest.items) || manifest.items.length === 0) {
    throw new Error("manifest.items 必须是非空数组");
  }
  if (manifest.items.length !== manifest.item_count) {
    throw new Error("manifest.items 数量必须与 item_count 一致");
  }

  const seen = new Set();
  for (const [index, item] of manifest.items.entries()) {
    assertPlainObject(item, `manifest.items[${index}]`);
    assertSafeId(item.item_id, `manifest.items[${index}].item_id`);
    assertSafeId(item.blind_map_id, `manifest.items[${index}].blind_map_id`);
    if (seen.has(item.item_id)) {
      throw new Error(`清单中项目编号重复：${item.item_id}`);
    }
    seen.add(item.item_id);
    validateArtifactHashes(
      item.input_artifact_sha256,
      `manifest.items[${index}].input_artifact_sha256`,
    );
  }
  validateAssignmentCatalog(manifest);
}

function inferExpectedPerRater(manifest) {
  return manifest.items_per_rater;
}

function validateAssignmentCatalog(manifest) {
  const mapIds = sortedMapIds(manifest);
  if (mapIds.length !== manifest.map_count) {
    throw new Error("manifest 的盲化地图数量与 map_count 不一致");
  }
  for (const [mapIndex, mapId] of mapIds.entries()) {
    const candidates = manifest.items.filter(
      (item) => item.blind_map_id === mapId,
    );
    if (candidates.length !== manifest.items_per_map) {
      throw new Error(
        `manifest 地图 ${mapId} 的项目数与 items_per_map 不一致`,
      );
    }
    for (const [itemIndex, item] of candidates.entries()) {
      if (item.map_index !== mapIndex || item.item_index !== itemIndex) {
        throw new Error(
          `manifest 地图 ${mapId} 的 map_index/item_index 顺序无效`,
        );
      }
    }
  }
  const expectedIds = new Set(manifest.items.map((item) => item.item_id));
  const expectedSlots = new Set(
    Array.from(
      {
        length:
          manifest.rater_slot_max - manifest.rater_slot_min + 1,
      },
      (_, index) => String(manifest.rater_slot_min + index),
    ),
  );
  if (
    !manifest.slot_assignments ||
    typeof manifest.slot_assignments !== "object" ||
    Array.isArray(manifest.slot_assignments) ||
    !sameSet(new Set(Object.keys(manifest.slot_assignments)), expectedSlots)
  ) {
    throw new Error("manifest.slot_assignments 与声明的席位范围不一致");
  }
  for (
    let slot = manifest.rater_slot_min;
    slot <= manifest.rater_slot_max;
    slot += 1
  ) {
    const assigned = manifest.slot_assignments[String(slot)];
    if (
      !Array.isArray(assigned) ||
      assigned.length !== manifest.items_per_rater ||
      !sameSet(new Set(assigned), expectedIds)
    ) {
      throw new Error(`席位 ${slot} 未完整覆盖当前目录`);
    }
  }
}

function sortedMapIds(manifest) {
  return [...new Set(manifest.items.map((item) => item.blind_map_id))].sort();
}

function sameSet(left, right) {
  return (
    left.size === right.size &&
    [...left].every((value) => right.has(value))
  );
}

function deriveAssignmentItemIds(manifest, raterSlot) {
  return [...manifest.slot_assignments[String(raterSlot)]];
}

async function importFiles(files) {
  if (!state.manifest || files.length === 0) {
    return;
  }

  elements["file-input"].value = "";
  state.selectedFileCount = files.length;
  const messages = [];
  const validExports = [];

  for (const [index, file] of files.entries()) {
    if (!file.name.toLowerCase().endsWith(".json")) {
      messages.push({
        level: "error",
        text: `${file.name}：不是 JSON 文件，已跳过。`,
      });
      continue;
    }
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const normalized = validateAndNormalizeExport(payload, file, index);
      validExports.push(normalized);
    } catch (error) {
      messages.push({
        level: "error",
        text: `${file.name}：${errorMessage(error)}`,
      });
    }
  }

  const selection = selectMonotonicExports(validExports);
  state.validExports = selection.acceptedExports;
  state.latestExports = selection.latestExports;
  state.judgments = state.latestExports
    .flatMap((entry) => entry.judgments)
    .sort(compareJudgments);
  state.raterRows = buildRaterRows(state.latestExports);
  state.itemRows = buildItemRows(state.judgments);

  messages.push(...selection.messages);
  const replaced =
    state.validExports.length - state.latestExports.length;
  if (state.validExports.length > 0) {
    messages.unshift({
      level: "info",
      text:
        `已验证并接受 ${state.validExports.length} 个文件，保留 ` +
        `${state.latestExports.length} 位评判者覆盖项目最多且时间最新的导出。`,
    });
  }
  if (replaced > 0) {
    messages.push({
      level: "warning",
      text: `${replaced} 个较早的重复导出未进入汇总。`,
    });
  }
  if (state.validExports.length === 0 && messages.length === 0) {
    messages.push({ level: "warning", text: "没有可汇总的有效文件。" });
  }

  showMessages(messages);
  render();
}

function validateAndNormalizeExport(payload, file, inputIndex) {
  assertExactKeys(payload, PAGES_EXPORT_FIELDS, "导出文件");
  if (payload.schema_version !== PAGES_EXPORT_SCHEMA) {
    throw new Error(`不支持的导出版本 ${String(payload.schema_version)}`);
  }
  if (payload.study_id !== state.manifest.study_id) {
    throw new Error(
      `study_id 不匹配（应为 ${state.manifest.study_id}）`,
    );
  }

  assertSha256(payload.bundle_id, "bundle_id");
  assertSha256(payload.registered_bundle_id, "registered_bundle_id");
  assertSha256(payload.collection_protocol_id, "collection_protocol_id");
  if (
    payload.collection_protocol_id !==
    state.manifest.collection_protocol_id
  ) {
    throw new Error("collection_protocol_id 与当前收集协议不匹配");
  }
  if (payload.presentation_medium !== state.manifest.presentation_medium) {
    throw new Error("presentation_medium 与当前清单不匹配");
  }
  assertSha256(
    payload.source_public_manifest_sha256,
    "source_public_manifest_sha256",
  );
  if (
    payload.source_public_manifest_sha256 !==
    state.manifest.source_public_manifest_sha256
  ) {
    throw new Error("source_public_manifest_sha256 与当前清单不匹配");
  }
  if (
    !Number.isInteger(payload.rater_slot) ||
    payload.rater_slot < state.manifest.rater_slot_min ||
    payload.rater_slot > state.manifest.rater_slot_max
  ) {
    throw new Error("rater_slot 不在当前 manifest 声明的范围内");
  }
  const expectedRaterId =
    `human_pages_${String(payload.rater_slot + 1).padStart(2, "0")}`;
  if (payload.judge_system_id !== expectedRaterId) {
    throw new Error(
      `judge_system_id 必须与席位一致（应为 ${expectedRaterId}）`,
    );
  }
  if (payload.assignment_rule_id !== state.manifest.assignment_rule_id) {
    throw new Error("assignment_rule_id 与当前清单不匹配");
  }
  if (payload.full_master_item_count !== EXPECTED_FULL_ITEM_COUNT) {
    throw new Error("full_master_item_count 与冻结 master 不匹配");
  }
  if (
    !Number.isInteger(payload.current_wave) ||
    payload.current_wave < 1 ||
    payload.current_wave > state.manifest.current_wave
  ) {
    throw new Error("current_wave 不在当前 release 链范围内");
  }
  assertSha256(payload.current_release_id, "current_release_id");
  assertSha256(payload.release_index_id, "release_index_id");

  const expectedAssignmentItemIds = deriveAssignmentItemIds(
    state.manifest,
    payload.rater_slot,
  );
  validateAssignmentItemIds(
    payload.assignment_item_ids,
    expectedAssignmentItemIds,
  );
  if (!Array.isArray(payload.judgments)) {
    throw new Error("judgments 必须是数组");
  }
  const exportedTime = parseTimestamp(payload.exported_utc, "exported_utc");

  const seenItems = new Set();
  const judgments = payload.judgments.map((judgment, index) => {
    const validated = validateJudgment(
      judgment,
      payload.judge_system_id,
      index,
    );
    if (seenItems.has(validated.item_id)) {
      throw new Error(`judgments 中项目重复：${validated.item_id}`);
    }
    seenItems.add(validated.item_id);
    return validated;
  });

  const assignmentItemIds = [...payload.assignment_item_ids];
  const assignmentSet = new Set(assignmentItemIds);
  for (const itemId of seenItems) {
    if (!assignmentSet.has(itemId)) {
      throw new Error(`判断项目不在该评判者分配中：${itemId}`);
    }
  }

  return {
    schemaVersion: payload.schema_version,
    judgeSystemId: payload.judge_system_id,
    raterSlot: payload.rater_slot,
    bundleId: payload.bundle_id,
    registeredBundleId: payload.registered_bundle_id,
    collectionProtocolId: payload.collection_protocol_id,
    exportedUtc: payload.exported_utc,
    exportedTime,
    fileName: file.name,
    fileLastModified: Number(file.lastModified) || 0,
    inputIndex,
    sourceBinding: "manifest",
    assignmentRuleId: payload.assignment_rule_id,
    assignmentItemIds,
    currentWave: payload.current_wave,
    currentReleaseId: payload.current_release_id,
    releaseIndexId: payload.release_index_id,
    judgments,
  };
}

function validateAssignmentItemIds(actual, expected) {
  if (!Array.isArray(actual)) {
    throw new Error("assignment_item_ids 必须是数组");
  }
  if (
    actual.length < 1 ||
    actual.length > expected.length ||
    new Set(actual).size !== actual.length
  ) {
    throw new Error("assignment_item_ids 不是有效的已发布目录");
  }
  let expectedOffset = 0;
  for (const [index, actualItemId] of actual.entries()) {
    assertSafeId(actualItemId, `assignment_item_ids[${index}]`);
    while (
      expectedOffset < expected.length &&
      expected[expectedOffset] !== actualItemId
    ) {
      expectedOffset += 1;
    }
    if (expectedOffset >= expected.length) {
      throw new Error(
        `assignment_item_ids 不是当前 append-only 目录的有序子序列（第 ${index + 1} 项）`,
      );
    }
    expectedOffset += 1;
  }
}

function validateJudgment(judgment, expectedRater, index) {
  const label = `judgments[${index}]`;
  assertExactKeys(judgment, JUDGMENT_FIELDS, label);
  if (judgment.schema_version !== JUDGMENT_SCHEMA) {
    throw new Error(`${label}.schema_version 不受支持`);
  }
  if (judgment.study_id !== state.manifest.study_id) {
    throw new Error(`${label}.study_id 不匹配`);
  }
  if (judgment.judge_type !== "human") {
    throw new Error(`${label}.judge_type 必须为 human`);
  }
  if (judgment.judge_system_id !== expectedRater) {
    throw new Error(`${label}.judge_system_id 与文件顶层不一致`);
  }
  assertSafeId(judgment.item_id, `${label}.item_id`);
  const manifestItem = state.itemById.get(judgment.item_id);
  if (!manifestItem) {
    throw new Error(`${label}.item_id 不在公开清单中`);
  }
  if (judgment.presentation_variant !== "canonical") {
    throw new Error(`${label}.presentation_variant 必须为 canonical`);
  }
  assertExactKeys(
    judgment.presented_routes,
    ["A", "B"],
    `${label}.presented_routes`,
  );
  if (
    judgment.presented_routes.A !== "A" ||
    judgment.presented_routes.B !== "B"
  ) {
    throw new Error(`${label}.presented_routes 必须精确为 {A: "A", B: "B"}`);
  }
  validateArtifactHashes(
    judgment.input_artifact_sha256,
    `${label}.input_artifact_sha256`,
    manifestItem.input_artifact_sha256,
  );
  if (judgment.control_item !== false) {
    throw new Error(`${label}.control_item 必须为 false`);
  }
  if (judgment.attention_check_passed !== null) {
    throw new Error(`${label}.attention_check_passed 必须为 null`);
  }

  if (!PAIRWISE_CHOICES.has(judgment.choice)) {
    throw new Error(`${label}.choice 必须为 A 或 B`);
  }

  const startedTime = parseTimestamp(
    judgment.started_utc,
    `${label}.started_utc`,
  );
  const completedTime = parseTimestamp(
    judgment.completed_utc,
    `${label}.completed_utc`,
  );
  if (completedTime < startedTime) {
    throw new Error(`${label}.completed_utc 不能早于 started_utc`);
  }
  if (
    typeof judgment.duration_seconds !== "number" ||
    !Number.isFinite(judgment.duration_seconds) ||
    judgment.duration_seconds <= 0 ||
    judgment.duration_seconds > MAX_DURATION_SECONDS
  ) {
    throw new Error(
      `${label}.duration_seconds 必须是大于 0 且不超过 43200 的有限数`,
    );
  }
  return judgment;
}

function validateArtifactHashes(binding, label, expected = null) {
  assertExactKeys(binding, ARTIFACT_HASH_FIELDS, label);
  for (const field of ARTIFACT_HASH_FIELDS) {
    assertSha256(binding[field], `${label}.${field}`);
    if (expected !== null && binding[field] !== expected[field]) {
      throw new Error(`${label}.${field} 与公开清单不匹配`);
    }
  }
}

function selectMonotonicExports(validExports) {
  const byRater = new Map();
  for (const entry of validExports) {
    if (!byRater.has(entry.judgeSystemId)) {
      byRater.set(entry.judgeSystemId, []);
    }
    byRater.get(entry.judgeSystemId).push(entry);
  }

  const acceptedExports = [];
  const latestExports = [];
  const messages = [];
  for (const [judgeSystemId, entries] of byRater) {
    try {
      const latest = validateMonotonicHistory(entries);
      acceptedExports.push(...entries);
      latestExports.push(latest);
    } catch (error) {
      messages.push({
        level: "error",
        text:
          `${judgeSystemId}：${errorMessage(error)}；` +
          `该评判者的 ${entries.length} 个导出已全部排除（fail closed）。`,
      });
    }
  }
  latestExports.sort((left, right) =>
    left.judgeSystemId.localeCompare(right.judgeSystemId),
  );
  return { acceptedExports, latestExports, messages };
}

function validateMonotonicHistory(entries) {
  if (entries.length === 1) {
    return entries[0];
  }
  const histories = entries.map((entry) => ({
    entry,
    itemIds: new Set(
      entry.judgments.map((judgment) => judgment.item_id),
    ),
  }));

  for (let leftIndex = 0; leftIndex < histories.length; leftIndex += 1) {
    for (
      let rightIndex = leftIndex + 1;
      rightIndex < histories.length;
      rightIndex += 1
    ) {
      const left = histories[leftIndex];
      const right = histories[rightIndex];
      const leftIsSubset = isItemSetSubset(
        left.itemIds,
        right.itemIds,
      );
      const rightIsSubset = isItemSetSubset(
        right.itemIds,
        left.itemIds,
      );
      if (!leftIsSubset && !rightIsSubset) {
        throw new Error(
          `检测到非单调分叉（${left.entry.fileName} 与 ` +
          `${right.entry.fileName} 的判断集合互不包含）`,
        );
      }
    }
  }

  histories.sort((left, right) =>
    compareExportHistory(left.entry, right.entry),
  );
  return histories[histories.length - 1].entry;
}

function compareExportHistory(left, right) {
  return (
    left.judgments.length - right.judgments.length ||
    left.exportedTime - right.exportedTime ||
    left.fileLastModified - right.fileLastModified ||
    left.inputIndex - right.inputIndex
  );
}

function isItemSetSubset(subset, superset) {
  return [...subset].every((itemId) => superset.has(itemId));
}

function compareJudgments(left, right) {
  return (
    left.judge_system_id.localeCompare(right.judge_system_id) ||
    left.item_id.localeCompare(right.item_id)
  );
}

function buildRaterRows(latestExports) {
  return latestExports.map((entry) => {
    const expected = state.expectedPerRater;
    const count = entry.judgments.length;
    return {
      judgeSystemId: entry.judgeSystemId,
      exportedUtc: entry.exportedUtc,
      count,
      expected,
      percent: expected === 0 ? 0 : Math.min(100, (count / expected) * 100),
      complete: expected > 0 && count >= expected,
      fileName: entry.fileName,
      sourceBinding: entry.sourceBinding,
    };
  });
}

function buildItemRows(judgments) {
  const rows = state.manifest.items.map((item) => ({
    itemId: item.item_id,
    blindMapId: item.blind_map_id,
    mapIndex: numericOrInfinity(item.map_index),
    itemIndex: numericOrInfinity(item.item_index),
    total: 0,
    choiceA: 0,
    choiceB: 0,
  }));
  const byId = new Map(rows.map((row) => [row.itemId, row]));
  for (const judgment of judgments) {
    const row = byId.get(judgment.item_id);
    row.total += 1;
    row[`choice${judgment.choice}`] += 1;
  }
  return rows.sort(
    (left, right) =>
      left.mapIndex - right.mapIndex ||
      left.itemIndex - right.itemIndex ||
      left.blindMapId.localeCompare(right.blindMapId) ||
      left.itemId.localeCompare(right.itemId),
  );
}

function render() {
  renderMetrics();
  renderRaters();
  renderItems();
  const hasResults = state.latestExports.length > 0;
  elements["clear-button"].disabled =
    state.selectedFileCount === 0 && !hasResults;
  elements["download-judgments"].disabled = !hasResults;
  elements["download-wrapper"].disabled = !hasResults;
  elements["download-raters"].disabled = !hasResults;
  elements["download-items"].disabled = !hasResults;
}

function renderMetrics() {
  const validFileCount = state.validExports.length;
  const judgmentCount = state.judgments.length;
  const completeCount = state.raterRows.filter((row) => row.complete).length;
  const depths = state.itemRows
    .map((row) => row.total)
    .sort((left, right) => left - right);
  const minimumDepth = depths[0] || 0;
  const maximumDepth = depths[depths.length - 1] || 0;
  const middle = Math.floor(depths.length / 2);
  const medianDepth =
    depths.length === 0
      ? 0
      : depths.length % 2 === 1
        ? depths[middle]
        : (depths[middle - 1] + depths[middle]) / 2;
  const atLeastFour = state.itemRows.filter((row) => row.total >= 4).length;
  const atLeastFive = state.itemRows.filter((row) => row.total >= 5).length;

  elements["metric-files"].textContent = validFileCount.toLocaleString();
  elements["metric-files-detail"].textContent =
    state.selectedFileCount === 0
      ? "尚未导入"
      : `${state.selectedFileCount.toLocaleString()} 个已选择`;
  elements["metric-raters"].textContent =
    state.latestExports.length.toLocaleString();
  elements["metric-judgments"].textContent = judgmentCount.toLocaleString();
  elements["metric-complete"].textContent = completeCount.toLocaleString();
  elements["metric-complete-detail"].textContent =
    `每人目标 ${state.expectedPerRater.toLocaleString()} 项`;
  elements["metric-coverage"].textContent =
    `${minimumDepth} / ${medianDepth} / ${maximumDepth}`;
  elements["metric-coverage-detail"].textContent =
    `${atLeastFour} 项达到4票 · ${atLeastFive} 项达到5票`;
}

function renderRaters() {
  const body = elements["rater-body"];
  body.replaceChildren();
  if (state.raterRows.length === 0) {
    body.appendChild(emptyTableRow(6, "导入结果后显示评判者进度。"));
    return;
  }
  for (const row of state.raterRows) {
    const tr = document.createElement("tr");
    tr.appendChild(textCell(row.judgeSystemId, "mono"));
    tr.appendChild(textCell(formatTimestamp(row.exportedUtc)));
    tr.appendChild(textCell(`${row.count} / ${row.expected}`, "number-cell"));

    const progressCell = document.createElement("td");
    progressCell.className = "progress-cell";
    const progressLine = document.createElement("div");
    progressLine.className = "progress-line";
    const track = document.createElement("span");
    track.className = "progress-track";
    const fill = document.createElement("span");
    fill.className = "progress-fill";
    fill.style.width = `${row.percent}%`;
    track.appendChild(fill);
    const percent = document.createElement("span");
    percent.textContent = formatPercent(row.percent);
    progressLine.append(track, percent);
    progressCell.appendChild(progressLine);
    tr.appendChild(progressCell);

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${row.complete ? "complete" : "incomplete"}`;
    badge.textContent = row.complete ? "已完成" : "进行中";
    statusCell.appendChild(badge);
    tr.appendChild(statusCell);
    tr.appendChild(textCell(row.fileName));
    body.appendChild(tr);
  }
}

function renderItems() {
  const body = elements["item-body"];
  body.replaceChildren();
  if (state.latestExports.length === 0) {
    body.appendChild(emptyTableRow(5, "导入结果后显示项目计数。"));
    return;
  }
  for (const row of state.itemRows) {
    const tr = document.createElement("tr");
    tr.appendChild(textCell(row.itemId, "mono"));
    tr.appendChild(textCell(row.blindMapId, "mono"));
    tr.appendChild(textCell(row.total, "number-cell"));
    tr.appendChild(textCell(row.choiceA, "number-cell"));
    tr.appendChild(textCell(row.choiceB, "number-cell"));
    body.appendChild(tr);
  }
}

function showMessages(messages) {
  const container = elements["messages"];
  container.replaceChildren();
  container.hidden = messages.length === 0;
  for (const message of messages) {
    const row = document.createElement("div");
    row.className = `message ${message.level}`;
    row.textContent = message.text;
    container.appendChild(row);
  }
}

function setManifestStatus(status, message) {
  elements["manifest-state"].classList.remove("ready", "error");
  if (status === "ready" || status === "error") {
    elements["manifest-state"].classList.add(status);
  }
  elements["manifest-message"].textContent = message;
}

function clearResults() {
  state.selectedFileCount = 0;
  state.validExports = [];
  state.latestExports = [];
  state.judgments = [];
  state.raterRows = [];
  state.itemRows = [];
  elements["file-input"].value = "";
  showMessages([]);
  render();
}

function downloadMergedJudgments() {
  const lines = state.judgments.map((judgment) => JSON.stringify(judgment));
  downloadText(
    `tbam_merged_judgments_${dateStamp()}.jsonl`,
    lines.length > 0 ? `${lines.join("\n")}\n` : "",
    "application/x-ndjson;charset=utf-8",
  );
}

function downloadMergedWrapper() {
  const manifest = state.manifest;
  const payload = {
    schema_version: MERGED_EXPORT_SCHEMA,
    merged_utc: new Date().toISOString(),
    study_id: manifest.study_id,
    bundle_id: manifest.bundle_id,
    collection_protocol_id: manifest.collection_protocol_id,
    presentation_medium: manifest.presentation_medium,
    source_public_manifest_sha256:
      manifest.source_public_manifest_sha256,
    source_manifest: {
      schema_version: manifest.schema_version,
      path: MANIFEST_URL,
      built_utc: manifest.built_utc,
      bundle_id: manifest.bundle_id,
      collection_protocol_id: manifest.collection_protocol_id,
      source_public_manifest_sha256:
        manifest.source_public_manifest_sha256,
    },
    assignment_rule_id: manifest.assignment_rule_id,
    source_bundle_ids: [
      ...new Set(state.latestExports.map((entry) => entry.bundleId)),
    ].sort(),
    registered_bundle_ids: [
      ...new Set(
        state.latestExports.map((entry) => entry.registeredBundleId),
      ),
    ].sort(),
    rater_exports: state.latestExports.map((entry) => ({
      schema_version: entry.schemaVersion,
      judge_system_id: entry.judgeSystemId,
      rater_slot: entry.raterSlot,
      bundle_id: entry.bundleId,
      registered_bundle_id: entry.registeredBundleId,
      collection_protocol_id: entry.collectionProtocolId,
      exported_utc: entry.exportedUtc,
      assignment_rule_id: entry.assignmentRuleId,
      assignment_item_ids: [...entry.assignmentItemIds],
      current_wave: entry.currentWave,
      current_release_id: entry.currentReleaseId,
      release_index_id: entry.releaseIndexId,
      judgment_count: entry.judgments.length,
      source_file: entry.fileName,
      source_file_last_modified_ms: entry.fileLastModified,
    })),
    judgments: state.judgments,
  };
  downloadText(
    `tbam_merged_results_${dateStamp()}.json`,
    `${JSON.stringify(payload, null, 2)}\n`,
    "application/json;charset=utf-8",
  );
}

function downloadRaterProgress() {
  const headers = [
    "judge_system_id",
    "exported_utc",
    "valid_judgments",
    "expected_judgments",
    "completion_percent",
    "complete",
    "source_binding",
    "source_file",
  ];
  const rows = state.raterRows.map((row) => [
    row.judgeSystemId,
    row.exportedUtc,
    row.count,
    row.expected,
    round(row.percent, 3),
    row.complete,
    row.sourceBinding,
    row.fileName,
  ]);
  downloadCsv(`tbam_rater_progress_${dateStamp()}.csv`, headers, rows);
}

function downloadItemSummary() {
  const headers = [
    "item_id",
    "blind_map_id",
    "judgment_count",
    "choice_A",
    "choice_B",
  ];
  const rows = state.itemRows.map((row) => [
    row.itemId,
    row.blindMapId,
    row.total,
    row.choiceA,
    row.choiceB,
  ]);
  downloadCsv(`tbam_item_summary_${dateStamp()}.csv`, headers, rows);
}

function downloadCsv(fileName, headers, rows) {
  const csv = [
    headers.map(csvCell).join(","),
    ...rows.map((row) => row.map(csvCell).join(",")),
  ].join("\r\n");
  downloadText(fileName, `\ufeff${csv}\r\n`, "text/csv;charset=utf-8");
}

function csvCell(value) {
  let text = String(value ?? "");
  if (/^[=+\-@\t\r]/.test(text)) {
    text = `'${text}`;
  }
  return `"${text.replaceAll('"', '""')}"`;
}

function downloadText(fileName, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function assertPlainObject(value, label) {
  if (!isPlainObject(value)) {
    throw new Error(`${label} 必须是对象`);
  }
}

function assertExactKeys(value, expectedKeys, label) {
  assertPlainObject(value, label);
  const actualKeys = Object.keys(value);
  const expected = new Set(expectedKeys);
  const missing = expectedKeys.filter((key) => !Object.hasOwn(value, key));
  const unexpected = actualKeys.filter((key) => !expected.has(key));
  if (
    actualKeys.length !== expectedKeys.length ||
    missing.length > 0 ||
    unexpected.length > 0
  ) {
    const details = [];
    if (missing.length > 0) {
      details.push(`缺少 ${missing.join(", ")}`);
    }
    if (unexpected.length > 0) {
      details.push(`多出 ${unexpected.join(", ")}`);
    }
    throw new Error(
      `${label} 字段必须精确为 ${expectedKeys.join(", ")}` +
      (details.length > 0 ? `（${details.join("；")}）` : ""),
    );
  }
}

function isPlainObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    (Object.getPrototypeOf(value) === Object.prototype ||
      Object.getPrototypeOf(value) === null)
  );
}

function assertNonEmptyString(value, label) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${label} 必须是非空字符串`);
  }
}

function assertSafeId(value, label) {
  assertNonEmptyString(value, label);
  if (!ID_PATTERN.test(value)) {
    throw new Error(`${label} 格式无效`);
  }
}

function assertSha256(value, label) {
  if (typeof value !== "string" || !HASH_PATTERN.test(value)) {
    throw new Error(`${label} 必须是 64 位 SHA-256`);
  }
}

function parseTimestamp(value, label) {
  assertNonEmptyString(value, label);
  if (!ISO_TIMESTAMP_PATTERN.test(value)) {
    throw new Error(`${label} 必须是带 Z 或 UTC 偏移的 ISO 8601 时间`);
  }
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    throw new Error(`${label} 不是有效时间`);
  }
  return timestamp;
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (isPlainObject(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function textCell(value, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  cell.textContent = String(value);
  return cell;
}

function emptyTableRow(columns, message) {
  const row = document.createElement("tr");
  row.className = "empty-row";
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.textContent = message;
  row.appendChild(cell);
  return row;
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function formatPercent(value) {
  return `${round(value, 1).toLocaleString("zh-CN", {
    maximumFractionDigits: 1,
  })}%`;
}

function numericOrInfinity(value) {
  return Number.isInteger(value) ? value : Number.POSITIVE_INFINITY;
}

function round(value, digits) {
  const factor = 10 ** digits;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function dateStamp() {
  return new Date().toISOString().replaceAll(/[:.]/g, "-");
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}
