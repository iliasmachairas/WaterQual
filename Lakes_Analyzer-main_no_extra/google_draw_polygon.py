from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import QgsRectangle, QgsGeometry, QgsWkbTypes, QgsPointXY
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

class ExtentDrawingTool(QgsMapTool):
    def __init__(self, canvas, callback):
        super().__init__(canvas)
        self.canvas = canvas
        self.callback = callback
        self.start_point = None
        
        # Create rubber band
        self.rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rb.setWidth(2)
        fill_color = QColor(10, 100, 255, 80)   # Blue with transparency
        self.rb.setFillColor(fill_color)
        self.rb.setBrushStyle(Qt.SolidPattern)
        # Border color (opaque)
        border_color = QColor(0, 100, 255, 200)
        self.rb.setStrokeColor(border_color)
        
    def canvasPressEvent(self, event):
        self.start_point = self.toMapCoordinates(event.pos())
        self.rb.reset(QgsWkbTypes.PolygonGeometry)
        
    def canvasMoveEvent(self, event):
        if not self.start_point:
            return
        end_point = self.toMapCoordinates(event.pos())
        rect = QgsRectangle(self.start_point, end_point)
        
        xmin = rect.xMinimum()
        ymin = rect.yMinimum()
        xmax = rect.xMaximum()
        ymax = rect.yMaximum()
        
        # Create proper QgsPointXY objects for polygon corners
        points = [
            QgsPointXY(xmin, ymin),
            QgsPointXY(xmax, ymin),
            QgsPointXY(xmax, ymax),
            QgsPointXY(xmin, ymax),
            QgsPointXY(xmin, ymin)  # Close the polygon
        ]
        self.rb.setToGeometry(QgsGeometry.fromPolygonXY([points]), None)
        
    def canvasReleaseEvent(self, event):
        end_point = self.toMapCoordinates(event.pos())
        rect = QgsRectangle(self.start_point, end_point)
        # Clear rubber band
        self.rb.reset(QgsWkbTypes.PolygonGeometry)
        # Send extent back to your callback
        self.callback(rect)
        print("rect",rect)
        # Restore previous tool
        self.canvas.unsetMapTool(self)

def my_extent_handler(extent):
    print("User selected extent:")
    print("  Xmin:", extent.xMinimum())
    print("  Ymin:", extent.yMinimum())
    print("  Xmax:", extent.xMaximum())
    print("  Ymax:", extent.yMaximum())

def get_extent_from_user(callback):
    canvas = iface.mapCanvas()
    tool = ExtentDrawingTool(canvas, callback)
    canvas.setMapTool(tool)
    print("Draw a rectangle on the map...")

# Run the tool
get_extent_from_user(my_extent_handler)