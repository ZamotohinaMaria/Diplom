# Приводит порядок XML-элементов в docx от pandoc 2.12 к схеме OOXML.
import zipfile,re,sys
for p in sys.argv[1:]:
    zin=zipfile.ZipFile(p); items=[(i,zin.read(i.filename)) for i in zin.infolist()]; zin.close()
    out=[]
    for i,b in items:
        if i.filename=='word/settings.xml':
            s=b.decode('utf8')
            m=re.search(r'<w:footnotePr>.*?</w:footnotePr>',s,re.S)
            if m:
                fp=m.group(0); s=s[:m.start()]+s[m.end():]; k=s.index('<w:rsids>'); s=s[:k]+fp+s[k:]
            s=re.sub(r'<w:proofState[^>]*/>','',s)
            b=s.encode('utf8')
        elif i.filename=='word/document.xml':
            s=b.decode('utf8')
            s=re.sub(r'(<w:numPr>.*?</w:numPr>)(<w:pStyle [^>]*/>)',r'\2\1',s)
            b=s.encode('utf8')
        out.append((i,b))
    z=zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED)
    for i,b in out: z.writestr(i,b)
    z.close()
