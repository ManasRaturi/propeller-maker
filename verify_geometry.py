"""Headless 10 x 4.5 benchmark, including a STEP round-trip topology audit.

Run with the project's local Python environment. The only stdout output is a JSON
report, which is also saved beside the benchmark STEP file. Relative paths are
resolved against this file's directory, so the check works from any directory.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import cadquery as cq
import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCP.TopoDS import TopoDS

from core.cad_generator import CadGenerator
from core.math_engine import PropellerMathEngine, PropellerParameters


PROJECT_DIR = Path(__file__).resolve().parent


def project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_DIR / path).resolve()


def _bbox(shape: cq.Shape) -> dict[str, float]:
    box = shape.BoundingBox()
    return {name: float(getattr(box, name)) for name in (
        "xmin", "xmax", "ymin", "ymax", "zmin", "zmax", "xlen", "ylen", "zlen"
    )}


def audit_step(path: Path, params: PropellerParameters) -> dict[str, Any]:
    """Inspect the actual reimported B-Rep, independently of exporter metadata."""
    checks: dict[str, Any] = {}
    failures: list[str] = []

    def require(name: str, condition: bool, **details: Any) -> None:
        checks[name] = {"passed": bool(condition), **details}
        if not condition:
            failures.append(name)

    imported = cq.importers.importStep(str(path))
    shape = imported.val()
    solids = shape.Solids()
    shells = shape.Shells()
    require("valid_brep", shape.isValid())
    require("single_solid", len(solids) == 1, count=len(solids))
    require("single_closed_shell", len(shells) == 1 and shells[0].Closed(),
            count=len(shells), closed=[bool(shell.Closed()) for shell in shells])
    volume = float(shape.Volume())
    require("positive_volume", math.isfinite(volume) and volume > 0, volume_mm3=volume)
    if len(solids) != 1:
        return {"passed": False, "failures": failures, "checks": checks}
    solid = solids[0]
    box = _bbox(solid)

    # MapShapesAndAncestors counts both incidences of a periodic surface seam.
    # Counting distinct faces instead would incorrectly flag a cylinder seam.
    ancestors = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(solid.wrapped, TopAbs_EDGE, TopAbs_FACE, ancestors)
    abnormal_edges = []
    degenerate_edges = []
    distal_edge_count = 0
    for index in range(1, ancestors.Extent() + 1):
        edge = TopoDS.Edge_s(ancestors.FindKey(index))
        incidences = int(ancestors.FindFromIndex(index).Extent())
        degenerate = bool(BRep_Tool.Degenerated_s(edge))
        cq_edge = cq.Edge(edge)
        # Lofted poles and fillet singularities can contain a kernel-declared
        # zero-length edge with one face. They do not form a physical boundary.
        edge_length = float(cq_edge.Length())
        zero_length_pole = degenerate and incidences == 1 and edge_length <= 1e-7
        if zero_length_pole:
            degenerate_edges.append({"index": index, "length_mm": edge_length,
                                     "face_incidences": incidences})
        edge_vertices = cq_edge.Vertices()
        is_distal = any(math.hypot(vertex.X, vertex.Y) >= 0.985 * params.radius_mm
                        for vertex in edge_vertices)
        distal_edge_count += int(is_distal)
        if incidences != 2 and not zero_length_pole:
            abnormal_edges.append({"index": index, "face_incidences": incidences,
                                   "degenerate": degenerate, "distal": is_distal})
    require("two_face_edge_incidence", not abnormal_edges,
            edge_count=ancestors.Extent(), physical_edge_count=ancestors.Extent() - len(degenerate_edges),
            zero_length_surface_singularities=degenerate_edges,
            abnormal_edges=abnormal_edges)

    bore_radius = float(getattr(params, "bore_radius_mm", 0.225 * params.hub_diameter_mm))
    hub_radius = float(params.hub_radius_mm)
    hub_height = float(params.hub_length_mm)
    tolerance = max(1e-5, params.diameter_mm * 1e-7)
    volume_tolerance = max(1e-5, params.diameter_mm ** 3 * 1e-12)
    probe_radius = bore_radius - max(1e-4, bore_radius * 1e-4)
    margin = max(1.0, hub_height * 0.1)
    probe = cq.Solid.makeCylinder(probe_radius, box["zlen"] + 2 * margin,
                                  cq.Vector(0, 0, box["zmin"] - margin))
    bore_intrusion = abs(float(solid.intersect(probe).Volume()))
    require("unobstructed_axial_through_bore", bore_intrusion <= volume_tolerance,
            nominal_diameter_mm=2 * bore_radius, probe_radius_mm=probe_radius,
            probe_zmin_mm=box["zmin"] - margin,
            probe_zmax_mm=box["zmax"] + margin,
            material_in_probe_mm3=bore_intrusion,
            volume_tolerance_mm3=volume_tolerance)

    bore_faces = []
    planar_hub_faces: dict[str, list[float]] = {"top": [], "bottom": []}
    for face in solid.Faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() == GeomAbs_Cylinder:
            cylinder = surface.Cylinder()
            axis = cylinder.Axis()
            location = axis.Location()
            direction = axis.Direction()
            if (abs(cylinder.Radius() - bore_radius) <= tolerance
                    and math.hypot(location.X(), location.Y()) <= tolerance
                    and abs(abs(direction.Z()) - 1.0) <= 1e-8):
                bounds = _bbox(face)
                bore_faces.append({"radius_mm": float(cylinder.Radius()),
                                   "zmin_mm": bounds["zmin"],
                                   "zmax_mm": bounds["zmax"]})
        elif surface.GetType() == GeomAbs_Plane:
            plane = surface.Plane()
            if abs(abs(plane.Axis().Direction().Z()) - 1.0) <= 1e-8:
                plane_z = plane.Location().Z()
                for label, expected_z in (("top", hub_height / 2),
                                          ("bottom", -hub_height / 2)):
                    if abs(plane_z - expected_z) <= tolerance:
                        planar_hub_faces[label].append(float(face.Area()))
    bore_wall_spans_height = (bool(bore_faces)
                              and min(f["zmin_mm"] for f in bore_faces)
                              <= -hub_height / 2 + tolerance
                              and max(f["zmax_mm"] for f in bore_faces)
                              >= hub_height / 2 - tolerance)
    require("concentric_cylindrical_bore_wall", bore_wall_spans_height,
            cylindrical_faces=bore_faces)
    require("flat_hub_top_and_bottom", all(planar_hub_faces.values()),
            face_areas_mm2=planar_hub_faces, nominal_height_mm=hub_height)

    engine = PropellerMathEngine(params)
    root_points = np.asarray(engine.generate_all_blade_stations(closed_loop=False)[0])
    root_zmin = float(root_points[:, 2].min())
    root_zmax = float(root_points[:, 2].max())
    require("root_section_within_hub_faces",
            root_zmin >= -hub_height / 2 - tolerance
            and root_zmax <= hub_height / 2 + tolerance,
            root_zmin_mm=root_zmin, root_zmax_mm=root_zmax,
            hub_zmin_mm=-hub_height / 2, hub_zmax_mm=hub_height / 2)

    # Detect any loft overshoot hidden between the sampled root stations. Blades
    # outside the hub are free to extend axially; only the hub's cylindrical
    # footprint is constrained to the two planar mounting faces.
    intrusion_volumes = {}
    for label, base_z, height in (
            ("above", hub_height / 2 + tolerance,
             max(margin, box["zmax"] - hub_height / 2 + margin)),
            ("below", box["zmin"] - margin,
             max(0.0, -hub_height / 2 - tolerance - (box["zmin"] - margin)))):
        if height <= tolerance:
            intrusion_volumes[label] = 0.0
            continue
        outside_probe = cq.Solid.makeCylinder(hub_radius - tolerance, height,
                                               cq.Vector(0, 0, base_z))
        intrusion_volumes[label] = abs(float(solid.intersect(outside_probe).Volume()))
    require("root_brep_within_hub_faces",
            all(value <= volume_tolerance for value in intrusion_volumes.values()),
            material_outside_hub_faces_mm3=intrusion_volumes,
            volume_tolerance_mm3=volume_tolerance)

    terminal_points = np.asarray(engine.generate_all_blade_stations(closed_loop=False)[-1])
    terminal_chord = float(np.linalg.norm(terminal_points.max(axis=0)
                                         - terminal_points.min(axis=0)))
    # This bound allows camber/thickness and sweep while rejecting the original
    # wide, abruptly cut terminal section. Topological closure is checked on the
    # exported distal edges, not inferred from the preview mesh.
    distal_vertices = [vertex for vertex in solid.Vertices()
                       if math.hypot(vertex.X, vertex.Y) >= 0.985 * params.radius_mm]
    distal_bad_edges = [edge for edge in abnormal_edges if edge["distal"]]
    require("compact_closed_blade_tips",
            bool(distal_vertices) and not distal_bad_edges
            and terminal_chord <= 0.020 * params.diameter_mm,
            distal_vertex_count=len(distal_vertices),
            distal_edge_count=distal_edge_count,
            abnormal_distal_edges=distal_bad_edges,
            terminal_section_extent_mm=terminal_chord,
            terminal_section_extent_limit_mm=0.020 * params.diameter_mm)

    return {"passed": not failures, "failures": failures, "checks": checks,
            "topology": {"solids": len(solids), "shells": len(shells),
                         "faces": len(solid.Faces()), "edges": ancestors.Extent()},
            "bounding_box_mm": box}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="work/benchmark_10x45.step",
                        help="Benchmark STEP path, relative to the project if not absolute.")
    parser.add_argument("--report", help="JSON report path (default: STEP name.report.json).")
    parser.add_argument("--existing", action="store_true",
                        help="Audit an existing --output STEP without regenerating it.")
    parser.add_argument("--verbose", action="store_true", help="Write generation progress to stderr.")
    args = parser.parse_args()
    output = project_path(args.output)
    report_path = (project_path(args.report) if args.report
                   else output.with_suffix(".report.json"))
    started = time.perf_counter()
    report: dict[str, Any] = {
        "benchmark": {"diameter_mm": 254.0, "pitch_mm": 114.3,
                      "num_blades": 2, "handedness": "CW"},
        "step_path": str(output), "report_path": str(report_path),
        "existing_step": args.existing,
    }
    try:
        params = PropellerParameters(254.0, 114.3, 2, "CW")
        if not args.existing:
            def progress(fraction: float, message: str) -> None:
                if args.verbose:
                    print(f"{fraction:5.0%} {message}", file=sys.stderr, flush=True)
            report["export"] = CadGenerator(params).generate_and_export_step(
                str(output), progress_callback=progress)
        report["round_trip"] = audit_step(output, params)
        report["passed"] = bool(report["round_trip"]["passed"]
                                and report.get("export", {}).get("is_valid", True))
        report["file_size_bytes"] = output.stat().st_size
    except Exception as exc:
        report["passed"] = False
        report["error"] = {"type": type(exc).__name__, "message": str(exc),
                           "traceback": traceback.format_exc()}
    report["elapsed_seconds"] = time.perf_counter() - started
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, allow_nan=False)
    report_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
