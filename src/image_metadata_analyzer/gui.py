import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import ImageTk

from image_metadata_analyzer.analyzer import analyze_data
from image_metadata_analyzer.duplicates import find_duplicates, move_to_trash
# Use a relative import or absolute based on package structure
# Assuming this runs as a module
from image_metadata_analyzer.reader import SUPPORTED_EXTENSIONS, get_exif_data
from image_metadata_analyzer.sharpness_gui import SharpnessTool
from image_metadata_analyzer.utils import load_image_preview, resolve_path
from image_metadata_analyzer.visualizer import (
    get_aperture_plot, get_apsc_equivalent_focal_length_plot,
    get_combination_plot, get_equivalent_focal_length_plot,
    get_focal_length_plot, get_iso_plot, get_lens_plot, get_shutter_speed_plot)


class RedirectText(object):
    """Redirects stdout to a tkinter text widget via a queue."""

    def __init__(self, text_queue):
        self.text_queue = text_queue

    def write(self, string):
        self.text_queue.put(string)

    def flush(self):
        pass


class ImageLibraryStatistics(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        self.log_queue: queue.Queue = queue.Queue()
        self.is_analyzing = False
        self.stop_event = threading.Event()

    def setup_ui(self):
        # Top controls
        controls_frame = ttk.LabelFrame(self, text="Configuration", padding=10)
        controls_frame.pack(fill="x", padx=10, pady=5)

        # Root Folder
        ttk.Label(controls_frame, text="Images Folder:").grid(
            row=0, column=0, sticky="w"
        )
        self.root_folder_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.root_folder_var, width=50).grid(
            row=0, column=1, padx=5
        )
        ttk.Button(
            controls_frame, text="Browse...", command=self.browse_root_folder
        ).grid(row=0, column=2)

        # Output Folder
        ttk.Label(controls_frame, text="Output Folder:").grid(
            row=1, column=0, sticky="w"
        )
        self.output_folder_var = tk.StringVar(value="analysis_results")
        ttk.Entry(controls_frame, textvariable=self.output_folder_var, width=50).grid(
            row=1, column=1, padx=5
        )
        ttk.Button(
            controls_frame, text="Browse...", command=self.browse_output_folder
        ).grid(row=1, column=2)

        # Buttons Frame
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)

        # Analyze Button
        self.analyze_btn = ttk.Button(
            btn_frame, text="Analyze", command=self.start_analysis
        )
        self.analyze_btn.pack(side="left", padx=5)

        # Cancel Button
        self.cancel_btn = ttk.Button(
            btn_frame, text="Cancel", command=self.cancel_analysis, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=5)

        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            controls_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)

        # Output / Results Area
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Logs Tab
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="Logs")

        self.log_text = tk.Text(self.logs_frame, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

        # Scrollbar for logs
        scrollbar = ttk.Scrollbar(
            self.logs_frame, orient="vertical", command=self.log_text.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.log_text["yscrollcommand"] = scrollbar.set
        self.log_text.pack(side="left", fill="both", expand=True)

        # Plots Tabs (Placeholders for now)
        self.plot_tabs = {}

    def browse_root_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.root_folder_var.set(folder)

    def browse_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder_var.set(folder)

    def log(self, message):
        self.log_queue.put(message)

    def update_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert("end", msg)
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass

        if self.is_analyzing:
            self.after(100, self.update_logs)

    def cancel_analysis(self):
        if self.is_analyzing:
            print("Stopping analysis...")
            self.stop_event.set()
            self.cancel_btn.config(state="disabled")

    def start_analysis(self):
        root_path = self.root_folder_var.get()
        output_path = self.output_folder_var.get()

        if not root_path:
            messagebox.showerror("Error", "Please select an images folder.")
            return

        self.is_analyzing = True
        self.stop_event.clear()
        self.analyze_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress_bar.config(mode="determinate", value=0)

        # Clear logs
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")

        # Clear existing plot tabs
        for tab in self.plot_tabs.values():
            self.notebook.forget(tab)
        self.plot_tabs = {}

        # Start thread
        threading.Thread(
            target=self.run_analysis, args=(root_path, output_path), daemon=True
        ).start()
        self.after(100, self.update_logs)

    def update_progress(self, value):
        self.progress_var.set(value)

    def run_analysis(self, root_folder, output_folder):
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.log_queue)

        try:
            # Resolve potential network paths (smb://) to local paths
            root_path = resolve_path(root_folder)
            # output_path = Path(output_folder) # Not actually used in GUI for display,
            # only passed if we wanted to save there

            if not root_path.is_dir():
                print(f"Error: Folder not found at '{root_path}'")
                if root_folder.startswith("smb://"):
                    msg = (
                        "Tip: For network locations, ensure "
                        "the share is mounted in your file manager first."
                    )
                    print(msg)
                return

            print(f"Scanning for images in '{root_path}'...")

            image_files = [
                f
                for f in root_path.rglob("*")
                if f.suffix.lower() in SUPPORTED_EXTENSIONS
            ]

            if not image_files:
                print("No supported image files found.")
                return

            total_files = len(image_files)
            print(f"Found {total_files} image files. Extracting metadata...")

            all_metadata = []
            for i, f in enumerate(image_files):
                if self.stop_event.is_set():
                    print("Analysis cancelled by user.")
                    break

                data = get_exif_data(f)
                if data:
                    all_metadata.append(data)

                # Update progress
                progress = ((i + 1) / total_files) * 100
                self.parent.after(0, self.update_progress, progress)

            if not all_metadata:
                print(
                    "Could not extract any valid EXIF metadata from the found images."
                )
                return

            analyze_data(all_metadata)

            # Generate Plots for GUI
            print("Generating plots...")
            plots = {
                "Shutter Speed": get_shutter_speed_plot(all_metadata),
                "Aperture": get_aperture_plot(all_metadata),
                "ISO": get_iso_plot(all_metadata),
                "Focal Length": get_focal_length_plot(all_metadata),
                "Equiv Focal Length (35mm)": get_equivalent_focal_length_plot(
                    all_metadata
                ),
                "Equiv Focal Length (APS-C)": get_apsc_equivalent_focal_length_plot(
                    all_metadata
                ),
                "Lens": get_lens_plot(all_metadata),
                "Combinations": get_combination_plot(all_metadata),
            }

            # Schedule GUI update to show plots
            self.parent.after(0, lambda: self.display_results(plots))

            print("Analysis complete.")

        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback

            traceback.print_exc()
        finally:
            sys.stdout = old_stdout
            self.parent.after(0, self.analysis_finished)

    def display_results(self, plots):
        for name, fig in plots.items():
            if fig:
                frame = ttk.Frame(self.notebook)
                self.notebook.add(frame, text=name)

                canvas = FigureCanvasTkAgg(fig, master=frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True)

                self.plot_tabs[name] = frame

        # Switch to first plot tab if available
        if self.plot_tabs:
            self.notebook.select(list(self.plot_tabs.values())[0])

    def analysis_finished(self):
        self.is_analyzing = False
        self.analyze_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        # Ensure it is 100% only if not cancelled? Or leave it as is.
        # If cancelled, it might be stopped at 50%.
        if not self.stop_event.is_set():
            self.progress_bar.config(value=100)


class DuplicateFinder(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        self.is_scanning = False
        self.found_duplicates = []
        self.photo_refs = []  # Keep references to images
        self.check_vars = {}  # Maps path to BooleanVar

    def setup_ui(self):
        # Top controls
        controls_frame = ttk.LabelFrame(self, text="Duplicate Detection", padding=10)
        controls_frame.pack(fill="x", padx=10, pady=5)

        # Root Folder
        ttk.Label(controls_frame, text="Images Folder:").grid(
            row=0, column=0, sticky="w"
        )
        self.root_folder_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.root_folder_var, width=50).grid(
            row=0, column=1, padx=5
        )
        ttk.Button(
            controls_frame, text="Browse...", command=self.browse_root_folder
        ).grid(row=0, column=2)

        # Buttons
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=1, column=0, columnspan=3, pady=10)

        self.scan_btn = ttk.Button(
            btn_frame, text="Find Duplicates", command=self.start_scan
        )
        self.scan_btn.pack(side="left", padx=5)

        self.status_lbl = ttk.Label(btn_frame, text="")
        self.status_lbl.pack(side="left", padx=10)

        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            controls_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

        # Results Area (Scrollable)
        results_container = ttk.Frame(self)
        results_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Canvas for scrolling
        self.canvas = tk.Canvas(results_container)
        scrollbar = ttk.Scrollbar(
            results_container, orient="vertical", command=self.canvas.yview
        )

        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bottom Actions
        actions_frame = ttk.Frame(self, padding=10)
        actions_frame.pack(fill="x")

        ttk.Button(
            actions_frame,
            text="Delete Selected (Move to Trash)",
            command=self.delete_selected,
        ).pack(side="right")

    def browse_root_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.root_folder_var.set(folder)

    def start_scan(self):
        folder = self.root_folder_var.get()
        if not folder:
            messagebox.showerror("Error", "Please select a folder.")
            return

        self.is_scanning = True
        self.scan_btn.config(state="disabled")
        self.progress_bar.config(value=0)
        self.status_lbl.config(text="Scanning...")

        # Clear previous results
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.photo_refs.clear()
        self.check_vars.clear()
        self.found_duplicates = []

        threading.Thread(target=self.run_scan, args=(folder,), daemon=True).start()

    def run_scan(self, folder):
        try:
            resolved_path = resolve_path(folder)

            def progress_cb(current, total):
                if total > 0:
                    val = (current / total) * 100
                    self.parent.after(0, lambda: self.progress_var.set(val))
                    self.parent.after(
                        0,
                        lambda: self.status_lbl.config(
                            text=f"Processed {current}/{total}"
                        ),
                    )

            results = find_duplicates(resolved_path, callback=progress_cb)

            # Pre-load thumbnails in background to avoid blocking GUI
            self.parent.after(
                0, lambda: self.status_lbl.config(text="Generating previews...")
            )

            thumbnails = []
            for group in results:
                thumb = None
                if group["files"]:
                    try:
                        thumb = load_image_preview(
                            group["files"][0], max_size=(150, 150)
                        )
                    except Exception:
                        pass
                thumbnails.append(thumb)

            self.parent.after(0, lambda: self.display_results(results, thumbnails))
        except Exception as e:
            print(f"Error scanning: {e}")
            import traceback

            traceback.print_exc()
            self.parent.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.parent.after(0, self.scan_finished)

    def scan_finished(self):
        self.is_scanning = False
        self.scan_btn.config(state="normal")
        self.status_lbl.config(text="Scan complete.")
        self.progress_bar.config(value=100)

    def display_results(self, duplicates, thumbnails):
        if not duplicates:
            ttk.Label(self.scrollable_frame, text="No duplicates found.").pack(pady=20)
            return

        self.found_duplicates = duplicates

        for i, (group, thumb_img) in enumerate(zip(duplicates, thumbnails)):
            group_frame = ttk.LabelFrame(
                self.scrollable_frame,
                text=f"Group {i+1} (Size: {group['size']} bytes)",
                padding=5,
            )
            group_frame.pack(fill="x", pady=5, padx=5)

            # Content layout: Image on left, Files on right
            content_frame = ttk.Frame(group_frame)
            content_frame.pack(fill="x")

            # Image Preview
            if thumb_img:
                try:
                    photo = ImageTk.PhotoImage(thumb_img)
                    self.photo_refs.append(photo)  # Keep ref
                    lbl_img = ttk.Label(content_frame, image=photo)
                    lbl_img.pack(side="left", padx=10, anchor="n")
                except Exception:
                    ttk.Label(content_frame, text="[Preview Error]").pack(
                        side="left", padx=10, anchor="n"
                    )
            else:
                ttk.Label(content_frame, text="[No Preview]").pack(
                    side="left", padx=10, anchor="n"
                )

            # File List
            files_frame = ttk.Frame(content_frame)
            files_frame.pack(side="left", fill="both", expand=True)

            for fpath in group["files"]:
                var = tk.BooleanVar(value=False)
                self.check_vars[fpath] = var
                chk = ttk.Checkbutton(files_frame, text=str(fpath), variable=var)
                chk.pack(anchor="w")

    def delete_selected(self):
        to_delete = []

        # Validation: check groups
        for group in self.found_duplicates:
            files = group["files"]
            selected_count = sum(
                1 for f in files if self.check_vars.get(f) and self.check_vars[f].get()
            )

            if selected_count == len(files):
                messagebox.showerror(
                    "Error",
                    f"Cannot delete all copies in Group (Size: {group['size']}). Please keep at least one.",
                )
                return

            for f in files:
                if self.check_vars.get(f) and self.check_vars[f].get():
                    to_delete.append(f)

        if not to_delete:
            messagebox.showinfo("Info", "No files selected.")
            return

        if not messagebox.askyesno("Confirm", f"Move {len(to_delete)} files to trash?"):
            return

        # Execute Deletion
        deleted_count = 0
        for fpath in to_delete:
            if move_to_trash(fpath):
                deleted_count += 1

        messagebox.showinfo("Success", f"Moved {deleted_count} files to trash.")
        self.start_scan()


class Sidebar(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, width=200, padding=10)
        self.controller = controller

        ttk.Label(self, text="Tools", font=("Helvetica", 12, "bold")).pack(pady=10)

        ttk.Button(
            self,
            text="Image Library Statistics",
            command=lambda: controller.show_frame("ImageLibraryStatistics"),
        ).pack(fill="x", pady=5)

        ttk.Button(
            self,
            text="Blurry Image Finder",
            command=lambda: controller.show_frame("SharpnessTool"),
        ).pack(fill="x", pady=5)

        ttk.Button(
            self,
            text="Duplicate Finder",
            command=lambda: controller.show_frame("DuplicateFinder"),
        ).pack(fill="x", pady=5)

        self.pack(side="left", fill="y")


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Metadata Analyzer")

        # Attempt to improve DPI awareness on Windows/Linux
        try:
            # Unix/Linux often needs this for proper scaling if not handled by window manager
            self.call("tk", "scaling", self.winfo_fpixels("1i") / 72.0)
        except Exception:
            pass

        # Set Window Icon
        try:
            icon_path = None
            if hasattr(sys, "_MEIPASS"):
                # Running from PyInstaller bundle
                icon_path = Path(sys._MEIPASS) / "logo.png"
            else:
                # Running from source
                icon_path = Path(__file__).parent.parent.parent / "assets" / "logo.png"

            if icon_path and icon_path.exists():
                icon_image = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, icon_image)
        except Exception as e:
            print(f"Failed to load icon: {e}")

        # Maximize window
        try:
            # Windows and some Linux window managers
            self.state("zoomed")
        except tk.TclError:
            try:
                # Linux (X11)
                self.attributes("-zoomed", True)
            except tk.TclError:
                # Fallback: simple geometry set to screen size
                width = self.winfo_screenwidth()
                height = self.winfo_screenheight()
                self.geometry(f"{width}x{height}")

        self.sidebar = Sidebar(self, self)

        self.content_area = ttk.Frame(self)
        self.content_area.pack(side="right", fill="both", expand=True)

        self.frames = {}

        # Initialize frames
        for F in (ImageLibraryStatistics, DuplicateFinder, SharpnessTool):
            page_name = F.__name__
            frame = F(self.content_area)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self.show_frame("ImageLibraryStatistics")

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()


def main():
    app = MainApp()
    app.mainloop()


if __name__ == "__main__":
    main()
