# USB tethered cover dependency-group readiness

Date: 2026-10-29
Branch: `hardware-integration`
Source: `pendant-bodies/usb-tethered-cover.FCStd`

## Scope clarification

The earlier USB audit was rooted at the single manufacturing Body `Body_USBTetheredCover` and correctly returned `BLOCKED` when helper Bodies and support objects were treated as outside that Body. The extracted component document intentionally retains those native helper Bodies and their complete feature histories. For modular-component readiness, the correct boundary is this full dependency group within `usb-tethered-cover.FCStd`, with the master expressions explicitly permitted.

A fresh Tip-rooted audit expanded 39 objects (17 ordinary dependencies plus helper-Body Tip expansion). The explicit group allowlist contains the seven reached Body owners and the 22 same-document support objects required by the active Tip. Under that group scope, the auditor reports `READY`, with zero unknown references or uncertainties. No Sketcher external geometry, App::Link, or ShapeBinder references remain. The only cross-document inputs are the ten already validated width-profile expressions to `pendant_master#ExteriorEnvelope`, using `../pendant-master.FCStd`.

This means the component source is self-contained as an editable dependency group. It does not mean `Body_USBTetheredCover` can be separated from its helper geometry into a one-Body file without reconstruction. The top-level assembly continues to link only the manufacturing Body while the source document supplies its editable helper history.

## Current geometry evidence

The saved manufacturing Tip `USBPlugLeadIn` remains a valid one-solid Body. The canonical assembly cold-start check loaded the master and four component documents; its USB live link matched the source Body in validity, volume, and bounds. Prior reversible master-width testing verified the USB Tip and assembly link update and return to baseline, including fresh-process open after refresh saves the component.

The exact property-level dependency list and permitted group manifest are in `usb-component-group-readiness.json`. The report does not claim any shell, faceplate, or encoder extraction readiness.
