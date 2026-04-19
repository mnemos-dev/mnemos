# Mnemos — Claude Code Project Instructions

Bu dosya Claude Code tarafından `C:\Projeler\mnemos` altında çalıştığında
otomatik yüklenir. Sadece bu projeye özel kurallar burada; global kurallar
`~/.claude/CLAUDE.md`'de.

---

## Tek kelime resume protokolü 🧠

**Tetik:** Kullanıcı `/clear` sonrası şu ifadelerden birini yazdığında:
- Tek başına `mnemos`
- `devam`, `kaldığımız yer`, `resume`, `nerede kalmıştık`
- `mnemos'a devam`, `mnemos dev`

**Bir şey implemente etme, önce bağlamı yükle.** Akış:

1. `STATUS.md` oku — projenin amacı + şu anki capability seti
2. `docs/ROADMAP.md` oku — aktif sürümü (🔄) ve ilk işaretsiz `[ ]` veya `[~]` görevi bul
3. `git log --oneline -10` + `git status --short` çalıştır — son commit'ler ve kirli dosyalar
4. **<100 kelime özet ver:**
   - Proje amacı (1 cümle, STATUS §1'den)
   - Şu anki sürüm + faz (örn. "v0.4 AI Boost in-progress")
   - Son tamamlanan görev + commit hash
   - Sırada bekleyen ilk görev (ilk `[ ]` veya `[~]`)
   - Kirli / uncommitted durum varsa işaret et
5. **Sor:** "Devam mı, başka iş mi?" — kullanıcı onaylamadan implementasyona geçme

**Not:** Kullanıcı doğrudan bir görev (örn. "3.3'ü yapalım") derse 1-4. adımları
yine hızlıca yap ama 5. sormadan o göreve geç.

---

## Proje snapshot

- **Ne:** Obsidian-native AI memory palace. Claude Code JSONL transcript
  geçmişini aranabilir markdown hafızaya çevirir.
- **Canonical plan:** `docs/ROADMAP.md` — tek doğruluk kaynağı
- **Dış durum:** `STATUS.md` — indiren kişi için ne yapıyor, nereye gidiyor
- **Skill:** `skills/mnemos-refine-transcripts/` — `~/.claude/skills/` altına
  junction'lı, bu repo canonical
- **Canonical refinement prompt:** `docs/prompts/refine-transcripts.md`
- **Yazarın vault'u (test/pilot için):** `C:\Users\tugrademirors\OneDrive\Masaüstü\kasamd`
- **PyPI:** `mnemos-dev` — stable v0.3.3, v0.4.0 (AI Boost / Phase 1) hazırlıkta
- **GitHub:** `github.com/mnemos-dev/mnemos`

---

## Çalışma disiplini

1. Göreve başlamadan ROADMAP'te checkbox `[ ] → [~]` (in progress)
2. Görev bitince **tek commit'te:**
   - ROADMAP checkbox `[~] → [x]` + commit hash + tarih
   - STATUS.md'nin §2 "What works today" bölümüne ilgili capability ekle
     (STATUS §3'ten §2'ye taşıma şeklinde olabilir)
   - Kod + test
3. Skill / script / docs değişikliğinden sonra otomatik `git add → commit →
   push` (global kural)
4. Scope değişirse ROADMAP'te satırı güncelle, gerekirse alt-görev böl
5. Yeni phase başlarken önce `docs/specs/` altında design spec yaz (Phase 0
   formatında); sonra implementasyon
6. **Session-end STATUS discipline** — ROADMAP-takipli iş 2. maddeyle zaten
   STATUS'u güncel tutuyor. Ama iki durumda elle STATUS'a yazılmazsa bilgi
   sonraki resume'de kaybolur:
   - **ROADMAP-dışı meta iş** (repo polish, CI workflow, README ELI5,
     social preview, docs refresh — checkbox'ı olmayan iş): STATUS'a
     `### Post-v0.x.y repo polish (YYYY-MM-DD, not a release)` bloğu
     ekle. Gerekirse "Next session starts here" bloğunu da güncelle ki
     meta iş sıradaki Phase'i gölgelemesin.
   - **Pending user action** (GitHub UI upload, elle koşulacak komut,
     dışarıdan token rotate — kodda/git'te izi olmayan iş): STATUS'a
     `🟡 **Pending user action**` işaretli bir satır ekle. İşaret
     zorunlu — resume protokolü bu glyph'i yakalamalı.
   - Aynı zamanda STATUS'ta stale kalmış section varsa (eski istatistik,
     artık geçerli olmayan hardening recap) trim et.
   - **Tetik:** "tamam bu kadar", "kapatıyorum", "session'ı bitirelim",
     "yeni session'a hazırlık", "/clear öncesi" gibi ifadelerde bu
     checkpoint'i yap. Kullanıcı sormadıysa da batch commit sonrası
     kendine sor: "bu işin STATUS izi var mı?"

---

## Mimari hatırlatıcılar

- **Obsidian master, ChromaDB/sqlite-vec index.** Vault'ta olmayan memory
  yoktur. Silmek için `.md` dosyasını `_recycled/`'a taşı — watcher index'i
  temizler.
- **mnemos LLM çağırmaz.** Kullanıcı `--llm` flag verirse Claude API kullanılır,
  yoksa her şey regex + heuristic. Refinement skill de **Claude Code oturumu
  içinde** çalışır — maliyet sıfır.
- **Dual collection:** `mnemos_raw` (verbatim, lossless) + `mnemos_mined`
  (fragments). Arama RRF ile birleştirir. Raw = baseline, mined = precision.
- **Phase eksenleri:** Phase 0 = API'sız foundation (delivered). Phase 1 =
  AI boost. Phase 2 = automation. ROADMAP'te v0.x sürümleriyle eşlenmiş.

---

## Yasak / ihtiyatlı alanlar

- Çıplak `pip install` ile üretim ortamını kirletme — dev için
  `pip install -e ".[dev,llm]"` kullan
- `mnemos mine --rebuild` büyük vault'ta data kaybına yol açabilir; atomic
  rebuild implementasyonu Phase 0'da var ama her zaman `git status` +
  ChromaDB backup ile çalış
- ChromaDB `mnemos/.chroma/` ve SQLite `mnemos/graph.json` yerel runtime
  data — gitignore'lı, commit etme
- Benchmark data `benchmarks/longmemeval/data/` büyük — gitignore'lı
- Junction (`~/.claude/skills/mnemos-refine-transcripts`) ↔ repo:
  drift olmamalı. Skill güncellemesi sadece repo'daki `SKILL.md`'ye yapılır;
  junction aynısını görür.

---

## Kısa komut sözlüğü

| Komut | Ne yapar |
|---|---|
| `pytest tests/ -v` | Tüm testler |
| `python -m mnemos --vault <path>` | MCP server manuel başlat |
| `mnemos benchmark longmemeval --limit 10` | Hızlı benchmark smoke |
| `mnemos mine Sessions/ --rebuild` | Vault'u baştan indexle (atomic) |
| `git push origin main` | Skill/docs/script commit sonrası refleks |
