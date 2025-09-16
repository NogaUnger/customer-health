from app.scoring import clamp

def test_clamp_limits():
    assert clamp(-10) == 0
    assert clamp(150) == 100
    assert clamp(42.5) == 42.5
