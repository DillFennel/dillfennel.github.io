"""Verify that an HTML edit reaches the PDF and changes its download URL."""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest

from pypdf import PdfReader
from lxml import html

from build_site import build, normalized


class ResumeSyncTest(unittest.TestCase):
    def test_new_html_content_updates_pdf_and_download_link(self):
        repository = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'data').mkdir()
            shutil.copytree(repository / 'data/avatar', source / 'data/avatar')
            for name in ('index.html', 'styles.css', 'favicon.svg'):
                (source / name).write_bytes((repository / name).read_bytes())
            build(source, root / 'first')
            original = (root / 'first/index.html').read_text()
            phrase = 'Новый раздел автоматически попадает в PDF.'
            index = (source / 'index.html').read_text()
            index = index.replace('</main>', '<section><h2>Новый раздел</h2><p>' + phrase + '</p></section></main>')
            (source / 'index.html').write_text(index)
            build(source, root / 'second')
            updated = (root / 'second/index.html').read_text()
            pdf = PdfReader(root / 'second/data/resume/cv_petrushina_yulia.pdf')
            self.assertIn(normalized(phrase), normalized(''.join(p.extract_text() for p in pdf.pages)))
            original_link = html.fromstring(original).xpath('//a[@download]/@href')[0]
            updated_link = html.fromstring(updated).xpath('//a[@download]/@href')[0]
            self.assertNotEqual(original_link, updated_link)


if __name__ == '__main__':
    unittest.main()
