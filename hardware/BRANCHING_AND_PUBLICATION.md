## Published hardware history cleanup — 2026-11-25

The user authorized a hardware-only published-history rewrite. Historical
`hardware/` trees were removed and the selected current hardware snapshot restored
at engineering branch tips. All 27 branch names were retained. Every one of the
706 rewritten commits and every branch tip was checked for identical non-hardware
file trees. Firmware and other source content were not changed. Commit IDs may
change because of ancestry.

Historical candidate links and old commit IDs in prior reports are archival
references; remote branches no longer retain those experiments. Recovery is from
the verified complete offline bundle:

`/Users/davidcannan/Documents/Codex/archives/pendant-before-hardware-rewrite-20261125.bundle`

SHA-256: `9e6e67dad273199c20b932ecd11dfeb03908c21995e839eb75161f95d998830c`.

The separate pre-clean CAD archive remains available too. Do not push old local
branches or the backup bundle into this remote: doing so can restore the large
history. Preserve unpushed work before making a fresh clone in Working Copy or
other clients. Existing clones retain their old objects; fetching does not erase
them. Normal all-branch clones should receive only the retained hardware payload.

Earlier statements below describing remote recovery branches or a pending history
proposal describe the pre-rewrite state and are superseded by this section.


---

# Hardware integration and publication

The canonical engineering source is maintained on `hardware-integration-clean`; the older `hardware-integration` and `hardware/kicad` branches are recovery references. This integration branch contains both `hardware/freecad/` and `hardware/kicad/`.

The branch name `hardware` is unavailable while `hardware/kicad` exists: Git refs cannot simultaneously contain `refs/heads/hardware` and `refs/heads/hardware/kicad`. Keep the original branch as an immutable migration reference until a reviewed retirement or rename.

## Ownership contract

- **Engineering**: native `.FCStd`, `.step`, `.kicad_sch`, `.kicad_pro`, library sources, component maps, and hardware validation.
- **Main**: firmware, public documentation, and only approved generated hardware visuals.
- **Never merge this engineering branch into main wholesale**: doing so reintroduces native CAD files. Export from an exact engineering commit, validate, then use a separate publication branch/PR to copy only a reviewed allowlist of PNG/SVG/PDF and the README change.
- Stable publication paths: `docs/hardware/pendant-assembly.png`, `docs/hardware/pendant-schematic.svg`, and `docs/hardware/pendant-schematic.pdf`. These are intended outputs, not a claim they have already been generated.
- Record the source commit and verification status in `docs/hardware/SOURCE.md` on the publication branch.

## Migration findings

The source `hardware/kicad` branch was 12 commits ahead of `main` with no behind commits at inspection, and already carried the more recent FreeCAD master and KiCad schematic. No cherry-pick of an older FreeCAD model was appropriate.

Current limitations: KiCad source explicitly warns its symbol pin numbers are provisional; its `.kicad_prl` and lock files and a FreeCAD `.FCBak` were committed. Do not claim ERC, pin mapping, or mechanical fit has passed. Clean these transient artifacts on the engineering branch once preserved in Git history, and verify that no application is writing to them.

## Suggested local workflow

```bash
git fetch origin hardware-integration-clean
git worktree add ../cnc-pendant-hardware hardware-integration-clean
```

Open KiCad and FreeCAD from that worktree. Keep firmware development in a separate worktree for `main`.

## Engineering acceptance

Use `hardware/README.md` as the established design policy: a protected original baseline, a linked modular project, reproducible STEP exports, no custom carrier, KiCad as electrical authority. Preserve original source files; evaluate the direct encoder interface and stop safety boundary against measured hardware rather than assuming schematic placeholders are verified.

## Lightweight checkout

Use `git clone --single-branch --branch hardware-integration-clean https://github.com/Cdaprod/lolin-s2-mini-cnc-mpg-pendant-controller.git` for hardware. For firmware, select `main` instead. An unrestricted clone/fetch still downloads historical CAD branches. Existing Git objects are not removed by working-tree cleanup. Do not delete or rewrite recovery branches as part of routine cleanup.
