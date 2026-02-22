import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import logging
from pathlib import Path
from PIL import Image, ImageTk
import send2trash

# Local imports
from image_metadata_analyzer.sharpness import (
    calculate_sharpness,
    categorize_sharpness,
    SharpnessCategories,
    find_related_files,
)
from image_metadata_analyzer.reader import get_exif_data
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
        self.default_grid_size = "4x4"

        self.setup_ui()

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

        # Thresholds
        group = ttk.LabelFrame(container, text="Sharpness Thresholds", padding=10)
        group.grid(row=1, column=0, columnspan=3, sticky="ew", pady=20)

        # Blur Threshold
        ttk.Label(group, text="Blurry Limit (<):").grid(row=0, column=0, padx=5)
        self.blur_thresh_var = tk.DoubleVar(value=self.default_blur_threshold)
        scale_blur = tk.Scale(
            group,
            variable=self.blur_thresh_var,
            from_=0,
            to=2000,
            orient="horizontal",
            length=200,
        )
        scale_blur.grid(row=0, column=1, padx=5)
        ttk.Entry(group, textvariable=self.blur_thresh_var, width=8).grid(
            row=0, column=2, padx=5
        )

        # Sharp Threshold
        ttk.Label(group, text="Sharp Limit (>):").grid(row=1, column=0, padx=5)
        self.sharp_thresh_var = tk.DoubleVar(value=self.default_sharp_threshold)
        scale_sharp = tk.Scale(
            group,
            variable=self.sharp_thresh_var,
            from_=0,
            to=5000,
            orient="horizontal",
            length=200,
        )
        scale_sharp.grid(row=1, column=1, padx=5)
        ttk.Entry(group, textvariable=self.sharp_thresh_var, width=8).grid(
            row=1, column=2, padx=5
        )

        ttk.Label(
            group,
            text="(Scores depend on image resolution. Default values are estimates.)",
        ).grid(row=2, column=0, columnspan=3, pady=5)

        # Grid Size Selection
        frame_grid = ttk.Frame(container)
        frame_grid.grid(row=2, column=0, columnspan=3, pady=10, sticky="ew")

        ttk.Label(frame_grid, text="Grid Analysis Size:").pack(side="left", padx=5)
        self.grid_size_var = tk.StringVar(value=self.default_grid_size)
        grid_combo = ttk.Combobox(
            frame_grid,
            textvariable=self.grid_size_var,
            values=["1x1 (Global)", "2x2", "3x3", "4x4", "5x5", "8x8"],
            state="readonly",
            width=12,
        )
        grid_combo.pack(side="left", padx=5)
        ttk.Label(
            frame_grid,
            text="(Higher grid size helps find small sharp subjects in blurry backgrounds)",
        ).pack(side="left", padx=5)

        # Start Button
        self.start_btn = ttk.Button(
            container, text="Start Sharpness Scan", command=self.start_scan
        )
        self.start_btn.grid(row=3, column=0, columnspan=3, pady=20)

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

        ttk.Label(self.sidebar, text="Candidates (Blurry/Acceptable)").pack(pady=5)

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

        # Current Candidate (Large, Centered)
        self.panel_curr = self.create_image_panel(
            self.top_container, "Current Candidate"
        )
        self.panel_curr.pack(side="top", fill="both", expand=True)

        # Info & Actions (Below Candidate)
        self.info_frame = ttk.Frame(self.top_container, padding=5)
        self.info_frame.pack(side="top", fill="x", pady=5)

        # Metadata Label
        self.meta_lbl = ttk.Label(
            self.info_frame, text="", font=("Helvetica", 10), justify="center"
        )
        self.meta_lbl.pack(pady=2)

        # Buttons
        btn_frame = ttk.Frame(self.info_frame)
        btn_frame.pack(pady=5)

        self.prev_btn = ttk.Button(
            btn_frame, text="< Prev Candidate", command=self.prev_candidate
        )
        self.prev_btn.pack(side="left", padx=5)
        self.del_btn = ttk.Button(
            btn_frame,
            text="Delete Candidate (Trash)",
            command=self.delete_current_candidate,
        )
        self.del_btn.pack(side="left", padx=20)
        self.next_btn = ttk.Button(
            btn_frame, text="Next Candidate >", command=self.next_candidate
        )
        self.next_btn.pack(side="left", padx=5)

        # --- Bottom Container: Neighbors ---
        self.bottom_container = ttk.Frame(self.preview_area)
        self.bottom_container.pack(side="bottom", fill="x", ipady=5)

        # Neighbors
        self.panel_prev = self.create_image_panel(
            self.bottom_container, "Previous Image"
        )
        self.panel_prev.pack(side="left", fill="both", expand=True, padx=2)

        self.panel_next = self.create_image_panel(self.bottom_container, "Next Image")
        self.panel_next.pack(side="right", fill="both", expand=True, padx=2)

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

        # Bind click to fullscreen
        lbl.bind("<Button-1>", lambda e: self.on_thumbnail_single_click(e, frame))
        lbl.bind(
            "<Double-Button-1>", lambda e: self.on_thumbnail_double_click(e, frame)
        )

        return frame

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

    def open_fullscreen(self, path, mode, focus=(0.5, 0.5)):
        # Check if file exists
        if path and path.exists():
            FullscreenViewer(self, path, initial_mode=mode, focus_point=focus)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

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

        # Switch to Scan Tab
        self.notebook.tab(1, state="normal")
        self.notebook.select(1)
        self.notebook.tab(0, state="disabled")

        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")

        self.progress_var.set(0)
        self.review_progress_var.set(0)
        self.review_status_lbl.config(text="Scan Progress: 0%")
        self.scan_results = []
        self.files_map = {}
        self.candidates = []
        self.candidate_listbox.delete(0, "end")
        self.has_switched_to_review = False

        # Reset cache
        self.image_cache.clear()
        with self.preloader_queue.mutex:
            self.preloader_queue.queue.clear()

        threading.Thread(
            target=self.run_scan_thread, args=(folder,), daemon=True
        ).start()
        self.after(100, self.update_log_view)

    def cancel_scan(self):
        if self.is_scanning:
            self.stop_event.set()
            self.log("Stopping scan...")

    def run_scan_thread(self, folder_path):
        self.log(f"Scanning folder: {folder_path}")

        try:
            p = Path(folder_path)
            # Recursive scan
            extensions = {
                ".jpg",
                ".jpeg",
                ".tif",
                ".tiff",
                ".nef",
                ".cr2",
                ".arw",
                ".dng",
                ".raw",
            }
            files = [f for f in p.rglob("*") if f.suffix.lower() in extensions]

            if not files:
                self.log("No supported images found.")
                self.parent.after(0, self.scan_finished)
                return

            self.log(f"Found {len(files)} images. Starting analysis...")

            # Sort files alphabetically to handle previous/next logic
            files.sort(key=lambda x: x.name)
            self.sorted_files = files

            total = len(files)
            blur_t = self.blur_thresh_var.get()
            sharp_t = self.sharp_thresh_var.get()

            # Parse grid size
            grid_str = self.grid_size_var.get()
            try:
                # Extract first digit from "4x4" -> 4
                grid_size = int(grid_str.split("x")[0])
            except (ValueError, IndexError):
                grid_size = 1
                self.log(f"Warning: Invalid grid size '{grid_str}', defaulting to 1x1")

            for i, f in enumerate(files):
                if self.stop_event.is_set():
                    self.log("Scan cancelled.")
                    break

                self.log(f"Analyzing {f.name}...")

                # Sharpness
                score = calculate_sharpness(f, grid_size=grid_size)
                cat = categorize_sharpness(score, blur_t, sharp_t)

                # Exif (basic)
                exif = get_exif_data(f) or {}

                res = {"path": f, "score": score, "category": cat, "exif": exif}

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
        self.scan_results.append(result)
        self.files_map[result["path"]] = result

        # Update Progress
        pct = (current_idx / total_count) * 100
        self.progress_var.set(pct)
        self.review_progress_var.set(pct)
        self.review_status_lbl.config(
            text=f"Scan Progress: {int(pct)}% ({current_idx}/{total_count})"
        )

        # Handle Candidate
        if result["category"] in [
            SharpnessCategories.BLURRY,
            SharpnessCategories.ACCEPTABLE,
        ]:
            path = result["path"]
            self.candidates.append(path)

            # Add to listbox
            cat_name = SharpnessCategories.get_name(result["category"])
            self.candidate_listbox.insert("end", f"{path.name} ({cat_name})")

            # Color code
            color = SharpnessCategories.get_color(result["category"])
            idx = self.candidate_listbox.size() - 1
            self.candidate_listbox.itemconfig(idx, {"fg": color})

            # Auto-switch to review if we have enough candidates
            # The user requested switching "After the first 3 were scanned"
            if len(self.candidates) >= 3 and not self.has_switched_to_review:
                self.switch_to_review_mode()

            # If we are already reviewing, this new candidate might be the "Next" one for the current view.
            if self.has_switched_to_review:
                sel = self.candidate_listbox.curselection()
                if sel:
                    current_idx = sel[0]
                    new_idx = len(self.candidates) - 1
                    # If the new candidate is within the lookahead window (next 3), queue it
                    if current_idx < new_idx <= current_idx + 3:
                        self.queue_candidate(new_idx)

            # Update button states (e.g., enable "Next" if we were at the end)
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
            self.log(f"Found {len(self.candidates)} candidates for review.")
        else:
            messagebox.showinfo(
                "Result",
                "No blurry or 'acceptable' images found based on current thresholds.",
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
        CACHE_SIZE = (800, 600)
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

        # Start background thread for loading images
        threading.Thread(
            target=self.load_images_background,
            args=(prev_path, current_path, next_path, (800, 600), (400, 300)),
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
        cat_color = "black"
        score_txt = "N/A"
        cat_name = ""

        if res:
            cat_color = SharpnessCategories.get_color(res["category"])
            score_txt = f"{res['score']:.1f}"
            cat_name = SharpnessCategories.get_name(res["category"])

        details.config(
            text=f"{path.name}\n{cat_name} ({score_txt})", foreground=cat_color
        )
        lbl.config(image="", text="Loading...")

    def update_metadata_label(self, current_path):
        res = self.files_map.get(current_path)
        if res:
            exif = res["exif"]
            score = res["score"]
            aperture = exif.get("FNumber", "N/A")
            shutter = exif.get("ExposureTime", "N/A")
            cat_name = SharpnessCategories.get_name(res["category"])

            txt = (
                f"File: {current_path.name}\n"
                f"Category: {cat_name} (Score: {score:.1f})\n"
                f"Aperture: {aperture}, Shutter: {shutter}"
            )
            self.meta_lbl.config(text=txt)

    def load_images_background(
        self, prev_path, curr_path, next_path, size_curr, size_neighbors
    ):
        CACHE_SIZE = (800, 600)

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

            # 3. Resize for requested size (copy to avoid modifying cached)
            try:
                img_copy = img.copy()
                img_copy.thumbnail(requested_size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img_copy)
            except Exception as e:
                logger.error(f"Error resizing {path}: {e}")
                return None

        p_img = get_image(prev_path, size_neighbors)
        c_img = get_image(curr_path, size_curr)
        n_img = get_image(next_path, size_neighbors)

        # Update UI in main thread
        self.parent.after(0, lambda: self.update_panels_final(p_img, c_img, n_img))

    def update_panels_final(self, p_img, c_img, n_img):
        def set_img(panel, img):
            lbl = panel.img_lbl
            if img:
                lbl.config(image=img, text="")
                lbl.image = img
            elif lbl.cget("text") == "Loading...":
                lbl.config(image="", text="Preview\nUnavailable")

        set_img(self.panel_prev, p_img)
        set_img(self.panel_curr, c_img)
        set_img(self.panel_next, n_img)

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
