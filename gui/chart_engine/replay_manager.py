"""
Replay mode: step through historical OHLCV data.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider
from PySide6.QtCore import QTimer, Qt

class ReplayManager(QWidget):
    def __init__(self, chart_widget):
        super().__init__()
        self.chart = chart_widget
        self.data = []
        self.current_index = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._step)
        self.is_playing = False
        self.speed = 1

        layout = QHBoxLayout(self)
        self.play_btn = QPushButton("▶")
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn = QPushButton("■")
        self.stop_btn.clicked.connect(self.stop)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self._set_index)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.slider)
        self.hide()

    def start(self):
        self.data = self.chart._data_cache.get(self.chart.timeframe, [])
        self.current_index = 0
        self.slider.setMaximum(len(self.data) - 1)
        self.is_playing = True
        self.timer.start(int(1000 / self.speed))
        self.show()

    def stop(self):
        self.is_playing = False
        self.timer.stop()
        self.hide()
        if self.data:
            self.chart._update_chart(self.data)

    def toggle_play(self):
        if self.is_playing:
            self.timer.stop()
            self.play_btn.setText("▶")
            self.is_playing = False
        else:
            self.timer.start(int(1000 / self.speed))
            self.play_btn.setText("⏸")
            self.is_playing = True

    def _step(self):
        if self.current_index < len(self.data):
            self.chart.update_from_replay(self.data[:self.current_index+1])
            self.slider.setValue(self.current_index)
            self.current_index += 1
        else:
            self.stop()

    def _set_index(self, idx):
        self.current_index = idx
        self.chart.update_from_replay(self.data[:idx+1])