from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QSettings
from typing import List, Set

class WatchlistWidget(QWidget):
    symbols_changed = Signal(list)

    def __init__(self):
        super().__init__()
        self.all_symbols: List[str] = []
        self.favorites: Set[str] = set()
        self._settings = QSettings("FuturesTerminal", "Watchlist")

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter symbols...")
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.list)

        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("All")
        self.select_all_btn.clicked.connect(self.select_all)
        self.fav_btn = QPushButton("★")
        self.fav_btn.clicked.connect(self.add_favorite)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_selection)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.fav_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

        self.search.textChanged.connect(self.filter_list)
        self.list.itemSelectionChanged.connect(self._on_selection_changed)
        self._load_favorites()

    def populate(self, symbols: List[str]):
        self.all_symbols = sorted(symbols)
        self._rebuild_list()

    def _rebuild_list(self):
        self.list.clear()
        for sym in self.all_symbols:
            item = QListWidgetItem(sym)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if sym in self.favorites else Qt.Unchecked)
            self.list.addItem(item)

    def filter_list(self, text):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def select_all(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def clear_selection(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setCheckState(Qt.Unchecked)

    def add_favorite(self):
        for item in self.list.selectedItems():
            sym = item.text()
            if sym in self.favorites:
                self.favorites.remove(sym)
            else:
                self.favorites.add(sym)
        self._save_favorites()
        self._rebuild_list()
        self._on_selection_changed()

    def _on_selection_changed(self):
        selected = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.Checked and not item.isHidden():
                selected.append(item.text())
        self.symbols_changed.emit(selected)

    def _load_favorites(self):
        favs = self._settings.value("favorites", [])
        if favs:
            self.favorites = set(favs)
        else:
            # default favourites
            self.favorites = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def _save_favorites(self):
        self._settings.setValue("favorites", list(self.favorites))