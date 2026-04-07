# Email Outreach Template

## Structure

Every email needs:
1. **5 Subject Line Variants**
2. **Body** (3-4 paragraphs max)
3. **Clear CTA** with specific ask

---

## Subject Line Variants

Generate 5 options from these categories:

### 1. Direct
```
Quick question about [Role] at [Company]
[Role] opportunity at [Company]
```

### 2. Curiosity
```
Saw [Company]'s work on [specific thing]
Your [team/product] caught my attention
```

### 3. Mutual Connection
```
[Mutual Name] suggested I reach out
[Mutual Name] mentioned your team
```

### 4. Value-First
```
[Quantified impact] in [domain], interested in [Company]'s mission
[Title] exploring [Company]
```

### 5. Question
```
15 min for coffee? [Company] + [your domain]
Can I pick your brain about [Company]?
```

---

## Email Body Templates

### Template A: Recruiter/HR (Warm Lead)

```
Hi [Name],

[Personal connection opener: mutual contact, how you found them, or their post]

I know [acknowledgment: role may be in progress, team is busy, etc.], but I'd love to stay on your radar. {{cred_medium}}

If you have [Role] opportunities that could be a fit, I am actively looking and happy to connect!

I'm attaching my resume for your reference.

{{sign_off_email}}
{{first_name}}
```

### Template B: Hiring Manager/Team Member

```
Hi [Name],

I came across [how you found them: their profile, article, the role posting] and wanted to reach out directly. {{cred_short}}, and [Company]'s work on [specific thing] is exactly the kind of problem I love solving.

Quick background: {{cred_medium}}

Would you have 15 minutes for a quick call? I'd love to learn more about [specific aspect of their work/team].

{{sign_off_email}}
{{first_name}}
```

### Template C: Cold Outreach (No Mutual)

```
Hi [Name],

I hope this email finds you well. I'm reaching out because [specific reason: role posting, company news, their content].

I'm currently exploring opportunities in [industry], and [Company]'s approach to [specific thing] stands out. {{cred_medium}}

I'd love to connect if you have a few minutes. Would [specific day] or [specific day] work for a brief call?

{{sign_off_email}}
{{first_name}}
```

---

## Key Elements

### Opening Lines (Pick One)
- "My friend [Name] shared your message about..."
- "I came across your profile while researching..."
- "I saw [Company]'s announcement about..."
- "I recently applied for [Role] and wanted to reach out directly."
- "[Mutual] mentioned you're the person to talk to about..."

### Credibility Arc (Adapt Based on Role)
- **Full**: {{cred_long}}
- **Short**: {{cred_short}}
- **Medium**: {{cred_medium}}

### CTAs (Pick One)
- "Would you have 15 minutes for a quick call?"
- "Happy to connect over coffee if you're in [location]."
- "I'd love to stay on your radar for future opportunities."
- "Would [day] or [day] work for a brief chat?"
- "If you have a few minutes, I'd appreciate any insights."

### Sign-offs
- `{{sign_off_email}}` (default for email)
- `{{sign_off_formal}}` (more formal)

---

## Variables

- `[Name]` - Recipient first name
- `[Company]` - Target company
- `[Role]` - Specific role title
- `[Mutual Name]` - Mutual connection
- `[specific thing]` - Company product, mission, or news
- `[industry]` - Your target industry
- `[specific day]` - Suggest actual days (Tuesday, Thursday)

---

## Writing Rules

Follow rules from config/writing-style.json, plus:
1. Keep paragraphs to 2-3 sentences.
2. One clear CTA per email.
3. Attach resume when appropriate (mention it).
4. Total length: Under 200 words for cold outreach.
