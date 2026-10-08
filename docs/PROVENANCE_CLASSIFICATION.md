# Provenance and leak classification

## Purpose

The database tracks the existence and provenance of source/code/game availability, not redistribution of copyrighted material. A leaked source tree can be an important historical research record even when it is unauthorized and non-redistributable.

Leak records stay in the discovery/provenance layer and are never automatically promoted to an approved/open-source classification.

## Facets

| Facet | Values | Meaning |
|---|---|---|
| `provenance_class` | `official-authorized`, `authorized-source-release`, `leak`, `archival-recovery`, `reverse-engineered`, `fan-maintained`, `unknown` | How the material appears to have become available |
| `leak_status` | `not-leak`, `reported`, `suspected`, `confirmed`, `historical-confirmed`, `unknown` | Strength/status of a leak claim |
| `authorization_status` | existing authorization field | Whether the release appears authorized |
| `content_types` | free-form facets such as `source-code`, `binary`, `assets`, `full-game`, `sdk`, `server`, `tools`, `documentation` | What was made available |
| `access_status` | `public`, `restricted`, `removed`, `private`, `dead-link`, `unknown` | Current evidence/access state |
| `redistribution_status` | `allowed`, `restricted`, `forbidden`, `unknown` | Rights signal for redistribution |
| `classification_tags` | free-form | Additional searchable labels |

The evidence table stores the corresponding `*_claim` values so a later manual review can see which source made a classification claim.

## Important distinction

A record can have:

- `provenance_class=leak`
- `leak_status=reported`
- `authorization_status=unauthorized-or-unresolved`
- `redistribution_status=forbidden`

while the same game's evidence history can later contain an authorized source release.

The collector therefore keeps evidence history rather than treating one status as the entire history of the game.

## Leak discovery

The default Internet Archive and GitHub query sets include leak-oriented search terms such as:

- leaked game source
- game source leak
- source code leak
- stolen source
- unauthorized source
- unreleased game source

These are candidate-generation signals. The classifier intentionally uses conservative values such as `reported` or `suspected` rather than asserting that every mention of a leak is verified fact.

## Canonical search examples

    # Confirmed leak records.
    python cgsdb.py search --leak-status confirmed

    # Reported leaks containing source code.
    python cgsdb.py search --leak-status reported --content-type source-code

    # Authorized source releases excluding leaks.
    python cgsdb.py search --provenance authorized-source-release --leak-status not-leak

    # Non-redistributable records.
    python cgsdb.py search --redistribution-status forbidden

    # Custom classification tag.
    python cgsdb.py search --tag leaked-content

## Discovery-layer search

    python cgsdb.py discovery-search --leak-status reported
    python cgsdb.py discovery-search --provenance leak
    python cgsdb.py discovery-search --content-type source-code --access-status public
    python cgsdb.py discovery-search --tag leaked-content

These filters are ANDed, so several dimensions can be combined.

## Safety and provenance

The database may record public reporting, archive metadata, repository metadata, package metadata, timestamps, license claims, and other provenance facts concerning leaked material. It should not be used to redistribute or facilitate access to copyrighted source code or commercial game assets when the applicable rights do not permit that use.

For leak cases, prefer contemporary reporting or a primary statement, historical archive/repository metadata, licensing or authorization information, and independent corroboration.

Do not turn a filename, mirror, forum allegation, or search-result snippet into a `confirmed` leak without stronger evidence.
