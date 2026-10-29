# USB tether opening parameterization

Date: 2026-10-29  
Branch: `hardware-integration`  
Starting commit: `076557b`

## Change

Added `LocalParameters.TetherOpeningDiameter` to the existing native spreadsheet in `pendant-bodies/usb-tethered-cover.FCStd`, set to the original design value of **2.00 mm**. The alias drives `USBCoverTetherSketch.Constraints[1]`, which FreeCAD reports as the existing fully constraining **Diameter** constraint. The native PartDesign feature history and baseline manufacturing geometry are preserved. The parameter is component-local; it does not introduce a new shared master dimension.

The earlier candidate `USBCoverTetherPassage.Length` (25 mm) did not change the recomputed shape after a 0.5 mm perturbation, so that ineffective parameter was discarded and not added to the source document.

## Validation

The parameterized candidate was recomputed in FreeCAD 1.1.1, saved, closed, reopened, and recomputed at both changed and restored values. The manufacturing Body `Body_USBTetheredCover` remained valid and one solid throughout.

| Tether opening diameter | Tip volume (mm³) | Tip area (mm²) | Tessellated vertices | Result |
| ---: | ---: | ---: | ---: | --- |
| 2.00 mm baseline | 665.2206904482084 | 733.8375573312571 | 1,754 | Valid, one solid |
| 2.05 mm test | 664.7112391170108 | 734.0184676905585 | 1,720 | Valid, one solid |
| 2.00 mm restored after reopen | 665.2206904482084 | 733.8375573312571 | 1,754 | Returned to baseline |

The volume change at 2.05 mm was −0.5094513312 mm³. Restoring the alias returned the Tip volume, surface area, bounds, and tessellation count to their baseline values at the recorded precision.

## Linked assembly and portability check

Copied the master, assembly, all three editable component documents, and refresh workflow to a disposable relocated project. The relative App::Link to the USB component resolved there. With the USB alias at 2.05 mm, `refresh_modular_assembly.py` completed with no errors; all four live links and six interim solids were valid, and save/reopen passed. The USB link volume was 664.7112922434544 mm³. After restoring 2.00 mm and refreshing again, save/reopen passed and the link volume returned to 665.2206904482084 mm³. The small difference between isolated and assembly-context changed-value volume is within the FreeCAD kernel recompute precision observed here; restored baseline values agree.

The production master and assembly files were not modified. The original monolithic pendant was not modified. The existing recovery and untracked files were left untouched.

## Scope

This validates one additional local component parameter and its live-link assembly refresh. It does not complete encoder extraction, master-driven USB parameterization, or rear-shell dependency isolation. The rear shell remains a separate blocked workstream because `RearFullLandTransfer.Base` still consumes complex front-side geometry.
