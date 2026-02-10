from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTabWidget, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt
import os
import subprocess
import threading
import json

ABOUT_URL = "https://github.com/pez2k/gt2tools/releases/tag/GT2BillboardEditor10"


class ToolCTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.exe_path = None
        self._build_ui()
        self.auto_find_exe()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.select_btn = QPushButton("Select GT2BillboardEditor.exe")
        self.select_btn.clicked.connect(self.select_exe)
        top_bar.addWidget(self.select_btn)

        self.about_btn = QPushButton("(?)")
        self.about_btn.setFixedWidth(30)
        self.about_btn.clicked.connect(self.show_about)
        top_bar.addWidget(self.about_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top_bar)

        action_bar = QHBoxLayout()
        self.extract_btn = QPushButton("Extract .crstims.tsd")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self.extract)
        action_bar.addWidget(self.extract_btn)

        self.build_btn = QPushButton("Build Brands.json")
        self.build_btn.setEnabled(False)
        self.build_btn.clicked.connect(self.build)
        action_bar.addWidget(self.build_btn)
        layout.addLayout(action_bar)

        self.status_label = QLabel("Idle")
        layout.addWidget(self.status_label)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.console_tab = QWidget()
        console_layout = QVBoxLayout(self.console_tab)
        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        console_layout.addWidget(self.console_text)
        self.tabs.addTab(self.console_tab, "Console")

        self.pools_tab = QWidget()
        pools_layout = QVBoxLayout(self.pools_tab)
        self.pools_text = QTextEdit()
        pools_layout.addWidget(self.pools_text)
        save_pools_btn = QPushButton("Save Pools.json")
        save_pools_btn.clicked.connect(lambda: self.save_json("Pools.json", self.pools_text))
        pools_layout.addWidget(save_pools_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.tabs.addTab(self.pools_tab, "Pools.json")

        self.brands_tab = QWidget()
        brands_layout = QVBoxLayout(self.brands_tab)
        self.brands_text = QTextEdit()
        brands_layout.addWidget(self.brands_text)
        save_brands_btn = QPushButton("Save Brands.json")
        save_brands_btn.clicked.connect(lambda: self.save_json("Brands.json", self.brands_text))
        brands_layout.addWidget(save_brands_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.tabs.addTab(self.brands_tab, "Brands.json")

    def log(self, text):
        self.console_text.append(text)

    def enable_buttons(self):
        self.extract_btn.setEnabled(True)
        self.build_btn.setEnabled(True)

    def auto_find_exe(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        exe = os.path.join(script_dir, "GT2BillboardEditor.exe")
        if os.path.isfile(exe):
            self.exe_path = exe
            self.log(f"Auto-detected EXE: {exe}")
            self.enable_buttons()

    def select_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select GT2BillboardEditor.exe", "", "Executable (*.exe)"
        )
        if path:
            self.exe_path = path
            self.log(f"EXE selected: {path}")
            self.enable_buttons()

    def show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About GT2 Billboard Editor GUI")
        msg.setText(
            "GT2 Billboard Editor GUI\n\n"
            "Graphical frontend for GT2BillboardEditor by pez2k.\n"
            "Allows extracting billboard data, editing Pools.json and Brands.json,\n"
            "and rebuilding billboard assets."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setDetailedText(f"Visit: {ABOUT_URL}")
        msg.exec()

    def extract(self):
        tsd, _ = QFileDialog.getOpenFileName(
            self, "Select .crstims.tsd", "", "GT2 Billboard TSD (*.tsd)"
        )
        if tsd:
            self.run_tool(tsd)

    def build(self):
        brands, _ = QFileDialog.getOpenFileName(
            self, "Select Brands.json", "", "Brands.json (Brands.json)"
        )
        if brands:
            self.run_tool(brands)

    def run_tool(self, input_path):
        self.log(f"\nRunning with: {input_path}")
        self.status_label.setText("Running...")
        self.status_label.setStyleSheet("color: orange;")
        threading.Thread(target=self._run_process, args=(input_path,), daemon=True).start()

    def _run_process(self, input_path):
        error = None
        try:
            subprocess.run(
                [self.exe_path, input_path],
                cwd=os.path.dirname(self.exe_path),
                capture_output=True,
                text=True
            )
        except Exception as e:
            error = str(e)
        self._on_process_done(error)

    def _on_process_done(self, error):
        if error:
            self.log(f"Exception: {error}")
            self.status_label.setText("Failed")
            self.status_label.setStyleSheet("color: red;")
        else:
            self.load_json_tabs()
            self.status_label.setText("Done")
            self.status_label.setStyleSheet("color: green;")

    def load_json_tabs(self):
        if not self.exe_path:
            return
        base = os.path.dirname(self.exe_path)
        self.load_json(os.path.join(base, "Pools.json"), self.pools_text)
        self.load_json(os.path.join(base, "Brands.json"), self.brands_text)

    def load_json(self, path, widget):
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            widget.setPlainText(json.dumps(data, indent=4))
        except Exception as e:
            self.log(f"Failed to load {os.path.basename(path)}: {e}")

    def save_json(self, filename, widget):
        if not self.exe_path:
            return
        path = os.path.join(os.path.dirname(self.exe_path), filename)
        raw = widget.toPlainText()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Invalid JSON", f"{filename} contains invalid JSON:\n\n{e}")
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            widget.setPlainText(json.dumps(data, indent=4))
            self.log(f"Saved {filename}")
            self.status_label.setText(f"{filename} saved")
            self.status_label.setStyleSheet("color: green;")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))


    def get_state(self):
        return {
            "exe_path": getattr(self, "exe_path", ""),
            "console_text": self.console_text.toPlainText(),
            "pools_text": self.pools_text.toPlainText(),
            "brands_text": self.brands_text.toPlainText()
        }

    def load_state(self, state):
        exe = state.get("exe_path")
        if exe and os.path.isfile(exe):
            self.exe_path = exe
            self.enable_buttons()
        self.console_text.setPlainText(state.get("console_text", ""))
        self.pools_text.setPlainText(state.get("pools_text", ""))
        self.brands_text.setPlainText(state.get("brands_text", ""))
