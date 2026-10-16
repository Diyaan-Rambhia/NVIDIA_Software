import json
import re
from pathlib import Path
from backend.app.config.loader import load_all_config
from backend.app.features.f2_filings.text_chunker import chunk_text

all_cfg = load_all_config()
params = all_cfg.parameters.parameters

chunk_size_param = params.get("chunk_size")
chunk_overlap_param = params.get("chunk_overlap")

print("CHUNK_SIZE:", chunk_size_param.default, "bounds:", chunk_size_param.min, chunk_size_param.max, "unit:", chunk_size_param.unit)
print("CHUNK_OVERLAP:", chunk_overlap_param.default, "bounds:", chunk_overlap_param.min, chunk_overlap_param.max, "unit:", chunk_overlap_param.unit)

announcements_path = Path("data") / "transcripts" / "announcements.json"
if announcements_path.exists():
    data = json.loads(announcements_path.read_text(encoding="utf-8"))
    print(f"Total stored announcement items in announcements.json: {len(data)}")
    
    longest_overall_sentence = 0
    longest_sentence_text = ""
    any_longer_than_overlap = False
    
    for i, item in enumerate(data):
        text = item.get("attchmntText") or item.get("desc") or ""
        chunks = chunk_text(text, chunk_size=chunk_size_param.default, chunk_overlap=chunk_overlap_param.default)
        
        # Split sentences roughly by . ! ?
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        max_s = max((len(s) for s in sentences), default=0)
        
        print(f"Item {i+1} ({item.get('symbol')}): text_len={len(text)}, chunks={len(chunks)}, max_sentence_len={max_s}")
        if max_s > longest_overall_sentence:
            longest_overall_sentence = max_s
            longest_sentence_text = [s for s in sentences if len(s) == max_s][0]
        if max_s > chunk_overlap_param.default:
            any_longer_than_overlap = True

    print(f"Overall longest sentence length: {longest_overall_sentence}")
    print(f"Longest sentence: '{longest_sentence_text}'")
    print(f"Any sentence longer than overlap ({chunk_overlap_param.default})? {any_longer_than_overlap}")
else:
    print("No announcements.json found")
