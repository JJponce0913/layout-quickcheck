# Artifact generators

This package separates reproducible thesis artifacts by output type:

- `figures/` contains scripts that generate plots and diagrams.
- `tables/` contains scripts that generate LaTeX tables.

Each generator should read source data without modifying it and write its
artifact beneath the repository's `figures/` directory. Existing scripts remain
in `scripts/` until they are migrated and their generated outputs are verified.
