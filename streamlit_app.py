"""
EcchiGPT — Streamlit版
WordPress FAVO_Beta (Chat UI Edition) の忠実な移植

起動:
  pip install streamlit requests
  streamlit run app.py

JSONファイル（app.pyと同じフォルダ）:
  favo_actress_master.json   ← 女優マスター
  favo_fanza_cluster.json    ← 表記揺れ辞書
"""

import json
import re
import unicodedata
from pathlib import Path

import requests
import streamlit as st

# ─────────────────────────────────────────────
# ページ設定（最初に呼ぶ）
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="EcchiGPT",
    page_icon="🔍",
    layout="wide",
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

BASE_DIR         = Path(__file__).parent
MASTER_JSON_PATH = BASE_DIR / "favo_actress_master.json"
CLUSTER_JSON_PATH= BASE_DIR / "favo_fanza_cluster.json"

STOP_WORDS = {
    "が","を","に","へ","で","と","や","の","も","は","とか","など","な",
    "して","してる","している","され","される","なる","なっ","ある","いる",
    "から","まで","より","だけ","くらい","ぐらい","そして","でも","また",
    "です","ます","だ","ね","よ","なに","何","っぽい","みたい","感じ",
}
NOISE_WORDS = {"セックス","SEX","エロ","H","アダルト"}

PLAY_LABELS = {
    "":           "おまかせ",
    "soft":       "🌸 ソフト",
    "hard":       "🔥 ハード",
    "semeru":     "💥 責める",
    "semerareru": "💋 責められる",
}

# ─────────────────────────────────────────────
# CSS（WordPress版に忠実なスタイル）
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans JP', 'Hiragino Sans', sans-serif !important;
}
.block-container { padding-top: 1rem !important; max-width: 820px !important; }

/* ── ヘッダー ── */
.favo-header {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px;
    background: #fff; border: 1px solid #e5e5e5;
    border-radius: 16px 16px 0 0;
}
.favo-logo {
    width: 32px; height: 32px; border-radius: 8px;
    background: #111; color: #fff;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 15px; flex-shrink: 0;
}
.favo-header-title { font-weight: 800; font-size: 15px; color: #111; }
.favo-header-sub   { font-size: 11px; color: #aaa; margin-top: 1px; }

/* ── サマリーバー ── */
.favo-summary {
    display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
    padding: 7px 14px; min-height: 36px;
    background: #fafafa;
    border-left: 1px solid #e5e5e5;
    border-right: 1px solid #e5e5e5;
    font-size: 11px; color: #bbb;
}
.favo-chip {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px; border-radius: 999px;
    border: 1px solid #e0e0e0; background: #fff;
    font-size: 11px; color: #555;
}

/* ── チャットエリア ── */
.favo-chat-outer {
    border-left: 1px solid #e5e5e5;
    border-right: 1px solid #e5e5e5;
    background: #fff; padding: 14px 14px 4px;
    min-height: 180px;
}
.favo-row        { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 12px; }
.favo-row-user   { display: flex; flex-direction: row-reverse; gap: 8px; align-items: flex-start; margin-bottom: 12px; }
.favo-avatar {
    width: 26px; height: 26px; border-radius: 7px;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 800; flex-shrink: 0; margin-top: 2px;
}
.favo-avatar-bot  { background: #111; color: #fff; }
.favo-avatar-user { background: #f0f0f0; color: #555; }
.favo-bubble {
    max-width: 80%; padding: 10px 14px; border-radius: 14px;
    font-size: 13px; line-height: 1.55; border: 1px solid #efefef;
}
.favo-bubble-bot  { background: #fafafa; color: #222; border-color: #efefef; }
.favo-bubble-user { background: #111; color: #fff; border-color: #111; }

/* ── 女優カード ── */
.actress-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.actress-card { width: 76px; text-align: center; }
.actress-card img {
    width: 76px; height: 102px; object-fit: cover;
    border-radius: 8px; border: 2px solid #efefef; display: block;
}
.actress-card-name { font-size: 10px; color: #444; margin-top: 4px; word-break: break-all; font-weight: 700; }
.actress-card-tags { font-size: 9px; color: #bbb; }

/* ── 結果グリッド ── */
.favo-grid {
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 9px; margin: 12px 0 4px;
}
@media(max-width:580px){ .favo-grid{ grid-template-columns: repeat(2,1fr); } }
.favo-card-item {
    border: 1px solid #efefef; border-radius: 10px;
    overflow: hidden; background: #fff;
}
.favo-card-item img {
    width: 100%; aspect-ratio: 3/4; object-fit: cover; display: block;
}
.favo-card-link {
    display: block; text-align: center;
    font-size: 10px; color: #999; padding: 5px 4px;
    text-decoration: none; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.favo-card-link:hover { color: #111; }

/* ── 入力エリア ── */
.favo-input-outer {
    border: 1px solid #e5e5e5; border-top: 1px solid #f0f0f0;
    border-radius: 0 0 16px 16px;
    padding: 10px 14px 14px; background: #fff;
}
.favo-input-hint { font-size: 11px; color: #ccc; text-align: center; margin-top: 4px; }

/* ── Streamlit UI 調整 ── */
div[data-testid="stTextInput"] input {
    font-size: 15px !important;
    border: 1px solid #e5e5e5 !important;
    border-radius: 10px !important;
    background: #f7f7f7 !important;
    padding: 9px 13px !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #aaa !important;
    background: #fff !important;
    box-shadow: 0 0 0 3px rgba(0,0,0,.04) !important;
}
div[data-testid="stButton"] > button {
    border-radius: 9px !important;
    font-weight: 700 !important;
}
.send-btn > div > button {
    background: #111 !important; color: #fff !important;
    border: none !important;
}
.send-btn > div > button:hover { background: #333 !important; }
.mode-on > div > button {
    background: #111 !important; color: #fff !important;
    border-color: #111 !important;
}
.reset-btn > div > button {
    background: #fff !important; color: #888 !important;
    border: 1px solid #e5e5e5 !important;
    font-size: 12px !important;
}
div.element-container { margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
_DEFAULTS = {
    "mode":         "none",
    "play_filter":  "",
    "tags":         [],
    "last_q":       "",
    "page":         1,
    "results":      [],
    "has_more":     False,
    "chat":         [],
    "ai_hist":      [],
    "fanza_api_id": "",
    "fanza_aff_id": "",
    "openai_key":   "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("，",",").replace("、",",").replace("\u3000"," ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[a-z]+", lambda m: m.group(0).upper(), s)
    return s

def esc(s: str) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def dedup(lst: list) -> list:
    return list(dict.fromkeys(x for x in lst if x))


# ─────────────────────────────────────────────
# JSON読み込み（キャッシュ）
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_master() -> dict:
    _sample = {
        "波多野結衣": {"tags":["黒髪","ロング","スレンダー","清楚"],"keywords":["人気"],"celebs":["新垣結衣","石原さとみ"],"img":""},
        "天使もえ":   {"tags":["ブロンド","ショート","可愛い","童顔"],"keywords":[],"celebs":[],"img":""},
        "三上悠亜":   {"tags":["金髪","スレンダー","可愛い","アイドル"],"keywords":["元AKB"],"celebs":["指原莉乃","前田敦子"],"img":""},
    }
    if MASTER_JSON_PATH.exists():
        try:
            data = json.loads(MASTER_JSON_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict): return data
        except Exception: pass
    return _sample

@st.cache_data(ttl=3600, show_spinner=False)
def load_cluster() -> dict:
    _sample = {
        "巨乳":["おっぱい","Gカップ","爆乳"],
        "スレンダー":["細身","華奢","スリム"],
        "ショート":["ショートヘア","短髪"],
        "ロング":["ロングヘア","長髪"],
        "清楚":["上品","清潔感"],
    }
    if CLUSTER_JSON_PATH.exists():
        try:
            data = json.loads(CLUSTER_JSON_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict): return data
        except Exception: pass
    return _sample

@st.cache_data(ttl=3600, show_spinner=False)
def build_alias_map() -> dict:
    m = {}
    for canon, aliases in load_cluster().items():
        cn = norm(canon)
        if cn: m[cn] = cn
        for a in (aliases if isinstance(aliases, list) else []):
            an = norm(str(a))
            if an: m[an] = cn
    return m

@st.cache_data(ttl=3600, show_spinner=False)
def build_actress_kv() -> dict:
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
def build_celebrity_map() -> dict:
    celmap = {}
    for actress, v in load_master().items():
        an = norm(actress)
        if not an or not isinstance(v,dict): continue
        for c in v.get("celebs", v.get("celebrities",[])):
            cn = norm(str(c))
            if cn: celmap.setdefault(cn,{})[an] = 1
    return celmap


# ─────────────────────────────────────────────
# フィルタ
# ─────────────────────────────────────────────
def item_valid(item) -> bool:
    d = str(item.get("date",""))
    m = re.search(r"(\d{4})", d)
    y = int(m.group(1)) if m else 0
    if y > 0 and y <= MIN_RELEASE_YEAR: return False
    for g in item.get("iteminfo",{}).get("genre",[]):
        gn = norm(g.get("name",""))
        if any(w and w in gn for w in NG_GENRE_KEYWORDS): return False
    title = norm(item.get("title",""))
    return not any(w and w in title for w in NG_TITLE_KEYWORDS)

def is_collection(item) -> bool:
    return any(norm(g.get("name","")) == "ベスト・総集編"
               for g in item.get("iteminfo",{}).get("genre",[]))

def match_mode(item, mode) -> bool:
    if mode in ("none",""): return True
    col = is_collection(item)
    return col if mode=="collection" else not col

def is_hard(item) -> bool:
    for g in item.get("iteminfo",{}).get("genre",[]):
        if any(w and w in norm(g.get("name","")) for w in ["辱め","拘束","淫乱・ハード系","羞恥"]): return True
    return any(w and w in norm(item.get("title","")) for w in ["肉便器","性処理","アクメ"])

def match_play(item, pf) -> bool:
    if not pf or pf=="none": return True
    t = norm(item.get("title",""))
    if pf=="hard":        return is_hard(item)
    if pf=="soft":        return not is_hard(item)
    if pf=="semeru":      return "イカセ" in t
    if pf=="semerareru":  return "痴女" in t
    return True


# ─────────────────────────────────────────────
# スコアリング
# ─────────────────────────────────────────────
def score_item(item, meaning_list) -> int:
    if not meaning_list: return 0
    sc = 0
    title  = norm(item.get("title",""))
    genres = item.get("iteminfo",{}).get("genre",[])
    aset   = dedup([norm(a.get("name","")) for a in item.get("iteminfo",{}).get("actress",[])])
    db     = build_actress_kv()

    for m in meaning_list:
        m = norm(m)
        if not m: continue
        if m in title: sc += 3
        for g in genres:
            if m in norm(g.get("name","")): sc += 2; break
        for a in aset:
            if len(m)>=2 and m in a: sc += ACTRESS_NAME_POINT
            v = db.get(a)
            if v and m in (v["tags"]+v["keywords"]): sc += ACTRESS_MATCH_POINT; break
    return min(sc, ACTRESS_SCORE_CAP)

def score_actresses_for_ai(input_tags, limit=6) -> list:
    master = load_master()
    input_norm = [norm(t) for t in input_tags if norm(t)]
    if not input_norm or not master: return []

    rows = []
    for name, v in master.items():
        nn = norm(name)
        if not nn: continue
        all_tags = ([norm(t) for t in v.get("tags",[])+v.get("keywords",v.get("kw",[]))] if isinstance(v,dict) else [])
        s = 0
        for inp in input_norm:
            for nt in all_tags:
                if nt==inp: s+=3; break
                elif inp in nt or nt in inp: s+=1; break
        rows.append({"name":name,"nn":nn,"img":v.get("img","") if isinstance(v,dict) else "","tags":all_tags[:5],"score":s})

    rows.sort(key=lambda x: -x["score"])
    return rows[:limit]


# ─────────────────────────────────────────────
# クエリ分解
# ─────────────────────────────────────────────
def split_query(q_raw: str) -> dict:
    q = norm(q_raw)
    if not q: return {"search":[],"meaning":[],"noise":[],"celebrity":[]}

    celmap   = build_celebrity_map()
    cel_keys = sorted(celmap.keys(), key=lambda x: -len(x))
    celebs, rest = [], q
    for c in cel_keys:
        if c and c in rest: celebs.append(c); rest = rest.replace(c," ")

    alias_map = build_alias_map()
    search    = []
    for a in sorted(alias_map.keys(), key=lambda x: -len(x)):
        cn = alias_map.get(a,"")
        if a and cn and a in rest: search.append(cn); rest = rest.replace(a," ")

    meaning, noise = [], []
    for t in re.split(r"[\s,/|]+", norm(rest)):
        t = norm(t)
        if not t or len(t)<=1: noise.append(t)
        elif t in STOP_WORDS or t in NOISE_WORDS: noise.append(t)
        else: meaning.append(t)

    return {
        "search":    dedup(search),
        "meaning":   dedup(meaning),
        "noise":     dedup(noise),
        "celebrity": dedup(celebs),
    }


# ─────────────────────────────────────────────
# FANZA API
# ─────────────────────────────────────────────
@st.cache_data(ttl=CACHE_SEC, show_spinner=False)
def fanza_fetch(keyword: str, hits: int, api_id: str, aff_id: str) -> dict:
    if not keyword or not api_id or not aff_id:
        return {"items":[], "error":"missing_config"}
    try:
        r = requests.get(
            "https://api.dmm.com/affiliate/v3/ItemList",
            params={
                "api_id":api_id,"affiliate_id":aff_id,
                "site":"FANZA","service":"digital","floor":"videoa",
                "hits":str(min(100,max(1,hits))),"sort":"date",
                "keyword":keyword,"output":"json",
            },
            timeout=20,
        )
        r.raise_for_status()
        items = r.json().get("result",{}).get("items",[])
        return {"items":[it for it in items if item_valid(it)]}
    except Exception as e:
        return {"items":[], "error":str(e)}

def do_search(q_raw, mode, play_filter, page, api_id, aff_id) -> dict:
    split  = split_query(q_raw)
    celmap = build_celebrity_map()

    celeb_cands = dedup(
        a for c in split["celebrity"]
        for a in list(celmap.get(c,{}).keys())[:3]
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
                    if len(items)>=FETCH_HITS: break
    else:
        alias_map = build_alias_map()
        q_n = norm(q_raw)
        for a, c in sorted(alias_map.items(), key=lambda x: -len(x[0])):
            if a and a in q_n: q_n = q_n.replace(a,c)
        items = fanza_fetch(norm(q_n), FETCH_HITS, api_id, aff_id).get("items",[])

    filtered = [it for it in items if match_mode(it,mode) and match_play(it,play_filter)]
    sorted_  = sorted(filtered, key=lambda it: -score_item(it, split["meaning"]))

    off       = (page-1)*PER_PAGE
    page_items= sorted_[off:off+PER_PAGE]
    has_more  = len(sorted_) > off+PER_PAGE

    out = [{
        "title":    it.get("title",""),
        "url":      it.get("URL",""),
        "image":    it.get("imageURL",{}).get("small","") or it.get("imageURL",{}).get("large",""),
        "item_key": it.get("URL","") or it.get("content_id",""),
    } for it in page_items]

    return {"items":out,"has_more":has_more}


# ─────────────────────────────────────────────
# OpenAI 解釈
# ─────────────────────────────────────────────
def ai_interpret(user_msg, history, current_tags, api_key) -> dict:
    if not api_key: return {"error":"no_api_key"}

    cands = score_actresses_for_ai(current_tags or [user_msg], 6)
    actress_ctx = ""
    if cands:
        lines = [f"・{c['name']}（{'・'.join(c['tags']) or 'タグ未登録'}）" for c in cands]
        actress_ctx = "\n\n# 候補女優（タグマッチ上位）\n" + "\n".join(lines) + \
            "\n※希望に近い女優をselected_actressesに入れてください。"

    system = (
        "あなたはアダルトDVD検索サイトのアシスタントです。\n"
        "ユーザーの日本語入力から検索タグと最適な女優を選んでください。\n\n"
        "# 出力形式（JSONのみ・説明不要）\n"
        '{"tags":["タグ1"],"selected_actresses":["女優名"],'
        '"detected_celebs":["芸能人名"],'
        '"play_filter":"none|soft|hard|semeru|semerareru",'
        '"bot_reply":"返答（1〜2文、フレンドリーに）","remove_tags":["削除タグ"]}\n\n'
        "# ルール\n"
        "- detected_celebsには芸能人・タレント・アイドル名を必ず入れる\n"
        "- selected_actressesは候補リストから1〜3人\n"
        "- remove_tagsは前の条件で不要になったもの\n"
        "- 出力はJSONのみ"
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
# HTML レンダラー
# ─────────────────────────────────────────────
def render_header():
    st.markdown("""
    <div class="favo-header">
      <div class="favo-logo">E</div>
      <div>
        <div class="favo-header-title">EcchiGPT</div>
        <div class="favo-header-sub">会話で探していこう</div>
      </div>
    </div>""", unsafe_allow_html=True)

def render_summary():
    tags = st.session_state["tags"]
    mode = st.session_state["mode"]
    pf   = st.session_state["play_filter"]

    if not tags and mode=="none" and not pf:
        st.markdown(
            '<div class="favo-summary">条件：<span style="color:#ccc">（まだなし）</span></div>',
            unsafe_allow_html=True,
        )
        return

    chips = ""
    if mode != "none":
        chips += f'<span class="favo-chip">モード：{"単体" if mode=="single" else "総集編"}</span>'
    if pf:
        chips += f'<span class="favo-chip">プレイ：{esc(PLAY_LABELS.get(pf,pf))}</span>'
    for t in tags:
        chips += f'<span class="favo-chip">{esc(t)}</span>'

    st.markdown(f'<div class="favo-summary">条件：{chips}</div>', unsafe_allow_html=True)

def render_chat():
    html = '<div class="favo-chat-outer">'
    if not st.session_state["chat"]:
        html += (
            '<div class="favo-row">'
            '  <div class="favo-avatar favo-avatar-bot">E</div>'
            '  <div class="favo-bubble favo-bubble-bot">'
            '    どんな感じで探す？<br>'
            '    <span style="color:#bbb;font-size:11px;">外見・雰囲気・好きな芸能人、なんでもOKだよ</span>'
            '  </div>'
            '</div>'
        )
    else:
        for msg in st.session_state["chat"]:
            role = msg["role"]
            text = esc(msg["text"])
            if role == "user":
                html += (
                    f'<div class="favo-row-user">'
                    f'  <div class="favo-bubble favo-bubble-user">{text}</div>'
                    f'  <div class="favo-avatar favo-avatar-user">U</div>'
                    f'</div>'
                )
            else:
                html += (
                    f'<div class="favo-row">'
                    f'  <div class="favo-avatar favo-avatar-bot">E</div>'
                    f'  <div class="favo-bubble favo-bubble-bot">{text}'
                )
                for c in msg.get("actress_cards",[]):
                    img = (
                        f'<img src="{esc(c["img"])}" loading="lazy" alt="{esc(c["name"])}">'
                        if c.get("img") else
                        '<div style="width:76px;height:102px;background:#f0f0f0;border-radius:8px;'
                        'display:flex;align-items:center;justify-content:center;'
                        'font-size:9px;color:#ccc;">no img</div>'
                    )
                    tags_str = " · ".join(c.get("tags",[])[:3])
                    html += (
                        f'<div class="actress-row"><div class="actress-card">'
                        f'  {img}'
                        f'  <div class="actress-card-name">{esc(c["name"])}</div>'
                        f'  <div class="actress-card-tags">{esc(tags_str)}</div>'
                        f'</div></div>'
                    )
                html += '  </div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_results():
    items = st.session_state["results"]
    if not items: return

    html = '<div class="favo-grid">'
    for it in items:
        title_s = (it["title"][:18]+"…") if len(it["title"])>18 else it["title"]
        img_tag = (
            f'<img src="{esc(it["image"])}" loading="lazy" alt="">'
            if it.get("image") else
            '<div style="aspect-ratio:3/4;background:#f5f5f5;display:flex;align-items:center;'
            'justify-content:center;font-size:10px;color:#ccc;">no img</div>'
        )
        html += (
            f'<div class="favo-card-item">'
            f'  <a href="{esc(it["url"])}" target="_blank" rel="nofollow noopener">{img_tag}</a>'
            f'  <a class="favo-card-link" href="{esc(it["url"])}" target="_blank" rel="nofollow noopener">'
            f'    ▶ {esc(title_s)}</a>'
            f'</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown("## ⚙️ 設定")

        with st.expander("🔑 APIキー", expanded=True):
            fanza_api = st.text_input("FANZA API ID",       value=st.session_state["fanza_api_id"], type="password", key="sb_api")
            fanza_aff = st.text_input("FANZA Affiliate ID", value=st.session_state["fanza_aff_id"], type="password", key="sb_aff")
            openai_k  = st.text_input("OpenAI API Key",     value=st.session_state["openai_key"],   type="password", key="sb_oai")
            if st.button("💾 保存", use_container_width=True):
                st.session_state["fanza_api_id"] = fanza_api
                st.session_state["fanza_aff_id"] = fanza_aff
                st.session_state["openai_key"]   = openai_k
                st.success("保存した")

        st.divider()

        with st.expander("📁 JSONファイル", expanded=True):
            for path, label in [(MASTER_JSON_PATH,"Actress Master"),(CLUSTER_JSON_PATH,"Cluster")]:
                if path.exists():
                    kb = path.stat().st_size//1024
                    st.success(f"✅ {label} ({kb} KB)")
                else:
                    st.warning(f"⚠ {label} — サンプル動作中")

            up = st.file_uploader("JSONをアップロード（master/clusterどちらも可）", type="json", key="up_json")
            if up:
                try:
                    data = json.loads(up.read().decode("utf-8-sig"))
                    if not isinstance(data, dict):
                        st.error("dict形式が必要")
                    else:
                        dest = MASTER_JSON_PATH if "master" in up.name.lower() else CLUSTER_JSON_PATH
                        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                        st.cache_data.clear()
                        st.success(f"{dest.name} 保存（{len(data)}件）")
                        st.rerun()
                except Exception as e:
                    st.error(f"エラー: {e}")

            c1,c2 = st.columns(2)
            with c1:
                st.download_button("Master↓", data=json.dumps(load_master(),ensure_ascii=False,indent=2),
                                   file_name="favo_actress_master.json", mime="application/json", use_container_width=True)
            with c2:
                st.download_button("Cluster↓", data=json.dumps(load_cluster(),ensure_ascii=False,indent=2),
                                   file_name="favo_fanza_cluster.json", mime="application/json", use_container_width=True)

        with st.expander("➕ 女優を追加"):
            new_name   = st.text_input("女優名", key="add_name")
            new_tags   = st.text_input("タグ（カンマ区切り）", key="add_tags")
            new_celebs = st.text_input("芸能人（カンマ区切り）", key="add_celebs")
            if st.button("追加", use_container_width=True, key="btn_add_actress"):
                if new_name.strip():
                    master = load_master().copy()
                    master[new_name.strip()] = {
                        "tags":    [t.strip() for t in new_tags.split(",") if t.strip()],
                        "keywords": [],
                        "celebs":  [c.strip() for c in new_celebs.split(",") if c.strip()],
                        "img":     "",
                    }
                    MASTER_JSON_PATH.write_text(json.dumps(master,ensure_ascii=False,indent=2),encoding="utf-8")
                    st.cache_data.clear()
                    st.success(f"追加: {new_name}")
                    st.rerun()

        with st.expander("✏️ 女優を編集"):
            master = load_master()
            if master:
                sel = st.selectbox("女優を選択", list(master.keys()), key="sel_actress")
                entry_str = json.dumps(master.get(sel,{}), ensure_ascii=False, indent=2)
                edited = st.text_area("JSON編集", value=entry_str, height=180, key="edit_entry")
                if st.button("💾 保存", use_container_width=True, key="btn_edit_save"):
                    try:
                        master[sel] = json.loads(edited)
                        MASTER_JSON_PATH.write_text(json.dumps(master,ensure_ascii=False,indent=2),encoding="utf-8")
                        st.cache_data.clear()
                        st.success("保存した")
                    except Exception as e:
                        st.error(f"JSONエラー: {e}")


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    sidebar()

    # ── ヘッダー ──────────────────────────────
    hcol, rcol = st.columns([6,1])
    with hcol:
        render_header()
    with rcol:
        st.write("")  # 上の余白合わせ
        st.markdown('<div class="reset-btn">', unsafe_allow_html=True)
        if st.button("🔄 リセット", use_container_width=True, key="btn_reset"):
            for k,v in _DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ── サマリーバー ──────────────────────────
    render_summary()

    # ── モードバー ────────────────────────────
    mc1, mc2, mc3, mc4, mc5 = st.columns([1.2,1.2,1.4,1.6,1.2])

    with mc1:
        is_single = st.session_state["mode"]=="single"
        st.markdown('<div class="mode-on">' if is_single else '<div>', unsafe_allow_html=True)
        if st.button("📌 単体", use_container_width=True, key="btn_single"):
            st.session_state["mode"] = "none" if is_single else "single"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with mc2:
        is_col = st.session_state["mode"]=="collection"
        st.markdown('<div class="mode-on">' if is_col else '<div>', unsafe_allow_html=True)
        if st.button("📚 総集編", use_container_width=True, key="btn_col"):
            st.session_state["mode"] = "none" if is_col else "collection"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with mc3:
        pf_keys = list(PLAY_LABELS.keys())
        cur_pf  = st.session_state["play_filter"]
        cur_idx = pf_keys.index(cur_pf) if cur_pf in pf_keys else 0
        new_pf  = st.selectbox("プレイ", pf_keys, index=cur_idx,
                                format_func=lambda x: PLAY_LABELS[x],
                                label_visibility="collapsed", key="sel_pf")
        if new_pf != cur_pf:
            st.session_state["play_filter"] = new_pf
            st.rerun()

    with mc4:
        pass  # スペーサー

    with mc5:
        if st.session_state["tags"] or st.session_state["mode"]!="none" or st.session_state["play_filter"]:
            if st.button("✕ 条件クリア", use_container_width=True, key="btn_clear"):
                st.session_state.update({"tags":[],"last_q":"","results":[],"page":1,
                                          "mode":"none","play_filter":""})
                st.rerun()

    # ── チャット表示 ──────────────────────────
    render_chat()

    # ── 入力エリア ────────────────────────────
    st.markdown('<div class="favo-input-outer">', unsafe_allow_html=True)
    ic, bc = st.columns([5,1])
    with ic:
        user_input = st.text_input(
            "q", label_visibility="collapsed",
            placeholder="例：黒髪 ボブ 清楚 ちょいエロ…",
            key="txt_input",
        )
    with bc:
        st.markdown('<div class="send-btn">', unsafe_allow_html=True)
        send_clicked = st.button("↑ 送信", use_container_width=True, key="btn_send")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="favo-input-hint">Enter で送信 · 条件は積み重ねられる</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 送信ハンドラ ──────────────────────────
    if send_clicked and user_input.strip():
        typed = user_input.strip()
        st.session_state["chat"].append({"role":"user","text":typed,"actress_cards":[]})

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
                bot_reply = result.get("bot_reply","OK、探すね！")
                st.session_state["ai_hist"] += [
                    {"role":"user","content":typed},
                    {"role":"assistant","content":bot_reply},
                ]
                remove = [t.strip().lower() for t in result.get("remove_tags",[])]
                curr   = [t for t in st.session_state["tags"] if t.lower() not in remove]
                new_t  = [t.strip() for t in result.get("tags",[]) if t.strip()]
                sel    = [t.strip() for t in result.get("selected_actresses",[]) if t.strip()]
                st.session_state["tags"] = dedup(curr+new_t+sel)

                pf = result.get("play_filter","none")
                if pf and pf!="none": st.session_state["play_filter"] = pf

                # 女優カード
                master = load_master()
                for name in result.get("selected_actresses",[]):
                    v = master.get(name) or master.get(norm(name))
                    if v and isinstance(v,dict):
                        actress_cards.append({
                            "name":name,
                            "img": v.get("img",""),
                            "tags":v.get("tags",[])[:4],
                        })

                # 未登録芸能人のフォローメッセージ
                unknown = [c for c in result.get("detected_celebs",[])
                           if norm(c) not in build_celebrity_map()]
                if unknown:
                    bot_reply = f"ごめん、{'・'.join(unknown)}に似てる人は見つからなかった。他にいない？"
            else:
                # AIエラーフォールバック
                bot_reply = "OK、探すね 🔍"
                parts = dedup([norm(p) for p in typed.split()])
                st.session_state["tags"] = dedup(st.session_state["tags"]+parts)
        else:
            # OpenAIなし
            bot_reply = "OK、探すね 🔍（OpenAI未設定）"
            parts = dedup([norm(p) for p in typed.split()])
            st.session_state["tags"] = dedup(st.session_state["tags"]+parts)

        st.session_state["last_q"] = " ".join(st.session_state["tags"])
        st.session_state["chat"].append({"role":"bot","text":bot_reply,"actress_cards":actress_cards})

        # FANZA検索
        if fanza_api and fanza_aff and st.session_state["last_q"]:
            with st.spinner("検索中…"):
                res = do_search(
                    st.session_state["last_q"],
                    st.session_state["mode"],
                    st.session_state["play_filter"],
                    1, fanza_api, fanza_aff,
                )
            st.session_state.update({"results":res["items"],"has_more":res["has_more"],"page":2})
        elif not fanza_api or not fanza_aff:
            st.session_state["chat"].append({
                "role":"bot",
                "text":"⚠ サイドバーの「APIキー」にFANZA API IDとAffiliate IDを入力してね",
                "actress_cards":[],
            })

        st.rerun()

    # ── 結果表示 ──────────────────────────────
    if st.session_state["results"]:
        st.markdown('<hr style="margin:6px 0;">', unsafe_allow_html=True)
        render_results()

        if st.session_state["has_more"]:
            ncol, _, _ = st.columns([1,2,2])
            with ncol:
                if st.button("次の10件を見る →", use_container_width=True, key="btn_next"):
                    api  = st.session_state["fanza_api_id"]
                    aff  = st.session_state["fanza_aff_id"]
                    if api and aff:
                        with st.spinner("読み込み中…"):
                            res = do_search(
                                st.session_state["last_q"],
                                st.session_state["mode"],
                                st.session_state["play_filter"],
                                st.session_state["page"],
                                api, aff,
                            )
                        st.session_state["results"] += res["items"]
                        st.session_state["has_more"] = res["has_more"]
                        st.session_state["page"] += 1
                        st.rerun()

    elif st.session_state["last_q"] and not st.session_state["results"]:
        st.info("😔 該当作品なし。条件を少し変えてみて。")


if __name__ == "__main__":
    main()
