"""
Herramientas para aplicar un perfil longitudinal (cota inicio -> cota fin) a una selección de celdas.
"""
from qgis.PyQt.QtCore import Qt, pyqtSignal, QSettings
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import Qgis, QgsGeometry
from qgis.gui import QgsDoubleSpinBox, QgsMapTool, QgsRubberBand


class AxisDrawMapTool(QgsMapTool):
    """Map tool para dibujar el eje del cauce (polilínea). Clic izq: vértice, clic dcho: terminar, Esc: cancelar."""

    axis_finished = pyqtSignal(object)  # QgsGeometry (polilínea en CRS del lienzo)
    axis_cancelled = pyqtSignal()

    def __init__(self, canvas, uc):
        super().__init__(canvas)
        self.uc = uc
        self.points = []
        self.rb = QgsRubberBand(canvas, Qgis.GeometryType.Line)
        self.rb.setColor(QColor(220, 0, 0))
        self.rb.setWidth(2)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def activate(self):
        super().activate()
        self.points = []
        self.rb.reset(Qgis.GeometryType.Line)
        self.uc.bar_info("Dibuja el EJE del cauce empezando por el INICIO: clic izquierdo añade vértices, "
                         "clic derecho termina, Esc cancela.", dur=10)

    def deactivate(self):
        self.rb.reset(Qgis.GeometryType.Line)
        super().deactivate()

    def _update_rb(self, extra_pt=None):
        pts = self.points + ([extra_pt] if extra_pt is not None else [])
        if len(pts) >= 2:
            self.rb.setToGeometry(QgsGeometry.fromPolylineXY(pts))
        else:
            self.rb.reset(Qgis.GeometryType.Line)

    def canvasMoveEvent(self, e):
        if self.points:
            self._update_rb(self.toMapCoordinates(e.pos()))

    def canvasReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.points.append(self.toMapCoordinates(e.pos()))
            self._update_rb()
        elif e.button() == Qt.MouseButton.RightButton:
            if len(self.points) < 2:
                self.uc.bar_warn("El eje necesita al menos 2 vértices.")
                return
            geom = QgsGeometry.fromPolylineXY(self.points)
            self.points = []
            self.rb.reset(Qgis.GeometryType.Line)
            self.uc.clear_bar_messages()
            self.axis_finished.emit(geom)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.points = []
            self.rb.reset(Qgis.GeometryType.Line)
            self.uc.bar_info("Dibujo del eje cancelado", dur=3)
            self.axis_cancelled.emit()
        elif e.key() == Qt.Key.Key_Backspace and self.points:
            self.points.pop()
            self._update_rb()


class SlopeDialog(QDialog):
    """Diálogo para definir cota de inicio y fin del perfil longitudinal."""

    SETTINGS_KEY = "serval/profile_only_lower"

    def __init__(self, axis_length, z_start=None, z_end=None, decimals=3, vmin=-1e7, vmax=1e7, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Perfil longitudinal del cauce")
        self.length = axis_length

        self.z0 = QgsDoubleSpinBox()
        self.z1 = QgsDoubleSpinBox()
        for sb, val in ((self.z0, z_start), (self.z1, z_end)):
            sb.setDecimals(decimals)
            sb.setRange(max(vmin, -1e7), min(vmax, 1e7))
            sb.setShowClearButton(False)
            sb.setMinimumWidth(120)
            sb.setValue(float(val) if val is not None else 0.0)
            sb.valueChanged.connect(self.update_slope)

        self.swap_btn = QPushButton("Intercambiar inicio ↔ fin")
        self.swap_btn.clicked.connect(self.swap_values)

        self.slope_lab = QLabel()
        self.only_lower = QCheckBox("Solo rebajar (no subir celdas que ya están por debajo del perfil)")
        self.only_lower.setChecked(QSettings().value(self.SETTINGS_KEY, False, bool))

        form = QFormLayout()
        form.addRow("Cota inicio (primer vértice del eje):", self.z0)
        form.addRow("Cota fin (último vértice del eje):", self.z1)
        form.addRow("", self.swap_btn)
        form.addRow("Longitud del eje:", QLabel(f"{axis_length:.2f} unidades de mapa"))
        form.addRow("Pendiente:", self.slope_lab)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lout = QVBoxLayout()
        lout.addLayout(form)
        lout.addWidget(self.only_lower)
        lout.addWidget(btns)
        self.setLayout(lout)
        self.update_slope()

    def swap_values(self):
        a, b = self.z0.value(), self.z1.value()
        self.z0.setValue(b)
        self.z1.setValue(a)

    def update_slope(self):
        if self.length <= 0:
            self.slope_lab.setText("-")
            return
        drop = self.z0.value() - self.z1.value()
        pct = drop / self.length * 100.
        sense = "descendente" if drop > 0 else ("ascendente" if drop < 0 else "horizontal")
        self.slope_lab.setText(f"{abs(pct):.3f} % ({sense}), desnivel {drop:.3f}")

    def accept(self):
        QSettings().setValue(self.SETTINGS_KEY, self.only_lower.isChecked())
        super().accept()

    def values(self):
        return self.z0.value(), self.z1.value(), self.only_lower.isChecked()
