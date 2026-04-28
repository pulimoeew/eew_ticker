# 顾名思义，启动这个就对了
import sys
from PyQt6.QtWidgets import QApplication
from ui import TickerWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TickerWindow()
    win.show()
    sys.exit(app.exec())