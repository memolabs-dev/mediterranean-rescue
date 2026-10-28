"""Private Markdown reports: anomaly explanations and safe, redacted renderers."""

from .sheets_cells import load_contract

# Report texts. English is the default language; French is the first translation.
# Keys of EXPLANATIONS are anomaly codes and must exist in every language.
EXPLANATIONS = {
    "en": {
        "snapshot_too_large": "File above the byte limit; nothing was read.",
        "invalid_utf8": "Encoding is not UTF-8; nothing was read.",
        "nul_byte": "NUL byte in the file; nothing was read.",
        "quote_in_unquoted_field": "Quote inside a cell that is not quoted.",
        "text_after_closing_quote": "Text right after a closing quote.",
        "unterminated_quoted_field": "Quote never closed: the file was probably cut.",
        "invalid_csv": "Unreadable CSV structure at this point.",
        "missing_header": "Empty file, no header line.",
        "too_many_records": "More records than the limit; reading stopped, no candidate kept.",
        "too_many_columns": "A row has more cells than the limit; reading stopped, no candidate kept.",
        "duplicate_header": "Header present several times; columns cannot be mapped.",
        "unknown_column": "Column missing from the contract (drift or typo).",
        "missing_required_column": "Required column missing.",
        "optional_column_absent": "Optional contract column missing.",
        "column_order_differs_from_consumer": "Columns missing or in another order than the one the existing map reads by position.",
        "last_record_unterminated": "Last line has no line ending: the file may be cut, check against the source.",
        "decimal_comma_or_thousands": "Comma followed by three digits: decimal or thousands separator, to confirm.",
        "exact_duplicate_row": "Row identical to an earlier row; reported, never merged.",
        "extra_cells": "More cells than headers; row not normalized.",
        "missing_cells": "Fewer cells than headers; row not normalized.",
        "unnamed_column_has_value": "Column without header holding values (kept raw, outside the contract).",
        "hemisphere_missing": "Degrees and minutes without hemisphere, and no inference rule in the contract.",
        "hemisphere_ambiguous": "Without hemisphere, both readings fall inside the region: no position guessed.",
        "coordinate_outside_region": "Without hemisphere, no reading falls inside the contract region.",
        "hemisphere_inferred_from_region": "Hemisphere inferred from the contract region bounds (proposed rule, not validated).",
        "missing_date": "Date missing.",
        "invalid_date_format": "Date in an unexpected format.",
        "date_format_of_other_sheet": "Date in the other sheet's format; not converted.",
        "impossible_date": "Date that does not exist in the calendar.",
        "missing_kind": "Category missing.",
        "unknown_kind": "Category outside the contract; source value kept.",
        "negative_count": "Negative count.",
        "fractional_count": "Non-integer count.",
        "invalid_count": "Unreadable count.",
        "count_above_limit": "Count above the proposed limit.",
        "negative_decimal": "Negative measure.",
        "invalid_decimal": "Unreadable decimal measure.",
        "invalid_coordinate": "Unreadable coordinate.",
        "unsupported_coordinate_format": "Unsupported coordinate format; no conversion guessed.",
        "coordinate_axis_mismatch": "Hemisphere does not match the axis (N/S on longitude, E/W on latitude).",
        "coordinate_minutes_out_of_range": "Arc minutes equal to or above 60.",
        "coordinate_out_of_range": "Coordinate out of bounds, compared exactly before conversion.",
        "coordinate_pair_incomplete": "Only one of the two coordinates is known.",
        "coordinate_zero_zero": "Position 0,0: often a default value, to review.",
        "missing_position": "Unknown position; no replacement point.",
        "invalid_url": "Unreadable link.",
        "unsafe_url_scheme": "Link outside http/https refused.",
        "url_with_credentials": "Link holding credentials refused.",
        "empty_list_item": "Empty item in a semicolon-separated list.",
        "testimony_lists_misaligned": "Testimony lists of different lengths; no pair guessed.",
        "testimony_pair_incomplete": "Testimony without label or without link.",
        "subpopulation_exceeds_total": "Subpopulation above its total; to review, nothing is corrected.",
        "missing_required_value": "Required value missing.",
        "no_data_rows": "No data rows.",
    },
    "fr": {
        "snapshot_too_large": "Fichier au-delà de la limite d’octets ; rien n’a été lu.",
        "invalid_utf8": "Encodage différent d’UTF-8 ; rien n’a été lu.",
        "nul_byte": "Octet nul dans le fichier ; rien n’a été lu.",
        "quote_in_unquoted_field": "Guillemet au milieu d’une cellule non entourée de guillemets.",
        "text_after_closing_quote": "Texte collé après un guillemet fermant.",
        "unterminated_quoted_field": "Guillemet jamais refermé : fichier probablement interrompu.",
        "invalid_csv": "Structure CSV illisible à cet endroit.",
        "missing_header": "Fichier vide, sans ligne d’en-tête.",
        "too_many_records": "Plus d’enregistrements que la limite ; lecture arrêtée, aucun candidat gardé.",
        "too_many_columns": "Une ligne a plus de cases que la limite ; lecture arrêtée, aucun candidat gardé.",
        "duplicate_header": "En-tête présent plusieurs fois ; correspondance des colonnes impossible.",
        "unknown_column": "Colonne absente du contrat (dérive ou faute de frappe).",
        "missing_required_column": "Colonne obligatoire absente.",
        "optional_column_absent": "Colonne facultative du contrat absente.",
        "column_order_differs_from_consumer": "Colonnes absentes ou dans un autre ordre que celui lu par position dans la carte existante.",
        "last_record_unterminated": "Dernière ligne sans fin de ligne : fichier peut-être coupé, à vérifier contre la source.",
        "decimal_comma_or_thousands": "Virgule suivie de trois chiffres : décimale ou séparateur de milliers, à confirmer.",
        "exact_duplicate_row": "Ligne identique à une ligne précédente ; signalée, jamais fusionnée.",
        "extra_cells": "Plus de cellules que d’en-têtes ; ligne non normalisée.",
        "missing_cells": "Moins de cellules que d’en-têtes ; ligne non normalisée.",
        "unnamed_column_has_value": "Colonne sans en-tête contenant des valeurs (conservées brutes, hors contrat).",
        "hemisphere_missing": "Degrés et minutes sans hémisphère, et aucune règle d’inférence au contrat.",
        "hemisphere_ambiguous": "Sans hémisphère, les deux lectures tombent dans la région : aucune position devinée.",
        "coordinate_outside_region": "Sans hémisphère, aucune lecture ne tombe dans la région du contrat.",
        "hemisphere_inferred_from_region": "Hémisphère déduit des bornes de la région du contrat (règle proposée, non validée).",
        "missing_date": "Date absente.",
        "invalid_date_format": "Date dans un format inattendu.",
        "date_format_of_other_sheet": "Date au format de l’autre onglet ; non convertie.",
        "impossible_date": "Date qui n’existe pas au calendrier.",
        "missing_kind": "Catégorie absente.",
        "unknown_kind": "Catégorie hors contrat ; valeur source conservée.",
        "negative_count": "Effectif négatif.",
        "fractional_count": "Effectif non entier.",
        "invalid_count": "Effectif illisible.",
        "count_above_limit": "Effectif au-delà de la limite proposée.",
        "negative_decimal": "Mesure négative.",
        "invalid_decimal": "Mesure décimale illisible.",
        "invalid_coordinate": "Coordonnée illisible.",
        "unsupported_coordinate_format": "Format de coordonnée non pris en charge ; aucune conversion devinée.",
        "coordinate_axis_mismatch": "Hémisphère incompatible avec l’axe (N/S en longitude, E/W en latitude).",
        "coordinate_minutes_out_of_range": "Minutes d’arc égales ou supérieures à 60.",
        "coordinate_out_of_range": "Coordonnée hors des bornes, comparée exactement avant conversion.",
        "coordinate_pair_incomplete": "Une seule des deux coordonnées est connue.",
        "coordinate_zero_zero": "Position 0,0 : souvent une valeur par défaut, à revoir.",
        "missing_position": "Position inconnue ; aucun point de remplacement.",
        "invalid_url": "Lien illisible.",
        "unsafe_url_scheme": "Lien hors http/https refusé.",
        "url_with_credentials": "Lien contenant des identifiants refusé.",
        "empty_list_item": "Élément vide dans une liste séparée par des points-virgules.",
        "testimony_lists_misaligned": "Listes de témoignages de longueurs différentes ; aucune paire devinée.",
        "testimony_pair_incomplete": "Témoignage sans libellé ou sans lien.",
        "subpopulation_exceeds_total": "Sous-population supérieure à son total ; à revoir, rien n’est corrigé.",
        "missing_required_value": "Valeur obligatoire absente.",
        "no_data_rows": "Aucune ligne de données.",
    },
}

TEXT = {
    "en": {
        "title": "Diagnostic of sheet {sheet}",
        "synthetic": "> **Synthetic data.** Fictitious file written for tests: this report says nothing about the quality of the real dataset.",
        "unreviewed": "> **Unqualified source.** This diagnostic validates neither rights, nor the business contract, nor the facts.",
        "sha": "- Snapshot SHA-256: `{sha}` ({size} bytes, UTF-8 BOM: {bom})",
        "yes": "yes",
        "no": "no",
        "contract": "- Contract: `{version}` ({status})",
        "read": "- CSV reading: {text}",
        "normalization": "- Normalization: {text}",
        "identity": "- Identities: unresolved; a line number locates the snapshot, not an event",
        "publication": "- Publication: disabled; this tool creates no event and no draft",
        "counts_header": "| Records read | Rows diagnosed | Blank rows skipped | File errors | Rows with errors | Rows with warnings | Errors | Warnings |",
        "checks": "## Checks triggered",
        "checks_header": "| Code | Occurrences | Meaning |",
        "none": "none",
        "locations": "## Locations",
        "locations_note": "Physical start line in the snapshot; columns numbered from 1.",
        "locations_header": "| Level | Line | Column | Contract field | Code |",
        "file": "file",
        "truncated": "First {count} anomalies only; full list in diagnostic.json.",
        "limits": "## Limits",
        "limit_contract": "- The contract comes from the CartONG code and the export of 24 October 2026; it is not approved by the association.",
        "limit_hemisphere": "- A missing hemisphere is only inferred when a single reading falls inside the contract region; this rule is a proposal to validate.",
        "limit_units": "- Units, count definitions and unknown markers remain to be validated.",
        "limit_raw": "- Original cells are in `diagnostic.json` and `snapshot.csv`, both private.",
    },
    "fr": {
        "title": "Diagnostic de l’onglet {sheet}",
        "synthetic": "> **Données synthétiques.** Fichier fictif écrit pour les tests : ce rapport ne dit rien de la qualité du vrai jeu de données.",
        "unreviewed": "> **Source non qualifiée.** Ce diagnostic ne valide ni les droits, ni le contrat métier, ni les faits.",
        "sha": "- Empreinte SHA-256 du snapshot : `{sha}` ({size} octets, BOM UTF-8 : {bom})",
        "yes": "oui",
        "no": "non",
        "contract": "- Contrat : `{version}` ({status})",
        "read": "- Lecture du CSV : {text}",
        "normalization": "- Normalisation : {text}",
        "identity": "- Identités : non résolues ; un numéro de ligne localise le snapshot, pas un événement",
        "publication": "- Publication : désactivée ; cet outil ne crée ni événement ni brouillon",
        "counts_header": "| Enregistrements lus | Lignes diagnostiquées | Lignes vides ignorées | Erreurs de fichier | Lignes en erreur | Lignes avec avertissement | Erreurs | Avertissements |",
        "checks": "## Contrôles déclenchés",
        "checks_header": "| Code | Occurrences | Signification |",
        "none": "aucun",
        "locations": "## Localisation",
        "locations_note": "Ligne physique de début dans le snapshot ; colonne numérotée à partir de 1.",
        "locations_header": "| Niveau | Ligne | Colonne | Champ du contrat | Code |",
        "file": "fichier",
        "truncated": "{count} premières anomalies ; liste complète dans diagnostic.json.",
        "limits": "## Limites",
        "limit_contract": "- Le contrat vient du code CartONG et de l’export du 24 octobre 2026 ; il n’est pas approuvé par l’association.",
        "limit_hemisphere": "- L’hémisphère absent n’est déduit que si une seule lecture tombe dans la région du contrat ; cette règle est une proposition à valider.",
        "limit_units": "- Unités, définitions des compteurs et marqueurs d’inconnu restent à valider.",
        "limit_raw": "- Les cellules originales sont dans `diagnostic.json` et `snapshot.csv`, privés.",
    },
}

STATUS_TEXT = {
    "en": {
        "complete": "complete: the whole file was read and ends with a line ending",
        "end_unverified": "read to the last byte, but without a final line ending: a cut cannot be ruled out",
        "partial": "partial: reading stopped before the end, no candidate kept",
        "rejected": "rejected: the content was not read",
        "blocked": "blocked by at least one error",
        "needs_review": "no blocking error, human review required",
    },
    "fr": {
        "complete": "complète : tout le fichier a été lu et se termine par une fin de ligne",
        "end_unverified": "fichier lu jusqu’au dernier octet, mais sans fin de ligne finale : une coupure ne peut pas être exclue",
        "partial": "partielle : lecture arrêtée avant la fin, aucun candidat conservé",
        "rejected": "refusée : le contenu n’a pas été lu",
        "blocked": "bloquée par au moins une erreur",
        "needs_review": "sans erreur bloquante, revue humaine requise",
    },
}

LANGUAGES = tuple(TEXT)
DEFAULT_LANGUAGE = "en"
REPORT_LOCATIONS = 200


def render_report(result, contract=None, language=DEFAULT_LANGUAGE):
    """Readable private report: counts, contract field names and locations, no source value."""
    contract = contract or load_contract()
    text, status_text, explanations = TEXT[language], STATUS_TEXT[language], EXPLANATIONS[language]
    snapshot, status, counts = result["snapshot"], result["status"], result["counts"]
    fields = {c["name"] for c in contract["sheets"][snapshot["sheet"]]["columns"]}
    lines = [
        "# " + text["title"].format(sheet=snapshot["sheet"]),
        "",
        text["synthetic" if result["dataset_label"] == "synthetic" else "unreviewed"],
        "",
        text["sha"].format(
            sha=snapshot["sha256"],
            size=snapshot["bytes"],
            bom=text["yes" if snapshot["utf8_bom"] else "no"],
        ),
        text["contract"].format(
            version=result["contract"]["version"], status=result["contract"]["status"]
        ),
        text["read"].format(text=status_text[status["source_read"]]),
        text["normalization"].format(text=status_text[status["normalization"]]),
        text["identity"],
        text["publication"],
        "",
        text["counts_header"],
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {counts['records_read']} | {counts['rows_diagnosed']} | {counts['blank_rows_skipped']} "
        f"| {counts['file_errors']} | {counts['rows_with_errors']} | {counts['rows_with_warnings']} "
        f"| {counts['errors']} | {counts['warnings']} |",
        "",
        text["checks"],
        "",
        text["checks_header"],
        "| --- | ---: | --- |",
    ]
    for code, count in counts["issues_by_code"].items():
        lines.append(f"| `{code}` | {count} | {explanations.get(code, '')} |")
    if not counts["issues_by_code"]:
        lines.append(f"| {text['none']} | 0 | |")
    if result["issues"]:
        lines += [
            "",
            text["locations"],
            "",
            text["locations_note"],
            "",
            text["locations_header"],
            "| --- | ---: | ---: | --- | --- |",
        ]
        for item in result["issues"][:REPORT_LOCATIONS]:
            field = item["field"] if item["field"] in fields else ""
            line = item["line"] if item["line"] is not None else text["file"]
            column = item["column"] if item["column"] is not None else ""
            lines.append(f"| {item['severity']} | {line} | {column} | {field} | `{item['code']}` |")
        if len(result["issues"]) > REPORT_LOCATIONS:
            lines += ["", text["truncated"].format(count=REPORT_LOCATIONS)]
    lines += [
        "",
        text["limits"],
        "",
        text["limit_contract"],
        text["limit_hemisphere"],
        text["limit_units"],
        text["limit_raw"],
        "",
    ]
    return "\n".join(lines)


