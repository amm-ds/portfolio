"""Inline 5-customer Solomon-format instance shared by the test suite (no network)."""

TINY_INSTANCE = """
TINY

VEHICLE
NUMBER     CAPACITY
   5        60

CUSTOMER
CUST NO.  XCOORD.   YCOORD.    DEMAND   READY TIME  DUE DATE   SERVICE   TIME

    0      50         50          0          0        500          0
    1      52         50         10          0        200         10
    2      50         52         10         50        250         10
    3      48         50         10          0        300         10
    4      50         48         10         60        350         10
    5      54         54         10          0        500         10
"""
