# Mnemos Roadmap

**Single source of truth.** Implement ettikçe bu dosyayı güncelle, commit et.
Eski `docs/specs/2026-04-*` ve `docs/plans/2026-04-*` dosyaları historical
archive; burada çelişki olursa bu dosya geçerlidir.

**Son güncelleme:** 2026-04-16

---

## Sürüm durumu

| Sürüm | Başlık | Durum | PyPI |
|---|---|---|---|
| v0.1.0 | First Breath | ✅ | ✅ |
| v0.2.0 | Full Memory (= Phase 0 Foundation) | ✅ | ✅ |
| v0.3.0 | First-Run Experience | ✅ | ✅ |
| **v0.4.0** | **AI Boost (= Phase 1)** | **🔄 next** | — |
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

- [~] **3.12 PID-based active-session exclusion**

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

### Başarı kriterleri

- [x] External user, README'deki 5 adımı izleyerek clean vault'ta çalışır mnemos kurabiliyor *(3.9 pilot doğruladı)*
- [x] `mnemos init` 244 JSONL transcript'i keşfedip pilot + import önerebiliyor *(3.4a)*
- [x] `.mnemos-pending.json` resume çalışıyor — oturum kesilirse baştan başlamak gerekmiyor *(3.3 + 3.4a)*
- [x] `mnemos import` 5 formatın hepsini destekliyor *(3.5: claude-code/chatgpt/slack/markdown/memory)*
- [x] Skill install (junction/symlink) dokümante + test edilmiş *(3.6 CONTRIBUTING + 3.1 SKILL.md)*

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
3. **[`STATUS.md`](../STATUS.md) güncelle** — "What Mnemos can do today" bölümüne yeni capability'yi ekle, gerekirse "Where the roadmap ends up" satırını güncelle. STATUS.md dışarıya açık olan durum dosyası; buradaki checkbox değişmeden oraya özellik eklenmez, özellik eklenmeden checkbox flip edilmez — ikisi birlikte commit olur
4. Scope değişirse ilgili satırı güncelle, gerekirse yeni alt-görev ekle
5. Yeni phase design spec'leri `docs/specs/` altında; bu ROADMAP'te sadece özet
