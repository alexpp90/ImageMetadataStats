import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from image_metadata_analyzer.analyzer import analyze_data

# Use a relative import or absolute based on package structure
# Assuming this runs as a module
from image_metadata_analyzer.reader import get_exif_data
from image_metadata_analyzer.utils import resolve_path
from image_metadata_analyzer.visualizer import (
    get_aperture_plot,
    get_combination_plot,
    get_focal_length_plot,
    get_iso_plot,
    get_lens_plot,
    get_shutter_speed_plot,
)


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
        self.log_queue = queue.Queue()
        self.is_analyzing = False
        self.stop_event = threading.Event()

    def setup_ui(self):
        # Top controls
        controls_frame = ttk.LabelFrame(self, text="Configuration", padding=10)
        controls_frame.pack(fill="x", padx=10, pady=5)

        # Root Folder
        ttk.Label(controls_frame, text="Images Folder:").grid(row=0, column=0, sticky="w")
        self.root_folder_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.root_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text="Browse...", command=self.browse_root_folder).grid(row=0, column=2)

        # Output Folder
        ttk.Label(controls_frame, text="Output Folder:").grid(row=1, column=0, sticky="w")
        self.output_folder_var = tk.StringVar(value="analysis_results")
        ttk.Entry(controls_frame, textvariable=self.output_folder_var, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(controls_frame, text="Browse...", command=self.browse_output_folder).grid(row=1, column=2)

        # Buttons Frame
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)

        # Analyze Button
        self.analyze_btn = ttk.Button(btn_frame, text="Analyze", command=self.start_analysis)
        self.analyze_btn.pack(side="left", padx=5)

        # Cancel Button
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.cancel_analysis, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)

        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(controls_frame, variable=self.progress_var, maximum=100)
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
        scrollbar = ttk.Scrollbar(self.logs_frame, orient="vertical", command=self.log_text.yview)
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
        threading.Thread(target=self.run_analysis, args=(root_path, output_path), daemon=True).start()
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
            # output_path = Path(output_folder)
            # Not actually used in GUI for display, only passed if we wanted to save there

            if not root_path.is_dir():
                print(f"Error: Folder not found at '{root_path}'")
                if root_folder.startswith("smb://"):
                    print("Tip: For network locations, ensure the share is mounted in your file manager first.")
                return

            image_extensions = {".jpg", ".jpeg", ".tif", ".tiff", ".nef", ".cr2", ".arw", ".dng", ".raw"}
            print(f"Scanning for images in '{root_path}'...")

            image_files = [f for f in root_path.rglob("*") if f.suffix.lower() in image_extensions]

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
                print("Could not extract any valid EXIF metadata from the found images.")
                return

            analyze_data(all_metadata)

            # Generate Plots for GUI
            print("Generating plots...")
            plots = {
                "Shutter Speed": get_shutter_speed_plot(all_metadata),
                "Aperture": get_aperture_plot(all_metadata),
                "ISO": get_iso_plot(all_metadata),
                "Focal Length": get_focal_length_plot(all_metadata),
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


class Sidebar(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, width=200, padding=10)
        self.controller = controller

        ttk.Label(self, text="Tools", font=("Helvetica", 12, "bold")).pack(pady=10)

        ttk.Button(
            self, text="Image Library Statistics", command=lambda: controller.show_frame("ImageLibraryStatistics")
        ).pack(fill="x", pady=5)

        # Add more buttons here for future features

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
        for F in (ImageLibraryStatistics,):
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
