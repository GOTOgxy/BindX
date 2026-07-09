# App Hotkey Logic

杩欐槸 BindX 鍐呰仈鐨勭儹閿笟鍔℃ā鍧楋紝璐熻矗鍏ㄥ眬鐑敭瑙ｆ瀽銆佸簲鐢ㄧ獥鍙ｅ垏鎹?闅愯棌/鍚姩锛屼互鍙婄浉鍏?Win32 澶勭悊銆?

褰撳墠鐩綍涓嶅啀鍗曠嫭鎻愪緵 GUI銆佹墭鐩樺叆鍙ｆ垨鐙珛閰嶇疆鏂囦欢锛涜繍琛屼笌閰嶇疆缁熶竴鐢?BindX 涓荤▼搴忚礋璐ｃ€?

## 鍔熻兘

- 鍏ㄥ眬蹇嵎閿敞鍐岋紙RegisterHotKey锛夛紝鍚庡彴甯搁┗
- 绯荤粺鎵樼洏鍥炬爣锛屽崟鍑?鍙屽嚮鏄剧ず UI锛屽彸閿彍鍗?
- 鍐呯疆绠＄悊鐣岄潰锛坱kinter锛夛紝鏀寔娣诲姞/缂栬緫/鍒犻櫎/鍚敤/绂佺敤蹇嵎閿?
- 鏀寔褰曞埗蹇嵎閿紙鑷姩璇嗗埆淇グ閿?+ 涓婚敭锛?
- 鍏佽蹇嵎閿噸澶嶏紝閫氳繃鍚敤/绂佺敤鎺у埗
- 鍙屽嚮鍒楄〃鐩存帴鍒囨崲"鍚敤"鍜?鐑敭鍚姩"鐘舵€?
- 宸ュ叿鏍?杩愯涓?鍏ㄥ眬寮€鍏筹紝涓€閿惎鐢?绂佺敤鎵€鏈夌儹閿?
- 閰嶇疆鏂囦欢鍙€夛紝缂哄け鏃朵互绌洪厤缃惎鍔?
- 鍗曞疄渚嬭繍琛岋紙Mutex锛?
- 鏀寔寮€鏈鸿嚜鍚姩

## 鍐呯疆鏀寔鐨勫簲鐢?

### 缃戞槗浜戦煶涔?`cloudmusic`

| 鐘舵€?| 琛屼负 |
|------|------|
| 鏈惎鍔?| 涓嶅鐞?|
| 宸插惎鍔紝涓嶅湪鍓嶅彴 | 鍒囧埌鍓嶅彴 |
| 宸插湪鍓嶅彴 | 闅愯棌锛堟墭鐩樻ā寮忥級 |
| 宸插惎鍔ㄤ絾鏃犲彲瑙佺獥鍙?| 灏濊瘯鎭㈠鍒板墠鍙?|

### Zotero `zotero`

| 鐘舵€?| 琛屼负 |
|------|------|
| 鏈惎鍔?| 鍙寜閰嶇疆鍚姩 |
| 宸插惎鍔紝涓嶅湪鍓嶅彴 | 鍒囧埌鍓嶅彴 |
| 宸插湪鍓嶅彴 | 鏈€灏忓寲 + 浠庝换鍔℃爮闅愯棌 |
| 宸插惎鍔ㄤ絾鏃犲彲瑙佺獥鍙?| 灏濊瘯鎭㈠鍒板墠鍙?|

### Termius `termius`

| 鐘舵€?| 琛屼负 |
|------|------|
| 鏈惎鍔?| 鍙寜閰嶇疆鍚姩 |
| 宸插惎鍔紝涓嶅湪鍓嶅彴 | 鍒囧埌鍓嶅彴 |
| 宸插湪鍓嶅彴 | 鏈€灏忓寲 + 浠庝换鍔℃爮闅愯棌 |
| 宸插惎鍔ㄤ絾鏃犲彲瑙佺獥鍙?| 灏濊瘯鎭㈠鍒板墠鍙?|

### 鑷韩 `hot_key_manager`

缁戝畾鍚庡彲閫氳繃蹇嵎閿垏鎹㈢鐞嗙晫闈㈢殑鏄剧ず/闅愯棌銆?

### 閫氱敤搴旂敤 `generic`

鏀寔浠绘剰 Windows 搴旂敤锛屽彧闇€濉啓 exe 鍚嶇О鎴栧畨瑁呰矾寰勶紙鑷冲皯濉竴涓級銆傞€氳繃鍏滃簳閫昏緫鏌ユ壘涓荤獥鍙ｏ紙鏈夋爣棰樼殑鍙绐楀彛锛夈€?

| 閰嶇疆椤?| 蹇呭～ | 璇存槑 |
|--------|------|------|
| `exe_name` | 浜岄€変竴 | 鍙墽琛屾枃浠跺悕锛屽 `QQMusic.exe`锛堝彲浠庡畨瑁呰矾寰勮嚜鍔ㄦ彁鍙栵級 |
| `install_path` | 浜岄€変竴 | 瀹夎璺緞锛岀敤浜庡惎鍔ㄥ簲鐢?|
| `title_keyword` | 鍚?| 绐楀彛鏍囬鍏抽敭璇嶏紝鐢ㄤ簬鏇寸簿纭尮閰嶄富绐楀彛 |

## 椤圭洰缁撴瀯

| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `app.py` | 鍏ュ彛锛歮utex 鍗曞疄渚嬫鏌?+ mainloop |
| `hotkey_manager.py` | 鏍稿績閫昏緫锛歐in32 API銆丄ppController銆丠otkeyManager 鈥?**闆?tkinter** |
| `gui.py` | 鐣岄潰锛歵kinter UI銆佹墭鐩樺浘鏍囥€佸璇濇 |
| `app_hotkey_config.json` | 杩愯鏃堕厤缃紙鍙€夛級 |
| `hotkeys.bat` | 鍙屽嚮鍚姩锛坄pythonw app.py`锛?|
| `requirements.txt` | Python 渚濊禆锛堟棤绗笁鏂逛緷璧栵級 |

## 鎶€鏈灦鏋?

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?                  main thread                    鈹?
鈹?                                                 鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹? 鈹? tkinter mainloop 鈹?  鈹? tray window (HWND) 鈹?鈹?
鈹? 鈹? (message pump)   鈹?  鈹? WndProc callback    鈹?鈹?
鈹? 鈹?                  鈹?  鈹? sets flag on click  鈹?鈹?
鈹? 鈹? after(10) polls: 鈹?  鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹? 鈹? - tray events    鈹?                          鈹?
鈹? 鈹? after(20) polls: 鈹?                          鈹?
鈹? 鈹? - hotkey queue   鈹?                          鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                          鈹?
鈹?          鈹?                                     鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?
鈹? 鈹?        HotkeyManagerApp (tk.Tk)          鈹? 鈹?
鈹? 鈹? - Treeview list UI (鍙屽嚮鍒囨崲鍚敤/鍚姩)   鈹? 鈹?
鈹? 鈹? - "杩愯涓? 鍏ㄥ眬寮€鍏?                      鈹? 鈹?
鈹? 鈹? - EntryDialog (add/edit)                 鈹? 鈹?
鈹? 鈹? - HotkeyCaptureDialog (record hotkey)    鈹? 鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? 鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                       鈹?thread-safe queue
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈻尖攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?             hotkey polling thread               鈹?
鈹?                                                 鈹?
鈹? 鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹? 鈹? hidden message-only HWND                  鈹?鈹?
鈹? 鈹? - created in this thread                  鈹?鈹?
鈹? 鈹? - RegisterHotKey / UnregisterHotKey       鈹?鈹?
鈹? 鈹? - PeekMessageW(WM_HOTKEY) 鈫?queue         鈹?鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
```

### 鍏抽敭璁捐鍐崇瓥

**涓轰粈涔堢儹閿湪瀛愮嚎绋嬶紵**
- tkinter 鐨勬秷鎭惊鐜細娑堣垂鎵€鏈?Win32 娑堟伅锛堝寘鎷?WM_HOTKEY锛?
- 濡傛灉鐑敭绐楀彛鍦ㄤ富绾跨▼锛宍PeekMessageW` 鏃犳硶鑾峰彇娑堟伅
- 瀛愮嚎绋嬫嫢鏈夌嫭绔嬬殑娑堟伅寰幆鍜?HWND锛岀儹閿秷鎭笉浼氳 tkinter 鎶㈠崰

**涓轰粈涔堟墭鐩樺湪涓荤嚎绋嬶紵**
- ctypes 鐨?`WINFUNCTYPE` 鍥炶皟闇€瑕?Python GIL
- 鎵樼洏绐楀彛鐨?WndProc 鐢?tkinter 娑堟伅娉佃皟鐢紙涓荤嚎绋嬫寔鏈?GIL锛夛紝鍥炶皟瀹夊叏
- 瀛愮嚎绋嬬殑 ctypes 鍥炶皟浼氬洜 GIL 闂宕╂簝锛坄PyEval_RestoreThread` 閿欒锛?

**绾跨▼閫氫俊鏂瑰紡锛?*
- 鐑敭绾跨▼ 鈫?涓荤嚎绋嬶細`_hotkey_queue`锛坱hread-safe list + Lock锛?
- 鎵樼洏绾跨▼ 鈫?涓荤嚎绋嬶細`_tray_event` flag锛堜富绾跨▼ `after(10)` 杞璇诲彇锛?
- 涓荤嚎绋?鈫?鐑敭绾跨▼锛歚_pending_registers` / `_pending_unregisters` 闃熷垪

**浠诲姟鏍忛殣钘忥紙Zotero / Termius锛夛細**
- 閫氳繃 `SetWindowLongPtrW` 灏?`WS_EX_APPWINDOW` 鍒囨崲涓?`WS_EX_TOOLWINDOW`
- 鍚屾椂淇濆瓨/鎭㈠绐楀彛浣嶇疆锛坄GetWindowRect` / `SetWindowPos`锛?
- 绂佺敤 DWM 鍔ㄧ敾锛坄DWMWA_TRANSITIONS_FORCEDISABLED`锛夊疄鐜板嵆鏃跺垏鎹?

### 鏍稿績绫?

| 绫?| 鏂囦欢 | 鑱岃矗 |
|---|------|------|
| `AppController` | hotkey_manager.py | 搴旂敤鎺у埗閫昏緫锛氭煡鎵捐繘绋嬨€佺獥鍙ｆ縺娲?闅愯棌銆佸惎鍔ㄥ簲鐢?|
| `HotkeyManager` | hotkey_manager.py | 蹇嵎閿敓鍛藉懆鏈燂細娉ㄥ唽/娉ㄩ攢/杞/澧炲垹鏀规煡鏉＄洰 |
| `CallbackController` | hotkey_manager.py | 閫氱敤鍥炶皟鎺у埗鍣紙鐢ㄤ簬 `hot_key_manager`锛?|
| `HotkeyManagerApp` | gui.py | tkinter UI锛氬垪琛ㄥ睍绀恒€佹墭鐩樺浘鏍囥€佸璇濇 |
| `EntryDialog` | gui.py | 娣诲姞/缂栬緫鏉＄洰瀵硅瘽妗?|
| `HotkeyCaptureDialog` | gui.py | 蹇嵎閿綍鍒跺璇濇 |

### Win32 API 璋冪敤

閫氳繃 ctypes 鐩存帴璋冪敤锛屾棤绗笁鏂逛緷璧栵細

| API | 鐢ㄩ€?|
|-----|------|
| `RegisterHotKey` / `UnregisterHotKey` | 娉ㄥ唽/娉ㄩ攢鍏ㄥ眬鐑敭 |
| `PeekMessageW` | 闈為樆濉炶鍙栨秷鎭?|
| `EnumWindows` | 鏋氫妇绐楀彛鏌ユ壘鐩爣搴旂敤涓荤獥鍙?|
| `SetForegroundWindow` | 鍒囨崲鍒板墠鍙?|
| `ShowWindow` | 鏄剧ず/闅愯棌/鏈€灏忓寲绐楀彛 |
| `Shell_NotifyIconW` | 绠＄悊绯荤粺鎵樼洏鍥炬爣 |
| `DwmSetWindowAttribute` | 绂佺敤绐楀彛鍔ㄧ敾 |
| `SetWindowLongPtrW` | 淇敼绐楀彛鎵╁睍鏍峰紡锛堜换鍔℃爮闅愯棌锛?|
| `CreateToolhelp32Snapshot` | 鏋氫妇杩涚▼ |

## 閰嶇疆

閰嶇疆鏂囦欢锛歚app_hotkey_config.json`锛堝彲閫夛紝缂哄け鏃朵互绌洪厤缃惎鍔級

```json
{
  "display_name": "App Hotkey Manager",
  "mutex_name": "Global\\AppHotkeyManager",
  "entries": [
    {
      "app": "cloudmusic",
      "hotkey": "CTRL+ALT+Q",
      "launch_if_not_running": false,
      "install_path": ""
    },
    {
      "app": "zotero",
      "hotkey": "CTRL+ALT+Z",
      "launch_if_not_running": true,
      "install_path": "C:\\Program Files\\Zotero\\zotero.exe"
    },
    {
      "app": "termius",
      "hotkey": "CTRL+ALT+T",
      "launch_if_not_running": true,
      "install_path": ""
    },
    {
      "app": "hot_key_manager",
      "hotkey": "CTRL+ALT+H",
      "launch_if_not_running": false,
      "install_path": ""
    },
    {
      "app": "generic",
      "exe_name": "QQMusic.exe",
      "title_keyword": "",
      "hotkey": "CTRL+ALT+M",
      "install_path": "C:\\Program Files\\Tencent\\QQMusic\\QQMusic.exe"
    }
  ]
}
```

### 瀛楁璇存槑

| 瀛楁 | 璇存槑 |
|------|------|
| `display_name` | 杩愯鏃舵樉绀哄悕绉?|
| `mutex_name` | 鍗曞疄渚嬩簰鏂ヤ綋鍚嶇О锛屼竴鑸笉鐢ㄦ敼 |
| `entries` | 蹇嵎閿粦瀹氬垪琛?|
| `app` | 搴旂敤 ID锛歚cloudmusic`銆乣zotero`銆乣termius`銆乣hot_key_manager`銆乣generic` |
| `hotkey` | 蹇嵎閿瓧绗︿覆 |
| `enabled` | 鏄惁鍚敤锛堥粯璁?`true`锛夛紝鍙€氳繃 UI 鍒囨崲 |
| `launch_if_not_running` | 鏈惎鍔ㄦ椂鏄惁灏濊瘯鍚姩 |
| `install_path` | 瀹夎璺緞锛岀暀绌哄垯鑷姩鏌ユ壘锛堟敞鍐岃〃 App Paths 鈫?榛樿璺緞锛?|

### 蹇嵎閿啓娉?

鏍煎紡锛歚淇グ閿?淇グ閿?涓婚敭`

```text
CTRL+ALT+Q
CTRL+ALT+Z
CTRL+SHIFT+Z
ALT+F10
WIN+1
```

鏀寔鐨勪慨楗伴敭锛歚CTRL`銆乣ALT`銆乣SHIFT`銆乣WIN`

鏀寔鐨勪富閿細`A-Z`銆乣0-9`銆乣F1-F24`銆乣TAB`銆乣ESC`銆乣SPACE`銆乣ENTER`銆佹柟鍚戦敭銆乣HOME`銆乣END`銆乣PAGEUP`銆乣PAGEDOWN`銆乣INSERT`銆乣DELETE`

### install_path 鏌ユ壘椤哄簭

1. 閰嶇疆涓～鍐欑殑 `install_path`
2. Windows 娉ㄥ唽琛?`App Paths`
3. 鍐呯疆鐨勫父瑙侀粯璁ゅ畨瑁呰矾寰?

## 鏂囦欢璇存槑

| 鏂囦欢 | 浣滅敤 |
|------|------|
| `app.py` | 鍏ュ彛鏂囦欢 |
| `hotkey_manager.py` | 鏍稿績閫昏緫锛圵in32 API銆佹帶鍒跺櫒銆佺鐞嗗櫒锛?|
| `gui.py` | tkinter UI锛堜富鐣岄潰銆佸璇濇銆佹墭鐩橈級 |
| `app_hotkey_config.json` | 杩愯鏃堕厤缃?|
| `hotkeys.bat` | 鍙屽嚮鍚姩 |
| `requirements.txt` | Python 渚濊禆锛堢┖锛屾棤绗笁鏂逛緷璧栵級 |
| `README.md` | 椤圭洰鏂囨。 |

## 鐜

- Windows 10 / 11
- Python 3.10+锛坄PATH` 涓彲鐢級

## 杩愯

鍙屽嚮 `hotkeys.bat`锛屾垨鍛戒护琛屾墽琛岋細

```bat
pythonw app.py
```

- 宸﹂敭鐐瑰嚮鎵樼洏鍥炬爣锛氭樉绀虹鐞嗙晫闈?
- 鍙抽敭鐐瑰嚮鎵樼洏鍥炬爣锛氳彍鍗曪紙鏄剧ず / 閫€鍑猴級
- 鍏抽棴绐楀彛锛圶锛夛細鏈€灏忓寲鍒版墭鐩?
- 閰嶇疆 `hot_key_manager` 蹇嵎閿細鍒囨崲鐣岄潰鏄剧ず/闅愯棌


