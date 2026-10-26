"""Offscreen, code-sourced illustrations for the Propeller Maker study guide.

Only the existing mathematical engine is read. This module neither launches the
application nor alters the parameters or calculations used by the application.
"""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Rectangle
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.math_engine import PropellerMathEngine, PropellerParameters

TEAL = "#1B6C80"
INK = "#171C1D"
MUTED = "#5D6567"
RULE = "#DDE4E5"
PALE = "#DCEAED"


def _setup():
    for path in (PROJECT_ROOT / "ui" / "assets" / "fonts").glob("*.ttf"):
        font_manager.fontManager.addfont(str(path))
    plt.rcParams.update({
        "font.family": "IBM Plex Sans", "font.size": 11,
        "text.color": INK, "axes.labelcolor": MUTED,
        "axes.edgecolor": RULE, "xtick.color": MUTED,
        "ytick.color": MUTED, "mathtext.fontset": "dejavusans",
        "axes.titlesize": 12, "axes.titleweight": "semibold",
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "savefig.facecolor": "white",
    })


def _save(fig, path):
    fig.savefig(path, dpi=240, facecolor="white")
    plt.close(fig)
    return path


def _arrow(ax, start, end, color=INK, style="->", lw=1.3, **kwargs):
    arrow = FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=12,
                            linewidth=lw, color=color, **kwargs)
    ax.add_patch(arrow)
    return arrow


def _airfoil(engine, path):
    fig, ax = plt.subplots(figsize=(7, 2.9))
    outline = engine.generate_airfoil_coordinates(.22, 120, closed_loop=True)
    x, y = outline[:, 0] + .25, outline[:, 1]
    upper = outline[:120][::-1]
    lower = outline[119:238]
    upper_y = float(np.interp(.56, upper[:, 0] + .25, upper[:, 1]))
    lower_y = float(np.interp(.57, lower[:, 0] + .25, lower[:, 1]))
    ax.fill(x, y, facecolor=PALE, edgecolor=TEAL, linewidth=1.8, zorder=2)
    xc = np.linspace(0, 1, 250)
    yc = np.where(xc < .4, .04 / .4**2 * (.8 * xc - xc**2),
                  .04 / .6**2 * (.2 + .8 * xc - xc**2))
    ax.plot(xc, yc, color=TEAL, linestyle="--", lw=1.3, zorder=3)
    ax.plot([0, 1], [0, 0], color=MUTED, lw=.9)
    ax.plot([.25, .25], [-.075, .115], color=MUTED, lw=.8, linestyle=":")
    ax.plot(.25, 0, "o", color=INK, markersize=4, zorder=5)
    ax.annotate("Leading edge", (0, 0), (.0, .145), ha="left", fontsize=10,
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=.8))
    ax.annotate("Upper / suction surface", (.56, upper_y), (.47, .145), ha="center", fontsize=10,
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=.8))
    ax.annotate("Trailing edge", (1, 0), (1, .145), ha="right", fontsize=10,
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=.8))
    ax.annotate("Quarter-chord pivot", (.25, 0), (.18, -.105), ha="center", fontsize=10,
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=.8))
    ax.annotate("Lower / pressure surface", (.57, lower_y), (.66, -.105), ha="center", fontsize=10,
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=.8))
    ax.set(xlim=(-.03, 1.03), ylim=(-.14, .18),
           xlabel=r"Chord coordinate $x_c = x/c$", ylabel=r"$y/c$")
    ax.set_aspect("equal", adjustable="box")
    ax.set_yticks([-.1, 0, .1])
    ax.tick_params(labelsize=9)
    ax.text(.5, 1.08, "Dashed line: mean camber. Horizontal line: chord.",
            transform=ax.transAxes, ha="center", color=MUTED, fontsize=10)
    fig.subplots_adjust(left=.08, right=.98, bottom=.23, top=.83)
    return _save(fig, path)


def _helix(params, path):
    fig = plt.figure(figsize=(7, 2.9))
    ax = fig.add_axes([.05, .20, .61, .65])
    radius = .5 * params.radius_mm
    circumference = 2 * np.pi * radius
    pitch = params.pitch_mm
    beta = np.degrees(np.arctan2(pitch, circumference))
    ax.plot([0, circumference], [0, 0], color=INK, lw=1.5)
    ax.plot([circumference, circumference], [0, pitch], color=TEAL, lw=2)
    ax.plot([0, circumference], [0, pitch], color=TEAL, lw=2)
    ax.add_patch(Arc((0, 0), 170, 170, theta1=0, theta2=beta, color=INK, lw=1))
    ax.text(98, 11, rf"$\beta = {beta:.1f}^\circ$", fontsize=12)
    ax.text(circumference / 2, -28, rf"$2\pi r = {circumference:.1f}$ mm", ha="center")
    ax.text(circumference + 13, pitch / 2, rf"$P$ = {pitch:g} mm", va="center", fontsize=10)
    ax.text(85, pitch * .72, "Unroll one revolution\ninto a right triangle.", fontsize=10, color=MUTED)
    ax.set_xlim(-15, circumference + 80)
    ax.set_ylim(-45, pitch + 25)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.text(.70, .82, "One pitch, many angles", fontsize=11, weight="semibold")
    rows = [("Hub edge", .1), ("Half radius", .5), ("Tip", 1.0)]
    for i, (label, xi) in enumerate(rows):
        angle = np.degrees(PropellerMathEngine.pitch_angle_rad(params.pitch_mm, xi * params.radius_mm, xi))
        fig.text(.70, .66 - i * .18, label, fontsize=10, color=MUTED)
        fig.text(.96, .66 - i * .18, f"{angle:.1f}°", ha="right", fontsize=11)
    return _save(fig, path)


def _coordinates(path):
    fig, (ax, side) = plt.subplots(1, 2, figsize=(7, 2.9))
    for a in (ax, side):
        a.set_aspect("equal")
        a.set_xlim(-1.5, 1.5)
        a.set_ylim(-1.45, 1.45)
        a.axis("off")
    ax.set_title("View from +Z toward -Z", pad=10)
    ax.add_patch(Circle((0, 0), .98, fill=False, edgecolor=RULE, lw=1.2))
    ax.add_patch(Circle((0, 0), .13, facecolor=PALE, edgecolor=TEAL, lw=1.2))
    _arrow(ax, (-1.23, 0), (1.25, 0), color=MUTED, lw=.8)
    _arrow(ax, (0, -1.2), (0, 1.25), color=MUTED, lw=.8)
    ax.text(1.32, -.08, "+X", fontsize=11)
    ax.text(-.09, 1.33, "+Y", fontsize=11)
    ax.plot([0, 0], [.15, .96], color=TEAL, lw=7, solid_capstyle="round")
    _arrow(ax, (.02, 1.02), (.73, 1.02), color=TEAL, lw=2)
    ax.text(.77, 1.0, "Motion", fontsize=10, va="center", color=TEAL)
    _arrow(ax, (.74, .66), (.93, -.33), color=TEAL, lw=1.5,
           connectionstyle="arc3,rad=-.35")
    ax.text(.82, -.72, "CW", color=TEAL, fontsize=12, ha="center")
    ax.text(-1.35, -1.3, "At +Y, the blade moves toward +X.", fontsize=9.5, color=MUTED)
    side.set_title("Side view along the shaft", pad=10)
    side.add_patch(Rectangle((-.55, -.11), 1.1, .22, facecolor=PALE, edgecolor=TEAL, lw=1.3))
    side.plot([0, 0], [-.33, .33], color=INK, lw=2)
    _arrow(side, (0, .24), (0, 1.1), color=TEAL, lw=2.3)
    side.text(.16, .86, "+Z thrust\non propeller", fontsize=10, color=TEAL, va="center")
    for x in (-.72, 0, .72):
        _arrow(side, (x, -.37), (x, -1.07), color=MUTED, lw=1.2)
    side.text(0, -1.32, "Air is accelerated toward -Z.", fontsize=9.5, ha="center", color=MUTED)
    fig.subplots_adjust(left=.04, right=.96, bottom=.07, top=.84, wspace=.35)
    return _save(fig, path)


def _distributions(engine, params, path):
    data = engine.get_aerodynamic_summary()
    fig, axs = plt.subplots(1, 2, figsize=(7, 2.9))
    for ax, values, title, unit in zip(axs,
            (data["chord_mm"], data["pitch_angle_deg"]),
            ("Blade width", "Geometric twist"), ("Chord / mm", "Pitch angle / deg")):
        ax.plot(data["xi"], values, color=TEAL, lw=2)
        ax.axvline(.1, color=MUTED, lw=.8, linestyle=":")
        ax.axvline(.22, color=MUTED, lw=.8, linestyle=":")
        ax.set(xlim=(0, 1.02), ylim=(0, max(values) * 1.12),
               xlabel=r"Radius fraction $\xi = r/R$", ylabel=unit)
        ax.set_title(title, loc="left", pad=11)
        ax.grid(axis="y", color=RULE, lw=.7)
        ax.set_xticks([0, .25, .5, .75, 1])
        ax.tick_params(labelsize=9, length=0)
        ax.spines["left"].set_visible(False)
    axs[0].plot(.5, .155 * params.diameter_mm, "o", color=TEAL, markersize=4)
    axs[0].annotate("Peak chord", (.5, .155 * params.diameter_mm), (.61, 41.5),
                    fontsize=9, color=MUTED,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=.8))
    fig.text(.5, .02, "Dotted guides: hub edge at 0.10R and transition end at 0.22R.",
             ha="center", fontsize=9.5, color=MUTED)
    fig.subplots_adjust(left=.09, right=.98, bottom=.25, top=.84, wspace=.38)
    return _save(fig, path)


def _stations(engine, path):
    fig = plt.figure(figsize=(7, 3.2))
    ax = fig.add_subplot(121, projection="3d")
    slices = [.1, .22, .4, .6, .8, .96]
    for xi in slices:
        xyz = engine.section_coordinates(xi, closed_loop=True)
        ax.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color=TEAL, lw=1.1)
    ax.set_box_aspect((55, 120, 25))
    ax.view_init(elev=22, azim=-55)
    # An orientation triad reads clearly at print size; small 3D ticks do not.
    origin = np.array([-27.0, 5.0, -8.0])
    for offset, label in (([18, 0, 0], "X"), ([0, 30, 0], "Y"), ([0, 0, 9], "Z")):
        end = origin + offset
        ax.plot([origin[0], end[0]], [origin[1], end[1]], [origin[2], end[2]],
                color=MUTED, lw=1)
        ax.text(*end, label, fontsize=10, color=MUTED)
    ax.set_axis_off()
    ax.set_title("A stack of planar sections", loc="left", fontsize=11, pad=6)
    side = fig.add_subplot(122)
    for xi, color, style in zip((.22, .5, .8), (MUTED, TEAL, INK), ("--", "-", ":")):
        xyz = engine.section_coordinates(xi, closed_loop=True)
        side.plot(xyz[:, 0], xyz[:, 2], color=color, linestyle=style,
                  lw=1.4, label=rf"$r/R = {xi:.2f}$")
    side.set(xlabel="Tangential X / mm", ylabel="Axial Z / mm")
    side.set_aspect("equal", adjustable="datalim")
    side.grid(color=RULE, lw=.6)
    side.legend(loc="upper right", fontsize=9, frameon=False)
    side.tick_params(labelsize=8)
    side.set_title("Slices viewed in the X-Z plane", loc="left", fontsize=11, pad=6)
    fig.text(.22, .04, "X tangential · Y radial · Z axial", fontsize=9.5,
             color=MUTED, ha="center")
    fig.subplots_adjust(left=.03, right=.98, bottom=.20, top=.83, wspace=.35)
    return _save(fig, path)


def _hub(params, path):
    fig, ax = plt.subplots(figsize=(7, 2.9))
    radius = params.hub_radius_mm
    bore = params.bore_radius_mm
    half = params.hub_length_mm / 2
    for x, width in ((-radius, radius - bore), (bore, radius - bore)):
        ax.add_patch(Rectangle((x, -half), width, 2 * half,
                               facecolor=PALE, edgecolor=TEAL, lw=1.5))
    ax.plot([0, 0], [-half - 4, half + 5], color=MUTED, lw=.8, linestyle="-.")
    ax.text(0, .5, "Open\nbore", ha="center", va="center", fontsize=11, color=MUTED)
    ax.plot([-radius, -radius], [half + .7, half + 5], color=RULE, lw=.8)
    ax.plot([radius, radius], [half + .7, half + 5], color=RULE, lw=.8)
    _arrow(ax, (-radius, half + 3), (radius, half + 3), style="<->", color=INK)
    ax.text(0, half + 3.6, rf"Hub diameter $d_h$ = {2 * radius:.3f} mm", ha="center", va="bottom")
    _arrow(ax, (-bore, -half - 3), (bore, -half - 3), style="<->", color=INK)
    ax.text(0, -half - 3.8, rf"Bore $d_b$ = {2 * bore:.3f} mm", ha="center", va="top")
    _arrow(ax, (radius + 4, -half), (radius + 4, half), style="<->", color=INK)
    ax.text(radius + 5, 0, rf"$H$ = {2 * half:.3f} mm", va="center", fontsize=11)
    ax.text(-radius - 4, 0, "+Z", ha="right", color=TEAL, fontsize=11)
    _arrow(ax, (-radius - 3, -1.6), (-radius - 3, 1.6), color=TEAL)
    ax.set_xlim(-radius - 10, radius + 19)
    ax.set_ylim(-half - 7, half + 8)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.subplots_adjust(left=.02, right=.98, bottom=.02, top=.98)
    return _save(fig, path)


def make_figures(outdir: Path) -> dict:
    """Generate educational PNGs from the live benchmark engine, without a GUI."""
    _setup()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    params = PropellerParameters(254, 114.3, 2)
    engine = PropellerMathEngine(params)
    makers = {
        "airfoil": lambda p: _airfoil(engine, p),
        "helix": lambda p: _helix(params, p),
        "coordinates": _coordinates,
        "distributions": lambda p: _distributions(engine, params, p),
        "stations": lambda p: _stations(engine, p),
        "hub": lambda p: _hub(params, p),
    }
    return {key: fn(outdir / f"study_{key}.png") for key, fn in makers.items()}


if __name__ == "__main__":
    for name, path in make_figures(PROJECT_ROOT / "work" / "manual_figures").items():
        print(f"{name}: {path}")
