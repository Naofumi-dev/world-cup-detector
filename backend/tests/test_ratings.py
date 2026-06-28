"""Unit tests for the Elo engine with hand-computed expectations."""
import math

from app import ratings


def test_expected_score_even():
    assert ratings.expected_score(1500, 1500) == 0.5


def test_expected_score_400_point_gap():
    # A 400-point edge -> 1/(1+10^-1) = 10/11
    assert math.isclose(ratings.expected_score(1900, 1500), 10 / 11, rel_tol=1e-9)


def test_tournament_weight_keywords():
    assert ratings.tournament_weight("Friendly") == 20.0
    assert ratings.tournament_weight("FIFA World Cup") == 60.0
    # "qualification" is matched before the World Cup branch.
    assert ratings.tournament_weight("FIFA World Cup qualification") == 35.0
    assert ratings.tournament_weight("UEFA Euro") == 50.0
    assert ratings.tournament_weight("UEFA Nations League") == 40.0
    assert ratings.tournament_weight("Some Random Cup") == 30.0


def test_mov_multiplier():
    assert ratings.mov_multiplier(0) == 1.0
    assert ratings.mov_multiplier(1) == 1.0
    assert ratings.mov_multiplier(2) == 1.5
    assert ratings.mov_multiplier(3) == 1.75
    assert ratings.mov_multiplier(5) == 2.0  # 1.75 + 2/8


def test_update_ratings_home_win_is_zero_sum():
    new_home, new_away = ratings.update_ratings(
        1500, 1500, 1, 0, "Friendly", neutral=False
    )
    # K * (act - exp); home advantage shifts the expectation toward home.
    exp_home = ratings.expected_score(1565, 1500)
    assert math.isclose(new_home, 1500 + 20 * (1 - exp_home), rel_tol=1e-9)
    assert math.isclose(new_away, 1500 - 20 * (1 - exp_home), rel_tol=1e-9)
    # Equal K on both sides -> total rating is conserved.
    assert math.isclose(new_home + new_away, 3000.0, rel_tol=1e-12)


def test_neutral_removes_home_advantage():
    home_adv = ratings.update_ratings(1500, 1500, 1, 0, "Friendly", neutral=False)[0]
    neutral = ratings.update_ratings(1500, 1500, 1, 0, "Friendly", neutral=True)[0]
    # With no home boost, an even-rated home win earns more rating.
    assert neutral > home_adv


def test_bigger_win_moves_more():
    small = ratings.update_ratings(1500, 1500, 1, 0, "Friendly", neutral=True)[0]
    big = ratings.update_ratings(1500, 1500, 4, 0, "Friendly", neutral=True)[0]
    assert big > small
