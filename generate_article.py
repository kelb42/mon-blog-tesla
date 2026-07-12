"""
Génère un nouvel article de blog favorable à Tesla via l'API Claude,
et l'insère automatiquement dans index.html.

Utilisé par la GitHub Action .github/workflows/weekly-article.yml,
mais peut aussi être lancé manuellement :

    export ANTHROPIC_API_KEY=sk-ant-...
    python generate_article.py
"""

import json
import os
import re
import sys
from datetime import date

import anthropic

HTML_PATH = "index.html"
SITEMAP_PATH = "sitemap.xml"
ROBOTS_PATH = "robots.txt"
SOCIAL_DIR = "social_posts"

# URL réelle du site
SITE_URL = "https://kelb42.github.io/mon-blog-tesla"

# Sujets tournants : le script en pioche un nouveau à chaque exécution
# en évitant de répéter le dernier utilisé (stocké dans used_topics.json)
TOPICS = [
    "l'entretien d'une Tesla comparé à une voiture thermique",
    "le confort en hiver et la gestion du froid sur l'autonomie",
    "les road trips longue distance avec le réseau Supercharger",
    "la revente et la valeur résiduelle d'une Tesla d'occasion",
    "l'application mobile Tesla et ses fonctionnalités au quotidien",
    "la sécurité et les résultats aux crash-tests",
    "le coût réel sur un an comparé à une voiture essence équivalente",
    "les mises à jour logicielles et les nouvelles fonctions ajoutées",
    "le confort de conduite en ville avec une Model Y",
    "les options de personnalisation intérieure et extérieure",
]

USED_TOPICS_FILE = "used_topics.json"

SYSTEM_PROMPT = """Tu écris pour "Volt & Route", un blog personnel et sincère \
sur la vie quotidienne avec une Tesla Model Y. Le ton est chaleureux, concret, \
basé sur l'expérience réelle, jamais promotionnel à l'excès. Tu restes honnête \
et nuancé : tu peux mentionner un vrai inconvénient si c'est pertinent, \
l'objectif est la crédibilité, pas le survente.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans balises \
markdown, au format exact suivant :

{
  "title": "Titre de l'article (accrocheur, 6-10 mots)",
  "teaser": "Une phrase d'accroche de 15-25 mots pour la liste d'articles",
  "tag": "Un mot ou deux, ex: Expérience / Coûts / Technologie / Entretien",
  "paragraphs": ["Paragraphe 1...", "Paragraphe 2...", "Paragraphe 3..."]
}

3 à 4 paragraphes, 60-100 mots chacun, en français. Le dernier paragraphe peut \
mentionner naturellement, sans lourdeur, l'intérêt du programme de parrainage \
Tesla pour économiser sur la recharge."""


def pick_topic():
    used = []
    if os.path.exists(USED_TOPICS_FILE):
        with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
            used = json.load(f)
    remaining = [t for t in TOPICS if t not in used]
    if not remaining:
        remaining = TOPICS
        used = []
    topic = remaining[0]
    used.append(topic)
    with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2)
    return topic


def generate_article(topic):
    client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY depuis l'environnement
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Écris un article sur : {topic}"}
        ],
    )
    text = message.content[0].text.strip()
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def build_article_html(article):
    today = date.today()
    mois_fr = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
               "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    date_str = f"{today.day:02d} {mois_fr[today.month - 1]}<br>{today.year}"

    paragraphs_html = "\n          ".join(
        f"<p>{p}</p>" for p in article["paragraphs"]
    )

    return f"""
    <article class="article-card">
      <div class="date">{date_str}</div>
      <div>
        <h2>{article['title']}</h2>
        <p>{article['teaser']}</p>
        <span class="tag">{article['tag']}</span>
        <button class="toggle" onclick="toggleArticle(this)">Lire l'article</button>
        <div class="article-full">
          {paragraphs_html}
        </div>
      </div>
    </article>
"""


def insert_into_html(article_html):
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    marker = '<div class="articles">'
    idx = html.find(marker)
    if idx == -1:
        raise RuntimeError(f"Marqueur {marker!r} introuvable dans {HTML_PATH}")

    insert_at = idx + len(marker)
    new_html = html[:insert_at] + article_html + html[insert_at:]

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)


def update_sitemap():
    """Génère/actualise un sitemap.xml minimal pointant vers la page d'accueil.
    Le site étant une page unique, une seule URL suffit ; sa date de
    dernière modification est mise à jour à chaque nouvel article, ce qui
    aide Google à comprendre que le contenu a changé."""
    today = date.today().isoformat()
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
  </url>
</urlset>
"""
    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(sitemap)


def ensure_robots_txt():
    """Crée robots.txt s'il n'existe pas encore, avec un renvoi vers le sitemap."""
    if os.path.exists(ROBOTS_PATH):
        return
    content = f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    with open(ROBOTS_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def write_social_post(article):
    """Écrit un texte prêt à copier-coller pour X/Instagram dans social_posts/,
    à valider et publier manuellement (ou via Buffer/Later)."""
    os.makedirs(SOCIAL_DIR, exist_ok=True)
    today = date.today().isoformat()
    filename = os.path.join(SOCIAL_DIR, f"{today}.txt")

    post = (
        f"⚡ Nouvel article sur Volt & Route : {article['title']}\n\n"
        f"{article['teaser']}\n\n"
        f"À lire ici : {SITE_URL}\n"
        f"(lien de parrainage Tesla dispo sur le site 🚗)\n\n"
        f"#Tesla #ModelY #VoitureElectrique"
    )

    with open(filename, "w", encoding="utf-8") as f:
        f.write(post)

    print(f"Post réseaux sociaux écrit dans {filename}")


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY manquant dans l'environnement.", file=sys.stderr)
        sys.exit(1)

    topic = pick_topic()
    print(f"Sujet choisi : {topic}")

    article = generate_article(topic)
    print(f"Article généré : {article['title']}")

    html_block = build_article_html(article)
    insert_into_html(html_block)
    print("index.html mis à jour.")

    update_sitemap()
    ensure_robots_txt()
    write_social_post(article)
    print("sitemap.xml, robots.txt et post réseaux sociaux mis à jour.")


if __name__ == "__main__":
    main()
