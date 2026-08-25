import argparse
import sys
import time

import yaml
from pymodbus.client import ModbusTcpClient


NOK_REGISTER = 100
TRIGGER_REGISTER = 101


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_error(response):
    return response is None or getattr(response, "isError", lambda: True)()


def read_holding_register(client, address, unit_id):
    if int(address) != TRIGGER_REGISTER:
        raise ValueError(f"Sadece HR{TRIGGER_REGISTER} okunabilir.")

    try:
        return client.read_holding_registers(address=address, count=1, device_id=unit_id)
    except TypeError:
        try:
            return client.read_holding_registers(address=address, count=1, slave=unit_id)
        except TypeError:
            return client.read_holding_registers(address, 1, unit=unit_id)


def write_holding_register(client, address, value, unit_id):
    if int(address) != NOK_REGISTER:
        raise ValueError(f"Sadece HR{NOK_REGISTER} yazılabilir.")

    try:
        return client.write_register(address=address, value=int(value), device_id=unit_id)
    except TypeError:
        try:
            return client.write_register(address=address, value=int(value), slave=unit_id)
        except TypeError:
            return client.write_register(address, int(value), unit=unit_id)


def main():
    parser = argparse.ArgumentParser(description="Modbus TCP PLC hizli baglanti testi")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--unit-id", type=int)
    parser.add_argument("--write-test-register", type=int, help="Opsiyonel: sadece HR100'u kisa sure 1 yapip 0'a ceker")
    args = parser.parse_args()

    cfg = load_config(args.config)
    plc_cfg = cfg.get("plc", {})
    host = args.host or plc_cfg.get("host", "192.168.10.10")
    port = args.port or int(plc_cfg.get("port", 502))
    unit_id = args.unit_id if args.unit_id is not None else int(plc_cfg.get("unit_id", 1))
    trigger_register = TRIGGER_REGISTER

    client = ModbusTcpClient(host, port=port, timeout=float(plc_cfg.get("timeout_s", 1.0)))
    print(f"PLC baglanti deneniyor: {host}:{port}, unit_id={unit_id}")
    if not client.connect():
        print("HATA: PLC'ye TCP baglantisi kurulamadi.")
        return 2

    try:
        response = read_holding_register(client, trigger_register, unit_id)
        if is_error(response):
            print(f"HATA: trigger holding register okunamadi. register={trigger_register}")
            return 3
        value = int(response.registers[0])
        print(f"OK: trigger holding register {trigger_register} okunuyor, deger={value}")

        if args.write_test_register is not None:
            register = int(args.write_test_register)
            if register != NOK_REGISTER:
                print(f"HATA: Guvenlik nedeniyle sadece HR{NOK_REGISTER} yazilabilir.")
                return 6
            print(f"Yazma testi: holding register {register} -> 1")
            response = write_holding_register(client, register, 1, unit_id)
            if is_error(response):
                print(f"HATA: holding register {register} 1 yazilamadi.")
                return 4
            time.sleep(0.2)
            print(f"Yazma testi: holding register {register} -> 0")
            response = write_holding_register(client, register, 0, unit_id)
            if is_error(response):
                print(f"HATA: holding register {register} 0 yazilamadi.")
                return 5
            print("OK: yazma testi tamam.")
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
