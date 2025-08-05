"""Computes Zipf scales from raw frequencies.

The Zipf scale is defined in the following paper:

Van Heuven, W. J. B., Mandera, P., Keuleers, E., and Brysbaert, M. 2014.
SUBTLEX-UK: A new and improved word frequency database for British English.
The Quarterly Journal of Experimental Psychology 67(6): 1176-1190.
"""

import math


def zipf_scale(count: int, total: int) -> float:
    """Computes Zipf scale.

    The authors use "add-one" or "Laplace" smoothing, which also requires us
    to track the number of word types. Since this is never motivated in the
    first place, we put it aside.

    We also correct an apparent mistake; the formula is given with "+ 3" as the
    adjustment but to match the values in the authors' table 1, it must be + 9.

    Args:
        count: frequency of the token.
        total: total size of the corpus.

    Returns:
        Zipf scale.
    """
    return math.log10(count) - math.log10(total) + 9.0 if count > 0 else 0
