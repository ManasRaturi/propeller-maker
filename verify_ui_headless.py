r"""Exercise UI controller contracts without creating a Tk window or a display.

Run with the project's local Python: venv\Scripts\python.exe verify_ui_headless.py.
Widgets, dialogs and the worker thread are replaced with in-memory doubles. CAD
geometry is covered independently by verify_geometry.py.
"""

from pathlib import Path
from queue import Queue
import time
import unittest
from unittest.mock import Mock, patch

from ui import main_window
from ui.main_window import PropellerApp


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Widget(Value):
    def __init__(self, value=""):
        super().__init__(value)
        self.options = {}
        self.running = False

    def configure(self, **options):
        self.options.update(options)

    def cget(self, key):
        return self.options.get(key)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def controller():
    """Allocate the real class, bypassing CTk.__init__ completely."""
    app = object.__new__(PropellerApp)
    app.current_unit = "mm"
    app._dimensions_mm = {"diameter": 254.0, "pitch": 114.3}
    app._display_text = {"diameter": "254.0", "pitch": "114.3"}
    app._writing_fields = False
    app.diameter_var = Value("254.0")
    app.pitch_var = Value("114.3")
    app.blades_seg = Widget("2")
    app.unit_seg = Widget("mm")
    app.dia_entry = Widget()
    app.pitch_entry = Widget()
    app.dia_suffix = Widget()
    app.pitch_suffix = Widget()
    app.input_note = Widget()
    app.status_text = Widget()
    app.telemetry_lbl = Widget()
    app.viewport_caption = Widget()
    app.export_note = Widget()
    app.prog_bar = Widget()
    app.preview_btn = Widget()
    app.generate_btn = Widget()
    app.metric_labels = {key: Widget() for key in
                         ("thrust", "ratio", "hub", "bore", "height", "root", "tip", "area")}
    app._inputs = [app.dia_entry, app.pitch_entry, app.blades_seg, app.unit_seg]
    app._metrics_after = None
    app._poll_after = None
    app._events = Queue()
    app._closing = False
    app.is_generating = False
    app.current_model = None
    app.current_params = None
    app.last_error = None
    app._cached_params = None
    app._cached_shape = None
    app._cached_mesh = None
    app._last_output_dir = main_window.PROJECT_ROOT
    app._job_started = time.perf_counter()
    app.after = Mock(return_value="scheduled")
    app.after_cancel = Mock()
    app._draw_distributions = Mock()
    app._draw_solid = Mock()
    app.withdraw = Mock()
    app.destroy = Mock()
    return app


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.app = controller()

    def test_benchmark_defaults_and_internal_resolution(self):
        params = self.app._parse_parameters()
        self.assertEqual(PropellerApp._signature(params),
                         (254.0, 114.3, 2, "CW", 22, 60))

    def test_invalid_dimensions_and_blade_counts_are_rejected(self):
        for value in ("nan", "inf", "-inf", "-1", "0", "", "text", "12"):
            with self.subTest(diameter=value):
                app = controller()
                app.diameter_var.set(value)
                self.assertIsNone(app._parse_parameters(show_errors=True))
                self.assertTrue(app.input_note.cget("text"))
        for value in ("1", "9", "two"):
            with self.subTest(blades=value):
                app = controller()
                app.blades_seg.set(value)
                self.assertIsNone(app._parse_parameters())

    def test_unit_switches_preserve_canonical_dimensions(self):
        for _ in range(30):
            self.app._on_unit_toggled("in")
            self.assertEqual(self.app.diameter_var.get(), "10")
            self.assertEqual(self.app.pitch_var.get(), "4.5")
            self.app._on_unit_toggled("mm")
        params = self.app._parse_parameters()
        self.assertEqual((params.diameter_mm, params.pitch_mm), (254.0, 114.3))
        self.app._on_unit_toggled("in")
        self.app.diameter_var.set("9")
        self.app.pitch_var.set("4.7")
        self.app._on_unit_toggled("mm")
        params = self.app._parse_parameters()
        self.assertAlmostEqual(params.diameter_mm, 228.6)
        self.assertAlmostEqual(params.pitch_mm, 119.38)

    def test_invalid_input_does_not_change_units(self):
        self.app.pitch_var.set("nan")
        self.app._on_unit_toggled("in")
        self.assertEqual(self.app.current_unit, "mm")
        self.assertEqual(self.app.unit_seg.get(), "mm")

    def test_user_dimensions_and_all_detail_metrics_refresh(self):
        self.app._refresh_metrics()
        labels = self.app.metric_labels
        self.assertEqual(labels["hub"].cget("text"), "25.400 mm")
        self.assertEqual(labels["bore"].cget("text"), "11.430 mm")
        self.assertEqual(labels["ratio"].cget("text"), "0.450")
        self.assertTrue(all(label.cget("text") not in (None, "—")
                            for label in labels.values()))
        self.app._on_unit_toggled("in")
        self.assertEqual(labels["hub"].cget("text"), "1.000 in")
        self.assertEqual(labels["bore"].cget("text"), "0.450 in")
        self.app.diameter_var.set("nan")
        self.app._refresh_metrics()
        self.assertTrue(all(label.cget("text") == "—" for label in labels.values()))

    def test_busy_state_locks_inputs_and_actions(self):
        self.app._set_busy(True)
        self.assertTrue(self.app.is_generating)
        self.assertTrue(self.app.prog_bar.running)
        for widget in self.app._inputs + [self.app.preview_btn, self.app.generate_btn]:
            self.assertEqual(widget.cget("state"), "disabled")
        self.app._set_busy(False)
        self.assertFalse(self.app.prog_bar.running)
        for widget in self.app._inputs + [self.app.preview_btn, self.app.generate_btn]:
            self.assertEqual(widget.cget("state"), "normal")

    def test_preview_uses_cache_and_serializes_work(self):
        self.app._start_job = Mock()
        params = self.app._parse_parameters()
        self.app._cached_params = self.app._signature(params)
        self.app.on_preview_clicked()
        self.app._start_job.assert_not_called()
        self.app.diameter_var.set("260")
        self.app.on_preview_clicked()
        self.app._start_job.assert_called_once()
        self.assertEqual(self.app._start_job.call_args.args[0], "preview")
        self.app._start_job.reset_mock()
        self.app.is_generating = True
        self.app.on_preview_clicked()
        self.app._start_job.assert_not_called()

    def test_export_dialog_uses_folder_and_cancellation_is_safe(self):
        self.app._start_job = Mock()
        with patch.object(main_window.filedialog, "asksaveasfilename", return_value="") as dialog:
            self.app.on_generate_step_clicked()
            self.app._start_job.assert_not_called()
            self.assertEqual(dialog.call_args.kwargs["initialdir"],
                             str(main_window.PROJECT_ROOT))
            self.assertEqual(dialog.call_args.kwargs["initialfile"],
                             "propeller_254x114.3_2B_CW.step")
        destination = str(main_window.PROJECT_ROOT / "work" / "headless-test.step")
        with patch.object(main_window.filedialog, "asksaveasfilename", return_value=destination):
            self.app.on_generate_step_clicked()
        args = self.app._start_job.call_args.args
        self.assertEqual((args[0], args[2]), ("export", destination))
        self.assertEqual(self.app._last_output_dir, Path(destination).resolve().parent)

    def test_worker_thread_receives_matching_cache_only(self):
        params = self.app._parse_parameters()
        self.app._cached_params = self.app._signature(params)
        self.app._cached_shape, self.app._cached_mesh = object(), object()
        with patch.object(main_window.threading, "Thread") as thread:
            self.app._start_job("export", params, "chosen.step")
            thread.return_value.start.assert_called_once_with()
            kwargs = thread.call_args.kwargs
            self.assertIs(kwargs["target"].__func__, PropellerApp._cad_worker)
            self.assertEqual(kwargs["args"],
                             ("export", params, "chosen.step",
                              self.app._cached_shape, self.app._cached_mesh))
            self.assertTrue(kwargs["daemon"])
        self.app._set_busy(False)
        self.app.diameter_var.set("260")
        changed = self.app._parse_parameters()
        with patch.object(main_window.threading, "Thread") as thread:
            self.app._start_job("preview", changed)
            self.assertEqual(thread.call_args.kwargs["args"][-2:], (None, None))

    def test_cached_export_worker_reuses_geometry_and_reports_result(self):
        params = self.app._parse_parameters()
        shape, mesh = Mock(), {"vertices": [], "triangles": []}
        with patch.object(main_window, "CadGenerator") as generator_type:
            generator = generator_type.return_value
            generator.validate_topology.return_value = {"is_watertight": True}
            generator.generate_and_export_step.return_value = {"is_valid": True}
            self.app._cad_worker("export", params, "chosen.step", shape, mesh)
            generator.generate_propeller_solid.assert_not_called()
            generator.preview_mesh.assert_not_called()
            self.assertEqual(generator.generate_and_export_step.call_args.args[0], "chosen.step")
            self.assertIs(generator.generate_and_export_step.call_args.kwargs["propeller"], shape)
        event, result = self.app._events.get_nowait()
        self.assertEqual(event, "success")
        self.assertIs(result["shape"], shape)
        self.assertIs(result["mesh"], mesh)
        self.assertTrue(result["result"]["is_valid"])

    def test_close_finishes_inflight_work_without_destroying_controller(self):
        self.app.is_generating = True
        self.app._on_close()
        self.assertTrue(self.app._closing)
        self.app.withdraw.assert_called_once_with()
        self.app.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
