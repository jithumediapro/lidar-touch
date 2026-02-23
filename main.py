import sys
import argparse

from PyQt5.QtWidgets import QApplication

from config.settings import AppSettings
from processing.pipeline import ProcessingPipeline
from tuio.sender import TuioSender
from gui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description="LiDAR Touch - OptiTUIO-style Application")
    parser.add_argument("--mock", action="store_true",
                        help="Use mock LiDAR scanner (no hardware required)")
    parser.add_argument("--settings", type=str, default="settings.json",
                        help="Path to settings JSON file")
    args = parser.parse_args()

    # Load or create settings
    try:
        settings = AppSettings.load(args.settings)
    except (FileNotFoundError, Exception):
        settings = AppSettings()

    app = QApplication(sys.argv)
    app.setApplicationName("LiDAR Touch")

    # Create scanner
    if args.mock:
        from lidar.mock_scanner import MockLidarScanner
        scanner = MockLidarScanner(num_touches=2)
    else:
        from lidar.scanner import LidarScanner
        scanner = LidarScanner(settings.lidar_ip, settings.lidar_port)

    # Create processing pipeline
    pipeline = ProcessingPipeline(settings)

    # Create TUIO sender
    tuio_sender = TuioSender(settings.tuio_host, settings.tuio_port)
    tuio_sender.enabled = settings.tuio_enabled

    # Create main window
    window = MainWindow(settings, scanner, pipeline, tuio_sender)
    window._settings_path = args.settings

    # Wire scanner -> pipeline -> TUIO
    scanner.scan_ready.connect(pipeline.enqueue_scan)
    pipeline.touches_updated.connect(tuio_sender.send_frame)

    # Start pipeline thread
    pipeline.start()

    # In mock mode, auto-start the scanner
    if args.mock:
        scanner.start()
        window.control_panel.devices.set_connection_status("connected")
        window.control_panel.devices._connect_btn.setEnabled(False)
        window.control_panel.devices._stop_btn.setEnabled(True)

    window.show()
    exit_code = app.exec_()

    # Graceful shutdown
    scanner.stop()
    pipeline.stop()

    # Save settings
    try:
        settings.save(args.settings)
    except Exception:
        pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
