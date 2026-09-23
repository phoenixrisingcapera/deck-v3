"""Iteration 10: paragraph normalization discarded native chart associations."""
import re
import fitz
from app.services.deck_extractors.pdf_text_extractor import extract_pdf_text_by_page
from app.services.deck_extractors.slide_block_builder import build_slide_blocks


def test_native_chart_columns_survive_page_record_construction(tmp_path):
    source=tmp_path/'chart.pdf'
    with fitz.open() as doc:
        page=doc.new_page(width=960,height=540)
        page.insert_text((50,50),'Progress signals',fontsize=24)
        page.insert_text((200,350),'38%',fontsize=16)
        page.insert_text((700,150),'100%',fontsize=16)
        page.insert_text((200,430),'Upload',fontsize=16)
        page.insert_text((700,430),'Publish',fontsize=16)
        doc.save(source)
    extracted=extract_pdf_text_by_page(source,[1])[0]['text']
    record=build_slide_blocks(extracted,1)
    def associations(text):
        label_line=next(line for line in text.splitlines() if 'Upload' in line)
        labels=[(m.start(),m.group()) for m in re.finditer(r'Upload|Publish',label_line)]
        return {m.group():min(labels,key=lambda label:abs(label[0]-m.start()))[1]
                for line in text.splitlines() for m in re.finditer(r'\d+%',line)}
    assert associations(extracted)=={'100%':'Publish','38%':'Upload'}
    assert associations(record['rawText'])==associations(extracted)
    assert all(block['normalizedText']==' '.join(block['normalizedText'].split()) for block in record['blocks'])
