# Job Search Agent - AI-Powered Job Search Automation for Claude Code

Automates job search networking by analyzing your resume, matching LinkedIn connections to opportunities, and generating personalized outreach content. Works as a Claude Code slash command (`/job-search`) and ships with a local HTML dashboard for browsing fetched jobs, tracking applications, and seeing which of your connections work at target companies.

## Features

- **Guided first-run setup** — one command walks you through profile, connections import, keywords, API key, and first fetch
- **Local HTML dashboard** — browse fetched jobs, mark applied, track outreach, see matched connections per job (served at `http://localhost:8777`)
- **Multi-source job fetching** — JSearch (RapidAPI) searches across LinkedIn, Indeed, Glassdoor, and ZipRecruiter
- **LinkedIn connection matching** — highlights jobs at companies where you already have a connection
- **A/B tested LinkedIn connection requests** — 4 message variants (A/B/C/D) with character count enforcement (300 char limit)
- **Tailored cover letters and resumes** per job, exported as professional PDFs
- **Email outreach** with 5 subject line variants per recipient
- **Gmail draft integration** for one-click sending
- **Outreach tracking and performance analytics** — response rates by message type, company size, and recipient role
- **Company size classification** for tone adjustment (startup vs. large company phrasing)

## Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (optional — the dashboard works standalone)
- Python 3.9+
- Free API key: [RapidAPI (JSearch)](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) — 200 requests/month on the free tier

## Quick Start

```bash
git clone https://github.com/viviana-nieto/job-search-and-tracker.git
cd job-search-and-tracker
python setup.py
```

Everything the wizard does up to and including opening the dashboard runs on Python's standard library. The only two external packages — `requests` (for JSearch job fetching) and `reportlab` (for PDF export) — are installed lazily when you first opt into a job fetch. The wizard detects they're missing and prompts you before running `pip install -r requirements.txt`, so you can decline and still browse the dashboard.

### Setup in Claude Code (alternative)

If you use [Claude Code](https://docs.anthropic.com/en/docs/claude-code), you can configure this project without opening a separate terminal. Open the repo in Claude Code and type:

```
/job-search setup
```

Claude Code loads the project-local `.claude/commands/job-search.md` slash command and walks you through the same questions `python setup.py` asks, writes your config files, imports your LinkedIn connections, sets your RapidAPI key, and (optionally) fetches jobs and opens the dashboard — all in the Claude Code chat. This is often smoother than the terminal wizard because you never leave the window.

After setup, the same `/job-search` slash command handles daily commands too (`fetch jobs`, `write cover letter`, `show stats`, `score messages`, etc.). One entry point for everything. See [Available Commands](#available-commands) for the full list.

Both setup paths produce the same config files and end in the same state. Pick whichever is more convenient for you.

`python setup.py` walks you through everything:

1. Personal info, career context, credibility snippets
2. Job search preferences (roles, keywords, locations)
3. Writing style and talking points
4. **Import your LinkedIn connections** (optional — the wizard shows you how to export them)
5. **RapidAPI key** (optional — the wizard walks you through signup)
6. **First fetch + dashboard launch** — fetches jobs matching your keywords and opens the dashboard in your browser

At the end of setup, your browser opens to `http://localhost:8777/dashboard.html` with your actual jobs loaded.

### Daily commands

```bash
python scripts/dashboard.py       # open the dashboard
python scripts/fetch_jobs.py      # fetch more jobs + refresh matches
python setup.py --connections     # re-import LinkedIn connections
python setup.py --api-key         # update your RapidAPI key
python setup.py --keywords        # update search keywords/locations
python setup.py --fetch           # fetch + open dashboard without re-running setup
```

### From Claude Code

```
/job-search fetch jobs
```

## Available Commands

### Setup and dashboard (shell)

| Command | Description |
|---------|-------------|
| `python setup.py` | Full guided first-run wizard (profile, keywords, connections, API key, first fetch, dashboard) |
| `python setup.py --connections` | Import or re-import your LinkedIn connections CSV |
| `python setup.py --keywords` | Update search keywords and locations |
| `python setup.py --api-key` | Set or update your RapidAPI key (guided walkthrough + shell persistence) |
| `python setup.py --fetch` | Fetch jobs with saved config and open the dashboard |
| `python setup.py --from-config` | Regenerate `CLAUDE.md` and skill file from existing config |
| `python scripts/dashboard.py` | Regenerate data, start local server, auto-open the dashboard |
| `python scripts/dashboard.py --no-browser` | Same, but do not open the browser (for SSH/headless) |
| `python scripts/fetch_jobs.py` | Fetch jobs, refresh connection matches, update dashboard data |
| `python scripts/match_connections.py` | Manually refresh `connection-matches.json` |
| `python scripts/migrate_outreach_to_tracking.py` | Explicitly trigger migration from legacy `outreach-history.json` to `tracking.json` (optional — tracking-aware scripts auto-migrate on first read) |

### Claude Code slash command

| Command | Description |
|---------|-------------|
| `fetch jobs` | Fetch new job listings from JSearch (RapidAPI) |
| `run pipeline` | Full pipeline: fetch jobs, match connections, generate outreach materials |
| `write cover letter --company [Company] --role [Role]` | Generate a tailored cover letter |
| `write resume --company [Company]` | Generate a tailored resume |
| `generate pdf --type cover-letter --input [file]` | Export cover letter or resume as PDF |
| `draft connection --name [Name] --company [Company] --role [Role]` | Generate LinkedIn connection request (all 4 A/B variants) |
| `draft email --name [Name] --company [Company] --role [Role]` | Generate email outreach with 5 subject lines |
| `draft gmail --to [email] --subject [subject]` | Create a Gmail draft via API |
| `log outreach --name [Name] --company [Company]` | Log an outreach entry |
| `update outreach --name [Name] --company [Company] --status [status]` | Update outcome (accepted, replied, interview, etc.) |
| `show stats` | Display outreach performance analytics |
| `score messages` | Analyze message patterns and find what works |
| `classify company [Company]` | Check if a company is classified as startup or large |
| `save job --company [Company] --role [Role]` | Save a job posting for tracking |
| `list jobs` | List all saved job postings |
| `match connections --company [Company]` | Find LinkedIn connections at a target company |

## Project Structure

```
job-search-and-tracker/
├── README.md
├── requirements.txt
├── setup.py                          # Guided onboarding wizard (with --connections/--keywords/--api-key/--fetch flags)
├── commands/                         # Claude Code project CLAUDE.md template
│   └── CLAUDE.md.template            # Rendered into CLAUDE.md by setup.py
├── .claude/commands/                 # Project-local Claude Code slash commands
│   └── job-search.md                 # /job-search — setup + daily commands, ships with the repo
├── config/                           # User configuration (gitignored)
│   ├── profile.sample.json           # Your professional profile
│   ├── search-criteria.sample.json   # Target roles, industries, locations
│   ├── writing-style.sample.json     # Sign-offs, phrasing rules
│   ├── talking-points.sample.json    # Industry-specific talking points
│   └── humanizer-rules.json          # Anti-AI-writing rules (shipped)
├── dashboard/                        # Local HTML dashboard (served by local_server.py)
│   ├── dashboard.html                # Stats, weekly activity, goal circles
│   ├── jobs.html                     # All-jobs browser with filters, apply/ignore, matched connections
│   ├── companies.html                # Company-level view, follow status
│   ├── index.html                    # Redirect to jobs.html
│   ├── favicon.png
│   └── data.js                       # Generated embedded data (gitignored)
├── data/
│   ├── connections-template.csv      # Format reference for LinkedIn connections
│   ├── tracking-template.json        # v3.0 tracking schema template
│   ├── connections.csv               # Your LinkedIn export (gitignored)
│   ├── tracking.json                 # Your applications + outreach + stats (gitignored)
│   ├── connection-matches.json       # Jobs → matched connections (generated, gitignored)
│   ├── company-sizes.json            # Company classification cache (gitignored)
│   ├── resume.<ext>                  # Your resume, copied in by setup.py (gitignored)
│   └── jobs/
│       ├── sample-job.json           # Example job listing format
│       └── all-jobs.json             # Master job repository (generated)
├── scripts/
│   ├── config_loader.py              # Configuration loader shared by all scripts
│   ├── fetch_jobs.py                 # Job fetcher (JSearch), auto-chains match_connections + data.js regen
│   ├── match_connections.py          # LinkedIn connections → fetched jobs matcher
│   ├── local_server.py               # Dashboard server (http://localhost:8777, /api/tracking, /api/jobs)
│   ├── dashboard.py                  # One-shot launcher: regen data.js + serve + open browser
│   ├── generate_data_js.py           # Embed tracking + jobs + matches into dashboard/data.js
│   ├── migrate_outreach_to_tracking.py # Legacy outreach-history.json → tracking.json migration
│   ├── save_job.py                   # Save and manage individual job postings
│   ├── company_classifier.py         # Classify companies as startup/large
│   ├── smart_template.py             # Generate LinkedIn outreach messages
│   ├── generate_pdf.py               # Export cover letters and resumes as PDFs
│   ├── update_outreach.py            # Log outreach and update outcomes
│   └── score_messages.py             # Analyze outreach performance patterns
├── templates/
│   ├── en/                           # English templates (connection, cover letter, email, resume)
│   └── es/                           # Spanish templates
└── outputs/                          # Generated cover letters, resumes, daily summaries (gitignored)
```

## Configuration

All configuration lives in the `config/` directory. Copy the sample files and customize them:

| File | Purpose |
|------|---------|
| `profile.json` | Your name, contact info, career arc, skills, education, and credibility statements at three lengths (short/medium/long) |
| `search-criteria.json` | Target roles, industries with specific companies, preferred locations, search query keywords, scoring weights, and exclusions |
| `writing-style.json` | Sign-off variants by context (LinkedIn, email, formal), PM phrasing rules by company size, and general writing rules to follow |
| `talking-points.json` | Industry-specific talking points organized by context (AI/ML, fintech, enterprise SaaS, etc.) for personalizing outreach |

The `config_loader.py` script handles loading all config files and provides helper functions like `get_credibility("short")`, `get_sign_off("linkedin")`, and `get_pm_phrase("startup")` that templates and scripts use automatically.

## Customization

### Adding Custom Templates

Create new `.md` files in `templates/`. Use `{{placeholder}}` syntax for dynamic values:

- `{{name}}`, `{{first_name}}`, `{{title}}` - from your profile
- `{{email}}`, `{{phone}}`, `{{website}}`, `{{location}}` - contact info
- `{{sign_off_linkedin}}`, `{{sign_off_email}}`, `{{sign_off_formal}}` - context-specific sign-offs
- `{{cred_short}}`, `{{cred_medium}}`, `{{cred_long}}` - credibility statements at different lengths

### Adding Talking Points

Edit `config/talking-points.json` to add new industry categories or context-specific points. These are used by Claude to personalize outreach for specific companies and roles.

### Writing Rules

Edit `config/writing-style.json` to adjust:
- **sign_offs** - how you close messages in different contexts
- **pm_phrases** - how you describe your role by company size (e.g., "PM" for large companies, "product leader" for startups)
- **writing_rules** - constraints Claude follows when generating content (e.g., "never use the word 'synergy'", "keep sentences under 20 words")

### Company Classifications

Use the classifier to teach the system about new companies:
```bash
python scripts/company_classifier.py "Stripe" --add large
python scripts/company_classifier.py "Notion" --add startup
```

## LinkedIn Data Export

To match your existing connections with target companies:

1. Go to [LinkedIn Settings](https://www.linkedin.com/mypreferences/d/download-my-data)
2. Select **Connections** under "Get a copy of your data"
3. Click **Request archive**
4. Wait for the email (usually a few minutes)
5. Download and extract the archive
6. Copy `Connections.csv` to `data/connections.csv`

The CSV should have columns: `First Name`, `Last Name`, `URL`, `Email Address`, `Company`, `Position`, `Connected On`. See `data/connections-template.csv` for the expected format.

## API Setup

### JSearch (RapidAPI) - Recommended

JSearch aggregates listings from LinkedIn, Indeed, Glassdoor, and ZipRecruiter in a single API call. Free tier gives you **200 requests/month**.

The easiest path is `python setup.py --api-key`, which walks you through RapidAPI signup, subscribing to the free plan, pasting your key, and appending it to your shell profile. Or do it manually:

1. Go to [https://rapidapi.com/](https://rapidapi.com/) and create a free account (you can sign up with Google or GitHub)
2. Go to the JSearch API page: [https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
3. Click **"Subscribe to Test"** and select the **Basic (Free)** plan (200 requests/month, no credit card required)
4. After subscribing, you'll see the API playground. Your API key is shown in the **X-RapidAPI-Key** header field. Copy it.
5. Set the environment variable:
   ```bash
   # Add to your ~/.zshrc or ~/.bashrc for persistence:
   export RAPIDAPI_KEY=your_key_here
   ```
6. Verify it works:
   ```bash
   cd /path/to/job-search-and-tracker
   python3 scripts/fetch_jobs.py --keywords "Software Engineer" --locations "Remote"
   ```

**Usage notes:**
- Each keyword + location combination = 1 API request
- A typical search (e.g., 4 keywords x 2 locations) = ~8 requests per fetch
- Free tier resets monthly. At ~8 requests per fetch, the 200/month cap gives you ~25 fetches per month. Narrow your keyword list if you want to fetch more often.

## Dashboard

The local dashboard lives under `dashboard/` and is served by a small Python HTTP server:

```bash
python scripts/dashboard.py        # regenerates data, starts server, opens browser
python scripts/dashboard.py --no-browser  # headless mode
python scripts/dashboard.py --port 9000   # custom port
```

Pages:
- `dashboard.html` — stats, weekly activity, goal circles
- `jobs.html` — all fetched jobs with filters, apply/ignore/referral buttons, and matched connections per role
- `companies.html` — company-level view

State is persisted to `data/tracking.json` (gitignored). The dashboard talks to the local server's `/api/*` endpoints while it's running and falls back to an embedded `dashboard/data.js` file otherwise.

## Tests

The test suite covers the tracking module and the scripts that depend on it. Tests use only Python's stdlib `unittest` — no extra dependencies to install — and each test isolates itself with `tempfile`, so running them never touches your real `data/tracking.json` or any other user data.

```bash
python -m unittest discover tests
```

## Upgrading from a pre-dashboard clone

If you have an existing `data/outreach-history.json` from an older version, there's nothing you need to do. The tracking-aware scripts (`update_outreach.py`, `score_messages.py`, `local_server.py`, and anything else that touches tracking data) auto-migrate its contents into `data/tracking.json` the first time they run. You'll see a one-line notice in the script output like:

```
Migrated 3 legacy outreach entries from outreach-history.json.
```

The migration is idempotent and non-destructive — the legacy `outreach-history.json` file is left in place untouched, so you can keep it as a backup or delete it yourself once you've confirmed the new `data/tracking.json` looks right.

If you'd rather trigger the migration explicitly — for example, right after upgrading and before running any other command — you can still run:

```bash
python scripts/migrate_outreach_to_tracking.py
```

This does exactly the same thing the auto-migration does, just on demand.

## License

MIT
