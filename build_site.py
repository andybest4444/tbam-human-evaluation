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
import re
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
    "2630e8344a3697208ba01c2eea96c6c950f68d9078ade170d09d496c8fc3f9fe"
)
EXPECTED_BUNDLE_ID = (
    "801d770177c1d14b8e1f8e7c3531de78af5ad8cb0e55f573691a68ecf40a4b1e"
)
STUDY_ID = "tbam_s6_human_forced_choice_full_catalog_pages_v1"
PRESENTATION_MEDIUM = "static_route_maps_bilingual_pages_v1"
ASSIGNMENT_RULE_ID = "complete_catalog_round_robin_v1"
ASSET_VERSION = "full-catalog-bilingual-v1"
RATER_SLOT_MIN = 0
RATER_SLOT_MAX = 4
ITEMS_PER_RATER = 240
JUDGMENTS_PER_ITEM = 5
DIRECTIVE_EN = (
    "Reach the goal efficiently, avoid unnecessary elevation changes, and "
    "prioritize cover; stay dispersed in exposed areas and group together "
    "in concealed areas."
)
RUNTIME_FILES = (
    "index.html",
    "index-en.html",
    "app.js",
    "app-en.js",
    "styles.css",
    "static_api.js",
    "static_api-en.js",
    "results.html",
    "results.js",
    "results.css",
)
COLLECTION_RUNTIME_FILES = (
    "index.html",
    "index-en.html",
    "app.js",
    "app-en.js",
    "styles.css",
    "static_api.js",
    "static_api-en.js",
)
SOURCE_MIRROR_FILES = (
    ".nojekyll",
    "static_api.js",
    "results.html",
    "results.js",
    "results.css",
)
ENGLISH_TRANSLATIONS = {
    "备份中的 ${field} 无效": "Invalid ${field} in backup",
    "任意浏览器恢复服务器中的进度": (
        "resume server progress in any browser"
    ),
    "服务器自动保存草稿": "the server automatically saves drafts",
    "进度已保存在服务器": "progress is saved on the server",
    "服务器同步失败": "server synchronization failed",
    "尚无服务器草稿": "no server draft",
    "草稿已保存到此浏览器": "draft saved in this browser",
    "已读取服务器最新草稿": "loaded the latest server draft",
    "欢迎，${state.participant.username}": (
        "Welcome, ${state.participant.username}"
    ),
    "已提交 ${completed} 项，剩余 ${total - completed} 项；"
    "已提交项目仍可重新修改": (
        "Submitted ${completed} items; ${total - completed} remaining. "
        "Submitted choices may still be revised"
    ),
    '${next.status === "not_started" ? "开始" : "继续"}'
    "第 ${next.catalog_number} 项": (
        '${next.status === "not_started" ? "Start" : "Continue"} '
        "item ${next.catalog_number}"
    ),
    "${total} 项全部完成": "${total} items complete",
    "路线 ${arm} 的轨迹数据不完整": (
        "Route ${arm} trajectory data is incomplete"
    ),
    "项目 ${catalogItem.catalog_number} / ${state.catalog.length}": (
        "Item ${catalogItem.catalog_number} / ${state.catalog.length}"
    ),
    "项目 ${activeItem.catalog_number} 已提交；仍可重新打开修改": (
        "Item ${activeItem.catalog_number} submitted; you may reopen it "
        "and change the choice"
    ),
    "TBAM 匿名路线人工评判": "TBAM Anonymous Route Evaluation",
    "页面无法连接评判服务": "The page could not connect to the evaluation service",
    "公开制品已冻结并验证": "Public artifacts frozen and verified",
    "界面预览 · 未连接收集服务": (
        "Interface preview · collection service unavailable"
    ),
    "当前尚未开放新用户注册": "New participant registration is not open",
    "新用户注册尚未开放": "New participant registration is not open",
    "创建匿名席位": "Create anonymous slot",
    "读取已有进度": "Load existing progress",
    "已分配匿名编号": "Assigned anonymous ID",
    "已恢复服务器进度": "Restored progress from this browser",
    "教程已完成，个人目录已解锁": (
        "Instructions completed; your catalog is unlocked"
    ),
    "这个筛选条件下没有项目": "No items match this filter",
    "建议分多次完成；使用同一化名与 PIN 可随时恢复": (
        "You may split the catalog across sessions; use the same "
        "pseudonym and PIN to resume"
    ),
    "进度已保存在服务器，您可以继续下一项或稍后回来": (
        "Progress is saved; continue now or return later"
    ),
    "感谢完成完整目录。您仍可导出自己的匿名备份": (
        "Thank you for completing the catalog. You may still export "
        "your anonymous backup"
    ),
    "结合任务指令和两张匿名路线图，必须选择一条；"
    "不区分是否完成，不做分项评分": (
        "Using the task instruction and the two anonymous route maps, "
        "choose one route overall. Do not separately judge completion "
        "or assign dimension scores"
    ),
    "路线 A 和路线 B，哪条整体更好": (
        "Which route is better overall, Route A or Route B"
    ),
    "选择整体更好的路线": "Choose the better route overall",
    "请选择路线 A 或路线 B": "Please choose Route A or Route B",
    "有尚未同步的修改": "Unsaved changes",
    "正在同步草稿": "Saving draft",
    "草稿已同步": "Draft saved",
    "草稿已保存到服务器": "Draft saved in this browser",
    "已读取另一标签页的版本": "Loaded the version from another tab",
    "检测到另一标签页的更新，已读取服务器最新草稿": (
        "Another tab changed this item; its latest draft was loaded"
    ),
    "服务器同步失败，本地草稿已保留": (
        "Browser save failed; the local draft was retained"
    ),
    "匿名路线数据格式无效": "Invalid anonymous route data format",
    "的轨迹数据不完整": " trajectory data is incomplete",
    "浏览器不支持路线图画布": (
        "This browser does not support the route-map canvas"
    ),
    "匿名路线数据与当前项目不一致": (
        "Anonymous route data does not match the current item"
    ),
    "正在读取服务器草稿": "Loading saved draft",
    "正在载入匿名路线制品": "Loading anonymous route artifact",
    "已恢复此浏览器中更新的未同步草稿": (
        "Restored a newer unsaved draft from this browser"
    ),
    "正在保存恢复的浏览器草稿": "Saving the restored browser draft",
    "尚无浏览器草稿": "No browser draft",
    "已提交；仍可重新打开修改": (
        "submitted; you may reopen it and change the choice"
    ),
    "服务器汇总于": "Summary generated",
    "选择 A": "Choice A",
    "选择 B": "Choice B",
    "已退出当前用户": "Signed out",
    "导出失败": "Export failed",
    "返回任务目录": "Return to the catalog",
    "正在核对制品": "Verifying artifacts",
    "我的目录": "My catalog",
    "账户菜单": "Account menu",
    "正在验证冻结目录与评判协议": (
        "Verifying the frozen catalog and evaluation protocol"
    ),
    "匿名 · 均衡 · 可恢复": "Anonymous · balanced · resumable",
    "判断路线，不判断方法": "Judge the routes, not the methods",
    "您将比较成对的匿名团队路线。页面不会展示算法名称、奖励、回报、": (
        "You will compare pairs of anonymous team routes. The page does "
        "not reveal algorithm names, rewards, returns,"
    ),
    "训练规模或计算时间，只关注路线是否遵循同一条自然语言指令": (
        "training scale, or compute time. Judge only how well each route "
        "follows the same natural-language instruction"
    ),
    "研究规模": "Study size",
    "张冻结地图": "frozen maps",
    "项个人目录": "items in your catalog",
    "次独立判断 / 项": "independent judgments per item",
    "高效到达目标，避免不必要的升降，优先利用掩体；在暴露区域保持分散，": (
        "Reach the goal efficiently, avoid unnecessary elevation changes, "
        "and prioritize cover; stay dispersed in exposed areas,"
    ),
    "在隐蔽区域聚集": "and group together in concealed areas",
    "所有项目只有一个问题": "Every item asks one question",
    "根据任务指令和两张匿名路线图，必须选择 A 或 B": (
        "Using the task instruction and the two anonymous route maps, "
        "you must choose A or B"
    ),
    "不区分路线是否完成，不做分项评分，也不猜测生成方法": (
        "Do not separately judge completion, assign dimension scores, "
        "or guess the generating method"
    ),
    "继续您的评判": "Continue your evaluation",
    "使用同一化名与 PIN，可在任意浏览器恢复服务器中的进度": (
        "Use the same pseudonym and PIN to resume progress in this browser"
    ),
    "登录方式": "Sign-in method",
    "读取进度": "Load progress",
    "首次参加": "First visit",
    "化名": "Pseudonym",
    "例如 route_owl": "for example, route_owl",
    "请勿使用真实姓名、邮箱、学号或工号": (
        "Do not use your real name, email, student ID, or employee ID"
    ),
    "恢复 PIN": "Recovery PIN",
    "至少 6 位": "at least 6 characters",
    "我已阅读上述说明，自愿参加，并确认使用的是不含身份信息的化名": (
        "I have read the notice, volunteer to participate, and confirm "
        "that my pseudonym contains no identifying information"
    ),
    "当前尚未开放新用户注册；已有用户仍可读取进度": (
        "Registration is closed; existing participants may still load progress"
    ),
    "研究管理员入口": "Research administrator",
    "开始前 · 约 1 分钟": "Before you begin · about 1 minute",
    "每项只做一次 A/B 二选一": "Make one A/B choice for each item",
    "不判断是否完成，不做分项评分，也没有平局选项": (
        "Do not separately judge completion, assign dimension scores, "
        "or use a tie option"
    ),
    "说明 1 / 1": "Instructions 1 / 1",
    "路线图例示意": "Route-map legend example",
    "唯一问题": "Only question",
    "两张图使用相同地图、任务指令、图例和渲染规则": (
        "Both panels use the same map, task instruction, legend, and "
        "rendering rules"
    ),
    "结合任务指令与可见路线整体判断，必须选择 A 或 B；": (
        "Judge the visible routes as a whole against the task instruction "
        "and choose A or B;"
    ),
    "A/B 只是匿名位置，不代表具体方法": (
        "A and B are anonymous positions and do not identify methods"
    ),
    "确认理解": "Confirm understanding",
    "开始评判前": "Before starting",
    "我会直接选择 A 或 B": "I will choose A or B directly",
    "不区分是否完成，不做分项评分，不猜测生成方法": (
        "I will not separately judge completion, assign dimension scores, "
        "or guess the method"
    ),
    "解锁我的 240 项完整目录": "Unlock my complete 240-item catalog",
    "您的完整评判目录": "Your complete evaluation catalog",
    "完整目录包含 240 项；可以分多次完成，已提交项目仍可重新修改": (
        "The catalog contains 240 items. You may complete it over multiple "
        "sessions and revise submitted choices"
    ),
    "导出个人备份": "Export my backup",
    "欢迎回来": "Welcome back",
    "匿名评判者": "Anonymous evaluator",
    "您可以从任意未完成项目继续": (
        "Continue from any unfinished item"
    ),
    "开始第一项": "Start the first item",
    "未开始": "Not started",
    "已有草稿": "Draft",
    "已提交": "Submitted",
    "240 项 · 30 张地图 · 8 组比较": (
        "240 items · 30 maps · 8 comparisons per map"
    ),
    "正在读取目录": "Loading catalog",
    "目录筛选": "Catalog filters",
    "全部": "All",
    "待完成": "To do",
    "返回目录": "Back to catalog",
    "地图 01": "Map 01",
    "项目 1 / 240": "Item 1 / 240",
    "统一任务指令": "Shared task instruction",
    "路线 A": "Route A",
    "路线 B": "Route B",
    "匿名候选路线": "Anonymous candidate route",
    "高程图、掩体图与完整团队路径": (
        "elevation, cover, and complete team paths"
    ),
    "正在渲染路线": "Rendering Route",
    "静态完整路线": "Complete static routes",
    "左侧显示高程，右侧显示掩体；数字 0–5 分别对应": (
        "Elevation is shown on the left and cover on the right. Labels "
        "0–5 correspond to"
    ),
    "t=0、19、38、58、77、96，同编号标记表示同一时刻": (
        "t = 0, 19, 38, 58, 77, and 96. Matching labels indicate the "
        "same time step"
    ),
    "同编号标记表示同一时刻": (
        "Matching labels indicate the same time step"
    ),
    "保存当前选择": "Save this choice",
    "选择路线 A": "Choose Route A",
    "选择路线 B": "Choose Route B",
    "提交后仍可从目录重新打开，并用新选择覆盖旧选择": (
        "After submitting, you may reopen the item and replace your choice"
    ),
    "仅保存草稿": "Save draft only",
    "提交选择": "Submit choice",
    "退出当前用户": "Sign out",
    "请求失败": "Request failed",
    "请求失败（${response.status}）": (
        "Request failed (${response.status})"
    ),
    "正式评判": "Formal evaluation",
    "试点评判": "Pilot evaluation",
    "进行中": "In progress",
    "选择": "Choice",
    "A/B 二选一": "A/B forced choice",
    "有效作答时间无效": "Invalid active response time",
    "浏览器本地存储操作失败": "Browser-local storage operation failed",
    "Pages manifest 请求失败": "Pages manifest request failed",
    "Pages manifest 请求失败（${response.status}）": (
        "Pages manifest request failed (${response.status})"
    ),
    "Pages manifest 不完整或与冻结语料不一致": (
        "The Pages manifest is incomplete or differs from the frozen corpus"
    ),
    "此浏览器中的进度文件已损坏": (
        "The progress file in this browser is corrupted"
    ),
    "此浏览器中的进度属于另一实验版本": (
        "The progress in this browser belongs to another study version"
    ),
    "浏览器无法保存进度；请检查隐私模式或站点存储设置": (
        "The browser cannot save progress; check private-browsing and "
        "site-storage settings"
    ),
    "化名必须是文本": "The pseudonym must be text",
    "化名必须包含 3–32 个字符": (
        "The pseudonym must contain 3–32 characters"
    ),
    "化名只能包含字母、数字、点、下划线和连字符": (
        "The pseudonym may contain only letters, numbers, periods, "
        "underscores, and hyphens"
    ),
    "该化名属于保留名称，请更换": (
        "That pseudonym is reserved; choose another"
    ),
    "PIN 必须包含 6–64 个字符": (
        "The PIN must contain 6–64 characters"
    ),
    "首次参加需要研究者分配的席位编号（0–4）": (
        "First-time registration requires a researcher-assigned slot (0–4)"
    ),
    "席位编号必须是 0–4 的整数": (
        "The slot must be an integer from 0 to 4"
    ),
    "请先读取此浏览器中的进度": (
        "Load progress from this browser first"
    ),
    "Pages 完整目录分配无效": "Invalid complete-catalog assignment",
    "Pages 完整目录与冻结项目不一致": (
        "The complete catalog differs from the frozen items"
    ),
    "该项目不属于此席位的目录": (
        "This item is not assigned to this slot"
    ),
    "请求数据不是有效 JSON": "The request body is not valid JSON",
    "必须选择路线 A 或路线 B": "You must choose Route A or Route B",
    "草稿选择无效": "Invalid draft choice",
    "请先确认内部试运行说明": (
        "Accept the internal pilot notice before continuing"
    ),
    "该化名已属于另一席位；请使用原席位链接读取进度": (
        "This pseudonym belongs to another slot; use its original slot link"
    ),
    "此浏览器中该席位已经注册；请读取已有进度": (
        "This slot is already registered in this browser; load its progress"
    ),
    "此浏览器中没有该化名；请检查设备或导入完整备份": (
        "This pseudonym is not stored in this browser; check the device or "
        "import a complete backup"
    ),
    "化名或 PIN 不正确": "Incorrect pseudonym or PIN",
    "请先完成教程": "Complete the instructions first",
    "另一标签页已经修改了草稿": (
        "Another browser tab has changed the draft"
    ),
    "草稿数据无效": "Invalid draft data",
    "提交前必须先打开项目": "Open the item before submitting",
    "Pages 静态版不支持该请求": (
        "The static Pages version does not support this request"
    ),
    "备份文件不是有效 JSON": "The backup file is not valid JSON",
    "备份文件与当前 Pages 实验版本不兼容": (
        "The backup is incompatible with the current Pages study version"
    ),
    "此浏览器中该席位已属于另一化名，拒绝导入": (
        "This slot belongs to another pseudonym in this browser; import refused"
    ),
    "完整浏览器备份已导入。页面将重新载入": (
        "Complete browser backup imported. The page will reload"
    ),
    "同一浏览器恢复本地进度": (
        "resume local progress in the same browser"
    ),
    "此浏览器自动保存草稿": "this browser automatically saves drafts",
    "进度已保存在此浏览器": "progress is saved in this browser",
    "已恢复此浏览器中的进度": "restored progress from this browser",
    "草稿已保存在浏览器": "draft saved in this browser",
    "正在保存浏览器草稿": "saving browser draft",
    "浏览器保存失败": "browser save failed",
    "已读取浏览器最新草稿": "loaded the latest browser draft",
    "研究者分配的席位编号": "Researcher-assigned slot",
    "请使用研究者发送给您的唯一编号，不要与他人共用": (
        "Use the unique slot sent by the researcher; do not share it"
    ),
    "GitHub Pages 试运行：进度只保存在当前浏览器。"
    "完成后必须下载结果 JSON 并交回研究者": (
        "GitHub Pages pilot: progress is stored only in this browser. "
        "Download the result JSON and return it to the researcher when done"
    ),
    "下载结果与进度 JSON": "Download results and progress JSON",
    "下载跨浏览器备份": "Download cross-browser backup",
    "从完整浏览器备份恢复": "Restore from complete browser backup",
    "备份中的判断记录无效": "Invalid judgment record in backup",
    "备份中的制品哈希不匹配": "Artifact hash mismatch in backup",
    "备份中的时间记录无效": "Invalid timestamp record in backup",
    "备份中的参与者版本绑定无效": (
        "Invalid participant version binding in backup"
    ),
    "备份中的参与者身份字段无效": (
        "Invalid participant identity fields in backup"
    ),
    "备份中的 PIN 盐值无效": "Invalid PIN salt in backup",
    "备份中的教程完成时间无效": (
        "Invalid instruction-completion time in backup"
    ),
    "备份中的项目状态无效": "Invalid item state in backup",
    "备份中的开始时间无效": "Invalid start time in backup",
    "备份中的草稿无效": "Invalid draft in backup",
    "同名本地进度与备份的身份或 PIN 绑定冲突": (
        "The local profile and backup have conflicting identity or PIN bindings"
    ),
    "备份与本地判断具有相同时间但内容冲突": (
        "Backup and local judgment conflict at the same timestamp"
    ),
    "人工评判收集总表": "Human-evaluation collection dashboard",
    "偏好计数仅用于完整性监控；不得据此改变冻结设计或停止规则": (
        "Preference counts are for completeness monitoring only and must "
        "not change the frozen design or stopping rule"
    ),
    "返回评判入口": "Return to evaluation",
    "受保护页面": "Protected page",
    "输入管理员令牌": "Enter administrator token",
    "令牌仅保存在当前浏览器标签页，不会写入网址或本地存储": (
        "The token remains in this browser tab and is not written to the "
        "URL or local storage"
    ),
    "读取总表": "Load dashboard",
    "已提交判断": "Submitted judgments",
    "已注册评判者": "Registered evaluators",
    "完成全部目录": "Completed full catalog",
    "名评判者": "evaluators",
    "覆盖完整项目": "Fully covered items",
    "数据导出": "Data exports",
    "尚未读取": "Not loaded",
    "分析 JSONL": "Analysis JSONL",
    "项目汇总 CSV": "Item summary CSV",
    "进度 CSV": "Progress CSV",
    "私有名册 CSV": "Private roster CSV",
    "240 项覆盖表": "240-item coverage",
    "评判者进度": "Evaluator progress",
    "搜索地图、项目或评判者": "Search maps, items, or evaluators",
    "行": "rows",
    "地图": "Map",
    "匿名项目": "Anonymous item",
    "覆盖": "Coverage",
    "已分配": "Assigned",
    "匿名编号": "Anonymous ID",
    "运营化名": "Operational pseudonym",
    "进度": "Progress",
    "教程": "Instructions",
    "注册时间": "Registered",
    "最近登录": "Last sign-in",
    "已完成": "Complete",
    "未完成": "Incomplete",
    "封存": "sealed",
}
START_RUBRIC_HTML = """
            <section class="start-rubric" aria-labelledby="start-rubric-title">
              <p class="kicker">所有项目只有一个问题</p>
              <h2 id="start-rubric-title">路线 A 和路线 B，哪条整体更好？</h2>
              <p>
                根据任务指令和两张匿名路线图，必须选择 A 或 B。
                不区分路线是否完成，不做分项评分，也不猜测生成方法。
              </p>
            </section>
"""
START_RUBRIC_CSS = """

/* GitHub Pages start-page forced-choice rule. */
.toast-region {
  pointer-events: none;
}

.language-switch {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 8px 14px;
  border: 1px solid rgba(18, 60, 59, 0.22);
  border-radius: 999px;
  background: var(--forest);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.02em;
  text-decoration: none;
  box-shadow: 0 8px 24px rgba(18, 60, 59, 0.2);
}

.language-switch:hover,
.language-switch:focus-visible {
  background: #1b5753;
  outline: 3px solid rgba(229, 167, 70, 0.45);
  outline-offset: 2px;
}

.start-rubric {
  max-width: 690px;
  margin-top: 26px;
  padding: 22px;
  border: 1px solid rgba(27, 87, 83, 0.2);
  border-radius: 18px;
  background: var(--mint-light);
  box-shadow: 0 14px 38px rgba(31, 50, 47, 0.08);
}

.start-rubric h2 {
  margin: 0;
  color: var(--forest);
  font-size: 25px;
  letter-spacing: -0.025em;
}

.start-rubric > p:last-child {
  margin: 10px 0 0;
  color: #59645f;
  font-size: 14px;
  line-height: 1.65;
}

.pairwise-choice-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  padding: 24px;
}

.pairwise-choice-card {
  position: relative;
  cursor: pointer;
}

.pairwise-choice-card input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.pairwise-choice-card > span {
  min-height: 112px;
  display: grid;
  place-items: center;
  gap: 5px;
  padding: 20px;
  border: 2px solid var(--line);
  border-radius: 16px;
  background: white;
  color: var(--forest);
  font-size: 16px;
  font-weight: 800;
  text-align: center;
  transition: border-color 150ms ease, background 150ms ease, transform 150ms ease;
}

.pairwise-choice-card > span strong {
  font-family: Georgia, serif;
  font-size: 34px;
}

.pairwise-choice-card:hover > span {
  transform: translateY(-2px);
  border-color: var(--forest-2);
}

.pairwise-choice-card input:checked + span {
  border-color: var(--forest);
  background: var(--mint-light);
  box-shadow: 0 0 0 3px rgba(27, 87, 83, 0.12);
}

.pairwise-choice-card input:focus-visible + span {
  outline: 3px solid rgba(229, 167, 70, 0.5);
  outline-offset: 3px;
}

@media (max-width: 600px) {
  .language-switch {
    min-height: 36px;
    padding: 7px 12px;
  }

  .start-rubric {
    padding: 18px;
  }

  .pairwise-choice-group {
    grid-template-columns: 1fr;
    padding: 18px;
  }
}
"""

SIMPLE_TUTORIAL_HTML = """
        <section class="view tutorial-view" id="tutorial-view">
          <div class="page-heading">
            <div>
              <p class="kicker">开始前 · 约 1 分钟</p>
              <h1>每项只做一次 A/B 二选一</h1>
              <p>不判断是否完成，不做分项评分，也没有平局选项。</p>
            </div>
            <span class="step-chip">说明 1 / 1</span>
          </div>

          <div class="tutorial-layout">
            <div class="tutorial-main">
              <article class="instruction-card">
                <div class="mini-map" aria-label="路线图例示意">
                  <div class="terrain-grid" aria-hidden="true"></div>
                  <span class="mini-start">S</span>
                  <span class="mini-goal">G</span>
                  <span class="mini-agent agent-one"></span>
                  <span class="mini-agent agent-two"></span>
                  <span class="mini-agent agent-three"></span>
                  <span class="mini-path path-one"></span>
                  <span class="mini-path path-two"></span>
                </div>
                <div>
                  <p class="kicker">唯一问题</p>
                  <h2>路线 A 和路线 B，哪条整体更好？</h2>
                  <p>
                    两张图使用相同地图、任务指令、图例和渲染规则。
                    结合任务指令与可见路线整体判断，必须选择 A 或 B；
                    A/B 只是匿名位置，不代表具体方法。
                  </p>
                </div>
              </article>
            </div>

            <aside class="tutorial-checklist">
              <p class="kicker">确认理解</p>
              <h2>开始评判前</h2>
              <label class="check-card">
                <input type="checkbox" class="tutorial-check">
                <span>
                  <strong>我会直接选择 A 或 B</strong>
                  不区分是否完成，不做分项评分，不猜测生成方法。
                </span>
              </label>
              <button class="primary-button wide" id="finish-tutorial" type="button" disabled>
                解锁我的 240 项完整目录
                <span aria-hidden="true">→</span>
              </button>
            </aside>
          </div>
        </section>

"""

FORCED_CHOICE_RATING_JS = r"""
function ratingSection() {
  return `
    <section class="rating-section" data-choice-section>
      <header class="rating-heading">
        <span class="endpoint-number">选择</span>
        <div>
          <h2>路线 A 和路线 B，哪条整体更好？</h2>
          <p>结合任务指令和两张匿名路线图，必须选择一条；不区分是否完成，不做分项评分。</p>
        </div>
        <span class="endpoint-tag">A/B 二选一</span>
      </header>
      <div class="pairwise-choice-group" role="radiogroup" aria-label="选择整体更好的路线">
        <label class="pairwise-choice-card">
          <input type="radio" name="pairwise-choice" value="A" data-rating-field>
          <span><strong>A</strong>选择路线 A</span>
        </label>
        <label class="pairwise-choice-card">
          <input type="radio" name="pairwise-choice" value="B" data-rating-field>
          <span><strong>B</strong>选择路线 B</span>
        </label>
      </div>
    </section>
  `;
}
"""

FORCED_CHOICE_STATE_JS = r"""
function applyDraft(draft) {
  const choice = draft?.payload?.choice;
  state.activeSeconds = Number(draft?.active_seconds || 0);
  state.draftRevision = Number(draft?.revision || 0);
  if (choice === "A" || choice === "B") {
    const input = document.querySelector(
      `input[name="pairwise-choice"][value="${choice}"]`,
    );
    if (input) input.checked = true;
  }
}

function draftPayload() {
  const selected = document.querySelector(
    'input[name="pairwise-choice"]:checked',
  );
  return { choice: selected?.value || null };
}

function finalChoice() {
  const choice = draftPayload().choice;
  if (choice !== "A" && choice !== "B") {
    document
      .querySelector("[data-choice-section]")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    throw new Error("请选择路线 A 或路线 B。");
  }
  return choice;
}
"""

FORCED_CHOICE_EVENTS_JS = r"""
function updateCharacterCounts() {}

function bindRatingEvents() {
  const form = document.querySelector("#rating-form");
  form.oninput = (event) => {
    if (event.target.matches("[data-rating-field]")) {
      scheduleDraftSave();
    }
  };
  form.onclick = null;
  form.onkeydown = null;
  form.onchange = null;
}
"""

FORCED_CHOICE_SUBMIT_JS = r"""
async function submitRating(event) {
  event.preventDefault();
  let choice;
  try {
    choice = finalChoice();
  } catch (error) {
    toast(error.message, "error");
    return;
  }
  const button = $("#submit-rating");
  button.disabled = true;
  window.clearTimeout(state.saveTimer);
  state.saveTimer = null;
  state.saveQueued = false;
  const activeItem = state.activeItem;
  try {
    const result = await api(`/api/item/${activeItem.item_id}/submit`, {
      method: "POST",
      body: JSON.stringify({
        choice,
        active_seconds: Math.max(0.001, state.activeSeconds),
      }),
    });
    localStorage.removeItem(localDraftKey(activeItem.item_id));
    toast(`项目 ${activeItem.catalog_number} 已提交；仍可重新打开修改。`);
    const currentId = activeItem.item_id;
    state.activeItem = null;
    const item = state.catalog.find((row) => row.item_id === currentId);
    if (item) {
      item.status = "submitted";
      item.submitted_utc = result.record.completed_utc;
    }
    await loadDashboard();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
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


def replace_block(
    source: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    label: str,
) -> str:
    if source.count(start_marker) != 1 or source.count(end_marker) != 1:
        raise RuntimeError(f"{label} changed unexpectedly")
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[:start] + replacement + source[end:]


def translate_to_english(source: str, label: str) -> str:
    for before, after in sorted(
        ENGLISH_TRANSLATIONS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        source = source.replace(before, after)
    for before, after in {
        "（": "(",
        "）": ")",
        "，": ", ",
        "。": ".",
        "；": "; ",
        "：": ": ",
        "？": "?",
        "…": "...",
    }.items():
        source = source.replace(before, after)
    remaining = [
        f"{line_number}: {line.strip()}"
        for line_number, line in enumerate(source.splitlines(), start=1)
        if re.search(r"[\u3400-\u9fff]", line.replace("中文", ""))
    ]
    if remaining:
        raise RuntimeError(
            f"{label} contains untranslated Chinese text:\n"
            + "\n".join(remaining[:20])
        )
    return source


def transformed_index(portal: Path) -> str:
    source = (portal / "web" / "index.html").read_text(encoding="utf-8")
    source = source.replace(
        'href="/styles.css"',
        f'href="styles.css?v={ASSET_VERSION}"',
    )
    marker = '<script src="/app.js" defer></script>'
    replacement = (
        f'<script src="static_api.js?v={ASSET_VERSION}" defer></script>\n'
        f'    <script src="app.js?v={ASSET_VERSION}" defer></script>'
    )
    if marker not in source:
        raise RuntimeError("portal script tag changed unexpectedly")
    source = source.replace(marker, replacement)
    topbar_actions = '        <div class="topbar-actions">'
    if source.count(topbar_actions) != 1:
        raise RuntimeError("portal topbar actions changed unexpectedly")
    source = source.replace(
        topbar_actions,
        topbar_actions
        + '\n          <a class="language-switch" data-language-switch '
        'href="index-en.html" lang="en">English</a>',
        1,
    )
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
    page_replacements = {
        "每张地图恰好一项。目录与顺序已冻结，提交后该项不可修改。": (
            "完整目录包含 240 项；可以分多次完成，已提交项目仍可重新修改。"
        ),
        "<span>/ 30</span>": "<span>/ 240</span>",
        "<h2>30 项 · 30 张地图</h2>": (
            "<h2>240 项 · 30 张地图 · 8 组比较</h2>"
        ),
        '<strong id="judge-count-label">项目 1 / 30</strong>': (
            '<strong id="judge-count-label">项目 1 / 240</strong>'
        ),
        "<strong>提交前请再次确认</strong>": (
            "<strong>保存当前选择</strong>"
        ),
        "<span>最终提交后，该项目将锁定且不能由评判者修改。</span>": (
            "<span>提交后仍可从目录重新打开，并用新选择覆盖旧选择。</span>"
        ),
        "\n                  最终提交\n": "\n                  提交选择\n",
    }
    for before, after in page_replacements.items():
        if source.count(before) != 1:
            raise RuntimeError(
                f"portal full-catalog text changed unexpectedly: {before}"
            )
        source = source.replace(before, after, 1)
    source = replace_block(
        source,
        '    <dialog id="confirm-dialog">',
        "  </body>",
        "",
        "portal confirmation dialog",
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
    source = replace_block(
        source,
        '        <section class="view tutorial-view" id="tutorial-view">',
        '        <section class="view dashboard-view" id="dashboard-view">',
        SIMPLE_TUTORIAL_HTML,
        "portal tutorial",
    )
    route_note_before = """            <span>
              高程图用于判断升降；掩体图用于判断隐蔽与协同。数字 0–5 分别对应
              t=0、19、38、58、77、96，同编号标记表示同一时刻。
            </span>"""
    route_note_after = """            <span>
              左侧显示高程，右侧显示掩体；数字 0–5 分别对应
              t=0、19、38、58、77、96，同编号标记表示同一时刻。
            </span>"""
    if source.count(route_note_before) != 1:
        raise RuntimeError("portal route-map note changed unexpectedly")
    source = source.replace(route_note_before, route_note_after, 1)
    if 'href="/' in source or 'src="/' in source:
        raise RuntimeError("generated Pages index still contains a root URL")
    return source


def transformed_index_en(portal: Path) -> str:
    source = transformed_index(portal)
    replacements = {
        '<html lang="zh-CN">': '<html lang="en">',
        f'href="styles.css?v={ASSET_VERSION}"': (
            f'href="styles.css?v={ASSET_VERSION}"'
        ),
        f'src="static_api.js?v={ASSET_VERSION}"': (
            f'src="static_api-en.js?v={ASSET_VERSION}"'
        ),
        f'src="app.js?v={ASSET_VERSION}"': (
            f'src="app-en.js?v={ASSET_VERSION}"'
        ),
        (
            'href="index-en.html" lang="en">English</a>'
        ): 'href="index.html" lang="zh-CN">中文</a>',
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise RuntimeError(
                f"English index binding changed unexpectedly: {before}"
            )
        source = source.replace(before, after, 1)
    return translate_to_english(source, "English index")


def transformed_styles(portal: Path) -> str:
    source = (portal / "web" / "styles.css").read_text(encoding="utf-8")
    return source.rstrip() + START_RUBRIC_CSS.rstrip() + "\n"


def transformed_app(portal: Path) -> str:
    source = (portal / "web" / "app.js").read_text(encoding="utf-8")
    evidence_state = """  evidence: {
    all_sample: [],
    conditional_semantic: [],
  },
"""
    if source.count(evidence_state) != 1:
        raise RuntimeError("portal evidence state changed unexpectedly")
    source = source.replace(evidence_state, "", 1)
    evidence_reset = (
        "    state.evidence = { all_sample: [], conditional_semantic: [] };\n"
    )
    if source.count(evidence_reset) != 1:
        raise RuntimeError("portal evidence reset changed unexpectedly")
    source = source.replace(evidence_reset, "", 1)
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
    source = source.replace(recovery_before, recovery_after, 1)
    app_replacements = {
        "const total = state.catalog.length || 30;": (
            "const total = state.catalog.length || 240;"
        ),
        'button.textContent = "30 项全部完成";': (
            "button.textContent = `${total} 项全部完成`;"
        ),
        (
            '          ${item.status === "submitted" ? "disabled" : ""}\n'
        ): "",
        (
            '  if (!catalogItem || catalogItem.status === "submitted") '
            "return;"
        ): (
            "  if (!catalogItem) return;\n"
            '  $("#submit-rating").disabled = false;'
        ),
        (
            "`已提交 ${completed} 项，剩余 ${total - completed} 项；"
            "服务器自动保存草稿。`"
        ): (
            "`已提交 ${completed} 项，剩余 ${total - completed} 项；"
            "已提交项目仍可重新修改。`"
        ),
    }
    for before, after in app_replacements.items():
        if source.count(before) != 1:
            raise RuntimeError(
                f"portal full-catalog app changed unexpectedly: {before}"
            )
        source = source.replace(before, after, 1)
    source = replace_block(
        source,
        "function ratingSection(",
        "\nfunction localDraftKey",
        FORCED_CHOICE_RATING_JS.rstrip() + "\n",
        "portal rating form",
    )
    source = replace_block(
        source,
        "function applyDraft(",
        "\nfunction setSaveState",
        FORCED_CHOICE_STATE_JS.rstrip() + "\n",
        "portal rating state",
    )
    source = replace_block(
        source,
        "function updateCharacterCounts(",
        "\nfunction startActiveTimer",
        FORCED_CHOICE_EVENTS_JS.rstrip() + "\n",
        "portal rating events",
    )
    source = replace_block(
        source,
        "function confirmFinalSubmission(",
        "\nasync function submitRating(",
        "",
        "portal confirmation logic",
    )
    source = replace_block(
        source,
        "async function submitRating(",
        "\nfunction openAdmin",
        FORCED_CHOICE_SUBMIT_JS.rstrip() + "\n",
        "portal rating submission",
    )
    rating_render_before = """    $("#endpoint-forms").innerHTML =
      ratingSection("all_sample", 1, false) +
      (item.both_completed
        ? ratingSection("conditional_semantic", 2, true)
        : "");"""
    rating_render_after = """    $("#endpoint-forms").innerHTML =
      ratingSection();"""
    if source.count(rating_render_before) != 1:
        raise RuntimeError("portal rating rendering changed unexpectedly")
    source = source.replace(rating_render_before, rating_render_after, 1)
    admin_head_before = """        <th>Overall A</th><th>Overall B</th><th>平局</th>
        <th>条件 A</th><th>条件 B</th><th>条件平局</th>"""
    admin_head_after = """        <th>选择 A</th><th>选择 B</th>"""
    admin_cells_before = """            <td>${row.all_A ?? "封存"}</td><td>${row.all_B ?? "封存"}</td><td>${row.all_tie ?? "封存"}</td>
            <td>${row.conditional_A ?? "封存"}</td><td>${row.conditional_B ?? "封存"}</td><td>${row.conditional_tie ?? "封存"}</td>"""
    admin_cells_after = """            <td>${row.choice_A ?? "封存"}</td><td>${row.choice_B ?? "封存"}</td>"""
    if (
        source.count(admin_head_before) != 1
        or source.count(admin_cells_before) != 1
    ):
        raise RuntimeError("portal admin preference table changed unexpectedly")
    return source.replace(
        admin_head_before, admin_head_after, 1
    ).replace(admin_cells_before, admin_cells_after, 1)


def transformed_app_en(portal: Path) -> str:
    source = transformed_app(portal).replace('"zh-CN"', '"en-US"')
    return translate_to_english(source, "English app")


def transformed_static_api_en() -> str:
    source = (ROOT / "src" / "static_api.js").read_text(encoding="utf-8")
    replacements = {
        "consent_text: manifest.consent_text,": (
            "consent_text: manifest.consent_text_en,"
        ),
        "directive: item.directive,": "directive: manifest.directive_en,",
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise RuntimeError(
                f"English static API binding changed unexpectedly: {before}"
            )
        source = source.replace(before, after, 1)
    source = replace_block(
        source,
        "  function replaceTextNode(",
        "\n  function installStaticInterface(",
        "  function replaceTextNode() {}\n",
        "English browser-copy replacement",
    )
    return translate_to_english(source, "English static API")


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
        "slot_assignments": manifest["slot_assignments"],
        "directive": manifest["directive"],
        "directive_en": manifest["directive_en"],
        "consent_version": manifest["consent_version"],
        "consent_text_sha256": manifest["consent_text_sha256"],
        "consent_text_en_sha256": manifest["consent_text_en_sha256"],
        "collection_runtime_sha256": {
            name: manifest["runtime_sha256"][name]
            for name in COLLECTION_RUNTIME_FILES
        },
        "items": [
            {
                "item_id": item["item_id"],
                "blind_map_id": item["blind_map_id"],
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


def complete_catalog_assignments(
    items: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Return five balanced orderings, each containing all 240 items."""
    by_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_map[int(item["map_index"])].append(item)
    if set(by_map) != set(range(30)):
        raise RuntimeError("full-catalog assignment requires map indices 0–29")
    for map_index, candidates in by_map.items():
        candidates.sort(key=lambda item: int(item["item_index"]))
        if (
            len(candidates) != 8
            or [int(item["item_index"]) for item in candidates]
            != list(range(8))
        ):
            raise RuntimeError(
                f"full-catalog assignment is invalid for map {map_index}"
            )

    assignments: dict[str, list[str]] = {}
    for slot in range(RATER_SLOT_MIN, RATER_SLOT_MAX + 1):
        ordered: list[str] = []
        for round_index in range(8):
            for step in range(30):
                map_index = (
                    step + 7 * round_index + 6 * slot
                ) % 30
                item_index = (
                    round_index + map_index + slot
                ) % 8
                ordered.append(
                    str(by_map[map_index][item_index]["item_id"])
                )
        if len(ordered) != ITEMS_PER_RATER or len(set(ordered)) != 240:
            raise RuntimeError(
                f"slot {slot} does not contain the complete catalog"
            )
        assignments[str(slot)] = ordered
    return assignments


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
    (staging / "index-en.html").write_text(
        transformed_index_en(portal), encoding="utf-8"
    )
    (staging / "app.js").write_text(
        transformed_app(portal), encoding="utf-8"
    )
    (staging / "app-en.js").write_text(
        transformed_app_en(portal), encoding="utf-8"
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
    (staging / "static_api-en.js").write_text(
        transformed_static_api_en(), encoding="utf-8"
    )
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
                if key not in {"judge_source", "both_completed"}
            }
        )

    runtime_hashes = {
        name: sha256(staging / name) for name in RUNTIME_FILES
    }
    consent_text = (ROOT / "src" / "PILOT_TEST_NOTICE.txt").read_text(
        encoding="utf-8"
    )
    consent_text_en = (
        ROOT / "src" / "PILOT_TEST_NOTICE.en.txt"
    ).read_text(encoding="utf-8")
    consent_text_sha256 = hashlib.sha256(
        consent_text.encode("utf-8")
    ).hexdigest()
    consent_text_en_sha256 = hashlib.sha256(
        consent_text_en.encode("utf-8")
    ).hexdigest()
    slot_assignments = complete_catalog_assignments(public_items)
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
        "rater_slot_min": RATER_SLOT_MIN,
        "rater_slot_max": RATER_SLOT_MAX,
        "item_count": 240,
        "map_count": 30,
        "items_per_map": 8,
        "items_per_rater": ITEMS_PER_RATER,
        "judgments_per_item_if_all_slots_complete": JUDGMENTS_PER_ITEM,
        "slot_assignments": slot_assignments,
        "directive": str(manifest["directive"]),
        "directive_en": DIRECTIVE_EN,
        "consent_version": "pages-forced-choice-full-catalog-notice-v1",
        "consent_text": consent_text,
        "consent_text_sha256": consent_text_sha256,
        "consent_text_en": consent_text_en,
        "consent_text_en_sha256": consent_text_en_sha256,
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
        or manifest.get("rater_slot_min") != RATER_SLOT_MIN
        or manifest.get("rater_slot_max") != RATER_SLOT_MAX
        or manifest.get("item_count") != 240
        or manifest.get("map_count") != 30
        or manifest.get("items_per_map") != 8
        or manifest.get("items_per_rater") != ITEMS_PER_RATER
        or manifest.get("judgments_per_item_if_all_slots_complete")
        != JUDGMENTS_PER_ITEM
        or manifest.get("consent_version")
        != "pages-forced-choice-full-catalog-notice-v1"
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
        or hashlib.sha256(
            str(manifest.get("consent_text_en", "")).encode("utf-8")
        ).hexdigest()
        != manifest.get("consent_text_en_sha256")
        or manifest.get("consent_text_en")
        != (
            ROOT / "src" / "PILOT_TEST_NOTICE.en.txt"
        ).read_text(encoding="utf-8")
        or manifest.get("directive_en") != DIRECTIVE_EN
    ):
        raise RuntimeError(
            "generated bilingual consent or directive mismatch"
        )
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
    map_ids = sorted(map_counts)
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
    assignments = manifest.get("slot_assignments")
    if (
        not isinstance(assignments, dict)
        or set(assignments)
        != {
            str(slot)
            for slot in range(RATER_SLOT_MIN, RATER_SLOT_MAX + 1)
        }
    ):
        raise RuntimeError("generated full-catalog slot table is invalid")
    if assignments != complete_catalog_assignments(items):
        raise RuntimeError(
            "generated full-catalog slot ordering changed unexpectedly"
        )
    assignment_counts = {item_id: 0 for item_id in seen}
    for slot, assigned in assignments.items():
        if (
            not isinstance(assigned, list)
            or len(assigned) != ITEMS_PER_RATER
            or len(set(assigned)) != ITEMS_PER_RATER
            or set(assigned) != seen
        ):
            raise RuntimeError(
                f"slot {slot} does not contain all 240 items exactly once"
            )
        for item_id in assigned:
            assignment_counts[item_id] += 1
    if set(assignment_counts.values()) != {JUDGMENTS_PER_ITEM}:
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
