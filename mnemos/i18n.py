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
    # v1.0: outcome.mining + outcome.done removed — they were emitted by the
    # deleted mining-pipeline path. Task 27 (mnemos init v2) added the
    # identity_bootstrap_* keys below; the curated "process now" outcome now
    # falls back to outcome.later (no per-source mining UX in v1.0).
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
    # ---------------- Identity bootstrap (v1.0 task 27 — Phase 6) ----------------
    "identity_bootstrap_prompt": {
        "en": "Generate Identity Layer now? (~5-10 min, uses subscription quota) [Y/n]: ",
        "tr": "Identity Layer'ı şimdi oluşturayım mı? (~5-10 dk, abonelik kotası kullanır) [E/h]: ",
    },
    "identity_bootstrap_starting": {
        "en": "Bootstrapping Identity Layer...",
        "tr": "Identity Layer hazırlanıyor...",
    },
    "identity_bootstrap_done": {
        "en": "Identity Layer created: {path}",
        "tr": "Identity Layer oluşturuldu: {path}",
    },
    "identity_bootstrap_failed": {
        "en": "Identity bootstrap failed: {reason}. Run `mnemos identity bootstrap` later.",
        "tr": "Identity bootstrap başarısız: {reason}. `mnemos identity bootstrap` ile sonra tekrar deneyebilirsiniz.",
    },
    "identity_bootstrap_declined": {
        "en": "Skipped. Run `mnemos identity bootstrap` later.",
        "tr": "Atlandı. Sonra çalıştırmak için: `mnemos identity bootstrap`",
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
    # ---------------- Settings TUI (v1.1 G9 task 9.7) ----------------
    "settings.title": {
        "en": "Mnemos Settings",
        "tr": "Mnemos Ayarları",
    },
    "settings.refine_section": {
        "en": "Refine pipeline:",
        "tr": "Refine pipeline:",
    },
    "settings.briefing_section": {
        "en": "Briefing:",
        "tr": "Briefing:",
    },
    "settings.identity_section": {
        "en": "Identity:",
        "tr": "Identity:",
    },
    "settings.hooks_section": {
        "en": "Hooks (settings.json managed):",
        "tr": "Hooks (settings.json yönetilen):",
    },
    "settings.backend_section": {
        "en": "Backend & locale:",
        "tr": "Backend & dil:",
    },
    "settings.progress_section": {
        "en": "--- Refinement Progress ---",
        "tr": "--- Refine ilerlemesi ---",
    },
    # ---------------- Init refine quota + install-end-hook (v1.1 G10) ----
    "init.quota_warning_header": {
        "en": "Subscription quota reality check:",
        "tr": "Abonelik kotası gerçeği:",
    },
    "init.quota_warning_body": {
        "en": (
            "  Eligible JSONLs: {count}. Each refine = 1 'claude --print' message.\n"
            "  Pro tier ~45 messages / 5h -> ~{hours:.0f}h spread across sessions.\n"
            "  The hook processes a batch each session start in the background."
        ),
        "tr": (
            "  Uygun JSONL: {count}. Her refine = 1 'claude --print' mesajı.\n"
            "  Pro tier ~45 mesaj / 5sa -> ~{hours:.0f}sa oturumlara yayılır.\n"
            "  Hook her oturum başında bir batch'i arka planda işler."
        ),
    },
    "init.per_session_prompt": {
        "en": "JSONLs per session start [1-50, default 3]: ",
        "tr": "Oturum başına refine sayısı [1-50, vars. 3]: ",
    },
    "init.direction_prompt": {
        "en": "Direction [n=newest first | o=oldest first, default n]: ",
        "tr": "Yön [n=en yeni once | o=en eski once, vars. n]: ",
    },
    "init.min_turns_prompt": {
        "en": "Min user-turn threshold [1-10, default 3]: ",
        "tr": "Min user-turn esigi [1-10, vars. 3]: ",
    },
    "init.invalid_per_session": {
        "en": "Invalid; try 1-50.",
        "tr": "Gecersiz; 1-50 araliginda dene.",
    },
    "init.invalid_direction": {
        "en": "Invalid; try n or o.",
        "tr": "Gecersiz; n veya o.",
    },
    "init.invalid_min_turns": {
        "en": "Invalid; try 1-10.",
        "tr": "Gecersiz; 1-10 araliginda dene.",
    },
    "init.end_hook_prompt": {
        "en": "Install SessionEnd hook (refine + brief on /exit, ~40s detached)? [Y/n]: ",
        "tr": "SessionEnd hook'u kurulsun mu (/exit'te refine + brief, ~40s detached)? [Y/h]: ",
    },
    "init.end_hook_skipped": {
        "en": "Skipped. Run `mnemos install-end-hook --v1 --vault <path>` later.",
        "tr": "Atlandi. Sonra: `mnemos install-end-hook --v1 --vault <yol>`",
    },
    "init.end_hook_done": {
        "en": "SessionEnd hook installed.",
        "tr": "SessionEnd hook kuruldu.",
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
