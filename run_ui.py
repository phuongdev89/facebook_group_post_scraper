import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import src.utils.compat

from PyQt6.QtWidgets import QApplication
from src.database.schema import init_db
from src.ui.app import FacebookScraperApp

def main():
    # Initialize database
    init_db()
    
    app = QApplication(sys.argv)
    window = FacebookScraperApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
