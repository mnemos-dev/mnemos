"""CLI i18n — locale-aware string lookup for `mnemos init` / `mnemos import`.

Tiny dict-based design. No gettext, no .po files, no compilation step.
For 15–25 translatable strings the dict is more readable than the
machinery would save.

Public API:
    t(key, lang) -> str         # lookup, English fallback if missing
    resolve_lang(cfg) -> str    # pick locale from MnemosConfig

Error messages aimed at developers stay English on purpose. Only
user-facing onboarding text is localized.
"""
from __future__ import annotations

from typing import Dict

DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "tr")

# {key: {lang: text}}
_STRINGS: Dict[str, Dict[str, str]] = {
    # ---------------- Intro (Phase 1) ----------------
    "intro.body": {
        "en": (
            "Mnemos is your AI memory system. It stores conversations, decisions,\n"
            "and learnings as human-readable markdown inside your Obsidian vault.\n"
            "\n"
            "Two modes of use:\n"
            "  1. First-time setup — bulk-mine your past conversations.\n"
            "  2. Ongoing — every Claude Code session is mined automatically via\n"
            "     hooks (set up at the end of this wizard; full activation in\n"
            "     a future release).\n"
            "\n"
            "First-time setup is resumable. You can stop anywhere and pick up\n"
            "later — every decision is saved to .mnemos-pending.json.\n"
        ),
        "tr": (
            "Mnemos AI hafıza sistemin. Konuşmalarını, kararlarını, öğrendiklerini\n"
            "Obsidian vault'unda insan-okunabilir markdown olarak saklıyor.\n"
            "\n"
            "İki kullanım modu:\n"
            "  1. İlk kurulum — geçmiş konuşmalarını toplu mine etme.\n"
            "  2. Sürekli kullanım — her Claude Code session'ı hook'lar ile\n"
            "     otomatik mine edilir (bu sihirbaz sonunda kurulur; tam\n"
            "     aktivasyon ileriki bir sürümde).\n"
            "\n"
            "İlk kurulum tek seferde yapılmak zorunda değil — istediğin yerde\n"
            "durup sonra kaldığın yerden devam edebilirsin. Her karar\n"
            ".mnemos-pending.json'a yazılır.\n"
        ),
    },
    # ---------------- Discovery (Phase 2) ----------------
    "discovery.header": {
        "en": "\n=== Discovering knowledge sources ===\n",
        "tr": "\n=== Bilgi kaynakları taranıyor ===\n",
    },
    "discovery.empty": {
        "en": (
            "  No knowledge sources found. Nothing to mine right now.\n"
            "  Add markdown to Sessions/, memory/, or Topics/ and run\n"
            "  `mnemos mine <path>` later.\n"
        ),
        "tr": (
            "  Hiçbir bilgi kaynağı bulunamadı. Şu an mine edilecek bir şey yok.\n"
            "  Sessions/, memory/ veya Topics/ klasörüne markdown ekle ve daha\n"
            "  sonra `mnemos mine <path>` çalıştır.\n"
        ),
    },
    "discovery.total_estimate": {
        "en": "\n  Total estimated time if you process all: {estimate}\n",
        "tr": "\n  Hepsini işlersen tahmini toplam süre: {estimate}\n",
    },
    # ---------------- Choice (Phase 3) ----------------
    "choice.options_header": {
        "en": "Options:",
        "tr": "Seçenekler:",
    },
    "choice.option_a": {
        "en": "  [A] Process all now",
        "tr": "  [A] Hepsini şimdi işle",
    },
    "choice.option_s": {
        "en": "  [S] Selective — ask me per source",
        "tr": "  [S] Seçerek ilerle — kaynak kaynak sor",
    },
    "choice.option_l": {
        "en": "  [L] Later — just register sources, don't process now",
        "tr": "  [L] Sonra — şimdilik sadece kaynakları kaydet, işleme",
    },
    "choice.prompt": {
        "en": "\nChoice [A/S/L]: ",
        "tr": "\nSeçim [A/S/L]: ",
    },
    "choice.invalid": {
        "en": "Please type A, S, or L: ",
        "tr": "Lütfen A, S veya L yaz: ",
    },
    # ---------------- Per-source selective (Phase 3 / 4) ----------------
    "per_source.header": {
        "en": "\n  Source: {sid}  ({n} files, {est}, {cls})",
        "tr": "\n  Kaynak: {sid}  ({n} dosya, {est}, {cls})",
    },
    "per_source.prompt": {
        "en": "    Process now [Y], leave for later [L], skip entirely [S]? ",
        "tr": "    Şimdi işle [Y], sonraya bırak [L], tamamen atla [S]? ",
    },
    "per_source.invalid": {
        "en": "    Please type Y, L, or S: ",
        "tr": "    Lütfen Y, L veya S yaz: ",
    },
    # ---------------- Outcomes (Phase 4) ----------------
    "outcome.skipped": {
        "en": "    [skipped] {sid}",
        "tr": "    [atlandı] {sid}",
    },
    "outcome.skip_done": {
        "en": "  [skip] {sid} already done.",
        "tr": "  [atla] {sid} zaten tamamlanmış.",
    },
    "outcome.raw_registered": {
        "en": (
            "    [registered] {sid}: {n} files awaiting refinement.\n"
            "      → Run `/mnemos-refine-transcripts` skill in Claude Code\n"
            "        on `{path}` to convert these to Sessions/."
        ),
        "tr": (
            "    [kaydedildi] {sid}: {n} dosya rafine bekliyor.\n"
            "      → Claude Code oturumunda `/mnemos-refine-transcripts` skill'ini\n"
            "        `{path}` üzerinde çalıştırarak Sessions/'a dönüştür."
        ),
    },
    "outcome.later": {
        "en": "    [later] {sid} registered as pending.",
        "tr": "    [sonra] {sid} pending olarak kaydedildi.",
    },
    "outcome.mining": {
        "en": "    [mining] {sid} — {n} files...",
        "tr": "    [mine] {sid} — {n} dosya...",
    },
    "outcome.done": {
        "en": "    [done] {sid} — scanned: {scanned}, drawers: {drawers}, entities: {entities}",
        "tr": "    [bitti] {sid} — taranan: {scanned}, çekmece: {drawers}, varlık: {entities}",
    },
    # ---------------- Hook install (v0.3 task 3.7) ----------------
    "hook_install_prompt": {
        "en": "Install the auto-refine SessionStart hook so future Claude Code sessions mine themselves? [Y/n]: ",
        "tr": "Auto-refine SessionStart hook'unu kur — gelecekteki Claude Code oturumları kendiliğinden mine edilsin mi? [E/h]: ",
    },
    "hook_install_done": {
        "en": "Auto-refine hook installed.",
        "tr": "Auto-refine hook kuruldu.",
    },
    "hook_install_already": {
        "en": "Auto-refine hook already installed — skipping.",
        "tr": "Auto-refine hook zaten kurulu — atlıyorum.",
    },
    "hook_install_declined": {
        "en": "Skipped. Install later with: mnemos install-hook",
        "tr": "Atlandı. Daha sonra kurmak için: mnemos install-hook",
    },
    # ---------------- Backend selection (v0.3.1 task 3.14a) ----------------
    "backend.prompt_header": {
        "en": "\nVector backend — choose how embeddings are indexed:",
        "tr": "\nVektör arka ucu — gömü indeksleme yöntemini seç:",
    },
    "backend.option_c": {
        "en": (
            "  [C] ChromaDB (default)\n"
            "      Mature, widely used. Occasional index corruption has been reported."
        ),
        "tr": (
            "  [C] ChromaDB (varsayılan)\n"
            "      Olgun, yaygın. Zaman zaman indeks bozulması raporlanmıştır."
        ),
    },
    "backend.option_s": {
        "en": (
            "  [S] sqlite-vec\n"
            "      Single-file SQLite + vec0 extension. Same recall as ChromaDB\n"
            "      (verified 2026-04-17), recommended if you hit ChromaDB issues."
        ),
        "tr": (
            "  [S] sqlite-vec\n"
            "      Tek dosyalı SQLite + vec0 eklentisi. ChromaDB ile aynı recall\n"
            "      (2026-04-17'de doğrulandı), ChromaDB sorun çıkarırsa önerilir."
        ),
    },
    "backend.hint_windows_py314": {
        "en": (
            "  Note: on Windows + Python 3.14 sqlite-vec has shown fewer flush\n"
            "  issues in our own testing — you may prefer [S] here."
        ),
        "tr": (
            "  Not: Windows + Python 3.14'te sqlite-vec'in daha az flush sorunu\n"
            "  çıkardığını gözlemledik — bu ortamda [S] tercih edilebilir."
        ),
    },
    "backend.prompt": {
        "en": "[C]hromaDB (default) / [S]qlite-vec: ",
        "tr": "[C]hromaDB (varsayılan) / [S]qlite-vec: ",
    },
    "backend.invalid": {
        "en": "Please type C or S (or press Enter for the default): ",
        "tr": "Lütfen C veya S yaz (ya da varsayılan için Enter'a bas): ",
    },
    "backend.chose_chromadb": {
        "en": "  → Using ChromaDB.",
        "tr": "  → ChromaDB kullanılıyor.",
    },
    "backend.chose_sqlite": {
        "en": "  → Using sqlite-vec.",
        "tr": "  → sqlite-vec kullanılıyor.",
    },
    # ---------------- Statusline install (v0.3 task 3.7b) ----------------
    "statusline_install_prompt": {
        "en": "Install the statusline snippet so auto-refine progress shows in the chatbox footer? [Y/n]: ",
        "tr": "Statusline snippet'ini kur — auto-refine ilerleyişi sohbet kutusu altında görünsün mü? [E/h]: ",
    },
    "statusline_install_done": {
        "en": "Statusline snippet installed.",
        "tr": "Statusline snippet'i kuruldu.",
    },
    "statusline_install_already": {
        "en": "Statusline snippet already installed — skipping.",
        "tr": "Statusline snippet'i zaten kurulu — atlıyorum.",
    },
    "statusline_install_declined": {
        "en": "Skipped. Install later with: mnemos install-statusline",
        "tr": "Atlandı. Daha sonra kurmak için: mnemos install-statusline",
    },
    # ---------------- Recall-briefing hook install (v0.4 task 15b) ----------------
    "recall_hook_install_prompt": {
        "en": "Install recall-briefing hook? This auto-generates per-cwd memory briefings on SessionStart. (Y/n)",
        "tr": "Recall-briefing hook'u kurulsun mu? Her SessionStart'ta cwd-bazlı hatıra özeti üretir. (Y/n)",
    },
    "recall_hook_install_done": {
        "en": "Recall-briefing hook installed. recall_mode set to 'skill' in mnemos.yaml.",
        "tr": "Recall-briefing hook kuruldu. mnemos.yaml'da recall_mode 'skill' olarak ayarlandı.",
    },
    "recall_hook_install_declined": {
        "en": "Skipped recall-briefing hook. You can install later with: mnemos install-recall-hook",
        "tr": "Recall-briefing hook atlandı. Sonra kurmak için: mnemos install-recall-hook",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **fmt: object) -> str:
    """Look up a localized string. Falls back to English if `lang` is missing.

    `fmt` keyword args run through str.format on the resolved template.
    Unknown keys raise KeyError — these are typos, not runtime conditions.
    """
    bundle = _STRINGS[key]
    text = bundle.get(lang) or bundle[DEFAULT_LANG]
    return text.format(**fmt) if fmt else text


def resolve_lang(cfg) -> str:  # type: ignore[no-untyped-def]
    """Pick the active locale from a MnemosConfig instance.

    Uses the first entry of `cfg.languages` if it's supported, else falls
    back to English.
    """
    langs = getattr(cfg, "languages", None) or []
    for candidate in langs:
        if candidate in SUPPORTED_LANGS:
            return candidate
    return DEFAULT_LANG
