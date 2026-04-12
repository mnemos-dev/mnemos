"""Shared pytest fixtures for Mnemos test suite."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mnemos.config import MnemosConfig


# ---------------------------------------------------------------------------
# Vault / config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """Temporary vault directory with standard subdirectories."""
    (tmp_path / "Sessions").mkdir()
    (tmp_path / "Topics").mkdir()
    return tmp_path


@pytest.fixture()
def config(tmp_vault: Path) -> MnemosConfig:
    """MnemosConfig pointing at tmp_vault with Turkish + English support."""
    return MnemosConfig(
        vault_path=str(tmp_vault),
        languages=["tr", "en"],
    )


# ---------------------------------------------------------------------------
# Sample note fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_session_tr(tmp_vault: Path) -> Path:
    """Turkish session log about ProcureTrack / Supabase RLS decisions."""
    note = tmp_vault / "Sessions" / "2026-04-10-procuretrack.md"
    note.write_text(
        textwrap.dedent(
            """\
            ---
            date: 2026-04-10
            project: ProcureTrack
            tags: [approval, supabase]
            ---

            # ProcureTrack — Supabase RLS Karar Oturumu

            ## Alınan Kararlar

            - Supabase Row Level Security (RLS) tüm tablolarda zorunlu.
            - `auth.uid()` ile kullanıcı izolasyonu sağlanacak.
            - Onay akışı için `approvals` tablosu oluşturuldu.

            ## Sonraki Adımlar

            - RLS politikalarını test et.
            - Edge function ile bildirim gönder.
            """
        ),
        encoding="utf-8",
    )
    return note


@pytest.fixture()
def sample_session_en(tmp_vault: Path) -> Path:
    """English session log about LightRAG cost crisis and Google Gemini billing."""
    note = tmp_vault / "Sessions" / "2026-04-11-lightrag-cost.md"
    note.write_text(
        textwrap.dedent(
            """\
            ---
            date: 2026-04-11
            project: Mnemos
            tags: [lightrag, cost, gemini]
            ---

            # LightRAG Cost Crisis — Google Gemini Billing Spike

            ## Problem

            LightRAG's default graph-building pipeline called Gemini Flash
            for every chunk, causing a 40x cost spike overnight.

            ## Decision

            Switched to local embedding (chromadb default) for graph edges.
            Gemini API calls are now opt-in via `use_llm: true` in mnemos.yaml.

            ## Outcome

            Daily cost dropped from ~$12 to ~$0.30.
            """
        ),
        encoding="utf-8",
    )
    return note


@pytest.fixture()
def sample_topic(tmp_vault: Path) -> Path:
    """Topic note about ProcureTrack (Next.js 14 + Supabase)."""
    note = tmp_vault / "Topics" / "ProcureTrack.md"
    note.write_text(
        textwrap.dedent(
            """\
            ---
            project: ProcureTrack
            stack: [nextjs, supabase, typescript]
            status: active
            ---

            # ProcureTrack

            Tedarik süreçlerini dijitalleştiren Next.js 14 + Supabase uygulaması.

            ## Stack

            - **Frontend:** Next.js 14 App Router, Tailwind CSS
            - **Backend:** Supabase (Postgres + Auth + Storage)
            - **Language:** TypeScript

            ## Özellikler

            - Satın alma talep formu
            - Çok aşamalı onay akışı (RLS ile güvence altında)
            - Tedarikçi teklif karşılaştırması
            """
        ),
        encoding="utf-8",
    )
    return note
