import pytest

from senere.utilities import count_distance


@pytest.mark.parametrize('pos0, pos1, result', [
    ([0, 0], [3, 4], '5.00'),
    ((2.2, 1.4), (5.0, 4.4), '4.10')
])
def test_count_distance(pos0, pos1, result):
    ret = count_distance(pos0, pos1)
    assert '{:.2f}'.format(ret) == result
