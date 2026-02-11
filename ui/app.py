import sys
import json
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox,
    QFileDialog
)
from PyQt6.QtGui import QAction, QIcon

# Import the InitTab and other tabs
from ui.tabs.init import InitTab
from ui.tabs.tool_a import ToolATab
from ui.tabs.tool_b import ToolBTab
from ui.tabs.tool_c import ToolCTab
from ui.tabs.tool_d import ToolDTab
from ui.tabs.tool_e import ToolETab
from ui.tabs.tool_f import ToolFTab

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GT Multi Tool")
        self.setGeometry(100, 100, 1000, 900)
        self.setWindowIcon(QIcon("ico.ico"))
        self._create_tabs()
        self._create_menu()
        self._apply_theme('light')  

    # ---------- Tabs ----------
    def _create_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Add InitTab first, then the other tool tabs
        self.init_tab = InitTab()  # Make sure you use InitTab
        self.tool_a_tab = ToolATab()
        self.tool_b_tab = ToolBTab()
        self.tool_c_tab = ToolCTab()
        self.tool_d_tab = ToolDTab()
        self.tool_e_tab = ToolETab()
        self.tool_f_tab = ToolFTab()
        
        self.tabs.addTab(self.init_tab, "Init")  # Add InitTab as the first tab
        self.tabs.addTab(self.tool_a_tab, "TXT 2 CSV")
        self.tabs.addTab(self.tool_b_tab, "pPainter")
        self.tabs.addTab(self.tool_c_tab, "GT2 Billboard Editor GUI")
        self.tabs.addTab(self.tool_d_tab, ".tim Viewer")
        self.tabs.addTab(self.tool_e_tab, "GT2 Model Tool GUI")
        self.tabs.addTab(self.tool_f_tab, ".obj Viewer")

    # ---------- Menu ----------
    def _create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        new_action = QAction("New Project", self)
        new_action.triggered.connect(self._file_new_project)
        file_menu.addAction(new_action)

        open_action = QAction("Open Project...", self)
        open_action.triggered.connect(self._file_open_project)
        file_menu.addAction(open_action)

        save_action = QAction("Save Project", self)
        save_action.triggered.connect(self._file_save_project)
        file_menu.addAction(save_action)
    
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("Edit")

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._help_about)
        help_menu.addAction(about_action)
    # ---------- Themes ----------
        theme_menu = menubar.addMenu("Themes")

        light_theme_action = QAction("Light Theme", self)
        light_theme_action.triggered.connect(lambda: self._apply_theme('light'))
        theme_menu.addAction(light_theme_action)

        dark_theme_action = QAction("Dark Theme", self)
        dark_theme_action.triggered.connect(lambda: self._apply_theme('dark'))
        theme_menu.addAction(dark_theme_action)

    # Placeholes for future themes
    # blue_theme_action = QAction("Blue Theme", self)
    # blue_theme_action.triggered.connect(lambda: self._apply_theme('blue'))
    # theme_menu.addAction(blue_theme_action)


    def _apply_theme(self, theme_name):
        try:
            # Construct the path to the theme file
            theme_file_path = f"ui/themes/{theme_name}.qss"
        
        # Open and read the theme file
            with open(theme_file_path, "r") as f:
                qss = f.read()
        
        # Apply the QSS to the application
            self.setStyleSheet(qss)
            print(f"Applied {theme_name} theme")
    
        except Exception as e:
            print(f"Failed to apply {theme_name} theme: {e}")
        # Optionally apply a default theme (if any)
            self.setStyleSheet("")  # Reset to default theme if loading fails


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
            "tool_e": self.tool_e_tab.get_state(),
            "tool_f": self.tool_f_tab.get_state(),
            #"tool_g": self.tool_g_tab.get_state(), - placeholder
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
            self.tool_f_tab.load_state(project.get("tool_f", {}))
            #self.tool_g_tab.load_state(project.get("tool_g", {})) - placeholder

            QMessageBox.information(self, "Project Loaded", f"Project loaded from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    def _help_about(self):
        QMessageBox.information(
            self,
            "About",
            "GT Multi Tool\nVersion 0.11.226" # version number is labelled (Version.DD.MMYY)
        )

