#!/usr/bin/env python3
# ponytail: pull reviews, rebuttals, and decisions for each ICML 2026 spotlight
# paper via openreview-py. Saves per-paper JSON to data/reviews/<paper_id>.json
# with shape {paper_id, number, title, reviews: [...], rebuttals: [...],
# decision: ...}. Resume-safe: skips papers whose review file already exists.
import os, json, sys, time
from dotenv import load_dotenv
import openreview

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))
PAPERS = os.path.join(HERE, "data", "papers.json")
OUTDIR = os.path.join(HERE, "data", "reviews")


def val(field):
    return field.get("value") if isinstance(field, dict) else field


def login():
    for k in range(4):
        try:
            return openreview.api.OpenReviewClient(
                baseurl="https://api2.openreview.net",
                username=os.environ["EMAIL"],
                password=os.environ["PASSWORD"],
            )
        except openreview.openreview.OpenReviewException as e:
            if "RateLimit" in str(e):
                print("[rate-limit] login retry in 30s", file=sys.stderr)
                time.sleep(30)
            else:
                raise
    raise RuntimeError("login failed after 4 attempts")


def classify(note):
    """Return one of: 'review', 'rebuttal', 'decision', 'other'.
    Ponytail: use endswith on each invitation to avoid matching substring noise
    like .../Rebuttal_Acknowledgement (which is just an ack w/ empty comment)."""
    invs = note.invitations or []
    if any(i.endswith("/-/Decision") for i in invs):
        return "decision"
    if any(i.endswith("/-/Rebuttal") for i in invs):
        return "rebuttal"
    if any(i.endswith("/-/Official_Review") for i in invs):
        return "review"
    return "other"


def slim_review(n):
    c = n.content or {}
    return {
        "id": n.id,
        "invitations": n.invitations,
        "summary": val(c.get("summary")),
        "strengths_and_weaknesses": val(c.get("strengths_and_weaknesses")),
        "key_questions_for_authors": val(c.get("key_questions_for_authors")),
        "limitations": val(c.get("limitations")),
        "soundness": val(c.get("soundness")),
        "presentation": val(c.get("presentation")),
        "significance": val(c.get("significance")),
        "originality": val(c.get("originality")),
        "overall_recommendation": val(c.get("overall_recommendation")),
        "confidence": val(c.get("confidence")),
        "final_justification": val(c.get("final_justification")),
        "cdate": getattr(n, "cdate", None),
        "mdate": getattr(n, "mdate", None),
    }


def slim_rebuttal(n):
    c = n.content or {}
    return {
        "id": n.id,
        "invitations": n.invitations,
        "comment": val(c.get("comment")) or val(c.get("rebuttal")),
        "cdate": getattr(n, "cdate", None),
    }


def slim_decision(n):
    c = n.content or {}
    return {
        "id": n.id,
        "invitations": n.invitations,
        "decision": val(c.get("decision")),
        "comment": val(c.get("comment")),
        "cdate": getattr(n, "cdate", None),
    }


def main():
    papers = json.load(open(PAPERS))
    os.makedirs(OUTDIR, exist_ok=True)
    done = set(os.path.splitext(f)[0] for f in os.listdir(OUTDIR) if f.endswith(".json"))
    todo = [p for p in papers if p["id"] not in done]
    print(f"[resume] {len(done)} done, {len(todo)} to fetch", file=sys.stderr)
    c = login()
    written = 0
    for i, p in enumerate(todo, 1):
        try:
            notes = c.get_all_notes(forum=p["id"])
        except Exception as e:
            print(f"[err] {p['id']} ({p['number']}): {str(e)[:80]}", file=sys.stderr)
            time.sleep(2)
            continue
        reviews, rebuttals, decision = [], [], None
        for n in notes:
            k = classify(n)
            if k == "review":
                reviews.append(slim_review(n))
            elif k == "rebuttal":
                rebuttals.append(slim_rebuttal(n))
            elif k == "decision":
                decision = slim_decision(n)
        out = {
            "paper_id": p["id"],
            "number": p["number"],
            "title": p["title"],
            "reviews": reviews,
            "rebuttals": rebuttals,
            "decision": decision,
        }
        path = os.path.join(OUTDIR, f"{p['id']}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        written += 1
        if i % 25 == 0:
            print(f"[{i}/{len(todo)}] wrote {written}; last: {p['number']} "
                  f"reviews={len(reviews)} rebut={len(rebuttals)} dec={bool(decision)}",
                  file=sys.stderr)
    print(f"[done] wrote {written} review files -> {OUTDIR}", file=sys.stderr)


if __name__ == "__main__":
    main()