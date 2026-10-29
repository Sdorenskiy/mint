# MINT — quick guide for users

**Русская** версия: [docs/ru/QUICK_GUIDE.md](ru/QUICK_GUIDE.md)

MINT reviews any document — a contract, a policy, a report, a specification, a thesis — section by section, against
the documents in the knowledge base, and writes a report. It is an assistant,
not an approver: you check every finding. Your "correct / wrong" marks are the main source of MINT improvements.

## Start and update

- Start: `./run_mint.sh` (Windows: `run_mint.bat`); the page opens by itself: `http://localhost:8501`.
- Update: stop MINT and run `./update.sh path/to/mint-<version>.zip` (Windows: `update.bat`). Your settings
  (`.env`, `config.yaml`, checklists, glossary, prompt edits), the knowledge base and saved reviews are kept. The
  version number is at the bottom of the sidebar.
- Installing from scratch — [INSTALL.md](INSTALL.md).

## Document review

1. The **"📋 Document review"** tab → upload the document: .docx is best (findings can then be added as Word
   comments); .pdf, .md and .txt also work.
2. **"🧭 Profile"** (sidebar) — "Architecture and IT solutions" (the default) for design documentation or
   "General" for any other documents. The profile fills the "General review criteria" field; adjust them for the document if needed.
3. **"🎯 Special attention"** — what matters in this particular document, one item per line. Optional, but MINT
   answers each item separately across the whole document.
4. Check the **"📋 Checklist"** and **"📎 Basis documents"** blocks: MINT fills them itself; remove what does not
   fit and add a missing basis document (for example, the specification from the base).
5. **"🚀 Start the document review".** A large document takes tens of minutes: the model receives hundreds of requests. Keep
   the browser tab open until the review finishes.
6. Leave "⚙️ Review settings" alone unless needed — everything necessary is on by default.

The report: "⭐ Key points" first, then answers to the items, findings by document section, "❓ Not confirmed by a
source" (references and figures found neither in the document nor in the norms — check these especially), minor
findings and typos.

## Assessing the findings — the most important part

Below the report is the **"✍️ Expert assessment of findings"** block. Mark every finding:

| Mark | When |
|---|---|
| ✅ keep | the finding is correct — it goes into your list of findings |
| ➖ minor | correct but not significant |
| ❌ wrong | the finding is a mistake — **choose a reason** |

Reasons for "wrong": **the document has it** (MINT did not see it); **the model misread the text**; **not relevant
to the document**; **common practice, not an error**; **duplicates another finding**; **other** — then add a few
words in the comment. The reasons show what to fix in MINT, so a "wrong" without a reason is of little use.

At the bottom is the **"➕ Your own findings"** table: enter what you found yourself and MINT missed. This is as
valuable as the marks: it shows what MINT cannot do yet.

Marks are saved at once. To continue another day: **"📂 Saved reviews"** (at the top of the tab) → choose the
review → "📂 Open" — no need to upload the document again.

The result for the document's author: **"📥 My findings (.docx)"** — a table (No., section, finding, severity) of
the findings marked ✅ and your own; or **"📝 Document with my findings"** — the same findings as Word comments in
the document itself.

## Once a week: hand over the assessments

"📂 Saved reviews" → **"📤 Collect the assessments"** → **"📥 Download the assessments (.jsonl)"** — and give the
file to whoever maintains MINT. The file contains finding texts with quotes from the documents: pass it on only the
way the documents themselves may be passed on. If the documents may not leave, tick **"Without finding texts"**: only
check kinds, severity, marks and reasons remain.

## Consultant: problems, diagrams, explanations

The **"🧠 Consultant"** tab is for advice rather than "what the policy says": analyse a problem, propose options, draw
a diagram, explain how a system is built.

- Write as to a colleague: "Analyse a problem: … What can be done?", "Draw a diagram of how a message passes through
  …", "Explain what components … consists of and how they interact".
- How to read the answer: **📄** — how it works now, from the documents, with references; **💡** — the model's
  proposals and knowledge (you check them); **❔** — a statement about your systems without a reference: the model may
  have presented a guess as a document.
- A diagram is drawn right in the answer; the buttons above it download it as a picture, copy it, open it full
  screen. To refine it: **"⬇ Diagram (.mmd)"** and paste the code into draw.io (Arrange → Insert → Advanced → Mermaid)
  or Excalidraw ("Mermaid to Excalidraw").
- Refine in the same conversation: "and without sharding?", "add the antivirus to the diagram". **"➕ New
  conversation"** starts from scratch.
- **"🔎 What was found in the wiki"** under the answer — which searches were made and what the model got. If the
  answer is generic, not tied to your systems, the base describes them too little: upload the documents or a system
  card.
- For an exact answer from the documents (for approvals, without the model's additions) use the **"Chat"** tab.

## Good to know

- MINT makes mistakes. "Not described" sometimes means "described in another section in other words"; check
  references to clauses of standards against the source.
- Everything stays on your computer: the knowledge base in `KB_DIR`, reviews and logs in `LOG_DIR` (default
  `~/mint_logs`). MINT sends out only requests to the models — to the address in `.env`.
- If a review goes wrong, download "📥 the review log (.md)" and pass it on with a description (the log has
  fragments of the document — the same rules apply). 👍/👎 ratings below the report help too.
