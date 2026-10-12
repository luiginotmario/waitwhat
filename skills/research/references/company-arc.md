# Company explainer: questions to answer and an example outline

## Questions (answer from sources, cite in notes.md)

| Beat | Questions | Where to look |
| --- | --- | --- |
| Everyday problem | Who has the problem? What does a bad day look like for them? What does it cost (time, money, risk)? | homepage hero, case studies, blog "why we built" |
| What they built | What does the product *do*, in a verb phrase? What's the input and output? | product/features pages, docs overview |
| Concrete example | One real scenario, start to finish: who, what they put in, what happens, what comes out | case studies, docs quickstart, demo pages |
| How it works (optional) | The one mechanism worth seeing (an API call, a matching step, a pipeline) | docs, engineering blog |
| How they make money | Who pays, for what unit (seat, usage, transaction %, subscription tier)? | pricing page, terms, investor/about pages |
| Who uses it | Categories of users; named customers only if the company lists them publicly | customers/case-study pages, logos section |

If pricing isn't public, say "they sell to businesses" only if that's stated; otherwise omit the
money beat or say pricing isn't public.

## Example outline (fictional company, to show the shape only)

1. *Hook*: "It's 11 pm and Ana has forty supplier invoices, in three languages, to type into her
   books before the month closes." (person icon, a pile of papers growing)
2. *The real problem*: invoices arrive as messy PDFs; copying them by hand is slow and error-prone.
   (one invoice zooms in; fields highlight one by one)
3. *What they built*: "a service that reads an invoice like a person would and fills in the books
   for you." (node in the middle; papers flow in, tidy rows flow out)
4. *Concrete example*: one invoice → extracted vendor, date, total → matched to a purchase order →
   approved. (flow template with a pulse travelling the arrows)
5. *How it works*: one picture of the matching step, nothing more.
6. *Money*: "businesses pay per invoice processed" (coins along an arrow; only if sourced).
7. *Who uses it*: categories as small icons/labels ("accounting teams at retailers").
8. *Echo*: back to Ana, 11 pm, laptop closed.

Use `templates/company.py` and `templates/flow_causal.py` in the manim-scenes skill.
