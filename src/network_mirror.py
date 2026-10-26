"""Opt-in LAN-only UI-state mirror. Never dispatches machine actions.

Runs on port 8080 alongside CircuitPython's built-in Web API on port 80.
All requests are handled cooperatively with bounded receive and send timeouts.
"""
import json

HTML = """<!doctype html><html lang=en><meta name=viewport content="width=device-width,initial-scale=1">
<title>CDAPROD Pendant Mirror</title><style>
body{background:#15191d;color:#e8eef2;font:15px system-ui;text-align:center;margin:20px}
h2{font-weight:600}#dial{position:relative;margin:20px auto;width:240px;height:240px;border-radius:50%;overflow:hidden;border:5px solid #39454b;background:#030708;touch-action:manipulation}
#title{position:absolute;top:29px;width:100%;font-weight:bold}#status{position:absolute;top:53px;width:100%;font-size:12px}#items{position:absolute;top:77px;left:28px;right:28px;text-align:left;font-size:12px}
.item{padding:5px 7px;border-bottom:1px solid #31404a;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.sel{outline:1px solid #00d9ec;background:#15333a}
#footer{position:absolute;bottom:17px;width:100%;font-size:11px}#readout{position:absolute;top:94px;left:0;right:0;font-size:28px;font-weight:700;color:#00d9ec}#readout small{font-size:12px;color:#b3bdc3}
#warning{color:#ffbd4a}button{font:inherit;padding:9px;margin:4px}small{display:block;color:#b3bdc3}
</style><h2>CDAPROD · Pendant</h2><small id=link>Connecting…</small>
<div id=dial><div id=title></div><div id=status></div><div id=readout></div><div id=items></div><div id=footer>BACK · HOME</div></div>
<div id=warning>View only</div><div><button id=back>Back</button><button id=home>Home</button></div>
<script>
const dial=document.querySelector('#dial'),title=document.querySelector('#title'),status=document.querySelector('#status'),readout=document.querySelector('#readout'),items=document.querySelector('#items'),link=document.querySelector('#link'),warning=document.querySelector('#warning');
let page='';let key='';let authorized=false;
function message(s){warning.textContent=s}
function send(kind,x,y){if(!authorized)return;fetch('/api/touch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,x,y})}).then(r=>{if(!r.ok)message('Input rejected ('+r.status+')')}).catch(()=>message('Connection lost'))}
document.querySelector('#back').onclick=()=>send('tap',20,210);
document.querySelector('#home').onclick=()=>send('tap',200,210);
dial.onclick=e=>{const r=dial.getBoundingClientRect(),x=Math.floor((e.clientX-r.left)*240/r.width),y=Math.floor((e.clientY-r.top)*240/r.height);send('tap',Math.max(0,Math.min(239,x)),Math.max(0,Math.min(239,y)))};
function draw(v){const m=v.ui||{},s=v.status||{};authorized=!!v.remote_navigation;
const themes={HOME:['#030708','#00d9ec'],EXPLORER:['#090704','#ffb62b'],CONFIGURATION:['#01080f','#43e8ff'],PREVIEW:['#03050b','#00d8ff']};
const t=themes[m.active_page]||themes.HOME;dial.style.background=t[0];dial.style.borderColor=t[1];title.textContent=m.title||m.screen||'Pendant';status.textContent=(m.wireless_status||s.connection||'offline')+' · '+(m.grbl_status||'')+' · '+(m.axis_selector||'OFF');items.replaceChildren();readout.hidden=m.screen!=='HOME';readout.textContent=readout.hidden?'':((m.axis_selector||'OFF')+' · '+(m.resolution_selector||''));items.hidden=!readout.hidden;
(m.items||[]).slice(0,7).forEach((item,i)=>{const el=document.createElement('div');el.className='item'+(i===m.selected?' sel':'');el.style.borderColor=i===m.selected?t[1]:'#31404a';el.textContent=item[0];items.appendChild(el)});
const overlay=m.overlay;if(overlay){message(String(overlay[0])+': '+String(overlay[1]||''))}else{message(authorized?'Remote menu navigation enabled (no CNC commands)':'View only · remote input disabled')}
link.textContent='Connected · '+(m.screen||'')+' · '+(s.connection||'');}
async function poll(){try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw Error();draw(await r.json())}catch(e){authorized=false;link.textContent='Disconnected';message('Disconnected · controls disabled')}}
async function loop(){await poll();setTimeout(loop,1200)}loop();
</script></html>"""


class PendantMirror:
    """One-client, bounded, nonblocking HTTP mirror for CircuitPython."""

    REQUEST_LIMIT = 1536
    RESPONSE_LIMIT = 8192
    SEND_CHUNK = 512
    CLIENT_TIMEOUT = 1.5

    def __init__(self, radio, app, port=8080, allow_navigation=False,
                 socket_pool=None):
        import socketpool
        import time
        self.app = app
        self.allow_navigation = bool(allow_navigation)
        self.pool = (socket_pool if socket_pool is not None else
                     socketpool.SocketPool(radio))
        self.sock = self.pool.socket()
        self.sock.setblocking(False)
        self.sock.bind(("0.0.0.0", int(port)))
        self.sock.listen(1)
        self._time = time.monotonic
        self._client = None
        self._request = bytearray(self.REQUEST_LIMIT)
        self._request_size = 0
        self._request_length = None
        self._response = None
        self._response_offset = 0
        self._client_started = 0.0
        self.completed_requests = 0
        self.client_errors = 0
        self.last_error = None

    def deinit(self):
        self._close_client()
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def _close_client(self):
        client = self._client
        self._client = None
        self._request_size = 0
        self._request_length = None
        self._response = None
        self._response_offset = 0
        if client is not None:
            try:
                client.close()
            except OSError:
                pass

    def _fail_client(self, error):
        self.client_errors += 1
        self.last_error = type(error).__name__
        self._close_client()

    def snapshot(self):
        ui = self.app.ui.view_model()
        # Redact device/network detail views; only render necessary display data.
        for field in ("details", "text", "character", "filename", "macro"):
            ui.pop(field, None)
        if ui.get("screen") == "TEXT_ENTRY":
            ui["items"] = []
        if ui.get("screen") in ("WIFI_SCAN", "JOB_BROWSER", "EXPLORER", "MACRO_BROWSER"):
            ui["items"] = []
        if ui.get("screen") in ("NETWORK_INFO", "SYSTEM_INFO", "CONTROLLER_INFO"):
            ui["items"] = []
        ui.pop("jog_armed", None)
        ui.pop("motion_available", None)
        ui["title"] = str(ui.get("title", "Pendant"))[:48]
        ui["screen"] = str(ui.get("screen", ""))[:32]
        if isinstance(ui.get("items"), list):
            ui["items"] = [
                [str(item[0])[:48]] + list(item[1:])
                for item in ui["items"][:8]
                if isinstance(item, (list, tuple)) and item
            ]
        return {"ui": ui, "remote_navigation": self.allow_navigation,
                "status": {"machine": self.app.state.machine_state,
                           "connection": self.app.state.connection_state}}

    def navigate(self, data):
        """Only allow menu taps. Never invoke app.handle_ui_event commands."""
        if not self.allow_navigation or not isinstance(data, dict):
            return False
        if data.get("kind") != "tap":
            return False
        x, y = data.get("x"), data.get("y")
        if type(x) is not int or type(y) is not int:
            return False
        if not (0 <= x < 240 and 0 <= y < 240):
            return False
        ui = self.app.ui
        if (ui.current_screen in ("HOME", "TEXT_ENTRY", "ACTIVE_JOB", "BOOT") or
                ui.confirmation or ui.state.estop_latched or
                ui.state.estop_observed or ui.state.alarm is not None):
            return False
        from src.display.ui import TouchEvent
        if ui.active_overlay() is not None:
            return False
        # Limit browser input to BACK/HOME and static submenu entry only.
        # Never call app.handle_ui_event or UIManager._select on action items.
        if y >= 190:
            ui.handle(TouchEvent("tap", x, y))
            return True
        if y < 45:
            ui.back()
            return True
        if not (58 <= y < 190):
            return False
        from src.display.navigation import menu_window_start
        items = ui.items()
        if not items:
            return False
        selected = min(ui.focus.get(ui.current_screen, 0), len(items) - 1)
        start = menu_window_start(selected, len(items), 6)
        index = start + (y - 58) // 22
        if index >= len(items) or not items[index].enabled:
            return False
        item = items[index]
        # A static screen destination is the only admissible remote selection.
        # No actions, jobs, network mutations, macros, or confirmations.
        if (not item.target or item.command is not None or
                item.target not in ui.screens or
                item.target in ("ACTIVE_JOB", "TEXT_ENTRY", "JOB_DETAILS",
                                "MACRO_DETAILS", "WIFI_SCAN")):
            return False
        ui.focus[ui.current_screen] = index
        ui.enter(item.target)
        return True

    def _make_response(self, code, body, mime):
        encoded = body.encode("utf-8")
        if len(encoded) > self.RESPONSE_LIMIT:
            code, mime = "503 Service Unavailable", "text/plain"
            encoded = b"Mirror response exceeds limit"
        header = ("HTTP/1.1 {}\r\nContent-Type: {}\r\nCache-Control: no-store\r\n"
                  "Connection: close\r\nContent-Length: {}\r\n\r\n"
                  .format(code, mime, len(encoded))).encode("utf-8")
        self._response = header + encoded
        self._response_offset = 0

    def _request_complete(self):
        view = memoryview(self._request)[:self._request_size]
        boundary = bytes(view).find(b"\r\n\r\n")
        if boundary < 0:
            return False
        if self._request_length is None:
            header = bytes(view[:boundary]).decode("utf-8")
            first = header.split("\r\n", 1)[0]
            if first.startswith("POST "):
                try:
                    self._request_length = int(next(
                        line.split(":", 1)[1].strip()
                        for line in header.split("\r\n")
                        if line.lower().startswith("content-length:")))
                except (StopIteration, ValueError):
                    self._make_response("400 Bad Request", "Bad request", "text/plain")
                    return True
                if not 1 <= self._request_length <= 256:
                    self._make_response("413 Payload Too Large", "Request too large", "text/plain")
                    return True
            else:
                self._request_length = 0
        return self._request_size >= boundary + 4 + self._request_length

    def _handle_request(self):
        request = bytes(memoryview(self._request)[:self._request_size]).decode("utf-8")
        head, _, body = request.partition("\r\n\r\n")
        first = head.split("\r\n", 1)[0]
        if first.startswith("GET /api/state "):
            body_text = json.dumps(self.snapshot())
            self._make_response("200 OK", body_text, "application/json")
        elif (first.startswith("GET / ") or first.startswith("GET /pendant ") or
              first.startswith("GET /pendant/ ")):
            self._make_response("200 OK", HTML, "text/html; charset=utf-8")
        elif first.startswith("POST /api/touch "):
            try:
                accepted = self.navigate(json.loads(body[:self._request_length]))
            except (ValueError, TypeError):
                accepted = False
            self._make_response("204 No Content" if accepted else "403 Forbidden",
                                "", "text/plain")
        else:
            self._make_response("404 Not Found", "Not found", "text/plain")

    def poll(self):
        """Advance one nonblocking socket operation; never wait for a client."""
        if self.sock is None:
            return
        now = self._time()
        if self._client is None:
            try:
                self._client, _ = self.sock.accept()
                self._client.setblocking(False)
                self._client_started = now
            except OSError:
                return
        if now - self._client_started > self.CLIENT_TIMEOUT:
            self._fail_client(TimeoutError("client deadline exceeded"))
            return
        if self._response is None:
            remaining = self.REQUEST_LIMIT - self._request_size
            if remaining <= 0:
                self._make_response("413 Payload Too Large", "Request too large", "text/plain")
            else:
                try:
                    received = self._client.recv_into(
                        memoryview(self._request)[self._request_size:])
                except OSError:
                    # Nonblocking sockets report no data and disconnects as
                    # OSError on CircuitPython; the deadline bounds retries.
                    return
                if received <= 0:
                    self._fail_client(OSError("client disconnected"))
                    return
                self._request_size += received
                try:
                    if self._request_complete():
                        if self._response is None:
                            self._handle_request()
                except (UnicodeError, ValueError, TypeError, KeyError) as exc:
                    self._make_response("400 Bad Request", "Bad request", "text/plain")
                except MemoryError as exc:
                    self.client_errors += 1
                    self.last_error = "MemoryError"
                    self._make_response("503 Service Unavailable",
                                        "Mirror temporarily unavailable", "text/plain")
        if self._response is None:
            return
        end = min(self._response_offset + self.SEND_CHUNK, len(self._response))
        try:
            sent = self._client.send(memoryview(self._response)[self._response_offset:end])
        except OSError:
            return
        if sent is None or sent <= 0:
            self._fail_client(OSError("client disconnected during response"))
            return
        self._response_offset += sent
        if self._response_offset >= len(self._response):
            self.completed_requests += 1
            self.last_error = None
            self._close_client()
