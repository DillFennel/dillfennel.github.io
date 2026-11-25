"""Build the public site and its PDF from the same index.html.

No resume wording is stored in this script. Text coverage is checked against
the rendered PDF before the deployment artifact is created.
"""
from argparse import ArgumentParser
from functools import partial
from hashlib import sha256
from html import escape
from pathlib import Path
import re
import shutil
from urllib.parse import urljoin

from lxml import html
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_DIR = Path(__file__).parent / 'fonts'
PDF_PATH = Path('data/resume/yulia-petrushina-cpp.pdf')
INK = colors.HexColor('#22242a')
MUTED = colors.HexColor('#64656e')
ACCENT = colors.HexColor('#b83316')
LINE = colors.HexColor('#e7dce5')
PALE = colors.HexColor('#faf6f8')
WIDTH = A4[0] - 32 * mm - 12


def normalized(text):
    return re.sub(r'\s+', '', text)


def classes(node):
    return node.get('class', '').split()


class Resume:
    def __init__(self, source):
        self.source = source
        self.root = html.fromstring(source.read_bytes())
        self.base_url = self.root.xpath('//link[@rel="canonical"]/@href')[0]
        self.name = self.root.xpath('//h1')[0].text_content().strip()
        self.title = self.root.xpath('//title')[0].text_content().strip()
        self.story = []
        self.expected = []
        for name, file in [('Resume', 'OpenSans-Regular.ttf'), ('ResumeBold', 'OpenSans-SemiBold.ttf'), ('ResumeItalic', 'OpenSans-Italic.ttf')]:
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
        pdfmetrics.registerFontFamily('Resume', normal='Resume', bold='ResumeBold', italic='ResumeItalic', boldItalic='ResumeBold')
        self.styles = {
            'body': ParagraphStyle('body', fontName='Resume', fontSize=9.5, leading=12.4, textColor=INK, spaceAfter=3.5, allowWidows=0, allowOrphans=0),
            'name': ParagraphStyle('name', fontName='ResumeBold', fontSize=26, leading=31, textColor=INK, spaceAfter=4),
            'role': ParagraphStyle('role', fontName='Resume', fontSize=12.5, leading=17, textColor=ACCENT, spaceAfter=6),
            'contact': ParagraphStyle('contact', fontName='Resume', fontSize=8.5, leading=12, textColor=MUTED, spaceAfter=7),
            'section': ParagraphStyle('section', fontName='ResumeBold', fontSize=12, leading=16, textColor=ACCENT, spaceBefore=8, spaceAfter=4, keepWithNext=True),
            'heading': ParagraphStyle('heading', fontName='ResumeBold', fontSize=10.7, leading=14, textColor=INK, spaceBefore=6, spaceAfter=3, keepWithNext=True),
            'meta': ParagraphStyle('meta', fontName='Resume', fontSize=8.5, leading=11, textColor=MUTED, spaceAfter=4, keepWithNext=True),
            'bullet': ParagraphStyle('bullet', fontName='Resume', fontSize=9.5, leading=12.4, textColor=INK, leftIndent=10, bulletIndent=0, bulletFontName='Resume', bulletFontSize=7, bulletColor=ACCENT, spaceAfter=4, allowWidows=0, allowOrphans=0),
            'small': ParagraphStyle('small', fontName='Resume', fontSize=8.5, leading=11, textColor=MUTED, spaceAfter=4),
        }

    def inline(self, node):
        text = escape(node.text or '')
        for child in node:
            if child.tag in ('svg', 'img'):
                content = ''
            else:
                content = self.inline(child)
            if child.tag in ('strong', 'b'):
                content = '<b>' + content + '</b>'
            elif child.tag in ('em', 'i'):
                content = '<i>' + content + '</i>'
            elif child.tag == 'a':
                content = '<a href="' + escape(urljoin(self.base_url, child.get('href', '')), quote=True) + '" color="#b83316">' + content + '</a>'
            elif child.tag == 'br':
                content = '<br/>'
            text += content + escape(child.tail or '')
        return re.sub(r'\s*·\s*', ' · ', re.sub(r'\s+', ' ', text)).strip()

    def paragraph(self, node, style='body', bullet=False):
        self.expected.append(node.text_content())
        return Paragraph(self.inline(node), self.styles[style], bulletText='•' if bullet else None)

    def section(self, node):
        rule = HRFlowable(width='100%', thickness=.55, color=LINE, spaceAfter=6)
        rule.keepWithNext = True
        return [self.paragraph(node, 'section'), rule]

    def render(self, node, width=WIDTH):
        if node.get('aria-hidden') == 'true' or node.tag in ('svg', 'img', 'script', 'style'):
            return []
        if node.tag == 'h2':
            return self.section(node)
        if node.tag in ('h3', 'h4'):
            return [self.paragraph(node, 'heading')]
        if node.tag == 'p':
            cls = classes(node)
            style = 'meta' if 'eyebrow' in cls else 'small' if set(cls) & {'meta', 'stack', 'job__context', 'job__role'} else 'body'
            if 'meta' in cls and node.getprevious() is not None and node.getprevious().tag == 'h3':
                style = 'meta'
            return [self.paragraph(node, style)]
        if node.tag == 'a':
            if not node.text_content().strip():
                return []
            self.expected.append(node.text_content())
            return [Paragraph('<a href="' + escape(urljoin(self.base_url, node.get('href', '')), quote=True) + '" color="#b83316">' + self.inline(node) + '</a>', self.styles['small'])]
        if node.tag == 'li':
            return [KeepTogether([self.paragraph(node, 'bullet', True)])]
        if node.tag == 'table':
            result = []
            caption = node.find('caption')
            if caption is not None:
                result.append(self.paragraph(caption, 'small'))
            rows = [[self.paragraph(cell, 'small') for cell in row] for row in node.xpath('.//tr')]
            column_count = len(rows[0])
            first = width * .31
            table = Table(rows, colWidths=[first] + [(width-first)/(column_count-1)]*(column_count-1), repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,LINE),('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
            return result + [table, Spacer(1,5)]
        result = []
        if node.text and node.text.strip():
            self.expected.append(node.text)
            result.append(Paragraph(escape(node.text.strip()), self.styles['body']))
        for child in node:
            result.extend(self.render(child, width))
            if child.tail and child.tail.strip():
                self.expected.append(child.tail)
                result.append(Paragraph(escape(child.tail.strip()), self.styles['body']))
        return result

    def compose(self):
        self.story.append(self.paragraph(self.root.xpath('//h1')[0], 'name'))
        hero = self.root.xpath('//header[contains(@class,"hero")]')[0]
        role = hero.xpath('.//*[contains(@class,"hero__role")]')[0]
        self.story.append(self.paragraph(role, 'role'))
        contacts = self.root.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," header-contacts ")]')[0]
        self.story.append(self.paragraph(contacts, 'contact'))
        for p in hero.xpath('.//*[contains(@class,"hero__location") or contains(@class,"availability")]'):
            self.story.append(self.paragraph(p, 'small'))
        main = self.root.xpath('//main')[0]
        sections = list(main)
        i = 0
        while i < len(sections):
            section = sections[i]
            # A compact final row keeps related education/certificates together.
            if section.get('id') == 'education' and i+1 < len(sections) and sections[i+1].get('id') == 'certificates':
                left_width = WIDTH * .48
                columns = [self.render(section, left_width-16), self.render(sections[i+1], WIDTH-left_width)]
                table = Table([columns], colWidths=[left_width,WIDTH-left_width], hAlign='LEFT')
                table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(0,0),16),('RIGHTPADDING',(1,0),(1,0),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
                self.story.append(table)
                i += 2
                continue
            if 'layout__skills' in classes(section):
                self.story.extend(self.section(section.xpath('./h2')[0]))
                items=section.xpath('.//li') + hero.xpath('.//*[contains(@class,"skills--languages")]/li')
                self.expected.extend(n.text_content() for n in items)
                text=' · '.join(self.inline(n) for n in items)
                box=Table([[Paragraph(text,self.styles['body'])]],colWidths=[WIDTH])
                box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.5,LINE),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
                self.story.append(box)
            else:
                self.story.extend(self.render(section))
            i += 1

    def footer(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(.5)
        canvas.line(doc.leftMargin,13*mm,A4[0]-doc.rightMargin,13*mm)
        canvas.setFont('Resume',7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin,9*mm,self.name)
        canvas.drawRightString(A4[0]-doc.rightMargin,9*mm,str(doc.page))
        canvas.restoreState()

    def write(self, destination):
        self.compose()
        destination.parent.mkdir(parents=True,exist_ok=True)
        document=SimpleDocTemplate(str(destination),pagesize=A4,leftMargin=16*mm,rightMargin=16*mm,topMargin=15*mm,bottomMargin=19*mm,title=self.title,author=self.name)
        document.build(self.story,onFirstPage=self.footer,onLaterPages=self.footer,canvasmaker=partial(Canvas,invariant=1))
        pdf=PdfReader(destination)
        page_text=[]
        for number,page in enumerate(pdf.pages,1):
            lines=page.extract_text().splitlines()
            if lines[:2] != [self.name,str(number)]:
                raise ValueError('Unexpected PDF footer order')
            page_text.append('\n'.join(lines[2:]))
        actual=normalized(''.join(page_text))
        missing=[t for t in self.expected if normalized(t) not in actual]
        # Also check the source DOM independently of the renderer's selected blocks.
        for node in self.root.xpath('//main//*[self::h2 or self::h3 or self::p or self::li or self::th or self::td or self::caption]'):
            if not node.xpath('ancestor-or-self::*[@aria-hidden="true"]') and normalized(node.text_content()) not in actual:
                missing.append(node.text_content())
        if missing:
            raise ValueError('PDF text differs from index.html: '+repr(missing))
        print(f'PDF: {len(pdf.pages)} pages; {len(self.expected)} text blocks verified')


def build(source, output):
    source=source.resolve()
    output=output.resolve()
    if output==source or source in output.parents and output.name not in ('_site','build'):
        raise ValueError('Use a separate output directory, such as _site')
    output.mkdir(parents=True,exist_ok=True)
    for file in ('index.html','styles.css','favicon.svg'):
        shutil.copy2(source/file,output/file)
    shutil.copytree(source/'data',output/'data',dirs_exist_ok=True)
    Resume(source/'index.html').write(output/PDF_PATH)
    # A content-derived URL avoids an old cached PDF after a site update.
    version=sha256((output/PDF_PATH).read_bytes()).hexdigest()[:12]
    index=(source/'index.html').read_text()
    index=index.replace(f'href="{PDF_PATH.as_posix()}"',f'href="{PDF_PATH.as_posix()}?v={version}"')
    (output/'index.html').write_text(index)
    print('Public site:',output)


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,default=Path('_site'))
    args=parser.parse_args()
    build(args.source,args.output)
