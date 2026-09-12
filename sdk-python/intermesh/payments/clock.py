"""Le temps, en millisecondes entières — et pourquoi pas en secondes.

Les horodatages voyagent dans une charge utile signée, que Python et
JavaScript doivent sérialiser **octet pour octet à l'identique**. Or les
deux langages ne s'accordent pas sur les flottants ronds :

    Python      json.dumps({"t": 1788459123.0})  ->  {"t":1788459123.0}
    JavaScript  JSON.stringify({t: 1788459123.0}) ->  {"t":1788459123}

Une preuve signée côté Node serait donc refusée côté Python — mais
seulement quand l'horloge tombe pile sur une seconde ronde, soit environ
une fois sur un million. Assez rare pour passer tous les tests, assez
fréquent pour casser en production sans qu'on comprenne pourquoi.

Un entier se sérialise identiquement partout. La milliseconde est assez
fine pour des expirations de deux minutes, et reste exacte jusqu'en
l'an 287 000 dans un double JavaScript.
"""

from __future__ import annotations

import time


def now_ms() -> int:
    """Maintenant, en millisecondes entières depuis l'epoch."""
    return int(time.time() * 1000)


def seconds_to_ms(seconds: float) -> int:
    return int(seconds * 1000)
