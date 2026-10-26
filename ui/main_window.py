"""Compact native CAD workstation using the same validated B-Rep as STEP export."""

from pathlib import Path
from queue import Empty, Queue
import math
import threading
import time
import traceback
from tkinter import filedialog, messagebox

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.colors import LightSource, to_rgb
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from core.math_engine import PropellerMathEngine, PropellerParameters
from core.cad_generator import CadGenerator

from .layout import PropellerLayout
from .theme import (
    BASE, PANEL, FIELD, BORDER, DIVIDER, INK, MUTED, NUMERIC, ACCENT,
    ACCENT_HOVER, SECONDARY, SECONDARY_BORDER, OK, WARNING, ERROR,
    UI_FONT, MONO_FONT, MODEL_COLOR, load_fonts, status_copy,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PropellerApp(PropellerLayout, ctk.CTk):
    """Native parameter inspector, exact solid viewport and serialized CAD worker."""

    def __init__(self):
        load_fonts()
        ctk.set_appearance_mode("light")
        super().__init__()
        self.title("Propeller Maker")
        screen_scale = self._get_window_scaling()
        initial_width = max(1150, min(1400, int(self.winfo_screenwidth() / screen_scale) - 48))
        initial_height = max(750, min(880, int(self.winfo_screenheight() / screen_scale) - 64))
        self.geometry(f"{initial_width}x{initial_height}")
        self.minsize(1150, 750)
        self.configure(fg_color=BASE)
        # 48 header + fluid work area + 32 status; 304 inspector + white sheet.
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.current_unit = "mm"
        self._dimensions_mm = {"diameter": 254.0, "pitch": 114.3}
        self._display_text = {"diameter": "254.0", "pitch": "114.3"}
        self._writing_fields = False
        self._metrics_after = None
        self._events = Queue()
        self._closing = False
        self._poll_after = None
        self.is_generating = False
        self.current_params = None
        self.current_model = None
        self.last_error = None
        self._cached_params = None
        self._cached_shape = None
        self._cached_mesh = None
        self._last_output_dir = PROJECT_ROOT
        self._job_started = None
        self.cam_elev, self.cam_azim = 28.0, 45.0
        self._inputs = []
        self._camera_buttons = []
        self._build_header()
        self._build_workspace()
        self._build_status()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_metrics()
        self._poll_after = self.after(80, self._poll_events)
        self.after(150, self.on_preview_clicked)


    def _draw_distributions(self, params):
        if params is None:
            return
        data = PropellerMathEngine(params).get_aerodynamic_summary()
        for ax, values, title, ylabel in [
            (self.ax_chord, data["chord_mm"], "Blade chord", "c [mm]"),
            (self.ax_twist, data["pitch_angle_deg"], "Blade twist", "φ [deg]")]:
            ax.clear()
            ax.set_facecolor(PANEL)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.spines["bottom"].set_color(DIVIDER)
            ax.grid(axis="y", color=DIVIDER, linewidth=.6)
            ax.tick_params(colors=MUTED, labelsize=9, length=0, pad=5)
            ax.yaxis.set_major_locator(MaxNLocator(4))
            ax.xaxis.set_major_locator(MaxNLocator(5))
            ax.plot(data["xi"], values, color=ACCENT, linewidth=1.6)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, max(values) * 1.12)
            ax.set_title(title, loc="left", color=INK, fontsize=11, family=UI_FONT, pad=9)
            ax.set_xlabel("Radius / blade radius", color=MUTED, fontsize=9, family=UI_FONT, labelpad=4)
            ax.set_ylabel(ylabel, color=MUTED, fontsize=9, family=UI_FONT, labelpad=4)
            for tick in ax.get_xticklabels() + ax.get_yticklabels():
                tick.set_fontfamily(UI_FONT)
        self.canvas_2d.draw_idle()


    def _set_status(self, text, color=MUTED):
        self.status_text.configure(text=status_copy(text), text_color=color)

    def _schedule_metrics(self, *_args):
        if self._writing_fields:
            return
        if self._metrics_after is not None:
            self.after_cancel(self._metrics_after)
        self._metrics_after = self.after(160, self._refresh_metrics)

    def _parse_parameters(self, show_errors=False):
        values = {}
        fields = [("diameter", self.diameter_var, self.dia_entry),
                  ("pitch", self.pitch_var, self.pitch_entry)]
        try:
            for key, variable, widget in fields:
                raw = variable.get().strip()
                number = float(raw)
                if not math.isfinite(number) or number <= 0:
                    raise ValueError(f"{key.capitalize()} must be finite and positive.")
                widget.configure(border_color=BORDER)
                # Display conversions never overwrite the canonical millimetre values.
                if raw != self._display_text[key]:
                    self._dimensions_mm[key] = number * (25.4 if self.current_unit == "in" else 1.0)
                    self._display_text[key] = raw
                values[key] = self._dimensions_mm[key]
            params = PropellerParameters(
                diameter_mm=values["diameter"], pitch_mm=values["pitch"],
                num_blades=int(self.blades_seg.get()),
                handedness="CW")
            return params
        except (ValueError, OverflowError) as exc:
            if show_errors:
                for _key, _variable, widget in fields:
                    widget.configure(border_color=ERROR)
                if not self.is_generating:
                    self._set_status("INPUT ERROR", ERROR)
                self.input_note.configure(text=str(exc)[:46], text_color=ERROR)
            return None

    @staticmethod
    def _signature(params):
        return (params.diameter_mm, params.pitch_mm, params.num_blades,
                params.handedness, params.n_stations, params.n_airfoil_points)

    def _refresh_metrics(self):
        self._metrics_after = None
        params = self._parse_parameters(show_errors=True)
        if params is None:
            for label in self.metric_labels.values():
                label.configure(text="—", text_color=MUTED)
            return
        ratio = params.pitch_to_diameter_ratio
        scale = 1 if self.current_unit == "mm" else 1 / 25.4
        suffix = self.current_unit
        thrust_n, thrust_gf = params.estimate_static_thrust(rpm=6000.0)
        entries = {
            "thrust": f"{thrust_n:.2f} N ({thrust_gf:.0f} gf)",
            "ratio": f"{ratio:.3f}",
            "hub": f"{params.hub_diameter_mm * scale:.3f} {suffix}",
            "bore": f"{params.bore_diameter_mm * scale:.3f} {suffix}",
            "height": f"{params.hub_length_mm * scale:.3f} {suffix}",
            "root": f"{params.root_pitch_deg:.2f}°",
            "tip": f"{params.tip_pitch_deg:.2f}°",
            "area": f"{params.disk_area_m2:.5f} m²"}
        for key, value in entries.items():
            self.metric_labels[key].configure(text=value, text_color=NUMERIC)
        unusual = ratio < .2 or ratio > 2.5
        self.metric_labels["ratio"].configure(text_color=WARNING if unusual else NUMERIC)
        self.input_note.configure(
            text="P/D outside typical 0.2–2.5 range" if unusual else
                 f"{params.diameter_mm / 25.4:.4g} × {params.pitch_mm / 25.4:.4g} in · {params.num_blades} blades",
            text_color=WARNING if unusual else MUTED)
        if not self.is_generating:
            if self._cached_params == self._signature(params):
                self._set_status("READY", OK)
            else:
                self._set_status("PARAMETERS CHANGED / UPDATE VIEWPORT", MUTED)
        self._draw_distributions(params)

    def _on_unit_toggled(self, new_unit):
        if new_unit == self.current_unit:
            return
        if self._parse_parameters(show_errors=True) is None:
            self.unit_seg.set(self.current_unit)
            return
        self.current_unit = new_unit
        self.unit_seg.set(new_unit)
        scale = 25.4 if new_unit == "in" else 1.0
        self._writing_fields = True
        for key, variable in [("diameter", self.diameter_var), ("pitch", self.pitch_var)]:
            text = format(self._dimensions_mm[key] / scale, ".12g")
            self._display_text[key] = text
            variable.set(text)
        self._writing_fields = False
        self.dia_suffix.configure(text=new_unit)
        self.pitch_suffix.configure(text=new_unit)
        self._refresh_metrics()

    def set_camera_view(self, elev, azim):
        self.cam_elev, self.cam_azim = elev, azim
        self.ax_3d.view_init(elev=elev, azim=azim)
        self.canvas_3d.draw_idle()

    def _remember_camera(self, _event):
        self.cam_elev, self.cam_azim = self.ax_3d.elev, self.ax_3d.azim

    def _set_busy(self, busy):
        self.is_generating = busy
        state = "disabled" if busy else "normal"
        for widget in self._inputs + [self.preview_btn, self.generate_btn]:
            widget.configure(state=state)
        if busy:
            self.prog_bar.start()
        else:
            self.prog_bar.stop()
            self.prog_bar.set(0)

    def on_preview_clicked(self):
        if self.is_generating or self._closing:
            return
        params = self._parse_parameters(show_errors=True)
        if params is None:
            return
        if self._signature(params) == self._cached_params:
            self._set_status("READY", OK)
            return
        self._start_job("preview", params)

    def on_generate_step_clicked(self):
        if self.is_generating or self._closing:
            return
        params = self._parse_parameters(show_errors=True)
        if params is None:
            return
        default = (f"propeller_{params.diameter_mm:g}x{params.pitch_mm:g}_"
                   f"{params.num_blades}B_{params.handedness}.step")
        destination = filedialog.asksaveasfilename(
            parent=self, title="Export validated STEP solid",
            initialdir=str(self._last_output_dir), initialfile=default,
            defaultextension=".step", filetypes=[("STEP solid", "*.step *.stp")])
        if not destination:
            return
        self._last_output_dir = Path(destination).resolve().parent
        self._start_job("export", params, destination)

    def _start_job(self, action, params, destination=None):
        self.last_error = None
        self._set_busy(True)
        self._job_started = time.perf_counter()
        self._set_status("LOFTING B-REP SOLID..." if self._cached_params != self._signature(params)
                         else "VALIDATING MANIFOLD TOPOLOGY...")
        self.telemetry_lbl.configure(text="CAD operation in progress")
        if self._cached_mesh is None:
            self.viewport_caption.configure(text="Building your propeller…")
        cached = self._cached_shape if self._cached_params == self._signature(params) else None
        cached_mesh = self._cached_mesh if cached is not None else None
        # No Tk calls are made by this worker, including after(). All CAD work is serialized.
        threading.Thread(target=self._cad_worker,
                         args=(action, params, destination, cached, cached_mesh),
                         daemon=True, name="propeller-cad-worker").start()

    def _cad_worker(self, action, params, destination, shape, mesh):
        try:
            generator = CadGenerator(params)
            progress = lambda _fraction, message: self._events.put(("progress", message))
            if shape is None:
                shape = generator.generate_propeller_solid(progress)
            topology = generator.validate_topology(shape.val())
            if mesh is None:
                self._events.put(("progress", "TESSELLATING VALIDATED SOLID..."))
                mesh = generator.preview_mesh(shape)
            result = None
            if action == "export":
                result = generator.generate_and_export_step(destination, progress, propeller=shape)
            self._events.put(("success", dict(action=action, params=params, shape=shape,
                                               mesh=mesh, topology=topology, result=result)))
        except Exception:
            self._events.put(("error", traceback.format_exc()))

    def _poll_events(self):
        try:
            while True:
                event, payload = self._events.get_nowait()
                if event == "progress":
                    if not self._closing:
                        self._set_status(payload)
                elif event == "success":
                    self._on_success(payload)
                elif event == "error":
                    self._on_error(payload)
        except Empty:
            pass
        if self._closing and not self.is_generating:
            self.destroy()
            return
        self._poll_after = self.after(80, self._poll_events)

    def _draw_solid(self, mesh, params):
        self.ax_3d.clear()
        self._style_3d_axes()
        vertices = np.asarray(mesh["vertices"])
        triangles = np.asarray(mesh["triangles"], dtype=int)
        faces = vertices[triangles]
        normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        normals /= np.maximum(lengths[:, None], 1e-15)
        light = LightSource(azdeg=315, altdeg=45).shade_normals(normals)
        shade = .45 + .55 * light
        colors = np.clip(np.asarray(to_rgb(MODEL_COLOR))[None, :] * shade[:, None], 0, 1)
        surface = Poly3DCollection(faces, facecolors=colors, edgecolors="none",
                                   linewidths=0, antialiased=False, rasterized=True)
        self.ax_3d.add_collection3d(surface)
        radius = params.radius_mm
        xy_limit = radius * 1.06
        z_extent = max(abs(vertices[:, 2]).max() * 1.25, radius * .19)
        self.ax_3d.set_xlim(-xy_limit, xy_limit)
        self.ax_3d.set_ylim(-xy_limit, xy_limit)
        self.ax_3d.set_zlim(-z_extent, z_extent)
        # Aspect follows the physical axis spans: one mm has the same scale on X/Y/Z.
        self.ax_3d.set_box_aspect((2 * xy_limit, 2 * xy_limit, 2 * z_extent), zoom=1.35)
        angle = np.linspace(0, 2 * np.pi, 160)
        for fraction in (.25, .5, .75, 1):
            self.ax_3d.plot(radius * fraction * np.cos(angle), radius * fraction * np.sin(angle),
                            np.full_like(angle, -z_extent * .92), color=DIVIDER, linewidth=.55,
                            visible=self._axes_visible)
        self.ax_3d.view_init(elev=self.cam_elev, azim=self.cam_azim)
        self.current_params = params
        self.viewport_caption.configure(
            text=f"{params.diameter_mm:g} × {params.pitch_mm:g} mm · "
                 f"{params.num_blades} blades · Clockwise")
        self.canvas_3d.draw_idle()

    def _on_success(self, payload):
        self._cached_params = self._signature(payload["params"])
        self._cached_shape = payload["shape"]
        self.current_model = payload["shape"]
        self._cached_mesh = payload["mesh"]
        elapsed = time.perf_counter() - self._job_started
        self._set_busy(False)
        if self._closing:
            return
        self._draw_solid(payload["mesh"], payload["params"])
        self._draw_distributions(payload["params"])
        result = payload["result"]
        if result is None:
            self._set_status("READY", OK)
            self.telemetry_lbl.configure(text=f"1 solid | 1 closed shell | manifold | {elapsed:.1f} s")
        else:
            self._set_status("STEP EXPORTED", OK)
            self.telemetry_lbl.configure(
                text=f"{result['file_size_mb']:.2f} MB | 1 closed solid | readback valid | {elapsed:.1f} s")
            self.export_note.configure(text=Path(result["output_path"]).name, text_color=OK)

    def _on_error(self, details):
        self.last_error = details
        self._set_busy(False)
        if self._closing:
            return
        self._set_status("GEOMETRY / KERNEL ERROR", ERROR)
        self.telemetry_lbl.configure(text="Export not completed")
        log_path = PROJECT_ROOT / "propeller_error.log"
        try:
            log_path.write_text(details, encoding="utf-8")
        except OSError:
            pass
        error_line = next((line for line in reversed(details.splitlines()) if line.strip()), "CAD operation failed")
        messagebox.showerror("Geometry operation failed",
                             f"{error_line}\n\nDetails: {log_path}", parent=self)

    def _on_close(self):
        self._closing = True
        if self._metrics_after is not None:
            self.after_cancel(self._metrics_after)
            self._metrics_after = None
        if self.is_generating:
            # Finish any in-flight atomic export without touching a destroyed Tk interpreter.
            self.withdraw()
        else:
            if self._poll_after is not None:
                self.after_cancel(self._poll_after)
            self.destroy()


def launch():
    app = PropellerApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
