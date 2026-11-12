from app.services.pdf_report import calculate_grid, density_warning


def test_grid_presets():
    assert calculate_grid(1) == (1, 1)
    assert calculate_grid(4) == (2, 2)
    assert calculate_grid(6) == (2, 3)
    assert calculate_grid(9) == (3, 3)
    assert calculate_grid(12) == (3, 4)
    assert calculate_grid(16) == (4, 4)
    assert calculate_grid(20) == (4, 5)


def test_grid_auto():
    cols, rows = calculate_grid(11)
    assert cols * rows >= 11


def test_density_warning():
    assert density_warning(4) is None
    assert density_warning(16) is not None
