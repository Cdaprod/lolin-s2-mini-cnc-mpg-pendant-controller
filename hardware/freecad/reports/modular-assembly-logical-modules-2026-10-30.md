# Modular assembly logical groups

Date: 2026-10-30
Branch: `hardware-integration`
Scope: assembly hierarchy only; no component geometry or placements were redesigned.

## Tree organization

The assembly now exposes three module-level nodes:

| Module | Members | Editability |
|---|---|---|
| `ShellModule` | Front shell and rear shell | Two clearly marked static BREP interim snapshots; the coupled native shell histories remain unresolved. |
| `FaceplateModule` | Upper faceplate snapshot, fused encoder faceplate + pocket, two faceplate locators | The upper faceplate and fused encoder solid remain static interim snapshots. Both locator Bodies remain live App::Links to their editable source. |
| `OtherEditableComponents` | Display retainer, USB tethered cover, breakout board | Three live App::Links to editable source Bodies. |

The encoder faceplate and pocket remain fused as one interim representation. This does not complete shell or faceplate source-document modularization.

## Validation

The modified assembly builder created a disposable candidate. FreeCAD 1.1.1 recomputed the linked component documents and assembly, saved and reopened them, then verified the module memberships and source-link geometry. The candidate's root contained exactly the three module nodes.

The candidate passed a relocation test after copying the assembly, master, and linked component files to a separate temporary project tree. All four external link paths remained relative (`pendant-bodies/*.FCStd`). The existing refresh worker recomputed the five links and four interim snapshots, saved the copied assembly, reopened it, and returned success.

The promoted project assembly was reopened from its final path in a fresh FreeCADCmd process and recomputed without saving. It resolved all five live links and four static interim solids. The root contained nine solids, and its sorted per-solid volume/bounding-box signatures matched the nine members exactly, confirming no module member was omitted or counted twice.

Before this hierarchy change, `AssemblyRoot.Group` contained its two groups and their nine contents directly, yielding 18 solids in the root aggregate. The new root contains only `ShellModule`, `FaceplateModule`, and `OtherEditableComponents` and yields nine solids. Per-object volume, area, topology counts, bounds, validity, and source-link measurements were unchanged between the prior assembly and candidate. The aggregate compound's reported `Shape.Volume` is not used as a geometry acceptance check; the validated evidence is the one-to-one solid signature and each member's unchanged shape metrics.

The previous assembly was backed up and checksum-verified before replacement:

- Backup: `/Users/davidcannan/Documents/FreeCAD-Backups/module-tree-20261030T132630/pendant-modular-assembly.before.FCStd`
- Previous assembly SHA-256: `d727c69f3e3bc68857fc29aa29438fc2a6f7a59954a6f64b3766d466fa57bbdb`
- Promoted assembly SHA-256: `2e554ca1c06d5e6b6cf0c552fc722f85180752eced96e467f0f0b76388c77ee4`

`pendant.FCStd`, the master document, source component documents, and the user's OrcaSlicer multi-plate project were not changed by this grouping milestone. The shell and principal faceplate components are still static interim representations, so the project is not yet fully modular.
