---
name: job-search
description: Job search automation. Guided setup, JSearch job fetching, tailored cover letters and resumes, LinkedIn connection matching, outreach tracking with response analytics, and a local HTML dashboard. Use when the user wants to configure, run, or query their job search agent.
---

# /job-search

Multi-function slash command that runs every job-search workflow for this project: first-time setup, fetching jobs, generating cover letters and outreach messages, tracking applications, and reporting on outreach performance. Dispatches by subcommand.

## Project location

This skill is installed globally at `~/.claude/skills/job-search/`. Before running any Python script (`python scripts/fetch_jobs.py`, `python scripts/dashboard.py`, `python setup.py --from-config`, etc.), `cd` to that directory first. Every Bash call that touches the project should start with:

    cd ~/.claude/skills/job-search

If the user installed elsewhere (uncommon), substitute the actual install path. The default install command from the README places the project at `~/.claude/skills/job-search/`.

---

## How to execute

You are running this skill inside Claude Code, with access to the project at the current working directory.

**Parse the invocation:**

- `/job-search` with no argument → show the usage block below and stop.
- `/job-search <subcommand> [args]` → find the matching subcommand section and follow its instructions.

If the user's phrasing doesn't exactly match a known subcommand name, pick the closest one and confirm with the user before executing.

**Read config at runtime, every time.**

Nothing in this skill is templated or baked in. Every time a subcommand needs the user's profile, writing style, talking points, or search criteria, read the relevant JSON file with the Read tool. That way the skill is always in sync with whatever's on disk — the user can edit config files and the next invocation picks up the change.

Files you'll read, depending on the subcommand:

| File | Purpose |
|---|---|
| `config/profile.json` | Name, contact, career arc, credibility snippets, resume path, languages |
| `config/search-criteria.json` | Target roles, companies, industries, locations, keywords, scoring weights |
| `config/writing-style.json` | Sign-offs, PM phrases, writing rules (per-language) |
| `config/talking-points.json` | Industry talking points |
| `config/humanizer-rules.json` | Anti-AI-writing rules |
| `data/tracking.json` | v3.0 unified tracking: applications, outreach, stats |
| `data/connection-matches.json` | Generated jobs → connections mapping |
| `data/connections.csv` | LinkedIn connections export |
| `data/jobs/all-jobs.json` | Master job repository |

**Before any non-setup subcommand**, check that `config/profile.json` exists. If it doesn't, the user hasn't run setup yet — direct them to `/job-search setup` and stop.

**Always use the current working directory** as the project root. Never hardcode a specific path.

---

## Usage

```
/job-search                            # show this help
/job-search setup                      # first-run configuration wizard

/job-search fetch jobs                 # fetch jobs from JSearch
/job-search run pipeline               # full pipeline: fetch + generate materials
/job-search write cover letter for [company] [role]
/job-search write resume for [company] [role]
/job-search write connection for [name] at [company]
/job-search write email to [name] about [role]
/job-search draft gmail to [email]     # create a Gmail draft via MCP
/job-search log outreach to [name] at [company]
/job-search update outreach for [name] at [company] [status]
/job-search show stats                 # outreach performance report
/job-search score messages             # analyze message patterns
/job-search classify company [Company] # startup vs large classification
/job-search save job [description]     # save a job posting
/job-search list jobs                  # list saved jobs
/job-search match connections for [job]
```

---

# Subcommand: setup

Walk the user through the full configuration conversationally. Same outcome as running `python setup.py` in a terminal, but without leaving the Claude Code chat.

**Do NOT run `python setup.py` directly.** That script uses `input()` extensively and will hang when invoked via the Bash tool. This subcommand IS the setup wizard, translated into chat.

## Required reading before asking any questions

Read these first so you know exactly what to collect and produce:

1. **`setup.py`** — search for `collect_personal_info`, `collect_career_context`, `collect_credibility`, `collect_search_preferences`, `collect_writing_style`, `collect_talking_points`. Each has the canonical question text, default values, and the exact dict shape it returns. Mirror them.
2. **`config/profile.sample.json`**, **`config/search-criteria.sample.json`**, **`config/writing-style.sample.json`**, **`config/talking-points.sample.json`** — the exact JSON structure you'll produce.
3. **`data/tracking-template.json`** — the v3.0 tracking schema template.

## Step 0 — Introduction

> I'll walk you through configuring this job search agent. It takes about 5-10 minutes and covers:
>
> 1. Personal info and career context
> 2. Credibility snippets used in outreach
> 3. Job search preferences (roles, keywords, locations)
> 4. Writing style and talking points
> 5. LinkedIn connections (optional — skip and come back later)
> 6. RapidAPI key (optional — free tier: 200 requests/month)
> 7. First fetch + dashboard launch
>
> Ready to start?

If the user declines, stop. If they agree, continue.

If `config/profile.json` already exists, ask whether they want to re-run the full wizard (overwrites) or update individual pieces via flags like `python setup.py --connections`, `--keywords`, `--api-key`, `--fetch`. Don't clobber their config without consent.

## Step 1 — Personal Information

Mirror `collect_personal_info` in setup.py. Ask for:

- Full name (required)
- Professional headline (e.g., "Product and AI Leader") (required)
- Email, phone (required)
- Website or LinkedIn URL (optional)
- Location (default: `San Francisco Bay Area`)

Then the resume prompt:

- Ask for the absolute path to the resume file.
- Validate: file exists (`test -f` via Bash), extension in `.pdf`, `.md`, `.markdown`, `.docx`.
- If valid, offer to copy it to `data/resume.<ext>` (gitignored, portable). If accepted, `cp "$SRC" data/resume.<ext>` and store the in-project path. If declined, store the original absolute path.
- If they want to skip the resume entirely, warn that cover-letter and resume-tailoring commands will have very little context, and require explicit "skip anyway" confirmation.

Finally:

- Languages (comma-separated, default: `en, es`)
- Default language (default: first language in the list)

## Step 2 — Career Context

Mirror `collect_career_context`:

- Years of experience (default: `10`)
- 2-4 key roles, each with company, title, achievement line
- Core skills (list)
- Education (degree, school, year)

## Step 3 — Credibility Snippets

Mirror `collect_credibility`. Collect short, medium, and long credibility statements used in outreach templates, plus 2-3 quantified impact bullets. Consult `setup.py:collect_credibility` for the exact dict keys and prompts.

## Step 4 — Job Search Preferences

Mirror `collect_search_preferences`:

- Target role titles (default: Product Manager, Senior PM, Director of Product)
- Target industries (default: AI/ML, SaaS, Fintech, Health Tech)
- Target companies (optional)
- Preferred locations (default: San Francisco Bay Area, Remote)
- Acceptable locations (optional)
- Titles to exclude (default: Junior, Associate, Intern, Entry Level)
- Companies to exclude (optional)
- High-priority search keywords
- Medium-priority keywords (default: AI Product Manager, Data Product Manager, Strategy)
- Scoring weights (1-10): title, industry, company, location, seniority (defaults: 10, 8, 7, 6, 9)

Consult `setup.py:collect_search_preferences` for the nested dict shape.

## Step 5 — Writing Style

Mirror `collect_writing_style`. Uses the user's first name and language list. Collects sign-offs per context (LinkedIn, email, formal), PM phrasing per company size, and writing rules. Shape is nested by language: `{"en": {...}, "es": {...}}`.

Consult `setup.py:collect_writing_style` for the exact structure.

## Step 6 — Talking Points

Mirror `collect_talking_points`. Industry-organized (AI/ML, fintech, enterprise SaaS, etc.).

## Step 7 — LinkedIn Connections (optional)

Ask: "Have you exported your LinkedIn connections?"

**If no:** tell them how — open https://www.linkedin.com/mypreferences/d/download-my-data, select Connections, click Request archive, wait for the email. Offer to pause.

**If yes:** ask for the absolute path to their `Connections.csv`. Validate the file exists. Copy it:

```
cp "$SRC_PATH" data/connections.csv
```

**If skipped:** note they can run `python setup.py --connections` later.

## Step 8 — RapidAPI Key (optional)

Check if a key is already set:

```
echo "${RAPIDAPI_KEY:-MISSING}"
```

If it's a real key, use it and skip the rest of this step.

Otherwise ask: "Do you have a RapidAPI key?"

**If no:** walk them through signup, pausing after each step:

1. Open https://rapidapi.com/ and sign up (Google or GitHub login works)
2. Go to https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
3. Click "Subscribe to Test" and choose the Basic (Free) plan (200 req/month, no credit card)
4. Copy the `X-RapidAPI-Key` from the API playground

**Once they have a key:** ask them to paste it. Validate non-empty, no whitespace, reasonable length.

Offer to persist it to the shell rc:

- Detect shell from `$SHELL`. `zsh` → `~/.zshrc`, `bash` → `~/.bashrc`. Ambiguous → ask.
- Grep for an existing `export RAPIDAPI_KEY` line. If one exists, ask for permission to replace before writing.
- Append (or replace) via Bash:
  ```
  echo '' >> ~/.zshrc
  echo '# Job Search Agent (JSearch)' >> ~/.zshrc
  echo 'export RAPIDAPI_KEY="$PASTED_KEY"' >> ~/.zshrc
  ```
- Tell them to `source` the file or open a new terminal.

**Important:** each Bash call runs in its own subshell. Adding to `~/.zshrc` does NOT make the key available to subsequent Bash calls in this session. Hold the pasted key in chat state and pass it inline to the first fetch in Step 11: `RAPIDAPI_KEY="..." python scripts/fetch_jobs.py ...`

## Step 9 — Write config files

Use the **Write** tool to create these four files. Use shapes from `config/*.sample.json` as templates. Never use Bash `echo` redirection for JSON — always use Write.

1. `config/profile.json` — populate from Steps 1-3. `filename_prefix` = `LastName_FirstName` with non-alphanumerics stripped (see `setup.py:make_filename_prefix`). Include `resume_path`, `languages`, `default_language`.
2. `config/search-criteria.json` — from Step 4.
3. `config/writing-style.json` — from Step 5.
4. `config/talking-points.json` — from Step 6.

Confirm each file's path to the user after writing.

Ensure `data/tracking.json` exists for the dashboard:

```
test -f data/tracking.json || cp data/tracking-template.json data/tracking.json
```

## Step 10 — Generate CLAUDE.md

Delegate to the existing non-interactive entry point:

```
python setup.py --from-config
```

This reads the config JSONs you just wrote and regenerates `CLAUDE.md` at the project root. Non-interactive, safe to run via Bash.

## Step 11 — First fetch and dashboard

If a RapidAPI key is available, ask: "Fetch jobs now? This uses about N API requests of 200/month free" where N = keywords × locations.

**Check dependencies first.** `fetch_jobs.py` needs `requests` and `generate_pdf.py` needs `reportlab`. If `python -c "import requests" 2>/dev/null; echo $?` returns non-zero, offer to install:

```
python -m pip install -r requirements.txt
```

Ask for consent before running pip. Respect externally-managed Python environments — if pip fails, report the error and tell the user to set up a venv.

**If deps are ready, run the fetch:**

```
RAPIDAPI_KEY="$KEY" python scripts/fetch_jobs.py --keywords "$KW1" "$KW2" ... --locations "$LOC1" "$LOC2" ...
```

Each keyword and location is a separate shell-quoted argument (nargs="+").

**After the fetch:**

```
python scripts/generate_data_js.py
```

Then offer: "Open the dashboard?"

**If yes:**

```
python scripts/dashboard.py
```

Tell the user to visit http://localhost:8777/dashboard.html. The launcher auto-opens the browser by default; for headless sessions use `--no-browser`.

## Step 12 — Wrap up

Summarize what was created:

- Config files at `config/profile.json`, `config/search-criteria.json`, `config/writing-style.json`, `config/talking-points.json`
- `CLAUDE.md` at the project root
- `data/connections.csv` (if provided)
- `data/tracking.json`
- Dashboard running at http://localhost:8777 (if opened)

Tell them the daily commands:

- `/job-search fetch jobs` — fetch more jobs
- `/job-search show stats` — see outreach performance
- `python scripts/dashboard.py` — open the dashboard
- `/job-search setup` — re-run the wizard

---

# Subcommand: fetch jobs

Fetch jobs from two sources in one command:

1. **ATS direct fetch** (always runs if `data/company-ats.json` has entries): pulls open roles from Greenhouse, Lever, and Ashby career pages. Free, no API key, no signup.
2. **JSearch keyword search** (only if `$RAPIDAPI_KEY` is set): searches across LinkedIn, Indeed, Glassdoor, ZipRecruiter. Free tier: 200 requests/month.

If no `$RAPIDAPI_KEY` is configured, only ATS sources are used — that's the free baseline and it works out of the box after setup.

**Variants:**
- `fetch jobs` — default: ATS + JSearch (if key set)
- `fetch jobs for [keywords]` — override JSearch keywords
- `fetch jobs in [locations]` — override JSearch locations

## Before fetching

1. Read `config/search-criteria.json` for keywords and locations.
2. Check that `requests` is installed. If not, offer to run `python -m pip install -r requirements.txt`.
3. Check `data/company-ats.json` for companies to fetch from via ATS. If empty, suggest `python scripts/fetch_ats.py --probe "Company Name"` to add companies.

## Run the fetch

```
python scripts/fetch_jobs.py
```

Or with JSearch-specific options:

```
python scripts/fetch_jobs.py --keywords "..." "..." --locations "..." "..."
```

Or ATS only (skip JSearch even if a key is set):

```
python scripts/fetch_jobs.py --ats-only
```

The script automatically chains `match_connections.py` if `data/connections.csv` exists, and regenerates `dashboard/data.js`. Report how many jobs were fetched from each source.

## After fetching

Offer to open the dashboard:

```
python scripts/dashboard.py
```

---

# Subcommand: add company

Add a company to your ATS watchlist. Auto-detects whether they use Greenhouse, Lever, or Ashby and caches the result in `data/company-ats.json`.

```
python scripts/fetch_ats.py --probe "[Company Name]"
```

The next `/job-search fetch jobs` will include this company's open roles. If the company doesn't use any of the three supported ATS systems, the result is cached as "none" so repeated probes don't waste time.

To see all currently configured companies:

```
python scripts/fetch_ats.py --dry-run
```

---

# Subcommand: run pipeline

Generate application materials for each job the user has selected in the dashboard or in `data/selected-jobs.json`.

## Steps

1. Find the most recent `selected-jobs*.json` in `~/Downloads/` (sorted by mtime) or check `data/selected-jobs.json`. If neither exists, tell the user to select jobs in the dashboard first.
2. Create an `outputs/YYYY-MM-DD/` folder.
3. For each selected job:
   - Read the `language` field (defaults to `default_language` from profile).
   - Create `outputs/YYYY-MM-DD/[company-slug]-[role-slug]/`
   - Save the full job description as `job-description.md`.
   - Read the user's resume from `profile["resume_path"]`.
   - **Tailor resume**: follow `templates/{language}/resume-tailoring.md` guidelines. Save as `resume-tailored.md` and generate a PDF via `scripts/generate_pdf.py`.
   - Generate a **tailored connection request for recruiters** using `templates/{language}/connection-request.md` (under 300 chars). Save as `connection-request-recruiter.md`.
   - Generate a **hiring manager message** using the same template. Save as `hiring-manager-message.md`.
   - Write a **tailored cover letter** using `templates/{language}/cover-letter.md`. Save as `cover-letter.md` and generate a PDF.
4. Generate `outputs/YYYY-MM-DD/summary.md` with links to all materials.
5. Present everything to the user for review.
6. After approval, log each outreach via `/job-search log outreach`.

**Output folder structure:**

```
outputs/YYYY-MM-DD/
├── [company-slug]-[role-slug]/
│   ├── job-description.md
│   ├── cover-letter.md
│   ├── connection-request-recruiter.md
│   ├── hiring-manager-message.md
│   ├── resume-tailored.md
│   └── *.pdf
└── summary.md
```

---

# Subcommand: write cover letter

Generate a tailored cover letter for a specific company and role.

**Language:** Use `default_language` from `config/profile.json`. User can override with `in spanish`, `in english`, etc.

## Steps

1. Determine language (from user request or default).
2. Load the job description from `data/jobs/` if saved, else ask the user to paste it.
3. Read `templates/{language}/cover-letter.md` for structure.
4. Read `config/profile.json`, `config/talking-points.json`, `config/writing-style.json`.
5. Write the cover letter, tailoring credibility and value props to the role. Apply the Anti-AI Writing Check below.
6. Save to `outputs/cover-letters/[company]-[role-slug].md`.

Template variables you'll substitute yourself (not via a templating engine — just fill them in): `{{name}}`, `{{cred_long}}`, `{{sign_off_formal}}`, `{{title}}`, `{{phone}}`, `{{email}}`, `{{website}}` from `config/profile.json`.

---

# Subcommand: write resume

Tailor the base resume to match a specific job description.

**Language:** Use `default_language` from `config/profile.json`. User can override with `in spanish`, `in english`, etc.

## Steps

1. Determine language.
2. Read the user's base resume from `profile["resume_path"]`.
3. Read or ask for the full job description.
4. Follow the guidelines in `templates/{language}/resume-tailoring.md`.
5. Save tailored resume as `outputs/YYYY-MM-DD/[company-slug]-[role-slug]/resume-tailored.md`.
6. Generate the PDF:

   ```
   python scripts/generate_pdf.py --type resume --input [tailored.md] --company [Company]
   ```

7. Present the tailored resume, highlighting what changed and why.

---

# Subcommand: write connection

Generate a LinkedIn connection request (max 300 chars) personalized to a specific job.

## Steps

1. Classify the company size via `scripts/company_classifier.py`.
2. Determine recipient role (recruiter, hiring-manager, executive, peer, ceo).
3. Read `config/profile.json`, `config/writing-style.json`, `config/talking-points.json`.
4. Generate the message using the patterns from `smart_template.py`. You can call the script directly:

   ```
   python scripts/smart_template.py --name "[name]" --company "[company]" --job-title "[role]" --role [recipient_role] --type connection-request
   ```

5. Verify character count is under 300. If over, trim pleasantries first, then shorten credibility, then simplify the CTA.
6. Save to `outputs/connection-requests/[name]-[company].md`.
7. Ask the user if they want to log it via `/job-search log outreach`.

For a connection request without a specific job, use a broader approach focused on the company and mutual interest.

---

# Subcommand: write email

Generate an outreach email with 5 subject line variants.

## Steps

1. Read `templates/{language}/email-outreach.md` for structure.
2. Read `config/profile.json`, `config/talking-points.json`, `config/writing-style.json`.
3. Pick the template variant (recruiter, hiring manager, cold outreach).
4. Generate 5 subject lines spanning categories: direct, curiosity, mutual, value-first, question.
5. Write the email body. For cold outreach, keep it under 200 words.
6. Apply the Anti-AI Writing Check.
7. Save to `outputs/emails/[name]-[company].md`.

---

# Subcommand: draft gmail

Create a Gmail draft using the Gmail MCP integration.

## Steps

1. Generate the email content following the "write email" subcommand.
2. Use `gmail_create_draft` via the Gmail MCP:
   - `to`: recipient email
   - `from`: user's email from `config/profile.json` (`contact.email`)
   - `subject`: best subject line from the 5 variants
   - `body`: the generated email
3. Confirm draft creation and provide the Gmail link.

**Always ask before sending. Create drafts, not sent messages.**

---

# Subcommand: log outreach

Log a new outreach entry via the shared tracking module.

```
python scripts/update_outreach.py log --name "[name]" --company "[company]" --role [recipient_role] --type [msg_type] --message "[text]" --job-id "[optional]"
```

This writes to `data/tracking.json` (the refactored `update_outreach.py` uses `scripts/tracking.py` under the hood). The dashboard picks up the new entry immediately.

Before logging, check `data/tracking.json` to avoid duplicate outreach to the same person at the same company. Warn and ask for confirmation if a duplicate is about to be created.

---

# Subcommand: update outreach

Update the outcome of a previous outreach.

```
python scripts/update_outreach.py update --name "[name]" --company "[company]" --status [sent|accepted|replied|interview|no_response|declined] --date [YYYY-MM-DD optional]
```

The `accepted` transition automatically computes `response_time_days` if the original `sent` date is present.

---

# Subcommand: show stats

```
python scripts/update_outreach.py stats
```

Prints totals, outcome breakdown, breakdowns by message type, company size, and recipient role, and average response time. All computed from `data/tracking.json`.

---

# Subcommand: score messages

```
python scripts/score_messages.py
```

Analyzes outreach history to find the best-performing message patterns. Breakdowns by type, size, and recipient role, plus top performers and recommendations. Needs at least 10 logged outreach entries for meaningful output.

---

# Subcommand: classify company

```
python scripts/company_classifier.py "[Company]"
```

Returns `startup` or `large` for tone adjustment in messages. To teach the classifier a new company:

```
python scripts/company_classifier.py "[Company]" --add [startup|large]
```

---

# Subcommand: save job

```
python scripts/save_job.py save --company "[company]" --role "[role]" --url "[url]" --location "[location]" --salary "[salary]" --source [source] --status applied
```

Saves a structured job entry that other subcommands can link outreach to.

---

# Subcommand: list jobs

```
python scripts/save_job.py list
```

Lists all saved job postings from `data/jobs/`.

---

# Subcommand: match connections

Find the best LinkedIn connections to reach out to for a specific job.

## Steps

1. Read `data/connection-matches.json` if it exists — that's the precomputed map from `scripts/match_connections.py`.
2. If it's stale or missing, regenerate:
   ```
   python scripts/match_connections.py
   ```
3. Pull the matches for the target company + title.
4. Score connections using the weights in the Connection Matching Logic section below.
5. Check `data/tracking.json` for prior outreach to each candidate — flag duplicates.
6. Present top 5 with scores and recommended outreach type.

---

## Connection Matching Logic

When ranking connections for a job opportunity, score each one:

| Signal | Points |
|---|---|
| Works at target company | +50 |
| Same department/team | +30 |
| Hiring manager for the role | +40 |
| Recruiter at company | +25 |
| Has relevant title (VP, Director, Head of) | +20 |
| Shared school or past company | +15 |
| 1st-degree connection | +10 |
| 2nd-degree connection | +5 |
| Recently active on LinkedIn | +5 |

**Recommended outreach type by score:**
- ≥70 → direct message or email
- 40-69 → connection request with personalized note
- <40 → connection request with general note

**Fuzzy matching rules for company names:**
- Ignore case, `Inc`, `LLC`, `Corp`, `Ltd`, `Co.` suffixes
- Match parent companies (e.g., "Meta" matches "Facebook")
- Match subsidiaries listed in `data/company-sizes.json`

---

## Anti-AI Writing Check

All generated content must pass a humanizer check before you present it to the user. Read `config/humanizer-rules.json` for the full rule set. Summary:

**Vocabulary bans.** Never use: delve, tapestry, landscape (figurative), pivotal, crucial, foster, underscores, highlights, showcasing, nestled, vibrant, groundbreaking, renowned, breathtaking, testament, enduring, interplay, intricate, garner, encompasses.

**Phrase bans.** Never use: "it's not just about", "at its core", "the real question is", "let's dive in", "serves as a", "stands as a", "a testament to", "plays a crucial role", "in today's rapidly evolving".

**Structure rules.**
- Use `is`/`are` instead of `serves as`/`stands as`/`represents`
- No em dashes. Use commas or periods.
- No `-ing` phrases for fake depth (`highlighting`, `showcasing`, `reflecting`)
- Vary sentence length. Use active voice. Name the actor.
- No rule-of-three unless genuinely three items

**Tone.**
- Specific numbers and details, not vague claims
- Don't inflate importance. Simple facts need no ceremony.
- Cut filler: `in order to` → `to`, `due to the fact that` → `because`
- No generic positive conclusions, no sycophantic language

**Self-check.** After drafting any message, silently ask: "What makes this sound AI-generated?" Fix those tells before presenting.

---

## Error handling

1. **Missing config files** (`config/profile.json` does not exist) → direct the user to run `/job-search setup`.
2. **Missing `$RAPIDAPI_KEY`** → direct to `/job-search setup` (step 8) or `python setup.py --api-key`.
3. **Missing `data/connections.csv`** → run `/job-search setup` (step 7) or `python setup.py --connections`.
4. **Missing `data/tracking.json`** → copy from the template: `cp data/tracking-template.json data/tracking.json`. The local server also does this automatically on startup.
5. **Legacy `data/outreach-history.json` only** → `scripts/tracking.py` auto-migrates on first read. No manual action needed.
6. **Connection request exceeds 300 chars** → trim pleasantries first, then shorten credibility, then simplify the CTA.
7. **Duplicate outreach** → check `data/tracking.json` before logging. Warn and ask before creating a duplicate.
8. **Missing Python deps** (`requests`, `reportlab`) → offer to run `python -m pip install -r requirements.txt`. Respect externally-managed Python environments — if pip fails, report and tell the user to use a venv.

---

## Scripts reference

All scripts live in `scripts/` and can be run from the project root.

| Script | Purpose |
|---|---|
| `setup.py` | Terminal-based setup wizard (this subcommand `setup` is the Claude Code equivalent) |
| `fetch_jobs.py` | Fetch jobs via JSearch; auto-chains match_connections + data.js regen |
| `match_connections.py` | LinkedIn connections → fetched jobs matcher |
| `dashboard.py` | Regenerate data.js, start local server at :8777, open browser |
| `local_server.py` | Dashboard HTTP server (`/api/tracking`, `/api/jobs`, static files) |
| `generate_data_js.py` | Embed tracking + jobs + matches into `dashboard/data.js` |
| `migrate_outreach_to_tracking.py` | Explicit legacy migration (auto-run now handles most cases) |
| `tracking.py` | Single source of truth for `data/tracking.json` reads and writes |
| `update_outreach.py` | Log / update / stats CLI, delegates to `tracking.py` |
| `score_messages.py` | Performance analysis, reads `tracking.json` |
| `company_classifier.py` | Classify company size |
| `save_job.py` | Save and manage job postings |
| `smart_template.py` | Generate LinkedIn outreach messages |
| `generate_pdf.py` | Markdown → PDF conversion |

---

## File naming

All generated PDFs follow this pattern (from `profile.filename_prefix`):

- Cover letters: `{filename_prefix}_CoverLetter_[Company]_YYYY-MM-DD.pdf`
- Resumes: `{filename_prefix}_Resume_YYYY-MM-DD.pdf`

PDFs go to `~/Downloads/` by default.
