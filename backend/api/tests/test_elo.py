from app.game.elo import expected_score, updated_ratings


def test_equal_ratings_have_even_odds():
    assert expected_score(1200, 1200) == 0.5


def test_higher_rating_is_favoured():
    assert expected_score(1600, 1200) > 0.9


def test_win_gains_and_loss_loses_symmetrically():
    new_a, new_b = updated_ratings(1200, 1200, score_a=1.0, k=32)
    assert new_a == 1216  # +K/2 for beating an equal opponent
    assert new_b == 1184


def test_update_is_zero_sum():
    for ra, rb, sa in [(1200, 1200, 1.0), (1500, 1300, 0.0), (1000, 1800, 1.0)]:
        na, nb = updated_ratings(ra, rb, sa)
        assert (na + nb) == (ra + rb)  # rounding cancels for symmetric K


def test_upset_win_moves_more_points_than_expected_win():
    underdog_gain = updated_ratings(1000, 1600, 1.0)[0] - 1000
    favourite_gain = updated_ratings(1600, 1000, 1.0)[0] - 1600
    assert underdog_gain > favourite_gain
