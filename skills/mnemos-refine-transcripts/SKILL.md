---
name: mnemos-refine-transcripts
description: >
  Claude Code JSONL transcript'lerini (~/.claude/projects/) Mnemos vault'una
  yüksek-sinyalli Sessions/<YYYY-MM-DD>-<slug>.md notu olarak refine eder.
  Tetikler: "/mnemos-refine-transcripts", "transcript refine et",
  "JSONL'leri özetle ve Sessions'a yaz", "ham log'ları işle",
  "Claude Code history'i vault'a aktar", "unprocessed transcriptleri işle".
  mnemos API ÇAĞIRMAZ, LLM API ÇAĞIRMAZ — iş bu oturumdaki Claude tarafından yapılır.
---

<!--
INSTALL NOTE (mnemos-dev ≥ v0.3):
Bu skill makineye-özel path'ler kullanıyor. Kurulum:

1. Bu klasörü ~/.claude/skills/mnemos-refine-transcripts/ altına kopyala
   (veya symlink/junction et — repo canonical, junction drift olmamalı).
2. Aşağıdaki "Sabitler" bölümündeki path'leri kendi sistemine göre düzenle:
   - mnemos kurulum yolu (canonical prompt + extractor buradan okunur)
   - Claude Code transcripts kök klasörü (~/.claude/projects/)
   - Obsidian vault Sessions/ yolu
   - Ledger yolu (skill state)

v0.3'te `mnemos init` wizard'ı bu path'leri çoğunlukla resolve ediyor;
manuel edit hâlâ bazı non-standart kurulumlar için gerekli olabilir.
Otomatik hook kurulumu için `mnemos install-hook` kullan.
-->

# Mnemos — Refine Transcripts

JSONL transcript → refined `Sessions/*.md` dönüşümü. Kurallar tek bir kaynakta
tutulur; bu skill sadece **keşif + ledger + yazma** mekaniği sağlar.

## Sabitler

- **Canonical refinement prompt:** `C:\Projeler\mnemos\docs\prompts\refine-transcripts.md`
  (çıktı formatı, wing mapping, SKIP kriterleri, filtre kuralları hep burada)
- **Prose extractor:** `C:\Projeler\mnemos\scripts\extract_jsonl_prose.py`
- **Transcript kök:** `C:\Users\tugrademirors\.claude\projects\`
- **Vault Sessions:** `C:\Users\tugrademirors\OneDrive\Masaüstü\kasamd\Sessions\`
- **Ledger:** `C:\Users\tugrademirors\.claude\skills\mnemos-refine-transcripts\state\processed.tsv`

## Tetik örnekleri

- `/mnemos-refine-transcripts` — unprocessed taraması, pilot modu
- `/mnemos-refine-transcripts <path.jsonl>` — tek dosya
- `/mnemos-refine-transcripts <dir>` — dir altındaki tüm JSONL
- `/mnemos-refine-transcripts --limit 5` — pilot batch
- `/mnemos-refine-transcripts --all` — tüm unprocessed, soru sormadan
- `/mnemos-refine-transcripts --include-subagents` — subagent JSONL'lerini de dahil et (default: hariç)

## Akış

### 1) Canonical promptu yükle

Her çalıştırmada ilk iş: `C:\Projeler\mnemos\docs\prompts\refine-transcripts.md`'yi
Read ile oku. Kurallar oradan gelir — bu SKILL.md kuralları yeniden yazmaz.

Dosya yoksa kullanıcıya söyle ve dur: "Canonical refinement prompt bulunamadı.
Muhtemelen mnemos repo yolu değişti — beni güncelle."

### 2) Transcript listesini çıkar

Argümana göre:

| Girdi | Davranış |
|---|---|
| `<path.jsonl>` | Tek dosya |
| `<dir>` (klasör) | Glob `<dir>/**/*.jsonl` |
| argsız / `--unprocessed` | Glob `~/.claude/projects/**/*.jsonl`, ledger'ı filtrele |
| `--limit N` | İlk N tane |
| `--all` | Tüm unprocessed, pilot atla |

**Ledger filtresi:** `state/processed.tsv` dosyasını Read ile oku. Her satır
`<abs-path>\t<OK|SKIP>\t<meta>` formatında. İlk kolondaki path'ler listede ise
bu çağrıda tekrar işleme.

Dosya yoksa henüz hiç işlem yok demektir — filtre boş set.

**Subagent filtresi (default ON):** Path'inde `/subagents/` veya `\subagents\`
geçen JSONL'leri atla — bunlar kullanıcıyla değil parent session'ın alt-görevleriyle
konuşulan transcript'lerdir, kalıcı değer nadirdir. Geri almak için
`--include-subagents` bayrağı.

### 3) Pilot protokolü

Eğer `--all` DEĞİL ve filtrelenmiş liste > 5 ise:

1. İlk 5'i işle (adım 4-5)
2. Ara özeti göster:
   ```
   Pilot 5/N tamam. Wing dağılımı: X Mnemos, Y ProcureTrack, ...
   SKIP oranı: K/5
   Örnek yazılan dosya: <ilk OK filename>
   ```
3. Sor: "Devam edeyim mi? (`evet` / `N` ile limit / `dur`)"
4. Yanıta göre devam/bitir

Tek dosya, dir veya `--limit N` ile çağrıldıysa pilot yok — direkt işle.

### 4) Her transcript için

```bash
PYTHONUTF8=1 python "C:/Projeler/mnemos/scripts/extract_jsonl_prose.py" "<abs-path>"
```

Stdout digest. **Fast-path:** Digest header'ında `User turns detected: 0`
görürsen canonical prompt'u değerlendirmeye gerek yok — otomatik SKIP ("boş
transcript, 0 user turn"), ledger'a yaz, sonraki dosyaya geç.

Aksi halde digest'i canonical prompt'un kurallarıyla değerlendir:

- **SKIP ise** (prompt'taki kriterler):
  - Tek satır rapor: `SKIP <basename> — <kısa gerekçe>`
  - Ledger'a yaz: `<abs-path>\tSKIP\t<gerekçe>`
  - Dosya YAZMA
- **Değerli ise:**
  - Dosya yolu: `<vault>/Sessions/<YYYY-MM-DD>-<slug>.md`
  - Slug kuralı prompt dosyasındaki gibi (küçük harf, tire, Türkçe→ASCII, max 60)
  - **Collision check:** Aynı slug+tarih varsa sonuna `-2`, `-3` ekle
  - Write tool ile yaz
  - Tek satır rapor: `OK <filename> — <wing>, ~N satır`
  - Ledger'a yaz: `<abs-path>\tOK\t<filename>`

### 5) Ledger append

Her dosya sonrası ledger'a ekle. Dosya yoksa oluştur. Format:
```
<abs-path>\t<OK|SKIP>\t<filename-or-reason>
```

Header yok. Tab-separated. UTF-8.

**Önemli:** Ledger'ı batch sonunda değil her transcript sonunda güncelle —
oturum yarıda kesilirse resume için.

### 6) Final özet

Prompt'taki format:
```
İşlenen: N transcript
Yazılan: M dosya (wing dağılımı: X Mnemos, Y ProcureTrack, ...)
Atlanan: K (kısa: A, sonuçsuz: B, duplicate: C, ...)
Ledger: <tsv-path>
```

## v1.0 Tag/Wikilink Hibrit Kuralları

Her Session frontmatter'ında 5-prefix tag kategorisi ve prose'da entity wikilink üretiriz. Detaylı kurallar `docs/prompts/refine-transcripts.md`'de:
- TAG PREFIX KATEGORİLERİ
- PROSE İÇİNDE WIKILINK
- KALİTE KONTROL checklist

Refine sırasında bu üç bölümü canlı referans olarak kullan.

## Kritik prensipler

- **mnemos API çağrısı YOK.** Refinement = Claude Code oturumunda yapılan
  preprocess. Çıktı sadece dosya yazımı. (Kullanıcı ayrıca
  `mnemos mine` çalıştırırsa yazılan Sessions/ dosyaları vault'a gider.)
- **LLM API çağrısı YOK.** Her şey bu oturumdaki Claude.
- **Canonical prompt kaynağı tek:** `mnemos/docs/prompts/refine-transcripts.md`.
  Kural değişikliği orada yapılır, burada değil.
- **Ledger kalıcı.** `state/processed.tsv` silinmedikçe aynı JSONL tekrar işlenmez.
- **Skip de kaydedilir.** İki kere değer yok denilmesin.

## Dosya yapısı

```
~/.claude/skills/mnemos-refine-transcripts/
├── SKILL.md          ← Bu dosya
└── state/
    └── processed.tsv ← Ledger (oturumlar arası kalıcı)
```

## Sorun giderme

- **Extractor Unicode hatası** → `PYTHONUTF8=1` prefix'i atlanmış olabilir
- **Path boşluk içeriyor** → Bash çağrısında tırnakla sar
- **Slug Türkçe karakter sızdırdı** → prompt dosyasındaki ASCII tablosunu tekrar uygula
- **Ledger bozuldu / baştan başlamak istiyorum** → `processed.tsv`'yi sil, yeniden çağır
