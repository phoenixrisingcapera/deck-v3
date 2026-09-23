# Data Assets Layer

Decks depend on reusable data assets:

- companies
- people
- founders
- investors
- team members
- advisors
- logos
- headshots
- bios
- LinkedIn URLs
- company URLs
- sectors
- portfolio records

## Why this matters

Team slides, portfolio slides, investor intro slides, market maps, and contact slides all depend on structured people/company data.

## Product UI

```txt
/decks/[deckId]/data-assets
/decks/[deckId]/data-assets/people
/decks/[deckId]/data-assets/companies
```

## Asset audit examples

- missing founder headshot
- broken company URL
- missing logo
- bio too long for team slide
- person used in slide but not audited
- company used in market map but no sector assigned
