# Example: Non-Technical Ebook Generation

VasukiSquare is not limited to software programming manuals. It can generate structured, factual books on business, productivity, psychology, history, science, and practical guides.

## Generation Command

```bash
vasukisquare \
  --topic "Building Sustainable Daily Routines: The Psychology of Micro-Habits" \
  --title "Atomic Daily Routines" \
  --prompt "A practical self-improvement guide for knowledge workers and students. Include actionable exercises, reflection checklists, cognitive behavioral science principles, common failure modes, and a 30-day implementation roadmap." \
  --pages 35 \
  --output-dir "./output/daily-routines"
```

## Linux / macOS Bash

```bash
vasukisquare \
  --topic "Building Sustainable Daily Routines: The Psychology of Micro-Habits" \
  --title "Atomic Daily Routines" \
  --prompt "A practical self-improvement guide for knowledge workers. Focus on actionable exercises, reflection checklists, and a 30-day habit roadmap." \
  --pages 35 \
  --output-dir "./output/daily-routines"
```

## Windows PowerShell

```powershell
vasukisquare `
  --topic "Building Sustainable Daily Routines: The Psychology of Micro-Habits" `
  --title "Atomic Daily Routines" `
  --prompt "A practical self-improvement guide for knowledge workers. Focus on actionable exercises, reflection checklists, and a 30-day habit roadmap." `
  --pages 35 `
  --output-dir "./output/daily-routines"
```

## Pipeline Behavior for Non-Technical Subjects

1. **Intent Inference**: Sets `is_technical=false` and `code_requirements=false`.
2. **Component Customization**: Suppresses code snippet blocks and replaces them with concept cards, bulleted takeaways, checklists, callout boxes, and reflection questions.
3. **Research Strategy**: Queries psychological literature, behavioral research, and authoritative lifestyle studies rather than software repositories.
4. **Content Validation**: Audits the book for clarity, actionable steps, and absence of unwarranted code syntax.

