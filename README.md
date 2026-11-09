# prd-check

A Claude Code skill that checks a PRD against your codebase. It reads the PRD, breaks it into testable requirements, finds the code for each one, and produces a full PDF report showing what matches, what's partial, what's wrong and what's missing. Then it walks you through every mismatch so you can decide whether the **code** or the **PRD** needs fixing, and makes the change.

It also keeps platforms in sync: when one platform changes a PRD, the change is logged on the PRD so every other platform's next run checks it first.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3, for the PDF report
- Google Chrome, Chromium or Microsoft Edge, for printing the PDF. Without one you get an HTML report you can print yourself.
- A connector for wherever your PRDs live:
  - **Confluence / Jira:** the **Atlassian MCP** connector. Connect it in claude.ai → Settings → Connectors, then run `/mcp` in Claude Code and sign in to **claude.ai Atlassian MCP**. The older plain "Atlassian" connector no longer works.
  - **Google Docs:** the Google Docs connector.
  - **Local PDF or Markdown files, or pasted text:** nothing extra.

## Install

In Claude Code, run:

```
/plugin marketplace add aaron-maestro/prd-check
/plugin install prd-check@prd-check
```

Restart Claude Code (or start a new session) so the skill loads.

To get updates later:

```
/plugin marketplace update prd-check
```

**Without the plugin system:** copy `skills/prd-check/` into `~/.claude/skills/prd-check/` for yourself, or into `<your-repo>/.claude/skills/prd-check/` to share it with everyone working in that repo.

## Run it

Open Claude Code in the repo you want to check, then either type `/prd-check` or just ask:

```
/prd-check https://<site>.atlassian.net/wiki/spaces/ABC/pages/123456/My+Feature+PRD
```

```
Check the Topics PRD against this branch
Does the code match PROJ-1234 and its child tickets?
Verify ~/Downloads/feature-prd.pdf against this repo, only the tvOS parts
Run prd-check on every PRD in this Confluence folder: <folder link>
```

You can point it at a Confluence page or folder, a Jira issue or epic, a Google Doc, a Claude Doc, a PDF or Markdown file, or pasted text. With a folder, it lists the PRDs and asks which ones to check.

The first time it runs in a repo, it asks you to confirm which platform the repo is (e.g. `iOS/tvOS`, `Android`, `Web`, `Roku`).

## What happens

1. **Checks for PRD changes.** It first looks for anything that changed in the PRD since your platform last checked: entries in the PRD's change log, plus a diff against the version you checked before.
2. **Verifies the code.** It splits the PRD into requirements and checks each one against the code. It reads the implementation itself, not just matching names.
3. **Writes the PDF report** and opens it. The PDF is saved next to your repo, not inside it, as `PRD-Check-<prd>-<date>.pdf`. Every requirement gets a status:

   | Status | Meaning |
   |---|---|
   | ✅ Match | Implemented as specified |
   | 🟡 Partial | Some of it exists; something's missing |
   | ❌ Mismatch | Implemented differently from the PRD |
   | ⛔ Missing | No implementation found |
   | ➕ Undocumented | In the code, not in the PRD |
   | ❓ PRD unclear | The PRD is ambiguous or contradicts itself |
   | ☑️ Accepted | A known difference you already ruled on |
   | 🔍 Not verifiable here | Lives in another repo, platform, backend or prebuilt binary |

   Related problems are grouped into numbered decisions (`D1`, `D2`, …).
4. **Stops and waits.** Read the PDF at your own pace, then tell Claude you're ready.
5. **Goes through each decision with you.** For each one you pick **Code is wrong**, **PRD is wrong**, **Intentional / accept** or **Skip for now**. Claude never decides for you.
6. **Applies your decisions:**
   - **Code fixes** go on a new branch. Nothing is committed or pushed unless you ask.
   - **PRD fixes** are shown to you as before → after text first, and only applied after you confirm. Each one is logged in the PRD's change log.
7. **Learns.** It saves what it found, so the next run is faster and doesn't re-raise items you've already settled.

## What to commit

The skill keeps its notes in your repo:

```
.claude/prd-check/
├── learnings.md     ← platform, PRD versions checked, PRD → code map, past decisions
└── snapshots/       ← PRD text as of the last check, used to spot changes
```

Commit this folder. It gives your whole team the same map and decisions, and it's how the next run knows what changed in the PRD. Claude leaves it uncommitted so you can review it first.

If your repo publishes some paths to a public repo, make sure `.claude/` isn't one of them.

## Keeping platforms in sync

When a run changes a PRD, it adds a row to a **PRD Change Log** table at the end of the PRD page:

| Date | § | Change (before → after) | Why | Changed by | iOS/tvOS | Android | Web | Roku |
|---|---|---|---|---|---|---|---|---|
| 2026-11-09 | 3.4 | `refresh.max_age_ms` → `RefreshIntervalMs` | Matches shipped iOS API | Dev · iOS/tvOS | ✅ | ⏳ | ⏳ | — |

Cell values: ✅ verified · ⏳ needs checking · 🔧 fix in progress · ⚠️ disputed · — not applicable.

- **The platform that made the change** marks itself ✅ and every other platform ⏳.
- **When another platform runs prd-check**, it checks its ⏳ rows first. If its code already matches, it marks ✅ once you confirm. If not, you decide whether to fix the code, or dispute the change (⚠️, with a comment for the PRD owner).
- **Each platform only ever updates its own column.**
- **Jira tickets (optional):** after a change in behaviour, the skill offers to open one ticket per ⏳ platform, linked to the epic. It only creates them after you say yes.

Edits a PM makes by hand are caught too: each run diffs the PRD against the snapshot from your last check and flags unlogged changes.

For this to work, **every platform's repo needs to run prd-check** and commit its `.claude/prd-check/` folder.

## Troubleshooting

- **"deprecated HTTP+SSE transport" error from Confluence/Jira.** You're on the old Atlassian connector. Connect **Atlassian MCP** instead (see Requirements).
- **No PDF, only an HTML file.** No Chrome, Chromium or Edge was found. Open the `.html` file and print it to PDF from your browser.
- **The skill doesn't trigger.** Start a new Claude Code session after installing, or type `/prd-check` explicitly.
- **Lots of 🔍 rows.** That's expected when logic lives outside the repo, for example in a shared KMP binary or the backend. The report lists them under "Check elsewhere" with where to look.

## Repo layout

```
.claude-plugin/
  plugin.json             plugin name, version, description
  marketplace.json        lets people install from this repo
skills/prd-check/
  SKILL.md                the skill's instructions
  scripts/render_report.py  renders the report JSON to HTML and PDF
```

When you change the skill, bump `version` in `.claude-plugin/plugin.json` so `/plugin marketplace update` picks it up.
