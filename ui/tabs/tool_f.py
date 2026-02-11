import os
import json
import pathlib
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QHBoxLayout,
    QTextEdit, QSlider, QCheckBox
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QTimer
from OpenGL.GL import *
from OpenGL.GLU import *
from PIL import Image

# =========================
# OBJ + TEXTURE LOADER (BMP and PNG)
# =========================

class OBJModel:
    def __init__(self, obj_path, console=None):
        self.vertices = []
        self.texcoords = []
        self.normals = []
        self.faces = []  
        self.groups = {}
        self.materials = {}  
        self.console = console
        self.texture_id = None 
        self.base_dir = os.path.dirname(obj_path)
        self.obj_path = obj_path

        self._log(f"[OBJModel] Loading OBJ: {obj_path}")
        self._load_obj(obj_path)

    def _log(self, msg):
        if self.console:
        # Append message to QTextEdit console widget
            self.console.append(msg)
        else:
        # Print to terminal for debugging
            print(msg)


    # -------------------------
    # OBJ LOADER
    # -------------------------
    def _load_obj(self, obj_path):
        current_group = None
        current_material = None

        with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if line.startswith("mtllib "):
                    self.mtl_file = line.split()[1]
                    self._log(f"[OBJModel] Found MTL file: {self.mtl_file}")

                elif line.startswith("usemtl "):
                    current_material = line.split()[1]

                elif line.startswith("g "):
                    current_group = line.split()[1]
                    self.groups[current_group] = []

                elif line.startswith("v "):
                    _, x, y, z = line.split()
                    self.vertices.append((float(x), float(y), float(z)))

                elif line.startswith("vt "):
                    _, u, v = line.split()
                    self.texcoords.append((float(u), float(v)))

                elif line.startswith("vn "):
                    _, x, y, z = line.split()
                    self.normals.append((float(x), float(y), float(z)))

                elif line.startswith("f "):
                    face = []
                    for v in line.split()[1:]:
                        parts = v.split("/")
                        vi = int(parts[0]) - 1
                        ti = int(parts[1]) - 1 if len(parts) > 1 and parts[1] else -1
                        ni = int(parts[2]) - 1 if len(parts) > 2 and parts[2] else -1
                        face.append((vi, ti, ni))

                    if current_group is None or current_group.lower().startswith("lod0"):
                        self.faces.append((face, current_material))
                        if current_group:
                            self.groups[current_group].append((face, current_material))

        QTimer.singleShot(0, self._load_car_texture)

    # -------------------------
    # CAR FOLDER FALLBACK (Look for '_night' in 'Night' folder)
    # -------------------------
    def _load_car_texture(self):
        obj_name = os.path.splitext(os.path.basename(self.obj_path))[0]
        carid_folder = os.path.dirname(self.obj_path)  # This gets the "Night" folder

        # Look for subfolders containing '_night' within the current "Night" folder
        night_folder = None
        for root, dirs, files in os.walk(carid_folder):
            for dir_name in dirs:
                if dir_name.lower().endswith("_night"):  # Look for folder names ending with '_night'
                    night_folder = os.path.join(root, dir_name)
                    break
            if night_folder:
                break
        
        if night_folder:
            bmp_path = os.path.join(night_folder, f"{obj_name}.bmp")
            png_path = os.path.join(night_folder, f"{obj_name}.png")

            # Check if bmp or png exists in the _night folder
            if os.path.exists(bmp_path):
                self.texture_id = self._load_texture(bmp_path)
                self._log(f"[OBJModel] Loaded texture (BMP): {bmp_path}")
            elif os.path.exists(png_path):
                self.texture_id = self._load_texture(png_path)
                self._log(f"[OBJModel] Loaded texture (PNG): {png_path}")
            else:
                self._log(f"[OBJModel] No texture found in {night_folder}")
        else:
            self._log(f"[OBJModel] No '_night' folder found in {carid_folder}")

    # -------------------------
    # OPENGL TEXTURE CREATION (BMP and PNG)
    # -------------------------
    def _load_texture(self, path):
        try:
            img = Image.open(path).transpose(Image.FLIP_TOP_BOTTOM)
            img_data = img.convert("RGBA").tobytes()

            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA,
                img.width, img.height,
                0, GL_RGBA, GL_UNSIGNED_BYTE,
                img_data
            )
            return tex_id
        except Exception as e:
            self._log(f"[OBJModel] Error loading texture: {path} - {str(e)}")
            return None


# =========================
# OPENGL VIEWPORT
# =========================

class GLViewport(QOpenGLWidget):
    def __init__(self, parent=None, console=None):
        super().__init__(parent)
        self.main_scene_model = None
        self.loaded_model = None
        self.show_main_scene = True
        self.console = console

        self.distance = 10.0
        self.yaw = 0.0
        self.pitch = 20.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        self.last_mouse_pos = None
        self.last_button = None
        self.wireframe = False
        self.brightness = 1.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

    def load_main_scene(self, path):
        self.main_scene_model = None  
        self.main_scene_model = OBJModel(path, console=self.console)
        self.update()

    def load_model(self, path):
        self.loaded_model = OBJModel(path, console=self.console)
        self.update()

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)

        glLightfv(GL_LIGHT0, GL_POSITION, (5, 5, 5, 1))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (1, 1, 1, 1))
        glLightfv(GL_LIGHT0, GL_SPECULAR, (1, 1, 1, 1))
        glMaterialfv(GL_FRONT, GL_SPECULAR, (1, 1, 1, 1))
        glMaterialf(GL_FRONT, GL_SHININESS, 32)
        glClearColor(0.05, 0.05, 0.08, 1)

    def resizeGL(self, w, h):
        if h == 0: h = 1
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60, w / h, 0.1, 100)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        glTranslatef(self.pan_x, self.pan_y, -self.distance)
        glRotatef(self.pitch, 1, 0, 0)
        glRotatef(self.yaw, 0, 1, 0)
        glScalef(2, 2, 2)

        self._draw_grid()
        self._draw_axis()

        if self.show_main_scene and self.main_scene_model:
            self._draw_model(self.main_scene_model)

        if self.loaded_model:
            self._draw_model(self.loaded_model)

    def _draw_grid(self):
        glColor3f(0.3, 0.3, 0.3)
        glBegin(GL_LINES)
        for i in range(-10, 11, 1):
            glVertex3f(i, 0, -10)
            glVertex3f(i, 0, 10)

            glVertex3f(-10, 0, i)
            glVertex3f(10, 0, i)
        glEnd()

    def _draw_axis(self):
        glLineWidth(2)
        glBegin(GL_LINES)
        # X-axis (red)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(-10, 0, 0)
        glVertex3f(10, 0, 0)

        # Y-axis (green)
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(0, -10, 0)
        glVertex3f(0, 10, 0)

        # Z-axis (blue)
        glColor3f(0.0, 0.0, 1.0)
        glVertex3f(0, 0, -10)
        glVertex3f(0, 0, 10)
        glEnd()

    def _draw_model(self, model):
        if self.wireframe:
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        else:
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

        glColor3f(self.brightness, self.brightness, self.brightness)

        for face, mtl in model.faces:
            if mtl and mtl in model.materials:
                glBindTexture(GL_TEXTURE_2D, model.materials[mtl])
            elif model.texture_id:
                glBindTexture(GL_TEXTURE_2D, model.texture_id)
            else:
                glBindTexture(GL_TEXTURE_2D, 0)

            glBegin(GL_TRIANGLES)
            for i in range(1, len(face) - 1):
                for vi, ti, ni in (face[0], face[i], face[i + 1]):
                    if ni >= 0: glNormal3fv(model.normals[ni])
                    if ti >= 0: glTexCoord2fv(model.texcoords[ti])
                    glVertex3fv(model.vertices[vi])
            glEnd()

        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    def mousePressEvent(self, event):
        self.last_mouse_pos = event.position()
        self.last_button = event.button()

    def mouseMoveEvent(self, event):
        if not self.last_mouse_pos: return
        delta = event.position() - self.last_mouse_pos
        self.last_mouse_pos = event.position()
        if self.last_button == Qt.MouseButton.LeftButton:
            self.yaw += delta.x() * 0.5
            self.pitch += delta.y() * 0.5
            self.pitch = max(-89, min(89, self.pitch))
        elif self.last_button == Qt.MouseButton.MiddleButton:
            self.pan_x += delta.x() * 0.01
            self.pan_y -= delta.y() * 0.01
        self.update()

    def mouseReleaseEvent(self, event):
        self.last_mouse_pos = None

    def wheelEvent(self, event):
        self.distance -= event.angleDelta().y() / 240
        self.distance = max(1.5, min(25.0, self.distance))
        self.update()



# =========================
# TOOL F TAB (Brightness slider + Main Scene toggle)
# =========================
class ToolFTab(QWidget):
    def __init__(self):
        super().__init__()
        self.viewport = GLViewport(self) 
        self._build_ui()
        self._load_default_model()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        
        console_slider_layout = QHBoxLayout()


        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        self.viewport.console = self.console


        slider_layout = QVBoxLayout() 
        slider_label = QLabel("Brightness:")
        self.brightness_slider = QSlider(Qt.Orientation.Vertical)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(50)
        self.brightness_slider.valueChanged.connect(self._update_brightness)
        self.brightness_value_label = QLabel("0.50")
        slider_layout.addWidget(slider_label)
        slider_layout.addWidget(self.brightness_slider)
        slider_layout.addWidget(self.brightness_value_label)


        console_slider_layout.addWidget(self.console, 2) 
        console_slider_layout.addLayout(slider_layout)    


        btn_layout = QVBoxLayout()
        load_btn = QPushButton("Load OBJ")
        wire_btn = QPushButton("Wireframe")
        load_btn.clicked.connect(self._load_model)
        wire_btn.clicked.connect(self._toggle_wireframe)
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(wire_btn)

        self.main_scene_checkbox = QCheckBox("Show Main Scene")
        self.main_scene_checkbox.setChecked(True)
        self.main_scene_checkbox.stateChanged.connect(self._toggle_main_scene)


        layout.addWidget(self.viewport, 4)  
        layout.addLayout(btn_layout)
        layout.addLayout(console_slider_layout) 
        layout.addWidget(self.main_scene_checkbox)
        layout.addWidget(QLabel("Console:"))

    def _load_default_model(self):
        project_root = pathlib.Path(__file__).resolve().parents[2]
        path = project_root / "mdl" / "scene" / "rd.obj"

        if path.exists():
            self.viewport.load_main_scene(str(path))
        else:
            self.console.append(f"Main scene OBJ not found: {path}")

    def _load_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open OBJ", "", "OBJ Files (*.obj)"
        )
        if path:
            self.viewport.load_model(path)

    def _toggle_wireframe(self):
        self.viewport.wireframe = not self.viewport.wireframe
        self.viewport.update()

    def _update_brightness(self, value):
        brightness = value / 100.0
        self.viewport.brightness = brightness
        self.brightness_value_label.setText(f"{brightness:.2f}")
        self.viewport.update()

    def _toggle_main_scene(self, state):
        project_root = pathlib.Path(__file__).resolve().parents[2]
        path = project_root / "mdl" / "scene" / "rd.obj"

        if path.exists():
            self.viewport.load_main_scene(str(path))  
        else:
            self.console.append(f"Main scene OBJ not found: {path}")

    def get_state(self):
        return {
            "show_main_scene": self.viewport.show_main_scene,
            "brightness": self.viewport.brightness,
            "wireframe": self.viewport.wireframe,
            "console_text": self.console.toPlainText()  
        }

    def load_state(self, state):
        if "show_main_scene" in state:
            self.viewport.show_main_scene = state["show_main_scene"]
            self.main_scene_checkbox.setChecked(self.viewport.show_main_scene)

        if "brightness" in state:
            self.viewport.brightness = state["brightness"]
            self.brightness_slider.setValue(int(self.viewport.brightness * 100))

        if "wireframe" in state:
            self.viewport.wireframe = state["wireframe"]

        if "console_text" in state:
            self.console.setPlainText(state["console_text"])
