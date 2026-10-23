"""Shared word sequences between the manuscript and the abstracts of the cited arXiv papers.

This is a partial check, not a substitute for iThenticate/Crossref Similarity Check (which compares against
millions of documents). It catches accidental copying from the sources most likely to be paraphrased.

    python3 docs/paper/originality/check_originality.py
"""
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def manuscript():
    s = open(os.path.join(HERE, "..", "latex", "main.tex")).read().split("\\begin{document}")[1].split("\\bibliographystyle")[0]
    s = re.sub(r"%.*", "", s)
    s = re.sub(r"\\(cite|ref|label|includegraphics)\{[^}]*\}", " ", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", " ", s)
    return words(s)


def grams(ws, n):
    return {" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def main():
    m = manuscript()
    lines = ["# Originality check (partial)", "",
             f"Manuscript: {len(m)} words. Compared with the abstracts of the {len(glob.glob(os.path.join(HERE, 'abs_*.txt')))} "
             "cited arXiv papers (fetched from arxiv.org). A shared 8-word sequence would suggest copied wording; shared "
             "5-word sequences are usually technical phrases.", "",
             "| Source | Abstract words | Shared 5-word sequences | Shared 8-word sequences |", "|---|---|---|---|"]
    worst = []
    for f in sorted(glob.glob(os.path.join(HERE, "abs_*.txt"))):
        a = words(open(f).read())
        s5, s8 = grams(m, 5) & grams(a, 5), grams(m, 8) & grams(a, 8)
        lines.append(f"| arXiv:{os.path.basename(f)[4:-4]} | {len(a)} | {len(s5)} | {len(s8)} |")
        worst += sorted(s5)
    lines += ["", "Shared 5-word sequences found (all):", ""] + [f"- \"{w}\"" for w in worst] if worst else ["", "No shared 5-word sequences."]
    lines += ["", "Not covered: the full texts of the cited papers, journal articles without arXiv versions, and the wider "
              "literature. Run Crossref Similarity Check / iThenticate through the institution before submission; "
              "Elsevier also runs it on submission."]
    open(os.path.join(HERE, "..", "originality_check.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
