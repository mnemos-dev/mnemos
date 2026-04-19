# Mnemos Roadmap

**Single source of truth.** Implement ettikçe bu dosyayı güncelle, commit et.
Eski `docs/specs/2026-04-*` ve `docs/plans/2026-04-*` dosyaları historical
archive; burada çelişki olursa bu dosya geçerlidir.

**Son güncelleme:** 2026-04-19 (4.2.1-9 ship, v0.4.2-alpha batch hand-off)

---

## Sürüm durumu

| Sürüm | Başlık | Durum | PyPI |
|---|---|---|---|
| v0.1.0 | First Breath | ✅ | ✅ |
| v0.2.0 | Full Memory (= Phase 0 Foundation) | ✅ | ✅ |
| v0.3.0 | First-Run Experience | ✅ | ✅ |
| v0.3.1 | Backend UX (keşif + migrate + recovery) | ✅ | ✅ |
| v0.3.2 | Palace Hygiene (pipeline fixes + atomic rebuild) | ✅ | ✅ |
| v0.3.3 | Post-v0.3.2 cleanup (migrate rollback+lock, score parity, slow-tests) | ✅ | ✅ |
| **v0.4.0** | **AI Boost / Phase 1 — skill-first (mine + recall + pilot + settings TUI)** | **🔄 spec done** | — |
| v0.5.0 | Automation / Phase 2 (+ contradiction hygiene v0.4'ten) | ⏸ | — |
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

Benchmark: 10 soruda **%90 Recall@5** (Phase 1 hedefi %95+).
İlk run (2026-04-13) optimizasyon öncesi %70 idi; chunk 3000→800 + RRF
fetch ×3 + source_path metadata ile aynı gün %90'a çıktı. 2026-04-17'de
sqlite-vec ve ChromaDB backend'leri ayrı ayrı koşuldu — dördüncü ondalığa
kadar aynı sayılar (R@5=0.90, NDCG@10=0.7393, 8027 drawer). Backend seçimi
recall'u etkilemiyor; Phase 1 mining pipeline'ını hedefleyecek.

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

- [x] **3.3 `.mnemos-pending.json` schema** *(commit `0783ba2`, 2026-04-15)*
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

  **Delivered:** `mnemos/pending.py` + `tests/test_pending.py` (10 tests,
  all passing). Public API: `PendingSource`, `PendingState`, `load()`,
  `save()` (atomic via tmp+replace), `upsert_source()`, `pending_path()`.
  Status enum validated in `__post_init__`; unknown schema version raises.

- [x] **3.4a `mnemos init` onboarding core** *(commit `fc17751`, 2026-04-15)*
  Mevcut init sadece vault scaffold yapıyor. Yeni 5-faz akış (kullanıcı spec'i, 2026-04-15):

  1. **Faz 1 — Tanıtım** — Mnemos ne, nasıl çalışıyor; ilk run + her run
  2. **Faz 2 — Discovery** — sessizce tara, dosya sayısı + tahmini süre raporla
  3. **Faz 3 — Karar** — `[A]ll / [S]elective / [L]ater` üçlü seçim
  4. **Faz 4 — İşleme** — resumable, her dosya sonrası pending.json güncelle
  5. **Faz 5 — Hook aktivasyonu** — *(3.7'de gerçekleşir; 3.4a'da placeholder)*

  3.4a scope (ilk parça): **JSONL + curated-md** kaynakları için tüm 5 faz.
  Diğer formatlar (ChatGPT/Slack/Claude.ai/Gemini) 3.5'te discovery'ye eklenir.
  i18n (TR+EN) 3.4b'ye taşındı. Hook gerçek aktivasyonu 3.7'de.

  Dosyalar: `mnemos/cli.py` (`cmd_init` genişletme), yeni
  `mnemos/onboarding.py` discover/classify/process.

- [x] **3.4b CLI i18n altyapısı + TR+EN onboarding metinleri** *(commit `0ddaae9`, 2026-04-15)*
  Faz 1 tanıtım ve Faz 3 prompt'ları için locale-aware string sistemi.
  `mnemos.yaml`'daki `languages` listesi ilk dile düşer; default `en`.

  **Delivered:** `mnemos/i18n.py` (dict-based, 17 keys × {en, tr}),
  `t(key, lang, **fmt)` + `resolve_lang(cfg)`. CLI'da `cmd_init` →
  `_print_intro/_run_onboarding/_apply_decision/_mine_and_record/`
  `_print_hook_placeholder` hepsi `lang` parametresi alır.
  Windows cp1252 console fix: `main()` başında `sys.stdout.reconfigure(
  encoding='utf-8', errors='replace')`. 14 yeni test, hepsi yeşil.

- [x] **3.5 `mnemos import <source>` subcommand ailesi** *(commit `d9e97a9`, 2026-04-15)*
  Discovery'yi ChatGPT/Slack/Claude.ai/Gemini formatlarına genişletir
  (`onboarding.py`'a eklenir). `mnemos init [L]` seçen kullanıcı için
  parça parça ilerleme yolu.
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

- [x] **3.6 CONTRIBUTING.md** *(commit `4eef132`, 2026-04-15)*
  Git workflow, branch naming, test çalıştırma, skill geliştirme, nasıl
  yeni language/marker ekleneceği. Plus: architectural "no-cross" lines
  (Obsidian master, no LLM in mnemos itself, dual-collection separation,
  junction/symlink drift forbidden).

- [x] **3.7 SessionStart auto-refine hook** *(commit `725d569` + hardening `96aa07f`, 2026-04-16)*
  SessionStart hook + `scripts/auto_refine_hook.py` wrapper. Hook komutu:
  `python <script> --vault <path>` (Windows için forward slash yol, no
  `cmd /c` wrapper). Script `--vault` arg'ı veya `MNEMOS_VAULT` env'i kabul
  eder. Background: son 3 JSONL için `claude --print --dangerously-skip-permissions
  "/mnemos-refine-transcripts <path>"` (detached, `filelock`'lu, `ANTHROPIC_API_KEY`
  subprocess env'inden çıkarılır → subscription auth). Sonra `python -m
  mnemos.cli --vault <v> mine <v>/Sessions`. Statusline `.mnemos-hook-status.json`'dan
  canlı okur; haftalık backlog reminder `additionalContext`'le AI'a iletilir.
  Subagent JSONL'leri (`/subagents/`) picker'da filtrelenir. `mnemos install-hook`
  idempotent, settings.json'u yedekler, entry'yi `_managed_by: mnemos-auto-refine`
  field'ıyla tanımlar. `mnemos init` son fazı hook'u kullanıcı onayıyla kurar.
  Gerçek kullanımda doğrulandı: kullanıcının kasamd vault'unda 6 session
  JSONL otomatik refine edildi + mine tamamlandı, 0 API credit harcandı.

  **Pilot'ta düzeltilen bug zinciri:**
  - `725d569` — mine komutu `python -m mnemos` MCP server'ı başlatıyordu → `python -m mnemos.cli` + `--vault`; subagent JSONL filter; Windows `CREATE_NO_WINDOW`
  - `512e3dd` — marker `# mnemos-auto-refine\n<cmd>` formatı cmd.exe'de fail → `_managed_by` sibling field
  - `138a4cf` — `cmd /c` içindeki nested `\"path\"` cmd.exe quote stripping'iyle mangling → inner quotes çıkarıldı
  - `4ad8505` — `claude --print` env'deki `ANTHROPIC_API_KEY` yüzünden API quota kullanıyordu → subprocess env'inde strip → subscription auth
  - `47f58af` — `cmd /c` wrapper Claude Code dispatch'iyle interactive cmd başlatıyordu → direkt `python <script> --vault <path>` çağrısı, shell wrapper yok
  - `96aa07f` — Claude Code Windows hook dispatch'i backslash escape mangling yapıyordu (`\P\m\s` yeniyor) → forward slash normalization

  **Canonical docs:**
  - Spec: [`docs/specs/2026-04-15-v0.3-task-3.7-auto-refine-hook-design.md`](specs/2026-04-15-v0.3-task-3.7-auto-refine-hook-design.md)
  - Plan + pilot outcomes: [`docs/plans/2026-04-15-v0.3-task-3.7-auto-refine-hook-implementation.md`](plans/2026-04-15-v0.3-task-3.7-auto-refine-hook-implementation.md)

- [x] **3.7c Statusline UX + auto-refine davranış düzeltmeleri** *(commit `ef69170`, 2026-04-16)*

  **Sorun (3.7 canlı testinden 5 kök neden):**
  1. **Yıkıcı `busy` yazısı (asıl bug)** — `auto_refine.run()` lock'u alamayınca
     `phase=busy` yazıyor; bu paylaşılan status dosyasında lock'u tutan
     worker'ın `refining 2/3` yazısının üzerine biniyor. Statusline flicker:
     `refining → busy → refining → busy → idle → busy → idle`. Kullanıcı her
     subagent dispatch'inde flicker görüyor.
  2. **Subagent SessionStart fire'lıyor** — `matcher: ""` her event'te tetikleniyor,
     subagent kick'leri dahil. Her Agent dispatch'i (Explore, Plan, vb.) yeni bg
     worker spawn ediyor → çoğu zaman lock fail → `busy` yazıyor.
  3. **İş yokken bile mining yapılıyor** — `picked=[]` olsa bile bg `mnemos mine
     Sessions/` çalıştırıyor (3-5 sn lock tutuyor). Boş subagent dispatch'leri
     bile contention yaratıyor.
  4. **`phase=idle` 30s TTL Git Bash'te kırık olabilir** — `date -d "$updated_at"`
     ISO offset parse'ı bazı ortamlarda fail; fallback diff=0 → "30s sonra sessiz"
     hiç tetiklenmez. Spec'in istediği "Xm ago, N notes" mesajı için `last_outcome`
     + `last_finished_at` alanları gerekli.
  5. **`phase=starting` snapshot'ı yanıltıcı** — wrapper `starting 0m1s` yazıp
     1-2s sonra bg `refining` yazıyor; ilk render `starting`'de takılı kalıyor
     gibi görünüyor.

  **Çözüm (davranış + kozmetik):**
  - `mnemos/auto_refine.py`:
    - `run()` lock alamazsa **status dosyasına dokunmadan sessizce çık** (lock
      holder zaten file'ı güncel tutuyor; yıkıcı `busy` yazısı bug #1'i giderir)
    - `_run_locked()` `picked=[]` ise `mnemos mine` çağrısını **atla**
      (gereksiz lock-holding ve CPU). Reminder marking yine yapılır.
    - `write_status`'a `last_outcome` (`ok` / `noop`) + `last_finished_at`
      optional alanları (idle'a son round'un meta-bilgisini iletmek için)
  - `scripts/auto_refine_hook.py`:
    - **Subagent filter**: hook stdin JSON'unda `transcript_path` `/subagents/`
      içeriyorsa anında `exit 0` (bg spawn yok, status write yok). #2 fix.
    - `picked=[]` ve `reminder=False` ise wrapper **status dosyasına yazmadan
      ve bg spawn etmeden** çık (boş dispatch'lerde ekran sessiz kalır)
    - `picked>0` durumunda `phase=starting` yerine direkt `phase=refining,
      current=0, total=N` yaz (#5 fix)
  - `scripts/statusline_snippet.{sh,cmd}`:
    - idle TTL 30s → 600s (10 dk)
    - idle render: `last_outcome` + `last_finished_at` varsa
      `mnemos: last refine Xm ago · N notes · OK` formatı
    - `busy` mesajı: `mnemos: other session active` (geriye dönük; yeni
      kodda zaten yazılmıyor ama eski status dosyaları için)

  **Dosyalar:**
  - `mnemos/auto_refine.py` — lock-silent, skip-empty-mining, last_outcome
  - `scripts/auto_refine_hook.py` — stdin JSON parse, subagent filter, no-op skip,
    refining-without-starting
  - `scripts/statusline_snippet.{sh,cmd}` — TTL + idle format + busy wording
  - `tests/test_auto_refine.py` — lock-fail silent, skip-mining, last_outcome
  - `tests/test_auto_refine_hook_script.py` — subagent skip, no-op skip
  - `docs/specs/2026-04-15-v0.3-task-3.7-auto-refine-hook-design.md` — §5.1 güncel

- [x] **3.7d Mid-conversation re-fire'ı durdurma** *(commit `d6cbeed`, 2026-04-16)*

  **Sorun:** 3.7c subagent contention'ı kapattı ama hook hâlâ tek konuşma
  içinde defalarca tetikleniyor. Hook log: 3-5 refine round / saat.
  İki kalıntı kök neden:
  1. **Otomatik compaction `source=compact` ile SessionStart fire'lıyor.**
     Bu mid-conversation event — transcript daha bitmedi, refine etmek
     hem gereksiz hem de ledger'a "OK" olarak yazıp kalanı sonsuza
     kadar gözden kaçırıyor. Sadece "yeni session" semantiği taşıyan
     eventler refine etmeli (`startup`, `resume`, `clear`).
  2. **In-progress conversation'ın kendi JSONL'ı picker'a düşüyor.**
     `pick_recent_jsonls` mtime'a göre sıralıyor → en yeni dosya genelde
     bu konuşmanın canlı transcript'i. Refine edip ledger'a yazınca
     conversation'ın geri kalanı asla mine edilmiyor. Hook input'taki
     `transcript_path` zaten bunu söylüyor; picker'a "exclude" olarak
     iletilmeli.

  **Çözüm:**
  - `mnemos/auto_refine.py` — `pick_recent_jsonls`'a `exclude: set[str] | None`
    parametresi ekle. Listedeki path'leri es geç (str-normalize ile).
    `compute_backlog`'da exclude kullanmıyoruz — kullanıcı "hâlâ X dosya bekliyor"
    bilgisini görmek istiyor.
  - `scripts/auto_refine_hook.py`:
    - **Source whitelist**: hook stdin'inde `source` `compact` (veya gelecekteki
      ephemeral source'lar) ise anında `exit 0`. Whitelist: `{"", "startup",
      "resume", "clear"}`. Bilinmeyen source'lar default-skip (forward-compat
      için kasıtlı; yeni bir Claude Code event'i çıkarsa istemediğimiz davranışı
      önler).
    - `transcript_path`'i `pick_recent_jsonls(exclude={...})` olarak ilet.
  - **Ek temizlik**: `~/.claude/settings.json`'da hâlâ duran eski
    `mnemos-session-mine.py` SessionStart entry'si (mnemos-auto-refine ile
    overlap'lı, raw mine yapıyor — yeni refine flow'undan beri redundant).
    settings.json'dan kaldırılır + ilgili `~/.claude/hooks/mnemos-*.{py,json,log,lock}`
    dosyaları silinir (kullanıcı onayıyla).

  **Dosyalar:**
  - `mnemos/auto_refine.py` — `pick_recent_jsonls(exclude)` param
  - `scripts/auto_refine_hook.py` — source whitelist, exclude self-transcript
  - `tests/test_auto_refine.py` — exclude param testleri
  - `tests/test_auto_refine_hook_script.py` — source filter, self-exclude integration
  - `~/.claude/settings.json` — legacy SessionStart entry remove (manuel, backup ile)

- [x] **3.7b `mnemos install-statusline` CLI** *(commit `15a21fa`, 2026-04-16)*

  **Sorun:** 3.7 hook'u `<vault>/.mnemos-hook-status.json` yazıyor + repo
  `scripts/statusline_snippet.{sh,cmd}` ship'liyor ama kullanıcının onları
  manuel olarak kendi `statusline-command.sh`'ine eklemesi gerekiyor.
  Otomatize edilmeden "herkes göremez" → otomatik feedback yok.

  **Çözüm:** `install-hook` deseninde yeni bir komut. Akış:
  1. `~/.claude/settings.json`'daki `statusLine.command` field'ını oku.
  2. Eğer mevcut bir statusline script'i varsa (`bash <path>` formatında):
     - O script'in sonuna idempotent şekilde 3 satır ekle:
       ```bash
       # --- mnemos auto-refine statusline (managed by mnemos install-statusline) ---
       export MNEMOS_VAULT="<resolved-vault>"
       source "<repo>/scripts/statusline_snippet.sh"
       ```
     - "managed by" marker ile re-run'da skip et.
  3. Eğer hiç statusline yoksa:
     - `~/.claude/mnemos-statusline.sh` oluştur (sadece bizim snippet'i çağırır).
     - `settings.json`'a `statusLine: {type: "command", command: "bash ~/.claude/mnemos-statusline.sh"}` ekle.
  4. Yedek: `settings.json` ve hedef script için `.bak-YYYY-MM-DD` (install-hook gibi).
  5. `--uninstall` opsiyonu: snippet bloğunu marker'la bul + sil; ayrı script
     oluşturulmuşsa onu sil ve `statusLine` config'i kaldır.

  **Dosyalar:**
  - `mnemos/install_statusline.py` (yeni) — pure mantık, test edilebilir
  - `mnemos/cli.py` — `install-statusline` subparser + handler
  - `tests/test_install_statusline.py` — varolan script'e ekleme,
    sıfırdan oluşturma, idempotency, uninstall, settings.json preserve
  - `mnemos init` opsiyonel: hook prompt'tan sonra "statusline da kurayım
    mı? [Y/n]" prompt'u (i18n: `statusline_install_prompt/done/declined`)

  **Kabul kriteri:**
  - Mevcut statusline'ı olan kullanıcı: `install-statusline` çalıştırır →
    sonraki Claude Code session'da chatbox altında auto-refine progress
    görünür, tüm önceki statusline davranışı korunur.
  - Statusline'ı olmayan kullanıcı: `install-statusline` minimal bir
    statusline kurar, sadece mnemos progress satırı gösterir.
  - Re-run no-op (already-installed status).

- [x] **3.8 session-memory skill deprecation** *(commit `77f1b78`, 2026-04-16)*
  Eski `~/.claude/skills/session-memory/` (manuel SAVE-on-keyword skill) +
  `~/.claude/hooks/mnemos-session-mine.py` (raw-transcript miner) artık
  gereksiz — refine-transcripts skill her SessionStart'ta aynı bilgiyi
  daha kapsamlı + tool-noise'sız üretiyor.

  **Delivered:**
  - README'ye `### Migrating from older session-memory setups`
    bölümü eklendi: hangi dosyaların silinebileceği + nasıl
    `~/.claude/settings.json`'dan eski SessionStart entry'sinin
    çıkarılacağı (managed-by marker'ına dikkat çekildi).
  - CONTRIBUTING'in SessionStart hook bölümüne `#### Legacy hooks early
    adopters may still have` alt-başlığı eklendi (kontribütör
    perspektifi: bu hook'ları repo'ya geri ekleme).
  - README roadmap satırı güncel: 3.7b/3.7c/3.7d/3.8 deliveredlistesinde.
  - Yazarın kendi `~/.claude/settings.json`'ından legacy entry zaten
    3.7d kapsamında kaldırıldı; ilgili 4 dosya silindi (kullanıcı
    onayıyla). External user'lar için talimat README'de.

- [x] **3.9 New-user simülasyonu pilot** *(commit `d65384f`, 2026-04-16)*
  Temiz throwaway vault'ta (`C:/Temp/mnemos-pilot-2026-04-16/`) +
  isolated fake HOME'da (`C:/Temp/mnemos-pilot-home-2026-04-16/`)
  README'nin tüm onboarding flow'u sıfırdan koşturuldu:

  - **Init wizard** (piped stdin: `en\n\nA\nn\nn`) → `mnemos.yaml`,
    `Mnemos/` palace, `.mnemos-pending.json`. Discovery 341 JSONL +
    1 curated `.md` buldu, [A]ll seçimi curated'i mine etti
    (8 drawer + 24 entity, wing `pilot-vault-test` frontmatter'dan).
  - **Search + status + re-mine** (`files_scanned: 0, skipped: 1`) → all green.
  - **install-hook** & **install-statusline** isolated HOME'a karşı:
    install / re-run → `already-installed` / `--uninstall` → temiz
    cleanup. Her ikisi `.bak-2026-04-16` backup üretti.

  **Pilot bug**: `cmd_search` formatter `r.get("wing")` okuyordu;
  drawer'lar `metadata.wing`'de — tüm CLI search çıktısı `wing=?`
  gösteriyordu. Fix: `r.get("metadata") or {}`'tan oku, eski
  index'ler için `?` fallback. Yeni: `tests/test_cli_search.py`
  (2 test). Pilot raporu: [`docs/pilots/2026-04-16-new-user-pilot.md`](pilots/2026-04-16-new-user-pilot.md).

  **Pilot etmediklerimiz** (sebepleriyle pilot raporunda):
  PyPI install (3.10 bekliyor), canlı SessionStart fire (Claude Code
  içinden başlatılamaz; 3.7 production'da zaten doğrulandı), refine-skill
  execution (interactive Claude Code gerekir).

- [x] **3.10a Package-data fix (release-blocker)** *(commit `de47085`, 2026-04-16)*
  v0.3.0 wheel inceleme sırasında bulundu: `mnemos/cli.py:_hook_script_path()`
  ve `mnemos/install_statusline.py:_repo_snippet_path()` repo kökündeki
  `scripts/auto_refine_hook.py` + `scripts/statusline_snippet.{sh,cmd}`
  dosyalarına `Path(__file__).resolve().parent.parent / "scripts"` ile
  işaret ediyor. Wheel sadece `mnemos/` paketini ship'liyor (`packages =
  ["mnemos"]`), `scripts/` wheel'de yok. `pip install mnemos-dev`
  kullanıcılarında `install-hook` + `install-statusline` mevcut olmayan
  path'lere yazıyor → SessionStart'ta `python: can't open file`.

  **Fix:**
  - `scripts/auto_refine_hook.py` → `mnemos/auto_refine_hook.py`
    (importable module). `install-hook` artık `python -m mnemos.auto_refine_hook
    --vault X` yazıyor (filesystem path yok, sadece module invocation).
  - `scripts/statusline_snippet.{sh,cmd}` → `mnemos/_resources/...`.
    `_repo_snippet_path()` `Path(__file__).resolve().parent / "_resources" /
    name` döndürür (paket içinden çözer, hem dev hem pip install'ta çalışır).
  - `pyproject.toml`'da `_resources/*` non-py dosyalarını ship etmek için
    hatch `force-include` ya da `include` ayarı.
  - Author'un mevcut `~/.claude/settings.json`'ı eski path'i taşıyor; fix
    sonrası `mnemos install-hook --uninstall && install-hook` ile refresh.

- [x] **3.10 PyPI release v0.3.0** *(2026-04-16)*
  - PyPI: <https://pypi.org/project/mnemos-dev/0.3.0/>
  - GitHub release: <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.0>
  - Tag: `v0.3.0` (annotated). Wheel + sdist attached as release assets.

- [x] **3.11 Auto-refine noise filter + truthful status reporting** *(commit `a86c57a`, 2026-04-16)*

  **Sorun (kullanıcı raporu, 2026-04-16 post-3.10 canlı kullanım):**
  Hook tetikleniyor, statusline "refining 1/3 · 0m1s · backlog 151" sonra
  "last refine 4m ago · 3 notes · OK · backlog 152" gösteriyor — ama backlog
  150 → 151 → 152 büyüyor, hiç küçülmüyor. Soruşturmada iki ortogonal kök
  neden bulundu:

  1. **Picker en yeni 3'ü mtime'a göre alıyor.** Yazarın akışında en yeni
     JSONL'lar genelde `/clear → mnemos` resume session'ları (16-30 satırlık
     1-2 user turn). Refine-skill bunları doğru SKIP'liyor ama her yeni
     session +1 JSONL ekliyor → backlog asla küçülmüyor, picker hep noise
     dolaşıyor. Pilot sayıları doğruluyor: ledger 6 OK / 44 SKIP.
  2. **Statusline yalan söylüyor.** `last_outcome="ok"` `picked` boş değilse
     atanıyor — "3 notes · OK" aslında "3 JSONL ziyaret edildi (hepsi SKIP,
     0 markdown yazıldı)" demek. Kullanıcı "iş yapılmadı" hissi alıyor.

  **Çözüm:**
  - `mnemos/auto_refine.py`:
    - Yeni `MIN_USER_TURNS = 3` constant + `_count_user_turns(path)` helper
      (Claude Code JSONL'i parse eder, `tool_result` mesajlarını gerçek user
      turn olarak saymaz — sayım üst sınırı 500 satır, ucuz)
    - `pick_recent_jsonls` ve `compute_backlog`'a `min_user_turns: int =
      MIN_USER_TURNS` kwarg → kısa transcript'ler hem pick'e hem backlog'a
      görünmez (default 3, opt-out için `0`)
    - `_latest_outcome_for_path(ledger, path)` helper — ledger'ın son
      kaydını okur (append-only, latest wins)
    - `_run_locked` her refine sonrası bu helper'la OK / SKIP delta sayar;
      `last_ok` + `last_skip` status'a yazılır
    - Final `last_outcome`: `picked=[]` → "noop"; `ok>0` → "ok";
      `picked>0 ama ok=0` → **"skip"** (yeni state, yalanı kapatır)
    - `write_status` `last_ok`, `last_skip` opsiyonel kwarg alır; unset
      ise JSON'da yer almaz (geriye dönük uyum)
  - `mnemos/_resources/statusline_snippet.{sh,cmd}`:
    - Idle render `last_ok`/`last_skip` varsa kullanır:
      - `ok>0 & skip>0` → "X notes · Y skipped"
      - `ok>0 & skip=0` → "X notes"
      - `ok=0 & skip>0` → "0 notes (Y skipped)"
    - Eski status JSON formatında bu alanlar yoksa eski `total + outcome`
      render'ına düşer

  **Test (TDD):**
  - `tests/test_auto_refine.py`: `_count_user_turns` (minimal, tool_result
    exclude, missing file, malformed lines), picker turn-filter (newest
    short skipped, threshold boundary, 0=disable), backlog turn-filter,
    write_status outcome counts (set + omit), `_run_locked` ledger delta
    (mixed OK+SKIP, all SKIP → outcome=skip, all OK → outcome=ok, empty
    → outcome=noop). 12 yeni test + mevcut `_write_jsonl` helper'a
    `user_turns=3` default eklendi (mevcut testler bozulmadan)
  - `tests/test_auto_refine_hook_script.py`: `_run_hook` helper'ı 3-turn
    JSONL üretir (filtre subprocess'te de aktif olduğu için)

  **Etki:**
  - Backlog gerçek "işlenebilir" sayıyı yansıtır (test edilen vault'ta
    ~150 → muhtemelen ~30, çoğu noise filter'da düşer)
  - Her session açışta 30-60s × 3 boş `claude --print` çağrısı (subscription
    quota kullanıyor) durur
  - Statusline gerçekten yapılanı gösterir: "0 notes (3 skipped)" →
    kullanıcı sistem çalıştığını görüp picker'ın yanlış pick yaptığını
    anlar

- [x] **3.12 PID-based active-session exclusion** *(commit `136f49b`, 2026-04-17)*
  **3.12b hardening** *(commit `b7e9f40`, 2026-04-17)*:
  - mtime fallback (`RECENTLY_MODIFIED_SECONDS = 1800`): PID marker'ı olmayan
    JSONL'lar (3.12 deploy'undan önce açılmış session'lar) için mtime < 30 dk
    ise "muhtemelen açık" sayılır → picker + backlog'dan düşer. Canlı testte
    kanıtlanan açık: bu konuşmanın JSONL'ı marker'sız olduğu için yeni
    session tarafından refine edilmişti.
  - Wrapper status guard: status dosyasında `phase=refining/mining` görülürse
    wrapper yeni `refining 0/3` YAZMAZ → çalışan worker'ın status'ünü ezmez.
    Canlı testte "0/3 dondu" olarak gözlemlenmişti.
  - `read_status_phase(vault)` helper → hook wrapper kullanır.

  **Sorun:** 3.7d sadece kendi transcript'ini (self) exclude ediyor. 3-4
  eşzamanlı Claude Code penceresi açıksa picker diğer açık session'ların
  canlı JSONL'larını pick edip refine edebiliyor — transcript hâlâ yazılırken
  ledger'a OK olarak işaretleniyor, sonraki turn'ler sessizce kayboluyor.
  mtime heuristic (5 dk idle → kapalı sayılır) güvenilmez: kullanıcı
  pencereler arası geçiş yapıyor, düşünürken idle kalabiliyor.

  **Çözüm — PID marker dosyaları:**
  - `~/.claude/projects/.mnemos-active-sessions/<session-id>.json` marker:
    `{pid, transcript_path, started_at}`
  - Hook wrapper `os.getppid()` ile Claude Code'un PID'ini alır → marker yazar
  - Picker çalışmadan önce tüm marker'ları tarar:
    - PID canlı (`kernel32.OpenProcess` / `os.kill(0)`) → transcript exclude
    - PID ölü → marker silinir, transcript artık pick edilebilir
    - Marker > 24h → PID recycling guard, sil
  - `get_active_transcript_paths()` → picker `exclude=` + `compute_backlog(active_paths=)`
  - Geriye dönük uyum: `active_paths=None` = eski davranış (mevcut testler bozulmaz)

  **Test (TDD):**
  - `_is_pid_alive` (own PID=True, dead PID=False)
  - `register_active_session` (marker dosyası oluşur)
  - `get_active_transcript_paths` (live=included, dead=cleaned, stale=cleaned, empty=no crash)
  - `pick_recent_excludes_active_sessions` (mevcut exclude param ile çalışır)
  - `compute_backlog(active_paths=)` (active excluded, None=backward compat)

- [x] **3.12c Per-session statusline + one-shot sadeleştirme** *(commit `a04a1dc` + `1f7e296`, 2026-04-17)*
  Claude Code statusline komutunu session başında bir kez çağırıyor
  (sürekli poll yok — debug logla kanıtlandı). Snippet buna göre
  yeniden yazıldı: elapsed timer, running tally, stale-idle TTL
  kaldırıldı. `triggering_session_id` eklendi — sadece refine'ı
  tetikleyen session sonucu görür, diğer pencereler sessiz kalır.
  Canlı testte gözlemlenen sorun: başka penceredeki "last refine
  4m ago" yazısı kullanıcıda "kendini refine ediyor" izlenimi
  yaratıyordu. Artık yaratmıyor.

- [x] **3.13 Backlog batch temizliği** *(2026-04-17)*
  Tüm 53 unprocessed transcript tek seferde işlendi. 5 paralel
  subagent triage yaptı (OK/SKIP karar), ardından 34 OK dosya
  `claude --print --dangerously-skip-permissions` ile paralel (3'er)
  refine edildi. 19 SKIP ledger'a yazıldı. Final: 122 ledger entry
  (52 OK, 70 SKIP), backlog **0**, Sessions/ altında 66 .md not.

### Başarı kriterleri

- [x] External user, README'deki 5 adımı izleyerek clean vault'ta çalışır mnemos kurabiliyor *(3.9 pilot doğruladı)*
- [x] `mnemos init` 244 JSONL transcript'i keşfedip pilot + import önerebiliyor *(3.4a)*
- [x] `.mnemos-pending.json` resume çalışıyor — oturum kesilirse baştan başlamak gerekmiyor *(3.3 + 3.4a)*
- [x] `mnemos import` 5 formatın hepsini destekliyor *(3.5: claude-code/chatgpt/slack/markdown/memory)*
- [x] Skill install (junction/symlink) dokümante + test edilmiş *(3.6 CONTRIBUTING + 3.1 SKILL.md)*
- [x] Auto-refine hook production-hardened: noise filter, PID exclusion, mtime fallback, per-session statusline, backlog 0 *(3.11-3.13)*

---

## v0.3.1 — Backend UX ✅ *(2026-04-17)*

**Sorun:** Kod iki vector backend'i destekliyor (ChromaDB + sqlite-vec).
2026-04-17 parity benchmark'ında dördüncü ondalığa kadar aynı sayılar
verdiler (R@5=0.90). Ama external user bu alternatiften habersiz:
`mnemos init` sormuyor, README'de tek parantezli cümle, ChromaDB corrupt
olunca cryptic traceback. MemPalace'te (42K★) de aynı durum — onların
repair komutu (#239) + Qdrant (#700) + LanceDB (#574) PR'ları hâlâ open.

Biz zaten sqlite-vec'i ship'ledik; iş kullanıcının bunu keşfetmesini,
güvenle geçmesini ve hata sırasında yol bulmasını sağlamak.

**Canonical spec:**
[`docs/specs/2026-04-17-v0.3.1-backend-ux-design.md`](specs/2026-04-17-v0.3.1-backend-ux-design.md)

### Görevler

- [x] **3.14c BackendInitError wrapper** *(commit `9bb916d`, 2026-04-17)*
  `mnemos/errors.py` (yeni) + `mnemos/search.py`'de factory wrapper. ChromaDB
  HNSW load veya sqlite-vec DB open hatası yakalanır, kullanıcıya "migrate
  --backend X" önerisi bastırır. CLI main() tek noktada catch + stderr + exit 2.
  `tests/test_backend_errors.py` 7 test; full search+miner+pending suite 59 pass.

- [x] **3.14e `mnemos status` backend bilgisi** *(commit `c944dff`, 2026-04-17)*
  `SearchBackend.storage_path()` abstract (default None) + iki backend override.
  `get_stats()` çıktısında `storage_bytes` (shared `_path_size_bytes()` helper).
  `handle_status` `backend: {name, path, storage_bytes}` bloğu döner. CLI
  `Backend: <name> (<path> · N drawers · X MB)` satırını JSON öncesinde bastırır.
  9 yeni test + 50 pass full suite, real vault smoke doğruladı.

- [x] **3.14b `mnemos migrate --backend X` komutu** *(commit `a70f7ed`, 2026-04-17)*
  `mnemos/migrate.py` (yeni) + CLI subparser. Pre-flight plan (drawer +
  source file sayısı + süre tahmini, ±%30 marj), `--dry-run`, backup
  (`.chroma.bak-YYYY-MM-DD` / `search.sqlite3.bak-YYYY-MM-DD`, aynı gün ikinci
  migrate `.bak-DATE.2` suffix), yaml update, mine_log clear, rebuild,
  drawer-drop uyarısı (>%20 düşüş → "backup preserved"). 8 test + real-vault
  dry-run smoke doğruladı. Rollback-on-failure + migration-lock recovery
  follow-up iş olarak kayıtlı.

- [x] **3.14a `mnemos init` backend prompt** *(commit `3d99c17`, 2026-04-17)*
  `use_llm` prompt'u sonrası (yaml yazımından önce) backend picker — böylece
  ilk mining doğru backend'e gider. `_ask_backend_choice` + platform sniff
  `_resolve_backend_hint` (Windows+Py3.14 ek satır). 8 yeni i18n key (EN+TR).
  Re-run idempotency: yaml'da `search_backend` zaten varsa sormaz.
  conftest.py stdout UTF-8 reconfigure eklendi (cp1252 Windows test
  runner'larında unicode glyph crash fix). 18 yeni test + 63 pass full suite.

- [x] **3.14d README Troubleshooting + hero tweak** *(commit `1209457`, 2026-04-17)*
  README hero paragrafı iki backend'i açıkça anıyor + parity benchmark referansı.
  Yeni "Troubleshooting" bölümü 3 recipe: `mnemos status` (hangi backend),
  corruption → `migrate --backend sqlite-vec` (+ `--dry-run`), geri dönüş.
  Architecture diagram sqlite-vec'i peer olarak gösteriyor. CONTRIBUTING'e
  yeni architectural-line: "backend count stays at two" + 3. backend PR'ı
  için yüksek bar kriteri.

- [x] **3.14f Pilot + release v0.3.1** *(commit `d914e84`, 2026-04-17)*
  Clean vault pilot ([`docs/pilots/2026-04-17-v0.3.1-backend-pilot.md`](pilots/2026-04-17-v0.3.1-backend-pilot.md))
  tam akış yeşil. Version bump `0.3.0 → 0.3.1`, wheel + sdist build başarılı
  — kritik dosyalar (migrate, errors, auto_refine_hook, _resources) wheel'de
  (3.10a package-data bug'ı tekrar etmedi). Annotated tag `v0.3.1` pushed,
  GitHub release at <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.1>
  (wheel + sdist asset'li). PyPI upload kullanıcıya devredildi.

### Başarı kriterleri

- [ ] External user `mnemos init`'te backend seçimini görüyor, `mnemos.yaml`
      elle açmak zorunda kalmıyor
- [ ] ChromaDB corruption durumunda error mesajı `mnemos migrate --backend
      sqlite-vec` komutunu gösteriyor, kullanıcı copy-paste ile kurtuluyor
- [ ] `mnemos status` çıktısında backend satırı var — destek isteyen
      kullanıcı hangi backend'de olduğunu görebiliyor
- [ ] İki yönlü migrate çalışıyor (chromadb ↔ sqlite-vec), backup'lar güvende
- [ ] README Troubleshooting tek paragrafta problemi + çözümü veriyor

---

## v0.3.2 — Palace Hygiene ✅ *(2026-04-18)*

**Sorun:** Author vault'unda dokuz pipeline hatası birikti — aynı konu üç
ayrı wing'e bölünüyor (diacritic + tire), boş hall klasörleri graph
view'ı kirletiyor, `tags[0]` oda ismine terfi ediyor (başlık-uzunluğunda
odalar), drawer dosya adlarında çift tarih prefiksi, graph node'ları
sadece ID gösteriyor (başlıksız), entity listesi frontmatter tag'leriyle
kirli. Ve `mnemos mine --rebuild` adı "atomic" iken aslında sadece
`mine_log clear + re-mine` yapıyordu — backup yok, index wipe yok,
rollback yok. Büyük vault'ta kısmi hata data kaybına açık.

**Canonical spec:**
[`docs/specs/2026-04-18-v0.3.2-palace-hygiene-design.md`](specs/2026-04-18-v0.3.2-palace-hygiene-design.md)

### Görevler

- [x] **A1 Wing canonicalization (TR diacritic + delimiter normalize)** *(commit `94b624d`, 2026-04-18)*
- [x] **A2 Lazy hall / `_wing.md` / `_room.md` create** *(commit `590f302`)*
      — Empty wings ve phantom room klasörleri artık oluşmuyor.
- [x] **A3 `tags[0]` → room promotion'ı kaldır, wing≠room flatten** *(commit `0e72389`)*
- [x] **A4 Source-date filename + word-boundary slug** *(commit `6707010`)*
- [x] **A5 Drawer body H1 title + source wikilink** *(commit `13fc74c`,
      review fix `9532caf` — synthetic/manual source'ların `[[unknown]]`
      linki atılıyor)*
- [x] **A6 Entity hygiene — no tags, case-preserve dedup** *(commit `bbfa1b8`)*
- [x] **A2 follow-up test fix** *(commit `509582f`)* — `test_app_recall`,
      `test_app_wake_up`, üç `test_stack.py` testi A2'nin eski eager
      `_wing.md` davranışını varsayıyordu; her wing'e minimal drawer
      seed ederek lazy summary'yi tetiklettim.
- [x] **B1 `SearchBackend.drop_and_reinit()`** *(commit `2059783`)*
      — Abstract metod + ChromaDB + sqlite-vec implementasyonları.
      Rebuild sonrası backend aynı süreçte yeniden kullanılabilir.
- [x] **B2 `Palace.backup_wings(timestamp)`** *(commit `6a9570d`)*
      — Atomic `shutil.move`. `.N` collision suffix aynı saniyede iki
      rebuild çakışmasını engelliyor.
- [x] **B3 `KnowledgeGraph.reset()`** *(commit `1c4da1f`)*
- [x] **B4 `mnemos/rebuild.py` — `_resolve_sources` + `RebuildError`** *(commit `729eea4`)*
      — Explicit path > `cfg.mining_sources` > auto-discover `Sessions/`
      + `Topics/` > `RebuildError`.
- [x] **B5 `build_plan` + `format_plan`** *(commit `b70a935`)*
      — Dry-run için source sayısı + backup path + mevcut drawer count.
- [x] **B6 `rebuild_vault` orchestrator** *(commit `86a915b`)*
      — Dokuz faz: resolve → plan → dry-run gate → confirm → lock →
      backup (wings + index + graph) → `drop_and_reinit` + `graph.reset`
      → re-mine → verify → rollback on failure.
- [x] **B7 CLI wire — `mnemos mine --rebuild` + `--dry-run`/`--yes`/`--no-backup`** *(commit `85e301c`)*
      — `path` artık optional (`--rebuild` ile auto-discover çalışıyor).
- [x] **B8 Auto-refine hook `.rebuild.lock.flock` early-exit** *(commit `7f30777`)*
      — Orchestrator lock'u tuttuğunda hook sessizce çıkıyor. 50 ms
      non-blocking probe stale lock file'larını blokluyor değil.
- [x] **Code review fix-up** *(commit `d290de8`)* — `backend.close()` ve
      `graph._conn.close()` artık `try/finally`'de → Windows'ta rollback
      path'i `shutil.rmtree(storage_path)` çalıştırabilsin (açık handle
      `WinError 32` veriyordu). `_resolve_sources` iki kez çağrılmıyor
      artık (`plan["sources_resolved"]` taşınıyor). `test_rebuild_happy_
      path` parametrize edilip ChromaDB end-to-end rebuild test edildi
      (dir backup vs sqlite-vec'in file backup'ı — ilk kez). Yeni
      stale-lock recovery testi eklendi. 17 test, hepsi yeşil.
- [x] **C3 Version bump + CHANGELOG** *(commit `37244d7`)*
- [x] **C4 STATUS + ROADMAP güncel** *(commit `09c4451`)*
- [x] **C1 Light pilot** *(commits `bf60a6a` + `6c80e8d` + `1097ccb`)*
      — Unit tests green, dry-run against kasamd matched plan (81 sources,
      670 drawers), single-file smoke caught two A4/A5 regressions
      (double-date filename + `# # Title` H1) which were fixed.
- [x] **C2 Real vault rebuild + memory re-import + round-trip** *(commits
      `998a529` + `e9f3d6d` + `0abfd7e` + `bb53892`)*
      — kasamd rebuilt end-to-end. Caught and fixed three
      distribution-ready bugs (MEMORY.md noise, import-not-persisted,
      `_resolve_sources` replacement vs additive). Final: 683 drawers
      (NET +13 over pre-v0.3.2), 16 wings, 5 `mining_sources` entries
      auto-included in every rebuild forward.
- [ ] **C5 Build, tag, PyPI, GitHub release**

### Başarı kriterleri

- [x] `mnemos mine --rebuild` atomic — wings backup, index drop + reinit,
      graph reset, verify, rollback on failure
- [x] Auto-refine hook ve rebuild orchestrator concurrent çalışmıyor
      (FileLock-based mutual exclusion)
- [x] Pipeline hygiene — TR diacritic normalize, lazy summaries, no
      tags→room promotion, source-date filename, H1+wikilink body,
      case-preserve entity dedup
- [x] İki backend de `rebuild_vault` end-to-end test edildi (ChromaDB
      dir backup + sqlite-vec file backup)
- [x] Gerçek vault rebuild başarılı (C2 — kasamd pilot 683 drawer)

---

## v0.3.3 — Post-v0.3.2 cleanup ✅ *(2026-04-19)*

**Sorun:** v0.3.1 + v0.3.2 pilotlarında CHANGELOG'a "deferred" olarak düşen
dört ufak madde — bazıları cosmetic (score display, dry-run estimate),
bazıları user-experience-blocker (migrate rollback yok, concurrent migrate
koruması yok, durability test 300s timeout'la takılı). Phase 1 öncesi
tree'yi yeşil bırakmak için tek commit'te kapatıldı.

### Görevler

- [x] **Migrate rollback-on-failure + migration lock** *(commit `4ba52e4`)*
      `MigrateError`, `.migrate.lock.flock` (filelock, advisory), rebuild
      fail → backup+yaml+mine_log otomatik restore + partial new-backend
      cleanup. 3 yeni test (rollback, mine_log restore, lock contention).
- [x] **Dry-run estimate edge case** *(commit `4ba52e4`)*
      `MigrationPlan.format_estimate()` — 60s altı saniye modu, 1s floor.
      4 yeni test (seconds, sub-second floor, minute boundary, large vault).
- [x] **sqlite-vec score rescale** *(commit `4ba52e4`)*
      `_l2_to_cosine_sim` → `_l2_to_score`: `1 - L2/2` (linear, monotonic,
      ChromaDB ile visual band aynı 0.3–0.7). Ranking ve benchmark recall
      identical — sadece surface display değişti.
- [x] **Durability test deselect + slow marker** *(commit `4ba52e4`)*
      `pyproject.toml`'da `[tool.pytest.ini_options]` + `slow` marker
      register + `--strict-markers` + default `addopts = "-m 'not slow'"`.
      `test_write_without_close_can_lose_hnsw_segments` tagged + subprocess
      timeout 300→600s.
- [x] **PyPI release v0.3.3** — <https://pypi.org/project/mnemos-dev/0.3.3/>,
      GitHub release at <https://github.com/mnemos-dev/mnemos/releases/tag/v0.3.3>.

---

## v0.4.0 — AI Boost / Phase 1 🔄 *(başladı 2026-04-19)*

**Hedef:** Skill-first LLM augmentation. Kullanıcıya iki ortogonal eksen
sunuyoruz (mine-mode × recall-mode), her biri script (API'siz,
deterministic) veya skill (Claude Code oturumunda `claude --print`,
abonelik quota kullanır, API paketi yok). Pilot orchestrator 10 session'u
iki palace'ta paralel üretir, kullanıcı kendi verisinde karar verir.

**Orijinal API-based 4.2-4.4** (Claude SDK mining + rerank +
contradiction) **iptal** — skill paterni ile aynı amaca daha temiz ulaşıyor.
Rerank skill-recall'ın içinde eridi; contradiction v0.5 hygiene'a ertelendi.

**Canonical spec:**
[`docs/specs/2026-04-19-phase1-ai-boost-design.md`](specs/2026-04-19-phase1-ai-boost-design.md)

### Görevler

- [x] **4.1 Phase 1 design spec yaz** *(2026-04-19)*
  `docs/specs/2026-04-19-phase1-ai-boost-design.md` — skill-first reframe,
  4-kombo mimarisi, pilot orchestrator, settings TUI, v0.5'e ertelenen
  işler.
- [~] **4.2 Skill-mine + pilot orchestrator** *(~8h kod + post-pilot fixes)*
  - [x] **4.2.1** `skills/mnemos-mine-llm/` skill + canonical prompt *(commit `c7d6c58`)*
  - [x] **4.2.2** `mnemos/pilot.py` orchestrator + `mnemos mine --pilot-llm` *(commit `e300a2c`, 28+3 test)*
  - [x] **4.2.3** `skills/mnemos-compare-palaces/` skill + prompt *(commit `777d076`)*
  - [x] **4.2.5** `mnemos pilot --accept <script|skill>` komutu *(commit `777d076`, 7+3 test)*
  - [x] **4.2.6 Real-vault pilot** *(2026-04-19, kasamd 3 session)* — çalıştı,
        skill-mine drawer kalitesi script'ten açıkça üstün; 4 operational
        finding çıktı. Rapor:
        [`docs/pilots/2026-04-19-v0.4-phase1-real-vault-pilot.md`](pilots/2026-04-19-v0.4-phase1-real-vault-pilot.md)
  - [x] **4.2.7 Ledger reliability fix** *(2026-04-19)* — orchestrator
        `count_drawers_for_session` fallback: ledger boşsa drawer
        frontmatter `source:` field'ını okur, session'a ait drawer'ları
        filesystem'den sayar + "recovered from filesystem" OK outcome.
        SKILL.md'de ledger-append refleks olarak sertleştirildi ("🔴 ZORUNLU"
        + neden ile). 3 yeni test.
  - [x] **4.2.8 Report session-filter** *(2026-04-19)* — `_count_drawers`
        + `_hall_counts_for_palace` opsiyonel `sessions` filtresi alır;
        drawer frontmatter `source:` field'ından eşleştirir; `format_pilot_report`
        her iki palace'ı `plan.sessions` ile filter'lar — apples-to-apples.
        1 yeni test.
  - [x] **4.2.9 Palace indexer + `mnemos mine --from-palace`** *(2026-04-19)* —
        `mnemos/palace_indexer.py`: walk_palace + parse_drawer + index_palace.
        Frontmatter-authoritative (wing/room/hall/source/importance/language),
        drop_and_reinit + index_drawers_bulk. CLI `--from-palace PATH`.
        `accept_skill(reindex=True)` default → `_reindex_after_accept` helper;
        başarılıysa WARNING çıkmaz, fail'de advisory WARNING. 13+2 yeni test
        (palace_indexer + pilot reindex). Full suite 524 pass.
  - [~] **4.2.10 Latency realism + parallel-3** *(~1h, Finding 1)* —
        spec `25s/session` öngördü, gerçek `~4 min/session`.
        Docs kısmı *(2026-04-19)*: spec §4.2.2 step 4 "Latency realism"
        satırı; CLI `Estimated time` ~4 min/session × N formüle dayanıyor.
        Parallel-3 implementation v0.4.2-alpha batch'ine taşındı (aşağı).

#### v0.4.2-alpha batch — full skill-mine prep + run *(sonraki oturum)*

**Canonical plan:** [`docs/plans/2026-04-19-v0.4.2-full-skill-mine-prep.md`](plans/2026-04-19-v0.4.2-full-skill-mine-prep.md)

- [x] **4.2.11 Skill prompt multi-format** *(2026-04-19)* — `mine-llm.md`
      canonical prompt + `skills/mnemos-mine-llm/SKILL.md` artık 4 input
      format tipini destekliyor: Type A (refined Sessions), Type B
      (curated Topics — H2 subsection başına drawer, hall content
      inference'la), Type C (Claude Code memory — dosya başına tek
      drawer, `type: user|feedback|project|reference` → hall mapping),
      Type D (MEMORY.md index → SKIP). CHUNKING bölümü type-aware
      (Type A bölüm-baz, Type B H2-baz, Type C atomize). Source wikilink
      Type C için dead-link yaratmıyor (v0.3.2 A5 synthetic-source
      kuralı genişletildi). Orchestrator (4.2.12) artık bu prompt'a
      Sessions + Topics + memory dosyalarını güvenle pas'layabilir.
- [x] **4.2.12 Orchestrator multi-source plan** *(2026-04-19)* — `build_plan`
      artık `_resolve_source_dirs(vault)` helper'ı üzerinden Sessions/ +
      Topics/ + `cfg.mining_sources` union'ını keşfediyor (rebuild.py
      paterni). `rglob("*.md")` recursive — memory/ subfolder'ları dahil.
      MEMORY.md + leading-underscore dosyalar filtrelenir. Dedup normpath
      üstünden. Plan API rename: `plan.sessions` → `plan.sources`,
      `session_count` → `source_count`, `sessions_needing_run` →
      `sources_needing_run`, `count_drawers_for_session` →
      `count_drawers_for_source`. CLI help metinleri + Pilot plan çıktısı
      "Sources" etiketi kullanıyor. 5 yeni test (multi-source union,
      MEMORY.md skip, overlap dedup, `_` prefix skip, recursive subdir).
      Full suite **529 pass / 2 skip / 3 deselect**.
- [x] **4.2.13 CLI `--pilot-limit 0` no-limit mode** *(2026-04-19)* —
      `build_plan(limit=0)` artık "tüm kaynaklar" anlamına geliyor (full
      batch mine); negative limit hâlâ PilotError. CLI çıktısı
      zenginleşti: `Sources: N files (X Sessions + Y Topics + Z ext)
      (limit=all|N)` breakdown + `_format_duration_estimate` helper'ı
      (saniyeden dakikaya ve saate geçiş) + sequential vs paralel-3
      (target, 4.2.14) iki estimate. Yeni `source_breakdown(vault,
      sources)` helper'ı pilot.py'da — resolution order'ı (Sessions,
      Topics, yaml mining_sources) korur. 3 yeni test (limit=0=all,
      negative limit reject, source_breakdown). Full suite 531 pass.
- [ ] **4.2.14 Parallel-3 execution** *(~1.5h)* — ThreadPoolExecutor +
      filelock ledger lock + `--no-parallel` fallback. Progress output.
- [ ] **4.2.15 Full skill-mine run** *(~2.5h paralel-3 gerçek iş)* —
      ledger wipe → recycle Mnemos-pilot → 114-source mine → compare →
      accept skill. Kasamd kullanım deneyimi smoke.
- [ ] **4.3 Skill-recall** *(~5h)*
  - `skills/mnemos-recall/` — user-invoked `/mnemos-recall <query>`,
    vector top-50 → LLM judge → curated 300-500 kelime context
  - `skills/mnemos-briefing/` + `mnemos/recall_briefing.py` + `mnemos
    install-recall-hook` — opt-in SessionStart briefing (<4h freshness
    window, stale-ama-fresh model, refine-hook paraleli)
  - MCP server `instructions` alanı `recall_mode` yaml'dan dinamik
    (`script` → AI auto-query; `skill` → AI sessiz, skill-driven)
- [ ] **4.4 ~~Contradiction detection~~ → v0.5'e ertelendi** (spec §2)
- [ ] **4.5 `mnemos settings` TUI** *(~2.5h)*
  - `mnemos/settings_tui.py` — numbered menu, 8 satır: backend, mine-mode,
    recall-mode, refine-hook, recall-hook, statusline, languages, briefing
    hint. Alt-aksiyon mevcut komutlara (migrate, install-hook, vb.)
    delegate. i18n TR+EN.
- [ ] **4.6 Benchmark S+S combo** *(~3h)*
  - LongMemEval full 500q, sadece script-mine + script-recall ölçümü
  - **Hedef: Recall@5 ≥ %93** (Phase 0 %90'dan marjinal iyileşme;
    orijinal %95 iddiası skill-first yaklaşımla düştü — S+S combo'ya
    rerank gelmiyor. Skill modları kalitatif, pilot raporuyla değerlenir.)
- [ ] **4.7 PyPI release v0.4.0**

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
- [ ] **5.3 Contradiction detection / stale memory hygiene** *(2-3h, v0.4'ten ertelendi)*
  - Yeni memory mevcut memory'lerle çelişiyor mu? (örn. "X kullanıyoruz" vs
    yeni "Y'ye geçtik" → eski outdated işaretlenir)
  - Skill-based: `/mnemos-hygiene` periodic audit — skill yeni drawer'ları
    eskilerle karşılaştırır, çelişenleri `contradicts:` frontmatter + `stale: true`
    ile işaretler. Auto-recycle yerine kullanıcı onayıyla `_recycled/`'a.
- [ ] **5.4 Memory lifecycle / decay** *(2h)*
  - Eski, hiç aranmamış, çelişki-işaretli memory'ler zaman içinde fade out
  - `mnemos prune --dry-run` komutu
- [ ] **5.5 Knowledge graph deepening** *(3-4h)*
  - Cross-reference: "bu memory X projesinde, X projesi Y wing'inde, Y wing
    son Z günde şu kararları aldı" gibi dolaylı sorgular
  - `mnemos_graph` tool genişletme
- [ ] **5.6 PyPI release v0.5.0**

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
3. **[`STATUS.md`](../STATUS.md) güncelle** — "What Mnemos can do today" bölümüne yeni capability'yi ekle, gerekirse "Where the roadmap ends up" satırını güncelle. STATUS.md dışarıya açık olan durum dosyası; buradaki checkbox değişmeden oraya özellik eklenmez, özellik eklenmeden checkbox flip edilmez — ikisi birlikte commit olur
4. Scope değişirse ilgili satırı güncelle, gerekirse yeni alt-görev ekle
5. Yeni phase design spec'leri `docs/specs/` altında; bu ROADMAP'te sadece özet
