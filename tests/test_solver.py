import logging
import unittest

from batching_problem.definitions import (
    Article,
    Instance,
    Order,
    Parameters,
    WarehouseItem,
)
from distance_greedy_algorithm.solver import compute_picklists, greedy_solver

logging.disable(logging.WARNING)


def make_instance(articles, items, orders, **overrides):
    instance = Instance()
    settings = dict(
        min_number_requested_items=1,
        max_orders_per_batch=50,
        max_container_volume=1000,
        first_row=-50,
        last_row=50,
        first_aisle=-50,
        last_aisle=50,
    )
    settings.update(overrides)
    instance.parameters = Parameters(**settings)
    instance.articles = articles
    instance.warehouse_items = items
    instance.orders = orders
    instance.zones = sorted({item.zone for item in items})
    return instance


def two_items_of_one_article():
    article = Article("article-0", 10)
    items = [
        WarehouseItem("item-0", 4, 7, article, "zone-0"),
        WarehouseItem("item-1", 9, 7, article, "zone-0"),
    ]
    orders = [Order("order-0", [article]), Order("order-1", [article])]
    return make_instance([article], items, orders), article, items, orders


class PicklistPacking(unittest.TestCase):
    def test_an_item_larger_than_the_container_yields_no_empty_picklist(self):
        bulky = Article("article-bulky", 1500)
        small = Article("article-small", 10)
        items = [
            WarehouseItem("item-bulky", 4, 7, bulky, "zone-0"),
            WarehouseItem("item-small", 5, 7, small, "zone-0"),
        ]
        picklists = compute_picklists(items, 1000)
        self.assertNotIn([], picklists)
        self.assertEqual(sorted(len(p) for p in picklists), [1, 1])

    def test_items_are_packed_up_to_the_volume_limit(self):
        article = Article("article-0", 400)
        items = [
            WarehouseItem(f"item-{index}", index + 1, 1, article, "zone-0")
            for index in range(5)
        ]
        picklists = compute_picklists(items, 1000)
        self.assertEqual([len(p) for p in picklists], [2, 2, 1])
        for picklist in picklists:
            self.assertLessEqual(sum(i.article.volume for i in picklist), 1000)


class ImpossibleInstances(unittest.TestCase):
    def test_missing_supply_names_the_article(self):
        article = Article("article-0", 10)
        items = [WarehouseItem("item-0", 4, 7, article, "zone-0")]
        orders = [Order("order-0", [article, article])]
        instance = make_instance([article], items, orders)
        with self.assertRaises(ValueError) as caught:
            greedy_solver(instance)
        self.assertIn("article-0", str(caught.exception))

    def test_an_order_without_articles_is_reported(self):
        article = Article("article-0", 10)
        items = [WarehouseItem("item-0", 4, 7, article, "zone-0")]
        orders = [Order("order-empty", [])]
        instance = make_instance([article], items, orders)
        with self.assertRaises(ValueError) as caught:
            greedy_solver(instance)
        self.assertIn("order-empty", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
