import math
import time
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal


class LidarScanner(QThread):
    """Real UST-10LX scanner via hokuyolx library."""

    scan_ready = pyqtSignal(float, object, object)  # timestamp, angles, distances
    connection_status = pyqtSignal(str)

    NUM_POINTS = 1081
    ANGLE_MIN = math.radians(-135)
    ANGLE_MAX = math.radians(135)

    def __init__(self, ip="192.168.0.10", port=10940, parent=None):
        super().__init__(parent)
        self._ip = ip
        self._port = port
        self._running = False
        self._laser = None
        self._angles = np.linspace(self.ANGLE_MIN, self.ANGLE_MAX, self.NUM_POINTS)

    def run(self):
        from hokuyolx import HokuyoLX

        self._running = True
        try:
            self._laser = HokuyoLX(addr=(self._ip, self._port))
            self.connection_status.emit("connected")
        except Exception as e:
            self.connection_status.emit(f"error: {e}")
            return

        while self._running:
            try:
                timestamp, scan = self._laser.get_dist()
                distances = scan.astype(np.float64)
                self.scan_ready.emit(float(timestamp), self._angles.copy(), distances)
            except Exception as e:
                self.connection_status.emit(f"error: {e}")
                # Try to reconnect after a brief pause
                time.sleep(1.0)
                try:
                    if self._laser:
                        self._laser.close()
                    self._laser = HokuyoLX(addr=(self._ip, self._port))
                    self.connection_status.emit("reconnected")
                except Exception:
                    self.connection_status.emit("disconnected")
                    break

        if self._laser:
            try:
                self._laser.close()
            except Exception:
                pass
            self._laser = None
        self.connection_status.emit("disconnected")

    def stop(self):
        self._running = False
        self.wait(2000)

    def update_connection(self, ip, port):
        self._ip = ip
        self._port = port
