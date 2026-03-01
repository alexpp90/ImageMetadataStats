import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import send2trash
from PIL import Image, ImageTk

from image_metadata_analyzer.reader import get_exif_data
# Local imports
from image_metadata_analyzer.sharpness import (calculate_sharpness,
                                               find_related_files)
from image_metadata_analyzer.utils import load_image_preview

logger = logging.getLogger(__name__)


class FullscreenViewer(tk.Toplevel):
    def __init__(self, parent, path, initial_mode="fit", focus_point=(0.5, 0.5)):
        super().__init__(parent)
        self.parent = parent
        self.path = path
        self.initial_mode = initial_mode
        self.focus_point = focus_point  # (rel_x, rel_y) 0.0-1.0

        self.title(f"Fullscreen - {path.name}")
        self.attributes("-fullscreen", True)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}")

        # UI Elements
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.loading_lbl = ttk.Label(
            self,
            text="Loading full resolution...",
            anchor="center",
            background="black",
            foreground="white",
        )
        self.loading_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self.close_btn = ttk.Button(self, text="Close (Esc)", command=self.destroy)
        self.close_btn.place(relx=0.95, rely=0.05, anchor="ne")

        # State
        self.pil_image = None  # Full resolution PIL image
        self.tk_image = None
        self.scale = 1.0
        self.min_scale = 0.1
        self.fit_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start = None

        # Bindings
        self.bind("<Escape>", lambda e: self.destroy())
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_move)

        # Zoom bindings
        self.canvas.bind("<MouseWheel>", self.on_zoom_wheel)  # Windows/MacOS
        self.canvas.bind("<Button-4>", self.on_zoom_wheel)  # Linux Scroll Up
        self.canvas.bind("<Button-5>", self.on_zoom_wheel)  # Linux Scroll Down

        # Key navigation
        self.bind("<Left>", lambda e: self.pan_key(50, 0))
        self.bind("<Right>", lambda e: self.pan_key(-50, 0))
        self.bind("<Up>", lambda e: self.pan_key(0, 50))
        self.bind("<Down>", lambda e: self.pan_key(0, -50))
        self.bind("<plus>", lambda e: self.zoom_key(1.2))
        self.bind("<equal>", lambda e: self.zoom_key(1.2))  # Shared key with plus
        self.bind("<minus>", lambda e: self.zoom_key(0.8))

        # Start Loading
        self.after(100, self.load_image)

    def load_image(self):
        # Check cache
        img = None
        with self.parent.full_res_lock:
            img = self.parent.full_res_cache.get(self.path)

        if img:
            self.pil_image = img
            self.on_image_loaded()
        else:
            # Load in thread
            threading.Thread(target=self.load_worker, daemon=True).start()

    def load_worker(self):
        try:
            img = load_image_preview(self.path, full_res=True)
            if img:
                self.pil_image = img
                self.parent.after(0, self.on_image_loaded)
                # Add to parent cache if possible
                with self.parent.full_res_lock:
                    self.parent.full_res_cache[self.path] = img
            else:
                self.parent.after(
                    0, lambda: self.loading_lbl.config(text="Failed to load.")
                )
        except Exception as e:
            msg = f"Error: {e}"
            self.parent.after(0, lambda: self.loading_lbl.config(text=msg))

    def on_image_loaded(self):
        self.loading_lbl.place_forget()
        if not self.pil_image:
            return

        # Calculate fit scale
        sw = self.winfo_width()
        sh = self.winfo_height()
        iw, ih = self.pil_image.size

        # Avoid division by zero
        if iw == 0 or ih == 0:
            return

        scale_w = sw / iw
        scale_h = sh / ih
        self.fit_scale = min(scale_w, scale_h)
        self.min_scale = self.fit_scale

        if self.initial_mode == "fit":
            self.scale = self.fit_scale
            # Center image
            self.offset_x = (sw - iw * self.scale) / 2
            self.offset_y = (sh - ih * self.scale) / 2
        else:
            # 100%
            self.scale = 1.0
            # Center on focus point
            rel_x, rel_y = self.focus_point

            # Target center on screen
            cx = sw / 2
            cy = sh / 2

            # Image coordinate to be at cx, cy
            ix = rel_x * iw
            iy = rel_y * ih

            # offset_x + ix * scale = cx
            # offset_x = cx - ix * scale
            self.offset_x = cx - ix * self.scale
            self.offset_y = cy - iy * self.scale

            self.clamp_offsets()

        self.redraw()

    def redraw(self):
        if not self.pil_image:
            return

        # Optimized approach: Crop and Resize
        sw = self.winfo_width()
        sh = self.winfo_height()

        # Viewport rectangle on image
        # canvas_x = offset_x + image_x * scale
        # image_x = (canvas_x - offset_x) / scale

        x1 = max(0, (0 - self.offset_x) / self.scale)
        y1 = max(0, (0 - self.offset_y) / self.scale)
        x2 = min(self.pil_image.width, (sw - self.offset_x) / self.scale)
        y2 = min(self.pil_image.height, (sh - self.offset_y) / self.scale)

        if x2 <= x1 or y2 <= y1:
            self.canvas.delete("all")
            return

        # Crop
        crop_box = (int(x1), int(y1), int(x2) + 1, int(y2) + 1)

        try:
            region = self.pil_image.crop(crop_box)

            # Resize region to screen pixels
            target_w = int(region.width * self.scale)
            target_h = int(region.height * self.scale)

            if target_w <= 0 or target_h <= 0:
                return

            # Use BILINEAR for quality
            region = region.resize((target_w, target_h), Image.Resampling.BILINEAR)

            self.tk_image = ImageTk.PhotoImage(region)

            # Place on canvas
            dest_x = self.offset_x + x1 * self.scale
            dest_y = self.offset_y + y1 * self.scale

            self.canvas.delete("all")
            self.canvas.create_image(dest_x, dest_y, anchor="nw", image=self.tk_image)

        except Exception as e:
            logger.error(f"Redraw error: {e}")

    def clamp_offsets(self):
        sw = self.winfo_width()
        sh = self.winfo_height()
        if not self.pil_image:
            return

        iw = self.pil_image.width * self.scale
        ih = self.pil_image.height * self.scale

        if iw <= sw:
            self.offset_x = (sw - iw) / 2
        else:
            # Constrain: offset_x cannot be > 0 (left gap) and cannot be < sw - iw (right gap)
            self.offset_x = min(0, max(sw - iw, self.offset_x))

        if ih <= sh:
            self.offset_y = (sh - ih) / 2
        else:
            self.offset_y = min(0, max(sh - ih, self.offset_y))

    def on_drag_start(self, event):
        self.drag_start = (event.x, event.y)

    def on_drag_move(self, event):
        if not self.drag_start:
            return
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]

        self.offset_x += dx
        self.offset_y += dy
        self.drag_start = (event.x, event.y)

        self.clamp_offsets()
        self.redraw()

    def on_zoom_wheel(self, event):
        # Determine zoom direction
        factor = 1.0
        if event.num == 4:  # Linux Scroll Up
            factor = 1.2
        elif event.num == 5:  # Linux Scroll Down
            factor = 0.8
        else:  # Windows/MacOS
            if event.delta > 0:
                factor = 1.2
            else:
                factor = 0.8

        self.zoom(factor, event.x, event.y)

    def zoom_key(self, factor):
        cx = self.winfo_width() / 2
        cy = self.winfo_height() / 2
        self.zoom(factor, cx, cy)

    def zoom(self, factor, center_x, center_y):
        if not self.pil_image:
            return

        old_scale = self.scale
        new_scale = old_scale * factor

        # Limits
        # Min scale: Fit to screen
        if new_scale < self.fit_scale:
            new_scale = self.fit_scale

        # Max scale: Let's allow up to 400%
        if new_scale > 4.0:
            new_scale = 4.0

        if new_scale == old_scale:
            return

        # Calculate new offsets to keep (center_x, center_y) pointed at same image pixel
        # Image pixel at center_x:
        # px = (center_x - offset_x) / old_scale
        # New offset:
        # center_x = new_offset_x + px * new_scale
        # new_offset_x = center_x - px * new_scale

        px = (center_x - self.offset_x) / old_scale
        py = (center_y - self.offset_y) / old_scale

        self.offset_x = center_x - px * new_scale
        self.offset_y = center_y - py * new_scale

        self.scale = new_scale
        self.clamp_offsets()
        self.redraw()

    def pan_key(self, dx, dy):
        self.offset_x += dx
        self.offset_y += dy
        self.clamp_offsets()
        self.redraw()


class SharpnessTool(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.log_queue = queue.Queue()
        self.is_scanning = False
        self.stop_event = threading.Event()

        # State
        self.scan_results = []  # List of dicts: {path, score, category, exif}
        self.files_map = {}  # path -> result dict
        self.sorted_files = []  # List of paths sorted by filename
        self.candidates = []  # List of paths that are category 2 or 3

        # Caching and Review State
        self.image_cache = {}
        self.cache_lock = threading.Lock()
        self.preloader_queue = queue.Queue()
        self.has_switched_to_review = False

        # Full Resolution Caching
        self.full_res_cache = {}
        self.full_res_queue = queue.Queue()
        self.full_res_lock = threading.Lock()

        self.start_preloader()
        self.start_full_res_preloader()

        # Defaults
        self.default_blur_threshold = 100.0
        self.default_sharp_threshold = 500.0
        self.default_grid_size = "8x8"
        self.focus_mode = False

        self.setup_ui()
        self.setup_focus_ui()

    def setup_ui(self):
        # Notebook for switching between Setup, Scanning, and Review
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # --- Tab 1: Configuration ---
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Configuration")
        self.setup_config_ui()

        # --- Tab 2: Scanning ---
        self.scan_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.scan_frame, text="Scanning")
        self.setup_scan_ui()

        # --- Tab 3: Review ---
        self.review_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.review_frame, text="Review")
        self.setup_review_ui()

        # Initially disable other tabs
        self.notebook.tab(1, state="disabled")
        self.notebook.tab(2, state="disabled")

    def setup_config_ui(self):
        # Controls container
        container = ttk.Frame(self.config_frame, padding=20)
        container.pack(fill="x")

        # Folder Selection
        ttk.Label(container, text="Images Folder:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.folder_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.folder_var, width=50).grid(
            row=0, column=1, padx=5, pady=5
        )
        ttk.Button(container, text="Browse...", command=self.browse_folder).grid(
            row=0, column=2, pady=5
        )

        # Tool Selection
        tools_frame = ttk.LabelFrame(container, text="Analysis Tools", padding=10)
        tools_frame.grid(row=1, column=0, columnspan=3, pady=10, sticky="ew")

        # Create rows for each tool inside tools_frame for better alignment
        sharpness_row = ttk.Frame(tools_frame)
        sharpness_row.pack(fill="x", pady=5)

        self.tool_sharpness_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sharpness_row, text="Sharpness Analysis", variable=self.tool_sharpness_var).pack(side="left", padx=5)

        ttk.Label(sharpness_row, text="Grid Analysis Size:").pack(side="left", padx=(20, 5))
        self.grid_size_var = tk.StringVar(value=self.default_grid_size)
        grid_combo = ttk.Combobox(
            sharpness_row,
            textvariable=self.grid_size_var,
            values=["1x1 (Global)", "2x2", "3x3", "4x4", "5x5", "8x8"],
            state="readonly",
            width=12,
        )
        grid_combo.pack(side="left", padx=5)
        ttk.Label(
            sharpness_row,
            text="(Higher grid size helps find small sharp subjects in blurry backgrounds)",
        ).pack(side="left", padx=5)

        dummy1_row = ttk.Frame(tools_frame)
        dummy1_row.pack(fill="x", pady=5)
        self.tool_dummy1_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dummy1_row, text="Dummy Tool 1", variable=self.tool_dummy1_var).pack(side="left", padx=5)

        dummy2_row = ttk.Frame(tools_frame)
        dummy2_row.pack(fill="x", pady=5)
        self.tool_dummy2_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dummy2_row, text="Dummy Tool 2", variable=self.tool_dummy2_var).pack(side="left", padx=5)

        # Start Button
        self.start_btn = ttk.Button(
            container, text="Start Scan", command=self.start_scan
        )
        self.start_btn.grid(row=2, column=0, columnspan=3, pady=20)

    def setup_scan_ui(self):
        container = ttk.Frame(self.scan_frame, padding=20)
        container.pack(fill="both", expand=True)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            container, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill="x", pady=20)

        self.scan_status_lbl = ttk.Label(container, text="Ready...")
        self.scan_status_lbl.pack(pady=5)

        # Log area
        self.log_text = tk.Text(container, height=15, state="disabled")
        self.log_text.pack(fill="both", expand=True, pady=10)

        self.cancel_btn = ttk.Button(
            container, text="Cancel Scan", command=self.cancel_scan
        )
        self.cancel_btn.pack(pady=10)

    def setup_review_ui(self):
        # Layout: Left Sidebar (List), Right Main (Preview)
        self.paned = ttk.PanedWindow(self.review_frame, orient="horizontal")
        self.paned.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = ttk.Frame(self.paned, width=250, padding=5)
        self.paned.add(self.sidebar, weight=1)

        ttk.Label(self.sidebar, text="Images").pack(pady=5)

        # Scan Progress (Visible during review)
        self.scan_progress_frame = ttk.Frame(self.sidebar)
        self.scan_progress_frame.pack(fill="x", pady=(0, 10))

        self.review_status_lbl = ttk.Label(
            self.scan_progress_frame, text="Scan Progress: 0%"
        )
        self.review_status_lbl.pack(side="top", anchor="w")

        self.review_progress_var = tk.DoubleVar()
        self.review_progress_bar = ttk.Progressbar(
            self.scan_progress_frame, variable=self.review_progress_var, maximum=100
        )
        self.review_progress_bar.pack(fill="x")

        # Scrollbar and Listbox
        sb = ttk.Scrollbar(self.sidebar)
        sb.pack(side="right", fill="y")

        self.candidate_listbox = tk.Listbox(
            self.sidebar, yscrollcommand=sb.set, selectmode="single"
        )
        self.candidate_listbox.pack(fill="both", expand=True)
        sb.config(command=self.candidate_listbox.yview)

        self.candidate_listbox.bind("<<ListboxSelect>>", self.on_candidate_select)

        # Main Preview Area
        self.preview_area = ttk.Frame(self.paned, padding=10)
        self.paned.add(self.preview_area, weight=4)

        # --- Top Container: Main Candidate + Controls ---
        self.top_container = ttk.Frame(self.preview_area)
        self.top_container.pack(side="top", fill="both", expand=True, pady=(0, 10))

        # Grid Layout for Top Container (Image Center, Controls Right)
        self.top_container.columnconfigure(0, weight=1)  # Spacer Left
        self.top_container.columnconfigure(1, weight=0)  # Image Center
        self.top_container.columnconfigure(2, weight=1)  # Controls Right

        # Spacer (Left)
        ttk.Frame(self.top_container).grid(row=0, column=0, sticky="ew")

        # Current Candidate (Center)
        self.panel_curr = self.create_image_panel(self.top_container, "Current Image")
        # Using sticky="nsew" so it expands and centers properly if window shrinks
        self.panel_curr.grid(row=0, column=1, padx=10, sticky="nsew")

        # Info & Actions (Right)
        self.info_frame = ttk.Frame(self.top_container, padding=5)
        self.info_frame.grid(row=0, column=2, sticky="ns", padx=10)

        # Metadata Label
        self.meta_lbl = ttk.Label(
            self.info_frame,
            text="",
            font=("Helvetica", 10),
            justify="left",
            wraplength=200,
        )
        self.meta_lbl.pack(pady=10, anchor="w")

        # Buttons (Vertical Stack)
        btn_frame = ttk.Frame(self.info_frame)
        btn_frame.pack(pady=10, fill="x")

        self.prev_btn = ttk.Button(
            btn_frame, text="< Prev", command=self.prev_candidate
        )
        self.prev_btn.pack(side="top", fill="x", pady=2)

        self.next_btn = ttk.Button(
            btn_frame, text="Next >", command=self.next_candidate
        )
        self.next_btn.pack(side="top", fill="x", pady=2)

        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=10)

        self.del_btn = ttk.Button(
            btn_frame,
            text="Delete (Trash)",
            command=self.delete_current_candidate,
        )
        self.del_btn.pack(side="top", fill="x", pady=2)

        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=10)

        self.focus_toggle_btn = ttk.Button(
            btn_frame, text="Focus Mode", command=self.toggle_focus_mode
        )
        self.focus_toggle_btn.pack(side="top", fill="x", pady=2)

        # --- Bottom Container: Neighbors ---
        self.bottom_container = ttk.Frame(self.preview_area)
        self.bottom_container.pack(side="bottom", fill="both", expand=True, ipady=5)

        # Neighbors
        self.panel_prev = self.create_image_panel(
            self.bottom_container, "Previous Image"
        )
        self.panel_prev.pack(side="left", fill="both", expand=True, padx=2)

        self.panel_next = self.create_image_panel(self.bottom_container, "Next Image")
        self.panel_next.pack(side="right", fill="both", expand=True, padx=2)

    def setup_focus_ui(self):
        """Builds the fullscreen-optimized focus layout."""
        self.focus_frame = ttk.Frame(self)

        # Grid Configuration
        self.focus_frame.rowconfigure(0, weight=1)
        self.focus_frame.rowconfigure(1, weight=1)

        # Columns for Top Row centering
        self.focus_frame.columnconfigure(0, weight=1)  # Spacer Left
        self.focus_frame.columnconfigure(1, weight=0)  # Image Center
        self.focus_frame.columnconfigure(2, weight=1)  # Controls Right

        # --- Row 0: Main Area ---

        # Left Spacer (Row 0, Col 0)
        ttk.Frame(self.focus_frame).grid(row=0, column=0, sticky="ew")

        # Center (Row 0, Col 1) - Current Candidate
        self.focus_curr_container = ttk.Frame(self.focus_frame)
        self.focus_curr_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        self.focus_curr_lbl = ttk.Label(
            self.focus_curr_container, text="No Image", anchor="center"
        )
        self.focus_curr_lbl.pack(fill="both", expand=True)
        self.focus_curr_lbl.bind(
            "<Button-1>", lambda e: self.on_image_click(self.panel_curr.path)
        )

        # Right Gutter (Row 0, Col 2) - Controls
        self.focus_right_panel = ttk.Frame(self.focus_frame)
        self.focus_right_panel.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        # Controls Stack
        self.focus_exit_btn = ttk.Button(
            self.focus_right_panel,
            text="Exit Focus Mode",
            command=self.toggle_focus_mode,
        )
        self.focus_exit_btn.pack(side="top", pady=10, fill="x")

        ttk.Separator(self.focus_right_panel, orient="horizontal").pack(
            fill="x", pady=10
        )

        self.focus_score_lbl = ttk.Label(
            self.focus_right_panel, text="Sharpness Score: --", font=("Helvetica", 12, "bold")
        )
        self.focus_score_lbl.pack(side="top", pady=5, anchor="w")

        self.focus_cat_lbl = ttk.Label(
            self.focus_right_panel, text="", font=("Helvetica", 10)
        )
        self.focus_cat_lbl.pack(side="top", pady=5, anchor="w")

        self.focus_filename_lbl = ttk.Label(
            self.focus_right_panel, text="", wraplength=150
        )
        self.focus_filename_lbl.pack(side="top", pady=5, anchor="w")

        self.focus_meta_lbl = ttk.Label(
            self.focus_right_panel, text="", justify="left", wraplength=150
        )
        self.focus_meta_lbl.pack(side="top", pady=5, anchor="w")

        ttk.Separator(self.focus_right_panel, orient="horizontal").pack(
            fill="x", pady=10
        )

        # Navigation & Actions
        self.focus_prev_btn = ttk.Button(
            self.focus_right_panel, text="< Previous", command=self.prev_candidate
        )
        self.focus_prev_btn.pack(side="top", pady=5, fill="x")

        self.focus_next_btn = ttk.Button(
            self.focus_right_panel, text="Next >", command=self.next_candidate
        )
        self.focus_next_btn.pack(side="top", pady=5, fill="x")

        self.focus_del_btn = ttk.Button(
            self.focus_right_panel,
            text="DELETE (Trash)",
            command=self.delete_current_candidate,
        )
        self.focus_del_btn.pack(side="top", pady=20, fill="x")

        # --- Row 1: Bottom Strip ---
        self.focus_bottom_frame = ttk.Frame(self.focus_frame)
        self.focus_bottom_frame.grid(
            row=1, column=0, columnspan=3, sticky="nsew", pady=5
        )

        # Split 50/50
        self.focus_bottom_frame.columnconfigure(0, weight=1)
        self.focus_bottom_frame.columnconfigure(1, weight=1)

        # Bottom Left (Prev)
        self.focus_prev_lbl = ttk.Label(
            self.focus_bottom_frame, text="Prev", anchor="center", relief="sunken"
        )
        self.focus_prev_lbl.grid(row=0, column=0, sticky="nsew", padx=5)
        self.focus_prev_lbl.bind(
            "<Button-1>", lambda e: self.on_image_click(self.panel_prev.path)
        )

        # Bottom Right (Next)
        self.focus_next_lbl = ttk.Label(
            self.focus_bottom_frame, text="Next", anchor="center", relief="sunken"
        )
        self.focus_next_lbl.grid(row=0, column=1, sticky="nsew", padx=5)
        self.focus_next_lbl.bind(
            "<Button-1>", lambda e: self.on_image_click(self.panel_next.path)
        )

        # Add resize handlers for dynamic scaling
        self.focus_curr_lbl.bind(
            "<Configure>", lambda e: self.on_focus_label_resize(e, self.focus_curr_lbl)
        )
        self.focus_prev_lbl.bind(
            "<Configure>", lambda e: self.on_focus_label_resize(e, self.focus_prev_lbl)
        )
        self.focus_next_lbl.bind(
            "<Configure>", lambda e: self.on_focus_label_resize(e, self.focus_next_lbl)
        )

        # Keyboard Bindings for Focus Mode
        self.focus_frame.bind("<Left>", lambda e: self.prev_candidate())
        self.focus_frame.bind("<Right>", lambda e: self.next_candidate())
        self.focus_frame.bind("<Delete>", lambda e: self.delete_current_candidate())

    def toggle_focus_mode(self):
        self.focus_mode = not self.focus_mode

        # Access MainApp to toggle sidebar
        # self.parent is content_area, self.parent.master is MainApp
        main_app = self.parent.master

        if self.focus_mode:
            # Enable Focus Mode
            if hasattr(main_app, "toggle_sidebar"):
                main_app.toggle_sidebar(False)

            self.notebook.pack_forget()
            self.focus_frame.pack(fill="both", expand=True)
            self.focus_frame.focus_set()  # Enable keyboard events

            # Reload images to ensure they are sized correctly for Focus Mode (Equal sizes)
            if self.panel_curr.path:
                self.load_triplet_view(self.panel_curr.path)
            else:
                self.refresh_active_view()
        else:
            # Disable Focus Mode
            self.focus_frame.pack_forget()
            self.notebook.pack(fill="both", expand=True)

            if hasattr(main_app, "toggle_sidebar"):
                main_app.toggle_sidebar(True)

            # Reload images to ensure they are sized correctly for Standard Mode (Large Main, Small Neighbors)
            if self.panel_curr.path:
                self.load_triplet_view(self.panel_curr.path)
            else:
                self.refresh_active_view()

    def create_image_panel(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title)

        # Image Label (Placeholder)
        lbl = ttk.Label(frame, text="No Image", anchor="center")
        lbl.pack(fill="both", expand=True)

        # Details
        details = ttk.Label(frame, text="", font=("Helvetica", 9))
        details.pack(fill="x")

        frame.img_lbl = lbl  # Store ref
        frame.details_lbl = details  # Store ref
        frame.path = None  # Initialize path
        frame.pil_image = None  # Reference to unscaled base image
        frame.tk_image = None

        # Responsive resize handler
        frame.bind("<Configure>", lambda e: self.on_panel_resize(e, frame))

        # Bind click to fullscreen
        lbl.bind("<Button-1>", lambda e: self.on_thumbnail_single_click(e, frame))
        lbl.bind(
            "<Double-Button-1>", lambda e: self.on_thumbnail_double_click(e, frame)
        )

        return frame

    def on_panel_resize(self, event, panel):
        """Called when a panel resizes. Triggers image rescaling if available."""
        if hasattr(self, "_resize_timer_" + str(id(panel))):
            self.after_cancel(getattr(self, "_resize_timer_" + str(id(panel))))

        # Debounce the resize to prevent lag
        timer_id = self.after(100, lambda: self.scale_image_to_panel(panel))
        setattr(self, "_resize_timer_" + str(id(panel)), timer_id)

    def scale_image_to_panel(self, panel):
        """Scales the panel's PIL image to fit its current label dimensions."""
        if not hasattr(panel, "pil_image") or not panel.pil_image:
            return

        lbl = panel.img_lbl
        lbl.update_idletasks()  # Ensure dimensions are correct

        # Get dimensions of the label (the container)
        w = lbl.winfo_width()
        h = lbl.winfo_height()

        # Fallback to sensible default if container is uninitialized (e.g. 1x1)
        if w < 10 or h < 10:
            w, h = panel.pil_image.size

        try:
            img_copy = panel.pil_image.copy()
            img_copy.thumbnail((w, h), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img_copy)

            lbl.config(image=tk_img, text="")
            lbl.image = tk_img  # Keep reference to prevent garbage collection
        except Exception as e:
            logger.error(f"Error scaling panel image: {e}")

    def on_focus_label_resize(self, event, lbl):
        """Called when a focus mode label resizes."""
        if hasattr(self, "_resize_timer_f_" + str(id(lbl))):
            self.after_cancel(getattr(self, "_resize_timer_f_" + str(id(lbl))))

        timer_id = self.after(100, lambda: self.scale_image_to_focus_label(lbl))
        setattr(self, "_resize_timer_f_" + str(id(lbl)), timer_id)

    def scale_image_to_focus_label(self, lbl):
        """Scales the PIL image stored on a focus label to fit its dimensions."""
        if not hasattr(lbl, "pil_image") or not lbl.pil_image:
            return

        lbl.update_idletasks()
        w = lbl.winfo_width()
        h = lbl.winfo_height()

        if w < 10 or h < 10:
            w, h = lbl.pil_image.size

        try:
            img_copy = lbl.pil_image.copy()
            img_copy.thumbnail((w, h), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img_copy)

            lbl.config(image=tk_img, text="")
            lbl.image = tk_img
        except Exception as e:
            logger.error(f"Error scaling focus label image: {e}")

    def on_thumbnail_single_click(self, event, frame):
        if not frame.path:
            return
        self._pending_click_path = frame.path
        # Delay to detect double click
        self._pending_click_id = self.after(
            250, lambda: self.open_fullscreen(frame.path, "fit")
        )

    def on_thumbnail_double_click(self, event, frame):
        if not frame.path:
            return
        # Cancel single click
        if hasattr(self, "_pending_click_id"):
            self.after_cancel(self._pending_click_id)
            del self._pending_click_id

        # Calculate coordinates
        lbl = event.widget
        rx, ry = 0.5, 0.5

        if hasattr(lbl, "image") and lbl.image:
            img_w = lbl.image.width()
            img_h = lbl.image.height()
            lbl_w = lbl.winfo_width()
            lbl_h = lbl.winfo_height()

            # Image is centered
            x_start = (lbl_w - img_w) // 2
            y_start = (lbl_h - img_h) // 2

            click_x = event.x - x_start
            click_y = event.y - y_start

            rx = click_x / img_w
            ry = click_y / img_h

            # Clamp
            rx = max(0.0, min(1.0, rx))
            ry = max(0.0, min(1.0, ry))

        self.open_fullscreen(frame.path, "100%", (rx, ry))

    def on_image_click(self, path):
        if path and path.exists():
            self.open_fullscreen(path, "fit")

    def open_fullscreen(self, path, mode, focus=(0.5, 0.5)):
        # Check if file exists
        if path and path.exists():
            FullscreenViewer(self, path, initial_mode=mode, focus_point=focus)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)
            self._load_folder_contents(folder)

    def _load_folder_contents(self, folder_path):
        """Finds all supported images in the selected folder and populates the Review tab."""
        # Block the UI briefly
        self.config(cursor="watch")
        self.update()

        p = Path(folder_path)
        extensions = {
            ".jpg", ".jpeg", ".tif", ".tiff", ".nef",
            ".cr2", ".arw", ".dng", ".raw", ".heic", ".heif", ".png", ".webp"
        }
        files = [f for f in p.rglob("*") if f.suffix.lower() in extensions]
        files.sort(key=lambda x: x.name)

        self.sorted_files = files
        self.candidates = files.copy()
        self.scan_results = []
        self.files_map = {}

        self.candidate_listbox.delete(0, "end")

        for f in self.sorted_files:
            # Initialize with N/A score and empty EXIF (fetch EXIF asynchronously if needed later)
            res = {"path": f, "score": "N/A", "exif": {}}
            self.files_map[f] = res
            self.candidate_listbox.insert("end", f"{f.name} (Sharpness Score: N/A)")

        if self.candidates:
            self.notebook.tab(2, state="normal")
            self.log(f"Loaded {len(self.candidates)} images. Ready for review.")

            # Select first item
            self.candidate_listbox.selection_set(0)
            self.on_candidate_select(None)
        else:
            self.notebook.tab(2, state="disabled")
            self.log("No supported images found in the selected folder.")
            messagebox.showinfo("Folder Load", "No supported images found in the selected folder.")

        # Restore UI cursor
        self.config(cursor="")
        self.update()

    def log(self, msg):
        self.log_queue.put(msg)

    def update_log_view(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass

        if self.is_scanning:
            self.after(100, self.update_log_view)

    def start_scan(self):
        folder = self.folder_var.get()
        if not folder or not Path(folder).exists():
            messagebox.showerror("Error", "Please select a valid folder.")
            return

        self.is_scanning = True
        self.stop_event.clear()

        # Switch to Review Tab (as requested)
        self.notebook.tab(2, state="normal")
        self.notebook.select(2)
        # We also enable Scan Tab so the user can look at the raw logs if they want to
        self.notebook.tab(1, state="normal")
        self.notebook.tab(0, state="disabled")

        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")

        self.progress_var.set(0)
        self.review_progress_var.set(0)
        self.review_status_lbl.config(text="Scan Progress: 0%")
        # We don't reset these because they were populated during _load_folder_contents
        # self.scan_results = []
        # self.files_map = {}
        # self.candidates = []
        # self.candidate_listbox.delete(0, "end")
        self.has_switched_to_review = False

        # Reset cache
        self.image_cache.clear()
        with self.preloader_queue.mutex:
            self.preloader_queue.queue.clear()

        # Switch to review tab immediately as requested
        self.switch_to_review_mode()

        # Parse grid size in main thread
        grid_str = self.grid_size_var.get()
        try:
            # Extract first digit from "4x4" -> 4
            grid_size = int(grid_str.split("x")[0])
        except (ValueError, IndexError):
            grid_size = 1
            self.log(f"Warning: Invalid grid size '{grid_str}', defaulting to 1x1")

        # Pass the tool configuration
        tools = {
            "sharpness": self.tool_sharpness_var.get()
        }

        threading.Thread(
            target=self.run_scan_thread, args=(folder, grid_size, tools), daemon=True
        ).start()
        self.after(100, self.update_log_view)

    def cancel_scan(self):
        if self.is_scanning:
            self.stop_event.set()
            self.log("Stopping scan...")

    def run_scan_thread(self, folder_path, grid_size, tools):
        self.log(f"Scanning folder: {folder_path}")

        try:
            files = self.sorted_files

            if not files:
                self.log("No images to scan.")
                self.parent.after(0, self.scan_finished)
                return

            self.log(f"Scanning {len(files)} images. Starting analysis...")

            total = len(files)

            for i, f in enumerate(files):
                if self.stop_event.is_set():
                    self.log("Scan cancelled.")
                    break

                self.log(f"Analyzing {f.name}...")

                score = "N/A"
                if tools.get("sharpness", False):
                    score = calculate_sharpness(f, grid_size=grid_size)

                # Fetch EXIF
                exif = get_exif_data(f) or {}

                res = {"path": f, "score": score, "exif": exif}

                # Send result to main thread
                self.parent.after(
                    0,
                    lambda r=res, idx=i + 1, t=total: self.process_scan_result(
                        r, idx, t
                    ),
                )

            self.log("Scan complete.")

        except Exception as e:
            self.log(f"Error during scan: {e}")
            import traceback

            traceback.print_exc()

        self.parent.after(0, self.scan_finished)

    def process_scan_result(self, result, current_idx, total_count):
        if not self.is_scanning:
            return

        # Update lists
        # We replace the entry instead of appending it if it already exists
        path = result["path"]

        # update scan results list
        found = False
        for i, r in enumerate(self.scan_results):
            if r["path"] == path:
                self.scan_results[i] = result
                found = True
                break
        if not found:
            self.scan_results.append(result)

        self.files_map[path] = result

        # Update Progress
        pct = (current_idx / total_count) * 100
        self.progress_var.set(pct)
        self.review_progress_var.set(pct)
        self.review_status_lbl.config(
            text=f"Scan Progress: {int(pct)}% ({current_idx}/{total_count})"
        )

        # Update listbox entry
        # The file is already in candidates (from _load_folder_contents)
        if path in self.candidates:
            idx = self.candidates.index(path)
            score_val = result['score']
            if isinstance(score_val, float):
                score_text = f"{score_val:.1f}"
            else:
                score_text = "N/A"

            # Delete and reinsert to update text, but maintain selection if it was selected
            is_selected = (self.candidate_listbox.curselection() == (idx,))
            self.candidate_listbox.delete(idx)
            self.candidate_listbox.insert(idx, f"{path.name} (Sharpness Score: {score_text})")
            if is_selected:
                self.candidate_listbox.selection_set(idx)
                # Refresh metadata label
                self.update_metadata_label(path)

        # If we are already reviewing, this new candidate might be the "Next" one for the current view.
        if self.has_switched_to_review:
            sel = self.candidate_listbox.curselection()
            if sel:
                cur_sel_idx = sel[0]
                new_idx = self.candidates.index(path)
                # If the new candidate is within the lookahead window (next 3), queue it
                if cur_sel_idx < new_idx <= cur_sel_idx + 3:
                    self.queue_candidate(new_idx)

        # Update button states
        self.update_button_states()

    def switch_to_review_mode(self):
        self.has_switched_to_review = True
        self.notebook.tab(2, state="normal")
        self.notebook.select(2)
        self.log("Auto-switching to Review mode.")

        # Select the first one if nothing selected
        if not self.candidate_listbox.curselection():
            self.candidate_listbox.selection_set(0)
            self.on_candidate_select(None)

    def scan_finished(self):
        self.is_scanning = False
        self.notebook.tab(0, state="normal")

        self.review_status_lbl.config(text="Scan Complete.")

        if self.candidates:
            if not self.has_switched_to_review:
                self.switch_to_review_mode()
            self.log(f"Found {len(self.candidates)} images for review.")
        else:
            messagebox.showinfo(
                "Result",
                "No supported images found.",
            )
            self.notebook.select(0)

    def on_candidate_select(self, event):
        sel = self.candidate_listbox.curselection()
        if not sel:
            self.update_button_states()
            return

        idx = sel[0]
        current_path = self.candidates[idx]
        self.load_triplet_view(current_path)
        self.update_button_states()

        # Trigger preloader for next candidates
        self.preload_next_candidates(idx)

    def preload_next_candidates(self, current_idx):
        # Clear queue to prioritize new requests (user jumped to new location)
        with self.preloader_queue.mutex:
            self.preloader_queue.queue.clear()

        with self.full_res_queue.mutex:
            self.full_res_queue.queue.clear()

        # 1. Enqueue current triplet for full resolution loading IMMEDIATELY
        # This ensures the active image and neighbors are ready for fullscreen
        try:
            c_path = self.candidates[current_idx]
            self.queue_full_res_candidate(c_path)

            # Find neighbors for full res queue
            if c_path in self.sorted_files:
                f_idx = self.sorted_files.index(c_path)
                if f_idx < len(self.sorted_files) - 1:
                    self.queue_full_res_candidate(self.sorted_files[f_idx + 1])
                if f_idx > 0:
                    self.queue_full_res_candidate(self.sorted_files[f_idx - 1])
        except IndexError:
            pass

        # 2. Look ahead for next 3 candidates for preview loading
        count = 0
        for i in range(current_idx + 1, len(self.candidates)):
            if count >= 3:
                break
            self.queue_candidate(i)
            count += 1

    def queue_candidate(self, idx):
        try:
            c_path = self.candidates[idx]
            # Find neighbors
            if c_path in self.sorted_files:
                f_idx = self.sorted_files.index(c_path)

                # Prioritize: Candidate -> Next -> Prev
                self.preloader_queue.put(c_path)

                if f_idx < len(self.sorted_files) - 1:
                    self.preloader_queue.put(self.sorted_files[f_idx + 1])

                if f_idx > 0:
                    self.preloader_queue.put(self.sorted_files[f_idx - 1])
        except IndexError:
            pass

    def queue_full_res_candidate(self, path):
        if path is None:
            return
        self.full_res_queue.put(path)

    def start_preloader(self):
        threading.Thread(target=self.run_preloader, daemon=True).start()

    def start_full_res_preloader(self):
        threading.Thread(target=self.run_full_res_preloader, daemon=True).start()

    def run_preloader(self):
        CACHE_SIZE = (1200, 900)
        while True:
            try:
                path = self.preloader_queue.get()
                if path is None:
                    continue

                with self.cache_lock:
                    if path in self.image_cache:
                        continue

                try:
                    img = load_image_preview(path, max_size=CACHE_SIZE)
                    if img:
                        with self.cache_lock:
                            self.image_cache[path] = img
                            # Prune
                            if len(self.image_cache) > 30:
                                first = next(iter(self.image_cache))
                                del self.image_cache[first]
                except Exception:
                    pass
            except Exception:
                pass

    def run_full_res_preloader(self):
        # Limit full res cache to 5 images (approx 500MB-1GB depending on resolution)
        CACHE_LIMIT = 5

        while True:
            try:
                path = self.full_res_queue.get()
                if path is None:
                    continue

                with self.full_res_lock:
                    if path in self.full_res_cache:
                        continue

                try:
                    # Load full resolution
                    img = load_image_preview(path, full_res=True)
                    if img:
                        with self.full_res_lock:
                            self.full_res_cache[path] = img
                            # Prune (simple FIFO for now, or just random pop)
                            if len(self.full_res_cache) > CACHE_LIMIT:
                                first = next(iter(self.full_res_cache))
                                del self.full_res_cache[first]
                except Exception as e:
                    logger.error(f"Full res load error: {e}")
            except Exception:
                pass

    def update_button_states(self):
        sel = self.candidate_listbox.curselection()
        if not sel:
            try:
                self.prev_btn.state(["disabled"])
                self.next_btn.state(["disabled"])
                self.del_btn.state(["disabled"])
            except AttributeError:
                pass  # UI not ready
            return

        idx = sel[0]
        total = self.candidate_listbox.size()

        if idx > 0:
            self.prev_btn.state(["!disabled"])
        else:
            self.prev_btn.state(["disabled"])

        if idx < total - 1:
            self.next_btn.state(["!disabled"])
        else:
            self.next_btn.state(["disabled"])

        self.del_btn.state(["!disabled"])

    def load_triplet_view(self, current_path):
        # Find index in full sorted list
        if current_path not in self.sorted_files:
            return

        full_idx = self.sorted_files.index(current_path)

        prev_path = self.sorted_files[full_idx - 1] if full_idx > 0 else None
        next_path = (
            self.sorted_files[full_idx + 1]
            if full_idx < len(self.sorted_files) - 1
            else None
        )

        # Store paths in panels for fullscreen access
        self.panel_prev.path = prev_path
        self.panel_curr.path = current_path
        self.panel_next.path = next_path

        # Load Images in background to prevent UI freeze
        # Set placeholders first
        self.set_placeholder(self.panel_prev, prev_path)
        self.set_placeholder(self.panel_curr, current_path)
        self.set_placeholder(self.panel_next, next_path)

        # Update Metadata immediately
        self.update_metadata_label(current_path)

        # Clear current images to show loading state (avoids metadata/image mismatch)
        self.current_triplet_images = (None, None, None)
        self.refresh_active_view()

        # Determine sizes based on mode
        # User requested "Same Size" for all 3 images in Standard Mode and Focus Mode
        # Increased to utilize more space on 2K monitors (around 800px width as requested)
        common_size = (800, 600)  # Width, Height

        if self.focus_mode:
            size_curr = common_size
            size_neighbors = common_size
        else:
            size_curr = common_size
            size_neighbors = common_size

        # Start background thread for loading images
        threading.Thread(
            target=self.load_images_background,
            args=(prev_path, current_path, next_path, size_curr, size_neighbors),
            daemon=True,
        ).start()

    def set_placeholder(self, panel, path):
        lbl = panel.img_lbl
        details = panel.details_lbl

        if path is None:
            lbl.config(image="", text="No Image")
            details.config(text="")
            return

        res = self.files_map.get(path)
        score_txt = "N/A"

        if res:
            score_val = res.get('score', "N/A")
            if isinstance(score_val, float):
                score_txt = f"{score_val:.1f}"
            else:
                score_txt = str(score_val)

        details.config(text=f"{path.name}\nSharpness Score: {score_txt}", foreground="black")
        lbl.config(image="", text="Loading...")

    def _format_meta(self, val, unit=""):
        if val is None or val == "N/A":
            return "N/A"
        if isinstance(val, float):
            # Try to format nicely
            if unit == "s":
                if val < 1.0 and val > 0:
                    # Fraction for shutter speed
                    denom = int(round(1.0 / val))
                    return f"1/{denom}s"
                return f"{val}s"
            if unit == "mm":
                return f"{val:.0f}mm"
            if unit == "f/":
                return f"f/{val:.1f}"
            return f"{val:.1f}"
        return str(val)

    def update_metadata_label(self, current_path):
        res = self.files_map.get(current_path)
        if res:
            exif = res.get("exif", {})
            score_val = res.get("score", "N/A")

            if isinstance(score_val, float):
                score_str = f"{score_val:.1f}"
            else:
                score_str = str(score_val)

            iso = self._format_meta(exif.get("ISO"), "")
            shutter = self._format_meta(exif.get("Shutter Speed"), "s")
            aperture = self._format_meta(exif.get("Aperture"), "f/")
            focal = self._format_meta(exif.get("Focal Length"), "mm")

            # ISO: 100 | 1/200s | f/2.8 | 50mm
            meta_str = f"ISO: {iso} | {shutter} | {aperture} | {focal}"

            txt = f"File: {current_path.name}\n" f"Sharpness Score: {score_str}\n" f"{meta_str}"
            self.meta_lbl.config(text=txt)

            # Update Focus Mode labels if they exist
            if hasattr(self, "focus_score_lbl"):
                self.focus_score_lbl.config(
                    text=f"Sharpness Score: {score_str}", foreground="black"
                )
                self.focus_cat_lbl.config(text="", foreground="black")
                self.focus_meta_lbl.config(text=meta_str)
                self.focus_filename_lbl.config(text=current_path.name)

    def load_images_background(
        self, prev_path, curr_path, next_path, size_curr, size_neighbors
    ):
        CACHE_SIZE = (1200, 900)

        def get_image(path, requested_size):
            if path is None:
                return None

            img = None

            # 1. Try Cache
            with self.cache_lock:
                if path in self.image_cache:
                    img = self.image_cache[path]

            # 2. Load if not in cache
            if not img:
                try:
                    img = load_image_preview(path, max_size=CACHE_SIZE)
                    if img:
                        with self.cache_lock:
                            self.image_cache[path] = img
                            if len(self.image_cache) > 30:
                                first = next(iter(self.image_cache))
                                del self.image_cache[first]
                except Exception as e:
                    logger.error(f"Error loading {path}: {e}")

            if not img:
                return None

            # 3. Return the base unscaled PIL image.
            # We scale it dynamically in the main thread to fit the UI panel perfectly.
            try:
                img_copy = img.copy()
                img_copy.thumbnail(requested_size, Image.Resampling.LANCZOS)
                return img_copy
            except Exception as e:
                logger.error(f"Error preparing {path}: {e}")
                return None

        p_img = get_image(prev_path, size_neighbors)
        c_img = get_image(curr_path, size_curr)
        n_img = get_image(next_path, size_neighbors)

        # Update UI in main thread
        self.parent.after(0, lambda: self.update_panels_final(p_img, c_img, n_img))

    def update_panels_final(self, p_img, c_img, n_img):
        self.current_triplet_images = (p_img, c_img, n_img)
        self.refresh_active_view()

    def refresh_active_view(self):
        p_img, c_img, n_img = self.current_triplet_images

        if self.focus_mode:
            # Update Focus Mode
            def set_lbl(lbl, img, default_text):
                lbl.pil_image = img  # Store unscaled image for resize events

                if img:
                    self.scale_image_to_focus_label(lbl)
                else:
                    lbl.config(image="", text=default_text)

            set_lbl(self.focus_prev_lbl, p_img, "Prev")
            set_lbl(self.focus_curr_lbl, c_img, "No Image")
            set_lbl(self.focus_next_lbl, n_img, "Next")
        else:
            # Helper to set image on a label
            def set_panel_img(panel, img):
                lbl = panel.img_lbl
                panel.pil_image = img  # Store raw PIL image

                if img:
                    # Initial display before resize event fires
                    self.scale_image_to_panel(panel)
                elif lbl.cget("text") == "Loading...":
                    lbl.config(image="", text="Preview\nUnavailable")

            set_panel_img(self.panel_prev, p_img)
            set_panel_img(self.panel_curr, c_img)
            set_panel_img(self.panel_next, n_img)

    def prev_candidate(self):
        sel = self.candidate_listbox.curselection()
        if sel and sel[0] > 0:
            self.candidate_listbox.selection_clear(0, "end")
            self.candidate_listbox.selection_set(sel[0] - 1)
            self.candidate_listbox.event_generate("<<ListboxSelect>>")
            self.candidate_listbox.see(sel[0] - 1)

    def next_candidate(self):
        sel = self.candidate_listbox.curselection()
        if sel and sel[0] < self.candidate_listbox.size() - 1:
            self.candidate_listbox.selection_clear(0, "end")
            self.candidate_listbox.selection_set(sel[0] + 1)
            self.candidate_listbox.event_generate("<<ListboxSelect>>")
            self.candidate_listbox.see(sel[0] + 1)

    def delete_current_candidate(self):
        sel = self.candidate_listbox.curselection()
        if not sel:
            return

        idx = sel[0]
        path = self.candidates[idx]

        if messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to move '{path.name}' and related files to trash?",
        ):
            related = find_related_files(path)
            failed_trash = []

            for f in related:
                try:
                    send2trash.send2trash(str(f))
                    self.log(f"Moved to trash: {f}")
                except Exception as e:
                    failed_trash.append(f)
                    msg = f"Trash failed for {f}: {e}"
                    self.log(msg)

            if failed_trash:
                msg = (
                    f"Failed to move {len(failed_trash)} related file(s) to trash (e.g. network drive).\n"
                    "Do you want to PERMANENTLY delete them?"
                )
                if messagebox.askyesno("Trash Failed", msg):
                    for f in failed_trash:
                        try:
                            if f.exists():
                                f.unlink()
                                self.log(f"Permanently deleted: {f}")
                        except Exception as e:
                            msg = f"Delete failed for {f}: {e}"
                            self.log(msg)

            # Check if all files are gone
            remaining = [f for f in related if f.exists()]
            if not remaining:
                # Update UI
                self.candidates.pop(idx)
                self.candidate_listbox.delete(idx)
                if path in self.sorted_files:
                    self.sorted_files.remove(path)
                if path in self.files_map:
                    del self.files_map[path]

                # Select next if available, or prev
                if self.candidates:
                    new_idx = idx if idx < len(self.candidates) else idx - 1
                    self.candidate_listbox.selection_set(new_idx)
                    self.on_candidate_select(None)
                else:
                    self.panel_curr.img_lbl.config(image="", text="No Candidates")
                    self.panel_prev.img_lbl.config(image="", text="")
                    self.panel_next.img_lbl.config(image="", text="")

                    self.panel_curr.path = None
                    self.panel_prev.path = None
                    self.panel_next.path = None
