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

    mnemos_search(query=<user's full query>, limit=8, collection="both")

Do NOT pass `wing`, `room`, `hall`, or any filter. The user invoked
this skill precisely because they want cross-context — filtering by
current cwd or wing would defeat the purpose.

The result is a list of hits. Each hit carries at minimum:
`drawer_id`, `score`, `wing`, `room`, `hall`, `source_path`, `snippet`.
(Exact shape comes from `mnemos/server.py` — the MCP JSON is
pass-through.)

### Step 4 — Evaluate match quality

Inspect the top 3 hits by `score`:

- **If the top 3 are all below 0.5, or the search returned 0 results:**
  go to Step 6 (soft fallback). Do not synthesize — you will hallucinate.
- **Otherwise:** proceed to Step 5.

The 0.5 threshold is a calibrated default (RRF score combining raw and
mined collections). See the spec §11 for the rationale; if you are an
implementer and the threshold feels off for a specific backend, leave
the code alone and report back — calibration belongs in review, not
ad-hoc edits.

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
  unchanged regardless.
- **Prose paragraphs.** No headers unless the answer genuinely spans
  multiple halls (decisions + problems + events) and structure helps.
- **No hedging.** Skip "sanırım", "umarım", "I think". If the drawers
  are thin on a specific detail, say so ("drawer'larda X konusunda
  açık kayıt yok") rather than filling gaps with guesses.

### Step 7 — Soft fallback (no strong match)

Triggered when Step 4 sends you here (top score < 0.5 or no results).
Output format:

    Buna dair net kayıt bulamadım. En yakın 3 drawer:

    1. [[<slug-of-hit-1>]] (score=X.XX, wing=<wing>, hall=<hall>)
       <one-line snippet>
    2. [[<slug-of-hit-2>]] ...
    3. [[<slug-of-hit-3>]] ...

    Bu sorgu için palace'ta özel bir kayıt yok; yukarıdakilerden biri
    aradığın olabilir.

If there are fewer than 3 hits, list what you have. If there are
**zero** hits at all, emit:

    Palace'ta hiçbir drawer arama kriterine uymadı. Palace boşsa
    `mnemos mine Sessions/` ile başlayabilirsin.

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
spawn etmez, ayrı bir oturum açmaz. Tipik maliyet: 1 MCP call (lokal,
<50ms) + 5 `Read` (lokal, <20ms toplam) + ~5-15K input token drawer
body'leri için + ~500-1000 output token cevap için. Tek turn içinde
biter.
