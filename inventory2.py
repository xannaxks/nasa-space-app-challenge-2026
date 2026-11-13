import os
for root,dirs,files in os.walk('sim3464_database/database'):
    level=root.count(os.sep)
    if level>4: continue
    print('DIR:',root, ' N files:',len(files),' N dirs:',len(dirs))
    for f in sorted(files)[:40]:
        print(' ',f)
    print()
