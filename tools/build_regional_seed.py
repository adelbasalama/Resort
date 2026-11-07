"""Build the distributable, source-linked regional dataset. No API calls."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = "2026-11-07"
GWA = "https://www.gwa-online.de/service/abfallberatung/abfallentsorgung/"
EUV = "https://www.euv-stadtbetrieb.de/entsorgung-recycling/abfall-richtig-entsorgen/"
EDG = "https://www.edg.de/de/medien/pdf/download/abfallabc_2026.pdf?mtd=a"
USB = "https://www.usb-bochum.de/wp-content/uploads/2025/06/Trennen-leicht-gemacht_barrierefrei_DE.pdf"
WITTEN = "https://www.witten.de/medien/dokumente/abfallkalender_2026_web.pdf?20251210160510="
HEB = "https://www.heb-hagen.de/images/2024/PDF/HEB%20Abfall-Flyer_A5_komplett_WEB_Doppelseite.pdf"
WBL = "https://wbl.de/abfallentsorgung/abfalltrennung"
BATTERIES = "https://www.umweltbundesamt.de/umwelttipps-fuer-den-alltag/batterien-akkus-richtig-nutzen-fachgerecht"
DEPOSIT = "https://www.bundesumweltministerium.de/presse/fragen-und-antworten-faq/cluster/einweg-und-mehrweg"


def build():
    regions = []
    for key, name, url in [("dortmund", "Dortmund", EDG), ("bochum", "Bochum", USB),
                           ("hagen", "Hagen", HEB), ("witten", "Witten", WITTEN),
                           ("unna", "Unna", "https://www.stadtbetriebe-unna.de/entsorgung/biomuell"),
                           ("luenen", "Lünen", WBL), ("castrop-rauxel", "Castrop-Rauxel", EUV + "wertstoffe")]:
        regions.append(dict(id=key, name=name, source_url=url))
    rules = []
    sources = {}
    for region in regions:
        rid = region["id"]
        urls = {kind: region["source_url"] for kind in ["packaging", "paper", "bio", "residual", "glass"]}
        if rid == "dortmund":
            urls["bio"] = "https://www.edg.de/de/entsorgungsdienstleistungen/rein-damit/bioabfall.htm"
            urls["glass"] = EDG
        if rid == "bochum":
            urls["glass"] = "https://www.bochum.de/Umwelt--und-Gruenflaechenamt/Dienstleistungen-und-Infos/Abfallentsorgung"
        if rid == "hagen":
            urls["bio"] = "https://heb-hagen.de/rund-um-den-muell/standorte/abfallarten/kuechenabfaelle.html"
            urls["residual"] = "https://www.heb-hagen.de/einfache-sprache.html"
        if rid == "unna":
            urls = {kind: GWA + slug + "/" for kind, slug in
                    [("packaging", "wertstofftonne"), ("paper", "altpapier"), ("bio", "bioabfall"),
                     ("residual", "restmuell"), ("glass", "altglas")]}
        if rid == "castrop-rauxel":
            urls = {kind: EUV + slug for kind, slug in [("packaging", "wertstoffe"), ("paper", "altpapier"),
                    ("bio", "bioabfall"), ("residual", "restabfall"), ("glass", "altglas")]}
        packaging = "Gelbe Tonne / Gelber Sack (packaging)" if rid == "witten" else "Wertstofftonne (recycling bin)"
        bio = "Kitchen-waste collection at HEB Wertstoffhof" if rid == "hagen" else "Biotonne (organic waste)"
        def add(item, category, bin_label, prep, kind, condition="any", url=None):
            source = url or urls[kind]
            sources[source] = {"url": source, "checked_on": REVIEWED,
                               "review_method": "Official provider guidance; English paraphrase, not municipal endorsement."}
            rules.append(dict(region_id=rid, item_key=item, category=category, bin_label=bin_label,
                              preparation=prep, source_url=source, reviewed_on=REVIEWED,
                              condition=condition, version=1))
        for item in ["plastic_bottle", "plastic_container", "beverage_can"]:
            add(item, "recyclable", packaging, "Empty the packaging. Remove remaining contents.", "packaging")
        add("glass_bottle", "recyclable", "Altglascontainer (colour-separated glass)",
            "Empty it. Separate clear, brown and green container glass. No ceramic or drinking glasses.", "glass")
        for item in ["paper_bag", "cardboard", "newspaper"]:
            add(item, "recyclable", "Altpapiertonne (paper collection)", "Keep it dry; remove non-paper parts.", "paper", "clean")
            add(item, "landfill", "Restmülltonne (residual waste)", "Heavily food- or grease-soiled paper is unsuitable for paper recycling.", "residual", "soiled")
        for item in ["banana_peel", "coffee_grounds"]:
            add(item, "compostable", bio, "Remove packaging; no plastic or compostable-plastic bags.", "bio")
        for item in ["used_tissue", "diaper", "ceramic_cup"]:
            add(item, "landfill", "Restmülltonne (residual waste)", "Keep out of recycling containers.", "residual")
        add("battery", "special", "Battery take-back collection",
            "Never use household bins. Return household batteries to a suitable take-back point.", "residual", url=BATTERIES)
        # Deposit handling is selected using the user's answer, before ordinary bin lookup.
        for item in ["plastic_bottle", "beverage_can", "glass_bottle"]:
            add(item + "_deposit", "recyclable", "Pfandrückgabe (deposit return)",
                "Return the marked deposit container through its retailer return system.", "packaging", url=DEPOSIT)
    result = {"dataset_id": "ruhr-regions-2026-11-07-v1", "checked_on": REVIEWED,
              "scope": "Household quantities; supported item catalogue only. Not a complete Abfall-ABC.",
              "category_note": "landfill is the assignment's residual-waste reporting bucket, not a claim about treatment.",
              "regions": regions, "rules": rules, "sources": list(sources.values())}
    path = ROOT / "ai-coach/seeds/regional_rules.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(regions)} regions and {len(rules)} rules: {path}")


if __name__ == "__main__":
    build()
