---
name: mnemos-mine-llm
description: >
  Refined Mnemos session note'larını (`Sessions/*.md`) okuyup LLM-judged
  drawer `.md` dosyalarına ayrıştırır. Hedef: pilot-orchestrator tarafından
  çağrılır (script-mine'ın skill-mine karşılığı), ama user manuel de
  çağırabilir. Tetikler: "/mnemos-mine-llm", "LLM ile mine et", "skill-mine",
  "bu session'ı drawer'a ayır". mnemos API ÇAĞIRMAZ, LLM API ÇAĞIRMAZ —
  iş bu oturumdaki Claude tarafından yapılır.
---

<!--
INSTALL NOTE (mnemos-dev ≥ v0.4):
Refine-transcripts skill'iyle aynı kurulum — ~/.claude/skills/mnemos-mine-llm/
altına junction (Windows) veya symlink (Unix). Repo canonical, drift yasak.

v0.4'te `mnemos install-skills` komutu her iki skill'i tek seferde kuracak
(şu anda manuel junction).
-->

# Mnemos — Mine with LLM

Refined session `.md` → drawer `.md` dönüşümü. Refine-transcripts'in
**devamı** (noise temizlendikten sonraki ayrıştırma). Script-mine'ın
(`mnemos mine`) aynı işi regex'le yapan kardeşi.

## Sabitler

- **Canonical mining prompt:** `C:\Projeler\mnemos\docs\prompts\mine-llm.md`
  (drawer schema, hall taksonomi, wing/room/entity kuralları, chunking,
  skip kriterleri — hepsi orada)
- **Ledger:** `C:\Users\tugrademirors\.claude\skills\mnemos-mine-llm\state\mined.tsv`

Diğer path'ler argümanlarla gelir (vault-agnostic skill).

## Tetik örnekleri

- `/mnemos-mine-llm <session.md> <palace-root>` — tek session
- `/mnemos-mine-llm --dir <sessions-dir> <palace-root>` — dir altındaki
  tüm `.md`'ler
- `/mnemos-mine-llm --limit N --dir <sessions-dir> <palace-root>` — pilot
  batch
- `/mnemos-mine-llm --all --dir <sessions-dir> <palace-root>` — tüm
  unprocessed, soru sormadan

## Akış

### 1) Canonical promptu yükle

İlk iş: `C:\Projeler\mnemos\docs\prompts\mine-llm.md`'yi Read. Kurallar
oradan gelir; bu SKILL.md mekanik.

Dosya yoksa dur ve raporla: "Canonical mining prompt bulunamadı — mnemos
repo yolu değişti."

### 2) Argümanları parse et

| Girdi | Davranış |
|---|---|
| `<session.md> <palace-root>` | Tek dosya |
| `--dir <dir> <palace-root>` | Glob `<dir>/*.md`, ledger'ı filtrele |
| `--limit N ...` | İlk N |
| `--all ...` | Tüm unprocessed, pilot yok |

Palace root **mutlak yol** olmalı ve varolmalı (yoksa oluştur: `wings/`
alt-dizinini pre-create et).

**Ledger filtresi:** `state/mined.tsv` dosyasını Read. Format:
```
<session-abs-path>\t<palace-root>\t<drawer-count>\t<ISO-timestamp>
```
İkinci kolondaki palace root AYNI ise (aynı pilot'a tekrar) ledger'lı
session'ları skip et. Farklı palace root ise (yeni pilot, örn. `Mnemos/`
script-mine ama sonra `Mnemos-pilot/` skill-mine başlatıldı) o session'ı
YENIDEN işle (farklı palace'a yazacaksın).

### 3) Palace taxonomy hint üret

Palace root varsa:
- `<palace-root>/wings/` altındaki dizin isimlerini topla (existing wings)
- Her wing altındaki room dizinlerini topla
- Top 20-30 entity (frontmatter'lardan) topla — entity normalization için

Palace boşsa (yeni pilot'un ilk session'ı): hint boş, canonical prompt
yeni wing/room/entity üretir.

Bu hint'i canonical prompt'un `existing palace taxonomy` bölümüne
enjekte et.

### 4) Pilot protokolü

Eğer `--all` DEĞİL ve filtrelenmiş liste > 5 ise:

1. İlk 5'i işle (adım 5)
2. Ara özet:
   ```
   Pilot 5/N tamam. Wing dağılımı: X Mnemos, Y ProcureTrack
   Drawer üretimi: ort 5.4/session, toplam 27
   Hall dağılımı: 12 decisions, 8 events, 5 problems, 2 preferences
   ```
3. Sor: "Devam edeyim mi? (`evet` / `N` ile limit / `dur`)"
4. Yanıta göre sürdür/bitir

Tek dosya, `--limit N` veya `--all` ile çağrıldıysa pilot yok.

### 5) Her refined session için

1. Session `.md`'yi Read
2. Frontmatter parse (`date`, `project`, `tags`)
3. Canonical prompt'un kurallarını uygula (chunk section'lara, hall
   tespiti, wing canonicalize, entity extract, room pick)
4. Her drawer için:
   - Dosya yolu: `<palace-root>/wings/<Wing>/<room>/<hall>/<filename>.md`
   - Ara dizinler yoksa canonical prompt önermiş olduğu yapıda oluştur
   - Write tool ile yaz
5. **🔴 LEDGER APPEND ZORUNLU — session'ı terk etmeden önce en son adım:**
   ```
   <session-abs-path>\t<palace-root>\t<N>\t<ISO-timestamp>
   ```
   Tüm drawer'lar yazıldıktan sonra **bir kez** Bash/Write ile ledger'a
   append et. Bu adım **atlanamaz**. (2026-04-19 real-vault pilot'ta
   skill 3/3 session'da drawer yazdı ama ledger'a 1/3 düştü — uzun
   session'ın sonuna gelince "iş bitti" sanılıp ledger unutulmuş.)
   Self-check: drawer sayın > 0 ise ledger'a yazdın mı? Hayır → YAZ.
6. Tek satır rapor: `OK <session-basename> → N drawers (decisions:X events:Y...)`

**SKIP ise:**
- Ledger'a: `<session-abs-path>\t<palace-root>\t0\tSKIP:<gerekçe>`
  (yine **zorunlu** — orchestrator'ın resume mantığı buna bağımlı)
- Tek satır: `SKIP <session-basename> — <10-kelime gerekçe>`

**Orchestrator fallback (2026-04-19'dan itibaren):** Eğer ledger'a
yazamadıysan (context limit, crash, unutmak), orchestrator palace'ta
`source: <session>` içeren drawer'ı tarar ve filesystem'den drawer
sayısını okur. Bu senin için güvenlik ağı AMA asıl doğru yer ledger —
atlarsan resume bozulur (aynı session'ı tekrar işlersin).

### 6) Final özet

```
İşlenen: N session
Yazılan: M drawer (hall dağılımı: decisions:X events:Y problems:Z preferences:W emotional:V)
Wing dağılımı: Mnemos:A ProcureTrack:B General:C
SKIP: K session
Ledger: <tsv-path>
```

## Ledger format

`state/mined.tsv` — append-only, tab-separated, UTF-8, header yok:

```
<session-abs-path>\t<palace-root>\t<drawer-count>\t<ISO-timestamp-or-SKIP-reason>
```

Örnek:
```
C:\...\Sessions\2026-04-18-v032-group-b.md	C:\...\Mnemos-pilot	5	2026-04-19T14:30:22Z
C:\...\Sessions\2026-04-17-pilot.md	C:\...\Mnemos-pilot	0	SKIP: sadece todo list
```

## Kritik prensipler

- **mnemos API çağrısı YOK.** Drawer'ları Write tool ile dosya sistemi'ne
  yazarsın. `mnemos mine` daha sonra bu drawer'ları index'e alır.
- **LLM API çağrısı YOK.** Tüm iş bu oturumdaki Claude.
- **Canonical prompt kaynağı tek:** `mnemos/docs/prompts/mine-llm.md`.
- **Ledger kalıcı.** Resume için. palace_root'u ikinci kolona yazıyoruz ki
  aynı session farklı pilot palace'larına aynı ledger'dan tekrar
  işlenebilsin.
- **Palace taxonomy stabil.** Varolan wing/room'u yeniden yaratma.
  Refine-transcripts'in ürettiği `project:` field'ı Wing'e giriyor.
- **Skill, script'in tam ikamesi değil — alternatifi.** Pilot kıyaslama
  içindir. Kullanıcı her ikisini de deneyip seçiyor (spec §3 4-kombo).

## Dosya yapısı

```
~/.claude/skills/mnemos-mine-llm/
├── SKILL.md          ← Bu dosya
└── state/
    └── mined.tsv     ← Ledger (oturumlar arası kalıcı, gitignored)
```

## Sorun giderme

- **Palace root yok / yazılamaz** → argümanı kontrol et, absolute path mı?
- **Aynı session 2x işleniyor** → ledger'ın ikinci kolonunda palace root
  farklı mı? Farklıysa kasıtlı; aynıysa ledger bozulmuş demektir.
- **Drawer'lar `General` wing'e düşüyor** → refined session'ların
  `project:` frontmatter'ı boş veya generic olabilir. Refine-transcripts
  canonical prompt'undaki wing mapping tablosunu gözden geçir.
- **H1 title `-` ile başlıyor / bozuk** → canonical prompt'ta smart-title
  kuralı v0.3.2'de düzeltildi; promptu yeniden Read et, eski versiyonu
  cachelemiş olabilirsin.
- **Ledger resume çalışmıyor** → `state/mined.tsv`'yi aç, son satırın
  palace root'u mevcut çağrıyla eşleşiyor mu?
