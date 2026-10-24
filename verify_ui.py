"""Integration smoke test of the real Tk window, worker and STEP export action."""
import json
import time
import traceback
from pathlib import Path


def attach_smoke_test(app, report_path: Path, output_path: Path):
    from ui import main_window
    from core.cad_generator import CadGenerator
    state = {"passed": False, "checks": {}, "phase": "startup"}
    started = time.perf_counter()
    original_dialog = main_window.filedialog.asksaveasfilename
    original_error = main_window.messagebox.showerror
    errors = []
    main_window.messagebox.showerror = lambda *args, **kwargs: errors.append(str(args))

    def check(name, condition, **details):
        state["checks"][name] = {"passed": bool(condition), **details}
        if not condition:
            raise AssertionError(name)

    def finish(error=None):
        if error:
            state["error"] = error
        state["passed"] = not error and all(x["passed"] for x in state["checks"].values())
        state["elapsed_seconds"] = time.perf_counter()-started
        main_window.filedialog.asksaveasfilename = original_dialog
        main_window.messagebox.showerror = original_error
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(state, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(state, indent=2), flush=True)
        app._on_close()

    def callback_error(exc_type, exc, tb):
        errors.append("".join(traceback.format_exception(exc_type, exc, tb)))
    app.report_callback_exception = callback_error

    def poll():
        try:
            if errors or app.last_error:
                raise RuntimeError(app.last_error or errors[0])
            if time.perf_counter()-started > 180:
                raise TimeoutError("Native UI smoke test exceeded 180 seconds.")
            if app.is_generating or app.current_model is None:
                app.after(200, poll)
                return
            if state["phase"] == "startup":
                p = app._parse_parameters()
                check("benchmark_defaults", p.diameter_mm == 254 and p.pitch_mm == 114.3
                      and p.num_blades == 2 and p.handedness == "CCW")
                check("validated_actual_viewport", CadGenerator.validate_topology(app.current_model.val())["is_watertight"])
                for _ in range(20):
                    app._on_unit_toggled("in")
                    app._on_unit_toggled("mm")
                p = app._parse_parameters()
                check("unit_toggle_without_drift", p.diameter_mm == 254 and p.pitch_mm == 114.3)
                for bad in ("nan", "inf", "-1", ""):
                    app.diameter_var.set(bad)
                    check("reject_"+repr(bad), app._parse_parameters() is None)
                app.diameter_var.set("254")
                app._refresh_metrics()
                check("hub_and_bore_readouts", "25.400" in app.metric_labels["hub"].cget("text")
                      and "11.430" in app.metric_labels["bore"].cget("text"))
                for size in ("1400x880", "1150x750"):
                    app.geometry(size)
                    app.update_idletasks()
                    bottom = app.status_bar.winfo_rooty()+app.status_bar.winfo_height()
                    scale = app.sidebar_frame._get_widget_scaling()
                    check("layout_"+size, abs(app.sidebar_frame.winfo_width()-340*scale) <= 1
                          and abs(app.header_frame.winfo_height()-40*scale) <= 1
                          and abs(app.status_bar.winfo_height()-28*scale) <= 1
                          and bottom <= app.winfo_rooty()+app.winfo_height()+1,
                          sidebar_width=app.sidebar_frame.winfo_width())
                for elev, azim in ((90,-90),(0,-90),(0,0),(28,45)):
                    app.set_camera_view(elev,azim)
                app.canvas_3d.draw()
                aspect = app.ax_3d.get_box_aspect()
                spans = [abs(b-a) for a,b in (app.ax_3d.get_xlim(), app.ax_3d.get_ylim(), app.ax_3d.get_zlim())]
                ratios = [float(a/b) for a,b in zip(aspect,spans)]
                check("equal_physical_xyz_scale", max(ratios)-min(ratios) < 1e-10)
                state["phase"] = "export"
                main_window.filedialog.asksaveasfilename = lambda **kwargs: str(output_path)
                app.on_generate_step_clicked()
                app.after(200,poll)
                return
            check("ui_step_export_action", output_path.exists()
                  and app.status_text.cget("text") == "STEP EXPORTED",
                  output_path=str(output_path), bytes=output_path.stat().st_size)
            check("no_tk_or_worker_errors", not errors and app.last_error is None)
            state["phase"] = "complete"
            finish()
        except Exception:
            finish(traceback.format_exc())
    app.after(250,poll)
    return state
