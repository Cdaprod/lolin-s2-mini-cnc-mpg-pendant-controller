# Rear shell Sketcher dependency audit

Date: 2026-10-29
Branch: `hardware-integration`
Source evidence: authoritative `pendant.FCStd`, disposable
`remove-warp-bypass.FCStd`, and disposable post-cleanup candidate. Checksums are
recorded in the respective JSON manifests linked below.

## Result

The authoritative monolith's rear Tip closure is **51 objects** by ordinary
object links and **75 objects** after Sketcher external-geometry links are
included. In the disposable `RemoveWarpProneTongues → Pocket015` bypass, the
corresponding counts are **47 and 71**. These 24 extra objects expose the
Sketcher references omitted by ordinary dependency traversal. After the
validated removal of twelve unconstrained external references, that candidate
has matching ordinary and expanded counts of **47**. Constraint-driving
front-shell dependencies remain.

Machine-readable manifests:

- [Authoritative monolith](reports/rear-shell-sketch-dependency-manifest-monolith.json)
- [Disposable bypass before cleanup](reports/rear-shell-sketch-dependency-manifest-bypass-baseline.json)
- [Disposable bypass after cleanup](reports/rear-shell-sketch-dependency-manifest.json)

The initial audit was read-only. A narrowly scoped disposable candidate test
then removed six unconstrained Sketcher external references from each of
`RearAlignedM2PassageSketch` and `RearAlignedHeadSeatSketch`. Their 14
constraints per sketch were unchanged. All 16 active downstream feature shape
signatures matched the freshly recomputed baseline before and after save/reopen.
That candidate's expanded Tip closure returned to 47 objects, with no
Sketcher-external-geometry expansion. The production monolith, master, modular
assembly, recovery files, and untracked candidates remain unchanged.

## Active paths

| Rear Tip path | Sketcher reference | Upstream source | Constraint use |
|---|---|---|---|
| `RearBossWallRamps45 → … → Pocket018 → RearAlignedM2PassageSketch` | Six geometry references `g7`–`g12` | `RearScrewAlignmentBinder` | None of these six references is used by a saved sketch constraint. |
| `RearBossWallRamps45 → … → Pocket019 → RearAlignedHeadSeatSketch` | Same six `g7`–`g12` references | `RearScrewAlignmentBinder` | None of these six references is used by a saved sketch constraint. |
| Both paths above → `RearScrewAlignmentBinder.Support` | `App::PropertyXLinkSubList`, support is `Sketch020` | `Body.Sketch020` (front shell) | Binder support dependency. |
| `Sketch020` → external geometry | Six persistent generated-edge references | `Body.Pocket016` (front shell; saved as suppressed) | No constraints reference these six external geometry indices. |
| `Pocket016` → `Sketch019` and its base history | Thirteen persistent generated-edge references from `Pad017` and `AdditiveLoft` | Front-shell construction features | Five references drive constraints 52, 53, 61, 55, 63, 69, 79, 80, and 81 (some constraints use two referenced geometries); the rest are unreferenced by constraints. |

The full encoded subelement tokens, order, constraint indices, owner Bodies,
suppression states, and Tip-to-consumer paths are in the JSON manifest. The
tokens are FreeCAD persistent element-map references, not stable human labels
such as `Edge7`.

The two rear screw sketches stored references to binder geometry even though
those references were not constraint-driving. In the disposable test they
were removed via `SketchObject.delExternal(index)` in reverse index order.
Both sketches remained valid, their native constraints were unchanged, and
all 16 downstream feature signatures matched the source after full recompute,
save/reopen, and a second recompute. This validates the deletion for these
specific reference-only external geometries; it does not establish that the
remaining front-shell dependencies can be extracted safely.

The active dependency chain also reaches `Sketch019` through `Pocket016` and
`Sketch020`. This is distinct from the suppressed tongue path through
`Binder016`; the old `Binder016` route is absent from this bypass candidate's
expanded Tip graph. After the unconstrained rear screw references were removed,
the expanded closure equaled the ordinary 47-object closure, but active
front-shell dependencies still remain through `Sketch020`, `Pocket016`,
`Sketch019`, `Pad017`, `AdditiveLoft`, and their consumed profiles.

## Constraint-level details

`Sketch019` has thirteen external references. Two `Pad017` references and
three `AdditiveLoft` references are constraint-driving; eight other references
remain stored without a constraint using their external geometry index. The
five driven references are particularly sensitive to topological renaming and
must be reconstructed against explicit geometry if the source features are
removed.

`Sketch020` has six external references into `Pocket016` but no constraints
that use those indices. It is still the support of the active rear
`RearScrewAlignmentBinder`, so its saved external references are part of the
current link structure even though they do not drive its sketch constraints.

`Sketch021` is recorded separately as inactive Body history. It references
`Binder017.Face1` six times, and all six references are constraint-driving.
`Sketch021` and `Binder017` are not reached from the current rear Tip, so they
are not part of the active 71-object closure. They should not be repaired for
this extraction unless a fuller Body history is intentionally retained.

## FreeCAD 1.1.1 API behavior observed

The installed FreeCAD build reports version `1.1.1`, revision
`0108fd4b4850cc46e625b60e53cea7a7bbe69f8d`.

On the inspected `Sketcher::SketchObject` instances:

- `ExternalGeometry` exists as an `App::PropertyLinkSubList`, but is empty for
  these references.
- `ExternalGeo` exists as a `Part::PropertyGeometryList`; its runtime value
  includes the resolved geometry cache. The saved `Document.xml` entries carry
  `Sketcher::ExternalGeometryExtension` records with the source `Ref` token and
  flags.
- `ExternalTypes` and `_ExternalGeoVersion` are present.
- `addExternal`, `delExternal`, `getSubObjectList`, `getSubObject`, and
  `getSubObjects` are available.
- `getExternalGeometryCount` and `getExternalGeometry` are not available on
  this build.

Thus, inspecting only `ExternalGeometry`, `OutList`, or the ordinary
`ObjectDeps` table misses real Sketcher references. The audit script reads
`ExternalGeo` extension records from the FCStd archive and maps external
geometry order `i` to Sketcher constraint geometry index `-(i+3)`. It also
records the serialized reference verbatim so future FreeCAD versions can
cross-check this mapping against their runtime APIs.

The manifest records ShapeBinder/XLink support properties, Python-proxy
expressions, placements, owners, ordinary object dependencies, and active
paths. There are no `App::Link` objects in the expanded rear Tip closure.

## What can be stabilized

- The six `RearAlignedM2PassageSketch` and six `RearAlignedHeadSeatSketch`
  references are not used by constraints. A master-owned sketch/datum
  replacement or removal may be possible, but only after checking native sketch
  recompute and downstream Pocket geometry in a disposable copy.
- The six `Sketch020` references to `Pocket016` are also not constraint-driving.
  Their exact curves can be captured as a stable master-owned profile, subject
  to coordinate-frame and recompute validation.
- Five `Sketch019` references drive constraints. Replacing them requires
  rebuilding those constraint references against explicitly named master
  geometry while preserving the sketch solution, constraint status, and
  downstream feature output. A direct Binder or link redirection is not
  sufficient.
- `Sketch021 → Binder017` is an inactive-history dependency for this Tip and
  can remain outside a minimal source document if the final native feature chain
  does not consume it.

The unconstrained references were removed successfully in a disposable
candidate. The remaining constraint-driving `Sketch019` generated-edge refs
and profile-scope dependencies are not repaired. The extraction probe shows
that `copyObject` alone does not create a self-contained shell; targeted
reconstruction of required front-shell profile inputs remains needed.

## Reproduction and validation limits

The extraction probe used `Document.copyObject` on the now-reduced 47-object
closure. FreeCAD still reported missing generated-edge externals in
`Sketch020` (from `Pocket016`) and `Sketch019` (from `Pad017` and
`AdditiveLoft`), as well as out-of-scope `ExteriorEnvelope` links in the
profile sketches. The standalone candidate did not complete its bounded
recompute/save/reopen validation and is not promoted. This confirms that the
47-object manifest is now complete for serialized Sketcher external geometry
in the monolithic candidate, but not self-contained: ordinary object links,
support relationships, or copied profile scope still require the front-shell
construction history.

Run the reusable read-only manifest generator with:

```sh
hardware/freecad/scripts/audit_sketch_dependencies.py path/to/pendant.FCStd \
  --body Body002 --json output.json
```

The JSON manifests record source checksums and were generated without modifying
their source documents. The authoritative monolith remains unchanged. The report does not claim
that the feature history has been fully repaired or that standalone extraction
will pass. The JSON reflects the post-cleanup disposable candidate; the initial
71-object expansion and validated reduction are documented above. Remaining
work is focused on the generated-edge and out-of-scope profile references
reported by the extraction probe.
