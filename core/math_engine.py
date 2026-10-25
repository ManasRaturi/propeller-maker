"""Shared parametric propeller geometry in millimetres.

Standardized exclusively for Clockwise (CW) rotation viewed from upstream (+Z)
looking downstream (-Z), generating positive reaction thrust in the +Z direction.
Sections are planar radial airfoils so OpenCascade B-Rep kernels can loft, cap,
and union them reliably into a watertight manifold STEP solid.
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
    """User dimensions stored internally in mm; locked strictly to CW rotation."""

    diameter_mm: float
    pitch_mm: float
    num_blades: int
    handedness: str = "CW"
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
        # Standardized exclusively to Clockwise (CW) rotation (+Z thrust standard)
        handedness_norm = str(self.handedness).strip().upper()
        if handedness_norm in ("CW", "CW [LH]", "CW (LEFT-HAND)", "CLOCKWISE", "CW (CLOCKWISE)"):
            self.handedness = "CW"
        else:
            # Enforce CW rotation standard per engineering audit
            self.handedness = "CW"
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
        """CW rotation standard: 1.0 (Leading edge in +X, trailing edge in -X)."""
        return 1.0

    @property
    def root_pitch_deg(self) -> float:
        return float(np.degrees(PropellerMathEngine.pitch_angle_rad(
            self.pitch_mm, self.hub_radius_mm, self.hub_radius_mm / self.radius_mm)))

    @property
    def tip_pitch_deg(self) -> float:
        return float(np.degrees(PropellerMathEngine.pitch_angle_rad(
            self.pitch_mm, self.radius_mm, 1.0)))

    @property
    def disk_area_mm2(self) -> float:
        return float(np.pi * self.radius_mm ** 2)

    @property
    def disk_area_m2(self) -> float:
        return self.disk_area_mm2 * 1e-6

    def estimate_static_thrust(self, rpm: float = 6000.0, rho: float = 1.225) -> Tuple[float, float]:
        """Estimate static thrust via Blade Element Momentum Theory (BEMT)."""
        return PropellerMathEngine.estimate_static_thrust_bemt(
            self.diameter_mm, self.pitch_mm, self.num_blades, rpm=rpm, rho=rho)


class PropellerMathEngine:
    """NACA 4412 cambered sections, full-solidity APC planform, and CW helical twist."""

    def __init__(self, params: PropellerParameters):
        self.params = params

    @staticmethod
    def _transition_end(xi_root: float) -> float:
        # Hub embed region transition
        return min(0.82, max(0.22, xi_root / 0.70 + 0.06))

    @staticmethod
    def naca_thickness_distribution(xi: float, xi_root: float = 0.07) -> float:
        """NACA 4412 root (t=0.12) tapering smoothly to NACA 44085 (t=0.085) at the tip."""
        transition = PropellerMathEngine._transition_end(xi_root)
        if xi <= transition:
            weight = _smoothstep((xi - xi_root) / max(transition - xi_root, 1e-9))
            return 0.13 - 0.01 * weight  # 0.13 at root embed down to 0.12 at hub edge
        weight = _smoothstep((xi - transition) / (1.0 - transition))
        return 0.12 - 0.035 * weight  # 0.12 at hub edge down to 0.085 at blade tip

    @staticmethod
    def chord_distribution(xi: float, diameter_mm: float, xi_root: float = None) -> float:
        """Full-solidity APC-style chord distribution (GrabCAD 10x45 standard).

        Peak chord c_max ≈ 0.155*D at xi ≈ 0.50, tapering smoothly to a closed,
        compact 0.015*D terminal section at the tip (xi = 1.0).
        """
        if xi_root is None:
            xi_root = 0.70 * max(12.0, 0.10 * diameter_mm) / diameter_mm
        transition = PropellerMathEngine._transition_end(xi_root)
        positions = np.array([xi_root, transition, 0.50, 0.75, 0.96, 0.99, 1.0])
        chords = np.array([0.027, 0.072, 0.155, 0.115, 0.040, 0.023, 0.015])
        curve = PchipInterpolator(positions, chords, extrapolate=False)
        return float(diameter_mm * curve(float(np.clip(xi, xi_root, 1.0))))

    @staticmethod
    def pitch_angle_rad(pitch_mm: float, radius_mm: float, xi: float = 1.0) -> float:
        """Geometric helix pitch angle beta(r) = arctan(P / (2*pi*r)).

        Includes a structural root clamp (beta_max <= 65 deg) inside the hub blend region (xi < 0.18).
        """
        beta = float(np.arctan2(pitch_mm, 2.0 * np.pi * max(radius_mm, 1e-9)))
        if xi < 0.18:
            max_beta = np.radians(65.0)
            beta = min(beta, max_beta)
        return beta

    @property
    def radial_stations(self) -> np.ndarray:
        """Cosine spacing with explicit root, hub-edge and final three stations."""
        root = self.params.root_xi
        hub = self.params.hub_radius_mm / self.params.radius_mm
        anchors = np.array([root, hub, self._transition_end(root), 0.96, 0.99, 1.0])
        anchors = np.unique(anchors[(anchors >= root) & (anchors <= 1.0)])
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
            "pitch_angle_rad": np.array([self.pitch_angle_rad(self.params.pitch_mm, r, x) for r, x in zip(radius, xi)]),
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
        """NACA 4412 cambered section with closed trailing edge (-0.1036 * xc^4).

        Centered at quarter-chord: x_hat in [-0.25, +0.75].
        Order: TE -> Upper Surface (Suction) -> LE -> Lower Surface (Pressure) -> (TE if closed).
        LE is exactly at index n_points - 1.
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
                                        hand_sign: float = 1.0) -> np.ndarray:
        """Transform 2D airfoil coordinates onto a planar radial station for CW rotation.

        In the right-handed Cartesian coordinate system where +Z is the upstream thrust direction:
        - CW rotation moves a blade at +Y (X=0, Y=r) toward +X (V_rot = +Omega*r * i).
        - Leading Edge (LE, x_hat = -0.25) points toward (+X, +Z).
        - Trailing Edge (TE, x_hat = +0.75) points toward (-X, -Z).
        - Suction Surface (upper, y_hat > 0) faces +Z (upstream).
        - Pressure Surface (lower, y_hat < 0) faces -Z (downstream).
        """
        xs = chord_mm * coords_2d[:, 0]
        ys = chord_mm * coords_2d[:, 1]
        cp, sp = np.cos(pitch_angle_rad), np.sin(pitch_angle_rad)
        xi = radius_mm / self.params.radius_mm

        # Tangential coordinate s_tan (+X is direction of CW rotation)
        # Axial coordinate z_axial (+Z is upstream thrust direction)
        s_tan = -xs * cp - ys * sp + self.tangential_sweep_mm(xi)
        axial = -xs * sp + ys * cp

        # Smooth axial centering inside the embedded hub region to stay within planar hub faces
        transition = self._transition_end(self.params.root_xi)
        center_weight = 1.0 - _smoothstep((xi - self.params.root_xi) / max(transition - self.params.root_xi, 1e-9))
        axial = axial - center_weight * 0.5 * (float(np.min(axial)) + float(np.max(axial)))

        return np.column_stack((s_tan, np.full(len(s_tan), radius_mm), axial))

    def cylindrical_wrap_coordinates(self, coords_2d: np.ndarray, radius_mm: float,
                                     chord_mm: float, pitch_angle_rad: float) -> np.ndarray:
        """Cylindrical conformal transformation (Carlton, 2018).

        gamma = s_tan / r
        X = r * sin(gamma)
        Y = r * cos(gamma)
        Z = z_axial
        """
        xs = chord_mm * coords_2d[:, 0]
        ys = chord_mm * coords_2d[:, 1]
        cp, sp = np.cos(pitch_angle_rad), np.sin(pitch_angle_rad)
        xi = radius_mm / self.params.radius_mm

        s_tan = -xs * cp - ys * sp + self.tangential_sweep_mm(xi)
        axial = -xs * sp + ys * cp

        transition = self._transition_end(self.params.root_xi)
        center_weight = 1.0 - _smoothstep((xi - self.params.root_xi) / max(transition - self.params.root_xi, 1e-9))
        axial = axial - center_weight * 0.5 * (float(np.min(axial)) + float(np.max(axial)))

        gamma = s_tan / radius_mm
        X = radius_mm * np.sin(gamma)
        Y = radius_mm * np.cos(gamma)
        Z = axial
        return np.column_stack((X, Y, Z))

    def section_coordinates(self, xi: float, closed_loop: bool = False) -> np.ndarray:
        radius = xi * self.params.radius_mm
        chord = self.chord_distribution(xi, self.params.diameter_mm, self.params.root_xi)
        pitch = self.pitch_angle_rad(self.params.pitch_mm, radius, xi)
        coords_2d = self.generate_airfoil_coordinates(xi, self.params.n_airfoil_points, closed_loop=closed_loop)
        return self.cylindrical_conformal_transform(coords_2d, radius, chord, pitch, self.params.hand_sign)

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
            "pitch_angle_deg": np.array([np.degrees(self.pitch_angle_rad(self.params.pitch_mm, r, x)) for r, x in zip(radius, xi)]),
            "thickness_ratio_pct": np.array([100 * self.naca_thickness_distribution(x, self.params.root_xi) for x in xi]),
        }

    def generate_preview_mesh_data(self) -> Dict[str, List[np.ndarray]]:
        """Analytical fallback preview with a real open mounting bore."""
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

    def verify_cw_orientation(self) -> bool:
        """Unit test assertion: X_LE > X_TE, Z_LE > Z_TE, Z_upper > Z_lower at every station."""
        n = self.params.n_airfoil_points
        for xi in self.radial_stations:
            coords = self.section_coordinates(xi, closed_loop=False)
            # Index 0 is TE, Index n-1 is LE
            le = coords[n - 1]
            te = coords[0]

            assert le[0] > te[0], (
                f"Station xi={xi:.3f}: X_LE ({le[0]:.3f}) must be > X_TE ({te[0]:.3f}) for CW rotation!"
            )
            assert le[2] > te[2], (
                f"Station xi={xi:.3f}: Z_LE ({le[2]:.3f}) must be > Z_TE ({te[2]:.3f}) for +Z thrust!"
            )

            # Airfoil 2D coordinates to locate quarter-chord
            coords_2d = self.generate_airfoil_coordinates(xi, n, closed_loop=False)
            qc_upper_idx = np.argmin(np.abs(coords_2d[:n, 0]))
            qc_lower_idx = (n - 1) + np.argmin(np.abs(coords_2d[n - 1:, 0]))
            z_upper = coords[qc_upper_idx, 2]
            z_lower = coords[qc_lower_idx, 2]

            assert z_upper > z_lower, (
                f"Station xi={xi:.3f}: Z_upper ({z_upper:.3f}) must be > Z_lower ({z_lower:.3f}) "
                "for positive upstream suction camber!"
            )
        return True

    @staticmethod
    def estimate_static_thrust_bemt(diameter_mm: float, pitch_mm: float, num_blades: int,
                                    rpm: float = 6000.0, rho: float = 1.225) -> Tuple[float, float]:
        """Integrate static thrust using Blade Element Momentum Theory (BEMT).

        Based on McCormick (1995) and Adkins & Liebeck (1994) with Prandtl tip-loss corrections
        and low-Reynolds cambered airfoil polars.
        Returns (thrust_Newtons, thrust_grams_force).
        """
        R = diameter_mm / 2000.0
        P = pitch_mm / 1000.0
        B = num_blades
        omega = 2.0 * np.pi * rpm / 60.0
        r_hub = max(0.006, 0.10 * R)

        n_elem = 60
        r_stations = np.linspace(r_hub, R * 0.995, n_elem)
        dr = r_stations[1] - r_stations[0]
        total_thrust = 0.0

        for r in r_stations:
            xi = r / R
            c = PropellerMathEngine.chord_distribution(xi, diameter_mm) / 1000.0
            beta = np.arctan2(P, 2.0 * np.pi * r)
            V_rot = omega * r
            sigma = B * c / (2.0 * np.pi * r)

            # Iterative solve for induced inflow angle phi_i
            phi = 0.05
            for _ in range(30):
                sin_p = np.sin(phi)
                cos_p = np.cos(phi)

                # Prandtl tip loss factor
                f = (B / 2.0) * (R - r) / max(r * sin_p, 1e-6)
                F = (2.0 / np.pi) * np.arccos(np.exp(-min(f, 20.0)))
                F = max(F, 0.01)

                alpha = beta - phi
                alpha_0 = np.radians(-3.8)  # NACA 4412 zero-lift angle
                cl = 2.0 * np.pi * 0.95 * (alpha - alpha_0)
                cl = np.clip(cl, -0.5, 1.35)
                cd = 0.012 + 0.045 * cl ** 2

                # Momentum balance: 4 * F * sin^2(phi) = sigma * (cl * cos(phi) - cd * sin(phi))
                rhs = max(0.0, sigma * (cl * cos_p - cd * sin_p))
                sin_p_new = np.sqrt(rhs / (4.0 * F + 1e-9))
                phi_new = np.arcsin(np.clip(sin_p_new, 0.001, 0.8))
                phi = 0.5 * phi + 0.5 * phi_new

            V_eff = V_rot / np.cos(phi)
            dT = B * 0.5 * rho * (V_eff ** 2) * c * (cl * np.cos(phi) - cd * np.sin(phi)) * dr
            total_thrust += dT

        thrust_n = max(0.0, float(total_thrust))
        thrust_gf = thrust_n / 9.80665 * 1000.0
        return thrust_n, thrust_gf


if __name__ == "__main__":
    print("Testing PropellerMathEngine CW orientation and BEMT static thrust...")
    test_params = PropellerParameters(254.0, 114.3, 2, "CW")
    engine = PropellerMathEngine(test_params)
    engine.verify_cw_orientation()
    t_n, t_gf = engine.estimate_static_thrust_bemt(254.0, 114.3, 2, 6000.0)
    print(f"CW Orientation Verified: PASS (X_LE > X_TE, Z_LE > Z_TE, Z_upper > Z_lower)")
    print(f"10x4.5 BEMT Static Thrust at 6000 RPM: {t_n:.3f} N ({t_gf:.1f} gf)")
