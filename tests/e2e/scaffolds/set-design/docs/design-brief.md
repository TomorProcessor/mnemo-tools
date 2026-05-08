# Design Brief — set-design

> Non-authoritative tone note. The authoritative spec is `design-direction.md` and the v0 design source. This file captures intent for written content (microcopy, headings, error messages, tooltips).

## Voice

Clear. Technical. No marketing sparkle. The user is a developer who already knows what they want; we're not selling them anything.

- Use second person sparingly. "Open a folder" is better than "Open your folder" except where ownership clarity matters ("Save to your home folder").
- Prefer imperative verbs: "Open", "Send", "Revert". Avoid "Click here to…".
- Never use exclamation marks in normal UI copy. Reserve them for error states ("Build failed!" is acceptable; "Welcome!" is not).
- No emojis in copy. UI rows MAY use unicode dingbats for activity feed (📖 📝 ✏️ 🔧 ✅), but copy text never embeds emojis.

## Microcopy patterns

| Surface | Pattern | Example |
|---|---|---|
| Empty state | "Start [verb-ing]" + 1-line subtitle + 3 chips | "Start designing — Describe a component or paste a mockup" |
| Confirmation | Verb-led question, neutral phrasing | "Revert to commit `abc123f`?" |
| Destructive confirm | State the consequence first | "This will discard the last 2 turns. Revert anyway?" |
| Loading | Verb + ellipsis | "Starting dev server…" |
| Error banner | What broke + path forward | "Dev server crashed. [Restart]" |
| Toast (success) | Past tense + identifier | "Committed `abc123f`" |
| Toast (info) | Present tense | "Reconnecting to claude…" |
| Toast (error) | Code in monospace + 1-line cause | "`IMAGE_TOO_LARGE` — File exceeds 10 MB limit" |

## Error message tone

- Do NOT apologize. ("We're sorry, but…" is forbidden.)
- State the fact, then the action.
- Show the error code (UPPER_SNAKE_CASE) in monospace alongside the user-facing message — developers like seeing the code, and it makes support requests easier.

| ❌ Bad | ✅ Good |
|---|---|
| "Oops! Something went wrong with your image." | "`IMAGE_TOO_LARGE` — File exceeds the 10 MB limit. Try a smaller image." |
| "We couldn't connect to Claude. Please try again later." | "`CLAUDE_NOT_FOUND` — Claude CLI not in PATH. [Install instructions]" |
| "Sorry, this folder doesn't seem to be a git repository." | "`TARGET_NOT_GIT_REPO` — Folder is not a git repository. [Initialize git]" |

## Naming conventions

- The product name is **set-design** (lowercase, hyphenated). Never "SetDesign", "Set Design", "SET Design".
- The companion product name **SET** appears all-caps when referring to the orchestration framework. The "Push to SET" button is correct; "Push to set" is not.
- File paths and identifiers are always monospace.
- Commit SHAs are lowercase 7-char monospace (`abc123f`, not `ABC123F` or `abc123f0`).

## Content placeholders

When the design source needs sample text:

- For the welcome screen: actual product copy (above).
- For the chat panel empty state: actual product copy (above).
- For the preview iframe content: claude generates real UIs — no Lorem Ipsum.
- For settings page hint text: "What you need", "Adds approximately $0.005 per turn", etc. — real microcopy, not placeholder.

Do NOT use Lorem Ipsum anywhere in the design source. The TSX export is supposed to look like a real, functioning app.

## Future copy

Feature-specific microcopy lives in the corresponding `features/*.md` file. This brief covers cross-cutting tone only.
