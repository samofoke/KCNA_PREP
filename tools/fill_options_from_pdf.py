#!/usr/bin/env python3
import json
import os
import re
import subprocess
from typing import List, Dict, Tuple

PDF = 'KCNA-exam-prep.pdf'
TXT = 'KCNA-exam-prep.txt'
SRC_JSON = 'kcna_prep_qna_clean.json'
OUT_JSON = 'kcna_prep_qna_clean.filled.json'


def run_pdftotext():
    if not os.path.exists(PDF):
        raise SystemExit(f'Missing PDF: {PDF}')
    # Generate text with layout to keep option letters aligned
    subprocess.run(['pdftotext', '-layout', PDF, TXT], check=True)


def normalize_text(s: str) -> str:
    if s is None:
        return ''
    s = s.strip()
    # Fix common hyphenated splits like "di- rectly"
    s = re.sub(r'-\s+', '', s)
    # Normalize quotes and spaces
    s = s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    s = re.sub(r'\s+', ' ', s)
    return s


def keyify(s: str) -> str:
    s = normalize_text(s).lower()
    # keep alnum + space
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def parse_quizzes(text: List[str]) -> Dict[str, List[str]]:
    in_quizzes = False
    option_map: Dict[str, List[str]] = {}

    # Precompile patterns
    re_quizzes = re.compile(r'^\s*1\s+Quizzes\s*$')
    re_solutions = re.compile(r'^\s*2\s+Solutions\s*$')
    re_qstart = re.compile(r'^\s*(\d+)\.\s*(.*)')
    re_opt = re.compile(r'^\s*([A-E])\.(.*)')

    i = 0
    while i < len(text):
        line = text[i].rstrip('\n')
        if not in_quizzes:
            if re_quizzes.match(line):
                in_quizzes = True
            i += 1
            continue
        # Stop at solutions
        if re_solutions.match(line):
            break

        m = re_qstart.match(line)
        if m:
            # Capture question text across lines until first option
            qbuf = [m.group(2).rstrip()]
            j = i + 1
            while j < len(text):
                nxt = text[j].rstrip('\n')
                if re_opt.match(nxt):
                    break
                # stop if a new question starts unexpectedly (rare)
                if re_qstart.match(nxt):
                    break
                # skip page numbers or empty artifacts
                if re.fullmatch(r'\s*\d+\s*', nxt):
                    j += 1
                    continue
                qbuf.append(nxt.strip())
                j += 1

            # Join with hyphen fix
            qtext = ''
            for frag in qbuf:
                frag = frag.strip()
                if not frag:
                    continue
                if qtext.endswith('-'):
                    qtext = qtext[:-1] + frag
                else:
                    if qtext:
                        qtext += ' '
                    qtext += frag
            qtext = normalize_text(qtext)

            # Now parse options A..E up to 'Answer' or next question
            opts: Dict[str, str] = {}
            k = j
            cur_letter = None
            cur_buf: List[str] = []
            while k < len(text):
                s = text[k].rstrip('\n')
                if re_solutions.match(s):
                    break
                if re_qstart.match(s):
                    break
                if s.strip().startswith('Answer'):
                    # flush last option
                    if cur_letter is not None:
                        opts[cur_letter] = normalize_text(' '.join(cur_buf))
                        cur_letter = None
                        cur_buf = []
                    k += 1
                    break
                mo = re_opt.match(s)
                if mo:
                    # new option starts
                    if cur_letter is not None:
                        opts[cur_letter] = normalize_text(' '.join(cur_buf))
                    cur_letter = mo.group(1)
                    first = mo.group(2).strip()
                    cur_buf = [first]
                else:
                    # continuation of current option text
                    if cur_letter is not None:
                        # skip page numbers between wrapped lines
                        if re.fullmatch(r'\s*\d+\s*', s):
                            k += 1
                            continue
                        cur_buf.append(s.strip())
                k += 1
            # flush final
            if cur_letter is not None:
                opts[cur_letter] = normalize_text(' '.join(cur_buf))

            # Build ordered list
            ordered = [opts.get(ch) for ch in ['A', 'B', 'C', 'D', 'E']]
            ordered = [o for o in ordered if o and o.lower() != '']
            if ordered:
                option_map[keyify(qtext)] = ordered

            # advance
            i = k
            continue
        i += 1

    return option_map


def fill_json(options_map: Dict[str, List[str]]):
    with open(SRC_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    def letter_to_index(ch):
        if ch is None:
            return None
        m = {'A':0,'B':1,'C':2,'D':3,'E':4}
        s = str(ch).strip().upper()
        return m.get(s, None)

    total = 0
    filled = 0

    def process_question(q):
        nonlocal filled, total
        total += 1
        qtext = q.get('question') or ''
        k = keyify(qtext)
        opts = options_map.get(k)
        if opts:
            q['options'] = opts
            filled += 1
        # ensure answerIndex
        if 'answerIndex' not in q or not isinstance(q.get('answerIndex'), int):
            ai = letter_to_index(q.get('answer') or q.get('Answer'))
            if ai is not None:
                q['answerIndex'] = ai

    if isinstance(data, list):
        for q in data:
            process_question(q)
    elif isinstance(data, dict) and isinstance(data.get('sections'), list):
        for sec in data['sections']:
            for q in sec.get('questions', []):
                process_question(q)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'Processed: {total} questions; filled options for: {filled}.')
    print(f'Output written to: {OUT_JSON}')


def main():
    if not os.path.exists(TXT):
        run_pdftotext()
    with open(TXT, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    options_map = parse_quizzes(lines)
    if not options_map:
        raise SystemExit('Failed to parse any options from PDF text.')
    fill_json(options_map)


if __name__ == '__main__':
    main()
