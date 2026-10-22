---
name: research
description: Research for waitwhat videos - read URLs and documents with Jina Reader (scripts/fetch.py), search the web, verify facts and numbers, and build the company-explainer story (everyday problem → what they built → concrete example → how they make money → who uses it). Use for company URLs, attached papers/decks, current events, or any topic where a fact or number will be stated in the video.
---

# Research

The video will state things as true in a confident voice, so every fact must be checkable.
**No invented facts, numbers, quotes, customers or features.** If you can't verify something,
leave it out or say plainly that it's uncertain. Simplifying is fine; inventing is not.

## Tools
- `ww fetch <url>` → `workspace/research/<slug>.md` via Jina Reader (`https://r.jina.ai/<url>`,
  `JINA_API_KEY` optional for higher limits). Works for web pages and online PDFs. Each file
  records its source URL and fetch time.
- Web search: `ww fetch --search "…"` (live web search through OpenRouter on `OPENROUTER_API_KEY`;
  the findings and their source URLs are saved to `workspace/research/search-*.md`). Several searches
  in one call run in parallel. Use it for anything recent or anything you aren't sure of.
- `workspace/research/` may already hold the planner's web findings (facts it found online, with
  sources) and pages it read: start from them.
- Attachments in `inputs/`: read them directly (PDF, images, text). They are the primary source
  when present; the video explains *them*, not the general topic.

Keep notes in `workspace/research/notes.md`: each claim you plan to use, with its source file or
URL. Put the sources you relied on into `plan.sources`.

## Topic mode
For timeless topics (math, classic physics) your own knowledge is usually enough; check any
specific number, date or name you're not certain of. For recent or contested topics, search first
and prefer primary sources (papers, official docs, the organisation's own pages).

## Attachment mode
Read the whole thing. Identify the one question it answers and its single most important
figure or result. Use its real numbers, labels and terminology (explain the terminology).
Credit it in the narration naturally ("in this paper, the authors…").

## Company mode (the prompt is or contains a company URL)
1. Fetch the homepage, then the pages that answer the story's questions: product/features,
   pricing, customers/case studies, about, docs or a "how it works" page. 4–8 fetches is typical.
2. Search for independent context only if needed (what category they're in, how the problem is
   usually solved). Don't name or compare competitors in the video.
3. Fill this arc, in plain language, with something concrete at each step (see
   `references/company-arc.md` for questions and an example):
   - **Founding story** (when it is documented): the founders, the problem they hit, the
     turning point. It is often the best hook. Names, dates and famous lines need a source each;
     leave out anything you can't confirm.
   - **Everyday problem**: a specific person and a specific moment of pain.
   - **What they built**: one sentence a 12-year-old would understand, then one level deeper.
   - **Concrete example**: one real use case, walked end to end (from their docs or case study).
   - **How they make money**: only what their pricing page or reliable sources say.
   - **Who uses it**: customer categories or named customers they publicly list.
4. Tone: curious and fair, not an ad. No superlatives you can't back ("leading", "best").

Mark anything you couldn't verify in notes.md and keep it out of the narration.
