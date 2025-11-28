import sys
import os
from PyQt5.QtWidgets import QApplication

# Proje ana dizinini sistem yoluna ekle (Böylece 'src' ve 'gui' her yerden görünür)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from gui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Windows'ta ikonların düzgün görünmesi için
    try:
        import ctypes
        myappid = 'mycompany.myproduct.subproduct.version' # keyfi bir ID
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except:
        pass

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())