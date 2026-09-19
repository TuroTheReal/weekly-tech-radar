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
    budget = gh.TITLE_BUDGET - len(gh.TITLE_SUFFIX)
    for lang, month in [("fr", "Septembre"), ("en", "September")]:
        for n in range(0, 7):
            t = gh.build_seo_title(37, month, 2026, ["Business", "Cloud", "DevOps", "Sécurité", "IA", "Tech"][:n], lang)
            assert len(t) <= budget, f"{lang} {n} cats : {len(t)} > {budget} | {t}"
            assert "37" in t

def test_meta_description_tient_dans_le_budget():
    longs = ["Kubernetes v1.37 fait passer les histogrammes natifs en Beta"] * 4
    for lang in ("fr", "en"):
        d = gh.build_meta_description(longs, lang)
        assert len(d) <= gh.META_DESC_BUDGET, f"{lang} : {len(d)} > {gh.META_DESC_BUDGET}"
    assert gh.build_meta_description([], "fr")  # pas de crash sans article

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
