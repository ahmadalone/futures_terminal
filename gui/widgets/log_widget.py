from PySide6.QtWidgets import QTextEdit
import logging

class QTextEditLogger(logging.Handler):
    def __init__(self, widget: QTextEdit):
        super().__init__()
        self.widget = widget
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.append(msg)