# FreeCAD modular migration status

Date: 2026-10-29
Branch: `hardware-integration`
Authoritative source retained unchanged: `pendant.FCStd`

## Baseline

- FreeCAD 1.1.1, revision `0108fd4b4850cc46e625b60e53cea7a7bbe69f8d`.
- The source contains 816 document objects, including multiple physical Bodies, construction tools, archived versions, and transfer geometry. Object count is not a component count.
- The document already has shared parameter sources (`PendantDimensions`, `InternalHardware`, `ExteriorEnvelope`, `DualSided_OpposedWedge_Seam`, and `HangerParameters`). Their current expressions point within the monolithic document. They have not been moved or rewritten.
- Baseline Body inventory, Tips, shape validity, solid counts, volumes, and bounding boxes were captured in `/tmp/pendant_modular_baseline_audit.json` for this machine/session. The authoritative source was not saved or modified.
- A checksum-verified recovery backup of the source, working encoder handoff, and recovery log is stored outside the worktree at `/Users/davidcannan/Documents/FreeCAD-Backups/modular-migration-20261029T151539Z/`.

## Migrated and verified

`pendant-bodies/display-retainer.FCStd` contains the complete editable `Body_DisplayRetainer_EditableV2` history (nine features plus its Body Origin). FreeCAD's recursive cross-document object-copy operation was used. The candidate was recomputed, saved, closed, reopened, and recomputed again.

- Source and destination Body Tip: `RetainerShellClearancePocketV3`.
- Shape: valid, one solid.
- Volume: source `2050.792480333789 mm^3`; reopened destination `2050.792480333789 mm^3`.
- Bounding box: source and reopened destination `(-29.4202, -16, -10.0615, 29.4234, 25.8, -7.06147) mm`.
- No copied feature has a link back to the source document.
- The document remains independently editable. It currently has no external master dependency; no constraints were rewritten to create one.

`pendant-bodies/usb-tethered-cover.FCStd` contains the editable `Body_USBTetheredCover` plus the hidden envelope/press-fit dependency Bodies recursively required by its history. Its manufacturing Body tip is `USBPlugLeadIn`; the helper Bodies remain hidden. It was recomputed, saved, closed, reopened, and recomputed again.

`pendant-bodies/faceplate-locators.FCStd` contains the two Bodies in the source's `Faceplate Locators` group. Both six-feature histories were recomputed and reopened successfully as one valid solid each, with volumes and bounding boxes matching the source. They have no links back to the monolith.

- Manufacturing Body baseline: one valid solid, source volume `665.2206904482824 mm^3`, reopened destination `665.220690448208 mm^3` (difference about `7.4e-11 mm^3`); bounding box matches source.
- No dependency link points back to the source document. The extracted helper group contains seven valid single-solid Bodies; those helper solids are construction/dependency geometry and are not separate manufactured parts.

## Master and update behavior

`pendant-master.FCStd` now contains the original `PendantDimensions` sheet copied with its aliases and values, plus native sheets populated from the existing `InternalHardware`, `ExteriorEnvelope`, `DualSided_OpposedWedge_Seam`, and `HangerParameters` values. No values were invented. The source document's parameter objects and expressions remain unchanged. These copied values are not yet wired to migrated component sketches; that remains incremental work.

A disposable `Part::Box` test verified an external expression using the internal document name: `pendant_master#<<PendantDimensions>>.FaceplateThickness`. A change from `2.5 mm` to `3.0 mm` propagated after recompute, remained valid after save/reopen, and returned to `2.5 mm` when restored. The document label/file uses `pendant-master`, but the installed FreeCAD 1.1.1 expression parser required the loaded document's internal name `pendant_master`; using the hyphenated spelling produced an Invalid expression. The master was restored and saved at `2.5 mm`.

`hardware/freecad/scripts/update_modular_project.py` loads the master first, then recomputes, validates, and saves component documents. It can also refresh an explicitly supplied assembly candidate. The worker has a 300-second default timeout and process-group TERM/KILL cleanup. Its first full run successfully refreshed the master and both extracted component files; all reported Bodies were valid single solids. It does not open or save the untouched authoritative assembly.

## Still in the authoritative monolith

- Front/rear shells: recursive copy required 325 objects, including both physical shells and 11 helper Bodies. All 130 shared expressions redirected to the master evaluated in memory and the Tips matched. After save/reopen, however, the containing Body shapes reported different bounds from their unchanged Tips. The candidate was discarded because that mismatch fails geometry acceptance.
- Upper faceplate: recursive copy required 326 objects and included the front shell and ten helper Bodies, so it is not yet an independent component source.
- Encoder faceplate and pocket: copying both together required 288 objects and ten Bodies. The 60 redirected expressions initially resolved, but perturbing `FaceplateThickness` from 2.5 to 2.6 mm split the encoder-pocket Body into two solids; restoring the parameter did not return it to its original one-solid shape. The candidate was discarded.
- Breakout board: its Binder pulls in the front shell and 235 additional objects, so it is not currently independent.
- These failed or oversized candidates were disposable and have been closed/discarded; no shell, encoder, upper-faceplate, or breakout-board candidate was promoted. Their authoritative source geometry remains in `pendant.FCStd`.
- Archived/display-retainer v1 and helper/cutter/envelope Bodies are not independent manufacturing files and remain in the original document.
- The linked top-level assembly is now a separate candidate at `pendant-modular-assembly.FCStd`; `pendant.FCStd` remains unchanged and is not replaced.

## Recovery and execution rules

Keep `pendant.FCStd`, recovery files, and historical repair candidates untouched until the linked assembly passes acceptance tests. For each next component, use a disposable copy, preserve its complete dependency group, compare geometry in a common coordinate system, and reopen/recompute before promotion. A blocked component stays in the original document while independent components proceed.

## Continued migration and shell dependency investigation

The authoritative monolith remains byte-for-byte unchanged (SHA256 `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`). A checksum-verified backup of the monolith, master, and locator source is outside the worktree under `/Users/davidcannan/Documents/FreeCAD-Backups/modular-continuation-20261029T165650Z/`.

### Shell dependency report

The earlier broad XML inventory is retained in `shell-dependency-report.md` as historical analysis, but its 331/307-style closure and “dominant active rear-Tip path” statements are superseded for Tip reachability. The corrected audit follows `Body002.Tip` through feature input properties, skips Body/Part ownership containers, distinguishes suppressed ancestry, and enumerates the remaining paths. It establishes why the Tip closure did not shrink: the seam/back/land substitutions are not in that Tip's transitive feature inputs. The sole remaining front-shell reference in full ancestry is `Binder016.Support → Body.Sketch019`, reached through suppressed Pads 020–022.

The 325-object `front-rear-shells.FCStd` remains an unvalidated disposable candidate and is not included in the assembly or commits. Its recompute/save/reopen attempts still fail because of broken face references, suppressed-feature failures, and Body-versus-Tip shape mismatches. The requested 27.0 → 27.5 → 27.0 mm shell propagation and save/reopen validation therefore did not pass. No taper or shell geometry was changed.

### Master-driven locator parameter

`pendant-master.FCStd` now adds the alias `PendantDimensions.FaceplateLocatorBodyDepth = 2.0 mm`. The two lower-taper Pad lengths in `faceplate-locators.FCStd` use `pendant_master#<<PendantDimensions>>.FaceplateLocatorBodyDepth`; no other master cells or component properties changed. The master loads before components in the refresh sequence.

On a disposable relocated project, changing the alias 2.0 → 2.1 → 2.0 mm and running the refresh workflow changed Locator A volume `88.29496032374551 → 91.02502726603446 → 88.29496032374551 mm³`, moved its lower Z bound `-3.5 → -3.6 → -3.5 mm`, and returned to the exact original volume after restoration. Component and assembly were saved/reopened during refresh.

### Linked assembly and refresh

`pendant-modular-assembly.FCStd` is a separate top-level assembly candidate. It contains four `App::Link` objects to editable Bodies (display retainer, USB-tethered cover, and two faceplate locator Bodies) and six explicitly labeled static BREP interim components pulled from the monolith's saved shapes (front shell, rear shell, upper faceplate, encoder faceplate, encoder pocket, and breakout board). Each interim shape is valid and one solid; its volume and bounds match the saved source BREP. The links match their source Bodies' volumes and bounds. The original `pendant.FCStd` was not overwritten.

The candidate saves/reopens successfully. Opening the assembly by itself automatically loads the master and its relative-path linked documents. A relocation test copied only the assembly, master, and three component files to another temporary root; all four links resolved and remained valid there.

`scripts/build_modular_assembly.py` rebuilds the separate candidate from saved monolith BREP caches without recomputing the fragile monolith. `scripts/refresh_modular_assembly.py` loads the master first, recomputes and validates editable components, saves the master-driven locator Bodies with a backup, refreshes and validates assembly links/interim solids, then save/reopens the assembly. The refresh refuses to run while the FreeCAD GUI process is open, uses a bounded 170-second worker by default, and terminates its owned process group on timeout.

The full edit/save/refresh/restore test passed on a disposable relocated project: `USBPlugLeadIn.Size` 0.20 → 0.25 → 0.20 mm changed the assembly link volume `665.220690448208 → 665.1743368845141 → 665.2206904482084 mm³`, then returned to baseline. The edited native component document remained separately editable.

This is a useful interim assembly, not a fully modular or fully master-driven pendant: six legacy components remain static BREP representations, and the shell dependency migration is still blocked. The old monolith remains the authoritative editable source for them.

### Continued parameterization

The shared/local split now has one validated local component parameter in addition to the existing shared locator-depth alias. `usb-tethered-cover.FCStd` contains a `LocalParameters` spreadsheet with `USBLeadInChamferSize = 0.20 mm`, driving the existing native `USBPlugLeadIn.Size` chamfer. The feature history was preserved. Save/reopen/recompute retained a valid one-solid Body with volume `665.2206904482084 mm^3` and unchanged bounds. On a disposable candidate, changing the local alias 0.20 → 0.25 → 0.20 mm changed volume `665.2206904482084 → 665.1743368845141 → 665.2206904482082 mm^3`; the restored geometry matched the original within kernel precision. The modular assembly refresh then passed with all four links and six static interim shapes valid; the USB link retained the restored volume.

The display-retainer local-parameter attempt was not promoted. Driving the early base Pad caused the existing downstream junction Fillet to report invalid edge references on recompute, while a terminal clearance-pocket depth change did not measurably change its output. The original display-retainer document remains untouched. Continue identifying local parameters only where an actual edit produces a valid, measurable, recoverable geometry change.

The rear transfer-reference and frame-preserving profile experiments are recorded in `shell-dependency-report.md`. The Tip-rooted follow-up showed that `RearFullLandTransfer.Base`, `Binder008.Support`, and `Binder009.Support` are outside the active rear Tip dependency closure, so changing them cannot reduce its count. Their successful candidate substitutions were not promoted to the production master or assembly.

### Targeted dependency and fragile-reference audit (2026-10-29)

In a disposable copy of the monolith, explicitly recomputing suppressed `Pad022` reports the missing support subshape `Pad021.?Face97`. `Pad021` itself recomputes; `Pad022` retains a valid cached one-solid shape. Its downstream feature `RemoveWarpProneTongues` is active and uses it as `BaseFeature`. Targeted recompute through the rear active Tip retained the saved one-solid Tip shape, volume `40961.35900828918 mm^3`, and its original bounding box. This is a real suppressed-history failure but did not perturb the current cached downstream geometry during the limited test. No source repair was made.

The rear full-land link is only one of several remaining paths. `Binder008`/`Binder009` drive the rear envelope profiles and tapered seats; `Binder016` drives rear screw reinforcement; additional front-owned construction geometry reaches the rear Tip. The earlier graph-only closure estimate of 331 → 185 after a combined five-binder and land-transfer cut is not a validated minimum dependency cut. Details and the dependency-metric caveat are in `shell-dependency-report.md`.

The migrated retainer's structural junction fillet uses `DisplayRetainerHeaderPocketV2` edges `Edge57`, `Edge58`, `Edge64`, and `Edge65`, radius 0.6 mm. A 0.1 mm pocket-length perturbation passed targeted recompute in a disposable copy and left the final Tip valid and geometrically unchanged. The earlier base-Pad edit that failed therefore appears more topology-sensitive; the retainer source remains unchanged.

The property-level rear shell cut audit identifies three active front inputs: `RearFullLandTransfer.Base`, `Binder008.Support`, and `Binder009.Support`. A transfer-only fixed master snapshot preserved the rear Tip exactly but did not reduce the closure because the two envelope-profile paths remain; the disposable candidate was discarded. The audit and exact downstream chains are recorded in `shell-dependency-report.md`.

### Targeted rear profile reconstruction status (2026-10-29)

The first master-link attempt lost the sketch placement because new `App::Link` objects defaulted to origin placement. A follow-up disposable candidate set each link's `LinkPlacement` from its copied sketch's saved `Placement`; this restored both profile chains, recomputed the rear Tip, and passed save/close/reopen/recompute with matching geometry metrics. The three selected properties (`Binder008.Support`, `Binder009.Support`, and `RearFullLandTransfer.Base`) point to master-owned test references in that candidate. However, overall dependency closure did not shrink (307 local objects in the source versus 311 local plus 3 external objects in the candidate), other front references remain, and broad forced recompute still emits existing suppressed/history warnings. No CAD source or assembly file was promoted. The transform analysis and detailed measurements are recorded in `shell-dependency-report.md`.
