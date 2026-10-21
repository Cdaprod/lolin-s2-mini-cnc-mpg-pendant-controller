# Hardware branch rules

This branch (`hardware/kicad`) is the **working hardware source**, separate from `main`.

## Required workflows
- For KiCad schematics, component inventories, connector mappings, FreeCAD-to-KiCad handoffs, and cloned vendor CAD models, **checkout this branch first**.
- Use `git clone --branch hardware/kicad --single-branch https://github.com/Cdaprod/lolin-s2-mini-cnc-mpg-pendant-controller.git`, or in an existing clone: `git fetch origin hardware/kicad && git switch hardware/kicad`.
- Place new KiCad deliverables under `hardware/kicad/`, external vendor STEP/3D models under `hardware/models/vendor/`, user-created models under `hardware/models/created/`, and CAD integration notes under `hardware/docs/`.
- For a cloned third-party model, record source URL, vendor, part number, license, original filename, units, retrieval date, SHA-256, and any transforms in `hardware/models/MODEL_SOURCES.md`. Never assume mechanical dimensions without checking official drawings.
- Keep `main` unchanged unless explicitly asked to merge. Do not force push this branch. If integrating firmware from main, merge/rebase deliberately and review conflicts.
- The master KiCad inventory schematic is logical/harness-level, not fabrication-ready; verify connector pin numbers, USB-C CC/VBUS, physical dimensions and ERC before production.
- Keep electrical emergency stop independent of pendant MCU software. Do not restore the retired LM393 path without a measured requirement.
- Keep generated source and outputs together; update inventory when adding/removing parts. Avoid committing massive duplicate binary exports.
