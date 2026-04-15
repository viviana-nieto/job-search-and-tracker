# Git Hooks

## Pre-commit PII guard

Scans staged files for personal data (names, emails, file paths, embedded data blobs) before every commit. Blocks the commit if anything is found.

### Install

```bash
git config core.hooksPath .githooks
```

### Skip once (for a commit you've manually verified)

```bash
git commit --no-verify
```

### What it checks

- Owner name references (excluding GitHub username URLs)
- Work identity references
- Real email addresses (only `@example.com` is allowed)
- Hardcoded personal file paths (`/Users/viviana/`)
- HTML files with lines > 10KB (indicates embedded data blobs)
