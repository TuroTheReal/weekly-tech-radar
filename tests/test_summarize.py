"""Tests du post-processing du Tech Radar. Stdlib seule : python3 tests/test_summarize.py"""
import sys, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
# summarize importe anthropic au chargement, on n'en a pas besoin pour le post-processing
sys.modules.setdefault("anthropic", types.ModuleType("anthropic"))
import summarize as sz
import generate_html as gh

def article(title, category="DevOps", **kw):
    base = {"title": title, "title_fr": title, "summary_en": "x", "summary_fr": "x", "category": category}
    base.update(kw)
    return base

def test_title_keywords_ignore_ponctuation():
    # "Google," et "Google" doivent être le même mot
    assert "google" in sz.title_keywords("Google, Anthropic, OpenAI unveil cyber AI models")

def test_title_keywords_ignore_versions():
    # v1.37 est commun à toute une semaine de release, ce n'est pas un signal de doublon
    kw = sz.title_keywords("Kubernetes v1.37 graduates Rootless mode to Beta")
    assert "kubernetes" in kw and "v1.37" not in kw and "1.37" not in kw

def test_title_keywords_retire_stop_words():
    assert sz.title_keywords("A new tool for the cloud") == {"tool", "cloud"}

def test_title_actor():
    # la version fait partie de la clé, pour viser la série de release
    assert sz.title_actor("Kubernetes v1.37 graduates Rootless mode") == "kubernetes v1.37"
    assert sz.title_actor("Kubernetes disaster recovery from three scenarios") == "kubernetes"
    assert sz.title_actor("A predictive autoscaler provisions GPUs") == "predictive"
    assert sz.title_actor("") == ""

def test_vendor_cap_ne_touche_pas_aux_autres_sujets_du_produit():
    # Cas réel S37 : 4 articles sur la release v1.37 + 2 sujets Kubernetes sans
    # rapport. Seule la série de release doit être bornée.
    release = ["Kubernetes v1.37 Native Histograms graduates to Beta",
               "Kubernetes v1.37 Scheduler Preemption for in-place Pod Resize",
               "Kubernetes v1.37 Introducing Node Lifecycle Conditions",
               "Kubernetes v1.37 Advancing Workload-Aware Scheduling"]
    autres = ["Kubernetes disaster recovery from three failure scenarios",
              "Kubernetes access via identity provider as public client"]
    out = sz.post_process([article(t) for t in release + autres])
    gardes = [a['title'] for a in out]
    assert len(out) == sz.VENDOR_LIMIT + len(autres), f"obtenu {len(out)} : {gardes}"
    for t in autres:
        assert t in gardes, f"jeté à tort : {t}"

def test_dedup_conservatrice_pas_de_faux_positif():
    # Mesuré sur 542 titres publiés : 2 mots communs ne suffisent pas à conclure
    # au doublon. Ces deux là partagent "supply" et "chain", sujets différents.
    out = sz.post_process([
        article("Axios supply chain attack pulls malicious npm dependency", "Security"),
        article("Securing the open source supply chain across GitHub", "Security"),
    ])
    assert len(out) == 2, "faux positif : deux sujets distincts ont été fusionnés"

def test_dedup_attrape_un_vrai_doublon():
    out = sz.post_process([
        article("Kubernetes v1.37 moves DRA to GA", "DevOps"),
        article("Kubernetes v1.37 DRA reaches GA", "DevOps"),
    ])
    assert len(out) == 1, f"doublon non détecté : {[a['title'] for a in out]}"

def test_semaine_de_release_bornee_par_le_plafond_acteur():
    # Cas réel S37 : 4 features distinctes de la même release. La dédup ne doit pas
    # les confondre (c'est le plafond par acteur qui borne, pas la dédup).
    titles = ["Kubernetes v1.37 Native Histograms graduates to Beta",
              "Kubernetes v1.37 Scheduler Preemption for in-place Pod Resize",
              "Kubernetes v1.37 Introducing Node Lifecycle Conditions",
              "Kubernetes v1.37 Advancing Workload-Aware Scheduling"]
    out = sz.post_process([article(t) for t in titles])
    assert len(out) == sz.VENDOR_LIMIT, f"attendu {sz.VENDOR_LIMIT} (plafond acteur), obtenu {len(out)}"
    assert out[0]['title'].endswith("Beta"), "l'ordre d'origine doit être préservé"

def test_vendor_cap():
    titles = ["AWS adds cross-account EBS volume copy",
              "AWS DevOps Agent debugs DMS migration failures",
              "AWS Builder Center turns one",
              "AWS CloudFront outage serves errors instead of sites",
              "AWS opens a Paris local zone"]
    out = sz.post_process([article(t, "Cloud") for t in titles])
    assert len(out) == sz.VENDOR_LIMIT, f"attendu {sz.VENDOR_LIMIT}, obtenu {len(out)}"

def test_quota_categorie_toujours_applique():
    titles = ["Okta patches an SSO bypass", "Cloudflare blocks a record DDoS",
              "PaperCut flaws let attackers steal credentials", "OpenSSL freezes memory on tiny requests",
              "WordPress core allows unauthenticated code execution", "Fortinet warns of an exploited router bug"]
    out = sz.post_process([article(t, "Security") for t in titles])
    assert len(out) == sz.CATEGORY_LIMITS["Security"], f"attendu {sz.CATEGORY_LIMITS['Security']}, obtenu {len(out)}"

def test_check_lengths():
    ok = article("x" * sz.LENGTH_LIMITS["title"], title_fr="y" * sz.LENGTH_LIMITS["title_fr"])
    assert sz.check_lengths([ok]) == []
    trop_long = article("x" * (sz.LENGTH_LIMITS["title"] + 1))
    assert len(sz.check_lengths([trop_long])) == 1

def test_seo_title_tient_dans_le_budget():
    # le gabarit n'ajoute plus rien autour : ce que rend la fonction est ce que voit Google
    for lang, month in [("fr", "Septembre"), ("en", "September")]:
        for n in range(0, 7):
            t = gh.build_seo_title(37, month, 2026, ["Business", "Cloud", "DevOps", "Sécurité", "IA", "Tech"][:n], lang)
            assert len(t) <= gh.TITLE_BUDGET, f"{lang} {n} cats : {len(t)} > {gh.TITLE_BUDGET} | {t}"
            assert "37" in t

def test_seo_title_garde_des_categories():
    # sans le suffixe de marque, le budget doit loger au moins une catégorie : sinon les
    # 60 éditions ont le même titre à un numéro près, sans le moindre mot-clé.
    for lang, month in [("fr", "Septembre"), ("en", "September")]:
        t = gh.build_seo_title(37, month, 2026, ["Cloud", "DevOps", "Sécurité"], lang)
        assert "Cloud" in t, f"{lang} : aucune catégorie dans « {t} »"

def test_meta_description_tient_dans_le_budget():
    longs = ["Kubernetes v1.37 fait passer les histogrammes natifs en Beta"] * 4
    for lang in ("fr", "en"):
        d = gh.build_meta_description(37, longs, lang)
        assert len(d) <= gh.META_DESC_BUDGET, f"{lang} : {len(d)} > {gh.META_DESC_BUDGET}"
    assert gh.build_meta_description(37, [], "fr")  # pas de crash sans article

def test_meta_description_porte_son_prefixe():
    # Le préfixe vivait dans le gabarit, donc hors budget : les descriptions sortaient à
    # 175 signes pour un plafond annoncé de 155. La valeur rendue doit être complète.
    for lang, attendu in [("fr", "Tech Radar Semaine 37, "), ("en", "Tech Radar Week 37, ")]:
        d = gh.build_meta_description(37, ["Un titre d'article assez long pour compter"] * 4, lang)
        assert d.startswith(attendu), f"{lang} : préfixe absent de « {d[:40]} »"
        assert len(d) <= gh.META_DESC_BUDGET

class _FauxClient:
    """Client Anthropic bouchonné : rend un texte fixe et un stop_reason choisi."""
    def __init__(self, texte, stop_reason):
        self._reponse = types.SimpleNamespace(
            content=[types.SimpleNamespace(text=texte)], stop_reason=stop_reason)
        self.messages = self

    def create(self, **kwargs):
        return self._reponse

def test_ask_model_rend_le_texte():
    assert sz.ask_model(_FauxClient("[0, 1]", "end_turn"), "prompt", 4096) == "[0, 1]"

def test_ask_model_refuse_une_reponse_coupee():
    # stop_reason est le seul signal fiable de troncature : le JSON coupé reste parfois
    # parsable, et summarize_articles doit relancer plutôt que publier une édition amputée.
    try:
        sz.ask_model(_FauxClient('[{"title": "A"}, {"ti', "max_tokens"), "prompt", 16384)
    except ValueError:
        return
    assert False, "une réponse coupée par max_tokens doit lever"

def test_extract_json_fragment_dans_une_chaine_coupee_leve():
    # Un summary_en coupé en plein milieu peut contenir un fragment scalaire intact : le
    # scan ne doit pas le prendre pour la réponse.
    coupee = ('[{"title": "A", "category": "Cloud"}, '
              '{"title": "B", "summary_en": "See stats: [1, 2, 3] and more that never end')
    try:
        got = sz.extract_json(coupee)
    except ValueError:
        return
    assert False, f"fragment interne pris pour la réponse : {got!r}"

def test_extract_json_commentaire_apres_le_json():
    # Run du 2026-09-26 : dedup a renvoyé ses indices puis une explication qui recopie les
    # sources entre crochets. Borner la fin sur le dernier ] avalait cette explication.
    reponse = "[0, 2, 3]\n\nDuplicates removed:\n- [The Register] and [Ars Technica] cover the same event"
    assert sz.extract_json(reponse) == [0, 2, 3]

def test_extract_json_commentaire_avant_le_json():
    assert sz.extract_json("Here are the indices to keep:\n[0, 2, 3]") == [0, 2, 3]

def test_extract_json_crochets_parasites_avant_le_json():
    # des crochets dans la prose ne doivent pas être pris pour le début du JSON
    assert sz.extract_json("The [selected] indices:\n[0, 2, 3]") == [0, 2, 3]

def test_extract_json_bloc_markdown():
    assert sz.extract_json("```json\n[0, 2, 3]\n```") == [0, 2, 3]

def test_extract_json_bloc_markdown_non_ferme():
    # réponse coupée par max_tokens : la fence fermante manque, le JSON reste lisible
    assert sz.extract_json("```json\n[0, 2, 3]") == [0, 2, 3]

def test_extract_json_objets():
    # summarize renvoie des objets, pas des indices
    assert sz.extract_json('[{"title": "x"}]') == [{"title": "x"}]
    assert sz.extract_json('{"title": "x"}\nVoilà.') == {"title": "x"}

def test_extract_json_reponse_tronquee_leve():
    # summarize tourne près de max_tokens : une réponse coupée ouvre un tableau qui ne se
    # ferme jamais. Se rabattre sur le premier objet complet publierait une édition amputée
    # en silence, alors que lever laisse les 3 tentatives de summarize_articles relancer.
    coupees = ['[{"title": "A", "category": "Cloud"}, {"title": "B", "categ',
               '[{"title": "A"}, {"title": "B"}',
               '[{"title": "A"}, ']
    for coupee in coupees:
        try:
            got = sz.extract_json(coupee)
        except ValueError:
            continue
        assert False, f"réponse tronquée acceptée en silence : {got!r}"

def test_extract_json_prose_avec_crochets_seuls_leve():
    # que des sources entre crochets, aucun JSON : ne rien inventer
    try:
        sz.extract_json("See [The Register] and [Ars Technica] for details.")
    except ValueError:
        return
    assert False, "une réponse sans JSON doit lever"

def test_extract_json_sans_json_leve():
    try:
        sz.extract_json("I cannot help with that request.")
    except ValueError:
        return
    assert False, "une réponse sans JSON doit lever, pas renvoyer None"

if __name__ == "__main__":
    import io, contextlib
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # les fonctions loguent beaucoup
                fn()
            print(f"  ok   {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passent")
    sys.exit(1 if failed else 0)
