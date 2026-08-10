from enum import Enum
import time


NOK_REGISTER = 100
TRIGGER_REGISTER = 101
ALLOWED_REGISTERS = {NOK_REGISTER, TRIGGER_REGISTER}


class InspectionState(str, Enum):
    READY = "READY"
    BUSY = "BUSY"
    OK = "OK"
    NOK = "NOK"
    ERROR = "ERROR"


class NullPLCAdapter:
    """
    PLC entegrasyonu icin bos adapter.
    Gercek GPIO/Modbus adapteri ayni metodlari uygulayacak.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.state = InspectionState.READY
        self.last_result = None

    def poll(self):
        return None

    def set_state(self, state: InspectionState):
        self.state = state

    def publish_result(self, ok: bool):
        self.last_result = bool(ok)
        self.state = InspectionState.OK if ok else InspectionState.NOK
        return True

    def publish_error(self, message: str):
        self.last_result = None
        self.state = InspectionState.ERROR
        return True

    def reset_nok(self):
        self.last_result = True
        return True

    def close(self):
        pass

    def is_connected(self):
        return True

    def status_text(self):
        return "PLC simülasyon"

    def drain_debug_events(self):
        return []


class ModbusTCPPLCAdapter:
    """
    Modbus TCP PLC adapter.

    Raspberry Pi bu modelde Modbus client olarak PLC'ye baglanir:
    - PLC urun yokken trigger registerini 0, urun varken 1 yapar.
    - Pi trigger registerinin yukselen kenarinda resmi analiz eder.
    - Pi sonucu sadece nok holding register olarak yazar.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.state = InspectionState.READY
        self.last_result = None
        self._debug_events = []
        self._client = None
        self._connected = False
        self._last_trigger = False
        self._last_trigger_raw = None
        self._last_connect_attempt = 0.0
        self.last_error = ""

        self.host = self.config.get("host", "192.168.10.10")
        self.port = int(self.config.get("port", 502))
        self.unit_id = int(self.config.get("unit_id", self.config.get("slave_id", 1)))
        self.timeout_s = float(self.config.get("timeout_s", 1.0))
        self.reconnect_s = float(self.config.get("reconnect_s", 3.0))

        self.trigger_addr = TRIGGER_REGISTER
        self.nok_addr = NOK_REGISTER

        self._connect()
        self.set_state(InspectionState.READY)

    def poll(self):
        if not self._ensure_connected():
            return None

        response = self._read_holding_registers(self.trigger_addr, 1)
        if response is None:
            self._mark_disconnected()
            return None

        trigger_raw = int(response[0])
        if trigger_raw != self._last_trigger_raw:
            self._log_debug(f"HR{TRIGGER_REGISTER} okundu: {trigger_raw}")
            self._last_trigger_raw = trigger_raw
        trigger = trigger_raw != 0
        command = "capture" if trigger and not self._last_trigger else None
        if command == "capture":
            self._log_debug(f"HR{TRIGGER_REGISTER} 0->1 tetik yakalandı, kamera çekimi başlatılacak")
        self._last_trigger = trigger
        return command

    def set_state(self, state: InspectionState):
        self.state = state

    def publish_result(self, ok: bool):
        self.last_result = bool(ok)
        self.state = InspectionState.OK if ok else InspectionState.NOK
        if not self._ensure_connected():
            return False
        value = 0 if ok else 1
        if self._write_holding_register(self.nok_addr, value):
            self._log_debug(f"HR{NOK_REGISTER} yazıldı: {value}")
            return True
        # Yazma basarisiz: iletisim kopmus olabilir -> kopuk isaretle ki
        # is_connected() gercegi yansitsin ve _ensure_connected yeniden baglansin.
        self._mark_disconnected()
        return False

    def publish_error(self, message: str):
        self.last_result = None
        self.state = InspectionState.ERROR
        if not self._ensure_connected():
            return False
        if self._write_holding_register(self.nok_addr, 1):
            self._log_debug(f"HR{NOK_REGISTER} yazıldı: 1 (hata: {message})")
            return True
        self._mark_disconnected()
        return False

    def reset_nok(self):
        if not self._ensure_connected():
            return False
        if self._write_holding_register(self.nok_addr, 0):
            self.last_result = True
            self._log_debug(f"HR{NOK_REGISTER} resetlendi: 0")
            return True
        self._mark_disconnected()
        return False

    def close(self):
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        self._connected = False

    def _connect(self):
        self._last_connect_attempt = time.time()
        self._log_debug(
            f"Bağlantı deneniyor: {self.host}:{self.port}, unit_id={self.unit_id}, "
            f"oku=HR{TRIGGER_REGISTER}, yaz=HR{NOK_REGISTER}"
        )
        try:
            try:
                from pymodbus.client import ModbusTcpClient
            except ImportError:
                from pymodbus.client.sync import ModbusTcpClient

            self._client = ModbusTcpClient(self.host, port=self.port, timeout=self.timeout_s)
            self._connected = bool(self._client.connect())
            if self._connected:
                self.last_error = ""
                self._log_debug(f"Bağlantı başarılı: {self.host}:{self.port}")
            else:
                self.last_error = f"PLC bağlantısı yok: {self.host}:{self.port}; {self.reconnect_s:.0f} sn sonra tekrar denenecek"
                self._log_debug(self.last_error)
        except Exception as exc:
            self._client = None
            self._connected = False
            self.last_error = f"PLC bağlantı hatası: {self.host}:{self.port} - {exc}; {self.reconnect_s:.0f} sn sonra tekrar denenecek"
            self._log_debug(self.last_error)

    def _ensure_connected(self):
        if self._client is not None and self._connected:
            return True
        now = time.time()
        if now - self._last_connect_attempt >= self.reconnect_s:
            self.close()
            self._connect()
        return self._connected

    def _mark_disconnected(self):
        self._connected = False
        # Yeniden baglandiktan sonra hala HIGH olan tetik YENI bir yukselen kenar
        # olarak gorulsun; aksi halde kopma aninda bekleyen parca icin denetim hic
        # tetiklenmez ve PLC sonuc icin sonsuz bekler.
        self._last_trigger = False
        self._last_trigger_raw = None
        self.last_error = "PLC haberleşmesi koptu"
        self._log_debug(f"{self.last_error}; {self.reconnect_s:.0f} sn sonra tekrar denenecek")

    def is_connected(self):
        return bool(self._connected)

    def status_text(self):
        if self._connected:
            return f"PLC bağlı {self.host}:{self.port}"
        return self.last_error or f"PLC bağlı değil {self.host}:{self.port}"

    def drain_debug_events(self):
        events = self._debug_events
        self._debug_events = []
        return events

    def _log_debug(self, message: str):
        self._debug_events.append(message)
        if len(self._debug_events) > 100:
            self._debug_events = self._debug_events[-100:]

    def _read_holding_registers(self, address: int, count: int):
        if int(address) != TRIGGER_REGISTER or int(count) != 1:
            self.last_error = f"PLC okuma engellendi: sadece HR{TRIGGER_REGISTER} okunabilir"
            self._log_debug(self.last_error)
            return None

        try:
            response = self._client.read_holding_registers(address=address, count=count, device_id=self.unit_id)
        except TypeError:
            try:
                response = self._client.read_holding_registers(address=address, count=count, slave=self.unit_id)
            except TypeError:
                response = self._client.read_holding_registers(address, count, unit=self.unit_id)
        except Exception as exc:
            self.last_error = f"PLC HR{address} okuma exception: {exc}"
            self._log_debug(self.last_error)
            return None

        if response is None or getattr(response, "isError", lambda: True)():
            self.last_error = f"PLC HR{address} okunamadı: {response}"
            self._log_debug(self.last_error)
            return None
        return list(getattr(response, "registers", []))[:count]

    def _write_holding_registers(self, values: dict):
        for address, value in values.items():
            if not self._write_holding_register(address, value):
                self._mark_disconnected()
                return False
        return True

    def _write_holding_register(self, address: int, value: int):
        if int(address) != NOK_REGISTER:
            self.last_error = f"PLC yazma engellendi: sadece HR{NOK_REGISTER} yazılabilir"
            self._log_debug(self.last_error)
            return False

        try:
            response = self._client.write_register(address=address, value=int(value), device_id=self.unit_id)
        except TypeError:
            try:
                response = self._client.write_register(address=address, value=int(value), slave=self.unit_id)
            except TypeError:
                response = self._client.write_register(address, int(value), unit=self.unit_id)
        except Exception as exc:
            self.last_error = f"PLC HR{address} yazma exception: {exc}"
            self._log_debug(self.last_error)
            return False

        ok = response is not None and not getattr(response, "isError", lambda: True)()
        if not ok:
            self.last_error = f"PLC HR{address} yazılamadı: {response}"
            self._log_debug(self.last_error)
        return ok


def create_plc_adapter(config=None):
    plc_cfg = (config or {}).get("plc", {})
    # Elle cekim modu: PLC tamamen devre disi (ev/test). Baglanti denemesi/log olmaz,
    # tetik beklenmez. plc.type KORUNUR (sahada manual_mode kapatilinca geri gelir).
    if plc_cfg.get("manual_mode", False):
        return NullPLCAdapter(plc_cfg)
    plc_type = plc_cfg.get("type", "null")
    if plc_type is None:
        plc_type = "null"
    plc_type = str(plc_type).lower()
    if plc_type in ("null", "none", "disabled"):
        return NullPLCAdapter(plc_cfg)
    if plc_type in ("modbus_tcp", "modbus", "tcp"):
        return ModbusTCPPLCAdapter(plc_cfg)
    raise ValueError(f"Desteklenmeyen PLC adapter tipi: {plc_type}")
