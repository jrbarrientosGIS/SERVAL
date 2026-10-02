from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap, QCursor, QColor
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import Qgis, QgsGeometry
from qgis.gui import QgsMapTool, QgsRubberBand

from .utils import icon_path, get_logger


class RasterCellSelectionMapTool(QgsMapTool):
    """
    Raster cells selection tool
    """

    NEW_SELECTION = "New selection"
    ADD_TO_SELECTION = "Add to selection"
    REMOVE_FROM_SELECTION = "Remove from selection"
    LINE_SELECTION = "line"
    POLYGON_SELECTION = "polygon"

    def __init__(self, iface, uc, raster, debug=False):
        super(RasterCellSelectionMapTool, self).__init__(iface.mapCanvas())
        self.iface = iface
        self.uc = uc
        self.raster = raster
        self.mode = None
        self.geom_type = Qgis.GeometryType.Polygon
        self.setCursor(QCursor(QPixmap(icon_path('select_tool.svg')), 0, 0))
        self.current_rubber_band = QgsRubberBand(self.iface.mapCanvas(), Qgis.GeometryType.Polygon)
        self.selected_rubber_band = QgsRubberBand(self.iface.mapCanvas(), Qgis.GeometryType.Polygon)
        self.current_points = None
        self.selected_geometries = None
        self.selected_axes = None  # ejes (polilíneas) de selecciones por línea
        self.last_pos = None
        self.sel_line_width = 1
        self.cur_sel_color = QColor(Qt.GlobalColor.yellow)
        self.cur_sel_fill_color = QColor(Qt.GlobalColor.yellow)
        self.sel_color = QColor(Qt.GlobalColor.yellow)
        self.sel_fill_color = QColor(Qt.GlobalColor.yellow)
        self.prev_tool = None
        self.selection_mode = None
        self.logger = get_logger() if debug else None

    def init_tool(self, raster, mode=POLYGON_SELECTION, line_width=1):
        if not raster:
            self.uc.bar_warn("No raster selected")
            return False
        self.raster = raster
        self.mode = mode
        self.sel_line_width = line_width
        self.geom_type = Qgis.GeometryType.Line if mode == self.LINE_SELECTION else Qgis.GeometryType.Polygon
        self.cur_sel_color = QColor(Qt.GlobalColor.yellow)
        self.cur_sel_fill_color = QColor(Qt.GlobalColor.yellow)
        self.cur_sel_fill_color.setAlpha(20)
        self.sel_color = QColor(Qt.GlobalColor.yellow)
        self.sel_fill_color = QColor(Qt.GlobalColor.yellow)
        self.sel_fill_color.setAlpha(20)
        return True

    def set_prev_tool(self, prev_tool):
        self.prev_tool = prev_tool

    def activate(self):
        self.setCursor(QCursor(QPixmap(icon_path('select_tool.svg')), 0, 0))
        if self.logger:
            self.logger.debug(f"Selection tool activated")

    def deactivate(self):
        QgsMapTool.deactivate(self)
        if self.logger:
            self.logger.debug(f"Selection tool deactivated")

    def reset(self):
        if self.logger:
            self.logger.debug(f"Resetting the tool completely")
        self.current_rubber_reset()
        self.selected_rubber_reset()
        self.raster = None
        self.current_points = None
        self.selected_geometries = None
        self.selected_axes = None

    def selecting_finished(self):
        if self.logger:
            self.logger.debug(f"Selecting finished")
        self.current_selection_reset()

    def current_rubber_reset(self, col=None, fill_col=None, width=1, geom_type=Qgis.GeometryType.Polygon):
        if self.current_rubber_band is None:
            return
        self.current_rubber_band.reset(geom_type)
        self.current_rubber_band.setColor(col if col else self.cur_sel_color)
        self.current_rubber_band.setWidth(width)
        self.current_rubber_band.setFillColor(fill_col if fill_col else self.cur_sel_fill_color)

    def current_selection_reset(self):
        self.current_points = []
        self.current_rubber_reset()

    def selected_rubber_reset(self, col=None, fill_col=None, width=1, geom_type=Qgis.GeometryType.Polygon):
        if self.selected_rubber_band is None:
            return
        self.selected_rubber_band.reset(geom_type)
        self.selected_rubber_band.setColor(col if col else self.sel_color)
        self.selected_rubber_band.setWidth(width)
        self.selected_rubber_band.setFillColor(fill_col if fill_col else self.sel_fill_color)

    def clear_all_selections(self):
        self.current_selection_reset()
        self.selected_rubber_reset()
        self.selected_geometries = None
        self.selected_axes = None

    def create_selecting_geometry(self, cur_position=None):
        pt = [cur_position] if cur_position else []
        if self.geom_type == Qgis.GeometryType.Line:
            geom = QgsGeometry.fromPolylineXY(self.current_points + pt).buffer(self.sel_line_width / 2., 5)
        else:
            if len(self.current_points) < 2:
                geom = QgsGeometry.fromPolylineXY(self.current_points + pt)
            else:
                poly_pts = [self.current_points + pt]
                geom = QgsGeometry.fromPolygonXY(poly_pts)
        return geom

    def current_rubber_update(self, cur_position=None):
        self.current_rubber_reset()
        if not self.current_points:
            return
        geom = self.create_selecting_geometry(cur_position=cur_position)
        self.current_rubber_band.addGeometry(geom, None)
        if geom.isGeosValid():
            self.uc.clear_bar_messages()
        else:
            self.uc.bar_warn("Selected geometry is invalid")

    def selected_rubber_update(self):
        self.selected_rubber_reset()
        if self.selected_geometries is None:
            return
        for geom in self.selected_geometries:
            self.selected_rubber_band.addGeometry(geom, None)

    def canvasMoveEvent(self, e):
        if self.current_points is None:
            return
        self.current_rubber_update(self.toMapCoordinates(e.pos()))
        self.last_pos = self.toMapCoordinates(e.pos())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.uc.bar_info("Tool aborted")
            self.selecting_finished()
        elif e.key() == Qt.Key.Key_Backspace:
            if self.current_points:
                self.current_points.pop()
            self.current_rubber_update(cur_position=self.last_pos if self.last_pos else None)

    def canvasReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                self.selection_mode = self.REMOVE_FROM_SELECTION
            elif modifiers == Qt.KeyboardModifier.ControlModifier:
                self.selection_mode = self.ADD_TO_SELECTION
            else:
                self.selection_mode = self.NEW_SELECTION
            if self.logger:
                self.logger.debug(f"Right mouse button in mode: {self.selection_mode}")
            self.update_selection()
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return

        cur_pos = self.toMapCoordinates(e.pos())
        if self.current_points is None:
            self.current_points = [cur_pos]
        else:
            self.current_points.append(cur_pos)
        self.current_rubber_update(cur_position=cur_pos)

    def update_selection(self):
        if self.logger:
            self.logger.debug(f"Selection tool points: {[str(pt) for pt in self.current_points]}")
        if self.current_points is None:
            return

        new_geom = self.create_selecting_geometry()
        if new_geom.isEmpty():
            if self.logger:
                self.logger.debug(f"Selection geometry was empty.")
            return
        axis = None
        if self.geom_type == Qgis.GeometryType.Line and len(self.current_points) >= 2:
            axis = QgsGeometry.fromPolylineXY(self.current_points)
        if self.selection_mode == self.NEW_SELECTION:
            self.selected_geometries = [new_geom]
            self.selected_axes = [axis] if axis else None
        elif self.selection_mode == self.ADD_TO_SELECTION:
            self.selected_geometries = (self.selected_geometries or []) + [new_geom]
            if axis:
                self.selected_axes = (self.selected_axes or []) + [axis]
        else:
            # distract from existing geometries
            new_geoms = []
            for exist_geom in (self.selected_geometries or []):
                geom = exist_geom.difference(new_geom)
                if not geom.isGeosValid() or not geom.type() == Qgis.GeometryType.Polygon:
                    if self.logger:
                        self.logger.debug(f"Invalid geometry for selection: {geom.asWkt()}")
                    continue
                new_geoms.append(geom)
            self.selected_geometries = new_geoms
        self.selected_rubber_update()
        self.current_selection_reset()
        self.uc.bar_info("Selection created")

    def selection_from_layer(self, layer):
        if self.logger:
            self.logger.debug(f"Selection from layer: {layer.name()}")
        sel_geoms = []
        axes = []
        features = layer.getSelectedFeatures() if layer.selectedFeatureCount() else layer.getFeatures()
        for feat in features:
            if layer.geometryType() == Qgis.GeometryType.Line:
                axes.append(QgsGeometry(feat.geometry()))
            if layer.geometryType() == Qgis.GeometryType.Line or layer.geometryType() == Qgis.GeometryType.Point:
                geom = feat.geometry().buffer(self.sel_line_width / 2., 5)
            else:
                geom = feat.geometry()
            if geom.isGeosValid():
                sel_geoms.append(geom)
        self.selected_geometries = sel_geoms
        self.selected_axes = axes if axes else None
        self.selected_rubber_update()
        self.current_selection_reset()
        self.uc.bar_info("Selection loaded")

    def get_axis(self):
        """Devuelve el eje (polilínea simple) de la selección actual o None si no hay eje (selección por polígono)."""
        if not self.selected_axes:
            return None
        merged = QgsGeometry.collectGeometry(self.selected_axes).mergeLines()
        if merged.isEmpty():
            return None
        if merged.isMultipart():
            parts = merged.asGeometryCollection()
            self.uc.bar_warn("Hay varios ejes no conectados: se usa el más largo.", dur=5)
            return max(parts, key=lambda g: g.length())
        return merged
