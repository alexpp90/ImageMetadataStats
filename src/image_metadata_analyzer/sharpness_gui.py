import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import send2trash
from PIL import ImageTk

from image_metadata_analyzer.reader import get_exif_data
# Local imports
from image_metadata_analyzer.sharpness import (SharpnessCategories,
                                               calculate_sharpness,
                                               categorize_sharpness,
                                               find_related_files)
from image_metadata_analyzer.utils import load_image_preview

logger = logging.getLogger(__name__)


class SharpnessTool(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.log_queue: queue.Queue = queue.Queue()
        self.is_scanning = False
        self.stop_event = threading.Event()

        # State
        self.scan_results = []  # List of dicts: {path, score, category, exif}
        self.files_map = {}  # path -> result dict
        self.sorted_files = []  # List of paths sorted by filename
        self.candidates = []  # List of paths that are category 2 or 3

        # Defaults
        self.default_blur_threshold = 100.0
        self.default_sharp_threshold = 500.0

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

        # Start Button
        self.start_btn = ttk.Button(
            container, text="Start Sharpness Scan", command=self.start_scan
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

        ttk.Label(self.sidebar, text="Candidates (Blurry/Acceptable)").pack(pady=5)

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

        # 3-Panel Image View
        self.image_container = ttk.Frame(self.preview_area)
        self.image_container.pack(fill="both", expand=True)

        # Configure columns for 3 images
        self.image_container.columnconfigure(0, weight=1)
        self.image_container.columnconfigure(1, weight=1)
        self.image_container.columnconfigure(2, weight=1)
        self.image_container.rowconfigure(0, weight=1)

        # Prev
        self.panel_prev = self.create_image_panel(self.image_container, "Previous")
        self.panel_prev.grid(row=0, column=0, sticky="nsew", padx=2)

        # Current
        self.panel_curr = self.create_image_panel(self.image_container, "Candidate")
        self.panel_curr.grid(row=0, column=1, sticky="nsew", padx=2)

        # Next
        self.panel_next = self.create_image_panel(self.image_container, "Next")
        self.panel_next.grid(row=0, column=2, sticky="nsew", padx=2)

        # Info & Actions
        self.info_frame = ttk.Frame(self.preview_area, padding=10)
        self.info_frame.pack(fill="x")

        # Metadata Label
        self.meta_lbl = ttk.Label(self.info_frame, text="", font=("Helvetica", 10))
        self.meta_lbl.pack(pady=5)

        # Buttons
        btn_frame = ttk.Frame(self.info_frame)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame, text="< Prev Candidate", command=self.prev_candidate
        ).pack(side="left", padx=5)
        self.del_btn = ttk.Button(
            btn_frame,
            text="Delete Candidate (Trash)",
            command=self.delete_current_candidate,
        )
        self.del_btn.pack(side="left", padx=20)
        ttk.Button(
            btn_frame, text="Next Candidate >", command=self.next_candidate
        ).pack(side="left", padx=5)

    def create_image_panel(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title)

        # Image Label (Placeholder)
        lbl = ttk.Label(frame, text="No Image", anchor="center")
        lbl.pack(fill="both", expand=True)

        # Details
        details = ttk.Label(frame, text="", font=("Helvetica", 9))
        details.pack(fill="x")

        # Store refs dynamically
        setattr(frame, "img_lbl", lbl)
        setattr(frame, "details_lbl", details)
        return frame

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
        self.scan_results = []
        self.files_map = {}

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

            for i, f in enumerate(files):
                if self.stop_event.is_set():
                    self.log("Scan cancelled.")
                    break

                self.log(f"Analyzing {f.name}...")

                # Sharpness
                score = calculate_sharpness(f)
                cat = categorize_sharpness(score, blur_t, sharp_t)

                # Exif (basic)
                exif = get_exif_data(f) or {}

                res = {"path": f, "score": score, "category": cat, "exif": exif}

                self.scan_results.append(res)
                self.files_map[f] = res

                # Progress
                prog = ((i + 1) / total) * 100
                self.parent.after(0, lambda v=prog: self.progress_var.set(v))

            self.log("Scan complete.")

        except Exception as e:
            self.log(f"Error during scan: {e}")
            import traceback

            traceback.print_exc()

        self.parent.after(0, self.scan_finished)

    def scan_finished(self):
        self.is_scanning = False
        self.notebook.tab(0, state="normal")

        # Filter candidates
        self.candidates = [
            res["path"]
            for res in self.scan_results
            if res["category"]
            in [SharpnessCategories.BLURRY, SharpnessCategories.ACCEPTABLE]
        ]

        if self.candidates:
            self.notebook.tab(2, state="normal")
            self.notebook.select(2)
            self.populate_candidates()
            self.log(f"Found {len(self.candidates)} candidates for review.")
        else:
            messagebox.showinfo(
                "Result",
                "No blurry or 'acceptable' images found based on current thresholds.",
            )
            self.notebook.select(0)

    def populate_candidates(self):
        self.candidate_listbox.delete(0, "end")
        for path in self.candidates:
            res = self.files_map[path]
            cat_name = SharpnessCategories.get_name(res["category"])
            self.candidate_listbox.insert("end", f"{path.name} ({cat_name})")

            # Color code
            color = SharpnessCategories.get_color(res["category"])
            idx = self.candidate_listbox.size() - 1
            self.candidate_listbox.itemconfig(idx, {"fg": color})

        if self.candidates:
            self.candidate_listbox.selection_set(0)
            self.on_candidate_select(None)

    def on_candidate_select(self, event):
        sel = self.candidate_listbox.curselection()
        if not sel:
            return

        idx = sel[0]
        current_path = self.candidates[idx]
        self.load_triplet_view(current_path)

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
            args=(prev_path, current_path, next_path),
            daemon=True,
        ).start()

    def set_placeholder(self, panel, path):
        lbl = getattr(panel, "img_lbl")
        details = getattr(panel, "details_lbl")

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

    def load_images_background(self, prev_path, curr_path, next_path):
        # Helper to load one image
        def load_one(path):
            if path is None:
                return None
            try:
                img = load_image_preview(path, max_size=(300, 300))
                if img:
                    return ImageTk.PhotoImage(img)
                return None
            except Exception as e:
                logger.error(f"Failed to load thumbnail for {path}: {e}")
                return None

        p_img = load_one(prev_path)
        c_img = load_one(curr_path)
        n_img = load_one(next_path)

        # Update UI in main thread
        self.parent.after(0, lambda: self.update_panels_final(p_img, c_img, n_img))

    def update_panels_final(self, p_img, c_img, n_img):
        def set_img(panel, img):
            lbl = getattr(panel, "img_lbl")
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
            success = True
            for f in related:
                try:
                    send2trash.send2trash(f)
                    self.log(f"Moved to trash: {f}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete {f}:\n{e}")
                    success = False

            if success:
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
                    getattr(self.panel_curr, "img_lbl").config(image="", text="No Candidates")
                    getattr(self.panel_prev, "img_lbl").config(image="", text="")
                    getattr(self.panel_next, "img_lbl").config(image="", text="")
