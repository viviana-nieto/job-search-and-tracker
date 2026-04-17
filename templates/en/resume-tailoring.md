# Resume Tailoring Template

## Purpose
Tailor the user's base resume to a specific job description while maintaining the original format, structure, and truthfulness.

## Inputs Required
- Base resume (from config: resume_path)
- Job description (full text)
- Company name and role title

## Tailoring Rules

### What TO do:
- Reorder bullet points within each role to prioritize JD-relevant experience first
- Mirror keywords from the JD naturally (e.g., if JD says "cross-functional collaboration", use that phrase if your experience matches)
- Emphasize quantified achievements that align with the role's focus areas
- Adjust the professional summary/headline to reflect the target role
- Highlight technical skills mentioned in the JD that the user actually has
- If the JD emphasizes leadership, lead with leadership bullets. If it emphasizes technical depth, lead with technical bullets.

### What NOT to do:
- Never add experience, skills, or achievements the user doesn't have
- Never change job titles, company names, or dates
- Never invent metrics or numbers
- Never remove roles entirely (reorder bullets within roles instead)
- Never change the visual format/structure of the resume
- Keep the same number of bullet points per role (don't add or remove)

### Tailoring Process:
1. Read the full job description carefully
2. Identify the top 5 requirements/themes from the JD
3. For each role in the resume, reorder bullets so the most JD-relevant ones come first
4. Adjust the professional summary to reflect the target role
5. Ensure skills section highlights JD-relevant skills first
6. Review: does this resume read like someone who is a natural fit for THIS specific role?

## Output Format

Save tailored resume as markdown, maintaining the exact same section structure as the original:
- Same sections in the same order
- Same roles in the same order
- Bullet points reordered within each role
- Professional summary adjusted

### Visual format reproduction

If `config/resume-format.json` exists, the PDF generator will mimic the
original resume's visual style (fonts, sizes, colors, margins, bullet chars,
section dividers). No changes needed in the markdown.

For resumes with a 2-column layout (detected in the format profile), you can
use these markers in the tailored markdown to control column placement:

```
<name + contact header here>

<!-- sidebar -->
## SKILLS
- Python
- SQL

## EDUCATION
Stanford MBA

<!-- main -->
## EXPERIENCE
...
```

If no markers are provided, Skills / Education / Certifications / Languages
default to the sidebar and everything else to the main column.

## Variables
- `[Company]` - Target company
- `[Role]` - Target role title
- `{{name}}` - From config
- `{{title}}` - From config (may be adjusted to match target role)
- `{{email}}`, `{{phone}}`, `{{website}}`, `{{location}}` - From config

## Quality Check
After tailoring, verify:
1. Every bullet point is factually true (exists in base resume)
2. No new information was invented
3. The resume still reads naturally, not keyword-stuffed
4. Format matches the original resume exactly
5. The top 3 JD requirements are clearly addressed in the first page
