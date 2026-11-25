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

# CNC Pendant FreeCAD files

This branch is a clean working snapshot built from the project commit immediately before CAD files first entered the repository. It keeps the current project source snapshot and the selected FreeCAD files below, without the old sequence of large CAD snapshots in its ancestry.

## Working files

- `pendant.FCStd` — protected original design baseline. Keep it as a reference; do not save design edits over it.
- `pendant-master.FCStd` — shared parameters and reference geometry.
- `pendant-modular-assembly.FCStd` — assembly view. It includes five live component links and four static interim shapes; the latter are not independently editable sources.
- `pendant-bodies/` — native editable source documents for the breakout board, display retainer, faceplate locators, and USB tethered cover.
- `encoder-faceplate-pocket-unsplit-user-split.FCStd` — fused encoder faceplate/pocket handoff for the intended user split.

The front and rear shells are not yet available here as complete independent native component sources. The latest rear-shell structural review and the other candidate documents remain preserved in the original `hardware-integration` branch and the local archive; do not mistake an interim assembly shape for an editable shell source.

## Refreshing the modular assembly

Use `scripts/refresh_modular_assembly.py` only when the FreeCAD GUI is closed. It refreshes the four supported editable component sources and checks the assembly links. It does not turn static interim shapes into editable components.

## Excluded CAD experiments

The branch omits the large set of dated candidate/review models, duplicate assemblies, the generated STEP export, FreeCAD backups, and recovery files. The complete pre-migration `hardware/freecad/` folder was preserved locally at:

`/Users/davidcannan/Documents/Codex/archives/pendant-cad-pre-clean-branch-archive-2026-11-01.tar.gz`

Archive SHA-256: `d317a86bc968d9a9d8aaa13d14b6d0aa42e9a7dcf25dfcfa0e05b276e78b37d9`.

The old `hardware-integration` branch remains available for browsing or downloading an individual experimental model. Reports in this branch link to those archived review documents on GitHub where appropriate.
