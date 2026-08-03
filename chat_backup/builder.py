#!/usr/bin/env python3
"""Rebuild chat viewer from scratch, including phone-exported WhatsApp zips."""

import os, re, shutil, sqlite3, json, zipfile, mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from html import escape

OUT = os.path.expanduser("[redacted-local-path]")
# Optionally override with env var
OUT = os.environ.get("CHAT_BACKUP_DIR", OUT)
# Build into a temp dir, then atomically swap so a failed run never wipes the viewer
OUT_TMP = OUT + ".tmp"
# Signal exports live in the project dir (Downloads is TCC-protected and gets cleaned)
SIG_BASE = os.path.expanduser("[redacted-local-path]")
SIG_TXT = os.path.join(SIG_BASE, "messages")
SIG_ATT = os.path.join(SIG_BASE, "attachments")
WA_DB = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
WA_BASE = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared")
ZIP_DIR = os.path.expanduser("[redacted-local-path]")

MIN_MSGS = 2
APPLE_EPOCH = datetime(2001, 1, 1)

shutil.rmtree(OUT_TMP, ignore_errors=True)
MEDIA = os.path.join(OUT_TMP, "media")
os.makedirs(f"{MEDIA}/signal", exist_ok=True)
os.makedirs(f"{MEDIA}/whatsapp", exist_ok=True)

def parse_ts(s):
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S"]:
        try: return datetime.strptime(s.strip(), fmt)
        except: pass
    return None

def find_wa_media(local_path):
    for sub in ["", "Message/"]:
        p = os.path.join(WA_BASE, sub, local_path)
        if os.path.exists(p):
            return p
    return None

all_convos = []

# ═══════════ SIGNAL ═══════════
if os.path.isdir(SIG_TXT):
    for fname in sorted(os.listdir(SIG_TXT)):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(SIG_TXT, fname), encoding="utf-8") as f:
            content = f.read()
        first = content.split("\n")[0]
        name = first[14:].strip() if first.startswith("Conversation: ") else fname.replace(".txt","")
        entries = []
        cur = None
        for line in content.split("\n"):
            if line.startswith("From: "):
                if cur: entries.append(cur)
                cur = {"sender": line[6:].strip(), "ts": "", "text": "", "media": [], "reactions": []}
            elif line.startswith("Sent: ") and cur:
                dt = parse_ts(line[6:])
                if dt: cur["ts"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            elif line.startswith("Reaction: ") and cur:
                m = re.match(r"(.+?) from (.+)$", line[10:])
                if m:
                    emoji, reactor = m.group(1).strip(), m.group(2).strip()
                    reactor = re.sub(r"\s*\(\+?[\d\s\-]+\)\s*$", "", reactor)
                    if reactor == "Rafael Horvat": reactor = "You"
                    if not any(r["emoji"] == emoji and r["from"] == reactor for r in cur["reactions"]):
                        cur["reactions"].append({"emoji": emoji, "from": reactor})
            elif line.startswith("Attachment: ") and cur:
                m = re.match(r"Attachment: (.+?) \((\S+),", line[12:])
                if m:
                    cur["media"].append({"name": m.group(1).strip(), "type": m.group(2)})
            elif cur and not line.startswith(("Type: ", "Received: ", "Conversation:")):
                if line.strip() == "" and not cur["text"]: continue
                cur["text"] = (cur["text"] + "\n" + line) if cur["text"] else line
        if cur: entries.append(cur)
        # Drop empty entries (no text, no media) — e.g. call/reaction placeholders
        entries = [e for e in entries if e["text"].strip() or e["media"]]
        if len(entries) < MIN_MSGS: continue
        # Strip phone number from conversation name, e.g. "Marianne Dotzer ([redacted-phone])"
        clean_name = re.sub(r"\s*\(\+?[\d\s\-]+\)\s*$", "", name).strip()
        name = clean_name or name
        safe = re.sub(r'[^\w ._-]', '_', name)[:60]
        cid = f"s_{safe}"
        att_src = os.path.join(SIG_ATT, name)
        if os.path.isdir(att_src):
            mdir = os.path.join(MEDIA, "signal", cid)
            os.makedirs(mdir, exist_ok=True)
            for af in os.listdir(att_src):
                sf = os.path.join(att_src, af)
                if os.path.isfile(sf):
                    shutil.copy2(sf, os.path.join(mdir, af))
            for e in entries:
                for m in e["media"]:
                    an = m["name"]
                    for af in os.listdir(mdir):
                        if an in af or af in an:
                            m["path"] = os.path.join("media", "signal", cid, af)
                            m["contentType"] = m.get("type", "")
                            break
        all_convos.append({"id": cid, "name": name, "source": "Signal", "entries": entries})

print(f"Signal: {len([c for c in all_convos if c['source']=='Signal'])} convos")

# ═══════════ WHATSAPP (Mac) ═══════════
if os.path.exists(WA_DB):
    conn = sqlite3.connect(WA_DB)
    conn.row_factory = sqlite3.Row
    sessions = conn.execute("""
        SELECT Z_PK, ZPARTNERNAME, ZCONTACTJID FROM ZWACHATSESSION
        WHERE ZCONTACTJID IS NULL
           OR (ZCONTACTJID NOT LIKE '%.status%'
               AND ZCONTACTJID NOT LIKE '%@status%'
               AND ZCONTACTJID NOT LIKE '%newsletter%'
               AND ZCONTACTJID NOT LIKE '%@broadcast%')
        ORDER BY ZLASTMESSAGEDATE DESC
    """).fetchall()
    for s in sessions:
        pk = s["Z_PK"]; name = s["ZPARTNERNAME"] or "Unknown"
        # Only count messages that have actual content (text or media)
        cnt = conn.execute("""
            SELECT COUNT(*) FROM ZWAMESSAGE m LEFT JOIN ZWAMEDIAITEM mi ON m.ZMEDIAITEM=mi.Z_PK
            WHERE m.ZCHATSESSION=? AND (m.ZTEXT IS NOT NULL AND m.ZTEXT != '' OR mi.Z_PK IS NOT NULL)
        """, (pk,)).fetchone()[0]
        if cnt < MIN_MSGS: continue
        safe = re.sub(r'[^\w ._-]', '_', name)[:60]
        cid = f"w_{pk}_{safe}"
        mdir = os.path.join(MEDIA, "whatsapp", cid)
        os.makedirs(mdir, exist_ok=True)
        rows = conn.execute("""
            SELECT m.ZTEXT,m.ZSENTDATE,m.ZISFROMME,m.ZPUSHNAME,m.ZFROMJID,mi.ZMEDIALOCALPATH
            FROM ZWAMESSAGE m LEFT JOIN ZWAMEDIAITEM mi ON m.ZMEDIAITEM=mi.Z_PK
            WHERE m.ZCHATSESSION=? ORDER BY m.ZSENTDATE ASC
        """, (pk,)).fetchall()
        entries = []
        for r in rows:
            sent = r["ZSENTDATE"]
            ts_str = (APPLE_EPOCH+timedelta(seconds=sent)).strftime("%Y-%m-%d %H:%M:%S") if sent else ""
            if r["ZISFROMME"]:
                sender = "You"
            else:
                # Use the conversation partner name, not the cryptic push name
                sender = name.split(" - ")[0] if " - " in name else name
            text = r["ZTEXT"] or ""
            media = []
            lp = r["ZMEDIALOCALPATH"]
            if lp:
                src = find_wa_media(lp)
                if src:
                    dst = os.path.join(mdir, os.path.basename(lp))
                    shutil.copy2(src, dst)
                    rel = os.path.join("media", "whatsapp", cid, os.path.basename(lp))
                    mime, _ = mimetypes.guess_type(lp)
                    media.append({"path": rel, "contentType": mime or ""})
            # Skip empty messages (no text, no media) — WhatsApp status/placeholder noise
            if not text and not media:
                continue
            entries.append({"ts": ts_str, "sender": sender, "text": text, "media": media})
        all_convos.append({"id": cid, "name": name, "source": "WhatsApp", "entries": entries})
    conn.close()

print(f"WhatsApp (Mac): {len([c for c in all_convos if c['source']=='WhatsApp'])} convos")

# ═══════════ WHATSAPP (iPhone Export) ═══════════
# Look for WhatsApp export zips in Downloads and iPhone-Backup folders
ZIP_DIRS = [
    os.path.expanduser("[redacted-local-path]"),
    os.path.expanduser("[redacted-local-path]"),
]
ZIP_CONFIGS = [
    ("WhatsApp Chat - Dulcesita.zip", "Dulcesita"),
    ("WhatsApp Chat - Simon Baumann.zip", "Simon Baumann"),
]

for zip_name, chat_name in ZIP_CONFIGS:
    zp = None
    for zd in ZIP_DIRS:
        candidate = os.path.join(zd, zip_name)
        if os.path.exists(candidate):
            zp = candidate
            break
    if not zp: continue
    safe = re.sub(r'[^\w ._-]', '_', chat_name)[:60]
    cid = f"wa_export_{safe}"
    mdir = os.path.join(MEDIA, "whatsapp", cid)
    os.makedirs(mdir, exist_ok=True)
    chat_content = ""
    with zipfile.ZipFile(zp) as z:
        for name in z.namelist():
            if name == "_chat.txt":
                chat_content = z.read(name).decode("utf-8", errors="replace")
            elif not name.startswith("__MACOSX") and not name.endswith("/"):
                z.extract(name, mdir)
                # Flatten if in subdirectory
                src = os.path.join(mdir, name)
                dst = os.path.join(mdir, os.path.basename(name))
                if src != dst and os.path.exists(src):
                    shutil.move(src, dst)
        # Cleanup empty dirs
        for root, dirs, files in os.walk(mdir, topdown=False):
            for d in dirs:
                dp = os.path.join(root, d)
                try: os.rmdir(dp)
                except: pass

    # Remove extracted _chat.txt
    ct_path = os.path.join(mdir, "_chat.txt")
    if os.path.exists(ct_path): os.remove(ct_path)

    entries = []
    for line in chat_content.split("\n"):
        line = line.strip().strip("\u200e\u200f\ufeff\r")
        if not line: continue
        m = re.match(r'\[(\d{2}/\d{2}/\d{4}),\s*(\d{2}:\d{2}:\d{2})\]\s*(.+?):\s*(.*)', line)
        if not m: continue
        dp, tp, sender, msg = m.groups()
        # WhatsApp exports use DD/MM/YYYY
        try:
            dt = datetime.strptime(f"{dp} {tp}", "%d/%m/%Y %H:%M:%S")
            ts = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            ts = f"{dp} {tp}"
        msg = msg.strip().lstrip("\u200e\u200f\ufeff")

        media = []
        att_m = re.search(r'<attached:\s*(.+?)>', msg)
        if att_m:
            af = att_m.group(1).strip()
            ap = os.path.join(mdir, af)
            if os.path.exists(ap):
                rel = os.path.join("media", "whatsapp", cid, af)
                mime = ""
                if af.endswith(".opus"): mime = "audio/opus"
                elif af.endswith((".jpg",".jpeg")): mime = "image/jpeg"
                elif af.endswith(".png"): mime = "image/png"
                elif af.endswith(".webp"): mime = "image/webp"
                elif af.endswith(".mp4"): mime = "video/mp4"
                media.append({"path": rel, "contentType": mime})
            msg = f"[{af}]"
        # Handle system messages (no sender)
        sender_clean = sender.strip()
        if sender_clean == "Rafael Horvat":
            sender_clean = "You"
        entries.append({"ts": ts, "sender": sender_clean, "text": msg, "media": media})

    if entries:
        all_convos.append({
            "id": cid, "name": chat_name + " (iPhone)", "source": "WhatsApp", "entries": entries
        })
        vm = sum(1 for e in entries if any("opus" in m["path"] for m in e["media"]))
        print(f"Added {chat_name} (iPhone): {len(entries)} msgs, {vm} voice msgs")

# ═══════════ MERGE iPhone exports with newer Mac messages ═══════════
# The iPhone export has the full history + all voice messages, but the Mac
# DB has newer messages. Merge: iPhone messages first, then Mac messages
# that are newer than the export's last message (dedup by ts+text).
iphone_convos = [c for c in all_convos if "(iPhone)" in c["name"]]
mac_ids_to_drop = set()
for ic in iphone_convos:
    base_name = ic["name"].replace(" (iPhone)", "")
    mac_convos = [c for c in all_convos if c["source"] == "WhatsApp" and c["name"] == base_name and "(iPhone)" not in c["name"]]
    ic["name"] = base_name
    if not mac_convos:
        continue
    mc = mac_convos[0]
    mac_ids_to_drop.add(mc["id"])
    # Find the export's newest timestamp
    export_ts = max((e["ts"] for e in ic["entries"] if e["ts"]), default="")
    # Newer Mac messages = ts after export's newest
    newer = [e for e in mc["entries"] if e["ts"] and e["ts"] > export_ts]
    # Dedup guard against same-ts overlap
    existing = {(e["ts"], e["sender"], e["text"]) for e in ic["entries"]}
    newer = [e for e in newer if (e["ts"], e["sender"], e["text"]) not in existing]
    ic["entries"].extend(newer)
all_convos = [c for c in all_convos if c["id"] not in mac_ids_to_drop]

# ═══════════ SORT by most recent message ═══════════
def latest_ts(conv):
    for e in reversed(conv["entries"]):
        if e["ts"]:
            return e["ts"]
    return ""
all_convos.sort(key=lambda c: latest_ts(c), reverse=True)

# ═══════════ HTML ═══════════
convos_json = json.dumps(all_convos, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Chat Archive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Bitter:ital,wght@0,300;0,400;1,300&display=swap" rel="stylesheet">
<style>
:root {{
  --d: #221a16; --l: #fff3e3; --g: oklch(99.12% 0.36 111.47);
  --o: oklch(75.21% 0.23 51); --p: oklch(54.56% 0.38 293.61);
  --b: oklch(65.08% 0.3 254); --e: oklch(81% 0.45 153);
  --gs: linear-gradient(135deg,var(--p),var(--o),var(--g),var(--o),var(--p));
  --sd: 0 8px 32px rgba(0,0,0,.5), 0 2px 8px rgba(0,0,0,.3);
  --np: 0 4px 24px rgba(0,0,0,.6);
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;background:var(--d);color:var(--l);font-family:'Outfit',ui-sans-serif,sans-serif;overflow:hidden}}
.app{{display:flex;height:100vh;width:100vw}}
#sb{{width:340px;min-width:340px;background:#1a1410;border-right:1px solid rgba(255,243,227,.08);display:flex;flex-direction:column;position:relative;z-index:2}}
#sb-h{{padding:20px 16px 12px;border-bottom:1px solid rgba(255,243,227,.06)}}
#sb-h h1{{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.15em;background:var(--gs);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}}
#sr{{width:100%;padding:10px 14px;border:1px solid rgba(255,243,227,.12);border-radius:12px;font-size:13px;background:rgba(255,243,227,.04);color:var(--l);outline:none;font-family:'Outfit',sans-serif;transition:border-color .2s}}
#sr:focus{{border-color:rgba(255,243,227,.3)}}
#sr::placeholder{{color:rgba(255,243,227,.25)}}
#cl{{flex:1;overflow-y:auto;padding:6px 0}}
#cl::-webkit-scrollbar{{width:4px}}
#cl::-webkit-scrollbar-thumb{{background:rgba(255,243,227,.1);border-radius:2px}}
.cv{{padding:12px 16px;cursor:pointer;display:flex;align-items:center;gap:10px;border-bottom:1px solid rgba(255,243,227,.04);transition:background .15s}}
.cv:hover{{background:rgba(255,243,227,.04)}}
.cv.a{{background:rgba(255,243,227,.06);border-left:2px solid var(--o)}}
.bg{{font-size:9px;padding:1px 5px;border-radius:3px;font-weight:500;letter-spacing:.3px;flex-shrink:0;color:rgba(255,243,227,.3);background:rgba(255,243,227,.06);border:1px solid rgba(255,243,227,.08)}}
.nn{{font-size:14px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;line-height:1.3}}
.kk{{font-size:11px;color:rgba(255,243,227,.3);flex-shrink:0;font-weight:300}}
#mn{{flex:1;display:flex;flex-direction:column;background:radial-gradient(ellipse at 50% 0%, rgba(127,0,255,.03) 0%, transparent 70%), var(--d)}}
#pl{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:rgba(255,243,227,.2);gap:12px;letter-spacing:.02em}}
#pl span:first-child{{font-size:48px;font-weight:100}}
#pl span:last-child{{font-size:13px;font-weight:300}}
#hd{{padding:14px 20px;border-bottom:1px solid rgba(255,243,227,.06);font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px;display:none;background:rgba(20,16,12,.6);backdrop-filter:blur(12px);position:relative;z-index:1}}
#hd .src{{font-size:10px;font-weight:400;color:rgba(255,243,227,.25);letter-spacing:.02em}}
#ms{{flex:1;overflow-y:auto;padding:20px 16px;display:none}}
#ms::-webkit-scrollbar{{width:4px}}
#ms::-webkit-scrollbar-thumb{{background:rgba(255,243,227,.08);border-radius:2px}}
.w{{max-width:72%;margin-bottom:3px;padding:6px 10px;border-radius:14px;position:relative;clear:both;line-height:1.35;font-size:14px;filter:drop-shadow(0 1px 3px rgba(0,0,0,.3));word-wrap:break-word;overflow-wrap:break-word;word-break:break-word;hyphens:auto}}
.w.o{{float:right;background:linear-gradient(135deg,rgba(255,127,0,.22),rgba(127,0,255,.12));border-bottom-right-radius:4px}}
.w.i{{float:left;background:rgba(255,243,227,.06);border:1px solid rgba(255,243,227,.06);border-bottom-left-radius:4px}}
.mi{{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:8px;row-gap:1px}}
.t{{font-size:14px;font-weight:350;word-wrap:break-word;overflow-wrap:break-word;letter-spacing:.01em;flex:1 1 auto;min-width:0}}
.t a{{color:var(--o);text-decoration:none;border-bottom:1px solid rgba(255,127,0,.3)}}
.t a:hover{{border-color:var(--o)}}
.ts{{font-size:9.5px;color:rgba(255,243,227,.3);font-weight:300;letter-spacing:.02em;margin-left:auto;flex:0 0 auto;align-self:flex-end}}
.rx{{display:flex;flex-wrap:wrap;gap:3px;margin-top:3px;clear:both}}
.rc{{background:rgba(255,243,227,.08);border:1px solid rgba(255,243,227,.1);border-radius:10px;padding:0 7px;font-size:12px;display:inline-flex;align-items:center;gap:4px;line-height:1.5}}
.rc .rn{{font-size:9.5px;color:rgba(255,243,227,.35)}}
.md{{margin-top:4px}}
.md video{{max-width:100%;border-radius:10px;display:block;outline:none}}
.md img{{max-width:100%;max-height:320px;border-radius:10px;cursor:pointer;display:block;transition:opacity .2s}}
.md img:hover{{opacity:.85}}
.wp{{display:flex;align-items:center;gap:8px;border-radius:10px;padding:2px 0;min-width:220px;max-width:100%}}
.wp .pp{{width:30px;height:30px;border-radius:50%;border:none;background:var(--gs);color:#221a16;font-size:12px;cursor:pointer;flex-shrink:0;font-weight:700;transition:transform .1s}}
.wp .pp:active{{transform:scale(.92)}}
.wp .wv{{flex:1;display:flex;align-items:center;gap:2px;height:32px;min-width:80px;cursor:pointer}}
.wp .wv i{{flex:1;background:rgba(255,243,227,.14);border-radius:2px;height:100%;transition:background .15s;pointer-events:none}}
.wp .wv i.on{{background:var(--o)}}
.wp .wd{{display:flex;flex-direction:column;align-items:center;gap:2px;flex-shrink:0}}
.wp .wt{{font-size:9.5px;color:rgba(255,243,227,.45);font-variant-numeric:tabular-nums}}
.wp .sp{{font-size:10px;padding:1px 6px;border-radius:6px;border:1px solid rgba(255,243,227,.25);background:transparent;color:var(--l);cursor:pointer;font-family:'Outfit',sans-serif;line-height:1.5}}
.wp .sp:hover{{border-color:var(--o);color:var(--o)}}
.dy{{text-align:center;clear:both;padding:10px 0 14px;color:rgba(255,243,227,.2);font-size:11px;font-weight:300;letter-spacing:.03em;text-transform:uppercase}}
.ldh{{text-align:center;padding:10px 0;color:rgba(255,243,227,.3);font-size:12px;font-weight:300;clear:both;animation:pulse 1.2s ease-in-out infinite}}
#lb{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.95);z-index:9999;justify-content:center;align-items:center;cursor:pointer;backdrop-filter:blur(8px)}}
#lb img{{max-width:90%;max-height:90%;border-radius:12px;box-shadow:0 20px 80px rgba(0,0,0,.8)}}
@media(max-width:768px){{#sb{{width:100%;min-width:100%;z-index:10}} #sb.c{{display:none}} #mn{{display:none}} #mn.s{{display:flex}}}}
@keyframes pulse{{0%,100%{{opacity:.35}}50%{{opacity:.9}}}}
</style>
</head>
<body>
<div class="app">
<div id="sb">
  <div id="sb-h"><h1>Chat Archive</h1><input id="sr" placeholder="Search conversations..." oninput="fl()"></div>
  <div id="cl"></div>
</div>
<div id="mn">
  <div id="pl"><span>✦</span><span>select a conversation</span></div>
  <div id="hd"></div>
  <div id="ms"></div>
</div>
</div>
<div id="lb" onclick="this.style.display='none'"><img id="lbi"></div>
<script>
const D={json.dumps(convos_json)};
const C=JSON.parse(D);
let A=null;
function es(s){{const d=document.createElement('div');d.textContent=s;return d.innerHTML}}
function lk(s){{return s.replace(/(https?:\/\/[^\s]+)/g,'<a href="$1" target="_blank">$1</a>')}}
function lb(s){{document.getElementById('lbi').src=s;document.getElementById('lb').style.display='flex'}}
function fl(){{const v=document.getElementById('sr').value.toLowerCase();const el=document.getElementById('cl');el.innerHTML=''
  C.forEach(c=>{{if(v&&!c.name.toLowerCase().includes(v))return
    const d=document.createElement('div');d.className='cv'+(c.id===A?' a':'')
    d.innerHTML='<span class="bg">'+(c.source==='Signal'?'S':'WA')+'</span><span class="nn">'+es(c.name)+'</span><span class="kk">'+c.entries.length+'</span>'
    d.onclick=()=>op(c.id);el.appendChild(d)}})}}

// ---- Simple progressive rendering ----
// On open: render the most recent 20 messages instantly, scroll to bottom.
// Then fill the rest of the conversation in the background, 150 messages
// per batch, prepending above. Native scrolling, no virtualization.
let rows=[],msEl=null,hintEl=null,fillTok=0
const BATCH=150

function msgHtml(e){{let h=''
  const tsep=e.ts?e.ts.substring(11,16):''
  if(e.text)h+='<div class="mi"><span class="t">'+lk(es(e.text))+'</span>'+(tsep?'<span class="ts">'+tsep+'</span>':'')+'</div>'
  e.media.forEach(m=>{{const p=m.path;if(!p)return
    if((m.contentType||'').startsWith('audio/')||p.match(/\.(aac|m4a|opus|mp3|wav|ogg|flac)$/i))
      h+='<div class="md"><div class="wp" data-src="'+p+'"><button class="pp">▶</button><div class="wv"></div><div class="wd"><span class="wt">0:00</span><button class="sp">1×</button></div></div></div>'
    else if((m.contentType||'').startsWith('video/')||p.match(/\.(mp4|mov|webm)$/i))
      h+='<div class="md"><video controls preload="none" src="'+p+'"></video></div>'
    else if((m.contentType||'').startsWith('image/')||p.match(/\.(jpg|jpeg|png|gif|webp|svg)$/i))
      h+='<div class="md"><img loading="lazy" src="'+p+'" onclick="event.stopPropagation();lb(this.src)"></div>'
    else h+='<div class="md"><a href="'+p+'" download style="color:var(--o);font-size:13px">'+es(p.split('/').pop())+'</a></div>'}})
  if(!e.text&&tsep)h+='<div class="mi"><span class="ts">'+tsep+'</span></div>'
  if(e.reactions&&e.reactions.length){{h+='<div class="rx">'
    e.reactions.forEach(r=>{{h+='<span class="rc">'+es(r.emoji)+(r.from&&r.from!=='You'?'<span class="rn">'+es(r.from.split(' ')[0])+'</span>':'')+'</span>'}})
    h+='</div>'}}
  return h}}
function buildRows(c){{rows=[];let ld=''
  c.entries.forEach(e=>{{const d=e.ts?e.ts.substring(0,10):''
    if(d&&d!==ld){{rows.push({{t:'day',l:d}});ld=d}}
    rows.push({{t:'msg',e:e}})}})}}
function mkRow(i){{const r=rows[i]
  let dv
  if(r.t==='day'){{dv=document.createElement('div');dv.className='dy';dv.textContent=r.l}}
  else{{dv=document.createElement('div');dv.className='w '+(r.e.sender==='You'?'o':'i');dv.innerHTML=msgHtml(r.e);dv.querySelectorAll('.wp').forEach(initWp)}}
  return dv}}
function appendRange(s,e,container){{const frag=document.createDocumentFragment()
  for(let i=s;i<=e;i++)frag.appendChild(mkRow(i))
  container.appendChild(frag)}}
function fillOlder(next,tok){{if(tok!==fillTok)return
  const el=msEl
  if(next<=0){{if(hintEl){{hintEl.remove();hintEl=null}}return}}
  const s=Math.max(0,next-BATCH)
  const prevH=el.scrollHeight
  const frag=document.createDocumentFragment()
  for(let i=s;i<next;i++)frag.appendChild(mkRow(i))
  if(hintEl&&hintEl.nextSibling)el.insertBefore(frag,hintEl.nextSibling);else el.insertBefore(frag,el.firstChild)
  // keep the user's viewport in place while content is added above
  el.scrollTop+=el.scrollHeight-prevH
  if(s<=0){{if(hintEl){{hintEl.remove();hintEl=null}}}}
  else setTimeout(()=>fillOlder(s,tok),0)}}
function op(id){{if(window.innerWidth<=768){{document.getElementById('sb').classList.add('c');document.getElementById('mn').classList.add('s')}}
  A=id;const c=C.find(x=>x.id===id);if(!c)return
  document.getElementById('pl').style.display='none';document.getElementById('hd').style.display='flex';document.getElementById('ms').style.display='block'
  document.getElementById('hd').innerHTML=es(c.name)+'<span class="src">'+(c.source==='Signal'?'Signal':'WhatsApp')+'</span>'
  const el=document.getElementById('ms')
  msEl=el;fillTok++;hintEl=null
  buildRows(c)
  el.innerHTML=''
  const n=rows.length
  if(n<=20){{appendRange(0,n-1,el);el.scrollTop=el.scrollHeight;fl();return}}
  // render only the most recent 20 first
  appendRange(n-20,n-1,el)
  hintEl=document.createElement('div');hintEl.className='ldh';hintEl.textContent='Loading older messages…'
  el.insertBefore(hintEl,el.firstChild)
  el.scrollTop=el.scrollHeight
  // When lazy images load they grow the page — snap back to bottom if the
  // user is still at (or near) the bottom
  if(!el.__vInit){{el.__vInit=1
    el.addEventListener('load',e=>{{if(e.target&&e.target.tagName==='IMG'&&msEl){{
      const t=msEl.scrollTop,sh=msEl.scrollHeight,ch=msEl.clientHeight
      if(sh-t-ch<160)msEl.scrollTop=msEl.scrollHeight}}}},true)}}
  const tok=fillTok
  setTimeout(()=>fillOlder(n-20,tok),30)
  fl()}}

// ---- Waveform player ----
const wACtx=null
function getCtx(){{if(!wACtx)window.wACtx=new (window.AudioContext||window.webkitAudioContext)();return window.wACtx}}
const fmt=s=>{{const m=Math.floor(s/60),x=Math.floor(s%60);return m+':'+String(x).padStart(2,'0')}}
// One shared observer decodes waveforms only when they scroll into view
const wpObs=new IntersectionObserver(es=>{{es.forEach(x=>{{if(x.isIntersecting){{wpObs.unobserve(x.target);decodeWp(x.target)}}}})}},{{rootMargin:'400px'}})
function decodeWp(wp){{if(wp._decoded)return;wp._decoded=true
  const src=wp.dataset.src,ctx=getCtx()
  fetch(src).then(r=>r.arrayBuffer()).then(b=>ctx.decodeAudioData(b)).then(buf=>{{
    const ch=buf.getChannelData(0),n=60,step=Math.max(1,Math.floor(ch.length/n))
    let pk=[];for(let i=0;i<n;i++){{let s=0;for(let j=i*step;j<Math.min((i+1)*step,ch.length);j++)s+=Math.abs(ch[j]);pk.push(Math.max(0.02,s/step))}}
    const mx=Math.max(...pk);wp._peaks=pk.map(v=>v/mx)
    const bars=wp.querySelector('.wv'),tm=wp.querySelector('.wt')
    if(bars)bars.innerHTML=wp._peaks.map(v=>'<i style="height:'+Math.max(15,Math.round(v*100))+'%"></i>').join('')
    if(tm)tm.textContent='0:00 / '+fmt(buf.duration||0)
  }}).catch(()=>{{}})}}
function initWp(wp){{const src=wp.dataset.src,btn=wp.querySelector('.pp'),bars=wp.querySelector('.wv'),tm=wp.querySelector('.wt'),sp=wp.querySelector('.sp')
  const au=new Audio(src);au.preload='none'
  let playing=false,dur=0
  const speeds=[1,1.5,2];let si=0
  // placeholder waveform so the player never looks broken
  bars.innerHTML=Array.from({{length:60}},(_,i)=>0.2+0.5*Math.abs(Math.sin(i*0.9))+0.25*Math.random()).map(v=>'<i style="height:'+Math.max(15,Math.round(v*100))+'%"></i>').join('')
  function seekTo(clientX){{const r=bars.getBoundingClientRect();let f=(r.width?(clientX-r.left)/r.width:0);f=Math.max(0,Math.min(1,f))
    if(au.duration&&isFinite(au.duration))au.currentTime=f*au.duration
    else if(au.seekable&&au.seekable.length)au.currentTime=f*au.seekable.end(0)}}
  let dragging=false
  bars.addEventListener('pointerdown',e=>{{dragging=true;e.preventDefault();bars.setPointerCapture(e.pointerId);seekTo(e.clientX);if(au.paused){{getCtx().resume();decodeWp(wp);au.play().catch(()=>{{}})}}}})
  bars.addEventListener('pointermove',e=>{{if(dragging)seekTo(e.clientX)}})
  bars.addEventListener('pointerup',()=>{{dragging=false}})
  btn.onclick=()=>{{if(playing){{au.pause()}}else{{getCtx().resume();decodeWp(wp);au.play()}}}}
  au.onloadedmetadata=()=>{{dur=au.duration||0;tm.textContent='0:00 / '+fmt(dur)}}
  au.ontimeupdate=()=>{{tm.textContent=fmt(au.currentTime)+' / '+fmt(dur||au.duration||0)
    const nb=(wp._peaks||[]).length||60
    if(au.duration){{const f=au.currentTime/au.duration;bars.querySelectorAll('i').forEach((el,i)=>el.classList.toggle('on',i/nb<=f))}}}}
  au.onended=()=>{{playing=false;btn.textContent='▶'}}
  au.onplay=()=>{{playing=true;btn.textContent='❚❚'}}
  au.onpause=()=>{{playing=false;btn.textContent='▶'}}
  au.onerror=()=>{{btn.textContent='!'}}
  sp.onclick=()=>{{si=(si+1)%speeds.length;au.playbackRate=speeds[si];sp.textContent=speeds[si]+'×'}}
  wpObs.observe(bars)}}
fl()
</script>
</body>
</html>"""

with open(os.path.join(OUT_TMP, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)

# Atomic swap: only replace the live viewer if the build succeeded
shutil.rmtree(OUT + ".old", ignore_errors=True)
if os.path.isdir(OUT):
    os.rename(OUT, OUT + ".old")
os.rename(OUT_TMP, OUT)
shutil.rmtree(OUT + ".old", ignore_errors=True)

# Stats
total_msgs = sum(len(c["entries"]) for c in all_convos)
audio_files = sum(1 for _ in Path(OUT).rglob("*") if _.is_file() and _.suffix.lower() in (".aac",".opus",".m4a",".mp3",".wav",".ogg",".flac"))
media_files = sum(1 for _ in Path(OUT).rglob("*") if _.is_file() and _.suffix.lower() != ".html")

print(f"\nWritten: {OUT}/index.html")
print(f"Conversations: {len(all_convos)}")
print(f"Total messages: {total_msgs}")
print(f"Audio files (voice msgs): {audio_files}")
print(f"Total media files: {media_files}")
