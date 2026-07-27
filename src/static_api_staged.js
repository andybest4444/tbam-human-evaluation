(() => {
  "use strict";

  const scriptUrl = new URL(document.currentScript.src);
  const siteBase = new URL("./", scriptUrl);
  const nativeFetch = window.fetch.bind(window);
  const namespace = "tbam.pages.local.v2";
  const expectedMasterProtocolId = "__MASTER_PROTOCOL_ID__";
  const expectedReleaseIndexId = "__RELEASE_INDEX_ID__";
  const useEnglishConsent = __USE_ENGLISH_CONSENT__;
  const expectedStudyId =
    "tbam_e9_best_models_staged_pages_v1";
  const expectedDesignId = "e9_human_pairwise_v2";
  const expectedPresentationMedium =
    "static_route_maps_bilingual_staged_pages_v1";
  const expectedAssignmentRule =
    "complete_master_catalog_round_robin_5slots_v1";
  const expectedReleaseRule =
    "cumulative_append_only_artifact_binding_v1";
  const expectedConsentVersion =
    "pages-e9-best-models-staged-consent-v1";
  const expectedFullItemCount = 300;
  const expectedMapCount = 50;
  const expectedItemsPerMap = 6;
  const retiredVersions = [
    {
      studyId: "tbam_s6_human_forced_choice_full_catalog_pages_v1",
      protocolId:
        "fb40f2bd42dff9e6e1e1b108a9f53bb90c56cc39b06f50ae664f9c8a435d32d3",
    },
    {
      studyId: "tbam_e9_fixed_budget_human_pairwise_pages_v1",
      protocolId:
        "d44029836227f788c6cf35a1ae68a8392092e52b00fa22a99f868bd4843cf60a",
    },
    {
      studyId: "tbam_e9_fixed_budget_human_pairwise_pages_v2",
      protocolId:
        "9dcbcf36e3a192e8f34569e8ccf0cc7575c89a2f0d1c0416a3d8330f7c864bae",
    },
  ];
  const retiredPurgeMarker =
    `${namespace}:formal-v3-retired-progress-purged:v1`;
  const encoder = new TextEncoder();
  const legacyJudgmentSchema = "tbam.blind_pairwise_choice.v1";
  const tieJudgmentSchema = "tbam.blind_pairwise_choice.v2";
  let manifestPromise;

  function purgeRetiredProgress() {
    try {
      const localKeys = Array.from(
        { length: localStorage.length },
        (_, index) => localStorage.key(index),
      ).filter(Boolean);
      for (const key of localKeys) {
        const isRetired = retiredVersions.some(({ studyId, protocolId }) =>
          key === `${namespace}:${studyId}:${protocolId}:store` ||
          key.startsWith(`tbam-draft:${studyId}:${protocolId}:`),
        );
        if (isRetired) {
          localStorage.removeItem(key);
        }
      }
      for (const { studyId, protocolId } of retiredVersions) {
        sessionStorage.removeItem(
          `${namespace}:${studyId}:${protocolId}:session`,
        );
      }
      localStorage.setItem(retiredPurgeMarker, "1");
    } catch {
      // The regular storage checks will report an actionable browser error.
    }
  }

  purgeRetiredProgress();

  class LocalApiError extends Error {
    constructor(status, message, detail = undefined) {
      super(message);
      this.status = status;
      this.detail = detail;
    }
  }

  function now() {
    return new Date().toISOString();
  }

  function jsonResponse(payload, status = 200) {
    return new Response(JSON.stringify(payload), {
      status,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    });
  }

  function errorResponse(error) {
    const status = error instanceof LocalApiError ? error.status : 500;
    const payload = {
      error: status === 401 ? "authentication_required" : "local_pages_error",
      message: error?.message || "浏览器本地存储操作失败。",
    };
    if (error instanceof LocalApiError && error.detail !== undefined) {
      payload.detail = error.detail;
    }
    return jsonResponse(payload, status);
  }

  async function fetchJson(relativePath) {
    const response = await nativeFetch(new URL(relativePath, siteBase), {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Pages manifest 请求失败（${response.status}）`);
    }
    return response.json();
  }

  function validateMaster(master) {
    if (
      master?.schema_version !== "tbam.human_staged_master.public.v1" ||
      master?.status !== "frozen_staged_collection_wave1" ||
      master?.study_id !== expectedStudyId ||
      master?.source_design_id !== expectedDesignId ||
      master?.master_protocol_id !== expectedMasterProtocolId ||
      master?.presentation_medium !== expectedPresentationMedium ||
      master?.assignment_rule_id !== expectedAssignmentRule ||
      master?.release_rule_id !== expectedReleaseRule ||
      master?.consent_version !== expectedConsentVersion ||
      master?.map_count !== expectedMapCount ||
      master?.items_per_map !== expectedItemsPerMap ||
      master?.full_item_count !== expectedFullItemCount ||
      master?.rater_slot_min !== 0 ||
      master?.rater_slot_max !== 4 ||
      master?.judgments_per_item_if_all_slots_complete !== 5 ||
      !Array.isArray(master?.items) ||
      master.items.length !== expectedFullItemCount
    ) {
      throw new Error("Pages master assignment 不完整或与冻结协议不一致。");
    }
    const ids = master.items.map((item) => item.item_id);
    const idSet = new Set(ids);
    if (
      idSet.size !== expectedFullItemCount ||
      master.items.some(
        (item) =>
          !/^item_[0-9a-f]{16}$/.test(item.item_id) ||
          !/^map_[0-9]{2}_[0-9]{2}$/.test(item.blind_map_id) ||
          !Number.isInteger(item.master_map_index) ||
          item.master_map_index < 0 ||
          item.master_map_index >= expectedMapCount ||
          !Number.isInteger(item.item_index) ||
          item.item_index < 0 ||
          item.item_index >= expectedItemsPerMap,
      )
    ) {
      throw new Error("Pages master item identity 无效。");
    }
    for (let slot = 0; slot <= 4; slot += 1) {
      const assigned = master.slot_assignments?.[String(slot)];
      if (
        !Array.isArray(assigned) ||
        assigned.length !== expectedFullItemCount ||
        new Set(assigned).size !== expectedFullItemCount ||
        assigned.some((itemId) => !idSet.has(itemId))
      ) {
        throw new Error("Pages master 用户目录分配无效。");
      }
    }
    return { idSet };
  }

  function validateReleaseChain(master, index, releases, masterIds) {
    if (
      index?.schema_version !== "tbam.human_staged_release_index.v1" ||
      index?.status !== master.status ||
      index?.study_id !== expectedStudyId ||
      index?.master_protocol_id !== expectedMasterProtocolId ||
      index?.release_rule_id !== expectedReleaseRule ||
      index?.release_index_id !== expectedReleaseIndexId ||
      !Array.isArray(index?.releases) ||
      index.releases.length < 1 ||
      releases.length !== index.releases.length
    ) {
      throw new Error("Pages release index 不完整或与冻结协议不一致。");
    }
    let previousId = null;
    let previousIds = new Set();
    const immutableArtifacts = new Map();
    releases.forEach((release, offset) => {
      const descriptor = index.releases[offset];
      const expectedWave = offset + 1;
      if (
        release?.schema_version !== "tbam.human_staged_release.v1" ||
        release?.status !== master.status ||
        release?.study_id !== expectedStudyId ||
        release?.master_protocol_id !== expectedMasterProtocolId ||
        release?.release_rule_id !== expectedReleaseRule ||
        release?.wave_number !== expectedWave ||
        descriptor?.wave_number !== expectedWave ||
        descriptor?.release_id !== release.release_id ||
        release?.previous_release_id !== previousId ||
        descriptor?.previous_release_id !== previousId ||
        !Array.isArray(release?.cumulative_item_ids) ||
        !Array.isArray(release?.items) ||
        release.cumulative_item_ids.length !== release.cumulative_item_count ||
        release.items.length !== release.cumulative_item_count ||
        new Set(release.cumulative_item_ids).size !==
          release.cumulative_item_count ||
        release.cumulative_item_count !== descriptor.cumulative_item_count ||
        release.new_item_count !==
          release.cumulative_item_count - previousIds.size
      ) {
        throw new Error(`Pages release wave ${expectedWave} 无效。`);
      }
      const currentIds = new Set(release.cumulative_item_ids);
      if (
        [...previousIds].some((itemId) => !currentIds.has(itemId)) ||
        [...currentIds].some((itemId) => !masterIds.has(itemId))
      ) {
        throw new Error(`Pages release wave ${expectedWave} 不是 append-only。`);
      }
      const releaseById = new Map();
      for (const item of release.items) {
        const hash = item?.input_artifact_sha256?.judge_input;
        if (
          !currentIds.has(item?.item_id) ||
          releaseById.has(item.item_id) ||
          !/^[0-9a-f]{64}$/.test(hash || "") ||
          item.artifact_status !== "released_immutable"
        ) {
          throw new Error(`Pages release item 无效：${item?.item_id}`);
        }
        const binding = stableStringify({
          judge_input_path: item.judge_input_path,
          input_artifact_sha256: item.input_artifact_sha256,
          map_size: item.map_size,
          agent_count: item.agent_count,
          horizon: item.horizon,
        });
        if (
          immutableArtifacts.has(item.item_id) &&
          immutableArtifacts.get(item.item_id) !== binding
        ) {
          throw new Error(`已发布项目被修改：${item.item_id}`);
        }
        immutableArtifacts.set(item.item_id, binding);
        releaseById.set(item.item_id, item);
      }
      if ([...currentIds].some((itemId) => !releaseById.has(itemId))) {
        throw new Error(`Pages release wave ${expectedWave} 缺少项目制品。`);
      }
      previousId = release.release_id;
      previousIds = currentIds;
    });
    const current = releases.at(-1);
    if (
      index.current_wave !== current.wave_number ||
      index.current_release_id !== current.release_id ||
      index.cumulative_item_count !== current.cumulative_item_count
    ) {
      throw new Error("Pages current release 指针无效。");
    }
    return current;
  }

  async function loadManifest() {
    if (!manifestPromise) {
      manifestPromise = Promise.all([
        fetchJson("data/master_assignment.json"),
        fetchJson("data/release_index.json"),
      ]).then(async ([master, index]) => {
        const { idSet } = validateMaster(master);
        const releases = await Promise.all(
          index.releases.map((entry) => fetchJson(entry.path)),
        );
        const current = validateReleaseChain(
          master,
          index,
          releases,
          idSet,
        );
        const readyIds = new Set(current.cumulative_item_ids);
        const masterById = new Map(
          master.items.map((item) => [item.item_id, item]),
        );
        const items = current.items.map((item) => ({
          ...item,
          blind_map_id: masterById.get(item.item_id).blind_map_id,
          map_index: masterById.get(item.item_id).master_map_index,
          item_index: masterById.get(item.item_id).item_index,
          directive: master.directive,
          public_item_sha256: item.source_public_item_sha256,
        }));
        const itemsPerMap = items.length / expectedMapCount;
        if (
          !Number.isInteger(itemsPerMap) ||
          itemsPerMap < 1 ||
          itemsPerMap > expectedItemsPerMap
        ) {
          throw new Error("当前 release 没有按地图均衡发布。");
        }
        const slotAssignments = Object.fromEntries(
          Object.entries(master.slot_assignments).map(([slot, assigned]) => [
            slot,
            assigned.filter((itemId) => readyIds.has(itemId)),
          ]),
        );
        const manifest = {
          schema_version: "tbam.github_pages_bundle.v1",
          status: "complete_browser_local_collection",
          study_id: master.study_id,
          study_mode: master.study_mode,
          storage_mode: "browser_local",
          source_design_id: master.source_design_id,
          presentation_medium: master.presentation_medium,
          assignment_rule_id: master.assignment_rule_id,
          release_rule_id: master.release_rule_id,
          collection_protocol_id: master.master_protocol_id,
          source_public_manifest_sha256: master.master_protocol_id,
          bundle_id: index.release_index_id,
          rater_slot_min: master.rater_slot_min,
          rater_slot_max: master.rater_slot_max,
          item_count: items.length,
          full_item_count: master.full_item_count,
          map_count: expectedMapCount,
          items_per_map: itemsPerMap,
          items_per_rater: items.length,
          judgments_per_item_if_all_slots_complete:
            master.judgments_per_item_if_all_slots_complete,
          slot_assignments: slotAssignments,
          directive: master.directive,
          consent_version: master.consent_version,
          consent_text: useEnglishConsent
            ? master.consent_text_en
            : master.consent_text,
          consent_text_sha256: master.consent_text_sha256,
          items,
          current_wave: current.wave_number,
          current_release_id: current.release_id,
          release_index_id: index.release_index_id,
        };
        for (let slot = 0; slot <= 4; slot += 1) {
          assignedItems(manifest, { rater_slot: slot });
        }
        return manifest;
      });
    }
    return manifestPromise;
  }

  function storeKey(manifest) {
    return (
      `${namespace}:${manifest.study_id}:` +
      `${manifest.collection_protocol_id}:store`
    );
  }

  function sessionKey(manifest) {
    return (
      `${namespace}:${manifest.study_id}:` +
      `${manifest.collection_protocol_id}:session`
    );
  }

  function emptyStore(manifest) {
    return {
      schema_version: "tbam.pages_local_store.v2",
      study_id: manifest.study_id,
      collection_protocol_id: manifest.collection_protocol_id,
      presentation_medium: manifest.presentation_medium,
      consent_version: manifest.consent_version,
      consent_text_sha256: manifest.consent_text_sha256,
      source_public_manifest_sha256:
        manifest.source_public_manifest_sha256,
      profiles: Object.create(null),
    };
  }

  function readStore(manifest) {
    const raw = localStorage.getItem(storeKey(manifest));
    if (!raw) return emptyStore(manifest);
    let store;
    try {
      store = JSON.parse(raw);
    } catch {
      throw new LocalApiError(500, "此浏览器中的进度文件已损坏。");
    }
    if (
      store?.schema_version !== "tbam.pages_local_store.v2" ||
      store?.study_id !== manifest.study_id ||
      store?.collection_protocol_id !== manifest.collection_protocol_id ||
      store?.presentation_medium !== manifest.presentation_medium ||
      store?.consent_version !== manifest.consent_version ||
      store?.consent_text_sha256 !== manifest.consent_text_sha256 ||
      store?.source_public_manifest_sha256 !==
        manifest.source_public_manifest_sha256 ||
      !store.profiles ||
      typeof store.profiles !== "object"
    ) {
      throw new LocalApiError(500, "此浏览器中的进度属于另一实验版本。");
    }
    const profiles = Object.create(null);
    for (const [key, value] of Object.entries(store.profiles)) {
      profiles[key] = value;
    }
    store.profiles = profiles;
    return store;
  }

  function writeStore(manifest, store) {
    try {
      localStorage.setItem(storeKey(manifest), JSON.stringify(store));
    } catch {
      throw new LocalApiError(
        507,
        "浏览器无法保存进度；请检查隐私模式或站点存储设置。",
      );
    }
  }

  function normalizeUsername(raw) {
    if (typeof raw !== "string") {
      throw new LocalApiError(400, "化名必须是文本。");
    }
    const display = raw.normalize("NFKC").trim();
    if (display.length < 3 || display.length > 32) {
      throw new LocalApiError(400, "化名必须包含 3–32 个字符。");
    }
    if (!/^[\p{L}\p{N}._-]+$/u.test(display)) {
      throw new LocalApiError(
        400,
        "化名只能包含字母、数字、点、下划线和连字符。",
      );
    }
    const norm = display.toLowerCase();
    if (["__proto__", "prototype", "constructor"].includes(norm)) {
      throw new LocalApiError(400, "该化名属于保留名称，请更换。");
    }
    return { norm, display };
  }

  function validatePin(pin) {
    if (typeof pin !== "string" || pin.length < 6 || pin.length > 64) {
      throw new LocalApiError(400, "PIN 必须包含 6–64 个字符。");
    }
    return pin;
  }

  function bytesToBase64(bytes) {
    let binary = "";
    for (const value of bytes) binary += String.fromCharCode(value);
    return btoa(binary);
  }

  function base64ToBytes(value) {
    const binary = atob(value);
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  }

  function bytesToHex(bytes) {
    return [...bytes]
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
  }

  async function derivePin(pin, saltBase64) {
    const material = await crypto.subtle.importKey(
      "raw",
      encoder.encode(pin),
      "PBKDF2",
      false,
      ["deriveBits"],
    );
    const bits = await crypto.subtle.deriveBits(
      {
        name: "PBKDF2",
        hash: "SHA-256",
        salt: base64ToBytes(saltBase64),
        iterations: 120000,
      },
      material,
      256,
    );
    return bytesToHex(new Uint8Array(bits));
  }

  function requestedSlot(manifest) {
    const query = new URL(window.location.href).searchParams.get("slot");
    const input = document.querySelector("#pages-slot-input");
    const raw = query !== null ? query : input?.value;
    if (raw === undefined || raw === null || String(raw).trim() === "") {
      throw new LocalApiError(
        400,
        `首次参加需要研究者分配的席位编号（${manifest.rater_slot_min}–${manifest.rater_slot_max}）。`,
      );
    }
    const slot = Number(raw);
    if (
      !Number.isInteger(slot) ||
      slot < manifest.rater_slot_min ||
      slot > manifest.rater_slot_max
    ) {
      throw new LocalApiError(
        400,
        `席位编号必须是 ${manifest.rater_slot_min}–${manifest.rater_slot_max} 的整数。`,
      );
    }
    return slot;
  }

  function sessionNorm(manifest) {
    return sessionStorage.getItem(sessionKey(manifest));
  }

  function setSession(manifest, norm) {
    if (norm) sessionStorage.setItem(sessionKey(manifest), norm);
    else sessionStorage.removeItem(sessionKey(manifest));
  }

  function currentProfile(manifest, store, required = true) {
    const norm = sessionNorm(manifest);
    const profile =
      norm && Object.hasOwn(store.profiles, norm)
        ? store.profiles[norm]
        : null;
    if (!profile && required) {
      throw new LocalApiError(401, "请先读取此浏览器中的进度。");
    }
    return profile || null;
  }

  function assignedItems(manifest, profile) {
    const ids = manifest.slot_assignments?.[String(profile.rater_slot)];
    if (
      !Array.isArray(ids) ||
      ids.length !== manifest.items_per_rater ||
      new Set(ids).size !== manifest.items_per_rater
    ) {
      throw new LocalApiError(500, "Pages 完整目录分配无效。");
    }
    const byId = new Map(
      manifest.items.map((item) => [item.item_id, item]),
    );
    const assigned = ids.map((itemId) => byId.get(itemId));
    if (
      assigned.some((item) => !item) ||
      new Set(assigned.map((item) => item.item_id)).size !==
        manifest.items.length
    ) {
      throw new LocalApiError(500, "Pages 完整目录与冻结项目不一致。");
    }
    return assigned;
  }

  function itemState(profile, itemId) {
    if (!profile.items[itemId]) {
      profile.items[itemId] = {
        started_utc: null,
        draft: null,
        judgment: null,
      };
    }
    return profile.items[itemId];
  }

  function participantPayload(manifest, profile) {
    const assigned = assignedItems(manifest, profile);
    const states = assigned.map((item) => itemState(profile, item.item_id));
    return {
      username: profile.username,
      rater_id: profile.rater_id,
      rater_slot: profile.rater_slot,
      tutorial_completed: Boolean(profile.tutorial_completed_utc),
      completed: states.filter((state) => state.judgment).length,
      started: states.filter((state) => state.started_utc).length,
      total: assigned.length,
      study_id: manifest.study_id,
      study_mode: manifest.study_mode,
    };
  }

  function catalogPayload(manifest, profile) {
    return assignedItems(manifest, profile).map((item, index) => {
      const local = itemState(profile, item.item_id);
      const status = local.draft
        ? "draft"
        : local.judgment
          ? "submitted"
          : local.started_utc
            ? "in_progress"
            : "not_started";
      return {
        item_id: item.item_id,
        blind_map_id: item.blind_map_id,
        catalog_number: index + 1,
        status,
        started_utc: local.started_utc,
        updated_utc: local.draft?.updated_utc || null,
        submitted_utc: local.judgment?.completed_utc || null,
      };
    });
  }

  function requireAssigned(manifest, profile, itemId) {
    const item = assignedItems(manifest, profile).find(
      (candidate) => candidate.item_id === itemId,
    );
    if (!item) {
      throw new LocalApiError(403, "该项目不属于此席位的目录。");
    }
    return item;
  }

  function parseBody(options) {
    if (!options?.body) return {};
    try {
      const value = JSON.parse(options.body);
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        throw new Error();
      }
      return value;
    } catch {
      throw new LocalApiError(400, "请求数据不是有效 JSON。");
    }
  }

  function validateChoice(choice) {
    if (choice !== "A" && choice !== "B" && choice !== "tie") {
      throw new LocalApiError(
        400,
        "必须选择路线 A、路线 B 或平局。",
      );
    }
    return choice;
  }

  function validateDraftPayload(payload) {
    if (
      !payload ||
      typeof payload !== "object" ||
      Array.isArray(payload) ||
      Object.keys(payload).join(",") !== "choice" ||
      ![null, "A", "B", "tie"].includes(payload.choice)
    ) {
      throw new LocalApiError(400, "草稿选择无效。");
    }
    return { choice: payload.choice };
  }

  async function register(manifest, body) {
    if (body.consented !== true) {
      throw new LocalApiError(
        400,
        "请先确认内部评判说明与参与同意。",
      );
    }
    const { norm, display } = normalizeUsername(body.username);
    const pin = validatePin(body.pin);
    const slot = requestedSlot(manifest);
    const initialStore = readStore(manifest);
    if (Object.hasOwn(initialStore.profiles, norm)) {
      if (initialStore.profiles[norm].rater_slot !== slot) {
        throw new LocalApiError(
          409,
          "该化名已属于另一席位；请使用原席位链接读取进度。",
        );
      }
      return login(manifest, body);
    }
    const saltBytes = crypto.getRandomValues(new Uint8Array(16));
    const salt = bytesToBase64(saltBytes);
    const pinHash = await derivePin(pin, salt);
    const store = readStore(manifest);
    if (Object.hasOwn(store.profiles, norm)) {
      if (store.profiles[norm].rater_slot !== slot) {
        throw new LocalApiError(
          409,
          "该化名已属于另一席位；请使用原席位链接读取进度。",
        );
      }
      return login(manifest, body);
    }
    if (
      Object.values(store.profiles).some(
        (profile) => profile.rater_slot === slot,
      )
    ) {
      throw new LocalApiError(
        409,
        "此浏览器中该席位已经注册；请读取已有进度。",
      );
    }
    const created = now();
    const profile = {
      username: display,
      username_norm: norm,
      pin_salt: salt,
      pin_hash: pinHash,
      rater_slot: slot,
      rater_id: `human_pages_${String(slot + 1).padStart(2, "0")}`,
      collection_protocol_id: manifest.collection_protocol_id,
      registered_bundle_id: manifest.bundle_id,
      presentation_medium: manifest.presentation_medium,
      source_public_manifest_sha256:
        manifest.source_public_manifest_sha256,
      consented_utc: created,
      created_utc: created,
      last_login_utc: created,
      tutorial_completed_utc: null,
      items: {},
    };
    store.profiles[norm] = profile;
    writeStore(manifest, store);
    setSession(manifest, norm);
    return participantPayload(manifest, profile);
  }

  async function login(manifest, body) {
    const { norm } = normalizeUsername(body.username);
    const pin = validatePin(body.pin);
    const store = readStore(manifest);
    const profile = Object.hasOwn(store.profiles, norm)
      ? store.profiles[norm]
      : null;
    if (!profile) {
      throw new LocalApiError(
        401,
        "此浏览器中没有该化名；请检查设备或导入完整备份。",
      );
    }
    const derived = await derivePin(pin, profile.pin_salt);
    if (derived !== profile.pin_hash) {
      throw new LocalApiError(401, "化名或 PIN 不正确。");
    }
    setSession(manifest, norm);
    return participantPayload(manifest, profile);
  }

  function buildRecord(
    manifest,
    profile,
    item,
    local,
    choice,
    activeSeconds,
  ) {
    const duration = Number(activeSeconds);
    if (!Number.isFinite(duration) || duration <= 0 || duration > 43200) {
      throw new LocalApiError(400, "有效作答时间无效。");
    }
    const completed = now();
    return {
      schema_version: tieJudgmentSchema,
      study_id: manifest.study_id,
      item_id: item.item_id,
      judge_type: "human",
      judge_system_id: profile.rater_id,
      presentation_variant: "canonical",
      presented_routes: { A: "A", B: "B" },
      input_artifact_sha256: {
        ...item.input_artifact_sha256,
      },
      control_item: false,
      attention_check_passed: null,
      choice: validateChoice(choice),
      started_utc: local.started_utc || completed,
      completed_utc: completed,
      duration_seconds: Math.round(duration * 1000) / 1000,
    };
  }

  function stableStringify(value) {
    if (Array.isArray(value)) {
      return `[${value.map(stableStringify).join(",")}]`;
    }
    if (value && typeof value === "object") {
      return `{${Object.keys(value)
        .sort()
        .map(
          (key) =>
            `${JSON.stringify(key)}:${stableStringify(value[key])}`,
        )
        .join(",")}}`;
    }
    return JSON.stringify(value);
  }

  function validTimestamp(value) {
    return (
      typeof value === "string" &&
      Number.isFinite(Date.parse(value)) &&
      /(?:Z|[+-]\d\d:\d\d)$/.test(value)
    );
  }

  function validateStoredJudgment(manifest, profile, item, record) {
    const required = [
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
    ].sort();
    if (
      !record ||
      typeof record !== "object" ||
      Array.isArray(record) ||
      Object.keys(record).sort().join(",") !== required.join(",") ||
      ![legacyJudgmentSchema, tieJudgmentSchema].includes(
        record.schema_version,
      ) ||
      record.study_id !== manifest.study_id ||
      record.item_id !== item.item_id ||
      record.judge_type !== "human" ||
      record.judge_system_id !== profile.rater_id ||
      record.presentation_variant !== "canonical" ||
      !record.presented_routes ||
      typeof record.presented_routes !== "object" ||
      Array.isArray(record.presented_routes) ||
      Object.keys(record.presented_routes).sort().join(",") !== "A,B" ||
      record.presented_routes?.A !== "A" ||
      record.presented_routes?.B !== "B" ||
      record.control_item !== false ||
      record.attention_check_passed !== null
    ) {
      throw new Error(`备份中的判断记录无效：${item.item_id}`);
    }
    if (
      stableStringify(record.input_artifact_sha256) !==
      stableStringify(item.input_artifact_sha256)
    ) {
      throw new Error(`备份中的制品哈希不匹配：${item.item_id}`);
    }
    validateChoice(record.choice);
    if (
      record.schema_version === legacyJudgmentSchema &&
      record.choice === "tie"
    ) {
      throw new Error(`备份中的旧版判断记录不能包含平局：${item.item_id}`);
    }
    if (
      !validTimestamp(record.started_utc) ||
      !validTimestamp(record.completed_utc) ||
      Date.parse(record.completed_utc) < Date.parse(record.started_utc) ||
      typeof record.duration_seconds !== "number" ||
      !Number.isFinite(record.duration_seconds) ||
      record.duration_seconds <= 0 ||
      record.duration_seconds > 43200
    ) {
      throw new Error(`备份中的时间记录无效：${item.item_id}`);
    }
  }

  function validateImportedProfile(manifest, profile) {
    if (
      !profile ||
      typeof profile !== "object" ||
      Array.isArray(profile) ||
      profile.collection_protocol_id !==
        manifest.collection_protocol_id ||
      !/^[0-9a-f]{64}$/.test(profile.registered_bundle_id || "") ||
      profile.presentation_medium !== manifest.presentation_medium ||
      profile.source_public_manifest_sha256 !==
        manifest.source_public_manifest_sha256
    ) {
      throw new Error("备份中的参与者版本绑定无效。");
    }
    const normalized = normalizeUsername(profile.username);
    if (
      normalized.norm !== profile.username_norm ||
      !Number.isInteger(profile.rater_slot) ||
      profile.rater_slot < manifest.rater_slot_min ||
      profile.rater_slot > manifest.rater_slot_max ||
      profile.rater_id !==
        `human_pages_${String(profile.rater_slot + 1).padStart(2, "0")}` ||
      typeof profile.pin_salt !== "string" ||
      typeof profile.pin_hash !== "string" ||
      !/^[0-9a-f]{64}$/.test(profile.pin_hash) ||
      !profile.items ||
      typeof profile.items !== "object" ||
      Array.isArray(profile.items)
    ) {
      throw new Error("备份中的参与者身份字段无效。");
    }
    try {
      if (base64ToBytes(profile.pin_salt).length !== 16) throw new Error();
    } catch {
      throw new Error("备份中的 PIN 盐值无效。");
    }
    for (const field of ["consented_utc", "created_utc", "last_login_utc"]) {
      if (!validTimestamp(profile[field])) {
        throw new Error(`备份中的 ${field} 无效。`);
      }
    }
    if (
      profile.tutorial_completed_utc !== null &&
      !validTimestamp(profile.tutorial_completed_utc)
    ) {
      throw new Error("备份中的教程完成时间无效。");
    }

    const assigned = assignedItems(manifest, profile);
    const itemById = new Map(assigned.map((item) => [item.item_id, item]));
    for (const [itemId, local] of Object.entries(profile.items)) {
      const item = itemById.get(itemId);
      if (
        !item ||
        !local ||
        typeof local !== "object" ||
        Array.isArray(local) ||
        !("started_utc" in local) ||
        !("draft" in local) ||
        !("judgment" in local)
      ) {
        throw new Error(`备份中的项目状态无效：${itemId}`);
      }
      if (
        local.started_utc !== null &&
        !validTimestamp(local.started_utc)
      ) {
        throw new Error(`备份中的开始时间无效：${itemId}`);
      }
      if (local.judgment !== null) {
        validateStoredJudgment(manifest, profile, item, local.judgment);
      }
      if (local.draft !== null) {
        if (
          typeof local.draft !== "object" ||
          !Number.isInteger(local.draft.revision) ||
          local.draft.revision < 1 ||
          !validTimestamp(local.draft.updated_utc) ||
          typeof local.draft.active_seconds !== "number" ||
          !Number.isFinite(local.draft.active_seconds) ||
          local.draft.active_seconds < 0 ||
          !local.draft.payload ||
          typeof local.draft.payload !== "object"
        ) {
          throw new Error(`备份中的草稿无效：${itemId}`);
        }
        validateDraftPayload(local.draft.payload);
      }
    }
    return profile;
  }

  function earlierTimestamp(first, second) {
    if (!first) return second || null;
    if (!second) return first;
    return Date.parse(first) <= Date.parse(second) ? first : second;
  }

  function laterTimestamp(first, second) {
    if (!first) return second || null;
    if (!second) return first;
    return Date.parse(first) >= Date.parse(second) ? first : second;
  }

  function mergeProfiles(manifest, current, incoming) {
    if (!current) return structuredClone(incoming);
    validateImportedProfile(manifest, current);
    if (
      current.username_norm !== incoming.username_norm ||
      current.rater_slot !== incoming.rater_slot ||
      current.rater_id !== incoming.rater_id ||
      current.pin_salt !== incoming.pin_salt ||
      current.pin_hash !== incoming.pin_hash
    ) {
      throw new Error("同名本地进度与备份的身份或 PIN 绑定冲突。");
    }
    const merged = structuredClone(current);
    merged.consented_utc = earlierTimestamp(
      current.consented_utc,
      incoming.consented_utc,
    );
    merged.created_utc = earlierTimestamp(
      current.created_utc,
      incoming.created_utc,
    );
    merged.last_login_utc = laterTimestamp(
      current.last_login_utc,
      incoming.last_login_utc,
    );
    merged.tutorial_completed_utc = earlierTimestamp(
      current.tutorial_completed_utc,
      incoming.tutorial_completed_utc,
    );

    for (const item of assignedItems(manifest, merged)) {
      const existing = current.items[item.item_id] || {
        started_utc: null,
        draft: null,
        judgment: null,
      };
      const restored = incoming.items[item.item_id] || {
        started_utc: null,
        draft: null,
        judgment: null,
      };
      const state = {
        started_utc: earlierTimestamp(
          existing.started_utc,
          restored.started_utc,
        ),
        draft: null,
        judgment: null,
      };
      const judgments = [
        existing.judgment,
        restored.judgment,
      ].filter(Boolean);
      judgments.sort(
        (left, right) =>
          Date.parse(right.completed_utc) -
          Date.parse(left.completed_utc),
      );
      if (
        judgments.length === 2 &&
        judgments[0].completed_utc === judgments[1].completed_utc &&
        stableStringify(judgments[0]) !==
          stableStringify(judgments[1])
      ) {
        throw new Error(
          `备份与本地判断具有相同时间但内容冲突：${item.item_id}`,
        );
      }
      state.judgment = judgments[0] || null;
      const drafts = [existing.draft, restored.draft].filter(Boolean);
      drafts.sort(
        (left, right) =>
          Date.parse(right.updated_utc) -
            Date.parse(left.updated_utc) ||
          right.revision - left.revision,
      );
      const newestDraft = drafts[0] || null;
      if (
        newestDraft &&
        (
          !state.judgment ||
          Date.parse(newestDraft.updated_utc) >
            Date.parse(state.judgment.completed_utc)
        )
      ) {
        state.draft = newestDraft;
      }
      merged.items[item.item_id] = state;
    }
    return merged;
  }

  async function handleApi(url, options = {}) {
    const manifest = await loadManifest();
    const method = String(options.method || "GET").toUpperCase();
    const path = url.pathname;
    const body = parseBody(options);

    if (method === "GET" && path === "/api/config") {
      return jsonResponse({
        title: "TBAM 匿名路线人工评判",
        study_id: manifest.study_id,
        storage_namespace_id:
          `${manifest.study_id}:${manifest.collection_protocol_id}`,
        study_mode: manifest.study_mode,
        storage_mode: "browser_local",
        registration_open: true,
        consent_version: manifest.consent_version,
        consent_text: manifest.consent_text,
        item_count: manifest.item_count,
        full_item_count: manifest.full_item_count,
        map_count: manifest.map_count,
        items_per_map: manifest.items_per_map,
        items_per_rater: manifest.items_per_rater,
        current_wave: manifest.current_wave,
        current_release_id: manifest.current_release_id,
        judgments_per_item:
          manifest.judgments_per_item_if_all_slots_complete,
        public_manifest_sha256:
          manifest.source_public_manifest_sha256,
        artifact_status: "complete_frozen_artifacts",
      });
    }

    if (method === "GET" && path === "/api/me") {
      const store = readStore(manifest);
      const profile = currentProfile(manifest, store, false);
      return jsonResponse(
        profile
          ? {
              authenticated: true,
              participant: participantPayload(manifest, profile),
            }
          : { authenticated: false },
      );
    }

    if (method === "POST" && path === "/api/auth/register") {
      return jsonResponse(
        { participant: await register(manifest, body) },
        201,
      );
    }
    if (method === "POST" && path === "/api/auth/login") {
      return jsonResponse({ participant: await login(manifest, body) });
    }
    if (method === "POST" && path === "/api/auth/logout") {
      setSession(manifest, null);
      return jsonResponse({ ok: true });
    }

    const store = readStore(manifest);
    const profile = currentProfile(manifest, store);

    if (method === "POST" && path === "/api/tutorial/complete") {
      profile.tutorial_completed_utc ||= now();
      writeStore(manifest, store);
      return jsonResponse({ ok: true });
    }

    if (method === "GET" && path === "/api/catalog") {
      return jsonResponse({ items: catalogPayload(manifest, profile) });
    }

    const itemMatch = path.match(/^\/api\/item\/(item_[0-9a-f]{16})$/);
    if (method === "GET" && itemMatch) {
      const item = requireAssigned(manifest, profile, itemMatch[1]);
      const local = itemState(profile, item.item_id);
      const editableState =
        local.draft ||
        (local.judgment
          ? {
              payload: { choice: local.judgment.choice },
              active_seconds: local.judgment.duration_seconds,
              revision: 0,
              updated_utc: local.judgment.completed_utc,
            }
          : null);
      return jsonResponse({
        item_id: item.item_id,
        blind_map_id: item.blind_map_id,
        map_index: item.map_index,
        item_index: item.item_index,
        directive: item.directive,
        media: {
          judge_input: item.judge_input_path,
        },
        draft: editableState,
      });
    }

    const startMatch = path.match(
      /^\/api\/item\/(item_[0-9a-f]{16})\/start$/,
    );
    if (method === "POST" && startMatch) {
      if (!profile.tutorial_completed_utc) {
        throw new LocalApiError(403, "请先完成教程。");
      }
      const item = requireAssigned(manifest, profile, startMatch[1]);
      const local = itemState(profile, item.item_id);
      local.started_utc ||= now();
      writeStore(manifest, store);
      return jsonResponse({ started_utc: local.started_utc });
    }

    const draftMatch = path.match(
      /^\/api\/item\/(item_[0-9a-f]{16})\/draft$/,
    );
    if (method === "PUT" && draftMatch) {
      const item = requireAssigned(manifest, profile, draftMatch[1]);
      const local = itemState(profile, item.item_id);
      const currentRevision = Number(local.draft?.revision || 0);
      if (
        !Number.isInteger(body.expected_revision) ||
        body.expected_revision !== currentRevision
      ) {
        throw new LocalApiError(
          409,
          "另一标签页已经修改了草稿。",
          local.draft,
        );
      }
      const activeSeconds = Number(body.active_seconds);
      if (
        !Number.isFinite(activeSeconds) ||
        activeSeconds < 0 ||
        activeSeconds > 43200
      ) {
        throw new LocalApiError(400, "草稿数据无效。");
      }
      const payload = validateDraftPayload(body.payload);
      local.started_utc ||= now();
      local.draft = {
        payload,
        active_seconds: activeSeconds,
        revision: currentRevision + 1,
        updated_utc: now(),
      };
      writeStore(manifest, store);
      return jsonResponse({
        revision: local.draft.revision,
        updated_utc: local.draft.updated_utc,
        active_seconds: activeSeconds,
      });
    }

    const submitMatch = path.match(
      /^\/api\/item\/(item_[0-9a-f]{16})\/submit$/,
    );
    if (method === "POST" && submitMatch) {
      const item = requireAssigned(manifest, profile, submitMatch[1]);
      const local = itemState(profile, item.item_id);
      if (!local.started_utc) {
        throw new LocalApiError(400, "提交前必须先打开项目。");
      }
      local.judgment = buildRecord(
        manifest,
        profile,
        item,
        local,
        body.choice,
        body.active_seconds,
      );
      local.draft = null;
      writeStore(manifest, store);
      return jsonResponse({ record: local.judgment }, 201);
    }

    throw new LocalApiError(404, "Pages 静态版不支持该请求。");
  }

  async function withWriteLock(operation) {
    if (navigator.locks?.request) {
      return navigator.locks.request(
        `${namespace}:write`,
        { mode: "exclusive" },
        operation,
      );
    }
    return operation();
  }

  async function interceptedFetch(input, options = {}) {
    const raw =
      typeof input === "string" || input instanceof URL ? String(input) : input.url;
    const url = new URL(raw, window.location.href);
    if (url.pathname.startsWith("/api/")) {
      const execute = async () => {
        try {
          return await handleApi(url, options);
        } catch (error) {
          return errorResponse(error);
        }
      };
      const method = String(options.method || "GET").toUpperCase();
      if (method !== "GET" && method !== "HEAD") {
        return withWriteLock(execute);
      }
      return execute();
    }
    return nativeFetch(url, options);
  }

  async function scienceExport() {
    const manifest = await loadManifest();
    const store = readStore(manifest);
    const profile = currentProfile(manifest, store);
    const assigned = assignedItems(manifest, profile);
    const judgments = assigned
      .map((item) => itemState(profile, item.item_id).judgment)
      .filter(Boolean)
      .sort((first, second) => first.item_id.localeCompare(second.item_id));
    return {
      schema_version: "tbam.pages_human_rater_export.v2",
      study_id: manifest.study_id,
      judge_system_id: profile.rater_id,
      rater_slot: profile.rater_slot,
      presentation_medium: manifest.presentation_medium,
      collection_protocol_id: manifest.collection_protocol_id,
      registered_bundle_id: profile.registered_bundle_id,
      bundle_id: manifest.bundle_id,
      source_public_manifest_sha256:
        manifest.source_public_manifest_sha256,
      assignment_rule_id: manifest.assignment_rule_id,
      assignment_item_ids: assigned.map((item) => item.item_id),
      full_master_item_count: manifest.full_item_count,
      current_wave: manifest.current_wave,
      current_release_id: manifest.current_release_id,
      release_index_id: manifest.release_index_id,
      exported_utc: now(),
      judgments,
    };
  }

  async function browserBackup() {
    const manifest = await loadManifest();
    const store = readStore(manifest);
    const profile = currentProfile(manifest, store);
    return {
      schema_version: "tbam.pages_browser_backup.v2",
      study_id: manifest.study_id,
      presentation_medium: manifest.presentation_medium,
      collection_protocol_id: manifest.collection_protocol_id,
      bundle_id: manifest.bundle_id,
      source_public_manifest_sha256:
        manifest.source_public_manifest_sha256,
      current_wave: manifest.current_wave,
      current_release_id: manifest.current_release_id,
      release_index_id: manifest.release_index_id,
      exported_utc: now(),
      profile,
    };
  }

  function downloadJson(payload, filename) {
    const blob = new Blob(
      [JSON.stringify(payload, null, 2) + "\n"],
      { type: "application/json;charset=utf-8" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function downloadScienceExport() {
    try {
      const payload = await scienceExport();
      downloadJson(payload, `${payload.judge_system_id}_results.json`);
    } catch (error) {
      window.alert(error.message);
    }
  }

  async function downloadBrowserBackup() {
    try {
      const payload = await browserBackup();
      downloadJson(
        payload,
        `${payload.profile.rater_id}_browser_backup.json`,
      );
    } catch (error) {
      window.alert(error.message);
    }
  }

  async function importBrowserBackup(file) {
    const manifest = await loadManifest();
    let payload;
    try {
      payload = JSON.parse(await file.text());
    } catch {
      throw new Error("备份文件不是有效 JSON。");
    }
    if (
      payload?.schema_version !== "tbam.pages_browser_backup.v2" ||
      payload?.study_id !== manifest.study_id ||
      payload?.source_public_manifest_sha256 !==
        manifest.source_public_manifest_sha256 ||
      payload?.presentation_medium !== manifest.presentation_medium ||
      payload?.collection_protocol_id !==
        manifest.collection_protocol_id ||
      !/^[0-9a-f]{64}$/.test(payload?.bundle_id || "")
    ) {
      throw new Error("备份文件与当前 Pages 实验版本不兼容。");
    }
    const incoming = validateImportedProfile(manifest, payload.profile);
    await withWriteLock(async () => {
      const store = readStore(manifest);
      const norm = incoming.username_norm;
      for (const [otherNorm, profile] of Object.entries(store.profiles)) {
        if (
          otherNorm !== norm &&
          profile.rater_slot === incoming.rater_slot
        ) {
          throw new Error("此浏览器中该席位已属于另一化名，拒绝导入。");
        }
      }
      const current = Object.hasOwn(store.profiles, norm)
        ? store.profiles[norm]
        : null;
      store.profiles[norm] = mergeProfiles(manifest, current, incoming);
      writeStore(manifest, store);
      setSession(manifest, norm);
    });
    window.alert("完整浏览器备份已导入。页面将重新载入。");
    window.location.reload();
  }

  function replaceTextNode() {}

  function installStaticInterface() {
    const languageSwitch = document.querySelector("[data-language-switch]");
    if (languageSwitch) {
      const target = new URL(
        languageSwitch.getAttribute("href"),
        window.location.href,
      );
      const slot = new URL(window.location.href).searchParams.get("slot");
      target.search = "";
      if (/^[0-4]$/.test(slot || "")) {
        target.searchParams.set("slot", slot);
      }
      target.hash = "";
      languageSwitch.href = target.href;
    }
    const style = document.createElement("style");
    style.textContent = `
      .pages-export-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
      #pages-storage-warning { padding: 10px 12px; border: 1px solid rgba(205,139,44,.28);
        border-radius: 10px; background: rgba(255,248,230,.72); }
      @media (max-width: 760px) {
        .dashboard-heading { align-items: flex-start; flex-direction: column; gap: 18px; }
        .pages-export-actions { width: 100%; justify-content: stretch; }
        .pages-export-actions .secondary-button { flex: 1 1 100%; }
      }
    `;
    document.head.append(style);
    const querySlot = new URL(window.location.href).searchParams.get("slot");
    const form = document.querySelector("#auth-form");
    const pinField = document.querySelector("#pin-input")?.closest(".field");
    if (form && pinField && !document.querySelector("#pages-slot-field")) {
      const field = document.createElement("label");
      field.className = "field hidden";
      field.id = "pages-slot-field";
      field.innerHTML = `
        <span>研究者分配的席位编号</span>
        <input id="pages-slot-input" type="number" min="0" max="4"
          inputmode="numeric" placeholder="0–4" required>
        <small>请使用研究者发送给您的唯一编号，不要与他人共用。</small>
      `;
      pinField.after(field);
      const input = field.querySelector("input");
      if (querySlot !== null) {
        input.value = querySlot;
        input.readOnly = true;
      }
      const updateSlotVisibility = () => {
        field.classList.toggle(
          "hidden",
          !document.querySelector("#register-tab")?.classList.contains("active"),
        );
      };
      document
        .querySelector("#register-tab")
        ?.addEventListener("click", () => window.setTimeout(updateSlotVisibility));
      document
        .querySelector("#login-tab")
        ?.addEventListener("click", () => window.setTimeout(updateSlotVisibility));
      updateSlotVisibility();
    }

    const heading = document.querySelector(".auth-panel-heading");
    if (heading && !document.querySelector("#pages-storage-warning")) {
      const warning = document.createElement("p");
      warning.id = "pages-storage-warning";
      warning.className = "registration-note";
      warning.textContent =
        "GitHub Pages 内部评判：进度只保存在当前浏览器。完成后必须下载结果 JSON 并交回研究者。";
      heading.append(warning);
    }
    document.querySelector("#open-admin-login")?.classList.add("hidden");

    const exportButton = document.querySelector("#export-mine");
    if (exportButton) {
      exportButton.textContent = "下载结果与进度 JSON";
      exportButton.addEventListener(
        "click",
        (event) => {
          event.preventDefault();
          event.stopImmediatePropagation();
          downloadScienceExport();
        },
        true,
      );
      const backupButton = document.createElement("button");
      backupButton.className = "secondary-button";
      backupButton.id = "pages-backup-button";
      backupButton.type = "button";
      backupButton.textContent = "下载跨浏览器备份";
      backupButton.addEventListener("click", downloadBrowserBackup);
      const actions = document.createElement("div");
      actions.className = "pages-export-actions";
      exportButton.before(actions);
      actions.append(exportButton, backupButton);
    }

    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "application/json,.json";
    fileInput.className = "hidden";
    fileInput.id = "pages-backup-import";
    fileInput.addEventListener("change", async () => {
      const [file] = fileInput.files;
      if (!file) return;
      try {
        await importBrowserBackup(file);
      } catch (error) {
        window.alert(error.message);
      } finally {
        fileInput.value = "";
      }
    });
    document.body.append(fileInput);

    const importButton = document.createElement("button");
    importButton.type = "button";
    importButton.className = "admin-link";
    importButton.textContent = "从完整浏览器备份恢复";
    importButton.addEventListener("click", () => fileInput.click());
    document.querySelector("#auth-form")?.after(importButton);

  }

  window.fetch = interceptedFetch;
  window.TBAMPagesPilot = {
    siteBase: siteBase.href,
    loadManifest,
    scienceExport,
    browserBackup,
  };
  installStaticInterface();
})();
