import os
import sys
import json
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QScrollArea,
    QLineEdit, QFrame, QMenu, QStatusBar, QMessageBox, QTabWidget, QApplication, QMainWindow
)
from PyQt6.QtCore import Qt


CONFIG_FILE = "logic/data/config.json"
JSON_SCHEMA_FILE = "logic/data/headers.json"
CAR_NAMES_FILE = "logic/data/carnames.json"

def ensure_folders():
    os.makedirs("data", exist_ok=True)

def load_config():
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def load_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1] if len(rows) > 1 else []

def reveal_in_explorer(path):
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if sys.platform.startswith("win"):
        os.startfile(folder)
    elif sys.platform.startswith("darwin"):
        os.system(f'open "{folder}"')
    else:
        os.system(f'xdg-open "{folder}"')


class ToolATab(QWidget):
    def __init__(self):
        super().__init__()
        ensure_folders()
        self.config = load_config()
        self.entries = {}

        self._build_ui()

        if path := self.config.get("split_data_path"):
            if os.path.isdir(path):
                self.load_split_data(path)

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # ---- Left panel ----
        left_panel = QVBoxLayout()
        main_layout.addLayout(left_panel, 1)

        left_panel.addWidget(QLabel("Split Data", alignment=Qt.AlignmentFlag.AlignLeft))
        choose_btn = QPushButton("Choose Folder")
        choose_btn.clicked.connect(self.choose_split_folder)
        left_panel.addWidget(choose_btn)

        self._build_tree(left_panel)

        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel, 2)

        self._build_form_area(right_panel)
        self._build_bottom_bar(right_panel)

    def _build_tree(self, layout):
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemExpanded.connect(self._on_tree_expand)
        self.tree.itemDoubleClicked.connect(self._on_tree_double)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_right_click)
        layout.addWidget(self.tree)

    def choose_split_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not path:
            return

        self.load_split_data(path)
        self.config["split_data_path"] = path
        save_config(self.config)

    def load_split_data(self, path):
        self.tree.clear()
        root_item = QTreeWidgetItem([f"📁 {path}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, path)
        self.tree.addTopLevelItem(root_item)
        self._add_dummy(root_item)
        root_item.setExpanded(True)

    def _add_dummy(self, item):
        dummy = QTreeWidgetItem([""])
        item.addChild(dummy)

    def _on_tree_expand(self, item):
        if item.childCount() == 1 and item.child(0).text(0) == "":
            item.removeChild(item.child(0))

            path = item.data(0, Qt.ItemDataRole.UserRole)
            try:
                for name in sorted(os.listdir(path)):
                    full = os.path.join(path, name)
                    label = f"📁 {name}" if os.path.isdir(full) else f"📄 {name}"
                    child = QTreeWidgetItem([label])
                    child.setData(0, Qt.ItemDataRole.UserRole, full)
                    item.addChild(child)
                    if os.path.isdir(full):
                        self._add_dummy(child)
            except PermissionError:
                pass

    def _on_tree_double(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path.lower().endswith(".csv"):
            self.load_csv_to_entries(path)

    def _on_tree_right_click(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        self.tree.setCurrentItem(item)

        menu = QMenu(self)
        menu.addAction("Open", lambda: self._menu_open(item))
        menu.addAction("Reveal in Explorer", lambda: reveal_in_explorer(item.data(0, Qt.ItemDataRole.UserRole)))
        menu.addAction("Copy Path", lambda: QApplication.clipboard().setText(item.data(0, Qt.ItemDataRole.UserRole)))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _menu_open(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path.lower().endswith(".csv"):
            self.load_csv_to_entries(path)

    def _build_form_area(self, layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.form_container = QWidget()
        self.form_layout = QVBoxLayout(self.form_container)
        scroll.setWidget(self.form_container)
        layout.addWidget(scroll)

    def _build_bottom_bar(self, layout):
        bar = QHBoxLayout()
        import_btn = QPushButton("Import CSV")
        import_btn.clicked.connect(self.import_csv)
        export_btn = QPushButton("Generate CSV")
        export_btn.clicked.connect(self.export_csv)
        self.status_label = QLabel("Ready")

        bar.addWidget(import_btn)
        bar.addWidget(export_btn)
        bar.addStretch()
        bar.addWidget(self.status_label)

        layout.addLayout(bar)

    def load_csv_to_entries(self, path):
        headers, values = load_csv(path)

        for i in reversed(range(self.form_layout.count())):
            widget = self.form_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        self.entries.clear()

        for h, v in zip(headers, values):
            row = QHBoxLayout()
            label = QLabel(h, minimumWidth=150)
            entry = QLineEdit()
            entry.setText(v)
            row.addWidget(label)
            row.addWidget(entry)
            container = QWidget()
            container.setLayout(row)
            self.form_layout.addWidget(container)
            self.entries[h] = entry

        self.status_label.setText(f"Loaded: {os.path.basename(path)}")

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if path:
            self.load_csv_to_entries(path)

    def export_csv(self):
        if not self.entries:
            QMessageBox.warning(self, "No data", "Nothing to export")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if not path:
            return

        with open(path, "w", newline="") as f:
            csv.writer(f).writerows([
                list(self.entries.keys()),
                [e.text() for e in self.entries.values()]
            ])
        self.status_label.setText(f"Saved: {os.path.basename(path)}")

    def get_state(self):
        return {
            "split_data_path": self.config.get("split_data_path", ""),
            "entries": {k: v.text() for k, v in self.entries.items()}
        }
    
    def load_state(self, state):
        path = state.get("split_data_path")
        if path and os.path.isdir(path):
            self.load_split_data(path)
            self.config["split_data_path"] = path
        entries = state.get("entries", {})
        for key, val in entries.items():
            if key in self.entries:
                self.entries[key].setText(val)