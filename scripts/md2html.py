#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc-to-html 核心转换器：Markdown → 美观、可离线双击打开的单文件 HTML。

特性：
  - 侧栏目录（h2/h3，滚动高亮；h2 分组可折叠、整栏可收起）+ 回到顶部 + 打印样式
  - 分节楼层配色：各 h2 章节循环套用 8 色楼层色，标题带楼层号徽标，侧栏目录联动标色
  - 表格自动加横向滚动圆角容器；SQL/JSON/JS/Python/Bash 轻量语法高亮
  - 本地图片默认 base64 内嵌（--link-images 可关闭），外链图片原样保留
  - 文档头部的长元信息/修订记录 blockquote 自动折叠
  - Mermaid 代码块以源码形式保留（离线可用），如需图形化请由 agent 手绘 HTML/CSS 替换
  - 依赖（markdown / pymdown-extensions）首次运行自动装载到 scripts/_vendor，不污染系统环境

用法：
  python3 md2html.py INPUT.md [-o OUTPUT.html] [--title T] [--subtitle S]
                     [--accent "#4f46e5"] [--link-images] [--assets-base DIR]
                     [--cleanup PATH ...]
  支持多个输入文件，按顺序合并（以 <hr> 分隔）。
  清理中间产物：转换命令末尾加 --cleanup，或自检后单独执行
  `python3 md2html.py --cleanup assembled.md extracts/`（不转新文档）。
"""

import argparse
import base64
import datetime
import html
import pathlib
import re
import shutil
import subprocess
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
VENDOR_DIR = pathlib.Path(__file__).resolve().parent / "_vendor"
MERMAID_RE = re.compile(r'<pre><code class="language-mermaid">.*?</code></pre>', re.S)
IMG_RE = re.compile(r'<img src="([^"]+)"([^>]*)/?>')
HEADING_RE = re.compile(r"<h([23])>(.*?)</h[23]>", re.S)
FLOOR_COLORS = 8  # 楼层配色循环周期，与 CSS 中 --f1..--f8 一一对应


# ---------------------------------------------------------------- 依赖装载
def ensure_deps() -> list[str]:
    """返回可用的 markdown 扩展列表；缺依赖时装进 _vendor，失败则优雅降级。"""
    if str(VENDOR_DIR) not in sys.path and VENDOR_DIR.exists():
        sys.path.insert(0, str(VENDOR_DIR))
    try:
        import markdown  # noqa: F401
    except ImportError:
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--target", str(VENDOR_DIR),
                 "--quiet", "--disable-pip-version-check", "markdown", "pymdown-extensions"],
                check=True,
            )
            if str(VENDOR_DIR) not in sys.path:
                sys.path.insert(0, str(VENDOR_DIR))
        except subprocess.CalledProcessError:
            print("[doc-to-html] 警告：依赖安装失败，降级为基础渲染（表格/代码块可用，删除线不可用）", file=sys.stderr)
    exts = ["tables", "fenced_code"]
    try:
        import markdown  # noqa: F401
        import pymdownx  # noqa: F401
        exts.append("pymdownx.tilde")
    except ImportError:
        print("[doc-to-html] 提示：未检测到 pymdownx，~~删除线~~ 将保持原样", file=sys.stderr)
    return exts


def md_to_body(text: str, exts: list[str]) -> str:
    import markdown
    return markdown.Markdown(extensions=exts).convert(text)


# ---------------------------------------------------------------- 后处理
def fold_docmeta(body: str) -> str:
    """文档紧随标题的长元信息/修订 blockquote（>600 字符）折叠进 <details>。"""
    i = body.find("<blockquote>")
    if i < 0:
        return body
    j = body.find("</blockquote>", i)
    if j < 0:
        return body
    j += len("</blockquote>")
    if j - i < 600:
        return body
    rev = body[i:j]
    summary = "文档信息 / 修订记录（点击展开）"
    return body[:i] + (
        f'<details class="docmeta"><summary>{summary} <span>展开 / 收起</span></summary>{rev}</details>'
    ) + body[j:]


def mark_mermaid(body: str) -> str:
    return MERMAID_RE.sub(
        lambda m: m.group(0).replace('<pre><code class="language-mermaid">',
                                     '<pre class="mermaid-src"><code class="language-mermaid">'),
        body,
    )


def assign_heading_ids(body: str) -> tuple[str, list[tuple[int, str, str, int]]]:
    """给 h2/h3 分配 sec-N 锚点与楼层配色类，返回 (body, [(level, id, label, floor), ...])。

    floor 是该标题所属 h2 楼层的序号（从 1 起）；h2 自身即开启新楼层。
    配色类 fl-N 按 FLOOR_COLORS 循环，楼层号徽标用真实序号。
    """
    entries: list[tuple[int, str, str, int]] = []
    counter = {"n": 0}
    floor = {"n": 0}

    def repl(m: re.Match) -> str:
        level = int(m.group(1))
        inner = m.group(2)
        label = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        if level == 2:
            floor["n"] += 1
        seq = floor["n"] or 1
        f = (seq - 1) % FLOOR_COLORS + 1
        sid = f"sec-{counter['n']}"
        counter["n"] += 1
        entries.append((level, sid, label, f))
        badge = f'<span class="fl-badge">{seq:02d}</span>' if level == 2 else ""
        return f'<h{level} id="{sid}" class="fl-{f}">{badge}{inner}</h{level}>'

    return HEADING_RE.sub(repl, body), entries


def _toc_link(cls: str, sid: str, label: str) -> str:
    shown = label if len(label) <= 28 else label[:28] + "…"
    return f'<a class="{cls}" href="#{sid}" data-target="{sid}"><span class="lbl">{html.escape(shown)}</span></a>'


def build_toc(entries: list[tuple[int, str, str, int]]) -> tuple[str, str]:
    """生成侧栏目录与底部工具条。h2 为可折叠分组（含折叠箭头），h3 收进组内。

    返回 (toc_html, sidefoot_html)；没有任何 h3 分组时工具条为空串。
    """
    groups: list[tuple[tuple[int, str, str, int] | None, list[tuple[int, str, str, int]]]] = []
    for e in entries:
        if e[0] == 2:
            groups.append((e, []))
        elif groups:
            groups[-1][1].append(e)
        else:
            groups.append((None, [e]))

    parts = ['<nav id="toc" aria-label="目录">']
    has_subs = False
    for head, subs in groups:
        if head is None:
            for _, sid, label, _f in subs:
                parts.append(_toc_link("l3", sid, label))
            continue
        _, sid, label, f = head
        car = '<span class="car" title="折叠 / 展开">▾</span>' if subs else ""
        parts.append('<div class="tgroup">')
        parts.append(f'<a class="l2 fl-{f}" href="#{sid}" data-target="{sid}">'
                     f'<span class="lbl">{html.escape(label if len(label) <= 28 else label[:28] + "…")}</span>{car}</a>')
        if subs:
            has_subs = True
            parts.append('<div class="tsub">')
            for _, s3, l3, f3 in subs:
                parts.append(_toc_link(f"l3 fl-{f3}", s3, l3))
            parts.append("</div>")
        parts.append("</div>")
    parts.append("</nav>")
    foot = ('<div class="side-foot"><button id="texp" type="button">全部展开</button>'
            '<button id="tcol" type="button">全部收起</button></div>') if has_subs else ""
    return "".join(parts), foot


def embed_images(body: str, base_dir: pathlib.Path, embed: bool) -> str:
    """本地图片转 base64 data URI；外链保留；缺失图片打上 missing 标记。"""
    def repl(m: re.Match) -> str:
        src, tail = m.group(1), m.group(2)
        if src.startswith(("http://", "https://", "data:")) or not embed:
            return m.group(0)
        p = (base_dir / src) if not pathlib.Path(src).is_absolute() else pathlib.Path(src)
        p = p.resolve()
        if not p.is_file():
            return f'<img src="{src}" class="img-missing" alt="[图片缺失: {src}]"' + tail + ">"
        mime = "image/svg+xml" if p.suffix.lower() == ".svg" else (
            "image/png" if p.suffix.lower() == ".png" else
            "image/gif" if p.suffix.lower() == ".gif" else
            "image/webp" if p.suffix.lower() == ".webp" else "image/jpeg")
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        extra = "" if "alt=" in tail else ' alt=""'
        return f'<img src="data:{mime};base64,{data}" loading="lazy" decoding="async"{extra}' + tail + ">"
    return IMG_RE.sub(repl, body)


def build_chips(sources: list[str], raw_text: str) -> str:
    n_chars = len(re.sub(r"\s", "", raw_text))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    chips = [f'<span class="chip hot">doc-to-html</span>',
             f'<span class="chip">生成于 {now}</span>']
    if len(sources) == 1:
        chips.append(f'<span class="chip">来源 {html.escape(pathlib.Path(sources[0]).name)}</span>')
    else:
        chips.append(f'<span class="chip">来源 {len(sources)} 个文件</span>')
    chips.append(f'<span class="chip">约 {n_chars:,} 字</span>')
    return '<div class="hero-meta">' + "".join(chips) + "</div>"


# ---------------------------------------------------------------- 模板
CSS = """
:root{--ink:#21252d;--muted:#6d7380;--accent:__ACCENT__;--accent2:#8b5cf6;--soft:#eef0fe;--line:#e7e9f2;--bg:#f6f7fa;--code:#4a44c6;--f1:#4f46e5;--f2:#0f766e;--f3:#c2410c;--f4:#be185d;--f5:#0369a1;--f6:#7c3aed;--f7:#4d7c0f;--f8:#b45309}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.85 -apple-system,BlinkMacSystemFont,"SF Pro SC","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
::selection{background:#dfe3ff}
.sidebar{position:fixed;top:0;left:0;bottom:0;width:272px;background:#fcfcfe;border-right:1px solid var(--line);display:flex;flex-direction:column;z-index:10;transition:transform .28s ease}
.side-head{padding:22px 22px 16px;border-bottom:1px solid var(--line)}
.side-head .row{display:flex;align-items:center;gap:10px}
.logo{flex:0 0 auto;width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px}
.side-head b{font-size:14.5px;line-height:1.4;display:block}
.side-head small{color:var(--muted);font-size:12px;display:block;margin-top:2px}
#toc{flex:1;overflow:auto;padding:14px 12px 24px}
#toc a{display:block;text-decoration:none;border:0;color:#4b5058;font-size:13px;padding:5px 12px;border-radius:8px;line-height:1.5;margin:1px 0}
#toc a.l2{display:flex;align-items:center}
#toc a.l2 .lbl{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#toc a.l3{display:flex;align-items:center;padding-left:15px}
#toc a.l3 .lbl{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#toc a.l3::before{content:'';flex:0 0 auto;width:5px;height:5px;border-radius:50%;background:var(--accent);margin-right:7px}
#toc a.l2.fl-1{color:var(--f1)}#toc a.l2.fl-2{color:var(--f2)}#toc a.l2.fl-3{color:var(--f3)}#toc a.l2.fl-4{color:var(--f4)}#toc a.l2.fl-5{color:var(--f5)}#toc a.l2.fl-6{color:var(--f6)}#toc a.l2.fl-7{color:var(--f7)}#toc a.l2.fl-8{color:var(--f8)}
#toc a.l3.fl-1::before{background:var(--f1)}#toc a.l3.fl-2::before{background:var(--f2)}#toc a.l3.fl-3::before{background:var(--f3)}#toc a.l3.fl-4::before{background:var(--f4)}#toc a.l3.fl-5::before{background:var(--f5)}#toc a.l3.fl-6::before{background:var(--f6)}#toc a.l3.fl-7::before{background:var(--f7)}#toc a.l3.fl-8::before{background:var(--f8)}
.tgroup .car{flex:0 0 auto;width:20px;height:20px;margin:0 -7px 0 7px;display:flex;align-items:center;justify-content:center;border-radius:6px;font-size:9px;color:#9aa0b5;cursor:pointer;transition:transform .18s,background .18s;user-select:none}
.tgroup .car:hover{background:#e8eaf4;color:var(--ink)}
.tgroup.closed>.tsub{display:none}
.tgroup.closed .car{transform:rotate(-90deg)}
#toc a:hover{background:#f1f2f9;color:var(--ink)}
#toc a.active{background:var(--soft);color:var(--accent);font-weight:600}
.side-foot{padding:10px 12px;border-top:1px solid var(--line);display:flex;gap:8px}
.side-foot button{flex:1;border:1px solid var(--line);background:#fff;color:#5a6070;font-size:12px;line-height:1;padding:7px 0 8px;border-radius:8px;cursor:pointer;transition:color .15s,border-color .15s,background .15s}
.side-foot button:hover{color:var(--accent);border-color:#c9cffb;background:#f6f7ff}
.main{margin-left:272px;transition:margin-left .28s ease}
#side-toggle{position:fixed;top:26px;left:272px;margin-left:-14px;z-index:30;width:28px;height:28px;border-radius:50%;border:1px solid var(--line);background:#fff;color:#7c8291;font-size:15px;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(30,35,90,.15);transition:left .28s ease}
#side-toggle:hover{color:var(--accent);border-color:#c9cffb}
body.side-hidden .sidebar{transform:translateX(-102%)}
body.side-hidden .main{margin-left:0}
body.side-hidden #side-toggle{left:18px;margin-left:0}
.wrap{max-width:940px;margin:0 auto;padding:52px 60px 90px}
h1{font-size:29px;line-height:1.4;margin:6px 0 18px;font-weight:700;letter-spacing:.2px}
h1::after{content:'';display:block;width:64px;height:4px;border-radius:2px;margin-top:16px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.hero-meta{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 8px}
.chip{background:#fff;border:1px solid var(--line);color:#4b5058;font-size:12.5px;padding:4px 13px;border-radius:999px}
.chip.hot{background:var(--soft);border-color:#dcdffb;color:var(--accent);font-weight:700}
h2{font-size:21.5px;margin:58px 0 18px;padding-bottom:12px;border-bottom:1px solid var(--line);position:relative;scroll-margin-top:24px;line-height:1.5}
h2::before{content:'';position:absolute;left:0;bottom:-2px;width:30px;height:3px;border-radius:2px;background:currentColor}
h3{font-size:17.5px;margin:38px 0 14px;scroll-margin-top:24px;display:flex;align-items:baseline;gap:9px}
h3::before{content:'';flex:0 0 auto;width:7px;height:7px;border-radius:2px;background:currentColor;transform:rotate(45deg) translateY(-1px)}
h2.fl-1{color:var(--f1)}h2.fl-2{color:var(--f2)}h2.fl-3{color:var(--f3)}h2.fl-4{color:var(--f4)}h2.fl-5{color:var(--f5)}h2.fl-6{color:var(--f6)}h2.fl-7{color:var(--f7)}h2.fl-8{color:var(--f8)}
h3.fl-1{color:var(--f1)}h3.fl-2{color:var(--f2)}h3.fl-3{color:var(--f3)}h3.fl-4{color:var(--f4)}h3.fl-5{color:var(--f5)}h3.fl-6{color:var(--f6)}h3.fl-7{color:var(--f7)}h3.fl-8{color:var(--f8)}
.fl-badge{display:inline-block;min-width:20px;height:20px;margin-right:10px;padding:0 6px;border:1.5px solid currentColor;border-radius:6px;font-size:12px;font-weight:700;line-height:17px;text-align:center;vertical-align:3px;letter-spacing:.5px;opacity:.9}
p{margin:12px 0}
li{margin:6px 0}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid #d8dcfa}
a:hover{border-bottom-color:var(--accent)}
strong{color:#14171d}
hr{border:0;border-top:1px solid var(--line);margin:44px 0}
blockquote{margin:18px 0;padding:12px 20px;background:#f8f9ff;border-left:3px solid #bcc3f8;border-radius:0 10px 10px 0;color:#3a3f4a;font-size:14px}
blockquote p{margin:9px 0}
blockquote blockquote{background:transparent;border-left-color:#dfe2fa;margin:10px 0}
details.docmeta{margin:24px 0;border:1px solid var(--line);border-radius:14px;background:#fff;overflow:hidden}
details.docmeta summary{cursor:pointer;list-style:none;padding:14px 20px;font-weight:600;font-size:14.5px;color:var(--accent);background:#fbfbff;display:flex;align-items:center;gap:8px}
details.docmeta summary::-webkit-details-marker{display:none}
details.docmeta summary::before{content:'▸';transition:.2s;display:inline-block}
details.docmeta[open] summary::before{transform:rotate(90deg)}
details.docmeta summary span{margin-left:auto;font-size:12px;color:#9aa0b5;font-weight:400}
details.docmeta blockquote{margin:14px 16px;background:transparent;border-left:2px solid #e2e5f9;padding:4px 16px}
code{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:.86em;background:#f2f3f9;color:var(--code);padding:2px 6px;border-radius:5px;overflow-wrap:anywhere}
pre{background:#fafbfe;border:1px solid var(--line);border-radius:12px;padding:15px 18px;overflow:auto;line-height:1.7}
pre code{background:none;padding:0;color:#333a45;font-size:12.5px}
pre code .tok-kw{color:#7c3aed;font-weight:600}
pre code .tok-str{color:#0e7a4e}
pre code .tok-com{color:#9aa1af;font-style:italic}
pre.mermaid-src{border-style:dashed;background:#fcfcff}
pre.mermaid-src code{color:#5a5f8a}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:#fff;margin:18px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px;line-height:1.7}
th{background:#f4f5fa;font-weight:600;color:#333a45;text-align:left;font-size:12.8px;white-space:nowrap}
th,td{padding:9px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
tbody tr:hover{background:#fafbff}
td code,th code{font-size:.88em}
img{max-width:100%;border-radius:10px;border:1px solid var(--line)}
img.img-missing{opacity:.55;border-style:dashed;padding:14px}
figure{margin:22px 0}
figcaption{color:#9aa0b5;font-size:12.5px;text-align:center;margin-top:8px}
#totop{position:fixed;right:26px;bottom:26px;width:42px;height:42px;border-radius:50%;border:1px solid var(--line);background:#fff;color:var(--accent);font-size:18px;cursor:pointer;box-shadow:0 4px 14px rgba(30,35,90,.12);opacity:0;pointer-events:none;transition:.25s;z-index:20}
#totop.show{opacity:1;pointer-events:auto}
.foot{margin-top:70px;padding-top:18px;border-top:1px solid var(--line);color:#9aa0b5;font-size:12.5px;text-align:center}
@media print{.sidebar,#side-toggle,#totop{display:none}.main{margin-left:0}.wrap{max-width:100%;padding:0}.tw,pre{overflow:visible}body{background:#fff}h2{break-after:avoid}tr,pre{break-inside:avoid}details.docmeta{display:block}details.docmeta[open] summary{display:none}}
@media (max-width:1020px){.sidebar{position:static;width:auto;height:auto;border-right:0;border-bottom:1px solid var(--line);transform:none}#side-toggle{display:none}#toc{display:none}.main{margin-left:0;transition:none}.wrap{padding:34px 22px 60px}body.side-hidden .sidebar{transform:none}body.side-hidden .main{margin-left:0}}
"""

JS = r"""
(function(){
 var heads=[].slice.call(document.querySelectorAll('.content h2,.content h3'));
 var links=[].slice.call(document.querySelectorAll('#toc a'));
 var totop=document.getElementById('totop');
 var toc=document.getElementById('toc');
 var sideToggle=document.getElementById('side-toggle');
 var groups=[].slice.call(document.querySelectorAll('#toc .tgroup'));
 function setSide(hidden){
  document.body.classList.toggle('side-hidden',hidden);
  if(sideToggle){var h=document.body.classList.contains('side-hidden');
   sideToggle.textContent=h?'›':'‹';
   sideToggle.title=h?'展开侧栏':'收起侧栏';}}
 if(sideToggle)sideToggle.addEventListener('click',function(){
  setSide(!document.body.classList.contains('side-hidden'));});
 groups.forEach(function(g){
  var car=g.querySelector('.car');if(!car)return;
  car.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();g.classList.toggle('closed');});});
 var bE=document.getElementById('texp'),bC=document.getElementById('tcol');
 if(bE)bE.addEventListener('click',function(){groups.forEach(function(g){g.classList.remove('closed');});});
 if(bC)bC.addEventListener('click',function(){groups.forEach(function(g){g.classList.add('closed');});});
 function spy(){var y=window.scrollY+150,cur=links.length?0:-1,act=null;
  heads.forEach(function(h,i){if(h.offsetTop<=y)cur=i;});
  links.forEach(function(a){
   var on=!!(heads[cur]&&a.getAttribute('data-target')===heads[cur].id);
   a.classList.toggle('active',on);if(on)act=a;});
  totop.classList.toggle('show',window.scrollY>600);
  if(act&&toc){var g=act.closest?act.closest('.tgroup'):null;
   if(g)g.classList.remove('closed');
   var tb=toc.getBoundingClientRect(),ab=act.getBoundingClientRect(),rel=ab.top-tb.top;
   if(rel<0||rel>tb.height-46)toc.scrollTop+=rel-tb.height/2+20;}}
 addEventListener('scroll',spy,{passive:true});spy();
 document.querySelectorAll('.content table').forEach(function(t){
  var w=document.createElement('div');w.className='tw';
  t.parentNode.insertBefore(w,t);w.appendChild(t);});
 var LANG_COMMENTS={sql:'--',python:'#',bash:'#',sh:'#',yaml:'#',yml:'#',toml:'#',
  js:'//',javascript:'//',ts:'//',typescript:'//',java:'//',c:'//',cpp:'//',go:'//',rust:'//',json:null,mermaid:null};
 var LANG_KW={
  sql:'CREATE|TABLE|PRIMARY|KEY|UNIQUE|NOT|NULL|DEFAULT|CURRENT_TIMESTAMP|ENGINE|CHARSET|COMMENT|AUTO_INCREMENT|BIGINT|INT|TINYINT|VARCHAR|DATETIME|TIMESTAMP|SELECT|FROM|WHERE|LEFT|RIGHT|INNER|OUTER|JOIN|AND|OR|IS|GROUP|BY|ORDER|INSERT|INTO|VALUES|SET|EXISTS|CASE|WHEN|THEN|ELSE|END|AS|COUNT|SUM|MAX|MIN|DELETE|UPDATE|IFNULL|DISTINCT|LIMIT|ON|IN|DESC|ASC|LIKE|BETWEEN|HAVING|ALTER|DROP|REPLACE|VIEW|INDEX',
  python:'def|class|return|if|elif|else|for|while|import|from|as|with|try|except|finally|raise|lambda|None|True|False|and|or|not|in|is|pass|break|continue|global|yield|async|await',
  bash:'if|then|else|fi|for|while|do|done|case|esac|function|echo|export|local|return|cd|ls|grep|awk|sed|curl|set|source|sudo|npm|pip|git',
  js:'function|return|if|else|for|while|var|let|const|class|extends|new|this|typeof|instanceof|null|undefined|true|false|try|catch|finally|throw|switch|case|break|continue|import|export|from|default|async|await|yield',
  java:'public|private|protected|static|final|void|int|long|boolean|String|class|interface|extends|implements|new|return|if|else|for|while|try|catch|finally|throw|throws|this|super|null|true|false|import|package'};
 LANG_KW.ts=LANG_KW.js;LANG_KW.typescript=LANG_KW.js;LANG_KW.javascript=LANG_KW.js;
 function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
 document.querySelectorAll('pre code').forEach(function(el){
  var cls=el.className||'';var m=cls.match(/language-([a-zA-Z0-9_+-]+)/);
  var lang=m?m[1].toLowerCase():'';
  if(lang==='mermaid')return;
  var t=el.textContent,out='',last=0,mm;
  var parts=[];
  var com=LANG_COMMENTS[lang];
  if(com==='--')parts.push('(-{2,}[^\\n]*)');
  else if(com==='#')parts.push('(#[^\\n]*)');
  else if(com==='//')parts.push('(//[^\\n]*)','(/\\*[\\s\\S]*?\\*/)');
  else if(com===null&&lang==='json')parts.push('("(?:[^"\\\\]|\\\\.)*")(\\s*:)?');
  var str="('(?:[^'\\\\\\n]|\\\\.)*'|\"(?:[^\"\\\\\\n]|\\\\.)*\"|`(?:[^`\\\\]|\\\\.)*`)";
  parts.push(str);
  var kws=LANG_KW[lang];
  if(kws)parts.push('\\b('+kws+')\\b');
  if(!parts.length)return;
  var re=new RegExp(parts.join('|'),'g');
  while((mm=re.exec(t))){
   out+=esc(t.slice(last,mm.index));
   var seg=esc(mm[0]);
   if(mm[1]||mm[2]&&lang==='json')out+='<span class="tok-com">'+seg+'</span>';
   else if(mm[0][0]==="'"||mm[0][0]==='"'||mm[0][0]==='`')out+='<span class="tok-str">'+seg+'</span>';
   else out+='<span class="tok-kw">'+seg+'</span>';
   last=mm.index+mm[0].length;}
  out+=esc(t.slice(last));el.innerHTML=out;});
 totop.addEventListener('click',function(){scrollTo({top:0,behavior:'smooth'});});
})();
"""

HTML_SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<nav class="sidebar">
  <div class="side-head">
    <div class="row">
      <span class="logo">文</span>
      <span><b>__TITLE__</b><small>__SUBTITLE__</small></span>
    </div>
  </div>
  __TOC__
  __SIDEFOOT__
</nav>
<button id="side-toggle" title="收起侧栏" aria-label="收起 / 展开侧栏">‹</button>
<main class="main"><div class="wrap"><article class="content">
__CHIPS__
__BODY__
<div class="foot">__FOOTER__</div>
</article></div></main>
<button id="totop" title="回到顶部">↑</button>
<script>__JS__</script>
</body>
</html>
"""


def cleanup_paths(paths: list[str], protected: set[pathlib.Path]) -> tuple[list[str], list[tuple[str, str]]]:
    """删除中间产物（文件或目录，目录整删）；不存在或 HTML 产物一律跳过，绝不误删最终产物。"""
    removed, skipped = [], []
    for raw in paths:
        p = pathlib.Path(raw).expanduser()
        if not p.exists():
            skipped.append((str(p), "不存在"))
            continue
        if p.suffix.lower() in {".html", ".htm"} or p.resolve() in protected:
            skipped.append((str(p), "HTML 产物受保护"))
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        removed.append(str(p))
    return removed, skipped


def convert(inputs: list[str], args) -> pathlib.Path:
    exts = ensure_deps()
    parts, sources = [], []
    for f in inputs:
        p = pathlib.Path(f).expanduser()
        if not p.is_file():
            sys.exit(f"[doc-to-html] 输入文件不存在: {p}")
        text = p.read_text(encoding="utf-8-sig")
        parts.append(text)
        sources.append(str(p))
    raw = "\n\n---\n\n".join(parts)

    body = md_to_body(raw, exts)
    body = fold_docmeta(body)
    body = mark_mermaid(body)
    body, toc_entries = assign_heading_ids(body)

    assets_base = pathlib.Path(args.assets_base).expanduser() if args.assets_base else pathlib.Path(inputs[0]).expanduser().resolve().parent
    body = embed_images(body, assets_base, embed=not args.link_images)

    m1 = re.search(r"<h1>(.*?)</h1>", body)
    default_title = html.unescape(re.sub(r"<[^>]+>", "", m1.group(1))).strip() if m1 else pathlib.Path(inputs[0]).stem
    title = args.title or default_title
    subtitle = args.subtitle or "本地文档 · 离线可读"
    toc, sidefoot = build_toc(toc_entries)
    chips = build_chips(sources, raw)
    footer = f"由 doc-to-html · md2html.py 生成 · {datetime.date.today().isoformat()}"

    page = (HTML_SHELL
            .replace("__TITLE__", html.escape(title))
            .replace("__SUBTITLE__", html.escape(subtitle))
            .replace("__ACCENT__", args.accent)
            .replace("__CSS__", CSS)
            .replace("__TOC__", toc)
            .replace("__SIDEFOOT__", sidefoot)
            .replace("__CHIPS__", chips)
            .replace("__BODY__", body)
            .replace("__FOOTER__", html.escape(footer))
            .replace("__JS__", JS))

    out = pathlib.Path(args.output).expanduser() if args.output else pathlib.Path(inputs[0]).with_suffix(".html")
    out.write_text(page, encoding="utf-8")
    print(f"[doc-to-html] 已生成: {out}  ({out.stat().st_size/1024:.0f} KB, 目录条目 {len(toc_entries)})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Markdown → 美观的单文件离线 HTML")
    ap.add_argument("inputs", nargs="*", help="输入 .md 文件（可多个，按顺序合并；仅清理中间产物时可省略）")
    ap.add_argument("-o", "--output", help="输出 HTML 路径（默认与输入同名的 .html）")
    ap.add_argument("--title", help="页面标题（默认取第一个 h1 或文件名）")
    ap.add_argument("--subtitle", help="侧栏副标题")
    ap.add_argument("--accent", default="#4f46e5", help="主题色（默认靛蓝 #4f46e5）")
    ap.add_argument("--assets-base", help="相对图片路径的基准目录（默认第一个输入文件所在目录）")
    ap.add_argument("--link-images", action="store_true", help="不内嵌图片，保留相对链接")
    ap.add_argument("--cleanup", nargs="+", metavar="PATH",
                    help="删除指定的中间产物（文件或目录，空格分隔）；可附在转换命令末尾，或单独执行只做清理")
    args = ap.parse_args()
    if not args.inputs and not args.cleanup:
        ap.error("至少提供输入文件，或用 --cleanup 指定要清理的中间产物")
    out = convert(args.inputs, args) if args.inputs else None
    if args.cleanup:
        protected = {out.resolve()} if out else set()
        removed, skipped = cleanup_paths(args.cleanup, protected)
        for p in removed:
            print(f"[doc-to-html] 已删除中间产物: {p}")
        for p, why in skipped:
            print(f"[doc-to-html] 跳过: {p}（{why}）")
        print(f"[doc-to-html] 清理完成：删除 {len(removed)} 项，跳过 {len(skipped)} 项")


if __name__ == "__main__":
    main()
