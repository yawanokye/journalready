# Article Topic Idea Relevance Fix

Version 1.3.1 addresses the issues identified in the exported topic-idea report.

## Independent article mode

- Hides and disables source thesis or dissertation fields.
- Clears those fields before the request is sent.
- Removes thesis and dissertation language from AI and fallback outputs.
- Treats ideas as proposed studies and does not imply that results already exist.
- Caps readiness when method, data, variables and journal fit have not been supplied.

## Scholarly source relevance

- De-duplicates repeated title, area and country text in search queries.
- Searches ERIC only for education-related topics.
- Applies a conservative title and abstract relevance gate.
- Rejects country-only matches and records that share only one broad word.
- Preserves older exact or foundational matches instead of allowing recent weak matches to displace them.
- Shows matched topic signals in the interface.
- Displays a clear message when no record is relevant enough to retain.

## Research route and resources

- Recognises yield-curve, term-structure, interest-rate, exchange-rate, inflation and related finance topics as secondary-data research by default.
- Does not recommend questionnaires or qualitative instruments for those topics unless explicitly requested.
- Removes broad fallback resources when no substantive match exists.
- For term-structure topics, the structured fallback now proposes specific finance article directions rather than generic placeholders.

## Tests

The package passes 11 automated tests.
