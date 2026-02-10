import os
import struct
from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QScrollArea, QColorDialog,
    QGraphicsView, QGraphicsScene, QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtGui import QColor, QImage, QPixmap, QPainter
from PyQt6.QtCore import Qt

# ---------------- TIM Loader ----------------
def load_tim(filepath):
    with open(filepath, 'rb') as f:
        if f.read(4) != b'\x10\x00\x00\x00':
            raise ValueError("Not a TIM file")
        flags = struct.unpack('<I', f.read(4))[0]
        bpp_flag = flags & 3
        clut_flag = bool(flags & 8)
        bpp = {0:4,1:8,2:16,3:24}[bpp_flag]

        clut = None
        clut_w = clut_h = 0
        if clut_flag:
            clut_len = struct.unpack('<I', f.read(4))[0]
            _, _, clut_w, clut_h = struct.unpack('<HHHH', f.read(8))
            raw = f.read(clut_len-12)
            clut = []
            for i in range(clut_w*clut_h):
                val = struct.unpack_from('<H', raw, i*2)[0]
                r = (val & 0x1F) << 3
                g = ((val >> 5) & 0x1F) << 3
                b = ((val >> 10) & 0x1F) << 3
                clut.append((r,g,b))

        img_len = struct.unpack('<I', f.read(4))[0]
        _, _, w16, h = struct.unpack('<HHHH', f.read(8))
        img = f.read(img_len-12)
        data = []

        if bpp == 4:
            width = w16*4
            off = 0
            for y in range(h):
                row=[]
                for _ in range(w16):
                    word = struct.unpack_from('<H', img, off)[0]
                    off+=2
                    for i in range(4):
                        row.append((word >> (4*i)) & 0xF)
                data.append(row[:width])
        elif bpp==8:
            width = w16*2
            off=0
            for y in range(h):
                row=[]
                for _ in range(w16):
                    word = struct.unpack_from('<H', img, off)[0]
                    off+=2
                    row.extend([word & 0xFF, word >> 8])
                data.append(row[:width])
        elif bpp==16:
            width=w16
            off=0
            for y in range(h):
                row=[]
                for _ in range(w16):
                    val = struct.unpack_from('<H', img, off)[0]
                    off+=2
                    r=(val & 0x1F)<<3
                    g=((val>>5)&0x1F)<<3
                    b=((val>>10)&0x1F)<<3
                    row.append((r,g,b))
                data.append(row)
        elif bpp==24:
            width=(w16*2)//3
            off=0
            for y in range(h):
                row=[]
                for _ in range(width):
                    b,g,r=img[off:off+3]
                    off+=3
                    row.append((r,g,b))
                off=(y+1)*w16*2
                data.append(row)
        return {
            "bpp": bpp,
            "clut": clut,
            "clut_w": clut_w,
            "clut_h": clut_h,
            "data": data,
            "width": width,
            "height": h,
            "flags": flags,
            "w16": w16,
            "path": filepath
        }

# ---------------- Tool D Tab ----------------
class ToolDTab(QWidget):
    def __init__(self):
        super().__init__()
        self.image_info = None
        self.zoom_factor = 1.0
        self.current_folder = ""
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QHBoxLayout(self)

        # -------- Left: File Tree --------
        self.left = QVBoxLayout()
        layout.addLayout(self.left, 1)

        self.left.addWidget(QLabel("Files"))
        btn_folder = QPushButton("Open Folder")
        btn_folder.clicked.connect(self.open_folder)
        self.left.addWidget(btn_folder)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._on_tree_double)
        self.left.addWidget(self.tree, 1)

        # -------- Center: Canvas --------
        self.center = QVBoxLayout()
        layout.addLayout(self.center, 4)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints() | QPainter.RenderHint.Antialiasing)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.wheelEvent = self._wheel_event
        self.center.addWidget(self.view)

        # Info panel
        self.info_label = QLabel("No image loaded")
        self.info_label.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.info_label.setMinimumWidth(200)
        self.center.addWidget(self.info_label)

        # -------- Right: Palette --------
        self.right = QVBoxLayout()
        layout.addLayout(self.right, 1)

        self.right.addWidget(QLabel("Palette"))
        self.palette_tree = QTreeWidget()
        self.palette_tree.setColumnCount(2)
        self.palette_tree.setHeaderLabels(["Index","Color"])
        self.palette_tree.itemDoubleClicked.connect(self._on_palette_double)
        self.right.addWidget(self.palette_tree,1)

    # ---------- File Tree ----------
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        self.current_folder = folder
        self.tree.clear()
        root = QTreeWidgetItem([folder])
        root.setData(0, Qt.ItemDataRole.UserRole, folder)
        self.tree.addTopLevelItem(root)
        self._populate(root, folder)
        root.setExpanded(True)

    def _populate(self, parent, path):
        try:
            for name in sorted(os.listdir(path)):
                full = os.path.join(path,name)
                child = QTreeWidgetItem([name])
                child.setData(0, Qt.ItemDataRole.UserRole, full)
                parent.addChild(child)
                if os.path.isdir(full):
                    dummy = QTreeWidgetItem([""])
                    child.addChild(dummy)
        except PermissionError:
            pass

    def _on_tree_double(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isdir(path):
            item.takeChildren()
            self._populate(item, path)
        elif path.lower().endswith(".tim"):
            self.load_tim_file(path)

    # ---------- Canvas ----------
    def _wheel_event(self,event):
        factor=1.1 if event.angleDelta().y()>0 else 0.9
        self.zoom_factor*=factor
        self.render_image()

    def load_tim_file(self,path):
        try:
            self.image_info = load_tim(path)
        except Exception as e:
            QMessageBox.critical(self,"TIM Error",str(e))
            return
        self.zoom_factor = 1.0
        self.render_image()
        self.populate_palette()
        self.show_info()

    def render_image(self):
        if not self.image_info:
            return
        w,h=self.image_info["width"],self.image_info["height"]
        img=Image.new("RGBA",(w,h))
        if self.image_info["clut"]:
            pal=self.image_info["clut"]
            for y,row in enumerate(self.image_info["data"]):
                for x,idx in enumerate(row):
                    img.putpixel((x,y),(*pal[idx],255))
        else:
            for y,row in enumerate(self.image_info["data"]):
                for x,pix in enumerate(row):
                    img.putpixel((x,y),(*pix,255))
        zoomed_size=(max(1,int(w*self.zoom_factor)), max(1,int(h*self.zoom_factor)))
        img=img.resize(zoomed_size,Image.NEAREST)
        qim=QImage(img.tobytes(),img.width,img.height,QImage.Format.Format_RGBA8888)
        pix=QPixmap.fromImage(qim)
        self.scene.clear()
        self.scene.addPixmap(pix)
        self.view.fitInView(self.scene.itemsBoundingRect(),Qt.AspectRatioMode.KeepAspectRatio)

    # ---------- Palette ----------
    def populate_palette(self):
        self.palette_tree.clear()
        if not self.image_info or not self.image_info["clut"]:
            return
        for i,(r,g,b) in enumerate(self.image_info["clut"]):
            item = QTreeWidgetItem([str(i), f"#{r:02X}{g:02X}{b:02X}"])
            color = QColor(r,g,b)
            item.setBackground(1,color)
            self.palette_tree.addTopLevelItem(item)

    def _on_palette_double(self,item,col):
        idx=int(item.text(0))
        old_color=self.image_info["clut"][idx]
        qcolor=QColor(*old_color)
        new_color=QColorDialog.getColor(qcolor,self)
        if new_color.isValid():
            self.image_info["clut"][idx]=(new_color.red(),new_color.green(),new_color.blue())
            self.populate_palette()
            self.render_image()
            self.show_info()

    # ---------- Info Panel ----------
    def show_info(self):
        if not self.image_info:
            self.info_label.setText("No image loaded")
            return
        path=self.image_info["path"]
        size=os.path.getsize(path)
        w,h=self.image_info["width"],self.image_info["height"]
        bpp=self.image_info["bpp"]
        clut_len=len(self.image_info["clut"]) if self.image_info["clut"] else 0
        flags=self.image_info.get("flags",0)
        w16=self.image_info.get("w16",0)
        uses_clut="Yes" if self.image_info.get("clut") else "No"
        total_pixels=w*h
        info_text=(
            f"<b>File:</b> {os.path.basename(path)}<br>"
            f"<b>Path:</b> {path}<br>"
            f"<b>Size:</b> {size} bytes<br>"
            f"<b>Dimensions:</b> {w} x {h} pixels<br>"
            f"<b>Total Pixels:</b> {total_pixels}<br>"
            f"<b>BPP:</b> {bpp}<br>"
            f"<b>Uses CLUT:</b> {uses_clut}<br>"
            f"<b>Palette Entries:</b> {clut_len}<br>"
            f"<b>Flags:</b> 0x{flags:08X}<br>"
            f"<b>w16:</b> {w16}"
        )
        self.info_label.setText(info_text)

    # ---------- Save/Load State ----------
    def get_state(self):
        return {
            "last_folder": self.current_folder,
            "last_tim": self.image_info["path"] if self.image_info else None,
            "palette": self.image_info["clut"] if self.image_info else None,
            "zoom": self.zoom_factor
        }

    def load_state(self,state):
        folder=state.get("last_folder")
        if folder and os.path.isdir(folder):
            self.open_folder_from_path(folder)
        tim=state.get("last_tim")
        if tim and os.path.isfile(tim):
            self.load_tim_file(tim)
        palette=state.get("palette")
        if palette and self.image_info:
            self.image_info["clut"]=palette
            self.populate_palette()
            self.render_image()
        self.zoom_factor=state.get("zoom",1.0)
        self.render_image()


    def open_folder_from_path(self,folder):
        self.current_folder=folder
        self.tree.clear()
        root=QTreeWidgetItem([folder])
        root.setData(0,Qt.ItemDataRole.UserRole,folder)
        self.tree.addTopLevelItem(root)
        self._populate(root,folder)
        root.setExpanded(True)
