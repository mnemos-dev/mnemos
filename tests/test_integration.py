"""End-to-end integration tests.

v1.0: every test in this module exercised the deleted mining/drawer
paradigm (``handle_mine``, ``handle_add``, ``palace.recycle_drawer``,
the dual-collection raw+mined search RRF). They were removed when the
production code they covered (``mnemos.miner``, ``mnemos.palace``) was
deleted in Task 3.

A new, narrative-first integration suite covering the Sessions/.md
write path + read path is owed by Task 17 (Recall skill — Sessions-only
path) and Task 22 (``mnemos/reindex.py`` module). Until those land,
intentionally empty.
"""
from __future__ import annotations
