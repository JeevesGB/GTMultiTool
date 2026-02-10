import os
import json
import gzip
import shutil
import tempfile
import datetime
import subprocess
import webbrowser
from functools import partial

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QTextEdit,
    QMessageBox, QLineEdit, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEventLoop
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor

# ---------------- Paths ----------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Project root (GTMultiTool) - use this so paths work both in development and when packaged
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
PEZ2K_DIR = os.path.join(PROJECT_ROOT, "external", "pez2k")
CARNAMES_PATH = os.path.join(PROJECT_ROOT, "logic", "data", "CarNames.json")  # fixed path

# ---------------- Tool buttons ----------------
MODEL_TOOL_ARGS = {
    "ConvertToEditable": "-oe",
    "ConvertToEditableSplit": "-oes",
    "ConvertModelsToGT2": "-o2",
}

# GT2TextureEditor arguments for texture operations
# User must add GT2TextureEditor.exe to external/pez2k folder
TEXTURE_TOOL_ARGS = {
    "DumpTexture": "-oe",  # Creates editable files (BMP + color palettes)
    "ConvertTexturesToGT2": "-o2",  # Converts back to CDP/CNP format
}


TOOL_ARGS = {**MODEL_TOOL_ARGS, **TEXTURE_TOOL_ARGS}



class SubprocessWorker(QThread):
    finished_signal = pyqtSignal(int, str, str)
    error = pyqtSignal(str)

    def __init__(self, cmd, cwd, timeout, use_console=False):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd
        self.timeout = timeout
        self.use_console = use_console
        self._result = None
        self._error = None

    def run(self):
        try:
            if self.use_console:
                import sys
                creationflags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                if isinstance(self.cmd, (list, tuple)):
                    proc = subprocess.Popen(self.cmd, cwd=self.cwd, shell=False, creationflags=creationflags)
                else:
                    if sys.platform == 'win32':
                        proc = subprocess.Popen(['cmd.exe', '/k', self.cmd], cwd=self.cwd, creationflags=creationflags)
                    else:
                        proc = subprocess.Popen(self.cmd, cwd=self.cwd, shell=True, creationflags=creationflags)
                proc.wait(timeout=self.timeout)
                rc = proc.returncode
                out = ''
                err = ''
            else:
                proc = subprocess.Popen(self.cmd, cwd=self.cwd, shell=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                out, err = proc.communicate(timeout=self.timeout)
                rc = proc.returncode

            self._result = (rc, out or '', err or '')
            self.finished_signal.emit(rc, out or '', err or '')
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            self._error = f"Operation timed out after {self.timeout} seconds"
            self.error.emit(self._error)
        except Exception as e:
            self._error = str(e)
            self.error.emit(self._error)


class ToolETab(QWidget):
    def __init__(self):
        super().__init__()
        self.car_names = {}  # CarID -> {"name": "Mazda Demio", "first": "...", "second": "..."}
        self.selected_files = []
        self.carobj_root = None
        self.output_root = None

        self._build_ui()         
        self._load_car_names()   

# ================= UI =================
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        folder_layout = QHBoxLayout()
        self.btn_carobj = QPushButton("Select CarObj Folder")
        self.btn_carobj.clicked.connect(self.open_folder)
        self.lbl_carobj = QLabel("No folder selected")
        folder_layout.addWidget(self.btn_carobj)
        folder_layout.addWidget(self.lbl_carobj)
        main_layout.addLayout(folder_layout)

        out_layout = QHBoxLayout()
        self.btn_output = QPushButton("Select Output Folder")
        self.btn_output.clicked.connect(self.select_output_folder)
        self.lbl_output = QLabel("No output folder selected")
        out_layout.addWidget(self.btn_output)
        out_layout.addWidget(self.lbl_output)
        main_layout.addLayout(out_layout)

        btns_layout = QHBoxLayout()
        for tool_name in TOOL_ARGS:
            btn = QPushButton(tool_name.replace("_", " "))
            btn.clicked.connect(partial(self.run_tool, tool_name))
            btns_layout.addWidget(btn)
        main_layout.addLayout(btns_layout)

        info_label = QLabel("ℹ Texture tools (DumpTexture, ConvertToCDP) require GT2TextureEditor.exe")
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        main_layout.addWidget(info_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search CarID or NameFirstPart / NameSecondPart...")
        self.search.textChanged.connect(self._apply_filter)
        main_layout.addWidget(self.search)

        self.batch_checkbox = QCheckBox("Batch mode (convert all selected cars)")
        self.batch_checkbox.setChecked(True)
        main_layout.addWidget(self.batch_checkbox)

        area_layout = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._update_selected_files)
        self.list_widget.itemClicked.connect(self._show_selected_json)
        area_layout.addWidget(self.list_widget, 1)

        right_layout = QVBoxLayout()

        self.lbl_json_filename = QLabel("CarNames.json")
        right_layout.addWidget(self.lbl_json_filename)
        json_btn_layout = QHBoxLayout()
        self.btn_edit = QPushButton("Edit")
        self.btn_edit.clicked.connect(self._on_edit_clicked)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        self.btn_cancel.setVisible(False)
        json_btn_layout.addWidget(self.btn_edit)
        json_btn_layout.addWidget(self.btn_cancel)
        json_btn_layout.addStretch()
        right_layout.addLayout(json_btn_layout)

        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        right_layout.addWidget(self.json_view, 2)

        
        right_layout.addWidget(QLabel("Console"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        right_layout.addWidget(self.console, 1)

        area_layout.addLayout(right_layout, 2)

        main_layout.addLayout(area_layout)

# ================= Car Names =================
    def _load_car_names(self):
        if not os.path.isfile(CARNAMES_PATH):
            self.console.append(f"CarNames.json not found: {CARNAMES_PATH}")
            return

        try:
            with open(CARNAMES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.car_names = {}
            self.list_widget.clear()
            for entry in data:
                cid = entry.get("CarId")
                if not cid or cid.lower() == "carid":
                    continue
                first = entry.get("NameFirstPart", "")
                second = entry.get("NameSecondPart", "")
                friendly = f"{first} {second}".strip()
                self.car_names[cid.lower()] = {"name": friendly, "first": first, "second": second}
                # Add to list widget with checkbox
                item = QListWidgetItem(friendly)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, cid.lower())
                self.list_widget.addItem(item)
        except Exception as e:
            self.console.append(f"Failed to load CarNames.json: {e}")

        # Show full JSON in right view
        try:
            with open(CARNAMES_PATH, "r", encoding="utf-8") as f:
                self.json_view.setPlainText(f.read())
            # ensure header shows original filename
            try:
                self.lbl_json_filename.setText(os.path.basename(CARNAMES_PATH))
            except Exception:
                pass
        except Exception:
            pass

# ================= JSON Edit / Backup =================
    def _backup_path(self):
        base = os.path.splitext(CARNAMES_PATH)[0]
        ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{base}_backup_{ts}.json"

    def _on_edit_clicked(self):
        if self.btn_edit.text() == "Save":
            self._save_editing()
            return

        try:
            backup = self._backup_path()
            shutil.copy2(CARNAMES_PATH, backup)
            self.current_backup = backup
            with open(backup, 'r', encoding='utf-8') as f:
                self.json_view.setPlainText(f.read())
            try:
                self.lbl_json_filename.setText(os.path.basename(backup))
            except Exception:
                pass
            self.json_view.setReadOnly(False)
            self.btn_edit.setText('Save')
            self.btn_cancel.setVisible(True)
            self.console.append(f"Created CarNames backup: {os.path.basename(backup)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup: {e}")

    def _on_cancel_clicked(self):
        try:
            if hasattr(self, 'current_backup') and os.path.isfile(self.current_backup):
                try:
                    os.remove(self.current_backup)
                except Exception:
                    pass
                del self.current_backup
            with open(CARNAMES_PATH, 'r', encoding='utf-8') as f:
                self.json_view.setPlainText(f.read())
            try:
                self.lbl_json_filename.setText(os.path.basename(CARNAMES_PATH))
            except Exception:
                pass
            self.json_view.setReadOnly(True)
            self.btn_edit.setText('Edit')
            self.btn_cancel.setVisible(False)
            self.console.append('Edit cancelled; original CarNames.json restored in view.')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to cancel edit: {e}")

    def _save_editing(self):
        try:
            text = self.json_view.toPlainText()
            parsed = json.loads(text)
        except Exception as e:
            QMessageBox.critical(self, "Invalid JSON", f"Please fix JSON errors before saving:\n{e}")
            return

        if not hasattr(self, 'current_backup'):
            QMessageBox.critical(self, "Error", "Backup file not found. Cannot save.")
            return

        try:
            with open(self.current_backup, 'w', encoding='utf-8') as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            self.json_view.setReadOnly(True)
            self.btn_edit.setText('Edit')
            self.btn_cancel.setVisible(False)
            self.console.append(f"Saved edits to backup: {os.path.basename(self.current_backup)}")
            try:
                self._apply_car_names_from_json_text(text)
            except Exception as e:
                self.console.append(f"Warning: could not apply edited CarNames to UI: {e}")
            try:
                self.lbl_json_filename.setText(os.path.basename(self.current_backup))
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save backup: {e}")

    def _apply_car_names_from_json_text(self, text):
        data = json.loads(text)
        self.car_names = {}
        self.list_widget.clear()
        for entry in data:
            cid = entry.get('CarId')
            if not cid or str(cid).lower() == 'carid':
                continue
            first = entry.get('NameFirstPart', '')
            second = entry.get('NameSecondPart', '')
            friendly = f"{first} {second}".strip()
            self.car_names[str(cid).lower()] = {"name": friendly, "first": first, "second": second}
            item = QListWidgetItem(friendly)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, str(cid).lower())
            self.list_widget.addItem(item)

# ================= Search =================
    def _apply_filter(self, text):
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            name = item.text().lower()
            carid = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(not (text in name or text in carid))

# ================= Selection =================
    def _update_selected_files(self, item):
        self.selected_files = [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                               for i in range(self.list_widget.count())
                               if self.list_widget.item(i).checkState() == Qt.CheckState.Checked]

    def _show_selected_json(self, item):
        carid = item.data(Qt.ItemDataRole.UserRole)
        if not carid:
            return
        cursor = self.json_view.textCursor()
        text = self.json_view.toPlainText()
        pos = text.lower().find(f'"carid": "{carid}"')
        if pos != -1:
            cursor.setPosition(0)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            fmt_clear = QTextCharFormat()
            fmt_clear.setBackground(QColor("white"))
            cursor.mergeCharFormat(fmt_clear)
            cursor.clearSelection()

            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor,
                                len(f'"CarId": "{carid}"'))
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("yellow"))
            cursor.mergeCharFormat(fmt)
            self.json_view.setTextCursor(cursor)

# ================= Conversion =================
    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_root = folder
            self.lbl_output.setText(folder)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select CarObj Folder")
        if folder:
            self.carobj_root = folder
            self.lbl_carobj.setText(folder)

    def _check_exe(self, tool_name):
        is_texture_tool = tool_name in TEXTURE_TOOL_ARGS
        
        if is_texture_tool:
            exe_path = os.path.join(PEZ2K_DIR, "GT2TextureEditor.exe")
            exe_name = "GT2TextureEditor.exe"
            download_url = "https://github.com/pez2k/gt2tools/releases/tag/GT2TextureEditor03"
            tool_display_name = "GT2TextureEditor"
        else:
            exe_path = os.path.join(PEZ2K_DIR, "GT2ModelTool.exe")
            exe_name = "GT2ModelTool.exe"
            download_url = "https://github.com/pez2k/gt2tools/releases/tag/GT2ModelTool210"
            tool_display_name = "GT2ModelTool"
        
        if not os.path.isfile(exe_path):
            res = QMessageBox.question(
                self,
                f"{exe_name} Missing",
                f"{exe_name} not found in:\n{PEZ2K_DIR}\n\nDownload {tool_display_name} from GitHub?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if res == QMessageBox.StandardButton.Yes:
                webbrowser.open(download_url)
            return False
        return True

    def run_tool(self, tool_name):
        if not self.selected_files:
            QMessageBox.warning(self, "No selection", "No files selected.")
            return
        if not self.output_root:
            QMessageBox.warning(self, "No output folder", "Select an output folder.")
            return
        if not self._check_exe(tool_name):
            return

        is_texture_tool = tool_name in TEXTURE_TOOL_ARGS
        if is_texture_tool:
            exe_path = os.path.join(PEZ2K_DIR, "GT2TextureEditor.exe")
            arg = TEXTURE_TOOL_ARGS.get(tool_name)
        else:
            exe_path = os.path.join(PEZ2K_DIR, "GT2ModelTool.exe")
            arg = MODEL_TOOL_ARGS.get(tool_name)
        if not arg:
            QMessageBox.critical(self, "Error", f"No argument defined for tool: {tool_name}")
            return

        # Collect all files to process (both day and night for each car)
        files_to_process = []  # List of (src_file, is_night, carid, file_type)
        
        # For dedicated Convert buttons, determine whether this is a
        # models-to-GT2 or textures-to-GT2 operation.
        # Models: .json files -> .cdo/.cno
        # Textures: editable folders -> .cdp/.cnp
        is_convert_all_models = tool_name == "ConvertModelsToGT2"
        is_convert_all_textures = tool_name == "ConvertTexturesToGT2"
        is_convert_all = is_convert_all_models or is_convert_all_textures
        
        # For ConvertToGT2, use output_root as source (for editing workflow)
        # For other tools, use carobj_root as source
        source_root = self.output_root if is_convert_all else self.carobj_root
        
        if not source_root:
            if is_convert_all:
                QMessageBox.warning(self, "No folder selected", "Please select an Output folder first.")
            else:
                QMessageBox.warning(self, "No folder selected", "Please select a CarObj folder first.")
            return
        
        # Determine file extensions based on tool type
        if is_texture_tool and not is_convert_all:
            day_ext = ".cdp"
            night_ext = ".cnp"
        else:
            day_ext = ".cdo"
            night_ext = ".cno"
        
        for carid in self.selected_files:
            # Get the full car name from CarID
            car_name = self.car_names.get(carid, {}).get("name", carid)
            
            # For ConvertToGT2, look for both model files (.json) and texture files (.cdp/.cnp)
            if is_convert_all:
                # For Convert operations, look in Day/Night folders within output_root
                # Each car has its own folder (using car name) with Day/Night subfolders
                car_folder = os.path.join(source_root, car_name)

                # If this is a models conversion, look for .json model files
                if is_convert_all_models:
                    day_model = os.path.join(car_folder, "Day", carid + ".json")
                    night_model = os.path.join(car_folder, "Night", carid + ".json")
                    if os.path.isfile(day_model):
                        files_to_process.append((day_model, False, carid, "model"))
                    if os.path.isfile(night_model):
                        files_to_process.append((night_model, True, carid, "model"))

                # If this is a textures conversion, look for editable texture folders
                if is_convert_all_textures:
                    day_texture = os.path.join(car_folder, "Day", carid)
                    night_texture = os.path.join(car_folder, "Night", carid)
                    night_texture_alt = os.path.join(car_folder, "Night", carid + "_night")
                    # Check if day texture folder exists and contains any BMP file
                    if os.path.isdir(day_texture):
                        day_bmps = [f for f in os.listdir(day_texture) if f.lower().endswith('.bmp')]
                        if day_bmps:
                            files_to_process.append((day_texture, False, carid, "texture"))
                    # Check night textures: try both carid and carid_night folder names
                    if os.path.isdir(night_texture):
                        night_bmps = [f for f in os.listdir(night_texture) if f.lower().endswith('.bmp')]
                        if night_bmps:
                            files_to_process.append((night_texture, True, carid, "texture"))
                    elif os.path.isdir(night_texture_alt):
                        # Try the _night suffix folder
                        night_bmps = [f for f in os.listdir(night_texture_alt) if f.lower().endswith('.bmp')]
                        if night_bmps:
                            files_to_process.append((night_texture_alt, True, carid, "texture"))
            else:
                # Original logic for other tools
                day_file = os.path.join(self.carobj_root, carid + day_ext)
                night_file = os.path.join(self.carobj_root, carid + night_ext)
                
                if os.path.isfile(day_file):
                    files_to_process.append((day_file, False, carid, "file"))
                if os.path.isfile(night_file):
                    files_to_process.append((night_file, True, carid, "file"))
                
                if not (os.path.isfile(day_file) or os.path.isfile(night_file)):
                    ext_msg = f"texture ({day_ext}/{night_ext})" if is_texture_tool else f"model ({day_ext}/{night_ext})"
                    self.console.append(f"File not found for CarID {carid}: {ext_msg} files")

        if not files_to_process:
            QMessageBox.warning(self, "No files", "No files found to process.")
            return

        # Log detailed information about the operation
        source_folder_display = "Output" if is_convert_all else "CarObj"
        self.console.append(f"\n{'='*70}")
        self.console.append(f"Operation: {tool_name}")
        self.console.append(f"Source folder: {source_root}")
        self.console.append(f"Output folder: {self.output_root}")
        self.console.append(f"Files to process: {len(files_to_process)}")
        self.console.append(f"{'='*70}\n")

        # Process all collected files
        for src_file, is_night, carid, file_type in files_to_process:
            try:
                # For Convert operations, handle both models and textures
                if is_convert_all:
                    is_texture = file_type == "texture"
                    exe_path = os.path.join(PEZ2K_DIR, "GT2TextureEditor.exe") if is_texture else os.path.join(PEZ2K_DIR, "GT2ModelTool.exe")
                    # Select the correct renamed arguments for models/textures
                    if is_texture:
                        arg = TEXTURE_TOOL_ARGS.get("ConvertTexturesToGT2")
                    else:
                        arg = MODEL_TOOL_ARGS.get("ConvertModelsToGT2")
                
                # Handle .gz if needed (only for model files, not texture folders)
                work_file = src_file
                tmp_decompress = None
                if isinstance(src_file, str) and src_file.lower().endswith(".gz"):
                    tmp_decompress = tempfile.mkdtemp()
                    out = os.path.join(tmp_decompress, os.path.basename(src_file[:-3]))
                    with gzip.open(src_file, "rb") as f_in, open(out, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    work_file = out

                version_folder = "Night" if is_night else "Day"
                
                # For Convert operations, save to a "new" subfolder
                if is_convert_all:
                    out_dir = os.path.join(self.output_root, car_name, version_folder, "new")
                else:
                    out_dir = os.path.join(self.output_root, car_name, version_folder)
                os.makedirs(out_dir, exist_ok=True)

                # Display appropriate file type
                if is_convert_all and file_type == "texture":
                    display_type = "(.cnp)" if is_night else "(.cdp)"
                else:
                    display_type = "(.cnp)" if is_night else "(.cdp)" if is_texture_tool and not is_convert_all else ("(.cno)" if is_night else "(.cdo)")
                
                self.console.append(f"\n{'─'*70}")
                self.console.append(f"→ Processing: {car_name} {display_type} [{version_folder}]")
                self.console.append(f"  File type: {file_type}")
                self.console.append(f"  Source: {os.path.basename(src_file) if os.path.isfile(src_file) else os.path.basename(src_file)}")
                self.console.append(f"  Destination: {version_folder}/new" if is_convert_all else f"  Destination: {version_folder}")
                self.console.append(f"  Running {tool_name}...")

                # Run the tool in a temporary directory to collect output
                tmp_work_dir = tempfile.mkdtemp()
                
                # Validate source file/folder exists
                if not os.path.exists(work_file):
                    self.console.append(f"  ✗ Error: Source file not found: {work_file}")
                    continue
                
                # Copy the source file to temp directory (for files, not folders)
                try:
                    if os.path.isfile(work_file):
                        tmp_src = os.path.join(tmp_work_dir, os.path.basename(work_file))
                        shutil.copy2(work_file, tmp_src)
                    else:
                        # For folders (texture), copy the entire folder
                        tmp_src = os.path.join(tmp_work_dir, os.path.basename(work_file))
                        shutil.copytree(work_file, tmp_src)
                    # If we're converting a model JSON back to GT2, also copy companion OBJ/MTL files
                    # so GT2ModelTool can find them (it expects .obj present alongside .json)
                    if is_convert_all and file_type == "model":
                        src_dir = os.path.dirname(work_file)
                        base_name = os.path.splitext(os.path.basename(work_file))[0]
                        companion_names = [base_name, base_name + "_night"]
                        for name in companion_names:
                            for ext in (".obj", ".mtl"):
                                companion_path = os.path.join(src_dir, name + ext)
                                if os.path.isfile(companion_path):
                                    try:
                                        shutil.copy2(companion_path, os.path.join(tmp_work_dir, os.path.basename(companion_path)))
                                    except Exception:
                                        pass
                        # If we're converting the NIGHT variant but only the base OBJ/MTL
                        # exists, duplicate the base files to create the *_night variants
                        # that GT2ModelTool may expect (e.g. x2cpn -> x2cpn_night.obj).
                        if is_night:
                            try:
                                base_obj = os.path.join(tmp_work_dir, base_name + ".obj")
                                night_obj = os.path.join(tmp_work_dir, base_name + "_night.obj")
                                if os.path.isfile(base_obj) and not os.path.isfile(night_obj):
                                    shutil.copy2(base_obj, night_obj)
                                base_mtl = os.path.join(tmp_work_dir, base_name + ".mtl")
                                night_mtl = os.path.join(tmp_work_dir, base_name + "_night.mtl")
                                if os.path.isfile(base_mtl) and not os.path.isfile(night_mtl):
                                    shutil.copy2(base_mtl, night_mtl)
                            except Exception:
                                pass
                except Exception as e:
                    self.console.append(f"  ✗ Error copying file: {str(e)}")
                    try:
                        shutil.rmtree(tmp_work_dir)
                    except:
                        pass
                    continue
                
                # Use absolute paths to avoid embedded ..\ in the command passed to cmd.exe
                exe_path_abs = os.path.abspath(exe_path)
                tmp_src_abs = os.path.abspath(tmp_src)
                cmd_str = f'"{exe_path_abs}" {arg} "{tmp_src_abs}"'
                
                # Set timeout based on operation type
                timeout = 300 if tool_name == "DumpTexture" else 120 if is_convert_all else 60
                
                try:
                    self.console.append(f"  Command: {os.path.basename(exe_path)} {arg}")
                    self.console.append(f"  Processing (timeout in {timeout}s)...")
                    
                    # Run external tool in a worker thread so GUI stays responsive
                    use_console = ("ModelTool" in exe_path and "-o2" in arg)
                    # For interactive console runs, pass command as list to avoid quoting issues with cmd.exe
                    if use_console and os.name == 'nt':
                        cmd_for_worker = [exe_path_abs, arg, tmp_src_abs]
                    else:
                        cmd_for_worker = cmd_str
                    worker = SubprocessWorker(cmd_for_worker, tmp_work_dir, timeout, use_console=use_console)
                    loop = QEventLoop()

                    def _on_finished(rc, out, err):
                        loop.quit()

                    def _on_error(msg):
                        self.console.append(f"  ✗ Error: {msg}")
                        loop.quit()

                    worker.finished_signal.connect(_on_finished)
                    worker.error.connect(_on_error)

                    # If the tool requires interactive console, prompt the user first
                    if use_console:
                        reply = QMessageBox.question(
                            self,
                            "Run GT2ModelTool",
                            "This operation requires you to interact with GT2ModelTool in a separate console window.\n\nDo you want to open the tool now?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        )
                        if reply == QMessageBox.StandardButton.No:
                            self.console.append("  ✗ Aborted by user: interactive conversion skipped")
                            # Clean up temp and skip this file
                            try:
                                shutil.rmtree(tmp_work_dir)
                            except Exception:
                                pass
                            if tmp_decompress:
                                try:
                                    shutil.rmtree(tmp_decompress)
                                except Exception:
                                    pass
                            continue

                    self.console.append(f"  ℹ Launching external tool{(' (interactive console)' if use_console else '')}...")
                    worker.start()
                    # Wait here but keep the Qt event loop running so UI stays responsive
                    loop.exec()

                    # After worker finishes, collect result or error
                    if getattr(worker, '_error', None):
                        # Re-raise as TimeoutExpired if appropriate so outer except handles it
                        if 'timed out' in (worker._error or '').lower():
                            raise subprocess.TimeoutExpired(cmd_str, timeout)
                        else:
                            raise Exception(worker._error)

                    rc, stdout_data, stderr_data = worker._result if worker._result else (1, '', '')
                    result = type('obj', (object,), {'returncode': rc, 'stdout': stdout_data, 'stderr': stderr_data})()
                except subprocess.TimeoutExpired:
                    self.console.append(f"  ✗ Error: Operation timed out after {timeout} seconds")
                    try:
                        shutil.rmtree(tmp_work_dir)
                    except:
                        pass
                    if tmp_decompress:
                        try:
                            shutil.rmtree(tmp_decompress)
                        except:
                            pass
                    continue
                
                if result.returncode != 0:
                    self.console.append(f"  ✗ Error: {result.stderr if result.stderr else 'Unknown error'}")
                else:
                    # Check for actual output - if no files were created, something went wrong
                    files_in_temp = [f for f in os.listdir(tmp_work_dir) if os.path.isfile(os.path.join(tmp_work_dir, f))]
                    if result.stdout:
                        self.console.append(f"  Output: {result.stdout[:200]}")
                    
                    # Move all generated files to output directory
                    base_name = os.path.splitext(os.path.basename(work_file))[0]
                    input_file_ext = os.path.splitext(work_file)[1].lower()
                    
                    # For ConvertToGT2, we're looking for game format files (.cdo, .cno, .cdp, .cnp)
                    if is_convert_all:
                        if file_type == "model":
                            # Converting .json back to .cdo/.cno
                            file_extensions = ['.cdo', '.cno']
                        else:
                            # Converting texture folder back to .cdp/.cnp
                            file_extensions = ['.cdp', '.cnp']
                    else:
                        # For night models, the tool adds "_night" suffix to output files
                        search_patterns = [base_name]
                        if is_night and not is_texture_tool:
                            # Only model tools add "_night" suffix, texture tools don't
                            search_patterns.append(base_name + "_night")
                        
                        # Determine output file extensions based on tool type
                        if is_texture_tool:
                            # Texture tools output editable folders with BMP and PAL files
                            # The tool creates a folder, so we need to move the entire folder
                            file_extensions = []  # Will handle as folder
                        else:
                            # Model tools output model files
                            file_extensions = ['.json', '.obj', '.mtl', '.cdo', '.cno', '.cdp', '.cnp']
                    
                    files_moved = 0
                    
                    # For ConvertToGT2, look for output files with specific extensions
                    if is_convert_all:
                        for item in os.listdir(tmp_work_dir):
                            item_path = os.path.join(tmp_work_dir, item)
                            # Skip the input file
                            if os.path.isfile(item_path) and os.path.splitext(item)[1].lower() == input_file_ext:
                                continue
                            
                            item_ext = os.path.splitext(item)[1].lower()
                            if item_ext in file_extensions:
                                dest_path = os.path.join(out_dir, item)
                                shutil.move(item_path, dest_path)
                                self.console.append(f"  Saved: {os.path.join(car_name, version_folder, 'new', item)}")
                                files_moved += 1
                            elif os.path.isdir(item_path):
                                # Move folder (for texture conversions)
                                dest_path = os.path.join(out_dir, item)
                                shutil.move(item_path, dest_path)
                                self.console.append(f"  Saved: {os.path.join(car_name, version_folder, 'new', item)} (folder)")
                                files_moved += 1
                        # If this was a night model conversion and GT2ModelTool produced a
                        # .cdo (day) file instead of a .cno, duplicate it to create the
                        # expected night game format (.cno) so the Night/new folder contains
                        # the correct file type.
                        if file_type == "model" and is_night:
                            try:
                                for out_item in os.listdir(out_dir):
                                    if out_item.lower().endswith('.cdo'):
                                        base = os.path.splitext(out_item)[0]
                                        cdo_path = os.path.join(out_dir, out_item)
                                        cno_name = base + '.cno'
                                        cno_path = os.path.join(out_dir, cno_name)
                                        if not os.path.exists(cno_path):
                                            shutil.copy2(cdo_path, cno_path)
                                            self.console.append(f"  Saved: {os.path.join(car_name, version_folder, 'new', cno_name)}")
                                            files_moved += 1
                                            # Remove the .cdo if present so night folder contains .cno only
                                            try:
                                                if os.path.exists(cdo_path):
                                                    os.remove(cdo_path)
                                                    self.console.append(f"  Removed: {os.path.join(car_name, version_folder, 'new', out_item)}")
                                                    # adjust files_moved if desired (we already counted the .cno)
                                            except Exception as e:
                                                self.console.append(f"  ⚠ Warning: Could not remove .cdo file: {e}")
                            except Exception as e:
                                self.console.append(f"  ⚠ Warning: Could not create night .cno: {e}")
                    # For texture tools (DumpTexture), move the entire output folder
                    elif is_texture_tool:
                        for item in os.listdir(tmp_work_dir):
                            item_path = os.path.join(tmp_work_dir, item)
                            # Skip the input file
                            if os.path.isfile(item_path) and os.path.splitext(item)[1].lower() == input_file_ext:
                                continue
                            dest_path = os.path.join(out_dir, item)
                            if os.path.isdir(item_path):
                                # Move folder
                                shutil.move(item_path, dest_path)
                                self.console.append(f"  Saved: {os.path.join(car_name, version_folder, item)} (folder)")
                                files_moved += 1
                            elif os.path.isfile(item_path):
                                # Move file
                                shutil.move(item_path, dest_path)
                                self.console.append(f"  Saved: {os.path.join(car_name, version_folder, item)}")
                                files_moved += 1
                    else:
                        # For model tools (ConvertToEditable, etc), move specific file extensions
                        search_patterns = [base_name]
                        if is_night and not is_texture_tool:
                            search_patterns.append(base_name + "_night")
                        
                        for pattern in search_patterns:
                            for ext in file_extensions:
                                tmp_out = os.path.join(tmp_work_dir, pattern + ext)
                                if os.path.isfile(tmp_out):
                                    # For night models with _night suffix, rename back to base name
                                    if is_night and "_night" in pattern:
                                        dest_file = os.path.join(out_dir, base_name + ext)
                                    else:
                                        dest_file = os.path.join(out_dir, pattern + ext)
                                    shutil.move(tmp_out, dest_file)
                                    self.console.append(f"  Saved: {os.path.join(car_name, version_folder, os.path.basename(dest_file))}")
                                    files_moved += 1
                        
                        # If no files were found with expected pattern, just move everything that exists (except input file)
                        if files_moved == 0:
                            for item in os.listdir(tmp_work_dir):
                                item_path = os.path.join(tmp_work_dir, item)
                                if os.path.isfile(item_path):
                                    item_ext = os.path.splitext(item)[1].lower()
                                    # Skip files with same extension as input (the input file itself)
                                    if item_ext == input_file_ext:
                                        continue
                                    dest_file = os.path.join(out_dir, item)
                                    shutil.move(item_path, dest_file)
                                    self.console.append(f"  Saved: {os.path.join(car_name, version_folder, item)}")
                                    files_moved += 1
                        
                        if files_moved == 0:
                            self.console.append(f"  ⚠ Warning: No output files generated. Tool may not support {display_type} files.")
                    
                    self.console.append(f"  ✓ Success! Saved {files_moved} file(s) to: {out_dir}")
                    self.console.append(f"✓ Completed: {car_name} {display_type}\n")
                
                # Clean up temp directory
                try:
                    shutil.rmtree(tmp_work_dir)
                except Exception as e:
                    self.console.append(f"Warning: Could not clean temp directory: {e}")
                
                # Clean up decompression temp directory if created
                if tmp_decompress:
                    try:
                        shutil.rmtree(tmp_decompress)
                    except Exception:
                        pass
                
            except Exception as e:
                self.console.append(f"Exception processing {carid}: {str(e)}")

# ================= Save / Load =================
    def get_state(self):
        return {
            "carobj": self.carobj_root,
            "output": self.output_root,
            "batch": self.batch_checkbox.isChecked()
        }

    def load_state(self, state):
        if state.get("carobj"):
            self.carobj_root = state["carobj"]
            self.lbl_carobj.setText(state["carobj"])
        if state.get("output"):
            self.output_root = state["output"]
            self.lbl_output.setText(state["output"])
        self.batch_checkbox.setChecked(state.get("batch", True))
