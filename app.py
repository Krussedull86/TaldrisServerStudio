import sys
from PySide6.QtWidgets import QApplication
from desktop import STYLE
from update_ui import ReleaseStudio
if __name__=='__main__':
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window=ReleaseStudio(); window.show(); sys.exit(app.exec())
