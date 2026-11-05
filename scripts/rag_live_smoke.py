"""Opt-in actual multilingual E5 + FAISS recall smoke test (no OpenAI calls)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str((Path(__file__).resolve().parents[1] / "excel_rule_engine")))
from app.services.ai.rag_index import search


def main():
    examples=[('Chinh sach bao hanh may in la gi?', 'A-100'),
              ('What covers transport expenses?', 'B-200'),
              ('C-300', 'C-300')]
    # UTF-8 fixture without personal data; model may download on first run.
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/'knowledge.csv').write_text(
            'code,description\nA-100,Printer warranty covers repairs for twenty four months\n'
            'B-200,Travel allowance reimburses employee transport expenses\n'
            'C-300,Warehouse access requires a safety briefing\n',encoding='utf-8')
        records=[]
        for question,expected in examples:
            result=search(root,question,top_k=2)
            passed=any(expected in hit['text'] for hit in result['hits'])
            records.append({'question':question,'expected_code':expected,'found_at_2':passed,
                            'hits':[{'source':h['source'],'row':h['row'],'text':h['text']} for h in result['hits']]})
        print(json.dumps({'model':'intfloat/multilingual-e5-large','cases':records},ensure_ascii=True,indent=2))
        return 0 if all(r['found_at_2'] for r in records) else 1


if __name__=='__main__':
    raise SystemExit(main())
