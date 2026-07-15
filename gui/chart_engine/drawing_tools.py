"""
Drawing tools for trend lines, horizontal lines, rectangles.
"""
import pyqtgraph as pg

class DrawingToolManager:
    def __init__(self):
        self.drawings = []
        self.plot = None

    def attach_to_plot(self, plot: pg.PlotItem):
        self.plot = plot

    def add_trend_line(self):
        roi = pg.LineSegmentROI([[0,0],[1,1]], pen='y')
        self.plot.addItem(roi)
        self.drawings.append(roi)
        return roi

    def add_horizontal_line(self, y: float):
        line = pg.InfiniteLine(angle=0, movable=True, pen='w')
        line.setPos(y)
        self.plot.addItem(line)
        self.drawings.append(line)

    def add_rectangle(self):
        roi = pg.RectROI([0,0], [1,1], pen='r')
        self.plot.addItem(roi)
        self.drawings.append(roi)

    def clear_all(self):
        for item in self.drawings:
            self.plot.removeItem(item)
        self.drawings.clear()