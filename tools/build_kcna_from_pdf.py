#!/usr/bin/env python3
import json
import os
import re
import sys
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Tuple

PDF = 'KCNA-exam-prep.pdf'
TXT = 'KCNA-exam-prep.txt'
OUT = 'kcna_from_pdf.json'


def run_pdftotext():
    if not os.path.exists(PDF):
        print(f'! Missing {PDF}', file=sys.stderr)
        sys.exit(1)
    subprocess.run(['pdftotext', '-layout', PDF, TXT], check=True)


def clean_line(s: str) -> str:
    if s is None:
        return ''
    s = s.rstrip('\n')
    # strip soft hyphen breaks like 'di-\n rectly'
    s = s.replace('\u00AD', '')
    return s


def normalize_text(s: str) -> str:
    if s is None:
        return ''
    # remove hyphen+space line break artifacts
    s = re.sub(r'-\s+', '', s)
    # unify punctuation/quotes
    s = (s.replace('\u2019', "'").replace('\u2018', "'")
            .replace('\u201c', '"').replace('\u201d', '"'))
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def keyify(s: str) -> str:
    s = normalize_text(s).lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def parse_quizzes(lines: List[str]) -> Dict[str, Dict[str, Any]]:
    """Parse the '1 Quizzes' section: returns mapping by section_key (e.g., '1.1')
    to section dict with title and questions [{number, question, options:[..]}]."""
    re_quizzes = re.compile(r'^\s*1\s+Quizzes\s*$')
    re_solutions = re.compile(r'^\s*2\s+Solutions\s*$')
    re_sec = re.compile(r'^\s*1\.(\d+)\s+(.*)')
    re_q = re.compile(r'^\s*(\d+)\.\s*(.*)')
    re_opt = re.compile(r'^\s*([A-E])\.(.*)')

    in_quizzes = False
    sections: Dict[str, Dict[str, Any]] = {}
    cur_key = None

    i = 0
    while i < len(lines):
        raw = clean_line(lines[i])
        if not in_quizzes:
            if re_quizzes.match(raw):
                in_quizzes = True
            i += 1
            continue
        if re_solutions.match(raw):
            break
        msec = re_sec.match(raw)
        if msec:
            idx = msec.group(1)
            title = normalize_text(msec.group(2))
            cur_key = f'1.{idx}'
            sections[cur_key] = { 'title': title, 'questions': [] }
            i += 1
            continue
        m = re_q.match(raw)
        if m and cur_key:
            num = int(m.group(1))
            # accumulate question text until first option
            qbuf = [m.group(2).strip()]
            j = i + 1
            while j < len(lines):
                s = clean_line(lines[j])
                if re_opt.match(s) or re_q.match(s) or s.strip().startswith('Answer'):
                    break
                # skip page numbers
                if re.fullmatch(r'\s*\d+\s*', s):
                    j += 1
                    continue
                qbuf.append(s.strip())
                j += 1
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

            # parse options A..E
            opts: Dict[str, str] = {}
            k = j
            cur_letter = None
            cur_buf: List[str] = []
            while k < len(lines):
                s = clean_line(lines[k])
                if re_q.match(s) or s.strip().startswith('Answer'):
                    break
                mo = re_opt.match(s)
                if mo:
                    if cur_letter is not None:
                        opts[cur_letter] = normalize_text(' '.join(cur_buf))
                    cur_letter = mo.group(1)
                    first = mo.group(2).strip()
                    cur_buf = [first]
                else:
                    if cur_letter is not None:
                        if re.fullmatch(r'\s*\d+\s*', s):
                            k += 1
                            continue
                        cur_buf.append(s.strip())
                k += 1
            if cur_letter is not None:
                opts[cur_letter] = normalize_text(' '.join(cur_buf))
            options = [opts.get(x) for x in ['A','B','C','D','E']]
            options = [o for o in options if o]
            sections[cur_key]['questions'].append({
                'number': num,
                'question': qtext,
                'options': options
            })
            i = k
            continue
        i += 1
    return sections


def parse_solutions(lines: List[str]) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """Parse '2 Solutions' -> mapping of section_key '2.x' to mapping of number-> {answer, explanation, domain, competency, question(optional)}"""
    re_solutions = re.compile(r'^\s*2\s+Solutions\s*$')
    re_sec = re.compile(r'^\s*2\.(\d+)\s+(.*)')
    re_q = re.compile(r'^\s*(\d+)\.\s*Question\s*(.*)', re.IGNORECASE)
    re_ans = re.compile(r'Correct\s+Answer\s*:\s*([A-E])', re.IGNORECASE)
    re_expl = re.compile(r'^\s*Explanation\s*:\s*(.*)', re.IGNORECASE)

    in_solutions = False
    sections: Dict[str, Dict[int, Dict[str, Any]]] = {}
    cur_key = None
    i = 0
    while i < len(lines):
        raw = clean_line(lines[i])
        if not in_solutions:
            if re_solutions.match(raw):
                in_solutions = True
            i += 1
            continue
        msec = re_sec.match(raw)
        if msec:
            idx = msec.group(1)
            title = normalize_text(msec.group(2))
            cur_key = f'2.{idx}'
            sections[cur_key] = {}
            i += 1
            continue

        if cur_key:
            m = re_q.match(raw)
            if m:
                num = int(m.group(1))
                # capture question text following 'Question'
                qbuf = [m.group(2).strip()]
                j = i + 1
                # read until Correct Answer appears
                while j < len(lines):
                    s = clean_line(lines[j])
                    if re_ans.search(s):
                        break
                    if re_sec.match(s) or re_q.match(s):
                        break
                    if re.fullmatch(r'\s*\d+\s*', s):
                        j += 1
                        continue
                    qbuf.append(s.strip())
                    j += 1
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

                # parse answer line
                ans_letter = None
                expl_buf: List[str] = []
                domain = None
                competency = None

                k = j
                while k < len(lines):
                    s = clean_line(lines[k])
                    if re_sec.match(s) or re_q.match(s):
                        break
                    maa = re_ans.search(s)
                    if maa:
                        ans_letter = maa.group(1)
                        k += 1
                        continue
                    mex = re_expl.match(s)
                    if mex:
                        # include the rest of the line, then accumulate until Domain/Competency or next question/section
                        expl_buf.append(mex.group(1).strip())
                        k += 1
                        while k < len(lines):
                            s2 = clean_line(lines[k])
                            if re_sec.match(s2) or re_q.match(s2):
                                break
                            # capture Domain / Competency if present
                            md = re.match(r'^\s*Domain\s*:\s*(.*)$', s2)
                            mc = re.match(r'^\s*Competency\s*:\s*(.*)$', s2)
                            if md:
                                domain = normalize_text(md.group(1))
                            elif mc:
                                competency = normalize_text(mc.group(1))
                            else:
                                if not re.fullmatch(r'\s*\d+\s*', s2) and not s2.strip().startswith('Return to Question'):
                                    expl_buf.append(s2.strip())
                            k += 1
                        break
                    k += 1

                explanation = normalize_text(' '.join(expl_buf))
                sections[cur_key][num] = {
                    'question': qtext,
                    'answer': ans_letter,
                    'explanation': explanation,
                    'domain': domain,
                    'competency': competency,
                }
                i = k
                continue
        i += 1

    return sections


def merge(quizzes: Dict[str, Dict[str, Any]], solutions: Dict[str, Dict[int, Dict[str, Any]]]) -> Dict[str, Any]:
    # map 1.x -> 2.x
    sec_map: Dict[str, str] = {}
    for k in quizzes.keys():
        idx = k.split('.')[1]
        sec_map[k] = f'2.{idx}'

    out_sections: List[Dict[str, Any]] = []
    total = 0
    matched = 0

    def letter_to_index(ch):
        if ch is None: return None
        m={'A':0,'B':1,'C':2,'D':3,'E':4}
        ch=str(ch).strip().upper()
        return m.get(ch)

    for qkey, sec in quizzes.items():
        sol_key = sec_map.get(qkey)
        sol = solutions.get(sol_key, {})
        out_qs: List[Dict[str, Any]] = []
        for q in sec['questions']:
            total += 1
            num = q['number']
            s = sol.get(num)
            aq = {
                'number': num,
                'question': q['question'],
                'options': q.get('options') or [],
                'answer': s.get('answer') if s else None,
                'answerIndex': letter_to_index(s.get('answer') if s else None),
                'explanation': s.get('explanation') if s else '',
                'domain': s.get('domain') or '',
                'competency': s.get('competency') or ''
            }
            if s and aq['options'] and aq['answerIndex'] is not None:
                matched += 1
            out_qs.append(aq)
        out_sections.append({
            'section_key': sol_key or qkey,
            'title': sec['title'],
            'questions': out_qs
        })

    data = {
        'source_file': PDF,
        'generated_at': datetime.utcnow().isoformat(),
        'sections': out_sections,
        'notes': {
            'build': 'Parsed Quizzes for options and Solutions for answers/explanations/domains. Merged by section + number.'
        }
    }
    print(f'Merged questions: {total}; fully matched (options + answer): {matched}')
    return data


def main():
    if not os.path.exists(TXT):
        run_pdftotext()
    with open(TXT, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    quizzes = parse_quizzes(lines)
    solutions = parse_solutions(lines)

    data = merge(quizzes, solutions)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()

