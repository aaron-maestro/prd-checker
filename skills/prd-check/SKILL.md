---
name: prd-check
description: Cross-reference a PRD (Confluence page or folder, Jira epic, Claude Doc, Google Doc, PDF or local Markdown) against the codebase, and produce a full PDF report with a verification table showing which requirements are implemented correctly, partially, wrongly or not at all. For every mismatch it asks the developer whether the code or the PRD is wrong, then fixes the code on a branch or drafts the PRD change. Keeps platforms in sync: every PRD edit is logged in a change-log table on the PRD with per-platform verification status (and optional Jira tickets), and each run diffs the PRD against the last version that platform checked. Learns each project's PRD-to-code mappings and past decisions so later checks are faster and don't re-flag settled items. Use when the user asks to check, verify, audit or compare code against a PRD, spec, requirements doc or ticket, asks "does the code match the PRD", "are we done with the PRD", or runs /prd-check.
---

# PRD Check

Verify that the code does what the PRD says, and that the PRD says what the code does. Neither side is assumed correct: a mismatch is a question for the developer, not a verdict.

## 1. Gather inputs

Work out from the request (ask only for what's missing):

- **PRD source.** Accept any of:
  - Confluence URL or page title → Atlassian connector (get page, or CQL search by title)
  - Jira key or epic → Atlassian connector: the issue plus its child issues (JQL `parent = KEY`). Acceptance criteria count as requirements.
  - Claude Docs artifact link → load the docs skill, then read it
  - Google Doc → Google Docs connector
  - PDF → `pdf` skill if available, otherwise Read; `.md` / `.txt` → Read
  - Pasted text → use as-is

  If the needed connector isn't connected, tell the developer which one to connect, or ask them to paste or export the PRD.
- **Codebase and branch.** Default to the current repo and branch. Record `git rev-parse --abbrev-ref HEAD` and short SHA so the report says what was checked.
- **Scope.** Whole PRD, or one section / platform (e.g. "only the tvOS parts").
- **Platform.** Which platform this repo implements (e.g. `iOS/tvOS`, `Android`, `Web`, `Roku`). Read it from `Platform:` in the learnings file. If it isn't there, infer it from the repo (Xcode project → iOS/tvOS, Gradle Android app → Android, etc.), confirm it with the developer once, and record it. The platform names must match the column names in the PRD Change Log (step 7), so reuse any names already on the page.

## 2. Load what's been learned

Read `.claude/prd-check/learnings.md` at the repo root. It lives in the repo so the whole team shares it through git. If it exists it holds:
- **Map**: PRD terms → code locations (feature names, module paths, type names).
- **Decisions**: mismatches the developer already ruled on ("PRD says 30s, code uses 15s — intentional, PRD outdated, accepted 2026-11-09").
- **Conventions**: where features usually live, naming patterns, which PRD sections are out of scope for this repo.

Use the map to jump straight to code. Don't re-raise a mismatch already recorded as an accepted decision unless the PRD or code has changed since; list those as `Accepted` in the table.

## 2b. Check what changed in the PRD since this platform last looked

Do this before extracting requirements, for every PRD in scope. It catches PRD edits made because of another platform's decisions, and edits a PM made by hand.

**PRD Change Log.** Look for a `PRD Change Log` table on the PRD (format in step 7). For each row where this platform's cell is ⏳ or 🔧, verify that change first, against the "after" text. These rows go to the top of the report and become the first decisions.

**Version and snapshot diff.** The learnings file records, per PRD, the version that was checked last: the Confluence page version, a Claude Docs version, or a Jira `updated` timestamp. It also points to a snapshot of the PRD text at `.claude/prd-check/snapshots/<prd-slug>.md`.
- If the version is unchanged, carry on.
- If it changed, or there's no version, diff the current PRD text (markdown) against the snapshot. List each changed section with a before → after summary.
- Re-check every requirement in a changed section first, even ones recorded as ☑️ Accepted, since the decision may no longer hold.
- Changes that came with a Change Log row are already explained. Changes without one are unlogged edits; flag them as such in the report.
- With no snapshot yet (first run), say so in the report and skip the diff.

Put all of this in the report's `prd_changes` list (step 5).

## 3. Extract requirements

Break the PRD into atomic, testable requirements. Number them `R1`, `R2`, … and keep the PRD's own section reference (e.g. `§3.2`). Good requirements are specific: values, states, events, copy, limits, error cases, analytics events, settings/flags, platform availability.

Skip non-requirements (background, goals, open questions), but list open questions separately since they often explain mismatches.

If the PRD itself is ambiguous or contradicts itself, record it as a requirement with status `PRD unclear`.

## 4. Find and verify the code

For each requirement, search the code (Grep/Glob, or an Explore agent for broad sweeps across many requirements, e.g. one agent per PRD section). When a folder or several PRDs are given, list the PRD pages (skip QA specs, tech plans, trackers and guides), ask which to check, and use one general-purpose agent per PRD or feature group in parallel. Brief each with the PRD id, the fetch tool, the repo layout from CLAUDE.md, the status table, and the exact row format to return. Read the actual implementation; a matching name is not proof. Check:

- Values match (timeouts, limits, sizes, colors, copy strings, enum cases).
- Behaviour matches, including edge and error cases the PRD calls out.
- It's wired up: reachable from public API / UI, not dead code or behind a flag that's off.
- Tests exist that cover it (note, don't require).

Also note **code with no PRD counterpart** when it's user-facing or public API: undocumented behaviour is a PRD gap.

Assign one status per row:

| Status | Meaning |
|---|---|
| ✅ Match | Implemented as specified |
| 🟡 Partial | Some of it exists; something's missing |
| ❌ Mismatch | Implemented differently from the PRD |
| ⛔ Missing | No implementation found |
| ➕ Undocumented | In code, not in PRD |
| ❓ PRD unclear | PRD is ambiguous or contradicts itself |
| ☑️ Accepted | Known difference, already ruled on (from learnings) |
| 🔍 Not verifiable here | Belongs to another platform/repo, or lives in a prebuilt binary or backend this repo can't show; say where it should be checked |

🔍 rows aren't raised with the developer in step 6; list them at the end of the report as "check elsewhere".

## 5. Generate the full PDF report, then wait

Always produce a full PDF before asking any questions, so the developer can read everything at their own pace first.

**a. Merge findings into decisions.** Group ❌ and ⛔ rows that are the same underlying issue (e.g. one request-shape mismatch that appears in three PRDs) into numbered decisions `D1`, `D2`, … Each decision lists the PRD rows it covers, a one-sentence issue with the evidence, and `path:line`.

**b. Write the report JSON** to the scratchpad (or a temp dir), in this shape:

```json
{
  "title": "PRD Check: <PRD or folder title>",
  "meta": ["PRD: <link>", "Code: <repo> @ <branch> (<sha>)", "Generated: <YYYY-MM-DD>"],
  "legend": ["MKF/ = path/to/long/prefix/"],
  "prd_changes": [{"prd": "...", "section": "§3.4", "change": "before → after", "source": "Change log 2026-11-09 · Aaron · iOS/tvOS | Unlogged edit (v3 → v5)", "status": "mismatch", "finding": "This platform still sends the old shape"}],
  "decisions": [{"id": "D1", "rows": "K13, V28", "status": "mismatch", "issue": "...", "where": "path:line"}],
  "prds": [{
    "title": "...", "meta": ["Last updated ...", "Status ...", "Owner ..."],
    "rows": [{"id": "R1", "section": "§2.1", "requirement": "...", "location": "path:line", "status": "mismatch", "finding": "..."}],
    "undocumented": ["..."], "open_questions": ["..."], "docs_disagree": ["..."]
  }],
  "learned": ["..."]
}
```

`status` is one of `match`, `partial`, `mismatch`, `missing`, `undocumented`, `unclear`, `accepted`, `elsewhere`. Include **every** row, including ✅ and 🔍; the PDF is the full record. `finding` is one sentence of evidence, not opinion. Wrap code identifiers in backticks.

**c. Render it:**

```bash
python3 "<this skill's folder>/scripts/render_report.py" <report.json> <output.pdf>
```

Save the PDF where the developer will find it: the parent folder of the repo, or wherever they ask, named `PRD-Check-<prd-slug>-<YYYY-MM-DD>.pdf`. Never save it inside the repo. The script prints with headless Chrome/Chromium/Edge. If none is installed it writes only the HTML; tell the developer to open it and print to PDF. Open the PDF for them (`open` on macOS, `xdg-open` on Linux).

**d. Post a short summary in the terminal:**
- the counts per status
- the list of decisions (`D1`: one line each)
- the PDF path

Then **stop and wait**. Tell the developer to read the PDF and say when they're ready to go through the decisions. Don't call `AskUserQuestion` in this turn.

If the user asked for something shareable (for a PM, a channel, a ticket), also offer to attach the PDF, publish the report as an artifact, or post it as a Confluence/Jira comment. Never post without asking.

## 6. Resolve every issue with the developer

Only start once the developer says they've read the report. Start with the PRD changes from step 2b:
- Where this platform's code already matches, ask once, for all of them together, whether to mark them ✅ in the Change Log.
- Where it doesn't match, treat each one as a decision. The options are the same, plus **Dispute the change**: mark the cell ⚠️ and comment on the PRD for the owner and the platform that made the change, explaining why it doesn't work for this platform.

Then walk through the decisions (`D1`…). Then offer to handle the remaining 🟡, ❓ and ➕ rows as one batch: for example, PRD comments for the owners on every ❓ and ➕, and skip 🟡 unless the developer flags some. For each decision or row, ask the developer with `AskUserQuestion` (batch up to 4 rows per call; put the evidence in each question). Options:

- **Code is wrong**: fix the code to match the PRD
- **PRD is wrong**: update the PRD to match the code
- **Intentional / accept**: leave both, record the decision
- **Skip for now**: leave it out of this round

Never decide this yourself. Even when one side looks obviously right, the PM may have changed the requirement, or the code may be a deliberate workaround.

## 7. Apply the decisions

**Code fixes**
- If on the default branch (`main`, `master`, `develop`), create a branch first: `prd-check/<prd-slug>` or match the repo's branch naming (check `git branch -a` and any CLAUDE.md / CONTRIBUTING conventions). If the developer works with worktrees, follow their setup.
- Make the changes, following the repo's style, CLAUDE.md and any project skills. Build/test if the project has a quick way to.
- Do **not** commit or push unless the developer asks. Summarise the diff per requirement.

**PRD fixes**
- Draft the exact replacement text for each section (before → after), and show it to the developer.
- Only after explicit confirmation, apply it: a Confluence page update, a Jira edit/comment, or a Claude Docs update. For Google Docs or PDFs, give the text for them to paste. If they'd rather not edit the PRD directly, offer a comment on the page tagged for the PRD owner instead.
- **Log every PRD change** in the same edit, so other platforms find out. Add a row to a `PRD Change Log` table at the end of the PRD. Create the table under a `## PRD Change Log` heading if it's missing.

  | Date | § | Change (before → after) | Why | Changed by | iOS/tvOS | Android | Web | Roku |
  |---|---|---|---|---|---|---|---|---|
  | 2026-11-09 | 3.4 | `refresh.max_age_ms` → `RefreshIntervalMs` | Matches shipped iOS API | Aaron · iOS/tvOS | ✅ | ⏳ | ⏳ | — |

  - **Columns:** one per platform named in the PRD's metadata (e.g. "Platforms: Android TV, tvOS/iOS, Web"). If none are named, ask the developer which platforms the feature ships on.
  - **Cell values:** ✅ verified matches · ⏳ needs checking · 🔧 fix in progress (add the branch or ticket) · ⚠️ disputed (link the comment) · — not applicable.
  - **Setting cells:** this platform's cell is ✅ (or 🔧 if the code is still being fixed). Every other platform's cell is ⏳.
  - **Updating cells:** on later runs, this platform only edits its own column, and only after the developer confirms (step 6). Never change another platform's cells.
- **Offer a Jira ticket per affected platform.** After logging a PRD change that alters behaviour other platforms may have built the old way, offer to create one ticket for each platform marked ⏳, linked to the PRD's epic, or ask for the epic.
  - **Title:** `PRD change: <PRD title> §<section>: <short change>`.
  - **Body:** the before → after, the reason, a link to the PRD, and "Run prd-check on your repo to verify".
  - **Who it's for:** assign the ticket to the platform's feature lead or component, if the PRD names one.
  - **Confirm first:** list the tickets you'd create and wait for the developer's yes, since they notify other teams.
  - **After creating:** put the ticket key in the cell (`⏳ CTV-1234`).
  - **Wording changes:** skip the offer for changes that don't alter behaviour (typos, clarifications).

**Accepted / skipped** → nothing changes; recorded in learnings.

Finish with a short closing table: `# | Decision | Action taken | Where (branch/file or PRD link)`.

## 8. Learn

Update `.claude/prd-check/learnings.md` in the repo (create it from the template below if missing). Leave it uncommitted alongside any code fixes, and mention that committing it shares the learnings with the team. Keep it short and current; edit entries rather than appending duplicates, and drop entries whose code no longer exists.

- Add/correct **Map** entries for every requirement you located.
- Add a **Decisions** entry for each Accepted or PRD-is-wrong ruling, with PRD title, requirement, date, and who decided (the developer).
- Add **Conventions** you discovered (where features live, PRD sections that never apply to this repo, platform splits).
- Update **PRD versions**: for each PRD checked, record its current version (after any PRD edits made this run) and write the current PRD text to `.claude/prd-check/snapshots/<prd-slug>.md`. The next run diffs against it. Never put snapshots in paths that ship publicly (check CLAUDE.md).
- Append one line to **History**: date, PRD and version, branch, summary counts.

Tell the developer in one line what was learned.

### Learnings template

```markdown
# PRD Check learnings: <project>

Platform: <iOS/tvOS | Android | Web | Roku | …>

## PRD versions
- <PRD title> · <Confluence id / link> · v<N> · checked <YYYY-MM-DD> · snapshot: snapshots/<prd-slug>.md

## Map
- <PRD term / feature> → <path or type> (<notes>)

## Decisions
- <YYYY-MM-DD> · <PRD title> R# "<requirement>": <Accepted | PRD updated | Code fixed> — <reason>

## Conventions
- <e.g. Panels live in src/panels/<Name>/; analytics events in src/analytics/events.ts>

## History
- <YYYY-MM-DD> · <PRD title> v<N> · <branch>@<sha> · 14✅ 2🟡 3❌ 1⛔
```
