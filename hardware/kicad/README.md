# CNC MPG Pendant — generated native KiCad inventory

Open `CNC_MPG_Pendant_Master.kicad_pro` in KiCad and launch Schematic Editor.

- This is a **fresh, editable KiCad schematic** with custom embedded symbols, functional net labels, no LM393 and no passive encoder filter.
- It represents **existing breakout boards as assemblies**, not bare chips or a fabricated carrier PCB.
- It is **not fabrication-ready**: schematic pin numbers are symbolic indices; exact connector pin numbers, USB host VBUS/CC, button population, LED drive, battery and power protection need verification.
- `component_inventory.csv` is the full inventory, including mechanical parts and optional items not appropriate as electrical schematic symbols.
- The schematic includes logical labels for XIAO ↔ MCP I2C, encoder A/B, selector and button signals.
- The round display's interconnect is marked TBD because its actual XIAO mating pin map needs checking; do not wire its placeholder labels to arbitrary GPIO.
- The E-stop is shown isolated with no-connect markers: **never replace a hardwired stop with firmware or a GPIO input**.
- USB host role/power and the CH34x driver remain unimplemented.

Export using KiCad: `kicad-cli sch export pdf CNC_MPG_Pendant_Master.kicad_sch -o schematic.pdf`
Run ERC: `kicad-cli sch erc CNC_MPG_Pendant_Master.kicad_sch -o erc.txt`