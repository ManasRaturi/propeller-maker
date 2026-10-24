# Propeller CAD & CFD STEP Generator

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![CAD Kernel](https://img.shields.io/badge/Kernel-OpenCASCADE%20%2F%20CadQuery-orange)](https://github.com/CadQuery/cadquery)
[![UI Framework](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet)](https://github.com/TomSchimansky/CustomTkinter)
[![Export Format](https://img.shields.io/badge/Export-ISO%2010303--21%20STEP-brightgreen)](https://en.wikipedia.org/wiki/ISO_10303-21)
[![Topology](https://img.shields.io/badge/Topology-Watertight%202--Manifold-success)](#verification--topology-audit)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An engineering CAD workstation and automated Python pipeline for generating **parametric, watertight, single-solid propeller models**. The tool outputs high-fidelity **ISO 10303-21 STEP (`.stp` / `.step`)** geometry designed for Computational Fluid Dynamics (CFD) mesh generation (ANSYS Fluent, OpenFOAM, Star-CCM+), CAD assemblies (SolidWorks, Fusion 360, FreeCAD), and high-resolution 3D printing.

The default baseline is the commercial UAV 10 x 4.5 benchmark: **254.0 mm diameter, 114.3 mm geometric pitch, 2 blades, Counter-Clockwise (CCW)**.

---

## Table of Contents

- [Features](#features)
- [Architecture & Geometry Engine](#architecture--geometry-engine)
- [Mathematical Formulation](#mathematical-formulation)
- [User Interface](#user-interface)
- [Installation & Quickstart](#installation--quickstart)
  - [Windows Launchers](#windows-launchers)
  - [Unix / macOS](#unix--macos)
  - [Manual Setup](#manual-setup)
- [Verification & Topology Audit](#verification--topology-audit)
  - [Headless Benchmark Audit](#headless-benchmark-audit)
  - [UI & Export Smoke Test](#ui--export-smoke-test)
- [CFD Pre-Processing Guidelines](#cfd-pre-processing-guidelines)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Exact B-Rep Solid Modeling**: Employs CadQuery and the OpenCASCADE technology (OCP) kernel to generate true analytical B-Rep solids—not discrete mesh approximations.
- **Parametric Blade & Hub Control**:
  - Continuous diameter ($D$) and geometric pitch ($P$) customization.
  - Multi-blade configurations (2 to 8 blades).
  - Handedness selection: CCW (Right-Hand tractor/pusher) or CW (Left-Hand).
  - Imperial $\leftrightarrow$ Metric real-time dimension conversion (inches / mm).
- **Aerodynamic Airfoil Transitions**:
  - Smooth radial morphing from structural root (**NACA 4415**) to efficient midspan (**NACA 4412**), tapering to low-drag tip (**NACA 4409**).
  - Mathematically closed trailing edge (sharp closure coefficient `-0.1036`) eliminating zero-thickness singularities.
- **Continuous Ellipsoidal Tip Closures**:
  - Smoothly lofted terminal closure over the outer $0.8\% R$, replacing abrupt planar caps or singular poles with clean, manifold B-Rep topology.
- **Automated Hub Sizing & Shaft Bore**:
  - Dynamically sized hub height guaranteeing complete blade root enclosure.
  - Post-union concentric through-bore cut ensuring zero blade root encroachment inside the mounting shaft.
- **Desktop Engineering Workstation**:
  - Sleek modern dark-themed GUI powered by CustomTkinter.
  - Interactive orthographic 3D CAD viewport with single-click camera presets (Isometric, Top $+Z$, Front, Side).
  - Real-time 2D aerodynamic distribution graphs (Chord length $c(r)$ and Twist angle $\theta(r)$).
  - Instant telemetry: Pitch-to-Diameter ratio, hub/bore dimensions, root/tip pitch angles, and disk swept area.
- **Bulletproof Export Safety**:
  - Atomic two-stage STEP export with round-trip reimport verification prior to committing files to disk.
- **CI / Headless Automation**:
  - Complete CLI test harness for automated geometry auditing, boundary verification, and UI smoke testing.

---

## Architecture & Geometry Engine

```
       +-----------------------+
       |  User Input / Config  |
       |  (D, P, Blades, Hand) |
       +-----------+-----------+
                   |
                   v
       +-----------------------+
       |   MathEngine (Core)   |
       |  - NACA 4-digit math  |
       |  - Cosine stations    |
       |  - Helical twist law  |
       |  - Chord distribution |
       +-----------+-----------+
                   |
                   v
       +-----------------------+
       | CadGenerator (Kernel) |
       |  - Dual-spline wires  |
       |  - Blade loft & cap   |
       |  - Cylindrical hub    |
       |  - Union & bore cut   |
       +-----------+-----------+
                   |
        +----------+----------+
        |                     |
        v                     v
+---------------+     +---------------+
| CustomTkinter |     | Watertight    |
|   Viewport    |     | ISO 10303-21  |
| & 2D Telemetry|     | STEP Solid    |
+---------------+     +---------------+
```

The geometry pipeline follows strict topological stages to ensure non-manifold-free solids:

1. **Station Computation**: Radial evaluation across 22 cosine-spaced stations ($r/R$), with anchor points at root embed radius ($0.70\,r_{hub}$), hub edge, transition zones, and distal stations ($0.96$, $0.99$, $1.00$).
2. **Wire Assembly**: Airfoils are discretized with 60 high-precision coordinate pairs per surface. Upper and lower surfaces are assembled as two smooth cubic B-Spline edges that join at the closed trailing edge and leading edge nose.
3. **Ellipsoidal Blade Loft**: The sections are transformed in 3D space by local pitch twist $\theta(r)$ and tangential sweep $S(r)$. Stations are lofted through a continuous OpenCASCADE `ThruSections` shell, culminating in a compact ellipsoidal vertex closure.
4. **Radial Array**: The single blade solid is rotated and duplicated about the $Z$-axis:
   $$\Delta \phi = \frac{360^\circ}{N_{blades}}$$
5. **Hub Union**: The blades are fused with a solid cylinder.
6. **Through-Bore Subtraction**: The central mounting shaft bore is cut axially *after* the blade unions, guaranteeing no internal blade root geometry can obstruct the bore passage.
7. **Validation & Atomic Write**: The solid is exported to a temporary file, re-parsed through the OpenCASCADE topology reader (`BRepCheck_Analyzer`), verified for manifoldness, volume, and shell closure, and atomically moved to the destination path.

---

## Mathematical Formulation

### 1. Helical Geometric Twist

The local section pitch angle $\theta(r)$ is aligned with the geometric pitch $P$ along each radial distance $r$:

$$\theta(r) = \arctan\left( \frac{P}{2\pi r} \right)$$

For counter-clockwise (CCW) rotation, the twist angle is applied positively; for clockwise (CW) rotation, it is inverted.

### 2. Chord Distribution $c(\xi)$

Let normalized radial station be $\xi = r / R \in [\xi_{root}, 1.0]$. The chord distribution uses shape-preserving piecewise cubic Hermite interpolation (PCHIP) across aerodynamic control stations:

| Station $\xi$ | Definition | Chord Factor $c/D$ |
| :--- | :--- | :--- |
| $\xi_{root}$ | Embedded root ($0.70\,r_{hub}/R$) | `0.027` |
| $\xi_{trans}$ | Aerodynamic neck transition | `0.072` |
| $\xi_{peak}$ | Midspan maximum lift chord | `0.125` |
| $\xi_{outer}$ | Outboard lifting section | `0.090` |
| `0.96` | Outboard control station | `0.040` |
| `0.99` | Tip transition station | `0.023` |
| `1.00` | Distal blade boundary | `0.015` |

### 3. Airfoil Camber & Thickness Blending

The airfoil cross-section transitions smoothly from a thicker, structurally robust root to an efficient high-speed tip:

- **Root Section ($\xi \le \xi_{trans}$)**: Blends smoothly from **NACA 4415** (15% thickness) into **NACA 4412** (12% thickness).
- **Outboard Section ($\xi > \xi_{trans}$)**: Blends smoothly from **NACA 4412** down to **NACA 4409** (9% thickness) at the tip.

Closed trailing-edge formula ($x \in [0, 1]$):

$$y_t(x) = 5 t \left( 0.2969\sqrt{x} - 0.1260 x - 0.3516 x^2 + 0.2843 x^3 - 0.1036 x^4 \right)$$

### 4. Hub & Bore Scaling Dimensions

| Parameter | Formula | 10 x 4.5 in (254 mm) Benchmark |
| :--- | :--- | :--- |
| **Hub Outer Diameter** ($D_{hub}$) | $\max(12.0\text{ mm}, 0.10\,D)$ | **25.400 mm** (1.00 in) |
| **Mounting Bore Diameter** ($D_{bore}$) | $0.45 \times D_{hub}$ | **11.430 mm** (0.45 in) |
| **Blade Embed Radius** ($r_{embed}$) | $0.70 \times r_{hub}$ | **8.890 mm** (0.35 in) |
| **Hub Axial Height** ($H_{hub}$) | $\max(0.036\,D, 1.15 \times 2 \cdot z_{root}^{max})$ | **9.458 mm** (0.37 in) |

---

## User Interface

The desktop workstation is designed for clear visual inspection and responsive parameter iteration:

- **Parameter Controls**: Direct numeric inputs for Diameter and Pitch, segmented button selectors for Blade Count (2–8) and Handedness (`CCW [RH]` / `CW [LH]`).
- **Telemetry Card**: Real-time evaluation of:
  - Pitch-to-Diameter ($P/D$) ratio
  - Hub Outer Diameter and Center Bore Diameter
  - Hub Axial Thickness
  - Root Pitch Angle ($\theta_{root}$) and Tip Pitch Angle ($\theta_{tip}$)
  - Swept Disk Area ($A = \pi R^2$)
- **3D Orthographic CAD Viewport**:
  - Built with Matplotlib 3D with equal physical aspect scaling across $X, Y, Z$.
  - Shaded Poly3D triangulation with directional illumination.
  - Interactive mouse rotation and quick-alignment buttons: **Iso**, **Top (+Z)**, **Front**, and **Side**.
- **2D Aerodynamic Plots**:
  - Live **Chord Distribution $c(r)$** plot with marked transition and peak stations.
  - Live **Twist Distribution $\theta(r)$** plot comparing local pitch angles.

---

## Installation & Quickstart

### Prerequisites

- **Python 3.10, 3.11, or 3.12** (64-bit).
- Windows 10/11, Ubuntu/Debian 20.04+, or macOS 12+.

---

### Windows Launchers

The project includes portable, self-bootstrapping launchers:

1. **Double-click** `run.bat` or `run_windows.bat`.
   - Automatically detects or creates `./venv`.
   - Upgrades `pip` and installs required packages from `requirements.txt`.
   - Launches the desktop application.

2. **Verify Environment Setup**:
   ```cmd
   run.bat --check
   ```

3. **Run Native UI Smoke Test**:
   ```cmd
   run.bat --smoke-test
   ```

---

### Unix / macOS

A dedicated shell launcher is provided for Linux and macOS workstations:

```bash
chmod +x run_unix.sh
./run_unix.sh
```

---

### Manual Setup

If you prefer to configure your own environment:

```bash
# Clone the repository
git clone https://github.com/ManasRaturi/propeller-maker.git
cd propeller-maker

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Launch GUI
python main.py
```

---

## Verification & Topology Audit

### Headless Benchmark Audit

`verify_geometry.py` performs an independent, rigorous topology and geometric audit on the OpenCASCADE B-Rep:

```bash
python verify_geometry.py --verbose
```

#### Automated Inspection Criteria:
- [x] **Single Closed B-Rep**: Exactly 1 solid, 1 closed outer shell, and positive non-zero volume.
- [x] **Manifold Edge Incidence**: Validates that all physical edges (including periodic splines) have exactly 2 face incidences with zero non-manifold defects.
- [x] **Singularity Classification**: Any zero-length surface poles (ellipsoidal tip closures) are verified as benign degenerate singularities ($< 10^{-7}\text{ mm}$) and not open seams.
- [x] **Unobstructed Through-Bore**: Cylindrical clearance probe sweeps through the bore to verify 0.000 mm³ internal blade intrusion.
- [x] **Planar Hub Boundary**: Confirms flat upper and lower hub surfaces and validates that blade root lofts remain entirely bounded within the hub axial thickness.
- [x] **Distal Tip Compactness**: Verifies the terminal chord meets the boundary threshold ($\le 0.015 D$) before entering the ellipsoidal cap.

Output produces a standardized JSON audit report (e.g. `work/benchmark_10x45.report.json`).

### UI & Export Smoke Test

Run automated smoke tests across the full UI stack:

```bash
python main.py --smoke-test --report work/ui-smoke.report.json --test-export work/ui-smoke.step
```

---

## CFD Pre-Processing Guidelines

When using exported STEP models in Computational Fluid Dynamics:

1. **Multiple Reference Frame (MRF) / Sliding Mesh Domains**:
   - Create a cylindrical rotating domain enclosure enclosing the propeller:
     - Radius: $\approx 1.1 \times R$ to $1.2 \times R$
     - Axial span: $\approx 0.5 \times D$ upstream, $1.0 \times D$ downstream
2. **Mounting Bore Treatment**:
   - The through-bore is modeled as true physical geometry.
   - For an isolated aerodynamic study with a solid shaft, either extend a virtual motor shaft through the bore or use a CAD boolean to seal the cylinder prior to volume meshing.
3. **Boundary Layer Inflation**:
   - The closed trailing edge has an analytical thickness of $\approx 0$, making it ideal for prism layer inflation without face distortion.
   - Set inflation first layer height based on target $y^+ \le 1$ for wall-resolved simulations ($k\text{-}\omega\text{ SST}$) or $y^+ \approx 30\text{--}50$ for wall functions.

---

## Project Structure

```
Propeller Maker/
├── .gitignore              # Production git ignore rules
├── LICENSE                 # MIT License
├── README.md               # Documentation and technical guide
├── main.py                 # Application entry point & smoke test harness
├── requirements.txt        # Pinned runtime dependencies
├── run.bat                 # Windows environment bootstrapper
├── run_windows.bat         # Minimal Windows launcher
├── run_unix.sh             # Linux & macOS shell launcher
├── verify_geometry.py      # Headless CAD benchmark & B-Rep topology audit
├── verify_ui.py            # Automated CustomTkinter UI smoke test
├── core/
│   ├── __init__.py
│   ├── math_engine.py      # NACA generation, twist laws, PCHIP chord profiles
│   └── cad_generator.py    # OpenCASCADE B-Rep builder, lofts, booleans, STEP IO
└── ui/
    ├── __init__.py
    └── main_window.py      # CustomTkinter interface, 3D viewport, 2D charts
```

---

## Contributing

Contributions, feature requests, and bug reports are welcome!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/NewFeature`)
3. Commit your Changes (`git commit -m "Add new parametric airfoil option"`)
4. Push to the Branch (`git push origin feature/NewFeature`)
5. Open a Pull Request

---

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

Developed with precision for drone engineers, aerodynamicists, and CAD enthusiasts.
