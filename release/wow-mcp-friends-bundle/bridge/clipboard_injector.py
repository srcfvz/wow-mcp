import sys
import base64

def inject_to_clipboard(payload: str):
    """
    Encodes the payload to Base64 (to avoid special char issues in WoW)
    and copies it to the clipboard.
    """
    # WoW EditBox has a character limit, so we prefix it so the Lua knows to parse it.
    # Protocol: "WMCP:" + base64_payload
    b64_data = base64.b64encode(payload.encode('utf-8')).decode('utf-8')
    full_string = f"WMCP:{b64_data}"
    
    try:
        import pyperclip
        pyperclip.copy(full_string)
        return True, f"Injected: {full_string[:20]}..."
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    # Test script
    if len(sys.argv) > 1:
        success, msg = inject_to_clipboard(" ".join(sys.argv[1:]))
        print(msg)
    else:
        print("Usage: python clipboard_injector.py <text_to_inject>")
