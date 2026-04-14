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

## Workspace resolution

Before running any Python script, determine the workspace directory:

1. Check if a `.workspace` file exists in the project root (or in `~/.claude/skills/job-search/` for global installs). If it exists, read its single line — that's the workspace path where the user's data lives.
2. If no `.workspace` file, use the current working directory as the workspace.

**Every Bash call that runs a Python script must prepend the workspace path:**

```
JOB_SEARCH_DIR="/path/to/workspace" python scripts/fetch_jobs.py ...
```

All Python scripts respect `JOB_SEARCH_DIR` — they resolve config/, data/, outputs/, and dashboard/ relative to it. If the env var is not set, scripts fall back to their own parent directory (the traditional project-local model).

For project-local installs (the user cloned into a normal directory and opened it in Claude Code), `JOB_SEARCH_DIR` equals the cwd and the override is a no-op. Only global installs (skill directory != data directory) need the explicit override.

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

Configure the job search agent by extracting the user's profile from their resume, then collecting job preferences and writing style. Under 3 minutes if the user has a resume.

**Do NOT run `python setup.py` directly.** That script uses `input()` extensively and will hang when invoked via the Bash tool. This subcommand IS the setup wizard, translated into chat.

If `config/profile.json` already exists, ask whether they want to re-run from scratch or update individual pieces (`python setup.py --connections`, `--keywords`, `--api-key`, `--fetch`). Don't clobber their config without consent.

## Required reading before starting

Read these files so you know the exact JSON shapes you need to produce:

1. **`config/profile.sample.json`** — profile structure (name, contact, career, credibility, resume_path, languages)
2. **`config/search-criteria.sample.json`** — roles, companies, industries, locations, keywords, scoring weights
3. **`config/writing-style.sample.json`** — sign-offs, PM phrases, writing rules (per-language)
4. **`config/talking-points.sample.json`** — industry-organized talking points
5. **`data/tracking-template.json`** — the v3.0 tracking schema template

## Step 0 — Workspace location

Ask the user:

> Where do you want to keep your job search data? This is where your config, resume, tracking data, and generated materials will live.
>
> Default: ~/job-search

Create the directory and its subdirectories via Bash:

```
mkdir -p ~/job-search/{config,data/jobs,outputs,dashboard}
```

Copy template and starter files from the skill installation into the workspace:

```
cp data/tracking-template.json ~/job-search/data/
cp data/connections-template.csv ~/job-search/data/
cp data/company-ats.json ~/job-search/data/
cp data/jobs/sample-job.json ~/job-search/data/jobs/
cp config/*.sample.json ~/job-search/config/
cp config/humanizer-rules.json ~/job-search/config/
cp dashboard/*.html dashboard/favicon.png ~/job-search/dashboard/
```

(Substitute the user's chosen path for `~/job-search` in the commands above.)

Save the workspace path so future commands know where to find the data:

```
echo "/Users/username/job-search" > .workspace
```

(`.workspace` goes in the current project root — that's either `~/.claude/skills/job-search/` for global installs or the project-local clone directory.)

For **project-local installs** (user cloned into a normal directory and opened it in Claude Code), skip this step entirely — the project directory IS the workspace, no `.workspace` file is needed, and no files need copying.

From this point on, every Bash call in this setup that runs a Python script must prepend:

```
JOB_SEARCH_DIR="/chosen/path" python scripts/...
```

## Step 1 — Resume

Ask the user:

> Drop me the path to your resume (PDF, Markdown, or DOCX) and I'll extract your profile from it. This saves about 30 questions worth of manual input.
>
> If you don't have a resume ready, just say "skip" and I'll ask you the questions instead.

**If they provide a path:**
- Validate: file exists (`test -f` via Bash), extension in `.pdf`, `.md`, `.markdown`, `.docx`
- If invalid, loop: offer another path, or skip to manual
- Read the file using the **Read** tool (Claude Code reads PDFs natively, up to 20 pages)
- Offer to copy it to `data/resume.<ext>` (gitignored, portable): `cp "$SRC" data/resume.<ext>`
- Proceed to Step 2 (extraction)

**If they say "skip" or don't have a resume:**
- Fall back to the manual collection flow. Read `setup.py` and follow the questions from `collect_personal_info`, `collect_career_context`, and `collect_credibility` functions (about 29 questions total). Then skip Step 2 and go straight to Step 3.

## Step 2 — Confirm extracted profile

After reading the resume, extract and present the following in a structured block:

- **Name** and **contact info** (email, phone, location, website/LinkedIn)
- **Professional headline** (synthesize from most recent role + seniority)
- **Career arc**: list each role with company, title, dates, and one achievement line
- **Core skills**: extract from skills sections, technologies mentioned, and role descriptions
- **Education**: degrees, schools, graduation years
- **Credibility statements** (Claude generates these from the resume's achievements):
  - **Short** (1 sentence): e.g., "8 years building AI and fintech products at scale"
  - **Medium** (2-3 sentences): expanded version with specific numbers
  - **Long** (full paragraph): synthesized from the strongest achievements
- **Key quantified impact**: the single most impressive metric
- **Languages**: infer from resume language; ask if bilingual/multilingual is unclear

Present all of this and ask:

> Does this look right? Anything to add or correct?

Apply any corrections the user gives. This one interaction replaces ~29 manual questions.

Then present the **signature block** that will appear on cover letters:

> This is how your cover letter signature will look:
>
> Best,
>
> Jane Doe
> Senior Product Manager
> jane@example.com | 555-1234
> linkedin.com/in/janedoe
>
> Want to change anything? (name format, title, contact info, sign-off)

The user confirms or edits. These fields map to the `{{name}}`, `{{title}}`, `{{email}}`, `{{phone}}`, `{{website}}`, `{{sign_off_formal}}` template variables used by cover letters, emails, and PDFs. Getting them right here means every generated document uses the correct signature.

Also ask:

> What languages do you want outreach generated in? (default: en)

## Step 3 — What jobs are you looking for?

Three questions:

> 1. What roles are you targeting? (e.g., "Product Manager, Director of Product")
> 2. Any specific companies you're interested in?
> 3. Where do you want to work? (e.g., "San Francisco Bay Area, Remote")

From the answers + the resume, Claude auto-fills the rest of `search-criteria.json`:
- `exclude_titles`: infer from the user's seniority (a Senior PM probably excludes Junior, Associate, Intern, Entry Level)
- `industries.target`: infer from the resume's industry experience
- `search_queries.high_priority`: derived from target roles
- `search_queries.medium_priority`: derived from the user's industry keywords
- `scoring_weights`: use sensible defaults (title=10, industry=8, company=7, location=6, seniority=9) — do not ask

**Auto-probe target companies for ATS:**

If the user listed target companies, probe each for Greenhouse/Lever/Ashby and report:

```
python scripts/fetch_ats.py --probe "[Company Name]"
```

Or call `probe_company(name)` directly if imported. Report results:

> Checking which companies have public career pages...
>   Stripe: Greenhouse (23 open roles)
>   OpenAI: Ashby (45 open roles)
>   Acme Corp: no ATS detected

## Step 4 — Writing style

Ask:

> To make your outreach sound like YOU instead of generic AI, paste a few paragraphs of something you've actually written — a LinkedIn post, an email, a Slack message, anything that shows your natural voice.
>
> Skip this if you want clean defaults. You can always refine later.

**If they provide a writing sample:**

1. Analyze the sample for: sentence length patterns, word choices, formality level, directness, humor, personal quirks
2. Generate `config/writing-style.json` from the analysis:
   - `sign_offs`: infer appropriate sign-offs matching their tone (per context: LinkedIn, email, formal)
   - `pm_phrases`: infer from their career level (startup vs. large company phrasing)
   - `writing_rules`: extract style patterns as rules (e.g., "uses short sentences", "avoids jargon", "leads with data")
3. Generate `config/talking-points.json` from the resume's industry experience (no questions asked — just extract relevant industry talking points)

4. **Generate two sample outputs** to validate the style:
   - A cover letter for a realistic role at one of their target companies
   - A LinkedIn connection request to a recruiter at that company (under 300 chars)
   - Apply the humanizer rules from `config/humanizer-rules.json` automatically before presenting

5. Present the samples:

> Here's what your outreach would sound like:
>
> **Cover letter for [Company] — [Role]:**
> [3-paragraph letter using their voice, credibility, and talking points]
>
> **LinkedIn connection request (287/300 chars):**
> [Short, direct message in their voice]
>
> How do these sound? Too formal? Too casual? Anything you'd change?

6. Apply any feedback by adjusting `writing-style.json` parameters.

**If they skip the writing sample:**
- Use defaults: short, direct, no sycophantic language
- Generate `writing-style.json` with sensible rules (humanizer-aligned)
- Generate `talking-points.json` from resume industry experience
- Skip the sample output generation

## Step 5 — Write config files

Use the **Write** tool to create 4 JSON files. Read `config/*.sample.json` for the exact shapes. Never use Bash `echo` redirection for JSON — always use Write.

1. `config/profile.json` — from Steps 1-2. Include `filename_prefix` = `LastName_FirstName` (strip non-alphanumerics, see `setup.py:make_filename_prefix`). Include `resume_path`, `languages`, `default_language`.
2. `config/search-criteria.json` — from Step 3 + auto-inferred fields.
3. `config/writing-style.json` — from Step 4 (or defaults).
4. `config/talking-points.json` — auto-generated from resume industry experience.

Confirm each file path after writing.

Ensure `data/tracking.json` exists:

```
test -f data/tracking.json || cp data/tracking-template.json data/tracking.json
```

## Step 6 — Generate CLAUDE.md

```
python setup.py --from-config
```

Non-interactive. Reads the config JSONs and generates `CLAUDE.md` at the project root.

## Step 7 — LinkedIn Connections (optional)

> Have you exported your LinkedIn connections?

**If no:** show the export instructions (open https://www.linkedin.com/mypreferences/d/download-my-data, select Connections, request archive, wait for email). Offer to pause or skip.

**If yes:** ask for path, validate, copy to `data/connections.csv`.

**If skipped:** tell them `python setup.py --connections` later.

## Step 8 — RapidAPI Key (optional)

> The tool already fetches jobs from company career pages (free, no signup). Want to ALSO search across LinkedIn, Indeed, Glassdoor, and ZipRecruiter? That requires a free RapidAPI key (200 requests/month, no credit card).

Check if already set: `echo "${RAPIDAPI_KEY:-MISSING}"`

If missing, walk through signup (same 4-step guide as before). After pasting the key, offer to persist to shell rc. Hold key in chat state for Step 9.

**Framing matters:** position this as an optional upgrade, not a required step. ATS fetching already works without it.

## Step 9 — Fetch + dashboard

**Check dependencies:** if `python -c "import requests" 2>/dev/null; echo $?` returns non-zero, offer to install: `python -m pip install -r requirements.txt`

**Run the fetch:**

```
python scripts/fetch_jobs.py
```

(If RapidAPI key was pasted in Step 8, prepend `RAPIDAPI_KEY="$KEY"` to the command.)

The script runs ATS fetch first (from probed companies), then JSearch (if key set), chains connection matching, and regenerates dashboard data.

**Open the dashboard:**

```
python scripts/dashboard.py
```

## Step 10 — Wrap up

Summarize what was created and the daily commands:

- `/job-search fetch jobs` — fetch more jobs
- `/job-search write cover letter for [Company] [Role]` — tailored cover letter
- `/job-search run pipeline` — full pipeline for selected jobs
- `/job-search show stats` — outreach performance
- `/job-search add company` — add a company to your ATS watchlist
- `python scripts/dashboard.py` — open the dashboard

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
