# Hardware branch rules

The accepted hardware source is `hardware-integration-clean`, separate from firmware `main`. Use a review branch based on its current remote tip. `hardware-integration` and `hardware/kicad` are historical recovery references, not development targets.

## Required workflows
- For KiCad schematics, component inventories, connector mappings, FreeCAD-to-KiCad handoffs, and cloned vendor CAD models, **use the clean hardware branch first**.
- Use `git clone --branch hardware-integration-clean --single-branch https://github.com/Cdaprod/lolin-s2-mini-cnc-mpg-pendant-controller.git`, or in an existing clone: `git fetch origin hardware-integration-clean && git switch hardware-integration-clean`.
- Place new KiCad deliverables under `hardware/kicad/`, external vendor STEP/3D models under `hardware/models/vendor/`, user-created models under `hardware/models/created/`, and CAD integration notes under `hardware/docs/`.
- For a cloned third-party model, record source URL, vendor, part number, license, original filename, units, retrieval date, SHA-256, and any transforms in `hardware/models/MODEL_SOURCES.md`. Never assume mechanical dimensions without checking official drawings.
- Keep `main` unchanged unless explicitly asked to merge. Do not force push this branch. If integrating firmware from main, merge/rebase deliberately and review conflicts.
- The master KiCad inventory schematic is logical/harness-level, not fabrication-ready; verify connector pin numbers, USB-C CC/VBUS, physical dimensions and ERC before production.
- Keep electrical emergency stop independent of pendant MCU software. Do not restore the retired LM393 path without a measured requirement.
- Keep source, parameters, physical measurements, and meaningful engineering decisions. Generate experiments under ignored `.workbench/` and exports under ignored `build/`.
- Do not automatically stage or commit CAD output. Generate, inspect actual geometry, validate dependencies and save/reopen behavior, review significance, then explicitly promote source changes.
- Keep the eight-document inventory in `hardware/scripts/validate_sources.py` current only after deliberate review. Preserve the existing relative paths; modular documents have external dependencies.
- Preserve a checksum-verified local recovery copy before removing engineering files. Never select authority solely by filename, revision, or modification date.
- Warn at 5 MiB, document justification at 10 MiB, and block new ordinary-Git binaries at 25 MiB. The existing protected monolith is a documented exception; do not duplicate it.
- Publish accepted manufacturing exports through Releases or deliberately configured LFS. Retain the existing user-arranged 3MF as a documented exception. No automatic uploads or printer operations.
- Run `python3 hardware/scripts/validate_sources.py` before committing. Report its limited scope accurately; it does not prove recompute, electrical validity, or fit.
- Never rewrite published history, delete remote recovery branches, or force-push without explicit authorization.
