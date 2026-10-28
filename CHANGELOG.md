# Changelog

**English** · [Русский](docs/ru/CHANGELOG.md)

## 21.2 — a quiet installation, a compact document list, "New chat" always at hand

- **Documents of the base in the sidebar — a compact list.** It scrolls inside itself instead of stretching the whole
  sidebar; each document shows its role (📌 expert rules, 🗂️ system card), the number of vectors and the date it was
  indexed; a document indexed with another embedding model is marked ⛔ right under its name, details on hover. With
  more than 8 documents — a search by name ("note part 1" finds `Explanatory_note_part_1.docx`). Above the list —
  the number of **documents** in the base next to the number of vectors.
- **Removing documents** — in "🗑️ Remove from the base": choose one or several documents, "Remove selected", confirm.
  The 🗑️ button next to every document (it removed at once, without asking) is gone.
- **"➕ New chat"** is in the chat tab header and is always there: in an empty chat, right after the first answer
  (before, it appeared only after the next action) and while the model is answering (the click takes effect when the
  answer is ready).
- `install.sh` / `install.bat` no longer print hundreds of pip lines (`Ignoring … markers`, `Collecting …`): one line
  "installing packages…" and the result; pip's full output goes to `.venv/install.log`, and if something fails the
  end of it is shown on screen. GitHub checks that the installation stays quiet.
- `update.sh` / `update.bat` accept a `.tar.gz` archive ("Source code (tar.gz)" on the release page) as well as
  `.zip` and a folder.
- The self-check no longer shows Streamlit's harmless `missing ScriptRunContext` warning during the trial page run.

## 21.1 — installation from the first attempt, no PyTorch, the architecture profile by default

- **Installation from the first attempt.** `install.sh` / `install.bat` install exact package versions from
  `requirements.lock` (one file for Linux, Windows and macOS). GitHub tests them on every change and every night:
  a fresh install on Ubuntu (Python 3.10–3.12), Debian 12 without `python3-venv` (as Astra Linux 1.8) and Windows,
  then .docx parsing with the real Docling, base → chat → review and the self-check with the page on real Streamlit
  (`.github/workflows/install.yml`, `tests/test_real_install.py`). The scripts handle the usual snags themselves:
  an incomplete `.venv` left by an interrupted install is recreated; without `python3-venv` pip is downloaded by
  the system pip (no administrator); if the mirror lacks an exact version, the packages come from
  `requirements.txt`; `--clean` starts from scratch. The self-check suggests `./install.sh --clean` when the
  installed packages are not the tested ones.
- **No PyTorch.** .docx is parsed by Docling's Word backend called directly, not through Docling's general
  converter, which also loads PDF parsing with models. The result is identical to the full Docling — GitHub
  compares them on Docling's test documents and MINT's samples; `tools/docx_parity.py` checks your own documents.
  The installation is 72 packages, about 0.6 GB on disk and 165 MB to download instead of 122 packages, 2.1 GB and
  540 MB, with no model libraries (PyTorch, transformers, huggingface_hub, OpenCV). This also fixes
  `No module named 'torch'` / `'docling_parse'` when uploading a .docx after a fresh install. Docling is pinned to
  2.127.0. An existing installation with PyTorch keeps working; to drop it: `./install.sh --clean`.
- **The "Architecture and IT solutions" profile is the default** — the prompts are the same as before profiles
  (prompt-set version `ru-8fd10871` / `en-9c3500f7`). The general profile is in the sidebar or `profile: general`
  in `config.yaml`. `tools/review_stats.py` counts reviews without a profile as architecture.
- **Chat: a clarified question no longer replaces yours.** A follow-up question rewritten from the dialogue used to
  be searched alone, so a term, an abbreviation or a number lost in rewriting led the search astray. Now the
  search uses both questions: their candidates are merged and the reranker takes the better of the two scores.
  A rewrite that differs only in case or punctuation is not shown; the caption says "Searched by your question
  and by the one clarified from the dialogue". The prompts are unchanged.

## 21.0 — saved reviews, expert assessment of findings, update in place

The version for handing MINT over to colleagues: experts go through the findings, and their marks show what to
improve.

- **Profiles** — sets of prompts for chat, review and verification of fixes (sidebar → "🧭 Profile", `profile` in
  `config.yaml`). **"Architecture and IT solutions"** is the MINT prompts from before profiles, word for word: the
  roles of the Architecture Board, the architecture review criteria; the prompt-set version is the same as before
  (a test checks it), so results stay comparable. **"General — any documents"** (the default): neutral roles ("lead
  expert reviewer of documents", "a lead expert consultant on the knowledge base"), criteria for any document —
  requirements and obligations, completeness, consistency with the basis documents and the norms, figures, dates and
  references, hidden risks; the rules of the review are the same. The profile fills the "General review criteria"
  field; the profile texts are on the "📝 Prompts" page. The profile is saved with every review;
  `tools/review_stats.py` adds a breakdown by profile. **To keep working as before, set `profile: architecture`.**
- **Saved reviews** ("📂 Saved reviews" at the top of the review tab): every review is saved on the user's computer,
  in `LOG_DIR/audits/<id>` — the report, the log, raw model answers (compressed), a copy of the reviewed .docx and the
  expert assessment. A review opens without uploading the document again; it can be deleted. Re-checking failed
  sections writes into the same folder and keeps the assessment.
- **Expert assessment of findings** (the "✍️ Expert assessment of findings" block below the report): every finding
  in report order — main ones by section, answers to items, not confirmed, minor, typos — with its number in the
  report, the check that found it, "⭐ in Key points", "📎 per a basis document", how many checks found it and the
  quote; a mark ✅ keep / ➖ minor / ❌ wrong with a reason from a list and a comment; a table for the expert's own
  findings that MINT missed. Marks are saved at once and tied to the finding's text, so they survive a re-check.
  15 findings per page, a filter by block and "➡️ To unmarked".
- **"My findings"**: those marked ✅ (optionally ➖) and the expert's own — as Word (a table: No., section, finding,
  severity), Markdown, or Word comments in the reviewed document.
- **Assessment file for improving MINT** (`mint-review/1`): one review ("📤 Download the assessment (.json)") or all
  reviews with marks ("📥 Download the assessments (.jsonl)" in "📂 Saved reviews"). With finding texts by default;
  "Without finding texts" keeps only check kinds, severity, marks and reasons — no texts, quotes, sections, comments
  or file names. `tools/review_stats.py` summarizes many files in Markdown: the share of correct findings by check
  kind, report block, severity, "Key points", basis documents, model; reasons for "wrong"; how many findings experts
  added; text examples.
- **Update in place**: `update.sh` / `update.bat` take a new version (a .zip or a folder), replace the code folders
  entirely, keep `.env`, `config.yaml`, `glossary.json`, `checklists.yaml`, `prompts.yaml`, `.venv`, the base and
  logs (even if the archive has its own), and run `install.sh` (with the offline bundle if the new version has one).
  The MINT version is shown at the bottom of the sidebar.
- **A quick guide for users** — [docs/QUICK_GUIDE.md](docs/QUICK_GUIDE.md): starting, a review, assessing findings,
  handing over assessments, updating.
- `docs/SECURITY.md`: `LOG_DIR/audits/` and the assessment file are added to "What is stored where".
- **Basis documents — fixes after a run on a real security guide** (two specifications by code; Qwen 27B found 0
  and 2 partly of 20 reference findings with both specifications chosen by hand):
  - by title, a base document no longer matches through its own references: a guide or an explanatory note
    developed under the same specification ("developed in accordance with … Technical specification …") is not
    taken for the specification. The code is looked for further into a base document (the approval sheet) and not
    in its "Referenced documents";
  - fragments for a section: only one of the two specifications reached the checks in practice (147 fragments
    against 19), and mostly the abbreviation list and general requirement sections —
    they share words with any section. Now abbreviation, term and contents sections are not taken, the word score
    does not favour long lists, closeness in meaning is added (the base's own vectors, one embedding per section),
    and each basis document gets an equal share of `audit_basis_max_chars`;
  - the log tells what MINT found itself and how, what was added and what was removed by hand: before, everything
    that passed through the block on the tab was "chosen by hand".

- **Duplicates in the pieces of one long section**: a table of dozens of rows is reviewed in pieces, and the model
  writes about the same gap in every piece in its own words (on a security guide — about 10 times the same
  gap). Findings from different pieces of one section are now merged
  without the model at 40 % word overlap instead of 80 %; findings of one answer are never merged. The log shows how
  many.

- **Basis documents** (`audit_basis_docs`, `audit_basis_max_chars`, the "📎 Basis documents" block on the review
  tab): MINT takes the document's references to its basis — on the title page ("developed in accordance with …
  Technical specification for development (code)") and in "Referenced documents" — looks them up in the knowledge
  base by code (at the start of a base document; a document that only refers to the code does not count) or by
  title, and adds their fragments closest to the section to every section check and to the answers to items, as a
  separate block "the document must comply with them". On a security guide with 20 reference findings Qwen 27B found
  1 of 20 without help; with a "special attention" hint that brought the specification's requirements into every
  check — 5 and 2 partially: the requirement that concerns the whole document (where the data goes) is worded
  differently in a section, and search by section text does not find it. Now this happens without a hint. The block
  shows what was found and by which reference and what is not in the base; a document can be removed or added. The
  log has a "Basis documents" line.

- **Fewer false findings of the checks without the model** on technical documents (a security guide with large
  tables of servers and firewall rules): (1) abbreviations — parts of server, account and path names ("CORP\\Admins",
  "srv.CORP.local"), document codes ("…ТЗ.2"), product names ("Astra Linux SE"), words in capitals that also occur in
  ordinary spelling ("НЕТ", "ТЕСТ", "ВАЖНО") and well-known IT terms (SSH, NTP, TLS, TCP/UDP, DB, OS …) are no
  longer reported as undefined; (2) contents against headings — "Appendix A" added by Word numbering and table
  captions in the contents no longer count as missing sections; (3) empty table columns — group rows spanning the
  table ("Zone …") and an empty "No." column no longer make filled columns look empty; (4) the document type for the
  checklist is taken from the title (a short line or table cell, not in quotes), not from a reference to another
  document such as "… Technical specification for development" or "based on the technical specification …".

- **The deep review recognizes a process described without a table**: until now the questions about each pair of
  steps, each process requirement and the boundaries were asked only when the process was a table of operations. Now
  MINT also takes the steps from a list (numbered, "Step 1. …" paragraphs, or a bulleted list after a lead-in such
  as "The exchange goes as follows:") and from "Step N" subsections. Lists of requirements ("… must …"),
  participants, terms and short name lists are not taken for a process. The log header says which descriptions of a
  process were found ("“2.1 Exchange procedure” — list, steps: 4") or where MINT looked if it found none. The
  prompts of the process questions say "process steps" instead of "table of operations".

- **Diagrams brought up to date** (architecture and engineering, EN and RU): the review flow now shows passes 2–3,
  the answers to "special attention" and the checklist after the other checks and with their findings, merging that
  keeps different process steps apart, "Key points", reasoning for the review and raw model answers; the system card
  draft — in the knowledge base flow, as a separate row of panel 8 (mint/cards.py), in the "company specifics" table
  and in the service load table; the "⚙️ Review settings" block, MINT_CHECKLISTS and the shared pause on HTTP 429.

- **A system card draft from the knowledge base** (sidebar → "📌 For the review" → "🗂️ Draft a system card from
  the base"): MINT asks the base one narrow question per card section — names, purpose, services, limits, data
  protection, storage, plans, limitations, connection, requirements for neighbours — and puts a draft together on
  the card template: only what it finds, each fact with its source, "not in the base" where nothing is found,
  "check" where a reference does not lead to a fragment found. It downloads as .md; an expert checks it, adds
  limitations and plans and loads the card into the base. Works with any model and any base; the prompt is
  editable in "📝 Prompts".

- **Merging duplicates keeps different process steps apart**: in a DeepSeek run the deep review found "at step 3
  the recipient cannot read a file encrypted for another certificate" three times (transitions 1 → 2, 2 → 3,
  3 → 4), and the merge folded all encryption findings into one about step 4 → 5, so a reference finding was lost
  (as it had happened before). Now findings that start with different steps sharing none ("step 2 → step 3" and "step 4 →
  step 5") are not merged — neither by the model nor by word matching; the log shows them "kept apart (another
  process step)". The merge prompt says the same, but the model broke the rule — now the code keeps it.

- **The "Now" line under "⚙️ Review settings"** also shows duplicate merging and reasoning — the same way as the log
  header ("off", "as configured on the server", "on for the review"): merging turned off or reasoning is visible
  before the run, not only in the log.

- **"Whole document in one request" together with the deep review**: statements for the contradiction check and
  typos are now looked for section by section, as in the normal mode; in this mode they used to be one question
  for the whole document (and at most six typos were taken from it).

- **A point answer without severity tags**: in a DeepSeek run the model answered a "special attention" point
  with a list of a dozen findings but without [MEDIUM] tags — MINT glued them into one paragraph of the answer,
  and they did not count as findings (not merged with others, not in the annotated document). Now, if the answer
  has no tags at all, the list items after the "Answer:" line are findings of medium severity. The formatting
  check is clearer: "Clauses formatted as plain text instead of a heading: …" — the reference comparison took
  the old wording ("missing from the structure") for a finding about a missing clause.

- **Embeddings in batches again**: since the "review without noise" change, a batch request to the embedding
  model failed in MINT's own code (stray lines from streamed answers) and was silently replaced with one request
  per text — loading documents into the base and finding norms were slower by the batch size (`embed_batch_size`).
  The results did not change; now a batch is one request.

- **All review settings in one place**: the "⚙️ Review settings" block on the review tab — knowledge base, deep
  review, whole document in one request, self-critique (it used to be in the sidebar's main settings), merging
  duplicates, "Key points", systems, passes, reasoning, parallelism, limits and context sizes. Below the block — what
  is on now; the sidebar's "Expert settings" no longer have review settings.

- **"Key points" at the top of the report** (`audit_summary_max`, 12 by default): an editor model picks the most
  important findings — gaps and errors in the process, contradictions, numbers that do not add up, violations of
  norms — and writes the gist of each in one line with the number below ("→ no. 14", "→ special attention 2,
  no. 1"). It is a pointer, not a copy: the number of findings and the comparison with a reference do not change.
  If the model does not answer, the findings found by several checks and critical ones are taken.

- **Several passes** (`audit_passes`, 1–3): the section check and the deep review questions about the process,
  requirements, figures and contradictions are repeated with temperature at least 0.4; the findings of the passes
  are merged, and a finding shows "found: 3 (checks — 2, passes — 2)". What one pass misses by chance another
  finds, and what is found several times ranks higher in the report. The log shows what each pass produced.

- **Review with reasoning** (`audit_reasoning`): the model reasons before every review answer even if reasoning is
  off for the chat; 6000 tokens for reasoning are added to the answer length, the timeout is at least 300 s. The
  log shows whether the model actually reasoned.

- **"Special attention" answers agree with the other checks**: in a Qwen run the answer to a point was "no, no
  problem" — based on the model's guesses — although other checks had found two findings on that topic. Now the
  answers to points come after the section check and the deep review and get their findings: the answer must agree
  with them and need not repeat them. "No problem" only with a verbatim quote from the document; if the document
  does not say so — "not clear from the document" and what is not described. The same for the checklist: "yes"
  does not contradict what was found.

- **Self-critique does not drop process gaps**: in the same run it dropped findings about how a file gets from one
  system to another as "implementation details" and based on an assumption about what the systems are for. Now
  findings about who performs a step, through which system data is passed and whether the recipient can read it
  are not dropped that way; a finding may be dropped only if the text of the document or the norms refute it.

- **Raw model answers**: the review tab has "📥 Download raw model answers" next to the log. The file lists every
  request of the review, the re-check and the comparison with the reference: which check asked (a part of the
  document, a deep-check question, a special-attention point, the duplicate merge, the comparison), how long the
  answer took, what was asked (the start and end of the request; the whole document as a note) and what the
  model answered — word for word, before parsing into findings. It shows whether the model or MINT's parsing of
  its answer went wrong.

- **JSON with line breaks is not a loop**: Qwen writes JSON answers indented, and the line '"verdict": "FOUND",'
  repeats for every object — the loop guard cut such an answer at the third repeat and removed the repeats: in the
  reference comparison items 3–6 lost their verdicts and 7–9 never arrived. Short JSON fields ("key: short value")
  no longer count as repeats; identical findings or whole objects still do. Comparison: a verdict in any form
  ("✅ found", "Not found", "Partially", "Yes"); items without an answer or with an unclear verdict are asked
  again in batches of 3; the error says which items were not compared and why.

- **Other models (a run on Qwen 27B)**: answers are parsed however the model formats them:
  - a finding without a leading "-", with the tag after a label ("step 3 → step 4: [MEDIUM] …"), and any line
    break (\r, the Unicode line separator) is a separate finding; such findings used to be glued to the previous
    one (on Qwen — 5 of 40 deep-check answers);
  - JSON in a model answer: extra text with brackets before and after, trailing commas, objects without an array
    and a cut-off answer (whole objects are taken);
  - comparison with a reference: if the answer for the whole reference is not parsed, the reference is compared
    in batches of 3 items; if it still is not parsed, the error shows the start of the model's answer. On Qwen the
    comparison did not run at all ("answer not parsed"), although all 9 reference findings were in the review log.

- **Gateway asks to slow down (HTTP 429)**: MINT used to wait 2–5 s ignoring Retry-After, other threads kept
  sending, and the end-of-review retry ran at once with a single attempt — in a real run 16 of 34 deep-check
  questions and the duplicate merge failed this way. Now the pause is shared by all threads — as long as the
  gateway asks (Retry-After), otherwise 5, 10, 20 s (at most 60); a 429 gets at least 4 attempts whatever
  `llm_retries` is; the review log shows how many times the gateway asked to slow down and how long the pauses were.

- **Header with the sidebar collapsed**: Streamlit paints its top bar opaque, and the MINT title went half under
  it; now the page starts below the bar. The UI preview has a "sidebar collapsed" scenario that checks the
  header does not go under the bar.

- **More precise review** (from three deep-check runs on real requirements: the model finds all 8 important
  findings every time, but only 27–40 of 150–240 findings per run relate to them):
  - the step-transition question: the model wrote one finding per each of the 4 prompt questions for every
    transition; now at most two problems of this very transition, nothing common to all steps (format checks,
    deadlines, failures), the "where does the result go" question only if the next step does not use it; limits by
    question kind (`DEEP_KIND_MAX`): transition — 2, requirement — 2, boundaries — 3, contradictions — 2, the rest
    is shown in the log;
  - section check, "special attention" and self-check: a wish "requirements for … are not specified" is a finding
    only if the document itself or a norm from the knowledge base requires it;
  - contradictions only about the same subject; a finding whose last sentence itself says "no problem" / "no
    contradictions found" does not reach the report (the log shows how many were removed);
  - within a report section, findings found independently by several checks come first (marked "found by
    checks: N"), then by severity;
  - the log shows each group of merged duplicates: what was kept, what was merged in, what was kept apart;
  - typos: "no error" lines are removed for phrases longer than 200 characters too.

- **Merging duplicates without losses**: on real requirements two reference findings disappeared after merging,
  although the model had found them — the model merged findings of one deep-check question about different problems
  of one step, and a typo with other typos of the section, and the report kept one wording of the group. Now
  findings from one model answer (one part of the document, one deep-check question, one "special attention" point)
  are not merged with each other; typos are not sent to the model for merging — a repeated typo is recognised by the
  phrase being corrected, and lines where "correct" equals "as written" and the model itself says "no error" are
  removed. The merge prompt says: the same place in the document is not a reason to merge findings that ask
  different questions about it.

- **Universal report**: the main findings are grouped by document section, in document order, instead of the
  fixed topics "Information security", "Functional requirements", "SLA", "Architecture"; the report and the
  verification matrix are no longer titled "of the Architecture Board"; the self-check no longer asks for a topic.
  Less noise: a section check asks for at most 10 significant findings (was 20, the model filled the limit), and a
  finding that starts with a clause of another part of the document is dropped — on real requirements the first
  part (title page, contents, abbreviations) gave 19 findings, 15 of them about 2.2.3 and section 4. A finding's
  section is taken from the clause at its start. Formatting checks: bold contents lines and bold table headers no
  longer give false "missing from the contents" and asterisks in column names.

- **Expert knowledge in the review** — what a document cannot know about itself:
  - checklists by document type: the type is recognised by words in the file name and at the start of the document
    (or chosen by hand); each item is a question over the whole document with the answer "yes / partially / no /
    not applicable" and findings, the report has a "Checklist" block; items are edited on the review tab and saved
    to your own `checklists.yaml` (outside git; example — `checklists.example.yaml`);
  - knowledge base documents marked "📌 Always use in the review" (expert rules): the model gets them in every check
    on top of the norms found by search, in full or the closest fragments (`audit_pinned_max_chars`);
  - system cards ("🗂️"): a card is added to the check of a section that mentions the system (names from the
    "Names:" line and the heading, with word endings); for each system mentioned at least twice the model lists
    what the document requires from it — available, planned, change needed, conflict, unclear (`audit_systems`);
  - "special attention", checklist and system questions run in parallel (`audit_parallel`); the slider is now
    called "Review: requests to the model at the same time".

- **Review without noise** (after a deep review run on real requirements: 9 of 9 reference findings found, but
  about 300 findings in the report, one part looped into 420 identical lines, and the gateway ignored the length
  limit):
  - review answers come as a stream: MINT itself cuts off an answer far beyond the length limit or a looping one
    (`llm_stream`); a gateway without streaming gets an ordinary request, and MINT remembers that;
  - identical lines within an answer are dropped, at most 25 findings are taken from an answer (a narrow question
    — 6, "special attention" — 10, the whole document — 40), critical first;
  - the self-check runs in batches of 15, merging duplicates — in batches: previously both silently did nothing on
    a long list;
  - the report starts with the main findings; minor and general ones (low, without a quote or a place) and typos
    come in separate blocks;
  - sections are reviewed in parallel (`audit_parallel`); the log shows the wall-clock review time and the sum over
    sections;
  - a finding based on a norm ends with a [Source: file, section] reference; a reference to a file the model did
    not receive goes to "Not confirmed";
  - the comparison with a reference is stricter (a general finding does not count for a specific one) and shows
    how many findings the report has and how many of them match the reference;
  - whole document in one request: norms are searched for each section, not by the title page; the answer is at
    most a quarter of the model's window; the progress message no longer says "up to 4500 chars".

- **Deep review** (`audit_deep`, on by default) — so that not only a strong model finds gaps in a process and
  contradictions. The review is broken down into narrow questions that a medium-sized model answers reliably:
  - process: the code finds tables of operations; questions on each pair of neighbouring steps (where the input
    comes from, who passes it on, whether the recipient can read the data — encryption for whose certificate), on
    each process requirement (is there a step, no contradiction), on the process boundaries (start, end, a result
    for each consumer);
  - contradictions: the model lists the statements of the parts with a topic from a closed list; statements on one
    topic are compared (also within a section);
  - figures: the program lists and recalculates the indicators (per day × 365 against per year, average and
    maximum), the model judges the ready calculations;
  - typos — in each part.
  The questions run in parallel (`audit_parallel`, 3 by default), at most `audit_deep_max_calls` (60): the process
  and figures first. Questions lost to a gateway failure are retried together with unchecked sections.
- **Formatting without the model:** a clause formatted as plain text instead of a heading; the contents against the
  headings; empty tables, columns and fields; a step of the table of operations without a performer, service, input
  or result; an empty section.
- **Whole document in one request** (a checkbox on the tab, for comparison): one review — the whole document, an
  answer of up to 4000 tokens, a timeout of at least 300 s; if it does not fit into the window — review by section
  with a warning.
- **Comparison with a reference** below the report: expected findings → which the selected model found (found,
  partly, not found), a table to download. This is how models and settings are compared on one document.

- **Review: fewer duplicates, false "not described" findings and made-up references.** Based on a report on real
  functional requirements (14 parts; about 20 of 72 findings were duplicates, fragments and splitting artefacts;
  the key finding on the process was missed).
  - Parts follow the document's sections: a heading with its text and tables; a section up to 1.5 part limits is
    not split (a process table stays whole with its heading); a continued large table is marked. Tables from
    Docling are compacted — padding doubled the document. Real requirements: 6 parts instead of 14.
  - The whole document goes into every section review and self-check if it fits into the model's window
    (`audit_full_document`); otherwise the outline does, and "not described" findings are checked against other
    sections. Each part knows its place in the document. A "walk through the process step by step" rule.
  - "Special attention": one answer per point from the whole document (an "Answer:" line and findings) in a
    separate block of the report. Previously every part answered each point, and parts without the process wrote
    "the process is not described".
  - Without the model: abbreviations used without a definition, and defined but unused; references to tables,
    clauses and acts and figures in findings that are neither in the document nor in the norms go to the "Not
    confirmed by a source" block.
  - A sub-item of a finding ("deadlines and stages of the transition;") stays in its finding.
  - The model merges duplicates (+1 call, `audit_merge_duplicates`); each finding shows its section.
  - Special attention answers the model did not return are retried together with unchecked sections.
- **"Typical value" model window** (32768) — a README note: the server did not report the window, set it manually.

- **Timeouts in the review.** Sections the model did not answer (timeout, busy gateway, network) are checked
  again at the end of the review with a longer timeout (twice the setting, at least 180 s), unless no section
  was checked at all; "🔁 Recheck unchecked sections" rechecks only
  them and rebuilds the report. The review log shows how long each section took and on which attempt it was
  checked. The timeout message says what to change instead of suggesting to lower max_tokens.
- **"Turn off model reasoning"**, independent of the model: the standard switch-off parameter of vLLM and
  SGLang chat templates; a gateway that rejects it gets the request without it, and MINT remembers that. MINT
  notices reasoning in the answers (`reasoning_content`, reasoning tokens, `<think>`) and suggests the switch.
  `llm_extra_body` / `LLM_EXTRA_BODY` — your own request parameters for any gateway.
- **.pdf, .md and .txt** in the knowledge base, document review and fix verification (previously .docx only).
  - PDF is read from its text layer without models (pdfplumber): nothing is downloaded, nothing leaves the
    computer. Headings come from the PDF bookmarks, otherwise from the "Contents" page with dot leaders, slide
    titles or font size; running headers and footers, page numbers, the ESKD frame and stamp and the contents
    pages are removed; ruled tables become Markdown. The upload message says where the structure came from.
    Checked on 13 real PDFs (1388 pages, about 2 minutes): headings from bookmarks — 395 of 398, from the
    contents page — 111 of 114.
  - A scan without a text layer or a PDF with damaged fonts is not indexed: MINT says why and what to do.
  - .md: `#` headings and tables; .txt: numbered and capitalised headings, UTF-8 / UTF-16 / Windows-1251.
  - The review adds Word comments only to a .docx; other formats get the report and the log. The manifest
    records each document's format and structure source.
  - New dependency: `pdfplumber` (MIT).
- **Installation without PyTorch.** `requirements.txt` installs Docling's slim build `docling-slim[format-docx]`
  (only the .docx reader): no PyTorch, OpenCV or models — 66 packages and about 0.6 GB instead of 114 and 2.1 GB;
  the Docker image no longer needs the PyTorch index or the OpenCV system libraries. A mirror without
  `docling-slim` can still use `docling>=2.0` (`docs/INSTALL.md`). The self-check accepts either.
- **Prompts as data.** Every text the model receives is now in `mint/prompts/en.yaml` and `ru.yaml` — one key per
  text, `{{name}}` placeholders — instead of being spread over six modules. The texts were moved unchanged (the
  model requests in the tests are byte-for-byte the same). `prompts_version()` — the language and a hash of the
  set — is saved with every 👍/👎 rating (at answer time), in the review log and in quality-check results, so a
  result can be traced to the prompts it was produced with. `tests/test_prompts.py` checks that both languages have
  the same keys, placeholders and number of rules, and that the answer format the code parses is still in the
  prompts. PyYAML is now required (it was already in `requirements.txt`).
- **Prompts in the interface** (sidebar → "📝 Prompts"). The texts for the models — chat, follow-up rewrite,
  paraphrase, section review, self-critique, fix verification, draft questions — are edited in the interface
  language, with what each one does and what must stay in it:
  - "Try in this session" — the edit applies only in this browser window; "Save" — to `prompts.yaml` next to the
    program (`PROMPTS_PATH`), for everyone and after a restart; "Return to default". Only the edited texts are
    stored, so MINT updates still reach the rest; if a default changes after your edit was saved, the page
    warns and shows the difference;
  - "Check the edit" applies it in the session and opens the quality check with chat answers on the previous
    check's questions (asked twice); the result is compared with the previous answer check;
  - the answer format the code parses and the `{{…}}` placeholders cannot be removed: such an edit is not applied
    (a hand-written `prompts.yaml` too), and the page says what is missing. The defaults are unchanged;
  - the prompt version includes your edits; ratings, review logs and quality checks also record which prompts
    were edited (`prompts_custom`). A longer chat or review prompt reduces the room for fragments in the model
    window accordingly. In Docker the edits are kept in the data volume (`/data/prompts.yaml`).
- **Russian prompts aligned with the English ones.** Rules that existed only in English: answer in the language
  of the question; keep the language when rewriting a follow-up question or rephrasing a query; quotes verbatim
  in the original language, explanations in the interface language (a translated quote is not found in the
  document, and a finding loses its place or a fix its "fixed" status). Matters when the question or the
  document is not in Russian while the interface is.
- **Quality check: chat answers.** Each failure is attributed to search (the right fragment was not in the
  context) or to the model (false "no information", no reference to the right document, references outside the
  fragments found, an answer to a question the base cannot answer). "No information" is recognised by the
  `chat_no_info` phrase of the prompt. Each question can be asked 1–3 times. Results record the prompt version,
  language and model and are compared with the previous check with answers, question by question (sign test),
  listing what changed in the settings. A filter "answers with errors"; answers.csv has a row per answer. From the
  console: `eval_search.py --answers [--repeat N] [--quick]`.
- **Scenarios in the core.** `answer_question()`, `run_audit()` and `verify_remarks()` run a whole chat answer,
  document review or fix verification without the interface; the tabs only render. Feedback settings also record
  the language, chat history depth, abbreviation list and reranker weight.
- **Quality check in the interface** (sidebar → "Quality check"), so the search can be tested on the real base
  in a closed network without CSV files or a console:
  - MINT writes questions from fragments of the base (in the fragment's language) or reuses the last check's
    set; questions are edited in a table, your own rows are added there, and questions the base cannot answer
    are marked with "— not in the base —";
  - before the run, labels that can never be counted are flagged (the phrase or section is not in the
    document), and the fragment each question was written from is shown with the answer highlighted;
  - results: hit@K, hit@1, MRR and false alarms with changes since the last check; configurations compared
    with a sign test; recommendations applied to the session with one button (and a `config.yaml` snippet);
    the questions search gets wrong; downloads. Optionally the chat answers every question: does it cite the
    expected document, does it cite anything outside the fragments found, does it refuse honestly;
  - every check is saved to `LOG_DIR/eval/<date_time>`.
- **Evaluation core in `mint/evaluation.py`.** `eval_search.py` is now a thin console wrapper over it; its report
  follows the interface language (`MINT_LANG` or `--lang`). Repeated service requests within a run are cached
  per run (`services.request_cache`) instead of replacing service functions at run time.
- **Interface.** A theme of its own, with motion where it shows what happened:
  - the header draws itself once on load; a thin line at the top moves while MINT is working;
  - audit and fix verification open with a verdict stamp ("Needs rework", "Findings to address", "Approved",
    "All fixed") and counters by severity or status;
  - chat: your question on the right, the answer as a card, sources as a numbered list (document › section,
    scores below), an empty chat lists the documents in the base;
  - fonts (Onest, Unbounded — OFL) are served from `static/` by Streamlit itself (`enableStaticServing` in
    `.streamlit/config.toml`): nothing is loaded from the internet. Started from another folder, MINT falls
    back to system fonts;
  - `prefers-reduced-motion` turns all motion off; the layout works on a phone.
- **Reference check in chat.** Every `[Source: file, section]` in an answer is compared with the fragments the
  model actually received: the file must be among the sources and the section among that file's headings.
  References outside the context are marked ⚠️ and listed in a warning under the answer (they usually point to
  a made-up statement). No extra model call; invalid references are also saved with 👍/👎 feedback.
- **Adjacent fragments joined.** When search returns neighbouring fragments of one document, they reach the
  model as one block in document order, without repeating their overlap. Blocks stay in relevance order.
  Works for existing knowledge bases too.
- **Long fragments cut around the match.** A fragment longer than the context limit is cut around the matched
  passage (the child found by vector search, or the densest place for the question's words) instead of from
  its start; the nearest heading above the window is kept so that the section in the reference is right.
  Tables keep their title and header rows. Before, the matched text at the end of a long fragment was lost.

- **Chunking.** Fragments are cut at a paragraph break first, then at a line, a sentence and only then at a word
  (before, the cut almost always fell on the last space, mid-sentence). A heading no longer ends a fragment
  apart from its text, and overlaps start at a whole word. Applies to documents indexed after the update —
  re-index the base to apply it to existing documents.
- **Fragment truncation.** A fragment that starts with a heading line followed by a long paragraph without full
  stops was cut down to the heading alone; now at least half of the limit is kept.
- **Review sections.** A paragraph longer than the section size (typically a large table) is split — tables by
  rows with the header repeated — instead of becoming one section several times over the limit that did not fit
  the model window. A heading at the end of a section moves to the next one, together with its text.
- **Embeddings (hardening).** Vectors from a batch response are matched to texts by the `index` field of the
  OpenAI-compatible API, not by their position in the response. Common servers keep the order; this protects
  against gateways that do not.
- **Abbreviations.** Search also works in the other direction: a question with the full form ("information
  security tools") finds fragments that use only the abbreviation.
- **Fix verification (hardening).** If the model answers "fixed partially" instead of one of the requested
  statuses, it is shown as partial, not as fixed.
- **Search evaluation report** (`eval_search.py`).
  - No empty cells in `details.csv`: for questions without an answer in the base the "Место" (place) columns say
    whether the "low confidence" signal fired; a missing reranker score says why; "> 10" means not found.
    New columns: share of question words in the context and dense/BM25 agreement.
  - "Where configurations differ": the current configuration against the best one, plain hybrid and
    vector-only search, question by question, with a sign test p-value — whether the difference could be
    chance. Replaces the rough "10 % of questions" rule.
  - "Questions without an answer in the base": did the signal fire, best reranker score, what was found.
  - No duplicate column when `top_k` is 3.
  - Question draft (`--generate`): when the model paraphrases the quote, the closest sentence of the fragment
    is used, so `contains` is filled more often.
- **Source labels.** A source in chat, review and the evaluation report is labelled with the section where the
  match is, not the section the fragment starts with (fragments often span several sections).
- **Diagrams.** `docs/MINT_architecture` and `docs/MINT_engineering` are brought up to date with 20.1 and the
  changes above (languages, feedback, merged and focused fragments, reference check, the confidence rule,
  chunking, English stemming). They are now generated by `tools/diagrams/`, and `tests/test_diagrams.py` checks
  that they match the code. The previews are regenerated (they still showed 19.1).
- **English diagrams.** `docs/MINT_architecture` and `docs/MINT_engineering` are now in English; the Russian
  versions moved to `docs/ru/`. Both are built from the same scripts (`--lang en`, translations in
  `tools/diagrams/en.py`), so they cannot drift apart.
- **"Low confidence" signal.** With a reranker, the signal now depends only on its best score
  (`low_conf_rerank`). Before, it also required few question words in the context and disagreement between
  dense and BM25 — but on questions the base cannot answer the topic's words are usually there, so the signal
  almost never fired even when the reranker scored every fragment low. Without a reranker the rule is unchanged.
  `weight_rerank: 0` keeps the order of plain hybrid search while the reranker still decides on the signal.
  `eval_search.py` calibrates the thresholds by the same rule and suggests `weight_rerank: 0` when hybrid
  search without the reranker ranks best.

## 20.1 — English interface and search

- **English interface.**
  - The whole interface, error messages, reports (review report, review log, Word comments, verification
    matrix) and the self-check are available in English.
  - Switch in the sidebar (🌐) or set `MINT_LANG=en` / `ru` in `.env`; the default is the OS language.
- **English prompts.**
  - Separate English versions of all model prompts.
  - In chat the model answers in the language of the question.
  - Model answers in either language are understood: severities, verdicts, categories, statuses.
- **English documents in search.**
  - A Porter2 stemmer for English words, alongside the Russian one. The language is chosen per word, so mixed
    documents work.
  - English stop words.
  - Query analysis: "what is …", "components of …".
  - Abbreviations: "Service Level Agreement (SLA)".
  - English words inside Russian documents are now stemmed too.
  - Title-case expansions keep their capitals.
  - The BM25 index is rebuilt automatically on first use.
- **Characters per token.** "Detect from server" measures it in the language of the knowledge base: on Russian
  text for a Russian base (as before) and on English text for an English one, so English fragments are not cut
  short. For a mixed or empty base it measures both and takes the lower value, so fragment sizes are safe for
  either language. The base's language is detected from the letters in its text.
- **Tests.**
  - `tests/test_i18n.py`: completeness of the translation, English prompts and parsing, English search, the
    English interface end to end.
  - The page smoke test also switches the language on real Streamlit.

## Documentation (after 20.0)

- MIT license.
- English documentation: `README.md`, `docs/INSTALL.md`, `docs/OLLAMA.md`, `docs/SECURITY.md`, this changelog
  and `CONTRIBUTING.md`. Russian versions moved to `README.ru.md` and `docs/ru/`.
- `.env.example` comments in English and Russian.
- `run_mint.sh` also opens the browser on macOS.

## 20.0 — MVP for collecting feedback

- **Modular code.** The `mint/` package: a core without Streamlit (settings, services, search, review, fix
  verification) and the interface in `mint/ui/`. Start with `streamlit run app.py` or the `run_mint.*` scripts.
  Behaviour, the knowledge base and settings are unchanged; `web_app_v19.py` is gone.
- **Feedback.** 👍/👎 buttons under chat answers, review reports and verification matrices, followed by an
  optional comment. Ratings go to `LOG_DIR/feedback.jsonl` with the question, answer, sources and settings; a
  summary and a download button are in the sidebar.
- **Installation without administrator rights.** `install.sh` / `install.bat` (including from an offline
  bundle), `run_mint.sh` / `run_mint.bat`, and the [installation guide](docs/INSTALL.md).
- **Self-check** `check_install.py`, step by step:
  - Python and packages, with a hint for Astra Linux's closed software environment;
  - parsing a test .docx;
  - `.env`;
  - folders;
  - connections to the LLM, embeddings and reranker;
  - Streamlit settings;
  - a smoke test that opens the page on real Streamlit without a browser.

  The output contains no keys.
- **Safe Streamlit defaults** (`.streamlit/config.toml`):
  - the page is reachable only from this computer;
  - no usage statistics;
  - no e-mail prompt on first start.
- **Windows.**
  - Corporate certificates are taken from the Windows certificate store (`truststore`) when `CA_BUNDLE_PATH`
    is not set.
  - The FAISS index is read and written correctly on paths with non-ASCII characters.
- Fix verification: the result no longer disappears after downloading files.
- A relative `MINT_CONFIG` path is resolved from the program folder.
- Trying MINT without a gateway: Ollama + Docker ([docs/OLLAMA.md](docs/OLLAMA.md)).
- Security notes: [docs/SECURITY.md](docs/SECURITY.md).
- **Tests.** Tests are in the repository (`python tests/run_all.py`) and run on GitHub Actions: Linux with
  Python 3.10–3.12, and Windows. This includes a smoke test of the page on real Streamlit.
- `kb_stats.py`: per-document knowledge base statistics and comparison of two bases.

## 19.3

- New name.
- Review works for any document submitted for approval, not only specifications.
- "Special attention" field:
  - the model checks these points first;
  - self-critique cannot drop findings about them without a refutation;
  - norms for them are searched once and added to every section.
- The report and the section log survive downloads. The review log can be downloaded separately: run settings,
  norm sources and what self-critique rejected, per section.
- Your own `glossary.json`:
  - an empty value removes a wrong expansion found in documents;
  - Windows-1251 encoding is accepted.

## 19.2

- `.env` is read without python-dotenv too, in UTF-8 (with or without BOM) and Windows-1251.
- An empty system variable no longer overrides a value from `.env`.
- The sidebar shows which `.env` was read, or where MINT looked for it. On connection errors it shows the
  cause: key, address, certificate or no connection.
- Server responses are re-checked immediately after the key or certificate is fixed.

## 19.1

- **Chat history.** The chat uses its history: a follow-up question ("and for the second circuit?") is
  rewritten into a self-contained one.
- **Model output.** Reasoning blocks (`<think>`) are removed from answers, and a truncated answer is marked.
- **Source links.** A link points to the section inside a fragment, not only to the first one.
- **Search.** Question words are ignored by search, and a partial reranker failure no longer distorts the
  ranking.

## 19.0

- **Reranker.**
  - It scores all candidates (not just the first 6).
  - For each document it gets the most relevant part: the fragment found by vector search, or the window
    densest in query words.
  - If the candidates do not fit into one gateway request, several requests are sent.
- **Search.**
  - Vector search and the reranker get the original question.
  - Expansion words are added only to BM25, with a low weight.
  - The exact-phrase boost targets the subject of the question.
- **Embeddings.** The instruction prefix is chosen by model name (Qwen3-Embedding, e5, FRIDA…). Vectors are
  normalised, so search uses cosine similarity.
- **Review.**
  - Self-critique returns a category and a verbatim quote.
  - In the annotated document each finding is attached to one place as a Word comment; the text itself is
    not changed.
- **Speed and safety.** Writes to the knowledge base are locked, and BM25 for long queries is tens of times
  faster.
