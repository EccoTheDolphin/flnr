def assert_blob_eq(
    actual: str | bytes,
    expected: str | bytes,
    *,
    context: int = 64,
) -> None:
    if actual == expected:
        return

    if type(actual) is not type(expected):
        err_msg = (
            f"type mismatch: actual={type(actual).__name__}, "
            f"expected={type(expected).__name__}"
        )
        raise AssertionError(err_msg)

    limit = min(len(actual), len(expected))
    idx = 0
    while idx < limit and actual[idx] == expected[idx]:
        idx += 1

    start = max(0, idx - context)
    actual_end = min(len(actual), idx + context)
    expected_end = min(len(expected), idx + context)

    actual_chunk = actual[start:actual_end]
    expected_chunk = expected[start:expected_end]

    err_msg = (
        f"blob mismatch at index {idx}\n"
        f"actual length:   {len(actual)}\n"
        f"expected length: {len(expected)}\n"
        f"actual[{start}:{actual_end}]   = {actual_chunk!r}\n"
        f"expected[{start}:{expected_end}] = {expected_chunk!r}"
    )
    raise AssertionError(err_msg)
