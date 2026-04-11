# /setup

Walk the user through the full job search agent configuration conversationally — same outcome as running `python setup.py` in a terminal, but without ever leaving the Claude Code chat.

**Do NOT run `python setup.py` directly.** That script uses `input()` extensively and will hang when invoked via the Bash tool because Bash can't feed keystrokes to a running process. This skill IS the setup wizard, translated into chat.

---

## How to execute this skill

You are running interactively in Claude Code. Use these tools:

- **Chat messages** — ask the user each question and wait for a response. One question at a time unless they're cheap follow-ups in the same group (e.g., "name, email, phone, location").
- **Read** — to consult `setup.py` (for canonical question text, defaults, and return shapes) and the `config/*.sample.json` files (for exact JSON shapes).
- **Write** — to create the four config JSON files at the end. Never use Bash redirection for JSON — Write is safer.
- **Bash** — for copying files (resume, LinkedIn connections CSV), appending to shell rc, running `python setup.py --from-config`, running `python scripts/fetch_jobs.py`, and launching the dashboard.

If the user says "pause" or "come back to this later" at any step, stop cleanly and tell them they can re-run `/setup` to pick up from the beginning or use the terminal flags (`python setup.py --connections`, `--api-key`, `--keywords`, `--fetch`) to update individual pieces.

---

## Required reading before asking any questions

Before your first question, read these files so you know exactly what you're collecting and what shapes to produce:

1. **`setup.py`** — search for the functions `collect_personal_info`, `collect_career_context`, `collect_credibility`, `collect_search_preferences`, `collect_writing_style`, `collect_talking_points`. Each has the canonical question text, default values, and the exact dict shape it returns. Mirror them faithfully — the goal is feature parity with the terminal wizard, not reinvention.
2. **`config/profile.sample.json`**, **`config/search-criteria.sample.json`**, **`config/writing-style.sample.json`**, **`config/talking-points.sample.json`** — these show the exact JSON structure of each config file you'll produce.
3. **`data/tracking-template.json`** — the v3.0 tracking schema, in case you need to initialize it.
4. **`data/connections-template.csv`** — LinkedIn connections CSV format, in case the user asks what format to provide.

After reading, give the user a one-sentence summary of what you're about to do and ask if they're ready.

---

## Step 0 — Introduction

Say something like:

> I'll walk you through configuring this job search agent. It takes about 5-10 minutes and covers:
>
> 1. Personal info and career context
> 2. Credibility snippets used in outreach messages
> 3. Job search preferences (target roles, keywords, locations)
> 4. Writing style and talking points
> 5. LinkedIn connections import (optional — you can skip and come back later)
> 6. RapidAPI key for job fetching (optional — free tier is 200 requests/month)
> 7. First job fetch and dashboard launch
>
> Ready to start?

If the user declines, stop here. If they agree, continue.

---

## Step 1 — Personal Information

Mirror `collect_personal_info` in `setup.py`. Ask for:

- **Full name** (required)
- **Professional headline** (e.g., "Product and AI Leader") (required)
- **Email** (required)
- **Phone number** (required)
- **Website or LinkedIn URL** (optional)
- **Location** (default: `San Francisco Bay Area`)

Then the resume prompt:

- **Resume path**: ask for the absolute path to their resume file. Validate:
  - File must exist on disk — use Bash `test -f "$PATH" && echo OK || echo MISSING`
  - Extension must be one of `.pdf`, `.md`, `.markdown`, `.docx`
  - If invalid, explain what failed and loop: offer another path, or skip
  - If valid, offer to copy the file into `data/resume.<ext>` (which is gitignored, makes the config portable). If they accept, use `Bash cp "$SRC" data/resume.<ext>` and store the in-project path in the profile. If they decline, store the original absolute path as-is. If they skip the resume entirely, print a warning that cover-letter and resume-tailoring commands will have limited context, and require an explicit "yes skip anyway" confirmation before proceeding.

Finally:

- **Languages** (comma-separated, default: `en, es`)
- **Default language** (default: first language from the list)

Hold the answers in memory for later — do not write any files yet.

---

## Step 2 — Career Context

Mirror `collect_career_context`. Ask:

- **Years of professional experience** (default: `10`)
- **Key roles**: ask for 2-4 of their most impressive roles. For each, ask for company, title, and one achievement line. Build a list of `{"company", "title", "achievement"}` dicts.
- **Core skills** (comma-separated list)
- **Education** (degree, school, year — as a list of dicts)

---

## Step 3 — Credibility Snippets

Mirror `collect_credibility`. The terminal wizard collects short, medium, and long versions of credibility statements used in outreach templates. Ask for each and also collect 2-3 quantified impact bullets (e.g., "Grew X from $0 to $5M ARR in 18 months").

The return shape is `(credibility_dict, quantified_impact_list)`. Consult `setup.py:collect_credibility` for the exact keys.

---

## Step 4 — Job Search Preferences

Mirror `collect_search_preferences`. Ask:

**Roles**
- Target role titles (default: `Product Manager, Senior Product Manager, Director of Product`)

**Industries and companies**
- Target industries (default: `AI/ML, SaaS, Fintech, Health Tech`)
- Target companies (optional, comma-separated)

**Locations**
- Preferred locations (default: `San Francisco Bay Area, Remote`)
- Acceptable locations (optional)

**Exclusions**
- Titles to exclude (default: `Junior, Associate, Intern, Entry Level`)
- Companies to exclude (optional)

**Search keywords**
- High-priority keywords (default derived from target roles)
- Medium-priority keywords (default: `AI Product Manager, Data Product Manager, Strategy`)

**Scoring weights** (1-10)
- Title match, industry match, company match, location match, seniority match (defaults: 10, 8, 7, 6, 9)

The return shape is a nested dict. Consult `setup.py:collect_search_preferences` — it is about 90 lines long, mirror it exactly.

---

## Step 5 — Writing Style

Mirror `collect_writing_style`. Uses the user's first name and their language list. Collects sign-offs per context (LinkedIn, email, formal), PM phrasing per company size, and writing rules. Shape is nested by language (`{"en": {...}, "es": {...}}`).

Consult `setup.py:collect_writing_style` for the exact structure — it's the longest function in the wizard.

---

## Step 6 — Talking Points

Mirror `collect_talking_points`. Industry-specific talking points organized by category (AI/ML, fintech, enterprise SaaS, etc.).

---

## Step 7 — LinkedIn Connections (optional)

Ask: "Have you already exported your LinkedIn connections?"

**If no:** tell them how to export — open `https://www.linkedin.com/mypreferences/d/download-my-data`, select Connections, click Request archive, wait for the email. Offer to pause here and wait for them to come back.

**If yes:** ask for the absolute path to their `Connections.csv`. Validate the file exists. If valid, use Bash to copy it to `data/connections.csv`:

```
cp "$SRC_PATH" data/connections.csv
```

If invalid or they want to skip, tell them they can run `python setup.py --connections` later or re-invoke `/setup` and they can proceed without connections.

---

## Step 8 — RapidAPI Key (optional)

First, check whether the key is already in the environment:

```
echo "${RAPIDAPI_KEY:-MISSING}"
```

If the output shows a real key, tell the user you detected an existing `$RAPIDAPI_KEY` and are using it. Skip this step.

Otherwise, ask: "Do you already have a RapidAPI key for JSearch?"

**If no:** walk them through signup, pausing after each step for confirmation:

1. Open `https://rapidapi.com/` and sign up (Google or GitHub login works)
2. Go to the JSearch API page: `https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch`
3. Click "Subscribe to Test" and choose the Basic (Free) plan (200 requests/month, no credit card)
4. Copy the `X-RapidAPI-Key` value from the API playground

After each step, ask "Ready?" and wait for confirmation.

**Once they have a key**, ask them to paste it into the chat. Validate: non-empty, no whitespace, reasonable length (30+ chars).

Then ask: "Want me to add this to your shell profile so it's set in new terminals?"

**If yes:**
1. Detect their shell from `$SHELL`. `zsh` → `~/.zshrc`, `bash` → `~/.bashrc`. If ambiguous, ask which.
2. Check for an existing `export RAPIDAPI_KEY` line using Bash `grep "RAPIDAPI_KEY" ~/.zshrc` (or `~/.bashrc`). If one exists, ask for permission to replace it before writing.
3. Append (or replace) the line:
   ```
   echo '' >> ~/.zshrc
   echo '# Job Search Agent (JSearch)' >> ~/.zshrc
   echo 'export RAPIDAPI_KEY="$PASTED_KEY"' >> ~/.zshrc
   ```
4. Tell them to `source ~/.zshrc` or open a new terminal for the change to take effect.

**Important for this session:** since each Bash tool call runs in its own subshell, adding to `~/.zshrc` does NOT make the key available to subsequent Bash calls in this skill run. To run the first fetch in Step 11, you'll need to pass the key inline: `RAPIDAPI_KEY="..." python scripts/fetch_jobs.py ...`

Hold the pasted key in memory (as chat state) for Step 11.

---

## Step 9 — Write Config Files

Now that you have all answers, use the **Write** tool to create each config file. Follow the shapes from `config/*.sample.json` exactly. Never use Bash redirection (`echo > file`) for JSON — use Write.

Create these four files:

1. `config/profile.json` — shape from `config/profile.sample.json`, populated with the user's answers from Steps 1-3. Include `filename_prefix` computed as `LastName_FirstName` with any non-alphanumerics stripped (see `setup.py:make_filename_prefix`). Include `resume_path`, `languages`, `default_language`.

2. `config/search-criteria.json` — shape from `config/search-criteria.sample.json`, populated from Step 4.

3. `config/writing-style.json` — shape from `config/writing-style.sample.json`, populated from Step 5.

4. `config/talking-points.json` — shape from `config/talking-points.sample.json`, populated from Step 6.

After each file is written, tell the user the path it was written to.

Also ensure `data/tracking.json` exists (the local server needs it on the next step):

```
test -f data/tracking.json || cp data/tracking-template.json data/tracking.json
```

---

## Step 10 — Generate CLAUDE.md and skill file

Instead of manually constructing `CLAUDE.md` and `~/.claude/commands/job-search-agent.md` from scratch (too error-prone to reproduce in a skill), delegate to the existing non-interactive entry point:

```
python setup.py --from-config
```

This reads the four config JSONs you just wrote and regenerates `CLAUDE.md` at the project root and `~/.claude/commands/job-search-agent.md` as the user-level slash command. Non-interactive, safe to run via Bash.

Report what was created.

---

## Step 11 — First fetch and dashboard launch

Check whether a RapidAPI key is available (either from `$RAPIDAPI_KEY` in the env, or the one pasted in Step 8). If yes, ask: "Fetch jobs now? This uses about N API requests (of 200/month free)" where N = number of keywords × number of locations from Step 4.

**If yes and key was pasted in Step 8:**

```
RAPIDAPI_KEY="$PASTED_KEY" python scripts/fetch_jobs.py --keywords "$KW1" "$KW2" ... --locations "$LOC1" "$LOC2" ...
```

**If yes and key was already in env:** drop the `RAPIDAPI_KEY=` prefix, everything else is the same.

Pass each keyword and location as a separate shell-quoted argument (the `--keywords` and `--locations` flags take nargs="+"). Report how many jobs were fetched.

**After the fetch:** regenerate the dashboard data via:

```
python scripts/generate_data_js.py
```

Then offer: "Open the dashboard now?"

**If yes:** launch the server in the background and tell the user to visit `http://localhost:8777/dashboard.html`:

```
python scripts/dashboard.py
```

Note: `dashboard.py` auto-opens the browser by default. If the user is in a headless environment, suggest `python scripts/dashboard.py --no-browser` instead and have them open the URL manually.

---

## Step 12 — Wrap up

Report a summary of what was created:

- Config files at `config/profile.json`, `config/search-criteria.json`, `config/writing-style.json`, `config/talking-points.json`
- `CLAUDE.md` at the project root
- Skill file at `~/.claude/commands/job-search-agent.md`
- Connection CSV at `data/connections.csv` (if they provided one)
- Tracking file at `data/tracking.json`
- Dashboard running at `http://localhost:8777/dashboard.html` (if they opened it)

And tell them the daily commands:

- `python scripts/dashboard.py` — open the dashboard
- `python scripts/fetch_jobs.py` — fetch more jobs
- `/job-search-agent fetch jobs` — from Claude Code
- `/setup` again — re-run the full wizard if they want to reconfigure

---

## Key conventions

- **Read `setup.py` and sample config files FIRST.** Do not guess at question text, defaults, or JSON shapes — the canonical source of truth is on disk.
- **Ask one group of questions at a time.** Don't dump a 30-question form into the chat.
- **Respect skips.** Optional steps mean optional — if they skip, move on and note that they can come back later with `python setup.py --<flag>`.
- **Use Write for JSON, Bash for shell operations.** Never write JSON via Bash `echo` redirection.
- **Every written file gets confirmed to the user.** Show them the path after each Write.
- **If something fails**, explain what happened, offer to retry or skip, and never leave the config in a partially-written state.
- **Never commit anything.** This skill is about running setup, not git operations.
