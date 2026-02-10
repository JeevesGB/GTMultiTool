import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox,
    QFileDialog
)
from PyQt6.QtGui import QAction

# tab imports from the tabs folder - each tab is a separate file for better organization
from ui.tabs.tool_a import ToolATab
from ui.tabs.tool_b import ToolBTab
from ui.tabs.tool_c import ToolCTab
from ui.tabs.tool_d import ToolDTab
from ui.tabs.tool_e import ToolETab


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GT Multi Tool")
        self.setGeometry(100, 100, 1000, 700)
        self._create_tabs()
        self._create_menu()
        self._apply_theme()
# ---------- Tabs ----------
    def _create_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tool_a_tab = ToolATab()
        self.tool_b_tab = ToolBTab()
        self.tool_c_tab = ToolCTab()
        self.tool_d_tab = ToolDTab()
        self.tool_e_tab = ToolETab()

        self.tabs.addTab(self.tool_a_tab, "TXT 2 CSV")
        self.tabs.addTab(self.tool_b_tab, "pPainter")
        self.tabs.addTab(self.tool_c_tab, "GT2 Billboard Editor GUI")
        self.tabs.addTab(self.tool_d_tab, ".tim Viewer")
        self.tabs.addTab(self.tool_e_tab, "GT2 Model Tool GUI")
# ---------- Menu ----------
    def _create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        new_action = QAction("New Project", self)
        new_action.triggered.connect(self._file_new_project)

        open_action = QAction("Open Project...", self)
        open_action.triggered.connect(self._file_open_project)

        save_action = QAction("Save Project", self)
        save_action.triggered.connect(self._file_save_project)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)

        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        # Edit menu (placeholder)
        edit_menu = menubar.addMenu("Edit")


        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._help_about)
        help_menu.addAction(about_action)

    def _apply_theme(self):
        try:
            with open("ui/themes/t1.json", "r") as f:
                theme = json.load(f)
            bg_color = theme.get("background", "#B7C9DB")
            fg_color = theme.get("foreground", "#222222")
            self.setStyleSheet(f"QMainWindow {{ background-color: {bg_color}; color: {fg_color}; }}")
        except Exception as e:
            print(f"Theme apply failed: {e}")
            self.setStyleSheet("")

    def _file_new_project(self):
        self.tool_a_tab.load_state({})
        self.tool_b_tab.load_state({})
        self.tool_c_tab.load_state({})
        QMessageBox.information(self, "New Project", "New project started.")

    def _file_save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "GT Multi Tool Project (*.gtmulti)")
        if not path:
            return

        project = {
            "tool_a": self.tool_a_tab.get_state(),
            "tool_b": self.tool_b_tab.get_state(),
            "tool_c": self.tool_c_tab.get_state(),
            "tool_d": self.tool_d_tab.get_state(),
            "tool_e": self.tool_e_tab.get_state()
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(project, f, indent=4)
            QMessageBox.information(self, "Project Saved", f"Project saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def _file_open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "GT Multi Tool Project (*.gtmulti)")
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                project = json.load(f)

            self.tool_a_tab.load_state(project.get("tool_a", {}))
            self.tool_b_tab.load_state(project.get("tool_b", {}))
            self.tool_c_tab.load_state(project.get("tool_c", {}))
            self.tool_d_tab.load_state(project.get("tool_d", {}))
            self.tool_e_tab.load_state(project.get("tool_e", {}))

            QMessageBox.information(self, "Project Loaded", f"Project loaded from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    def _help_about(self):
        QMessageBox.information(
            self,
            "About",
            "GT Multi Tool\nVersion 0.0.1"
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())
