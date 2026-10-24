"""Shared parametric propeller geometry in millimetres.

The station geometry is used by both the B-Rep builder and the preview.  Sections
are planar radial airfoils so OpenCascade can loft and cap them reliably.  This
is a geometric model; the NACA sections do not imply validated aerodynamic data.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from scipy.interpolate import PchipInterpolator


def _smoothstep(value: float) -> float:
    value = float(np.clip(value, 0.0, 1.0))
    return value * value * (3.0 - 2.0 * value)


@dataclass
class PropellerParameters:
    """User dimensions stored internally in mm; derived dimensions need no inputs."""

    diameter_mm: float
    pitch_mm: float
    num_blades: int
    handedness: str
    n_stations: int = 22
    n_airfoil_points: int = 60

    def __post_init__(self):
        self.diameter_mm = float(self.diameter_mm)
        self.pitch_mm = float(self.pitch_mm)
        if not np.isfinite(self.diameter_mm) or self.diameter_mm <= 0.0:
            raise ValueError("Propeller diameter must be a finite positive number.")
        if not np.isfinite(self.pitch_mm) or self.pitch_mm <= 0.0:
            raise ValueError("Geometric pitch must be a finite positive number.")
        if self.diameter_mm <= self.hub_diameter_mm:
            raise ValueError("Propeller diameter must exceed the 12 mm minimum hub diameter.")
        if isinstance(self.num_blades, bool) or int(self.num_blades) != self.num_blades:
            raise ValueError("Blade count must be an integer from 2 to 8.")
        self.num_blades = int(self.num_blades)
        if not 2 <= self.num_blades <= 8:
            raise ValueError("Blade count must be from 2 to 8.")
        handedness_norm = str(self.handedness).strip().upper()
        if handedness_norm in ("CCW", "CCW [RH]", "CCW (RIGHT-HAND)"):
            self.handedness = "CCW"
        elif handedness_norm in ("CW", "CW [LH]", "CW (LEFT-HAND)"):
            self.handedness = "CW"
        else:
            raise ValueError("Handedness must be CCW or CW.")
        if int(self.n_stations) != self.n_stations or self.n_stations < 12:
            raise ValueError("At least 12 radial stations are required.")
        if int(self.n_airfoil_points) != self.n_airfoil_points or self.n_airfoil_points < 16:
            raise ValueError("At least 16 points per airfoil surface are required.")
        self.n_stations = int(self.n_stations)
        self.n_airfoil_points = int(self.n_airfoil_points)

    @property
    def radius_mm(self) -> float:
        return self.diameter_mm / 2.0

    @property
    def hub_diameter_mm(self) -> float:
        """Explicit brief formula; the 12 mm lower limit applies to diameter."""
        return max(12.0, 0.10 * self.diameter_mm)

    @property
    def hub_radius_mm(self) -> float:
        return self.hub_diameter_mm / 2.0

    @property
    def bore_diameter_mm(self) -> float:
        return 0.45 * self.hub_diameter_mm

    @property
    def hub_bore_diameter_mm(self) -> float:
        return self.bore_diameter_mm

    @property
    def bore_radius_mm(self) -> float:
        return self.bore_diameter_mm / 2.0

    @property
    def blade_root_embed_radius_mm(self) -> float:
        """A positive overlap with the hub, outside the eventual mounting bore."""
        return 0.70 * self.hub_radius_mm

    @property
    def root_xi(self) -> float:
        return self.blade_root_embed_radius_mm / self.radius_mm

    @property
    def hub_length_mm(self) -> float:
        """Contain the entire buried root, including asymmetric camber and twist."""
        extent = PropellerMathEngine(self).root_axial_extent_mm()
        return max(0.036 * self.diameter_mm, 1.15 * 2.0 * extent)

    @property
    def hub_height_mm(self) -> float:
        return self.hub_length_mm

    @property
    def pitch_to_diameter_ratio(self) -> float:
        return self.pitch_mm / self.diameter_mm

    @property
    def hand_sign(self) -> float:
        return 1.0 if self.handedness == "CCW" else -1.0

    @property
    def root_pitch_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.pitch_mm, 2.0 * np.pi * self.hub_radius_mm)))

    @property
    def tip_pitch_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.pitch_mm, 2.0 * np.pi * self.radius_mm)))

    @property
    def disk_area_mm2(self) -> float:
        return float(np.pi * self.radius_mm ** 2)

    @property
    def disk_area_m2(self) -> float:
        return self.disk_area_mm2 * 1e-6


class PropellerMathEngine:
    """Closed NACA sections, a swept commercial planform, and helical twist."""

    def __init__(self, params: PropellerParameters):
        self.params = params

    @staticmethod
    def _transition_end(xi_root: float) -> float:
        # Very small props have a comparatively large minimum-size hub.
        return min(0.82, max(0.22, xi_root / 0.70 + 0.06))

    @staticmethod
    def naca_thickness_distribution(xi: float, xi_root: float = 0.07) -> float:
        """NACA 4415 neck blends into 4412 and tapers to 4409."""
        transition = PropellerMathEngine._transition_end(xi_root)
        if xi <= transition:
            weight = _smoothstep((xi - xi_root) / max(transition - xi_root, 1e-9))
            return 0.15 - 0.03 * weight
        weight = _smoothstep((xi - transition) / (1.0 - transition))
        return 0.12 - 0.03 * weight

    @staticmethod
    def chord_distribution(xi: float, diameter_mm: float, xi_root: float = None) -> float:
        """Smooth neck, midspan maximum, and elliptical-style compact tip taper."""
        if xi_root is None:
            xi_root = 0.70 * max(12.0, 0.10 * diameter_mm) / diameter_mm
        transition = PropellerMathEngine._transition_end(xi_root)
        # Compress the lifting region when the 12 mm hub dominates a small prop.
        peak = max(0.55, transition + 0.25 * (1.0 - transition))
        outer = peak + 0.55 * (0.96 - peak)
        positions = np.array([xi_root, transition, peak, outer, 0.96, 0.99, 1.0])
        chords = np.array([0.027, 0.072, 0.125, 0.090, 0.040, 0.023, 0.015])
        curve = PchipInterpolator(positions, chords, extrapolate=False)
        return float(diameter_mm * curve(float(np.clip(xi, xi_root, 1.0))))

    @staticmethod
    def pitch_angle_rad(pitch_mm: float, radius_mm: float) -> float:
        return float(np.arctan2(pitch_mm, 2.0 * np.pi * max(radius_mm, 0.0)))

    @property
    def radial_stations(self) -> np.ndarray:
        """Cosine spacing with explicit root, hub-edge and final three stations."""
        root = self.params.root_xi
        hub = self.params.hub_radius_mm / self.params.radius_mm
        anchors = np.array([root, hub, self._transition_end(root), 0.96, 0.99, 1.0])
        anchors = np.unique(anchors[(anchors >= root) & (anchors <= 1.0)])
        # Fill to the requested total, retaining the mandatory tip locations.
        candidates = root + (0.96 - root) * (1.0 - np.cos(np.linspace(0.0, np.pi, self.params.n_stations * 3))) / 2.0
        chosen = list(anchors)
        while len(chosen) < self.params.n_stations:
            distances = np.min(np.abs(candidates[:, None] - np.array(chosen)[None, :]), axis=1)
            chosen.append(float(candidates[int(np.argmax(distances))]))
        return np.array(sorted(chosen), dtype=float)

    def station_data(self) -> Dict[str, np.ndarray]:
        xi = self.radial_stations
        radius = xi * self.params.radius_mm
        return {
            "xi": xi,
            "radius_mm": radius,
            "chord_mm": np.array([self.chord_distribution(x, self.params.diameter_mm, self.params.root_xi) for x in xi]),
            "pitch_angle_rad": np.arctan2(self.params.pitch_mm, 2.0 * np.pi * radius),
            "thickness_ratio": np.array([self.naca_thickness_distribution(x, self.params.root_xi) for x in xi]),
            "sweep_mm": np.array([self.tangential_sweep_mm(x) for x in xi]),
        }

    def tangential_sweep_mm(self, xi: float) -> float:
        transition = self._transition_end(self.params.root_xi)
        aft = _smoothstep((xi - transition) / max(0.85 - transition, 0.05))
        tip_forward = _smoothstep((xi - 0.94) / 0.06)
        return self.params.diameter_mm * (0.018 * aft - 0.008 * tip_forward)

    def generate_airfoil_coordinates(self, xi: float, n_points: int = 60,
                                     m: float = 0.04, p: float = 0.40,
                                     closed_loop: bool = False) -> np.ndarray:
        """TE -> upper -> LE -> lower; duplicate TE only when closed_loop=True.

        The upper surface contains n_points points, with the LE at n_points-1.
        The lower spline can be built from that LE, the remaining points, and TE.
        """
        t = self.naca_thickness_distribution(xi, self.params.root_xi)
        xc = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, n_points)))
        yt = 5.0 * t * (0.2969 * np.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2
                        + 0.2843 * xc ** 3 - 0.1036 * xc ** 4)
        yt[[0, -1]] = 0.0
        forward = xc < p
        yc = np.where(forward, m / p ** 2 * (2 * p * xc - xc ** 2),
                      m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * xc - xc ** 2))
        dy = np.where(forward, 2 * m / p ** 2 * (p - xc),
                      2 * m / (1 - p) ** 2 * (p - xc))
        yc[[0, -1]] = 0.0
        angle = np.arctan(dy)
        upper = np.column_stack((xc - yt * np.sin(angle) - 0.25,
                                 yc + yt * np.cos(angle)))
        lower = np.column_stack((xc + yt * np.sin(angle) - 0.25,
                                 yc - yt * np.cos(angle)))
        points = np.concatenate((upper[::-1], lower[1:-1]))
        return np.vstack((points, points[0])) if closed_loop else points

    def cylindrical_conformal_transform(self, coords_2d: np.ndarray, radius_mm: float,
                                       chord_mm: float, pitch_angle_rad: float,
                                       hand_sign: float) -> np.ndarray:
        """Compatibility API: map a section onto a planar radial station.

        Planar sections replace the old cylinder-wrapped loops, which needed
        approximate non-planar filling faces at each end of the loft.
        """
        xs, ys = chord_mm * coords_2d[:, 0], chord_mm * coords_2d[:, 1]
        cp, sp = np.cos(pitch_angle_rad), np.sin(pitch_angle_rad)
        xi = radius_mm / self.params.radius_mm
        tangent = -xs * cp - ys * sp + self.tangential_sweep_mm(xi)
        axial = -xs * sp + ys * cp
        transition = self._transition_end(self.params.root_xi)
        center_weight = 1.0 - _smoothstep((xi - self.params.root_xi) / max(transition - self.params.root_xi, 1e-9))
        axial = axial - center_weight * 0.5 * (float(np.min(axial)) + float(np.max(axial)))
        return np.column_stack((hand_sign * tangent, np.full(len(tangent), radius_mm), axial))

    def section_coordinates(self, xi: float, closed_loop: bool = False) -> np.ndarray:
        radius = xi * self.params.radius_mm
        return self.cylindrical_conformal_transform(
            self.generate_airfoil_coordinates(xi, self.params.n_airfoil_points, closed_loop=closed_loop),
            radius, self.chord_distribution(xi, self.params.diameter_mm, self.params.root_xi),
            self.pitch_angle_rad(self.params.pitch_mm, radius), self.params.hand_sign)

    def root_axial_extent_mm(self) -> float:
        """Conservative buried-neck envelope used to size the flat hub faces."""
        hub_xi = self.params.hub_radius_mm / self.params.radius_mm
        xi = np.linspace(self.params.root_xi, hub_xi, 18)
        return max(float(np.max(np.abs(self.section_coordinates(float(x))[:, 2]))) for x in xi)

    def generate_all_blade_stations(self, closed_loop: bool = False) -> List[np.ndarray]:
        return [self.section_coordinates(float(x), closed_loop) for x in self.radial_stations]

    def get_aerodynamic_summary(self) -> Dict[str, np.ndarray]:
        xi = np.linspace(self.params.root_xi, 1.0, 160)
        radius = xi * self.params.radius_mm
        return {
            "xi": xi,
            "radius_mm": radius,
            "chord_mm": np.array([self.chord_distribution(x, self.params.diameter_mm, self.params.root_xi) for x in xi]),
            "pitch_angle_deg": np.degrees(np.arctan2(self.params.pitch_mm, 2.0 * np.pi * radius)),
            "thickness_ratio_pct": np.array([100 * self.naca_thickness_distribution(x, self.params.root_xi) for x in xi]),
        }

    def generate_preview_mesh_data(self) -> Dict[str, List[np.ndarray]]:
        """Analytical fallback preview with a real open mounting bore and no spinner.

        The UI can prefer tessellation of the finished B-Rep for exact agreement.
        """
        stations = np.array(self.generate_all_blade_stations(closed_loop=True))
        bx, by, bz = stations[:, :, 0], stations[:, :, 1], stations[:, :, 2]
        blades = []
        for k in range(self.params.num_blades):
            angle = k * 2 * np.pi / self.params.num_blades
            blades.append((bx * np.cos(angle) - by * np.sin(angle),
                           bx * np.sin(angle) + by * np.cos(angle), bz.copy()))
        theta = np.linspace(0.0, 2 * np.pi, 80)
        half_height = self.params.hub_length_mm / 2
        theta_wall, z = np.meshgrid(theta, [-half_height, half_height])
        hub = (self.params.hub_radius_mm * np.cos(theta_wall), self.params.hub_radius_mm * np.sin(theta_wall), z)
        bore = (self.params.bore_radius_mm * np.cos(theta_wall), self.params.bore_radius_mm * np.sin(theta_wall), z)
        theta_face, radius = np.meshgrid(theta, [self.params.bore_radius_mm, self.params.hub_radius_mm])
        top = (radius * np.cos(theta_face), radius * np.sin(theta_face), np.full_like(radius, half_height))
        bottom = (top[0], top[1], -top[2])
        return {"blades": blades, "hub": hub, "bore": bore, "hub_top": top, "hub_bottom": bottom}
