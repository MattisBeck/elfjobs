import re

from django.conf import settings


def css():
    return (settings.BASE_DIR / "static" / "css" / "main.css").read_text()


def mobile_blocks():
    """Inhalt aller @media (max-width: 720px)-Blöcke, einfach hintereinander."""
    text = css()
    blocks = []
    for match in re.finditer(r"@media \(max-width: 720px\) \{", text):
        depth, i = 1, match.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        blocks.append(text[match.end():i])
    return "\n".join(blocks)


def test_link_buttons_are_real_boxes():
    # <a class="button"> bleibt sonst inline, dann greift min-height nicht (#97).
    rule = re.search(r"a\.button \{([^}]*)\}", css())

    assert rule
    assert "display: inline-flex" in rule.group(1)
    assert "text-decoration: none" in rule.group(1)


def test_buttons_are_44px_on_phones():
    # docs/design.md: Klickflächen auf dem Handy mindestens 44 px (#97).
    # Eigene Regel nur für .button, nicht z. B. „.filter-form .button“.
    rule = re.search(r"^\s*\.button \{([^}]*)\}", mobile_blocks(), re.MULTILINE)

    assert rule
    assert "min-height: 44px" in rule.group(1)


def test_email_field_looks_like_the_other_fields():
    assert '.form input[type="email"]' in css()
