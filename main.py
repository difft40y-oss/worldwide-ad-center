@app.get("/advertise", response_class=HTMLResponse)
async def advertise_portal(db: DBWrapper = Depends(get_db)):
    now = int(time.time())
    db.execute("DELETE FROM saved_banners WHERE expires_at < ?", (now,))
    db.commit()
    rows = db.execute("SELECT draft_id, headline, subtext, img_data, expires_at FROM saved_banners ORDER BY expires_at DESC LIMIT 8").fetchall()
    lib = "".join([f'<div style="background:#0f172a;padding:10px;border-radius:8px;margin-top:8px;border:1px solid #334155;">' + (f'<img src="{r}" style="width:100%;max-height:80px;object-fit:cover;border-radius:5px;margin-bottom:5px;">' if r else '') + f'<b>{r}</b> <span style="color:#f59e0b;font-size:11px;">({max(1,int((r-now)/3600))}h left)</span><br><small style="color:#94a3b8">{r}</small><br><button onclick="ld('{r}')" style="background:#38bdf8;border:none;padding:5px 10px;border-radius:4px;font-size:11px;font-weight:bold;margin-top:5px;">Load Draft</button></div>' for r in rows]) or '<p style="color:#94a3b8;font-size:12px;">No saved drafts yet.</p>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:18px}}.box{{background:#1e293b;padding:16px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}.tpl{{background:#0f172a;border:1px solid #14b8a6;color:#14b8a6;padding:6px 9px;border-radius:6px;font-size:11px;margin:3px}}input{{width:100%;padding:10px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:11px;background:#14b8a6;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:7px}}</style></head>
    <body><div class="box"><h3 style="margin-top:0">Templates &amp; Live Preview</h3>
    <button class="tpl" onclick="tp('Flash Sale: 50% Off!','Limited-time deals across Nepal.','Shop Now')">E-Commerce</button>
    <button class="tpl" onclick="tp('Smart App Launch','Try free for 14 days today.','Download')">App Launch</button>
    <button class="tpl" onclick="tp('Local Service Offer','Trusted quality &amp; fast booking.','Book Now')">Local Offer</button>
    <div style="background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px dashed #38bdf8;margin-top:10px;"><div id="pi"></div><h4 id="ph" style="margin:5px 0">Your Headline</h4><p id="ps" style="font-size:12px;color:#cbd5e1;margin:0 0 8px 0">Offer description</p><span id="pb" style="background:#22c55e;color:#0f172a;padding:5px 12px;border-radius:4px;font-size:12px;font-weight:bold">Learn More</span></div></div>
    <div class="box"><h3 style="margin-top:0">Banner Editor &amp; Attachment</h3>
    <input id="hl" oninput="sy()" placeholder="Headline"><input id="sub" oninput="sy()" placeholder="Description"><input id="btn" oninput="sy()" placeholder="Button Text"><input id="url" placeholder="Target URL (https://...)">
    <input type="file" accept="image/*" onchange="ri(this)" style="font-size:12px">
    <button class="btn" style="background:#38bdf8" onclick="sv()">SAVE TO 7-DAY LIBRARY</button>
    <button class="btn" onclick="sb()">SUBMIT FOR APPROVAL</button><p id="res" style="color:#22c55e;font-size:12px"></p></div>
    <div class="box"><h3 style="margin-top:0">7-Day Temporary Library</h3>{lib}</div>{FOOTER}
    <script>let im="";function sy(){{document.getElementById('ph').innerText=document.getElementById('hl').value||'Your Headline';document.getElementById('ps').innerText=document.getElementById('sub').value||'Offer description';document.getElementById('pb').innerText=document.getElementById('btn').value||'Learn More'}}
    function tp(h,s,b){{document.getElementById('hl').value=h;document.getElementById('sub').value=s;document.getElementById('btn').value=b;sy()}}
    function ri(i){{if(!i.files)return;if(i.files.size>520000){{alert('Max 500KB');return}}const r=new FileReader();r.onload=e=>{{im=e.target.result;document.getElementById('pi').innerHTML='<img src="'+im+'" style="width:100%;max-height:90px;object-fit:cover;border-radius:5px">'}};r.readAsDataURL(i.files)}}
    async function sv(){{const r=await fetch('/api/v1/save-banner-draft',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value||'Draft',subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value||'Learn More',target_url:document.getElementById('url').value,img_data:im}})}});const d=await r.json();document.getElementById('res').innerText=d.message;setTimeout(()=>location.reload(),900)}}
    async function ld(id){{const r=await fetch('/api/v1/load-banner-draft/'+id);const d=await r.json();document.getElementById('hl').value=d.headline;document.getElementById('sub').value=d.subtext;document.getElementById('btn').value=d.btn_text;document.getElementById('url').value=d.target_url;im=d.img_data||'';document.getElementById('pi').innerHTML=im?'<img src="'+im+'" style="width:100%;max-height:90px;object-fit:cover;border-radius:5px">':'';sy()}}
    async function sb(){{const r=await fetch('/api/v1/submit-advertiser',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value,subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value,target_url:document.getElementById('url').value,img_data:im}})}});const d=await r.json();document.getElementById('res').innerText=d.message}}</script></body></html>"""

@app.post("/api/v1/save-banner-draft")
async def save_banner_draft(req: CampaignReq, db: DBWrapper = Depends(get_db)):
    db.execute("INSERT INTO saved_banners (draft_id, headline, subtext, btn_text, target_url, img_data, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (f"DRF-{int(time.time()*1000)}", req.headline, req.subtext, req.btn_text, req.target_url, req.img_data, int(time.time())+604800))
    db.commit()
    return {"message": "Saved to 7-day library!"}

@app.get("/api/v1/load-banner-draft/{did}")
async def load_banner_draft(did: str, db: DBWrapper = Depends(get_db)):
    r = db.execute("SELECT headline, subtext, btn_text, target_url, img_data FROM saved_banners WHERE draft_id=?", (did,)).fetchone()
    return {"headline":r,"subtext":r,"btn_text":r,"target_url":r,"img_data":r} if r else {{}}

@app.post("/api/v1/submit-advertiser")
async def submit_advertiser(req: CampaignReq):
    send_telegram_alert(f"📢 New Advertiser Request!\n• Headline: {req.headline}\n• URL: {req.target_url}\n• Image: {'Yes' if req.img_data else 'No'}")
    return {"message": "Submitted! Admin notified via Telegram."}

@app.get("/api/v1/tag.js")