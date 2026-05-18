#!/usr/bin/env python3
import json
import socket
import sys
import time
from pathlib import Path


HOOK_PC = 0x001C99C0
LOG_PATH = Path("opcode.txt")
VM_BASE = 0x00B2D408


class Client:
    def __init__(self, host: str = "127.0.0.1", port: int = 21512, timeout: float = 5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.fp = self.sock.makefile("rwb", buffering=0)

    def close(self):
        try:
            self.fp.close()
        finally:
            self.sock.close()

    def cmd(self, name: str, **kwargs):
        payload = {"cmd": name}
        payload.update(kwargs)
        self.fp.write(json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n")
        raw = self.fp.readline()
        if not raw:
            raise RuntimeError("debugserver closed")
        data = json.loads(raw.decode("utf-8"))
        if not data.get("ok"):
            raise RuntimeError(data.get("error", name))
        return data


def reg_u32(display: str) -> int:
    return int(display.split(".", 1)[0], 16)


def regs(client: Client) -> dict[str, int]:
    data = client.cmd("read_registers", cpu="ee")
    return {x["name"]: reg_u32(x["display"]) for x in data["data"]["GPR"]["regs"]}


def read_u32(client: Client, addr: int) -> int:
    data = client.cmd("read_memory", address=f"0x{addr:08X}", length=4)
    return int.from_bytes(bytes.fromhex(data["hex"]), "little")


def read_u16(client: Client, addr: int) -> int:
    data = client.cmd("read_memory", address=f"0x{addr:08X}", length=2)
    return int.from_bytes(bytes.fromhex(data["hex"]), "little")


def read_u8(client: Client, addr: int) -> int:
    data = client.cmd("read_memory", address=f"0x{addr:08X}", length=1)
    return int(data["hex"], 16)


def read_hex(client: Client, addr: int, length: int) -> str:
    if length <= 0:
        return ""
    data = client.cmd("read_memory", address=f"0x{addr:08X}", length=length)
    return data["hex"].upper()


def read_string(client: Client, addr: int) -> str:
    try:
        data = client.cmd("read_memory", address=f"0x{addr:08X}", length=512)
        raw = bytes.fromhex(data["hex"])
        end = raw.find(b"\x00")
        if end >= 0:
            raw = raw[:end]
        return raw.decode("cp932", "replace")
    except Exception:
        return ""


def wait_break(client: Client) -> int:
    while True:
        data = client.cmd("status")["data"]
        if data["paused"]:
            return int(data["pc"], 16)
        time.sleep(0.01)


def main():
    out = LOG_PATH.open("w", encoding="utf-8", newline="\n")
    client = Client()
    try:
        client.cmd("clear_breakpoints")
        client.cmd("set_breakpoint", address=f"0x{HOOK_PC:08X}")
        if client.cmd("status")["data"]["paused"]:
            client.cmd("resume")
        while True:
            pc = wait_break(client)
            if pc != HOOK_PC:
                client.cmd("resume")
                continue
            r = regs(client)
            ctx = read_u32(client, r["s0"] + 0x44)
            if ctx == 0:
                client.cmd("resume")
                continue
            vm = read_u32(client, ctx + 8)
            if vm < VM_BASE:
                client.cmd("resume")
                continue
            op = read_u8(client, vm)
            name = read_string(client, r["a1"])
            if op == 0x00 and name != "nop":
                client.cmd("resume")
                continue
            rel = vm - VM_BASE
            inst_hex = read_hex(client, vm, 8)
            arg_hex = inst_hex[2:] if len(inst_hex) >= 2 else ""
            extra = ""
            if op == 0x1F and name == "msg_disp" and read_u8(client, vm + 1) == 0x00:
                text_off = read_u16(client, vm + 2)
                text_mem = VM_BASE + text_off
                text = read_string(client, text_mem)
                extra = f" {text if text else '<NULL>'}"
            out.write(f"{rel:08X} {op:02X} {name} {arg_hex}{extra}\n")
            out.flush()
            client.cmd("resume")
    finally:
        client.close()
        out.close()


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("python dump_opcode.py")
    main()
