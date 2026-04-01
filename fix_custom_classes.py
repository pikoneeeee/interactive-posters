"""Add CSS styles for all custom box classes in ch_6-ch_45"""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

# CSS to add for custom classes - will be inserted before </style>
# Uses the file's accent color variables pattern
CUSTOM_CSS = """
        /* Custom content boxes */
        .step-box, .calculation-box, .calc-box, .example-box, .example-card,
        .molecule-box, .formula-example, .sign-box, .reaction-box,
        .calculation-example, .oxide-box, .concept-box, .valency-box,
        .law-box, .formula-box, .heat-box, .process-box {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 1rem;
            padding: 1.25rem;
            margin: 0.75rem 0;
        }
        .step-box p, .calculation-box p, .calc-box p, .example-box p,
        .example-card p, .molecule-box p, .formula-example p, .sign-box p,
        .reaction-box p, .calculation-example p, .oxide-box p, .concept-box p,
        .valency-box p, .law-box p, .formula-box p, .heat-box p, .process-box p {
            margin-bottom: 0.35rem;
            line-height: 1.6;
        }"""

count = 0
for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()

    if ".step-box," in html:
        print(f"already fixed ch_{i}.html")
        continue

    # Insert before closing </style>
    marker = "\n    </style>"
    if marker in html:
        html = html.replace(marker, CUSTOM_CSS + marker, 1)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
        print(f"fixed ch_{i}.html")
    else:
        print(f"marker not found ch_{i}.html")

print(f"\nFixed {count} files")
