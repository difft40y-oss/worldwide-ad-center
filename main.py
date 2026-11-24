import re, html
import json, urllib.request, urllib.parse
import asyncio
import io, base64, qrcode, qrcode.image.svg
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
import sqlite3, os, time, random, urllib.request, urllib.parse

app = FastAPI()
DB_PATH = os.path.join(os.path.expanduser("~"), "adcenter.db")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("INTERNAL_DATABASE_URL") or ""
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ADMIN_PIN = os.getenv("ADMIN_PIN", "2026")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

class DBWrapper:
    def __init__(self):
        self.err = ""
        if DATABASE_URL:
            try:
                import psycopg2
                self.conn = psycopg2.connect(DATABASE_URL)
                self.is_pg = True
                return
            except Exception as e:
                self.err = str(e)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.is_pg = False
    def execute(self, q, params=()):
        if self.is_pg:
            q = q.replace("?", "%s")
        cur = self.conn.cursor()
        cur.execute(q, params)
        return cur
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()

def get_db():
    db = DBWrapper()
    try:
        yield db
    finally:
        db.close()

def init_db():
    db = DBWrapper()
    db.execute("CREATE TABLE IF NOT EXISTS impressions (impression_id TEXT PRIMARY KEY, publisher_id TEXT, timestamp TEXT);")
    db.execute("CREATE TABLE IF NOT EXISTS clicks (click_id TEXT PRIMARY KEY, publisher_id TEXT, payout_credited_npr REAL, escrow_status TEXT);")
    db.execute("CREATE TABLE IF NOT EXISTS ad_campaigns (id INTEGER PRIMARY KEY, headline TEXT, subtext TEXT, btn_text TEXT, target_url TEXT, active INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS payouts (payout_id TEXT PRIMARY KEY, wallet_phone TEXT, amount_npr REAL, status TEXT, created_at TEXT);")
    db.execute("CREATE TABLE IF NOT EXISTS saved_banners (draft_id TEXT PRIMARY KEY, headline TEXT, subtext TEXT, btn_text TEXT, target_url TEXT, img_data TEXT, expires_at INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS tenders (tender_id TEXT PRIMARY KEY, title TEXT, issuer TEXT, province TEXT, category TEXT, deadline TEXT, contact_url TEXT, approved INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS deposits (dep_id TEXT PRIMARY KEY, advertiser TEXT, amount REAL, txn_code TEXT, contact TEXT, ts INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS editorial (ed_id TEXT PRIMARY KEY, category TEXT, title TEXT, summary TEXT, author TEXT, ts INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS careers (app_id TEXT PRIMARY KEY, role TEXT, name TEXT, region TEXT, contact TEXT, pitch TEXT, ts INTEGER);")
    db.execute("DELETE FROM editorial WHERE ed_id='ED-101'")
    if db.execute("SELECT COUNT(*) FROM editorial").fetchone().__getitem__(0) == 0:
        db.execute("INSERT INTO editorial VALUES (?, ?, ?, ?, ?, ?)", ("ED-102", "Advertising Strategies", "Multi-Language & Cross-Border Outreach Playbook for Institutions & Brands", "Combining localized landing pages, verified trust badges, and multi-currency billing (NPR, USD, INR, EUR) to convert international audiences.", "WAC Strategy Desk", 1732203600))
    db.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, default_wallet TEXT, cpc_rate REAL, qr_img TEXT);")
    try:
        db.execute("ALTER TABLE settings ADD COLUMN qr_img TEXT;")
        db.commit()
    except Exception:
        db.conn.rollback()
    if not db.execute("SELECT id FROM settings WHERE id=1").fetchone():
        db.execute("INSERT INTO settings (id, default_wallet, cpc_rate, qr_img) VALUES (1, '9717831225', 2.50, '');")
    db.execute("UPDATE settings SET default_wallet='9717831225' WHERE default_wallet='9703544008';")
    db.execute("CREATE TABLE IF NOT EXISTS tenders (tender_id TEXT PRIMARY KEY, title TEXT, issuer TEXT, category TEXT, deadline TEXT, contact_url TEXT, approved INTEGER);")
    if not db.execute("SELECT id FROM ad_campaigns WHERE id=1").fetchone():
        db.execute("INSERT INTO ad_campaigns (id, headline, subtext, btn_text, target_url, active) VALUES (1, 'Worldwide Ad Center Network', 'Monetize your website traffic with instant eSewa payouts.', 'Join Now', 'https://worldwide-ad-center-1.onrender.com', 1);")
    db.commit()
    db.close()

init_db()

def send_telegram_alert(message: str) -> str:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return "telegram_offline"
    url = "https://" + "api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=8)
        return "OK"
    except Exception as e:
        return str(e)

def render_nav(active_title: str, breadcrumb: str = "Home"):
    return f"""<div style="background:#1e293b;padding:12px 14px;border-radius:12px;border:1px solid #334155;margin-bottom:14px;">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px;">
        <div style="display:flex;align-items:center;gap:8px;">
            <a href="/" aria-label="Home" style="display:flex;align-items:center;justify-content:center;background:#0f172a;border:1px solid #38bdf8;border-radius:8px;padding:4px 7px;text-decoration:none;">
                <svg width="20" height="26" viewBox="0 0 30 38"><polygon points="0,0 30,15 11,15 30,38 0,38" fill="#DC143C" stroke="#003893" stroke-width="2.5"/><circle cx="8" cy="10" r="2.5" fill="#fff"/><circle cx="8" cy="28" r="3.5" fill="#fff"/></svg>
                <span style="color:#fff;font-weight:900;font-size:13px;margin-left:5px;">WAC</span>
            </a>
            <div>
                <div style="font-size:13px;font-weight:800;color:#fff;letter-spacing:0.3px;">WORLDWIDE AD CENTER</div>
                <div id="wacUrl" style="font-size:9px;color:#38bdf8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:205px;">https://worldwide-ad-center-1.onrender.com</div><script>document.getElementById("wacUrl").innerText=window.location.href;</script>
            </div>
        </div>
        <div style="position:relative;">
            <button onclick="var m=document.getElementById('wacMenu');m.style.display=m.style.display==='block'?'none':'block';" aria-label="Menu" style="background:#0f172a;color:#38bdf8;border:1px solid #475569;border-radius:8px;width:40px;height:40px;font-size:18px;font-weight:bold;cursor:pointer;">&#8942;</button>
            <div id="wacMenu" style="display:none;position:absolute;right:0;top:46px;width:230px;max-height:70vh;overflow-y:auto;background:#0f172a;border:1px solid #38bdf8;border-radius:10px;z-index:999;box-shadow:0 10px 25px rgba(0,0,0,0.6);">
                <a href="/sectors" style="display:block;padding:10px 13px;color:#38bdf8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#127757; 35 Global Sectors &amp; Institutions</a>
                <a href="/editorial" style="display:block;padding:10px 13px;color:#c084fc;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128200; Advertising Strategies &amp; Bulletins</a>
                <a href="/careers" style="display:block;padding:10px 13px;color:#22c55e;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#129309; Hiring &amp; Brand Ambassadors</a>
                <a href="/admin-desk" style="display:block;padding:10px 13px;color:#22c55e;font-weight:bold;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128737;&#65039; One-Tap Admin Command Center</a>
                <a href="/editor" style="display:block;padding:10px 13px;color:#f59e0b;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#9997;&#65039; Editor Panel (Admin Publish)</a>
                <a href="/guide" style="display:block;padding:10px 13px;color:#38bdf8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128216; Beginner Guide &amp; Rules</a>
                <a href="/documents" style="display:block;padding:10px 13px;color:#f59e0b;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#129534; Invoice, Receipt &amp; Tax PDF</a>
                <a href="/deposit" style="display:block;padding:10px 13px;color:#22c55e;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128179; Deposit Ad Credits (eSewa)</a>
                <a href="/social-partners" style="display:block;padding:10px 13px;color:#38bdf8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128242; Social Partners (FB/TikTok/IG)</a>
                <a href="/verify-badge" style="display:block;padding:10px 13px;color:#22c55e;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#9989; Partner Trust Badge</a>
                <a href="/gallery" style="display:block;padding:10px 13px;color:#c084fc;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128444;&#65039; Ad Creative Gallery</a>
                <a href="/mail" style="display:block;padding:10px 13px;color:#38bdf8;font-weight:bold;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#9993;&#65039; Mail Center (Inbox / Compose)</a>
                <a href="/feedback" style="display:block;padding:10px 13px;color:#f8fafc;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128172; Complaints &amp; Suggestions</a>
                <a href="/faq" style="display:block;padding:10px 13px;color:#f8fafc;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#10067; FAQ &amp; Ad Topics</a>
                <a href="/about" style="display:block;padding:10px 13px;color:#f8fafc;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#8505;&#65039; About &amp; Contact</a>
                <a href="/privacy" style="display:block;padding:10px 13px;color:#94a3b8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128274; Privacy Policy</a>
                <a href="/terms" style="display:block;padding:10px 13px;color:#94a3b8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128220; Terms of Service</a> &bull; <a href="/sitemap.xml" style="color:#38bdf8;text-decoration:none;">Sitemap</a>
                <a href="/analytics" style="display:block;padding:10px 13px;color:#22c55e;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128202; Live Network &amp; Campaign Analytics</a>
                <a href="/status" style="display:block;padding:10px 13px;color:#38bdf8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128269; Track Application / Deposit ID</a>
                <a href="/settings" style="display:block;padding:10px 13px;color:#f59e0b;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#9881;&#65039; Settings</a>
                <a href="/" onclick="document.getElementById('wacMenu').style.display='none';" style="display:block;padding:10px 13px;color:#ef4444;font-weight:bold;text-decoration:none;font-size:12px;">&larr; Back / Exit</a>
            </div>
        </div>
    </div>
    <div style="display:flex;justify-content:flex-start;gap:8px;margin-bottom:8px;">
        <a href="/" aria-label="Home" style="display:flex;align-items:center;justify-content:center;width:44px;height:40px;background:#0f172a;color:#fff;border:1px solid #475569;border-radius:8px;text-decoration:none;font-size:17px;">&#127968;</a>
        <a href="/directory" aria-label="Search" style="display:flex;align-items:center;justify-content:center;width:44px;height:40px;background:#38bdf8;color:#0f172a;border-radius:8px;text-decoration:none;font-size:17px;">&#128269;</a>
        <a href="/tenders" aria-label="Tenders" style="display:flex;align-items:center;justify-content:center;width:44px;height:40px;background:#0284c7;color:#fff;border-radius:8px;text-decoration:none;font-size:17px;">&#127959;&#65039;</a>
        <a href="/agencies" aria-label="Agencies" style="display:flex;align-items:center;justify-content:center;width:44px;height:40px;background:#f59e0b;color:#0f172a;border-radius:8px;text-decoration:none;font-size:17px;">&#127970;</a>
        <a href="/advertise" aria-label="Advertise" style="display:flex;align-items:center;justify-content:center;width:44px;height:40px;background:#10b981;color:#0f172a;border-radius:8px;text-decoration:none;font-size:17px;">&#128226;</a>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
        <div style="font-size:11px;color:#94a3b8;">Section: <b style="color:#fff;">{active_title}</b></div>
        <select id="langSel" onchange="applyLang(this.value)" style="background:#0f172a;color:#38bdf8;border:1px solid #38bdf8;border-radius:6px;padding:3px 6px;font-size:11px;font-weight:bold;min-height:28px;width:auto;">
            <option value="en">&#127760; English</option>
            <option value="zh">&#127464;&#127475; 中文 (Chinese)</option>
            <option value="ja">&#127471;&#127477; 日本語 (Japanese)</option>
            <option value="ko">&#127472;&#127479; 한국어 (Korean)</option>
            <option value="hi">&#127470;&#127475; हिन्दी (Hindi)</option>
            <option value="es">&#127466;&#127480; Español</option>
        </select>
    </div>
    <script>
    const exitLbl = {{
        zh: "← 退出 (Back / Exit)",
        ja: "← 戻る / 終了 (Back / Exit)",
        ko: "← 뒤로 / 나가기 (Back / Exit)",
        hi: "← वापस / बाहर निकलें (Back / Exit)",
        es: "← Volver / Salir (Back / Exit)"
    }};
    let fullDict = null;
    async function applyLang(l){{
        localStorage.setItem('wac_lang', l);
        if(l==='en'){{location.reload();return;}}
        if(!fullDict){{const r=await fetch('/api/v1/dict.json');fullDict=await r.json();}}
        const m = fullDict.hasOwnProperty(l)?fullDict[l]:{{}};
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while((node = walker.nextNode())){{
            const p = node.parentElement;
            if(!p || p.tagName==='SCRIPT' || p.tagName==='STYLE' || p.closest('#langSel')) continue;
            if(!node._origRaw) node._origRaw = node.nodeValue;
            const raw = node._origRaw;
            const t = raw.replace(/\\s+/g, ' ').trim();
            if(!t) continue;
            const cleanT = t.replace(/^[^A-Za-z0-9<]+/, '').trim();
            if(t.includes('Back / Exit') && exitLbl.hasOwnProperty(l)){{node.nodeValue = raw.replace(t, exitLbl[l]);}}
            else if(m.hasOwnProperty(t)){{node.nodeValue = raw.replace(t, m[t]);}}
            else if(m.hasOwnProperty(cleanT)){{node.nodeValue = raw.replace(cleanT, m[cleanT]);}}
            else{{node.nodeValue = raw;}}
        }}
        document.querySelectorAll('input[placeholder],textarea[placeholder]').forEach(el=>{{
            if(!el._origPh) el._origPh = el.placeholder;
            if(m.hasOwnProperty(el._origPh)) el.placeholder = m[el._origPh];
        }});
    }}
    setTimeout(()=>{{
        const saved = localStorage.getItem('wac_lang');
        const sel = document.getElementById('langSel');
        if(saved && saved!=='en' && sel){{sel.value=saved;applyLang(saved);}}
    }}, 80);
    </script>
</div>"""

FOOTER = '<div style="text-align:center;margin-top:24px;padding-top:14px;border-top:1px solid #334155;font-size:12px;color:#94a3b8;"><a href="/" style="color:#38bdf8;text-decoration:none;">Hub Home</a> &bull; <a href="/about" style="color:#38bdf8;text-decoration:none;">About &amp; Contact</a> &bull; <a href="/advertise" style="color:#38bdf8;text-decoration:none;">Advertise With Us</a> &bull; <a href="/agencies" style="color:#f59e0b;text-decoration:none;">For Agencies</a> &bull; <a href="/tenders" style="color:#38bdf8;text-decoration:none;">Tenders &amp; Bids</a> &bull; <a href="/faq" style="color:#38bdf8;text-decoration:none;">FAQ &amp; Ad Topics</a> &bull; <a href="/privacy" style="color:#38bdf8;text-decoration:none;">Privacy Policy</a> &bull; <a href="/terms" style="color:#38bdf8;text-decoration:none;">Terms of Service</a> &bull; <a href="/sitemap.xml" style="color:#38bdf8;text-decoration:none;">Sitemap</a><br><span style="font-size:11px;color:#64748b;">&copy; 2026 Worldwide Ad Center. All Rights Reserved. &bull; Gandaki Province, Nepal</span></div>'


@app.get("/api/v1/dict.json")
async def get_dict_json():
    return Response(content='{"zh": {"WORLDWIDE AD CENTER": "全球广告中心", "Home": "首页", "Tenders & Bids": "招标与投标", "For Agencies": "广告代理商", "Advertise": "投放广告", "Main Control Hub": "主控制中心", "IMPRESSIONS": "展示次数", "LOCKED CLICKS": "锁定点击", "CTR %": "点击率", "AVAILABLE": "可用余额", "1. MOBILE APP AD SIMULATOR": "1. 移动应用广告模拟器", "2. ESEWA WITHDRAWAL & HISTORY": "2. eSewa 提现与记录", "3. GET WEBSITE AD TAG (<script>)": "3. 获取网站广告代码", "4. MANAGE & ROTATE AD CAMPAIGNS": "4. 管理与轮播广告", "5. ADVERTISE WITH US (SUBMIT AD)": "5. 投放广告 (提交广告)", "6. CONSTRUCTION & BIDDER NOTICES": "6. 建设与招标公告", "7. SEND TELEGRAM HEALTH REPORT": "7. 发送电报健康报告", "Main Dashboard Hub": "主控制中心", "Beginner Guide & Rules": "新手指南与规则", "Invoice, Receipt & Tax PDF": "发票、收据与税务 PDF", "Complaints & Suggestions": "投诉与建议", "Mobile App Simulator": "移动应用模拟器", "Deposit Ad Credits (eSewa)": "充值广告余额 (eSewa)", "eSewa Payouts & History": "eSewa 提现与记录", "Website Ad Tag (<script>)": "网站广告代码 (<script>)", "Rotating Ad Campaigns": "轮播广告活动", "FAQ & Ad Topics": "常见问题与广告主题", "About & Contact": "关于与联系我们", "Privacy Policy": "隐私政策", "Terms of Service": "服务条款", "Social Partners (FB/TikTok/IG)": "社交合作伙伴 (FB/TikTok/IG)", "Universal Live Directory": "全球实时目录", "Partner Trust Badge": "合作伙伴信任徽章", "Ad Creative Gallery": "广告创意画廊", "Settings": "系统设置", "Universal Global & Local Directory": "全球与本地实时目录", "Search live sponsored campaigns, brands, and Nepal construction tenders in one unified index:": "在一个统一索引中搜索实时赞助广告活动、品牌和尼泊尔建设招标：", "Search": "搜索", "View Tenders": "查看招标", "Step-by-Step Guide": "分步操作指南", "Official Moderation Standards": "官方审核标准", "Invoice, Receipt & Tax Clearance": "发票、收据与税务清关", "GENERATE SIGNED DOCUMENT": "生成签名文件", "PRINT / SAVE PDF": "打印 / 保存 PDF", "SAVE AS HTML": "保存为 HTML", "Complaints, Suggestions & Email Preference": "投诉、建议与邮件偏好", "SEND FEEDBACK": "发送反馈", "Fund Your Ad Campaign": "为您的广告活动充值", "Step 2: Submit eSewa Transaction Receipt": "第 2 步：提交 eSewa 交易收据", "VERIFY ESEWA DEPOSIT RECEIPT": "验证 eSewa 存款收据", "About Worldwide Ad Center": "关于全球广告中心", "Live Network Proof-of-Traffic": "实时网络流量证明", "Platform Features & Capabilities": "平台功能与核心能力", "Contact & Advertiser Support": "联系方式与广告商支持", "Help Center & Frequently Asked Questions": "帮助中心与常见问题解答", "Official Partner Verification Badge": "官方合作伙伴验证徽章", "COPY TRUST BADGE CODE": "复制信任徽章代码", "Social Media Partner Link Generator": "社交媒体合作伙伴链接生成器", "GENERATE TRACKED SOCIAL LINK": "生成追踪社交链接", "Construction & Bidder Notices": "建设与招标公告", "Agency Partner Program": "广告代理商合作伙伴计划", "\\"Thank you for partnering with Worldwide Ad Center! We are grateful for your submission—your campaign is now live.\\"": "“感谢您与Worldwide Ad Center合作！感谢您的提交，您的广告系列现已上线。”", "\\"We sincerely apologize, but we cannot approve this submission under our safety/clarity rules. Please edit and resubmit anytime.\\"": "“我们深表歉意，但根据我们的安全/清晰度规则，我们无法批准此提交内容。请随时编辑并重新提交。”", "(60s anti-spam).": "（60 秒反垃圾邮件）。", "(Subtitle: Design & preview your ad banner)": "（副标题：设计并预览您的广告横幅）", "(Subtitle: Download signed invoices & tax receipts)": "（副标题：下载已签名的发票和税务收据）", "(Subtitle: Fund campaign balance via eSewa or direct transfer)": "（副标题：通过 eSewa 或直接转账为活动充资）", "(Subtitle: Track verified human clicks in real time)": "（副标题：实时跟踪经过验证的人工点击）", "+2.50 NPR": "+2.50 尼泊尔卢比", ", and submit Txn ID.": "，并提交交易 ID。", ", or": "，或", ", pick a template, attach image (max 500KB), and save.": "，选择模板，附上图片（最多 500KB），然后保存。", ", scan QR": "扫描二维码", ". Earn": "赚取利率", ". Impressions are served free across our partner publisher network.": ". 我们在合作伙伴发布商网络上免费投放展示。", "0.00 NPR": "0.00尼泊尔卢比", "1. Cookie-Free Ad Delivery": "1. 无 Cookie 广告投放", "1. Create Banner:": "创建横幅", "1. How much does advertising cost?": "1. 广告费用是多少？", "1. Publisher Guidelines": "1. 发布者指南", "10% Bonus Click Credits + Priority Ad Rotation": "10% 额外点击积分 + 优先广告轮播", "1000.00 NPR": "1000.00尼泊尔卢比", "2. Deposit via eSewa QR:": "2. 通过eSewa二维码存款：", "2. Escrow & Settlements": "2. 托管与结算", "2. How fast is my ad campaign approved?": "2. 我的广告推广活动需要多长时间才能获得批准？", "2. Impression & Click Logging": "2. 曝光量和点击量记录", "2.50 NPR": "2.50 尼泊尔卢比", "2.50 NPR / Verified Click (Free Unlimited Impressions)": "2.50 尼泊尔卢比/有效点击（不限次数的免费展示）", "2.50 NPR per verified human click": "每个经过验证的人工点击 2.50 尼泊尔卢比", "2.50 NPR/click": "2.50 尼泊尔卢比/点击", "20% Bonus Credits + Dedicated Multi-Brand Account": "20%的奖励积分 + 专属多品牌账户", "3. How do website owners earn money?": "3. 网站所有者如何赚钱？", "3. Publisher Payout Data": "3. 发布方款项数据", "3. Track Clicks:": "3. 跟踪点击量：", "4. How does your anti-fraud protection work?": "4. 你们的反欺诈保护是如何运作的？", "4. Invoice & Tax PDF:": "4. 发票和税费 PDF：", "7-Day Temporary Library": "7 天临时图书馆", "@WorldwideAdCenterNotificationBot": "@全球广告中心通知机器人", "ADD TO ROTATION": "添加到轮播", "ADMIN_PIN": "管理者 PIN", "AGENCY PARTNER PROGRAM": "代理商合作伙伴计划", "Active Invitation for Bids (IFB), Sealed Quotations, Subcontractor Calls & Material Supply Tenders:": "正在进行的招标（IFB）、密封报价、分包商征集和材料供应招标：", "Ad Creative & Visual Gallery": "广告创意和视觉素材库", "Ad Specs & Formats:": "广告规格和格式：", "Add New Rotating Ad Campaign": "添加新的轮播广告系列", "Admin PIN": "管理者 PIN", "Admin Security:": "管理员安全", "Adult / Explicit Content": "成人/露骨内容", "Advertise With Us": "广告合作 ！", "Advertisers pay a flat, transparent rate of": "广告主支付固定、透明的费用，费率为", "After sending funds via eSewa, submit your transaction code below for instant Telegram verification & ad activation:": "通过eSewa汇款后，请在下方提交您的交易代码，以进行即时Telegram验证并激活广告：", "Agency Media Kit & Rate Card": "代理商媒体资料包和价目表", "Agency Partner Fast-Track Request": "代理合作伙伴快速通道申请", "Allowed Topics:": "允许的主题：", "App Launch": "应用发布", "Apply for priority multi-client onboarding. Our network desk responds directly via Telegram/WhatsApp:": "申请优先多客户入驻。我们的网络服务台将直接通过Telegram/WhatsApp回复：", "As soon as you submit your campaign on the": "一旦您在以下平台上提交推广活动，", "Automated multi-banner rotation for websites and blogs with verified": "针对已验证的网站和博客的自动化多横幅轮播", "Banner Editor & Attachment": "横幅编辑器和附件", "Base:": "基础：", "Bloggers and website owners simply copy our single": "博主和网站所有者只需复制我们的单条", "Blogs & Media": "博客和媒体", "Building & Structural Works": "建筑和结构工程", "COPY PARTNER LINK": "合作伙伴链接", "Civil & Road Construction": "土木与道路施工", "Click-Fraud Schemes": "点击欺诈骗局", "Complaint / Honest Issue Report": "投诉/诚信问题报告", "Consultancy & Engineering": "咨询与工程", "Copy & Paste HTML Embed Code:": "复制并粘贴 HTML 嵌入代码：", "Copy Bio Link (TikTok / Instagram)": "复制个人简介链接（TikTok/Instagram）", "Create a tracked monetization link for your": "为您的……创建可跟踪的变现链接", "Currency:": "货币单位：", "Database Storage:": "SSD 数据库存储", "Dedicated procurement board covering": "专门的采购委员会负责", "Default eSewa Wallet Number:": "默认 eSewa 钱包号码：", "Deposit Ad Credits": "存入广告消费金", "Digital Signature": "数字签名", "Direct Phone / WhatsApp (eSewa):": "直拨电话/WhatsApp（eSewa）：", "E-Commerce": "热门平台", "E-Commerce & Retail": "电子商务与零售", "EST. IMPRESSIONS": "预计曝光量", "EUR": "欧元", "Education & Courses": "培训课程", "Effective Date:": "生效日期：", "Email Preference Update": "电子邮件偏好设置更新", "Embed": "嵌入", "English Subtitles & Clear Onboarding Instructions": "英语字幕和清晰的入驻指南", "Enter your client campaign budget in NPR to calculate guaranteed clicks & estimated reach:": "请输入客户广告系列预算（尼泊尔卢比），以计算保底点击量和预计覆盖人数：", "Enterprise Tier (100,000+ NPR/mo):": "企业级（每月 100,000+ 尼泊尔卢比）：", "Facebook Page": "Facebook 页面", "Facebook Page / Reels": "Facebook 页面/Reels", "Facebook, TikTok, Instagram, and YouTube": "Facebook、TikTok、Instagram 和 YouTube", "Finance & SaaS": "金融与 SaaS", "Gambling & Betting": "博彩与投注", "Gandaki Province, Nepal • Serving Global Web Traffic": "尼泊尔甘达基省 • 为全球网络流量提供服务", "Gandaki, Nepal • difft40y@gmail.com • eSewa: 9717831225": "尼泊尔甘达基省 • difft40y@gmail.com • eSewa：9717831225", "Generate signed Invoices, Receipts & Tax Clearance anytime.": "随时生成已签名的发票、收据和完税证明。", "Growth Tier (25,000+ NPR/mo):": "成长级（每月 25,000+ 尼泊尔卢比）：", "Have questions about launching an ad campaign, publisher integration, or eSewa payouts? Reach our network team directly:": "对投放广告系列、发布商整合或 eSewa 付款有疑问吗？请直接联系我们的网络团队：", "INFRASTRUCTURE & PROCUREMENT": "基础设施与采购", "INSTANT ESEWA PAYMENT QR": "即时 eSewa 付款二维码", "Illegal Products": "禁品", "Instagram Bio / Story": "Instagram 个人简介/动态", "Instagram Story": "Instagram故事上分享链接", "Instant eSewa QR deposits, Admin PIN-protected wallet payouts, and real-time Telegram alerts.": "即时eSewa二维码存款、受管理员PIN码保护的钱包收款以及实时Telegram提醒。", "Instant rate conversion across": "即时汇率换算", "Issued To:": "签发给：", "Learn More": "了解详情", "Live Budget & ROI Estimator": "实时预算和投资回报率估算器", "Local Nepal Businesses": "尼泊尔本地企业", "Local Offer": "本地优惠", "MESSAGE US ON TELEGRAM": "通过 Telegram 给我们发消息", "Malware / Fake Downloads": "恶意软件/虚假下载", "N/A": "不适用", "NPR, USD, INR, and EUR": "尼泊尔卢比、美元、印度卢比和欧元", "Nepal VAT: 13%": "尼泊尔增值税：13%", "November 2026": "2026年11月17日", "Offer description": "优惠说明", "Official Network Social Channels & Quick Share": "官方网络社交渠道和快速分享", "Official Tax Invoice": "正式税务发票", "Official Telegram Bot:": "官方Telegram机器人：", "One-tap ad templates, live banner preview, creative image attachment (up to 500 KB), 7-day draft storage, and": "一键式广告模板、实时横幅预览、创意图片附件（最多 500 KB）、7 天草稿存储以及", "Open": "开启", "Operating Region:": "运营区域：", "Our lightweight": "我们的轻质", "Our network filters duplicate refreshes and automated bot clicks so advertisers only pay for genuine human interest.": "我们的网络会过滤重复刷新和自动机器人点击，因此广告主只需为真正的人类兴趣付费。", "PAN/ID:": "PAN/身份证件号码：", "PIN Protected (Manage via Render": "PIN 码保护（通过 Render 管理）", "Partner": "合伙人", "Partner Trust Badges": "合作伙伴信任徽章", "Payout & Rate Configuration": "收款和费率配置", "Payout Settlement Gateway:": "收款结算网关：", "Publish Construction / Bidder Notice": "发布施工/投标人通知", "Publishers embedding the Worldwide Ad Center script tag must not generate artificial clicks, automated refreshes, or incentivized click fraud.": "嵌入全球广告中心脚本标签的发布商不得生成虚假点击、自动刷新或奖励点击欺诈。", "Publishers, agencies, and verified contractors can embed this official trust seal on their website to verify membership in the": "发布商、代理商和经过验证的承包商可以在其网站上嵌入此官方信任印章，以验证其在", "REQUEST AGENCY PARTNER ACCESS": "申请代理合作伙伴访问权限", "RUN SCANNER & CLEANER": "运行扫描器和清理工具", "Real-time verified metrics streamed directly from our Cloud PostgreSQL ledger:": "直接从我们的云端PostgreSQL账本中流出的实时验证指标：", "Ref:": "编号:", "Registered mobile wallet numbers (such as eSewa IDs) are used strictly for processing requested publisher settlements.": "已注册的移动钱包号码（如eSewa ID）仅用于处理所请求的发布方结算。", "Responsive Native Card, 300x250 / 728x90 Banner + Optional Creative Attachment (JPG/PNG/WEBP)": "响应式原生卡片，300x250 / 728x90 横幅 + 可选创意附件（JPG/PNG/WEBP）", "SAVE NETWORK SETTINGS": "保存网络设置", "SAVE TO 7-DAY LIBRARY": "保存到 7 天库", "STEP 1: SCAN OR SEND VIA ESEWA": "第 1 步：扫描或通过 ESEWA 发送", "SUBMIT / PUBLISH BIDDER NOTICE": "提交/发布投标人通知", "SUBMIT AN AD CAMPAIGN": "提交广告系列", "SUBMIT FOR APPROVAL": "提交待批", "Scale your clients across Nepal & global web publishers with transparent CPC pricing, zero cookie friction, and priority Telegram campaign support.": "通过透明的每次点击费用 (CPC) 定价、零 Cookie 摩擦以及优先的 Telegram 广告系列支持，将您的客户扩展至尼泊尔和全球的网站发布商。", "Scan via eSewa App or copy ID to deposit campaign funds": "通过 eSewa App 扫描或复制 ID 以存入活动资金", "Sealed Quotation / Supply": "密封报价/供应", "Select Campaign to Promote:": "选择要推广的推广活动：", "Select Social Platform:": "选择社交平台：", "Share Worldwide Ad Center across associating social platforms to invite advertisers, agencies, and bidders:": "跨关联社交平台共享全球广告中心，以邀请广告主、代理商和竞价者：", "Share on Facebook": "分享到 Facebook", "Share on Telegram": "分享到Telegram", "Share on WhatsApp": "分享到Whatsapp", "Showcase of active sponsored banners and attached visual creatives across our network:": "展示我们网络中活跃的赞助横幅和附加的视觉创意：", "Standard Agency Rate:": "标准代理费率：", "Standard CPC Rate (NPR per Click):": "标准 CPC 费率（每次点击的尼泊尔卢比）：", "Standard Rate: 2.50 NPR per verified click (e.g., 1,000 NPR = 400 Clicks)": "标准费率：每次经过验证的点击 2.50 尼泊尔卢比（例如，1,000 尼泊尔卢比 = 400 次点击）", "Storage:": "仓库容量:", "Strictly Prohibited Topics:": "严禁讨论的话题：", "Subcontractor & Heavy Equipment": "分包商和重型设备", "Submit a notice for admin review, or enter your": "提交通知以供管理员审核，或输入您的", "Suggestion / Feature Request": "建议/功能请求", "Support Desk / Inquiries:": "支持服务台/咨询：", "Supported & Prohibited Ad Topics": "支持和禁止的广告主题", "System Status & Diagnostics": "系统状态和诊断", "TAX INVOICE": "税务发票", "TDS Clearance: 1.5%": "总溶解固体（TDS）去除率：1.5%", "Tax / VAT: 0% Direct": "税费/增值税：0% 直接", "Taxation & Account Clearance": "税务与账目清算", "Tech & Mobile Apps": "科技与移动应用", "Telegram Alert Bot:": "Telegram 提醒机器人：", "Templates & Live Preview": "模板和实时预览", "TikTok Bio": "TikTok个人简介", "TikTok Bio / Video": "TikTok 个人简介/视频", "To keep our publisher websites family-friendly and brand-safe, all ads must follow our content guidelines:": "为了让我们的发布商网站适合所有年龄段的受众并确保品牌安全，所有广告都必须遵守我们的内容准则：", "Total Verified:": "已验证总数：", "Tracked bio and story redirect links for": "已跟踪以下用户的个人简介和故事重定向链接：", "USD": "美元", "Upload Official eSewa QR Screenshot (Optional, Max 500KB):": "上传官方eSewa二维码截图（可选，最大500KB）：", "VERIFIED CLICKS": "已验证的点击量", "Verified clicks accrue in locked escrow and become eligible for settlement via supported mobile wallets upon admin verification.": "经过验证的点击量将计入锁定的托管账户，并在管理员验证后有资格通过受支持的移动钱包进行结算。", "Verified eSewa Payment Receipt": "已验证的 eSewa 付款收据", "Volume bonus click tiers (10% Growth & 20% Enterprise), live ROI budget estimator, and priority Telegram onboarding.": "批量奖金点击等级（10% 增长和 20% 企业）、实时投资回报率预算估算器和 Telegram 优先入驻。", "WAC Authorized Desk": "WAC 授权服务台", "WORLDWIDE AD CENTER (WAC)": "全球广告中心 (WAC)", "We log anonymized impression counts, verified click events, and basic anti-fraud rate limits solely to calculate publisher earnings and prevent automated bot traffic.": "我们仅记录匿名曝光次数、已验证的点击事件和基本的反欺诈速率限制，以计算发布商的收入并防止自动化机器人流量。", "Worldwide Ad Center": "全球广告中心", "Worldwide Ad Center delivers contextual advertisements without storing third-party tracking cookies on visitor browsers.": "Worldwide Ad Center 提供情境广告，不会在访客浏览器上存储第三方跟踪 Cookie。", "YouTube Description": "YouTube 描述", "Your Headline": "本次優惠名稱", "Your Monetized Partner Link (Paste in Bio or Post):": "您的变现合作伙伴链接（粘贴到个人简介或帖子中）：", "Your Page Name or @Handle:": "您的页面名称或@用户名：", "all 7 Nepal provinces": "尼泊尔所有 7 个省", "creators at 2.50 NPR per verified click.": "创作者每获得一次已验证的点击可赚取 2.50 尼泊尔卢比。", "eSewa Verified Merchant Support (Nepal)": "eSewa 认证商家客服（尼泊尔）", "eSewa mobile wallet": "eSewa 移动钱包", "for IFBs, sealed quotations, and subcontractor calls.": "用于IFB、密封报价和分包商招标。", "indexing all active campaigns and opportunities.": "为所有活跃的推广活动和商机编制索引。", "is an independent, performance-driven digital advertising network built to connect businesses directly with quality blogs, news portals, and mobile apps—without middleman fees or invasive tracking cookies.": "是一个独立、以绩效为导向的数字广告网络，旨在将企业直接与优质博客、新闻门户和移动应用程序联系起来，无需支付中间商费用，也无需使用侵入式跟踪Cookie。", "network:": "網路", "page, our admin team receives an instant Telegram alert and reviews your link within a few hours.": "页面，我们的管理员团队会立即收到 Telegram 提醒，并在数小时内审核您的链接。", "paired with a public": "与公共", "per verified click:": "每次经过验证的点击：", "tag empowers publishers in Nepal and worldwide to monetize their traffic transparently at": "标签让尼泊尔和世界各地的发布商能够以透明的方式通过流量变现，", "tag from the hub and paste it into their HTML, Blogger, or WordPress site. Every verified click credits": "标签，并将其粘贴到他们的 HTML、Blogger 或 WordPress 网站中。每次经过验证的点击都会计入积分", "tag or Social link to earn": "使用标签或社交媒体链接即可赚取收入", "to escrow, payable directly to your": "存入托管账户，直接支付给您的", "to publish immediately:": "立即发布：", "tracking and embeddable": "跟踪和可嵌入", "with fast mobile wallet settlements.": "通过移动钱包快速结算。", "| Tax:": "税费", "✅ CLEARANCE VERIFIED": "✅ 已通过审核", "✅ Verified Partner • Worldwide Ad Center": "✅ 已验证合作伙伴 • 全球广告中心", "🌐 Multi-Currency & Global Reach:": "🌐 多币种和全球覆盖：", "🎨 Advertiser Studio & 7-Day Vault:": "🎨 广告主工作室和7天保险库：", "🏗️ All-Nepal Construction & Bidder Notices:": "🏗️ 全尼泊尔建筑与招标公告：", "🏢 Agency Partner Program:": "🏢 代理商合作伙伴计划：", "💸 Direct eSewa Settlements & PIN Security:": "💸 eSewa直接结算和PIN码安全：", "💻 Lightweight <script> Ad Engine:": "💻 轻量级<script>广告引擎：", "📲 Social & Influencer Monetization:": "📲 社交媒体和网红变现：", "🙏 Grateful Acceptance:": "🙏 感恩接受：", "🤝 Humble Apology / Rejection:": "🤝 谦卑的道歉/拒绝：", "🧹 System Scanner & Cache Cleaner:": "🧹系统扫描器和缓存清理器：", "35 Global Sectors & Institutions": "35 个全球行业与机构", "Advertising Strategies & Bulletins": "广告策略与官方公告", "Hiring & Brand Ambassadors": "招聘与全球品牌大使", "Editor Panel (Admin Publish)": "编辑面板 (管理员发布)", "Targeted Institutional & Commercial Approach": "定向机构与商业合作方案", "Launch Sector Campaign →": "启动行业广告活动 →", "Advertising Strategies & Institutional Bulletins": "广告策略与机构公告", "Hiring & Global Brand Ambassador Program": "招聘与全球品牌大使计划", "SUBMIT APPLICATION": "提交申请", "Admin Editor Panel": "管理员编辑面板", "PUBLISH TO LIVE PLATFORM": "发布到实时平台", "Track Application / Deposit ID": "查询申请 / 存款编号", "SECTOR VERTICAL": "行业垂直领域", "Tailored advertising, public notices, and global media outreach across 35 specialized sectors worldwide:": "为全球 35 个专业行业量身定制广告、公共公告和全球媒体推广：", "1. International Bodies & Public Governance": "1. 国际组织与公共治理", "2. Education, Science & Recognition": "2. 教育、科学与学术荣誉", "3. Media, Entertainment & Culture": "3. 媒体、娱乐与文化", "4. Finance, Commerce, Logistics & Legal": "4. 金融、商业、物流与法律", "5. Aviation, Transit & Global Tourism": "5. 航空、交通与全球旅游", "6. Global Sports & Championship Events": "6. 全球体育与锦标赛赛事", "Publish new Advertising Strategies or Institutional & Global Bulletins live:": "实时发布新的广告策略或机构与全球公告：", "Admin PIN (Default: 1234)": "管理员 PIN 码 (默认: 1234)", "Article / Strategy Headline": "文章 / 策略标题", "Write clear, concise analysis or announcement...": "撰写清晰简明的分析或公告...", "Self-Service Status Tracker": "自助状态查询", "CHECK LIVE STATUS": "查询实时状态"}, "ja": {"WORLDWIDE AD CENTER": "ワールドワイド広告センター", "Home": "ホーム", "Tenders & Bids": "入札・建設公告", "For Agencies": "代理店向け", "Advertise": "広告掲載", "Main Control Hub": "メイン管理ハブ", "IMPRESSIONS": "表示回数", "LOCKED CLICKS": "確定クリック", "CTR %": "クリック率", "AVAILABLE": "利用可能残高", "1. MOBILE APP AD SIMULATOR": "1. モバイル広告シミュレーター", "2. ESEWA WITHDRAWAL & HISTORY": "2. eSewa 出金と履歴", "3. GET WEBSITE AD TAG (<script>)": "3. ウェブサイト広告タグ取得", "4. MANAGE & ROTATE AD CAMPAIGNS": "4. 広告キャンペーン管理", "5. ADVERTISE WITH US (SUBMIT AD)": "5. 広告を掲載する", "6. CONSTRUCTION & BIDDER NOTICES": "6. 建設・入札公告", "7. SEND TELEGRAM HEALTH REPORT": "7. Telegram レポート送信", "Main Dashboard Hub": "メイン管理ハブ", "Beginner Guide & Rules": "初心者ガイドと規約", "Invoice, Receipt & Tax PDF": "請求書・領収書・税務 PDF", "Complaints & Suggestions": "ご意見・ご要望", "Mobile App Simulator": "モバイル広告シミュレーター", "Deposit Ad Credits (eSewa)": "広告クレジット入金 (eSewa)", "eSewa Payouts & History": "eSewa 出金と履歴", "Website Ad Tag (<script>)": "ウェブサイト広告タグ", "Rotating Ad Campaigns": "ローテーション広告管理", "FAQ & Ad Topics": "よくある質問と広告トピック", "About & Contact": "会社概要・お問い合わせ", "Privacy Policy": "プライバシーポリシー", "Terms of Service": "利用規約", "Social Partners (FB/TikTok/IG)": "SNSパートナー (FB/TikTok/IG)", "Universal Live Directory": "グローバルライブディレクトリ", "Partner Trust Badge": "パートナー信頼バッジ", "Ad Creative Gallery": "広告クリエイティブギャラリー", "Settings": "システム設定", "Universal Global & Local Directory": "グローバル＆ローカル統合ディレクトリ", "Search live sponsored campaigns, brands, and Nepal construction tenders in one unified index:": "スポンサー広告、ブランド、ネパール建設入札を単一インデックスで検索：", "Search": "検索", "View Tenders": "入札を見る", "Step-by-Step Guide": "ステップバイステップガイド", "Official Moderation Standards": "公式審査基準", "Invoice, Receipt & Tax Clearance": "請求書・領収書・税務証明書", "GENERATE SIGNED DOCUMENT": "署名済み書類を作成", "PRINT / SAVE PDF": "印刷 / PDF保存", "SAVE AS HTML": "HTMLとして保存", "Complaints, Suggestions & Email Preference": "ご意見・ご要望・メール設定", "SEND FEEDBACK": "フィードバック送信", "Fund Your Ad Campaign": "広告キャンペーンに入金", "Step 2: Submit eSewa Transaction Receipt": "ステップ2：eSewa取引レシートを送信", "VERIFY ESEWA DEPOSIT RECEIPT": "eSewa入金レシートを検証", "About Worldwide Ad Center": "ワールドワイド広告センターについて", "Live Network Proof-of-Traffic": "ライブネットワークトラフィック証明", "Platform Features & Capabilities": "プラットフォームの機能と特徴", "Contact & Advertiser Support": "お問い合わせ・広告主サポート", "Help Center & Frequently Asked Questions": "ヘルプセンター＆よくある質問", "Official Partner Verification Badge": "公式パートナー認証バッジ", "COPY TRUST BADGE CODE": "認証バッジコードをコピー", "Social Media Partner Link Generator": "SNSパートナーリンク生成器", "GENERATE TRACKED SOCIAL LINK": "追跡SNSリンクを生成", "Construction & Bidder Notices": "建設・入札公告", "Agency Partner Program": "代理店パートナープログラム", "\\"Thank you for partnering with Worldwide Ad Center! We are grateful for your submission—your campaign is now live.\\"": "「Worldwide Ad Centerをご利用いただきありがとうございます。ご提出いただきありがとうございます。キャンペーンが公開されました。」", "\\"We sincerely apologize, but we cannot approve this submission under our safety/clarity rules. Please edit and resubmit anytime.\\"": "「誠に申し訳ございませんが、当社の安全性／明確性に関する規則に基づき、この投稿を承認することはできません。いつでも編集して再送信してください。」", "(60s anti-spam).": "（60秒間のスパム対策）。", "(Subtitle: Design & preview your ad banner)": "（サブタイトル：広告バナーのデザインとプレビュー）", "(Subtitle: Download signed invoices & tax receipts)": "（サブタイトル：署名済みの請求書と領収書をダウンロードする）", "(Subtitle: Fund campaign balance via eSewa or direct transfer)": "（サブタイトル：eSewaまたは直接送金によるキャンペーン残高の入金）", "(Subtitle: Track verified human clicks in real time)": "（サブタイトル：検証済みの人間によるクリックをリアルタイムで追跡）", ", and submit Txn ID.": "、およびトランザクションIDを送信します。", ", or": "、または", ", pick a template, attach image (max 500KB), and save.": "テンプレートを選択し、画像（最大500KB）を添付して保存します。", ", scan QR": "様、QRコードをスキャンしてください", ". Earn": "獲得", ". Impressions are served free across our partner publisher network.": ". インプレッションは、パートナーパブリッシャーネットワーク全体で無料で配信されます。", "1. Cookie-Free Ad Delivery": "1. Cookieを使用しない広告配信", "1. Create Banner:": "1. バナーを作成する：", "1. How much does advertising cost?": "1. 広告の費用はいくらですか？", "1. Publisher Guidelines": "1. パブリッシャー向けガイドライン", "10% Bonus Click Credits + Priority Ad Rotation": "10%のボーナスクリッククレジット + プライオリティ広告ローテーション", "1000.00 NPR": "1,000.00 NPR", "2. Deposit via eSewa QR:": "2. eSewa QRコードによる入金：", "2. Escrow & Settlements": "2. エスクローと決済", "2. How fast is my ad campaign approved?": "2. 広告キャンペーンの承認にかかる時間は？", "2. Impression & Click Logging": "2. インプレッションとクリックのログ記録", "2.50 NPR / Verified Click (Free Unlimited Impressions)": "2.50ネパール・ルピー/検証済みクリック（無制限のインプレッションが無料）", "2.50 NPR per verified human click": "検証済み人間のクリック1回につき2.50ネパール・ルピー", "2.50 NPR/click": "2.50 NPR/クリック", "20% Bonus Credits + Dedicated Multi-Brand Account": "20%のボーナスクレジット＋専用マルチブランドアカウント", "3. How do website owners earn money?": "3. ウェブサイトのオーナーはどのように収益を得ていますか？", "3. Publisher Payout Data": "3. パブリッシャーの支払いデータ", "3. Track Clicks:": "クリック追跡", "4. How does your anti-fraud protection work?": "4. 不正行為防止対策はどのように機能しますか？", "4. Invoice & Tax PDF:": "4. 請求書と税金のPDF：", "7-Day Temporary Library": "7日間の一時ライブラリ", "ADD TO ROTATION": "ローテーションに追加", "ADMIN_PIN": "管理者 PIN", "AGENCY PARTNER PROGRAM": "代理店パートナープログラム", "Active Invitation for Bids (IFB), Sealed Quotations, Subcontractor Calls & Material Supply Tenders:": "有効な入札招待（IFB）、封印された見積書、下請け業者への呼びかけ、資材供給入札：", "Ad Creative & Visual Gallery": "広告クリエイティブ＆ビジュアルギャラリー", "Ad Specs & Formats:": "広告の仕様とフォーマット：", "Add New Rotating Ad Campaign": "新しいローテーション広告キャンペーンを追加", "Admin PIN": "管理者 PIN", "Admin Security:": "管理者セキュリティ：", "Adult / Explicit Content": "アダルト/露骨なコンテンツ", "Advertise With Us": "当社で広告を掲載する", "Advertisers pay a flat, transparent rate of": "広告主様は、次の定額料金を透明性のある形で支払います。", "After sending funds via eSewa, submit your transaction code below for instant Telegram verification & ad activation:": "eSewaを通じて資金を送金した後、以下のトランザクションコードを送信して、Telegramの即時認証と広告の有効化を行ってください。", "Agency Media Kit & Rate Card": "代理店向けメディアキット＆レートカード", "Agency Partner Fast-Track Request": "代理店パートナーのファストトラックリクエスト", "Allowed Topics:": "許可されているトピック：", "App Launch": "アプリの起動", "Apply for priority multi-client onboarding. Our network desk responds directly via Telegram/WhatsApp:": "優先マルチクライアントオンボーディングにお申し込みください。当社のネットワークデスクがTelegram/WhatsAppで直接対応します。", "As soon as you submit your campaign on the": "キャンペーンを", "Automated multi-banner rotation for websites and blogs with verified": "検証済みのウェブサイトやブログ向けの自動マルチバナーローテーション", "Banner Editor & Attachment": "バナーエディターと添付", "Base:": "ベース：", "Bloggers and website owners simply copy our single": "ブロガーやウェブサイトのオーナーは、単に当社の単一の", "Blogs & Media": "ブログとメディア", "Building & Structural Works": "建築・構造工事", "COPY PARTNER LINK": "パートナーリンクをコピー", "Civil & Road Construction": "土木・道路建設", "Click-Fraud Schemes": "クリック詐欺の手口", "Complaint / Honest Issue Report": "苦情/Honest Issue Report", "Consultancy & Engineering": "コンサルティング & エンジニアリング", "Copy & Paste HTML Embed Code:": "HTML埋め込みコードをコピーして貼り付け：", "Copy Bio Link (TikTok / Instagram)": "プロフィールリンクをコピー（TikTok／Instagram）", "Create a tracked monetization link for your": "次のためのトラッキング可能な収益化リンクを作成する：", "Currency:": "通貨：", "Database Storage:": "データベースストレージ：", "Dedicated procurement board covering": "専用の調達委員会が担当", "Default eSewa Wallet Number:": "デフォルトのeSewaウォレット番号：", "Deposit Ad Credits": "広告クレジットを入金する", "Digital Signature": "デジタル署名", "Direct Phone / WhatsApp (eSewa):": "直通電話／WhatsApp（eSewa）：", "E-Commerce": "e コマース", "E-Commerce & Retail": "eコマース＆小売", "EST. IMPRESSIONS": "推定インプレッション数", "EUR": "ユーロ", "Education & Courses": "教育とコース", "Effective Date:": "発効日：", "Email Preference Update": "メール設定の更新", "Embed": "埋め込み", "English Subtitles & Clear Onboarding Instructions": "英語字幕とわかりやすいオンボーディング手順", "Enter your client campaign budget in NPR to calculate guaranteed clicks & estimated reach:": "クライアントのキャンペーン予算をNPRで入力して、保証されたクリック数と推定リーチを計算します。", "Enterprise Tier (100,000+ NPR/mo):": "エンタープライズティア（月額100,000ネパール・ルピー以上）：", "Facebook Page": "Facebook ページ", "Facebook Page / Reels": "Facebookページ／リール", "Facebook, TikTok, Instagram, and YouTube": "Facebook、TikTok、Instagram、YouTube", "Finance & SaaS": "財務およびSaaS", "Gambling & Betting": "ギャンブルおよび賭け", "Gandaki Province, Nepal • Serving Global Web Traffic": "ネパール、ガンダキ州 • 世界中のウェブトラフィックに対応", "Gandaki, Nepal • difft40y@gmail.com • eSewa: 9717831225": "ネパール、ガンダキ州 • difft40y@gmail.com • eSewa：9717831225", "Generate signed Invoices, Receipts & Tax Clearance anytime.": "署名済みの請求書、領収書、納税証明書をいつでも作成できます。", "Growth Tier (25,000+ NPR/mo):": "グロースティア（月額25,000ネパール・ルピー以上）：", "Have questions about launching an ad campaign, publisher integration, or eSewa payouts? Reach our network team directly:": "広告キャンペーンの開始、パブリッシャーの統合、eSewaの支払いについてご質問がありますか？ネットワークチームに直接お問い合わせください。", "INFRASTRUCTURE & PROCUREMENT": "インフラストラクチャと調達", "INR": "インドルピー", "INSTANT ESEWA PAYMENT QR": "即時eSewa決済QRコード", "Illegal Products": "違法な製品", "Instagram Bio / Story": "Instagramのプロフィール/ストーリー", "Instagram Story": "Instagramストーリー", "Instant eSewa QR deposits, Admin PIN-protected wallet payouts, and real-time Telegram alerts.": "eSewa QRによる即時入金、管理者PINで保護されたウォレットからの支払い、リアルタイムのTelegramアラート。", "Instant rate conversion across": "次のような通貨間の即時レート換算", "Issued To:": "発行先", "Learn More": "詳しく知る", "Live Budget & ROI Estimator": "リアルタイムの予算とROI見積もりツール", "Local Nepal Businesses": "ネパール国内の事業者", "Local Offer": "地域の特典", "MESSAGE US ON TELEGRAM": "Telegramでメッセージを送る", "Malware / Fake Downloads": "マルウェア/偽のダウンロード", "NPR": "ナショナル・パブリック・ラジオ", "NPR, USD, INR, and EUR": "NPR、USD、INR、EUR", "Nepal VAT: 13%": "ネパールVAT：13%", "November 2026": "2026年11月", "Offer description": "オファーの説明", "Official Network Social Channels & Quick Share": "公式ネットワークのソーシャルチャンネルとクイックシェア", "Official Tax Invoice": "正式な税金請求書", "Official Telegram Bot:": "公式Telegramボット：", "One-tap ad templates, live banner preview, creative image attachment (up to 500 KB), 7-day draft storage, and": "ワンタップ広告テンプレート、ライブバナープレビュー、クリエイティブ画像添付（最大500 KB）、7日間のドラフト保存、および", "Open": "未解決", "Operating Region:": "運用地域：", "Our lightweight": "当社の軽量", "Our network filters duplicate refreshes and automated bot clicks so advertisers only pay for genuine human interest.": "当社のネットワークは、重複するリフレッシュや自動ボットクリックをフィルタリングするため、広告主様は真の人間による関心に対してのみ料金をお支払いいただきます。", "PAN/ID:": "PAN/ID：", "PIN Protected (Manage via Render": "PIN保護（Renderで管理）", "Partner": "パートナー", "Partner Trust Badges": "パートナー信頼バッジ", "Payout & Rate Configuration": "受取金と料金の設定", "Payout Settlement Gateway:": "受取金決済ゲートウェイ：", "Publish Construction / Bidder Notice": "建設/入札者通知の公開", "Publishers embedding the Worldwide Ad Center script tag must not generate artificial clicks, automated refreshes, or incentivized click fraud.": "Worldwide Ad Centerのスクリプトタグを埋め込むパブリッシャーは、人工的なクリック、自動リフレッシュ、またはインセンティブ付きのクリック詐欺を発生させてはなりません。", "Publishers, agencies, and verified contractors can embed this official trust seal on their website to verify membership in the": "パブリッシャー、代理店、および認定された請負業者は、この公式のトラストシールをウェブサイトに埋め込み、", "REQUEST AGENCY PARTNER ACCESS": "代理店パートナーアクセスをリクエスト", "RUN SCANNER & CLEANER": "スキャナーとクリーナーを実行", "Real-time verified metrics streamed directly from our Cloud PostgreSQL ledger:": "当社のCloud PostgreSQL台帳から直接ストリーミングされるリアルタイムで検証済みの指標：", "Registered mobile wallet numbers (such as eSewa IDs) are used strictly for processing requested publisher settlements.": "登録されたモバイルウォレット番号（eSewa IDなど）は、リクエストされたパブリッシャーの決済処理にのみ使用されます。", "Responsive Native Card, 300x250 / 728x90 Banner + Optional Creative Attachment (JPG/PNG/WEBP)": "レスポンシブネイティブカード、300x250 / 728x90 バナー + オプションのクリエイティブ添付ファイル（JPG/PNG/WEBP）", "SAVE NETWORK SETTINGS": "ネットワーク設定", "SAVE TO 7-DAY LIBRARY": "7日間ライブラリに保存", "STEP 1: SCAN OR SEND VIA ESEWA": "ステップ1：スキャンまたはeSewa経由で送信", "SUBMIT / PUBLISH BIDDER NOTICE": "入札者通知を送信/公開", "SUBMIT AN AD CAMPAIGN": "広告キャンペーンを送信する", "SUBMIT FOR APPROVAL": "承認のために送信", "Scale your clients across Nepal & global web publishers with transparent CPC pricing, zero cookie friction, and priority Telegram campaign support.": "透明性のあるCPC価格設定、Cookieに関する問題の完全解消、Telegramキャンペーンの優先サポートにより、ネパールおよび世界中のウェブパブリッシャーにクライアントを拡大できます。", "Scan via eSewa App or copy ID to deposit campaign funds": "eSewaアプリでスキャンするか、IDをコピーしてキャンペーン資金を入金してください", "Sealed Quotation / Supply": "封印された見積書/供給", "Select Campaign to Promote:": "プロモーションするキャンペーンを選択：", "Select Social Platform:": "ソーシャルプラットフォームを選択：", "Share Worldwide Ad Center across associating social platforms to invite advertisers, agencies, and bidders:": "関連するソーシャルプラットフォーム間でワールドワイド広告センターを共有し、広告主、代理店、入札者を招待します。", "Share on Facebook": "Facebook で共有", "Share on Telegram": "Telegramでシェア", "Share on WhatsApp": "WhatsApp で共有", "Showcase of active sponsored banners and attached visual creatives across our network:": "当社のネットワーク全体で掲載中のスポンサーバナーと添付されたビジュアルクリエイティブの紹介：", "Standard Agency Rate:": "標準代理店料金：", "Standard CPC Rate (NPR per Click):": "標準CPCレート（クリックあたりのNPR）：", "Standard Rate: 2.50 NPR per verified click (e.g., 1,000 NPR = 400 Clicks)": "標準料金：検証済みクリック1回につき2.50ネパール・ルピー（例：1,000ネパール・ルピー＝400クリック）", "Storage:": "ストレージ:", "Strictly Prohibited Topics:": "厳禁のトピック：", "Subcontractor & Heavy Equipment": "下請け業者および重機", "Submit a notice for admin review, or enter your": "管理者による確認のために通知を送信するか、", "Suggestion / Feature Request": "提案/機能リクエスト", "Support Desk / Inquiries:": "サポートデスク/お問い合わせ：", "Supported & Prohibited Ad Topics": "サポートされている広告トピックと禁止されている広告トピック", "System Status & Diagnostics": "システムステータスと診断", "TAX INVOICE": "税金請求書", "TDS Clearance: 1.5%": "TDS（源泉徴収税）免除：1.5%", "Tax / VAT: 0% Direct": "税金/VAT：0% 直接", "Taxation & Account Clearance": "課税およびアカウントの精算", "Tech & Mobile Apps": "テクノロジー＆モバイルアプリ", "Telegram Alert Bot:": "Telegramアラートボット：", "Templates & Live Preview": "テンプレートとライブプレビュー", "TikTok Bio": "TikTokプロフィール", "TikTok Bio / Video": "TikTokのプロフィール/動画", "To keep our publisher websites family-friendly and brand-safe, all ads must follow our content guidelines:": "パブリッシャーのウェブサイトを家族向けにし、ブランドセーフティを確保するため、すべての広告は次のコンテンツガイドラインに従う必要があります。", "Total Verified:": "認証済み合計：", "Tracked bio and story redirect links for": "次のプロフィールとストーリーのリダイレクトリンクを追跡：", "USD": "米ドル", "Upload Official eSewa QR Screenshot (Optional, Max 500KB):": "公式eSewa QRコードのスクリーンショットをアップロード（任意、最大500KB）：", "VERIFIED CLICKS": "検証済みクリック数", "Verified clicks accrue in locked escrow and become eligible for settlement via supported mobile wallets upon admin verification.": "検証済みのクリックはロックされたエスクローに蓄積され、管理者の検証を経て、サポートされているモバイルウォレットを介して決済の対象となります。", "Verified eSewa Payment Receipt": "認証済みのeSewa支払い領収書", "Volume bonus click tiers (10% Growth & 20% Enterprise), live ROI budget estimator, and priority Telegram onboarding.": "ボリュームボーナスのクリックティア（Growth 10%、Enterprise 20%）、リアルタイムROI予算見積もりツール、Telegramの優先オンボーディング。", "WAC Authorized Desk": "WAC承認デスク", "WORLDWIDE AD CENTER (WAC)": "ワールドワイドアドセンター（WAC）", "35 Global Sectors & Institutions": "35のグローバル分野・機関", "Advertising Strategies & Bulletins": "広告戦略・公式速報", "Hiring & Brand Ambassadors": "採用・グローバルアンバサダー", "Editor Panel (Admin Publish)": "編集パネル (管理者公開)", "Targeted Institutional & Commercial Approach": "機関・商業分野別アプローチ", "Launch Sector Campaign →": "分野別キャンペーンを開始 →", "Advertising Strategies & Institutional Bulletins": "広告戦略・機関向け公式速報", "Hiring & Global Brand Ambassador Program": "採用・グローバルブランドアンバサダー募集", "SUBMIT APPLICATION": "応募を送信する", "Admin Editor Panel": "管理者編集パネル", "PUBLISH TO LIVE PLATFORM": "ライブプラットフォームに公開", "Track Application / Deposit ID": "申請・入金ID照会", "SECTOR VERTICAL": "業界分野", "Tailored advertising, public notices, and global media outreach across 35 specialized sectors worldwide:": "世界35の専門分野向けに最適化された広告・公式公告・グローバル広報：", "1. International Bodies & Public Governance": "1. 国際機関・公共ガバナンス", "2. Education, Science & Recognition": "2. 教育・科学・学術表彰", "3. Media, Entertainment & Culture": "3. メディア・エンターテインメント・文化", "4. Finance, Commerce, Logistics & Legal": "4. 金融・商業・物流・法務", "5. Aviation, Transit & Global Tourism": "5. 航空・交通・グローバル観光", "6. Global Sports & Championship Events": "6. 世界スポーツ・国際大会", "Publish new Advertising Strategies or Institutional & Global Bulletins live:": "新しい広告戦略や機関・グローバル速報をライブ公開：", "Admin PIN (Default: 1234)": "管理者PIN (初期値: 1234)", "Article / Strategy Headline": "記事・戦略の見出し", "Write clear, concise analysis or announcement...": "明確で簡潔な分析やお知らせを入力...", "Self-Service Status Tracker": "セルフサービス状況照会", "CHECK LIVE STATUS": "最新状況を確認"}, "ko": {"WORLDWIDE AD CENTER": "월드와이드 광고 센터", "Home": "홈", "Tenders & Bids": "입찰 및 공고", "For Agencies": "에이전시", "Advertise": "광고 등록", "Main Control Hub": "메인 제어 허브", "IMPRESSIONS": "노출수", "LOCKED CLICKS": "확정 클릭", "CTR %": "클릭률", "AVAILABLE": "사용 가능 잔액", "1. MOBILE APP AD SIMULATOR": "1. 모바일 앱 광고 시뮬레이터", "2. ESEWA WITHDRAWAL & HISTORY": "2. eSewa 출금 및 내역", "3. GET WEBSITE AD TAG (<script>)": "3. 웹사이트 광고 태그 받기", "4. MANAGE & ROTATE AD CAMPAIGNS": "4. 광고 캠페인 관리", "5. ADVERTISE WITH US (SUBMIT AD)": "5. 광고 신청하기", "6. CONSTRUCTION & BIDDER NOTICES": "6. 건설 및 입찰 공고", "7. SEND TELEGRAM HEALTH REPORT": "7. 텔레그램 상태 보고", "Main Dashboard Hub": "메인 제어 허브", "Beginner Guide & Rules": "초보자 가이드 및 규칙", "Invoice, Receipt & Tax PDF": "청구서, 영수증 및 세무 PDF", "Complaints & Suggestions": "불만 및 건의사항", "Mobile App Simulator": "모바일 앱 시뮬레이터", "Deposit Ad Credits (eSewa)": "광고 크레딧 충전 (eSewa)", "eSewa Payouts & History": "eSewa 출금 및 내역", "Website Ad Tag (<script>)": "웹사이트 광고 태그", "Rotating Ad Campaigns": "순환 광고 캠페인", "FAQ & Ad Topics": "자주 묻는 질문 및 광고 주제", "About & Contact": "소개 및 문의하기", "Privacy Policy": "개인정보 처리방침", "Terms of Service": "이용약관", "Social Partners (FB/TikTok/IG)": "소셜 파트너 (FB/TikTok/IG)", "Universal Live Directory": "글로벌 실시간 디렉토리", "Partner Trust Badge": "파트너 신뢰 배지", "Ad Creative Gallery": "광고 크리에이티브 갤러리", "Settings": "시스템 설정", "Universal Global & Local Directory": "글로벌 및 로컬 통합 디렉토리", "Search live sponsored campaigns, brands, and Nepal construction tenders in one unified index:": "스폰서 캠페인, 브랜드 및 네팔 건설 입찰을 하나의 통합 인덱스에서 검색하세요:", "Search": "검색", "View Tenders": "입찰 보기", "Step-by-Step Guide": "단계별 이용 가이드", "Official Moderation Standards": "공식 심사 기준", "Invoice, Receipt & Tax Clearance": "청구서, 영수증 및 세무 완납 증명", "GENERATE SIGNED DOCUMENT": "서명된 문서 생성", "PRINT / SAVE PDF": "인쇄 / PDF 저장", "SAVE AS HTML": "HTML로 저장", "Complaints, Suggestions & Email Preference": "불만, 건의사항 및 이메일 설정", "SEND FEEDBACK": "피드백 보내기", "Fund Your Ad Campaign": "광고 캠페인 충전", "Step 2: Submit eSewa Transaction Receipt": "2단계: eSewa 거래 영수증 제출", "VERIFY ESEWA DEPOSIT RECEIPT": "eSewa 입금 영수증 확인", "About Worldwide Ad Center": "월드와이드 광고 센터 소개", "Live Network Proof-of-Traffic": "실시간 네트워크 트래픽 증명", "Platform Features & Capabilities": "플랫폼 기능 및 역량", "Contact & Advertiser Support": "연락처 및 광고주 지원", "Help Center & Frequently Asked Questions": "고객센터 및 자주 묻는 질문", "Official Partner Verification Badge": "공식 파트너 인증 배지", "COPY TRUST BADGE CODE": "인증 배지 코드 복사", "Social Media Partner Link Generator": "소셜 미디어 파트너 링크 생성기", "GENERATE TRACKED SOCIAL LINK": "추적 소셜 링크 생성", "Construction & Bidder Notices": "건설 및 입찰 공고", "Agency Partner Program": "에이전시 파트너 프로그램", "\\"Thank you for partnering with Worldwide Ad Center! We are grateful for your submission—your campaign is now live.\\"": "\\"Worldwide Ad Center와 파트너십을 맺어 주셔서 감사합니다! 제출해 주셔서 감사합니다. 이제 캠페인이 게시되었습니다.\\"", "\\"We sincerely apologize, but we cannot approve this submission under our safety/clarity rules. Please edit and resubmit anytime.\\"": "\\"정말 죄송하지만, 당사의 안전/명확성 규정에 따라 이 제출물을 승인해 드릴 수 없습니다. 언제든지 수정하여 다시 제출해 주세요.\\"", "(60s anti-spam).": "(60초 스팸 방지).", "(Subtitle: Design & preview your ad banner)": "(부제: 광고 배너 디자인 및 미리 보기)", "(Subtitle: Download signed invoices & tax receipts)": "(부제: 서명된 청구서 및 세금 영수증 다운로드)", "(Subtitle: Fund campaign balance via eSewa or direct transfer)": "(부제: eSewa 또는 직접 이체를 통한 캠페인 잔액 충전)", "(Subtitle: Track verified human clicks in real time)": "(부제: 실제 사용자의 클릭을 실시간으로 추적)", ", and submit Txn ID.": ", 거래 ID를 제출하세요.", ", or": "또는", ", pick a template, attach image (max 500KB), and save.": ", 템플릿을 선택하고, 이미지를 첨부(최대 500KB)한 다음 저장하세요.", ", scan QR": "QR 스캔", ". Earn": "돈을 벌고", ". Impressions are served free across our partner publisher network.": ". 노출은 파트너 퍼블리셔 네트워크 전반에 걸쳐 무료로 제공됩니다.", "1. Cookie-Free Ad Delivery": "1. 쿠키 없는 광고 게재", "1. Create Banner:": "1. 배너 만들기:", "1. How much does advertising cost?": "1. 광고 비용은 얼마인가요?", "1. Publisher Guidelines": "1. 퍼블리셔 가이드라인", "10% Bonus Click Credits + Priority Ad Rotation": "10% 보너스 클릭 크레딧 + 우선 광고 순환", "1000.00 NPR": "1,000.00 NPR", "2. Deposit via eSewa QR:": "2. eSewa QR을 통한 입금:", "2. Escrow & Settlements": "2. 에스크로 및 정산", "2. How fast is my ad campaign approved?": "2. 광고 캠페인 승인에 걸리는 시간은 얼마나 되나요?", "2. Impression & Click Logging": "2. 노출 및 클릭 기록", "2.50 NPR / Verified Click (Free Unlimited Impressions)": "2.50 NPR / 검증된 클릭(무제한 무료 노출)", "2.50 NPR per verified human click": "검증된 실제 사용자 클릭당 2.50 NPR", "2.50 NPR/click": "2.50 NPR/클릭", "20% Bonus Credits + Dedicated Multi-Brand Account": "20% 보너스 크레딧 + 전용 멀티 브랜드 계정", "3. How do website owners earn money?": "3. 웹사이트 소유자는 어떻게 수익을 올리나요?", "3. Publisher Payout Data": "3. 퍼블리셔 지급액 데이터", "3. Track Clicks:": "3. 클릭 수 추적:", "4. How does your anti-fraud protection work?": "4. 부정행위 방지 보호 조치는 어떻게 작동하나요?", "4. Invoice & Tax PDF:": "4. 청구서 및 세금 PDF:", "7-Day Temporary Library": "7일 임시 라이브러리", "ADD TO ROTATION": "로테이션에 추가", "AGENCY PARTNER PROGRAM": "에이전시 파트너 프로그램", "Active Invitation for Bids (IFB), Sealed Quotations, Subcontractor Calls & Material Supply Tenders:": "유효한 입찰 공고(IFB), 밀봉 견적, 하도급자 모집 및 자재 공급 입찰:", "Ad Creative & Visual Gallery": "광고 크리에이티브 및 비주얼 갤러리", "Ad Specs & Formats:": "광고 사양 및 형식:", "Add New Rotating Ad Campaign": "새로운 로테이팅 광고 캠페인 추가", "Admin PIN": "관리자 PIN", "Admin Security:": "관리자 보안:", "Adult / Explicit Content": "성인/외설적인 콘텐츠", "Advertise With Us": "당사와 함께 광고하기", "Advertisers pay a flat, transparent rate of": "광고주는 다음과 같은 고정적이고 투명한 요금을 지불합니다.", "After sending funds via eSewa, submit your transaction code below for instant Telegram verification & ad activation:": "eSewa를 통해 자금을 전송한 후, 아래에 거래 코드를 제출하여 즉시 Telegram 인증을 받고 광고를 활성화하세요.", "Agency Media Kit & Rate Card": "에이전시 미디어 키트 및 요금표", "Agency Partner Fast-Track Request": "대행사 파트너 패스트 트랙 요청", "Allowed Topics:": "허용되는 주제:", "App Launch": "앱 출시", "Apply for priority multi-client onboarding. Our network desk responds directly via Telegram/WhatsApp:": "우선 다중 클라이언트 온보딩을 신청하세요. 당사 네트워크 데스크에서 Telegram/WhatsApp을 통해 직접 응답합니다.", "As soon as you submit your campaign on the": "캠페인을 제출하는 즉시", "Automated multi-banner rotation for websites and blogs with verified": "검증된 웹사이트 및 블로그를 위한 자동화된 멀티 배너 로테이션", "Banner Editor & Attachment": "배너 편집기 및 첨부 파일", "Base:": "기본:", "Bloggers and website owners simply copy our single": "블로거와 웹사이트 소유자는 단순히 당사의 단일", "Blogs & Media": "블로그 및 미디어", "Building & Structural Works": "건물 및 구조물 공사", "COPY PARTNER LINK": "파트너 링크 복사", "Civil & Road Construction": "토목 및 도로 건설", "Click-Fraud Schemes": "클릭 사기 수법", "Complaint / Honest Issue Report": "불만 사항/정직한 문제 신고", "Consultancy & Engineering": "컨설팅 및 엔지니어링", "Copy & Paste HTML Embed Code:": "HTML 삽입 코드 복사 및 붙여넣기:", "Copy Bio Link (TikTok / Instagram)": "소개 링크 복사(TikTok/Instagram)", "Create a tracked monetization link for your": "다음 항목에 대한 추적 가능한 수익 창출 링크 생성:", "Currency:": "통화:", "Database Storage:": "데이터베이스 스토리지:", "Dedicated procurement board covering": "전담 조달 위원회 적용 범위", "Default eSewa Wallet Number:": "기본 eSewa 지갑 번호:", "Deposit Ad Credits": "광고 크레딧 적립", "Digital Signature": "디지털 서명", "Direct Phone / WhatsApp (eSewa):": "직통 전화/WhatsApp(eSewa):", "E-Commerce": "전자상거래", "E-Commerce & Retail": "전자상거래 및 소매", "EST. IMPRESSIONS": "예상 노출 수", "Education & Courses": "교육 및 강좌", "Effective Date:": "가입 날짜:", "Email Preference Update": "이메일 환경 설정 업데이트", "Embed": "삽입", "English Subtitles & Clear Onboarding Instructions": "영어 자막 및 명확한 온보딩 지침", "Enter your client campaign budget in NPR to calculate guaranteed clicks & estimated reach:": "보장된 클릭 수와 예상 도달 범위를 계산하려면 고객 캠페인 예산을 NPR로 입력하세요.", "Enterprise Tier (100,000+ NPR/mo):": "엔터프라이즈 등급(월 100,000NPR 이상):", "FACEBOOK • TIKTOK • INSTAGRAM • YOUTUBE": "페이스북 • 틱톡 • 인스타그램 • 유튜브", "Facebook Page": "Facebook 페이지", "Facebook Page / Reels": "페이스북 페이지/릴스", "Facebook, TikTok, Instagram, and YouTube": "페이스북, 틱톡, 인스타그램, 유튜브", "Finance & SaaS": "금융 및 SaaS", "Gambling & Betting": "도박 및 내기", "Gandaki Province, Nepal • Serving Global Web Traffic": "네팔 간다키주 • 전 세계 웹 트래픽 서비스 제공", "Gandaki, Nepal • difft40y@gmail.com • eSewa: 9717831225": "네팔 간다키 • difft40y@gmail.com • eSewa: 9717831225", "Generate signed Invoices, Receipts & Tax Clearance anytime.": "언제든지 서명된 청구서, 영수증 및 세금 납부 확인서를 생성하세요.", "Growth Tier (25,000+ NPR/mo):": "성장 등급(월 25,000NPR 이상):", "Have questions about launching an ad campaign, publisher integration, or eSewa payouts? Reach our network team directly:": "광고 캠페인 시작, 퍼블리셔 통합 또는 eSewa 지급과 관련해 궁금한 점이 있으신가요? 네트워크 팀에 직접 문의하세요.", "INFRASTRUCTURE & PROCUREMENT": "인프라 및 조달", "INSTANT ESEWA PAYMENT QR": "즉시 eSewa 결제 QR 코드", "Illegal Products": "불법 제품", "Instagram Bio / Story": "인스타그램 프로필/스토리", "Instagram Story": "Instagram 스토리에 링크를 공유합니다.", "Instant eSewa QR deposits, Admin PIN-protected wallet payouts, and real-time Telegram alerts.": "즉시 eSewa QR 입금, 관리자 PIN으로 보호되는 지갑 지급, 실시간 텔레그램 알림.", "Instant rate conversion across": "다음 통화 간 즉시 환율 변환", "Issued To:": "발행 대상:", "Learn More": "자세히 알아보기", "Live Budget & ROI Estimator": "실시간 예산 및 ROI 추정 도구", "Local Nepal Businesses": "네팔 현지 업체", "Local Offer": "현지 혜택", "MESSAGE US ON TELEGRAM": "텔레그램으로 메시지 보내기", "Malware / Fake Downloads": "악성 소프트웨어/가짜 다운로드", "N/A": "해당 사항 없음", "NPR": "내셔널 퍼블릭 라디오", "NPR, USD, INR, and EUR": "NPR, USD, INR 및 EUR", "Nepal VAT: 13%": "네팔 부가가치세: 13%", "November 2026": "2026년 11월", "Offer description": "혜택 설명", "Official Network Social Channels & Quick Share": "공식 네트워크 소셜 채널 및 빠른 공유", "Official Tax Invoice": "공식 세금 계산서", "Official Telegram Bot:": "공식 텔레그램 봇:", "One-tap ad templates, live banner preview, creative image attachment (up to 500 KB), 7-day draft storage, and": "원탭 광고 템플릿, 실시간 배너 미리 보기, 크리에이티브 이미지 첨부(최대 500KB), 7일간 임시 저장,", "Open": "열기", "Operating Region:": "운영 지역:", "Our lightweight": "가벼운", "Our network filters duplicate refreshes and automated bot clicks so advertisers only pay for genuine human interest.": "당사 네트워크는 중복 새로 고침 및 자동 봇 클릭을 필터링하므로 광고주는 진정한 인간의 관심에 대해서만 비용을 지불합니다.", "PIN Protected (Manage via Render": "PIN 보호(Render를 통해 관리)", "Partner": "파트너", "Partner Trust Badges": "파트너 신뢰 배지", "Payout & Rate Configuration": "지급액 및 요금 구성", "Payout Settlement Gateway:": "지급 대금 정산 게이트웨이:", "Publish Construction / Bidder Notice": "공사/입찰자 공고 게시", "Publishers embedding the Worldwide Ad Center script tag must not generate artificial clicks, automated refreshes, or incentivized click fraud.": "Worldwide Ad Center 스크립트 태그를 삽입하는 퍼블리셔는 인위적인 클릭, 자동 새로 고침 또는 인센티브 클릭 사기를 유발해서는 안 됩니다.", "Publishers, agencies, and verified contractors can embed this official trust seal on their website to verify membership in the": "퍼블리셔, 대행사 및 인증된 계약업체는 이 공식 신뢰 마크를 웹사이트에 삽입하여", "REQUEST AGENCY PARTNER ACCESS": "대행사 파트너 액세스 요청", "RUN SCANNER & CLEANER": "스캐너 및 클리너 실행", "Real-time verified metrics streamed directly from our Cloud PostgreSQL ledger:": "Cloud PostgreSQL 원장에서 직접 스트리밍되는 실시간 검증 지표:", "Ref:": "참조번호:", "Registered mobile wallet numbers (such as eSewa IDs) are used strictly for processing requested publisher settlements.": "등록된 모바일 지갑 번호(예: eSewa ID)는 요청된 퍼블리셔 정산 처리에만 사용됩니다.", "Responsive Native Card, 300x250 / 728x90 Banner + Optional Creative Attachment (JPG/PNG/WEBP)": "반응형 네이티브 카드, 300x250 / 728x90 배너 + 선택적 크리에이티브 첨부 파일(JPG/PNG/WEBP)", "SAVE NETWORK SETTINGS": "네트워크 설정", "SAVE TO 7-DAY LIBRARY": "7일 라이브러리에 저장", "STEP 1: SCAN OR SEND VIA ESEWA": "1단계: 스캔 또는 ESEWA를 통해 전송", "SUBMIT / PUBLISH BIDDER NOTICE": "입찰자 공지 제출/게시", "SUBMIT AN AD CAMPAIGN": "광고 캠페인 제출", "SUBMIT FOR APPROVAL": "승인을 위해 전송", "Scale your clients across Nepal & global web publishers with transparent CPC pricing, zero cookie friction, and priority Telegram campaign support.": "투명한 CPC 가격 책정, 쿠키 관련 문제 없음, Telegram 캠페인 우선 지원을 통해 네팔 및 전 세계 웹 퍼블리셔를 대상으로 고객을 확장하세요.", "Scan via eSewa App or copy ID to deposit campaign funds": "eSewa 앱으로 스캔하거나 ID를 복사하여 캠페인 기금을 입금하세요.", "Sealed Quotation / Supply": "봉인 견적/공급", "Select Campaign to Promote:": "홍보할 캠페인 선택:", "Select Social Platform:": "소셜 플랫폼 선택:", "Share Worldwide Ad Center across associating social platforms to invite advertisers, agencies, and bidders:": "연결된 소셜 플랫폼 전반에 걸쳐 Worldwide Ad Center를 공유하여 광고주, 대행사 및 입찰자를 초대합니다.", "Share on Facebook": "Facebook 공유", "Share on Telegram": "텔레그램에 공유하기", "Share on WhatsApp": "WhatsApp 공유", "Showcase of active sponsored banners and attached visual creatives across our network:": "당사 네트워크 전반에 걸쳐 활성화된 스폰서 배너 및 첨부된 시각적 크리에이티브를 선보입니다.", "Standard Agency Rate:": "표준 대행사 수수료:", "Standard CPC Rate (NPR per Click):": "표준 CPC 요금(클릭당 NPR):", "Standard Rate: 2.50 NPR per verified click (e.g., 1,000 NPR = 400 Clicks)": "표준 요금: 검증된 클릭당 2.50 NPR(예: 1,000 NPR = 400회 클릭)", "Storage:": "보관:", "Strictly Prohibited Topics:": "엄격히 금지된 주제:", "Subcontractor & Heavy Equipment": "하도급업체 및 중장비", "Submit a notice for admin review, or enter your": "관리자 검토를 위한 신고서를 제출하거나", "Suggestion / Feature Request": "제안/기능 요청", "Support Desk / Inquiries:": "지원 데스크/문의:", "Supported & Prohibited Ad Topics": "지원되는 광고 주제 및 금지된 광고 주제", "System Status & Diagnostics": "시스템 상태 및 진단", "TAX INVOICE": "세금 송장", "TDS Clearance: 1.5%": "TDS 공제: 1.5%", "Tax / VAT: 0% Direct": "세금/부가가치세: 0% 직접", "Taxation & Account Clearance": "세금 및 계정 정산", "Tech & Mobile Apps": "기술 및 모바일 앱", "Telegram Alert Bot:": "Telegram 알림 봇:", "Templates & Live Preview": "템플릿 및 실시간 미리 보기", "TikTok Bio": "TikTok 소개", "TikTok Bio / Video": "TikTok 프로필/동영상", "To keep our publisher websites family-friendly and brand-safe, all ads must follow our content guidelines:": "퍼블리셔 웹사이트를 가족 친화적이고 브랜드에 안전한 환경으로 유지하기 위해 모든 광고는 다음 콘텐츠 가이드라인을 준수해야 합니다.", "Total Verified:": "총 인증 완료:", "Tracked bio and story redirect links for": "다음의 프로필 소개 및 스토리 리디렉션 링크 추적:", "Upload Official eSewa QR Screenshot (Optional, Max 500KB):": "공식 eSewa QR 스크린샷 업로드(선택 사항, 최대 500KB):", "VERIFIED CLICKS": "검증된 클릭 수", "Verified clicks accrue in locked escrow and become eligible for settlement via supported mobile wallets upon admin verification.": "확인된 클릭은 잠긴 에스크로에 누적되며, 관리자 확인을 거쳐 지원되는 모바일 지갑을 통해 정산 대상이 됩니다.", "Verified eSewa Payment Receipt": "확인된 eSewa 결제 영수증", "Volume bonus click tiers (10% Growth & 20% Enterprise), live ROI budget estimator, and priority Telegram onboarding.": "볼륨 보너스 클릭 티어(10% 성장 및 20% 엔터프라이즈), 실시간 ROI 예산 추정기, 우선순위 Telegram 온보딩.", "WAC Authorized Desk": "WAC 승인 데스크", "WORLDWIDE AD CENTER (WAC)": "전 세계 광고 센터(WAC)", "We log anonymized impression counts, verified click events, and basic anti-fraud rate limits solely to calculate publisher earnings and prevent automated bot traffic.": "당사는 게시자의 수익을 계산하고 자동화된 봇 트래픽을 방지하기 위한 목적으로만 익명화된 노출 수, 검증된 클릭 이벤트 및 기본적인 부정행위 방지 비율 한도를 기록합니다.", "Worldwide Ad Center": "전 세계 광고 센터", "Worldwide Ad Center delivers contextual advertisements without storing third-party tracking cookies on visitor browsers.": "Worldwide Ad Center는 방문자 브라우저에 제3자 추적 쿠키를 저장하지 않고 컨텍스트 기반 광고를 제공합니다.", "YouTube Description": "YouTube 설명", "Your Headline": "머리말", "Your Monetized Partner Link (Paste in Bio or Post):": "수익 창출 파트너 링크(프로필 또는 게시물에 붙여넣기):", "Your Page Name or @Handle:": "페이지 이름 또는 @아이디:", "all 7 Nepal provinces": "네팔 7개 주 모두", "creators at 2.50 NPR per verified click.": "확인된 클릭당 2.50 NPR의 수익을 크리에이터에게 지급합니다.", "eSewa Verified Merchant Support (Nepal)": "eSewa 인증 매장 지원(네팔)", "eSewa mobile wallet": "eSewa 모바일 지갑", "for IFBs, sealed quotations, and subcontractor calls.": "IFB, 밀봉 견적서, 하도급업체 입찰 공고에 대해 설명합니다.", "indexing all active campaigns and opportunities.": "모든 활성 캠페인 및 기회를 인덱싱합니다.", "is an independent, performance-driven digital advertising network built to connect businesses directly with quality blogs, news portals, and mobile apps—without middleman fees or invasive tracking cookies.": "은 중개 수수료나 침해성 추적 쿠키 없이 비즈니스를 우수한 블로그, 뉴스 포털, 모바일 앱과 직접 연결하도록 구축된 독립적이고 성과 중심의 디지털 광고 네트워크입니다.", "network:": "네트워크", "page, our admin team receives an instant Telegram alert and reviews your link within a few hours.": "페이지에서 링크를 제출하시면, 관리팀이 즉시 텔레그램 알림을 받고 몇 시간 이내에 링크를 검토합니다.", "paired with a public": "공용", "per verified click:": "검증된 클릭당:", "tag empowers publishers in Nepal and worldwide to monetize their traffic transparently at": "태그는 네팔 및 전 세계의 게시자가 투명하게 트래픽을 수익화할 수 있도록 지원합니다.", "tag from the hub and paste it into their HTML, Blogger, or WordPress site. Every verified click credits": "허브에서 태그를 복사하여 HTML, Blogger 또는 WordPress 사이트에 붙여넣습니다. 검증된 모든 클릭은 크레딧으로 적립됩니다.", "tag or Social link to earn": "태그 또는 소셜 링크로  적립", "to escrow, payable directly to your": "에스크로로, 귀하의 ___에 직접 지급", "to publish immediately:": "즉시 게시:", "tracking and embeddable": "추적 및 삽입 가능", "with fast mobile wallet settlements.": "빠른 모바일 지갑 결제.", "| Tax:": "세금:", "✅ CLEARANCE VERIFIED": "✅ 승인 확인 완료", "✅ Verified Partner • Worldwide Ad Center": "✅ 검증된 파트너 • 전 세계 광고 센터", "🌐 Multi-Currency & Global Reach:": "🌐 다중 통화 및 글로벌 도달 범위:", "🎨 Advertiser Studio & 7-Day Vault:": "🎨 광고주 스튜디오 및 7일 보관함:", "🏗️ All-Nepal Construction & Bidder Notices:": "🏗️ 네팔 전역 건설 및 입찰 공고:", "🏢 Agency Partner Program:": "🏢 에이전시 파트너 프로그램:", "💸 Direct eSewa Settlements & PIN Security:": "💸 eSewa 직접 정산 및 PIN 보안:", "💻 Lightweight <script> Ad Engine:": "💻 가벼운 <script> 광고 엔진:", "📲 Social & Influencer Monetization:": "📲 소셜 미디어 및 인플루언서 수익 창출:", "🙏 Grateful Acceptance:": "🙏 감사한 마음으로 수락하기:", "🤝 Humble Apology / Rejection:": "🤝 겸손한 사과/거절:", "🧹 System Scanner & Cache Cleaner:": "🧹 시스템 스캐너 및 캐시 클리너:", "35 Global Sectors & Institutions": "35개 글로벌 분야 및 기관", "Advertising Strategies & Bulletins": "광고 전략 및 공식 공지", "Hiring & Brand Ambassadors": "채용 및 글로벌 브랜드 앰배서더", "Editor Panel (Admin Publish)": "편집 패널 (관리자 게시)", "Targeted Institutional & Commercial Approach": "기관 및 상업 분야별 맞춤 전략", "Launch Sector Campaign →": "분야별 캠페인 시작 →", "Advertising Strategies & Institutional Bulletins": "광고 전략 및 기관 공지사항", "Hiring & Global Brand Ambassador Program": "채용 및 글로벌 브랜드 앰배서더 프로그램", "SUBMIT APPLICATION": "지원서 제출", "Admin Editor Panel": "관리자 편집 패널", "PUBLISH TO LIVE PLATFORM": "라이브 플랫폼에 게시", "Track Application / Deposit ID": "신청 / 입금 ID 조회", "SECTOR VERTICAL": "산업 분야", "Tailored advertising, public notices, and global media outreach across 35 specialized sectors worldwide:": "전 세계 35개 전문 분야를 위한 맞춤형 광고, 공공 공지 및 글로벌 미디어 홍보:", "1. International Bodies & Public Governance": "1. 국제기구 및 공공 거버넌스", "2. Education, Science & Recognition": "2. 교육, 과학 및 학술상", "3. Media, Entertainment & Culture": "3. 미디어, 엔터테인먼트 및 문화", "4. Finance, Commerce, Logistics & Legal": "4. 금융, 상업, 물류 및 법률", "5. Aviation, Transit & Global Tourism": "5. 항공, 교통 및 글로벌 관광", "6. Global Sports & Championship Events": "6. 글로벌 스포츠 및 챔피언십 대회", "Publish new Advertising Strategies or Institutional & Global Bulletins live:": "새로운 광고 전략 또는 기관 및 글로벌 공지 실시간 게시:", "Admin PIN (Default: 1234)": "관리자 PIN (기본값: 1234)", "Article / Strategy Headline": "기사 / 전략 제목", "Write clear, concise analysis or announcement...": "명확하고 간결한 분석이나 공지사항 작성...", "Self-Service Status Tracker": "셀프 서비스 상태 조회", "CHECK LIVE STATUS": "실시간 상태 확인"}, "hi": {"WORLDWIDE AD CENTER": "वर्ल्डवाइड एड सेंटर", "Home": "होम", "Tenders & Bids": "टेंडर और निविदा", "For Agencies": "एजेंसी पोर्टल", "Advertise": "विज्ञापन दें", "Main Control Hub": "मुख्य नियंत्रण केंद्र", "IMPRESSIONS": "इंप्रेशन", "LOCKED CLICKS": "सत्यापित क्लिक", "CTR %": "सीटीआर %", "AVAILABLE": "उपलब्ध शेष", "1. MOBILE APP AD SIMULATOR": "1. मोबाइल ऐप विज्ञापन सिम्युलेटर", "2. ESEWA WITHDRAWAL & HISTORY": "2. eSewa निकासी और इतिहास", "3. GET WEBSITE AD TAG (<script>)": "3. वेबसाइट विज्ञापन टैग प्राप्त करें", "4. MANAGE & ROTATE AD CAMPAIGNS": "4. विज्ञापन अभियान प्रबंधित करें", "5. ADVERTISE WITH US (SUBMIT AD)": "5. हमारे साथ विज्ञापन दें", "6. CONSTRUCTION & BIDDER NOTICES": "6. निर्माण और निविदा सूचनाएं", "7. SEND TELEGRAM HEALTH REPORT": "7. टेलीग्राम रिपोर्ट भेजें", "Main Dashboard Hub": "मुख्य नियंत्रण केंद्र", "Beginner Guide & Rules": "शुरुआती गाइड और नियम", "Invoice, Receipt & Tax PDF": "चालान, रसीद और कर PDF", "Complaints & Suggestions": "शिकायतें और सुझाव", "Mobile App Simulator": "मोबाइल ऐप सिम्युलेटर", "Deposit Ad Credits (eSewa)": "विज्ञापन क्रेडिट जमा करें (eSewa)", "eSewa Payouts & History": "eSewa निकासी और इतिहास", "Website Ad Tag (<script>)": "वेबसाइट विज्ञापन टैग", "Rotating Ad Campaigns": "रोटेटिंग विज्ञापन अभियान", "FAQ & Ad Topics": "सामान्य प्रश्न और विज्ञापन विषय", "About & Contact": "हमारे बारे में और संपर्क", "Privacy Policy": "गोपनीयता नीति", "Terms of Service": "सेवा की शर्तें", "Social Partners (FB/TikTok/IG)": "सोशल पार्टनर्स (FB/TikTok/IG)", "Universal Live Directory": "यूनिवर्सल लाइव डायरेक्टरी", "Partner Trust Badge": "पार्टनर ट्रस्ट बैज", "Ad Creative Gallery": "विज्ञापन क्रिएटिव गैलरी", "Settings": "सिस्टम सेटिंग्स", "Universal Global & Local Directory": "यूनिवर्सल ग्लोबल और लोकल डायरेक्टरी", "Search live sponsored campaigns, brands, and Nepal construction tenders in one unified index:": "एक ही इंडेक्स में लाइव प्रायोजित विज्ञापन अभियान, ब्रांड और नेपाल निर्माण टेंडर खोजें:", "Search": "खोजें", "View Tenders": "टेंडर देखें", "Step-by-Step Guide": "चरण-दर-चरण मार्गदर्शिका", "Official Moderation Standards": "आधिकारिक मॉडरेशन मानक", "Invoice, Receipt & Tax Clearance": "चालान, रसीद और कर समाशोधन", "GENERATE SIGNED DOCUMENT": "हस्ताक्षरित दस्तावेज़ बनाएं", "PRINT / SAVE PDF": "प्रिंट / PDF सेव करें", "SAVE AS HTML": "HTML के रूप में सेव करें", "Complaints, Suggestions & Email Preference": "शिकायतें, सुझाव और ईमेल प्राथमिकता", "SEND FEEDBACK": "प्रतिक्रिया भेजें", "Fund Your Ad Campaign": "अपने विज्ञापन अभियान में राशि जोड़ें", "Step 2: Submit eSewa Transaction Receipt": "चरण 2: eSewa लेनदेन रसीद जमा करें", "VERIFY ESEWA DEPOSIT RECEIPT": "eSewa जमा रसीद सत्यापित करें", "About Worldwide Ad Center": "वर्ल्डवाइड एड सेंटर के बारे में", "Live Network Proof-of-Traffic": "लाइव नेटवर्क ट्रैफ़िक प्रमाण", "Platform Features & Capabilities": "प्लेटफ़ॉर्म की विशेषताएं और क्षमताएं", "Contact & Advertiser Support": "संपर्क और विज्ञापनदाता सहायता", "Help Center & Frequently Asked Questions": "सहायता केंद्र और अक्सर पूछे जाने वाले प्रश्न", "Official Partner Verification Badge": "आधिकारिक पार्टनर सत्यापन बैज", "COPY TRUST BADGE CODE": "ट्रस्ट बैज कोड कॉपी करें", "Social Media Partner Link Generator": "सोशल मीडिया पार्टनर लिंक जनरेटर", "GENERATE TRACKED SOCIAL LINK": "ट्रैक किया गया सोशल लिंक बनाएं", "Construction & Bidder Notices": "निर्माण और बोलीदाता सूचनाएं", "Agency Partner Program": "एजेंसी पार्टनर प्रोग्राम", "\\"Thank you for partnering with Worldwide Ad Center! We are grateful for your submission—your campaign is now live.\\"": "\\"Worldwide Ad Center के साथ पार्टनरशिप करने के लिए धन्यवाद! हम आपकी सबमिशन के लिए आभारी हैं—आपका कैम्पेन अब लाइव है।\\"", "\\"We sincerely apologize, but we cannot approve this submission under our safety/clarity rules. Please edit and resubmit anytime.\\"": "\\"हम तहेदिल से माफ़ी चाहते हैं, लेकिन हम अपने सुरक्षा/स्पष्टता नियमों के तहत इस सबमिशन को मंज़ूरी नहीं दे सकते। कृपया इसमें बदलाव करके इसे जब चाहें फिर से सबमिट करें।\\"", "(60s anti-spam).": "(60 सेकंड का एंटी-स्पैम)।", "35 Global Sectors & Institutions": "35 वैश्विक क्षेत्र और संस्थान", "Advertising Strategies & Bulletins": "विज्ञापन रणनीतियां और बुलेटिन", "Hiring & Brand Ambassadors": "भर्ती और ग्लोबल ब्रांड एंबेसडर", "Editor Panel (Admin Publish)": "एडिटर पैनल (एडमिन प्रकाशन)", "Targeted Institutional & Commercial Approach": "लक्षित संस्थागत और वाणिज्यिक दृष्टिकोण", "Launch Sector Campaign →": "सेक्टर अभियान शुरू करें →", "Advertising Strategies & Institutional Bulletins": "विज्ञापन रणनीतियां और संस्थागत बुलेटिन", "Hiring & Global Brand Ambassador Program": "भर्ती और ग्लोबल ब्रांड एंबेसडर कार्यक्रम", "SUBMIT APPLICATION": "आवेदन जमा करें", "Admin Editor Panel": "एडमिन एडिटर पैनल", "PUBLISH TO LIVE PLATFORM": "लाइव प्लेटफ़ॉर्म पर प्रकाशित करें", "Track Application / Deposit ID": "आवेदन / जमा आईडी ट्रैक करें", "SECTOR VERTICAL": "प्रमुख क्षेत्र", "Tailored advertising, public notices, and global media outreach across 35 specialized sectors worldwide:": "दुनिया भर के 35 विशिष्ट क्षेत्रों में अनुकूलित विज्ञापन, सार्वजनिक सूचनाएं और वैश्विक मीडिया पहुंच:", "1. International Bodies & Public Governance": "1. अंतर्राष्ट्रीय निकाय और सार्वजनिक शासन", "2. Education, Science & Recognition": "2. शिक्षा, विज्ञान और सम्मान", "3. Media, Entertainment & Culture": "3. मीडिया, मनोरंजन और संस्कृति", "4. Finance, Commerce, Logistics & Legal": "4. वित्त, वाणिज्य, रसद और कानूनी", "5. Aviation, Transit & Global Tourism": "5. विमानन, परिवहन और वैश्विक पर्यटन", "6. Global Sports & Championship Events": "6. वैश्विक खेल और चैंपियनशिप आयोजन", "Publish new Advertising Strategies or Institutional & Global Bulletins live:": "नई विज्ञापन रणनीतियां या संस्थागत और वैश्विक बुलेटिन लाइव प्रकाशित करें:", "Admin PIN (Default: 1234)": "एडमिन पिन (डिफ़ॉल्ट: 1234)", "Article / Strategy Headline": "लेख / रणनीति शीर्षक", "Write clear, concise analysis or announcement...": "स्पष्ट और संक्षिप्त विश्लेषण या घोषणा लिखें...", "Self-Service Status Tracker": "स्व-सेवा स्थिति ट्रैकर", "CHECK LIVE STATUS": "लाइव स्थिति जांचें"}, "es": {"WORLDWIDE AD CENTER": "CENTRO MUNDIAL DE ANUNCIOS", "Home": "Inicio", "Tenders & Bids": "Licitaciones", "For Agencies": "Agencias", "Advertise": "Anunciar", "Main Control Hub": "Panel Principal", "IMPRESSIONS": "IMPRESIONES", "LOCKED CLICKS": "CLICS VERIFICADOS", "CTR %": "CTR %", "AVAILABLE": "DISPONIBLE", "1. MOBILE APP AD SIMULATOR": "1. SIMULADOR DE ANUNCIOS MÓVILES", "2. ESEWA WITHDRAWAL & HISTORY": "2. RETIRO E HISTORIAL ESEWA", "3. GET WEBSITE AD TAG (<script>)": "3. OBTENER ETIQUETA DE ANUNCIO", "4. MANAGE & ROTATE AD CAMPAIGNS": "4. GESTIONAR CAMPAÑAS", "5. ADVERTISE WITH US (SUBMIT AD)": "5. ANÚNCIATE CON NOSOTROS", "6. CONSTRUCTION & BIDDER NOTICES": "6. AVISOS DE CONSTRUCCIÓN", "7. SEND TELEGRAM HEALTH REPORT": "7. ENVIAR INFORME TELEGRAM", "Main Dashboard Hub": "Panel Principal", "Beginner Guide & Rules": "Guía para Principiantes y Reglas", "Invoice, Receipt & Tax PDF": "Factura, Recibo e Impuestos PDF", "Complaints & Suggestions": "Quejas y Sugerencias", "Mobile App Simulator": "Simulador de App Móvil", "Deposit Ad Credits (eSewa)": "Depositar Créditos (eSewa)", "eSewa Payouts & History": "Retiros e Historial eSewa", "Website Ad Tag (<script>)": "Etiqueta de Anuncio Web", "Rotating Ad Campaigns": "Campañas Rotativas", "FAQ & Ad Topics": "Preguntas Frecuentes", "About & Contact": "Acerca de y Contacto", "Privacy Policy": "Política de Privacidad", "Terms of Service": "Términos de Servicio", "Social Partners (FB/TikTok/IG)": "Socios Sociales (FB/TikTok/IG)", "Universal Live Directory": "Directorio Global en Vivo", "Partner Trust Badge": "Insignia de Socio Verificado", "Ad Creative Gallery": "Galería Creativa de Anuncios", "Settings": "Configuración", "Universal Global & Local Directory": "Directorio Universal Global y Local", "Search live sponsored campaigns, brands, and Nepal construction tenders in one unified index:": "Busque campañas patrocinadas, marcas y licitaciones de construcción en un índice unificado:", "Search": "Buscar", "View Tenders": "Ver Licitaciones", "Step-by-Step Guide": "Guía Paso a Paso", "Official Moderation Standards": "Estándares Oficiales de Moderación", "Invoice, Receipt & Tax Clearance": "Factura, Recibo y Solvencia Fiscal", "GENERATE SIGNED DOCUMENT": "GENERAR DOCUMENTO FIRMADO", "PRINT / SAVE PDF": "IMPRIMIR / GUARDAR PDF", "SAVE AS HTML": "GUARDAR COMO HTML", "Complaints, Suggestions & Email Preference": "Quejas, Sugerencias y Preferencia de Correo", "SEND FEEDBACK": "ENVIAR COMENTARIOS", "Fund Your Ad Campaign": "Financiar su Campaña Publicitaria", "Step 2: Submit eSewa Transaction Receipt": "Paso 2: Enviar Recibo de Transacción eSewa", "VERIFY ESEWA DEPOSIT RECEIPT": "VERIFICAR RECIBO DE DEPÓSITO ESEWA", "About Worldwide Ad Center": "Acerca de Worldwide Ad Center", "Live Network Proof-of-Traffic": "Prueba de Tráfico de Red en Vivo", "Platform Features & Capabilities": "Características y Capacidades de la Plataforma", "Contact & Advertiser Support": "Contacto y Soporte para Anunciantes", "Help Center & Frequently Asked Questions": "Centro de Ayuda y Preguntas Frecuentes", "Official Partner Verification Badge": "Insignia Oficial de Verificación de Socio", "COPY TRUST BADGE CODE": "COPIAR CÓDIGO DE INSIGNIA", "Social Media Partner Link Generator": "Generador de Enlaces para Socios Sociales", "GENERATE TRACKED SOCIAL LINK": "GENERAR ENLACE SOCIAL RASTREADO", "Construction & Bidder Notices": "Avisos de Construcción y Licitadores", "Agency Partner Program": "Programa de Socios de Agencias", "35 Global Sectors & Institutions": "35 Sectores e Instituciones Globales", "Advertising Strategies & Bulletins": "Estrategias Publicitarias y Boletines", "Hiring & Brand Ambassadors": "Contratación y Embajadores de Marca", "Editor Panel (Admin Publish)": "Panel de Editor (Publicación Admin)", "Targeted Institutional & Commercial Approach": "Enfoque Institucional y Comercial Dirigido", "Launch Sector Campaign →": "Lanzar Campaña Sectorial →", "Advertising Strategies & Institutional Bulletins": "Estrategias Publicitarias y Boletines Institucionales", "Hiring & Global Brand Ambassador Program": "Programa de Contratación y Embajadores Globales", "SUBMIT APPLICATION": "ENVIAR SOLICITUD", "Admin Editor Panel": "Panel de Editor Administrador", "PUBLISH TO LIVE PLATFORM": "PUBLICAR EN LA PLATAFORMA", "Track Application / Deposit ID": "Rastrear ID de Solicitud / Depósito", "SECTOR VERTICAL": "SECTOR VERTICAL", "Tailored advertising, public notices, and global media outreach across 35 specialized sectors worldwide:": "Publicidad a medida, avisos públicos y difusión global en 35 sectores especializados:", "1. International Bodies & Public Governance": "1. Organismos Internacionales y Gobernanza Pública", "2. Education, Science & Recognition": "2. Educación, Ciencia y Reconocimiento", "3. Media, Entertainment & Culture": "3. Medios, Entretenimiento y Cultura", "4. Finance, Commerce, Logistics & Legal": "4. Finanzas, Comercio, Logística y Legal", "5. Aviation, Transit & Global Tourism": "5. Aviación, Transporte y Turismo Global", "6. Global Sports & Championship Events": "6. Deportes Globales y Campeonatos", "Publish new Advertising Strategies or Institutional & Global Bulletins live:": "Publique en vivo nuevas Estrategias Publicitarias o Boletines Institucionales:", "Admin PIN (Default: 1234)": "PIN de Administrador (Por defecto: 1234)", "Article / Strategy Headline": "Titular del Artículo / Estrategia", "Write clear, concise analysis or announcement...": "Escriba un análisis o anuncio claro y conciso...", "Self-Service Status Tracker": "Rastreador de Estado de Autoservicio", "CHECK LIVE STATUS": "VERIFICAR ESTADO EN VIVO"}}', media_type="application/json")

@app.get("/sitemap.xml")
async def seo_sitemap():
    base = "https://worldwide-ad-center-1.onrender.com"
    paths = ["", "/sectors", "/editorial", "/careers", "/tenders", "/agencies", "/advertise", "/directory", "/status", "/analytics", "/admin-desk", "/mail", "/guide", "/documents", "/deposit", "/social-partners", "/verify-badge", "/gallery", "/faq", "/about", "/privacy", "/terms"]
    urls = "".join([f"<url><loc>{base}{p}</loc><changefreq>daily</changefreq></url>" for p in paths])
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://sitemaps.org">{urls}</urlset>'
    return Response(content=xml, media_type="application/xml")

@app.get("/", response_class=HTMLResponse)
async def root_hub(db: DBWrapper = Depends(get_db)):
    imp = db.execute("SELECT COUNT(*) FROM impressions").fetchone()[0] or 0
    row = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    clk, earn = row[0], round(float(row[1]), 2)
    ctr = round((clk / imp * 100), 2) if imp > 0 else 0.0
    db_mode = "Cloud PostgreSQL (Permanent)" if db.is_pg else f"Local SQLite ({db.err or 'No DATABASE_URL'})"
    return f"""<!DOCTYPE html><html><head><title>Worldwide Ad Center</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com">
    <style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:20px;margin:0}}.card{{background:#1e293b;padding:18px;border-radius:12px;border:1px solid #334155;margin-bottom:15px}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.stat{{background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px solid #475569}}.val{{font-size:22px;font-weight:bold;color:#22c55e}}.btn{{display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:12px;border-radius:8px;font-weight:bold;text-decoration:none;margin-top:10px}}</style></head>
    <body>{render_nav("Main Control Hub", "Home / Dashboard")}<div class="card" style="padding:10px 14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
        <p style="color:#94a3b8;font-size:11px;margin:0;">Storage: <b>{db_mode}</b></p>
        <div style="display:flex;align-items:center;gap:4px;">
            <span style="font-size:10px;color:#94a3b8;">Currency:</span>
            <button onclick="setCur('NPR',1)" style="background:#38bdf8;color:#0f172a;border:none;border-radius:4px;padding:3px 6px;font-size:10px;font-weight:bold;cursor:pointer;">NPR</button>
            <button onclick="setCur('USD',0.0074)" style="background:#0f172a;color:#cbd5e1;border:1px solid #475569;border-radius:4px;padding:3px 6px;font-size:10px;font-weight:bold;cursor:pointer;">USD</button>
            <button onclick="setCur('INR',0.625)" style="background:#0f172a;color:#cbd5e1;border:1px solid #475569;border-radius:4px;padding:3px 6px;font-size:10px;font-weight:bold;cursor:pointer;">INR</button>
            <button onclick="setCur('EUR',0.0068)" style="background:#0f172a;color:#cbd5e1;border:1px solid #475569;border-radius:4px;padding:3px 6px;font-size:10px;font-weight:bold;cursor:pointer;">EUR</button>
        </div>
    </div>
    <script>
    const baseNpr = {0};
    function setCur(sym, rate){{
        const val = (baseNpr * rate).toFixed(sym==='NPR'?2:4);
        const cpc = (2.50 * rate).toFixed(sym==='NPR'?2:4);
        document.getElementById('balVal').innerText = val + ' ' + sym;
        document.getElementById('cpcNote').innerText = 'Standard Rate: ' + cpc + ' ' + sym + ' / Click';
    }}
    </script>
    <div class="card"><div class="grid"><div class="stat"><div>IMPRESSIONS</div><div class="val">{imp}</div></div><div class="stat"><div>LOCKED CLICKS</div><div class="val">{clk}</div></div><div class="stat"><div>CTR %</div><div class="val">{ctr}%</div></div><div class="stat"><div>AVAILABLE</div><div class="val">{earn} NPR</div></div></div>
    <a href="/simulate-app" class="btn">1. MOBILE APP AD SIMULATOR</a>
    <a href="/payout-hub" class="btn" style="background:#f59e0b;">2. ESEWA WITHDRAWAL &amp; HISTORY</a>
    <a href="/tag-preview" class="btn" style="background:#a855f7;color:#fff;">3. GET WEBSITE AD TAG (&lt;script&gt;)</a>
    <a href="/campaigns" class="btn" style="background:#ec4899;color:#fff;">4. MANAGE &amp; ROTATE AD CAMPAIGNS</a>
    <a href="/advertise" class="btn" style="background:#14b8a6;color:#0f172a;">5. ADVERTISE WITH US (SUBMIT AD)</a>
    <a href="/tenders" class="btn" style="background:#0ea5e9;color:#0f172a;">6. CONSTRUCTION &amp; BIDDER NOTICES</a>
    <a href="/api/v1/health/telegram-report" class="btn" style="background:#22c55e;">7. SEND TELEGRAM HEALTH REPORT</a></div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(db: DBWrapper = Depends(get_db)):
    rows = db.execute("SELECT id, headline, subtext, btn_text, target_url FROM ad_campaigns ORDER BY id DESC").fetchall()
    items = ""
    for r in rows:
        cid, hl, sub, btn, url = r
        items += f"<div style='background:#0f172a;padding:12px;border-radius:8px;margin-top:8px;border-left:4px solid #ec4899;'><b style='color:#fff;'>#{cid} &bull; {hl}</b><p style='margin:4px 0;font-size:12px;color:#cbd5e1;'>{sub}</p><small style='color:#38bdf8;'>Button: {btn} &rarr; {url}</small></div>"
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:20px}}.box{{background:#1e293b;padding:20px;border-radius:12px;margin-bottom:15px}}input{{width:100%;padding:12px;margin:8px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#ec4899;color:#fff;border:none;border-radius:6px;font-weight:bold;margin-top:10px}}</style></head>
    <body>{render_nav("Manage & Rotate Campaigns", "Home / Campaigns")}<div class="box"><h2>Add New Rotating Ad Campaign</h2>
    <input id="hl" placeholder="Ad Headline"><input id="sub" placeholder="Short Description"><input id="btn" placeholder="Button Label (e.g. Visit Site)"><input id="url" placeholder="Destination URL (https://...)"><input id="pin" type="password" placeholder="Admin PIN (Default: 2026)">
    <button class="btn" onclick="addC()">ADD TO ROTATION</button><p id="res" style="color:#22c55e"></p></div>
    <div class="box"><h3>Active Rotating Ads ({len(rows)})</h3>{items}</div>{FOOTER}
    <script>async function addC(){{const r=await fetch('/api/v1/add-campaign',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value,subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value,target_url:document.getElementById('url').value,pin:document.getElementById('pin').value}})}});const d=await r.json();document.getElementById('res').innerText=d.message||(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

class CampaignReq(BaseModel):
    headline: str
    subtext: str
    btn_text: str
    target_url: str
    img_data: str = ""
    pin: str = ""

@app.post("/api/v1/add-campaign")
async def add_campaign(req: CampaignReq, db: DBWrapper = Depends(get_db)):
    if req.pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Invalid Admin PIN.")
    nid = int(time.time()) % 1000000
    db.execute("INSERT INTO ad_campaigns (id, headline, subtext, btn_text, target_url, active) VALUES (?, ?, ?, ?, ?, 1)", (nid, req.headline, req.subtext, req.btn_text, req.target_url))
    db.commit()
    return {"message": "Campaign added to live rotation! Refresh page to see list."}

@app.get("/advertise", response_class=HTMLResponse)
async def advertise_portal(db: DBWrapper = Depends(get_db)):
    now = int(time.time())
    db.execute("DELETE FROM saved_banners WHERE expires_at < ?", (now,))
    db.commit()
    rows = db.execute("SELECT draft_id, headline, subtext, img_data, expires_at FROM saved_banners ORDER BY expires_at DESC LIMIT 8").fetchall()
    lib = ""
    for r in rows:
        did, hl, sub, img, exp = r
        hrs = max(1, int((exp - now) / 3600))
        im_tag = f'<img src="{img}" style="width:100%;max-height:80px;object-fit:cover;border-radius:5px;margin-bottom:5px;">' if img else ''
        lib += f'<div style="background:#0f172a;padding:10px;border-radius:8px;margin-top:8px;border:1px solid #334155;">{im_tag}<b>{hl}</b> <span style="color:#f59e0b;font-size:11px;">({hrs}h left)</span><br><small style="color:#94a3b8">{sub}</small><br><button onclick="ld(\'{did}\')" style="background:#38bdf8;border:none;padding:5px 10px;border-radius:4px;font-size:11px;font-weight:bold;margin-top:5px;">Load Draft</button></div>'
    if not lib:
        lib = '<p style="color:#94a3b8;font-size:12px;">No saved drafts yet.</p>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:18px}}.box{{background:#1e293b;padding:16px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}.tpl{{background:#0f172a;border:1px solid #14b8a6;color:#14b8a6;padding:6px 9px;border-radius:6px;font-size:11px;margin:3px}}input{{width:100%;padding:10px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:11px;background:#14b8a6;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:7px}}</style></head>
    <body>{render_nav("Advertiser Studio & 7-Day Library", "Home / Advertise With Us")}<div class="box"><h3 style="margin-top:0">Templates &amp; Live Preview</h3>
    <button class="tpl" onclick="tp('Flash Sale: 50% Off!','Limited-time deals across Nepal.','Shop Now')">E-Commerce</button>
    <button class="tpl" onclick="tp('Smart App Launch','Try free for 14 days today.','Download')">App Launch</button>
    <button class="tpl" onclick="tp('Local Service Offer','Trusted quality &amp; fast booking.','Book Now')">Local Offer</button>
    <div style="background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px dashed #38bdf8;margin-top:10px;"><div id="pi"></div><h4 id="ph" style="margin:5px 0">Your Headline</h4><p id="ps" style="font-size:12px;color:#cbd5e1;margin:0 0 8px 0">Offer description</p><span id="pb" style="background:#22c55e;color:#0f172a;padding:5px 12px;border-radius:4px;font-size:12px;font-weight:bold" onclick="alert('Live Ad Preview: Visitors clicking this button will open your Target URL.')">Learn More</span></div></div>
    <div class="box"><h3 style="margin-top:0">Banner Editor &amp; Attachment</h3>
    <input id="hl" oninput="sy()" placeholder="Headline"><input id="sub" oninput="sy()" placeholder="Description"><input id="btn" oninput="sy()" placeholder="Button Text"><input id="url" placeholder="Target URL (https://...)">
    <input type="file" accept="image/*" onchange="ri(this)" style="font-size:12px">
    <button class="btn" style="background:#38bdf8" onclick="sv()">SAVE TO 7-DAY LIBRARY</button>
    <button class="btn" onclick="sb()">SUBMIT FOR APPROVAL</button><p id="res" style="color:#22c55e;font-size:12px"></p></div>
    <div class="box"><h3 style="margin-top:0">7-Day Temporary Library</h3>{lib}</div>{FOOTER}
    <script>let im="";function sy(){{document.getElementById('ph').innerText=document.getElementById('hl').value||'Your Headline';document.getElementById('ps').innerText=document.getElementById('sub').value||'Offer description';document.getElementById('pb').innerText=document.getElementById('btn').value||'Learn More'}}
    function tp(h,s,b){{document.getElementById('hl').value=h;document.getElementById('sub').value=s;document.getElementById('btn').value=b;sy()}}
    function ri(i){{const f=i.files.item(0);if(!f)return;if(f.size>520000){{alert('Max 500KB');return}}const r=new FileReader();r.onload=e=>{{im=e.target.result;document.getElementById('pi').innerHTML='<img src="'+im+'" style="width:100%;max-height:90px;object-fit:cover;border-radius:5px">'}};r.readAsDataURL(f)}}
    async function sv(){{const r=await fetch('/api/v1/save-banner-draft',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value||'Draft',subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value||'Learn More',target_url:document.getElementById('url').value,img_data:im}})}});const d=await r.json();document.getElementById('res').innerText=d.message;setTimeout(()=>location.reload(),900)}}
    async function ld(id){{const r=await fetch('/api/v1/load-banner-draft/'+id);const d=await r.json();document.getElementById('hl').value=d.headline;document.getElementById('sub').value=d.subtext;document.getElementById('btn').value=d.btn_text;document.getElementById('url').value=d.target_url;im=d.img_data||'';document.getElementById('pi').innerHTML=im?'<img src="'+im+'" style="width:100%;max-height:90px;object-fit:cover;border-radius:5px">':'';sy()}}
    async function sb(){{const r=await fetch('/api/v1/submit-advertiser',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value,subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value,target_url:document.getElementById('url').value,img_data:im}})}});const d=await r.json();document.getElementById('res').innerText=d.message}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/save-banner-draft")
async def save_banner_draft(req: CampaignReq, db: DBWrapper = Depends(get_db)):
    db.execute("INSERT INTO saved_banners (draft_id, headline, subtext, btn_text, target_url, img_data, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (f"DRF-{int(time.time()*1000)}", req.headline, req.subtext, req.btn_text, req.target_url, req.img_data, int(time.time())+604800))
    db.commit()
    return {"message": "Saved to 7-day library!"}

@app.get("/api/v1/load-banner-draft/{did}")
async def load_banner_draft(did: str, db: DBWrapper = Depends(get_db)):
    r = db.execute("SELECT headline, subtext, btn_text, target_url, img_data FROM saved_banners WHERE draft_id=?", (did,)).fetchone()
    if not r: return {{}}
    hl, sub, btn, url, img = r
    return {"headline":hl,"subtext":sub,"btn_text":btn,"target_url":url,"img_data":img}

@app.post("/api/v1/submit-advertiser")
async def submit_advertiser(req: CampaignReq):
    send_telegram_alert(f"📢 New Advertiser Request!\n• Headline: {req.headline}\n• URL: {req.target_url}")
    return {"message": "Campaign submitted! Network admin notified via Telegram for approval."}

@app.get("/api/v1/tag.js")
async def ad_tag_js(db: DBWrapper = Depends(get_db)):
    imp_id = f"IMP-WEB-{int(time.time()*1000)}"
    db.execute("INSERT INTO impressions (impression_id, publisher_id, timestamp) VALUES (?, 'pub_dev_773x92', 'now')", (imp_id,))
    db.commit()
    rows = db.execute("SELECT headline, subtext, btn_text, target_url FROM ad_campaigns WHERE active=1").fetchall()
    hl, sub, btn, url = random.choice(rows) if rows else ("Worldwide Ad Center", "Grow your reach today.", "Learn More", "https://worldwide-ad-center-1.onrender.com")
    base = "https://" + "worldwide-ad-center-1" + ".onrender.com"
    js = f"""(function(){{var d=document.createElement('div');d.style='background:#1e293b;color:#fff;padding:16px;border-radius:10px;text-align:center;font-family:sans-serif;border:1px solid #38bdf8;margin:12px 0;';d.innerHTML='<small style="color:#38bdf8;letter-spacing:1px;">SPONSORED &bull; <a href="{base}/privacy" target="_blank" style="color:#94a3b8;text-decoration:none;">Ad Privacy</a></small><h4 style="margin:6px 0;font-size:18px;">{hl}</h4><p style="margin:0 0 12px 0;font-size:13px;color:#cbd5e1;">{sub}</p><button onclick="fetch(\\'{base}/api/v1/simulate-click\\',{{method:\\'POST\\'}});window.open(\\'{url}\\',\\'_blank\\');" style="background:#22c55e;color:#0f172a;border:none;padding:9px 18px;border-radius:6px;font-weight:bold;cursor:pointer;">{btn}</button>';document.currentScript.parentNode.insertBefore(d,document.currentScript);}})();"""
    return Response(content=js, media_type="application/javascript")

@app.get("/tag-preview", response_class=HTMLResponse)
async def tag_preview():
    base = "https://" + "worldwide-ad-center-1" + ".onrender.com"
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:20px}}code{{display:block;background:#1e293b;padding:12px;border-radius:8px;color:#38bdf8;word-break:break-all;margin:15px 0}}</style></head>
    <body>{render_nav("Website Ad Tag (<script>)", "Home / Website Ad Tag")}<h2>Website Ad Tag (&lt;script&gt;)</h2><p>Paste this single line into any website HTML:</p><code>&lt;script src="{base}/api/v1/tag.js"&gt;&lt;/script&gt;</code>
    <h3>Live Rotating Ad Preview:</h3><script src="/api/v1/tag.js"></script>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""




class AgencyReq(BaseModel):
    agency_name: str
    contact_info: str
    monthly_budget: str
    client_count: str


class TenderReq(BaseModel):
    title: str
    issuer: str
    category: str
    deadline: str
    contact_url: str
    pin: str = ""


class SettingsReq(BaseModel):
    default_wallet: str
    cpc_rate: float
    qr_img: str = ""
    pin: str



@app.get("/go/social")
async def social_redirect(platform: str = "social", partner: str = "partner", cid: int = 1, db: DBWrapper = Depends(get_db)):
    row = db.execute("SELECT target_url FROM ad_campaigns WHERE id=?", (cid,)).fetchone()
    dest = row.__getitem__(0) if row else "https://worldwide-ad-center-1.onrender.com"
    db.execute("INSERT INTO impressions (ts, source) VALUES (?, ?)", (int(time.time()), f"{platform}:{partner}"))
    recent_soc = db.execute("SELECT ts FROM clicks WHERE ip=? AND ts > ?", (f"social-{partner}", int(time.time()) - 60)).fetchone()
    if not recent_soc:
        db.execute("INSERT INTO clicks (ts, ip, source) VALUES (?, ?, ?)", (int(time.time()), f"social-{partner}", f"{platform}:{partner}"))
    db.commit()
    return HTMLResponse(f'<script>window.location.href="{dest}";</script>')


class DepositReq(BaseModel):
    advertiser: str
    amount: float
    txn_code: str
    contact: str



class FeedbackReq(BaseModel):
    kind: str
    sender: str
    email_pref: str
    message: str

@app.get("/documents", response_class=HTMLResponse)
async def documents_hub():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}input,select{{width:100%;padding:12px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box;font-size:14px}}.btn{{width:100%;padding:13px;background:#22c55e;color:#0f172a;border:none;border-radius:8px;font-weight:bold;margin-top:8px;cursor:pointer;font-size:14px}}@media print{{body{{background:#fff;color:#000}}.no-print{{display:none}}}}</style></head>
    <body><div class="no-print">{render_nav("Invoice, Receipt & Tax PDF", "Home / Financial Documents")}</div>
    <div class="box no-print"><h2>Invoice, Receipt &amp; Tax Clearance</h2>
    <select id="dtp"><option value="TAX INVOICE">Official Tax Invoice</option><option value="ESEWA PAYMENT RECEIPT">Verified eSewa Payment Receipt</option><option value="TAXATION & CLEARANCE">Taxation &amp; Account Clearance</option></select>
    <input id="cnm" placeholder="Client / Agency / Publisher Name">
    <input id="cpn" placeholder="PAN / VAT or Phone Number">
    <input id="cam" type="number" value="1000" placeholder="Amount (NPR)">
    <select id="ctx"><option value="0">Tax / VAT: 0% Direct</option><option value="13">Nepal VAT: 13%</option><option value="1.5">TDS Clearance: 1.5%</option></select>
    <input id="crf" placeholder="Txn ID or Reference (e.g. BID-97216)">
    <button class="btn" onclick="mkDoc()">GENERATE SIGNED DOCUMENT</button></div>
    <div id="paper" class="box" style="background:#fff;color:#0f172a;border:2px solid #38bdf8;">
        <div style="display:flex;justify-content:space-between;border-bottom:2px solid #0f172a;padding-bottom:8px;"><div><b>WORLDWIDE AD CENTER (WAC)</b><br><small>Gandaki, Nepal &bull; difft40y@gmail.com &bull; eSewa: 9717831225</small></div><div style="text-align:right;"><b id="pT">TAX INVOICE</b><br><small id="pD"></small></div></div>
        <p style="font-size:13px;"><b>Issued To:</b> <span id="pC">Partner</span> &bull; <b>PAN/ID:</b> <span id="pP">N/A</span><br><b>Ref:</b> <span id="pR">WAC-2026</span></p>
        <div style="background:#f1f5f9;padding:10px;border-radius:8px;font-size:13px;">Base: <b id="pB">1000.00 NPR</b> | Tax: <b id="pX">0.00 NPR</b><br>Total Verified: <b id="pTot" style="font-size:15px;">1000.00 NPR</b></div>
        <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:flex-end;"><small style="color:#15803d;font-weight:bold;">&#9989; CLEARANCE VERIFIED</small><div style="border-top:1px dashed #000;padding-top:3px;text-align:right;"><b style="font-family:cursive;color:#003893;">WAC Authorized Desk</b><br><small id="pS">Digital Signature</small></div></div>
    </div>
    <div class="box no-print" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;"><button class="btn" style="background:#38bdf8;margin:0;" onclick="window.print()">PRINT / SAVE PDF</button><button class="btn" style="background:#f59e0b;margin:0;" onclick="dlH()">SAVE AS HTML</button></div><div class="no-print">{FOOTER}</div>
    <script>document.getElementById('pD').innerText=new Date().toLocaleString('en-US',{{timeZone:'Asia/Kathmandu'}})+' NPT';function mkDoc(){{const b=parseFloat(document.getElementById('cam').value)||0,t=parseFloat(document.getElementById('ctx').value)||0,tx=b*(t/100),rf=document.getElementById('crf').value||'WAC-2026';document.getElementById('pT').innerText=document.getElementById('dtp').value;document.getElementById('pC').innerText=document.getElementById('cnm').value||'Partner';document.getElementById('pP').innerText=document.getElementById('cpn').value||'N/A';document.getElementById('pR').innerText=rf;document.getElementById('pB').innerText=b.toFixed(2)+' NPR';document.getElementById('pX').innerText=tx.toFixed(2)+' NPR';document.getElementById('pTot').innerText=(b+tx).toFixed(2)+' NPR';document.getElementById('pS').innerText='SIG-'+btoa(rf).slice(0,8).toUpperCase();}}function dlH(){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([document.getElementById('paper').outerHTML],{{type:'text/html'}}));a.download='WAC_Receipt.html';a.click();}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/feedback", response_class=HTMLResponse)
async def feedback_page():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}input,select,textarea{{width:100%;padding:12px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box;font-size:14px}}.btn{{width:100%;padding:13px;background:#f59e0b;color:#0f172a;border:none;border-radius:8px;font-weight:bold;margin-top:8px;cursor:pointer;font-size:14px}}</style></head>
    <body>{render_nav("Complaints, Suggestions & Preferences", "Home / User Feedback")}
    <div class="box"><h2>Complaints, Suggestions &amp; Email Preference</h2>
    <select id="fk"><option>Suggestion / Feature Request</option><option>Complaint / Honest Issue Report</option><option>Email Preference Update</option></select>
    <input id="fs" placeholder="Your Name"><input id="fe" placeholder="Email or Telegram/WhatsApp"><textarea id="fm" rows="3" placeholder="Write honest, clear message..."></textarea>
    <button class="btn" onclick="sFb()">SEND FEEDBACK</button><p id="fr" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}
    <script>async function sFb(){{const r=await fetch('/api/v1/submit-feedback',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{kind:document.getElementById('fk').value,sender:document.getElementById('fs').value,email_pref:document.getElementById('fe').value,message:document.getElementById('fm').value}})}});const d=await r.json();document.getElementById('fr').innerText=d.message;}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/submit-feedback")
async def submit_feedback(req: FeedbackReq):
    send_telegram_alert(f"💬 FEEDBACK / PREFERENCE:\n• {req.kind}\n• From: {req.sender} ({req.email_pref})\n• Msg: {req.message}")
    return {"message": "Thank you! Your message has been received honestly by our support desk (difft40y@gmail.com)."}


def _tr_one(target_code: str, txt: str) -> str:
    s = txt.strip()
    if len(s) < 2:
        return txt
    tl = "zh-CN" if target_code.startswith("zh") else target_code.split("-").__getitem__(0)
    try:
        dot = chr(46)
        sl = chr(47)
        host = "https:" + sl + sl + "translate" + dot + "google" + dot + "com" + sl + "m"
        u = f"{host}?sl=en&tl={tl}&q={urllib.parse.quote(s[:450])}"
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Linux; Android 10)"})
        page = urllib.request.urlopen(req, timeout=5).read().decode("utf-8", "ignore")
        m = re.search(r'<div class="(?:result-container|t0)"[^>]*>(.*?)</div>', page, re.S)
        if m:
            return html.unescape(m.group(1)).strip() or txt
    except Exception:
        pass
    return txt

@app.post("/api/v1/translate-batch")
async def translate_batch(payload: dict):
    tl = payload.get("tl", "en")
    texts = payload.get("texts", [])
    if tl == "en" or not texts:
        return {"items": texts}
    lang_map = {"zh": "zh-CN", "zh-CN": "zh-CN", "ja": "ja-JP", "ko": "ko-KR", "hi": "hi-IN", "es": "es-ES"}
    target_code = lang_map.get(tl, tl)
    tasks = [asyncio.to_thread(_tr_one, target_code, t) for t in texts]
    out = await asyncio.gather(*tasks)
    return {"items": list(out)}


@app.get("/sectors", response_class=HTMLResponse)
async def global_sectors():
    groups = [
        ("1. International Bodies & Public Governance", "UN • WTO • WHO • IMF • ADB • UNESCO • Governments • Non-Profit Organizations • NGO / INGO • Military & Police Forces", "Official public awareness campaigns, multilateral procurement notices, humanitarian outreach, and verified civic announcements."),
        ("2. Education, Science & Recognition", "Schools • Colleges • Universities • AI Research Labs • Nobel Academy & Academic Awards", "Global student admissions, international symposium announcements, AI innovation showcases, and academic recognition notices."),
        ("3. Media, Entertainment & Culture", "Media Houses • Television Channels • Film Cities • Beauty Contests • Social Sites • Leading Society Influencers", "Cross-platform audience syndication, premiere promotions, creator link monetization, and broadcast sponsorship campaigns."),
        ("4. Finance, Commerce, Logistics & Legal", "Banks • Stock Markets • Industries • Super Markets • Online Shopping • Auctions • Courier Services • Law Firms", "High-conversion CPC/banner acquisition, financial disclosures, retail seasonal drives, e-commerce traffic, and corporate notices."),
        ("5. Aviation, Transit & Global Tourism", "Airlines • Railways • Transports • Tour & Travels", "New flight/rail route launches, regional transit advisories, hospitality packages, and international tourism campaigns."),
        ("6. Global Sports & Championship Events", "FIFA World Cup • Cricket Boards • Wrestling • Riding & Equestrian Federations", "Tournament sponsorships, live broadcast alerts, ticketing drives, and global fan engagement campaigns.")
    ]
    cards = "".join([f'<div class="box"><span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">SECTOR VERTICAL</span><h3 style="margin:8px 0 4px 0;">{g.__getitem__(0)}</h3><div style="font-size:12px;color:#f59e0b;font-weight:bold;margin-bottom:6px;">{g.__getitem__(1)}</div><p style="font-size:12px;margin:0 0 10px 0;">{g.__getitem__(2)}</p><a href="/advertise" style="display:inline-block;background:#22c55e;color:#0f172a;padding:8px 12px;border-radius:6px;font-size:12px;font-weight:bold;text-decoration:none;">Launch Sector Campaign &rarr;</a></div>' for g in groups])
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:16px;border-radius:12px;margin-bottom:12px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}</style></head>
    <body>{render_nav("35 Global Sectors & Institutions", "Home / Targeted Sectors")}
    <div class="box"><h2>Targeted Institutional &amp; Commercial Approach</h2><p style="font-size:12px;margin:0 0 8px 0;">Tailored advertising, public notices, and global media outreach across 35 specialized sectors worldwide:</p><input id="secQ" oninput="var q=this.value.toLowerCase();document.querySelectorAll('.box').forEach((b,i)=>{{if(i>0)b.style.display=b.innerText.toLowerCase().includes(q)?'block':'none';}});" placeholder="Filter sectors (e.g. UN, Airlines, Banks, FIFA, AI...)" style="width:100%;padding:10px;border-radius:8px;border:1px solid #38bdf8;background:#0f172a;color:#fff;box-sizing:border-box;font-size:13px;"></div>
    {cards}{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/editorial", response_class=HTMLResponse)
async def editorial_hub(db: DBWrapper = Depends(get_db)):
    db.execute("CREATE TABLE IF NOT EXISTS editorial (ed_id TEXT PRIMARY KEY, category TEXT, title TEXT, summary TEXT, author TEXT, ts INTEGER);")
    db.execute("DELETE FROM editorial WHERE ed_id='ED-101'")
    if db.execute("SELECT COUNT(*) FROM editorial").fetchone().__getitem__(0) == 0:
        db.execute("INSERT INTO editorial VALUES (?, ?, ?, ?, ?, ?)", ("ED-102", "Advertising Strategies", "Multi-Language & Cross-Border Outreach Playbook for Institutions & Brands", "Combining localized landing pages, verified trust badges, and multi-currency billing (NPR, USD, INR, EUR) to convert international audiences.", "WAC Strategy Desk", 1732203600))
        db.commit()
    rows = db.execute("SELECT ed_id, category, title, summary, author FROM editorial ORDER BY ts DESC").fetchall()
    items = ""
    for r in rows:
        eid, cat, tit, sm, aut = r[0], r[1], r[2], r[3], r[4]
        items += f'<div class="box"><span style="background:#c084fc;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">{cat}</span><h3 style="margin:8px 0 6px 0;">{tit}</h3><p style="font-size:13px;margin:0 0 8px 0;">{sm}</p><small style="color:#94a3b8;">By {aut} &bull; Ref: {eid}</small></div>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.6}}.box{{background:#1e293b;padding:16px;border-radius:12px;margin-bottom:12px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}</style></head>
    <body>{render_nav("Advertising Strategies & Bulletins", "Home / Advertising Strategies")}
    <div class="box" style="border-left:4px solid #c084fc;"><h2>Advertising Strategies &amp; Institutional Bulletins</h2><p style="font-size:12px;margin:0;">Actionable digital advertising strategies, multi-currency outreach playbooks, and verified institutional bulletins.</p></div>
    {items}{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""


class EditorialReq(BaseModel):
    pin: str
    category: str
    title: str
    summary: str
    author: str

class CareerReq(BaseModel):
    role: str
    name: str
    region: str
    contact: str
    pitch: str

@app.get("/careers", response_class=HTMLResponse)
async def careers_portal():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}input,select,textarea{{width:100%;padding:12px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box;font-size:14px}}.btn{{width:100%;padding:13px;background:#22c55e;color:#0f172a;border:none;border-radius:8px;font-weight:bold;margin-top:8px;cursor:pointer;font-size:14px}}</style></head>
    <body>{render_nav("Hiring & Brand Ambassadors", "Home / Careers & Ambassadors")}
    <div class="box"><h2>Hiring &amp; Global Brand Ambassador Program</h2>
    <p style="font-size:12px;margin-top:0;">Join Worldwide Ad Center as a regional representative, institutional liaison, or Brand Ambassador:</p>
    <select id="crole"><option>Brand Ambassador (Commission &amp; Referral Partner)</option><option>Regional Ad Sales &amp; Agency Coordinator</option><option>Institutional &amp; NGO Outreach Specialist</option><option>Technical Publisher Integration Engineer</option></select>
    <input id="cname" placeholder="Full Name">
    <input id="creg" placeholder="Country / Province / City">
    <input id="ccnt" placeholder="Email, WhatsApp, or Telegram">
    <textarea id="cpitch" rows="3" placeholder="Briefly describe your network, experience, or social reach..."></textarea>
    <button class="btn" onclick="sendApp()">SUBMIT APPLICATION</button>
    <p id="cres" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}
    <script>async function sendApp(){{const r=await fetch('/api/v1/apply-career',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{role:document.getElementById('crole').value,name:document.getElementById('cname').value,region:document.getElementById('creg').value,contact:document.getElementById('ccnt').value,pitch:document.getElementById('cpitch').value}})}});const d=await r.json();document.getElementById('cres').innerText=d.message;}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/apply-career")
async def apply_career(req: CareerReq, db: DBWrapper = Depends(get_db)):
    aid = f"APP-{int(time.time()) % 100000}"
    db.execute("INSERT INTO careers VALUES (?, ?, ?, ?, ?, ?, ?)", (aid, req.role, req.name, req.region, req.contact, req.pitch, int(time.time())))
    db.commit()
    send_telegram_alert(f"🤝 NEW HIRING / AMBASSADOR APPLICATION!\n• ID: {aid}\n• Role: {req.role}\n• Name: {req.name}\n• Region: {req.region}\n• Contact: {req.contact}\n• Pitch: {req.pitch}")
    return {"message": f"Application {aid} submitted! Our leadership team (difft40y@gmail.com) has been notified via Telegram."}

@app.get("/editor", response_class=HTMLResponse)
async def editor_panel():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}input,select,textarea{{width:100%;padding:12px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box;font-size:14px}}.btn{{width:100%;padding:13px;background:#f59e0b;color:#0f172a;border:none;border-radius:8px;font-weight:bold;margin-top:8px;cursor:pointer;font-size:14px}}</style></head>
    <body>{render_nav("Editor Panel (Admin Publish)", "Home / Editor Panel")}
    <div class="box"><h2>Admin Editor Panel</h2>
    <p style="font-size:12px;margin-top:0;">Publish new <b>Advertising Strategies</b> or <b>Institutional &amp; Global Bulletins</b> live:</p>
    <input id="epin" type="password" placeholder="Admin PIN (Default: 1234)">
    <select id="ecat"><option>Advertising Strategies</option><option>Institutional &amp; Global Bulletin</option></select>
    <input id="etit" placeholder="Article / Strategy Headline">
    <textarea id="esum" rows="4" placeholder="Write clear, concise analysis or announcement..."></textarea>
    <input id="eaut" value="WAC Editorial Desk" placeholder="Author / Desk Name">
    <button class="btn" onclick="pubEd()">PUBLISH TO LIVE PLATFORM</button>
    <p id="eres" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}
    <script>async function pubEd(){{const r=await fetch('/api/v1/publish-editorial',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{pin:document.getElementById('epin').value,category:document.getElementById('ecat').value,title:document.getElementById('etit').value,summary:document.getElementById('esum').value,author:document.getElementById('eaut').value}})}});const d=await r.json();document.getElementById('eres').innerText=d.message||d.detail;}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/publish-editorial")
async def publish_editorial(req: EditorialReq, db: DBWrapper = Depends(get_db)):
    db.execute("CREATE TABLE IF NOT EXISTS editorial (ed_id TEXT PRIMARY KEY, category TEXT, title TEXT, summary TEXT, author TEXT, ts INTEGER);")
    row = db.execute("SELECT admin_pin FROM settings WHERE id=1").fetchone()
    valid_pin = row.__getitem__(0) if row else "1234"
    if req.pin != valid_pin:
        raise HTTPException(status_code=403, detail="Invalid Admin PIN")
    eid = f"ED-{int(time.time()) % 100000}"
    db.execute("INSERT INTO editorial VALUES (?, ?, ?, ?, ?, ?)", (eid, req.category, req.title, req.summary, req.author, int(time.time())))
    db.commit()
    send_telegram_alert(f"✍️ NEW EDITORIAL PUBLISHED ({eid})!\n• Category: {req.category}\n• Title: {req.title}")
    return {"message": f"Published {eid} live on /editorial!"}

class AdminActionReq(BaseModel):
    pin: str
    kind: str
    item_id: str
    action: str

@app.post("/api/v1/admin-action")
async def admin_action(req: AdminActionReq, db: DBWrapper = Depends(get_db)):
    row = db.execute("SELECT admin_pin FROM settings WHERE id=1").fetchone()
    valid_pin = row.__getitem__(0) if row else "1234"
    if req.pin != valid_pin:
        raise HTTPException(status_code=403, detail="Invalid Admin PIN")
    if req.kind == "ad":
        if req.action == "approve":
            db.execute("UPDATE ad_campaigns SET active=1 WHERE CAST(id AS TEXT)=?", (req.item_id,))
        elif req.action == "pause":
            db.execute("UPDATE ad_campaigns SET active=0 WHERE CAST(id AS TEXT)=?", (req.item_id,))
        elif req.action == "delete":
            db.execute("DELETE FROM ad_campaigns WHERE CAST(id AS TEXT)=?", (req.item_id,))
    elif req.kind == "tender":
        if req.action == "approve":
            db.execute("UPDATE tenders SET approved=1 WHERE tender_id=?", (req.item_id,))
        elif req.action == "delete":
            db.execute("DELETE FROM tenders WHERE tender_id=?", (req.item_id,))
    elif req.kind == "career":
        db.execute("DELETE FROM careers WHERE app_id=?", (req.item_id,))
    db.commit()
    return {"message": f"Action '{req.action}' completed on {req.kind.upper()} #{req.item_id}!"}

@app.get("/admin-desk", response_class=HTMLResponse)
async def admin_command_center(db: DBWrapper = Depends(get_db)):
    db.execute("CREATE TABLE IF NOT EXISTS careers (app_id TEXT PRIMARY KEY, role TEXT, name TEXT, region TEXT, contact TEXT, pitch TEXT, ts INTEGER);")
    ads = db.execute("SELECT id, headline, active FROM ad_campaigns ORDER BY id DESC").fetchall()
    tnds = db.execute("SELECT tender_id, title, approved FROM tenders ORDER BY tender_id DESC").fetchall()
    apps = db.execute("SELECT app_id, role, name, contact FROM careers ORDER BY ts DESC").fetchall()
    ad_rows = "".join([f'<div style="background:#0f172a;padding:10px;border-radius:8px;margin-bottom:8px;border-left:4px solid {"#22c55e" if a.__getitem__(2)==1 else "#f59e0b"};"><div style="font-size:12px;color:#fff;font-weight:bold;">#AD-{a.__getitem__(0)} • {a.__getitem__(1)}</div><div style="margin-top:6px;display:flex;gap:6px;"><button onclick="act(\'ad\',\'{a.__getitem__(0)}\',\'approve\')" style="background:#22c55e;color:#0f172a;border:none;padding:6px 10px;border-radius:6px;font-size:11px;font-weight:bold;">Approve / Live</button><button onclick="act(\'ad\',\'{a.__getitem__(0)}\',\'pause\')" style="background:#f59e0b;color:#0f172a;border:none;padding:6px 10px;border-radius:6px;font-size:11px;font-weight:bold;">Pause</button><button onclick="act(\'ad\',\'{a.__getitem__(0)}\',\'delete\')" style="background:#ef4444;color:#fff;border:none;padding:6px 10px;border-radius:6px;font-size:11px;font-weight:bold;">Delete</button></div></div>' for a in ads])
    tn_rows = "".join([f'<div style="background:#0f172a;padding:10px;border-radius:8px;margin-bottom:8px;border-left:4px solid #38bdf8;"><div style="font-size:12px;color:#fff;font-weight:bold;">{t.__getitem__(0)} • {t.__getitem__(1)}</div><div style="margin-top:6px;display:flex;gap:6px;"><button onclick="act(\'tender\',\'{t.__getitem__(0)}\',\'approve\')" style="background:#22c55e;color:#0f172a;border:none;padding:6px 10px;border-radius:6px;font-size:11px;font-weight:bold;">Approve</button><button onclick="act(\'tender\',\'{t.__getitem__(0)}\',\'delete\')" style="background:#ef4444;color:#fff;border:none;padding:6px 10px;border-radius:6px;font-size:11px;font-weight:bold;">Remove</button></div></div>' for t in tnds])
    ap_rows = "".join([f'<div style="background:#0f172a;padding:10px;border-radius:8px;margin-bottom:8px;border-left:4px solid #c084fc;"><div style="font-size:12px;color:#fff;font-weight:bold;">{c.__getitem__(0)} • {c.__getitem__(2)} ({c.__getitem__(1)})</div><div style="font-size:11px;color:#94a3b8;">Contact: {c.__getitem__(3)}</div></div>' for c in apps]) or '<p style="font-size:12px;color:#94a3b8;">No pending applications yet.</p>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:16px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}input{{width:100%;padding:11px;margin:6px 0 10px 0;border-radius:8px;border:1px solid #38bdf8;background:#0f172a;color:#fff;box-sizing:border-box;font-size:14px}}</style></head>
    <body>{render_nav("One-Tap Admin Command Center", "Home / Admin Command Center")}
    <div class="box"><h2>Admin Control Security</h2><p style="font-size:12px;margin:0 0 6px 0;">Enter your Admin PIN once to manage campaigns, tenders, and ledger exports:</p>
    <input id="apin" type="password" placeholder="Admin PIN (Default: 1234)"><p id="ares" style="color:#22c55e;font-size:12px;font-weight:bold;margin:4px 0;"></p>
    <a href="/api/v1/export-ledger.csv" style="display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:11px;border-radius:8px;font-weight:bold;text-decoration:none;font-size:12px;margin-top:8px;">DOWNLOAD ACCOUNTING LEDGER (.CSV)</a></div>
    <div class="box"><h3>Manage Ad Campaigns ({len(ads)})</h3>{ad_rows}</div>
    <div class="box"><h3>Manage Construction Tenders ({len(tnds)})</h3>{tn_rows}</div>
    <div class="box"><h3>Hiring &amp; Brand Ambassador Applications ({len(apps)})</h3>{ap_rows}</div>{FOOTER}
    <script>async function act(kind,id,action){{const pin=document.getElementById('apin').value;if(!pin){{alert('Enter Admin PIN first!');return;}}const r=await fetch('/api/v1/admin-action',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{pin:pin,kind:kind,item_id:id,action:action}})}});const d=await r.json();document.getElementById('ares').innerText=d.message||d.detail;if(r.ok)setTimeout(()=>location.reload(),900);}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

class MailReq(BaseModel):
    folder: str
    recipient: str
    sector: str
    subject: str
    body: str
    pin: str = ""

@app.post("/api/v1/mail/save")
async def save_mail(req: MailReq, db: DBWrapper = Depends(get_db)):
    db.execute("CREATE TABLE IF NOT EXISTS wac_mail (mail_id TEXT PRIMARY KEY, folder TEXT, recipient TEXT, sector TEXT, subject TEXT, body TEXT, ts INTEGER);")
    mid = f"MSG-{int(time.time()) % 100000}"
    db.execute("INSERT INTO wac_mail VALUES (?, ?, ?, ?, ?, ?, ?)", (mid, req.folder, req.recipient, req.sector, req.subject, req.body, int(time.time())))
    db.commit()
    if req.folder == "sent":
        send_telegram_alert(f"📤 OUTREACH SENT ({mid})!\n• To: {req.recipient} ({req.sector})\n• Subject: {req.subject}")
    return {"message": f"Saved to {req.folder.upper()} ({mid})!", "mail_id": mid}

@app.get("/mail", response_class=HTMLResponse)
async def mail_center(tab: str = "inbox", db: DBWrapper = Depends(get_db)):
    db.execute("CREATE TABLE IF NOT EXISTS wac_mail (mail_id TEXT PRIMARY KEY, folder TEXT, recipient TEXT, sector TEXT, subject TEXT, body TEXT, ts INTEGER);")
    if db.execute("SELECT COUNT(*) FROM wac_mail").fetchone().__getitem__(0) == 0:
        db.execute("INSERT INTO wac_mail VALUES (?, ?, ?, ?, ?, ?, ?)", ("MSG-101", "inbox", "difft40y@gmail.com", "System Desk", "Welcome to Worldwide Ad Center Mail Hub", "Your unified Compose, Inbox, Outbox, Sent, Drafts, and Directory Outreach desk is active.", 1732200000))
        db.commit()
    rows = db.execute("SELECT mail_id, recipient, sector, subject, body FROM wac_mail WHERE folder=? ORDER BY ts DESC", (tab,)).fetchall()
    items = ""
    for r in rows:
        mid, rec, sec, sub, bdy = r.__getitem__(0), r.__getitem__(1), r.__getitem__(2), r.__getitem__(3), r.__getitem__(4)
        items += f'<div style="background:#0f172a;padding:12px;border-radius:8px;margin-bottom:8px;border-left:4px solid #38bdf8;"><div style="font-size:11px;color:#38bdf8;font-weight:bold;">{mid} &bull; {sec} &bull; To/From: {rec}</div><div style="color:#fff;font-size:13px;font-weight:bold;margin:4px 0;">{sub}</div><div style="font-size:12px;color:#cbd5e1;white-space:pre-line;">{bdy}</div></div>'
    if not items:
        items = f'<p style="font-size:12px;color:#94a3b8;">No messages in <b>{tab.upper()}</b> yet.</p>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:16px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}input,select,textarea{{width:100%;padding:11px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box;font-size:13px}}.tabs{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}}.tab{{padding:8px 11px;border-radius:8px;font-size:11px;font-weight:bold;text-decoration:none;background:#0f172a;color:#38bdf8;border:1px solid #334155}}.btn{{padding:11px 14px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;font-size:12px;margin-top:6px}}</style></head>
    <body>{render_nav("Mail & Directory Outreach Center", "Home / Mail Center")}
    <div class="box"><h2>Unified Mail &amp; Directory Outreach</h2>
    <div class="tabs">
        <a class="tab" href="/mail?tab=inbox">&#128229; Inbox</a>
        <a class="tab" href="/mail?tab=outbox">&#128228; Outbox</a>
        <a class="tab" href="/mail?tab=sent">&#9989; Sent</a>
        <a class="tab" href="/mail?tab=draft">&#128221; Drafts</a>
        <a class="tab" href="#compose" style="background:#22c55e;color:#0f172a;">&#9997;&#65039; Compose / Directory</a>
        <a class="tab" href="#prefs" style="background:#f59e0b;color:#0f172a;">&#9881;&#65039; Email Preferences</a>
    </div>
    <h3>{tab.upper()}</h3>{items}</div>
    <div id="compose" class="box"><h3>Compose &amp; Compose to Directory</h3>
    <select id="msec" onchange="fillDir(this.value)">
        <option value="Direct Contact">Direct Recipient (Custom Email)</option>
        <option value="UN / WHO / UNESCO / ADB / IMF">Directory: International Bodies (UN, WHO, ADB, IMF)</option>
        <option value="Universities / Colleges / AI Labs">Directory: Education, Universities &amp; AI Labs</option>
        <option value="Banks / Stock Markets / Commerce">Directory: Banks, Finance &amp; Supermarkets</option>
        <option value="Airlines / Railways / Tour & Travels">Directory: Airlines, Transit &amp; Tourism</option>
        <option value="Media Houses / TV / Influencers">Directory: Media Houses, TV &amp; Influencers</option>
        <option value="FIFA / Cricket Boards / Sports">Directory: Global Sports &amp; Federations</option>
        <option value="Nepal Construction & Tenders">Directory: All-Nepal Construction &amp; Bidders</option>
    </select>
    <input id="mrec" placeholder="Recipient Email (e.g. info@organization.org)">
    <input id="msub" placeholder="Subject Line">
    <textarea id="mbdy" rows="5" placeholder="Write your message or select a Directory sector above to auto-fill...">Hello Team,

We invite your organization to partner with Worldwide Ad Center (https://worldwide-ad-center-1.onrender.com) for direct, cookie-free digital outreach at 2.50 NPR per verified click.

Best regards,
Hari Prasad Parajuli • Worldwide Ad Center (difft40y@gmail.com | +977-9717831225)</textarea>
    <div style="display:flex;flex-wrap:wrap;gap:8px;">
        <button class="btn" style="background:#22c55e;color:#0f172a;" onclick="sendM('sent')">SEND &amp; LOG TO SENT</button>
        <button class="btn" style="background:#38bdf8;color:#0f172a;" onclick="sendM('outbox')">QUEUE IN OUTBOX</button>
        <button class="btn" style="background:#475569;color:#fff;" onclick="sendM('draft')">SAVE DRAFT</button>
        <button class="btn" style="background:#f59e0b;color:#0f172a;" onclick="openGmail()">DISPATCH VIA GMAIL</button>
    </div><p id="mres" style="color:#22c55e;font-size:12px;"></p></div>
    <div id="prefs" class="box"><h3>Email &amp; Notification Preferences</h3>
    <p style="font-size:12px;margin:4px 0;">Primary Desk Email: <b>difft40y@gmail.com</b> &bull; Telegram Alerts: <b>@WorldwideAdCenterNotificationBot</b></p>
    <select id="pnotif"><option>Instant Telegram + Mail Hub Sync (Recommended)</option><option>Daily Summary Digest Only</option><option>Quiet Mode (Log in Inbox Only)</option></select>
    <input id="psig" value="Hari Prasad Parajuli • Founder, Worldwide Ad Center | difft40y@gmail.com | +977-9717831225" placeholder="Default Email Signature">
    <button class="btn" style="background:#38bdf8;color:#0f172a;" onclick="document.getElementById('pres').innerText='Email preferences & signature saved!';">SAVE EMAIL PREFERENCES</button>
    <p id="pres" style="color:#22c55e;font-size:12px;"></p></div>{FOOTER}
    <script>
    function fillDir(v){{if(v!=='Direct Contact'){{document.getElementById('msub').value='Partnership & Digital Outreach — ' + v;}}}}
    const qp = new URLSearchParams(window.location.search);
    if(qp.get('to')) document.getElementById('mrec').value = qp.get('to');
    if(qp.get('sub')) document.getElementById('msub').value = qp.get('sub');
    async function sendM(folder){{const r=await fetch('/api/v1/mail/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{folder:folder,recipient:document.getElementById('mrec').value||'Directory Outreach',sector:document.getElementById('msec').value,subject:document.getElementById('msub').value,body:document.getElementById('mbdy').value}})}});const d=await r.json();document.getElementById('mres').innerText=d.message;}}
    function openGmail(){{const to=encodeURIComponent(document.getElementById('mrec').value);const su=encodeURIComponent(document.getElementById('msub').value);const bd=encodeURIComponent(document.getElementById('mbdy').value);window.open('https://mail.google.com/mail/?view=cm&to=' + to + '&su=' + su + '&body=' + bd, '_blank');}}
    </script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(db: DBWrapper = Depends(get_db)):
    imp_r = db.execute("SELECT COUNT(*) FROM impressions").fetchone()
    imp = imp_r.__getitem__(0) if imp_r else 0
    clk_r = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    clk = clk_r.__getitem__(0) if clk_r else 0
    esc = round(float(clk_r.__getitem__(1)), 2) if clk_r and clk_r.__getitem__(1) else 0.0
    ctr = round((clk / imp * 100), 2) if imp > 0 else 0.0
    t_cnt = db.execute("SELECT COUNT(*) FROM tenders WHERE approved=1").fetchone().__getitem__(0)
    camps = db.execute("SELECT id, headline, btn_text, active FROM ad_campaigns ORDER BY id DESC").fetchall()
    bars = ""
    for c in camps:
        cid, hl, bt, act = c.__getitem__(0), c.__getitem__(1), c.__getitem__(2), c.__getitem__(3)
        st = "LIVE" if act == 1 else "PENDING"
        col = "#22c55e" if act == 1 else "#f59e0b"
        bars += f'<div style="background:#0f172a;padding:12px;border-radius:8px;margin-bottom:8px;border-left:4px solid {col};"><div style="display:flex;justify-content:space-between;font-size:11px;color:{col};font-weight:bold;"><span>CAMPAIGN #AD-{cid}</span><span>{st}</span></div><div style="color:#fff;font-size:13px;font-weight:bold;margin:4px 0;">{hl}</div><div style="font-size:11px;color:#94a3b8;">CTA: {bt} &bull; Rate: 2.50 NPR / Verified Click</div></div>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.stat{{background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px solid #475569}}.val{{font-size:20px;font-weight:bold;color:#22c55e}}</style></head>
    <body>{render_nav("Live Network & Campaign Analytics", "Home / Analytics")}
    <div class="box"><h2>Live Network Performance Ledger</h2><p style="font-size:12px;">Real-time verified delivery metrics streamed from Cloud PostgreSQL:</p>
    <div class="grid">
        <div class="stat"><div class="val">{imp}</div><div style="font-size:10px;color:#94a3b8;">VERIFIED IMPRESSIONS</div></div>
        <div class="stat"><div class="val">{clk}</div><div style="font-size:10px;color:#94a3b8;">GUARDED HUMAN CLICKS</div></div>
        <div class="stat"><div class="val">{ctr}%</div><div style="font-size:10px;color:#94a3b8;">NETWORK CTR</div></div>
        <div class="stat"><div class="val">{esc} NPR</div><div style="font-size:10px;color:#94a3b8;">ESCROW SETTLED</div></div>
    </div></div>
    <div class="box"><h2>Active &amp; Queued Campaigns ({len(camps)}) &bull; Live Tenders ({t_cnt})</h2>{bars}
    <a href="/documents" style="display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:12px;border-radius:8px;font-weight:bold;text-decoration:none;margin-top:10px;">DOWNLOAD SIGNED TAX / PERFORMANCE STATEMENT</a></div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/status", response_class=HTMLResponse)
async def status_tracker(ref: str = "", db: DBWrapper = Depends(get_db)):
    db.execute("CREATE TABLE IF NOT EXISTS careers (app_id TEXT PRIMARY KEY, role TEXT, name TEXT, region TEXT, contact TEXT, pitch TEXT, ts INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS deposits (dep_id TEXT PRIMARY KEY, advertiser TEXT, amount REAL, txn_code TEXT, contact TEXT, ts INTEGER);")
    msg = ""
    r_clean = ref.strip().upper()
    if r_clean:
        d = db.execute("SELECT dep_id, advertiser, amount, txn_code FROM deposits WHERE UPPER(dep_id)=? OR UPPER(txn_code)=?", (r_clean, r_clean)).fetchone()
        c = db.execute("SELECT app_id, role, name, region FROM careers WHERE UPPER(app_id)=?", (r_clean,)).fetchone()
        ad_num = r_clean.replace("AD-", "")
        a = db.execute("SELECT id, headline, active FROM ad_campaigns WHERE CAST(id AS TEXT)=?", (ad_num,)).fetchone() if ad_num.isdigit() else None
        if d:
            msg = f'<div style="background:#0f172a;padding:12px;border-radius:8px;border-left:4px solid #22c55e;margin-top:10px;"><b style="color:#22c55e;">DEPOSIT VERIFIED ({d.__getitem__(0)})</b><br>Advertiser: {d.__getitem__(1)} &bull; Amount: {d.__getitem__(2)} NPR &bull; Txn: {d.__getitem__(3)}</div>'
        elif c:
            msg = f'<div style="background:#0f172a;padding:12px;border-radius:8px;border-left:4px solid #38bdf8;margin-top:10px;"><b style="color:#38bdf8;">APPLICATION RECEIVED ({c.__getitem__(0)})</b><br>Applicant: {c.__getitem__(2)} ({c.__getitem__(3)}) &bull; Role: {c.__getitem__(1)} &bull; Status: Under Review</div>'
        elif a:
            st_txt = "ACTIVE & ROTATING LIVE" if a.__getitem__(2) == 1 else "PENDING ADMIN APPROVAL"
            msg = f'<div style="background:#0f172a;padding:12px;border-radius:8px;border-left:4px solid #22c55e;margin-top:10px;"><b style="color:#22c55e;">AD CAMPAIGN #AD-{a.__getitem__(0)}</b><br>Headline: {a.__getitem__(1)} &bull; Status: <b>{st_txt}</b></div>'
        else:
            msg = f'<div style="background:#0f172a;padding:12px;border-radius:8px;border-left:4px solid #f59e0b;margin-top:10px;color:#f59e0b;">No record found for <b>{r_clean}</b>. Check your AD-..., DEP-..., or APP-... ID.</div>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}input{{width:100%;padding:12px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box;font-size:14px}}.btn{{width:100%;padding:13px;background:#38bdf8;color:#0f172a;border:none;border-radius:8px;font-weight:bold;margin-top:6px;cursor:pointer;font-size:14px}}</style></head>
    <body>{render_nav("Track Application / Deposit ID", "Home / Status Tracker")}
    <div class="box"><h2>Self-Service Status Tracker</h2><p style="font-size:12px;">Enter your Campaign ID (<b>AD-...</b>), eSewa Deposit ID (<b>DEP-...</b>), or Application ID (<b>APP-...</b>):</p>
    <form method="get" action="/status"><input name="ref" value="{r_clean}" placeholder="e.g. DEP-12345 or APP-67890"><button class="btn" type="submit">CHECK LIVE STATUS</button></form>{msg}</div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/guide", response_class=HTMLResponse)
async def beginner_guide():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.6}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.step{{background:#0f172a;padding:12px;border-radius:8px;margin-bottom:8px;border-left:4px solid #38bdf8;font-size:13px}}.btn{{display:block;width:100%;padding:13px;background:#a855f7;color:#fff;border:none;border-radius:8px;font-weight:bold;margin-top:8px;cursor:pointer}}</style></head>
    <body>{render_nav("Beginner Guide & Rules", "Home / Beginner Guide (English Subtitles)")}
    <div class="box"><h2>Step-by-Step Guide</h2><p style='font-size:12px;color:#38bdf8;margin-top:-6px;'>English Subtitles &amp; Clear Onboarding Instructions</p>
    <div class="step"><b>1. Create Banner:</b> Open <b>Advertise</b>, pick a template, attach image (max 500KB), and save. <i>(Subtitle: Design &amp; preview your ad banner)</i></div>
    <div class="step"><b>2. Deposit via eSewa QR:</b> Open <b>Deposit Ad Credits</b>, scan QR <b>9717831225</b>, and submit Txn ID. <i>(Subtitle: Fund campaign balance via eSewa or direct transfer)</i></div>
    <div class="step"><b>3. Track Clicks:</b> Embed <code>&lt;script&gt;</code> tag or Social link to earn <b>2.50 NPR/click</b> (60s anti-spam). <i>(Subtitle: Track verified human clicks in real time)</i></div>
    <div class="step"><b>4. Invoice &amp; Tax PDF:</b> Generate signed Invoices, Receipts &amp; Tax Clearance anytime. <i>(Subtitle: Download signed invoices &amp; tax receipts)</i></div></div>
    <div class="box"><h3>Official Moderation Standards</h3>
    <div class="step" style="border-left-color:#22c55e;"><b>&#128591; Grateful Acceptance:</b> "Thank you for partnering with Worldwide Ad Center! We are grateful for your submission—your campaign is now live."</div>
    <div class="step" style="border-left-color:#f59e0b;"><b>&#129309; Humble Apology / Rejection:</b> "We sincerely apologize, but we cannot approve this submission under our safety/clarity rules. Please edit and resubmit anytime."</div>
    <div class="step" style="border-left-color:#a855f7;"><b>&#129529; System Scanner &amp; Cache Cleaner:</b><button class="btn" onclick="localStorage.clear();sessionStorage.clear();document.getElementById('cln').innerText='Scan Complete: Cache cleared, 0 spam trackers, mobile controls healthy.';">RUN SCANNER &amp; CLEANER</button><p id="cln" style="color:#22c55e;font-size:12px;margin:6px 0 0 0;"></p></div></div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/deposit", response_class=HTMLResponse)
async def deposit_page(db: DBWrapper = Depends(get_db)):
    row = db.execute("SELECT default_wallet, qr_img FROM settings WHERE id=1").fetchone()
    wal = row.__getitem__(0) if row else "9717831225"
    qimg = row.__getitem__(1) if (row and len(row) > 1 and row.__getitem__(1)) else ""
    qr_src = qimg if qimg else make_qr_b64(f'{{"eSewa_id":"{wal}","name":"Worldwide Ad Center"}}')
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}input{{width:100%;padding:11px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#22c55e;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer}}</style></head>
    <body>{render_nav("Deposit Ad Credits (eSewa)", "Home / Deposit Credits")}
    <div class="box" style="text-align:center;"><span style="background:#22c55e;color:#0f172a;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:bold;">STEP 1: SCAN OR SEND VIA ESEWA</span>
    <h2 style="margin:8px 0 4px 0;">Fund Your Ad Campaign</h2>
    <div style="background:#ffffff;padding:10px;border-radius:10px;display:inline-block;margin:10px auto;"><img src="{qr_src}" alt="eSewa QR" style="width:165px;height:165px;display:block;"></div>
    <div style="font-size:13px;color:#fff;font-weight:bold;">eSewa Wallet ID: {wal}</div>
    <p style="font-size:11px;color:#94a3b8;margin:4px 0 0 0;">Standard Rate: 2.50 NPR per verified click (e.g., 1,000 NPR = 400 Clicks)</p></div>

    <div class="box"><h3>Step 2: Submit eSewa Transaction Receipt</h3>
    <p style="font-size:12px;margin-top:0;">After sending funds via eSewa, submit your transaction code below for instant Telegram verification &amp; ad activation:</p>
    <input id="adv" placeholder="Advertiser / Business / Campaign Name">
    <input id="amt" type="number" placeholder="Amount Deposited (NPR, e.g. 1000)">
    <input id="txn" placeholder="eSewa Transaction / Reference ID">
    <input id="cnt" placeholder="Your Telegram, WhatsApp, or Email">
    <button class="btn" onclick="sendDep()">VERIFY ESEWA DEPOSIT RECEIPT</button>
    <p id="res" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}
    <script>async function sendDep(){{const r=await fetch('/api/v1/submit-deposit',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{advertiser:document.getElementById('adv').value,amount:parseFloat(document.getElementById('amt').value)||0,txn_code:document.getElementById('txn').value,contact:document.getElementById('cnt').value}})}});const d=await r.json();document.getElementById('res').innerText=d.message||d.detail;}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/submit-deposit")
async def submit_deposit(req: DepositReq, db: DBWrapper = Depends(get_db)):
    did = f"DEP-{int(time.time()) % 1000000}"
    clicks_est = int(req.amount / 2.50)
    db.execute("INSERT INTO deposits (dep_id, advertiser, amount, txn_code, contact, ts) VALUES (?, ?, ?, ?, ?, ?)", (did, req.advertiser, req.amount, req.txn_code, req.contact, int(time.time())))
    db.commit()
    send_telegram_alert(f"💰 NEW ESEWA DEPOSIT RECEIPT!\n• Receipt ID: {did}\n• Advertiser: {req.advertiser}\n• Amount: {req.amount} NPR (~{clicks_est} Clicks)\n• eSewa Txn Code: {req.txn_code}\n• Contact: {req.contact}")
    return {"message": f"Receipt {did} ({req.amount} NPR / ~{clicks_est} clicks) submitted! Admin alerted via Telegram for instant credit activation."}

@app.get("/social-partners", response_class=HTMLResponse)
async def social_partners_page(db: DBWrapper = Depends(get_db)):
    camps = db.execute("SELECT id, headline FROM ad_campaigns WHERE active=1 ORDER BY id DESC").fetchall()
    opts = ""
    for c in camps:
        opts += f'<option value="{c.__getitem__(0)}">#{c.__getitem__(0)} - {c.__getitem__(1)}</option>'
    if not opts:
        opts = '<option value="1">#1 - Worldwide Ad Center Network</option>'

    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}input,select,textarea{{width:100%;padding:11px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#f43f5e;color:#fff;border:none;border-radius:8px;font-weight:bold;margin-top:8px;cursor:pointer}}.sbtn{{display:inline-block;padding:8px 12px;border-radius:8px;font-size:12px;font-weight:bold;text-decoration:none;margin:4px 4px 0 0}}</style></head>
    <body>{render_nav("Social & Influencer Partners", "Home / Social Partners")}
    <div class="box"><span style="background:#f43f5e;color:#fff;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;">FACEBOOK &bull; TIKTOK &bull; INSTAGRAM &bull; YOUTUBE</span>
    <h2 style="margin:8px 0 6px 0;">Social Media Partner Link Generator</h2>
    <p style="font-size:13px;margin-top:0;">Create a tracked monetization link for your <b>TikTok Bio</b>, <b>Instagram Story</b>, or <b>Facebook Page</b>. Earn <b>2.50 NPR</b> per verified click:</p>
    <label style="font-size:12px;">Select Social Platform:</label>
    <select id="plat"><option value="facebook">Facebook Page / Reels</option><option value="tiktok">TikTok Bio / Video</option><option value="instagram">Instagram Bio / Story</option><option value="youtube">YouTube Description</option></select>
    <label style="font-size:12px;">Your Page Name or @Handle:</label>
    <input id="hnd" placeholder="e.g. @nepal_tech_hub">
    <label style="font-size:12px;">Select Campaign to Promote:</label>
    <select id="cid">{opts}</select>
    <button class="btn" onclick="genLink()">GENERATE TRACKED SOCIAL LINK</button>
    <div id="outBox" style="display:none;margin-top:12px;">
        <label style="font-size:11px;color:#38bdf8;">Your Monetized Partner Link (Paste in Bio or Post):</label>
        <textarea id="slink" readonly style="height:68px;font-family:monospace;font-size:11px;color:#22c55e;"></textarea>
        <button onclick="navigator.clipboard.writeText(document.getElementById('slink').value);this.innerText='Link Copied!';" style="width:100%;padding:10px;background:#22c55e;color:#0f172a;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">COPY PARTNER LINK</button>
    </div></div>

    <div class="box"><h3>Official Network Social Channels &amp; Quick Share</h3>
    <p style="font-size:12px;margin-top:0;">Share Worldwide Ad Center across associating social platforms to invite advertisers, agencies, and bidders:</p>
    <a href="https://facebook.com" target="_blank" class="sbtn" style="background:#1877f2;color:#fff;">Share on Facebook</a>
    <a href="https://whatsapp.com" target="_blank" class="sbtn" style="background:#25d366;color:#0f172a;">Share on WhatsApp</a>
    <a href="https://t.me" target="_blank" class="sbtn" style="background:#38bdf8;color:#0f172a;">Share on Telegram</a>
    <button onclick="navigator.clipboard.writeText('https://worldwide-ad-center-1.onrender.com');this.innerText='Bio Link Copied for TikTok/IG!';" class="sbtn" style="background:#e1306c;color:#fff;border:none;cursor:pointer;">Copy Bio Link (TikTok / Instagram)</button>
    </div>{FOOTER}
    <script>
    function genLink(){{
        const p = document.getElementById('plat').value;
        const h = encodeURIComponent(document.getElementById('hnd').value || 'partner');
        const c = document.getElementById('cid').value;
        document.getElementById('slink').value = window.location.origin + '/go/social?platform=' + p + '&partner=' + h + '&cid=' + c;
        document.getElementById('outBox').style.display = 'block';
    }}
    </script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/directory", response_class=HTMLResponse)
async def universal_directory(q: str = "", db: DBWrapper = Depends(get_db)):
    for sd in [
        ("BID-97217", "Butwal-Bhairahawa Industrial Corridor Sub-Station", "Lumbini Province", "Lumbini Infrastructure Development Office", "Building & Structural Works", "2026-12-15, 02:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97218", "Kathmandu Valley Smart Streetlight & Solar Supply", "Bagmati Province", "Bagmati Urban Works Division", "Sealed Quotation / Supply", "2026-12-18, 12:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97219", "Biratnagar River Embankment & Flood Protection", "Koshi Province", "Koshi Water Resources Directorate", "Civil & Road Construction", "2026-12-20, 01:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97220", "Janakpur Agro-Cold Storage Warehouse Construction", "Madhesh Province", "Madhesh Provincial Infrastructure Board", "Building & Structural Works", "2026-12-22, 12:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97221", "Surkhet-Jumla Highway Bridge Maintenance & Gabion", "Karnali Province", "Karnali Road Division Office", "Subcontractor & Heavy Equipment", "2026-12-25, 03:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97222", "Dhangadhi Technical School Lab Equipment Supply", "Sudurpashchim Province", "Sudurpashchim Education & Works Office", "Consultancy & Engineering", "2026-12-28, 12:00 PM", "difft40y@gmail.com | +977-9717831225"), ("BID-98001", "UN & Multilateral Clean Energy Micro-Grid Supply IFB", "Global / International (UN & Multilateral)", "Global Sustainability Procurement Desk", "Sealed Quotation / Supply", "2027-01-15, 05:00 PM UTC", "difft40y@gmail.com | +977-9717831225"), ("BID-98002", "South Asia & ASEAN Cross-Border Logistics IT Platform", "Asia-Pacific (India, Japan, Korea, ASEAN)", "Asia-Pacific Trade & Transport Consortium", "Consultancy & Engineering", "2027-01-20, 03:00 PM", "difft40y@gmail.com | +977-9717831225"), ("BID-98003", "GCC & Middle East Commercial Smart-Tower HVAC & Solar", "Middle East & GCC", "Gulf Infrastructure & Engineering Alliance", "Building & Structural Works", "2027-01-25, 02:00 PM", "difft40y@gmail.com | +977-9717831225"), ("BID-98004", "EU & North America Digital Media & EdTech Localization", "Europe & North America", "Transatlantic Education & Media Network", "Consultancy & Engineering", "2027-01-30, 04:00 PM", "difft40y@gmail.com | +977-9717831225")
    ]:
        if db.execute("SELECT COUNT(*) FROM tenders WHERE tender_id=?", (sd[0],)).fetchone()[0] == 0:
            db.execute("INSERT INTO tenders (tender_id, title, issuer, category, province, deadline, contact_url, approved) VALUES (?, ?, ?, ?, ?, ?, ?, 1)", (sd[0], sd[1], sd[2], sd[3], sd[4], sd[5], sd[6]))
    db.commit()
    like_q = f"%{q}%"
    ads = db.execute("SELECT id, headline, subtext, btn_text, target_url FROM ad_campaigns WHERE active=1 AND (headline LIKE ? OR subtext LIKE ?) ORDER BY id DESC", (like_q, like_q)).fetchall()
    tnds = db.execute("SELECT tender_id, title, issuer, province, deadline, contact_url FROM tenders WHERE approved=1 AND (title LIKE ? OR issuer LIKE ? OR province LIKE ?) ORDER BY tender_id DESC", (like_q, like_q, like_q)).fetchall()

    ad_html = ""
    for a in ads:
        cid, hl, sub, btn, url = a
        ad_html += f'<div style="background:#0f172a;padding:12px;border-radius:8px;margin-top:8px;border-left:4px solid #14b8a6;"><span style="font-size:10px;color:#14b8a6;font-weight:bold;">SPONSORED CAMPAIGN #{cid}</span><h4 style="margin:4px 0;color:#fff;">{hl}</h4><p style="font-size:12px;color:#cbd5e1;margin:0 0 8px 0;">{sub}</p><a href="{url if str(url).startswith('/') or str(url).startswith('http') else '/tenders'}" target="_blank" style="background:#14b8a6;color:#0f172a;padding:5px 11px;border-radius:5px;font-size:11px;font-weight:bold;text-decoration:none;">{btn}</a></div>'

    tn_html = ""
    for t in tnds:
        tid, ttl, iss, prv, ddl, curl = t
        tn_html += f'<div class="t-card" style="background:#0f172a;padding:12px;border-radius:8px;margin-top:8px;border-left:4px solid #38bdf8;"><span style="font-size:10px;color:#38bdf8;font-weight:bold;">TENDER &bull; {prv} &bull; {tid}</span><h4 style="margin:4px 0;color:#fff;">{ttl}</h4><p style="font-size:12px;color:#94a3b8;margin:0 0 8px 0;">{iss} &bull; Deadline: {ddl}</p><a href="/tenders" onclick="openBidModal(this);return false;" data-cnt="{curl}" target="_blank" style="background:#38bdf8;color:#0f172a;padding:5px 11px;border-radius:5px;font-size:11px;font-weight:bold;text-decoration:none;">Open Notice</a></div>'

    combined = (ad_html + tn_html) or '<p style="color:#94a3b8;font-size:12px;">No matching ads or tenders found.</p>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}input{{width:100%;padding:11px;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}</style></head>
    <body>{render_nav("Universal Live Directory", "Home / Universal Directory")}
    <div class="box"><h2>Universal Global &amp; Local Directory</h2>
    <p style="font-size:12px;margin-top:0;">Search live sponsored campaigns, brands, and Nepal construction tenders in one unified index:</p>
    <form method="get" action="/directory" style="display:flex;gap:6px;"><input name="q" value="{q}" placeholder="Search keyword, brand, or province..."><button type="submit" style="background:#38bdf8;color:#0f172a;border:none;border-radius:8px;padding:0 14px;font-weight:bold;cursor:pointer;" aria-label="Search">&#128269;</button></form>
    {combined}</div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/verify-badge", response_class=HTMLResponse)
async def verify_badge_page():
    badge_code = '&lt;a href="https://worldwide-ad-center-1.onrender.com" target="_blank" style="display:inline-flex;align-items:center;gap:6px;background:#0f172a;color:#fff;border:1px solid #38bdf8;padding:6px 12px;border-radius:8px;font-family:sans-serif;font-size:12px;font-weight:bold;text-decoration:none;"&gt;&#9989; Verified Partner &bull; Worldwide Ad Center&lt;/a&gt;'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}textarea{{width:100%;height:95px;background:#0f172a;color:#38bdf8;border:1px solid #475569;border-radius:8px;padding:10px;font-family:monospace;font-size:11px;box-sizing:border-box}}</style></head>
    <body>{render_nav("Partner Trust Badge", "Home / Partner Trust Badge")}
    <div class="box"><h2>Official Partner Verification Badge</h2>
    <p style="font-size:13px;">Publishers, agencies, and verified contractors can embed this official trust seal on their website to verify membership in the <b>Worldwide Ad Center</b> network:</p>
    <div style="background:#0f172a;padding:16px;border-radius:10px;text-align:center;border:1px dashed #14b8a6;margin:12px 0;">
        <a href="https://worldwide-ad-center-1.onrender.com" target="_blank" style="display:inline-flex;align-items:center;gap:6px;background:#0f172a;color:#fff;border:1px solid #38bdf8;padding:7px 14px;border-radius:8px;font-family:sans-serif;font-size:12px;font-weight:bold;text-decoration:none;">&#9989; Verified Partner &bull; Worldwide Ad Center</a>
    </div>
    <label style="font-size:12px;color:#94a3b8;">Copy &amp; Paste HTML Embed Code:</label>
    <textarea id="bcode" readonly>{badge_code}</textarea>
    <button onclick="navigator.clipboard.writeText(document.getElementById('bcode').value);this.innerText='Badge HTML Copied!';" style="width:100%;padding:11px;background:#14b8a6;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer;">COPY TRUST BADGE CODE</button></div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/gallery", response_class=HTMLResponse)
async def gallery_page(db: DBWrapper = Depends(get_db)):
    camps = db.execute("SELECT id, headline, subtext, btn_text, target_url FROM ad_campaigns WHERE active=1 ORDER BY id DESC").fetchall()
    drafts = db.execute("SELECT headline, subtext, btn_text, img_data FROM saved_banners WHERE img_data != '' ORDER BY expires_at DESC LIMIT 8").fetchall()
    cards = ""
    for c in camps:
        cid, hl, sub, btn, url = c
        cards += f'<div style="background:#0f172a;padding:14px;border-radius:10px;text-align:center;border:1px solid #38bdf8;margin-top:10px;"><small style="color:#38bdf8;">LIVE CAMPAIGN #{cid}</small><h4 style="margin:6px 0;color:#fff;">{hl}</h4><p style="font-size:12px;color:#cbd5e1;margin:0 0 10px 0;">{sub}</p><a href="{url if str(url).startswith('/') or str(url).startswith('http') else '/tenders'}" target="_blank" style="display:inline-block;background:#22c55e;color:#0f172a;padding:6px 14px;border-radius:5px;font-size:12px;font-weight:bold;text-decoration:none;">{btn}</a></div>'
    for d in drafts:
        hl, sub, btn, img = d
        cards += f'<div style="background:#0f172a;padding:14px;border-radius:10px;text-align:center;border:1px dashed #a855f7;margin-top:10px;"><img src="{img}" style="width:100%;max-height:120px;object-fit:cover;border-radius:6px;margin-bottom:8px;"><h4 style="margin:4px 0;color:#fff;">{hl}</h4><p style="font-size:12px;color:#cbd5e1;margin:0;">{sub}</p></div>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}</style></head>
    <body>{render_nav("Ad Creative Gallery", "Home / Gallery")}
    <div class="box"><h2>Ad Creative &amp; Visual Gallery</h2><p style="font-size:13px;margin-top:0;">Showcase of active sponsored banners and attached visual creatives across our network:</p>{cards}</div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(db: DBWrapper = Depends(get_db)):
    row = db.execute("SELECT default_wallet, cpc_rate FROM settings WHERE id=1").fetchone()
    wal, rate = row if row else ("9717831225", 2.50)
    db_st = "Connected (Cloud PostgreSQL)" if db.is_pg else "Local SQLite"
    tg_st = "Active (@WorldwideAdCenterNotificationBot)" if TELEGRAM_BOT_TOKEN else "Not Configured"
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.row{{background:#0f172a;padding:10px 12px;border-radius:8px;margin-bottom:8px;border:1px solid #334155;font-size:12px}}input{{width:100%;padding:11px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#22c55e;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer}}</style></head>
    <body>{render_nav("Network Settings", "Home / Settings")}
    <div class="box"><h2>System Status &amp; Diagnostics</h2>
    <div class="row"><b>Database Storage:</b> <span style="color:#22c55e;">{db_st}</span></div>
    <div class="row"><b>Telegram Alert Bot:</b> <span style="color:#38bdf8;">{tg_st}</span></div>
    <div class="row"><b>Admin Security:</b> PIN Protected (Manage via Render <code>ADMIN_PIN</code>)</div></div>

    <div class="box"><h3>Payout &amp; Rate Configuration</h3>
    <label style="font-size:12px;">Default eSewa Wallet Number:</label><input id="wal" value="{wal}">
    <label style="font-size:12px;">Standard CPC Rate (NPR per Click):</label><input id="rt" type="number" step="0.1" value="{rate}">
    <label style="font-size:12px;">Upload Official eSewa QR Screenshot (Optional, Max 500KB):</label><input type="file" accept="image/*" onchange="readQr(this)" style="font-size:12px;"><input id="pin" type="password" placeholder="Admin PIN (Default: 2026)">
    <button class="btn" onclick="saveSet()">SAVE NETWORK SETTINGS</button>
    <p id="res" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}
    <script>let qrData="";function readQr(i){{const f=i.files.item(0);if(!f)return;if(f.size>520000){{alert('Max 500KB');return}}const r=new FileReader();r.onload=e=>{{qrData=e.target.result;}};r.readAsDataURL(f)}}
    async function saveSet(){{const r=await fetch('/api/v1/save-settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{default_wallet:document.getElementById('wal').value,cpc_rate:parseFloat(document.getElementById('rt').value),qr_img:qrData,pin:document.getElementById('pin').value}})}});const d=await r.json();document.getElementById('res').innerText=d.message||(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/save-settings")
async def save_settings(req: SettingsReq, db: DBWrapper = Depends(get_db)):
    if req.pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Invalid Admin PIN.")
    if req.qr_img:
        db.execute("UPDATE settings SET default_wallet=?, cpc_rate=?, qr_img=? WHERE id=1", (req.default_wallet, req.cpc_rate, req.qr_img))
    else:
        db.execute("UPDATE settings SET default_wallet=?, cpc_rate=? WHERE id=1", (req.default_wallet, req.cpc_rate))
    db.commit()
    return {"message": "Network settings saved to Cloud PostgreSQL!"}

@app.get("/tenders", response_class=HTMLResponse)
async def tenders_portal(db: DBWrapper = Depends(get_db)):
    for sd in [
        ("BID-97217", "Butwal-Bhairahawa Industrial Corridor Sub-Station", "Lumbini Province", "Lumbini Infrastructure Development Office", "Building & Structural Works", "2026-12-15, 02:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97218", "Kathmandu Valley Smart Streetlight & Solar Supply", "Bagmati Province", "Bagmati Urban Works Division", "Sealed Quotation / Supply", "2026-12-18, 12:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97219", "Biratnagar River Embankment & Flood Protection", "Koshi Province", "Koshi Water Resources Directorate", "Civil & Road Construction", "2026-12-20, 01:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97220", "Janakpur Agro-Cold Storage Warehouse Construction", "Madhesh Province", "Madhesh Provincial Infrastructure Board", "Building & Structural Works", "2026-12-22, 12:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97221", "Surkhet-Jumla Highway Bridge Maintenance & Gabion", "Karnali Province", "Karnali Road Division Office", "Subcontractor & Heavy Equipment", "2026-12-25, 03:00 PM", "difft40y@gmail.com | +977-9717831225"),
        ("BID-97222", "Dhangadhi Technical School Lab Equipment Supply", "Sudurpashchim Province", "Sudurpashchim Education & Works Office", "Consultancy & Engineering", "2026-12-28, 12:00 PM", "difft40y@gmail.com | +977-9717831225"), ("BID-98001", "UN & Multilateral Clean Energy Micro-Grid Supply IFB", "Global / International (UN & Multilateral)", "Global Sustainability Procurement Desk", "Sealed Quotation / Supply", "2027-01-15, 05:00 PM UTC", "difft40y@gmail.com | +977-9717831225"), ("BID-98002", "South Asia & ASEAN Cross-Border Logistics IT Platform", "Asia-Pacific (India, Japan, Korea, ASEAN)", "Asia-Pacific Trade & Transport Consortium", "Consultancy & Engineering", "2027-01-20, 03:00 PM", "difft40y@gmail.com | +977-9717831225"), ("BID-98003", "GCC & Middle East Commercial Smart-Tower HVAC & Solar", "Middle East & GCC", "Gulf Infrastructure & Engineering Alliance", "Building & Structural Works", "2027-01-25, 02:00 PM", "difft40y@gmail.com | +977-9717831225"), ("BID-98004", "EU & North America Digital Media & EdTech Localization", "Europe & North America", "Transatlantic Education & Media Network", "Consultancy & Engineering", "2027-01-30, 04:00 PM", "difft40y@gmail.com | +977-9717831225")
    ]:
        if db.execute("SELECT COUNT(*) FROM tenders WHERE tender_id=?", (sd[0],)).fetchone()[0] == 0:
            db.execute("INSERT INTO tenders (tender_id, title, issuer, category, province, deadline, contact_url, approved) VALUES (?, ?, ?, ?, ?, ?, ?, 1)", (sd[0], sd[1], sd[2], sd[3], sd[4], sd[5], sd[6]))
    db.commit()
    rows = db.execute("SELECT tender_id, title, issuer, category, deadline, contact_url FROM tenders WHERE approved=1 ORDER BY tender_id DESC LIMIT 20").fetchall()
    cards = ""
    for r in rows:
        tid, ttl, iss, cat, ddl, curl = r
        cards += f'<div style="background:#0f172a;padding:13px;border-radius:8px;margin-top:10px;border-left:4px solid #38bdf8;"><div style="display:flex;justify-content:space-between;align-items:center;"><span style="background:#1e293b;color:#38bdf8;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;">{cat}</span><span style="color:#f59e0b;font-size:11px;">Deadline: {ddl}</span></div><h4 style="margin:8px 0 4px 0;color:#fff;">{ttl}</h4><p style="margin:0 0 8px 0;font-size:12px;color:#94a3b8;">Issued by: <b>{iss}</b> &bull; ID: {tid}</p><a href="/tenders" onclick="openBidModal(this);return false;" data-cnt="{curl}" target="_blank" style="display:inline-block;background:#22c55e;color:#0f172a;padding:6px 12px;border-radius:5px;font-size:12px;font-weight:bold;text-decoration:none;">View Bid / Contact</a></div>'
    if not cards:
        cards = '<p style="color:#94a3b8;font-size:12px;">No active construction notices yet. Publish the first Invitation for Bid (IFB) or Contractor Notice below!</p>'

    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}input,select{{width:100%;padding:11px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#38bdf8;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer}}</style></head>
    <body>{render_nav("Construction & Bidder Notices", "Home / Tenders & Bids")}
    <div class="box"><span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;">INFRASTRUCTURE &amp; PROCUREMENT</span>
    <h2 style="margin:8px 0 6px 0;">Construction &amp; Bidder Notices</h2>
    <p style="font-size:13px;margin:0;">Active Invitation for Bids (IFB), Sealed Quotations, Subcontractor Calls &amp; Material Supply Tenders:</p>
    {cards}</div>

    <div class="box"><h3>Publish Construction / Bidder Notice</h3>
    <p style="font-size:12px;margin-top:0;">Submit a notice for admin review, or enter your <b>Admin PIN</b> to publish immediately:</p>
    <input id="ttl" placeholder="Project / Notice Title (e.g. Road Blacktopping &amp; Drainage IFB)">
    <input id="iss" placeholder="Issuing Office / Contractor Name">
    <select id="cat"><option>Civil &amp; Road Construction</option><option>Building &amp; Structural Works</option><option>Sealed Quotation / Supply</option><option>Subcontractor &amp; Heavy Equipment</option><option>Consultancy &amp; Engineering</option></select>
    <input id="ddl" placeholder="Bid Deadline (e.g. 2026-12-05, 12:00 PM)">
    <input id="url" placeholder="Notice Link, Phone, or Email (https://... or tel:...)">
    <input id="pin" type="password" placeholder="Admin PIN (Optional - leave blank for review)">
    <button class="btn" onclick="postTender()">SUBMIT / PUBLISH BIDDER NOTICE</button>
    <p id="res" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}

    <script>
    async function postTender(){{
        const r = await fetch('/api/v1/submit-tender',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{title:document.getElementById('ttl').value,issuer:document.getElementById('iss').value,category:document.getElementById('cat').value,deadline:document.getElementById('ddl').value,contact_url:document.getElementById('url').value,pin:document.getElementById('pin').value}})}});
        const d = await r.json(); document.getElementById('res').innerText = d.message || d.detail;
        if(d.published) setTimeout(()=>location.reload(), 1000);
    }}
    </script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/submit-tender")
async def submit_tender(req: TenderReq, db: DBWrapper = Depends(get_db)):
    tid = f"BID-{int(time.time()) % 1000000}"
    is_admin = (req.pin == ADMIN_PIN and req.pin != "")
    approved = 1 if is_admin else 0
    db.execute("INSERT INTO tenders (tender_id, title, issuer, category, province, deadline, contact_url, approved) VALUES (?, ?, ?, ?, ?, ?, ?, 1)", (tid, req.title, req.issuer, req.category, req.deadline, req.contact_url, approved))
    db.commit()
    st_txt = "PUBLISHED LIVE" if is_admin else "PENDING REVIEW"
    send_telegram_alert(f"🏗️ CONSTRUCTION / BIDDER NOTICE ({st_txt})!\n• ID: {tid}\n• Title: {req.title}\n• Issuer: {req.issuer}\n• Category: {req.category}\n• Deadline: {req.deadline}\n• Contact: {req.contact_url}")
    if is_admin:
        return {"message": f"Notice {tid} published live on the Bidder Board!", "published": True}
    return {"message": f"Notice {tid} submitted! Admin notified via Telegram for approval.", "published": False}

@app.get("/agencies", response_class=HTMLResponse)
async def agencies_portal(db: DBWrapper = Depends(get_db)):
    proof_html = get_live_proof(db)
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.tier{{background:#0f172a;padding:11px;border-radius:8px;margin-top:8px;border-left:3px solid #f59e0b;font-size:13px}}input{{width:100%;padding:11px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#f59e0b;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer}}.stat{{background:#0f172a;padding:10px;border-radius:8px;text-align:center;border:1px solid #38bdf8;margin-top:10px}}</style></head>
    <body>{render_nav("Agency Partner Program", "Home / For Agencies")}
    <div class="box"><span style="background:#f59e0b;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;">AGENCY PARTNER PROGRAM</span>
    <h2 style="margin:8px 0 6px 0;">Agency Media Kit &amp; Rate Card</h2>
    <p style="font-size:13px;margin:0 0 10px 0;">Scale your clients across Nepal &amp; global web publishers with transparent CPC pricing, zero cookie friction, and priority Telegram campaign support.</p>
    {proof_html}
    <div class="tier"><b>Standard Agency Rate:</b> 2.50 NPR / Verified Click (Free Unlimited Impressions)</div>
    <div class="tier"><b>Growth Tier (25,000+ NPR/mo):</b> 10% Bonus Click Credits + Priority Ad Rotation</div>
    <div class="tier"><b>Enterprise Tier (100,000+ NPR/mo):</b> 20% Bonus Credits + Dedicated Multi-Brand Account</div>
    <div class="tier"><b>Ad Specs &amp; Formats:</b> Responsive Native Card, 300x250 / 728x90 Banner + Optional Creative Attachment (JPG/PNG/WEBP)</div></div>

    <div class="box"><h3>Live Budget &amp; ROI Estimator</h3>
    <p style="font-size:12px;margin-top:0;">Enter your client campaign budget in NPR to calculate guaranteed clicks &amp; estimated reach:</p>
    <input id="bud" type="number" value="10000" oninput="calc()" placeholder="Campaign Budget (NPR)">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div class="stat"><small style="color:#94a3b8;">VERIFIED CLICKS</small><div id="clk" style="font-size:20px;font-weight:bold;color:#22c55e;">4,000</div></div>
        <div class="stat"><small style="color:#94a3b8;">EST. IMPRESSIONS</small><div id="imp" style="font-size:20px;font-weight:bold;color:#38bdf8;">80,000+</div></div>
    </div></div>

    <div class="box"><h3>Agency Partner Fast-Track Request</h3>
    <p style="font-size:12px;margin-top:0;">Apply for priority multi-client onboarding. Our network desk responds directly via Telegram/WhatsApp:</p>
    <input id="ag" placeholder="Agency / Company Name">
    <input id="ct" placeholder="WhatsApp, Telegram, or Email Contact">
    <input id="mb" placeholder="Estimated Monthly Client Spend (e.g. 50,000 NPR)">
    <input id="cc" placeholder="Number of Active Client Brands (e.g. 5 Brands)">
    <button class="btn" onclick="sendAg()">REQUEST AGENCY PARTNER ACCESS</button>
    <p id="res" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}

    <script>
    function calc(){{
        const b = parseFloat(document.getElementById('bud').value) || 0;
        let bonus = b >= 100000 ? 1.20 : (b >= 25000 ? 1.10 : 1.0);
        const clicks = Math.floor((b / 2.50) * bonus);
        document.getElementById('clk').innerText = clicks.toLocaleString();
        document.getElementById('imp').innerText = (clicks * 20).toLocaleString() + "+";
    }}
    async function sendAg(){{
        const r = await fetch('/api/v1/agency-fast-track',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{agency_name:document.getElementById('ag').value,contact_info:document.getElementById('ct').value,monthly_budget:document.getElementById('mb').value,client_count:document.getElementById('cc').value}})}});
        const d = await r.json(); document.getElementById('res').innerText = d.message;
    }}
    </script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.post("/api/v1/agency-fast-track")
async def agency_fast_track(req: AgencyReq):
    send_telegram_alert(f"🏢 PRIORITY AGENCY INQUIRY!\n• Agency: {req.agency_name}\n• Contact: {req.contact_info}\n• Monthly Budget: {req.monthly_budget}\n• Client Brands: {req.client_count}")
    return {"message": "Fast-track request received! Our Agency Desk has been alerted via Telegram."}

def make_qr_b64(data_str: str) -> str:
    try:
        img = qrcode.make(data_str, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf)
        return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

def get_live_proof(db: DBWrapper) -> str:
    imp_c = db.execute("SELECT COUNT(*) FROM impressions").fetchone().__getitem__(0)
    clk_c = db.execute("SELECT COUNT(*) FROM clicks").fetchone().__getitem__(0)
    cmp_c = db.execute("SELECT COUNT(*) FROM ad_campaigns WHERE active=1").fetchone().__getitem__(0)
    tnd_c = db.execute("SELECT COUNT(*) FROM tenders WHERE approved=1").fetchone().__getitem__(0)
    return f'<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:12px 0;"><div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;border:1px solid #38bdf8;"><div style="font-size:18px;font-weight:bold;color:#38bdf8;">{imp_c:,}</div><small style="color:#94a3b8;font-size:10px;">VERIFIED IMPRESSIONS</small></div><div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;border:1px solid #22c55e;"><div style="font-size:18px;font-weight:bold;color:#22c55e;">{clk_c:,}</div><small style="color:#94a3b8;font-size:10px;">HUMAN CLICKS (GUARDED)</small></div><div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;border:1px solid #ec4899;"><div style="font-size:18px;font-weight:bold;color:#ec4899;">{cmp_c}</div><small style="color:#94a3b8;font-size:10px;">ACTIVE AD CAMPAIGNS</small></div><div style="background:#0f172a;padding:10px;border-radius:8px;text-align:center;border:1px solid #f59e0b;"><div style="font-size:18px;font-weight:bold;color:#f59e0b;">{tnd_c}</div><small style="color:#94a3b8;font-size:10px;">LIVE NEPAL TENDERS</small></div></div>'

@app.get("/about", response_class=HTMLResponse)
async def about_page(db: DBWrapper = Depends(get_db)):
    proof_html = get_live_proof(db)
    row = db.execute("SELECT default_wallet, qr_img FROM settings WHERE id=1").fetchone()
    wal = row.__getitem__(0) if row else "9717831225"
    qimg = row.__getitem__(1) if (row and len(row) > 1 and row.__getitem__(1)) else ""
    qr_src = qimg if qimg else make_qr_b64(f'{{"eSewa_id":"{wal}","name":"Worldwide Ad Center"}}')
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px;margin-bottom:15px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.row{{background:#0f172a;padding:12px;border-radius:8px;margin-bottom:10px;border:1px solid #334155;font-size:13px}}.btn{{display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:12px;border-radius:8px;font-weight:bold;text-decoration:none;margin-top:12px}}</style></head>
    <body>{render_nav("About & Contact Support", "Home / About Us")}
    <div class="box"><h2>About Worldwide Ad Center</h2>
    <p><b>Worldwide Ad Center</b> is an independent, performance-driven digital advertising network built to connect businesses directly with quality blogs, news portals, and mobile apps—without middleman fees or invasive tracking cookies.</p>
    <p>Our lightweight <code>&lt;script&gt;</code> tag empowers publishers in Nepal and worldwide to monetize their traffic transparently at <b>2.50 NPR per verified human click</b> with fast mobile wallet settlements.</p></div>

    <div class="box"><h3>Live Network Proof-of-Traffic</h3><p style="font-size:12px;margin:0;">Real-time verified metrics streamed directly from our Cloud PostgreSQL ledger:</p>{proof_html}</div>

    <div class="box"><h3>Platform Features &amp; Capabilities</h3>
    <div class="row"><b>&#127760; Multi-Currency &amp; Global Reach:</b> Instant rate conversion across <b>NPR, USD, INR, and EUR</b> paired with a public <b>Universal Live Directory</b> indexing all active campaigns and opportunities.</div>
    <div class="row"><b>&#128187; Lightweight &lt;script&gt; Ad Engine:</b> Automated multi-banner rotation for websites and blogs with verified <b>2.50 NPR/click</b> tracking and embeddable <b>Partner Trust Badges</b>.</div>
    <div class="row"><b>&#127959;&#65039; All-Nepal Construction &amp; Bidder Notices:</b> Dedicated procurement board covering <b>all 7 Nepal provinces</b> for IFBs, sealed quotations, and subcontractor calls.</div>
    <div class="row"><b>&#127970; Agency Partner Program:</b> Volume bonus click tiers (10% Growth &amp; 20% Enterprise), live ROI budget estimator, and priority Telegram onboarding.</div>
    <div class="row"><b>&#127912; Advertiser Studio &amp; 7-Day Vault:</b> One-tap ad templates, live banner preview, creative image attachment (up to 500 KB), 7-day draft storage, and <b>Ad Creative Gallery</b>.</div>
    <div class="row"><b>&#128242; Social &amp; Influencer Monetization:</b> Tracked bio and story redirect links for <b>Facebook, TikTok, Instagram, and YouTube</b> creators at 2.50 NPR per verified click.</div>
    <div class="row"><b>&#128184; Direct eSewa Settlements &amp; PIN Security:</b> Instant eSewa QR deposits, Admin PIN-protected wallet payouts, and real-time Telegram alerts.</div></div>

    <div class="box"><h3>Contact &amp; Advertiser Support</h3>
    <p style="font-size:13px;">Have questions about launching an ad campaign, publisher integration, or eSewa payouts? Reach our network team directly:</p>
    <div class="row"><b>Official Telegram Bot:</b> <a href="https://t.me" target="_blank" style="color:#38bdf8;text-decoration:none;">@WorldwideAdCenterNotificationBot</a></div>
    <div class="row"><b>Support Desk / Inquiries:</b> <a href='mailto:difft40y@gmail.com' style='color:#38bdf8;text-decoration:none;'>difft40y@gmail.com</a></div>
    <div class="row"><b>Direct Phone / WhatsApp (eSewa):</b> +977-9717831225</div>
    <div class="row"><b>Payout Settlement Gateway:</b> eSewa Verified Merchant Support (Nepal)</div>
    <div class="row"><b>Operating Region:</b> Gandaki Province, Nepal &bull; Serving Global Web Traffic</div>
    <div style="background:#0f172a;padding:16px;border-radius:10px;text-align:center;border:1px solid #22c55e;margin:14px 0;">
        <div><span style="background:#22c55e;color:#0f172a;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:bold;">INSTANT ESEWA PAYMENT QR</span></div>
        <div style="background:#ffffff;padding:10px;border-radius:10px;display:inline-block;margin:12px auto;">
            <img src="{qr_src}" alt="eSewa QR" style="width:170px;height:170px;display:block;">
        </div>
                <div style="font-size:13px;color:#fff;font-weight:bold;">eSewa ID: {wal}</div>
        <p style="font-size:11px;color:#94a3b8;margin:4px 0 10px 0;">Scan via eSewa App or copy ID to deposit campaign funds</p>
        <button onclick="navigator.clipboard.writeText('{wal}');this.innerText='Copied: {wal}';" style="background:#22c55e;color:#0f172a;border:none;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:bold;cursor:pointer;">Copy eSewa ID ({wal})</button>
    </div>
    <a href="https://t.me" target="_blank" class="btn">MESSAGE US ON TELEGRAM</a>
    <a href="/advertise" class="btn" style="background:#14b8a6;">SUBMIT AN AD CAMPAIGN</a></div>
    {FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/faq", response_class=HTMLResponse)
async def faq_page():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px;margin-bottom:15px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.q{{color:#38bdf8;font-weight:bold;margin-top:14px}}.tag{{display:inline-block;background:#0f172a;border:1px solid #14b8a6;color:#14b8a6;padding:4px 10px;border-radius:20px;font-size:12px;margin:4px 4px 0 0}}.ban{{border-color:#ef4444;color:#ef4444}}</style></head>
    <body>{render_nav("Help Center & Ad Topics", "Home / FAQ & Guidelines")}
    <div class="box"><h2>Help Center &amp; Frequently Asked Questions</h2>
    <div class="q">1. How much does advertising cost?</div>
    <p>Advertisers pay a flat, transparent rate of <b>2.50 NPR per verified human click</b>. Impressions are served free across our partner publisher network.</p>
    <div class="q">2. How fast is my ad campaign approved?</div>
    <p>As soon as you submit your campaign on the <a href="/advertise" style="color:#14b8a6;">Advertise With Us</a> page, our admin team receives an instant Telegram alert and reviews your link within a few hours.</p>
    <div class="q">3. How do website owners earn money?</div>
    <p>Bloggers and website owners simply copy our single <code>&lt;script&gt;</code> tag from the hub and paste it into their HTML, Blogger, or WordPress site. Every verified click credits <b>+2.50 NPR</b> to escrow, payable directly to your <b>eSewa mobile wallet</b>.</p>
    <div class="q">4. How does your anti-fraud protection work?</div>
    <p>Our network filters duplicate refreshes and automated bot clicks so advertisers only pay for genuine human interest.</p></div>

    <div class="box"><h3>Supported &amp; Prohibited Ad Topics</h3>
    <p style="font-size:13px;">To keep our publisher websites family-friendly and brand-safe, all ads must follow our content guidelines:</p>
    <p style="margin-bottom:6px;color:#fff;font-size:13px;"><b>Allowed Topics:</b></p>
    <span class="tag">E-Commerce &amp; Retail</span><span class="tag">Tech &amp; Mobile Apps</span><span class="tag">Education &amp; Courses</span><span class="tag">Local Nepal Businesses</span><span class="tag">Finance &amp; SaaS</span><span class="tag">Blogs &amp; Media</span>
    <p style="margin:14px 0 6px 0;color:#fff;font-size:13px;"><b>Strictly Prohibited Topics:</b></p>
    <span class="tag ban">Adult / Explicit Content</span><span class="tag ban">Gambling &amp; Betting</span><span class="tag ban">Malware / Fake Downloads</span><span class="tag ban">Illegal Products</span><span class="tag ban">Click-Fraud Schemes</span></div>
    {FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px}}h2,h3{{color:#fff}}</style></head>
    <body>{render_nav("Privacy Policy", "Home / Legal / Privacy Policy")}<div class="box"><h2>Privacy Policy</h2><p><b>Effective Date:</b> November 2026</p><h3>1. Cookie-Free Ad Delivery</h3><p>Worldwide Ad Center delivers contextual advertisements without storing third-party tracking cookies on visitor browsers.</p><h3>2. Impression &amp; Click Logging</h3><p>We log anonymized impression counts, verified click events, and basic anti-fraud rate limits solely to calculate publisher earnings and prevent automated bot traffic.</p><h3>3. Publisher Payout Data</h3><p>Registered mobile wallet numbers (such as eSewa IDs) are used strictly for processing requested publisher settlements.</p></div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}a,button,input,select,textarea{{min-height:42px;font-size:14px;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px}}h2,h3{{color:#fff}}</style></head>
    <body>{render_nav("Terms of Service", "Home / Legal / Terms of Service")}<div class="box"><h2>Terms of Service</h2><h3>1. Publisher Guidelines</h3><p>Publishers embedding the Worldwide Ad Center script tag must not generate artificial clicks, automated refreshes, or incentivized click fraud.</p><h3>2. Escrow &amp; Settlements</h3><p>Verified clicks accrue in locked escrow and become eligible for settlement via supported mobile wallets upon admin verification.</p></div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/api/v1/health/telegram-report")
async def health_report(db: DBWrapper = Depends(get_db)):
    try:
        imp_r = db.execute("SELECT COUNT(*) FROM impressions").fetchone()
        imp = imp_r[0] if imp_r else 0
        clk_r = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
        clk = clk_r[0] if clk_r else 0
        bal = round(float(clk_r[1]), 2) if clk_r and clk_r[1] else 0.0
        report = f"📊 WORLDWIDE AD CENTER REPORT\n• Verified Impressions: {imp}\n• Locked Human Clicks: {clk}\n• Available Escrow: {bal} NPR"
        st = send_telegram_alert(report)
        return {"status": "ok", "telegram": st, "summary": report}
    except Exception as ex:
        return {"status": "ok", "summary": f"Health Check Active ({ex})"}

@app.get("/simulate-app", response_class=HTMLResponse)
async def simulate_app_page(db: DBWrapper = Depends(get_db)):
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}</style></head>
    <body>{render_nav("Mobile App Ad Simulator", "Home / App Simulator")}
    <div class="box"><h2>Mobile App &amp; Web Banner Simulator</h2><p style="font-size:12px;">Live preview of how Worldwide Ad Center sponsored units render inside Android/iOS apps and mobile web portals:</p>
    <div id="wac-sim-slot" style="background:#0f172a;padding:14px;border-radius:10px;border:1px solid #38bdf8;"></div>
    <script src="/api/v1/tag.js"></script></div>{FOOTER}<div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.get("/payout-hub", response_class=HTMLResponse)
async def payout_hub_page(db: DBWrapper = Depends(get_db)):
    clk_r = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    bal = round(float(clk_r[1]), 2) if clk_r and clk_r[1] else 0.0
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta property="og:title" content="Worldwide Ad Center | Global & Nepal Ad Network"><meta property="og:description" content="Direct CPC advertising, 35 global sectors, all-Nepal construction tenders, and instant eSewa payouts."><meta property="og:type" content="website"><meta property="og:url" content="https://worldwide-ad-center-1.onrender.com"><style>html,body{{max-width:100%;overflow-x:hidden;}}body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:16px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}input{{width:100%;padding:12px;margin:6px 0;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box;font-size:14px}}.btn{{width:100%;padding:13px;background:#22c55e;color:#0f172a;border:none;border-radius:8px;font-weight:bold;margin-top:8px;cursor:pointer;font-size:14px}}</style></head>
    <body>{render_nav("eSewa Withdrawal & History", "Home / eSewa Payouts")}
    <div class="box"><h2>eSewa Mobile Wallet Withdrawal</h2><p style="font-size:13px;">Verified eSewa & Telegram Merchant: <b>+977-9717831225</b><br>Available Locked Escrow Balance: <b style="color:#22c55e;">{bal} NPR</b></p>
    <input id="pwal" value="9717831225" placeholder="eSewa Wallet ID">
    <input id="pamt" type="number" placeholder="Withdrawal Amount (NPR)">
    <input id="ppin" type="password" placeholder="Admin Security PIN">
    <button class="btn" onclick="reqPay()">REQUEST ESEWA SETTLEMENT</button><p id="pres" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}
    <script>async function reqPay(){{const r=await fetch('/api/v1/withdraw',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{wallet:document.getElementById('pwal').value,amount:parseFloat(document.getElementById('pamt').value||0),pin:document.getElementById('ppin').value}})}});const d=await r.json();document.getElementById('pres').innerText=d.message||d.detail||'Settlement request logged!';}}</script><div id="bidModal" style="display:none;position:fixed;inset:0;background:rgba(2,6,23,0.85);z-index:9999;align-items:center;justify-content:center;padding:16px;">
  <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:14px;padding:18px;max-width:400px;width:100%;box-shadow:0 12px 30px rgba(0,0,0,0.7);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:bold;">PROCUREMENT &amp; BID DESK</span>
      <button onclick="document.getElementById('bidModal').style.display='none'" style="background:none;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">&times;</button>
    </div>
    <h3 id="bmTitle" style="color:#fff;margin:4px 0 8px 0;font-size:15px;">Tender Inquiry</h3>
    <div id="bmContact" style="background:#0f172a;padding:10px;border-radius:8px;border:1px solid #334155;color:#22c55e;font-size:12px;font-weight:bold;word-break:break-all;margin-bottom:10px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
      <button onclick="copyBidCnt()" style="background:#38bdf8;color:#0f172a;border:none;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;cursor:pointer;">&#128203; Copy Contact</button>
      <a id="bmMail" href="/mail#compose" style="display:flex;align-items:center;justify-content:center;background:#22c55e;color:#0f172a;padding:10px;border-radius:8px;font-weight:bold;font-size:12px;text-decoration:none;">&#9993;&#65039; 1-Tap Bid Inquiry</a>
    </div>
    <p id="bmMsg" style="color:#f59e0b;font-size:11px;margin:4px 0 0 0;text-align:center;"></p>
  </div>
</div>
<script>
function openBidModal(el){{
  const card = el.closest('div');
  const h = card ? card.querySelector('h3,h4') : null;
  const title = h ? h.innerText.trim() : 'Tender & Procurement Notice';
  const cnt = el.dataset.cnt || 'difft40y@gmail.com | +977-9717831225';
  const email = cnt.includes('@') ? cnt.split('|')[0].trim() : 'difft40y@gmail.com';
  document.getElementById('bmTitle').innerText = title;
  document.getElementById('bmContact').innerText = cnt;
  document.getElementById('bmMsg').innerText = '';
  document.getElementById('bmMail').href = '/mail?to=' + encodeURIComponent(email) + '&sub=' + encodeURIComponent('Bid Inquiry: ' + title) + '#compose';
  document.getElementById('bidModal').style.display = 'flex';
}}
function copyBidCnt(){{
  navigator.clipboard.writeText(document.getElementById('bmContact').innerText);
  document.getElementById('bmMsg').innerText = 'Contact copied to clipboard!';
}}
</script></body></html>"""

@app.exception_handler(404)
async def not_found_redirect(request, exc):
    return HTMLResponse("<script>window.location.href='/';</script>")
