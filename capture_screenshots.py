import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QHeaderView
from PySide6.QtCore import QTimer, QCoreApplication, Qt
from app import MainWindow, load_qss, BASE_DIR, ASSETS_DIR

def run_capture():
    app = QApplication(sys.argv)
    load_qss(app, ASSETS_DIR / "styles.qss")

    window = MainWindow()
    window.resize(1600, 960)
    window.show()

    # Process initial events
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)

    screenshots_dir = ASSETS_DIR / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    def settle_and_capture(path: Path):
        # Remove any lingering graphics effect (opacity fading)
        current_widget = window.stack.currentWidget()
        if current_widget:
            current_widget.setGraphicsEffect(None)
        for _ in range(15):
            app.processEvents()
            time.sleep(0.04)
        window.grab().save(str(path))
        print(f"Captured: {path.name}")

    # 1. Capture Home Page (Fresh & Clean)
    window.switch_page(0, animate=False)
    settle_and_capture(screenshots_dir / "screenshot1.png")

    # 2. Open Sample JSON & Capture JSON Hierarchy Page
    sample_file = BASE_DIR / "samples" / "student_complex.json"
    window.open_json_file(str(sample_file))
    window.switch_page(1, animate=False)
    window.json_page.tree.expandAll()
    settle_and_capture(screenshots_dir / "screenshot2.png")

    # 3. Convert Page & Telemetry
    window.switch_page(2, animate=False)
    window.converter.convert_file(window.current_json_path)
    window.convert_page.engine.setProgress(1.0)
    window.convert_page.progress.setValue(100)
    window.convert_page.refresh()
    settle_and_capture(screenshots_dir / "screenshot3.png")

    # 4. Tables Page
    window.switch_page(3, animate=False)
    window.tables_page.refresh()
    if window.tables_page.tables_list.count() > 0:
        window.tables_page.tables_list.setCurrentRow(0)
    window.tables_page.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    settle_and_capture(screenshots_dir / "screenshot4.png")

    # 5. Schema Visualizer Page
    window.switch_page(4, animate=False)
    window.schema_page.refresh()
    if window.schema_page.schema_tables.count() > 0:
        window.schema_page.schema_tables.setCurrentRow(0)
    settle_and_capture(screenshots_dir / "screenshot5.png")

    print("All 5 screenshots updated successfully!")
    window.close()

if __name__ == "__main__":
    run_capture()
