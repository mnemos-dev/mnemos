# Phase 0 — Foundation (Raw Storage Altyapisi) Design Spec

**Date:** 2026-04-13
**Status:** Approved
**Goal:** MemPalace'in API'siz %96.6 recall oranini yakalamak icin raw verbatim storage, dual collection, metadata filtering ve benchmark altyapisi kurmak.

---

## Background

Mnemos v0.1 **lossy mining** yapiyor: dosyalari paragraflara boluyor, regex ile siniflandiriyor, sadece fragment'lari sakliyor. Orijinal baglam (conversation akisi, soru-cevap iliskisi) kayboluyor.

MemPalace'in %96.6 recall'u "store everything, then make it findable" yaklasimina dayaniyor — ham text korunuyor, uzerine yapisal metadata ekleniyor.

Phase 0 bu temeli kuruyor. Phase 1 (AI Engine) ve sonraki phase'ler bunun uzerine oturacak.

---

## 0.1 + 0.3: Raw Verbatim Storage + Dual Collection

### Tasarim

Mevcut tek collection yerine iki ChromaDB collection kullanilacak:

```
ChromaDB
├── mnemos_raw       ← orijinal dosya tam metin (verbatim, kayipsiz)
└── mnemos_mined     ← regex ile cikarilmis fragment'lar (mevcut yapi)
```

### mnemos_raw Collection

- Mine edilen her dosyanin **tam icerigi** tek dokuman olarak saklanir
- Dosya buyukse chunk'lanir (ChromaDB embedding limiti ~8191 token / ~30K karakter) ama chunk'lar arasi overlap ile baglam korunur
- Metadata: `wing`, `room`, `source_path`, `language`, `mined_at`, `chunk_index` (chunk varsa)
- Document ID: `raw-<source_path_hash>` (veya chunk varsa `raw-<hash>-<chunk_index>`)

### mnemos_mined Collection

- Mevcut `mnemos_drawers` collection'i `mnemos_mined` olarak yeniden adlandirilir
- Mevcut davranis aynen devam eder — regex fragment'lari burada
- Yeni eklenen metadata: `raw_id` (iliskili raw dokumana referans)

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
        collection="both"  -> ikisinde de ara, skorla birlestir
        """
```

### Miner / Server Degisiklikleri

- `handle_mine()`: Dosyayi mine ederken once `index_raw()` ile tam icerigi sakla, sonra fragment'lari `index_drawer()` ile sakla
- `mnemos_search` tool'u: Yeni `collection` parametresi (default: "both")
- Mevcut drawer .md dosyalari Obsidian'da aynen kalir — raw collection sadece ChromaDB'de

### Migration

- Mevcut `mnemos_drawers` collection varsa silinip `mnemos_mined` olarak yeniden olusturulur (alpha, kullanici uyarilir)
- Mevcut mine edilen dosyalar icin raw collection bos baslar
- `mnemos mine --rebuild` komutu: mine_log sifirlanir, tum kaynaklar tekrar taranir, hem raw hem mined doldurulur
- Rebuild islemi mevcut drawer .md dosyalarini silmez — yeni dosyalar eklenir, ayni icerik zaten upsert ile guncellenir

---

## 0.2: Metadata Filtering Sagllamlastirma

### Mevcut Durum

- `_build_where_filter()` sadece `$and` destekliyor
- Wing/room/hall string match — gecersiz deger hata vermez ama bos sonuc donuyor (bu zaten dogru davranis)

### Iyilestirmeler

1. **`$or` destegi**: Birden fazla wing'de arama yapabilme
   ```python
   # Ornek: ProcureTrack VEYA GYP wing'inde ara
   search(query, wing=["ProcureTrack", "GYP"])
   ```
   - Wing/room/hall parametreleri `str | list[str]` kabul edecek
   - Tek deger: `{"wing": "X"}` (mevcut)
   - Liste: `{"wing": {"$in": ["X", "Y"]}}` (yeni)

2. **Hall-only filter**: Wing belirtmeden hall bazli arama
   ```python
   # Tum wing'lerde sadece decisions hall'unde ara
   search(query, hall="decisions")
   ```
   Bu zaten calisiyor ama test coverage eksik — test eklenecek.

3. **Negative filter**: Belirli wing'i haric tutma
   ```python
   search(query, exclude_wing="General")
   ```

---

## 0.4: Benchmark Altyapisi

### Yaklasim

MemPalace'in LongMemEval benchmark'ini aynen kullanarak elma-elma karsilastirma.

### Yapi

```
benchmarks/
├── longmemeval/
│   ├── runner.py          ← ana benchmark calistirici
│   ├── dataset.py         ← HuggingFace'den dataset indirme + parse
│   └── metrics.py         ← Recall@K, NDCG@10 hesaplama
├── results/               ← sonuc dosyalari
│   └── results_longmemeval_YYYY-MM-DD.jsonl
├── conftest.py            ← pytest fixtures (opsiyonel)
└── README.md              ← benchmark kullanim klavuzu
```

### LongMemEval Pipeline

1. **Dataset indirme**: HuggingFace'den 500 soru + ~53 conversation session indirilir
2. **Ingestion**: Conversation'lar Mnemos'a mine edilir (raw + mined)
3. **Query**: Her soru icin `mnemos_search` cagirilir
4. **Scoring**: Ground-truth cevap top-K sonuclarda mi kontrol edilir
5. **Report**: Recall@5, Recall@10, NDCG@10 hesaplanir

### Test Modlari

| Mod | Aciklama | Hedef |
|-----|----------|-------|
| raw-only | Sadece raw collection'da arama | Baseline |
| mined-only | Sadece mined collection'da arama | Mevcut sistem performansi |
| combined | Her iki collection'da arama, skor birlestirme | En yuksek recall |
| filtered | Wing/room metadata filtering ile | MemPalace'in +%34 iyilestirmesi |

### CLI

```bash
# Benchmark calistir
mnemos benchmark longmemeval

# Belirli modda calistir
mnemos benchmark longmemeval --mode raw-only

# Sonuclari goster
mnemos benchmark results
```

---

## Kapsam Disi (Sonraki Phase'ler)

- Claude API ile mining/reranking (Phase 1)
- Contradiction detection (Phase 1)
- Auto-mining pipeline / hooks (Phase 2)
- Memory lifecycle / decay (Phase 2)
- Knowledge graph guclendirme (Phase 2)

---

## Uygulama Sirasi

1. **0.1 + 0.3**: Dual collection + raw storage (SearchEngine, Miner, Server)
2. **0.2**: Metadata filtering iyilestirmeleri
3. **0.4**: Benchmark altyapisi + ilk olcum
4. Tum testler gecmeli, mevcut 51 test kirilmamali

---

## Basari Kriterleri

- [ ] Raw collection'a tam dosya icerigi yaziliyor
- [ ] Mined collection mevcut davranisi koruyor
- [ ] Search hem raw hem mined'da arayip sonuclari birlestirebiliyor
- [ ] Wing/room list filter ($in) calisiyor
- [ ] LongMemEval benchmark calistiriliyor ve Recall@5 olculuyor
- [ ] Mevcut 51 test hala geciyor
- [ ] Yeni testler eklenmis (raw indexing, dual search, filtering, benchmark)
