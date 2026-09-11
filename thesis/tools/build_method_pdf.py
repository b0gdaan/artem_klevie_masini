"""Build the explicitly labelled methodological manuscript from its Markdown source.

Usage: python thesis/tools/build_method_pdf.py --root . --font-dir C:/Windows/Fonts
Requires reportlab. Figures and metrics must come from the same verified run.
"""
import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--font-dir', type=Path, default=Path('C:/Windows/Fonts'))
    parser.add_argument('--evidence', type=Path, default=Path('thesis/evidence/revision-2026-09-11'))
    args = parser.parse_args()
    root = args.root.resolve()
    for name, file in [('Thesis', 'times.ttf'), ('Thesis-Bold', 'timesbd.ttf'),
                       ('Thesis-Italic', 'timesi.ttf'), ('Thesis-BoldItalic', 'timesbi.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(args.font_dir / file)))
    pdfmetrics.registerFontFamily('Thesis', normal='Thesis', bold='Thesis-Bold',
                                  italic='Thesis-Italic', boldItalic='Thesis-BoldItalic')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('BodyThesis', fontName='Thesis', fontSize=12, leading=18,
                              alignment=TA_JUSTIFY, spaceAfter=6, splitLongWords=True))
    styles.add(ParagraphStyle('HeadThesis', fontName='Thesis-Bold', fontSize=16, leading=20,
                              spaceBefore=14, spaceAfter=10, keepWithNext=True))
    styles.add(ParagraphStyle('CoverThesis', fontName='Thesis-Bold', fontSize=18, leading=25,
                              alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle('SmallThesis', fontName='Thesis', fontSize=10, leading=13,
                              spaceAfter=6))
    body, head, small = styles['BodyThesis'], styles['HeadThesis'], styles['SmallThesis']

    def p(text, style=body):
        text = escape(text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        return Paragraph(text, style)

    story = [p('ACADEMIA MARIBOR', styles['CoverThesis']), Spacer(1, 1.5*cm),
             p('Artem Rakhmanov', styles['CoverThesis']),
             p('SEO optimizacija spletnih mest', styles['CoverThesis']),
             p('Metode in strategije doseganja visokih pozicij v iskalnikih', styles['CoverThesis']),
             Spacer(1, cm), p('Metodološka različica praktičnega dela', styles['CoverThesis']),
             p('Mentor: mag. Dušan Brglez'), p('Maribor, september 2026'), Spacer(1, cm),
             p('Delovni rokopis za uskladitev z mentorjem. Sintetični poskus in ločen pregled javne strani. '
               'Dokument ni končna diplomska naloga in ne dokazuje rasti obiska resničnega podjetja.'), PageBreak()]
    lines = (root / 'thesis/Prakticni_del_metodicna_razlicica.md').read_text(encoding='utf-8').splitlines()
    story += [p('Vsebina', head)]
    for line in lines:
        if line.startswith('## '):
            story.append(p(line[3:]))
    story += [p('Priloga A Grafični rezultati sintetičnega poskusa'), PageBreak()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('# '):
            i += 1
            continue
        if line.startswith('## '):
            story.append(p(line[3:], head))
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+', c) for c in cells):
                    rows.append([p(c, small) for c in cells])
                i += 1
            table = Table(rows, colWidths=[4*cm, 1.7*cm, 3*cm, 7.3*cm], repeatRows=1)
            table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),
                ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#aaaaaa')),
                ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
            story.extend([table, Spacer(1, 10)])
            continue
        elif line:
            story.append(p(line))
        i += 1
    for name, caption in [('effects.png','Ocene učinkov in negotovost'),
                           ('timeseries.png','Časovne vrste sintetičnih podatkov'),
                           ('audit_issues.png','Simulirani HTML pregled pred ukrepi in po njih')]:
        image = Image(str(root / args.evidence / 'figures' / name))
        factor = min(16*cm/image.imageWidth, 19*cm/image.imageHeight)
        image.drawWidth = image.imageWidth * factor
        image.drawHeight = image.imageHeight * factor
        story += [PageBreak(), p(caption, head), image,
                  p('Vir: sintetični zagon smoke-20260911T132222Z-72ee40. '
                    'Graf ne predstavlja izmerjenih učinkov na javnem spletišču.', small)]

    def footer(canvas, doc):
        if doc.page > 1:
            canvas.setFont('Thesis', 10)
            canvas.drawCentredString(A4[0]/2, 1.4*cm, str(doc.page))

    output = root / 'thesis/Diplomsko_delo_Rakhmanov_metodicna_razlicica.pdf'
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=3*cm, rightMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2.5*cm,
                            title='SEO optimizacija spletnih mest - metodoloska razlicica',
                            author='Artem Rakhmanov')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == '__main__':
    main()
