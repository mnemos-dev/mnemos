# Mnemos Roadmap

**Single source of truth.** Implement ettikçe bu dosyayı güncelle, commit et.
Eski `docs/specs/2026-04-*` ve `docs/plans/2026-04-*` dosyaları historical
archive; burada çelişki olursa bu dosya geçerlidir.

**Son güncelleme:** 2026-04-15

---

## Sürüm durumu

| Sürüm | Başlık | Durum | PyPI |
|---|---|---|---|
| v0.1.0 | First Breath | ✅ | ✅ |
| v0.2.0 | Full Memory (= Phase 0 Foundation) | ✅ | ✅ |
| **v0.3.0** | **First-Run Experience** | **🔄 in progress** | — |
| v0.4.0 | AI Boost (= Phase 1) | ⏸ next | — |
| v0.5.0 | Automation (= Phase 2) | ⏸ | — |
| v0.6.0 | Community & Ecosystem | ⏸ | — |

---

## v0.1.0 — First Breath ✅ *(2026-04-12)*

- [x] Core MCP tools: search, add, mine, status
- [x] Regex-only mining (LLM optional)
- [x] ChromaDB + Obsidian dual storage
- [x] File watcher (sync)
- [x] CLI: init, mine, search, status
- [x] TR + EN language support
- [x] PyPI publish (mnemos-dev)
- [x] GitHub org (mnemos-dev)

## v0.2.0 — Full Memory / Phase 0 Foundation ✅ *(2026-04-13 → 04-14)*

Amaç: API kullanmadan MemPalace seviyesinde recall (%96+) yakalamak.

- [x] Second wave tools: recall, graph, timeline, wake_up
- [x] L0-L3 memory stack
- [x] Knowledge graph (temporal triples, SQLite)
- [x] Dual ChromaDB collection (raw + mined), RRF merge
- [x] Metadata filter `$in` (çoklu wing/room)
- [x] 5 conversation format normalizer (Claude Code JSONL, Claude.ai, ChatGPT, Slack, plain text)
- [x] Exchange-pair chunking (soru+cevap birlikte)
- [x] Room detection — 72+ folder/keyword pattern, 13 kategori
- [x] Heuristic entity detection (person/project)
- [x] 172 marker (87 EN + 85 TR) — 4 hall (decisions/preferences/problems/events)
- [x] Scoring + disambiguation (min_confidence=0.3, problem→milestone)
- [x] Prose extraction (kod satırı filtreleme)
- [x] LongMemEval benchmark harness
- [x] `_recycled` soft-delete mekanizması
- [x] sqlite-vec alternatif backend (cosine score)
- [x] Case-insensitive wing resolution
- [x] Bulk indexing API (10-25x hızlı mining)

İlk benchmark: 10 soruda %70 Recall@5 (Phase 1 hedefi %95+).

---

## v0.3.0 — First-Run Experience 🔄 *(başladı 2026-04-15)*

**Sorun:** Phase 0 teknik olarak hazır ama external user için "indir →
çalıştır → faydalan" yolu yok. v0.3 bu kapıyı açar.

**Ana karar — refinement selektif:**

| Kaynak | Refine? |
|---|---|
| JSONL transcripts, email export, PDF | EVET (noisy/raw) |
| Frontmatter'lı curated `.md` (memory, Sessions, Topics) | HAYIR |

Refinement = Claude Code oturumunda çalışan user-triggered skill. mnemos
hiçbir LLM API'sı çağırmaz. Maliyet sıfır, bağımlılık sıfır.

### Görevler

- [x] **3.1 refine-transcripts skill** *(commit `a74c10f`, 2026-04-15)*
  - `skills/mnemos-refine-transcripts/SKILL.md` + canonical prompt referansı
  - Ledger (`state/processed.tsv`) — OK+SKIP kayıtlı, resume çalışır
  - Subagent filtresi default ON, `--include-subagents` opt-in
  - 0-turn fast-path, collision guard, pilot protokolü (>5 → ilk 5 sonrası onay)
  - 5 transcript pilot: 2 OK (GYP GTIP/TPAO kota), 3 SKIP
  - Junction kurulumu (`~/.claude/skills/` → repo) zero-drift

- [x] **3.2 README reposition** *(commit `0fd64fc`, 2026-04-15)*
  - Hero: "Turn your Claude Code history into a searchable memory palace"
  - Quick Start'ta skill install (mklink/ln -s) + pilot flow
  - "Why Not Just Raw Transcripts?" karşılaştırma tablosu
  - Roadmap bölümü v0.3=First-Run

- [ ] **3.3 `.mnemos-pending.json` schema** *(30 dk)*
  Vault kökünde tek JSON. Schema:
  ```json
  {
    "version": 1,
    "sources": [
      {
        "id": "claude-code-jsonl",
        "path": "~/.claude/projects",
        "kind": "raw-jsonl",
        "status": "in-progress",   // pending|in-progress|done|skipped-by-user|error
        "discovered_at": "ISO-8601",
        "total": 244,
        "processed": 5,
        "last_action": "pilot-accepted"
      }
    ]
  }
  ```
  Dosyalar: `mnemos/pending.py` (yeni) — read/write/append API. Tüm
  `init` + `import` komutları bu modülü kullanır.

- [ ] **3.4 `mnemos init` wizard genişletme** *(2-3h, 3.3'ten sonra)*
  Mevcut init sadece vault scaffold yapıyor. Yeni akış:
  1. **Discover** — sessizce tara: `~/.claude/projects/` (JSONL), yerel
     `Sessions/`, `memory/`, Obsidian `Topics/`
  2. **Classify** — her kaynak curated mı raw mı işaretle
     - Frontmatter'lı `.md` → curated → direkt mine
     - JSONL/email/PDF → raw → önce refine skill
  3. **Sun** — kaynakları tek tek, topluca değil
  4. **Raw pilot protokolü** — 5'li pilot → user review → full batch
  5. **Resume** — her karar `.mnemos-pending.json`'a yazılır

  Dosyalar: `mnemos/cli.py` (`cmd_init` genişletme), yeni
  `mnemos/onboarding.py` discover/classify.

- [ ] **3.5 `mnemos import <source>` subcommand ailesi** *(1-2h, 3.3'ten sonra)*
  Init'ten sonra kaynak ekleme:
  - `mnemos import claude-code [--projects-dir PATH] [--limit N] [--refine]`
    — refine skill prompt'unu kullanıcıya verir (mnemos LLM çağırmaz) +
    `mnemos mine Sessions/` orchestrate
  - `mnemos import chatgpt <export.json>`
  - `mnemos import slack <export.json>`
  - `mnemos import markdown <dir>`
  - `mnemos import memory <dir>` (Claude memory klasörleri)
  Her komut `.mnemos-pending.json`'u günceller.
  Dosyalar: `mnemos/cli.py` (argparse subparser), yeni
  `mnemos/importers/` modülü.

- [ ] **3.6 CONTRIBUTING.md** *(30 dk, bağımsız)*
  Git workflow, branch naming, test çalıştırma, skill geliştirme, nasıl
  yeni language/marker ekleneceği.

- [ ] **3.7 New-user simülasyonu pilot** *(1h, tüm yukarıdakilerden sonra)*
  Temiz throwaway klasörde:
  1. Yeni vault klasörü oluştur
  2. `pip install -e .` dev-install
  3. Junction skill kur
  4. `mnemos init` wizard baştan sona
  5. 5 JSONL pilot → Sessions/
  6. `mnemos mine Sessions/` → search kalite
  7. Patlayan her yeri not et, düzelt
  8. Dokümantasyon boşluklarını README/CONTRIBUTING'e ekle

- [ ] **3.8 PyPI release v0.3.0**
  - `pyproject.toml` version bump
  - `python -m build` + `twine upload`
  - GitHub release notes + tag

### Başarı kriterleri

- [ ] External user, README'deki 5 adımı izleyerek clean vault'ta çalışır mnemos kurabiliyor
- [ ] `mnemos init` 244 JSONL transcript'i keşfedip pilot + import önerebiliyor
- [ ] `.mnemos-pending.json` resume çalışıyor — oturum kesilirse baştan başlamak gerekmiyor
- [ ] `mnemos import` 5 formatın hepsini destekliyor
- [ ] Skill install (junction/symlink) dokümante + test edilmiş

---

## v0.4.0 — AI Boost / Phase 1 ⏸

**Hedef:** Recall@5 ≥ %95 (Phase 0 baseline'ı %70 → hedef %100).
Claude API opsiyonel; `mnemos-dev[llm]` extra'ya bağlı.

### Görevler

- [ ] **4.1 Phase 1 design spec yaz** *(1h)*
  `docs/specs/YYYY-MM-DD-phase1-ai-boost-design.md` — Phase 0 spec formatında
- [ ] **4.2 LLM mining** *(3-4h)*
  - Claude API regex'in yakaladıklarını doğrular + kaçırdıklarını yakalar
  - **Emotional hall eklenir** (Phase 0'da false-positive riski nedeniyle ertelendi)
  - `mnemos mine Sessions/ --llm` mevcut flag'in arkasında
- [ ] **4.3 LLM reranking** *(2h)*
  - Search top-50 → Claude → top-10 precision boost
  - `mnemos_search` tool'una `rerank: bool` parametresi
- [ ] **4.4 Contradiction detection** *(2-3h)*
  - Yeni memory mevcut memory'lerle çelişiyor mu? (örn. "X kullanıyoruz" vs
    yeni "Y'ye geçtik" → eski outdated işaretlenir, `_recycled`'a taşınır)
  - `mnemos_add` sırasında otomatik check
- [ ] **4.5 Benchmark tekrar** *(1h)*
  - LongMemEval full 500 soru, 4 mod
  - Hedef: Recall@5 ≥ %95, Recall@10 ≥ %97
- [ ] **4.6 PyPI release v0.4.0**

---

## v0.5.0 — Automation / Phase 2 ⏸

**Hedef:** Mnemos kendi kendine sağlıklı kalır — kullanıcı müdahalesi
asgariye iner.

### Görevler

- [ ] **5.1 Phase 2 design spec yaz** *(1h)*
  `docs/specs/YYYY-MM-DD-phase2-automation-design.md`
- [ ] **5.2 Session hooks** *(2-3h)*
  - Claude Code session bittiğinde otomatik mine
  - `settings.json` hook'u: `SessionEnd → mnemos mine --incremental`
- [ ] **5.3 Memory lifecycle / decay** *(2h)*
  - Eski, hiç aranmamış, çelişki-işaretli memory'ler zaman içinde fade out
  - `mnemos prune --dry-run` komutu
- [ ] **5.4 Knowledge graph deepening** *(3-4h)*
  - Cross-reference: "bu memory X projesinde, X projesi Y wing'inde, Y wing
    son Z günde şu kararları aldı" gibi dolaylı sorgular
  - `mnemos_graph` tool genişletme
- [ ] **5.5 PyPI release v0.5.0**

---

## v0.6.0 — Community & Ecosystem ⏸

**Hedef:** Teknik-dışı adoption driver'ları — dil çeşitliği, UI, marketing.

### Görevler

- [ ] **6.1 Ek dil marker setleri** *(1-2h her biri)*
  de, es, fr, ja — her dil için ~80 marker, mevcut EN/TR formatında
- [ ] **6.2 Obsidian plugin** *(~1-2 gün)*
  TypeScript, in-vault UI — memory browser, timeline view, graph view
  (Obsidian canvas entegrasyonu)
- [ ] **6.3 Demo video + launch blog post** *(~1 gün)*
  YouTube 3-5 dk demo + blog (Medium / Dev.to)
- [ ] **6.4 Contributor onboarding polish**
  Good-first-issue etiketleri, issue templates, PR templates
- [ ] **6.5 PyPI release v0.6.0**

---

## Historical archive

Delivered sürümlerin design/plan artifact'ları `docs/archive/` altında.
Aktif plan bu dosyadır; arşiv sadece tasarım rationale için referans.
İndeks: [`docs/archive/README.md`](archive/README.md).

---

## Çalışma şekli

1. Görev başlamadan önce bu dosyadaki checkbox'ı `[ ] → [~]` (in progress) yap
2. Görev bitince `[~] → [x]` + commit hash'i ekle (`*(commit <hash>, <tarih>)*`)
3. Scope değişirse ilgili satırı güncelle, gerekirse yeni alt-görev ekle
4. Yeni phase design spec'leri `docs/specs/` altında; bu ROADMAP'te sadece özet
