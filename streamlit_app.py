"""
EcchiGPT — Streamlit版
起動: streamlit run streamlit_app.py
JSON: favo_actress_master.json / favo_fanza_cluster.json を同フォルダに置く
"""

import json
import re
import unicodedata
from pathlib import Path

import requests
import streamlit as st

# ─────────────────────────────────────────────
st.set_page_config(
    page_title="EcchiGPT",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────
CACHE_SEC        = 300
FETCH_HITS       = 60
PER_PAGE         = 10
MIN_RELEASE_YEAR = 2016

NG_GENRE_KEYWORDS = [
    "熟女","熟妻","おばさん","五十路","義母","母さん","母子","近親相姦",
    "VR","ニューハーフ","男の娘",
]
NG_TITLE_KEYWORDS = ["VR","AIリマスター","ＡＩリマスター"]
ACTRESS_MATCH_POINT = 12
ACTRESS_NAME_POINT  = 25
ACTRESS_SCORE_CAP   = 120

BASE_DIR          = Path(__file__).parent
MASTER_JSON_PATH  = BASE_DIR / "favo_actress_master.json"
CLUSTER_JSON_PATH = BASE_DIR / "favo_fanza_cluster.json"

STOP_WORDS = {
    "が","を","に","へ","で","と","や","の","も","は","とか","など","な",
    "して","してる","している","され","される","なる","なっ","ある","いる",
    "から","まで","より","だけ","くらい","ぐらい","そして","でも","また",
    "です","ます","だ","ね","よ","なに","何","っぽい","みたい","感じ",
}
NOISE_WORDS = {"セックス","SEX","エロ","H","アダルト"}
PLAY_LABELS = {
    "":"おまかせ",
    "soft":"🌸 ソフト",
    "hard":"🔥 ハード",
    "semeru":"💥 責める",
    "semerareru":"💋 責められる",
}

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans JP', 'Hiragino Sans', sans-serif !important;
    background: #f7f7f8 !important;
}

/* ページ幅・余白 */
.block-container {
    padding: 0 0 5rem 0 !important;
    max-width: 760px !important;
}
header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }
.stDeployButton { display: none !important; }

/* ─ ヘッダー ─ */
.favo-header {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 20px 12px;
    background: #fff;
    border-bottom: 1px solid #ebebeb;
    position: sticky; top: 0; z-index: 100;
}
.favo-logo {
    width: 28px; height: 28px; border-radius: 7px;
    background: #111; color: #fff;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 13px; flex-shrink: 0;
}
.favo-htitle { font-weight: 700; font-size: 14px; color: #111; line-height: 1.2; }
.favo-hsub   { font-size: 11px; color: #aaa; }

/* ─ 条件チップバー ─ */
.favo-summary {
    display: flex; align-items: center; gap: 5px; flex-wrap: wrap;
    padding: 6px 20px; min-height: 34px;
    background: #fafafa;
    border-bottom: 1px solid #ebebeb;
    font-size: 11px; color: #bbb;
}
.favo-chip {
    display: inline-flex; align-items: center;
    padding: 2px 9px; border-radius: 999px;
    border: 1px solid #e0e0e0; background: #fff;
    font-size: 11px; color: #555;
}

/* ─ モードバー ─ */
.modebar-wrap {
    padding: 8px 20px;
    background: #fff;
    border-bottom: 1px solid #ebebeb;
    display: flex; align-items: center; gap: 6px;
}

/* ─ Streamlit ボタン（モードバー） ─ */
div[data-testid="stButton"] button {
    border-radius: 999px !important;
    font-size: 12px !important;
    padding: 4px 14px !important;
    font-family: inherit !important;
    border: 1px solid #e0e0e0 !important;
    background: #fff !important;
    color: #555 !important;
    transition: all .15s !important;
    font-weight: 500 !important;
}
div[data-testid="stButton"] button:hover {
    border-color: #999 !important;
    color: #111 !important;
}
.mode-on div[data-testid="stButton"] button {
    background: #111 !important;
    border-color: #111 !important;
    color: #fff !important;
}

/* ─ チャットエリア ─ */
/* アシスタントメッセージ */
[data-testid="stChatMessage"] {
    padding: 16px 20px !important;
    background: transparent !important;
    border: none !important;
    max-width: 100% !important;
}
/* userは右寄せ風 */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: transparent !important;
    flex-direction: row-reverse !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stChatMessageContent {
    background: #111 !important;
    color: #fff !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 10px 14px !important;
    font-size: 14px !important;
    max-width: 75% !important;
    border: none !important;
    box-shadow: none !important;
}
/* assistantはChatGPT風グレー */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) .stChatMessageContent {
    background: #f0f0f0 !important;
    color: #111 !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 10px 14px !important;
    font-size: 14px !important;
    max-width: 80% !important;
    border: none !important;
    box-shadow: none !important;
}
/* アバター */
[data-testid="chatAvatarIcon-assistant"] {
    background: #111 !important;
    border-radius: 50% !important;
    color: #fff !important;
    font-size: 14px !important;
}
[data-testid="chatAvatarIcon-user"] {
    background: #e8e8e8 !important;
    border-radius: 50% !important;
    color: #555 !important;
}

/* ─ chat_input ─ */
[data-testid="stChatInput"] {
    border-top: 1px solid #ebebeb !important;
    background: #fff !important;
    padding: 10px 20px !important;
}
[data-testid="stChatInput"] textarea {
    font-size: 14px !important;
    border-radius: 24px !important;
    border: 1px solid #e0e0e0 !important;
    background: #fff !important;
    font-family: inherit !important;
    padding: 10px 16px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.06) !important;
    resize: none !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #aaa !important;
    box-shadow: 0 0 0 3px rgba(0,0,0,.06) !important;
    outline: none !important;
}
[data-testid="stChatInput"] button {
    background: #111 !important;
    border-radius: 50% !important;
    color: #fff !important;
    border: none !important;
}

/* ─ 結果グリッド ─ */
.favo-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    padding: 0 20px 8px;
    margin-top: 6px;
}
@media(max-width:540px){ .favo-grid { grid-template-columns: repeat(2,1fr); padding: 0 10px 8px; } }
.favo-card {
    border: 1px solid #ebebeb;
    border-radius: 10px;
    overflow: hidden;
    background: #fff;
    transition: all .18s;
    text-decoration: none;
    display: block;
}
.favo-card:hover {
    border-color: #ccc;
    box-shadow: 0 4px 12px rgba(0,0,0,.08);
    transform: translateY(-1px);
}
.favo-card img { width: 100%; aspect-ratio: 3/4; object-fit: cover; display: block; }
.favo-card-title {
    display: block; text-align: center;
    font-size: 10px; color: #999;
    padding: 5px 4px;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    text-decoration: none;
}
.favo-card-title:hover { color: #111; }
.no-img {
    width: 100%; aspect-ratio: 3/4;
    background: #f5f5f5;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; color: #ccc;
}

/* ─ 女優カード ─ */
.actress-grid { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.actress-item { width: 72px; text-align: center; }
.actress-item img {
    width: 72px; height: 96px; object-fit: cover;
    border-radius: 8px; border: 2px solid #ebebeb; display: block;
    transition: border-color .15s;
}
.actress-item img:hover { border-color: #111; }
.actress-name { font-size: 10px; color: #444; margin-top: 3px; font-weight: 700; word-break: break-all; }
.actress-tags { font-size: 9px; color: #bbb; }

.favo-divider { height: 1px; background: #ebebeb; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
_DEFAULTS = {
    "mode": "none",
    "play_filter": "",
    "tags": [],
    "last_q": "",
    "page": 1,
    "results": [],
    "has_more": False,
    "chat": [],
    "ai_hist": [],
    "fanza_api_id": "",
    "fanza_aff_id": "",
    "openai_key": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────
def norm(s):
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("，",",").replace("、",",").replace("\u3000"," ")
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"[a-z]+", lambda m: m.group(0).upper(), s)

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def dedup(lst):
    return list(dict.fromkeys(x for x in lst if x))

# ─────────────────────────────────────────────
# JSON 読み込み
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_master():
    sample = {
        "波多野結衣": {"tags":["黒髪","ロング","スレンダー","清楚"],"keywords":["人気"],"celebs":["新垣結衣","石原さとみ"],"img":""},
        "天使もえ":   {"tags":["ブロンド","ショート","可愛い","童顔"],"keywords":[],"celebs":[],"img":""},
        "三上悠亜":   {"tags":["金髪","スレンダー","可愛い","アイドル"],"keywords":["元AKB"],"celebs":["指原莉乃","前田敦子"],"img":""},
    }
    if MASTER_JSON_PATH.exists():
        try:
            d = json.loads(MASTER_JSON_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(d, dict): return d
        except Exception: pass
    return sample

@st.cache_data(ttl=3600, show_spinner=False)
def load_cluster():
    sample = {
        "巨乳":["おっぱい","Gカップ","爆乳"],
        "スレンダー":["細身","華奢","スリム"],
        "ショート":["ショートヘア","短髪"],
        "ロング":["ロングヘア","長髪"],
        "清楚":["上品","清潔感"],
    }
    if CLUSTER_JSON_PATH.exists():
        try:
            d = json.loads(CLUSTER_JSON_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(d, dict): return d
        except Exception: pass
    return sample

@st.cache_data(ttl=3600, show_spinner=False)
def build_alias_map():
    m = {}
    for canon, aliases in load_cluster().items():
        cn = norm(canon)
        if cn: m[cn] = cn
        for a in (aliases if isinstance(aliases, list) else []):
            an = norm(str(a))
            if an: m[an] = cn
    return m

@st.cache_data(ttl=3600, show_spinner=False)
def build_actress_kv():
    out = {}
    for name, v in load_master().items():
        nn = norm(name)
        if not nn: continue
        tags = v.get("tags",[]) if isinstance(v,dict) else (v if isinstance(v,list) else [])
        kw   = v.get("keywords", v.get("kw",[])) if isinstance(v,dict) else []
        out[nn] = {
            "tags":     [norm(t) for t in tags if norm(t)],
            "keywords": [norm(t) for t in kw   if norm(t)],
            "img":      v.get("img","") if isinstance(v,dict) else "",
        }
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def build_celebrity_map():
    celmap = {}
    for actress, v in load_master().items():
        an = norm(actress)
        if not an or not isinstance(v, dict): continue
        for c in v.get("celebs", v.get("celebrities",[])):
            cn = norm(str(c))
            if cn: celmap.setdefault(cn, {})[an] = 1
    return celmap

# ─────────────────────────────────────────────
# フィルタ
# ─────────────────────────────────────────────
def item_valid(item):
    m = re.search(r"(\d{4})", str(item.get("date","")))
    y = int(m.group(1)) if m else 0
    if y > 0 and y <= MIN_RELEASE_YEAR: return False
    for g in item.get("iteminfo",{}).get("genre",[]):
        gn = norm(g.get("name",""))
        if any(w and w in gn for w in NG_GENRE_KEYWORDS): return False
    return not any(w and w in norm(item.get("title","")) for w in NG_TITLE_KEYWORDS)

def is_collection(item):
    return any(norm(g.get("name","")) == "ベスト・総集編"
               for g in item.get("iteminfo",{}).get("genre",[]))

def match_mode(item, mode):
    if mode in ("none",""): return True
    return is_collection(item) if mode == "collection" else not is_collection(item)

def is_hard(item):
    for g in item.get("iteminfo",{}).get("genre",[]):
        if any(w and w in norm(g.get("name","")) for w in ["辱め","拘束","淫乱・ハード系","羞恥"]): return True
    return any(w and w in norm(item.get("title","")) for w in ["肉便器","性処理","アクメ"])

def match_play(item, pf):
    if not pf or pf == "none": return True
    t = norm(item.get("title",""))
    if pf == "hard":        return is_hard(item)
    if pf == "soft":        return not is_hard(item)
    if pf == "semeru":      return "イカセ" in t
    if pf == "semerareru":  return "痴女" in t
    return True

# ─────────────────────────────────────────────
# スコアリング
# ─────────────────────────────────────────────
def score_item(item, meaning_list):
    if not meaning_list: return 0
    sc = 0
    title = norm(item.get("title",""))
    db    = build_actress_kv()
    aset  = dedup([norm(a.get("name","")) for a in item.get("iteminfo",{}).get("actress",[])])
    for m in meaning_list:
        m = norm(m)
        if not m: continue
        if m in title: sc += 3
        for g in item.get("iteminfo",{}).get("genre",[]):
            if m in norm(g.get("name","")): sc += 2; break
        for a in aset:
            if len(m) >= 2 and m in a: sc += ACTRESS_NAME_POINT
            v = db.get(a)
            if v and m in (v["tags"] + v["keywords"]): sc += ACTRESS_MATCH_POINT; break
    return min(sc, ACTRESS_SCORE_CAP)

def score_actresses_for_ai(input_tags, limit=6):
    master = load_master()
    input_norm = [norm(t) for t in input_tags if norm(t)]
    if not input_norm or not master: return []
    rows = []
    for name, v in master.items():
        nn = norm(name)
        if not nn: continue
        all_tags = ([norm(t) for t in v.get("tags",[]) + v.get("keywords", v.get("kw",[]))]
                    if isinstance(v, dict) else [])
        s = sum(3 if nt == inp else (1 if inp in nt or nt in inp else 0)
                for inp in input_norm for nt in all_tags)
        rows.append({"name":name,"img":v.get("img","") if isinstance(v,dict) else "","tags":all_tags[:5],"score":s})
    rows.sort(key=lambda x: -x["score"])
    return rows[:limit]

# ─────────────────────────────────────────────
# クエリ分解
# ─────────────────────────────────────────────
def split_query(q_raw):
    q = norm(q_raw)
    if not q: return {"search":[],"meaning":[],"noise":[],"celebrity":[]}
    celmap   = build_celebrity_map()
    cel_keys = sorted(celmap.keys(), key=lambda x: -len(x))
    celebs, rest = [], q
    for c in cel_keys:
        if c and c in rest: celebs.append(c); rest = rest.replace(c, " ")
    alias_map = build_alias_map()
    search = []
    for a in sorted(alias_map.keys(), key=lambda x: -len(x)):
        cn = alias_map.get(a, "")
        if a and cn and a in rest: search.append(cn); rest = rest.replace(a, " ")
    meaning, noise = [], []
    for t in re.split(r"[\s,/|]+", norm(rest)):
        t = norm(t)
        if not t or len(t) <= 1: noise.append(t)
        elif t in STOP_WORDS or t in NOISE_WORDS: noise.append(t)
        else: meaning.append(t)
    return {"search":dedup(search),"meaning":dedup(meaning),"noise":dedup(noise),"celebrity":dedup(celebs)}

# ─────────────────────────────────────────────
# FANZA API
# ─────────────────────────────────────────────
@st.cache_data(ttl=CACHE_SEC, show_spinner=False)
def fanza_fetch(keyword, hits, api_id, aff_id):
    if not keyword or not api_id or not aff_id:
        return {"items":[], "error":"missing_config"}
    try:
        r = requests.get(
            "https://api.dmm.com/affiliate/v3/ItemList",
            params={"api_id":api_id,"affiliate_id":aff_id,"site":"FANZA","service":"digital",
                    "floor":"videoa","hits":str(min(100,max(1,hits))),"sort":"date",
                    "keyword":keyword,"output":"json"},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("result",{}).get("items",[])
        return {"items":[it for it in items if item_valid(it)]}
    except Exception as e:
        return {"items":[], "error":str(e)}

def do_search(q_raw, mode, play_filter, page, api_id, aff_id):
    split  = split_query(q_raw)
    celmap = build_celebrity_map()
    celeb_cands = dedup(
        a for c in split["celebrity"]
        for a in list(celmap.get(c, {}).keys())[:3]
    )[:5]

    if split["search"]:
        items = fanza_fetch(" ".join(split["search"]), FETCH_HITS, api_id, aff_id).get("items",[])
    elif celeb_cands:
        items, seen = [], set()
        for c in celeb_cands[:3]:
            for it in fanza_fetch(c, 25, api_id, aff_id).get("items",[]):
                k = it.get("URL","") or it.get("content_id","")
                if k and k not in seen:
                    seen.add(k); items.append(it)
                if len(items) >= FETCH_HITS: break
    else:
        alias_map = build_alias_map()
        q_n = norm(q_raw)
        for a, c in sorted(alias_map.items(), key=lambda x: -len(x[0])):
            if a and a in q_n: q_n = q_n.replace(a, c)
        items = fanza_fetch(norm(q_n), FETCH_HITS, api_id, aff_id).get("items",[])

    filtered = [it for it in items if match_mode(it, mode) and match_play(it, play_filter)]
    sorted_  = sorted(filtered, key=lambda it: -score_item(it, split["meaning"]))
    off       = (page - 1) * PER_PAGE
    page_items= sorted_[off:off+PER_PAGE]
    has_more  = len(sorted_) > off + PER_PAGE
    out = [{
        "title":    it.get("title",""),
        "url":      it.get("URL",""),
        "image":    it.get("imageURL",{}).get("small","") or it.get("imageURL",{}).get("large",""),
    } for it in page_items]
    return {"items":out, "has_more":has_more}

# ─────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────
def ai_interpret(user_msg, history, current_tags, api_key):
    if not api_key: return {"error":"no_api_key"}
    cands = score_actresses_for_ai(current_tags or [user_msg], 6)
    actress_ctx = ""
    if cands:
        lines = [f"・{c['name']}（{'・'.join(c['tags']) or 'タグ未登録'}）" for c in cands]
        actress_ctx = "\n\n# 候補女優\n" + "\n".join(lines) + "\n※希望に近い女優をselected_actressesに。"
    system = (
        "あなたはアダルトDVD検索サイトのアシスタントです。\n"
        "ユーザーの日本語入力から検索タグと最適な女優を選んでください。\n\n"
        "# 出力形式（JSONのみ）\n"
        '{"tags":["タグ"],"selected_actresses":["女優名"],'
        '"detected_celebs":["芸能人名"],'
        '"play_filter":"none|soft|hard|semeru|semerareru",'
        '"bot_reply":"返答（1〜2文、フレンドリーに）","remove_tags":["削除タグ"]}'
        + actress_ctx
    )
    messages = [{"role":"system","content":system}]
    for h in history[-6:]:
        if h.get("role") in ("user","assistant") and h.get("content"):
            messages.append({"role":h["role"],"content":h["content"]})
    messages.append({"role":"user","content":str(user_msg)})
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":"gpt-4o-mini","messages":messages,"temperature":0.3,"max_tokens":400},
            timeout=15,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        text = re.sub(r"^```json\s*","",text.strip())
        text = re.sub(r"```\s*$","",text).strip()
        return json.loads(text)
    except Exception as e:
        return {"error":str(e)}

# ─────────────────────────────────────────────
# 結果カードHTML
# ─────────────────────────────────────────────
def render_results_html(items):
    if not items: return ""
    cards = ""
    for it in items:
        t   = (it["title"][:18]+"…") if len(it["title"]) > 18 else it["title"]
        url = esc(it.get("url","#"))
        img = (f'<img src="{esc(it["image"])}" loading="lazy" alt="">'
               if it.get("image") else '<div class="no-img">no img</div>')
        cards += (
            f'<a class="favo-card" href="{url}" target="_blank" rel="nofollow noopener">'
            f'{img}'
            f'<span class="favo-card-title">▶ {esc(t)}</span>'
            f'</a>'
        )
    return f'<div class="favo-grid">{cards}</div>'

def render_actress_cards_html(cards):
    if not cards: return ""
    html = '<div class="actress-grid">'
    for c in cards:
        img = (f'<img src="{esc(c["img"])}" loading="lazy" alt="{esc(c["name"])}">'
               if c.get("img") else
               '<div style="width:72px;height:96px;background:#f0f0f0;border-radius:8px;'
               'display:flex;align-items:center;justify-content:center;font-size:9px;color:#ccc">no img</div>')
        tags_str = " · ".join(c.get("tags",[])[:3])
        html += (
            f'<div class="actress-item">{img}'
            f'<div class="actress-name">{esc(c["name"])}</div>'
            f'<div class="actress-tags">{esc(tags_str)}</div>'
            f'</div>'
        )
    return html + '</div>'

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown("## ⚙️ 設定")
        with st.expander("🔑 APIキー", expanded=True):
            for key, label in [("fanza_api_id","FANZA API ID"),
                                ("fanza_aff_id","FANZA Affiliate ID"),
                                ("openai_key","OpenAI API Key")]:
                st.session_state[key] = st.text_input(
                    label, value=st.session_state[key], type="password", key=f"sb_{key}")

        st.divider()
        with st.expander("📁 JSONファイル", expanded=True):
            for path, label in [(MASTER_JSON_PATH,"Actress Master"),(CLUSTER_JSON_PATH,"Cluster")]:
                if path.exists(): st.success(f"✅ {label} ({path.stat().st_size//1024} KB)")
                else: st.warning(f"⚠ {label} — サンプル動作中")
            up = st.file_uploader("JSONをアップロード", type="json", key="up_json")
            if up:
                try:
                    data = json.loads(up.read().decode("utf-8-sig"))
                    if not isinstance(data, dict): st.error("dict形式が必要")
                    else:
                        dest = MASTER_JSON_PATH if "master" in up.name.lower() else CLUSTER_JSON_PATH
                        dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
                        st.cache_data.clear(); st.success(f"{dest.name} 保存（{len(data)}件）"); st.rerun()
                except Exception as e: st.error(f"エラー: {e}")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("Master↓", data=json.dumps(load_master(),ensure_ascii=False,indent=2),
                                   file_name="favo_actress_master.json", mime="application/json", use_container_width=True)
            with c2:
                st.download_button("Cluster↓", data=json.dumps(load_cluster(),ensure_ascii=False,indent=2),
                                   file_name="favo_fanza_cluster.json", mime="application/json", use_container_width=True)

        with st.expander("➕ 女優を追加"):
            nn = st.text_input("女優名", key="add_name")
            nt = st.text_input("タグ（カンマ）", key="add_tags")
            nc = st.text_input("芸能人（カンマ）", key="add_celebs")
            if st.button("追加", use_container_width=True, key="btn_add"):
                if nn.strip():
                    master = load_master().copy()
                    master[nn.strip()] = {
                        "tags":    [t.strip() for t in nt.split(",") if t.strip()],
                        "keywords": [],
                        "celebs":  [c.strip() for c in nc.split(",") if c.strip()],
                        "img": "",
                    }
                    MASTER_JSON_PATH.write_text(json.dumps(master,ensure_ascii=False,indent=2),encoding="utf-8")
                    st.cache_data.clear(); st.success(f"追加: {nn}"); st.rerun()

# ─────────────────────────────────────────────
# 送信ハンドラ
# ─────────────────────────────────────────────
def handle_send(typed):
    api_key   = st.session_state["openai_key"]
    fanza_api = st.session_state["fanza_api_id"]
    fanza_aff = st.session_state["fanza_aff_id"]
    actress_cards = []
    bot_reply = "OK、探すね！"

    if api_key:
        with st.spinner("考え中…"):
            result = ai_interpret(typed, st.session_state["ai_hist"],
                                  st.session_state["tags"], api_key)
        if not result.get("error"):
            bot_reply = result.get("bot_reply", "OK、探すね！")
            st.session_state["ai_hist"] += [
                {"role":"user","content":typed},
                {"role":"assistant","content":bot_reply},
            ]
            remove = [t.strip().lower() for t in result.get("remove_tags",[])]
            curr   = [t for t in st.session_state["tags"] if t.lower() not in remove]
            new_t  = [t.strip() for t in result.get("tags",[]) if t.strip()]
            sel    = [t.strip() for t in result.get("selected_actresses",[]) if t.strip()]
            st.session_state["tags"] = dedup(curr + new_t + sel)

            pf = result.get("play_filter","none")
            if pf and pf != "none": st.session_state["play_filter"] = pf

            master = load_master()
            for name in result.get("selected_actresses",[]):
                v = master.get(name) or master.get(norm(name))
                if v and isinstance(v, dict):
                    actress_cards.append({"name":name,"img":v.get("img",""),"tags":v.get("tags",[])[:4]})

            unknown = [c for c in result.get("detected_celebs",[])
                       if norm(c) not in build_celebrity_map()]
            if unknown:
                bot_reply = f"ごめん、{'・'.join(unknown)}に似てる人は見つからなかった。他にいない？"
        else:
            bot_reply = "OK、探すね 🔍"
            st.session_state["tags"] = dedup(
                st.session_state["tags"] + [norm(p) for p in typed.split() if norm(p)])
    else:
        bot_reply = "OK、探すね 🔍"
        st.session_state["tags"] = dedup(
            st.session_state["tags"] + [norm(p) for p in typed.split() if norm(p)])

    st.session_state["last_q"] = " ".join(st.session_state["tags"])

    # チャット履歴に追加（actress_cardsのHTMLも一緒に保存）
    actress_html = render_actress_cards_html(actress_cards)
    st.session_state["chat"].append({
        "role": "bot",
        "text": bot_reply,
        "actress_html": actress_html,
    })

    # FANZA検索
    if fanza_api and fanza_aff and st.session_state["last_q"]:
        with st.spinner("検索中…"):
            res = do_search(st.session_state["last_q"], st.session_state["mode"],
                            st.session_state["play_filter"], 1, fanza_api, fanza_aff)
        st.session_state.update({"results":res["items"],"has_more":res["has_more"],"page":2})
    elif not fanza_api or not fanza_aff:
        st.session_state["chat"].append({
            "role":"bot","text":"⚠ サイドバーの「APIキー」にFANZAのキーを入力してね","actress_html":"",
        })

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    sidebar()

    # ── ヘッダー ──
    st.markdown("""
    <div class="favo-header">
      <div class="favo-logo">E</div>
      <div>
        <div class="favo-htitle">EcchiGPT</div>
        <div class="favo-hsub">会話で探していこう</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── サマリーバー ──
    tags = st.session_state["tags"]
    mode = st.session_state["mode"]
    pf   = st.session_state["play_filter"]
    if not tags and mode == "none" and not pf:
        chips = '<span style="color:#ccc">（まだなし）</span>'
    else:
        chips = ""
        if mode != "none":
            chips += f'<span class="favo-chip">{"単体" if mode=="single" else "総集編"}</span>'
        if pf:
            chips += f'<span class="favo-chip">プレイ:{esc(PLAY_LABELS.get(pf,pf))}</span>'
        for t in tags:
            chips += f'<span class="favo-chip">{esc(t)}</span>'
    st.markdown(f'<div class="favo-summary">条件：{chips}</div>', unsafe_allow_html=True)

    # ── モードバー ──
    mc1, mc2, mc3, mc4, mc5 = st.columns([1.1, 1.2, 1.5, 0.8, 1.2])
    with mc1:
        is_s = mode == "single"
        if is_s: st.markdown('<div class="mode-on">', unsafe_allow_html=True)
        if st.button("📌 単体", key="btn_single", use_container_width=True):
            st.session_state["mode"] = "none" if is_s else "single"
            st.rerun()
        if is_s: st.markdown('</div>', unsafe_allow_html=True)

    with mc2:
        is_c = mode == "collection"
        if is_c: st.markdown('<div class="mode-on">', unsafe_allow_html=True)
        if st.button("📚 総集編", key="btn_col", use_container_width=True):
            st.session_state["mode"] = "none" if is_c else "collection"
            st.rerun()
        if is_c: st.markdown('</div>', unsafe_allow_html=True)

    with mc3:
        pf_keys = list(PLAY_LABELS.keys())
        new_pf = st.selectbox("プレイ", pf_keys,
                               index=pf_keys.index(pf) if pf in pf_keys else 0,
                               format_func=lambda x: PLAY_LABELS[x],
                               label_visibility="collapsed", key="sel_pf")
        if new_pf != pf:
            st.session_state["play_filter"] = new_pf
            st.rerun()

    with mc5:
        if tags or mode != "none" or pf:
            if st.button("✕ クリア", key="btn_clear", use_container_width=True):
                st.session_state.update({"tags":[],"last_q":"","results":[],"page":1,
                                          "mode":"none","play_filter":""})
                st.rerun()

    with mc4:
        if st.button("🔄", key="btn_reset", use_container_width=True, help="リセット"):
            for k, v in _DEFAULTS.items(): st.session_state[k] = v
            st.rerun()

    st.markdown('<div class="favo-divider"></div>', unsafe_allow_html=True)

    # ── 入力を先に受け取る（rerun前にsession_stateへ反映） ──
    user_input = st.chat_input("例：黒髪 ボブ 清楚 ちょいエロ…")
    if user_input:
        st.session_state["chat"].append({"role":"user","text":user_input,"actress_html":""})
        handle_send(user_input)
        st.rerun()

    # ── チャット履歴を描画（入力処理後に描画するので最新が反映される） ──
    if not st.session_state["chat"]:
        with st.chat_message("assistant", avatar="🔍"):
            st.write("どんな感じで探す？外見・雰囲気・好きな芸能人、なんでもOKだよ 👀")
    else:
        for msg in st.session_state["chat"]:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["text"])
            else:
                with st.chat_message("assistant", avatar="🔍"):
                    st.write(msg["text"])
                    if msg.get("actress_html"):
                        st.markdown(msg["actress_html"], unsafe_allow_html=True)

    # ── 結果グリッド ──
    if st.session_state["results"]:
        st.markdown('<div class="favo-divider"></div>', unsafe_allow_html=True)
        st.markdown(render_results_html(st.session_state["results"]), unsafe_allow_html=True)

        if st.session_state["has_more"]:
            col_n, _, _ = st.columns([1.2, 2, 2])
            with col_n:
                if st.button("次の10件 →", key="btn_next", use_container_width=True):
                    api = st.session_state["fanza_api_id"]
                    aff = st.session_state["fanza_aff_id"]
                    if api and aff:
                        with st.spinner("読み込み中…"):
                            res = do_search(st.session_state["last_q"], st.session_state["mode"],
                                            st.session_state["play_filter"], st.session_state["page"],
                                            api, aff)
                        st.session_state["results"] += res["items"]
                        st.session_state["has_more"] = res["has_more"]
                        st.session_state["page"] += 1
                        st.rerun()

    elif st.session_state["last_q"] and not st.session_state["results"]:
        st.info("😔 該当作品なし。条件を変えてみて。")


if __name__ == "__main__":
    main()
