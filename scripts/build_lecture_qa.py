"""Render shared review questions into existing Markdown and HTML lectures."""

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNING = ROOT / "docs/learning"
START = "<!-- BEGIN GENERATED QA -->"
END = "<!-- END GENERATED QA -->"


def markdown(lecture: dict, intro: str, index: int) -> str:
    lines = ["## 一問一答と解説", "", intro, ""]
    lines.extend([f"![{lecture['figure_alt']}]({lecture['figure']})", ""])
    for number, item in enumerate(lecture["items"], 1):
        lines.extend(
            [
                f"### L{index}-Q{number:02d}",
                "",
                f"**問い：** {item['q']}",
                "",
                "<details>",
                "<summary>解答例と解説</summary>",
                "",
                f"**解答例：** {item['a']}",
                "",
                f"**解説：** {item['e']}",
                "",
            ]
        )
        if "formula" in item:
            lines.extend([f"> {item['formula']}", ""])
        if "source" in item:
            lines.extend([f"[出典・照合先]({item['source']})", ""])
        lines.extend(["</details>", ""])
    return "\n".join(lines).rstrip()


def browser(lecture: dict, intro: str, index: int) -> str:
    esc = html.escape
    lines = [
        '<section id="review-qa" class="review-qa">',
        "<h2>一問一答と解説</h2>",
        f"<p>{esc(intro)}</p>",
        '<figure><img src="'
        + esc(lecture["figure"])
        + '" alt="'
        + esc(lecture["figure_alt"])
        + '"></figure>',
    ]
    for number, item in enumerate(lecture["items"], 1):
        label = f"L{index}-Q{number:02d}"
        lines.extend(
            [
                f'<article class="qa-item" id="{label.lower()}">',
                f"<h3>{label}</h3><p><strong>問い：</strong>{esc(item['q'])}</p>",
                "<details><summary>解答例と解説</summary>",
                f"<p><strong>解答例：</strong>{esc(item['a'])}</p>",
                f"<p><strong>解説：</strong>{esc(item['e'])}</p>",
            ]
        )
        if "formula" in item:
            lines.append(f'<p class="formula">{esc(item["formula"])}</p>')
        if "source" in item:
            lines.append(f'<p><a href="{esc(item["source"])}">出典・照合先</a></p>')
        lines.append("</details></article>")
    lines.append("</section>")
    return "\n".join(lines)


def inject(text: str, content: str, suffix: str) -> str:
    block = START + "\n" + content + "\n" + END
    if START in text:
        assert text.count(START) == text.count(END) == 1
        before, rest = text.split(START)
        _, after = rest.split(END)
        return before + block + after
    if suffix == ".html":
        assert "<footer>" in text
        text = text.replace("</nav>", '<a href="#review-qa">一問一答と解説</a></nav>', 1)
        return text.replace("<footer>", block + "\n<footer>", 1)
    first, rest = text.split("\n", 1)
    return first + "\n\n[一問一答と解説](#一問一答と解説)\n" + rest.rstrip() + "\n\n" + block + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads((LEARNING / "assets/lecture-qa.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    stale = []
    for index, lecture in enumerate(data["lectures"], 1):
        for suffix, render in [(".md", markdown), (".html", browser)]:
            path = LEARNING / (lecture["stem"] + suffix)
            if not path.exists():  # Lecture 2 currently has only a Markdown edition.
                assert suffix == ".html" and lecture["stem"] == "02-design-comparison"
                continue
            text = path.read_text(encoding="utf-8")
            expected = inject(text, render(lecture, data["intro"], index), suffix)
            if text != expected:
                stale.append(path.relative_to(ROOT).as_posix())
                if not args.check:
                    path.write_text(expected, encoding="utf-8")
    if args.check and stale:
        raise SystemExit("Stale lecture Q&A: " + ", ".join(stale))
    counts = [len(lecture["items"]) for lecture in data["lectures"]]
    print(f"Lecture Q&A: {counts}, total {sum(counts)}; {'checked' if args.check else 'rendered'}")


if __name__ == "__main__":
    main()
