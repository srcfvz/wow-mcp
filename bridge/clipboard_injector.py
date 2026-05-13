import sys
import base64
import json

def inject_to_clipboard(payload: str, msg_type: str = "NOTICE"):
    """
    Encodes the payload to a structured JSON envelope, then Base64,
    and copies it to the OS clipboard.
    
    msg_type can be:
      - NOTICE: Print to chat frame.
      - WAYPOINT: Add a TomTom waypoint (requires /way x y name format in payload or structured data).
      - CHAT_RESPONSE: A response intended for chat (though still requires manual paste/send for safety).
    """
    envelope = {
        "v": 1,
        "type": msg_type,
        "payload": payload
    }
    
    json_str = json.dumps(envelope)
    b64_data = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    full_string = f"WMCP1:{b64_data}"
    
    try:
        import pyperclip
        pyperclip.copy(full_string)
        return True, f"Injected ({msg_type}): {full_string[:30]}..."
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        success, msg = inject_to_clipboard(" ".join(sys.argv[1:]))
        print(msg)
    else:
        print("Usage: python clipboard_injector.py <text_to_inject>")
