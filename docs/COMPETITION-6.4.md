# TechDigital Prospect: competitive positioning for 6.4

Research date: 2026-10-20. Official vendor sources only. This is a positioning review, not a comparative performance benchmark. Vendor functionality is summarized from published documentation; product scope below is the supplied implementation scope. No price comparison is asserted.

## Where the product fits

**TechDigital Prospect by AliceLabs LLC is a local desktop workspace for preparing and investigating prospect CSVs, with reviewable evidence.** It occupies an earlier stage of the workflow than sending campaigns or managing replies. Its defensible appeal is local operation, explicit discovery configuration, field-level source/conflict review, and resumable investigation—not a larger database, better delivery, or universal replacement for an outbound suite.

| Product | Officially documented offering | Implication for TechDigital Prospect |
| --- | --- | --- |
| Hunter | Company discovery, Domain Search, Email Finder, bulk verification, lead management, and automated email sequences. Hunter states its data comes from the public web. [H1] | Public-web discovery alone is not unique. Emphasize the local CSV investigation workflow and evidence users can inspect. Do not describe Hunter as merely a paid third-party database. |
| Apollo | A maintained contact/company database, search, CSV/CRM enrichment, data health monitoring, API access, and outreach sequences. Its documented data inputs include contributors, engagement signals, public crawling, and third-party providers. [A1–A2] | Position the configurable web-discovery approach as a different workflow. Do not imply equivalent coverage, phone data, CRM functionality, or engagement-derived verification. |
| Clay | Configurable sequential enrichment through multiple providers; users can reorder steps, apply conditions, and expose the successful provider. [C1] | Call Prospect's feature a **web discovery waterfall** and name DuckDuckGo/Bing/Google. Do not imply access to Clay-style provider databases or claim that source visibility is unique. |
| Smartlead | Cold email campaigns, warmup, and a shared inbox for replies across mailboxes, with routing, follow-up automation, and reporting. Its help center also documents prospect search. [S1–S3] | Prospect prepares and checks data before use in downstream tools. It does not replace campaign execution, inbox handling, warmup, or prospect databases. Avoid labeling Smartlead only a sender. |

## Landing page recommendations

Publish under `https://techdigital.site/prospect/` and preserve the marketplace's existing root. Use **TechDigital Prospect** consistently; identify **AliceLabs LLC** as publisher. Mention NexusCold only in migration/release notes where necessary.

Suggested hero:

> Prepare prospect CSVs with evidence you can inspect.
>
> TechDigital Prospect brings CSV quality checks, configurable web discovery, website research, and email diagnostics into a local desktop workspace. Review sources and conflicts, then resume work from encrypted checkpoints.

Recommended content order:

1. **A concrete workflow:** import and map a CSV → investigate via configured search engines and websites → inspect field sources/conflicts and diagnostics → review results. Show real application screenshots with synthetic or consented examples.
2. **Three specific value cards:** CSV quality and mapping; web discovery with visible evidence; encrypted resumable local work. Include CLI availability as a secondary capability.
3. **Clear email-check scope:** DNS/MX and SMTP checks without a `DATA` command; exact-domain SPF/DMARC publication diagnostics. State that these are diagnostic signals and do not establish mailbox deliverability, effective authentication, inbox placement, or guaranteed acceptance.
4. **Optional adviser:** Ollama advice receives aggregate statistics and the user's question. Clarify the question itself can contain information the user types. Hosted `/api/chat` is an advisory gateway, not a hosted processing version of the desktop pipeline.
5. **A short fit guide:** suitable for users who want local CSV preparation and inspectable research; sending, inbox management, CRM, and maintained contact databases require other tools.
6. **An honest evaluation CTA:** “Download evaluation” only when a working release URL exists; otherwise “View setup guide.” Secondary CTA: “Discuss commercial licensing” to `mailto:legal@alicelabs.site`. Put AL1 noncommercial evaluation terms close to the CTA and link the full license. Do not advertise a free commercial application because an optional model can be downloaded without charge.

## Claims to keep out of the page

- “More accurate than Hunter/Apollo,” “better deliverability,” “zero bounces,” response or conversion uplift, or speed/coverage percentages without a reproducible comparative study.
- “All-in-one outbound,” campaign automation, inbox, CRM, paid-provider waterfall, or hosted lead processing.
- “Fully offline”: discovery, scraping, DNS, and SMTP checks contact external services. Prefer “local desktop workflow” and explain network-dependent steps.
- “Your data never leaves your device”: network queries and optional advisory requests require a precise data-flow explanation.
- “SPF/DMARC verified” or “deliverability guaranteed”: exact-domain publication diagnostics and SMTP probes have narrower meaning.
- “Open source,” “free commercial use,” or invented pricing inconsistent with AL1. Avoid competitor prices and database-size figures; they change and are unnecessary to explain fit.

## Proof to add before stronger marketing

Show one sanitized input-to-result example with missing fields, conflicting sources, and uncertain email status. Explain what encrypted checkpoints protect and how users resume. Add measured runtime/coverage results only after recording dataset composition, configuration, network conditions, failure handling, and methodology. Until then, use observable functionality rather than outcome promises.

## Official sources

All accessed 2026-10-20. Feature summaries are vendor-described capabilities, not independently verified outcomes.

- **H1:** Hunter, “What is Hunter?” (dated 2026-08-12): https://help.hunter.io/en/articles/11048031-what-is-hunter
- **A1:** Apollo, “Apollo Data Overview” (updated 2026-10-15): https://knowledge.apollo.io/hc/en-us/articles/45824429846669-Apollo-Data-Overview
- **A2:** Apollo, “Sequences Overview”: https://knowledge.apollo.io/hc/en-us/articles/4409237165837-Sequences-Overview
- **C1:** Clay, “Waterfalls”: https://university.clay.com/docs/building-a-data-waterfall
- **S1:** Smartlead, product overview: https://www.smartlead.ai/
- **S2:** Smartlead, “Unified Inbox for Cold Email Replies”: https://www.smartlead.ai/unified-inbox
- **S3:** Smartlead Help Center (campaigns, SmartProspect, warmup topics): https://helpcenter.smartlead.ai/
