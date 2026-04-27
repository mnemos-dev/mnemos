# Mnemos — Explain Like I'm 5

(Or: explain like I'm a Labrador.)

---

## What is it?

You talk to **Claude Code** in your terminal. It is smart.

Tomorrow you talk to Claude Code again. It forgot everything. 🐕

**Mnemos is a notebook for Claude.** Every time you finish a chat, Mnemos
writes down what you talked about. Next time you start a chat, Claude
reads the notebook first — so it remembers you, your projects, the
decisions you made yesterday.

The notebook is just a folder full of plain text files on your computer.
You can read them. You can edit them. You can throw them away. **They are
yours.**

---

## What do I need?

**Required:**
- A computer (Windows, macOS, or Linux)
- **Python 3.10 or newer** — type `python --version` in your terminal to check
- **Claude Code** already installed and working — type `claude --version` to check

**Optional but most people install it (more on this below):**
- **Obsidian** — a free app that makes the notebook prettier to browse

That's it. No account. No cloud. No bills.

---

## How do I install it?

Open a terminal. Copy-paste this one line:

```bash
pip install mnemos-dev
```

Wait a few seconds. Done.

To check it worked:

```bash
mnemos --help
```

You should see a list of commands. If you do, you're good.

---

## How do I set it up?

Pick a folder where the notebook will live. Anywhere is fine — your
Desktop is great. Then:

```bash
mnemos init
```

Mnemos will ask you a few questions. The defaults are good. Just press
**Enter** through them unless you have a strong opinion.

When it's done, you'll have:

- A folder full of `.md` files (the notebook)
- A few hooks installed in Claude Code (the auto-magic glue)

You will not have to touch any of this again.

---

## How do I use it?

**You don't.** That's the whole point.

Open Claude Code like you always do. Talk to Claude like you always do.
Close it with **`/exit`** when you're done.

Behind the scenes:

1. While you talk → Claude Code records the chat (it always did)
2. When you `/exit` → Mnemos refines the chat into a tidy markdown note
3. Next time you open Claude Code → Mnemos hands Claude a briefing of
   what you and it have been working on

That's it. **No buttons. No commands. No remembering to "save."**

---

## Three things to know

### 1. Always close with `/exit`

Just typing `exit` or clicking the **X** also works most of the time, but
`/exit` is the cleanest way. It gives Mnemos 5 full seconds to start its
work before the terminal closes. (And if you forget — Mnemos has a
backup plan that catches up the next time you open Claude.)

### 2. The notes live in your folder

Open the folder you picked during `mnemos init`. You'll see a
`Sessions/` subfolder. Every chat becomes a `.md` file there. Open one
in any text editor. It's just text. It's just yours.

If you don't like a note → delete the file. Gone.

(For a much nicer way to browse them, see the Obsidian section below.)

### 3. There's no AI bill

Mnemos uses **your Claude Code subscription** — the one you already pay
for. It does not call any API on its own. The refinement work happens
inside your Claude Code session, on the quota you have anyway.

Your Anthropic dashboard will not show new charges from Mnemos. Ever.

---

## What about Obsidian?

**Short answer:** You don't need Obsidian. Mnemos works without it. But
most people install it anyway because it makes the notebook a lot nicer
to use, and it's free.

### What is Obsidian?

[Obsidian](https://obsidian.md) is a free desktop app. Point it at a
folder of `.md` files and it shows them as a beautiful, connected
note-taking system — with sidebar navigation, full-text search, a graph
view of how your notes link to each other, and a clean reader.

It does **not** upload anything. It does **not** need an account. It is
just a viewer/editor for the folder you already have.

### Do I need it?

| You're someone who... | Obsidian recommendation |
|---|---|
| Just wants Claude to remember you, doesn't care about reading the notes | **Skip it.** You're done. Mnemos works fine without it. |
| Wants to occasionally read what got written | **Optional.** Any text editor (Notepad, VS Code, TextEdit) opens `.md` files. |
| Wants to actually browse/search/explore your memory | **Get it.** This is the experience the project was built around. |

### How do I install Obsidian?

1. Go to [obsidian.md](https://obsidian.md) and download for your OS
2. Open Obsidian
3. Click **"Open folder as vault"**
4. Pick the same folder you gave to `mnemos init`

Done. Your `Sessions/` notes now show up in Obsidian's sidebar. Click
any wikilink (`[[like this]]`) inside a note to jump to the linked
note. Try the **graph view** (left sidebar icon that looks like a
constellation) — it draws every link between every Session as a map.

That's the "memory palace" the project name hints at. The palace is
just your folder; Obsidian is the lights.

---

## Did something look weird?

| What you saw | What happened |
|---|---|
| **A blank terminal popped up briefly when I `/exit`** | That was Mnemos doing its work. It closes itself when done. ✅ |
| **My new chat had a "Mnemos: briefing loaded · N sessions" line at the top** | That means Mnemos handed Claude a briefing. ✅ |
| **My new chat had no briefing line** | Either it's your first time in this folder, or Mnemos doesn't have enough refined sessions yet to brief safely. Keep using Claude — it'll catch up. |
| **Claude said something like "let me check the briefing"** | That's exactly the point. Claude is reading what you and it discussed before. ✅ |

---

## Want to peek under the hood?

- **What works today vs. coming soon:** [`STATUS.md`](STATUS.md)
- **The road ahead:** [`docs/ROADMAP.md`](docs/ROADMAP.md)
- **How we got here, including which bets broke:** [`HISTORY.md`](HISTORY.md)
- **Full feature list and the technical README:** [`README.md`](README.md)

---

## Want to stop using it?

Two commands and Mnemos is gone:

```bash
mnemos install-end-hook --uninstall
pip uninstall mnemos-dev
```

Your notebook folder stays put. Your data is yours. **Always.**

---

*Questions? Open an issue at <https://github.com/mnemos-dev/mnemos/issues>.*
*Latest release: <https://github.com/mnemos-dev/mnemos/releases/tag/v1.1.0>*
