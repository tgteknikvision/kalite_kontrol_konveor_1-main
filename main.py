"""
Konveyör Bant Denetim Sistemi — Ana GUI Çalışma Dosyası
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys
import time
import yaml
import cv2
import numpy as np

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QSlider,
                             QTextEdit, QGroupBox, QFormLayout, QMessageBox, QComboBox, QDialog,
                             QLineEdit, QSpinBox, QCheckBox, QDoubleSpinBox,
                             QScrollArea, QSizePolicy, QGridLayout, QFrame)
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QColor

from inspector.worker import InspectionWorker
from inspector.plc import InspectionState, create_plc_adapter

CONFIG_PATH = "config.yaml"


class NoWheelMixin:
    """Fare ORTA TEKERLEĞİ ayar değiştirmesin (kullanıcı isteği, 2026-08-03).

    NEDEN: kaydırılabilir Ayarlar penceresinde sayfayı kaydırmak isterken imleç
    bir slider/spinbox üstündeyse Qt varsayılanı DEĞERİ değiştirir — operatör
    farkında olmadan poz/eşik bozabilir (sahada gerçek risk).
    `event.ignore()` olayı ÜST widget'a bırakır: sayfa yine kayar, yalnız değer
    değişmez. (Olayı yutmak yerine yok saymak önemli — yutulursa sayfa da kaymaz.)
    Değer değiştirmek için tıkla-sürükle ya da klavye kullanılır."""

    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(NoWheelMixin, QSlider):
    pass


class NoWheelSpinBox(NoWheelMixin, QSpinBox):
    pass


class NoWheelDoubleSpinBox(NoWheelMixin, QDoubleSpinBox):
    """Ondalık ayıracı olarak hem VİRGÜL hem NOKTA kabul eder.

    NEDEN (2026-08-03, saha hatası — kullanıcı "derinlik değerlerini
    değiştiremiyorum"): sistem yereli `tr_TR`, ayıraç ','. Kullanıcı '0.5' yazınca
    Qt noktayı REDDETMİYOR, SESSİZCE ATIYOR → değer 5.0 oluyor; '1.5' → 15.0.
    Yani yanlış giriş fark edilmeden eşiği 10 KATINA çıkarıyor (derinlik eşiği 1.5
    yerine 15 olursa her sağlam parça NOK olur). Artık nokta, yerelin ayıracına
    çevrilerek doğrulanıyor: '0.5' de '0,5' de 0.5 verir."""

    def _ayirac_duzelt(self, text: str) -> str:
        ayirac = str(self.locale().decimalPoint())
        digeri = "." if ayirac == "," else ","
        return text.replace(digeri, ayirac)

    def validate(self, text, pos):
        return super().validate(self._ayirac_duzelt(text), pos)

    def valueFromText(self, text):
        return super().valueFromText(self._ayirac_duzelt(text))


class NoWheelComboBox(NoWheelMixin, QComboBox):
    pass


class ROIResultPanel(QGroupBox):
    """"Kontrol Merkezi" — canlı görüntünün üstündeki denetim sonucu TABLOSU.

    Her kontrol noktası bir SATIR; sütunlar hizalı (QGridLayout) ve satır araları
    çizgili → tablo görünümü. Satır:
        ad | OK/NOK rozeti | ölçüm+eşik kutusu (1-2 adet) | sebep

    **Delikte İKİ eşik vardır** (kullanıcı karışıklığı, 2026-08-03: "ölçülen 35.9,
    eşik 30, yine de hata"): `açıklık` (koyu%) VE `derinlik` (çekirdek%). Panel
    eskiden yalnız açıklığı gösteriyordu, derinlikten kalan nokta sebepsiz NOK gibi
    görünüyordu. Artık ikisi de gösterilir ve ikisi de buradan ayarlanır.

    Eşiklerin HEPSİ ALT SINIRDIR: ölçülen >= eşik olmalı. Bu yüzden her kutunun
    başında "en az" yazar (≥/< sembolleri kullanıcı isteğiyle KALDIRILDI — iki
    gösterge kafa karıştırıyordu, yazı yeterli).
    """

    # tip -> [(config anahtari, sutun basligi, olcum anahtari, varsayilan), ...]
    THRESHOLDS = {
        "hole": [("hole_dark_ratio_min", "açıklık", "black_ratio", 20.0),
                 ("hole_core_ratio_min", "derinlik", "core_ratio", 2.0)],
        "notch": [("notch_dark_min", "oluk", "black_ratio", 50.0)],
    }
    MAX_ESIK = 2                       # bir satirda en fazla kac esik kutusu

    threshold_changed = pyqtSignal(str, str, float)   # (nokta_adi, anahtar, yeni_deger)

    def __init__(self, parent=None):
        super().__init__("Kontrol Merkezi", parent)
        self._rows = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 6)
        outer.setSpacing(4)

        self.lbl_header = QLabel("Denetim bekleniyor")
        self.lbl_header.setAlignment(Qt.AlignCenter)
        self.lbl_header.setFont(QFont("Arial", 12, QFont.Bold))
        outer.addWidget(self.lbl_header)

        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(3)
        self._grid.setColumnStretch(2 + self.MAX_ESIK * 3, 1)    # sebep sutunu esner
        outer.addLayout(self._grid)
        self._set_header(None)

    # ---- ic yardimcilar -------------------------------------------------
    def _set_header(self, is_ok):
        if is_ok is None:
            self.lbl_header.setText("Denetim bekleniyor"); renk = "#9aa0ab"
        elif is_ok:
            self.lbl_header.setText("PARÇA OK");  renk = "#2ecc71"
        else:
            self.lbl_header.setText("PARÇA NOK"); renk = "#ff4d4d"
        self.lbl_header.setStyleSheet(f"color:{renk}; padding:1px;")

    def _make_row(self, name, grid_row, esik_var=True):
        """esik_var=False (ör. 'YON' satırı): eşik sütunları HİÇ oluşturulmaz ve
        sonuç yazısı rozetin hemen yanından başlar (boş sütunların sağına itilmesin)."""
        info = {"name": name, "cells": [], "widgets": []}
        col = 0

        lbl_name = QLabel(str(name))
        lbl_name.setFont(QFont("Arial", 11, QFont.Bold))
        lbl_name.setMinimumWidth(38)
        lbl_name.setStyleSheet("color:#d7dae0;")
        self._grid.addWidget(lbl_name, grid_row, col); col += 1

        lbl_state = QLabel("—")
        lbl_state.setAlignment(Qt.AlignCenter)
        lbl_state.setFixedWidth(56)
        lbl_state.setFont(QFont("Arial", 11, QFont.Bold))
        self._grid.addWidget(lbl_state, grid_row, col); col += 1

        # Her esik icin 3 sutun: "olcum" | "en az" | kutu
        for _ in range(self.MAX_ESIK if esik_var else 0):
            lbl_m = QLabel("")
            lbl_m.setFont(QFont("Arial", 11, QFont.Bold))
            lbl_m.setStyleSheet("color:#d7dae0;")
            lbl_m.setMinimumWidth(118)
            lbl_r = QLabel("en az")
            lbl_r.setStyleSheet("color:#9aa0ab; font-size:11px;")
            spin = NoWheelDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(1)
            spin.setSingleStep(1.0)
            spin.setSuffix(" %")
            spin.setFixedWidth(88)
            spin.setKeyboardTracking(False)
            spin.setAlignment(Qt.AlignCenter)
            spin.setFont(QFont("Arial", 11, QFont.Bold))
            for wdg in (lbl_m, lbl_r, spin):
                self._grid.addWidget(wdg, grid_row, col); col += 1
            hucre = {"measured": lbl_m, "rule": lbl_r, "spin": spin, "key": None}
            timer = QTimer(spin)
            timer.setSingleShot(True); timer.setInterval(400)
            timer.timeout.connect(lambda n=name, h=hucre: self._emit_change(n, h))
            hucre["timer"] = timer
            spin.valueChanged.connect(lambda _v, tm=timer: tm.start())
            spin.editingFinished.connect(lambda n=name, h=hucre: self._emit_change(n, h))
            info["cells"].append(hucre)
            info["widgets"] += [lbl_m, lbl_r, spin]

        lbl_note = QLabel("")
        lbl_note.setFont(QFont("Arial", 11))
        # Esik sutunu yoksa yazi rozetin yanindan baslasin: kalan sutunlari kapla.
        if esik_var:
            self._grid.addWidget(lbl_note, grid_row, col)
        else:
            self._grid.addWidget(lbl_note, grid_row, col, 1, self.MAX_ESIK * 3 + 1)
        info["note"] = lbl_note
        info["widgets"] += [lbl_name, lbl_state, lbl_note]
        info["state"] = lbl_state
        return info

    def _add_separator(self, grid_row):
        cizgi = QFrame()
        cizgi.setFrameShape(QFrame.HLine)
        cizgi.setStyleSheet("color:#2c313b; background-color:#2c313b; max-height:1px;")
        self._grid.addWidget(cizgi, grid_row, 0, 1, 3 + self.MAX_ESIK * 3)
        return cizgi

    def _emit_change(self, name, hucre):
        hucre["timer"].stop()
        if hucre["key"]:
            self.threshold_changed.emit(str(name), hucre["key"], float(hucre["spin"].value()))

    def _clear(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._rows = {}

    # ---- disa donuk API --------------------------------------------------
    def update_results(self, is_ok, results, thresholds, types):
        """results: evaluate_with_profile sonucu.
        thresholds: {ad: [(anahtar, baslik, olcum_anahtari, deger), ...]}
        types: {ad: 'hole'|'notch'|'yon'}"""
        self._set_header(is_ok)
        if set(results) != set(self._rows):
            self._clear()
            satir = 0
            for name in results:
                if satir:
                    self._add_separator(satir); satir += 1
                self._rows[name] = self._make_row(
                    name, satir, esik_var=bool(thresholds.get(name)))
                satir += 1

        for name, res in results.items():
            info = self._rows[name]
            ok = bool(res.get("ok", True))
            info["state"].setText("OK" if ok else "NOK")
            info["state"].setStyleSheet(
                "color:#0d1a11; background-color:#2ecc71; border-radius:4px; padding:1px;"
                if ok else
                "color:#2a0f10; background-color:#ff4d4d; border-radius:4px; padding:1px;")

            metrics = res.get("metrics", {}) or {}
            esikler = thresholds.get(name) or []
            for i, hucre in enumerate(info["cells"]):
                if i >= len(esikler):
                    hucre["key"] = None
                    for k in ("measured", "rule", "spin"):
                        hucre[k].setVisible(False)
                    continue
                key, baslik, olcum_anahtari, deger = esikler[i]
                hucre["key"] = key
                for k in ("measured", "rule", "spin"):
                    hucre[k].setVisible(True)
                olculen = metrics.get(olcum_anahtari)
                hucre["measured"].setText(
                    f"{baslik} %{olculen:.1f}" if isinstance(olculen, (int, float))
                    else f"{baslik} —")
                # Programatik guncelleme sinyal TETIKLEMESIN (yoksa config'e geri yazar).
                hucre["spin"].blockSignals(True)
                hucre["spin"].setValue(float(deger))
                hucre["spin"].blockSignals(False)
                hucre["spin"].setToolTip(
                    f"{name} — {baslik} alt sınırı\n"
                    f"KURAL: ölçülen {baslik} bu değerden BÜYÜK/EŞİT olmalı.\n"
                    "Tıklayıp rakamı yazın (Enter) ya da okları kullanın.\n"
                    "Fare tekerleği bilerek devre dışı (kazara değişmesin).")

            # Sebep sutunu: OK ise bos, NOK ise neden kaldigi. 'yon' satirinda
            # esik olmadigi icin sonucun kendisi burada yazar (diger satirlarla
            # ayni yazi tipi/boyutu - kullanici istegi).
            mesaj = res.get("msg", "")
            if types.get(name) == "yon":
                info["note"].setText(mesaj)
                info["note"].setStyleSheet("color:#d7dae0;" if ok else "color:#ff9b9b;")
            else:
                info["note"].setText("" if ok else mesaj)
                info["note"].setStyleSheet("color:#ff9b9b;")
            # Dar ekranda yazi kesilebilir; tam metin her zaman ipucunda dursun.
            info["note"].setToolTip(mesaj)


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

STYLESHEET = """
/* === Profesyonel koyu (grafit) tema === */
QMainWindow, QDialog { background-color: #15171c; }
QWidget { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #d6dae2; }
QLabel { color: #c4c9d2; background: transparent; }

/* Panel kartlari */
QGroupBox {
    background-color: #1b1e25;
    color: #aeb4bf;
    border: 1px solid #2c313b;
    border-radius: 8px;
    margin-top: 22px;
    padding-top: 8px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 3px 10px;
    background-color: #262b36;
    border: 1px solid #313845;
    border-radius: 5px;
    color: #cdd6e6;
    font-weight: bold;
}

/* Butonlar: varsayilan = notr gri */
QPushButton {
    background-color: #272c36;
    color: #d6dae2;
    border: 1px solid #353b47;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover { background-color: #2f3641; border-color: #434b59; }
QPushButton:pressed { background-color: #20242c; }
QPushButton:disabled { background-color: #1d2026; color: #5a606b; border-color: #262a31; }

/* Vurgulu butonlar (yalniz anlamli aksiyonlar) */
QPushButton[accent="primary"] { background-color: #345e8c; color: #f2f6fb; border: 1px solid #3f6fa3; }
QPushButton[accent="primary"]:hover { background-color: #3d6ea3; border-color: #4880bd; }
QPushButton[accent="primary"]:pressed { background-color: #2c5179; }
QPushButton[accent="success"] { background-color: #2f6d4f; color: #eef6f1; border: 1px solid #387f5c; }
QPushButton[accent="success"]:hover { background-color: #38805d; border-color: #429069; }
QPushButton[accent="success"]:pressed { background-color: #285f44; }
QPushButton[accent="danger"] { background-color: #8f3f43; color: #f7eded; border: 1px solid #a44a4e; }
QPushButton[accent="danger"]:hover { background-color: #a3494d; border-color: #b85458; }
QPushButton[accent="danger"]:pressed { background-color: #7a363a; }
QPushButton[accent="primary"]:disabled,
QPushButton[accent="success"]:disabled,
QPushButton[accent="danger"]:disabled { background-color: #1d2026; color: #5a606b; border: 1px solid #262a31; }

QCheckBox { color: #c4c9d2; font-size: 13px; background: transparent; }
QCheckBox:disabled { color: #5a606b; }

/* Girisler */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #1e222a;
    color: #d6dae2;
    border: 1px solid #2f343f;
    border-radius: 5px;
    padding: 4px 6px;
    selection-background-color: #345e8c;
    selection-color: #f2f6fb;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover { border-color: #3c4250; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus { border-color: #3f6fa3; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {
    background-color: #191c22; color: #5a606b; border-color: #23272e;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background-color: #1e222a; color: #d6dae2;
    border: 1px solid #2f343f; selection-background-color: #345e8c;
    outline: 0;
}

/* Loglar */
QTextEdit {
    background-color: #14161b;
    color: #9aa0ab;
    border: 1px solid #2c313b;
    border-radius: 6px;
    padding: 6px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
}

/* Kaydiriciar */
QSlider::groove:horizontal { border: none; height: 6px; background: #2a2f39; margin: 2px 0; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #345e8c; border-radius: 3px; }
QSlider::handle:horizontal { background: #3f6fa3; border: none; width: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::handle:horizontal:hover { background: #4880bd; }

/* Scrollbar */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #15171c; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #2f343f; border-radius: 6px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #3c4250; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: #15171c; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #2f343f; border-radius: 6px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #3c4250; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""

class SettingsDialog(QDialog):
    """PLC + kamera + çekim ayarları tek pencerede (sol panelden taşındı).

    Yalnız arayüzü kurar ve değerleri toplar; uygulama/yan etkiler (kamera restart,
    PLC adapter yenileme, config yazma) 'Kaydet' sonrası MainWindow._apply_settings'te.
    """

    # 1456x1088 = imx296 Global Shutter'in DOGAL (native) cozunurlugu: en keskin
    # goruntu. Dijital zoom yazilimda kirpip geri buyuttugu icin DETAY URETMEZ,
    # bulaniklastirir (olculdu: zoom 2.0 -> gercek detayin ~%33'u). Buyutme gerekiyorsa
    # once dogal cozunurluk + zoom 1.0 denenmeli; hala kucukse kamerayi fiziksel
    # yaklastirmak (optik) tek gercek cozumdur.
    RESOLUTIONS = ["1456x1088", "1280x960", "800x600", "640x640", "640x480"]

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(420)
        self.resize(440, 720)
        cfg_plc = config.get("plc", {}) or {}
        cfg_cam = config.get("camera", {}) or {}
        cfg_res = config.get("resolution", {}) or {}
        cfg_insp = config.get("inspection", {}) or {}
        cfg_cams = config.get("cameras", {}) or {}
        cfg_cam2 = config.get("camera2", {}) or {}
        cfg_res2 = config.get("resolution2", {}) or {}

        # Iki kamera bolumuyle pencere uzayabilir: icerik kaydirilabilir, butonlar sabit.
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)

        # --- PLC ---
        plc_group = QGroupBox("PLC")
        plc_form = QFormLayout(plc_group)
        self.combo_plc_type = NoWheelComboBox()
        self.combo_plc_type.addItems(["null", "modbus_tcp"])
        idx = self.combo_plc_type.findText(str(cfg_plc.get("type", "null")))
        self.combo_plc_type.setCurrentIndex(idx if idx >= 0 else 0)
        self.input_plc_host = QLineEdit(str(cfg_plc.get("host", "192.168.10.10")))
        self.spin_plc_port = NoWheelSpinBox()
        self.spin_plc_port.setRange(1, 65535)
        self.spin_plc_port.setValue(int(cfg_plc.get("port", 502)))
        self.spin_plc_unit = NoWheelSpinBox()
        self.spin_plc_unit.setRange(0, 247)
        self.spin_plc_unit.setValue(int(cfg_plc.get("unit_id", 1)))
        self.spin_plc_poll = NoWheelSpinBox()
        self.spin_plc_poll.setRange(10, 1000)
        self.spin_plc_poll.setSingleStep(10)
        self.spin_plc_poll.setValue(int(cfg_plc.get("poll_ms", 50)))
        plc_form.addRow("PLC Tipi:", self.combo_plc_type)
        plc_form.addRow("PLC IP:", self.input_plc_host)
        plc_form.addRow("PLC Port:", self.spin_plc_port)
        plc_form.addRow("Unit ID:", self.spin_plc_unit)
        plc_form.addRow("Poll ms:", self.spin_plc_poll)
        layout.addWidget(plc_group)

        # --- Kameralar (her ikisi de BAGIMSIZ acilip kapanir) ---
        # Grup basligindaki kutu = o kamerayi kullan/kullanma. Kapali kamera hic
        # acilmaz, satiri gizlenir. En az bir kamera acik olmalidir (accept'te kontrol).
        def _enabled(n):
            # Yeni bayrak varsa o; yoksa eski enabled_count (1|2) ile geriye uyum.
            key = f"camera{n}_enabled"
            if key in cfg_cams:
                return bool(cfg_cams[key])
            return n <= int(cfg_cams.get("enabled_count", 1) or 1)

        cam_group, self._cam1_w = self._build_camera_group(
            "Kamera 1 (kullan)", cfg_cam, cfg_res, checked=_enabled(1))
        layout.addWidget(cam_group)

        # Kamera 2 on-dolumu: yazilmamis anahtarlar kamera 1'den devralinir.
        cam2_group, self._cam2_w = self._build_camera_group(
            "Kamera 2 (kullan)", {**cfg_cam, **cfg_cam2}, {**cfg_res, **cfg_res2},
            checked=_enabled(2))
        layout.addWidget(cam2_group)

        hint_cams = QLabel(
            "İki kamera da açıksa TEK PLC tetiğinde ikisi de çeker; iki analiz VE'lenir\n"
            "(ikisi de OK ise parça OK) ve PLC'ye TEK sonuç yazılır. Her kameranın\n"
            "kendi kontrol noktaları ve eşikleri vardır. En az bir kamera açık olmalı.")
        hint_cams.setWordWrap(True)
        hint_cams.setStyleSheet("color:#a6adc8; font-size:11px;")
        layout.addWidget(hint_cams)

        # --- Çekim ---
        insp_group = QGroupBox("Çekim")
        insp_form = QFormLayout(insp_group)
        self.spin_trigger_delay = NoWheelSpinBox()
        self.spin_trigger_delay.setRange(0, 5000)
        self.spin_trigger_delay.setSingleStep(10)
        self.spin_trigger_delay.setValue(int(cfg_insp.get("trigger_delay_ms", 0)))
        insp_form.addRow("Çekim Gecikmesi ms:", self.spin_trigger_delay)
        layout.addWidget(insp_group)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("Kaydet")
        btn_save.setProperty("accent", "primary")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Vazgeç")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        outer.addLayout(btn_row)

    def _build_camera_group(self, title: str, cam_cfg: dict, res_cfg: dict, checked: bool = True):
        """Bir kameranın ayar grubu (çözünürlük/FPS/zoom/exposure/gain).
        Grup başlığındaki kutu o kameranın AÇIK/KAPALI durumudur (kapalıyken
        alanlar da pasifleşir). Döner: (QGroupBox, widget sözlüğü)."""
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(bool(checked))
        form = QFormLayout(group)
        w = {"group": group}

        w["res"] = NoWheelComboBox()
        w["res"].addItems(self.RESOLUTIONS)
        curr_res = f"{int(res_cfg.get('width', 640))}x{int(res_cfg.get('height', 480))}"
        idx = w["res"].findText(curr_res)
        if idx < 0:  # listede olmayan ozel cozunurluk: sessizce degistirme, listeye ekle
            w["res"].insertItem(0, curr_res)
            idx = 0
        w["res"].setCurrentIndex(idx)

        w["fps"] = NoWheelSpinBox()
        w["fps"].setRange(1, 120)
        w["fps"].setValue(int(cam_cfg.get("fps", 60)))

        zoom_val = min(30, max(10, int(round(float(cam_cfg.get("zoom", 1.0)) * 10))))
        w["zoom_lbl"] = QLabel(f"{zoom_val / 10:.1f}x")
        w["zoom"] = NoWheelSlider(Qt.Horizontal)
        w["zoom"].setRange(10, 30)
        w["zoom"].setValue(zoom_val)
        w["zoom"].valueChanged.connect(
            lambda v, lbl=w["zoom_lbl"]: lbl.setText(f"{v / 10:.1f}x"))
        zoom_row = QWidget()
        zoom_layout = QHBoxLayout(zoom_row)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.addWidget(w["zoom"], stretch=1)
        zoom_layout.addWidget(w["zoom_lbl"])

        w["manual_exp"] = QCheckBox("Aktif")
        w["manual_exp"].setChecked(bool(cam_cfg.get("manual_exposure_enabled", False)))
        # ALT SINIR = SENSORUN gercek alt siniri (imx296: 29 us; Pi'de olculdu).
        # Eskiden min=100/adim=100 idi -> hareketli bantta gereken kisa pozlara
        # (~50-150 us) INILEMIYORDU. Adim 50 us: 100-1000 us araliginda hassas ayar.
        w["exposure"] = NoWheelSpinBox()
        w["exposure"].setRange(20, 1000000)
        w["exposure"].setSingleStep(50)
        w["exposure"].setValue(int(cam_cfg.get("exposure_us", 8000)))
        w["exposure"].setToolTip(
            "POZ SÜRESİ (mikrosaniye): sensörün ışığı topladığı süre.\n"
            "Uzun = aydınlık ama HAREKET BULANIK. Kısa = karanlık ama KESKİN.\n"
            "Sensör alt sınırı 29 µs (altı yazılsa da kırpılır).\n"
            "Sahada ölçüldü (aydınlatma açık, Gain 16): 300 µs -> metal 148,\n"
            "500 µs -> 186, 1000 µs -> 232, 4000 µs -> DOYGUN (delik kaybolur!).\n"
            "Hareketli bantta önerilen: 300-500 µs. Fazla poz da az poz kadar zararlı.")
        # ANALOG GAIN TAVANI = 16: imx296'nin GERCEK analog tavani 15.7 (Pi'de olculdu).
        # Ustunu istersen libcamera SESSIZCE DIJITAL kazanca cevirir (gain 26/43/64
        # istendi -> analog hep 15.7, kalani dijital 1.7/2.8/8.0). Dijital kazanc
        # gurultuyu de carpar, bilgi EKLEMEZ: 29 us + dijital 8.0'da goruntu grilesip
        # metal dokusu kayboldu. Bu yuzden tavan bilincli olarak 16'da tutuluyor.
        w["gain"] = NoWheelDoubleSpinBox()
        w["gain"].setRange(1.0, 16.0)
        w["gain"].setSingleStep(0.5)
        w["gain"].setDecimals(1)
        w["gain"].setValue(float(cam_cfg.get("analogue_gain", 1.0)))
        w["gain"].setToolTip(
            "ANALOG GAIN: sensörden gelen sinyali ELEKTRONİK olarak yükseltir.\n"
            "Görüntüyü aydınlatır ama IŞIK EKLEMEZ -> gürültü de birlikte büyür.\n"
            "Tavan 16 = imx296'nın gerçek analog sınırı (ölçüldü: 15.7). Üstü\n"
            "sensörde YOK; libcamera dijital kazanca çevirir (sahte parlaklık).\n"
            "Kısa poz yüzünden karardıysa gain'i 16'ya kadar aç; hâlâ karanlıksa\n"
            "tek gerçek çözüm AYDINLATMAYI güçlendirmektir.")

        form.addRow("Çözünürlük:", w["res"])
        form.addRow("Kamera FPS:", w["fps"])
        form.addRow("Dijital Zoom:", zoom_row)
        form.addRow("Exposure/Gain Kilidi:", w["manual_exp"])
        form.addRow("Exposure us:", w["exposure"])
        form.addRow("Analog Gain:", w["gain"])
        return group, w

    @staticmethod
    def _camera_values(w: dict) -> dict:
        res_w, res_h = map(int, w["res"].currentText().split("x"))
        return {
            "res_w": res_w,
            "res_h": res_h,
            "fps": int(w["fps"].value()),
            "zoom": w["zoom"].value() / 10.0,
            "manual_exposure": bool(w["manual_exp"].isChecked()),
            "exposure_us": int(w["exposure"].value()),
            "analogue_gain": float(w["gain"].value()),
        }

    def values(self) -> dict:
        vals = {
            "plc_type": self.combo_plc_type.currentText(),
            "plc_host": self.input_plc_host.text().strip() or "192.168.10.10",
            "plc_port": int(self.spin_plc_port.value()),
            "plc_unit_id": int(self.spin_plc_unit.value()),
            "plc_poll_ms": int(self.spin_plc_poll.value()),
            "trigger_delay_ms": int(self.spin_trigger_delay.value()),
        }
        # Kamera 1 anahtarlari ESKI adlariyla duz sozlukte (geriye uyum).
        vals.update(self._camera_values(self._cam1_w))
        vals["camera1_enabled"] = bool(self._cam1_w["group"].isChecked())
        vals["camera2_enabled"] = bool(self._cam2_w["group"].isChecked())
        vals["cam2"] = self._camera_values(self._cam2_w)
        return vals

    def accept(self):
        # En az bir kamera acik olmali; ikisi de kapaliysa denetim yapilamaz.
        if not (self._cam1_w["group"].isChecked() or self._cam2_w["group"].isChecked()):
            QMessageBox.warning(self, "Kamera seçimi",
                                "En az bir kamera açık olmalı.\n"
                                "Kamera 1 ya da Kamera 2 kutusunu işaretleyin.")
            return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.worker = None
        self.rois = self.config.get("dynamic_rois", {})
        self.disabled_rois = set(self.config.get("disabled_rois", []))
        self._last_snapshot = None
        self._last_full_snapshot = None
        self._snapshot_full_pixmap = None
        self._last_product_box = None
        # --- IKINCI KAMERA (opsiyonel, cameras.enabled_count=2) ---
        # Kamera 1'in alanlarina HIC dokunulmaz; kamera 2 PARALEL alanlarda tutulur
        # (config'teki camera2/resolution2/dynamic_rois_2/roi2 mantiginin aynisi).
        # enabled_count=1 iken bu alanlar bos kalir ve program birebir eskisi gibi calisir.
        self.worker2 = None
        self.rois_2 = self.config.get("dynamic_rois_2", {})
        self.disabled_rois_2 = set(self.config.get("disabled_rois_2", []))
        self._last_snapshot_2 = None
        self._last_full_snapshot_2 = None
        self._snapshot_full_pixmap_2 = None
        self._last_product_box_2 = None
        self._cam1_row = None
        self._cam2_row = None
        # Odak (netlik) yardimcisi: kamera basina anlik ve en iyi netlik degeri
        self._focus_values = {}
        self._focus_best = {}
        self._focus_last = {}
        self._capture_counter = 0
        self._inspection_state = InspectionState.READY
        # Ayarlar/Kontrol Noktalari penceresi acikken PLC tetigi cekim baslatmasin
        # (eski kalibrasyon modunun tek gerekli kalintisi).
        self._dialog_paused = False
        self._capture_pending = False
        self._last_plc_connected = None
        self._nok_reset_pending = False
        self.plc = create_plc_adapter(self.config)

        self.setWindowTitle("Konveyör Denetim Sistemi - ROI Eşik")
        self.resize(1180, 720)
        self.setStyleSheet(STYLESHEET)

        self._init_ui()
        self._start_worker()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # ==========================================
        # SOL PANEL (Kontroller & Parametreler)
        # ==========================================
        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Sistem Durumu Group
        status_group = QGroupBox("Sistem Durumu")
        status_layout = QFormLayout(status_group)
        self.lbl_state = QLabel("BAŞLATILIYOR...")
        self.lbl_state.setFont(QFont("Arial", 12, QFont.Bold))
        self.lbl_state.setStyleSheet("color: #d8a657;")
        self.lbl_fps = QLabel("0.0")
        self.lbl_fps.setFont(QFont("Arial", 11))
        self.lbl_plc = QLabel("READY")
        self.lbl_plc.setFont(QFont("Arial", 11, QFont.Bold))
        self.lbl_plc.setStyleSheet("color: #62b87d;")
        # ODAK (netlik) yardimcisi: lens odak halkasini cevirirken bu sayi
        # EN YUKSEK olduginda odak dogrudur. Yaninda o kamerada gorulen en iyi
        # deger de yazar; boylece tepe noktasini gectigini anlarsin.
        self.lbl_focus = QLabel("-")
        self.lbl_focus.setFont(QFont("Arial", 11, QFont.Bold))
        self.lbl_focus.setStyleSheet("color: #7cc4e8;")
        self.lbl_focus.setToolTip(
            "NETLİK (odak) yardımcısı — lens odak halkasını çevirirken kullan.\n"
            "Sayı EN YÜKSEK olduğunda odak en iyidir; parantezdeki değer o kamerada\n"
            "görülen en iyi netliktir (tepeyi geçtiysen sayı düşer).\n"
            "DİKKAT: yalnız ışık/exposure SABİTKEN kıyaslanabilir; farklı kameraların\n"
            "ya da farklı sahnelerin değerleri birbiriyle kıyaslanmaz.")
        # POZ SURESI: hareket bulanikliginin ASIL sebebi. Global shutter uzun pozdaki
        # bulanikligi ONLEMEZ. Oto-pozlama parlaklik icin pozu uzatir (16.6 ms'ye kadar
        # olculdu) -> bant hareket ederken parca bulanik cikar.
        self.lbl_exposure = QLabel("-")
        self.lbl_exposure.setFont(QFont("Arial", 11, QFont.Bold))
        self.lbl_exposure.setStyleSheet("color: #9aa0ab;")
        self.lbl_exposure.setToolTip(
            "Kameranın FİİLEN kullandığı poz süresi (oto-pozlamada değişir).\n"
            "HAREKET BULANIKLIĞI doğrudan bu süreyle orantılıdır:\n"
            "bant hareket ederken parça, poz süresi boyunca yol alır.\n"
            "Bant hareketliyken kural: ≤1 ms hedefle (yeşil), 1-3 ms sınırda (sarı),\n"
            ">3 ms bulanık (kırmızı). Kısaltmak için: Ayarlar → 'Exposure/Gain Kilidi'\n"
            "işaretle + 'Exposure us' düşür; karardıysa ışığı artır ya da Analog Gain yükselt.")
        status_layout.addRow("Durum:", self.lbl_state)
        status_layout.addRow("FPS:", self.lbl_fps)
        status_layout.addRow("Netlik:", self.lbl_focus)
        status_layout.addRow("Poz:", self.lbl_exposure)
        status_layout.addRow("PLC:", self.lbl_plc)
        left_layout.addWidget(status_group)

        # 2. Calisma Modu — sol panelde tek operasyonel anahtar kaldi. Tum PLC/kamera/
        # cekim ayarlari sag paneldeki "⚙ Ayarlar" penceresine tasindi; kalibrasyon
        # kilidi kaldirildi (Kontrol Noktalari kaydedilince sistem hazirdir).
        mode_group = QGroupBox("Çalışma Modu")
        mode_layout = QVBoxLayout(mode_group)

        # Elle cekim modu: PLC'yi tamamen kapatir (ev/test). Isaretliyse baglanti
        # denemesi/log olmaz, GUI bloklanmaz, tetik beklenmez. Sahada (PLC'li)
        # kapatilir; plc.type korunur.
        self.chk_manual_mode = QCheckBox("Elle Çekim Modu (PLC devre dışı)")
        self.chk_manual_mode.setToolTip(
            "İşaretliyse PLC tamamen kapatılır (ev/test): bağlantı denemesi ve log olmaz,\n"
            "canlı görüntü bloklanmaz, tetik beklenmez. BOŞLUK/ENTER ya da canlı görüntüye\n"
            "tıklayarak elle resim çek. Sahada (PLC bağlıyken) bu kutuyu KAPAT.")
        self.chk_manual_mode.setChecked(bool(self.config.get("plc", {}).get("manual_mode", False)))
        self.chk_manual_mode.stateChanged.connect(self._on_manual_mode_changed)
        mode_layout.addWidget(self.chk_manual_mode)

        hint = QLabel("Elle çekim: BOŞLUK/ENTER ya da canlı görüntüye tıkla.\n"
                      "Kamera/PLC ayarları: aşağıdaki '⚙ Ayarlar'.\n"
                      "Eşikler: Kontrol Noktaları → noktaya sağ tık → Ayarlar.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a6adc8; font-size:11px;")
        mode_layout.addWidget(hint)

        left_layout.addWidget(mode_group)

        left_layout.addStretch()

        # 3. "⚙ Ayarlar" — SOL PANELİN DİBİNDE, SABİT.
        # Kamera satırlarında DEĞİL: bir kamera kapatılınca o satır gizlendiği için
        # oradaki buton erişilemez oluyordu (kamera 1 kapalıyken Ayarlar'a girilemiyordu).
        # Ayarlar tüm kameralar + PLC için ortak olduğundan yeri sol panel.
        self.btn_settings = QPushButton("⚙ Ayarlar")
        self.btn_settings.setToolTip(
            "PLC, kamera(lar) ve çekim ayarları (tek pencerede; Kaydet ile uygulanır).\n"
            "Kameraları buradan açıp kapatabilirsiniz.")
        self.btn_settings.clicked.connect(self._open_settings)
        left_layout.addWidget(self.btn_settings)

        # ==========================================
        # KAMERA SATIRLARI (her kamera: canlı | son çekim)
        # ==========================================
        # Kamera 2 satiri YALNIZ cameras.enabled_count=2 iken gorunur; tek kamerada
        # duzen birebir eskisi gibidir (ust satir + altta tam-genislik log).
        self._cam1_row = self._build_camera_row(1)
        self._cam2_row = self._build_camera_row(2)
        # Her kamera BAGIMSIZ acilip kapanir: kapali kameranin satiri gizlenir.
        self._cam1_row.setVisible(self._camera_enabled(1))
        self._cam2_row.setVisible(self._camera_enabled(2))

        # Sistem Logları: en altta, tam genişlik
        log_group = QGroupBox("Sistem Logları")
        log_layout = QVBoxLayout(log_group)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.txt_logs)
        log_group.setMinimumHeight(150)

        # Kamera satır(lar)ı + alttaki tam-genişlik log dikey istiflenir
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._cam1_row, stretch=3)
        content_layout.addWidget(self._cam2_row, stretch=3)
        content_layout.addWidget(log_group, stretch=1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFixedWidth(320)
        left_scroll.setWidget(left_panel)

        main_layout.addWidget(left_scroll)
        main_layout.addWidget(content_widget, stretch=1)

    def _build_camera_row(self, cam_no: int) -> QWidget:
        """Bir kameranın satırını kurar: solda canlı görüntü (üstünde son denetim
        sonucu bandı), sağda son alınan tam resim + o kameraya ait butonlar.

        Widget'lar kamera 1 için eski adlarıyla (video_label, lbl_snapshot, ...),
        kamera 2 için '_2' ekli paralel adlarla saklanır."""
        two = (cam_no == 2)
        suffix = "  (Kamera 2)" if two else ""

        # --- SOL: canlı görüntü ---
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(10, 0, 10, 0)

        # Canli goruntunun hemen ustunde son denetim sonucu/hatalar (kirmizi = NOK).
        # Son denetim sonucu: HER kontrol noktasi icin bir satir (ad | OK/NOK |
        # olculen | esik slider'i). Slider o noktanin esigini dogrudan ayarlar.
        lbl_live_errors = ROIResultPanel()
        lbl_live_errors.threshold_changed.connect(
            lambda ad, anahtar, deger, n=cam_no: self._on_panel_threshold_changed(n, ad, anahtar, deger))
        lbl_live_errors.setVisible(False)
        center_layout.addWidget(lbl_live_errors)

        video_label = QLabel(f"Kamera Görüntüsü Bekleniyor...{suffix}")
        video_label.setAlignment(Qt.AlignCenter)
        video_label.setStyleSheet("background-color: #0f1115; border: 1px solid #2c313b; border-radius: 8px;")
        video_label.setMinimumSize(480, 360)
        video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Elle Cekim Modunda canli goruntuye tiklayinca resim cek + test et
        # (iki kamera etkinse tek tikla IKISI birden cekilir; karar VE'lenir).
        video_label.setToolTip("Elle Çekim Modunda: tıkla → resim çek ve test et")
        video_label.mousePressEvent = self._on_video_clicked
        center_layout.addWidget(video_label)

        # --- SAĞ: son alınan resim + butonlar ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        snapshot_group = QGroupBox(f"Son Alınan Tam Resim{suffix}  (tam çözünürlük için tıkla)")
        snapshot_layout = QVBoxLayout(snapshot_group)
        lbl_snapshot = QLabel("Henüz resim alınmadı.")
        lbl_snapshot.setAlignment(Qt.AlignCenter)
        lbl_snapshot.setStyleSheet("background-color: #14161b; border: 1px solid #2c313b; border-radius: 6px;")
        lbl_snapshot.setMinimumHeight(240)
        lbl_snapshot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lbl_snapshot.setCursor(Qt.PointingHandCursor)
        lbl_snapshot.setToolTip("Büyütmek için tıklayın")
        lbl_snapshot.mousePressEvent = lambda event, n=cam_no: self._open_snapshot_zoom(event, n)
        snapshot_layout.addWidget(lbl_snapshot, stretch=1)

        # Her kameranin KENDI kontrol noktalari/urun cercevesi var (kamera secimi
        # ayri bir diyalog degil, ilgili kameranin satirindaki buton).
        btn_roi_manager = QPushButton(f"Kontrol Noktaları{suffix}")
        btn_roi_manager.setToolTip(
            "Kontrol noktalarını çiz/düzenle: Delik (daire), Çentik (kutu).\n"
            "Yön öğretme de burada: menüden 'Yön Referansı Al (doğru parça)'.\n"
            "Silmek için noktaya sağ tıkla.")
        btn_roi_manager.clicked.connect(lambda _=False, n=cam_no: self._open_roi_manager(n))
        snapshot_layout.addWidget(btn_roi_manager)

        # NOT: "⚙ Ayarlar" bilinçli olarak BURADA DEĞİL, SOL PANELDE (bkz. _init_ui).
        # Kamera satırı gizlenebildiği için (o kamera kapatılınca) buradaki bir buton
        # erişilemez hale gelirdi -> kamera 1 kapatılınca Ayarlar'a girilemiyordu.
        btn_find_product_box = QPushButton(f"Ürün Çerçevesi Bul{suffix}")
        btn_find_product_box.clicked.connect(lambda _=False, n=cam_no: self._capture_product_box_for_roi(n))
        snapshot_layout.addWidget(btn_find_product_box)

        right_layout.addWidget(snapshot_group, stretch=1)

        # Sağ resim panelini kaydırılabilir kapsayıcıya koy (taşarsa kaysın)
        images_scroll = QScrollArea()
        images_scroll.setWidgetResizable(True)
        images_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        images_scroll.setWidget(right_panel)

        # SATIR: solda canlı görüntü, sağda son alınan resim — eşit genişlik
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(center_panel, stretch=1)
        row_layout.addWidget(images_scroll, stretch=1)

        if two:
            self.lbl_live_errors_2 = lbl_live_errors
            self.video_label_2 = video_label
            self.lbl_snapshot_2 = lbl_snapshot
            self.btn_roi_manager_2 = btn_roi_manager
            self.btn_find_product_box_2 = btn_find_product_box
        else:
            self.lbl_live_errors = lbl_live_errors
            self.video_label = video_label
            self.lbl_snapshot = lbl_snapshot
            self.btn_roi_manager = btn_roi_manager
            self.btn_find_product_box = btn_find_product_box
        return row

    # ==========================================
    # İKİNCİ KAMERA — ortak yardımcılar
    # ==========================================
    def _camera_enabled(self, cam_no: int) -> bool:
        """Kamera açık mı? Her kamera BAĞIMSIZ açılıp kapatılır
        (`cameras.camera1_enabled` / `cameras.camera2_enabled`).
        Eski `cameras.enabled_count` (1|2) config'leri için geriye uyum korunur."""
        cams = self.config.get("cameras", {}) or {}
        key = f"camera{cam_no}_enabled"
        if key in cams:
            return bool(cams[key])
        return cam_no <= int(cams.get("enabled_count", 1) or 1)

    def _second_camera_enabled(self) -> bool:
        return self._camera_enabled(2)

    def _camera_config_view(self, cam_no: int) -> dict:
        """Kamera 2 için config GÖRÜNÜMÜ üretir (§13 çekirdek ilkesi).

        features.py / alignment.py'ye HİÇ dokunmadan, aynı fonksiyonları ikinci
        kameranın kendi ROI'leri ve eşikleriyle çalıştırmak için config'i remap eder.
        Kamera 1 için config'in kendisi döner (sıfır regresyon)."""
        if cam_no != 2:
            return self.config

        roi1 = self.config.get("roi", {}) or {}
        roi2 = self.config.get("roi2", {}) or {}
        # Esikler kamera 1'den devralinir, roi2 yazdiysa o kazanir. AMA nokta
        # KIMLIGINE bagli anahtarlar (hangi nokta hangi tip, referans kutusu, yon
        # referansi) kamera 1'den DEVRALINMAZ; yoksa kamera 2 yanlis noktalari
        # kullanir. Yon referansi yoksa features surum uyusmazliginda sessizce gecer.
        roi_view = {**roi1, **roi2}
        for key in ("roi_types", "point_overrides", "reference_box",
                    "handedness_hole_diff", "handedness_version", "handedness_check"):
            if key not in roi2:
                roi_view.pop(key, None)

        align1 = self.config.get("alignment", {}) or {}
        align2 = self.config.get("alignment2", {}) or {}

        return {
            **self.config,
            "camera": {**(self.config.get("camera", {}) or {}),
                       **(self.config.get("camera2", {}) or {})},
            "resolution": {**(self.config.get("resolution", {}) or {}),
                           **(self.config.get("resolution2", {}) or {})},
            "dynamic_rois": self.config.get("dynamic_rois_2", {}) or {},
            "disabled_rois": self.config.get("disabled_rois_2", []) or [],
            "roi": roi_view,
            "alignment": {**align1, **align2},
        }

    def _cam_widgets(self, cam_no: int) -> dict:
        """Kameranın arayüz parçaları (tek yerden erişim)."""
        if cam_no == 2:
            return {"video": getattr(self, "video_label_2", None),
                    "snapshot": getattr(self, "lbl_snapshot_2", None),
                    "errors": getattr(self, "lbl_live_errors_2", None)}
        return {"video": self.video_label,
                "snapshot": self.lbl_snapshot,
                "errors": self.lbl_live_errors}

    def _active_cameras(self) -> list:
        """Açık kameralar. İkisi de kapatılamaz; hepsi kapalıysa kamera 1'e düşülür."""
        return [n for n in (1, 2) if self._camera_enabled(n)] or [1]

    def keyPressEvent(self, event):
        # Elle test: BOSLUK/ENTER -> resim cek + test et. keyPressEvent yalniz odaktaki
        # widget tusu KULLANMADIYSA cagrilir; boylece metin kutularina yazmayi bozmaz.
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self._manual_capture()
            event.accept()
            return
        super().keyPressEvent(event)

    def _restart_plc_adapter(self):
        if self.plc:
            self.plc.close()
        self._nok_reset_pending = False
        self.plc = create_plc_adapter(self.config)
        self._set_inspection_state(InspectionState.READY)

    def _on_manual_mode_changed(self, *_):
        manual = bool(self.chk_manual_mode.isChecked())
        self.config.setdefault("plc", {})["manual_mode"] = manual
        self._save_config()
        self._last_plc_connected = None  # durum yeniden degerlendirilsin
        self._restart_plc_adapter()
        if manual:
            self.lbl_plc.setText("PLC KAPALI")
            self.lbl_plc.setStyleSheet("color:#9aa0ab;")
            self._append_log("[ELLE TEST] Elle çekim modu AÇIK: PLC devre dışı. "
                             "Resim çekmek için BOŞLUK/ENTER tuşu ya da canlı görüntüye tıkla.")
        else:
            self._append_log("[ÜRETİM] Elle çekim modu KAPALI: PLC etkin "
                             "(tetik HR101 ile otomatik çekim).")

    def _manual_mode_on(self) -> bool:
        return bool(self.config.get("plc", {}).get("manual_mode", False))

    def _manual_capture(self, *_):
        """Elle çekim (fare/tuş): Elle Çekim Modunda resim çek + analiz et. Üretimde
        (PLC açık) tuş/tık yanlışlıkla çekim yapmasın diye yok sayılır (çekimi PLC
        tetiği yapar)."""
        if not self._manual_mode_on():
            self._append_log("[ELLE TEST] Önce 'Elle Çekim Modu (PLC devre dışı)' kutusunu işaretle.")
            return
        self._capture_full_frame()

    def _on_video_clicked(self, event=None):
        # Canli goruntuye tiklayinca elle cekim (yalniz elle modda).
        self._manual_capture()

    def _open_settings(self):
        """'⚙ Ayarlar' penceresi: PLC + kamera + çekim ayarları. Pencere açıkken PLC
        tetiği çekim başlatmaz; 'Kaydet' ile değerler topluca uygulanır."""
        dlg = SettingsDialog(self.config, self)
        self._dialog_paused = True
        try:
            accepted = dlg.exec_() == QDialog.Accepted
        finally:
            self._dialog_paused = False
        if accepted:
            self._apply_settings(dlg.values())

    def _apply_settings(self, v: dict):
        """Ayarlar penceresinden gelen değerleri uygular: config'e yazar; yalnız
        DEĞİŞEN tarafı tetikler (kamera restart / zoom / PLC adapter yenileme)."""
        plc_cfg = self.config.setdefault("plc", {})
        new_plc = (v["plc_type"], v["plc_host"], v["plc_port"], v["plc_unit_id"], v["plc_poll_ms"])
        plc_changed = new_plc != (
            str(plc_cfg.get("type", "null")), str(plc_cfg.get("host", "192.168.10.10")),
            int(plc_cfg.get("port", 502)), int(plc_cfg.get("unit_id", 1)),
            int(plc_cfg.get("poll_ms", 50)))
        plc_cfg["type"] = v["plc_type"]
        plc_cfg["host"] = v["plc_host"]
        plc_cfg["port"] = v["plc_port"]
        plc_cfg["unit_id"] = v["plc_unit_id"]
        plc_cfg["poll_ms"] = v["plc_poll_ms"]

        self.config.setdefault("inspection", {})["trigger_delay_ms"] = v["trigger_delay_ms"]

        camera_cfg = self.config.setdefault("camera", {})
        res_cfg = self.config.setdefault("resolution", {})
        res_changed = (int(res_cfg.get("width", 0)), int(res_cfg.get("height", 0))) != (v["res_w"], v["res_h"])
        cam_restart = (res_changed
                       or int(camera_cfg.get("fps", 0)) != v["fps"]
                       or bool(camera_cfg.get("manual_exposure_enabled", False)) != v["manual_exposure"]
                       or int(camera_cfg.get("exposure_us", 0)) != v["exposure_us"]
                       or abs(float(camera_cfg.get("analogue_gain", 0.0)) - v["analogue_gain"]) > 1e-6)
        zoom_changed = abs(float(camera_cfg.get("zoom", 1.0)) - v["zoom"]) > 1e-6

        res_cfg["width"], res_cfg["height"] = v["res_w"], v["res_h"]
        camera_cfg["fps"] = v["fps"]
        camera_cfg["manual_exposure_enabled"] = v["manual_exposure"]
        camera_cfg["exposure_us"] = v["exposure_us"]
        camera_cfg["analogue_gain"] = v["analogue_gain"]
        camera_cfg["zoom"] = v["zoom"]

        if self.worker:
            if cam_restart:
                # Tek restart yeter: worker._open_camera cozunurluk/FPS/exposure'u
                # config'ten yeniden okur.
                self._append_log("[Ayarlar] Kamera ayarları değişti; kamera yeniden başlatılıyor...")
                self.worker.change_camera_controls()
            if zoom_changed:
                self.worker.set_zoom(v["zoom"])
        # --- KAMERA AC/KAPA (her ikisi de bagimsiz) ---
        # DIKKAT: 'was', yeni bayraklar YAZILMADAN once okunmali.
        was = {n: self._camera_enabled(n) for n in (1, 2)}
        want = {1: bool(v.get("camera1_enabled", True)),
                2: bool(v.get("camera2_enabled", False))}
        if not (want[1] or want[2]):        # emniyet: ikisi de kapatilamaz
            want[1] = True
        cams_cfg = self.config.setdefault("cameras", {})
        cams_cfg["camera1_enabled"] = want[1]
        cams_cfg["camera2_enabled"] = want[2]
        cams_cfg.pop("enabled_count", None)   # eski sayi tabanli anahtar artik yaniltici

        c2 = v.get("cam2") or {}
        if c2:
            cam2_cfg = self.config.setdefault("camera2", {})
            res2_cfg = self.config.setdefault("resolution2", {})
            res2_changed = (int(res2_cfg.get("width", 0)), int(res2_cfg.get("height", 0))) != (c2["res_w"], c2["res_h"])
            cam2_restart = (res2_changed
                            or int(cam2_cfg.get("fps", 0)) != c2["fps"]
                            or bool(cam2_cfg.get("manual_exposure_enabled", False)) != c2["manual_exposure"]
                            or int(cam2_cfg.get("exposure_us", 0)) != c2["exposure_us"]
                            or abs(float(cam2_cfg.get("analogue_gain", 0.0)) - c2["analogue_gain"]) > 1e-6)
            zoom2_changed = abs(float(cam2_cfg.get("zoom", 1.0)) - c2["zoom"]) > 1e-6
            res2_cfg["width"], res2_cfg["height"] = c2["res_w"], c2["res_h"]
            cam2_cfg["fps"] = c2["fps"]
            cam2_cfg["manual_exposure_enabled"] = c2["manual_exposure"]
            cam2_cfg["exposure_us"] = c2["exposure_us"]
            cam2_cfg["analogue_gain"] = c2["analogue_gain"]
            cam2_cfg["zoom"] = c2["zoom"]
            cam2_cfg.setdefault("backend", str(camera_cfg.get("backend", "picamera2")))
            cam2_cfg.setdefault("opencv_index", 1)

            if want[2] and self.worker2:
                if cam2_restart:
                    self._append_log("[Ayarlar] Kamera 2 ayarları değişti; kamera yeniden başlatılıyor...")
                    self.worker2.change_camera_controls()
                if zoom2_changed:
                    self.worker2.set_zoom(c2["zoom"])

        # Ac/kapa: yalniz DURUMU DEGISEN kameraya dokunulur (uygulama yeniden baslamaz).
        for n in (1, 2):
            if want[n] and not was[n]:
                self._start_camera(n)
            elif not want[n] and was[n]:
                self._stop_camera(n)
        if self._cam1_row is not None:
            self._cam1_row.setVisible(want[1])
        if self._cam2_row is not None:
            self._cam2_row.setVisible(want[2])

        if res_changed or zoom_changed:
            self._invalidate_snapshot("Kamera ölçeği değişti. ROI ayarı için yeniden tam resim alın.", clear_references=True)
        if plc_changed:
            self._append_log("[Ayarlar] PLC ayarları değişti; bağlantı yenileniyor...")
            self._last_plc_connected = None
            self._restart_plc_adapter()
            self._plc_timer.setInterval(v["plc_poll_ms"])
        self._save_config()
        self._append_log("[Ayarlar] Kaydedildi.")

    def _start_worker(self):
        # Yalnız AÇIK kameralar için worker oluşturulur (kapalı kamera hiç açılmaz).
        for cam_no in self._active_cameras():
            self._start_camera(cam_no)

        self._plc_timer = QTimer(self)
        self._plc_timer.timeout.connect(self._poll_plc)
        self._plc_timer.start(int(self.config.get("plc", {}).get("poll_ms", 50)))

    def _start_camera(self, cam_no: int):
        """Kamerayı başlatır (zaten çalışıyorsa dokunmaz). Her iki kamera da
        bağımsız açılıp kapanabildiği için tek giriş noktası."""
        if cam_no == 2:
            if self.worker2 is not None:
                return
            self.worker2 = InspectionWorker(self.config, cam_index=1)
            worker = self.worker2
            worker.frame_ready.connect(self._update_frame_2)
            worker.fps_updated.connect(self._update_fps_2)
        else:
            if self.worker is not None:
                return
            self.worker = InspectionWorker(self.config, cam_index=0)
            worker = self.worker
            worker.frame_ready.connect(self._update_frame)
            worker.fps_updated.connect(self._update_fps_1)
        worker.state_changed.connect(self._update_state)
        worker.log_message.connect(self._append_log)
        worker.error_occurred.connect(self._handle_error)
        # Netlik "en iyi" degeri sifirlansin: yeni ayar/kamera icin temiz baslangic
        # (aksi halde eski tepe takili kalir ve odak ayari yaniltir).
        self._focus_best.pop(cam_no, None)
        self._focus_values.pop(cam_no, None)
        worker.start()
        self._append_log(f"[Kamera {cam_no}] Kamera açıldı.")

    def _stop_camera(self, cam_no: int):
        """Kamerayı durdurur ve o kameraya ait snapshot'ları temizler."""
        worker = self.worker2 if cam_no == 2 else self.worker
        if worker is None:
            return
        worker.stop()
        worker.wait(3000)
        if cam_no == 2:
            self.worker2 = None
            self._last_snapshot_2 = None
            self._last_full_snapshot_2 = None
        else:
            self.worker = None
            self._last_snapshot = None
            self._last_full_snapshot = None
        self._append_log(f"[Kamera {cam_no}] Kamera kapatıldı.")

    def _update_focus_metric(self, cam_no, frame):
        """Canlı NETLİK (odak) göstergesi — lens odak halkasını ayarlamak için.

        Kareden merkezdeki sabit pencereyi NATIVE piksellerde alıp Laplacian
        varyansı hesaplar (yüksek = keskin). Saniyede ~4 kez çalışır (ucuz).
        Odak halkası çevrilirken sayının TEPE yaptığı yer en iyi odaktır.
        NOT: metrik gürültüyü de sayar; bu yüzden yalnız ışık/exposure sabitken
        ve AYNI kamerada kıyaslanır (mutlak bir 'iyi' değeri yoktur)."""
        now = time.time()
        if now - self._focus_last.get(cam_no, 0.0) < 0.25:
            return
        self._focus_last[cam_no] = now
        h, w = frame.shape[:2]
        cw, ch = min(w, 480), min(h, 360)
        x1, y1 = (w - cw) // 2, (h - ch) // 2
        win = frame[y1:y1 + ch, x1:x1 + cw]
        if win.size == 0:
            return
        gray = cv2.cvtColor(win, cv2.COLOR_BGR2GRAY) if win.ndim == 3 else win
        val = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        self._focus_values[cam_no] = val
        self._focus_best[cam_no] = max(self._focus_best.get(cam_no, 0.0), val)
        parts, worst_pct = [], 100.0
        for n in self._active_cameras():
            if n not in self._focus_values:
                continue
            cur, best = self._focus_values[n], self._focus_best[n]
            pct = (100.0 * cur / best) if best > 0 else 100.0
            worst_pct = min(worst_pct, pct)
            parts.append(f"K{n} {cur:.0f} / en iyi {best:.0f} (%{pct:.0f})")
        if not parts:
            return
        self.lbl_focus.setText("  |  ".join(parts))
        # Renk: odak halkasini cevirirken ekrana bakmadan da anlasilsin.
        # >=%90 yesil (tepedesin), >=%50 sari (yaklastin), altisi kirmizi (odak kacik).
        color = "#62b87d" if worst_pct >= 90 else ("#d8a657" if worst_pct >= 50 else "#d96b6b")
        self.lbl_focus.setStyleSheet(f"color: {color};")
        self._update_exposure_label()

    def _camera_exposure_locked(self, cam_no: int) -> bool:
        """O kameranin poz/gain KILIDI (manual_exposure_enabled) acik mi?"""
        cfg = self.config.get("camera" if cam_no == 1 else f"camera{cam_no}", {}) or {}
        if cam_no != 1 and "manual_exposure_enabled" not in cfg:
            cfg = self.config.get("camera", {}) or {}     # kamera 2 devralir (worker gibi)
        return bool(cfg.get("manual_exposure_enabled", False))

    def _update_exposure_label(self):
        """Kameranın fiilen kullandığı poz süresini gösterir (hareket bulanıklığı ölçütü).

        KILIT DURUMU DA YAZILIR: 'OTO' iken config'teki exposure_us/analogue_gain
        UYGULANMAZ (worker._camera_controls bos doner) ve oto-pozlama parlaklik icin
        pozu uzatir -> hareket bulanikligi. Bu tuzak sahada bir kez yasandi (kullanici
        200 us yazmisti ama kutu kapali oldugu icin kamera 19 ms kullaniyordu), bu
        yuzden durum artik tek bakista gorunuyor."""
        parts, worst_us, any_auto = [], 0, False
        for n in self._active_cameras():
            worker = self.worker2 if n == 2 else self.worker
            us = int(getattr(worker, "last_exposure_us", 0) or 0) if worker else 0
            if not us:
                continue
            gain = float(getattr(worker, "last_gain", 0.0) or 0.0)
            locked = self._camera_exposure_locked(n)
            any_auto = any_auto or not locked
            worst_us = max(worst_us, us)
            parts.append(f"K{n} {us / 1000.0:.1f} ms (gain {gain:.1f}) "
                         f"{'🔒' if locked else '⚠ OTO'}")
        if not parts:
            return
        self.lbl_exposure.setText("  |  ".join(parts))
        # Bant hareketliyken: <=1ms iyi, 1-3ms sinirda, >3ms hareket bulanikligi kesin.
        # Kilit kapaliysa deger ne olursa olsun UYARI rengi: oto-pozlama her an uzatabilir.
        if any_auto:
            color = "#d8a657"
        else:
            color = "#62b87d" if worst_us <= 1000 else ("#d8a657" if worst_us <= 3000 else "#d96b6b")
        self.lbl_exposure.setStyleSheet(f"color: {color};")

    def _render_frame(self, cv_img, label, cam_no=1):
        self._update_focus_metric(cam_no, cv_img)
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img).scaled(
            label.width(), label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(pixmap)

    @pyqtSlot(np.ndarray)
    def _update_frame(self, cv_img):
        self._render_frame(cv_img, self.video_label, 1)

    @pyqtSlot(np.ndarray)
    def _update_frame_2(self, cv_img):
        label = getattr(self, "video_label_2", None)
        if label is not None:
            self._render_frame(cv_img, label, 2)

    @pyqtSlot(str)
    def _update_state(self, state_name):
        self.lbl_state.setText(state_name)
        if "CANLI" in state_name:
            c = "#62b87d"
        else:
            c = "#9aa0ab"  # Gri-Mavi
        self.lbl_state.setStyleSheet(f"color: {c};")

    def _cam_prefix(self, cam_no: int) -> str:
        """Yalnız kamera 1 açıkken boş; aksi halde 'Kamera N: ' (log/mesajlar ayrışsın)."""
        return f"Kamera {cam_no}: " if self._active_cameras() != [1] else ""

    def _handle_snapshot(self, part_id, crop_img, cam_no: int = 1):
        if crop_img.size == 0:
            return False
        # Kamera 2 icin config GORUNUMU: analiz motoru degismeden kendi ROI/esikleriyle calisir.
        cfg_view = self._camera_config_view(cam_no)
        if cam_no == 2:
            self._last_full_snapshot_2 = crop_img.copy()
        else:
            self._last_full_snapshot = crop_img.copy()

        from inspector.features import evaluate_with_profile, has_reference_profile
        roi_method = str(cfg_view.get("roi", {}).get("decision_method", "hole")).lower()
        if roi_method == "template" and not has_reference_profile(cfg_view):
            self._append_log("[Uyarı] OK referans yok; template yöntemi analizde NOK dönecek "
                             "(aktif kullanım için roi.decision_method: hole önerilir).")
        analysis_img, product_box = self._prepare_roi_analysis_frame(crop_img, cam_no)
        if cam_no == 2:
            self._last_snapshot_2 = analysis_img.copy()
        else:
            self._last_snapshot = analysis_img.copy()
        is_ok, results, display_img = evaluate_with_profile(analysis_img, cfg_view)

        self._display_snapshot(display_img, cam_no)
        self._update_live_errors(is_ok, results, cam_no)

        # Log yazdırma. part_id == 0 -> "Kontrol Noktaları" kaydedilince calisan
        # ONIZLEME analizi. Eskiden onizleme HIC loglanmiyordu: ekranda "3: NOK
        # (oluk YOK)" yaziyordu ama olculen koyu%/blob degerleri hicbir yerde
        # gorunmuyordu -> esik ayarlamak icin illa urun gecirmek gerekiyordu.
        # Artik onizleme de loglaniyor (ayri etiketle), boylece kaydet-bak-ayarla
        # dongusu urun gecirmeden yapilabiliyor.
        if True:
            status_str = "OK" if is_ok else "NOK"
            cam_tag = f" [Kamera {cam_no}]" if self._active_cameras() != [1] else ""
            log_msg = (f"[Analiz]{cam_tag} Resim #{part_id:04d} -> {status_str}"
                       if part_id > 0 else
                       f"[Önizleme]{cam_tag} son kare -> {status_str} (PLC'ye YAZILMAZ)")
            if product_box:
                log_msg += f"\n   - ürün çerçevesi: x={product_box[0]}, y={product_box[1]}, w={product_box[2]}, h={product_box[3]}"
            from inspector.features import format_limits, format_metrics
            for name, res in results.items():
                r_stat = "OK" if res["ok"] else "NOK"
                log_msg += f"\n   - {name}: {r_stat} ({res['msg']})"
                log_msg += f"\n     ölçüm: {format_metrics(res.get('metrics', {}))}"
                log_msg += f"\n     OK bant: {format_limits(res.get('limits', {}))}"
            self._append_log(log_msg)
        return bool(is_ok)

    def _point_thresholds(self, cam_no: int, name: str, roi_type: str):
        """Bir noktanin YURURLUKTEKI esikleri (delikte İKİ tane: açıklık + derinlik).
        Oncelik analiz motoruyla AYNI: once nokta override'i, yoksa global deger.
        Döner: [(config_anahtari, başlık, ölçüm_anahtarı, değer), ...] — 'yon' için boş."""
        tanim = ROIResultPanel.THRESHOLDS.get(roi_type) or []
        roi_cfg = self._camera_config_view(cam_no).get("roi", {}) or {}
        ov = (roi_cfg.get("point_overrides", {}) or {}).get(name, {}) or {}
        sonuc = []
        for key, baslik, olcum, varsayilan in tanim:
            deger = ov.get(key, roi_cfg.get(key, varsayilan))
            sonuc.append((key, baslik, olcum, float(deger)))
        return sonuc

    def _update_live_errors(self, is_ok, results, cam_no: int = 1):
        """Canli goruntunun ustundeki sonuc panelini gunceller: her kontrol
        noktasi icin ad + OK/NOK rozeti + olculen deger + esik slider'i."""
        panel = self._cam_widgets(cam_no)["errors"]
        if panel is None:
            return
        from inspector.features import roi_point_type
        roi_types = (self._camera_config_view(cam_no).get("roi", {}) or {}).get("roi_types", {}) or {}
        tipler, esikler = {}, {}
        for name in results:
            if name == "YON":                # yon sonucu bir ROI degil, esigi yok
                tipler[name] = "yon"
                continue
            tip = roi_point_type(name, roi_types)
            tipler[name] = tip
            thr = self._point_thresholds(cam_no, name, tip)
            if thr:
                esikler[name] = thr
        panel.update_results(is_ok, results, esikler, tipler)
        panel.setVisible(True)

    def _on_panel_threshold_changed(self, cam_no: int, name: str, key: str, value: float):
        """Sonuc panelindeki slider birakildi -> nokta basina esigi yaz, kaydet ve
        SON KAREYI YENIDEN degerlendir (aninda sonuc gorunsun).

        PLC'ye yazilmaz: bu bir onizlemedir (_handle_snapshot part_id=0)."""
        roi_key = "roi2" if cam_no == 2 else "roi"
        roi_cfg = self.config.setdefault(roi_key, {})
        overrides = roi_cfg.setdefault("point_overrides", {})
        overrides.setdefault(str(name), {})[key] = float(value)
        self._save_config()
        self._append_log(f"[Eşik] {self._cam_prefix(cam_no)}{name} → {key} = %{value:.0f} "
                         "(panelden ayarlandı)")
        full = self._last_full_snapshot_2 if cam_no == 2 else self._last_full_snapshot
        if full is not None:
            try:
                self._handle_snapshot(0, full, cam_no)      # onizleme: PLC'ye yazmaz
            except Exception as exc:
                self._append_log(f"[Uyarı] Önizleme yenilenemedi: {exc}")

    def _alignment_enabled(self, cam_no: int = 1):
        cfg_view = self._camera_config_view(cam_no)
        return str(cfg_view.get("alignment", {}).get("mode", "contour")).lower() == "contour"

    def _prepare_roi_analysis_frame(self, frame, cam_no: int = 1):
        if not self._alignment_enabled(cam_no):
            return frame.copy(), None

        from inspector.alignment import crop_box, find_product_box
        cfg_view = self._camera_config_view(cam_no)
        product_box = find_product_box(frame, cfg_view)
        if product_box is None:
            raise ValueError(f"{self._cam_prefix(cam_no)}Ürün konturu bulunamadı. "
                             "Işık/arka plan veya alignment min_area_ratio ayarını kontrol edin.")

        product_frame = crop_box(frame, product_box)
        if product_frame is None or product_frame.size == 0:
            raise ValueError(f"{self._cam_prefix(cam_no)}Ürün çerçevesi kırpılamadı.")

        if cam_no == 2:
            self._last_product_box_2 = product_box
        else:
            self._last_product_box = product_box
        return product_frame, product_box

    def _capture_product_box_for_roi(self, cam_no: int = 1):
        frame = self._get_latest_camera_frame(cam_no)
        if frame is None:
            QMessageBox.warning(self, "Uyarı", f"{self._cam_prefix(cam_no)}Henüz kamera görüntüsü alınmadı.")
            return

        try:
            product_frame, product_box = self._prepare_roi_analysis_frame(frame, cam_no)
        except ValueError as exc:
            QMessageBox.warning(self, "Ürün Bulunamadı", str(exc))
            self._append_log(f"[Ürün Bulma HATA] {exc}")
            return

        if cam_no == 2:
            self._last_full_snapshot_2 = frame.copy()
            self._last_snapshot_2 = product_frame.copy()
        else:
            self._last_full_snapshot = frame.copy()
            self._last_snapshot = product_frame.copy()
        preview = product_frame.copy()
        cv2.rectangle(preview, (0, 0), (preview.shape[1] - 1, preview.shape[0] - 1), (0, 255, 255), 3)
        # product_box None ise hizalama kapali (alignment.mode != contour): tam kare kullaniliyor.
        if product_box:
            label = "URUN CERCEVESI - ROI BURADA CIZILECEK"
        else:
            label = "TAM KARE (hizalama kapali) - ROI BURADA CIZILECEK"
        cv2.putText(preview, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
        self._display_snapshot(preview, cam_no)
        if product_box:
            self._append_log(
                f"[Ürün Bulma] {self._cam_prefix(cam_no)}Çerçeve bulundu: x={product_box[0]}, y={product_box[1]}, "
                f"w={product_box[2]}, h={product_box[3]}. ROI'leri bu çerçevenin içinde çizin."
            )
        else:
            self._append_log(
                f"[Ürün Bulma] {self._cam_prefix(cam_no)}Hizalama kapalı (alignment.mode != contour). "
                "Tam kare alındı; ROI'leri doğrudan tam kare üzerinde çizin."
            )

    def _display_snapshot(self, display_img, cam_no: int = 1):
        rgb_image = cv2.cvtColor(display_img, cv2.COLOR_BGR2RGB)
        h_i, w_i, ch = rgb_image.shape
        bytes_per_line = ch * w_i
        q_img = QImage(rgb_image.data, w_i, h_i, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        # zoom için tam çözünürlüğü sakla (kamera başına ayrı)
        if cam_no == 2:
            self._snapshot_full_pixmap_2 = pixmap
        else:
            self._snapshot_full_pixmap = pixmap
        self._rescale_snapshot(cam_no)

    def _rescale_snapshot(self, cam_no=None):
        """Snapshot'i lbl_snapshot'in GUNCEL boyutuna gore yeniden olcekler (canli
        goruntu gibi paneli doldursun; pencere buyuyunce kucuk kalmasin).
        cam_no verilmezse (resizeEvent) etkin tum kameralar icin calisir."""
        for n in ([cam_no] if cam_no else self._active_cameras()):
            pixmap = self._snapshot_full_pixmap_2 if n == 2 else self._snapshot_full_pixmap
            label = self._cam_widgets(n)["snapshot"]
            if pixmap is None or pixmap.isNull() or label is None:
                continue
            label.setPixmap(pixmap.scaled(
                max(1, label.width()),
                max(1, label.height()),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Pencere boyutu degisince snapshot'i da yeniden olcekle (layout otursun diye gecikmeli).
        QTimer.singleShot(0, self._rescale_snapshot)

    def _open_snapshot_zoom(self, event=None, cam_no: int = 1):
        """Son alınan tam resmi tam çözünürlükte, kaydırılabilir bir pencerede açar."""
        pixmap = self._snapshot_full_pixmap_2 if cam_no == 2 else self._snapshot_full_pixmap
        if pixmap is None or pixmap.isNull():
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Son Alınan Tam Resim{'  (Kamera 2)' if cam_no == 2 else ''} — Yakınlaştırılmış")
        dlg.resize(1000, 760)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(6, 6, 6, 6)
        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(False)
        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignCenter)
        scroll.setWidget(img_label)
        layout.addWidget(scroll)
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)
        dlg.exec_()

    def _store_setup_snapshot(self, frame, cam_no: int = 1) -> bool:
        """Analiz YAPMADAN, tetikle gelen GERÇEK kareyi kontrol noktası editörüne hazırlar.

        NEDEN (2026-08-03, saha sorunu): Kontrol noktaları ELLE ayarlanırken ürün
        durgun duruyor, operatörün ELİ karede oluyor ve (tetiklemeli aydınlatmada)
        ışık koşulu farklı. Otomatikte ise ürün tetikten çekime kadar YOL ALIYOR ->
        kalibrasyon karesi ile üretim karesi ÖRTÜŞMÜYOR. Doğru çözüm: ayarı GERÇEK
        üretim karesi üzerinden yapmak. Ama `_production_ready_error` (nokta yok)
        eskiden kare ALINMADAN dönüyordu -> "noktaları sil, otomatikte çalıştır,
        gerçek kareyi yakala" akışı İMKANSIZDI. Artık kare saklanır, PLC'ye yine
        ERROR yazılır (üretim güvenliği bozulmaz), analiz yapılmaz.

        Döner: kare saklandıysa True.
        """
        if frame is None or getattr(frame, "size", 0) == 0:
            return False
        if cam_no == 2:
            self._last_full_snapshot_2 = frame.copy()
        else:
            self._last_full_snapshot = frame.copy()
        try:
            analysis_img, box = self._prepare_roi_analysis_frame(frame, cam_no)
        except ValueError as exc:
            # Urun cercevesi bulunamadi: kare yine de tam haliyle duruyor ama
            # editor hizalanmis kareyi bekler -> kullaniciya sebebini soyle.
            self._append_log(f"[Uyarı] {exc}")
            return False
        if box:
            # URUN CERCEVESI KARARLILIGI: kontrol noktalari bu kutuya GORELI saklanir
            # ve kutu boyutuyla OLCEKLENIR (_roi_bounds sx/sy). Kutu tetikten tetige
            # oynarsa TUM noktalar birlikte kayar/buyur -> yanlis NOK. Nokta cizilmemis
            # kurulum turunda da kutuyu loga yaz ki yayilim OLCULEBILSIN.
            ref = (self._camera_config_view(cam_no).get("roi", {}) or {}).get("reference_box")
            sapma = ""
            if ref and len(ref) == 2 and int(ref[0]) > 0 and int(ref[1]) > 0:
                dx = (box[2] / float(ref[0]) - 1.0) * 100.0
                dy = (box[3] / float(ref[1]) - 1.0) * 100.0
                sapma = (f"  | referansa gore  en %{dx:+.1f}  boy %{dy:+.1f}"
                         f"  (referans {int(ref[0])}x{int(ref[1])})")
            self._append_log(
                f"[Kurulum] {self._cam_prefix(cam_no)}ürün çerçevesi: "
                f"x={box[0]}, y={box[1]}, w={box[2]}, h={box[3]}{sapma}")
        if cam_no == 2:
            self._last_snapshot_2 = analysis_img.copy()
        else:
            self._last_snapshot = analysis_img.copy()
        self._display_snapshot(analysis_img, cam_no)
        return True

    def _capture_full_frame(self):
        if self._inspection_state == InspectionState.BUSY:
            return
        # TEK tetik -> etkin TUM kameralardan ayni anda kare al (§13).
        # SIRA ONEMLI: kare ONCE alinir, uretim-hazir kontrolu SONRA yapilir.
        # Boylece nokta cizilmemisken de tetikle gelen GERCEK kare saklanir ve
        # kontrol noktalari o kare uzerinden ayarlanabilir (bkz. _store_setup_snapshot).
        cams = self._active_cameras()
        frames = {}
        for n in cams:
            frame = self._get_latest_camera_frame(n)
            if frame is None:
                self._append_log(f"[HATA] {self._cam_prefix(n)}Kamera görüntüsü yok veya görüntü bayat.")
                if self._manual_mode_on():
                    QMessageBox.warning(self, "Uyarı",
                                        f"{self._cam_prefix(n)}Henüz kamera görüntüsü alınmadı! "
                                        "Lütfen canlı görüntünün başlamasını bekleyin.")
                self._publish_plc_error(f"{self._cam_prefix(n)}Kamera görüntüsü yok")
                self._set_inspection_state(InspectionState.ERROR)
                return
            frames[n] = frame

        ready_error = self._production_ready_error()
        if ready_error:
            self._append_log(f"[HATA] Üretim hazır değil: {ready_error}")
            stored = [n for n in cams if self._store_setup_snapshot(frames[n], n)]
            if stored:
                self._append_log(
                    "[Kurulum] Tetikle gelen GERÇEK üretim karesi saklandı (kamera "
                    + ", ".join(str(n) for n in stored)
                    + "). 'Kontrol Noktaları' butonuyla ayarı BU kare üzerinden yapın "
                    "— elle konumlandırılmış kareyle üretim karesi örtüşmez.")
            self._publish_plc_error(ready_error)
            self._set_inspection_state(InspectionState.ERROR)
            return
        try:
            self._set_inspection_state(InspectionState.BUSY)
            self._capture_counter += 1
            cam_info = f" ({len(cams)} kamera)" if len(cams) > 1 else ""
            self._append_log(f"[Tetik] Tam resim alındı{cam_info}. Analiz başlatılıyor. Resim #{self._capture_counter:04d}")
            # IKI YUZ DENETIMI: her kamera KENDI ROI/esikleriyle analiz edilir, kararlar
            # VE'lenir (ikisi de OK ise parca OK) ve PLC'ye TEK sonuc yazilir.
            # Kisa-devre YOK: operator her iki yuzun sonucunu da gorsun diye hepsi analiz edilir.
            is_ok = True
            for n in cams:
                is_ok = self._handle_snapshot(self._capture_counter, frames[n], n) and is_ok
            if len(cams) > 1:
                self._append_log(f"[Sonuç] Birleşik karar (tüm kameralar OK olmalı): "
                                 f"{'OK' if is_ok else 'NOK'}")
            # Elle Cekim Modunda plc NullPLCAdapter'dir: publish her zaman True doner,
            # yani asagidaki dallanma hem sahada hem ev/test modunda dogru calisir.
            if self._publish_plc_result(is_ok):
                self._set_inspection_state(InspectionState.OK if is_ok else InspectionState.NOK)
            else:
                # PLC yazimi basarisiz: HMI'da yanlis OK/NOK gosterme, ERROR'a gec.
                # Baglanti geri gelince _update_plc_connection_status ERROR->READY toparlar.
                self._append_log("[HATA] PLC sonucu yazılamadı; durum ERROR.")
                self._set_inspection_state(InspectionState.ERROR)
        except Exception as exc:
            self._append_log(f"[HATA] Analiz başarısız: {exc}")
            self._publish_plc_error(str(exc))
            self._set_inspection_state(InspectionState.ERROR)

    def _publish_plc_result(self, is_ok: bool):
        written = bool(self.plc.publish_result(is_ok))
        if written and not is_ok:
            QTimer.singleShot(1000, self._reset_plc_nok)
        elif written and is_ok:
            QTimer.singleShot(1000, self._set_ready_after_result)
        return written

    def _publish_plc_error(self, message: str):
        written = bool(self.plc.publish_error(message))
        if written:
            QTimer.singleShot(1000, self._reset_plc_nok)
        return written

    def _reset_plc_nok(self):
        reset = getattr(self.plc, "reset_nok", None)
        if reset is None:
            return
        if reset():
            self._nok_reset_pending = False
            self._append_plc_debug_events()
            self._set_ready_after_result()
        else:
            # Reset basarisiz (baglanti kopuk olabilir): HR100 NOK'ta takili
            # kalmasin diye bayrak kalir; _poll_plc baglanti gelince tekrar dener.
            self._nok_reset_pending = True
            self._append_plc_debug_events()

    def _set_ready_after_result(self):
        # ERROR'u da haric tut: gercek bir sistem hatasi (kamera yok / uretim hazir
        # degil / PLC yazim hatasi) operatore gorunur kalsin; READY'ye ancak yeni bir
        # tetik ya da PLC yeniden baglanmasi (_update_plc_connection_status) ile donsun.
        if self._inspection_state in (InspectionState.BUSY, InspectionState.ERROR):
            return
        if not self.plc.is_connected():
            return
        self._set_inspection_state(InspectionState.READY)

    def _set_inspection_state(self, state: InspectionState):
        self._inspection_state = state
        self.plc.set_state(state)
        self.lbl_plc.setText(state.value)
        colors = {
            InspectionState.READY: "#62b87d",
            InspectionState.BUSY: "#d8a657",
            InspectionState.OK: "#62b87d",
            InspectionState.NOK: "#d96b6b",
            InspectionState.ERROR: "#d96b6b",
        }
        self.lbl_plc.setStyleSheet(f"color: {colors.get(state, '#9aa0ab')};")

    def _poll_plc(self):
        # Ayarlar/Kontrol Noktalari penceresi acikken tetik isleme: duzenleme
        # ortasinda cekim baslamasin (eski kalibrasyon modu davranisi).
        if self._dialog_paused:
            return
        command = self.plc.poll()
        self._append_plc_debug_events()
        self._update_plc_connection_status()
        # Onceki NOK/hata reseti baglanti kopuklugu yuzunden basarisiz olduysa,
        # baglanti geri geldiginde HR100=0'i tekrar dene (takili NOK'u temizle).
        if self._nok_reset_pending and self.plc.is_connected():
            self._reset_plc_nok()
        if command == "capture":
            self._capture_from_plc()

    def _append_plc_debug_events(self):
        drain = getattr(self.plc, "drain_debug_events", None)
        if not drain:
            return
        for event in drain():
            self._append_log(f"[PLC DEBUG] {event}")

    def _capture_from_plc(self):
        if self._capture_pending or self._inspection_state == InspectionState.BUSY:
            return
        delay_ms = int(self.config.get("inspection", {}).get("trigger_delay_ms", 0))
        if delay_ms <= 0:
            self._capture_full_frame()
            return
        self._capture_pending = True
        self._append_log(f"[Tetik] PLC trigger alındı. Çekim {delay_ms} ms geciktirildi.")
        QTimer.singleShot(delay_ms, self._delayed_capture)

    def _delayed_capture(self):
        self._capture_pending = False
        if self._dialog_paused:
            return
        self._capture_full_frame()

    def _update_plc_connection_status(self):
        connected = bool(self.plc.is_connected())
        if connected == self._last_plc_connected:
            return
        self._last_plc_connected = connected
        if connected:
            self._append_log(f"[PLC] {self.plc.status_text()}")
            if self._inspection_state == InspectionState.ERROR:
                self._set_inspection_state(InspectionState.READY)
        else:
            self._append_log(f"[PLC HATA] {self.plc.status_text()}")
            self.lbl_plc.setText("PLC YOK")
            self.lbl_plc.setStyleSheet("color: #d96b6b;")

    def _production_ready_error(self):
        # 'yon' tipi noktalar kusur kontrolu degil (yalniz yon tayini olcumu);
        # uretim hazirligi icin en az bir delik/centik noktasi gerekir.
        # Iki kamera etkinse HER IKISINDE de nokta tanimli olmali (biri bossa
        # o yuz denetlenmemis olur -> uretime hazir degil).
        from inspector.features import roi_point_type
        for n in self._active_cameras():
            cfg_view = self._camera_config_view(n)
            roi_types = cfg_view.get("roi", {}).get("roi_types", {}) or {}
            active_rois = [
                name for name in cfg_view.get("dynamic_rois", {})
                if name not in set(cfg_view.get("disabled_rois", []))
                and roi_point_type(name, roi_types) != "yon"
            ]
            if not active_rois:
                return f"{self._cam_prefix(n)}Aktif kontrol noktası yok (en az 1 delik/çentik çizin)"
            # 'hole' yöntemi referans/öğrenme gerektirmez; yalnız 'template' için ara.
            roi_method = str(cfg_view.get("roi", {}).get("decision_method", "hole")).lower()
            if roi_method == "template":
                profile_rois = cfg_view.get("reference_profile", {}).get("rois", {})
                missing_refs = [
                    name for name in active_rois
                    if not profile_rois.get(name, {}).get("references")
                ]
                if missing_refs:
                    return f"{self._cam_prefix(n)}Referans yok: {', '.join(map(str, missing_refs))}"
        if not self.plc.is_connected():
            return self.plc.status_text()
        return None

    def _update_fps_for(self, cam_no, fps):
        # Tek FPS etiketi var: ilk AÇIK kameranın değerini gösterir.
        active = self._active_cameras()
        if active and active[0] == cam_no:
            self.lbl_fps.setText(f"{fps:.1f}")

    @pyqtSlot(float)
    def _update_fps_1(self, fps):
        self._update_fps_for(1, fps)

    @pyqtSlot(float)
    def _update_fps_2(self, fps):
        self._update_fps_for(2, fps)

    # Saha teshisi icin loglar DISKE de yazilir: ekrandaki kutu uygulama kapaninca
    # kaybolur ve 15 tetiklik bir olcumu elle kopyalamak hem zahmetli hem hataya acik.
    # Gunluk dosya: ~/konveyor_loglari/denetim-YYYY-AA-GG.log (proje disi -> repoya
    # sizmaz). SD asinmasi ihmal edilebilir: satir ~100 bayt, oysa config.yaml her UI
    # etkilesiminde ~148 KB yeniden yaziliyor (§9).
    LOG_DIR = os.path.join(os.path.expanduser("~"), "konveyor_loglari")

    def _log_file_path(self):
        return os.path.join(self.LOG_DIR, f"denetim-{time.strftime('%Y-%m-%d')}.log")

    @pyqtSlot(str)
    def _append_log(self, msg):
        self.txt_logs.append(msg)
        scrollbar = self.txt_logs.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # Diske yazma ASLA arayuzu bozmasin: her hata sessizce yutulur.
        if getattr(self, "_log_file_broken", False):
            return
        try:
            os.makedirs(self.LOG_DIR, exist_ok=True)
            stamp = time.strftime("%H:%M:%S")
            with open(self._log_file_path(), "a", encoding="utf-8") as f:
                for i, line in enumerate(str(msg).splitlines() or [""]):
                    f.write(f"{stamp} {line}\n" if i == 0 else f"         {line}\n")
        except Exception:
            self._log_file_broken = True      # bir kez dene, tutmuyorsa vazgec

    @pyqtSlot(str)
    def _handle_error(self, err_msg):
        self._append_log(f"[HATA] {err_msg}")
        if self._manual_mode_on():
            # Ev/test: operatore gorunur uyari yeter (Null PLC zaten yazmaz).
            QMessageBox.critical(self, "Kamera / Sistem Hatası", err_msg)
            return
        self._publish_plc_error(err_msg)
        self._set_inspection_state(InspectionState.ERROR)

    def _invalidate_snapshot(self, reason, clear_references=False):
        self._last_snapshot = None
        self._last_snapshot_2 = None
        for n in self._active_cameras():
            label = self._cam_widgets(n)["snapshot"]
            if label is not None:
                label.setText(reason)
        if clear_references and self.config.get("reference_profile", {}).get("count", 0):
            self.config["reference_profile"] = {"count": 0, "rois": {}}
            self._save_config()
            self._append_log("[Referans] Kamera ölçeği değiştiği için OK referansları sıfırlandı.")

    def _open_roi_manager(self, cam_no: int = 1):
        """Kontrol noktası editörü. Her kamera KENDİ noktalarını düzenler:
        kamera 1 -> dynamic_rois/roi, kamera 2 -> dynamic_rois_2/roi2."""
        two = (cam_no == 2)
        snapshot = self._last_snapshot_2 if two else self._last_snapshot
        if snapshot is None:
            QMessageBox.warning(self, "Uyarı",
                                f"{self._cam_prefix(cam_no)}Henüz ürün çerçevesi alınmadı! "
                                "Önce 'Ürün Çerçevesi Bul' butonunu kullanın.")
            return

        rois_key = "dynamic_rois_2" if two else "dynamic_rois"
        disabled_key = "disabled_rois_2" if two else "disabled_rois"
        roi_key = "roi2" if two else "roi"

        from inspector.roi_editor import ROIDialog
        roi_cfg_now = self.config.get(roi_key, {}) or {}
        # Kamera 2'nin esik on-dolumu: roi2 yazdiysa o, yoksa kamera 1'in degeri.
        defaults_src = {**(self.config.get("roi", {}) or {}), **roi_cfg_now} if two else roi_cfg_now
        dlg = ROIDialog(
            snapshot,
            self.rois_2 if two else self.rois,
            self,
            title=f"Kontrol Noktaları{' — KAMERA 2' if two else ''} (ürün çerçevesi içinde)",
            list_label="Tanımlı kontrol noktaları (delik / çentik):",
            roi_types=roi_cfg_now.get("roi_types", {}),
            disabled_rois=self.disabled_rois_2 if two else self.disabled_rois,
            point_overrides=roi_cfg_now.get("point_overrides", {}),
            roi_defaults={
                "hole_dark_ratio_min": float(defaults_src.get("hole_dark_ratio_min", 20.0)),
                "hole_core_ratio_min": float(defaults_src.get("hole_core_ratio_min", 2.0)),
                "notch_dark_min": float(defaults_src.get("notch_dark_min", 50.0)),
            },
        )
        # Editordeyken PLC tetigi cekim baslatmasin (duzenleme ortasinda analiz olmaz).
        self._dialog_paused = True
        try:
            accepted = dlg.exec_() == QDialog.Accepted
        finally:
            self._dialog_paused = False
        if accepted:
            rois = dlg.rois
            disabled = set(dlg.disabled_rois)
            if two:
                self.rois_2, self.disabled_rois_2 = rois, disabled
            else:
                self.rois, self.disabled_rois = rois, disabled
            self.config[rois_key] = rois
            self.config[disabled_key] = sorted(disabled)
            roi_cfg = self.config.setdefault(roi_key, {})
            # Her ROI'nin tipi (delik=yuvarlaklik kontrolu, centik=var/yok).
            roi_cfg["roi_types"] = {n: t for n, t in dlg.roi_types.items() if n in rois}
            # Nokta basina esik ayarlari (sag tik -> Ayarlar); silinen noktalarinki duser.
            roi_cfg["point_overrides"] = {n: v for n, v in dlg.point_overrides.items() if n in rois and v}
            # Editordeki "Referansi Sifirla" istegi: ogretilmis OK referanslarini temizle.
            if dlg.reset_reference_requested:
                self.config["reference_profile"] = {"count": 0, "rois": {}}
                self._append_log("[Referans] OK referans profili sıfırlandı (Kontrol Noktaları).")
            # ROI'ler bu urun kutusu boyutunda cizildi; analizde kutu boyutu
            # degisirse (Otsu/isik) ROI'leri orantili olceklemek icin sakla.
            roi_cfg["reference_box"] = [int(snapshot.shape[1]), int(snapshot.shape[0])]
            # Editorde "Yon Referansi Al" kullanildiysa referansi kaydet: ters/ayna
            # parcalar bundan sonra otomatik NOK verir.
            if dlg.handedness_ref_diff is not None:
                from inspector.features import HANDEDNESS_VERSION
                roi_cfg["handedness_hole_diff"] = float(dlg.handedness_ref_diff)
                roi_cfg["handedness_check"] = True
                roi_cfg["handedness_version"] = HANDEDNESS_VERSION
                roi_cfg.setdefault("handedness_margin_diff", 12.0)
                self._append_log(
                    f"[Yön] {self._cam_prefix(cam_no)}Doğru parça yön referansı kaydedildi (sağ−sol fark "
                    f"{dlg.handedness_ref_diff:+.0f}). Ters/ayna parçalar otomatik NOK verecek.")
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, default_flow_style=False)
            active_count = len(rois) - len(disabled)
            self._append_log(f"[Kontrol Noktaları] {self._cam_prefix(cam_no)}"
                             f"{active_count}/{len(rois)} aktif nokta kaydedildi.")
            full = self._last_full_snapshot_2 if two else self._last_full_snapshot
            preview_frame = full if full is not None else snapshot
            self._handle_snapshot(0, preview_frame, cam_no)

    def _get_latest_camera_frame(self, cam_no: int = 1):
        worker = self.worker2 if cam_no == 2 else self.worker
        if worker and getattr(worker, "last_raw_frame", None) is not None:
            cfg_view = self._camera_config_view(cam_no)
            max_age_ms = int(cfg_view.get("camera", {}).get("max_frame_age_ms", 1000))
            last_time = float(getattr(worker, "last_frame_time", 0.0) or 0.0)
            if last_time and (time.time() - last_time) * 1000.0 > max_age_ms:
                return None
            return worker.last_raw_frame.copy()
        return None

    def _save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, default_flow_style=False)

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        if self.worker2:
            self.worker2.stop()
            self.worker2.wait()
        if self.plc:
            self.plc.close()
        event.accept()

def apply_dark_palette(app):
    """Stylesheet'in dokunmadigi varsayilan-arka planli widget'lari (panel
    container'lari, scroll viewport) koyuya cevirir; aksi halde Windows varsayilani
    acik renk groupbox margin'lerinde 'beyaz bant' olarak sizar."""
    pal = QPalette()
    bg = QColor("#15171c")
    base = QColor("#1e222a")
    alt = QColor("#1b1e25")
    text = QColor("#d6dae2")
    disabled = QColor("#5a606b")
    pal.setColor(QPalette.Window, bg)
    pal.setColor(QPalette.WindowText, text)
    pal.setColor(QPalette.Base, base)
    pal.setColor(QPalette.AlternateBase, alt)
    pal.setColor(QPalette.Text, text)
    pal.setColor(QPalette.Button, QColor("#272c36"))
    pal.setColor(QPalette.ButtonText, text)
    pal.setColor(QPalette.ToolTipBase, alt)
    pal.setColor(QPalette.ToolTipText, text)
    pal.setColor(QPalette.Highlight, QColor("#345e8c"))
    pal.setColor(QPalette.HighlightedText, QColor("#f2f6fb"))
    pal.setColor(QPalette.Disabled, QPalette.Text, disabled)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, disabled)
    pal.setColor(QPalette.Disabled, QPalette.WindowText, disabled)
    app.setPalette(pal)


def _install_global_excepthook():
    """Slot/callback icindeki yakalanmamis hatalar uygulamayi (ozellikle konsolsuz
    pythonw'da) SESSIZCE kapatmasin: mesaj goster, mumkunse acik kal."""
    import traceback

    def _hook(exctype, value, tb):
        text = "".join(traceback.format_exception(exctype, value, tb))
        try:
            if sys.stderr:
                sys.stderr.write(text)
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "Beklenmedik Hata",
                                 f"{exctype.__name__}: {value}\n\n"
                                 "Uygulama açık kalmaya çalışıyor; loglara bakın.")
        except Exception:
            pass

    sys.excepthook = _hook


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _install_global_excepthook()
    apply_dark_palette(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
