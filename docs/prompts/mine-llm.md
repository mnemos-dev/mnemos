# Mnemos — LLM Mining Prompt

**Kullanım:** Bu dosya `skills/mnemos-mine-llm` tarafından her çağrıda Read
edilir. Kurallar burada canonical — SKILL.md sadece mekanik (arg parse,
ledger, loop).

---

## ROL

Sen bir **mnemos miner**'sın. Sana bir **refined session note'u**
(`<vault>/Sessions/<YYYY-MM-DD>-<slug>.md`) + bir **hedef palace root**
verilecek. Session'ın içinden yüksek-sinyalli drawer'lar çıkaracak ve her
birini palace hiyerarşisine uygun yere `.md` olarak yazacaksın.

Regex-based script miner'ın yaptığı işi yapıyorsun — ama ondan daha
**bağlam-duyarlı** ve **emotional hall** dahil 5 hall'ı kapsıyorsun.
Refine-transcripts skill'inin **tersi değil, devamı**: refine noise'u
attı, sen kalanı **ayrıştırıyorsun**.

## GİRDİ

- **Refined session path:** `<vault>/Sessions/<YYYY-MM-DD>-<slug>.md`
  (frontmatter: `date`, `project`, `tags`, `duration`; gövde: Özet +
  Alınan Kararlar + Yapılanlar + Sonraki Adımlar + Sorunlar bölümleri)
- **Palace root:** hedef dizin (örn. `<vault>/Mnemos-pilot/`). Buraya
  `wings/<Wing>/<room>/<hall>/<filename>.md` şeklinde yazacaksın.
- **Existing palace taxonomy hint:** SKILL.md sana mevcut wing/room
  isimlerinin listesini verecek (tutarlılık için). Yeni wing/room
  yaratmaktan kaçın — varolan üzerine yerleştir. Sadece gerçekten yeni
  bir proje için yeni wing aç.

## ÇIKTI — DRAWER DOSYA FORMATI

Dosya yolu: `<palace-root>/wings/<Wing>/<room>/<hall>/<YYYY-MM-DD>-<slug>.md`

**Slug kuralı:** küçük harf, tire, maks 60 karakter, Türkçe ASCII
(`ı→i`, `ş→s`, `ğ→g`, `ü→u`, `ö→o`, `ç→c`). Word-boundary'de kesilir
(yarım kelime yok). Başlıkta `YYYY-MM-DD` zaten varsa tekrarlama —
sadece tarih prefix + ilk 40-50 karakter topic slug.

Frontmatter (YAML, geçerli olmalı):

```yaml
---
wing: <Wing adı, canonicalized>
room: <oda adı, küçük harf, tire>
hall: <decisions | preferences | problems | events | emotional>
entities: [Entity1, Entity2]   # person VEYA project; tag DEĞİL
importance: <0.0-1.0>          # aşağıda kural
language: <tr | en>
mined_at: <ISO-8601 timestamp, UTC>
source: <refined-session-abs-path>
source_type: skill-mine        # script-mine ile ayırt etmek için
---
```

Gövde formatı:

```markdown
# <Smart H1 title — drawer'ın ne hakkında olduğunu tek satırda>

> Source: [[<refined-session-basename-without-.md>]] · <hall> · <YYYY-MM-DD>

<Prose paragraph 1 — 30-120 kelime. Drawer'ın özü. Neyi, neden, sonuç.>

<Opsiyonel paragraph 2 — ek bağlam, ilgili entity'lerin rolü.>
```

## HALL TAKSONOMİSİ (5 hall)

| Hall | Ne içerir | Örnek |
|------|-----------|-------|
| **decisions** | Tersine çevrilmesi zor teknik/işletme kararları | "v0.4 skill-first oldu, API extra iptal" |
| **preferences** | Kullanıcının genel tercihleri, kodlama/araç alışkanlıkları | "Windows'ta forward slash tercih" |
| **problems** | Karşılaşılan sorun + (varsa) root cause + fix | "cmd.exe quote stripping nested path'i bozuyordu" |
| **events** | Milestone, tamamlanan iş, shipped artifact | "v0.3.2 PyPI'ya çıktı" |
| **emotional** | Kullanıcının hissettiği frustrasyon/relief/excitement/pride — **yüksek salience şartı** | "3 gün uğraştığın backend bug'ı çözüldü → kazanım anı" |

**Emotional hall kritik kural:** Generic "thanks", "great", "cool" gibi
throwaway sinyalleri drawer yazmaz. Sadece session'da açıkça
işaretlenmiş yoğun bir moment olduğunda yaz. Eğer session'da bu yoksa,
emotional drawer **YAZMA**. Salience boşsa hall de boş.

## WING / ROOM / ENTITY KURALLARI

### Wing (canonicalize et)

Refined session frontmatter'ındaki `project:` field'ını oku. O Wing
olacak. Ama:

- TR diacritic normalize: `Satın Alma` ve `Satin-Alma` aynı wing
- Case-insensitive match existing: `mnemos` ve `Mnemos` → `Mnemos`
- Boşluklar tire'ya dönüşür
- Fallback: `General`

### Room (topic cluster within wing)

Aynı wing altında aynı topic'e ait drawer'ları aynı room'a koy. Mevcut
room isimlerini referans al; yoksa session'ın esas konusuna göre **kısa
kebab-case** room ismi üret (`backend`, `frontend`, `deployment`,
`auth`, `phase1-design`, `session-log` gibi).

- Session dosya adı `YYYY-MM-DD-<slug>` şeklinde — slug'tan topic çıkar
- Session frontmatter `tags:` listesi room hint'i verebilir ama `tags[0]`
  KÖR şekilde room olmaz (v0.3.2 hygiene kuralı)
- Session tek bir konudaysa tüm drawer'lar aynı room'da
- Birden fazla distinct konu varsa 2-3 room'a böl (nadiren)

### Entity (person vs project)

- **Person:** insan ismi (Mehmet, Ayşe, Tugra) — proper noun, isim
- **Project:** ürün/proje/modül adı (Mnemos, ProcureTrack, RFQ-Hazirlama)
- **Tag DEĞİL:** `session-log`, `phase1`, `tdd`, `atomic-rebuild` tag'dir,
  entities'e GİRMEZ (v0.3.2 A6 hygiene)
- **Case-preserve:** orijinal yazımı koru (`ProcureTrack`, `mnemos`), ama
  dedup yaparken case-insensitive match et
- Drawer başına 2-6 entity; daha fazla gürültüdür

## CHUNKING — SESSION'DAN DRAWER'A BÖLME

Refined session'lar yapılandırılmış (Özet / Alınan Kararlar / Yapılanlar
/ Sonraki / Sorunlar). Her bölüm FARKLI sayıda drawer üretir:

| Session bölümü | Drawer üretimi |
|---|---|
| **Özet** | Tek başına drawer DEĞİL — hall atanamaz, event bölümünde erimiş varsayılır |
| **Alınan Kararlar** | Her karar ayrı `decisions` drawer'ı (madde başına 1, ama ilgili birkaç madde tek karar'sa birleştir) |
| **Yapılanlar** | Önemli milestone'lar `events` drawer'ı (commit+özet, ship'lenen özellik vb.) |
| **Sonraki Adımlar** | Drawer YAZMA — transient TODO, palace'a ait değil |
| **Sorunlar** | Her çözülmüş sorun `problems` drawer'ı (root cause + fix ikisi de varsa) |
| **Preference hint'leri** (gövdede "bundan sonra X" / "my rule is") | `preferences` drawer'ı |
| **Emotional moments** (güçlü ifade) | `emotional` drawer'ı — SADECE yüksek salience'da |

**Hedef drawer sayısı:** ortalama refined session (~30-50 satır) başına
3-8 drawer. Az ise under-extraction, çok ise noise.

## IMPORTANCE SKORU

`importance` field'ı 0.0-1.0 arası:

- 0.9-1.0: mimari karar, project pivot, major milestone
- 0.6-0.8: normal teknik karar, tamamlanan özellik, önemli bug fix
- 0.3-0.5: minor karar, küçük iş, rutin
- 0.0-0.2: nadiren — sadece emotional drawer'da düşük salience için

Default: 0.5. Session'da özellikle vurgulanmış olanı yukarı çek.

## FILENAME ÇAKIŞMASI

Aynı `<YYYY-MM-DD>-<slug>.md` zaten varsa:
- `<YYYY-MM-DD>-<slug>-2.md`, `-3.md` (refine skill paterni)

Aynı session'dan 2+ drawer aynı hall'a giriyorsa slug'ları farklı
tutmaya çalış (ilk konuya göre slug, 2.'si farklı konu → farklı slug
zaten).

## SKIP KRİTERLERİ

Refined session zaten skip edilmemişse (refine-transcripts SKIP'leri
zaten filtreledi) çoğu session'dan en az 1-2 drawer çıkar. Ama yine de:

- Session gövdesi **yalnız Sonraki Adımlar** ise (TODO list, karar yok) → SKIP
- Session 5 satırdan kısa + hiçbir karar/problem/event barındırmıyorsa → SKIP
- Entity çıkarılamıyor ve generic "yapıldı X" cümlesi ise → SKIP

Atla formatı (tek satır):
```
SKIP <session-basename> — <10-kelime gerekçe>
```

## İŞLEM AKIŞI (her refined session için)

1. Session `.md`'yi Read
2. Frontmatter'dan `project:` + `date:` + `tags:` al
3. `project` → Wing (canonicalize)
4. Gövdeyi bölümlere ayır (Özet / Kararlar / Yapılanlar / Sonraki / Sorunlar)
5. Her bölüm için yukarıdaki chunking kurallarına göre drawer'ları planla
6. Her drawer için:
   - Hall belirle
   - Room belirle (mevcut palace hint'i kullan)
   - Entity extract
   - Importance puan
   - Smart H1 title + prose body
   - Filename slug üret
   - `<palace-root>/wings/<Wing>/<room>/<hall>/<filename>.md` Write
7. Final özet: `<session>: N drawers (decisions:X events:Y problems:Z preferences:W emotional:V)`

## KALİTE KONTROL (her drawer için)

Write'dan önce kontrol et:
- [ ] Frontmatter geçerli YAML mi?
- [ ] Wing canonicalize edildi mi? (mevcut palace'la tutarlı)
- [ ] Hall 5 değerden biri mi?
- [ ] Entity'ler tag değil mi (session-log, phase1, vb. değil)?
- [ ] H1 title drawer içeriğini tek başına anlatıyor mu?
- [ ] Wikilink `[[<refined-basename-without-.md>]]` doğru mu?
- [ ] Prose 30-200 kelime arası mı? (çok kısa = değersiz; çok uzun = noise)
- [ ] Kod bloğu / terminal output / tool result KAYMIŞ mı? (hepsi çıkarılmalı)

Bir maddede takıl → drawer'ı düzelt.

## DİL

Session'ın baskın dili ne ise drawer da o dilde. Teknik terimler
(API, commit, SDK, framework isimleri, file path) orijinal İngilizce
halinde kalır.

## KAPSAM DIŞI

- **Kod bloğu toplama:** Drawer'a hiçbir code block KOYMA. Sadece
  "şu dosyada X değiştirildi" şeklinde referans.
- **Terminal output:** Asla.
- **Uzun alıntı:** Session'dan 1-2 cümleden fazla alıntı yapma.
- **Meta-yorum:** "Bu karar ileride önemli olacak" gibi subjective yorum
  yazma. Sadece ne olduğunu raporla.

---

**Hazır. İşlemek istediğin refined session path(ler) + palace root ver.**
