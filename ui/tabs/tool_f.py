import os
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QHBoxLayout
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, QTimer
from OpenGL.GL import *
from OpenGL.GLU import *
from PIL import Image


# =========================
# OBJ + MTL + TEXTURE LOADER
# =========================

class OBJModel:
    def __init__(self, obj_path):
        self.vertices = []
        self.texcoords = []
        self.normals = []
        self.faces = []
        self.texture_id = None

        self._load_obj(obj_path)

    def _load_obj(self, obj_path):
        base_dir = os.path.dirname(obj_path)

        with open(obj_path, "r") as f:
            for line in f:
                if line.startswith("v "):
                    _, x, y, z = line.split()
                    self.vertices.append((float(x), float(y), float(z)))

                elif line.startswith("vt "):
                    _, u, v = line.split()
                    self.texcoords.append((float(u), float(v)))

                elif line.startswith("vn "):
                    _, x, y, z = line.split()
                    self.normals.append((float(x), float(y), float(z)))

                elif line.startswith("mtllib "):
                    self._load_mtl(os.path.join(base_dir, line.split()[1]))

                elif line.startswith("f "):
                    face = []
                    for v in line.split()[1:]:
                        parts = v.split("/")
                        vi = int(parts[0]) - 1
                        ti = int(parts[1]) - 1 if len(parts) > 1 and parts[1] else -1
                        ni = int(parts[2]) - 1 if len(parts) > 2 and parts[2] else -1
                        face.append((vi, ti, ni))
                    self.faces.append(face)

    def _load_mtl(self, mtl_path):
        texture_file = None
        with open(mtl_path, "r") as f:
            for line in f:
                if line.startswith("map_Kd"):
                    texture_file = line.split()[1]

        if texture_file:
            self.texture_id = self._load_texture(
                os.path.join(os.path.dirname(mtl_path), texture_file)
            )

    def _load_texture(self, path):
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


# =========================
# OPENGL VIEWPORT
# =========================

class GLViewport(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.model = None

        # Camera
        self.distance = 6.0
        self.yaw = 0.0
        self.pitch = 20.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        self.last_mouse_pos = None
        self.last_button = None

        self.wireframe = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

    def load_model(self, path):
        self.model = OBJModel(path)
        self.update()

    # ---------- OpenGL ----------
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
        if h == 0:
            h = 1
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

        if self.model:
            self._draw_model()

    # ---------- Drawing ----------
    def _draw_grid(self, size=10, step=1):
        glDisable(GL_LIGHTING)
        glColor3f(0.3, 0.3, 0.3)
        glBegin(GL_LINES)
        for i in range(-size, size + 1, step):
            glVertex3f(i, 0, -size)
            glVertex3f(i, 0, size)
            glVertex3f(-size, 0, i)
            glVertex3f(size, 0, i)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_axis(self):
        glDisable(GL_LIGHTING)
        glBegin(GL_LINES)
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0); glVertex3f(2, 0, 0)
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0); glVertex3f(0, 2, 0)
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0); glVertex3f(0, 0, 2)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_model(self):
        if self.wireframe:
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        else:
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

        if self.model.texture_id:
            glBindTexture(GL_TEXTURE_2D, self.model.texture_id)

        glColor3f(1, 1, 1)
        glBegin(GL_TRIANGLES)

        for face in self.model.faces:
            for i in range(1, len(face) - 1):
                for vi, ti, ni in (face[0], face[i], face[i + 1]):
                    if ni >= 0:
                        glNormal3fv(self.model.normals[ni])
                    if ti >= 0:
                        glTexCoord2fv(self.model.texcoords[ti])
                    glVertex3fv(self.model.vertices[vi])

        glEnd()
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    # ---------- Input ----------
    def mousePressEvent(self, event):
        self.last_mouse_pos = event.position()
        self.last_button = event.button()

    def mouseMoveEvent(self, event):
        if not self.last_mouse_pos:
            return

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
# TOOL F TAB
# =========================

class ToolFTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_default_model()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.viewport = GLViewport(self)

        btn_layout = QHBoxLayout()
        load_btn = QPushButton("Load OBJ")
        wire_btn = QPushButton("Wireframe")

        load_btn.clicked.connect(self._load_model)
        wire_btn.clicked.connect(self._toggle_wireframe)

        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(wire_btn)

        layout.addWidget(self.viewport, 1)
        layout.addLayout(btn_layout)

    def _load_default_model(self):
        base = os.path.dirname(__file__)
        path = os.path.join(base, "mdl", "cube.obj")
        if os.path.exists(path):
            self.viewport.load_model(path)

    def _load_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open OBJ", "", "OBJ Files (*.obj)"
        )
        if path:
            self.viewport.load_model(path)

    def _toggle_wireframe(self):
        self.viewport.wireframe = not self.viewport.wireframe
        self.viewport.update()

    def get_state(self):
        return {}

    def load_state(self, state):
        pass
