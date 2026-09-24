import cv2
import numpy as np
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QLabel,
                             QPushButton, QListWidget, QDoubleSpinBox, QFormLayout,
                             QScrollArea, QMenu)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor

class ROILabel(QLabel):
    new_roi = pyqtSignal(int, int, int, int)
    roi_selected = pyqtSignal(str)
    roi_right_clicked = pyqtSignal(str, object)   # (ad, global QPoint) -> sag tik menusu
    draw_cancelled = pyqtSignal()                 # cizim modu iptal edildi (ESC/sag tik)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self._drawing = False
        self._start_pt = None
        self._end_pt = None
        self._mode = None
        self._active_roi = None
        self._drag_origin = None
        self._roi_origin = None
        self._original_pixmap = None
        self._scale = 1.0
        self._zoom = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self.rois = {}
        self.disabled_rois = set()
        self.selected_roi = None
        self.types = {}           # ad -> "hole" (delik) | "notch" (centik)
        self.draw_shape = "circle"  # yeni ciziminin sekli: "circle" | "rect"
        # Cizim modu: SADECE "Yeni ROI Ciz" ile silahlanir (yanlislikla surukleyip
        # ROI olusturmayi onler). Moddayken mevcut ROI'ler GIZLENIR (temiz tuval);
        # cizim biter/iptal edilir edilmez geri gorunurler.
        self.drawing_mode = False

    def set_image(self, pixmap: QPixmap):
        self._original_pixmap = pixmap
        self._zoom = 1.0
        self.setFixedSize(pixmap.size())
        self._update_display()

    def set_zoom(self, zoom: float):
        if not self._original_pixmap:
            return
        self._zoom = max(0.25, min(4.0, float(zoom)))
        self.setFixedSize(
            max(1, int(self._original_pixmap.width() * self._zoom)),
            max(1, int(self._original_pixmap.height() * self._zoom)),
        )
        self._update_display()

    def _update_display(self):
        if not self._original_pixmap: return
        scaled = self._original_pixmap.scaled(
            max(1, int(self._original_pixmap.width() * self._zoom)),
            max(1, int(self._original_pixmap.height() * self._zoom)),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._scale = scaled.width() / self._original_pixmap.width()
        self._offset_x = 0
        self._offset_y = 0

        canvas = QPixmap(scaled.width(), scaled.height())
        canvas.fill(QColor("#11111b"))
        painter = QPainter(canvas)
        painter.drawPixmap(self._offset_x, self._offset_y, scaled)

        # Mevcut ROI'leri ciz (delik -> daire, centik -> dikdortgen).
        # CIZIM MODUNDA GIZLENIR: yeni ROI cizerken oncekiler tuvali kirletmesin
        # (kullanici istegi); mod kapaninca yeniden gorunurler.
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        if not self.drawing_mode:
            for name, (x, y, w, h) in self.rois.items():
                cx = int(x * self._scale) + self._offset_x
                cy = int(y * self._scale) + self._offset_y
                cw = int(w * self._scale)
                ch = int(h * self._scale)
                roi_type = self.types.get(name, "hole")
                # Yon noktalari turuncu (kusur kontrolu degil, yon tayini olcumu).
                color = QColor("#fab387") if roi_type == "yon" else Qt.yellow
                if name in self.disabled_rois:
                    color = Qt.gray
                if name == self.selected_roi:
                    color = Qt.cyan
                painter.setPen(QPen(color, 2))
                if roi_type == "hole":
                    painter.drawEllipse(cx, cy, cw, ch)
                else:   # notch ve yon: dikdortgen
                    painter.drawRect(cx, cy, cw, ch)
                tip = {"notch": "çentik", "yon": "yön"}.get(roi_type, "delik")
                label = f"{name} ({tip})" + ("  PASIF" if name in self.disabled_rois else "")
                painter.drawText(cx, cy - 5, label)

        # Cizilmekte olan yeni ROI'yi ciz (moda gore daire/kutu)
        if self._start_pt and self._end_pt:
            painter.setPen(QPen(Qt.red, 2))
            x1, y1 = self._start_pt
            x2, y2 = self._end_pt
            x1 = min(max(x1, self._offset_x), self._offset_x + scaled.width())
            x2 = min(max(x2, self._offset_x), self._offset_x + scaled.width())
            y1 = min(max(y1, self._offset_y), self._offset_y + scaled.height())
            y2 = min(max(y2, self._offset_y), self._offset_y + scaled.height())
            rx, ry, rw, rh = min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)
            if self.draw_shape == "circle":
                painter.drawEllipse(rx, ry, rw, rh)
            else:
                painter.drawRect(rx, ry, rw, rh)

        painter.end()
        self.setPixmap(canvas)

    def cancel_drawing(self):
        """Cizim modunu iptal eder (ESC ya da sag tik); mevcut ROI'ler geri gorunur."""
        if not self.drawing_mode:
            return
        self.drawing_mode = False
        self._drawing = False
        self._start_pt = None
        self._end_pt = None
        self._mode = None
        self._update_display()
        self.draw_cancelled.emit()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            # Cizim modundayken sag tik = iptal.
            if self.drawing_mode:
                self.cancel_drawing()
                return
            # Normal modda: ROI'ye sag tik -> baglam menusu (Sil).
            hit_name, _ = self._hit_test(ev.x(), ev.y())
            if hit_name:
                self.selected_roi = hit_name
                self.roi_selected.emit(hit_name)
                self._update_display()
                self.roi_right_clicked.emit(hit_name, ev.globalPos())
            return

        if ev.button() == Qt.LeftButton and self._point_in_image(ev.x(), ev.y()):
            # Cizim SADECE silahlanmis moddayken baslar (yanlislikla cizim onlenir).
            if self.drawing_mode:
                self._drawing = True
                self._mode = "draw"
                self._start_pt = (ev.x(), ev.y())
                self._end_pt = self._start_pt
                self._update_display()
                return

            hit_name, hit_mode = self._hit_test(ev.x(), ev.y())
            if hit_name:
                self.selected_roi = hit_name
                self._active_roi = hit_name
                self._mode = hit_mode
                self._drag_origin = (ev.x(), ev.y())
                self._roi_origin = list(self.rois[hit_name])
                self.roi_selected.emit(hit_name)
                self._update_display()

    def mouseMoveEvent(self, ev):
        if self._mode in ("move", "resize") and self._active_roi:
            self._update_active_roi(ev.x(), ev.y())
            self._update_display()
        elif self._drawing:
            self._end_pt = self._clamp_to_image(ev.x(), ev.y())
            self._update_display()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._mode in ("move", "resize"):
            if self._active_roi:
                self._update_active_roi(ev.x(), ev.y())
            self._mode = None
            self._active_roi = None
            self._drag_origin = None
            self._roi_origin = None
            self._update_display()
        elif ev.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            self._end_pt = self._clamp_to_image(ev.x(), ev.y())

            x1 = min(self._start_pt[0], self._end_pt[0]) - self._offset_x
            y1 = min(self._start_pt[1], self._end_pt[1]) - self._offset_y
            x2 = max(self._start_pt[0], self._end_pt[0]) - self._offset_x
            y2 = max(self._start_pt[1], self._end_pt[1]) - self._offset_y

            w = x2 - x1
            h = y2 - y1

            if w > 5 and h > 5 and self._scale > 0:
                orig_x = int(x1 / self._scale)
                orig_y = int(y1 / self._scale)
                orig_w = int(w / self._scale)
                orig_h = int(h / self._scale)

                # Sinirlarin disina tasmayi engelle
                orig_x = max(0, orig_x)
                orig_y = max(0, orig_y)
                orig_w = min(orig_w, self._original_pixmap.width() - orig_x)
                orig_h = min(orig_h, self._original_pixmap.height() - orig_y)

                # Basarili cizim -> mod TEK SEFERLIK kapanir (hafizaya alindi),
                # mevcut ROI'ler yeniden gorunur. Cok kucuk surukleme -> mod acik
                # kalir, kullanici yeniden dener.
                self.drawing_mode = False
                self.new_roi.emit(orig_x, orig_y, orig_w, orig_h)

            self._start_pt = None
            self._end_pt = None
            self._mode = None
            self._update_display()

    def _update_active_roi(self, x, y):
        if not self._active_roi or not self._drag_origin or not self._roi_origin or self._scale <= 0:
            return
        img_x, img_y = self._widget_to_image(*self._clamp_to_image(x, y))
        start_x, start_y = self._widget_to_image(*self._drag_origin)
        dx = int(img_x - start_x)
        dy = int(img_y - start_y)
        ox, oy, ow, oh = self._roi_origin
        max_w = self._original_pixmap.width()
        max_h = self._original_pixmap.height()

        if self._mode == "move":
            nx = min(max(0, ox + dx), max(0, max_w - ow))
            ny = min(max(0, oy + dy), max(0, max_h - oh))
            self.rois[self._active_roi] = [nx, ny, ow, oh]
        elif self._mode == "resize":
            nw = min(max(6, ow + dx), max_w - ox)
            nh = min(max(6, oh + dy), max_h - oy)
            self.rois[self._active_roi] = [ox, oy, nw, nh]

    def _point_in_image(self, x, y) -> bool:
        if not self._original_pixmap:
            return False
        img_w = self._original_pixmap.width() * self._scale
        img_h = self._original_pixmap.height() * self._scale
        return self._offset_x <= x <= self._offset_x + img_w and self._offset_y <= y <= self._offset_y + img_h

    def _clamp_to_image(self, x, y) -> tuple:
        if not self._original_pixmap:
            return x, y
        img_w = int(self._original_pixmap.width() * self._scale)
        img_h = int(self._original_pixmap.height() * self._scale)
        x = min(max(x, self._offset_x), self._offset_x + img_w)
        y = min(max(y, self._offset_y), self._offset_y + img_h)
        return x, y

    def _widget_to_image(self, x, y) -> tuple:
        return ((x - self._offset_x) / self._scale, (y - self._offset_y) / self._scale)

    def _hit_test(self, x, y) -> tuple:
        handle = 10
        for name in reversed(list(self.rois.keys())):
            rx, ry, rw, rh = self.rois[name]
            sx = int(rx * self._scale) + self._offset_x
            sy = int(ry * self._scale) + self._offset_y
            sw = int(rw * self._scale)
            sh = int(rh * self._scale)
            if sx <= x <= sx + sw and sy <= y <= sy + sh:
                if sx + sw - handle <= x <= sx + sw + handle and sy + sh - handle <= y <= sy + sh + handle:
                    return name, "resize"
                return name, "move"
        return None, None


class ROIDialog(QDialog):
    def __init__(
        self,
        image: np.ndarray,
        existing_rois: dict,
        parent=None,
        title: str = "Kontrol Noktaları",
        list_label: str = "Tanımlı kontrol noktaları:",
        prompt: str = None,
        roi_types: dict = None,
        disabled_rois=None,
        point_overrides: dict = None,
        roi_defaults: dict = None,
        **_ignored,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(1100, 720)
        self.rois = existing_rois.copy()
        self.disabled_rois = set(disabled_rois or [])
        # Nokta tipleri: delik (hole) | centik (notch) | yon. Eskileri varsayilan delik.
        self.roi_types = {n: str(t).lower() for n, t in (roi_types or {}).items()}
        for _n in self.rois:
            self.roi_types.setdefault(_n, "hole")
        self._add_type = "hole"
        # Yon referansi: menudeki "Yon Referansi Al" ile bu penceredeki GUNCEL
        # noktalar + acik goruntuden olculur; cagiran (main), dialog kabulunde
        # None degilse config'e yazar. (Dogru parca goruntusuyle acilmis olmali.)
        self._image_bgr = image
        self.handedness_ref_diff = None
        # NOKTA BASINA esik ayarlari (sag tik -> Ayarlar). Ayari olmayan nokta
        # global degeri kullanir; cagiran (main) kabulde config'e yazar.
        self.point_overrides = {n: dict(v) for n, v in (point_overrides or {}).items()
                                if isinstance(v, dict)}
        # Global varsayilanlar (Ayarlar penceresinin on-dolumu icin).
        self.roi_defaults = {"hole_dark_ratio_min": 20.0, "hole_core_ratio_min": 2.0,
                             "notch_dark_min": 25.0}
        self.roi_defaults.update(roi_defaults or {})
        # "Referansi Sifirla" istegi: kabulde main, reference_profile'i temizler.
        self.reset_reference_requested = False

        self.layout = QHBoxLayout(self)

        self.lbl_img = ROILabel()
        self.lbl_img.setStyleSheet("background-color: #11111b; border: 2px solid #45475a;")
        h, w, ch = image.shape
        bytes_per_line = ch * w
        qimg = QImage(image.data, w, h, bytes_per_line, QImage.Format_BGR888)
        self.lbl_img.new_roi.connect(self._on_new_roi)
        self.lbl_img.roi_selected.connect(self._select_roi)
        self.lbl_img.roi_right_clicked.connect(self._on_canvas_right_click)
        self.lbl_img.draw_cancelled.connect(self._on_draw_cancelled)
        self.lbl_img.rois = self.rois
        self.lbl_img.disabled_rois = self.disabled_rois
        self.lbl_img.types = self.roi_types
        self.lbl_img.set_image(QPixmap.fromImage(qimg))
        initial_zoom = min(1.0, 850 / max(1, w), 620 / max(1, h))
        self.lbl_img.set_zoom(initial_zoom)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #11111b; border: 2px solid #45475a;")
        self.scroll_area.setWidget(self.lbl_img)

        image_panel = QVBoxLayout()
        zoom_layout = QHBoxLayout()
        btn_zoom_out = QPushButton("Zoom -")
        btn_zoom_out.clicked.connect(lambda: self._change_zoom(0.8))
        zoom_layout.addWidget(btn_zoom_out)
        btn_zoom_100 = QPushButton("100%")
        btn_zoom_100.clicked.connect(lambda: self._set_zoom(1.0))
        zoom_layout.addWidget(btn_zoom_100)
        btn_zoom_in = QPushButton("Zoom +")
        btn_zoom_in.clicked.connect(lambda: self._change_zoom(1.25))
        zoom_layout.addWidget(btn_zoom_in)
        image_panel.addLayout(zoom_layout)
        image_panel.addWidget(self.scroll_area)

        self.layout.addLayout(image_panel, stretch=3)

        right_panel = QVBoxLayout()

        # --- Tek "Yeni Kontrol Noktasi" butonu: tiklaninca tip secenegi sunar
        # (delik/centik/yon), secim yapilinca cizim modu SILAHLANIR (tek cizim). ---
        self.btn_add_roi = QPushButton("＋ Yeni Kontrol Noktası")
        self.btn_add_roi.setStyleSheet(
            "background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 10px;")
        add_menu = QMenu(self.btn_add_roi)
        add_menu.setStyleSheet(
            "QMenu { background-color: #1e222a; color: #d6dae2; border: 1px solid #45475a; }"
            "QMenu::item { padding: 8px 24px; }"
            "QMenu::item:selected { background-color: #345e8c; }")
        add_menu.addAction("●  Delik (daire)", lambda: self._arm_draw("hole"))
        add_menu.addAction("▭  Çentik (kutu)", lambda: self._arm_draw("notch"))
        add_menu.addSeparator()
        add_menu.addAction("🧭  Yön Referansı Al (doğru parça)", self._take_handedness_reference)
        self.btn_add_roi.setMenu(add_menu)
        right_panel.addWidget(self.btn_add_roi)

        self.lbl_hint = QLabel()
        self.lbl_hint.setStyleSheet("color: #a6adc8;")
        self.lbl_hint.setWordWrap(True)
        right_panel.addWidget(self.lbl_hint)

        lbl_info = QLabel(list_label)
        lbl_info.setStyleSheet("color: #cdd6f4; font-weight: bold;")
        right_panel.addWidget(lbl_info)
        self.list_rois = QListWidget()
        self.list_rois.setStyleSheet("background-color: #313244; color: #cdd6f4;")
        self.list_rois.setToolTip(
            "Ctrl (tek tek) ya da Shift (aralık) ile birden çok nokta seçilebilir.\n"
            "Silme: 'Sil' butonu, Delete tuşu ya da sağ tık menüsü.")
        # COKLU SECIM: Ctrl/Shift ile birden cok nokta secilip TEK SEFERDE silinir.
        self.list_rois.setSelectionMode(QListWidget.ExtendedSelection)
        right_panel.addWidget(self.list_rois)
        self.list_rois.currentTextChanged.connect(self._select_roi)
        # Listede sag tik -> Sil menusu (coklu secimde hepsini siler).
        self.list_rois.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_rois.customContextMenuRequested.connect(self._on_list_context_menu)

        btn_del = QPushButton("Sil")
        btn_del.setToolTip("Listede seçili kontrol noktalarını siler (Ctrl ile çoklu seçim).")
        btn_del.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold; padding: 8px;")
        btn_del.clicked.connect(self._del_roi)
        right_panel.addWidget(btn_del)

        # Eski OK (template) referanslarini temizler; 'Kaydet ve Kapat'ta uygulanir.
        btn_reset_ref = QPushButton("Referansı Sıfırla")
        btn_reset_ref.setToolTip("Öğretilmiş OK referanslarını temizler ('Kaydet ve Kapat' ile uygulanır).")
        btn_reset_ref.setStyleSheet("background-color: #f9e2af; color: #11111b; font-weight: bold; padding: 8px;")
        btn_reset_ref.clicked.connect(self._request_reference_reset)
        right_panel.addWidget(btn_reset_ref)

        btn_ok = QPushButton("Kaydet ve Kapat")
        btn_ok.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 12px;")
        btn_ok.clicked.connect(self.accept)
        right_panel.addWidget(btn_ok)

        self.layout.addLayout(right_panel, stretch=1)

        self._reset_hint()
        self._update_list()

    def _reset_hint(self):
        self.lbl_hint.setText(
            "'Yeni Kontrol Noktası'na tıkla → Delik / Çentik seç → resimde sürükleyerek "
            "çiz (isim otomatik: 1, 2, 3…). Silmek için listede ya da resimde sağ tıkla. "
            "Yön öğretme: DOĞRU parça görüntüsündeyken menüden 'Yön Referansı Al'.")

    def _arm_draw(self, t):
        """Tip secildi -> cizim modunu silahlandir. Mevcut noktalar cizim bitene
        kadar GIZLENIR (temiz tuval); iptal: ESC ya da sag tik."""
        self._add_type = t
        self.lbl_img.draw_shape = "circle" if t == "hole" else "rect"
        self.lbl_img.selected_roi = None
        self.lbl_img.drawing_mode = True
        self.lbl_img._update_display()
        tip = "DELİK (daire)" if t == "hole" else "ÇENTİK (kutu)"
        self.lbl_hint.setText(
            f"ÇİZİM MODU: {tip} — resimde sürükleyerek çiz. Mevcut noktalar çizim "
            "bitene kadar gizlendi. İptal: ESC ya da sağ tık.")

    def _on_draw_cancelled(self):
        self._reset_hint()

    def _take_handedness_reference(self):
        """TEK KOMUT yon ogretme (dogru parca goruntusu acikken): bu penceredeki
        GUNCEL noktalarla imza olculur (2 delikten); 'Kaydet ve Kapat' ile config'e
        yazilir. Ters/ayna parca bundan sonra otomatik NOK verir."""
        from inspector.features import hole_handedness_diff
        cfg = {"dynamic_rois": self.rois,
               "disabled_rois": sorted(self.disabled_rois),
               "roi": {"roi_types": self.roi_types}}
        diff = hole_handedness_diff(self._image_bgr, cfg)
        if diff is None:
            self.lbl_hint.setText(
                "⚠ Yön referansı için en az 2 'Delik' noktası gerekli — önce delikleri "
                "çizin, sonra menüden tekrar 'Yön Referansı Al' deneyin.")
            return
        self.handedness_ref_diff = float(diff)
        self.lbl_hint.setText(
            f"🧭 Yön referansı alındı (sağ−sol parlaklık farkı {diff:+.0f}). "
            "'Kaydet ve Kapat' ile kalıcı olur; ters/ayna parçalar otomatik NOK verecek.")

    def keyPressEvent(self, ev):
        # Cizim modundayken ESC cizimi iptal etsin (diyalogu KAPATMASIN).
        if ev.key() == Qt.Key_Escape and self.lbl_img.drawing_mode:
            self.lbl_img.cancel_drawing()
            return
        # Delete tusu: listede secili noktalari sil.
        if ev.key() == Qt.Key_Delete:
            self._del_roi()
            return
        super().keyPressEvent(ev)

    def _selected_names(self) -> list:
        """Listede SECILI tum kontrol noktasi adlari (coklu secim destekli);
        secim yoksa aktif ogeye duser."""
        names = [it.text().split("  (")[0] for it in self.list_rois.selectedItems()]
        if not names:
            cur = self._current_name()
            if cur:
                names = [cur]
        return names

    def _on_list_context_menu(self, pos):
        item = self.list_rois.itemAt(pos)
        if item is None:
            return
        # Tiklanan oge mevcut coklu secimin PARCASIYSA tum secim silinir;
        # degilse yalniz tiklanan oge hedeflenir.
        if item not in self.list_rois.selectedItems():
            self.list_rois.setCurrentItem(item)
        names = self._selected_names()
        if not names:
            return
        menu = QMenu(self)
        act_settings = None
        if len(names) > 1:
            act_del = menu.addAction(f"Seçilen {len(names)} noktayı Sil")
        else:
            act_settings = menu.addAction(f"⚙  '{names[0]}' Ayarlar…")
            act_del = menu.addAction(f"🗑  '{names[0]}' Sil")
        chosen = menu.exec_(self.list_rois.mapToGlobal(pos))
        if chosen == act_del:
            for n in names:
                self._delete_roi_by_name(n)
        elif act_settings is not None and chosen == act_settings:
            self._open_point_settings(names[0])

    def _on_canvas_right_click(self, name, global_pos):
        menu = QMenu(self)
        act_settings = menu.addAction(f"⚙  '{name}' Ayarlar…")
        act_del = menu.addAction(f"🗑  '{name}' Sil")
        chosen = menu.exec_(global_pos)
        if chosen == act_del:
            self._delete_roi_by_name(name)
        elif chosen == act_settings:
            self._open_point_settings(name)

    def _request_reference_reset(self):
        self.reset_reference_requested = True
        self.lbl_hint.setText(
            "🗑 Öğretilmiş OK referansları 'Kaydet ve Kapat' ile SIFIRLANACAK. "
            "(Vazgeçmek için pencereyi X ile kapat.)")

    # Tip basina ayarlanabilir esikler: (config anahtari, etiket, aralik, adim, aciklama).
    POINT_SETTINGS = {
        "hole": [
            ("hole_dark_ratio_min", "Delik Açıklık Eşiği (koyu%)", (0.0, 50.0), 1.0,
             "Delik en az bu kadar AÇIK (koyu) okumalı; altı 'kapalı/tıkalı' NOK.\n"
             "Tam açık delik ~%25, kısmen bantlı ~%11 okur; eşiği aralarına koy."),
            ("hole_core_ratio_min", "Derinlik Eşiği (çekirdek koyu%)", (0.0, 30.0), 0.5,
             "Deliğin çekirdeğinde en az bu kadar siyaha-yakın piksel olmalı;\n"
             "altı 'tıkalı/dolu' NOK. 0 = derinlik kapısı kapalı."),
        ],
        "notch": [
            ("notch_dark_min", "Oluk Eşiği (koyu%)", (0.0, 90.0), 1.0,
             "Koyu alan bu eşiğin ÜSTÜNDEyse 'oluk VAR'.\n"
             "Oluklu parça ~%50, oluksuz ~%17 okur; eşiği aralarına koy."),
        ],
    }

    def _open_point_settings(self, name):
        """Noktaya OZEL esik ayarlari (tipine gore): delik -> Aciklik + Derinlik,
        centik -> Oluk Esigi. Kaydet = override yaz; Varsayilana Don = hepsini sil
        (global config degerleri kullanilir). Kalici kayit 'Kaydet ve Kapat' ile."""
        if name not in self.rois:
            return
        rtype = self.roi_types.get(name, "hole")
        fields = self.POINT_SETTINGS.get(rtype)
        if not fields:
            self.lbl_hint.setText("Bu noktanın ayarı yok (kusur kontrolüne girmez).")
            return
        ov_now = self.point_overrides.get(name) or {}

        dlg = QDialog(self)
        tip = "delik" if rtype == "hole" else "çentik"
        dlg.setWindowTitle(f"'{name}' ({tip}) Kontrol Noktası Ayarları")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        spins = {}
        for key, label, rng, step, desc in fields:
            global_val = float(self.roi_defaults.get(key, rng[0]))
            info = QLabel(desc + f"  (genel değer: %{global_val:g})")
            info.setWordWrap(True)
            info.setStyleSheet("color:#a6adc8; font-size:11px;")
            lay.addWidget(info)
            class _NoWheelSpin(QDoubleSpinBox):
                # (1) Fare tekerlegi degeri DEGISTIRMESIN (kazara ayar bozulmasi).
                # (2) Ondalik ayirac: hem ',' hem '.' kabul. tr_TR yerelinde Qt
                #     noktayi SESSIZCE ATIYOR -> '1.5' yazan 15.0 aliyordu (esik
                #     10 katina cikip her saglam parcayi NOK yapardi).
                def wheelEvent(self, event):
                    event.ignore()
                def _ayirac_duzelt(self, text):
                    ayirac = str(self.locale().decimalPoint())
                    return text.replace("." if ayirac == "," else ",", ayirac)
                def validate(self, text, pos):
                    return super().validate(self._ayirac_duzelt(text), pos)
                def valueFromText(self, text):
                    return super().valueFromText(self._ayirac_duzelt(text))
            spin = _NoWheelSpin()
            spin.setDecimals(1)
            spin.setRange(*rng)
            spin.setSingleStep(step)
            spin.setValue(float(ov_now.get(key, global_val)))
            form.addRow(label + ":", spin)
            spins[key] = spin
        lay.addLayout(form)
        btns = QHBoxLayout()
        b_save = QPushButton("Kaydet")
        b_save.setStyleSheet("background-color:#a6e3a1; color:#11111b; font-weight:bold; padding:8px;")
        b_default = QPushButton("Varsayılana Dön")
        b_cancel = QPushButton("Vazgeç")
        btns.addWidget(b_save); btns.addWidget(b_default); btns.addWidget(b_cancel)
        lay.addLayout(btns)
        result = {"action": None}
        b_save.clicked.connect(lambda: (result.update(action="save"), dlg.accept()))
        b_default.clicked.connect(lambda: (result.update(action="default"), dlg.accept()))
        b_cancel.clicked.connect(dlg.reject)
        if dlg.exec_() != QDialog.Accepted or result["action"] is None:
            return
        if result["action"] == "save":
            ov = self.point_overrides.setdefault(name, {})
            texts = []
            for key, label, _rng, _step, _desc in fields:
                val = float(spins[key].value())
                # Genel degerle ayniysa override yazma (gereksiz kayit olmasin).
                if abs(val - float(self.roi_defaults.get(key, val))) < 1e-9:
                    ov.pop(key, None)
                else:
                    ov[key] = val
                    texts.append(f"{label} = %{val:g}")
            if not ov:
                self.point_overrides.pop(name, None)
            self.lbl_hint.setText(
                f"⚙ '{name}': " + ("; ".join(texts) if texts else "genel değerler") +
                " ('Kaydet ve Kapat' ile kalıcı olur).")
        else:
            for key, *_ in fields:
                ov = self.point_overrides.get(name)
                if ov:
                    ov.pop(key, None)
            if not self.point_overrides.get(name):
                self.point_overrides.pop(name, None)
            self.lbl_hint.setText(
                f"⚙ '{name}' özel eşikleri kaldırıldı; genel değerler kullanılacak.")
        self._update_list()

    def _set_zoom(self, zoom: float):
        self.lbl_img.set_zoom(zoom)

    def _change_zoom(self, factor: float):
        self.lbl_img.set_zoom(self.lbl_img._zoom * factor)

    def _on_new_roi(self, x, y, w, h):
        # Otomatik sirali rakam isim (1, 2, 3 ...). Cizim modu label tarafinda
        # TEK SEFERLIK kapandi -> ROI hafizaya alindi, mevcutlar yeniden gorunur.
        idx = 1
        while str(idx) in self.rois:
            idx += 1
        name = str(idx)
        self.rois[name] = [x, y, w, h]
        self.roi_types[name] = self._add_type
        self.lbl_img.rois = self.rois
        self.lbl_img.types = self.roi_types
        self.lbl_img.disabled_rois = self.disabled_rois
        self.lbl_img._update_display()
        self._update_list()
        self._select_roi(name)
        tip = {"notch": "çentik", "yon": "yön"}.get(self._add_type, "delik")
        self.lbl_hint.setText(
            f"Kontrol noktası '{name}' ({tip}) eklendi ve hafızaya alındı. Yenisi "
            "için tekrar 'Yeni Kontrol Noktası'na tıkla; silmek için sağ tıkla.")

    def _del_roi(self):
        # Coklu secim destekli: listede secili TUM noktalari tek seferde sil.
        for name in self._selected_names():
            self._delete_roi_by_name(name)

    def _delete_roi_by_name(self, name):
        if not name or name not in self.rois:
            return
        del self.rois[name]
        self.roi_types.pop(name, None)
        self.point_overrides.pop(name, None)
        self.disabled_rois.discard(name)
        self.lbl_img.rois = self.rois
        self.lbl_img.types = self.roi_types
        self.lbl_img.disabled_rois = self.disabled_rois
        self.lbl_img.selected_roi = None
        self.lbl_img._update_display()
        self._update_list()

    def _current_name(self):
        item = self.list_rois.currentItem()
        if not item:
            return None
        return item.text().split("  (")[0]

    def _select_roi(self, name):
        if not name:
            return
        name = name.split("  (")[0]
        if name not in self.rois:
            return
        self.lbl_img.selected_roi = name
        self.lbl_img._update_display()
        matches = self.list_rois.findItems(name, Qt.MatchStartsWith)
        if matches and self.list_rois.currentItem() is not matches[0]:
            self.list_rois.setCurrentItem(matches[0])

    def _update_list(self):
        self.list_rois.clear()
        for name in self.rois:
            tip = {"notch": "çentik", "yon": "yön"}.get(
                self.roi_types.get(name, "hole"), "delik")
            suffix = "  [PASIF]" if name in self.disabled_rois else ""
            # Ozel esigi olan nokta listede gorunsun (sag tik -> Ayarlar ile degisir).
            ov = self.point_overrides.get(name) or {}
            parts = []
            val = ov.get("notch_dark_min") if tip == "çentik" else ov.get("hole_dark_ratio_min")
            if val is not None:
                parts.append(f"eşik %{float(val):.0f}")
            if tip == "delik" and ov.get("hole_core_ratio_min") is not None:
                parts.append(f"derinlik %{float(ov['hole_core_ratio_min']):g}")
            if parts:
                suffix += "  [" + ", ".join(parts) + "]"
            self.list_rois.addItem(f"{name}  ({tip}){suffix}")
