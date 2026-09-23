"""
worker.py
---------
PyQt5 QThread: kamera okuma ve canlı görüntü akışı.
"""

import time
import numpy as np
import cv2

from PyQt5.QtCore import QThread, pyqtSignal


class InspectionWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    state_changed = pyqtSignal(str)
    fps_updated = pyqtSignal(float)
    log_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: dict, cam_index: int = 0):
        """cam_index: 0 = birinci kamera (config 'camera'/'resolution'),
        1 = ikinci kamera (config 'camera2'/'resolution2'). Kamera 2'de
        tanimlanmayan anahtarlar kamera 1'den devralinir (bkz. _cam_cfg)."""
        super().__init__()
        self._cfg = config
        self._cam_index = int(cam_index)
        self._cam_no = self._cam_index + 1                      # log/etiket icin 1-tabanli
        self._cam_key = "camera" if cam_index == 0 else f"camera{self._cam_no}"
        self._res_key = "resolution" if cam_index == 0 else f"resolution{self._cam_no}"
        self._running = False
        self._cap = None
        self._read_fn = None
        self._meta_fn = None                 # picamera2: gercek poz/gain okumak icin
        self.last_raw_frame = None
        self.last_frame_time = 0.0
        # Kameranin FIILEN kullandigi poz suresi/gain (oto-pozlamada degisir).
        # HAREKET BULANIKLIGI dogrudan poz suresiyle orantilidir -> GUI'de gosterilir.
        self.last_exposure_us = 0
        self.last_gain = 0.0
        self._meta_last = 0.0
        # Picamera2 acilamayip OpenCV yedegine dusuldu mu? Pi'de /dev/video0 rp1-cfe
        # dugumudur, KARE VERMEZ; yedekte takili kalmamak icin run() belirli araliklarla
        # Picamera2'yi yeniden dener (2026-09-23 arizasi: diger kamera ayni anda kapanirken
        # libcamera "Camera __init__ sequence did not complete" verdi, kamera hic gelmedi).
        self._on_fallback = False
        self._last_picam_retry = 0.0
        self._zoom = float(self._cam_cfg().get("zoom", 1.0))

    PICAM_RETRY_S = 10.0       # OpenCV yedeginde kare gelmezse Picamera2'yi bu aralikla dene

    def _fallback_retry_due(self, failed_reads: int) -> bool:
        """Picamera2 tercih edilmisken OpenCV yedegine dusuldu ve kare gelmiyorsa,
        son denemeden >= PICAM_RETRY_S gectiyse Picamera2 yeniden denensin."""
        return (self._on_fallback and failed_reads >= 100
                and (time.time() - self._last_picam_retry) >= self.PICAM_RETRY_S)

    def _cam_cfg(self) -> dict:
        """Bu kameranin ayar sozlugu. Kamera 2 icin yazilmamis anahtarlar kamera 1'den
        gelir (yeni kamerada her ayari bastan girmek gerekmesin)."""
        base = self._cfg.get("camera", {}) or {}
        if self._cam_key == "camera":
            return base
        return {**base, **(self._cfg.get(self._cam_key, {}) or {})}

    def _res_cfg(self) -> dict:
        base = self._cfg.get("resolution", {}) or {}
        if self._res_key == "resolution":
            return base
        return {**base, **(self._cfg.get(self._res_key, {}) or {})}

    def _open_camera(self):
        cam_cfg = self._cam_cfg()
        res_cfg = self._res_cfg()
        backend = cam_cfg.get("backend", "picamera2")
        w = int(res_cfg.get("width", 640))
        h = int(res_cfg.get("height", 480))
        fps = cam_cfg.get("fps", 60)

        if backend == "picamera2":
            cam = None
            try:
                from picamera2 import Picamera2
                # Pi'de cam0/cam1 CSI girisleri: her worker kendi kamerasini acar.
                cam = Picamera2(self._cam_index)
                camera_controls = {"FrameRate": fps}
                camera_controls.update(self._camera_controls())
                # DIKKAT: ayri ad! Eskiden 'cam_cfg' (config sozlugu) burada picamera2
                # yapilandirmasiyla GOLGELENIYORDU -> asagidaki awb_mode/color_gains
                # okumalari hep varsayilani goruyor, config anahtarlari HIC uygulanmiyordu.
                pc_cfg = cam.create_video_configuration(
                    main={"size": (w, h), "format": "BGR888"},
                    controls=camera_controls,
                )
                cam.configure(pc_cfg)

                awb_mode = cam_cfg.get("awb_mode", "Auto")
                if awb_mode != "Auto":
                    try:
                        from picamera2 import controls
                        if hasattr(controls.AwbModeEnum, awb_mode):
                            enum_val = getattr(controls.AwbModeEnum, awb_mode)
                            cam.set_controls({"AwbMode": enum_val})
                            self.log_message.emit(f"[Kamera {self._cam_no}] AWB modu ayarlandı: {awb_mode}")
                    except Exception as awb_err:
                        self.log_message.emit(f"[UYARI] AWB ayarı uygulanamadı: {awb_err}")

                gains = cam_cfg.get("color_gains")
                if gains is not None and len(gains) == 2:
                    try:
                        cam.set_controls({"AwbEnable": False, "ColourGains": (float(gains[0]), float(gains[1]))})
                        self.log_message.emit(f"[Kamera {self._cam_no}] Sabit kazançlar uygulandı: R={gains[0]}, B={gains[1]}")
                    except Exception as gain_err:
                        self.log_message.emit(f"[UYARI] Sabit AWB kazançları uygulanamadı: {gain_err}")

                cam.start()
                time.sleep(1.5)
                self._cap = cam

                def safe_read():
                    try:
                        frame = cam.capture_array()
                        if frame is None or frame.size == 0:
                            return False, None
                        if len(frame.shape) == 3:
                            if frame.shape[2] == 4:
                                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                            elif frame.shape[2] == 3:
                                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        return True, frame
                    except Exception:
                        return False, None

                self._read_fn = safe_read
                self._meta_fn = cam.capture_metadata
                self._on_fallback = False
                self.log_message.emit(
                    f"[Kamera {self._cam_no}] Picamera2 açıldı (cam{self._cam_index}) - {w}x{h} @ {fps}fps")
                return True
            except Exception as e:
                # YARIM KALAN NESNEYI KAPAT (2026-09-23 saha): cam olusturulup configure/
                # start'ta patlarsa kamera bu surecte ACQUIRED kalir -> sonraki her
                # Picamera2(idx) denemesi "Camera __init__ sequence did not complete" verir;
                # 10 s'lik yeniden denemeler bu yuzden hic tutmadi. close() serbest birakir.
                if cam is not None:
                    try:
                        cam.close()
                    except Exception:
                        pass
                self._last_picam_retry = time.time()
                self.log_message.emit(
                    f"[UYARI] Kamera {self._cam_no}: Picamera2 başlatılamadı: {e} -> OpenCV'ye geçiliyor "
                    f"(kare gelmezse {int(self.PICAM_RETRY_S)} s sonra Picamera2 yeniden denenir)")

        self._meta_fn = None          # OpenCV yedeginde poz/gain okunamaz
        self._on_fallback = (backend == "picamera2")   # tercih picamera2 idi, yedekteyiz
        idx = int(cam_cfg.get("opencv_index", self._cam_index))
        cap = cv2.VideoCapture(idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, fps)
        if not cap.isOpened():
            self.error_occurred.emit(f"Kamera {self._cam_no} (index {idx}) açılamadı!")
            return False
        self._cap = cap
        self._read_fn = cap.read
        self._apply_opencv_camera_controls(cap)
        self.log_message.emit(f"[Kamera {self._cam_no}] OpenCV açıldı - index {idx}")
        return True

    def _release_camera(self):
        if self._cap is None:
            return
        # Nesnenin TIPINE gore kapat (config'teki backend'e gore DEGIL): picamera2
        # tercihliyken OpenCV yedegine dusulmusse eski kod VideoCapture'a stop() cagirip
        # sessizce hata yutuyor, /dev/video* acik kaliyordu.
        try:
            if hasattr(self._cap, "release"):          # OpenCV VideoCapture (yedek)
                self._cap.release()
            else:                                      # Picamera2
                self._cap.stop()
                self._cap.close()
        except Exception:
            pass
        self._cap = None

    def change_resolution(self, w: int, h: int):
        res = self._cfg.setdefault(self._res_key, {})
        res["width"] = w
        res["height"] = h
        self._restart_camera_requested = True

    def change_fps(self, fps: int):
        self._cfg.setdefault(self._cam_key, {})["fps"] = int(fps)
        self._restart_camera_requested = True

    def change_camera_controls(self):
        self._restart_camera_requested = True

    def set_zoom(self, zoom: float):
        self._zoom = max(1.0, float(zoom))
        self._cfg.setdefault(self._cam_key, {})["zoom"] = self._zoom

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        if not self._open_camera():
            return

        res = self._res_cfg()
        w = int(res.get("width", 640))
        h = int(res.get("height", 480))
        fps_timer = time.time()
        frame_count = 0
        prev_state_name = ""
        failed_reads = 0
        read_error_reported = False

        while self._running:
            if getattr(self, "_restart_camera_requested", False):
                self._restart_camera_requested = False
                self._release_camera()
                if not self._open_camera():
                    break
                res = self._res_cfg()
                w = int(res.get("width", 640))
                h = int(res.get("height", 480))
                continue

            ok, frame = self._read_fn()
            if not ok or frame is None:
                failed_reads += 1
                if failed_reads >= 100 and not read_error_reported:
                    self.error_occurred.emit("Kamera görüntüsü okunamıyor.")
                    read_error_reported = True
                if self._fallback_retry_due(failed_reads):
                    self.log_message.emit(
                        f"[Kamera {self._cam_no}] OpenCV yedeğinden kare gelmiyor; "
                        "Picamera2 yeniden deneniyor...")
                    self._restart_camera_requested = True
                    failed_reads = 0
                    continue
                time.sleep(0.02)
                continue

            failed_reads = 0
            read_error_reported = False
            self._read_exposure_metadata()
            frame = cv2.resize(frame, (w, h))
            frame = self._apply_digital_zoom(frame)
            self.last_raw_frame = frame.copy()
            self.last_frame_time = time.time()
            frame_count += 1

            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                fps_val = frame_count / elapsed
                frame_count = 0
                fps_timer = time.time()
                self.fps_updated.emit(fps_val)

            state_name = "CANLI"
            if state_name != prev_state_name:
                self.state_changed.emit(state_name)
                prev_state_name = state_name

            self.frame_ready.emit(frame)

        self._release_camera()

    def _read_exposure_metadata(self):
        """Kameranin FIILEN kullandigi poz suresi/gain'i okur (saniyede 1 kez).

        Neden onemli: HAREKET BULANIKLIGI poz suresiyle dogru orantilidir. Global
        shutter yalnizca 'egilme' bozulmasini onler, uzun pozdaki bulanikligi ONLEMEZ.
        Oto-pozlama parlaklik icin poz suresini uzatir (olculdu: 16.6 ms'ye kadar) ->
        bant hareket ederken parca bulanik cikar. GUI bu degeri gosterir."""
        if self._meta_fn is None:
            return
        now = time.time()
        if now - self._meta_last < 1.0:
            return
        self._meta_last = now
        try:
            md = self._meta_fn() or {}
            self.last_exposure_us = int(md.get("ExposureTime", 0) or 0)
            self.last_gain = float(md.get("AnalogueGain", 0.0) or 0.0)
        except Exception:
            pass

    def _apply_digital_zoom(self, frame: np.ndarray) -> np.ndarray:
        zoom = max(1.0, self._zoom)
        if zoom <= 1.01:
            return frame
        h, w = frame.shape[:2]
        crop_w = max(1, int(w / zoom))
        crop_h = max(1, int(h / zoom))
        x1 = (w - crop_w) // 2
        y1 = (h - crop_h) // 2
        cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    def _camera_controls(self) -> dict:
        camera_cfg = self._cam_cfg()
        if not camera_cfg.get("manual_exposure_enabled", False):
            return {}

        controls = {"AeEnable": False}
        exposure_us = int(camera_cfg.get("exposure_us", 8000))
        analogue_gain = float(camera_cfg.get("analogue_gain", 1.0))
        if exposure_us > 0:
            controls["ExposureTime"] = exposure_us
        if analogue_gain > 0:
            controls["AnalogueGain"] = analogue_gain
        return controls

    def _apply_opencv_camera_controls(self, cap):
        camera_cfg = self._cam_cfg()
        if not camera_cfg.get("manual_exposure_enabled", False):
            return
        try:
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_EXPOSURE, float(camera_cfg.get("exposure_us", 8000)))
            cap.set(cv2.CAP_PROP_GAIN, float(camera_cfg.get("analogue_gain", 1.0)))
            self.log_message.emit("[Kamera] OpenCV manuel exposure/gain uygulandı")
        except Exception as err:
            self.log_message.emit(f"[UYARI] OpenCV exposure/gain uygulanamadı: {err}")
