import random as r
import os
import logging
import argparse

from batching_problem.generator import generate_instance

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

parameters = {
    "small": {
        "nbr_warehouse_items": 10_000,
        "nbr_orders": 500,
        "nbr_zones": 10,
    },
    "medium": {
        "nbr_warehouse_items": 100_000,
        "nbr_orders": 5_000,
        "nbr_zones": 50,
    },
    "large": {
        "nbr_warehouse_items": 1_000_000,
        "nbr_orders": 50_000,
        "nbr_zones": 100,
    },
}

parser = argparse.ArgumentParser()
parser.add_argument(
    "-n",
    "--nbr_instances",
    type=int,
    help="Number of instances per type",
    default=5,
)
parser.add_argument(
    "-t",
    "--instance-types",
    type=str,
    help="Directory for writing instances",
    nargs="+",
    default=parameters.keys(),
    choices=parameters.keys(),
)
parser.add_argument(
    "-d",
    "--dir",
    type=str,
    help="Directory for writing instances",
    default="instances",
)


if __name__ == "__main__":
    args = parser.parse_args()
    defaults = parser.parse_args([])
    if (
        set(args.instance_types) != set(defaults.instance_types)
        or args.nbr_instances != defaults.nbr_instances
    ):
        logger.warning(
            "Generating only part of the benchmark draws from a different point of "
            "the random stream, so these instances differ from the ones a full run "
            "produces. Run without -t and -n to reproduce the instances in "
            "instances.zip."
        )
    r.seed(1)
    os.makedirs(args.dir, exist_ok=True)
    for size in args.instance_types:
        for nbr in range(args.nbr_instances):
            path = f"{args.dir}/{size}-{nbr}"
            os.makedirs(path, exist_ok=True)
            generate_instance(path, parameters[size])
