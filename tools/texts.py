import json,re,sys
N=json.load(open('public/data/nodes.json'))
def walk(o,path):
    if isinstance(o,dict):
        for k,v in o.items():
            if k in('text','label') and isinstance(v,str): yield path+'.'+k,v
            else: yield from walk(v,path+'.'+str(o.get('id',k)) if k in('choices','sub') else path)
    elif isinstance(o,list):
        for i,v in enumerate(o): yield from walk(v,path+(f'.{v.get("id")}' if isinstance(v,dict) and v.get('id') else ''))
rx=re.compile(sys.argv[1])
for nid,n in N.items():
    for p,t in walk(n,nid):
        if rx.search(t): print(p,'|',t[:150])
