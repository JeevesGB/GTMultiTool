from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox

class InitTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Welcome to GT Multi Tool!"))

        button = QPushButton("Home")
        button.clicked.connect(self._initialize)  # Make sure this method exists
        layout.addWidget(button)

    def _initialize(self):
        # This is what happens when the button is clicked
        QMessageBox.information(self, "Initialize", "Project initialized!")
        # You can add any actual initialization logic here
