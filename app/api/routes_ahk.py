from fastapi import APIRouter
from pydantic import BaseModel
import subprocess

router = APIRouter()

# WINDOWS PATHS (DO NOT CHECK EXISTS IN WSL)
AHK_EXE = r'C:\Program Files\AutoHotkey\v2\AutoHotkey.exe'
AHK_SCRIPT = r'C:\Users\ccaetab\olena\ahk\tradezero.ahk'


class SymbolPayload(BaseModel):
    symbol: str


@router.post("/ahk/symbol")
def send_symbol(payload: SymbolPayload):
    symbol = payload.symbol.upper().strip()

    print(f"🔥 AHK ROUTE HIT: {symbol}")

    if not symbol.isalpha():
        return {"status": "ignored"}

    # ✅ CORRECT WSL → WINDOWS BRIDGE
    cmd = [
        "cmd.exe",
        "/c",
        "start",
        "",
        AHK_EXE,
        AHK_SCRIPT,
        symbol
    ]

    print("🔥 AHK CMD:", cmd)

    try:
        subprocess.Popen(cmd)
        return {"status": "ok", "symbol": symbol}

    except Exception as e:
        print("❌ AHK ERROR:", e)
        return {"status": "error", "detail": str(e)}
