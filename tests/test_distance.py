import math
import unittest
from collections import deque
from itertools import combinations_with_replacement

from batching_problem.definitions import Instance, Parameters, WarehouseItem


def make_instance(first_row=-50, last_row=50, first_aisle=-50, last_aisle=50):
    instance = Instance()
    instance.parameters = Parameters(
        first_row=first_row,
        last_row=last_row,
        first_aisle=first_aisle,
        last_aisle=last_aisle,
    )
    return instance


def item(row, aisle, zone="zone-0"):
    return WarehouseItem(f"item-{aisle}-{row}-{zone}", row, aisle, None, zone)


class SameAisleDistance(unittest.TestCase):
    def setUp(self):
        self.instance = make_instance()

    def test_same_side_walks_along_the_aisle(self):
        self.assertEqual(self.instance.distance(item(-4, 7), item(-7, 7)), 3)
        self.assertEqual(self.instance.distance(item(4, 3), item(9, 3)), 5)

    def test_opposite_sides_pass_the_middle_cross_aisle(self):
        self.assertEqual(self.instance.distance(item(-4, 7), item(7, 7)), 11)

    def test_co_located_items_are_at_distance_zero(self):
        for row, aisle in [(5, 7), (-7, 7), (30, -12), (1, 1), (49, 3)]:
            self.assertEqual(self.instance.distance(item(row, aisle), item(row, aisle)), 0)

    def test_deep_items_do_not_detour_around_the_end(self):
        self.assertEqual(self.instance.distance(item(48, 5), item(49, 5)), 1)


class DifferentAisleDistance(unittest.TestCase):
    def setUp(self):
        self.instance = make_instance()

    def test_middle_cross_aisle_is_used_when_it_is_shorter(self):
        self.assertEqual(self.instance.distance(item(-4, 7), item(-7, 9)), 13)

    def test_end_cross_aisle_is_used_when_it_is_shorter(self):
        self.assertEqual(self.instance.distance(item(48, 5), item(49, 6)), 4)

    def test_opposite_sides_must_pass_the_middle_cross_aisle(self):
        self.assertEqual(self.instance.distance(item(-30, 1), item(40, 2)), 71)

    def test_asymmetric_layout_uses_the_nearer_end(self):
        instance = make_instance(first_row=-10, last_row=100)
        self.assertEqual(instance.distance(item(-8, 1), item(-9, 3)), 5)


class DistanceIsAMetric(unittest.TestCase):
    """The paper's NP-hardness proof relies on d being a metric on the layout."""

    def setUp(self):
        self.instance = make_instance()
        self.locations = [(row, aisle) for aisle in range(-3, 4) for row in range(-9, 10) if row]

    def test_different_zones_are_unreachable(self):
        self.assertEqual(
            self.instance.distance(item(4, 7, "zone-0"), item(4, 7, "zone-1")), math.inf
        )

    def test_symmetric(self):
        for first, second in combinations_with_replacement(self.locations, 2):
            self.assertEqual(
                self.instance.distance(item(*first), item(*second)),
                self.instance.distance(item(*second), item(*first)),
            )

    def test_triangle_inequality(self):
        for first, second in combinations_with_replacement(self.locations, 2):
            direct = self.instance.distance(item(*first), item(*second))
            for middle in self.locations:
                detour = self.instance.distance(item(*first), item(*middle)) + self.instance.distance(
                    item(*middle), item(*second)
                )
                self.assertLessEqual(direct, detour)


class DistanceMatchesTheLayout(unittest.TestCase):
    """Every distance must be the shortest walk through the aisles and cross-aisles."""

    def shortest_walks(self, first_row, last_row, first_aisle, last_aisle, source):
        distances = {source: 0}
        queue = deque([source])
        while queue:
            aisle, row = queue.popleft()
            neighbours = []
            if row + 1 <= last_row:
                neighbours.append((aisle, row + 1))
            if row - 1 >= first_row:
                neighbours.append((aisle, row - 1))
            if row in (first_row, 0, last_row):
                if aisle + 1 <= last_aisle:
                    neighbours.append((aisle + 1, row))
                if aisle - 1 >= first_aisle:
                    neighbours.append((aisle - 1, row))
            for neighbour in neighbours:
                if neighbour not in distances:
                    distances[neighbour] = distances[(aisle, row)] + 1
                    queue.append(neighbour)
        return distances

    def assert_layout_matches(self, first_row, last_row, first_aisle, last_aisle):
        instance = make_instance(first_row, last_row, first_aisle, last_aisle)
        locations = [
            (aisle, row)
            for aisle in range(first_aisle, last_aisle + 1)
            for row in range(first_row + 1, last_row)
            if row
        ]
        for source in locations:
            walks = self.shortest_walks(first_row, last_row, first_aisle, last_aisle, source)
            for target in locations:
                self.assertEqual(
                    instance.distance(item(source[1], source[0]), item(target[1], target[0])),
                    walks[target],
                    f"{source} -> {target}",
                )

    def test_symmetric_layout(self):
        self.assert_layout_matches(-5, 5, -3, 3)

    def test_asymmetric_layout(self):
        self.assert_layout_matches(-4, 6, -2, 4)

    def test_one_sided_aisle_range(self):
        self.assert_layout_matches(-10, 3, 0, 5)


if __name__ == "__main__":
    unittest.main()
