"""Validated OpenCascade construction; preview and STEP share one B-Rep."""
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import cadquery as cq
import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

from .math_engine import PropellerMathEngine, PropellerParameters

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CadGenerator:
    def __init__(self, params: PropellerParameters):
        self.params = params
        self.math_engine = PropellerMathEngine(params)
        self.finishing_notes = []

    def _build_station_wire(self, points: Any) -> cq.Wire:
        """Two splines preserve the exactly closed, sharp NACA trailing edge."""
        n = self.params.n_airfoil_points
        vectors = [cq.Vector(*map(float, point)) for point in points]
        upper = cq.Edge.makeSpline(vectors[:n])
        lower = cq.Edge.makeSpline(vectors[n-1:] + [vectors[0]])
        wire = cq.Wire.assembleEdges([upper, lower])
        if not wire.IsClosed() or not wire.isValid():
            raise RuntimeError("Airfoil section is not a valid closed wire.")
        return wire

    def build_single_blade(self) -> cq.Solid:
        """Loft planar stations into a rounded terminal vertex, exactly at R.

        The nominal compact c(1)=0.015D section starts an ellipsoidal closure.
        Reserve 0.8% R for that closure instead of leaving a planar tip face.
        """
        stations = [np.array(p, copy=True) for p in
                    self.math_engine.generate_all_blade_stations(closed_loop=False)]
        radius = self.params.radius_mm
        cap_length = .008*radius
        center = .5*(stations[-1].min(axis=0)+stations[-1].max(axis=0))
        tip_y = math.sqrt(radius*radius-center[0]*center[0])
        cap_start = tip_y-cap_length
        root_y = float(stations[0][0, 1])
        for section in stations:
            original_y = float(section[0, 1])
            section[:, 1] = root_y+(original_y-root_y)*(cap_start-root_y)/(radius-root_y)
        cap_section = stations[-1].copy()
        center[1] = cap_start
        wires = [self._build_station_wire(s) for s in stations]
        for angle in (25, 45, 65, 80, 88):
            theta = math.radians(angle)
            section = center+(cap_section-center)*math.cos(theta)
            section[:, 1] = cap_start+cap_length*math.sin(theta)
            wires.append(self._build_station_wire(section))
        builder = BRepOffsetAPI_ThruSections(True, False, 1e-7)
        # Every wire has the same TE/LE ordering. Automatic compatibility can
        # rotate origins/add degenerate edges as the terminal sections shrink,
        # creating visible ripples despite a topologically valid result.
        builder.CheckCompatibility(False)
        builder.SetMaxDegree(3)
        for wire in wires:
            builder.AddWire(wire.wrapped)
        builder.AddVertex(cq.Vertex.makeVertex(float(center[0]), tip_y, float(center[2])).wrapped)
        builder.Build()
        if not builder.IsDone():
            raise RuntimeError("OpenCascade could not loft the rounded blade.")
        blade = cq.Solid(builder.Shape())
        if not blade.isValid() or blade.Volume() <= 0:
            raise RuntimeError("Rounded blade loft failed B-Rep validation.")
        return blade

    def build_hub(self) -> cq.Solid:
        """Flat cylindrical blank; bore is cut after all blade unions."""
        p = self.params
        hub = cq.Solid.makeCylinder(p.hub_radius_mm, p.hub_length_mm,
                                   cq.Vector(0, 0, -p.hub_length_mm/2))
        try:
            chamfer = min(.4, .025*p.hub_diameter_mm, .06*p.hub_length_mm)
            finished = hub.chamfer(chamfer, None, hub.Edges())
            if finished.isValid() and finished.Volume() > 0:
                hub = finished
        except Exception as exc:
            self.finishing_notes.append(f"Hub rim chamfer omitted: {type(exc).__name__}")
        return hub

    def build_hub_and_spinner(self) -> cq.Workplane:
        """Compatibility alias for original callers. No spinner is generated."""
        return cq.Workplane(obj=self.build_hub())

    def _try_root_fillet(self, shape: cq.Shape) -> cq.Shape:
        p = self.params
        radius = p.hub_radius_mm
        candidates = []
        for edge in shape.Edges():
            if edge.geomType() != "BSPLINE":
                continue
            samples = [edge.positionAt(t) for t in (.1, .5, .9)]
            if all(abs(math.hypot(v.x, v.y)-radius) < max(.05, radius*.01)
                   and abs(v.z) < .48*p.hub_length_mm for v in samples):
                candidates.append(edge)
        if candidates:
            try:
                rounded = shape.fillet(min(.4, p.diameter_mm*.001), candidates)
                if rounded.isValid() and len(rounded.Solids()) == 1:
                    self.finishing_notes.append("Blade root fillet applied.")
                    return rounded
            except Exception as exc:
                self.finishing_notes.append(f"Root fillet omitted: {type(exc).__name__}")
        else:
            self.finishing_notes.append("Root blend uses the smooth embedded loft.")
        return shape

    @staticmethod
    def validate_topology(shape: cq.Shape) -> Dict[str, Any]:
        solids = shape.Solids()
        if len(solids) != 1:
            raise RuntimeError(f"Expected one connected solid, found {len(solids)}.")
        solid = solids[0]
        shells = solid.Shells()
        if not solid.isValid() or not BRepCheck_Analyzer(solid.wrapped).IsValid():
            raise RuntimeError("OpenCascade reports invalid B-Rep topology.")
        if len(shells) != 1 or not shells[0].Closed() or solid.Volume() <= 0:
            raise RuntimeError("Expected one closed shell with positive volume.")
        adjacency = TopTools_IndexedDataMapOfShapeListOfShape()
        TopExp.MapShapesAndAncestors_s(solid.wrapped, TopAbs_EDGE, TopAbs_FACE, adjacency)
        # A smooth surface pole has a zero-length degenerate edge with one
        # face incidence. It is not an open boundary in physical space.
        poles = 0
        bad_edges = 0
        for i in range(1, adjacency.Extent()+1):
            edge = cq.Edge(adjacency.FindKey(i))
            incidence = adjacency.FindFromIndex(i).Size()
            pole = BRep_Tool.Degenerated_s(edge.wrapped) and edge.Length() < 1e-7
            poles += int(pole)
            if incidence != 2 and not (pole and incidence == 1):
                bad_edges += 1
        if bad_edges:
            raise RuntimeError(f"Found {bad_edges} open or non-manifold edges.")
        return {"is_valid": True, "is_watertight": True, "solid_count": 1,
                "shell_count": 1, "non_manifold_edges": 0, "degenerate_pole_edges": poles,
                "volume_mm3": float(solid.Volume())}

    def generate_propeller_solid(self, progress_callback: Optional[Callable] = None) -> cq.Workplane:
        def progress(frac, message):
            if progress_callback:
                progress_callback(frac, message)
        progress(.1, "LOFTING B-REP SOLID...")
        blade = self.build_single_blade()
        progress(.4, "FORMING CYLINDRICAL HUB...")
        shape = self.build_hub()
        for i in range(self.params.num_blades):
            progress(.45+.3*i/self.params.num_blades,
                     f"UNITING BLADE {i+1} OF {self.params.num_blades}...")
            shape = shape.fuse(blade.rotate((0, 0, 0), (0, 0, 1), 360*i/self.params.num_blades))
        shape = shape.clean()
        shape = self._try_root_fillet(shape)
        progress(.82, "BORING CENTER MOUNTING HOLE...")
        p = self.params
        bore = cq.Solid.makeCylinder(p.bore_diameter_mm/2, p.hub_length_mm+2,
                                    cq.Vector(0, 0, -p.hub_length_mm/2-1))
        shape = shape.cut(bore).clean()
        progress(.9, "VALIDATING MANIFOLD TOPOLOGY...")
        self.validate_topology(shape)
        return cq.Workplane(obj=shape.Solids()[0])

    @staticmethod
    def preview_mesh(propeller: cq.Workplane) -> Dict[str, Any]:
        """Tessellate the actual validated solid at scale-relative tolerance."""
        shape = propeller.val()
        tolerance = max(.015, shape.BoundingBox().DiagonalLength*.0003)
        vertices, triangles = shape.tessellate(tolerance, .15)
        return {"vertices": np.array([v.toTuple() for v in vertices]),
                "triangles": np.asarray(triangles, dtype=int)}

    def generate_and_export_step(self, output_path: str, progress_callback: Optional[Callable] = None,
                                 propeller: Optional[cq.Workplane] = None) -> Dict[str, Any]:
        start = time.perf_counter()
        out_file = Path(output_path).expanduser()
        if not out_file.is_absolute():
            out_file = PROJECT_ROOT/out_file
        out_file = out_file.resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if propeller is None:
            propeller = self.generate_propeller_solid(progress_callback)
        topology = self.validate_topology(propeller.val())
        if progress_callback:
            progress_callback(.95, "WRITING AND READING BACK STEP...")
        fd, temporary = tempfile.mkstemp(suffix=".step", prefix=".propeller-", dir=out_file.parent)
        os.close(fd)
        try:
            cq.exporters.export(propeller, temporary, exportType="STEP")
            imported = cq.importers.importStep(temporary).val()
            self.validate_topology(imported)
            os.replace(temporary, out_file)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        bb = propeller.val().BoundingBox()
        size = out_file.stat().st_size
        if progress_callback:
            progress_callback(1., "STEP EXPORTED")
        return {**topology, "output_path": str(out_file), "file_size_bytes": size,
                "file_size_mb": size/(1024*1024), "elapsed_seconds": time.perf_counter()-start,
                "bounding_box": {k: float(v) for k, v in dict(xmin=bb.xmin, xmax=bb.xmax,
                 ymin=bb.ymin, ymax=bb.ymax, zmin=bb.zmin, zmax=bb.zmax,
                 dx=bb.xlen, dy=bb.ylen, dz=bb.zlen).items()},
                "diameter_mm": self.params.diameter_mm, "pitch_mm": self.params.pitch_mm,
                "num_blades": self.params.num_blades, "handedness": self.params.handedness,
                "finishing_notes": self.finishing_notes}
