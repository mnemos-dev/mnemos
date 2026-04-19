---
name: mnemos-compare-palaces
description: >
  Script-mine ve skill-mine'ın aynı pilot session'lar üzerinde ürettiği
  drawer'ları yan yana okur, beş eksende (richness / cleanliness / hall
  accuracy / body readability / wikilink validity) kanıta dayalı
  karşılaştırma yazar. `mnemos mine --pilot-llm` sonrası çalışır,
  pilot rapor dosyasındaki `## Qualitative judgment` placeholder'ını
  doldurur. Kullanıcıya "X kazandı" DEMEZ — kanıt sunar, karar kullanıcıda.
  Tetikler: "/mnemos-compare-palaces", "iki palace'ı karşılaştır",
  "pilot raporunu doldur", "compare palaces". mnemos API ÇAĞIRMAZ,
  LLM API ÇAĞIRMAZ.
---

<!--
INSTALL NOTE (mnemos-dev ≥ v0.4):
Junction/symlink ~/.claude/skills/mnemos-compare-palaces/ → repo canonical
skills/mnemos-compare-palaces/. Refine & mine-llm skill'leriyle aynı pattern.
-->

# Mnemos — Compare Palaces

İki palace root'u (`Mnemos/` ve `Mnemos-pilot/`) okur, drawer'ları aynı
source session bazında eşleştirir, pilot rapor dosyasındaki qualitative
judgment section'ını doldurur.

## Sabitler

- **Canonical compare prompt:** `C:\Projeler\mnemos\docs\prompts\compare-palaces.md`
  (analiz kriterleri, çıktı formatı, kapsam dışı — hepsi orada)

## Tetik örnekleri

- `/mnemos-compare-palaces <script-palace> <skill-palace>`
  — En yeni pilot rapor'u otomatik bul
- `/mnemos-compare-palaces <script-palace> <skill-palace> <report-path>`
  — Belirtilen raporu kullan
- `/mnemos-compare-palaces` — args'sız çağrı: vault'ta `Mnemos/` +
  `Mnemos-pilot/` var mı bak, docs/pilots/*-llm-mine-pilot.md en yenisini
  al; bulamazsan kullanıcıya hangi path'leri vermesi gerektiğini söyle.

## Akış

### 1) Canonical promptu yükle

`C:\Projeler\mnemos\docs\prompts\compare-palaces.md`'yi Read. Analiz
kuralları oradan; bu SKILL.md mekanik.

### 2) Argümanları çöz

| Girdi | Davranış |
|---|---|
| `<script-palace> <skill-palace> [report]` | Path'leri doğrudan kullan |
| args'sız | Vault detect — cwd'de `mnemos.yaml` varsa `vault_path` oradan; yoksa home dir'e git, `OneDrive/Masaüstü/kasamd` gibi olası vault'ları dene. Rapor için `<vault>/docs/pilots/`'da `*-llm-mine-pilot*.md` pattern'ine uyan en yeni dosyayı seç. |

Palace path'lerden biri yoksa (dir yoksa / boşsa) kullanıcıya söyle ve
dur: "`<path>` yok veya boş — önce `mnemos mine --pilot-llm` çalıştır."

Rapor yoksa (vault'ta `docs/pilots/` dizini yok veya uyan dosya yok)
kullanıcıya söyle: "Pilot raporu bulunamadı — önce pilot koş."

### 3) Rapor'u oku

Rapor .md'yi Read. "Per-session outcomes" tablosundan pilot'a giren
session'ları + her birinin OK/SKIP outcome'ını çıkar.

### 4) Üç sample session seç

Uzun + orta + kısa dağılımı için canonical prompt'un seçim kurallarını
uygula. İdeal: her üçü de her iki palace'ta drawer üretmiş olmalı
(OK × 2). Eğer skill-mine'da az OK varsa, hepsini kullan.

### 5) Drawer'ları topla

Her seçilen session için her iki palace'tan drawer'ları topla:

```bash
# script palace drawer'ları
find <script-palace>/wings -name "*.md" -type f | while read drawer; do
    # her drawer'ın frontmatter'ındaki `source:` field'ını çıkar
    # hedef session'a işaret edenleri topla
done
```

Bash yerine Read ile drawer'ı okuyup frontmatter parse etmek daha kolay.
Glob tool ile `<palace>/wings/**/*.md` listele, her birinin ilk 30
satırını oku, frontmatter `source:` alanını çıkar.

Her palace × 3 session için drawer listesi:
- palace'tan kaç drawer geldi
- hangi hall'larda (decisions/events/problems/preferences/emotional)
- entity listesi kalitesi (tag kaçmış mı?)
- H1 başlık + body prose örneği

### 6) Beş eksende analiz + çıktı

Canonical prompt'un şablonuna göre her sample için Richness / Cleanliness
/ Hall accuracy / Body readability / Wikilink validity'yi konkre
örneklerle yaz. Aggregate observation + Trade-offs paragraflarını
şablona göre doldur.

### 7) Rapor'u güncelle

Edit tool ile rapor .md'deki placeholder'ı değiştir:

**Bul:**
```
## Qualitative judgment

*Run `/mnemos-compare-palaces` to populate this section with a drawer-by-drawer
comparison (3 sample sessions side-by-side, richness / cleanliness / hall accuracy /
body readability / wikilink validity). The skill will NOT decide for you — you pick
the mode based on the evidence.*
```

**Yaz:** Yukarıda 4-6. adımlarda ürettiğin 3 sample + aggregate +
trade-offs blocku.

Diğer bölümlere (Quantitative summary, Per-session outcomes, Next step)
**dokunma**.

### 8) Final rapor

Tek satır:
```
Rapor güncellendi: <report-path> (sample: A, B, C)
```

## Kritik prensipler

- **Karar vermeme.** Sen kanıt sunarsın. Kullanıcı seçer.
- **Kanıt göster.** Her ekseni konkre bir drawer örneğiyle destekle;
  "daha iyi" demeyi "session X'te script 4 drawer, skill 2 drawer,
  skill'in biri iki decision'ı birleştirmiş" ile değiştir.
- **Edit-in-place, dokunulmaz sections.** Quantitative summary
  pilot orchestrator'dan gelir — dokunma. Per-session outcomes
  tablosu OK sayılarına göre doğru — dokunma.
- **mnemos API çağrısı YOK, LLM API çağrısı YOK.**

## Dosya yapısı

```
~/.claude/skills/mnemos-compare-palaces/
└── SKILL.md          ← Bu dosya
```

Ledger yok — bu skill one-shot, idempotent değil (tekrar koşarsa aynı
rapor'u tekrar fill eder — placeholder artık orada olmadığı için
section'ı tanır ve update eder; Edit tool'un robustness'ına güvenir).

## Sorun giderme

- **Placeholder bulunamadı** → Rapor bu skill'den önce manuel edit
  edilmiş veya farklı formatta. Canonical prompt'un `## Qualitative
  judgment` header'ını arayıp o section'ı replace et.
- **Drawer'larda `source:` field yok** → v0.3.2 öncesi drawer'lar olabilir.
  Filename prefix'i (tarih) veya wikilink satırından session basename'i
  çıkar.
- **Sample session hepsi skill-mine'da SKIP olmuş** → Aggregate
  observation'a bunu yaz — "skill-mine N session'ın M'sini SKIP'ledi;
  bu önemli sinyal — pilot'u daha fazla session'la tekrar düşün."
