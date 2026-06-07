import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import subprocess
import threading
import queue
import time
import os
import sys

# Color Palette (Modern Premium Dark Mode)
BG_COLOR = "#0b0e14"       # Deep dark space blue
PANEL_COLOR = "#121820"    # Darker blue-gray for sidebars
TEXT_COLOR = "#c9d1d9"     # Light gray for standard text
TEXT_WHITE = "#ffffff"     # Pure white for main statistics/headers
ACCENT_BLUE = "#58a6ff"    # Cool blue for Sequential mode
ACCENT_GREEN = "#3fb950"   # Emerald green for status/running
ACCENT_RED = "#f85149"     # Warning red for stops/ants
BORDER_COLOR = "#21262d"   # Clean boundary lines

class LangtonAntGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Langton's Ant Simulator - 2D Visualization")
        self.root.geometry("1100x750")
        self.root.configure(bg=BG_COLOR)
        
        # Simulation process variables
        self.process = None
        self.msg_queue = queue.Queue()
        self.is_running = False
        self.is_paused = False
        
        # State tracking
        self.grid_size = 100
        self.steps_limit = 10000
        self.ants_count = 1
        
        self.current_step = 0
        self.black_cells_count = 0
        self.white_cells_count = 0
        self.migrations_count = 0
        self.start_time = 0.0
        self.elapsed_time = 0.0
        
        self.zoom_level = 1.0
        self.show_grid = True
        self.center_view = True
        self.speed_factor = "Max"  # Options: 1x, 2x, 5x, 10x, Max
        self.step_mode = False
        
        # Track canvas cells and ant shapes
        self.black_cells = {}      # (x,y) -> canvas rectangle ID
        self.ant_shapes = {}       # ant_id -> canvas polygon ID
        self.ant_positions = {}    # ant_id -> (x, y, dir)
        
        # Build layout
        self.setup_ui()
        
        # Start queue poller
        self.poll_queue()
        
        # Setup clean exit on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        # Top Header Bar
        self.header_frame = tk.Frame(self.root, bg=BG_COLOR, height=50, bd=0)
        self.header_frame.pack(fill=tk.X, side=tk.TOP, padx=15, pady=5)
        
        self.mode_label = tk.Label(self.header_frame, text="Mode: Sequential", font=("Segoe UI", 12, "bold"), fg=ACCENT_BLUE, bg=BG_COLOR)
        self.mode_label.pack(side=tk.LEFT, pady=10)
        
        self.step_progress_label = tk.Label(self.header_frame, text="Step: 0 / 10000", font=("Segoe UI", 12, "bold"), fg=TEXT_WHITE, bg=BG_COLOR)
        self.step_progress_label.pack(side=tk.LEFT, expand=True)
        
        self.status_label = tk.Label(self.header_frame, text="Simulation Stopped", font=("Segoe UI", 12, "bold"), fg=ACCENT_RED, bg=BG_COLOR)
        self.status_label.pack(side=tk.RIGHT, pady=10)
        
        # Separator Line
        sep = tk.Frame(self.root, height=1, bg=BORDER_COLOR)
        sep.pack(fill=tk.X, side=tk.TOP)
        
        # Main container for Sidebar and Canvas Area
        self.main_container = tk.Frame(self.root, bg=BG_COLOR)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left Sidebar (Controls and Statistics)
        self.sidebar = tk.Frame(self.main_container, width=280, bg=PANEL_COLOR, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.sidebar.pack(fill=tk.Y, side=tk.LEFT, padx=10, pady=10)
        self.sidebar.pack_propagate(False)
        
        self.setup_sidebar_controls()
        
        # Canvas Workspace Frame (Dark background)
        self.workspace = tk.Frame(self.main_container, bg=BG_COLOR)
        self.workspace.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT, padx=10, pady=10)
        
        # Interactive Canvas for Grid
        self.canvas_frame = tk.Frame(self.workspace, bg=BG_COLOR, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#ffffff", bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Canvas Event bindings for pan/zoom
        self.canvas.bind("<ButtonPress-1>", self.on_pan_start)
        self.canvas.bind("<B1-Motion>", self.on_pan_drag)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._offset_x = 0
        self._offset_y = 0
        
        # Bottom Status Footer
        self.footer = tk.Frame(self.root, bg=BG_COLOR, height=25)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=2)
        
        self.bottom_status = tk.Label(self.footer, text="Status: Ready", font=("Segoe UI", 9), fg=TEXT_COLOR, bg=BG_COLOR)
        self.bottom_status.pack(side=tk.LEFT)

    def setup_sidebar_controls(self):
        # Sidebar scrolling capability/container
        sb_canvas = tk.Canvas(self.sidebar, bg=PANEL_COLOR, bd=0, highlightthickness=0)
        sb_scrollbar = ttk.Scrollbar(self.sidebar, orient="vertical", command=sb_canvas.yview)
        scrollable_frame = tk.Frame(sb_canvas, bg=PANEL_COLOR)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: sb_canvas.configure(
                scrollregion=sb_canvas.bbox("all")
            )
        )
        sb_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=260)
        sb_canvas.configure(yscrollcommand=sb_scrollbar.set)
        
        sb_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        sb_scrollbar.pack(side="right", fill="y")
        
        # Control Elements container
        f = scrollable_frame
        
        # Section Title: Simulation Controls
        lbl = tk.Label(f, text="Simulation Controls", font=("Segoe UI", 11, "bold"), fg=TEXT_WHITE, bg=PANEL_COLOR)
        lbl.pack(anchor="w", pady=(5, 10))
        
        # Mode selector dropdown
        mode_f = tk.Frame(f, bg=PANEL_COLOR)
        mode_f.pack(fill=tk.X, pady=3)
        tk.Label(mode_f, text="Mode:", fg=TEXT_COLOR, bg=PANEL_COLOR, width=12, anchor="w").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="Sequential")
        self.mode_combo = ttk.Combobox(mode_f, textvariable=self.mode_var, values=["Sequential", "MPI"], width=12, state="readonly")
        self.mode_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_change)
        
        # Inputs: Grid Size N
        n_f = tk.Frame(f, bg=PANEL_COLOR)
        n_f.pack(fill=tk.X, pady=3)
        tk.Label(n_f, text="Grid Size (N):", fg=TEXT_COLOR, bg=PANEL_COLOR, width=12, anchor="w").pack(side=tk.LEFT)
        self.n_entry = tk.Entry(n_f, bg=BG_COLOR, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, bd=1, width=10)
        self.n_entry.insert(0, "100")
        self.n_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Inputs: Steps T
        t_f = tk.Frame(f, bg=PANEL_COLOR)
        t_f.pack(fill=tk.X, pady=3)
        tk.Label(t_f, text="Steps (T):", fg=TEXT_COLOR, bg=PANEL_COLOR, width=12, anchor="w").pack(side=tk.LEFT)
        self.t_entry = tk.Entry(t_f, bg=BG_COLOR, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, bd=1, width=10)
        self.t_entry.insert(0, "10000")
        self.t_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Inputs: Ants Count
        a_f = tk.Frame(f, bg=PANEL_COLOR)
        a_f.pack(fill=tk.X, pady=3)
        tk.Label(a_f, text="Ants:", fg=TEXT_COLOR, bg=PANEL_COLOR, width=12, anchor="w").pack(side=tk.LEFT)
        self.a_entry = tk.Entry(a_f, bg=BG_COLOR, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, bd=1, width=10)
        self.a_entry.insert(0, "1")
        self.a_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Inputs: MPI Processes P (only active in MPI mode)
        self.p_f = tk.Frame(f, bg=PANEL_COLOR)
        self.p_f.pack(fill=tk.X, pady=3)
        self.p_label = tk.Label(self.p_f, text="Processes (P):", fg=TEXT_COLOR, bg=PANEL_COLOR, width=12, anchor="w")
        self.p_label.pack(side=tk.LEFT)
        self.p_entry = tk.Entry(self.p_f, bg=BG_COLOR, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, bd=1, width=10)
        self.p_entry.insert(0, "4")
        self.p_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Hide P initially since default mode is Sequential
        self.p_f.pack_forget()
        
        # Spacing
        tk.Frame(f, height=5, bg=PANEL_COLOR).pack()
        
        # Buttons Grid (custom flat styled buttons)
        btn_style = {"bg": "#21262d", "fg": TEXT_WHITE, "relief": tk.FLAT, "bd": 0, "activebackground": "#30363d", "activeforeground": TEXT_WHITE, "pady": 4}
        
        self.start_btn = tk.Button(f, text="Start", command=self.on_start, font=("Segoe UI", 10, "bold"), bg=ACCENT_GREEN, fg=BG_COLOR, activebackground="#4cbf60", activeforeground=BG_COLOR, relief=tk.FLAT, bd=0, pady=5)
        self.start_btn.pack(fill=tk.X, pady=5)
        
        # Row 1: Stop / Pause
        r1_f = tk.Frame(f, bg=PANEL_COLOR)
        r1_f.pack(fill=tk.X, pady=2)
        self.stop_btn = tk.Button(r1_f, text="Stop", command=self.on_stop, state=tk.DISABLED, width=10, **btn_style)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.pause_btn = tk.Button(r1_f, text="Pause", command=self.on_pause, state=tk.DISABLED, width=10, **btn_style)
        self.pause_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Row 2: Fit View / Grid ON/OFF
        r2_f = tk.Frame(f, bg=PANEL_COLOR)
        r2_f.pack(fill=tk.X, pady=2)
        self.fit_btn = tk.Button(r2_f, text="Fit View", command=self.on_fit_view, **btn_style)
        self.fit_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.grid_btn = tk.Button(r2_f, text="Grid: ON", command=self.on_toggle_grid, **btn_style)
        self.grid_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Row 3: Center View / Speed factor
        r3_f = tk.Frame(f, bg=PANEL_COLOR)
        r3_f.pack(fill=tk.X, pady=2)
        self.center_btn = tk.Button(r3_f, text="Center: ON", command=self.on_toggle_center, **btn_style)
        self.center_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.speed_btn = tk.Button(r3_f, text="Speed: Max", command=self.on_change_speed, **btn_style)
        self.speed_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Row 4: Step mode / Step +1 / Reset
        r4_f = tk.Frame(f, bg=PANEL_COLOR)
        r4_f.pack(fill=tk.X, pady=2)
        self.stepmode_btn = tk.Button(r4_f, text="Step Mode: OFF", command=self.on_toggle_stepmode, **btn_style)
        self.stepmode_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        r5_f = tk.Frame(f, bg=PANEL_COLOR)
        r5_f.pack(fill=tk.X, pady=2)
        self.step_btn = tk.Button(r5_f, text="Step +1", command=self.on_step_plus_one, state=tk.DISABLED, width=10, **btn_style)
        self.step_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.reset_btn = tk.Button(r5_f, text="Reset", command=self.on_reset, **btn_style)
        self.reset_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        self.png_btn = tk.Button(f, text="Export PNG", command=self.on_export_png, **btn_style)
        self.png_btn.pack(fill=tk.X, pady=5)
        
        # MPI Info Section
        self.mpi_lbl = tk.Label(f, text="MPI Info", font=("Segoe UI", 11, "bold"), fg=TEXT_WHITE, bg=PANEL_COLOR)
        self.mpi_lbl.pack(anchor="w", pady=(15, 5))
        
        self.mpi_procs_lbl = tk.Label(f, text="Processes: 1", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.mpi_procs_lbl.pack(anchor="w", pady=1)
        self.mpi_rank_lbl = tk.Label(f, text="My Rank: 0", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.mpi_rank_lbl.pack(anchor="w", pady=1)
        
        # Statistics Section
        tk.Label(f, text="Statistics", font=("Segoe UI", 11, "bold"), fg=TEXT_WHITE, bg=PANEL_COLOR).pack(anchor="w", pady=(15, 5))
        
        self.stat_black = tk.Label(f, text="Black cells: 0", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_black.pack(anchor="w", pady=1)
        self.stat_white = tk.Label(f, text="White cells: 0", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_white.pack(anchor="w", pady=1)
        self.stat_elapsed = tk.Label(f, text="Elapsed: 0.000s", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_elapsed.pack(anchor="w", pady=1)
        self.stat_speed = tk.Label(f, text="Steps/s: 0", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_speed.pack(anchor="w", pady=1)
        self.stat_ants = tk.Label(f, text="Ants active: 0", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_ants.pack(anchor="w", pady=1)
        self.stat_zoom = tk.Label(f, text="Zoom: 100%", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_zoom.pack(anchor="w", pady=1)
        
        self.stat_comm = tk.Label(f, text="Comm events: 0", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_comm.pack(anchor="w", pady=1)
        self.stat_mig = tk.Label(f, text="Migrations: 0", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_mig.pack(anchor="w", pady=1)
        
        self.stat_pos = tk.Label(f, text="Ant position: [N/A]", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_pos.pack(anchor="w", pady=1)
        self.stat_dir = tk.Label(f, text="Ant direction: N/A", fg=TEXT_COLOR, bg=PANEL_COLOR, font=("Courier New", 9))
        self.stat_dir.pack(anchor="w", pady=1)

    def on_mode_change(self, event=None):
        mode = self.mode_var.get()
        if mode == "MPI":
            self.p_f.pack(fill=tk.X, pady=3, after=self.a_entry.master)
            self.mode_label.config(text="Mode: MPI", fg=ACCENT_GREEN)
            self.mpi_procs_lbl.config(text=f"Processes: {self.p_entry.get()}")
        else:
            self.p_f.pack_forget()
            self.mode_label.config(text="Mode: Sequential", fg=ACCENT_BLUE)
            self.mpi_procs_lbl.config(text="Processes: 1")

    def on_start(self):
        if self.is_running:
            if self.is_paused:
                self.is_paused = False
                self.status_label.config(text="Simulation Running", fg=ACCENT_GREEN)
                self.bottom_status.config(text="Status: Running")
                self.start_btn.config(text="Start", bg=ACCENT_GREEN)
            return

        # Start a new simulation
        try:
            self.grid_size = int(self.n_entry.get())
            self.steps_limit = int(self.t_entry.get())
            self.ants_count = int(self.a_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid integers for grid size, steps, and ants.")
            return

        self.on_reset()
        
        # Prepare execution arguments
        mode = self.mode_var.get()
        if mode == "Sequential":
            exec_path = os.path.join("build", "langton.exe")
            if not os.path.exists(exec_path):
                messagebox.showerror("Executable Missing", f"Could not find sequential executable at {exec_path}.\nPlease build using build.bat first.")
                return
            cmd = [exec_path, "-n", str(self.grid_size), "-t", str(self.steps_limit), "-a", str(self.ants_count), "-g"]
            self.mpi_procs_lbl.config(text="Processes: 1")
            self.mpi_rank_lbl.config(text="My Rank: 0")
        else:
            exec_path = os.path.join("build-mpi", "langton_mpi.exe")
            if not os.path.exists(exec_path):
                messagebox.showerror("Executable Missing", f"Could not find MPI executable at {exec_path}.\nPlease build using build-mpi.bat first.")
                return
            try:
                p_count = int(self.p_entry.get())
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid integer for MPI processes.")
                return
            cmd = ["mpiexec", "-n", str(p_count), exec_path, "-n", str(self.grid_size), "-t", str(self.steps_limit), "-a", str(self.ants_count), "-g"]
            self.mpi_procs_lbl.config(text=f"Processes: {p_count}")
            self.mpi_rank_lbl.config(text="My Rank: 0")

        # Launch process
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to start simulator: {str(e)}")
            return

        self.is_running = True
        self.is_paused = False
        self.start_time = time.time()
        self.current_step = 0
        
        # Update UI buttons state
        self.start_btn.config(state=tk.DISABLED, bg="#21262d")
        self.stop_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL, text="Pause")
        self.n_entry.config(state=tk.DISABLED)
        self.t_entry.config(state=tk.DISABLED)
        self.a_entry.config(state=tk.DISABLED)
        self.p_entry.config(state=tk.DISABLED)
        self.mode_combo.config(state=tk.DISABLED)
        
        self.status_label.config(text="Simulation Running", fg=ACCENT_GREEN)
        self.bottom_status.config(text="Status: Running")
        
        # Start reading stdout in worker thread
        threading.Thread(target=self.read_stdout, args=(self.process,), daemon=True).start()

    def on_stop(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.is_running = False
        self.is_paused = False
        
        self.start_btn.config(state=tk.NORMAL, bg=ACCENT_GREEN, text="Start")
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED, text="Pause")
        self.n_entry.config(state=tk.NORMAL)
        self.t_entry.config(state=tk.NORMAL)
        self.a_entry.config(state=tk.NORMAL)
        self.p_entry.config(state=tk.NORMAL)
        self.mode_combo.config(state=tk.NORMAL)
        
        self.status_label.config(text="Simulation Stopped", fg=ACCENT_RED)
        self.bottom_status.config(text="Status: Stopped")

    def on_pause(self):
        if not self.is_running:
            return
        if self.is_paused:
            # Resume
            self.is_paused = False
            self.pause_btn.config(text="Pause")
            self.status_label.config(text="Simulation Running", fg=ACCENT_GREEN)
            self.bottom_status.config(text="Status: Running")
        else:
            # Pause
            self.is_paused = True
            self.pause_btn.config(text="Resume")
            self.status_label.config(text="Simulation Paused", fg="orange")
            self.bottom_status.config(text="Status: Paused")

    def on_reset(self):
        self.on_stop()
        self.canvas.delete("all")
        self.black_cells.clear()
        self.ant_shapes.clear()
        self.ant_positions.clear()
        
        self.current_step = 0
        self.black_cells_count = 0
        self.white_cells_count = self.grid_size * self.grid_size
        self.migrations_count = 0
        self.elapsed_time = 0.0
        
        self.step_progress_label.config(text=f"Step: 0 / {self.steps_limit}")
        self.stat_black.config(text="Black cells: 0")
        self.stat_white.config(text=f"White cells: {self.white_cells_count}")
        self.stat_elapsed.config(text="Elapsed: 0.000s")
        self.stat_speed.config(text="Steps/s: 0")
        self.stat_ants.config(text="Ants active: 0")
        self.stat_comm.config(text="Comm events: 0")
        self.stat_mig.config(text="Migrations: 0")
        self.stat_pos.config(text="Ant position: [N/A]")
        self.stat_dir.config(text="Ant direction: N/A")
        
        self.on_fit_view()

    def on_fit_view(self):
        # Center and fit the canvas grid
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10: cw = 600
        if ch < 10: ch = 600
        
        # Calculate cell size to fit N grid size
        margin = 40
        available_w = cw - margin
        available_h = ch - margin
        
        size = min(available_w, available_h)
        self.cell_pixel_size = max(1.0, size / self.grid_size)
        
        self.zoom_level = 1.0
        self.stat_zoom.config(text="Zoom: 100%")
        
        # Offsets to center
        self._offset_x = (cw - self.cell_pixel_size * self.grid_size) / 2
        self._offset_y = (ch - self.cell_pixel_size * self.grid_size) / 2
        
        self.redraw_grid()

    def on_toggle_grid(self):
        self.show_grid = not self.show_grid
        self.grid_btn.config(text=f"Grid: {'ON' if self.show_grid else 'OFF'}")
        self.redraw_grid()

    def on_toggle_center(self):
        self.center_view = not self.center_view
        self.center_btn.config(text=f"Center: {'ON' if self.center_view else 'OFF'}")

    def on_change_speed(self):
        speeds = ["1x", "2x", "5x", "10x", "Max"]
        idx = (speeds.index(self.speed_factor) + 1) % len(speeds)
        self.speed_factor = speeds[idx]
        self.speed_btn.config(text=f"Speed: {self.speed_factor}")

    def on_toggle_stepmode(self):
        self.step_mode = not self.step_mode
        self.stepmode_btn.config(text=f"Step Mode: {'ON' if self.step_mode else 'OFF'}")
        if self.step_mode:
            self.step_btn.config(state=tk.NORMAL)
            if self.is_running and not self.is_paused:
                self.on_pause()
        else:
            self.step_btn.config(state=tk.DISABLED)
            if self.is_running and self.is_paused:
                self.on_pause()

    def on_step_plus_one(self):
        # In step mode, process messages until the next STEP message is reached
        if not self.is_running:
            return
        self.is_paused = False
        # Enable processing for just one step
        self.root.after(1, self.step_once_process)

    def step_once_process(self):
        # Process queue until a STEP line is read, then pause again
        processed_step = False
        t_start = time.time()
        while not self.msg_queue.empty() and not processed_step:
            msg_type, args = self.msg_queue.get_nowait()
            self.handle_message(msg_type, args)
            if msg_type == "STEP":
                processed_step = True
            if time.time() - t_start > 0.05: # safety timeout
                break
        self.is_paused = True
        self.pause_btn.config(text="Resume")
        self.status_label.config(text="Simulation Paused", fg="orange")
        self.bottom_status.config(text="Status: Paused")

    def on_export_png(self):
        # Saves the canvas to a Postscript file, which is simple
        try:
            filename = f"grid_step_{self.current_step}.ps"
            self.canvas.postscript(file=filename, colormode="color")
            messagebox.showinfo("Export Exported", f"Successfully exported canvas layout to Postscript vector file: {filename}\n(You can convert it to PNG using standard converters).")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

    # Canvas Panning and Zooming Event Handlers
    def on_pan_start(self, event):
        self._pan_start_x = event.x
        self._pan_start_y = event.y

    def on_pan_drag(self, event):
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        self._offset_x += dx
        self._offset_y += dy
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self.redraw_grid()

    def on_zoom(self, event):
        # Mousewheel zoom
        factor = 1.1 if event.delta > 0 else 0.9
        
        # Zoom around mouse cursor coordinate
        mouse_x = event.x
        mouse_y = event.y
        
        # Calculate cell coordinates under mouse before zoom
        grid_mouse_x = (mouse_x - self._offset_x) / self.cell_pixel_size
        grid_mouse_y = (mouse_y - self._offset_y) / self.cell_pixel_size
        
        # Update cell size
        self.cell_pixel_size *= factor
        if self.cell_pixel_size < 0.2: self.cell_pixel_size = 0.2
        if self.cell_pixel_size > 100.0: self.cell_pixel_size = 100.0
        
        # Update offsets so that the same cell remains under the mouse cursor
        self._offset_x = mouse_x - grid_mouse_x * self.cell_pixel_size
        self._offset_y = mouse_y - grid_mouse_y * self.cell_pixel_size
        
        self.zoom_level *= factor
        self.stat_zoom.config(text=f"Zoom: {int(self.zoom_level * 100)}%")
        
        self.redraw_grid()

    # Worker thread reads subprocess stdout
    def read_stdout(self, proc):
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            cmd = parts[0]
            
            # Put structured message into thread-safe queue
            self.msg_queue.put((cmd, parts[1:]))
            
            if cmd == "FINISHED":
                break
                
        # Read remaining stderr if any
        stderr_text = proc.stderr.read()
        if stderr_text:
            print(f"Subprocess stderr: {stderr_text}", file=sys.stderr)

    # Tkinter Main Loop queue checker
    def poll_queue(self):
        # Control animation speed by limiting messages processed per check
        max_messages_to_process = 50
        if self.speed_factor == "1x":
            max_messages_to_process = 1
        elif self.speed_factor == "2x":
            max_messages_to_process = 2
        elif self.speed_factor == "5x":
            max_messages_to_process = 5
        elif self.speed_factor == "10x":
            max_messages_to_process = 10
        elif self.speed_factor == "Max":
            max_messages_to_process = 1000  # process as fast as possible
            
        if not self.is_paused:
            processed_count = 0
            while not self.msg_queue.empty() and processed_count < max_messages_to_process:
                try:
                    msg_type, args = self.msg_queue.get_nowait()
                    self.handle_message(msg_type, args)
                    if msg_type == "STEP":
                        processed_count += 1
                except queue.Empty:
                    break
                    
        # Repeat call every 10 milliseconds
        self.root.after(10, self.poll_queue)

    def handle_message(self, cmd, args):
        if cmd == "INIT":
            self.grid_size = int(args[0])
            self.ants_count = int(args[1])
            p_count = int(args[2])
            self.black_cells.clear()
            self.canvas.delete("all")
            self.on_fit_view()
        elif cmd == "START":
            self.start_time = time.time()
        elif cmd == "STEP":
            self.current_step = int(args[0])
            self.step_progress_label.config(text=f"Step: {self.current_step} / {self.steps_limit}")
        elif cmd == "FLIP":
            x = int(args[0])
            y = int(args[1])
            color = int(args[2])
            self.update_cell_color(x, y, color)
        elif cmd == "ANT":
            ant_id = int(args[0])
            x = int(args[1])
            y = int(args[2])
            dir_val = int(args[3])
            self.ant_positions[ant_id] = (x, y, dir_val)
            self.draw_ant(ant_id, x, y, dir_val)
        elif cmd == "STATS":
            self.black_cells_count = int(args[0])
            self.white_cells_count = int(args[1])
            migrations = int(args[2])
            
            # Calculate live speed
            self.elapsed_time = time.time() - self.start_time
            speed = int(self.current_step / max(0.001, self.elapsed_time))
            
            # MPI communication estimation based on step structure
            world_size = int(self.p_entry.get()) if self.mode_var.get() == "MPI" else 1
            comm_events = self.current_step * (4 if world_size > 1 else 0)
            
            self.stat_black.config(text=f"Black cells: {self.black_cells_count}")
            self.stat_white.config(text=f"White cells: {self.white_cells_count}")
            self.stat_elapsed.config(text=f"Elapsed: {self.elapsed_time:.3f}s")
            self.stat_speed.config(text=f"Steps/s: {speed}")
            self.stat_ants.config(text=f"Ants active: {len(self.ant_positions)}")
            self.stat_comm.config(text=f"Comm events: {comm_events}")
            self.stat_mig.config(text=f"Migrations: {migrations}")
            
            # Show first ant stats
            if 0 in self.ant_positions:
                ax, ay, ad = self.ant_positions[0]
                dir_names = ["UP (North)", "RIGHT (East)", "DOWN (South)", "LEFT (West)"]
                self.stat_pos.config(text=f"Ant position: [{ax}, {ay}]")
                self.stat_dir.config(text=f"Ant direction: {dir_names[ad]}")
                
                # Auto center view if enabled
                if self.center_view:
                    self.center_view_on_ant(ax, ay)
                    
        elif cmd == "FINISHED":
            self.on_stop()
            self.status_label.config(text="Status: Finished", fg=ACCENT_GREEN)
            self.bottom_status.config(text="Status: Finished")
            messagebox.showinfo("Simulation Complete", "The Langton's Ant simulation has completed successfully!")

    def center_view_on_ant(self, ax, ay):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10: cw = 600
        if ch < 10: ch = 600
        
        # Calculate offset to bring ant center
        self._offset_x = cw / 2 - (ax + 0.5) * self.cell_pixel_size
        self._offset_y = ch / 2 - (ay + 0.5) * self.cell_pixel_size
        self.redraw_grid()

    # Draw grid cells
    def redraw_grid(self):
        # Draw background grid boundary/background
        self.canvas.delete("grid_line")
        
        w_size = self.cell_pixel_size * self.grid_size
        x0 = self._offset_x
        y0 = self._offset_y
        x1 = x0 + w_size
        y1 = y0 + w_size
        
        # Draw boundary
        self.canvas.delete("boundary")
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="#ffffff", outline=BORDER_COLOR, width=2, tags="boundary")
        
        # Draw grid lines if Grid: ON and cell size is reasonable (not too small)
        if self.show_grid and self.cell_pixel_size >= 4.0:
            for i in range(self.grid_size + 1):
                pos_x = x0 + i * self.cell_pixel_size
                self.canvas.create_line(pos_x, y0, pos_x, y1, fill="#e1e4e8", tags="grid_line")
                
                pos_y = y0 + i * self.cell_pixel_size
                self.canvas.create_line(x0, pos_y, x1, pos_y, fill="#e1e4e8", tags="grid_line")

        # Reposition all black cells
        for (x, y), rect_id in list(self.black_cells.items()):
            px0 = x0 + x * self.cell_pixel_size
            py0 = y0 + y * self.cell_pixel_size
            px1 = px0 + self.cell_pixel_size
            py1 = py0 + self.cell_pixel_size
            self.canvas.coords(rect_id, px0, py0, px1, py1)
            # Lift it above the boundary
            self.canvas.tag_raise(rect_id)

        # Reposition all ants
        for ant_id, (x, y, dir_val) in list(self.ant_positions.items()):
            self.draw_ant(ant_id, x, y, dir_val)

    def update_cell_color(self, x, y, color):
        # Optimized cell redraw: only draw/delete canvas elements as needed
        if color == 1:
            # Black cell: draw only if not already drawn
            if (x, y) not in self.black_cells:
                px0 = self._offset_x + x * self.cell_pixel_size
                py0 = self._offset_y + y * self.cell_pixel_size
                px1 = px0 + self.cell_pixel_size
                py1 = py0 + self.cell_pixel_size
                
                rect_id = self.canvas.create_rectangle(px0, py0, px1, py1, fill="#000000", outline="")
                self.black_cells[(x, y)] = rect_id
        else:
            # White cell: delete rectangle if present
            if (x, y) in self.black_cells:
                rect_id = self.black_cells.pop((x, y))
                self.canvas.delete(rect_id)

    def draw_ant(self, ant_id, x, y, dir_val):
        # Delete previous shape
        if ant_id in self.ant_shapes:
            self.canvas.delete(self.ant_shapes[ant_id])
            
        # Draw ant as a triangular pointer based on direction
        px0 = self._offset_x + x * self.cell_pixel_size
        py0 = self._offset_y + y * self.cell_pixel_size
        px1 = px0 + self.cell_pixel_size
        py1 = py0 + self.cell_pixel_size
        cx = (px0 + px1) / 2
        cy = (py0 + py1) / 2
        
        # Triangle vertices
        if dir_val == 0:    # UP
            coords = [cx, py0 + 1, px0 + 2, py1 - 2, px1 - 2, py1 - 2]
        elif dir_val == 1:  # RIGHT
            coords = [px1 - 1, cy, px0 + 2, py0 + 2, px0 + 2, py1 - 2]
        elif dir_val == 2:  # DOWN
            coords = [cx, py1 - 1, px0 + 2, py0 + 2, px1 - 2, py0 + 2]
        else:               # LEFT
            coords = [px0 + 1, cy, px1 - 2, py0 + 2, px1 - 2, py1 - 2]
            
        # Draw ant shape (using high-visibility orange-red color)
        poly_id = self.canvas.create_polygon(coords, fill=ACCENT_RED, outline="#ffc300", width=1)
        self.ant_shapes[ant_id] = poly_id
        self.canvas.tag_raise(poly_id)

    def on_close(self):
        self.on_stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LangtonAntGUI(root)
    # Perform initial resize config fit
    root.update()
    app.on_fit_view()
    root.mainloop()
