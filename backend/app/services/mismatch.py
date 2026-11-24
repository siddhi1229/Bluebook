def calculate(issued: int, used: int, unused: int):
    returned = used + unused
    difference = issued - returned
    status = 'MATCHED' if difference == 0 else ('MISMATCH' if difference > 0 else 'EXCESS_RETURN')
    return returned, difference, status
