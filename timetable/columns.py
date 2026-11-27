"""Überlappende Termine nebeneinander statt übereinander (#135), wie in einem Kalender.

Dieselbe Regel für „In meiner Woche“ (week.py) und das Stundenplan-Raster (views.py).
Blöcke, die sich (auch über einen dritten) überschneiden, bilden eine Gruppe. In der Gruppe
bekommt jeder Block die erste Spalte, in der gerade nichts liegt. Alle Blöcke der Gruppe
teilen sich die Breite durch die Zahl ihrer Spalten. Wer sich nur berührt (Ende = Anfang),
überschneidet sich nicht.
"""


def side_by_side(spans):
    """spans: Liste von (start, end) in Minuten. Gibt pro Eintrag in derselben Reihenfolge
    {"left", "width"} in Prozent der Tagesspalte zurück (Text mit Punkt, für CSS)."""
    columns = [0] * len(spans)
    counts = [1] * len(spans)
    group = []  # Indizes der aktuellen Gruppe
    column_ends = []  # Ende des letzten Blocks pro Spalte der Gruppe
    group_end = 0

    def close_group():
        for index in group:
            counts[index] = len(column_ends)

    # Nach Beginn, bei gleichem Beginn der längere zuerst (er bekommt die linke Spalte)
    for index in sorted(range(len(spans)), key=lambda i: (spans[i][0], -spans[i][1])):
        start, end = spans[index]
        if group and start >= group_end:
            close_group()
            group, column_ends, group_end = [], [], 0
        for column, column_end in enumerate(column_ends):
            if column_end <= start:
                break
        else:
            column = len(column_ends)
            column_ends.append(0)
        column_ends[column] = end
        columns[index] = column
        group.append(index)
        group_end = max(group_end, end)
    close_group()

    return [
        {"left": f"{column / count * 100:.4f}", "width": f"{100 / count:.4f}"}
        for column, count in zip(columns, counts)
    ]


def overlaps(span, other):
    """Überschneiden sich zwei (start, end)? Berühren zählt nicht."""
    return span[0] < other[1] and other[0] < span[1]
