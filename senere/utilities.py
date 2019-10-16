from enum import Enum
from itertools import product

import numpy as np


def count_distance(pos0, pos1):
    """Get distance between points with positions `pos0` and `pos1`.

    >>> count_distance([0,0], [3,4])
    5
    >>> print('%.2f'%count_distance((2.2, 1.4), (5.0, 4.4)))
    4.10
    """
    dx = pos1[0] - pos0[0]
    dy = pos1[1] - pos0[1]
    return (dx**2 + dy**2)**0.5


class GridArea:
    NONE = 0
    EMPTY = 1
    BUSY = 2
    OCCUPIED = 3

    @staticmethod
    def str_cell_type(ct):
        return {GridArea.NONE: 'NONE', GridArea.EMPTY: 'EMPTY',
                GridArea.BUSY: 'BUSY', GridArea.OCCUPIED: 'OCCUPIED'}[ct]

    def __init__(self, r_min, r_max, points=None):
        self.r_min, self.r_max = r_min, r_max
        if self.r_max - self.r_min < 1:
            raise ValueError('(r_max - r_min) must be >= 1')
        # Initialize the area:
        self._max_x, self._max_y = 0, 0
        self._num_empty_per_row = []
        self._num_empty = 0
        self._area = np.zeros((0, 0))
        self._points = []
        # Add points:
        for point in (points or []):
            self.add(point)

    @property
    def max_x(self):
        return self._max_x

    @property
    def max_y(self):
        return self._max_y

    @property
    def area(self):
        return self._area

    @property
    def points(self):
        return self._points

    @property
    def empty(self):
        return len(self._points) == 0

    def add_random_points(self, n=1):
        if self.empty:
            raise RuntimeError('can not add random points to empty GridArea')
        for _ in range(n):
            pos = self.get_random_empty_point()
            self.add(pos)

    def get_random_empty_point(self):
        if self._num_empty == 0:
            raise ValueError('no empty cells')
        n = np.random.randint(self._num_empty)
        cs = np.cumsum(self._num_empty_per_row)
        y = 0
        while cs[y] <= n:
            y += 1
        n -= cs[y - 1] if y > 0 else 0
        for x in range(self.max_x):
            if self._area[x][y] == GridArea.EMPTY:
                if n == 0:
                    return x, y
                n -= 1
        raise RuntimeError('empty cell not found!')

    def add(self, pos):
        x0, y0 = pos
        if x0 < 0 or y0 < 0:
            raise ValueError('negative coordinates disallowed')

        # Only first point may be added to NONE place:
        if len(self._points) > 0 and (x0 > self.max_x or y0 > self.max_y or
                                      self._area[x0][y0] != GridArea.EMPTY):
            raise ValueError(
                f'adding point to any cell except EMPTY is disallowed when'
                f'GridArea is not empty')

        # Resize the area if needed (checking is performed inside):
        max_x = max(x0 + self.r_max + 1, self.max_x)
        max_y = max(y0 + self.r_max + 1, self.max_y)
        self.resize(max_x, max_y)

        # Mark NONE points inside r_min circle as BUSY:
        square = product(range(max(0, x0 - self.r_min), x0 + self.r_min + 1),
                         range(max(0, y0 - self.r_min), y0 + self.r_min + 1))
        for x, y in square:
            # skip corner points out of the circle:
            if count_distance((x, y), (x0, y0)) > self.r_min:
                continue
            # no other points can be inside the busy area:
            ct = self._area[x][y]
            if ct == GridArea.OCCUPIED:
                raise ValueError(f'point {x0},{y0} is too close to occupied'
                                 f'point {x},{y}')
            # if a point was EMPTY, we need to de-count it:
            if ct == GridArea.EMPTY:
                self._num_empty_per_row[y] -= 1
                self._num_empty -= 1

            # all other points (inside circle, not occupied) are now busy:
            self._area[x][y] = GridArea.BUSY

        # After marking busy points, mark (x0, y0) as occupied. We don't
        # check whether this point was empty, since after the cycle
        # it is already marked as BUSY:
        self._area[x0][y0] = GridArea.OCCUPIED

        # Mark NONE points in a ring between r_min and r_max as EMPTY:
        square = product(range(max(0, x0 - self.r_max), x0 + self.r_max + 1),
                         range(max(0, y0 - self.r_max), y0 + self.r_max + 1))
        for x, y in square:
            distance = count_distance((x, y), (x0, y0))
            # Skip points not laying inside the ring:
            if not (self.r_min < distance <= self.r_max):
                continue
            # Inspect cell type, mark it as EMPTY if it was NONE:
            ct = self._area[x][y]
            if ct == GridArea.NONE:
                self._num_empty_per_row[y] += 1
                self._num_empty += 1
                self._area[x][y] = GridArea.EMPTY

        # Finally, add the point to the points list:
        self._points.append((x0, y0))

    def resize(self, max_x, max_y):
        if max_x < self._max_x or max_y < self._max_y:
            raise ValueError('area size can not be reduced')
        if max_x == self._max_x and max_y == self._max_y:
            return  # do nothing if no actual resize takes place

        # Create new area and copy old area into it:
        new_area = np.zeros((max_x, max_y))
        new_area[:self._max_x, :self._max_y] = self._area
        self._area = new_area

        # Extend num_empty_per_row:
        self._num_empty_per_row.extend([0] * (max_y - self._max_y))

        # Store new sizes:
        self._max_x = max_x
        self._max_y = max_y

    def __str__(self):
        return f'GridArea {self.max_x}x{self.max_y} with {len(self._points)} ' \
               f'points and {self._num_empty} empty places'
