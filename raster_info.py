import glob, tifffile

for f in sorted(glob.glob("sim3464_database/sim3464_JezeroNili_FINAL/Rasters/**/*.tif", recursive=True)):
    try:
        with tifffile.TiffFile(f) as t:
            p = t.pages[0]
            print("="*100)
            print(f)
            print(f"  shape={p.shape} dtype={p.dtype}")
            tags = p.tags
            for k in ['ImageWidth','ImageLength','ModelPixelScaleTag','ModelTiepointTag','GeoKeyDirectoryTag']:
                if k in tags:
                    print(f"  {k}={tags[k].value}")
            # descriptions
            if p.description:
                d = p.description[:600].replace('\n',' | ')
                print(f"  desc={d}")
    except Exception as e:
        print(f, "ERR", e)
