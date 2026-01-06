import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import sys
from pathlib import Path
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Use a relative import or absolute based on package structure
# Assuming this runs as a module
from image_metadata_analyzer.reader import get_exif_data
from image_metadata_analyzer.analyzer import analyze_data
from image_metadata_analyzer.visualizer import (
    get_shutter_speed_plot, get_aperture_plot, get_iso_plot,
    get_focal_length_plot, get_lens_plot, get_combination_plot
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

        # Analyze Button
        self.analyze_btn = ttk.Button(controls_frame, text="Analyze", command=self.start_analysis)
        self.analyze_btn.grid(row=2, column=0, columnspan=3, pady=10)

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
        self.log_text['yscrollcommand'] = scrollbar.set
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

    def start_analysis(self):
        root_path = self.root_folder_var.get()
        output_path = self.output_folder_var.get()

        if not root_path:
            messagebox.showerror("Error", "Please select an images folder.")
            return

        self.is_analyzing = True
        self.analyze_btn.config(state="disabled")
        self.progress_bar.config(mode="indeterminate")
        self.progress_bar.start()

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

    def run_analysis(self, root_folder, output_folder):
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.log_queue)

        try:
            root_path = Path(root_folder)
            output_path = Path(output_folder)

            if not root_path.is_dir():
                print(f"Error: Folder not found at '{root_path}'")
                return

            image_extensions = {'.jpg', '.jpeg', '.tif', '.tiff', '.nef', '.cr2', '.arw', '.dng', '.raw'}
            print(f"Scanning for images in '{root_path}'...")

            image_files = [f for f in root_path.rglob('*') if f.suffix.lower() in image_extensions]

            if not image_files:
                print("No supported image files found.")
                return

            print(f"Found {len(image_files)} image files. Extracting metadata...")

            # Since we can't easily hook into tqdm from here without more work,
            # we'll iterate manually to update progress if we wanted specific progress,
            # but for now we are using indeterminate mode.
            # To actually show progress, we'd need to change how we process images.
            # Let's do a simple loop here instead of list comp to update logs/progress occasionally?
            # Or just rely on indeterminate for now.

            all_metadata = []
            for i, f in enumerate(image_files):
                data = get_exif_data(f)
                if data:
                    all_metadata.append(data)

                # Update simple progress every 10 images to avoid spamming queue
                if i % 10 == 0:
                    # We can't easily update the specific progress bar from the thread safely
                    # without queue or `after`, but indeterminate is running.
                    pass

            if not all_metadata:
                print("Could not extract any valid EXIF metadata from the found images.")
                return

            df = pd.DataFrame(all_metadata)
            if df.empty:
                print("Could not extract any valid EXIF metadata.")
                return

            # Data Cleaning (same as CLI)
            df['Shutter Speed'] = pd.to_numeric(df['Shutter Speed'], errors='coerce')
            df['Aperture'] = pd.to_numeric(df['Aperture'], errors='coerce').round(1)
            focal_length_series = pd.to_numeric(df['Focal Length'], errors='coerce')
            not_na_mask = focal_length_series.notna()
            integer_series = pd.Series(pd.NA, index=df.index, dtype='Int64')
            integer_series[not_na_mask] = focal_length_series[not_na_mask].round().astype(int)
            df['Focal Length'] = integer_series
            df['ISO'] = pd.to_numeric(df['ISO'], errors='coerce').astype('Int64')

            analyze_data(df)

            # Generate Plots for GUI
            print("Generating plots...")
            plots = {
                "Shutter Speed": get_shutter_speed_plot(df),
                "Aperture": get_aperture_plot(df),
                "ISO": get_iso_plot(df),
                "Focal Length": get_focal_length_plot(df),
                "Lens": get_lens_plot(df),
                "Combinations": get_combination_plot(df)
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
        self.progress_bar.stop()
        self.progress_bar.config(mode="determinate", value=100)


class Sidebar(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, width=200, padding=10)
        self.controller = controller

        ttk.Label(self, text="Tools", font=("Helvetica", 12, "bold")).pack(pady=10)

        ttk.Button(self, text="Image Library Statistics",
                   command=lambda: controller.show_frame("ImageLibraryStatistics")).pack(fill="x", pady=5)

        # Add more buttons here for future features

        self.pack(side="left", fill="y")


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Metadata Analyzer")
        self.geometry("1000x700")

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
