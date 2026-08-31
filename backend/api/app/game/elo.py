"""Standard Elo rating update.

Kept as a pure function so it is trivially unit-testable and has no I/O.
"""


def expected_score(rating_a: int, rating_b: int) -> float:
    """Probability that A beats B under the logistic Elo model."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def updated_ratings(
    rating_a: int, rating_b: int, score_a: float, k: int = 32
) -> tuple[int, int]:
    """Return the new (rating_a, rating_b).

    score_a is A's result: 1.0 win, 0.0 loss, 0.5 draw. B's score is the complement,
    so the update is zero-sum and total rating is conserved (rounding aside).
    """
    exp_a = expected_score(rating_a, rating_b)
    exp_b = 1.0 - exp_a
    score_b = 1.0 - score_a

    new_a = rating_a + round(k * (score_a - exp_a))
    new_b = rating_b + round(k * (score_b - exp_b))
    return new_a, new_b
