"""Score the current activity labels against the human review corrections in data/review_labels.json.

Usage: python -m analytics.evaluate
"""
import json
import sqlite3


def score(con, labels_path="data/review_labels.json", reel_path="data/review_reel.json", verbose=True):
    labels = json.load(open(labels_path))["labels"]
    start = {m["moment"]: m["t_sec"] for m in json.load(open(reel_path))}
    right = 0
    for lab in labels:
        s = start[lab["moment"]]
        row = con.execute("SELECT AVG(state='belt_work'), COUNT(*) FROM person_activity WHERE track_id=? AND t_sec>=? AND t_sec<?",
                          (lab["track"], s, s + 5)).fetchone()
        if not row[1]:
            got = "not_a_person"                      # track filtered out
        else:
            got = "unloading" if row[0] >= 0.5 else "not_unloading"
        ok = got == lab["expect"] or (lab["expect"] == "not_a_person" and got == "not_a_person")
        right += ok
        if verbose:
            print(f"  {'ok ' if ok else 'MISS'} moment {lab['moment']:>2} track {lab['track']:>3}: expected {lab['expect']}, got {got}  ({lab['note']})")
    if verbose:
        print(f"{right} of {len(labels)} reviewer corrections satisfied")
    return right, len(labels)


if __name__ == "__main__":
    score(sqlite3.connect("data/unloading.db"))
