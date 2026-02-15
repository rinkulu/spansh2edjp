import csv
import json
import os
import threading
import time
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog as fd
from tkinter import ttk

import requests


class ThreadExit(Exception):
    pass


class MainFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(width=600)
        self._thread: FetcherThread | None = None

        # File selectors
        self.files_frame = ttk.Frame(self)
        self.files_frame.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        self.input_label = ttk.Label(self.files_frame, text="Файл маршрута со Spansh")
        self.input_textbox = ttk.Entry(self.files_frame, textvariable=self.input_var)
        self.select_input_btn = ttk.Button(self.files_frame, text="Выбрать...", command=self.select_input)

        self.output_label = ttk.Label(self.files_frame, text="Выходной файл для EDJP")
        default_output = Path.cwd() / 'output.route'
        self.output_var = tk.StringVar(value=str(default_output))
        self.output_textbox = ttk.Entry(self.files_frame, textvariable=self.output_var)
        self.select_output_btn = ttk.Button(self.files_frame, text="Выбрать...", command=self.select_output_dir)

        self.input_label.grid(row=0, column=0, sticky="W")
        self.input_textbox.grid(row=0, column=1, sticky="NWSE", padx=5)
        self.select_input_btn.grid(row=0, column=2)
        self.output_label.grid(row=1, column=0, sticky="W")
        self.output_textbox.grid(row=1, column=1, sticky="NWSE", padx=5)
        self.select_output_btn.grid(row=1, column=2)

        # Fetch coords checkbox
        self.coords_frame = ttk.Frame(self)
        self.fetch_coords_var = tk.BooleanVar(value=True)
        self.fetch_coords_checkbox = ttk.Checkbutton(self.coords_frame, text="Запрашивать координаты", variable=self.fetch_coords_var)
        self.fetch_coords_descr = ttk.Label(self.coords_frame, wraplength=600, text="При включении этой опции программа будет запрашивать игровой ID и координаты для каждой системы на маршруте со Spansh. Это займёт определённое время. Вы сможете прервать процесс в любой момент.\nПри отключении этой опции координаты будут эмулированы на основании расстояний между системами, однако некоторые фукции EDJP могут работать с таким маршрутом неправильно.")  # noqa
        self.fetch_coords_checkbox.grid(row=0, column=0, sticky="NWSE")
        self.fetch_coords_descr.grid(row=1, column=0, sticky="NWSE")

        # Buttons
        self.buttons_frame = ttk.Frame(self)
        self.buttons_frame.columnconfigure(0, weight=1)
        self.buttons_frame.columnconfigure(1, weight=1)
        self.start_button = ttk.Button(self.buttons_frame, text="Конвертировать", command=self.convert, padding=5)
        self.abort_button = ttk.Button(self.buttons_frame, text="Прервать", state=tk.DISABLED, command=self.abort, padding=5)
        self.start_button.grid(row=0, column=0, sticky="NWSE")
        self.abort_button.grid(row=0, column=1, sticky="NWSE")

        # Status
        self.status_var = tk.StringVar(value="Ready.")
        self.status_textbox = ttk.Label(self, textvariable=self.status_var)

        # Mappings
        self.files_frame.grid(row=0, column=0, sticky="NWSE")
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky="EW", pady=5)
        self.coords_frame.grid(row=2, column=0, sticky="NWSE")
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=3, column=0, sticky="EW", pady=5)
        self.buttons_frame.grid(row=4, column=0, sticky="NWSE")
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=5, column=0, sticky="EW", pady=5)
        self.status_textbox.grid(row=6, column=0, sticky="W")


    def select_input(self):
        selected = Path(self.input_var.get())
        initial = selected.parent if selected.parent.exists() else Path.cwd()
        path = fd.askopenfilename(
            title="Выбрать файл маршрута Spansh",
            filetypes=(
                ('Spansh CSV', '*.csv'),
                ('All', '*.*'),
            ),
            initialdir=initial
        )
        if path:
            self.input_var.set(str(Path(path)))


    def select_output_dir(self):
        selected = Path(self.output_var.get())
        selected_name = selected.name or 'output.route'
        selected_dir = selected.parent if selected.parent.exists() else Path.cwd()
        new_dir = fd.askdirectory(
            title="Выбрать выходной каталог",
            initialdir=selected_dir
        )
        if new_dir:
            self.output_var.set(str(Path(new_dir) / selected_name))


    def convert(self):
        if self._thread is not None:
            return
        self.ui_working_mode()

        input_path = Path(self.input_var.get())
        output_path = Path(self.output_var.get())
        if not input_path.exists():
            self.status_var.set("Input file not found!")
            self.ui_normal_mode()
            return
        if not output_path.parent.exists():
            self.status_var.set("Output directory not found!")
            self.ui_normal_mode()
            return

        if self.fetch_coords_var.get() is False:
            try:
                self.convert_without_fetching(input_path, output_path)
            except Exception:
                self.status_var.set("Unknown error occured!")
            self.ui_normal_mode()
            return
        else:
            self._thread = FetcherThread(
                input_path,
                output_path,
                self.__thread_finished_callback,
                self.__thread_crashed_callback,
                self.set_status
            )
            self._thread.start()


    def abort(self):
        if self._thread is None:
            return
        self._thread.stop()
        self._thread = None
        self.status_var.set("Aborted.")
        self.ui_normal_mode()


    def set_status(self, text: str):
        self.after(0, lambda: self.status_var.set(text))


    def __thread_finished_callback(self):
        def __inner():
            self._thread = None
            os.system(f'explorer /select,\"{self.output_var.get()}\"')
            self.ui_normal_mode()
        self.after(0, __inner)


    def __thread_crashed_callback(self):
        def __inner():
            self.status_var.set("Unknown error occured!")
            self._thread = None
            self.ui_normal_mode()
        self.after(0, __inner)


    def ui_working_mode(self):
        self.input_label.configure(state=tk.DISABLED)
        self.input_textbox.configure(state=tk.DISABLED)
        self.select_input_btn.configure(state=tk.DISABLED)
        self.output_label.configure(state=tk.DISABLED)
        self.output_textbox.configure(state=tk.DISABLED)
        self.select_output_btn.configure(state=tk.DISABLED)
        self.fetch_coords_checkbox.configure(state=tk.DISABLED)
        self.fetch_coords_descr.configure(state=tk.DISABLED)
        self.start_button.configure(state=tk.DISABLED)
        self.abort_button.configure(state=tk.NORMAL)

    def ui_normal_mode(self):
        self.input_label.configure(state=tk.NORMAL)
        self.input_textbox.configure(state=tk.NORMAL)
        self.select_input_btn.configure(state=tk.NORMAL)
        self.output_label.configure(state=tk.NORMAL)
        self.output_textbox.configure(state=tk.NORMAL)
        self.select_output_btn.configure(state=tk.NORMAL)
        self.fetch_coords_checkbox.configure(state=tk.NORMAL)
        self.fetch_coords_descr.configure(state=tk.NORMAL)
        self.start_button.configure(state=tk.NORMAL)
        self.abort_button.configure(state=tk.DISABLED)


    def convert_without_fetching(self, input_file: Path, output_file: Path):
        status = self.status_var.set
        status("Reading input file...")
        reader = csv.reader(open(input_file, 'r', encoding='utf-8'))
        reader.__next__()  # skip headers
        output = {
            "RouteWaypoints": [],
            "CurrentDestination": 0,
            "AutoSetNextDestination": True
        }
        current_x = 0
        status("Converting...")
        for row in reader:
            name, distance = row[0], float(row[1])
            if current_x >= 0:
                current_x -= distance
            else:
                current_x += distance
            output["RouteWaypoints"].append({
                "SystemName": name,
                "ID64": 0,
                "Coords": {
                    "x": current_x, "y": 0, "z": 0
                },
                "Notes": "",
                "Jumps": 1
            })
        status("Writing to output file...")
        with open(output_file, 'w', encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        status("Finished.")
        os.system(f'explorer /select,\"{output_file}\"')


class FetcherThread(threading.Thread):
    def __init__(
        self,
        input_file: Path,
        output_file: Path,
        on_finish_cb: Callable,
        on_exception_cb: Callable,
        set_status_cb: Callable[[str], None]
    ):
        self._stop_event = threading.Event()
        self._on_finish_cb = on_finish_cb
        self._on_exception_cb = on_exception_cb
        self._log_cb = set_status_cb
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file


    def sleep(self, timeout_s: float):
        STEP = 0.25
        slept = 0
        while slept < timeout_s:
            if self._stop_event.is_set():
                raise ThreadExit
            time.sleep(STEP)
            slept += STEP


    def stop(self):
        self._stop_event.set()
        self.join()


    def run(self):
        try:
            self.do_run()
        except ThreadExit:  # aborted while sleeping
            pass
        except Exception:
            self._on_exception_cb()


    def do_run(self):
        self._log_cb("Reading input file...")
        reader = csv.reader(open(self.input_file, 'r', encoding='utf-8'))
        reader.__next__()  # skip headers
        data = list(reader)
        total = len(data)
        output = {
            "RouteWaypoints": [],
            "CurrentDestination": 0,
            "AutoSetNextDestination": True
        }

        for i, row in enumerate(data):
            if self._stop_event.is_set():
                return
            name = row[0]
            output["RouteWaypoints"].append(self.fetch_system(name, i, total))
            self.sleep(1)

        self._log_cb("Writing to output file...")
        with open(self.output_file, 'w', encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        self._log_cb("Finished.")
        self._on_finish_cb()


    def fetch_system(self, name: str, current: int, total: int) -> dict:
        url = "https://spansh.co.uk/api/search"
        params = {
            "q": name,
        }
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"  # noqa
        }
        while True:
            self._log_cb(f"Fetching {name} ({current}/{total})...")
            try:
                res = requests.get(url, params=params, headers=headers, timeout=5)
                res.raise_for_status()
            except requests.RequestException:
                self._log_cb(f"Couldn't fetch data for {name}, retrying in 3 seconds... ({current}/{total})")
                self.sleep(3)
                continue

            id64 = x = y = z = None
            for record in res.json().get("results", []):
                if (
                    record.get("type") == "system"
                    and record.get("record", {}).get("name") == name
                ):
                    system_data: dict = record.get("record")
                    id64 = system_data.get("id64")
                    x = system_data.get("x")
                    y = system_data.get("y")
                    z = system_data.get("z")

            if None in (id64, x, y, z):
                print(f"Couldn't get the data needed for {name}. This is a Spansh problem.")
                raise ThreadExit

            return {
                "SystemName": name,
                "ID64": id64,
                "Coords": {
                    "x": x, "y": y, "z": z
                },
                "Notes": "",
                "Jumps": 1
            }


app = tk.Tk()
app.title("spansh2edjp")
app.resizable(False, False)
MainFrame(app).pack(padx=5, pady=5, fill="both")
app.mainloop()
