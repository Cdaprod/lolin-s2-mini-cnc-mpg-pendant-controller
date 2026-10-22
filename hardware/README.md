Understood. I’ll keep that component out of the active hardware documentation and future design discussions.

The Encoder Interface section of `hardware/README.md` should read:

# CNC MPG Pendant — Hardware

This directory contains the version-controlled mechanical and electrical design of the CNC MPG pendant.

## Design Philosophy

**One repository. One FreeCAD master. One consolidated STEP assembly. One KiCad project. One coordinated hardware revision.**

The hardware is developed as a single integrated system. Mechanical geometry, electrical connections, firmware pin assignments, and visual documentation must remain consistent with the same version of the design.

Git provides the revision history. Do not create parallel projects, duplicate component libraries, or files named `final`, `latest`, `v2`, etc.

## Directory Structure

```text
hardware/
├── README.md
├── freecad/
│   ├── pendant.FCStd
│   └── pendant_assembly.step
├── kicad/
│   ├── pendant.kicad_pro
│   ├── pendant.kicad_sch
│   └── pendant.kicad_pcb
└── visuals/
    ├── assembly.png
    ├── schematic.pdf
    └── ...
```

The filenames above are conventions. Existing authoritative files may retain their current names rather than being renamed unnecessarily.

The `visuals/` directory contains selected PNG, SVG, PDF, and other visual deliverables generated from the active design. These are supporting outputs, not independent design sources.

## 1. FreeCAD — Mechanical Authority

`freecad/pendant.FCStd` is the **single editable mechanical master**.

It contains the complete pendant assembly, including:

- Front shell, faceplate, rear shell, and mating geometry.
- XIAO ESP32-S3 and Round Display.
- MCP23017 module.
- Salvaged encoder and selector assembly.
- Existing `Body_BreakoutBoard`.
- Mounting supports, clearances, fasteners, and other mechanical features.

Preserve distinct bodies and meaningful object names within the FreeCAD document.

Do not arbitrarily change the enclosure silhouette, overall dimensions, selector positions, or established component placements to resolve local clearance problems.

Maintain valid, recomputable, parametric geometry wherever practical.

### Single STEP Policy

`freecad/pendant_assembly.step` is the **only maintained STEP file**.

It is a consolidated export of the current FreeCAD assembly, preserving separate solids and component placements wherever the export format supports them.

Do not maintain individual component STEP files in Git.

When KiCad StepUp or another tool requires individual component geometry, generate temporary exports from the FreeCAD master. These must not become separate authoritative models.

Whenever the mechanical assembly changes, regenerate the consolidated STEP export and commit it alongside the updated `.FCStd`.

## 2. KiCad — Electrical Authority

The KiCad project is the authoritative source for electrical connectivity.

It must contain the actual electrical schematic, symbols, nets, component references, footprints, and PCB information relevant to the design.

**A mechanical STEP model is not an electrical schematic.**

The active hardware includes:

- Seeed XIAO ESP32-S3.
- Seeed 1.28-inch Round Display.
- MCP23017 I²C GPIO expander.
- Salvaged MPG encoder.
- Salvaged selector switches and buttons.
- Existing breakout board and interconnecting wiring.

The architecture uses separate interconnected boards and wiring harnesses, not a newly designed universal carrier PCB.

Do not invent PCB routing or fabricate a new carrier board merely to populate `pendant.kicad_pcb`. Use the PCB editor only for physical board reconstruction or genuine board-design requirements.

### Encoder Interface

The encoder operates from the 3.3 V supply and provides single-ended A/B signals to the microcontroller.

The current bench wiring includes matched 1 kΩ series resistors and 1 nF capacitors to ground on the two signal lines. Their inclusion in the final schematic must reflect the selected and validated physical circuit.

Verify GPIO assignments, electrical levels, connector orientation, and signal behavior against the actual hardware and firmware.

Unknown connections must remain explicitly unverified.

### Physical Wiring

Wiring harnesses and connector pinouts belong in the KiCad schematic wherever practical.

A separate harness documentation system is not required.

Preserve distinctions between connector series, pitches, pin numbering, and verified physical connections.

## 3. Visuals — Review and Handoff

`visuals/` contains useful, human-readable representations of the active hardware design.

Examples include:

- FreeCAD assembly renders.
- Enclosure cross-sections.
- KiCad schematic PDF exports.
- Wiring and connector diagrams.
- Component placement illustrations.
- Mechanical fit and clearance views.

Visuals should accurately reflect the version-controlled source files.

Prefer reproducible exports over manually maintained drawings.

Do not accumulate obsolete screenshots or multiple competing versions of the same illustration.

## 4. FreeCAD ↔ KiCad Integration

FreeCAD and KiCad must describe the same physical hardware.

Use KiCad StepUp when geometry exchange, placement verification, or PCB-to-enclosure integration is required.

The intended workflow is:

1. Edit the existing FreeCAD or KiCad source.
2. Verify affected dimensions, pins, nets, and component placements.
3. Exchange or compare geometry using StepUp when applicable.
4. Resolve discrepancies in the authoritative source.
5. Regenerate the consolidated STEP and relevant visuals.
6. Commit all related changes together.

KiCad symbols and footprints must agree on pin and pad numbering. A complete assembly STEP file does not replace KiCad’s footprint definitions.

Temporary component-level STEP exports are permitted for integration, but are not versioned.

## 5. Version Control

The Git repository maintains the history of the entire hardware design.

The `hardware-integration` branch contains the authoritative native hardware engineering sources. The `main` branch contains firmware, public documentation, and reviewed generated preview artifacts. Do not merge this engineering branch wholesale into `main`; publish an explicit allowlist of validated SVG, PNG, and PDF artifacts through a review pull request.

Keep related changes together:

- FreeCAD modifications with updated STEP exports.
- Electrical changes with corresponding schematic and footprint updates.
- Pin mapping changes with affected firmware configuration.
- Updated visuals when they materially help review.

Avoid committing temporary CAD backups, caches, intermediate exports, or duplicate assemblies.

Do not overwrite validated geometry or electrical work without preserving the change in Git history.

## 6. Codex and Automation Requirements

Codex and other automated engineering tools must modify the existing version-controlled design rather than create replacement projects.

Before making changes, inspect the current FreeCAD document, KiCad project, and relevant firmware configuration.

Automation must:

- Preserve the single-master FreeCAD and single-STEP policy.
- Reuse existing bodies, sketches, component placements, and established design features.
- Avoid unnecessary enclosure enlargement or destructive geometry changes.
- Preserve the physical salvaged breakout board and selector positions.
- Build genuine KiCad electrical schematics rather than conceptual block diagrams presented as finished schematics.
- Avoid introducing a carrier PCB unless explicitly requested.
- Use temporary component exports when StepUp requires them.
- Validate FreeCAD recompute, geometry, KiCad ERC/DRC, and mechanical integration where applicable.
- Report assumptions, unresolved issues, and validation results accurately.

Do not claim a design is manufacturing-ready merely because its files export successfully.

## 7. Validation

Before accepting a hardware change, perform applicable checks:

- FreeCAD recomputes without unexpected errors.
- Existing enclosure and mounting geometry remains intact.
- Component collisions and clearances are evaluated.
- Consolidated STEP matches the current FreeCAD assembly.
- KiCad electrical connectivity reflects the actual hardware.
- Symbol pins and footprint pads agree.
- Firmware pin mappings agree with verified electrical connections.
- KiCad ERC and applicable PCB DRC checks pass, or exceptions are documented.
- Visual deliverables reflect the current design.

Software-controlled stop or deadman inputs must not be represented as substitutes for a properly implemented machine emergency-stop safety circuit.

## Governing Rule

**Maintain one coherent hardware design, not a collection of competing revisions.**

FreeCAD defines the mechanical assembly. KiCad defines electrical connectivity. The consolidated STEP and `visuals/` directory provide reproducible representations of that design.

Git records its evolution.

All future engineering work must preserve this structure unless the project explicitly adopts a new architecture.