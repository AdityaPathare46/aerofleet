"""Build the expert-diagnosis recording sheets from PX4 forum crash threads.

Rows: threads whose title or first post describes a crash and that have at least one reply from PX4 staff, the
dev team or an experienced forum member (trust level 3+). Threads whose log is rated as a crash on Flight Review
come first (in random order, not marked), then the rest at random. Seed 5. Reviewers record what the expert
concluded; they do not judge the crash themselves. The sheets contain forum text and are not committed.

    python research/px4_log_study/make_forum_sheet.py FORUM_THREADS_JSONL OUT_DIR
"""
import csv
import json
import os
import random
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

EXPERT = {"staff": "PX4 staff", "DevTeam": "PX4 dev team", "trust4": "experienced user", "trust3": "experienced user",
          "volunteer-team": "PX4 volunteer"}
CRASHY = ("crash", "fell", "flip", "fly away", "flyaway", "fly-away", "lost control", "hit the ground")
CAUSES = ["pilot input / handling", "wrong mode or mode switch", "battery / power", "motor / ESC / propeller",
          "vibration / mounting", "GPS / compass / estimator", "radio or data link", "tuning / configuration",
          "software / firmware bug", "airframe / mechanical", "wind / environment", "not stated"]
FILL = [("Is it a crash or loss of control?", ["yes", "no"]),
        ("Expert's conclusion", ["drone", "pilot", "both", "unclear", "no diagnosis given"]),
        ("Cause the expert names", CAUSES),
        ("Who gave it", ["PX4 staff / dev team", "experienced user", "other user", "original poster"]),
        ("Did the poster confirm?", ["yes", "no / disputed", "not stated"]),
        ("Quote: the sentence with the diagnosis", None)]
FONT, BOLD = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
INPUT, HEAD = PatternFill("solid", fgColor="FFFF00"), PatternFill("solid", fgColor="D9E1F2")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))


def label(r):
    if r["is_op"]:
        return "original poster"
    return EXPERT.get(r["role"], "other user")


def build(path, rows):
    wb = Workbook()
    ins = wb.active
    ins.title = "Instructions"
    lines = [
        ("Recording expert crash diagnoses from the PX4 forum", BOLD), ("", FONT),
        ("You are NOT judging the crash. You are recording what the forum's expert said. No drone knowledge is "
         "needed, only careful reading. Do not use AI tools; work on your own and do not compare with the other "
         "reviewer until both are done.", FONT), ("", FONT),
        ("For each row on 'Threads': read the 'Replies' cell (or open the thread link) and fill the yellow cells.", BOLD),
        ("1. Is it a crash or loss of control? 'no' if the thread is really about something else (then skip the rest).", FONT),
        ("2. Expert's conclusion: what the most experienced replier (PX4 staff / dev team first) says caused it.", FONT),
        ("   drone = hardware, software, configuration or tuning; pilot = the operator's inputs, mode choice or "
         "decisions; both; unclear = they discuss it but do not conclude; no diagnosis given = nobody answers the cause.", FONT),
        ("3. Cause the expert names, from the list. 'not stated' if they give none.", FONT),
        ("4. Who gave it, and 5. whether the original poster later agreed or reported the fix worked.", FONT),
        ("6. Copy the one sentence that states the diagnosis. Leave empty if none.", FONT), ("", FONT),
        ("Batch 1 = rows 1-50 (about 3 minutes each). Do those first.", BOLD), ("", FONT),
        ("Example (not a real thread): conclusion 'drone'; cause 'vibration / mounting'; who 'PX4 staff / dev team'; "
         "confirmed 'yes'; quote 'Your accel is clipping heavily, the FC needs soft mounting.'", FONT)]
    for i, (t, f) in enumerate(lines, 1):
        c = ins.cell(row=i, column=1, value=t)
        c.font, c.alignment = f, Alignment(wrap_text=True, vertical="top")
    ins.cell(row=len(lines) + 2, column=1, value="Progress (rows with a conclusion):").font = BOLD
    ins.cell(row=len(lines) + 2, column=2, value=f"=COUNTA(Threads!G2:G{len(rows) + 1})&\" of {len(rows)}\"").font = FONT
    ins.column_dimensions["A"].width = 120
    ins.column_dimensions["B"].width = 16

    ws = wb.create_sheet("Threads")
    heads = ["#", "Batch", "Thread", "Title", "First post (excerpt)", "Replies (role in brackets)"] + [h for h, _ in FILL]
    widths = [5, 7, 10, 40, 50, 90, 12, 14, 24, 22, 14, 50]
    for j, (h, w) in enumerate(zip(heads, widths), 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font, c.fill, c.alignment = BOLD, HEAD, Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[c.column_letter].width = w
    for i, t in enumerate(rows, 2):
        replies = " || ".join(f"[{label(r)}] {r['text'][:700]}" for r in t["replies"])[:6000]
        vals = [i - 1, 1 if i - 1 <= 50 else 2, None, t["title"], t["op_text"][:600], replies]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font, c.border, c.alignment = FONT, THIN, Alignment(wrap_text=True, vertical="top")
        link = ws.cell(row=i, column=3, value="Open thread")
        link.hyperlink = t["url"]
        link.font = Font(name="Arial", size=10, color="0563C1", underline="single")
        for j in range(7, 7 + len(FILL)):
            c = ws.cell(row=i, column=j)
            c.fill, c.font, c.border, c.alignment = INPUT, FONT, THIN, Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 120
    n = len(rows) + 1
    for k, (_, opts) in enumerate(FILL):
        if opts:
            col = ws.cell(row=1, column=7 + k).column_letter
            dv = DataValidation(type="list", formula1='"' + ",".join(opts) + '"', allow_blank=True)
            dv.error, dv.errorTitle = "Pick a value from the list.", "Not in the list"
            ws.add_data_validation(dv)
            dv.add(f"{col}2:{col}{n}")
    ws.freeze_panes = "D2"
    wb.save(path)


def main(src, out_dir, seed=5):
    os.makedirs(out_dir, exist_ok=True)
    threads = [json.loads(line) for line in open(src)]
    keep = [t for t in threads
            if any(k in (t["title"] + " " + t["op_text"]).lower() for k in CRASHY)
            and any((not r["is_op"]) and r["role"] in EXPERT for r in t["replies"])]
    rated = [t for t in keep if any(x["rating"] in ("crash_sw_hw", "crash_pilot") for x in t["in_index"])]
    rest = [t for t in keep if t not in rated]
    rng = random.Random(seed)
    rng.shuffle(rated)
    rng.shuffle(rest)
    rows = rated + rest
    for who in ("A", "B"):
        build(os.path.join(out_dir, f"forum_diagnosis_reviewer_{who}.xlsx"), rows)
    with open(os.path.join(out_dir, "forum_key_DO_NOT_OPEN.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["#", "topic_id", "url", "log_ids", "flight_review_ratings"])
        for i, t in enumerate(rows, 1):
            w.writerow([i, t["topic_id"], t["url"], " ".join(t["log_ids"]),
                        " ".join(f"{x['log_id']}:{x['rating'] or 'unrated'}" for x in t["in_index"])])
    print(f"{len(rows)} threads ({len(rated)} with a crash-rated log first); sheets in {out_dir}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
