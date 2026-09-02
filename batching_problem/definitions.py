import json
import math
from typing import List
import logging

import numpy as np

logger = logging.getLogger(__name__)


class InstanceEncoder(json.JSONEncoder):
    def default(self, o):
        if type(o) == WarehouseItem:
            ret = o.__dict__
            ret["article"] = o.article.id
            return ret
        elif type(o) == Order:
            ret = o.__dict__
            ret["positions"] = [pos.id for pos in o.positions]
            return ret
        elif type(o) == Batch:
            ret = o.__dict__
            ret["picklists"] = [
                [item.id for item in picklist] for picklist in o.picklists
            ]
            ret["orders"] = [order.id for order in o.orders]
        return o.__dict__


class Article:
    id: str
    volume: float

    def __init__(self, id, volume) -> None:
        self.id = id
        self.volume = volume


class WarehouseItem:
    id: str
    row: int
    aisle: int
    article: Article
    zone: str

    def __init__(self, id, row, aisle, article, zone) -> None:
        self.id = id
        self.row = row
        self.aisle = aisle
        self.article = article
        self.zone = zone

    def __lt__(self, other):
        return self.id < other.id


class Order:
    id: str
    positions: List[Article]

    def __init__(self, id, positions) -> None:
        self.id = id
        self.positions = positions


class Parameters:
    min_number_requested_items: int
    max_orders_per_batch: int
    max_container_volume: int
    first_row: int
    last_row: int
    first_aisle: int
    last_aisle: int

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Batch:
    picklists: List[List[WarehouseItem]]
    orders: List[Order]

    def __init__(self, orders, picklists):
        self.picklists = picklists
        self.orders = orders


def write_file_as_json(object_to_write, path):
    with open(path, "w") as f:
        f.write(json.dumps(object_to_write, indent=4, cls=InstanceEncoder))


class Instance:
    id: str
    articles: List[Article]
    orders: List[Order]
    warehouse_items: List[WarehouseItem]
    zones: List[str]
    parameters: Parameters
    batches: List[Batch]
    stats: dict

    def __init__(self) -> None:
        self.batches = []

    def write(self, directory):
        for object in ["articles", "warehouse_items", "orders", "parameters"]:
            write_file_as_json(
                self.__getattribute__(object), f"{directory}/{object}.json"
            )

    def store_result(self, path):
        write_file_as_json(self.batches, f"{path}/batches.json")
        write_file_as_json(self.stats, f"{path}/statistics.json")

    def read(self, path=None):
        if path is None:
            path = self.id
        with open(f"{path}/parameters.json", "r") as file:
            self.parameters = Parameters(**json.load(file))
        self.build_distance_matrix()

        with open(f"{path}/articles.json", "r") as file:
            self.articles = [Article(**a) for a in json.load(file)]

        articles_by_id = {a.id: a for a in self.articles}
        with open(f"{path}/orders.json", "r") as file:
            self.orders = [
                Order(
                    id=o["id"],
                    positions=[articles_by_id[pos] for pos in o["positions"]],
                )
                for o in json.load(file)
            ]

        with open(f"{path}/warehouse_items.json", "r") as file:
            self.warehouse_items = []
            for w in json.load(file):
                w["article"] = articles_by_id[w["article"]]
                self.warehouse_items.append(WarehouseItem(**w))

        self.zones = list(set(item.zone for item in self.warehouse_items))

    def check_feasibility(self) -> bool:
        if (
            sum(len(picklist) for batch in self.batches for picklist in batch.picklists)
            < self.parameters.min_number_requested_items
        ):
            logger.warning("Fewer items than requested")
            return False

        for batch in self.batches:
            if len(batch.orders) > self.parameters.max_orders_per_batch:
                logger.warning("Batch exceeds max commissions limit!")
                return False

            articles = [
                article.id for order in batch.orders for article in order.positions
            ]
            picklist_articles = [
                item.article.id for picklist in batch.picklists for item in picklist
            ]
            if sorted(articles) != sorted(picklist_articles):
                logger.warning(
                    "requested and assigned articles for some orders in this batch do not match!"
                )
                return False

            for picklist in batch.picklists:
                if len(set(item.zone for item in picklist)) > 1:
                    logger.warning("picklist contains items of multiple zones!")
                    return False
                if (
                    sum(item.article.volume for item in picklist)
                    > self.parameters.max_container_volume
                ):
                    logger.warning("Container volume exceeds limit")
                    return False
        return True

    @staticmethod
    def aisle_distance(u: int, v: int):
        return abs(u - v)

    def row_distance(self, u: int, v: int):
        middle_distance = abs(u) + abs(v)
        if min(u, v) < 0 < max(u, v):
            return middle_distance
        elif u < 0:
            return min(
                middle_distance, 2 * abs(self.parameters.first_row) - middle_distance
            )
        else:
            return min(middle_distance, 2 * self.parameters.last_row - middle_distance)

    def location_index(self, row: int, aisle: int) -> int:
        # Translates a (row, aisle) warehouse location into its flat index in
        # `distance_matrix`. Locations are laid out row-major, so all aisles
        # of one row occupy `nbr_aisles` consecutive indices.
        return (row - self.first_row) * self.nbr_aisles + (aisle - self.first_aisle)

    def build_distance_matrix(self) -> None:
        # Precomputes a location x location distance matrix covering every
        # (row, aisle) combination allowed by `parameters`. All zones share
        # the same row/aisle extent, so this single matrix is reused for
        # every zone instead of building one per zone.
        self.first_row = self.parameters.first_row
        self.first_aisle = self.parameters.first_aisle
        rows = list(range(self.first_row, self.parameters.last_row + 1))
        aisles = list(range(self.first_aisle, self.parameters.last_aisle + 1))
        self.nbr_aisles = len(aisles)
        self.nbr_locations = len(rows) * len(aisles)

        # Small (nbr_rows x nbr_rows / nbr_aisles x nbr_aisles) pairwise
        # matrices, built with the scalar formulas above so there remains a
        # single source of truth for the metric -- cheap even as plain
        # Python loops (~10k calls each for a 100x100 warehouse).
        row_dist = np.array(
            [[self.row_distance(u, v) for v in rows] for u in rows], dtype=np.int32
        )
        aisle_dist = np.array(
            [[self.aisle_distance(u, v) for v in aisles] for u in aisles], dtype=np.int32
        )

        # Full location-to-location matrix: full[r1,a1,r2,a2] =
        # row_dist[r1,r2] + aisle_dist[a1,a2], flattened row-major to match
        # location_index. This is the O((nbr_rows*nbr_aisles)^2) step, so it
        # stays vectorized in numpy rather than a Python double loop. The
        # result is then flattened into a plain Python list: `distance()` is
        # called millions of times per solve with one pair at a time, and a
        # flat list index beats numpy's per-call scalar-indexing overhead by
        # a wide margin at that call volume (see distance() below).
        n = self.nbr_locations
        combined = row_dist[:, None, :, None] + aisle_dist[None, :, None, :]
        self.distance_matrix = combined.reshape(n * n).astype(np.int16).tolist()

        logger.info(
            f"Built {n}x{n} location distance matrix "
            f"({n * n * 2 / 1e6:.1f} MB as int16)"
        )

    def distance(self, u: WarehouseItem, v: WarehouseItem):
        if u.zone != v.zone:
            return math.inf
        # Inlines location_index() for both endpoints rather than calling it:
        # distance() runs in the innermost loop of the solver (millions of
        # calls per solve), where the extra Python function-call/attribute
        # overhead of two method calls measurably outweighs the few extra
        # arithmetic ops -- keep this in sync with location_index() above.
        first_row, first_aisle = self.first_row, self.first_aisle
        nbr_aisles, n = self.nbr_aisles, self.nbr_locations
        i = (u.row - first_row) * nbr_aisles + (u.aisle - first_aisle)
        j = (v.row - first_row) * nbr_aisles + (v.aisle - first_aisle)
        return self.distance_matrix[i * n + j]

    def picklist_cost(self, picklist: List[WarehouseItem]) -> int:
        if len(picklist) == 0:
            return 0
        conveyor_belt = WarehouseItem("conveyor", 0, 0, None, picklist[0].zone)
        return (
            self.distance(conveyor_belt, picklist[0])
            + self.distance(picklist[-1], conveyor_belt)
            + sum(
                self.distance(picklist[i], picklist[i + 1])
                for i in range(len(picklist) - 1)
            )
        )

    def evaluate(self, time_elapsed):
        logger.info(f"Time elapsed: {time_elapsed}s")

        feasible = self.check_feasibility()
        if not feasible:
            logger.warning("instance not feasible")

        nbr_picklist_items = sum(
            len(p) for batch in self.batches for p in batch.picklists
        )
        logger.info(f"number of picklist items: {nbr_picklist_items}")

        nbr_picklists = sum(len(batch.picklists) for batch in self.batches)
        logger.info(f"number of picklists: {nbr_picklists}")

        objective_value = sum(
            self.picklist_cost(picklist)
            for batch in self.batches
            for picklist in batch.picklists
        )
        logger.info(f"total distance: {objective_value}")

        self.stats = dict(
            time_elapsed=time_elapsed,
            nbr_picklist_items=nbr_picklist_items,
            nbr_picklists=nbr_picklists,
            objective_value=objective_value,
            feasible=feasible,
        )
