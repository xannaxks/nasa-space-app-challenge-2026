import os
from collections import Counter
root='sim3464_database'
rows=[]
for dp,dn,fn in os.walk(root):
    for f in fn:
        fp=os.path.join(dp,f)
        try:
            sz=os.path.getsize(fp)
        except:
            sz=-1
        rows.append((sz,fp))
rows.sort(reverse=True)
print(f'TOTAL FILES: {len(rows)} TOTAL BYTES: {sum(s for s,_ in rows if s>0)}')
c=Counter()
for s,fp in rows:
    ext=os.path.splitext(fp)[1].lower() or '(no ext)'
    c[ext]+=1
print('BY EXT:')
for k,v in c.most_common():
    print(k,v)
print('--- TOP 30 LARGEST ---')
for s,p in rows[:30]:
    print(f'{s/1e6:.2f} MB {p}')
