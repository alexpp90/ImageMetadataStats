import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import logging
from pathlib import Path
from PIL import Image, ImageTk
import send2trash
import rawpy
import numpy as np

# Local imports
from image_metadata_analyzer.sharpness import (
    calculate_sharpness, categorize_sharpness, SharpnessCategories,
    find_related_files
)
from image_metadata_analyzer.reader import get_exif_data
from image_metadata_analyzer.utils import load_image_preview

logger = logging.getLogger(__name__)

class SharpnessTool(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.log_queue = queue.Queue()
        self.is_scanning = False
        self.stop_event = threading.Event()

        # State
        self.scan_results = [] # List of dicts: {path, score, category, exif}
        self.files_map = {} # path -> result dict
        self.sorted_files = [] # List of paths sorted by filename
        self.candidates = [] # List of paths that are category 2 or 3

        # Caching and Review State
        self.image_cache = {}
        self.cache_lock = threading.Lock()
        self.preloader_queue = queue.Queue()
        self.has_switched_to_review = False

        # Focus Mode State
        self.focus_mode = False
        self.current_triplet_images = (None, None, None)

        self.start_preloader()

        # Defaults
        self.default_blur_threshold = 100.0
        self.default_sharp_threshold = 500.0
        self.default_grid_size = "4x4"

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
        ttk.Label(container, text="Images Folder:").grid(row=0, column=0, sticky="w", pady=5)
        self.folder_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.folder_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(container, text="Browse...", command=self.browse_folder).grid(row=0, column=2, pady=5)

        # Thresholds
        group = ttk.LabelFrame(container, text="Sharpness Thresholds", padding=10)
        group.grid(row=1, column=0, columnspan=3, sticky="ew", pady=20)

        # Blur Threshold
        ttk.Label(group, text="Blurry Limit (<):").grid(row=0, column=0, padx=5)
        self.blur_thresh_var = tk.DoubleVar(value=self.default_blur_threshold)
        scale_blur = tk.Scale(group, variable=self.blur_thresh_var, from_=0, to=2000, orient="horizontal", length=200)
        scale_blur.grid(row=0, column=1, padx=5)
        ttk.Entry(group, textvariable=self.blur_thresh_var, width=8).grid(row=0, column=2, padx=5)

        # Sharp Threshold
        ttk.Label(group, text="Sharp Limit (>):").grid(row=1, column=0, padx=5)
        self.sharp_thresh_var = tk.DoubleVar(value=self.default_sharp_threshold)
        scale_sharp = tk.Scale(group, variable=self.sharp_thresh_var, from_=0, to=5000, orient="horizontal", length=200)
        scale_sharp.grid(row=1, column=1, padx=5)
        ttk.Entry(group, textvariable=self.sharp_thresh_var, width=8).grid(row=1, column=2, padx=5)

        ttk.Label(group, text="(Scores depend on image resolution. Default values are estimates.)").grid(row=2, column=0, columnspan=3, pady=5)

        # Grid Size Selection
        frame_grid = ttk.Frame(container)
        frame_grid.grid(row=2, column=0, columnspan=3, pady=10, sticky="ew")

        ttk.Label(frame_grid, text="Grid Analysis Size:").pack(side="left", padx=5)
        self.grid_size_var = tk.StringVar(value=self.default_grid_size)
        grid_combo = ttk.Combobox(frame_grid, textvariable=self.grid_size_var,
                                  values=["1x1 (Global)", "2x2", "3x3", "4x4", "5x5", "8x8"],
                                  state="readonly", width=12)
        grid_combo.pack(side="left", padx=5)
        ttk.Label(frame_grid, text="(Higher grid size helps find small sharp subjects in blurry backgrounds)").pack(side="left", padx=5)

        # Start Button
        self.start_btn = ttk.Button(container, text="Start Sharpness Scan", command=self.start_scan)
        self.start_btn.grid(row=3, column=0, columnspan=3, pady=20)

    def setup_scan_ui(self):
        container = ttk.Frame(self.scan_frame, padding=20)
        container.pack(fill="both", expand=True)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(container, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=20)

        self.scan_status_lbl = ttk.Label(container, text="Ready...")
        self.scan_status_lbl.pack(pady=5)

        # Log area
        self.log_text = tk.Text(container, height=15, state="disabled")
        self.log_text.pack(fill="both", expand=True, pady=10)

        self.cancel_btn = ttk.Button(container, text="Cancel Scan", command=self.cancel_scan)
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

        self.review_status_lbl = ttk.Label(self.scan_progress_frame, text="Scan Progress: 0%")
        self.review_status_lbl.pack(side="top", anchor="w")

        self.review_progress_var = tk.DoubleVar()
        self.review_progress_bar = ttk.Progressbar(self.scan_progress_frame, variable=self.review_progress_var, maximum=100)
        self.review_progress_bar.pack(fill="x")

        # Scrollbar and Listbox
        sb = ttk.Scrollbar(self.sidebar)
        sb.pack(side="right", fill="y")

        self.candidate_listbox = tk.Listbox(self.sidebar, yscrollcommand=sb.set, selectmode="single")
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
        self.panel_curr = self.create_image_panel(self.top_container, "Current Candidate")
        self.panel_curr.pack(side="top", fill="both", expand=True)

        # Info & Actions (Below Candidate)
        self.info_frame = ttk.Frame(self.top_container, padding=5)
        self.info_frame.pack(side="top", fill="x", pady=5)

        # Metadata Label
        self.meta_lbl = ttk.Label(self.info_frame, text="", font=("Helvetica", 10), justify="center")
        self.meta_lbl.pack(pady=2)

        # Buttons
        btn_frame = ttk.Frame(self.info_frame)
        btn_frame.pack(pady=5)

        self.prev_btn = ttk.Button(btn_frame, text="< Prev Candidate", command=self.prev_candidate)
        self.prev_btn.pack(side="left", padx=5)
        self.del_btn = ttk.Button(btn_frame, text="Delete Candidate (Trash)", command=self.delete_current_candidate)
        self.del_btn.pack(side="left", padx=20)
        self.next_btn = ttk.Button(btn_frame, text="Next Candidate >", command=self.next_candidate)
        self.next_btn.pack(side="left", padx=5)

        self.focus_toggle_btn = ttk.Button(btn_frame, text="Focus Mode", command=self.toggle_focus_mode)
        self.focus_toggle_btn.pack(side="left", padx=20)

        # --- Bottom Container: Neighbors ---
        self.bottom_container = ttk.Frame(self.preview_area)
        self.bottom_container.pack(side="bottom", fill="x", ipady=5)

        # Neighbors
        self.panel_prev = self.create_image_panel(self.bottom_container, "Previous Image")
        self.panel_prev.pack(side="left", fill="both", expand=True, padx=2)

        self.panel_next = self.create_image_panel(self.bottom_container, "Next Image")
        self.panel_next.pack(side="right", fill="both", expand=True, padx=2)

    def setup_focus_ui(self):
        """Builds the fullscreen-optimized focus layout."""
        self.focus_frame = ttk.Frame(self)

        # Grid Configuration
        # Row 0: Top (Main), Row 1: Bottom (Neighbors)
        # User requested "Same Size" for all 3 images.
        self.focus_frame.rowconfigure(0, weight=1)
        self.focus_frame.rowconfigure(1, weight=1)

        # Col 0: Left (Prev), Col 1: Center (Main/Spacer), Col 2: Right (Next/Controls)
        self.focus_frame.columnconfigure(0, weight=1)
        self.focus_frame.columnconfigure(1, weight=1)
        self.focus_frame.columnconfigure(2, weight=1)

        # --- Row 0: Main Area ---

        # Left Gutter (Row 0, Col 0) - Nav
        self.focus_left_panel = ttk.Frame(self.focus_frame)
        self.focus_left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.focus_prev_btn = ttk.Button(self.focus_left_panel, text="< Previous", command=self.prev_candidate)
        self.focus_prev_btn.pack(side="top", pady=50)

        # Center (Row 0, Col 1) - Current Candidate
        self.focus_curr_container = ttk.Frame(self.focus_frame)
        self.focus_curr_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        self.focus_curr_lbl = ttk.Label(self.focus_curr_container, text="No Image", anchor="center")
        self.focus_curr_lbl.pack(fill="both", expand=True)
        self.focus_curr_lbl.bind("<Button-1>", lambda e: self.on_image_click(self.panel_curr.path))

        # Right Gutter (Row 0, Col 2) - Controls
        self.focus_right_panel = ttk.Frame(self.focus_frame)
        self.focus_right_panel.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        self.focus_exit_btn = ttk.Button(self.focus_right_panel, text="Exit Focus Mode", command=self.toggle_focus_mode)
        self.focus_exit_btn.pack(side="top", pady=10, fill="x")

        ttk.Separator(self.focus_right_panel, orient="horizontal").pack(fill="x", pady=10)

        self.focus_score_lbl = ttk.Label(self.focus_right_panel, text="Score: --", font=("Helvetica", 12, "bold"))
        self.focus_score_lbl.pack(side="top", pady=5)

        self.focus_cat_lbl = ttk.Label(self.focus_right_panel, text="Category", font=("Helvetica", 10))
        self.focus_cat_lbl.pack(side="top", pady=5)

        self.focus_meta_lbl = ttk.Label(self.focus_right_panel, text="Metadata", justify="left", wraplength=150)
        self.focus_meta_lbl.pack(side="top", pady=20)

        ttk.Separator(self.focus_right_panel, orient="horizontal").pack(fill="x", pady=10)

        self.focus_del_btn = ttk.Button(self.focus_right_panel, text="DELETE (Trash)", command=self.delete_current_candidate)
        self.focus_del_btn.pack(side="top", pady=20, fill="x")

        self.focus_next_btn = ttk.Button(self.focus_right_panel, text="Next >", command=self.next_candidate)
        self.focus_next_btn.pack(side="top", pady=20, fill="x")

        # --- Row 1: Bottom Strip ---

        # Bottom Left (Row 1, Col 0) - Previous Image
        self.focus_prev_lbl = ttk.Label(self.focus_frame, text="Prev", anchor="center", relief="sunken")
        self.focus_prev_lbl.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.focus_prev_lbl.bind("<Button-1>", lambda e: self.on_image_click(self.panel_prev.path))

        # Bottom Center (Row 1, Col 1) - Filename/Spacer
        self.focus_filename_lbl = ttk.Label(self.focus_frame, text="", font=("Helvetica", 14))
        self.focus_filename_lbl.grid(row=1, column=1, sticky="n", pady=5)

        # Bottom Right (Row 1, Col 2) - Next Image
        self.focus_next_lbl = ttk.Label(self.focus_frame, text="Next", anchor="center", relief="sunken")
        self.focus_next_lbl.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)
        self.focus_next_lbl.bind("<Button-1>", lambda e: self.on_image_click(self.panel_next.path))

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
            if hasattr(main_app, 'toggle_sidebar'):
                main_app.toggle_sidebar(False)

            self.notebook.pack_forget()
            self.focus_frame.pack(fill="both", expand=True)
            self.focus_frame.focus_set() # Enable keyboard events

            # Reload images to ensure they are sized correctly for Focus Mode (Equal sizes)
            if self.panel_curr.path:
                self.load_triplet_view(self.panel_curr.path)
            else:
                self.refresh_active_view()
        else:
            # Disable Focus Mode
            self.focus_frame.pack_forget()
            self.notebook.pack(fill="both", expand=True)

            if hasattr(main_app, 'toggle_sidebar'):
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

        frame.img_lbl = lbl # Store ref
        frame.details_lbl = details # Store ref
        frame.path = None # Initialize path

        # Bind click to fullscreen
        lbl.bind("<Button-1>", lambda e: self.on_image_click(frame.path))
        return frame

    def on_image_click(self, path):
        if path:
            self.show_fullscreen(path)

    def show_fullscreen(self, path):
        if not path or not path.exists():
            return

        top = tk.Toplevel(self)
        top.title(f"Fullscreen - {path.name}")

        # Configure fullscreen
        top.attributes("-fullscreen", True)
        top.bind("<Escape>", lambda e: top.destroy())

        # UI
        lbl = ttk.Label(top, text="Loading full resolution...", anchor="center", background="black", foreground="white")
        lbl.pack(fill="both", expand=True)

        # Close button
        btn_close = ttk.Button(top, text="Close (Esc)", command=top.destroy)
        btn_close.place(relx=0.95, rely=0.05, anchor="ne")

        # Load image in background
        def load_full():
            try:
                # Target a very large size for fullscreen
                # Note: rawpy logic in utils.load_image_preview handles half_size=True, which is still large
                img = load_image_preview(path, max_size=(3000, 2000))
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self.parent.after(0, lambda: display(photo))
                else:
                    self.parent.after(0, lambda: lbl.config(text="Failed to load image."))
            except Exception as e:
                logger.error(f"Fullscreen load error: {e}")
                self.parent.after(0, lambda: lbl.config(text=f"Error: {e}"))

        def display(photo):
            if not top.winfo_exists(): return
            lbl.config(image=photo, text="")
            lbl.image = photo # Keep ref

        threading.Thread(target=load_full, daemon=True).start()

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

        threading.Thread(target=self.run_scan_thread, args=(folder,), daemon=True).start()
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
            extensions = {'.jpg', '.jpeg', '.tif', '.tiff', '.nef', '.cr2', '.arw', '.dng', '.raw'}
            files = [f for f in p.rglob('*') if f.suffix.lower() in extensions]

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
                grid_size = int(grid_str.split('x')[0])
            except:
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

                res = {
                    "path": f,
                    "score": score,
                    "category": cat,
                    "exif": exif
                }

                # Send result to main thread
                self.parent.after(0, lambda r=res, idx=i+1, t=total: self.process_scan_result(r, idx, t))

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
        self.review_status_lbl.config(text=f"Scan Progress: {int(pct)}% ({current_idx}/{total_count})")

        # Handle Candidate
        if result["category"] in [SharpnessCategories.BLURRY, SharpnessCategories.ACCEPTABLE]:
            path = result["path"]
            self.candidates.append(path)

            # Add to listbox
            cat_name = SharpnessCategories.get_name(result["category"])
            self.candidate_listbox.insert("end", f"{path.name} ({cat_name})")

            # Color code
            color = SharpnessCategories.get_color(result["category"])
            idx = self.candidate_listbox.size() - 1
            self.candidate_listbox.itemconfig(idx, {'fg': color})

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
            messagebox.showinfo("Result", "No blurry or 'acceptable' images found based on current thresholds.")
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

        # Look ahead for next 3 candidates
        count = 0
        for i in range(current_idx + 1, len(self.candidates)):
            if count >= 3: break
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

    def start_preloader(self):
        threading.Thread(target=self.run_preloader, daemon=True).start()

    def run_preloader(self):
        CACHE_SIZE = (800, 600)
        while True:
            try:
                path = self.preloader_queue.get()
                if path is None: continue

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
                except Exception as e:
                    pass
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
                pass # UI not ready
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
        next_path = self.sorted_files[full_idx + 1] if full_idx < len(self.sorted_files) - 1 else None

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
        # Focus Mode: All same size (approx half screen height/width)
        # Standard Mode: Main large, Neighbors small
        if self.focus_mode:
            # Target ~1/3 width of 1920px screen to prevent overflow
            size_curr = (600, 450)
            size_neighbors = (600, 450)
        else:
            size_curr = (800, 600)
            size_neighbors = (400, 300)

        # Start background thread for loading images
        threading.Thread(target=self.load_images_background,
                         args=(prev_path, current_path, next_path, size_curr, size_neighbors),
                         daemon=True).start()

    def set_placeholder(self, panel, path):
        lbl = panel.img_lbl
        details = panel.details_lbl

        if path is None:
            lbl.config(image='', text="No Image")
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

        details.config(text=f"{path.name}\n{cat_name} ({score_txt})", foreground=cat_color)
        lbl.config(image='', text="Loading...")

    def update_metadata_label(self, current_path):
        res = self.files_map.get(current_path)
        if res:
            exif = res["exif"]
            score = res["score"]
            aperture = exif.get('FNumber', 'N/A')
            shutter = exif.get('ExposureTime', 'N/A')
            cat_name = SharpnessCategories.get_name(res["category"])
            cat_color = SharpnessCategories.get_color(res["category"])

            # Standard View Text
            txt = (f"File: {current_path.name}\n"
                   f"Category: {cat_name} (Score: {score:.1f})\n"
                   f"Aperture: {aperture}, Shutter: {shutter}")
            self.meta_lbl.config(text=txt)

            # Focus View Text
            if hasattr(self, 'focus_score_lbl'):
                self.focus_score_lbl.config(text=f"Score: {score:.1f}", foreground=cat_color)
                self.focus_cat_lbl.config(text=f"{cat_name}", foreground=cat_color)

                meta_txt = (f"Aperture: {aperture}\n"
                            f"Shutter: {shutter}\n"
                            f"ISO: {exif.get('ISOSpeedRatings', 'N/A')}\n"
                            f"Focal: {exif.get('FocalLength', 'N/A')}")
                self.focus_meta_lbl.config(text=meta_txt)
                self.focus_filename_lbl.config(text=current_path.name)

    def load_images_background(self, prev_path, curr_path, next_path, size_curr, size_neighbors):
        CACHE_SIZE = (800, 600)

        def get_image(path, requested_size):
            if path is None: return None

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

            if not img: return None

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
        self.current_triplet_images = (p_img, c_img, n_img)
        self.refresh_active_view()

    def refresh_active_view(self):
        p_img, c_img, n_img = self.current_triplet_images

        # Helper to set image on a label
        def set_lbl_img(lbl, img, fallback_text="No Image"):
            if img:
                lbl.config(image=img, text="")
                lbl.image = img # Keep ref
            else:
                lbl.config(image='', text=fallback_text)

        if self.focus_mode:
            # Update Focus UI
            set_lbl_img(self.focus_prev_lbl, p_img, "Prev\nUnavailable")
            set_lbl_img(self.focus_curr_lbl, c_img, "Loading...")
            set_lbl_img(self.focus_next_lbl, n_img, "Next\nUnavailable")
        else:
            # Update Standard UI
            def set_panel(panel, img):
                lbl = panel.img_lbl
                if img:
                    lbl.config(image=img, text="")
                    lbl.image = img
                elif lbl.cget("text") == "Loading...":
                    lbl.config(image='', text="Preview\nUnavailable")

            set_panel(self.panel_prev, p_img)
            set_panel(self.panel_curr, c_img)
            set_panel(self.panel_next, n_img)

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

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to move '{path.name}' and related files to trash?"):
            related = find_related_files(path)
            failed_trash = []

            for f in related:
                try:
                    send2trash.send2trash(str(f))
                    self.log(f"Moved to trash: {f}")
                except Exception as e:
                    failed_trash.append(f)
                    self.log(f"Trash failed for {f}: {e}")

            if failed_trash:
                msg = (f"Failed to move {len(failed_trash)} related file(s) to trash (e.g. network drive).\n"
                       "Do you want to PERMANENTLY delete them?")
                if messagebox.askyesno("Trash Failed", msg):
                    for f in failed_trash:
                        try:
                            if f.exists():
                                f.unlink()
                                self.log(f"Permanently deleted: {f}")
                        except Exception as e:
                            self.log(f"Delete failed for {f}: {e}")

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
                    self.panel_curr.img_lbl.config(image='', text="No Candidates")
                    self.panel_prev.img_lbl.config(image='', text="")
                    self.panel_next.img_lbl.config(image='', text="")

                    self.panel_curr.path = None
                    self.panel_prev.path = None
                    self.panel_next.path = None
