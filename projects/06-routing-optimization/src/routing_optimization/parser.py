"""Parser for the Solomon VRPTW text format.

Layout of a Solomon ``.txt`` file::

    C101                    <- instance name
    <blank>
    VEHICLE
    NUMBER     CAPACITY
      25         200        <- fleet size and vehicle capacity
    CUSTOMER
    CUST NO.  XCOORD. ...   <- column header
    <blank>
        0      40  50   0    0  1236   0   <- depot (id 0)
        1      45  68  10  912   967  90   <- customer: id x y demand ready due service
        ...

The parser is tolerant of blank lines, trailing whitespace and the split
``SERVICE   TIME`` header; only well-formed numeric rows become customers.
"""

from pathlib import Path

from routing_optimization.schemas import Customer, Problem

_N_CUSTOMER_FIELDS = 7


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def parse_solomon(text: str, name: str | None = None) -> Problem:
    """Parse Solomon-format instance text into a :class:`Problem`.

    Args:
        text: Full contents of a Solomon ``.txt`` instance file.
        name: Instance name override; defaults to the first non-blank line.

    Returns:
        The parsed problem with the depot as ``customers[0]``.

    Raises:
        ValueError: If the capacity line or any customer row is malformed.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty instance text")
    instance_name = name if name is not None else lines[0]

    veh_idx = next((i for i, ln in enumerate(lines) if ln.upper().startswith("NUMBER")), None)
    if veh_idx is None or veh_idx + 1 >= len(lines):
        raise ValueError("missing NUMBER/CAPACITY header in instance text")
    fleet = lines[veh_idx + 1].split()
    if len(fleet) < 2 or not all(_is_number(tok) for tok in fleet[:2]):
        raise ValueError(f"malformed fleet line: {lines[veh_idx + 1]!r}")
    max_vehicles, vehicle_capacity = int(fleet[0]), float(fleet[1])

    customers: list[Customer] = []
    for ln in lines[veh_idx + 2 :]:
        parts = ln.split()
        if len(parts) < _N_CUSTOMER_FIELDS or not all(
            _is_number(tok) for tok in parts[:_N_CUSTOMER_FIELDS]
        ):
            continue  # column header / section word / blank-equivalent line
        cid = int(parts[0])
        values = [float(tok) for tok in parts[1:_N_CUSTOMER_FIELDS]]
        x, y, demand, ready, due, service = values
        if demand.is_integer():
            demand = float(int(demand))
        customers.append(
            Customer(
                id=cid,
                x=x,
                y=y,
                demand=demand,
                ready_time=ready,
                due_time=due,
                service_time=service,
            )
        )

    if len(customers) < 2:
        raise ValueError(f"no customer rows parsed for {instance_name}")
    return Problem(
        name=instance_name,
        customers=customers,
        vehicle_capacity=vehicle_capacity,
        max_vehicles=max_vehicles,
    )


def parse_solomon_file(path: str | Path, name: str | None = None) -> Problem:
    """Parse a Solomon instance file; ``name`` defaults to the file stem."""
    p = Path(path)
    return parse_solomon(p.read_text(encoding="utf-8"), name=name or p.stem)
