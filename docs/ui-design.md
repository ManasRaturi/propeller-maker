# Native UI design

[Default desktop reference in Figma](https://www.figma.com/design/xjpnXfWr87ZLNZuNQHJfqy/Propeller-Maker?node-id=2-40) · [Compact view with blade profiles](https://www.figma.com/design/xjpnXfWr87ZLNZuNQHJfqy/Propeller-Maker?node-id=2-41)

The redesign answers one question: **What will my propeller look like, and can I export it?** The model is the largest element; dimension inputs remain beside it and export stays in the top bar.

## Direction

The taste skill dealt **Framed sheet**, seed **884451844**, for a desktop builder. No redraws were needed. Its neutral frame and single white workspace are retained: a 48 px top bar, 304 px inspector, 8 px outer inset, 16 px sheet corners, and no shadows. The face comes from an instrument-like neutral frame, IBM Plex typography and teal geometry. The product's own two-blade form becomes its mark, while the exact propeller solid is the signature visual.

This is a native desktop application, so the design is checked at its supported desktop sizes, 1400 × 880 and 1150 × 750. Web-only mobile navigation and browser inspection rules are not applicable.

## What is visible

- Diameter, pitch, blade count and mm/in units are the editable inputs.
- Clockwise rotation is stated once; it remains fixed by the existing engine.
- Outer hub diameter, shaft bore and thickness remain visible because they affect mounting.
- Pitch ratio, root/tip angles, swept area, estimated thrust and topology diagnostics are behind **Engineering details**.
- Chord and twist plots are behind **Blade profiles**, closed initially.
- Camera presets and an optional axes view stay inside the model workspace.
- Export and preview actions use their existing callbacks. Worker progress is translated into plain UI wording at the presentation boundary.

Internal sampling counts, kernel names, file standards and manifold diagnostics do not occupy the normal editing view. All metric widgets required by existing callbacks remain present.

## Portable resources

The implementation stays with CustomTkinter and Matplotlib. UI resources live under `ui/`; it adds no browser, service, installer or network dependency.

IBM Plex Sans Regular/SemiBold and IBM Plex Mono Regular are bundled in `ui/assets/fonts/`, with their [SIL Open Font License](https://github.com/IBM/plex/blob/master/LICENSE.txt). Source: [IBM Plex](https://github.com/IBM/plex). Windows registers these fonts privately for the running process, without installing them. Matplotlib loads the bundled files directly; platforms whose Tk cannot use a process-private font use their native font fallback.

The main presentation tokens are defined in `ui/theme.py`: ground `#F4F6F6`, white sheet, ink `#171C1D`, secondary text `#5D6567`, and teal `#1B6C80`. Typography follows 12/14/16/22 px roles, with Plex Mono for figures. Filled near-black is reserved for the STEP export action. Numeric readouts are aligned at one right edge.

## Reference integrity and review

The Figma file contains editable text, auto-layout groups, semantic color/spacing/radius variables, shared text styles, reusable action/input/segment/readout/disclosure components and component instances. The UI is not a screenshot placed inside Figma. Only the central propeller is a discrete raster content asset, rendered offscreen from the existing benchmark STEP solid. Profile vectors are generated from the existing `PropellerMathEngine.get_aerodynamic_summary()` output.

The benchmark reference uses 254 mm diameter, 114.3 mm pitch, two blades and clockwise rotation. Its hub diameter is 25.400 mm, shaft bore 11.430 mm and thickness 9.144 mm, read from the existing parameter engine. There are no invented operating statistics or placeholder datasets.

Both reference compositions were visually reviewed after synchronization with the native layout. Text uses IBM Plex Sans or IBM Plex Mono, labels fit, the main model carries the teal, and the compact expanded-profile view retains all primary controls. The final screenshots are design references; they are not captures of the user's active desktop.

## Implementation validation

- All core files retain their original hashes. Fourteen behavioral controller methods are AST-identical; other controller edits change presentation text only.
- Eleven headless controller regression tests pass, covering validation, unit conversion, metrics, cache use, worker serialization, export callbacks and closing during work.
- A newly generated benchmark STEP passes all eleven geometry and round-trip checks.
- Native widgets were constructed with the Tk root kept withdrawn, window mapping forbidden and title-bar manipulation suppressed. Disclosures, axes and camera controls passed; no visible application was opened.
- Offscreen renders and projected mesh-vertex bounds confirm all four camera presets fit both 1000 × 640 and 1000 × 400 canvases. A uniform presentation zoom of 1.35 retains equal physical X/Y/Z scale.

The browser-specific taste inspector does not measure Tk widgets. Figma composition review, native hidden-widget checks and offscreen Matplotlib rendering serve as the desktop checks. The optional visible smoke test remains available for a later interactive session.
