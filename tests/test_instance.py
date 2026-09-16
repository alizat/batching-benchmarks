import json
import logging
import os
import tempfile
import unittest

from batching_problem.definitions import (
    Article,
    Batch,
    Instance,
    Order,
    Parameters,
    WarehouseItem,
)

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


class FeasibilityChecks(unittest.TestCase):
    def test_an_honest_solution_is_feasible(self):
        instance, _, items, orders = two_items_of_one_article()
        instance.batches = [Batch(orders, [[items[0]], [items[1]]])]
        self.assertTrue(instance.check_feasibility())

    def test_one_item_serving_two_demands_is_rejected(self):
        instance, _, items, orders = two_items_of_one_article()
        instance.batches = [Batch(orders, [[items[0]], [items[0]]])]
        self.assertFalse(instance.check_feasibility())

    def test_an_item_outside_the_warehouse_is_rejected(self):
        instance, article, items, orders = two_items_of_one_article()
        invented = WarehouseItem("item-invented", 1, 1, article, "zone-0")
        instance.batches = [Batch(orders, [[items[0]], [invented]])]
        self.assertFalse(instance.check_feasibility())

    def test_an_order_in_two_batches_is_rejected(self):
        instance, _, items, orders = two_items_of_one_article()
        instance.batches = [
            Batch([orders[0]], [[items[0]]]),
            Batch([orders[0]], [[items[1]]]),
        ]
        self.assertFalse(instance.check_feasibility())


class WritingAnInstance(unittest.TestCase):
    def test_writing_leaves_the_instance_usable(self):
        instance, _, items, _ = two_items_of_one_article()
        with tempfile.TemporaryDirectory() as directory:
            instance.write(directory)
            self.assertIsInstance(items[0].article, Article)
            self.assertIsInstance(instance.orders[0].positions[0], Article)
            instance.write(directory)
            with open(os.path.join(directory, "warehouse_items.json")) as handle:
                written = json.load(handle)
        self.assertEqual(written[0]["article"], "article-0")

    def test_storing_results_leaves_the_batches_usable(self):
        instance, _, items, orders = two_items_of_one_article()
        instance.batches = [Batch(orders, [[items[0]], [items[1]]])]
        instance.stats = {}
        with tempfile.TemporaryDirectory() as directory:
            instance.store_result(directory)
            self.assertIsInstance(instance.batches[0].picklists[0][0], WarehouseItem)
            instance.store_result(directory)


if __name__ == "__main__":
    unittest.main()
