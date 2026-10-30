# USB cover master-envelope parameterization

Date: 2026-10-29  
Branch: `hardware-integration`  
Component: `pendant-bodies/usb-tethered-cover.FCStd`

## Change

The five width-controlled front/rear envelope profiles in the editable USB-cover document previously read `ExteriorEnvelope.ExteriorWidth / ExteriorEnvelope.ReferenceWidth` from a component-local `App::VarSet`. They now use the existing master sheet:

```text
pendant_master#<<ExteriorEnvelope>>.ExteriorWidth /
pendant_master#<<ExteriorEnvelope>>.ReferenceWidth
```

The master aliases already held the component's original `79.5569559596823 mm` baseline values, so no master dimension or manufactured design value was invented. The component's local VarSet remains in the document to preserve its extracted history; it no longer drives these five profile ratios. FreeCAD stored the master reference as `../pendant-master.FCStd`.

## Validation

The disposable component candidate was recomputed after wiring the five expressions. All five expression statuses were `Valid`; 26 objects recomputed. The main USB Body remained a valid one-solid `USBPlugLeadIn` Tip. At the original master width, the saved and reopened Body had a valid zero-volume BREP symmetric difference from the pre-change Body. Seven tipped Bodies in the component were compared at the original parameter values; each was valid, retained one solid, and had valid zero-volume symmetric-difference residuals against its source.

A relocated disposable project was used to test actual propagation through the refresh workflow:

| Master `ExteriorWidth` | USB Body volume | USB assembly-link volume | Assembly reopen |
| ---: | ---: | ---: | --- |
| `79.5569559596823 mm` baseline | `665.2206904482822 mm³` | `665.2206904482822 mm³` | Passed |
| `80.0 mm` test | `666.4116826978413 mm³` | `666.4116826978413 mm³` | Passed |
| restored `79.5569559596823 mm` | `665.2206904482822 mm³` | `665.2206904482822 mm³` | Passed |

All five live links and five interim solids passed validation in both changed and restored refreshes. The test project used relative component-to-master paths. The component was also opened by itself from the repository in a fresh FreeCADCmd process: FreeCAD loaded the master automatically, the five expressions remained valid, and the Body was up-to-date. The repository master was not changed; the 80 mm edit existed only in the disposable project. No fit or interference claim is made for that temporary test value.

Raw measurements and source hashes are in `usb-master-envelope-parameterization.json`. The test scripts and changed master values were confined to `/tmp/usb-master-parameterization/`.

## Cold-start cache persistence

A fresh-process test exposed a refresh-workflow gap: with the master at 80 mm, refreshing recomputed the USB Body in memory, but the source component was not saved, so a new process reopened the assembly at the stale `79.5569559596823 mm` cached shape. `scripts/refresh_modular_assembly.py` now backs up and saves every component document whose external master expressions it refreshes. In a relocated disposable project, the revised refresh saved the USB source; a separate FreeCADCmd process then opened the assembly with the 80 mm shape. After restoring the master width, refreshing saved the restored source, and a second fresh process opened the assembly at the original shape. Both fresh opens found five live links and five interim solids, and the assembly/link shapes were valid. The earlier in-process close/reopen check alone did not prove this cold-start behavior.

The Tip-rooted dependency auditor still reports `BLOCKED` if asked whether the USB Body is an isolated one-Body extraction: even when the master expression is explicitly allowed, it reports 32 same-document helper-object/Body ownership edges. The component has no ShapeBinders, Sketcher external-geometry references, or App::Links in this audit; the 10 external expression records are the intended two master aliases on each of the five profiles. This parameterization does not claim to solve that helper-history packaging boundary.
