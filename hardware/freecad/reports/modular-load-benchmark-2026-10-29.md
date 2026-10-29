# Modular assembly document-load benchmark

Date: 2026-10-29  
FreeCAD: 1.1.1  
Branch: `hardware-integration`

## Method

Ran three interleaved trials per document. Every trial used a fresh `freecadcmd` process. The timer covered `App.openDocument()`; it excluded FreeCAD process startup and did not explicitly recompute or save. Opening the assembly also loaded its relative linked documents. The operating-system file cache was not flushed, so these are repeatable warm-cache measurements rather than cold-start guarantees.

Run the bounded benchmark with:

```sh
python3 hardware/freecad/scripts/benchmark_document_open.py --runs 3 --timeout 170
```

Raw per-run data is in `modular-load-benchmark-2026-10-29.json`.

## Results

| Document opened | Median `openDocument` | File size | Loaded documents / objects |
| --- | ---: | ---: | ---: |
| Original monolith `pendant.FCStd` | 5.714 s | 65,817,113 bytes | 1 / 816 |
| `pendant-modular-assembly.FCStd` | 0.422 s | 2,545,943 bytes | 5 / 167 |

The assembly-open median was **13.6× faster** in this run. Its loaded document set was the assembly, master, display retainer, USB cover, and locator component document. Those five files total 4,705,387 bytes. The result measures saved-document loading only; it does not establish a 13.6× improvement in recomputation, viewport rendering, or interactive editing.

The assembly still contains six static BREP interim components. This benchmark demonstrates a loading advantage for the current modular assembly and its three editable linked sources; it does not claim that all pendant components have been modularized.
