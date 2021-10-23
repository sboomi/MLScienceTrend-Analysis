# Informations sur les formats de fichier

## PDF

Le PDF (Portable Document Format) est un format de fichier crée par Adobe, qui a pour but de standardiser un document et à formater le contenu de sorte à ce qu'une liseuse comme Adobe reader puisse les lire. Chaque PDF obéit à des règles de version et est découpé en plusieurs parties. Dans sa structure brute, il s'agit d'un mélange de texte et de bytes. La partie texte contient des instructions pour décoder les flux de bytes et organiser le document selon une certaine structure.

Bien qu'il soit compact, la structure interne n'est pas idéale pour extraire des informations. On pourrait y extraire du texte, mais la disposition en colonnes risquerait de fausser l'analyse. De plus, les techniques de collecte d'information PDF ne sont pas appropriées pour certains cas comme des tables ou des figures. Il faudrait donc passer par un OCR, ce qui demande davantage de temps par rapport à d'autres formats éventuellement disponibles.

## JSON

JSON (JavaScript Object Notation) est un format d'objet organisé tel un objet Javascript. Le JSON est un moyen allégé d’exprimer les données et peut être compris par n’importe quel langage de programmation.