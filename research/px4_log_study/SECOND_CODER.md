# Second, independent coding of the forum crash threads (for Atharv)

**Why.** The expert conclusions and causes for 161 PX4 forum threads were recorded once, with AI assistance. A reviewer
will ask whether another person reading the same threads records the same thing. Agreement (Cohen's kappa) is the
answer, and it is the cheapest real improvement to the paper.

**Time.** About a day: 161 threads at 2–4 minutes each.

## What to do

1. Open `research/px4_log_study/forum_review/forum_diagnosis_reviewer_B.xlsx` (on the One Touch drive; it is not in
   git because it contains forum text). Read the **Instructions** tab first.
2. For each row in **Threads**, open the thread link and fill the drop-downs:
   *Is it a crash*, *Expert's conclusion*, *Cause the expert names*, *Who gave it*, *Did the poster confirm?*, and paste
   the sentence that gives the diagnosis.
3. You record what the **expert** concluded. You do not judge the crash yourself.
   - **The quote must be copied from that thread**: the exact sentence in which the expert gives the diagnosis.
     The scoring script checks every quote against its own thread and rejects quotes that are not found there or that
     are pasted into several rows. If the expert gives no diagnosis, leave the quote empty and choose
     *no diagnosis given* or *unclear*; that is a valid and common answer.
   - Expect a mix: in many threads the expert never commits to a cause. Do not choose *drone* unless the expert says
     the aircraft (hardware, tuning, firmware) caused it.
4. **Do not look at** `forum_review/forum_key_DO_NOT_OPEN.csv`, `results/px4_log_study/forum_expert_labels.csv` or
   `forum_expert_labels.md`, and do not discuss threads with Aditya until you have finished. That is what makes the
   check independent.
5. Save the sheet and send it back.

## Scoring (after the sheet is returned)

```bash
cd research
../.venv/bin/python px4_log_study/score_forum.py results/px4_log_study/forum_expert_labels.csv \
    px4_log_study/forum_review/forum_diagnosis_reviewer_B.xlsx px4_log_study/forum_review/forum_key_DO_NOT_OPEN.csv \
    results/px4_log_study/forum_agreement.md "/Volumes/One Touch/AeroFleet_px4_data/forum_cache"
```

Declared before the second coding (24 Oct 2026): the labels are reported as reliable if kappa is at least 0.60 for
the expert's conclusion and for the cause. Whatever the value, it goes into the paper (Section 3.3 and Threats to
validity). Threads where the two recordings disagree are listed, settled by discussion, and the analyses that use
the labels (Q4, Fig. 6, the troubleshooting knowledge base) are re-run on the settled labels.
