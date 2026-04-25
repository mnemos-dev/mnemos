---
name: mnemos-recall
description: Cross-context recall from the Mnemos memory palace.
  User invokes /mnemos-recall <query> to ask a free-text question;
  skill searches the palace via MCP, reads top drawers, and synthesizes
  a narrative answer with wikilink citations. In-session only
  (no subprocess). Use when cwd-based auto-briefing doesn't cover
  the query (e.g. working in cwd A but asking about work done in cwd B).
---

# Mnemos recall skill — explicit cross-context query

You have been invoked in the current Claude Code session as the slash
command `/mnemos-recall`. Everything after the command name on the
user's line is the **free-text query**.

The cwd-scoped auto-briefing (installed by `mnemos install-recall-hook`)
already handles "where are we in this project" at session start. This
skill exists for the cross-context case: user is working in cwd A but
remembers something from cwd B, or wants to pull a decision from a
different wing. Answer with a short narrative; cite every drawer you
lean on.

**You are NOT a subprocess.** You are the current session's Claude.
The mnemos MCP tools (`mnemos_search`, `Read`, etc.) are already bound
to you. Use them directly. Do not spawn `claude --print` or any child
process.

## Process

### Step 1 — Parse arguments

The user's query is everything after `/mnemos-recall `. If the argument
is empty, go to the "No arguments" branch under Errors below.

### Step 2 — Check that mnemos is connected

Confirm `mnemos_search` is a callable tool in this session. If it is
not (no MCP binding), go to the "Mnemos not connected" branch under
Errors. The most reliable check is to attempt the call in Step 3 and
handle the tool-not-found error there — do not fabricate a check.

### Step 3 — Semantic search

Call:

    mnemos_search(query=<user's full query>, limit=8, collection="raw")

Do NOT pass `wing`, `room`, `hall`, or any filter. The user invoked
this skill precisely because they want cross-context — filtering by
current cwd or wing would defeat the purpose.

v1.0 narrative-first pivot: only the `raw` collection (Sessions/<date>-<slug>.md
files) is searchable — the mined-fragments collection was retired.
`collection="raw"` is the default and only valid value; passing
`"mined"` or `"both"` triggers a deprecation warning and falls back
to raw.

The result is a list of hits. Each hit carries at minimum:
`drawer_id`, `score`, `wing`, `room`, `hall`, `source_path`, `snippet`.
(Exact shape comes from `mnemos/server.py` — the MCP JSON is
pass-through.)

### Step 4 — Evaluate match quality

Inspect the top 3 hits by `score` (or all hits if fewer than 3 were
returned):

- **If the top 3 are all below 0.015, or the search returned 0 results:**
  go to **Step 7 (Sessions grep rescue)**. Do not synthesize — you will
  hallucinate. If the rescue also comes back empty, Step 7 will chain to
  Step 8 (soft fallback).
- **Otherwise:** proceed to Step 5.

The 0.015 threshold is a calibrated default for RRF scoring with k=60.
v1.0 searches only the raw collection, so RRF is now single-stream
(`1/(60+rank_raw)`); 0.015 ≈ rank-7 floor below which hits are
typically topically unrelated noise. Spec §11 documents calibration
policy. Note that Step 5 below reads up to 5 drawers for narrative
breadth; the threshold sample stays at 3 because a quality check is
cheap and representative.

## Score Threshold

Default threshold: **0.015** (k=60 RRF scoring).

**Calibration note:** This threshold was calibrated (kalibre edildi)
on the kasamd vault (sqlite-vec backend, ~78 Sessions). New vaults may
behave differently; ChromaDB vs sqlite-vec score distributions can
vary. The threshold is soft — if scores fall below it, the skill
falls through to Sessions grep rescue (Step 7) which usually recovers
a useful answer regardless of score band. v1.1 may make this
configurable via `mnemos.yaml` if pilots show recurring miscalibration.

### Step 5 — Read drawers (in score order, stop at 5 successes)

Iterate the hits from highest score to lowest. For each:

1. `Read` the file at `source_path` (full body).
2. If Read fails (file missing / renamed / not a file), **skip** and
   continue with the next candidate.
3. Stop after 5 **successfully read** drawers, or when the candidate
   list is exhausted.

The 8-hit search intentionally gives a 3-drawer buffer for broken
links. If fewer than 5 drawers are readable, synthesize from whatever
did load — do not retry the search.

If **zero** drawers are readable across the top 8, emit:

    Index-filesystem uyumsuzluğu var — palace'ta bu sorguyla eşleşen
    drawer'lar için `.md` dosyaları bulunamadı. `mnemos mine --rebuild`
    ile indexi yenileyin.

And stop.

### Step 6 — Synthesize the narrative answer

Write a 150-300 word narrative answering the user's question. Rules:

- **Cite every claim.** Each sentence that asserts a fact or decision
  gets `[[drawer-slug]]` at the end, where `drawer-slug` is the
  drawer's filename without the `.md` extension (Obsidian will open
  it on click).
- **Language = query language.** TR query → TR answer. EN query → EN
  answer. If the drawer bodies are in a different language from the
  query (common case: TR query, some EN drawer bodies), summarize the
  content _in the query's language_ — the wikilink slug stays
  unchanged regardless (do not translate `[[po-edge-pdf]]` to
  `[[po-kenar-pdf]]` or similar).
- **Prose paragraphs.** No headers unless the answer genuinely spans
  multiple halls (decisions + problems + events) and structure helps.
- **No hedging.** Skip "sanırım", "umarım", "I think". If the drawers
  are thin on a specific detail, say so ("drawer'larda X konusunda
  açık kayıt yok") rather than filling gaps with guesses.
- **Single drawer.** If exactly one drawer was successfully read,
  synthesize normally but end the answer with this sentence:
  "Bu konuda palace'ta tek kayıt var; daha fazla bağlam için `mnemos
  mine` ile indeksi genişletebilirsin."

### Step 7 — Sessions grep rescue (fallback before giving up)

Triggered from Step 4 when drawer scores are all below 0.015 (no strong
semantic match). Embedding-based search sometimes misses obvious matches
— especially for Turkish-dominant queries against mixed-language drawers,
for unique project names, or when a topic was discussed in JSONL
transcripts but didn't get mined into a dedicated drawer. Session .md
files are refined per-conversation summaries; a plain keyword grep over
them often finds matches the vector index missed.

**1. Derive the vault root.**
Any hit from Step 3's `mnemos_search` carries `source_path` like
`<vault>/Mnemos/<wing>/<room>/drawers/<slug>.md`. Walk up the path until
you find the directory that contains both `Sessions/` and `Mnemos/`
subdirectories — that's the vault root. If Step 3 returned 0 hits
(no source_path to derive from), skip this step and go straight to
Step 8 (soft fallback).

**2. Extract 2-4 content keywords from the query.**
Strip question words, stopwords, and tense markers. Keep noun phrases,
project names, and unique terms.

- `"tavuklu bir oyun yapacaktık biz sanki?"` → `["tavuk", "oyun"]`
- `"PO skill formatı neydi"` → `["PO", "skill", "format"]`
- `"procuretrack onaycılar kimdi"` → `["procuretrack", "onaycı"]`

**3. Grep each keyword against `<vault>/Sessions/`.**
Use Claude Code's `Grep` tool (case-insensitive) with
`output_mode="files_with_matches"`:

    Grep(pattern=keyword, path="<vault>/Sessions", -i=true,
         output_mode="files_with_matches", glob="*.md")

Collect the result file lists per keyword.

**4. Score sessions by keyword coverage.**
For each unique Session file across all keyword hits, `score = count of
distinct keywords it matched`. Break ties by filename date (newer first —
Session filenames start `YYYY-MM-DD-...`).

**5. If no Session file matched any keyword → chain to Step 8.**

**6. Otherwise: pick top 3 Session files by score.**
`Read` each fully (they are ~5-15 KB — small enough). Focus synthesis on
their `Özet`, `Alınan Kararlar`, `Sorunlar`, `Sonraki Adımlar` sections
(markdown `##` headers in Turkish refined sessions).

**7. Synthesize narrative answer (same rules as Step 6 drawer path).**
150-300 words, query language, cite as `[[session-slug]]` where
`session-slug` is the Session filename without the `.md` extension
(Obsidian opens the Session file directly; this is different from drawer
wikilinks but uses the same `[[...]]` syntax).

**8. Append a one-line attribution footer to the narrative:**

    _Drawer index'te doğrudan match yoktu; bu cevap Session
    dosyalarından sentezlendi — konu henüz ayrı drawer'a
    ayrıştırılmamış olabilir._

This tells the reader: the answer is grounded in refined conversation
summaries, not distilled drawers, and that a `mnemos mine Sessions/`
run might promote the detail into a proper drawer.

### Step 8 — Soft fallback (no match anywhere)

Triggered when both the drawer path (Step 5-6) and the Sessions rescue
(Step 7) came up empty. Output format:

    Buna dair net kayıt bulamadım. En yakın 3 drawer:

    1. [[<slug-of-hit-1>]] (score=X.XX, wing=<wing>, hall=<hall>)
       <one-line snippet>
    2. [[<slug-of-hit-2>]] ...
    3. [[<slug-of-hit-3>]] ...

    Bu sorgu için ne drawer index'te ne de Sessions grep'inde özel kayıt
    bulundu. Yukarıdakilerden biri ilgili olabilir.

If there are fewer than 3 drawer hits, list what you have. If there are
**zero** drawer hits at all, emit:

    Palace'ta hiçbir drawer arama kriterine uymadı ve Sessions grep'i de
    boş döndü. Palace boşsa `mnemos mine Sessions/` ile başlayabilirsin.

## Errors

- **No arguments (`/mnemos-recall` alone):**

      Kullanım: /mnemos-recall <soru>
      Örnek: /mnemos-recall "PO skill formatı neydi"

      Cwd-bazlı otomatik briefing'in kapsamadığı cross-context sorgular
      için. Otomatik briefing session başında sessizce yükleniyor —
      explicit recall'u yalnızca onunla cevaplanmayan soru için çağır.

- **Mnemos not connected (no `mnemos_search` tool):**

      Mnemos MCP bağlı değil. `mnemos init --vault <path>` ile kurulumu
      tamamla, Claude Code'u yeniden başlat, sonra bu skill'i çağır.

## Cost

Skill current Claude Code session'ının içinde çalışır — `claude --print`
spawn etmez, ayrı bir oturum açmaz.

Typical happy-path (strong drawer match): 1 MCP call (<50ms) + 5 `Read`
(<20ms) + ~5-15K input token + ~500-1000 output token. One turn.

Sessions grep rescue (weak drawer match): +2-4 `Grep` calls (each <50ms
across ~70 Session files) + 3 `Read` on matched sessions (each ~5-15 KB).
Net +100-300ms and +5-15K input token over the happy path. Still one
turn.
