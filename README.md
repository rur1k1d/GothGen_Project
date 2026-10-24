# GothGen_Project

Your gothic nickname generator.

Python 3.11+, standard library only. No network calls. No GUI.

## Why

The goal is a small, auditable tool for:

- daily name picks from an attested corpus;
- filtered lists by culture, gender, and type;
- constructed name ideas from historical lexicon elements, clearly labelled;
- brand and handle variants for a chosen name;
- source-aware records instead of untraceable name lists.

The tool does not decide whether a name, domain, handle, or trademark is free.
It gives candidates. Availability and legal checks stay manual.

## Quick start

```bash
cd projects/Name_Generator_Project

python3 namegen.py daily
python3 namegen.py daily --date 2026-10-22 --culture gothic --top 5
python3 namegen.py generate --culture norse --gender m --count 5 --seed 42
python3 namegen.py combine --culture anglo_saxon --count 5 --seed 7
python3 namegen.py leet Alaric
python3 namegen.py offer Rurik
python3 namegen.py explain Goar --json
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

## Commands

| Command | Purpose |
| --- | --- |
| `daily` | Deterministic picks for a date, optionally filtered by culture. |
| `generate` | Weighted random sample from attested names. Use `--seed` for repeatability. |
| `combine` | Construct names from lexicon elements. Output is `constructed`, not attested. |
| `leet` | Show ASCII and leetspeak variants. |
| `offer` | Full name card plus brand directions and handle suggestions. |
| `explain` | Full record, provenance, and source. |

Global data flags: `--names`, `--sources`, `--lexicon`.

## Data model

`data/names.csv` is the corpus. Required columns:

```text
id,name,ascii,gender,name_type,culture,subculture,origin,era,
source_id,source_locator,meaning,elements,variants,status,confidence,
gothic_like,notes
```

Rules:

- `name_type` is `person` or `place`; `generate` uses `person` by default.
- `status` is `attested` or `constructed`.
- `confidence` is `high`, `medium`, `low`, or `uncertain`.
- `gothic_like=true` means resemblance only. It never means a Gothic cognate.
- `source_id` must exist in `data/sources.csv`.
- `source_locator` is the chapter, annal, line range, or inscription reference.
- Unknown meaning is written as `uncertain`. Do not invent a translation.

`data/sources.csv` records author, title, year, edition, URL, licence, access
date, and notes. `data/lexicon.csv` records elements used by `combine`.

## Culture scope

Current corpus: Gothic, Geatish, Anglo-Saxon, Norse, Varangian Rus, Scythian,
and Alan/Sarmatian.

Safety rules:

- Scythian and Alan/Sarmatian entries are attested-only. `combine` refuses them.
- Do not build artificial Scythian names from Gothic elements.
- `Goar` is Alanic, not Gothic. It is marked `gothic_like=true` for resemblance
  only, with `status=attested` and a clear note.
- Varangian Rus covers Norse, Slavic, and mixed names from the Primary Chronicle
  and related sources. Keep the distinction visible in `origin` and `notes`.
- Geatish names come from literary sources such as *Beowulf*. Treat literary
  status honestly.

## Private game-data layer

`data/private/` is gitignored and optional. It can hold a private game-derived
layer, for example a Total War: Attila name database, for personal use only.

If used:

- never commit it;
- never redistribute it;
- mark records `source_type=game` and `confidence=low`;
- keep public historical sources as the core corpus.

The generator itself does not read `data/private/` by default.

## Output and claims

`offer` and `generate` print:

- the name and ASCII form;
- a leetspeak variant;
- culture, gender, type, meaning, elements, variants;
- status and confidence;
- source and locator.

Every card ends with:

```text
Check domain and trademark availability before use.
```

This is a research aid, not legal advice. Domain and trademark checks are
separate manual steps.

## Known limitations

- Meanings for several early names are uncertain or disputed.
- Some names are known only through Greek or Latin transmission.
- The corpus is small and curated, not a complete onomasticon.
- Constructed names can resemble real names by accident.
- Leetspeak variants may be unreadable, already taken, or unsuitable for a brand.

## Licence and source use

Code is a local project. Data provenance is per row. Before redistributing any
data file, audit the licence and terms of every source in `data/sources.csv`.
Do not redistribute text excerpts from copyrighted editions.
