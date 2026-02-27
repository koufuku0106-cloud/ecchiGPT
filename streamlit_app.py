"""
EcchiGPT — Streamlit版
WordPress FAVO_Beta (Chat UI Edition) の忠実な移植

起動:
  pip install streamlit requests
  streamlit run streamlit_app.py

JSONファイル（同じフォルダ）:
  favo_actress_master.json
  favo_fanza_cluster.json
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
    "":"おまかせ","soft":"🌸 ソフト","hard":"🔥 ハード",
    "semeru":"💥 責める","semerareru":"💋 責められる",
}

# ─────────────────────────────────────────────
# グローバルCSS（Streamlit自体を極力消す）
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
html,body,[class*="css"]{font-family:'Noto Sans JP','Hiragino Sans',sans-serif!important;background:#f4f4f4!important;}
.block-container{padding:1rem .5rem 2rem!important;max-width:800px!important;}
header[data-testid="stHeader"]{display:none!important;}
footer{display:none!important;}
.stDeployButton{display:none!important;}
/* Streamlit ウィジェットを完全に見えなくする */
div[data-testid="stTextInput"],
div[data-testid="stButton"],
div[data-testid="stSelectbox"],
div[data-testid="stCheckbox"]{
    position:fixed!important;bottom:-9999px!important;left:-9999px!important;
    width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;
    pointer-events:none!important;
}
/* 余白ゼロ */
div.element-container,div.stMarkdown,div[data-testid="column"]{margin:0!important;padding:0!important;}
hr{display:none!important;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
_DEFAULTS = {
    "mode":"none","play_filter":"",
    "tags":[],"last_q":"","page":1,
    "results":[],"has_more":False,
    "chat":[],"ai_hist":[],
    "fanza_api_id":"","fanza_aff_id":"","openai_key":"",
}
for _k,_v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────
def norm(s):
    s = unicodedata.normalize("NFKC",str(s))
    s = s.replace("，",",").replace("、",",").replace("\u3000"," ")
    s = re.sub(r"\s+"," ",s).strip()
    return re.sub(r"[a-z]+",lambda m:m.group(0).upper(),s)

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def dedup(lst):
    return list(dict.fromkeys(x for x in lst if x))

# ─────────────────────────────────────────────
# JSON読み込み
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600,show_spinner=False)
def load_master():
    s={"波多野結衣":{"tags":["黒髪","ロング","スレンダー","清楚"],"keywords":["人気"],"celebs":["新垣結衣","石原さとみ"],"img":""},
       "天使もえ":{"tags":["ブロンド","ショート","可愛い","童顔"],"keywords":[],"celebs":[],"img":""},
       "三上悠亜":{"tags":["金髪","スレンダー","可愛い","アイドル"],"keywords":["元AKB"],"celebs":["指原莉乃","前田敦子"],"img":""}}
    if MASTER_JSON_PATH.exists():
        try:
            d=json.loads(MASTER_JSON_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(d,dict): return d
        except: pass
    return s

@st.cache_data(ttl=3600,show_spinner=False)
def load_cluster():
    s={"巨乳":["おっぱい","Gカップ","爆乳"],"スレンダー":["細身","華奢","スリム"],
       "ショート":["ショートヘア","短髪"],"ロング":["ロングヘア","長髪"],"清楚":["上品","清潔感"]}
    if CLUSTER_JSON_PATH.exists():
        try:
            d=json.loads(CLUSTER_JSON_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(d,dict): return d
        except: pass
    return s

@st.cache_data(ttl=3600,show_spinner=False)
def build_alias_map():
    m={}
    for canon,aliases in load_cluster().items():
        cn=norm(canon)
        if cn: m[cn]=cn
        for a in (aliases if isinstance(aliases,list) else []):
            an=norm(str(a))
            if an: m[an]=cn
    return m

@st.cache_data(ttl=3600,show_spinner=False)
def build_actress_kv():
    out={}
    for name,v in load_master().items():
        nn=norm(name)
        if not nn: continue
        tags=v.get("tags",[]) if isinstance(v,dict) else (v if isinstance(v,list) else [])
        kw=v.get("keywords",v.get("kw",[])) if isinstance(v,dict) else []
        out[nn]={"tags":[norm(t) for t in tags if norm(t)],"keywords":[norm(t) for t in kw if norm(t)],
                 "img":v.get("img","") if isinstance(v,dict) else ""}
    return out

@st.cache_data(ttl=3600,show_spinner=False)
def build_celebrity_map():
    celmap={}
    for actress,v in load_master().items():
        an=norm(actress)
        if not an or not isinstance(v,dict): continue
        for c in v.get("celebs",v.get("celebrities",[])):
            cn=norm(str(c))
            if cn: celmap.setdefault(cn,{})[an]=1
    return celmap

# ─────────────────────────────────────────────
# フィルタ・スコア
# ─────────────────────────────────────────────
def item_valid(item):
    m=re.search(r"(\d{4})",str(item.get("date","")))
    y=int(m.group(1)) if m else 0
    if y>0 and y<=MIN_RELEASE_YEAR: return False
    for g in item.get("iteminfo",{}).get("genre",[]):
        gn=norm(g.get("name",""))
        if any(w and w in gn for w in NG_GENRE_KEYWORDS): return False
    return not any(w and w in norm(item.get("title","")) for w in NG_TITLE_KEYWORDS)

def is_collection(item):
    return any(norm(g.get("name",""))=="ベスト・総集編" for g in item.get("iteminfo",{}).get("genre",[]))

def match_mode(item,mode):
    if mode in("none",""): return True
    col=is_collection(item)
    return col if mode=="collection" else not col

def is_hard(item):
    for g in item.get("iteminfo",{}).get("genre",[]):
        if any(w and w in norm(g.get("name","")) for w in ["辱め","拘束","淫乱・ハード系","羞恥"]): return True
    return any(w and w in norm(item.get("title","")) for w in ["肉便器","性処理","アクメ"])

def match_play(item,pf):
    if not pf or pf=="none": return True
    t=norm(item.get("title",""))
    if pf=="hard": return is_hard(item)
    if pf=="soft": return not is_hard(item)
    if pf=="semeru": return "イカセ" in t
    if pf=="semerareru": return "痴女" in t
    return True

def score_item(item,meaning_list):
    if not meaning_list: return 0
    sc=0; title=norm(item.get("title","")); db=build_actress_kv()
    aset=dedup([norm(a.get("name","")) for a in item.get("iteminfo",{}).get("actress",[])])
    for m in meaning_list:
        m=norm(m)
        if not m: continue
        if m in title: sc+=3
        for g in item.get("iteminfo",{}).get("genre",[]):
            if m in norm(g.get("name","")): sc+=2; break
        for a in aset:
            if len(m)>=2 and m in a: sc+=ACTRESS_NAME_POINT
            v=db.get(a)
            if v and m in(v["tags"]+v["keywords"]): sc+=ACTRESS_MATCH_POINT; break
    return min(sc,ACTRESS_SCORE_CAP)

def score_actresses_for_ai(input_tags,limit=6):
    master=load_master(); input_norm=[norm(t) for t in input_tags if norm(t)]
    if not input_norm or not master: return []
    rows=[]
    for name,v in master.items():
        nn=norm(name)
        if not nn: continue
        all_tags=([norm(t) for t in v.get("tags",[])+v.get("keywords",v.get("kw",[]))] if isinstance(v,dict) else [])
        s=sum(3 if nt==inp else(1 if inp in nt or nt in inp else 0) for inp in input_norm for nt in all_tags[:1 or len(all_tags)])
        rows.append({"name":name,"nn":nn,"img":v.get("img","") if isinstance(v,dict) else "","tags":all_tags[:5],"score":s})
    rows.sort(key=lambda x:-x["score"])
    return rows[:limit]

# ─────────────────────────────────────────────
# クエリ分解
# ─────────────────────────────────────────────
def split_query(q_raw):
    q=norm(q_raw)
    if not q: return {"search":[],"meaning":[],"noise":[],"celebrity":[]}
    celmap=build_celebrity_map(); cel_keys=sorted(celmap.keys(),key=lambda x:-len(x))
    celebs,rest=[],q
    for c in cel_keys:
        if c and c in rest: celebs.append(c); rest=rest.replace(c," ")
    alias_map=build_alias_map(); search=[]
    for a in sorted(alias_map.keys(),key=lambda x:-len(x)):
        cn=alias_map.get(a,"")
        if a and cn and a in rest: search.append(cn); rest=rest.replace(a," ")
    meaning,noise=[],[]
    for t in re.split(r"[\s,/|]+",norm(rest)):
        t=norm(t)
        if not t or len(t)<=1: noise.append(t)
        elif t in STOP_WORDS or t in NOISE_WORDS: noise.append(t)
        else: meaning.append(t)
    return {"search":dedup(search),"meaning":dedup(meaning),"noise":dedup(noise),"celebrity":dedup(celebs)}

# ─────────────────────────────────────────────
# FANZA API
# ─────────────────────────────────────────────
@st.cache_data(ttl=CACHE_SEC,show_spinner=False)
def fanza_fetch(keyword,hits,api_id,aff_id):
    if not keyword or not api_id or not aff_id: return {"items":[],"error":"missing_config"}
    try:
        r=requests.get("https://api.dmm.com/affiliate/v3/ItemList",
            params={"api_id":api_id,"affiliate_id":aff_id,"site":"FANZA","service":"digital",
                    "floor":"videoa","hits":str(min(100,max(1,hits))),"sort":"date","keyword":keyword,"output":"json"},
            timeout=20)
        r.raise_for_status()
        items=r.json().get("result",{}).get("items",[])
        return {"items":[it for it in items if item_valid(it)]}
    except Exception as e:
        return {"items":[],"error":str(e)}

def do_search(q_raw,mode,play_filter,page,api_id,aff_id):
    split=split_query(q_raw); celmap=build_celebrity_map()
    celeb_cands=dedup(a for c in split["celebrity"] for a in list(celmap.get(c,{}).keys())[:3])[:5]
    if split["search"]:
        items=fanza_fetch(" ".join(split["search"]),FETCH_HITS,api_id,aff_id).get("items",[])
    elif celeb_cands:
        items,seen=[],set()
        for c in celeb_cands[:3]:
            for it in fanza_fetch(c,25,api_id,aff_id).get("items",[]):
                k=it.get("URL","") or it.get("content_id","")
                if k and k not in seen: seen.add(k); items.append(it)
                if len(items)>=FETCH_HITS: break
    else:
        alias_map=build_alias_map(); q_n=norm(q_raw)
        for a,c in sorted(alias_map.items(),key=lambda x:-len(x[0])):
            if a and a in q_n: q_n=q_n.replace(a,c)
        items=fanza_fetch(norm(q_n),FETCH_HITS,api_id,aff_id).get("items",[])
    filtered=[it for it in items if match_mode(it,mode) and match_play(it,play_filter)]
    sorted_=sorted(filtered,key=lambda it:-score_item(it,split["meaning"]))
    off=(page-1)*PER_PAGE; page_items=sorted_[off:off+PER_PAGE]; has_more=len(sorted_)>off+PER_PAGE
    out=[{"title":it.get("title",""),"url":it.get("URL",""),
          "image":it.get("imageURL",{}).get("small","") or it.get("imageURL",{}).get("large",""),
          "item_key":it.get("URL","") or it.get("content_id","")} for it in page_items]
    return {"items":out,"has_more":has_more}

# ─────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────
def ai_interpret(user_msg,history,current_tags,api_key):
    if not api_key: return {"error":"no_api_key"}
    cands=score_actresses_for_ai(current_tags or [user_msg],6)
    actress_ctx=""
    if cands:
        lines=[f"・{c['name']}（{'・'.join(c['tags']) or 'タグ未登録'}）" for c in cands]
        actress_ctx="\n\n# 候補女優\n"+"\n".join(lines)+"\n※希望に近い女優をselected_actressesに。"
    system=(
        "あなたはアダルトDVD検索サイトのアシスタントです。\n"
        "ユーザーの日本語入力から検索タグと最適な女優を選んでください。\n\n"
        "# 出力形式（JSONのみ）\n"
        '{"tags":["タグ"],"selected_actresses":["女優名"],'
        '"detected_celebs":["芸能人名"],'
        '"play_filter":"none|soft|hard|semeru|semerareru",'
        '"bot_reply":"返答（1〜2文）","remove_tags":["削除タグ"]}'
        +actress_ctx
    )
    messages=[{"role":"system","content":system}]
    for h in history[-6:]:
        if h.get("role") in("user","assistant") and h.get("content"):
            messages.append({"role":h["role"],"content":h["content"]})
    messages.append({"role":"user","content":str(user_msg)})
    try:
        r=requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":"gpt-4o-mini","messages":messages,"temperature":0.3,"max_tokens":400},timeout=15)
        r.raise_for_status()
        text=r.json()["choices"][0]["message"]["content"]
        text=re.sub(r"^```json\s*","",text.strip()); text=re.sub(r"```\s*$","",text).strip()
        return json.loads(text)
    except Exception as e:
        return {"error":str(e)}

# ─────────────────────────────────────────────
# HTML UI 生成
# ─────────────────────────────────────────────
def build_ui_html():
    tags=st.session_state["tags"]; mode=st.session_state["mode"]
    pf=st.session_state["play_filter"]; chat=st.session_state["chat"]
    results=st.session_state["results"]; has_more=st.session_state["has_more"]

    # サマリーチップ
    if not tags and mode=="none" and not pf:
        chips_html='<span style="color:#ccc">（まだなし）</span>'
    else:
        chips_html=""
        if mode!="none": chips_html+=f'<span class="chip">{"単体" if mode=="single" else "総集編"}</span>'
        if pf: chips_html+=f'<span class="chip">プレイ:{esc(PLAY_LABELS.get(pf,pf))}</span>'
        for t in tags: chips_html+=f'<span class="chip">{esc(t)}</span>'

    # モードボタン
    s_on='on' if mode=="single" else ''
    c_on='on' if mode=="collection" else ''

    # プレイセレクト
    pf_opts="".join(f'<option value="{k}"{"selected" if k==pf else ""}>{v}</option>' for k,v in PLAY_LABELS.items())

    # チャット
    if not chat:
        chat_inner=(
            '<div class="row">'
            '<div class="av bot">E</div>'
            '<div class="bbl bot">どんな感じで探す？<br>'
            '<span style="color:#bbb;font-size:11px">外見・雰囲気・好きな芸能人、なんでもOKだよ</span>'
            '</div></div>'
        )
    else:
        chat_inner=""
        for msg in chat:
            txt=esc(msg["text"])
            if msg["role"]=="user":
                chat_inner+=f'<div class="row user"><div class="bbl user">{txt}</div><div class="av user">U</div></div>'
            else:
                cards=""
                for c in msg.get("actress_cards",[]):
                    img=(f'<img src="{esc(c["img"])}" loading="lazy" alt="{esc(c["name"])}">'
                         if c.get("img") else
                         '<div class="no-img">no img</div>')
                    tg=" · ".join(c.get("tags",[])[:3])
                    cards+=f'<div class="acard">{img}<div class="aname">{esc(c["name"])}</div><div class="atag">{esc(tg)}</div></div>'
                ac=f'<div class="arow">{cards}</div>' if cards else ""
                chat_inner+=f'<div class="row"><div class="av bot">E</div><div class="bbl bot">{txt}{ac}</div></div>'

    # 結果グリッド
    if results:
        grid=""
        for it in results:
            t=(it["title"][:18]+"…") if len(it["title"])>18 else it["title"]
            img=(f'<img src="{esc(it["image"])}" loading="lazy" alt="">'
                 if it.get("image") else '<div class="no-img-card"></div>')
            grid+=f'<div class="card"><a href="{esc(it["url"])}" target="_blank" rel="nofollow noopener">{img}</a><a class="card-link" href="{esc(it["url"])}" target="_blank" rel="nofollow noopener">▶ {esc(t)}</a></div>'
        nxt=('<div class="next-wrap"><button class="next-btn" onclick="act(\'next\')">次の10件を見る →</button></div>'
             if has_more else "")
        results_html=f'<div id="results"><div class="grid">{grid}</div>{nxt}</div>'
    else:
        results_html=""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Noto Sans JP','Hiragino Sans',sans-serif;background:#f4f4f4;padding:0;}}
#root{{
  background:#fff;border:1px solid #e5e5e5;border-radius:16px;
  overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.07);
  max-width:780px;margin:0 auto;
}}
/* ─ ヘッダー ─ */
#hdr{{display:flex;align-items:center;gap:10px;padding:13px 16px;border-bottom:1px solid #efefef;background:#fff;}}
#logo{{width:30px;height:30px;border-radius:8px;background:#111;color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:900;font-size:14px;flex-shrink:0;}}
#title{{font-weight:700;font-size:14px;color:#111;}}
#sub{{font-size:11px;color:#aaa;margin-top:1px;}}
#reset-btn{{margin-left:auto;padding:5px 12px;border-radius:8px;border:1px solid #e5e5e5;
  background:#fff;cursor:pointer;font-size:12px;color:#666;font-family:inherit;transition:all .15s;}}
#reset-btn:hover{{border-color:#ccc;color:#333;}}
/* ─ サマリー ─ */
#summary{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:8px 14px;
  min-height:38px;background:#fafafa;border-bottom:1px solid #f0f0f0;font-size:11px;color:#bbb;}}
.chip{{display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;
  border:1px solid #e0e0e0;background:#fff;font-size:11px;color:#555;}}
#clear-btn{{margin-left:auto;padding:3px 8px;border-radius:7px;border:1px solid #e5e5e5;
  background:#fff;cursor:pointer;font-size:11px;color:#bbb;font-family:inherit;transition:all .15s;}}
#clear-btn:hover{{color:#666;border-color:#ccc;}}
/* ─ モードバー ─ */
#modebar{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:8px 14px;
  border-bottom:1px solid #f0f0f0;background:#fff;}}
#modebar-lbl{{font-size:11px;color:#bbb;}}
.mbtn{{padding:5px 13px;border-radius:999px;border:1px solid #e0e0e0;background:#fff;
  color:#666;font-size:12px;cursor:pointer;font-family:inherit;transition:all .15s;}}
.mbtn:hover{{border-color:#999;color:#333;}}
.mbtn.on{{background:#111;border-color:#111;color:#fff;}}
#play-sel{{padding:5px 10px;border-radius:999px;border:1px solid #e0e0e0;background:#fff;
  color:#666;font-size:12px;cursor:pointer;font-family:inherit;outline:none;}}
#mode-note{{font-size:11px;color:#ccc;}}
/* ─ チャット ─ */
#chat{{min-height:200px;max-height:360px;overflow-y:auto;padding:14px 14px 8px;
  background:#fff;display:flex;flex-direction:column;gap:12px;scroll-behavior:smooth;}}
#chat::-webkit-scrollbar{{width:4px;}}
#chat::-webkit-scrollbar-thumb{{background:#e8e8e8;border-radius:2px;}}
.row{{display:flex;gap:8px;align-items:flex-start;}}
.row.user{{flex-direction:row-reverse;}}
.av{{width:26px;height:26px;border-radius:7px;flex-shrink:0;margin-top:2px;
  display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;}}
.av.bot{{background:#111;color:#fff;}}
.av.user{{background:#f0f0f0;color:#555;}}
.bbl{{max-width:80%;padding:10px 13px;border-radius:14px;font-size:13px;line-height:1.55;border:1px solid #efefef;}}
.bbl.bot{{background:#fafafa;color:#222;}}
.bbl.user{{background:#111;color:#fff;border-color:#111;}}
/* ─ 女優カード ─ */
.arow{{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;}}
.acard{{width:76px;text-align:center;}}
.acard img{{width:76px;height:102px;object-fit:cover;border-radius:8px;border:2px solid #efefef;display:block;transition:border-color .15s;}}
.acard img:hover{{border-color:#111;}}
.no-img{{width:76px;height:102px;background:#f0f0f0;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:9px;color:#ccc;}}
.aname{{font-size:10px;color:#444;margin-top:4px;word-break:break-all;font-weight:700;}}
.atag{{font-size:9px;color:#bbb;line-height:1.4;}}
/* ─ 入力 ─ */
#input-zone{{padding:10px 12px 13px;border-top:1px solid #f0f0f0;background:#fff;}}
#input-wrap{{display:flex;align-items:center;gap:8px;background:#f7f7f7;
  border:1px solid #e5e5e5;border-radius:12px;padding:6px 8px 6px 12px;
  transition:border-color .2s,box-shadow .2s;}}
#input-wrap:focus-within{{border-color:#bbb;box-shadow:0 0 0 3px rgba(0,0,0,.05);background:#fff;}}
#q{{flex:1;background:transparent;border:none;outline:none;font-size:15px;color:#222;font-family:inherit;}}
#q::placeholder{{color:#bbb;}}
#go{{width:34px;height:34px;border-radius:9px;border:none;background:#111;color:#fff;
  cursor:pointer;font-size:16px;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:background .15s;}}
#go:hover{{background:#333;}}
#hint{{font-size:11px;color:#ccc;text-align:center;margin-top:6px;}}
/* ─ 結果 ─ */
#results{{padding:0 14px 14px;border-top:1px solid #f0f0f0;}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin:12px 0 4px;}}
@media(max-width:520px){{.grid{{grid-template-columns:repeat(2,1fr);}}}}
.card{{border:1px solid #efefef;border-radius:10px;overflow:hidden;background:#fff;transition:all .18s;}}
.card:hover{{border-color:#ccc;box-shadow:0 4px 14px rgba(0,0,0,.08);transform:translateY(-1px);}}
.card img{{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;}}
.no-img-card{{width:100%;aspect-ratio:3/4;background:#f5f5f5;}}
.card-link{{display:block;text-align:center;font-size:10px;color:#999;padding:5px 4px;
  text-decoration:none;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;}}
.card-link:hover{{color:#111;}}
.next-wrap{{display:flex;justify-content:center;padding:6px 0 2px;}}
.next-btn{{padding:9px 24px;border-radius:10px;border:1px solid #e0e0e0;background:#fff;
  color:#555;font-size:13px;cursor:pointer;font-family:inherit;transition:all .15s;}}
.next-btn:hover{{border-color:#111;color:#111;}}
</style>
</head>
<body>
<div id="root">

  <div id="hdr">
    <div id="logo">E</div>
    <div><div id="title">EcchiGPT</div><div id="sub">会話で探していこう</div></div>
    <button id="reset-btn" onclick="act('reset')">リセット</button>
  </div>

  <div id="summary">
    <span style="color:#bbb;font-size:11px;white-space:nowrap">条件：</span>
    {chips_html}
    {('<button id="clear-btn" onclick="act(\'clear\')">クリア</button>' if (tags or mode!="none" or pf) else "")}
  </div>

  <div id="modebar">
    <span id="modebar-lbl">絞り込み</span>
    <button class="mbtn {s_on}" onclick="act('mode','single')">単体作品</button>
    <button class="mbtn {c_on}" onclick="act('mode','collection')">総集編</button>
    <select id="play-sel" onchange="act('play',this.value)">{pf_opts}</select>
    <span id="mode-note">（未選択＝おまかせ）</span>
  </div>

  <div id="chat">{chat_inner}</div>

  <div id="input-zone">
    <div id="input-wrap">
      <input id="q" type="text" placeholder="例：黒髪 ボブ 清楚 ちょいエロ…"
        onkeydown="if(event.key==='Enter'&&!event.isComposing)submit()">
      <button id="go" onclick="submit()">↑</button>
    </div>
    <div id="hint">Enter で送信 · 条件は積み重ねられる</div>
  </div>

  {results_html}

</div>

<script>
// チャット自動スクロール
(function(){{var c=document.getElementById('chat');if(c)c.scrollTop=c.scrollHeight;}})();

// Streamlit の隠し input へ値を送る共通関数
function sendToStreamlit(inputKey, val){{
  // iframe の親ウィンドウにある Streamlit テキスト入力を探す
  var doc = window.parent.document;
  var inputs = doc.querySelectorAll('input[type="text"]');
  var target = null;
  inputs.forEach(function(inp){{
    var ph = inp.getAttribute('placeholder') || '';
    var al = inp.getAttribute('aria-label') || '';
    if(ph === inputKey || al === inputKey) target = inp;
  }});
  if(!target) return false;
  var nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');
  nativeSet.set.call(target, val);
  target.dispatchEvent(new Event('input',{{bubbles:true}}));
  return true;
}}

function triggerBtn(labelContains){{
  var doc = window.parent.document;
  var btns = doc.querySelectorAll('button');
  btns.forEach(function(b){{
    if((b.innerText||b.textContent||'').trim().includes(labelContains)) b.click();
  }});
}}

function submit(){{
  var q = document.getElementById('q').value.trim();
  if(!q) return;
  // まず input に値をセット → ボタンを押す
  if(sendToStreamlit('例：黒髪 ボブ 清楚 ちょいエロ…', q)){{
    document.getElementById('q').value='';
    setTimeout(function(){{ triggerBtn('__send__'); }}, 100);
  }}
}}

function act(action, val){{
  var v = action + (val ? ':'+val : '');
  if(sendToStreamlit('__action__', v)){{
    setTimeout(function(){{ triggerBtn('__act__'); }}, 100);
  }}
}}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────
# 送信ハンドラ
# ─────────────────────────────────────────────
def handle_send(typed):
    st.session_state["chat"].append({"role":"user","text":typed,"actress_cards":[]})
    api_key=st.session_state["openai_key"]; fanza_api=st.session_state["fanza_api_id"]
    fanza_aff=st.session_state["fanza_aff_id"]; actress_cards=[]; bot_reply="OK、探すね！"

    if api_key:
        with st.spinner("考え中…"):
            result=ai_interpret(typed,st.session_state["ai_hist"],st.session_state["tags"],api_key)
        if not result.get("error"):
            bot_reply=result.get("bot_reply","OK、探すね！")
            st.session_state["ai_hist"]+=[{"role":"user","content":typed},{"role":"assistant","content":bot_reply}]
            remove=[t.strip().lower() for t in result.get("remove_tags",[])]
            curr=[t for t in st.session_state["tags"] if t.lower() not in remove]
            new_t=[t.strip() for t in result.get("tags",[]) if t.strip()]
            sel=[t.strip() for t in result.get("selected_actresses",[]) if t.strip()]
            st.session_state["tags"]=dedup(curr+new_t+sel)
            pf=result.get("play_filter","none")
            if pf and pf!="none": st.session_state["play_filter"]=pf
            master=load_master()
            for name in result.get("selected_actresses",[]):
                v=master.get(name) or master.get(norm(name))
                if v and isinstance(v,dict):
                    actress_cards.append({"name":name,"img":v.get("img",""),"tags":v.get("tags",[])[:4]})
            unknown=[c for c in result.get("detected_celebs",[]) if norm(c) not in build_celebrity_map()]
            if unknown: bot_reply=f"ごめん、{'・'.join(unknown)}に似てる人は見つからなかった。他にいない？"
        else:
            bot_reply="OK、探すね 🔍"
            st.session_state["tags"]=dedup(st.session_state["tags"]+[norm(p) for p in typed.split() if norm(p)])
    else:
        bot_reply="OK、探すね 🔍"
        st.session_state["tags"]=dedup(st.session_state["tags"]+[norm(p) for p in typed.split() if norm(p)])

    st.session_state["last_q"]=" ".join(st.session_state["tags"])
    st.session_state["chat"].append({"role":"bot","text":bot_reply,"actress_cards":actress_cards})

    if fanza_api and fanza_aff and st.session_state["last_q"]:
        with st.spinner("検索中…"):
            res=do_search(st.session_state["last_q"],st.session_state["mode"],
                          st.session_state["play_filter"],1,fanza_api,fanza_aff)
        st.session_state.update({"results":res["items"],"has_more":res["has_more"],"page":2})
    elif not fanza_api or not fanza_aff:
        st.session_state["chat"].append({"role":"bot","actress_cards":[],
            "text":"⚠ サイドバーの「APIキー」にFANZA API IDとAffiliate IDを入力してね"})

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown("## ⚙️ 設定")
        with st.expander("🔑 APIキー",expanded=True):
            for key,label,ph in [
                ("fanza_api_id","FANZA API ID",""),
                ("fanza_aff_id","FANZA Affiliate ID",""),
                ("openai_key","OpenAI API Key",""),
            ]:
                val=st.text_input(label,value=st.session_state[key],type="password",key=f"sb_{key}")
                st.session_state[key]=val
        st.divider()
        with st.expander("📁 JSONファイル",expanded=True):
            for path,label in [(MASTER_JSON_PATH,"Actress Master"),(CLUSTER_JSON_PATH,"Cluster")]:
                if path.exists(): st.success(f"✅ {label} ({path.stat().st_size//1024} KB)")
                else: st.warning(f"⚠ {label} — サンプル動作中")
            up=st.file_uploader("JSONをアップロード",type="json",key="up_json")
            if up:
                try:
                    data=json.loads(up.read().decode("utf-8-sig"))
                    if not isinstance(data,dict): st.error("dict形式が必要")
                    else:
                        dest=MASTER_JSON_PATH if "master" in up.name.lower() else CLUSTER_JSON_PATH
                        dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
                        st.cache_data.clear(); st.success(f"{dest.name} 保存（{len(data)}件）"); st.rerun()
                except Exception as e: st.error(f"エラー: {e}")
            c1,c2=st.columns(2)
            with c1: st.download_button("Master↓",data=json.dumps(load_master(),ensure_ascii=False,indent=2),file_name="favo_actress_master.json",mime="application/json",use_container_width=True)
            with c2: st.download_button("Cluster↓",data=json.dumps(load_cluster(),ensure_ascii=False,indent=2),file_name="favo_fanza_cluster.json",mime="application/json",use_container_width=True)
        with st.expander("➕ 女優を追加"):
            nn=st.text_input("女優名",key="add_name"); nt=st.text_input("タグ（カンマ）",key="add_tags"); nc=st.text_input("芸能人（カンマ）",key="add_celebs")
            if st.button("追加",use_container_width=True,key="btn_add"):
                if nn.strip():
                    master=load_master().copy()
                    master[nn.strip()]={"tags":[t.strip() for t in nt.split(",") if t.strip()],"keywords":[],"celebs":[c.strip() for c in nc.split(",") if c.strip()],"img":""}
                    MASTER_JSON_PATH.write_text(json.dumps(master,ensure_ascii=False,indent=2),encoding="utf-8")
                    st.cache_data.clear(); st.success(f"追加: {nn}"); st.rerun()

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    sidebar()

    # 隠し入力（Streamlit側で値を受け取る）
    send_val = st.text_input("send","",placeholder="例：黒髪 ボブ 清楚 ちょいエロ…",key="hidden_send",label_visibility="collapsed")
    send_btn = st.button("__send__",key="btn_send_hidden")

    act_val  = st.text_input("act","",placeholder="__action__",key="hidden_act",label_visibility="collapsed")
    act_btn  = st.button("__act__",key="btn_act_hidden")

    # アクション処理
    if act_btn and act_val.strip():
        parts=act_val.split(":",1); action=parts[0]; val=parts[1] if len(parts)>1 else ""
        if action=="reset":
            for k,v in _DEFAULTS.items(): st.session_state[k]=v
        elif action=="clear":
            st.session_state.update({"tags":[],"last_q":"","results":[],"page":1,"mode":"none","play_filter":""})
        elif action=="mode":
            st.session_state["mode"]="none" if st.session_state["mode"]==val else val
        elif action=="play":
            st.session_state["play_filter"]=val
        elif action=="next":
            api=st.session_state["fanza_api_id"]; aff=st.session_state["fanza_aff_id"]
            if api and aff:
                with st.spinner("読み込み中…"):
                    res=do_search(st.session_state["last_q"],st.session_state["mode"],
                                  st.session_state["play_filter"],st.session_state["page"],api,aff)
                st.session_state["results"]+=res["items"]
                st.session_state["has_more"]=res["has_more"]
                st.session_state["page"]+=1
        st.rerun()

    # 送信処理
    if send_btn and send_val.strip():
        handle_send(send_val.strip())
        st.rerun()

    # HTML UI 出力（Streamlit要素より後に描画）
    st.components.v1.html(build_ui_html(), height=900, scrolling=True)


if __name__ == "__main__":
    main()
