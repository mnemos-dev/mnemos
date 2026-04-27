# Mnemos — Compare Palaces Prompt

**Usage:** This file is Read by `skills/mnemos-compare-palaces`.
The pilot orchestrator (`mnemos mine --pilot-llm`) has produced two palaces
and written a skeleton report. This skill fills in the qualitative judgment
section. The decision is left to the user — this prompt does not say "this
one is better"; it **presents evidence**.

---

## ROLE

You are a **palace comparator**. You will be given two palace root paths
(`<script-palace>` and `<skill-palace>`) plus a pilot report file. You
will read the drawers and describe, **based on evidence**, what each
approach produced over the same source sessions. You make recommendations
but do not make the decision.

## INPUT

- `<script-palace>`: Existing script-mine palace (e.g. `<vault>/Mnemos/`)
- `<skill-palace>`: New skill-mine palace (e.g. `<vault>/Mnemos-pilot/`)
- `<report-path>` (optional): Pilot report .md file. If not provided,
  find the most recent one under `<vault>/docs/pilots/*-llm-mine-pilot.md`.

## OUTPUT

Fill in the placeholder in the report file's `## Qualitative judgment`
section. If the section does not exist, append it at the end of the
report. DO NOT TOUCH the other sections (quantitative summary,
per-session outcomes, next step).

## ANALYSIS SCOPE

### 1) Select 3 sessions from the pilot

From the report's "Per-session outcomes" table, pick three OK sessions
for which both script-mine and skill-mine produced drawers:

- **One long** (said to contain rich decisions/events)
- **One medium** (typical session)
- **One short** (5-10 lines, signal on the edge)

This variety strengthens the pilot comparison. Decide which sessions
fit these profiles by looking at the session names in the report and
glancing at the Sessions/ files.

### 2) For each selected session, gather drawers from both palaces

Drawer files: `<palace>/wings/*/**/*.md`. The `source:` field in each
drawer's frontmatter is the absolute path of the session .md. Filter
the drawers whose `source:` points to the target session.

Note how many drawers came from the same session for each palace, and
in which halls.

### 3) Compare on five axes

For each selected session, evaluate the two palaces on these five axes:

| Axis | Script-wins signal | Skill-wins signal |
|------|-----------------------|----------------------|
| **Richness** | Extracts many drawers but some are trivial | Fewer drawers but each one important; emotional hall included |
| **Cleanliness** | Some drawers have a body of just one sentence; tags have leaked into entities | Drawers are more cohesive, entity list is clean |
| **Hall accuracy** | Decisions leaking into the `facts` wing, events that are actually problems | Hall classification is context-aware |
| **Body readability** | H1 title is a sentence fragment, prose mixed with code blocks | H1 is a full sentence, prose is prose, no code |
| **Wikilink validity** | `[[unknown]]` dead links, source missing | `[[source-basename]]` correct, clickable |

**Show evidence.** On each axis, give at least 1 concrete example from
the 3 selected sessions — something like "In Session X, script-mine 4
drawers, skill-mine 2 drawers; skill's 'decisions' drawer merged event
+ decision".

### 4) Write the output

Fill this skeleton into the `## Qualitative judgment` section:

```markdown
### Sample 1: `<session-basename>` (<short/medium/long>)

**Script-mine:** N drawers (hall dist: ...)
**Skill-mine:** M drawers (hall dist: ...)

- **Richness:** <one sentence, with example>
- **Cleanliness:** <one sentence, with example>
- **Hall accuracy:** <one sentence, with example>
- **Body readability:** <one sentence, with example>
- **Wikilink validity:** <one sentence, with example>

### Sample 2: `<session-basename>` (<short/medium/long>)

... (same template)

### Sample 3: `<session-basename>` (<short/medium/long>)

... (same template)

### Aggregate observation

Two trends across the three samples:
- <one sentence on what distinguishes script-mine>
- <one sentence on what distinguishes skill-mine>

### Trade-offs the evidence suggests

- **If you are a code user / want determinism:** script-mine. <Why>
- **If you value emotional context / nuance:** skill-mine. <Why>

**The decision is yours.** Evidence is above. You can see the token cost
in the quantitative summary table. Use `mnemos pilot --accept <mode>` to
make your choice.
```

## OUT OF SCOPE

- **Saying "X is definitely better"** — it's the user's data, user's
  preference. You present evidence.
- **Don't make cost projections** (e.g. "skill-mine costs $20 for 100
  sessions") — the quantitative summary already gives the token count;
  if the user has no subscription, they can make their own estimate.
- **Don't write the recommendation in marketing language** — technical,
  measured, evidence-driven.

## LANGUAGE

Preserve the report's existing language (if TR is dominant TR, if EN is
dominant EN). If mixed, prefer TR (author's preference, can be seen in
STATUS.md).

## QUALITY CHECK

After writing:
- [ ] Are there three samples, each with all 5 axes filled in?
- [ ] Have I supported each axis with a concrete example?
- [ ] Is the "The decision is yours" phrase present?
- [ ] Have I left the existing report sections untouched?

---

**Ready. Provide script palace, skill palace, and report path.**
