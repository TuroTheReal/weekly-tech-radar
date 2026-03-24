import subprocess, json, sys, tempfile, os
from pathlib import Path
from datetime import datetime

PORTFOLIO_REPO = "https://github.com/TuroTheReal/Portfolio.git"
URL_WEBSITE = "https://arthur-portfolio.com"
SCRIPT_DIR = Path(__file__).parent

def load_enriched(year, week):
    path = SCRIPT_DIR.parent / "data" / str(year) / f"week-{week:02d}-enriched.json"
    with open(path, "r") as f:
        return json.load(f)

def clone_or_local(portfolio_arg=None):
    # En local : chemin direct vers le repo Portfolio
    if portfolio_arg and portfolio_arg.is_dir():
        return portfolio_arg
    # En CI (GitHub Actions) : clone avec authentification via PAT
    token = os.environ.get("GH_TOKEN")
    if token:
        clone_url = PORTFOLIO_REPO.replace("https://", f"https://x-access-token:{token}@")
    else:
        clone_url = PORTFOLIO_REPO
    tempfile_path = tempfile.mkdtemp()
    subprocess.run(["git", "clone", clone_url, tempfile_path], check=True)
    return Path(tempfile_path)

def run_generate(portfolio_path):
    subprocess.run(["python3", str(SCRIPT_DIR / "generate_html.py"), str(portfolio_path)], check=True)


def update_sitemap(portfolio_path, enriched):
    sitemap_path = portfolio_path / "sitemap.xml"
    with open(sitemap_path, "r") as f:
        content = f.read()

    week = enriched['week']
    year = enriched['year']
    filename = f"{year}-week-{week:02d}.html"

    # Vérifier si l'édition existe déjà dans le sitemap
    if filename in content:
        print(f"Sitemap: {filename} already present, skipping")
        return

    date_iso = enriched['date_end']
    en_url = f"{URL_WEBSITE}/en/tech-radar/{filename}"
    fr_url = f"{URL_WEBSITE}/fr/tech-radar/{filename}"

    # Deux blocs <url> : EN + FR, même pattern que le reste du sitemap
    new_entries = f"""
  <url>
    <loc>{en_url}</loc>
    <lastmod>{date_iso}</lastmod>
    <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>
    <xhtml:link rel="alternate" hreflang="fr" href="{fr_url}"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="{en_url}"/>
  </url>

  <url>
    <loc>{fr_url}</loc>
    <lastmod>{date_iso}</lastmod>
    <xhtml:link rel="alternate" hreflang="en" href="{en_url}"/>
    <xhtml:link rel="alternate" hreflang="fr" href="{fr_url}"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="{en_url}"/>
  </url>
"""

    # Insérer avant </urlset>
    content = content.replace("</urlset>", new_entries + "</urlset>")
    with open(sitemap_path, "w") as f:
        f.write(content)
    print(f"Sitemap: added {filename}")

def git_publish(portfolio_path, enriched):
    subprocess.run(["git", "checkout", "-B", f"radar/{enriched['year']}-week-{enriched['week']:02d}"], check=True, cwd=portfolio_path)
    subprocess.run(["git", "add", "."], check=True, cwd=portfolio_path)
    subprocess.run(["git", "commit", "-m", f"feat: Tech Radar {enriched['year']}-week-{enriched['week']:02d}"], check=True, cwd=portfolio_path)
    subprocess.run(["git", "push", "-u", "origin", f"radar/{enriched['year']}-week-{enriched['week']:02d}"], check=True, cwd=portfolio_path)


def create_pr(portfolio_path, enriched):
    subprocess.run(["gh", "pr", "create", "--title", f"Tech Radar {enriched['year']}-week-{enriched['week']:02d}", "--body", f"Add Tech Radar for {enriched['year']}-week-{enriched['week']:02d}", "--base", "main"], check=True, cwd=portfolio_path)

if __name__ == "__main__":
    # Arg 1 : chemin Portfolio (optionnel, sinon clone)
    # Arg 2 : numéro semaine (optionnel, sinon semaine courante)
    # Arg 3 : année (optionnel, sinon année courante)
    portfolio_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if len(sys.argv) > 2:
        week = int(sys.argv[2])
        year = int(sys.argv[3]) if len(sys.argv) > 3 else datetime.now().year
    else:
        year, week, _ = datetime.now().isocalendar()
    enriched = load_enriched(year, week)
    print(f"Loaded week {enriched['week']} ({len(enriched['articles'])} articles)")
    portfolio_path = clone_or_local(portfolio_arg)
    run_generate(portfolio_path)
    print("Generated HTML files")
    update_sitemap(portfolio_path, enriched)
    print("Updated sitemap")
    git_publish(portfolio_path, enriched)
    print("Pushed to GitHub")
    create_pr(portfolio_path, enriched)
    print("Created PR")