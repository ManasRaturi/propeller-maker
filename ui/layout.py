"""The native workstation's presentation layer; no geometry or export decisions."""

from tkinter import Canvas, StringVar

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from . import theme as t


class PropellerLayout:
    @staticmethod
    def _font(size=14, mono=False, bold=False):
        return ctk.CTkFont(family=t.MONO_FONT if mono else t.UI_FONT,
                          size=size, weight="bold" if bold else "normal")

    def _build_header(self):
        self.header_frame = ctk.CTkFrame(self, height=48, fg_color=t.BASE, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_propagate(False)
        self.header_frame.grid_columnconfigure(1, weight=1)
        mark = Canvas(self.header_frame, width=28, height=28, bg=t.BASE,
                      highlightthickness=0)
        mark.grid(row=0, column=0, padx=(24, 10), pady=10)
        mark.create_polygon(13, 14, 3, 8, 2, 3, 7, 2, 15, 12,
                            smooth=True, fill=t.ACCENT)
        mark.create_polygon(15, 14, 25, 20, 26, 25, 21, 26, 13, 16,
                            smooth=True, fill=t.ACCENT)
        mark.create_oval(10, 10, 18, 18, fill=t.BASE, outline=t.ACCENT, width=2)
        ctk.CTkLabel(self.header_frame, text="Propeller Maker", font=self._font(18, bold=True),
                     text_color=t.INK).grid(row=0, column=1, sticky="w")
        actions = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        actions.grid(row=0, column=2, padx=(16, 16), pady=7)
        self.preview_btn = ctk.CTkButton(
            actions, text="Update preview", width=138, height=34, corner_radius=6,
            border_width=1, border_color=t.BORDER, fg_color=t.BASE,
            hover_color=t.SECONDARY, text_color=t.INK, font=self._font(14),
            command=self.on_preview_clicked)
        self.preview_btn.pack(side="left", padx=(0, 8))
        self.generate_btn = ctk.CTkButton(
            actions, text="Export STEP…", width=140, height=34, corner_radius=6,
            fg_color=t.INK, hover_color=t.PRIMARY_HOVER, text_color=t.PANEL,
            font=self._font(14, bold=True), command=self.on_generate_step_clicked)
        self.generate_btn.pack(side="left")

    def _build_workspace(self):
        # 304 inspector + fluid white sheet + 8 outer inset = the window width.
        self.workspace_frame = ctk.CTkFrame(self, fg_color=t.BASE, corner_radius=0)
        self.workspace_frame.grid(row=1, column=0, sticky="nsew")
        self.workspace_frame.grid_columnconfigure(0, minsize=304, weight=0)
        self.workspace_frame.grid_columnconfigure(1, weight=1)
        self.workspace_frame.grid_rowconfigure(0, weight=1)
        self.sidebar_frame = ctk.CTkFrame(self.workspace_frame, width=304,
                                         fg_color=t.BASE, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(0, weight=1)
        self.scroll_sidebar = ctk.CTkScrollableFrame(
            self.sidebar_frame, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=t.DIVIDER, scrollbar_button_hover_color=t.BORDER)
        self.scroll_sidebar.grid(row=0, column=0, sticky="nsew", padx=(18, 10), pady=(12, 0))
        self._build_inspector(self.scroll_sidebar)
        footer = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        footer.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 16))
        ctk.CTkLabel(footer, text="STEP solid · .step / .stp", text_color=t.MUTED,
                     font=self._font(12), anchor="w").pack(fill="x")
        self.export_note = ctk.CTkLabel(
            footer, text="Ready for CAD, CFD and fabrication", text_color=t.MUTED,
            font=self._font(12), anchor="w", justify="left", wraplength=252)
        self.export_note.pack(fill="x")
        self._build_viewport()

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, anchor="w", height=24,
                     font=self._font(14, bold=True), text_color=t.INK).pack(
                         fill="x", pady=(24, 8))

    def _segment(self, parent, values, command, default, width=None):
        options = dict(values=values, height=36, corner_radius=6, border_width=2,
                       fg_color=t.SECONDARY, selected_color=t.PANEL,
                       selected_hover_color=t.SELECTED_HOVER, unselected_color=t.SECONDARY,
                       unselected_hover_color=t.CONTROL_HOVER, text_color=t.INK,
                       text_color_disabled=t.MUTED, font=self._font(14), command=command)
        if width is not None:
            options["width"] = width
        widget = ctk.CTkSegmentedButton(parent, **options)
        widget.set(default)
        self._inputs.append(widget)
        return widget

    def _dimension_field(self, parent, label, key):
        ctk.CTkLabel(parent, text=label, anchor="w", height=22,
                     text_color=t.INK, font=self._font(14)).pack(fill="x", pady=(16, 6))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1)
        variable = StringVar(value=self._display_text[key])
        variable.trace_add("write", self._schedule_metrics)
        entry = ctk.CTkEntry(
            row, textvariable=variable, height=40, corner_radius=6,
            border_width=1, border_color=t.BORDER, fg_color=t.FIELD,
            text_color=t.INK, font=self._font(16, mono=True))
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", lambda _event: self.on_preview_clicked())
        entry.bind("<FocusIn>", lambda _event: entry.configure(border_color=t.ACCENT))
        entry.bind("<FocusOut>", lambda _event: self._parse_parameters(show_errors=True))
        suffix = ctk.CTkLabel(row, text="mm", width=38, height=40,
                              font=self._font(14), text_color=t.MUTED)
        suffix.grid(row=0, column=1, padx=(4, 0))
        self._inputs.append(entry)
        return variable, entry, suffix

    def _metric_row(self, parent, key, text):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        row.pack(fill="x")
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=text, text_color=t.MUTED,
                     font=self._font(12)).pack(side="left")
        value = ctk.CTkLabel(row, text="—", text_color=t.INK,
                              font=self._font(12, mono=True))
        value.pack(side="right")
        self.metric_labels[key] = value

    def _build_inspector(self, parent):
        title = ctk.CTkFrame(parent, fg_color="transparent")
        title.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(title, text="Dimensions", font=self._font(22, bold=True),
                     text_color=t.INK).pack(side="left")
        self.unit_seg = self._segment(title, ["mm", "in"], self._on_unit_toggled, "mm", 88)
        self.unit_seg.pack(side="right")
        self.diameter_var, self.dia_entry, self.dia_suffix = self._dimension_field(
            parent, "Diameter", "diameter")
        self.pitch_var, self.pitch_entry, self.pitch_suffix = self._dimension_field(
            parent, "Pitch", "pitch")
        ctk.CTkLabel(parent, text="Blades", anchor="w", text_color=t.INK,
                     font=self._font(14)).pack(fill="x", pady=(16, 6))
        self.blades_seg = self._segment(parent, [str(i) for i in range(2, 9)],
                                        lambda _value: self._schedule_metrics(), "2")
        self.blades_seg.pack(fill="x")
        ctk.CTkLabel(parent, text="Clockwise rotation", anchor="w", text_color=t.MUTED,
                     font=self._font(12)).pack(fill="x", pady=(10, 0))
        self.input_note = ctk.CTkLabel(
            parent, text="10 × 4.5 in · 2 blades", anchor="w", justify="left",
            wraplength=252, font=self._font(12), text_color=t.MUTED)
        self.input_note.pack(fill="x", pady=(4, 0))
        self._section(parent, "Hub dimensions")
        self.metric_labels = {}
        self.metrics_card = ctk.CTkFrame(parent, fg_color="transparent")
        self.metrics_card.pack(fill="x")
        for key, label in [("hub", "Outer diameter"), ("bore", "Shaft bore"),
                           ("height", "Thickness")]:
            self._metric_row(self.metrics_card, key, label)
        ctk.CTkFrame(parent, height=1, fg_color=t.DIVIDER).pack(fill="x", pady=(20, 12))
        self._details_open = False
        self.details_button = ctk.CTkButton(
            parent, text="Engineering details  +", height=34, anchor="w",
            corner_radius=6, fg_color="transparent", hover_color=t.SECONDARY,
            text_color=t.MUTED, font=self._font(12), command=self._toggle_details)
        self.details_button.pack(fill="x")
        self.details_frame = ctk.CTkFrame(parent, fg_color="transparent")
        for key, label in [("ratio", "Pitch / diameter"), ("root", "Root pitch"),
                           ("tip", "Tip pitch"), ("area", "Swept area")]:
            self._metric_row(self.details_frame, key, label)
        self._metric_row(self.details_frame, "thrust", "Thrust at 6,000 RPM")
        ctk.CTkLabel(self.details_frame, text="Estimated static thrust · BEMT", anchor="w",
                     font=self._font(12), text_color=t.MUTED).pack(fill="x", pady=(0, 8))
        self.telemetry_lbl = ctk.CTkLabel(
            self.details_frame, text="Solid validation pending", text_color=t.MUTED,
            font=self._font(12), anchor="w", justify="left", wraplength=250)
        self.telemetry_lbl.pack(fill="x", pady=(8, 0))

    def _toggle_details(self):
        self._details_open = not self._details_open
        if self._details_open:
            self.details_frame.pack(fill="x", pady=(8, 12))
        else:
            self.details_frame.pack_forget()
        self.details_button.configure(
            text="Engineering details  −" if self._details_open else "Engineering details  +")

    def _build_viewport(self):
        self._axes_visible = False
        self._profiles_open = False
        self.viewport_container = ctk.CTkFrame(
            self.workspace_frame, fg_color=t.PANEL, corner_radius=16,
            border_width=1, border_color=t.DIVIDER)
        self.viewport_container.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self.viewport_container.grid_columnconfigure(0, weight=1)
        self.viewport_container.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(self.viewport_container, fg_color="transparent", height=52)
        toolbar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(toolbar, text="3D preview", font=self._font(16, bold=True),
                     text_color=t.INK).grid(row=0, column=0, sticky="w")
        cameras = ctk.CTkFrame(toolbar, fg_color="transparent")
        cameras.grid(row=0, column=1, sticky="e")
        self._camera_presets = [("Isometric", 28, 45), ("Top", 90, -90),
                                ("Front", 0, -90), ("Side", 0, 0)]
        for name, elevation, azimuth in self._camera_presets:
            button = ctk.CTkButton(
                cameras, text=name, width=88 if name == "Isometric" else 48,
                height=32, corner_radius=6, fg_color=t.SECONDARY if name == "Isometric" else t.PANEL,
                hover_color=t.SECONDARY, text_color=t.INK, font=self._font(12),
                command=lambda e=elevation, a=azimuth: self._select_camera(e, a))
            button.pack(side="left", padx=(4, 0))
            self._camera_buttons.append(button)
        self.axes_button = ctk.CTkButton(
            cameras, text="Axes", width=52, height=32, corner_radius=6,
            border_width=1, border_color=t.BORDER, fg_color=t.PANEL,
            hover_color=t.SECONDARY, text_color=t.MUTED, font=self._font(12),
            command=self._toggle_axes)
        self.axes_button.pack(side="left", padx=(12, 0))
        self.viewport_3d_frame = ctk.CTkFrame(self.viewport_container, fg_color=t.PANEL,
                                             corner_radius=0)
        self.viewport_3d_frame.grid(row=1, column=0, sticky="nsew", padx=8)
        self.viewport_3d_frame.grid_columnconfigure(0, weight=1)
        self.viewport_3d_frame.grid_rowconfigure(0, weight=1)
        self.fig_3d = Figure(figsize=(8, 6), dpi=100, facecolor=t.PANEL)
        self.ax_3d = self.fig_3d.add_subplot(111, projection="3d", facecolor=t.PANEL)
        self.fig_3d.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self._style_3d_axes()
        self.ax_3d.text2D(.5, .5, "Building your propeller…", ha="center",
                           transform=self.ax_3d.transAxes, color=t.MUTED,
                           fontsize=12, family=t.UI_FONT)
        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self.viewport_3d_frame)
        self.canvas_3d.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.canvas_3d.mpl_connect("button_release_event", self._remember_camera)
        self.canvas_3d.mpl_connect("button_release_event", self._sync_camera_buttons)
        caption_row = ctk.CTkFrame(self.viewport_container, fg_color="transparent")
        caption_row.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        caption_row.grid_columnconfigure(0, weight=1)
        self.viewport_caption = ctk.CTkLabel(
            caption_row, text="Preparing preview…", font=self._font(12),
            text_color=t.MUTED, anchor="w")
        self.viewport_caption.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(caption_row, text="Drag to orbit · Right-drag to zoom", font=self._font(12),
                     text_color=t.MUTED).grid(row=0, column=1, padx=(16, 0), sticky="e")
        self.profiles_button = ctk.CTkButton(
            self.viewport_container, text="Blade profiles  +", anchor="w", height=40,
            corner_radius=6, fg_color=t.PANEL, hover_color=t.BASE,
            text_color=t.MUTED, font=self._font(12), command=self._toggle_profiles)
        self.profiles_button.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.viewport_2d_frame = ctk.CTkFrame(self.viewport_container, height=216,
                                             fg_color=t.PANEL, corner_radius=0)
        self.viewport_2d_frame.grid_propagate(False)
        self.viewport_2d_frame.grid_rowconfigure(0, weight=1)
        self.viewport_2d_frame.grid_columnconfigure(0, weight=1)
        self.fig_2d = Figure(figsize=(8, 2.2), dpi=100, facecolor=t.PANEL)
        self.ax_chord = self.fig_2d.add_subplot(121, facecolor=t.PANEL)
        self.ax_twist = self.fig_2d.add_subplot(122, facecolor=t.PANEL)
        self.fig_2d.subplots_adjust(left=.08, right=.97, bottom=.27, top=.79, wspace=.35)
        self.canvas_2d = FigureCanvasTkAgg(self.fig_2d, master=self.viewport_2d_frame)
        self.canvas_2d.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._draw_distributions(self._parse_parameters())

    def _toggle_profiles(self):
        self._profiles_open = not self._profiles_open
        if self._profiles_open:
            self.viewport_2d_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))
            self.canvas_2d.draw_idle()
        else:
            self.viewport_2d_frame.grid_remove()
        self.profiles_button.configure(
            text="Blade profiles  −" if self._profiles_open else "Blade profiles  +")

    def _select_camera(self, elev, azim):
        self.set_camera_view(elev, azim)
        self._sync_camera_buttons()

    def _sync_camera_buttons(self, _event=None):
        for button, (_, elev, azim) in zip(self._camera_buttons, self._camera_presets):
            selected = abs(self.cam_elev - elev) < .1 and abs(self.cam_azim - azim) < .1
            button.configure(fg_color=t.SECONDARY if selected else t.PANEL)

    def _toggle_axes(self):
        self._axes_visible = not self._axes_visible
        self._style_3d_axes()
        for line in self.ax_3d.lines:
            line.set_visible(self._axes_visible)
        self.axes_button.configure(fg_color=t.SECONDARY if self._axes_visible else t.PANEL,
                                   text_color=t.INK if self._axes_visible else t.MUTED)
        self.canvas_3d.draw_idle()

    def _style_3d_axes(self):
        ax = self.ax_3d
        ax.set_facecolor(t.PANEL)
        ax.set_proj_type("ortho")
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.fill = False
            axis.pane.set_edgecolor(t.PANEL)
            axis.line.set_color(t.DIVIDER)
            axis._axinfo["grid"].update(color=t.DIVIDER, linewidth=.5, linestyle="-")
            axis.set_major_locator(MaxNLocator(4))
        for label, setter in [("X [mm]", ax.set_xlabel), ("Y [mm]", ax.set_ylabel),
                              ("Z [mm]", ax.set_zlabel)]:
            setter(label, color=t.MUTED, fontsize=9, family=t.UI_FONT, labelpad=6)
        ax.tick_params(colors=t.MUTED, labelsize=9, pad=1)
        if self._axes_visible:
            ax.set_axis_on()
        else:
            ax.set_axis_off()
        ax.view_init(elev=self.cam_elev, azim=self.cam_azim)

    def _build_status(self):
        self.status_bar = ctk.CTkFrame(self, height=32, fg_color=t.BASE, corner_radius=0)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        self.status_bar.grid_propagate(False)
        self.status_bar.grid_columnconfigure(0, weight=1)
        self.status_text = ctk.CTkLabel(
            self.status_bar, text="Preparing your propeller…", anchor="w",
            text_color=t.MUTED, font=self._font(12))
        self.status_text.grid(row=0, column=0, padx=24, sticky="ew")
        self.prog_bar = ctk.CTkProgressBar(
            self.status_bar, mode="indeterminate", width=100, height=3,
            corner_radius=2, fg_color=t.DIVIDER, progress_color=t.ACCENT)
        self.prog_bar.grid(row=0, column=1, padx=(12, 24))
        self.prog_bar.set(0)
