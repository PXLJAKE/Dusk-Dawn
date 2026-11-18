"""Wandelt ASCII-STL in binäre STL um und meldet Kanten, die nicht genau zwei Dreiecke haben.

Aufruf: python3 stl_binaer.py <zielordner> <datei.stl> ...
"""
import sys, struct, numpy as np, collections, os
def read_ascii(p):
    v=[];
    with open(p) as f:
        for l in f:
            l=l.strip()
            if l.startswith('vertex'): v.append([float(x) for x in l.split()[1:]])
    return np.array(v,dtype=np.float32).reshape(-1,3,3)
for p in sys.argv[2:]:
    t=read_ascii(p); n=len(t)
    keys=np.round(t.reshape(-1,3),4); _,idx=np.unique(keys,axis=0,return_inverse=True); idx=idx.reshape(-1,3)
    e=collections.Counter()
    for a,b,c in idx:
        for u,w in ((a,b),(b,c),(c,a)): e[(min(u,w),max(u,w))]+=1
    bad=sum(1 for k,c in e.items() if c!=2)
    mn=t.reshape(-1,3).min(0); mx=t.reshape(-1,3).max(0)
    nrm=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]); l=np.linalg.norm(nrm,axis=1,keepdims=True); l[l==0]=1; nrm=nrm/l
    out=os.path.join(sys.argv[1],os.path.basename(p))
    with open(out,'wb') as f:
        f.write(b'Dusk & Dawn Soundlampe v2'.ljust(80,b' ')); f.write(struct.pack('<I',n))
        d=np.zeros(n,dtype=[('n','<f4',3),('v','<f4',(3,3)),('a','<u2')]); d['n']=nrm; d['v']=t; f.write(d.tobytes())
    print(f"{os.path.basename(p):24s} tris={n:7d} nonmanifold_edges={bad:4d} size={mx-mn} zmin={mn[2]:.2f} {os.path.getsize(out)/1e6:.1f}MB")
