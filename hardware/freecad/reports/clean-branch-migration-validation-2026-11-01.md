# Clean FreeCAD branch migration and validation

Date: 2026-11-01

## Branch construction

`hardware-integration-clean` starts at `839c47b` (`Remove old Python tests workflow and add backup file`), the parent of `7a805d5`, the first commit that added CAD models to this repository. The base contains the project infrastructure and has no `hardware/freecad` tree. The clean branch then records one current-tree snapshot from `hardware-integration`, with the FreeCAD model inventory reduced to the selected files below. It does not inherit the sequence of large CAD snapshots from `hardware-integration`.

The source branch, its commits, and all existing worktrees were left unchanged. Before constructing the branch, the full local `hardware/freecad/` folder—including tracked and untracked candidates, backups, reports, and the locally modified preview script—was copied to `/Users/davidcannan/Documents/Codex/archives/pendant-cad-pre-clean-branch-archive-2026-11-01.tar.gz` and archive-stream verified. SHA-256: `d317a86bc968d9a9d8aaa13d14b6d0aa42e9a7dcf25dfcfa0e05b276e78b37d9`.

The archive is outside Git and must be retained. The original `hardware-integration` branch also remains available. This migration does not delete that branch or rewrite `main`.

## Model inventory

The clean branch tracks eight FreeCAD documents totaling 70,676,203 bytes (70.68 MB):

- `pendant.FCStd` — protected original baseline.
- `pendant-master.FCStd` — shared parameter source.
- `pendant-modular-assembly.FCStd` — top-level assembly.
- `pendant-bodies/breakout-board.FCStd`.
- `pendant-bodies/display-retainer.FCStd`.
- `pendant-bodies/faceplate-locators.FCStd`.
- `pendant-bodies/usb-tethered-cover.FCStd`.
- `encoder-faceplate-pocket-unsplit-user-split.FCStd` — fused handoff for the intended user split.

No STEP, STL, or FreeCAD backup files are tracked under `hardware/freecad/`. Generated STL sidecars are excluded from `hardware/printing/pendant/meshes/`; the user-arranged `pendant-orcaslicer.3mf` is retained. FreeCAD transient-file ignore rules cover `.FCBak`, `.FCStd1`, `.FCStd.autosave`, and `.FCStd~`.

The dated rear-shell candidates, candidate assemblies, duplicate models, large fused encoder working copy, and other experiments remain in the verified local archive and on the old branch. The rear shell is not claimed to be a fully editable standalone source in this clean branch.

## FreeCAD validation

Validation used disposable copies under `/private/tmp/pendant-cnc-clean-validation/`; the clean branch's model files and the open GUI documents were not changed by the checks.

- Cold open and native recompute succeeded for the four linked component source documents. All tipped PartDesign Bodies were valid, with one solid each.
- The encoder unsplit handoff opened and recomputed as one valid solid (14,630.093 mm³).
- A master-driven, reversible parameter test was run after save/reopen: `InternalHardware.ShellMountPassageDiameter` changed from 2.30 mm to 2.35 mm and back. The display retainer and both faceplate locators changed at the probe value; the maximum volume error after restoring and reopening was 0.0 mm³.
- The modular assembly cold-opened, recomputed, saved, closed, reopened, and recomputed. Its five live links resolved to the four preserved component documents, and each linked shape matched its source. Four `Interim_*` static shapes remained valid single solids.
- Direct external document links in the retained FreeCAD files resolve in the preserved relative folder layout. Relative Markdown image links resolve. Candidate-model links in reports point to the old `hardware-integration` branch.

The assembly still includes four static interim representations, so this is a smaller-history branch and a usable partial modular assembly—not completion of all component modularization. The protected monolith was preserved byte-for-byte and not recomputed or saved.

## Pull behavior and limitation

A clone restricted to `hardware-integration-clean` receives the clean branch ancestry and current files (including the 70.68 MB of FreeCAD documents). The old remote branch remains intact, so an existing checkout that still fetches every `origin` branch with `git fetch --all` can still fetch the old history. To avoid that while retaining the old branch, use a single-branch clone or narrow the local fetch refspec to the desired branches. This branch creation alone does not reduce GitHub's stored repository size.
