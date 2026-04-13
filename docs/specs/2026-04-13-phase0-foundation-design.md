# Phase 0 — Foundation Design Spec

**Date:** 2026-04-13
**Status:** Approved
**Goal:** API kullanmadan MemPalace ile esit recall (%96+) yakalamak.
API (Phase 1) sadece %96'nin ustune cikmak icin kullanilacak.

---

## Background

### Neden %96 degil?

Mnemos v0.1 **lossy mining** yapiyor:
- Dosyalari paragraflara boluyor, regex ile siniflandiriyor, sadece fragment'lari sakliyor
- Orijinal baglam (conversation akisi, soru-cevap iliskisi) kayboluyor
- Mining pattern'lari yetersiz: EN 25 pattern, TR 24 pattern (MemPalace: 115+)
- Room detection: sadece dosya adi + ilk H2 (MemPalace: 72 pattern)
- Entity detection: sadece CamelCase (MemPalace: heuristic scoring)
- Conversation format destegi yok (MemPalace: 5 format)

### MemPalace %96'yi nasil yakaliyor?

3 temel sac ayagi — hicbiri API gerektirmiyor:
1. **Raw verbatim storage** — dosyanin tamami ChromaDB'de korunuyor
2. **Exchange-pair chunking** — soru+cevap birlikte chunk'laniyor, baglam korunuyor
3. **Metadata filtering** — wing/room ile arama alani daraltiliyor (+%34 iyilestirme)

### Strateji

```
Phase 0: API'siz %96+ recall
  0.1 + 0.3  Raw storage + dual collection
  0.2        Metadata filtering guclendirme
  0.5        Conversation format normalizer
  0.6        Mining engine guclendirme (API'siz)
  0.7        Benchmark (LongMemEval) — %96 hedefi

Phase 1: API ile %96'nin ustune cik
  1.1  LLM mining (regex'in yakalayamadiklarini yakala)
  1.2  LLM reranking
  1.3  Contradiction detection
  1.4  Benchmark tekrari — %100 hedefi
```

---

## 0.1 + 0.3: Raw Verbatim Storage + Dual Collection

### Tasarim

Mevcut tek collection yerine iki ChromaDB collection:

```
ChromaDB
├── mnemos_raw       ← orijinal dosya tam metin (verbatim, kayipsiz)
└── mnemos_mined     ← cikarilmis fragment'lar (mevcut yapi)
```

### mnemos_raw Collection

- Mine edilen her dosyanin **tam icerigi** tek dokuman olarak saklanir
- Dosya buyukse chunk'lanir (ChromaDB embedding limiti ~8191 token / ~30K karakter)
  - Chunk'lar arasi overlap ile baglam korunur
  - MemPalace yaklasimi: 800 char chunk, fazlasi sonraki chunk'a tasar, hicbir sey atilmaz
- Metadata: `wing`, `room`, `source_path`, `language`, `mined_at`, `chunk_index` (chunk varsa)
- Document ID: `raw-<source_path_hash>` (veya chunk varsa `raw-<hash>-<chunk_index>`)

### mnemos_mined Collection

- Mevcut `mnemos_drawers` collection'i `mnemos_mined` olarak yeniden adlandirilir
- Mevcut davranis aynen devam eder
- Yeni metadata: `raw_id` (iliskili raw dokumana referans)

### SearchEngine Degisiklikleri

```python
class SearchEngine:
    COLLECTION_RAW = "mnemos_raw"
    COLLECTION_MINED = "mnemos_mined"

    def __init__(self, config, in_memory=False):
        self._raw = client.get_or_create_collection(COLLECTION_RAW, ...)
        self._mined = client.get_or_create_collection(COLLECTION_MINED, ...)

    def index_raw(self, doc_id, text, metadata):
        """Tam dosya icerigini raw collection'a yaz."""

    def index_drawer(self, drawer_id, text, metadata):
        """Fragment'i mined collection'a yaz (mevcut davranis)."""

    def search(self, query, ..., collection="both"):
        """
        collection="raw"   -> sadece raw'da ara
        collection="mined" -> sadece mined'da ara
        collection="both"  -> ikisinde de ara, skorla birlestir, dedup
        """
```

### Miner / Server Degisiklikleri

- `handle_mine()`: once `index_raw()` ile tam icerigi sakla, sonra fragment'lari `index_drawer()` ile sakla
- `mnemos_search` tool'u: Yeni `collection` parametresi (default: "both")
- Mevcut drawer .md dosyalari Obsidian'da aynen kalir — raw collection sadece ChromaDB'de

### Migration

- Mevcut `mnemos_drawers` collection varsa silinip `mnemos_mined` olarak yeniden olusturulur (alpha, kullanici uyarilir)
- Mevcut mine edilen dosyalar icin raw collection bos baslar
- `mnemos mine --rebuild` komutu: mine_log sifirlanir, tum kaynaklar tekrar taranir, hem raw hem mined doldurulur
- Rebuild islemi mevcut drawer .md dosyalarini silmez — ayni icerik upsert ile guncellenir

---

## 0.2: Metadata Filtering Guclendirme

### Iyilestirmeler

1. **`$in` destegi**: Birden fazla wing/room/hall'de arama
   ```python
   # ProcureTrack VEYA GYP wing'inde ara
   search(query, wing=["ProcureTrack", "GYP"])
   ```
   - Parametreler `str | list[str]` kabul eder
   - Tek deger: `{"wing": "X"}` (mevcut)
   - Liste: `{"wing": {"$in": ["X", "Y"]}}` (yeni)

2. **Hall-only filter**: Wing belirtmeden hall bazli arama (zaten calisiyor, test eksik)

3. **Negative filter**: Belirli wing/room'u haric tutma
   ```python
   search(query, exclude_wing="General")
   ```

---

## 0.5: Conversation Format Normalizer

### Amac

MemPalace 5 conversation formatini destekliyor. Biz de ayni formatlari markdown'a cevirip mevcut pipeline'a verecegiz.

### Desteklenecek Formatlar

| Format | Kaynak | Dosya Tipi |
|--------|--------|------------|
| Claude Code JSONL | `~/.claude/projects/*/conversations/` | `.jsonl` |
| Claude.ai JSON | claude.ai export | `.json` |
| ChatGPT JSON | chatgpt.com export | `.json` |
| Slack JSON | Slack workspace export | `.json` |
| Plain text | Herhangi bir text | `.txt`, `.md` |

### Cikti Formati

Tum formatlar standart transcript'e donusturulur:

```markdown
> user message here
assistant response here

> next user message
assistant response
```

### Modul Yapisi

```python
# mnemos/normalizer.py

def normalize_file(filepath: Path) -> str:
    """Dosya formatini tespit et ve standart transcript'e cevir."""

def _try_claude_code_jsonl(text: str) -> str | None:
    """Claude Code JSONL formatini parse et.
    - tool_use/tool_result mesajlarini birlestir
    - ardisik assistant mesajlarini birlestir
    """

def _try_chatgpt_json(text: str) -> str | None:
    """ChatGPT export formatini parse et.
    - mapping tree yapisini traverse et
    - role + content cikar
    """

def _try_slack_json(text: str) -> str | None:
    """Slack export formatini parse et.
    - Speaker degisimlerinde role ata
    """

def _try_plain_text(text: str) -> str:
    """Fallback: markdown/text olarak birak."""
```

### Tool result truncation (MemPalace yaklasimi)

- Bash output: ilk 20 + son 20 satir
- Grep/Glob: ilk 20 sonuc
- Diger: 2048 byte

### Entegrasyon

- `mnemos mine` komutu `.jsonl` ve `.json` dosyalarini da kabul eder
- Miner once normalizer'dan gecirir, sonra mevcut pipeline'a verir
- `--format` flag: otomatik tespit yerine format belirtme (opsiyonel)

---

## 0.6: Mining Engine Guclendirme (API'siz)

### 0.6.1: Exchange-Pair Chunking

Mevcut: Paragraf bazli bolme (baglam kayboluyor)
Yeni: Conversation transcript'lerde soru+cevap birlikte chunk'lanir

```python
def chunk_exchanges(transcript: str, chunk_size: int = 800) -> list[str]:
    """Transcript'i exchange pair'lerine bol.

    - '>' ile baslayan satirlar user turn
    - Sonraki satirlar assistant response
    - Bir exchange chunk_size'i asarsa, response parcalanir
      ama user sorusu her zaman ilk chunk'ta kalir
    - Hicbir sey atilmaz — her karakter korunur
    """
```

Fallback: Conversation olmayan dosyalarda mevcut paragraf chunking devam eder.

### 0.6.2: Room Detection (72 Pattern)

Mevcut: Dosya adi + ilk H2 heading
Yeni: MemPalace'in 72 folder/filename pattern'ini + icerik keyword scoring'ini ekle

```yaml
# mnemos/patterns/rooms.yaml
rooms:
  frontend:
    folders: [frontend, front-end, client, ui, views, components, pages]
    keywords: [react, vue, angular, css, html, dom, render, component]
  backend:
    folders: [backend, server, api, routes, services, controllers, models, database, db]
    keywords: [endpoint, middleware, query, schema, migration, orm]
  planning:
    folders: [planning, roadmap, strategy, specs, requirements]
    keywords: [plan, roadmap, milestone, deadline, priority, sprint, scope, spec]
  decisions:
    folders: [decisions, adrs]
    keywords: [decided, chose, picked, switched, migrated, trade-off, approach]
  problems:
    folders: [issues, bugs]
    keywords: [problem, issue, broken, failed, crash, stuck, workaround, fix]
  meetings:
    folders: [meetings, calls, meeting_notes, standup, minutes]
    keywords: [meeting, call, standup, discussed, attendees, agenda]
  # ... 13 kategori toplam (MemPalace ile ayni)
```

Algoritma:
1. Dosya yolundaki klasor isimlerini pattern'larla esle
2. Eslesme yoksa: ilk 3000 karakterde keyword scoring
3. En yuksek skorlu room sec
4. Hala eslesme yoksa: "general"

### 0.6.3: Heuristic Entity Detection

Mevcut: Sadece CamelCase regex
Yeni: MemPalace'in iki-pasli heuristic yaklasimi

```python
# mnemos/entity_detector.py

class EntityDetector:
    """API'siz entity tespit — heuristic scoring."""

    # 200+ stopword (common words, programming keywords)
    STOPWORDS = {...}

    def detect(self, text: str) -> dict:
        """Return {persons: [...], projects: [...], uncertain: [...]}"""

    def _pass1_candidates(self, text: str) -> list[str]:
        """3+ kez gecen buyuk harfli kelimeleri bul, stopword filtrele."""

    def _pass2_classify(self, candidate: str, text: str) -> tuple[str, float]:
        """
        Person sinyalleri (agirlikli):
          - Diyalog: '> Speaker:', 'Speaker said' (x3)
          - Eylem: said, asked, told, thinks, wants (x2)
          - Zamir yakinligi: 3 satir icinde he/she/they (x2)
          - Dogrudan hitap: 'hey Name', 'thanks Name' (x4)

        Project sinyalleri (agirlikli):
          - Fiiller: building, shipped, deployed (x2)
          - Mimari: 'Name architecture', 'Name pipeline' (x2)
          - Versiyon: 'Name v2', 'Name-core' (x3)
          - Kod: 'import Name', 'Name.py' (x3)

        Siniflandirma:
          person_ratio >= 0.7 + 2+ sinyal tipi + skor >= 5 -> Person
          person_ratio <= 0.3 -> Project
          Digeri -> Uncertain
        """
```

Turkce eklentiler:
- Turkce eylem fiilleri: "dedi", "sordu", "istedi", "yapti"
- Turkce hitap: "Bey", "Hanim", "hocam"

### 0.6.4: General Extractor (115+ Marker)

Mevcut: 4 hall, ~25 EN pattern, ~24 TR pattern = 49 toplam
Yeni: 5 hall, MemPalace seviyesinde marker'lar + Turkce karsiliklari

```yaml
# mnemos/patterns/en.yaml (guncellenecek)
decisions:  # 21 marker
  - "we decided"
  - "we chose"
  - "we picked"
  - "we went with"
  - "let's use"
  - "decision is"
  - "agreed to"
  - "because"
  - "trade-off"
  - "architecture"
  - "approach"
  - "configure"
  - "the plan is"
  - "going forward"
  - "from now on"
  - "switched to"
  - "migrated to"
  - "instead of"
  - "better than"
  - "opted for"
  - "settled on"

preferences:  # 16 marker
  - "I prefer"
  - "we prefer"
  - "always use"
  - "never use"
  - "never do"
  - "best practice"
  - "my rule is"
  - "don't like"
  - "hate when"
  - "love when"
  - "snake_case"
  - "camelCase"
  - "tabs"
  - "spaces"
  - "convention"
  - "standard"

problems:  # 17 marker
  - "bug"
  - "error"
  - "crash"
  - "broke"
  - "doesn't work"
  - "root cause"
  - "the fix"
  - "workaround"
  - "fixed"
  - "solution is"
  - "failed"
  - "broken"
  - "stuck"
  - "regression"
  - "flaky"
  - "timeout"
  - "memory leak"

events:  # 33 marker (milestones)
  - "shipped"
  - "completed"
  - "launched"
  - "deployed"
  - "it works"
  - "figured out"
  - "migrated"
  - "breakthrough"
  - "finally"
  - "v1.0"
  - "v2.0"
  - "2x faster"
  - "released"
  - "merged"
  - "passed"
  - "went live"
  - "first time"
  - "milestone"
  - "done"
  - "finished"
  - "resolved"
  - "got it working"
  - "up and running"
  - "production ready"
  - "all tests pass"
  - "0 errors"
  - "100%"
  - "PR approved"
  - "code review done"
  - "demo ready"
  - "cut the release"
  - "tagged"
  - "published"

emotional:  # 28 marker (YENi hall)
  - "love"
  - "hate"
  - "scared"
  - "proud"
  - "frustrated"
  - "excited"
  - "worried"
  - "happy"
  - "sad"
  - "angry"
  - "relieved"
  - "I feel"
  - "I'm sorry"
  - "thank you"
  - "amazing"
  - "terrible"
  - "awesome"
  - "nightmare"
  - "dream"
  - "stressed"
  - "burned out"
  - "grateful"
  - "disappointed"
  - "surprised"
  - "overwhelmed"
  - "confident"
  - "nervous"
  - "hopeful"
```

Turkce marker'lar da ayni oranda genisletilecek (~100 pattern).

### 0.6.5: Scoring + Disambiguation

Mevcut: Pattern eslesirse dogrudan hall ata
Yeni: MemPalace'in scoring yaklasimi

```python
def classify_segment(text: str, patterns: dict) -> tuple[str, float]:
    """
    1. Her hall icin marker sayisini say (skor)
    2. Uzunluk bonusu: >500 char +2, 200-500 +1
    3. Confidence = min(1.0, max_score / 5.0)
    4. Disambiguation:
       - Problem + "fixed/solved" -> events (milestone)
       - Problem + pozitif sentiment -> events veya emotional
    5. min_confidence = 0.3 altindakileri at
    """
```

### 0.6.6: Code Line Filtering

Mevcut: Yok — kod satirlari da mining'e dahil
Yeni: MemPalace'in prose extraction'i

```python
def extract_prose(text: str) -> str:
    """Kod satirlarini cikar, sadece insanin yazdigi text'i birak.
    - Shell komutlari (cd, git, pip, npm...) atla
    - Programlama yapilarini (import, def, class, return) atla
    - Kod bloklarini (```) atla
    - Alpha orani <%40 olan satirlari atla
    """
```

---

## 0.7: Benchmark (LongMemEval)

### Yapi

```
benchmarks/
├── longmemeval/
│   ├── runner.py          ← ana benchmark calistirici
│   ├── dataset.py         ← HuggingFace'den dataset indirme + parse
│   └── metrics.py         ← Recall@K, NDCG@10 hesaplama
├── results/
│   └── results_longmemeval_YYYY-MM-DD.jsonl
└── README.md
```

### Pipeline

1. HuggingFace'den 500 soru + ~53 conversation session indir
2. Conversation'lari normalizer'dan gecir -> markdown
3. Mnemos'a mine et (raw + mined)
4. Her soru icin `mnemos_search` cagir
5. Ground-truth cevap top-K sonuclarda mi kontrol et
6. Recall@5, Recall@10, NDCG@10 hesapla

### Test Modlari

| Mod | Aciklama | Hedef |
|-----|----------|-------|
| raw-only | Sadece raw collection | Baseline |
| mined-only | Sadece mined collection | Mining kalitesi |
| combined | raw + mined birlestirme | En yuksek recall |
| filtered | Wing/room metadata filtering | +%34 iyilestirme |

### CLI

```bash
mnemos benchmark longmemeval
mnemos benchmark longmemeval --mode raw-only
mnemos benchmark results
```

### Hedef

| Metrik | MemPalace | Mnemos Phase 0 Hedef |
|--------|-----------|---------------------|
| Recall@5 | %96.6 | %95+ |
| Recall@10 | %98.2 | %97+ |

---

## Kapsam Disi (Phase 1+)

- Claude API ile mining/reranking (Phase 1)
- Contradiction detection (Phase 1)
- Auto-mining pipeline / hooks (Phase 2)
- Memory lifecycle / decay (Phase 2)
- Knowledge graph guclendirme (Phase 2)

---

## Uygulama Sirasi

1. **0.1 + 0.3**: Dual collection + raw storage (SearchEngine, Miner, Server)
2. **0.2**: Metadata filtering iyilestirmeleri
3. **0.5**: Conversation format normalizer
4. **0.6**: Mining engine guclendirme (exchange-pair chunking, room detection, entity detection, general extractor, scoring, code filtering)
5. **0.7**: Benchmark + ilk olcum
6. Tum testler gecmeli, mevcut 51 test kirilmamali

---

## Basari Kriterleri

- [ ] Raw collection'a tam dosya icerigi yaziliyor
- [ ] Mined collection mevcut davranisi koruyor
- [ ] Search hem raw hem mined'da arayip sonuclari birlestirebiliyor
- [ ] Wing/room list filter ($in) calisiyor
- [ ] 5 conversation formati normalize ediliyor (Claude Code, Claude.ai, ChatGPT, Slack, plain text)
- [ ] Exchange-pair chunking calisiyor (soru+cevap birlikte)
- [ ] Room detection 72+ pattern ile calisiyor
- [ ] Entity detection heuristic scoring ile calisiyor
- [ ] General extractor 115+ EN marker + ~100 TR marker ile calisiyor
- [ ] Emotional hall eklenmis
- [ ] Code line filtering calisiyor
- [ ] Scoring + disambiguation calisiyor (min_confidence=0.3)
- [ ] LongMemEval benchmark calisiyor ve Recall@5 >= %95
- [ ] Mevcut 51 test hala geciyor
- [ ] Yeni testler eklenmis (her yeni modul icin)
