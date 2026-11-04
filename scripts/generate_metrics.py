#!/usr/bin/env python3
"""Build GitHub stats SVGs from public API data. Python stdlib only.

GitHub Actions sets GITHUB_TOKEN. The token is used in memory only and is never
written into SVGs, logs or repository files. --demo is for PREVIEW only; it
writes visually watermarked sample graphics to a different output folder.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import math
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

W, BG, BORDER, FG, MUTED, COPPER = 1100, '#11151B', '#35414D', '#FAF6F0', '#AAB5C1', '#D49A78'
PALETTE = ['#C87A53', '#8AAEA7', '#D2B184', '#A48DBA', '#8399BD', '#697680']
LANG_NAME = {'Jupyter Notebook': 'Jupyter', 'TypeScript': 'TypeScript', 'JavaScript':'JavaScript'}

def esc(s):
    return escape(str(s), quote=True)

def base(height):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}"><rect width="{W}" height="{height}" rx="16" fill="{BG}"/><rect x="1" y="1" width="1098" height="{height-2}" rx="15" fill="none" stroke="{BORDER}"/>'''

def end():return '</svg>'

def label(x,y,t, size=14, fill=MUTED, weight=400):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}">{esc(t)}</text>'

def bg_card(x,y,w,h):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#191F28" stroke="#37424E"/>'

def tag(x,y,text):
    return f'<rect x="{x}" y="{y}" width="120" height="24" rx="7" fill="#30231F"/>'+label(x+12,y+17,text,12,COPPER,700)

def svg_stats(d, demo=False):
    s=base(224)+label(38,42,'GITHUB / PUBLIC SNAPSHOT',16,COPPER,700)+label(869,41,'IXM  ·  GITHUB',12,MUTED,700)
    fields=[('PUBLIC REPOSITORIES',d.get('repos','—')),('REPOSITORY STARS',d.get('stars','—')),('FOLLOWERS',d.get('followers','—')),('CONTRIBUTIONS / YEAR',d.get('contrib','—'))]
    for i,(name,v) in enumerate(fields):
        x=22+i*273
        s+=bg_card(x,70,257,128)
        s+=label(x+22,107,name,13,MUTED,700)
        s+=label(x+22,162,v,41,FG,700)
        s+=f'<path d="M{x+22} 179 H{x+94}" stroke="{PALETTE[i%len(PALETTE)]}" stroke-width="4" stroke-linecap="round"/>'
    if demo:s+=label(800,218,'DESIGN PREVIEW · SAMPLE COUNTS',11,'#E6A58C',700)
    return s+end()

def svg_languages(counts, demo=False):
    s=base(268)+label(38,44,'TOP LANGUAGES · PRIMARY LANGUAGE PER REPOSITORY',16,COPPER,700)
    s+=label(39,70,'Measured from public repository metadata — not lines of code',12,MUTED)
    top=list(counts.most_common(6))
    if not top:
        s+=label(38,135,'No public repository languages detected yet.',25,FG)
        return s+end()
    total=sum(counts.values()); mx=max(counts.values()); y=97
    for idx,(name,val) in enumerate(top):
        x=39+(idx//3)*534; y=103+(idx%3)*48
        pct=round(100*val/total)
        s+=label(x,y,LANG_NAME.get(name,name),16,FG,600)+label(x+441,y,f'{val} repo'+('s' if val!=1 else '')+f' · {pct}%',13,MUTED,400)
        s+=f'<rect x="{x}" y="{y+11}" width="482" height="10" rx="5" fill="#29313B"/>'
        s+=f'<rect x="{x}" y="{y+11}" width="{max(8,round(482*val/mx))}" height="10" rx="5" fill="{PALETTE[idx]}"/>'
    if demo:s+=label(857,262,'SAMPLE DATA',11,'#E6A58C',700)
    return s+end()

def svg_activity(weeks, demo=False):
    s=base(295)+label(38,43,'CONTRIBUTION ACTIVITY  ·  52 WEEKS',16,COPPER,700)
    s+=label(38,66,'Public GitHub contribution calendar · weekly totals',12,MUTED)
    if not weeks:
        s+=label(38,154,'Contribution data unavailable — try the workflow again.',24,FG)
        return s+end()
    vals=[sum(int(day.get('contributionCount',0)) for day in wk.get('contributionDays',[])) for wk in weeks][-52:]
    if not vals: vals=[0]
    m=max(max(vals),1); left=47; right=1045; top=103; bottom=245
    for k in range(4):
        yy=top+k*(bottom-top)/3
        s+=f'<path d="M{left} {yy:.1f} H{right}" stroke="#32404E" stroke-dasharray="4 7"/>'
    points=[]
    for i,v in enumerate(vals):
        x=left+(right-left)*(i/max(1,len(vals)-1))
        y=bottom-(bottom-top)*v/m
        points.append((x,y))
    s+='<defs><linearGradient id="activity" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#C87A53" stop-opacity=".28"/><stop offset="1" stop-color="#C87A53" stop-opacity="0"/></linearGradient></defs>'
    line=' '.join(f'{x:.1f},{y:.1f}' for x,y in points)
    poly=f'{left},{bottom} '+line+f' {right},{bottom}'
    s+=f'<polygon points="{poly}" fill="url(#activity)"/><polyline points="{line}" fill="none" stroke="{COPPER}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
    for x,y in points:
        if y<bottom-8:s+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#F2D1BA"/>'
    s+=label(left,270,'~ 12 MONTHS AGO',12,MUTED)+label(964,270,'THIS WEEK',12,MUTED)
    if demo:s+=label(400,287,'DESIGN PREVIEW · NOT LIVE ACTIVITY',11,'#E6A58C',700)
    return s+end()

def request_json(url, token, data=None):
    headers={'Accept':'application/vnd.github+json','User-Agent':'IXM-public-stats/1.0','X-GitHub-Api-Version':'2022-11-28'}
    if token:headers['Authorization']='Bearer '+token
    if data is not None:
        headers['Content-Type']='application/json'
        data=json.dumps(data).encode('utf-8')
    req=Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')
    try:
        with urlopen(req,timeout=25) as f:return json.load(f)
    except HTTPError as e:
        raise RuntimeError(f'GitHub API HTTP {e.code} at {url} (token is not printed)') from None
    except URLError as e:
        raise RuntimeError('GitHub API network request failed') from None

def live_data(user,token):
    if not token:
        raise RuntimeError('GITHUB_TOKEN is required for live statistics; use the GitHub Actions workflow')
    profile=request_json('https://api.github.com/users/'+user,token)
    repos=[]
    for page in range(1,11):
        batch=request_json(f'https://api.github.com/users/{user}/repos?type=owner&per_page=100&page={page}',token)
        if not isinstance(batch,list):raise RuntimeError('Unexpected repos response from GitHub')
        repos.extend(x for x in batch if not x.get('private') and not x.get('fork'))
        if len(batch)<100:break
    languages=Counter(x['language'] for x in repos if x.get('language'))
    # GitHub's GraphQL API exposes the public contribution calendar.
    query='query($login:String!){ user(login:$login){ contributionsCollection { contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } } } } }'
    weeks=[]; contribution=None
    try:
        obj=request_json('https://api.github.com/graphql',token,{'query':query,'variables':{'login':user}})
        if obj.get('errors'):raise RuntimeError('GitHub GraphQL returned errors')
        c=obj['data']['user']['contributionsCollection']['contributionCalendar']
        contribution=int(c['totalContributions'])
        weeks=c['weeks']
    except (KeyError, TypeError, ValueError, RuntimeError) as e:
        print('Contribution calendar unavailable; other stats will be refreshed.',file=sys.stderr)
    overview={'repos':len(repos),'stars':sum(int(x.get('stargazers_count',0)) for x in repos),'followers':int(profile.get('followers',0)), 'contrib':contribution if contribution is not None else '—'}
    return overview,languages,weeks

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--username',default='ismailmalin')
    ap.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'assets'))
    ap.add_argument('--demo',action='store_true',help='Create clearly marked fictitious preview graphics, never for publication')
    args=ap.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if args.demo:
        overview={'repos':18,'stars':7,'followers':3,'contrib':46}
        lang=Counter({'Python':7,'HTML':4,'Java':3,'TypeScript':2,'JavaScript':1,'SQL':1})
        weeks=[{'contributionDays':[{'contributionCount':((i*7+j*3)%14==0)*((i+j)%4+1)} for j in range(7)]} for i in range(52)]
    else:
        overview,lang,weeks=live_data(args.username,os.environ.get('GITHUB_TOKEN',''))
    outputs={'ixm-stats.svg':svg_stats(overview,args.demo),'ixm-languages.svg':svg_languages(lang,args.demo),'ixm-activity.svg':svg_activity(weeks,args.demo)}
    for filename,data in outputs.items():
        (out/filename).write_text(data,encoding='utf-8')
        print('Generated:',out/filename)

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError) as e:
        print('ERROR:',str(e),file=sys.stderr)
        sys.exit(1)
