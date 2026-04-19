# v0.4.0 — AI Boost / Phase 1 (design spec)

**Tarih:** 2026-04-19
**Durum:** Tasarım onaylandı, implementasyon başlıyor
**Önceki sürüm:** v0.3.3 post-v0.3.2 cleanup (2026-04-19 PyPI'ya çıktı)
**Sonraki sürüm:** v0.5.0 Automation / Phase 2

---

## 1. Problem özeti

Phase 0 teslim etti: API'siz regex + vector search ile LongMemEval 10q
subset'inde **%90 Recall@5** (2026-04-17, iki backend'de parity). Hedef
%95'e taşımak; ama bunu **API bağımlılığı eklemeden** yapmak hem ürün
vaadimizle (Obsidian-native, opak-sistem-yok) hem de Phase 0 doktriniyle
(*mnemos LLM çağırmaz*) uyumlu.

**Orijinal ROADMAP 4.1-4.6 (2026-04-13 Phase 0 spec'inde tasarlanmıştı):**
- 4.2 API-based LLM mining (`mnemos-dev[llm]` extra + `ANTHROPIC_API_KEY`)
- 4.3 API-based LLM reranking (search top-50 → top-10)
- 4.4 API-based contradiction detection
- 4.5 Benchmark (hedef R@5 ≥%95)

**Yeniden çerçeveleme (2026-04-19 tartışması, bu spec'in özü):**
v0.3.0'da teslim ettiğimiz `mnemos-refine-transcripts` skill'i kanıtladı ki
Claude Code oturumu içinde çalışan skill'ler, mnemos paketinin dışında
LLM işi yaptırmak için temiz bir yol. API paketlemeye gerek yok; kullanıcı
abonelik quota'sını kullanıyor; maliyet kullanıcıya şeffaf.

Bu paterni mining'in kendisine ve recall'a genişletiyoruz. Artık her
kullanıcının **iki ortogonal ekseni var:**

| | Script-recall | Skill-recall |
|---|---|---|
| **Script-mine** | (1) Bugün — hızlı, API'siz, deterministic | (2) Vector + LLM judgment |
| **Skill-mine** | (3) LLM'le zenginleşmiş drawer'lar, hızlı recall | (4) LLM her yerde — maks kalite, maks latency |

Kullanıcı başlangıçta bir **pilot** yapar (10 session hem script-mine hem
skill-mine'la paralel işlenir), ürettiği iki palace'ı kendi verisinde
karşılaştırır, karar verir, kaybeden `_recycled/`'a gider. Recall modu
runtime'da `mnemos settings`'ten değiştirilebilir — post-pilot tek palace
üzerinde dört kombonun hepsi yaşayabilir.

**4.3 rerank** bu modelde ayrı görev değil; skill-recall zaten LLM
judgment yapıyor, rerank onun içinde erimiş.

**4.4 contradiction** ortogonal endişe (hijyen); v0.5 Automation'a ertelendi.

---

## 2. Kapsam

### Kapsam içinde

- **4.2 Skill-mine + pilot orchestrator + comparison skill** — yeni
  `mnemos-mine-llm` skill'i, `mnemos mine --pilot-llm [N=10]` komutu, iki
  palace yan yana üretme, `mnemos-compare-palaces` skill'i LLM-judged
  karar raporu üretir.
- **4.3 Skill-recall** — `/mnemos-recall <query>` user-invoked skill;
  opt-in SessionStart briefing hook (refine-hook paraleli); MCP server
  `instructions` alanı `recall_mode` yaml ayarından dinamik üretilir.
- **4.5 `mnemos settings` TUI** — fragmanlı komutları (install-hook,
  install-statusline, migrate, yaml elle) tek numbered menu altında
  toplar. Mine-mode, recall-mode, backend, hook'lar, languages.
- **4.6 LongMemEval benchmark** — sadece S+S (script-mine + script-recall)
  combo'su için kantitatif ölçüm (500 soru full run, 4 mod). Skill modları
  kalitatif, pilot raporuna entegre.
- **4.7 PyPI release v0.4.0**

### Kapsam dışı (v0.5 veya sonrası)

- **API-based LLM mining** (`mnemos-dev[llm]` extra) — skill-mine paterniyle
  gereksiz.
- **Rerank ayrı görev olarak** — skill-recall içinde.
- **Contradiction detection / stale memory flagging** — v0.5 hijyen görevi.
- **Per-turn auto-recall** (UserPromptSubmit hook) — 5-15s blocking
  latency kullanıcı deneyimini bozar. SessionStart briefing yeter; explicit
  `/mnemos-recall` kalan kullanıcı ihtiyacını karşılar.
- **Multi-language skill prompts** (Phase 0 EN+TR marker desteği var ama
  skill prompt'ları öncelikle EN yazılır; TR+EN çıktı destekli) — marker
  genişletme v0.6 işi.
- **Palace merge** (script-mine + skill-mine drawer union'ı) — pilot
  sonrası kullanıcı birini seçer, diğeri recycle.

---

## 3. Mimari eksen — 4-kombo

Spec boyunca şu tabloya refer ediyoruz:

```
                        Script-recall            Skill-recall
                    ┌────────────────────┬────────────────────┐
     Script-mine    │ (1) BUGÜN          │ (2)                │
                    │ MCP vector search  │ Vector → LLM judge │
                    │ 200-500ms          │ 5-15s              │
                    │ Auto AI query      │ Explicit /recall   │
                    ├────────────────────┼────────────────────┤
     Skill-mine     │ (3)                │ (4) MAKS KALİTE    │
                    │ Curated drawers +  │ LLM both ends      │
                    │ fast MCP search    │ Slow but richest   │
                    └────────────────────┴────────────────────┘
```

**Mine-mode** vault başına tek seçimdir (steady-state). **Recall-mode**
per-vault yaml setting, flip edilebilir; MCP server açılışta okur.

---

## 4. Görev 4.2 — Skill-mine + pilot orchestrator

### 4.2.1 `mnemos-mine-llm` skill'i

`skills/mnemos-mine-llm/SKILL.md` (repo canonical, `~/.claude/skills/`'e
junction'lı, refine-transcripts paterniyle).

**Girdi:** Bir refined session `.md` dosyasının path'i + hedef palace root
(`Mnemos-pilot/` gibi).

**Çıktı:** Hedef palace altında bir veya birkaç drawer `.md` dosyası.
Skill dosyaları **doğrudan** yazar — intermediate JSON/validator yok
(kullanıcı kararı, 2026-04-19).

**Drawer formatı** (mevcut palace schema'sıyla uyumlu):

```markdown
---
wing: Mnemos
room: phase1-design
hall: decisions
entities: [skill-mine, pilot-orchestrator]
source_path: Sessions/2026-04-19-phase1-design.md
mined_at: 2026-04-19T10:30:00
---

# Skill-mine pilot orchestrator kararı

> Source: [[Sessions/2026-04-19-phase1-design]]

Kullanıcı 10 session'lık pilot önerisini onayladı. Script-mine ve
skill-mine paralel çalışacak, iki palace üretilecek...
```

**Prompt tasarımı** (skill içinde):
- Refined session .md'yi oku
- Existing palace'ı incele — mevcut wing/room isimlerini topla (tutarlılık
  için)
- Exchange'leri segment'lere böl, her birinin hall'unu (decisions /
  preferences / problems / events / emotional) tespit et
- Her önemli segment için drawer .md üret (frontmatter + H1 + source
  wikilink + prose)
- Entity extract (kişi / proje ayırt et, tags değil — v0.3.2 hygiene
  kurallarına uy)
- Wing canonicalization (v0.3.2 TR diacritic normalize sürüyor)

**Ledger:** `skills/mnemos-mine-llm/state/mined.tsv` — işlenen refined
session path'leri + timestamp + drawer count + palace root. Resume için
(orchestrator yarıda kesilirse).

**Junction:** Refine-skill'deki paternin aynısı. Repo canonical, `~/.claude/
skills/mnemos-mine-llm`'e junction (Windows) veya symlink (Unix).
CONTRIBUTING'deki architectural-line'a eklenir.

### 4.2.2 Orchestrator: `mnemos mine --pilot-llm [N]`

**Yeni modül:** `mnemos/pilot.py`

**Akış:**

1. **Pre-flight:**
   - Vault'taki `Sessions/` dizinini tara, refined session .md'leri listele
   - N (default 10) en yeni'yi al (configurable `--limit`)
   - Pre-flight plan: N session × ~30s skill call + script mine ~30s total
     = tahmini süre
   - Confirm (unless `--yes`)

2. **İki palace ayarla:**
   - `<vault>/Mnemos/` — mevcut (script-mined, palace_root default)
   - `<vault>/Mnemos-pilot/` — yeni, skill-mined hedefi
   - `Mnemos-pilot/` rebuild lock'u `<vault>/.mnemos-pilot.lock.flock`
     — pilot çalışırken ikinci pilot instance başlatılamasın

3. **Script-mine bacağı:**
   - `mnemos mine Sessions/` mevcut davranışla çalışır (paralel değil —
     skill-mine'dan bağımsız, zaten hızlı)

4. **Skill-mine bacağı:**
   - Her session için `claude --print --dangerously-skip-permissions
     --output-format json "/mnemos-mine-llm <session.md> <Mnemos-pilot>"`
   - Paralel 3'lü (refine-hook paterni, `filelock` advisory)
   - Subprocess env'inde `ANTHROPIC_API_KEY` stripped → subscription auth
   - Her çağrının `usage` alanı JSON'dan parse edilir:
     `{input_tokens, output_tokens, cache_read_input_tokens,
       cache_creation_input_tokens}`
   - Token sayaçları aggregated

5. **Skill-mined drawer'ları index'le:**
   - `mnemos mine Mnemos-pilot/ --palace-root Mnemos-pilot` — mevcut
     miner drawer .md'leri okuyup ChromaDB/sqlite-vec index'e yazar
   - Skill zaten semantik iş yaptı; miner sadece embedding + metadata
     parse yapar, pattern classification tekrar koşmaz (yeni flag
     `--skip-classification` eklenecek; drawer frontmatter authoritative)

6. **Pilot rapor üret:**
   - `<vault>/docs/pilots/2026-MM-DD-llm-mine-pilot.md` iskelet
   - Script-mine: N drawers, H halls, E entities, süre X sn, 0 token
   - Skill-mine: N' drawers, H' halls, E' entities, süre Y sn, T total
     tokens (input I, output O, cache R)
   - 3 random session için drawer'ların yan yana diff'i (script tarafı
     vs skill tarafı aynı session'dan ne çıkardı)
   - Rapor sonunda placeholder: *"Run `/mnemos-compare-palaces` to fill
     in the qualitative judgment."*

7. **Orchestrator bitti:** kullanıcıya next step'leri söyle:
   ```
   Pilot complete. Review:
     docs/pilots/2026-04-19-llm-mine-pilot.md

   Next:
     1. /mnemos-compare-palaces           → LLM judgment report
     2. mnemos pilot --accept script      → keep script-mine, recycle Mnemos-pilot/
     3. mnemos pilot --accept skill       → keep skill-mine, move Mnemos-pilot/ to Mnemos/
     4. mnemos pilot --keep-both          → (not recommended — see spec §3)
   ```

### 4.2.3 `mnemos-compare-palaces` skill'i

`skills/mnemos-compare-palaces/SKILL.md`

**Girdi:** iki palace root path'i + pilot rapor iskeleti

**Akış:**
- Her iki palace'tan aynı 10 source session için drawer'ları oku
- Boyut/sayı metrikleri topla (drawer count, hall distribution, entity
  overlap, drawer body length avg)
- 3 örnek session için yan yana analiz:
  - Hangisi daha zengin? (drawer count, semantic coverage)
  - Hangisi daha temiz? (noise, junk drawers, entity garbage)
  - Hall siniflandirması daha tutarlı mı?
  - Drawer body kendi başına okunabiliyor mu?
  - Wikilink'ler doğru mu?
- LLM kendi judgment'ını yazar ama karar kullanıcıya bırakır:
  *"Skill-mine appears to surface 40% more emotional-hall segments but
  also produces 15% more low-confidence drawers. If emotional context
  matters to your recall usage, skill-mine wins; if you want tighter
  deterministic drawer sets, script-mine. You decide."*
- Pilot rapor iskeletini fill-in yapar

**Ledger:** yok — user-invoked one-shot.

### 4.2.4 Token accounting

Claude Code'un `claude --print --output-format json` çıktısı her call
sonrası:
```json
{
  "type": "result",
  "result": "...",
  "usage": {
    "input_tokens": 3240,
    "output_tokens": 1820,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 2100
  }
}
```

Orchestrator her pilot call'u için bu alanı parse eder, aggregated
toplamı rapor'a yazar. Subscription kullanıcıları için "$0" değil
"**abonelik quota** kullanımı" olarak rapor edilir — biz metered
fiyat tahmin etmiyoruz (kullanıcının planını bilmiyoruz). Kullanıcı
isterse şeffaflık için Sonnet 4.6 fiyat şablonu (`$3/M input + $15/M
output`) ile tahmini gösteren `--estimate-cost` flag'i eklenebilir (nice-
to-have, scope içinde değil; implementation kolaysa pilot orchestrator
koyabilir).

### 4.2.5 `mnemos pilot --accept <mode>`

- `--accept script`: `Mnemos-pilot/` → `_recycled/Mnemos-pilot-YYYY-MM-DD/`
- `--accept skill`:
  1. `Mnemos/` → `_recycled/Mnemos-script-YYYY-MM-DD/`
  2. `Mnemos-pilot/` → `Mnemos/`
  3. `mnemos.yaml`'da `mine_mode: skill` yaz
  4. ChromaDB/sqlite-vec index rebuild (yeni drawer'lar güncel palace
     root'u yansıtsın)
- Her ikisi `.mnemos-pending.json`'u günceller, `pilot_completed_at`
  timestamp ile.

---

## 5. Görev 4.3 — Skill-recall

### 5.1 `mnemos-recall` skill'i

`skills/mnemos-recall/SKILL.md`

**Girdi:** Query string (kullanıcı yazar, veya session context'inden
çıkarılır)

**Akış:**

1. **Fast vector filter:** Skill `python -m mnemos.cli search "<query>"
   --limit 50 --format json --vault <v>` subprocess çağırır. Script-recall
   MCP tool'u değil, CLI — skill'in internal call'ı.
2. **LLM judgment:** Top-50 drawer'ın title + first 200 char + metadata'sı
   prompt'a koyulur. LLM sorar: "Hangi 10 drawer gerçekten bu query'ye
   alakalı?"
3. **Full body read:** Seçilen 10 drawer'ın full body'sini oku.
4. **Curate:** 300-500 kelimelik context briefing yaz — wikilink'ler
   kaynak drawer'lara işaret eder, kullanıcı takip edebilir.
5. stdout'a yazdır. Skill user-invoked olduğu için Claude Code session'a
   direkt enjekte olur.

**Latency:** 5-15s (vector search <1s, LLM judgment 3-10s, full read 1s,
curate 1-3s). Kullanıcı explicit bekler.

**Kullanım:**
```
/mnemos-recall "gyp satın alma otomasyonu son durum"
/mnemos-recall "phase1 rerank kararı neydi"
```

### 5.2 SessionStart briefing hook (opt-in)

**Amaç:** Skill-recall modunda çalışan kullanıcı her session açtığında
"son bir haftada ne üzerinde çalıştığın" özetini görsün, explicit
`/mnemos-recall` çağırmak zorunda kalmasın.

**Yeni modül:** `mnemos/recall_briefing.py`

**Akış** (refine-hook paternine paralel):

1. SessionStart hook tetiklenir
2. Wrapper non-blocking background spawn:
   `claude --print --dangerously-skip-permissions --output-format json
   "/mnemos-briefing"`
3. Skill `<vault>/mnemos.yaml`'ın `briefing_projects: [...]` hint'ini
   okur (boşsa son 7 günde aktivite olan wing'leri otomatik seçer)
4. Seçilen wing'ler için son 10-20 drawer'ın title + hall + entities
   listesini oku
5. Son 3 `Sessions/*.md` dosyasının ilk paragraflarını oku (ne üzerinde
   çalışıyordu)
6. LLM 200-300 kelimelik briefing yazar:
   - Aktif projeler: `[[Mnemos]]`, `[[GYP]]`
   - Son 48 saat kararlar: ...
   - Açık meseleler: ...
   - Sırada bekleyen: ...
7. `<vault>/.mnemos-briefing.md` dosyasına yazar (prev → prev-prev rotate)

**Context enjeksiyonu** (tek tasarım seçimi, iki alternatif):

**Alt-A: Stale-ama-fresh model** (önerilen v0.4 için)
- Mevcut SessionStart hook briefing DOSYASI VARSA + fresh (<4h) ise
  `additionalContext` ile enjekte
- Değilse enjekte yok, background regenerate et (sonraki session'da
  hazır olsun)
- 2. session'dan itibaren briefing görünür

**Alt-B: Blocking fresh model** (v0.5'e ertelenebilir)
- SessionStart 10-15s block, güncel briefing her seferinde üret
- Temiz ama latency maliyetli

**v0.4 Alt-A'yı seçiyor.** Refine-hook'un `last_outcome` idle-render
paternine uyar.

**CLI:** `mnemos install-recall-hook` (idempotent, install-hook ile aynı
shape), `mnemos install-recall-hook --uninstall`.

**Skill:** `skills/mnemos-briefing/SKILL.md` (recall skill'inden ayrı —
bu cron-like auto, recall user-invoked).

### 5.3 MCP server `instructions` — recall_mode-aware

Mevcut MCP server (`mnemos/__main__.py` veya `mnemos/server.py`)
`instructions` alanı statik:
> "At the START of every session, call mnemos_wake_up..."

`mnemos.yaml`'dan `recall_mode` okunup dinamik üretilecek:

- `recall_mode: script` (default): mevcut instruction — AI auto-calls
  `mnemos_search` when relevant. Her turn potansiyel.
- `recall_mode: skill`: instruction değişir:
  > "The user prefers skill-based recall. Do NOT call `mnemos_search`
  > unless the user explicitly asks. Session-start briefing is already
  > injected as context; user will invoke `/mnemos-recall` for on-demand
  > queries."

Tool'lar tamamı expose kalır — skill internal olarak search'ü kullanıyor.

---

## 6. Görev 4.5 — `mnemos settings` TUI

**Yeni modül:** `mnemos/settings_tui.py`

**Davranış:**

- Numbered menu (init paterninin devamı, curses değil — platform-agnostic)
- i18n TR+EN (mevcut `mnemos/i18n.py`'a key ekle)
- `mnemos.yaml` canonical store
- Her satır mevcut state + action affordance gösterir
- Reset hook, install hook gibi işler alt-prompt açar
- Windows cp1252 uyumlu (conftest fix'i sürüyor)

**İskelet:**

```
╭────────────────────────────────────────────────────────╮
│  mnemos settings  —  vault: ~/.../kasamd              │
├────────────────────────────────────────────────────────┤
│  1. Backend          chromadb (620 MB · 683 drawers)  │
│  2. Mine mode        script                           │
│  3. Recall mode      script                           │
│  4. Refine hook      ✅ installed                     │
│  5. Recall hook      ❌ not installed                 │
│  6. Statusline       ✅ installed                     │
│  7. Languages        tr, en                           │
│  8. Briefing hint    (auto-detect recent activity)    │
│  9. Vault            ~/.../kasamd   (read-only)       │
├────────────────────────────────────────────────────────┤
│  Press number to change, q to quit.                   │
╰────────────────────────────────────────────────────────╯

> _
```

**Her satırın alt-davranışı:**

| # | Action |
|---|---|
| 1 | Submenu: "migrate to sqlite-vec" / "migrate to chromadb" / "cancel" — `mnemos migrate`'e delegate |
| 2 | "run pilot (10 sessions)" / "switch to skill (no pilot)" / "cancel" |
| 3 | Toggle script ↔ skill + warn "restart Claude Code for MCP to pick up new mode" |
| 4-6 | Install / uninstall / refresh — mevcut install-* komutlarına delegate |
| 7 | Comma-separated edit, yaml valid langs subset |
| 8 | Edit briefing_projects list; default empty = auto-detect |
| 9 | Read-only display |

**Ayrı komutlar** (`mnemos install-hook`, `mnemos migrate`, vb.)
**kaybolmuyor** — settings TUI onların üstünde thin wrapper. CLI
automation script'leri çalışmaya devam eder.

---

## 7. Görev 4.6 — Benchmark

LongMemEval full 500 soru, 4 mod — ama artık **sadece S+S combo'su
için**. Skill-recall kalitatif, benchmark'landırılamaz (her run farklı
LLM judgment; deterministic değil).

**Çalıştırma:**
```bash
mnemos benchmark longmemeval --limit 500 --mode combined
```

**Hedef:** R@5 ≥ **%93** (Phase 0 %90'dan marjinal iyileşme; skill-mine
pilot drawer kalitesini artırabilir ama S+S combo script-mine kullandığı
için esas etki 4.2 drawer hygiene fix'lerinden gelecek).

**Not:** Orijinal Phase 0 spec'inde %95+ hedefti; API-based rerank'in
sağlayacağı +5% boost beklenmişti. Skill-first yaklaşımda rerank S+S
combo'suna dokunmuyor — kullanıcı rerank benefit'ini skill-recall
seçerek alır (benchmark'sız, kalitatif). Hedef bu nedenle %93'e
indirildi. %95 iddiamız kalkar; Phase 1'de yeni iddia: *"%90'ın üstüne
deterministic-ama-iyileşen skor + opsiyonel LLM-driven kalitatif upgrade."*

---

## 8. Görev 4.7 — PyPI release v0.4.0

Standard release rutini (v0.3.x paternleri):

- Version bump `0.3.3 → 0.4.0` (`pyproject.toml` + `mnemos/__init__.py`)
- `CHANGELOG.md` — Phase 1 summary, 4 yeni skill, pilot akışı, settings
  TUI, breaking changes yok
- `STATUS.md` §2 güncel — skill-mine capability, skill-recall capability,
  mnemos settings, briefing hook, pilot orchestrator
- `ROADMAP.md` — 4.2-4.7 checkbox'ları `[x]`
- Wheel + sdist build
- Pre-release inspection (3.10a paterni): wheel'de skill path'leri package-
  data olarak mı ship'leniyor? Skill dosyaları `mnemos/_resources/skills/`
  altında mı? Junction/symlink install script'i CLI `install-skills`
  komutuyla mı?
- Tag `v0.4.0` (annotated), GitHub release (asset'li)
- PyPI upload (kullanıcıya devredilir, standart)

---

## 9. Dosya listesi

**Yeni modüller:**
- `mnemos/pilot.py` — orchestrator
- `mnemos/recall_briefing.py` — SessionStart briefing hook wrapper
- `mnemos/settings_tui.py` — interactive settings panel

**Yeni skill'ler:** (hepsi junction'lı, repo canonical)
- `skills/mnemos-mine-llm/` — SKILL.md + prompt + state ledger dizini
- `skills/mnemos-recall/` — SKILL.md + prompt
- `skills/mnemos-briefing/` — SKILL.md + prompt (auto-invoked by hook)
- `skills/mnemos-compare-palaces/` — SKILL.md + prompt

**Değişen modüller:**
- `mnemos/cli.py` — yeni subcommand'ler: `mine --pilot-llm`, `pilot
  --accept`, `settings`, `install-recall-hook`
- `mnemos/miner.py` — `--skip-classification` flag (skill-mined drawer
  frontmatter'ına güven)
- `mnemos/server.py` (veya `mnemos/__main__.py`) — `instructions`
  dinamik, `recall_mode`'dan okur
- `mnemos/i18n.py` — yeni key'ler (settings TUI, pilot flow, briefing)
- `mnemos/config.py` — yeni yaml alanları: `mine_mode`, `recall_mode`,
  `briefing_projects`

**Yeni test dosyaları:**
- `tests/test_pilot.py` — orchestrator happy path, iki palace
  concurrency, accept logic, rollback on failure
- `tests/test_recall_briefing.py` — hook wrapper, stale file logic,
  blocking-model negative test
- `tests/test_settings_tui.py` — numbered menu navigation, yaml
  roundtrip, submenu delegation
- `tests/test_skill_mine_integration.py` — fake-claude subprocess
  mock (skill çıktısını deterministic simüle et)
- `tests/test_mcp_instructions_mode.py` — recall_mode değişince
  instruction string değişir

---

## 10. Uygulama sırası

| Sıra | Görev | Tahmini süre |
|------|-------|--------------|
| 1 | 4.2.1 mnemos-mine-llm skill — SKILL.md + prompt | 2h |
| 2 | 4.2.2 Orchestrator `pilot.py` + CLI subcommand | 3h |
| 3 | 4.2.3 Compare-palaces skill | 1.5h |
| 4 | 4.2.5 `mnemos pilot --accept` | 1h |
| 5 | Real-vault pilot (author's kasamd, 10 sessions) | 1h (live test) |
| 6 | 4.3.1 mnemos-recall skill | 2h |
| 7 | 4.3.2 briefing hook + `install-recall-hook` | 2.5h |
| 8 | 4.3.3 MCP server instructions mode-aware | 30m |
| 9 | 4.5 Settings TUI | 2.5h |
| 10 | 4.6 Benchmark S+S full 500q | 1h (automated, +2h verify) |
| 11 | 4.7 Release prep + pilot-in-pilot (clean-vault) | 2h |

Toplam **~19h** aktif iş, +2-3 gün pilot/validation sürünme. Phase 0
(v0.2) ~40h, Phase 1 yarısı — skill-first yaklaşım paket mühendisliğini
kısaltıyor (API client, retry logic, rate limiter, cost estimator,
optional extra paketleme yok).

---

## 11. Başarı kriterleri

- [ ] `mnemos-mine-llm` skill 10 sessionluk pilot'u başarıyla tamamlıyor
  (ledger resume, paralel-3 spawn, token accounting rapor'a geçiyor)
- [ ] `mnemos mine --pilot-llm` iki palace yan yana üretiyor, pilot rapor
  iskeleti `docs/pilots/`'a yazılıyor
- [ ] `/mnemos-compare-palaces` LLM judgment raporu + 3 yan yana sample
  ile iskeleti tamamlıyor
- [ ] `mnemos pilot --accept skill` kaybeden palace'ı `_recycled/`'a
  taşıyor, yaml update, index rebuild atomic
- [ ] `/mnemos-recall "<query>"` 5-15s içinde curated 300-500 kelimelik
  context döndürüyor, wikilink'ler valid
- [ ] SessionStart briefing hook fresh `.mnemos-briefing.md` <4h ise
  `additionalContext` enjekte ediyor, değilse sessiz + background
  regenerate
- [ ] `mnemos settings` TUI 8 satırlık menüyü açıyor, her satır altında
  doğru alt-aksiyonu delegate ediyor, yaml roundtrip temiz
- [ ] Recall mode yaml'dan değişince MCP server instructions dinamik
  güncelleniyor (Claude Code restart'tan sonra AI auto-query davranışı
  değişiyor)
- [ ] LongMemEval 500q S+S combo'suda Recall@5 ≥ **%93**
- [ ] Mevcut 463 test kırılmadı, yeni ~50 test eklendi hepsi yeşil
- [ ] Clean-vault pilot (throwaway) tam flow yeşil: init → mine →
  pilot-llm → compare → accept → recall → briefing-hook
- [ ] PyPI v0.4.0 wheel'de tüm skill path'leri + yeni modüller mevcut
  (3.10a paket-data regressonu tekrar etmedi)

---

## 12. Açık sorular / ileride bakılacak

1. **Briefing hook freshness window** — 4 saat uygun mu? Pilot'ta
   ölçülecek. Çok kısa ise her session regenerate, çok uzun ise
   stale context.
2. **Skill prompt versiyonlama** — prompt değişirse mevcut skill-mined
   drawer'lar eski prompt sürümünden. Yeni drawer'lar yeni prompt'tan
   gelir; versioning gerek mi? İlk sürüm için pas geç, v0.4.1'de bak.
3. **Palace merge opsiyonu** — pilot'ta beğenildiği halde "keep both"
   isteği gelirse? Spec dışı ama implementation kolaysa
   `mnemos pilot --keep-both` flag'i konabilir; UI level'da not
   önerilen.
4. **Token cost estimator flag** — Sonnet 4.6 fiyat şablonu + estimated
   cost. Nice-to-have. Hızlıca eklenebilir; release öncesi karar.
5. **Briefing skill input size** — son 10-20 drawer + 3 session paragrafı
   ~5K token. Briefing output 300-500 kelime ~700 token. Skill call başına
   ~6K token. Session başına bir kez. Kabul edilebilir; ama briefing sık
   regenerate oluyorsa cumulative cost visible olmalı — statusline'a
   briefing meta gösterilsin mi?

---

**Doc owner:** Tugra Demirors
**Review:** self (single-maintainer project)
**Next:** bu spec onaylandı; implementasyon 4.2'den başlıyor.
