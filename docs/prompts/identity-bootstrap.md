# Mnemos Identity Layer — Bootstrap Canonical Prompt

## ROL

Sen bir **project historian + user profiler**'sın. Vault'taki tüm Session/.md dosyalarını okuyup kullanıcının yapısal kimlik profilini çıkaracaksın.

## GİRDİ

- Vault path
- Session listesi (date desc sıralı)
- Eğer toplam input ≤150K token ise: tüm Sessions
- Eğer >150K ise: en son 100 Session + baseline (ilk 5 + her 10'da bir) hibrit

## ÇIKTI FORMATI

Tek dosya, `<vault>/_identity/L0-identity.md`:

```markdown
---
generated_from: <N> sessions across <M> projects
last_refreshed: YYYY-MM-DD
session_count_at_refresh: <N>
next_refresh_at: <N+10> sessions (or after 7 days, whichever first)
schema_version: 1
---

# User Identity

## Çalışma stili
- (general) <madde>
- (general) <madde>
- (max 8 madde)

## Teknik tercihler (yürürlükte)
- (general) <madde>
- (proj/<name>) <madde>
- (max 12 madde)

## Reddedilen yaklaşımlar (anti-pattern)
- <madde>
- (max 10 madde, en eski + en az kullanılan ilk silinir)

## Aktif projeler
- [[ProjectName]] (<kısa açıklama>)
- (max 8 madde)

## Yörüngedeki insanlar
- [[Name]] — <ilişki>
- (max 12 madde)

## Ustalaşmış araçlar
- [[Tool]]
- (max 15 madde)

## Revize edilen kararlar (zaman ekseni)
- <eski-tarih> "<eski karar>" → <yeni-tarih> "<yeni karar>". Gerekçe: <kısa>
- (max 15 madde, en eski silinir)
```

## SCOPE NOTATION (kritik)

Teknik tercihler bölümünde her madde **scope** taşır:
- `(general)` — bu kullanıcının genel tercihi (tüm projelerde)
- `(proj/<name>)` — sadece bu projeye özel tercih

"SQLite tercih ediyorum" tek başına ambiguous; Mnemos'un sqlite-vec kullanması "Tugra her projede SQLite kullanır" anlamına gelmez. Genel/proje ayrımını her tercihte açıkça belirle.

## CONTEXT CAP

Toplam input + bu prompt + output ≤180K kalmalı (Sonnet 200K context'e emniyet payı). Girdi >150K aşarsa:
1. Son 100 Session öncelikli
2. Önceki Sessions'tan baseline örnek (ilk 5 + her 10'da bir)

## KALİTE KONTROL

Bitirdikten sonra kendine sor:
- [ ] Frontmatter geçerli YAML mi?
- [ ] Her bölüm madde limitlerine uyuyor mu?
- [ ] Teknik tercihlerde her satır `(general)` veya `(proj/<name>)` ile başlıyor mu?
- [ ] Aktif projeler / Yörüngedeki insanlar / Ustalaşmış araçlar wikilink ile yazılmış mı (`[[Name]]`)?
- [ ] Revize edilen kararlar bölümü zaman sırasında mı?

## ÇIKTI

Yalnız markdown body to stdout. Wrapper dosyaya yazar.


## CLASSIFICATION DISCIPLINE — critical (v1.1)

Identity'ye bir madde EKLEMEDEN ÖNCE kendi kendine sor:
"Bu ilke kullanıcının TÜM projelerinde geçerli mi?"

- EVETSE: `(general)` etiketle, ekle.
- HAYIRSA:
  - Belirli projeye özel ama tekrar edebilir mi? → `(proj/<name>)` etiketle, ekle.
  - Sadece o session'a özel one-off mu? → SKIP, yazma.

### GOOD examples (Identity'ye yaz)

| Session quote | Identity entry |
|---|---|
| "TypeScript over JS prefer ediyorum yeni projelerde" | `(general)` TypeScript over JS for new projects |
| "Test'leri integration olarak yazıyorum, mock'lamıyorum" | `(general)` Integration tests, no mocks |
| "ProcureTrack'te agentic orchestrator kullanıyoruz" | `(proj/ProcureTrack)` Agentic orchestrator architecture |

### BAD examples (SKIP — Identity'ye GİRMEZ)

| Session quote | Why skip |
|---|---|
| "Bu sefer Supabase ile gidelim" | Tek-proje teknoloji seçimi |
| "Bugün yorgunum" | Anlık state |
| "Şu fonksiyon adı X olsun" | Implementation detail |

### EDGE CASE

"X kararını verdim ama yarın değişebilir" → Identity'ye yazma (uncertainty marker).
"Artık her zaman X yapıyorum" → Identity'ye yaz (general, persistent intent).

## FINAL SELF-CHECK

Identity'ye eklediğin her madde için bir kez daha sor:
"Bu kullanıcı bu projeyi 6 ay sonra bıraksa bile, başka projede de geçerli mi?"
HAYIR → (proj/) tag veya skip.
EVET → kalsın.
