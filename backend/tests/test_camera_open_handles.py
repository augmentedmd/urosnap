import numpy as np

from app.services.video import devices


class FakeCap:
    open_handles = 0

    def __init__(self, *args):
        FakeCap.open_handles += 1
        self.reads = 0
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        # Exclusive device: any concurrent handle makes it deliver nothing.
        self.reads += 1
        if FakeCap.open_handles > 1 or self.reads < 4:
            return False, None
        return True, np.zeros((48, 64, 3), dtype=np.uint8)

    def set(self, *args):
        return True

    def get(self, *args):
        return 0

    def release(self):
        if not self.released:
            self.released = True
            FakeCap.open_handles -= 1


def test_quick_open_uses_one_handle_and_warms_up(monkeypatch):
    FakeCap.open_handles = 0
    monkeypatch.setattr(devices.cv2, "VideoCapture", FakeCap)
    monkeypatch.setattr(devices, "_default_backends", lambda: [(700, "DirectShow")])
    monkeypatch.setattr(devices.time, "sleep", lambda _s: None)

    cap = devices.open_capture_quick("camera:0", "640x480")

    assert FakeCap.open_handles == 1
    cap.release()
    assert FakeCap.open_handles == 0
